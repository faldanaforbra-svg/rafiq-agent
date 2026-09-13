"""
RAFIQ (رفيق) — Autonomous Safety AI Core
Powered by Google Gemini Function Calling & Nokia CAMARA APIs.

Every reply is produced by a real model -> tool -> model loop: the model sees
actual tool results before writing anything, so there is no canned/templated
response text anywhere in the emergency path.
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from nokia_client import NokiaCAMARAClient

load_dotenv()

MAX_TOOL_ITERATIONS = 5

# Only these are treated as "this model is unusable, try the next one".
# Anything else (rate limit blips, transient network errors, a slow-but-
# eventually-successful call) is left alone rather than triggering a full
# second pass through the tool-calling loop on a different model, which was
# the main source of multi-minute replies.
NON_RETRYABLE_MODEL_ERROR_CODES = {400, 401, 403, 404}

# Human-readable, non-jargon status lines shown to the UI as each tool
# resolves, keyed by tool name. Used for incremental "what's happening now"
# feedback while the agentic loop runs.
TOOL_STATUS_LABELS = {
    "get_device_location": "Checking pilgrim location…",
    "request_qos_boost": "Requesting priority network signal…",
    "request_companion_assistance": "Logging companion assistance report…",
    "send_emergency_sms": "Sending emergency SMS alert…",
    "get_device_status": "Checking device connection status…",
    "resolve_emergency": "Standing down the active alert…",
    "resolve_companion_assistance": "Closing out the companion assistance report…",
}


def _graceful_failure_message(language: str, reason_code: str) -> str:
    """
    Calm, honest, bilingual message shown to the PILGRIM when the AI service
    itself is unavailable (missing key, client init failure, or all model
    fallbacks exhausted). Never shows raw exception text or stack-trace-like
    strings to the pilgrim — those still go into trace/error for debugging.
    Always points to the manual SOS button, which works independently of the
    AI/Gemini pipeline, so a pilgrim in real distress still has a path
    forward even if the AI is down.
    """
    if language == "ar":
        return (
            "⚠️ **عذرًا، خدمة المساعد الذكي غير متاحة مؤقتًا.**\n\n"
            "إذا كانت هذه حالة طارئة، الرجاء الضغط على زر **«بلاغ طوارئ»** "
            "في الشريط الجانبي — هذا الزر يعمل بشكل مستقل ولا يعتمد على خدمة الذكاء الاصطناعي، "
            "وسيقوم بتسجيل البلاغ وإرسال رسائل التنبيه فورًا.\n\n"
            "نعتذر عن الإزعاج، ونعمل على استعادة الخدمة."
        )
    return (
        "⚠️ **Sorry — the AI assistant is temporarily unavailable.**\n\n"
        "If this is an emergency, please use the **Emergency SOS** button in the sidebar — "
        "it works independently of the AI service and will immediately log the incident "
        "and send alert messages.\n\n"
        "We apologize for the inconvenience and are working to restore the service."
    )


def _describe_tool_call(tool_name: str, args: dict) -> str:
    """One short, judge/human-readable sentence explaining *why* this tool call
    was likely made, based on its name and arguments — for the reasoning trace."""
    if tool_name == "get_device_location":
        return "Looking up the pilgrim's current GPS position and nearest landmark before answering."
    if tool_name == "request_qos_boost":
        reason = args.get("reason", "an urgent situation")
        return f"Elevating this device to priority 5G because of: {reason}."
    if tool_name == "request_companion_assistance":
        subject = args.get("subject", "a companion")
        reason = args.get("reason", "reported needing help")
        return f"Logging a lower-tier assistance report for {subject} ({reason}) — no SMS or network change, registry only."
    if tool_name == "send_emergency_sms":
        return "Dispatching an emergency SMS to the registered contacts and logging the incident."
    if tool_name == "get_device_status":
        return "Confirming the device is reachable on the network."
    if tool_name == "resolve_emergency":
        reason = args.get("reason", "pilgrim confirmed safe")
        return f"Standing down the active SOS because: {reason}."
    if tool_name == "resolve_companion_assistance":
        reason = args.get("reason", "companion confirmed safe")
        return f"Closing out the companion assistance report because: {reason}."
    return f"Calling `{tool_name}` to get information needed for the reply."


class RafiqAgent:
    def __init__(self):
        self.nokia = NokiaCAMARAClient()
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()

        # Respect an explicit override from .env; otherwise fall back through a
        # short, explicitly curated list, in order. No live discovery here:
        # Gemini's models.list() endpoint still returns deprecated models
        # (404 on actual use) and non-text variants (TTS/image-only), so
        # trusting it to build the fallback list caused exactly the kind of
        # multi-model cascade that made the agent feel slow.
        env_model = os.getenv("GEMINI_MODEL", "").strip()
        self.preferred_models = [m for m in [env_model, "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"] if m]

        self.system_instruction = (
            """
