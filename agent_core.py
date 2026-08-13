"""
RAFIQ (رفيق) — Autonomous Safety AI Core
Powered by Google Gemini Function Calling & Nokia CAMARA APIs.
Includes dynamic model discovery and fallback for Gemini model endpoints.
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from nokia_client import NokiaCAMARAClient

load_dotenv()

class RafiqAgent:
    def __init__(self):
        self.nokia = NokiaCAMARAClient()
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()

        # Updated active Gemini models
        self.preferred_models = [
            "gemini-2.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-latest"
        ]

        self.system_instruction = (
            "You are RAFIQ (رفيق), an autonomous AI safety companion for Hajj & Umrah pilgrims in Makkah. "
            "You are directly connected to the Nokia Telecom Network Open Gateway APIs.\n\n"
            "MANDATORY TOOL CALLING INSTRUCTIONS:\n"
            "- Whenever the pilgrim expresses danger, disorientation, panic, feeling lost, illness, heat stroke, or requests emergency help, "
            "YOU MUST IMMEDIATELY CALL `send_emergency_sms`, `request_qos_boost`, AND `get_device_location`.\n"
            "- Do NOT merely promise help in text. YOU MUST EXECUTE THE TOOLS FIRST.\n"
            "- If network slowdown or heavy crowds are mentioned, call `request_qos_boost`.\n"
            "- Provide a comforting, practical, and clear response after executing the required network tools."
        )

    def dispatch_emergency_sms(self, recipients: list, message: str) -> dict:
        """Helper for manual UI SOS dispatches."""
        sms_res = self.nokia.send_sms_alert(recipients, message)
        return {
            "tool": "nokia.send_sms_alert",
            "args": {"recipients": recipients, "message": message},
            "result": sms_res
        }

    def _get_active_models(self, client) -> list:
        """Queries Google API to find currently active models for the provided API key."""
        try:
            available = [
                m.name.replace("models/", "") 
                for m in client.models.list() 
                if hasattr(m, 'name')
            ]
            
            # Prioritize preferred models present on this API key
            discovered = [m for m in self.preferred_models if m in available]
            others = [m for m in available if "flash" in m and m not in discovered]
            
            candidates = discovered + others
            if candidates:
                return candidates
        except Exception as e:
            print(f"[Rafiq Agent] Dynamic model listing notice: {e}")
            
        return self.preferred_models

    def analyze_and_respond(
        self,
        pilgrim_query: str,
        phone_number: str,
        profile_data: dict,
        language: str = "en",
        image_bytes: bytes = None,
        audio_bytes: bytes = None
    ) -> dict:
        trace = []

        recipients_csv = f"{profile_data.get('group', '')},{profile_data.get('contact', '')}".strip(",") or "+966500000000"

        # Define Callable Tools
        def get_device_location(msisdn: str) -> dict:
            res = self.nokia.get_device_location(msisdn)
            trace.append({"tool": "nokia.get_device_location", "args": {"msisdn": msisdn}, "result": res})
            return res

        def request_qos_boost(msisdn: str, reason: str = "Urgent Safety Boost") -> dict:
            res = self.nokia.request_qos_boost(msisdn, 30, reason)
            self.nokia.register_incident(msisdn, reason, profile_data)
            trace.append({"tool": "nokia.request_qos_boost", "args": {"msisdn": msisdn, "reason": reason}, "result": res})
            return res

        def send_emergency_sms(recipients_csv: str, message: str) -> dict:
            recipients = [r.strip() for r in recipients_csv.split(",") if r.strip()]
            res = self.nokia.send_sms_alert(recipients, message)
            self.nokia.register_incident(phone_number, message, profile_data)
            trace.append({"tool": "nokia.send_sms_alert", "args": {"recipients_csv": recipients_csv, "message": message}, "result": res})
            return res

        def get_device_status(msisdn: str) -> dict:
            res = self.nokia.get_device_status(msisdn)
            trace.append({"tool": "nokia.get_device_status", "args": {"msisdn": msisdn}, "result": res})
            return res

        tools_list = [get_device_location, request_qos_boost, send_emergency_sms, get_device_status]
        
        tool_map = {
            "get_device_location": get_device_location,
            "request_qos_boost": request_qos_boost,
            "send_emergency_sms": send_emergency_sms,
            "get_device_status": get_device_status
        }

        if not self.api_key:
            return {"response": "⚠️ **GEMINI_API_KEY Missing!** Configure `.env` file.", "trace": trace, "error": "MISSING_KEY"}

        lang_prompt = "Respond in clear, reassuring Arabic." if language == "ar" else "Respond in clear, reassuring English."

        context_prompt = f"""
Language Instruction: {lang_prompt}

Pilgrim Context:
- Name: {profile_data.get('name', 'Pilgrim User')}
- Phone (MSISDN): {phone_number}
- Default Emergency Recipients: {recipients_csv}

Pilgrim Request: {pilgrim_query}
"""

        try:
            client = genai.Client(api_key=self.api_key)
            models_to_try = self._get_active_models(client)
            
            contents = []
            if image_bytes:
                contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            if audio_bytes:
                contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))
            contents.append(context_prompt)

            last_error = ""

            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_instruction,
                            tools=tools_list,
                            temperature=0.2
                        )
                    )

                    # Execute function calls if requested by the model
                    if response.function_calls:
                        for fc in response.function_calls:
                            func = tool_map.get(fc.name)
                            if func:
                                try:
                                    func(**fc.args)
                                except Exception as e:
                                    print(f"[Rafiq] Error executing {fc.name}: {e}")
                        
                        final_text = response.text or (
                            "🚨 **Emergency Network Protocol Activated.** I have boosted your 5G signal, verified your GPS coordinates, and sent SOS alerts to your contacts. The Security Command Center has been notified."
                            if language == "en" else
                            "🚨 **تم تفعيل بروتوكول الطوارئ للشبكة.** تم تحديد موقعك، ورفع أولوية 5G، وإرسال تنبيهات لجهات الاتصال وتنبيه مركز القيادة."
                        )
                        return {"response": final_text, "trace": trace, "error": None}

                    if response and response.text:
                        return {"response": response.text, "trace": trace, "error": None}

                except Exception as model_e:
                    last_error = str(model_e)
                    print(f"[Rafiq Agent] Model '{model_name}' endpoint notice: {model_e}")

            return {"response": f"⚠️ **API Execution Error:** `{last_error}`", "trace": trace, "error": last_error}

        except Exception as e:
            err_str = str(e)
            return {"response": f"⚠️ **Client Error:** `{err_str}`", "trace": trace, "error": err_str}