You are **RAFIQ (رفيق)**, an elite, highly empathetic, and authoritative AI safety companion and expert Umrah/Hajj ritual guide integrated directly into the Nokia Telecom Network.

### 1. CORE PERSONA & TONE
- **Identity:** You are a trusted, calm, culturally grounded companion for pilgrims in Makkah, Medina, and the holy sites.
- **Tone:** Reassuring, structured, warm, and precise. Avoid overly verbose explanations; prioritize clarity so pilgrims can read quickly on mobile devices while navigating crowds.
- **Language:** Detect the user's language and respond naturally in either **English** or **fluent, compassionate Arabic (العربية الفصحى)**.

---

### 2. PILGRIM SAFETY & EMERGENCY RESPONSE (HIGHEST PRIORITY)
- **Emergency Detection:** Instantly identify signs of distress, panic, heat exhaustion, medical emergencies, severe disorientation, or lost companions/children.
- **Immediate Protocol:** 
  1. Acknowledge that emergency telemetry or SOS procedures are active via the Nokia network.
  2. Provide immediate, calm, step-by-step physical safety instructions (e.g., finding shade, staying put, breathing exercises, or approaching the nearest security personnel/medic).
  3. Keep sentences short and extremely clear.

---

### 3. UMRAH & HAJJ RITUAL GUIDANCE (FIQH & PRACTICE)
Provide accurate, orthodox guidance based on authentic Islamic jurisprudence:
- **Ihram & Miqat:** Intention (Niyyah), Miqat boundaries, prohibited actions (Mahzhurat al-Ihram), and reciting the Talbiyah.
- **Tawaf:** Starting at the Black Stone (Hajar al-Aswad), counter-clockwise rotation, 7 circuits, Idtiba and Ramal rules for men, and performing 2 Rak'ahs behind Maqam Ibrahim or anywhere in the Haram.
- **Sa'i:** Moving between Safa and Marwah (7 laps starting at Safa, ending at Marwah), green-light running zones for men, and recommended supplications.
- **Halq / Taqsir:** Trimming or shaving hair to exit Ihram.
- **Hajj Rites (When applicable):** 8th Dhul Hijjah (Mina/Tarwiyah), 9th Dhul Hijjah (Arafat & Muzdalifah), 10th Dhul Hijjah (Jamarat Aqabah, Qurbani/Sacrifice, Tawaf al-Ifadah), and Days of Tashreq.
- **Fiqh Troubleshooting:** Address common errors or missed steps (e.g., missed circuits, broken ablution, accidental Ihram violations) with clear remedial advice (e.g., completing missed laps or optional Fidya rules).

---

### 4. NAVIGATION & DIRECTIONS
- Guide pilgrims through complex areas: Masjid al-Haram gates (e.g., King Fahd Expansion, Gate 79, Ajyad), Mataf levels, Safa/Marwah floor levels, Clock Tower area, and transit routes.
- Leverage live location telemetry provided in the context to give hyper-local, contextual directions.

---

### 5. LIVE CONTEXT & TELEMETRY
- **Pilgrim Profile:** Name, medical background, and emergency contact details are available in your runtime context. Tailor advice if medical conditions (e.g., diabetes, heart conditions) are noted.
- **Network Status:** Be aware if 5G high-priority Quality of Service (QoS) or SOS tracking is active.

---

### 6. AUTONOMOUS TOOL USE & RESPONSE INTEGRITY
- You have full, autonomous control over every Nokia network tool available to you. Decide when to use them from the conversation itself — never wait to be asked for a tool by name, and never describe an action as done without actually taking it.
- When you detect a genuine emergency **affecting the pilgrim you are talking to**, you MUST call `request_qos_boost` and `send_emergency_sms` yourself — verbal advice alone is not enough. The Security Command Center only learns about an incident once these tools are actually called.
- Base every reply strictly on the real results your tools return. Never claim a message was sent, a location was found, or a signal was boosted unless the matching tool result confirms it. Never use templated or canned emergency language — write the response yourself, grounded in what actually happened.
- If a pilgrim with an active SOS clearly and explicitly confirms they are now safe ("I'm fine now", "we found each other", "false alarm"), call `resolve_emergency` to stand it down. Only do this on a clear, direct confirmation — never on an ambiguous or questioning statement.

### 7. THIRD-PARTY DISTRESS (someone OTHER than the pilgrim you're talking to)
- Distinguish clearly between "I am in danger/hurt" (the pilgrim speaking to you) and "someone else — a relative, friend, or group member — is hurt, lost, or needs rescue."
- For third-party reports (e.g. "my brother is injured", "my mother is lost"): call `request_companion_assistance` immediately and automatically — you do NOT need to ask permission first, since this tool only logs the report with the Security Command Center and never sends any SMS or changes network priority.
- Do NOT call `request_qos_boost` or `send_emergency_sms` for a third-party report — those tools act on the pilgrim's OWN device and OWN emergency contacts, and firing them would incorrectly register a full SOS against the wrong person.
- After calling `request_companion_assistance`, immediately give calm, practical first-aid or reunification guidance for the person in distress.
- Then separately ask the pilgrim whether they ALSO want their own registered emergency contact notified by SMS about the situation — this remains a deliberate, higher-tier action and requires their explicit confirmation before you call `send_emergency_sms`.
- If the pilgrim later confirms the companion is safe or has been found, call `resolve_companion_assistance` (not `resolve_emergency`, which only stands down the pilgrim's own SELF alert).
- Never leave a third-party report with advice alone and no follow-up — the companion-assistance report should already be logged automatically, and you should still offer the concrete next step of contact notification.
"""
        )

    def _send_pilgrim_confirmation(self, pilgrim_phone: str, notified_recipients: list) -> dict:
        """Sends a confirmation SMS back to the pilgrim's own number confirming their
        emergency contact(s) were notified. Shared by both the manual SOS button and
        the AI agent's tool, so both paths behave identically."""
        clean_recipients = [r for r in notified_recipients if r]
        confirmation_text = (
            f"RAFIQ Safety Confirmation: Your emergency alert was sent to "
            f"{', '.join(clean_recipients) if clean_recipients else 'your emergency contact'}. "
            f"Stay where you are if it is safe to do so — help has been notified."
        )
        return self.nokia.send_sms_alert([pilgrim_phone], confirmation_text)

    def dispatch_emergency_sms(self, recipients: list, message: str, pilgrim_phone: str = None) -> dict:
        """Helper for manual UI SOS dispatches — mirrors the AI tool's behavior,
        including the pilgrim confirmation SMS, so manual and AI-triggered SOS
        are consistent."""
        sms_res = self.nokia.send_sms_alert(recipients, message)
        result = {
            "tool": "nokia.send_sms_alert",
            "args": {"recipients": recipients, "message": message},
            "result": sms_res
        }
        if pilgrim_phone:
            result["pilgrim_confirmation"] = self._send_pilgrim_confirmation(pilgrim_phone, recipients)
        return result

    def analyze_and_respond(
        self,
        pilgrim_query: str,
        phone_number: str,
        profile_data: dict,
        language: str = "en",
        image_bytes: bytes = None,
        audio_bytes: bytes = None,
        history: list = None,
        on_status=None,
    ) -> dict:
        """
        history: optional list of {"role": "user"|"assistant", "content": str}
        from the current session's prior turns (text only), used to give the
        model short-term conversational memory. Kept in-session only — the
        caller is responsible for what it passes in and for resetting it
        between sessions/users.
        on_status: optional callable(str) invoked with a short human-readable
        status line as each tool call resolves, for incremental UI feedback.
        """
        trace = []
        recipients = [r for r in [profile_data.get('group', ''), profile_data.get('contact', '')] if r] or ["+966500000000"]

        # --- Tool definitions (closures capture this request's phone/profile) ---
        def get_device_location(msisdn: str) -> dict:
            """Returns the pilgrim's current GPS location, nearest landmark, and
            zone via the Nokia Location Verification API."""
            return self.nokia.get_device_location(msisdn)

        def request_qos_boost(msisdn: str, reason: str = "Urgent Safety Boost") -> dict:
            """Elevates the pilgrim's device to priority 5G network quality during
            an emergency and logs the incident with the Security Command Center."""
            res = self.nokia.request_qos_boost(msisdn, 30, reason)
            self.nokia.register_incident(msisdn, reason, profile_data, incident_type="SELF")
            return res

        def request_companion_assistance(subject: str, reason: str) -> dict:
            """Call this — automatically, with no need to ask permission first
            — the moment the pilgrim reports that someone ELSE (a companion,
            friend, or family member, not the pilgrim themself) needs
            emergency rescue or is injured. This is a lower-tier alert:
            it logs the incident with the Security Command Center so
            responders are aware, but does NOT boost the pilgrim's own
            network priority and does NOT send any SMS to anyone. Use this
            instead of request_qos_boost/send_emergency_sms whenever the
            person at risk is not the pilgrim themself.
            subject: who is actually at risk, e.g. "Pilgrim's brother — Mohamed".
            reason: brief description of the situation, e.g. "Reported injured, needs rescue".
            """
            incident = self.nokia.register_incident(
                phone_number, reason, profile_data, incident_type="THIRD_PARTY", subject=subject
            )
            return {
                "status": "LOGGED_WITH_COMMAND_CENTER",
                "incident_id": incident["id"],
                "subject": subject,
                "note": "Registry-only: no SMS sent, no network priority change made. "
                        "Offer to also SMS the pilgrim's own emergency contact if they want that.",
            }

        def send_emergency_sms(recipients_csv: str, message: str) -> dict:
            """Sends an emergency SMS to the given comma-separated recipient
            numbers, logs the incident with the Security Command Center, and
            automatically sends a separate confirmation SMS back to the
            pilgrim's own phone confirming their contact was notified."""
            recipient_list = [r.strip() for r in recipients_csv.split(",") if r.strip()]
            contact_res = self.nokia.send_sms_alert(recipient_list, message)
            self.nokia.register_incident(phone_number, message, profile_data, incident_type="SELF")
            confirm_res = self._send_pilgrim_confirmation(phone_number, recipient_list)
            return {"contact_dispatch": contact_res, "pilgrim_confirmation": confirm_res}

        def get_device_status(msisdn: str) -> dict:
            """Returns the pilgrim's device reachability and connectivity status
            via the Nokia Device Status API."""
            return self.nokia.get_device_status(msisdn)

        def resolve_emergency(reason: str = "Pilgrim confirmed safe") -> dict:
            """Call ONLY when the pilgrim has clearly and explicitly confirmed
            THEY THEMSELF are now safe after an active SOS about their own
            safety. Cancels that SELF emergency, restores standard network
            priority, and notifies the emergency contacts that it has been
            resolved. Does NOT resolve a separate THIRD_PARTY companion-
            assistance report — use resolve_companion_assistance for that."""
            res = self.nokia.resolve_incident(phone_number, reason, incident_type="SELF")
            stand_down_msg = (
                f"RAFIQ Update: {profile_data.get('name', 'This pilgrim')} has confirmed "
                f"they are safe. The earlier emergency alert is now resolved."
            )
            res["stand_down_notification"] = self.nokia.send_sms_alert(recipients, stand_down_msg)
            return res

        def resolve_companion_assistance(reason: str = "Companion confirmed safe") -> dict:
            """Call ONLY when the pilgrim clearly confirms the OTHER person
            (the companion/friend/family member previously reported as
            needing help) is now safe or has been found. Closes out the
            THIRD_PARTY incident only — does not touch any active SELF
            emergency for the pilgrim, and sends no SMS (this tier never
            sends SMS)."""
            return self.nokia.resolve_incident(phone_number, reason, incident_type="THIRD_PARTY")

        tools_list = [
            get_device_location, request_qos_boost, request_companion_assistance,
            send_emergency_sms, get_device_status, resolve_emergency, resolve_companion_assistance,
        ]
        tool_map = {f.__name__: f for f in tools_list}

        if not self.api_key:
            return {
                "response": _graceful_failure_message(language, "MISSING_KEY"),
                "trace": trace,
                "error": "MISSING_KEY",
            }

        lang_prompt = "Respond in clear, reassuring Arabic." if language == "ar" else "Respond in clear, reassuring English."
        context_prompt = f"""
Language Instruction: {lang_prompt}

Pilgrim Context:
- Name: {profile_data.get('name', 'Pilgrim User')}
- Phone (MSISDN): {phone_number}
- Default Emergency Recipients: {', '.join(recipients)}

Pilgrim Request: {pilgrim_query}
"""

        # Short-term in-session memory: replay prior turns (text only — we don't
        # re-send past images/audio) ahead of the current message so the model
        # can recall things like a name mentioned earlier in this session.
        contents = []
        for turn in (history or []):
            role = "model" if turn.get("role") == "assistant" else "user"
            text = turn.get("content", "")
            if text:
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

        parts = []
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
        if audio_bytes:
            parts.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))
        parts.append(types.Part.from_text(text=context_prompt))
        contents.append(types.Content(role="user", parts=parts))

        try:
            client = genai.Client(api_key=self.api_key)
        except Exception as e:
            return {
                "response": _graceful_failure_message(language, "CLIENT_ERROR"),
                "trace": trace,
                "error": str(e),
            }

        models_to_try = self.preferred_models

        last_error = ""
        for model_name in models_to_try:
            try:
                final_text = self._run_agentic_turn(client, model_name, contents, tools_list, tool_map, trace, on_status)
                return {"response": final_text, "trace": trace, "error": None}
            except Exception as model_e:
                last_error = str(model_e)
                print(f"[Rafiq Agent] Model '{model_name}' endpoint notice: {model_e}")
                if not self._is_retryable_with_other_model(model_e):
                    # Real failure mid-response (e.g. a tool already fired) is
                    # not something a different model can safely redo from
                    # scratch — surface it now instead of silently re-running
                    # the whole turn (and possibly re-firing SOS tools).
                    break

        return {
            "response": _graceful_failure_message(language, "ALL_MODELS_FAILED"),
            "trace": trace,
            "error": last_error,
        }

    @staticmethod
    def _is_retryable_with_other_model(exc: Exception) -> bool:
        """True only for errors that mean 'this model itself is unusable'
        (bad model name, no access, malformed request — HTTP 400/401/403/404
        from the Gemini API) — not rate limits (429), server hiccups (5xx),
        or a call that simply took a while to succeed."""
        if isinstance(exc, genai_errors.APIError):
            return exc.code in NON_RETRYABLE_MODEL_ERROR_CODES
        return False

    def _run_agentic_turn(self, client, model_name, contents, tools_list, tool_map, trace, on_status=None) -> str:
        """Runs the full model -> tool -> model loop until the model produces a
        final text answer grounded in real tool results. This is the piece that
        was missing before: tool results now always go back to the model, so the
        final reply is always genuinely generated, never a hardcoded string."""
        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            tools=tools_list,
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        working_contents = list(contents)

        for _ in range(MAX_TOOL_ITERATIONS):
            response = client.models.generate_content(model=model_name, contents=working_contents, config=config)

            if not response.function_calls:
                return response.text or "I'm here — could you tell me a bit more about what you need?"

            function_response_parts = []
            for fc in response.function_calls:
                func = tool_map.get(fc.name)
                args = dict(fc.args) if fc.args else {}

                if on_status:
                    try:
                        on_status(TOOL_STATUS_LABELS.get(fc.name, f"Running {fc.name}…"))
                    except Exception:
                        pass  # status feedback is best-effort, never fatal

                try:
                    result = func(**args) if func else {"error": f"Unknown tool: {fc.name}"}
                except Exception as e:
                    result = {"error": str(e)}
                trace.append({
                    "tool": fc.name,
                    "args": args,
                    "result": result,
                    "reasoning": _describe_tool_call(fc.name, args),
                })
                function_response_parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))

            working_contents.append(response.candidates[0].content)
            # NOTE: Gemini's live API rejects role="tool" (400 INVALID_ARGUMENT)
            # despite some SDK docs suggesting it. Function/tool results must be
            # sent back as role="user" — confirmed against real production errors.
            working_contents.append(types.Content(role="user", parts=function_response_parts))

        # Iteration cap hit with tools still pending — force one final text-only
        # synthesis call (no tools offered) rather than ever falling back to a
        # hardcoded string. This should be rare in practice.
        closing_config = types.GenerateContentConfig(
            system_instruction=self.system_instruction + "\n\nRespond to the pilgrim now, in your own words, summarizing what you just did. Do not call any more tools.",
            temperature=0.2,
        )
        closing_response = client.models.generate_content(model=model_name, contents=working_contents, config=closing_config)
        return closing_response.text or "I've taken the necessary safety actions — let me know if you need anything else."

    # ------------------------------------------------------------------
    # Command Center (authority-side) AI features. These are read-only:
    # they never call any Nokia tool that changes state (no SMS, no QoS
    # boost, no incident writes) — they only summarize/rank data that
    # already exists in the incident registry, for a human dispatcher.
    # ------------------------------------------------------------------

    def generate_dispatcher_briefing(self, incident: dict) -> dict:
        """
        Produces a short, human-readable briefing paragraph for a single
        incident, synthesizing the raw fields (reason, incident_type,
        subject, location, profile/medical notes, timestamp) into something
        a dispatcher can read in a few seconds. Falls back to a clearly
        labeled non-AI summary if the API key is missing or the call fails —
        never blocks the Command Center from working.
        """
        if not self.api_key:
            return {"briefing": self._fallback_briefing(incident), "ai_generated": False}

        prof = incident.get("profile", {})
        loc = incident.get("location", {})
        prompt = f"""
You are writing a one-paragraph briefing for a human security dispatcher at a Hajj/Umrah safety command center. Be concise (3-4 sentences max), factual, and actionable. Do not invent details not present below.

Incident type: {incident.get('incident_type', 'SELF')}
Subject (who the incident concerns): {incident.get('subject', prof.get('name', 'Unknown'))}
Reported by (pilgrim/reporting phone): {incident.get('phone_number')}
Reason logged: {incident.get('reason')}
Zone: {loc.get('zone', 'Unknown')}
Nearest landmark: {loc.get('nearest_landmark', 'Unknown')}
Medical notes on file for reporting pilgrim: {prof.get('medical', 'None listed')}
Status: {incident.get('status')}
Logged at: {incident.get('timestamp')}

Write the briefing now, addressed to the dispatcher, in your own words.
"""
        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.preferred_models[0],
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=types.GenerateContentConfig(temperature=0.2),
            )
            text = response.text
            if text:
                return {"briefing": text.strip(), "ai_generated": True}
        except Exception as e:
            print(f"[Rafiq Agent] Dispatcher briefing generation failed: {e}")

        return {"briefing": self._fallback_briefing(incident), "ai_generated": False}

    @staticmethod
    def _fallback_briefing(incident: dict) -> str:
        """Deterministic, non-AI summary used when the API key is missing or
        the model call fails, so the Command Center never shows a blank or
        broken briefing."""
        loc = incident.get("location", {})
        kind = "self-reported emergency" if incident.get("incident_type", "SELF") == "SELF" else "third-party companion report"
        return (
            f"{kind.capitalize()} logged near {loc.get('nearest_landmark', 'an unknown landmark')} "
            f"({loc.get('zone', 'unknown zone')}) at {incident.get('timestamp', 'an unknown time')}. "
            f"Reason on file: {incident.get('reason', 'not specified')}. "
            f"Concerns: {incident.get('subject', 'unspecified')}."
        )

    def triage_active_incidents(self, active_incidents: list) -> dict:
        """
        Ranks currently-active incidents by urgency using the AI, returning
        an ordered list of incident IDs with a one-line rationale for the
        top of the list. Read-only — does not modify any incident. Falls
        back to a deterministic rule (SELF before THIRD_PARTY, then oldest
        first) if the API key is missing or the call fails.
        """
        if not active_incidents:
            return {"ranked_ids": [], "rationale": "No active incidents.", "ai_generated": False}

        if not self.api_key:
            return self._fallback_triage(active_incidents)

        incident_summaries = "\n".join(
            f"- ID {a['id']}: type={a.get('incident_type', 'SELF')}, subject={a.get('subject', 'N/A')}, "
            f"reason=\"{a.get('reason', '')}\", zone={a.get('location', {}).get('zone', 'Unknown')}, "
            f"medical_notes=\"{a.get('profile', {}).get('medical', 'None')}\", logged_at={a.get('timestamp')}"
            for a in active_incidents
        )
        prompt = f"""
You are triaging active safety incidents for a Hajj/Umrah command center dispatcher. Rank the incidents below from MOST to LEAST urgent, considering: medical risk (e.g. diabetic, heart conditions), whether it's a direct self-emergency vs a third-party report, and any signs of severity in the reason text.

Incidents:
{incident_summaries}

Respond ONLY as JSON, no markdown, no preamble, in this exact shape:
{{"ranked_ids": ["<id in most urgent first order>", ...], "rationale": "<one sentence explaining the #1 pick>"}}
"""
        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.preferred_models[0],
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=types.GenerateContentConfig(temperature=0.1),
            )
            text = (response.text or "").strip()
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            import json
            parsed = json.loads(text)
            valid_ids = {a["id"] for a in active_incidents}
            ranked = [i for i in parsed.get("ranked_ids", []) if i in valid_ids]
            # Safety net: if the model dropped or hallucinated IDs, append any
            # missing real ones at the end rather than silently losing them.
            missing = [a["id"] for a in active_incidents if a["id"] not in ranked]
            ranked.extend(missing)
            return {"ranked_ids": ranked, "rationale": parsed.get("rationale", ""), "ai_generated": True}
        except Exception as e:
            print(f"[Rafiq Agent] Triage generation failed: {e}")
            return self._fallback_triage(active_incidents)

    @staticmethod
    def _fallback_triage(active_incidents: list) -> dict:
        """Deterministic ordering used when the AI triage is unavailable:
        SELF incidents before THIRD_PARTY, oldest timestamp first within
        each group (earliest-reported gets attention first)."""
        def sort_key(a):
            is_third_party = 1 if a.get("incident_type", "SELF") == "THIRD_PARTY" else 0
            return (is_third_party, a.get("timestamp", ""))

        ordered = sorted(active_incidents, key=sort_key)
        return {
            "ranked_ids": [a["id"] for a in ordered],
            "rationale": "Rule-based ordering (AI triage unavailable): self-emergencies first, then oldest-reported first.",
            "ai_generated": False,
        }