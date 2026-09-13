import streamlit as st
import folium
from streamlit_folium import st_folium
from agent_core import RafiqAgent
from nokia_client import HAJJ_ZONES
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="RAFIQ (رفيق) — Telecom AI Pilgrim Safety Layer",
    page_icon="🕋",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown("""
<style>
    :root {
        --primary-color: #1a472a;
        --secondary-color: #c41e3a;
        --accent-light: #ecf5f0;
    }
    
    /* Sidebar styling */
    .stSidebar [data-testid="stSidebarContent"] {
        background-color: #ffffff;
        padding: 20px;
    }
    
    /* Chat messages */
    .stChatMessage {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    
    /* Button styling */
    .stButton > button {
        background-color: var(--primary-color);
        color: white;
        border-radius: 6px;
        font-weight: 600;
        padding: 10px 20px;
        border: none;
    }
    
    .stButton > button:hover {
        background-color: #0f3320;
    }
    
    /* Headings */
    h1, h2, h3 {
        color: var(--primary-color);
        font-weight: 700;
    }
    
    /* Card/container styling */
    [data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Custom Theme Styling (Saudi Green-Marble + Makkah Gold Outlines)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

    :root {
        --bg-marble-green: #EEF4F0;
        --card-bg: #FFFFFF;
        --card-border: #D8E3DD;
        --gold-accent: #C5A059;
        --gold-bright: #D4AF37;
        --saudi-green: #006C35;
        --sos-red: #E11D48;
        --text-dark: #0F172A;
        --text-muted: #475569;
    }

    .stApp {
        background-color: var(--bg-marble-green);
        background-image: 
            radial-gradient(circle at 50% 0%, rgba(0, 108, 53, 0.08) 0%, transparent 65%),
            linear-gradient(rgba(200, 218, 208, 0.5) 1px, transparent 1px),
            linear-gradient(90deg, rgba(200, 218, 208, 0.5) 1px, transparent 1px);
        background-size: 100% 100%, 30px 30px, 30px 30px;
        color: var(--text-dark);
        font-family: 'Inter', 'IBM Plex Sans Arabic', sans-serif;
    }

    .main-title-container {
        background-color: #FFFFFF;
        border: 1px solid var(--card-border);
        border-top: 4px solid var(--saudi-green);
        border-radius: 12px;
        padding: 16px 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 16px rgba(0, 108, 53, 0.05);
    }

    .gold-arabic {
        color: var(--gold-accent) !important;
        font-family: 'IBM Plex Sans Arabic', sans-serif !important;
        font-weight: 700;
    }

    .tech-subtitle {
        color: var(--saudi-green);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    div[data-testid="stExpander"], div.stCard {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 12px !important;
    }

    .stButton > button {
        background: #FFFFFF !important;
        color: var(--text-dark) !important;
        border: 2px solid var(--gold-accent) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    .stButton > button:hover {
        border-color: var(--saudi-green) !important;
        color: var(--saudi-green) !important;
        background: #F0FDF4 !important;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #E11D48 0%, #BE123C 100%) !important;
        color: #FFFFFF !important;
        border: 2px solid var(--gold-bright) !important;
        font-weight: 700 !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid var(--card-border) !important;
    }
</style>
""", unsafe_allow_html=True)

if "agent" not in st.session_state:
    st.session_state.agent = RafiqAgent()

if "setting_trace_vis" not in st.session_state:
    st.session_state.setting_trace_vis = False

if "lang" not in st.session_state:
    st.session_state.lang = "en"

if "cmd_authenticated" not in st.session_state:
    st.session_state.cmd_authenticated = False

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Assalamu Alaikum! I am **RAFIQ (رفيق)**, your autonomous AI safety companion connected directly to Nokia Telecom Network APIs. How can I guide you today?"
        }
    ]

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

if "last_active_user" not in st.session_state:
    st.session_state.last_active_user = "Rafiq User"

if "media_widget_key" not in st.session_state:
    # Bumped after every successful send so the file_uploader / audio_input
    # widgets reset to empty instead of resubmitting the same attachment on
    # every rerun (this was the cause of the infinite image-analysis loop).
    st.session_state.media_widget_key = 0

if "last_sent_media_signature" not in st.session_state:
    # Second safety net: even if a widget somehow still holds old bytes on a
    # rerun, never send the exact same attachment twice in a row.
    st.session_state.last_sent_media_signature = None

def get_active_incidents_for_user(user_name, incident_type=None):
    """Returns active incidents for this pilgrim's name, optionally filtered
    to a specific incident_type ('SELF' or 'THIRD_PARTY'). Replaces the old
    single is_sos_active_for_user boolean, which conflated 'an incident is
    active' with 'network priority is boosted' — those are different facts
    since THIRD_PARTY companion reports never boost QoS."""
    alerts = st.session_state.agent.nokia.alerts
    return [
        a for a in alerts
        if a.get("status") == "ACTIVE"
        and a.get("profile", {}).get("name") == user_name
        and (incident_type is None or a.get("incident_type", "SELF") == incident_type)
    ]

T_dict = {
    "en": {
        "title": "RAFIQ", "title_ar": "رفيق",
        "subtitle": "AUTONOMOUS PILGRIM SAFETY LAYER • POWERED BY NOKIA CAMARA APIs",
        "tab_pilgrim": "🕋 PILGRIM COMPANION", "tab_authority": "🚨 COMMAND CENTER",
        "setting_header": "🔧 Agent Settings",
        "setting_trace_vis": "Always Expand AI Reasoning Trace",
        "profile_header": "👤 Pilgrim Profile & Emergency Contacts",
        "name_label": "Full Name (Switch user for testing):", "id_label": "Passport / ID Number:",
        "group_label": "Group Leader Phone:", "contact_label": "Emergency Contact Phone:",
        "medical_label": "Medical Notes / Allergies:", "save_profile": "Save Profile",
        "telemetry_header": "📡 Network Telemetry", "loc_header": "📍 Live Nokia Location API",
        "qod_header": "⚡ 5G Quality on Demand (QoD)", "qod_active": "Priority Boost Active",
        "qod_inactive": "⚪ Standard Network QoS", "sos_btn_off": "🚨 EMERGENCY SOS (TAP TO ACTIVATE)",
        "sos_btn_on": "🟢 SOS ACTIVE — TAP TO CANCEL",
        "sos_success": "🚨 SOS Dispatched! Elevated 5G priority activated & carrier SMS alerts sent.",
        "sos_cancelled": "⚠️ SOS Cancelled. 5G network priority restored to standard.",
        "incident_active_label": "Active Incident (Self)", "incident_inactive_label": "No Active Self-Incident",
        "companion_report_active_label": "Companion Report Active",
        "companion_report_caption": "For reporting a companion/friend/family member — NOT yourself — needs help. Registry-only: no SMS sent, no network priority changed.",
        "companion_btn_off": "🟡 Report Companion Needs Help", "companion_btn_on": "🟢 Companion Report Active — Mark Safe",
        "companion_subject_label": "Who needs help? (name/relation):", "companion_reason_label": "Brief situation:",
        "companion_logged_toast": "🟡 Companion assistance report logged with Command Center.",
        "companion_resolved_toast": "✅ Companion assistance report marked resolved.",
        "expand_map": "🗺️ Open Navigation GIS Map",
        "chat_placeholder": "Ask for guidance, location support, or emergency assistance...",
        "quick_actions": "💡 Instant Quick Actions:", "qa_loc": "📍 Where am I right now?",
        "qa_sig": "📶 Check 5G signal status", "qa_gate": "🕋 Direct me to Gate 79",
        "multimodal_expander": "📷 / 🎙️ Scan Signboard or Record Voice Query",
        "upload_img": "Upload Gate / Signboard Image:", "record_audio": "Record Voice Query:",
        "auth_title": "🔒 Security Access Verification", "auth_prompt": "Enter Security Passcode:",
        "auth_btn": "Authenticate", "auth_err": "❌ Incorrect Passcode. Access Denied.",
        "cmd_title": "🚨 Security Command Center",
        "cmd_subtitle": "Real-time Telemetry Dispatch, Multi-User SOS Feed & Sector Controls",
        "feed_header": "🚨 Incident Feed & Emergency Log", "dispatch_btn": "Dispatch Responder",
        "resolve_btn": "✅ Mark Resolved", "clear_btn": "🗑️ Clear Record",
        "clear_all_btn": "🗑️ Clear Resolved Records",
    },
    "ar": {
        "title": "RAFIQ", "title_ar": "رفيق",
        "subtitle": "طبقة السلامة الذكية • مدعومة بشبكات نوكيا البرمجية (CAMARA APIs)",
        "tab_pilgrim": "🕋 تطبيق الحاج", "tab_authority": "🚨 مركز قيادة الأمن والسلامة",
        "setting_header": "🔧 إعدادات المساعد",
        "setting_trace_vis": "عرض تفاصيل المساعد دائماً",
        "profile_header": "👤 ملف الحاج وبيانات الاتصال",
        "name_label": "الاسم الكامل (تغيير المستخدم للاختبار):", "id_label": "رقم الهوية / الجواز:",
        "group_label": "رقم قائد الحملة:", "contact_label": "رقم طوارئ العائلة:",
        "medical_label": "ملاحظات طبية / حساسيات:", "save_profile": "حفظ ملف الطوارئ",
        "telemetry_header": "📡 بيانات الاتصال والشبكة", "loc_header": "📍 موقع نوكيا الحي (Nokia Location API)",
        "qod_header": "⚡ جودة الاتصال عند الطلب (5G QoD)", "qod_active": "أولوية الشبكة مفعّلة",
        "qod_inactive": "⚪ أولوية الاتصال العادية", "sos_btn_off": "🚨 إرسال بلاغ طوارئ (اضغط للتفعيل)",
        "sos_btn_on": "🟢 البلاغ نشط — اضغط للإلغاء (إنذار خاطئ)",
        "sos_success": "🚨 تم إرسال البلاغ! تم رفع أولوية الشبكة وإرسال رسائل SMS.",
        "sos_cancelled": "⚠️ تم إلغاء البلاغ وإعادة أولوية الشبكة إلى وضعها الطبيعي.",
        "incident_active_label": "بلاغ شخصي نشط", "incident_inactive_label": "لا يوجد بلاغ شخصي نشط",
        "companion_report_active_label": "بلاغ مرافق نشط",
        "companion_report_caption": "للإبلاغ عن مرافق أو صديق أو فرد من العائلة — وليس نفسك — بحاجة للمساعدة. تسجيل فقط: لا يتم إرسال SMS ولا تغيير أولوية الشبكة.",
        "companion_btn_off": "🟡 الإبلاغ عن مرافق بحاجة للمساعدة", "companion_btn_on": "🟢 بلاغ المرافق نشط — تحديد كآمن",
        "companion_subject_label": "من يحتاج المساعدة؟ (الاسم/صلة القرابة):", "companion_reason_label": "وصف موجز للحالة:",
        "companion_logged_toast": "🟡 تم تسجيل بلاغ مساعدة المرافق مع مركز القيادة.",
        "companion_resolved_toast": "✅ تم إغلاق بلاغ مساعدة المرافق.",
        "expand_map": "🗺️ فتح خريطة الملاحة التفاعلية",
        "chat_placeholder": "اطلب المساعدة، الإرشاد، أو أرسل بلاغ طوارئ...",
        "quick_actions": "💡 إجراءات سريعة:", "qa_loc": "📍 أين أنا الآن؟",
        "qa_sig": "📶 افحص جودة الشبكة", "qa_gate": "🕋 كيف أصل إلى باب 79؟",
        "multimodal_expander": "📷 / 🎙️ مدخلات المسح والصوت",
        "upload_img": "ارفع صورة اللافتة أو البوابة:", "record_audio": "سجّل استفسارك الصوتي:",
        "auth_title": "🔒 التحقق من صلاحيات الدخول", "auth_prompt": "أدخل رمز المرور الأمني:",
        "auth_btn": "تسجيل الدخول", "auth_err": "❌ رمز المرور غير صحيح.",
        "cmd_title": "🚨 مركز عمليات الأمن واستجابة الطوارئ",
        "cmd_subtitle": "تتبع البلاغات الحية لجميع المستخدمين، إدارة الحشود، والتحكم بالشبكة",
        "feed_header": "🚨 الموجز العام لبلاغات ورسائل طوارئ الحجاج",
        "dispatch_btn": "إرسال فرقة أمنية", "resolve_btn": "✅ معالجة وإغلاق البلاغ",
        "clear_btn": "🗑️ مسح البلاغ", "clear_all_btn": "🗑️ مسح جميع البلاغات المعالجة",
    }
}

L = T_dict[st.session_state.lang]

# Fragment auto-refreshes every 3 seconds to pull live incident updates from AI agent tool executions
@st.fragment(run_every=3)
def render_command_feed(labels):
    nokia = st.session_state.agent.nokia
    all_active = [a for a in nokia.alerts if a.get("status") == "ACTIVE"]

    # --- Zone clustering alert: real aggregation over the live alerts list ---
    clusters = nokia.get_zone_incident_clusters(min_incidents=2)
    if clusters:
        for c in clusters:
            st.error(
                f"🚨 **Possible mass-incident pattern:** {c['count']} active incidents in "
                f"**{c['zone']}** (IDs: {', '.join(c['incident_ids'])}). Consider dispatching additional units."
            )

    # --- AI severity triage across all active incidents ---
    if all_active:
        with st.expander("🧭 AI Triage — Suggested Response Order", expanded=len(all_active) > 1):
            if st.button("🔄 Run / Refresh AI Triage", key="btn_run_triage"):
                st.session_state.triage_result = st.session_state.agent.triage_active_incidents(all_active)
            triage = st.session_state.get("triage_result")
            if triage:
                tag = "🤖 AI-generated" if triage.get("ai_generated") else "📏 Rule-based fallback (AI unavailable)"
                st.caption(tag)
                st.write(triage.get("rationale", ""))
                id_to_alert = {a["id"]: a for a in all_active}
                for rank, inc_id in enumerate(triage.get("ranked_ids", []), start=1):
                    a = id_to_alert.get(inc_id)
                    if a:
                        subj = a.get("subject", a.get("profile", {}).get("name", "Unknown"))
                        st.write(f"{rank}. Incident #{inc_id} — {subj} ({a.get('incident_type', 'SELF')})")
            else:
                st.caption("Click the button above to have the AI rank active incidents by urgency.")

    st.subheader(labels["feed_header"])

    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        feed_filter = st.radio("Filter Incidents:", ["All Incidents", "Active Only", "Resolved Only"], horizontal=True, key="cmd_feed_filter")

    with f_col2:
        if [a for a in nokia.alerts if a.get("status") == "RESOLVED"]:
            if st.button(labels["clear_all_btn"], key="btn_clear_all_res"):
                nokia.alerts[:] = [a for a in nokia.alerts if a.get("status") == "ACTIVE"]
                st.toast("🧹 Cleared resolved incident records.")
                st.rerun()

    search_query = st.text_input("🔍 Search Incidents (Name, Subject, ID, Phone):", key="cmd_search").strip().lower()
    current_alerts = nokia.alerts

    if feed_filter == "Active Only":
        displayed_alerts = [a for a in current_alerts if a.get("status") == "ACTIVE"]
    elif feed_filter == "Resolved Only":
        displayed_alerts = [a for a in current_alerts if a.get("status") == "RESOLVED"]
    else:
        displayed_alerts = list(current_alerts)

    if search_query:
        displayed_alerts = [
            a for a in displayed_alerts
            if search_query in str(a.get("profile", {}).get("name", "")).lower()
            or search_query in str(a.get("subject", "")).lower()
            or search_query in str(a.get("profile", {}).get("id_num", "")).lower()
            or search_query in str(a.get("phone_number", "")).lower()
        ]

    if not displayed_alerts:
        st.info("No active incidents logged. (Trigger an emergency query in the chat to test AI dispatch).")
    else:
        for alert in reversed(displayed_alerts):
            prof = alert.get("profile", {})
            loc = alert.get("location", {})
            is_active = alert.get("status") == "ACTIVE"
            incident_type = alert.get("incident_type", "SELF")
            user_name = prof.get("name", alert.get("phone_number", "Unknown Pilgrim"))
            subject = alert.get("subject", user_name)
            alert_id = alert["id"]

            if incident_type == "THIRD_PARTY":
                type_badge = "🟡 COMPANION REPORT"
            else:
                type_badge = "🔴 SELF SOS"
            status_badge = "🟢 ACTIVE" if is_active else "⚪ RESOLVED"

            header = f"⚠️ Incident #{alert_id} — {type_badge} — Subject: {subject} ({status_badge})"

            with st.expander(header, expanded=is_active):
                st.info(f"**SOS / AI Emergency Message:** *\"{alert.get('reason', 'Direct Emergency SOS triggered.')}\"*")

                # AI dispatcher briefing (cached per-incident so we don't
                # regenerate on every 3s auto-refresh)
                briefing_cache_key = f"briefing_{alert_id}_{alert.get('timestamp')}"
                if briefing_cache_key not in st.session_state:
                    st.session_state[briefing_cache_key] = st.session_state.agent.generate_dispatcher_briefing(alert)
                briefing = st.session_state[briefing_cache_key]
                briefing_tag = "🤖 AI Briefing" if briefing.get("ai_generated") else "📋 Briefing (AI unavailable, rule-based)"
                st.markdown(f"**{briefing_tag}:** {briefing.get('briefing', '')}")

                ic1, ic2 = st.columns(2)
                ic1.markdown(
                    f"**Reporting Pilgrim:** `{user_name}`\n\n"
                    f"**Incident Type:** `{incident_type}`\n\n"
                    f"**Subject:** `{subject}`\n\n"
                    f"**Passport/ID:** `{prof.get('id_num', 'N/A')}`\n\n"
                    f"**MSISDN:** `{alert.get('phone_number')}`"
                )
                ic2.markdown(f"**Group Leader:** `{prof.get('group', 'N/A')}`\n\n**Emergency Contact:** `{prof.get('contact', 'N/A')}`\n\n**Medical Notes:** `{prof.get('medical', 'None Listed')}`")

                st.divider()
                loc1, loc2 = st.columns(2)
                loc1.markdown(f"**Zone:** `{loc.get('zone', 'Makkah Core')}`\n\n**Landmark:** `{loc.get('nearest_landmark', 'Masjid al-Haram')}`\n\n**GPS:** `{loc.get('latitude')}, {loc.get('longitude')}`")
                loc2.markdown(f"**Accuracy Radius:** `{loc.get('accuracy_radius_m', 25)} meters`\n\n**Timestamp:** `{alert.get('timestamp', 'N/A')}`")

                st.divider()
                act1, act2 = st.columns(2)
                if is_active:
                    if act1.button(labels["dispatch_btn"], key=f"disp_{alert_id}"):
                        st.success(f"Security unit dispatched to {loc.get('nearest_landmark')} for '{subject}'.")
                    if act2.button(labels["resolve_btn"], key=f"res_{alert_id}", type="primary"):
                        alert["status"] = "RESOLVED"
                        if incident_type == "SELF":
                            remaining = [
                                a for a in nokia.alerts
                                if a.get("status") == "ACTIVE" and a.get("phone_number") == alert.get("phone_number")
                                and a.get("incident_type", "SELF") == "SELF"
                            ]
                            if not remaining:
                                nokia.deactivate_qos_boost(alert.get("phone_number"))
                        st.toast(f"✅ Incident #{alert_id} marked as RESOLVED.")
                        st.rerun()
                else:
                    if act1.button(labels["clear_btn"], key=f"clr_{alert_id}"):
                        st.session_state.agent.nokia.alerts[:] = [a for a in st.session_state.agent.nokia.alerts if a.get("id") != alert_id]
                        st.toast(f"🗑️ Incident #{alert_id} removed.")
                        st.rerun()

# Sidebar Setup
with st.sidebar:
    st.markdown("### 🌐 Language / اللغة")
    lang_choice = st.radio("Select Language / اختر اللغة:", ["English", "العربية"], index=0 if st.session_state.lang == "en" else 1)
    new_lang = "en" if lang_choice == "English" else "ar"
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    st.divider()

    st.markdown(f"### {L['setting_header']}")
    trace_vis_setting = st.toggle(L["setting_trace_vis"], value=st.session_state.setting_trace_vis, key="trace_vis_toggle")
    if trace_vis_setting != st.session_state.setting_trace_vis:
        st.session_state.setting_trace_vis = trace_vis_setting
        st.rerun()
    st.divider()

    st.markdown("### 📡 GSMA Open Gateway")
    st.caption("Powered by Nokia Network as Code APIs & Google Gemini 2.5 Flash")

# Title Banner
st.markdown(f"""
<div class="main-title-container">
    <div style="display:flex; align-items:baseline; justify-content:space-between; flex-wrap:wrap;">
        <div style="display:flex; align-items:baseline; gap:16px;">
            <h1 style="margin:0; font-size: 2.6rem; color: #006C35 !important;">{L['title']}</h1>
            <h1 class="gold-arabic" style="margin:0; font-size: 2.6rem;">{L['title_ar']}</h1>
        </div>
        <div class="tech-subtitle">{L['subtitle']}</div>
    </div>
</div>
""", unsafe_allow_html=True)

tab_pilgrim, tab_authority = st.tabs([L["tab_pilgrim"], L["tab_authority"]])

# TAB 1: PILGRIM COMPANION
with tab_pilgrim:
    col_chat, col_telemetry = st.columns([2, 1])

    with col_telemetry:
        st.subheader(L["telemetry_header"])
        selected_phone = st.text_input("Pilgrim Phone Number (MSISDN):", "+999991234567")
        
        with st.expander(L["profile_header"], expanded=True):
            p_name = st.text_input(L["name_label"], value="Rafiq User", key="p_name_val")
            p_id = st.text_input(L["id_label"], "A12345678", key="p_id")
            p_group = st.text_input(L["group_label"], "+966501234567", key="p_group")
            p_contact = st.text_input(L["contact_label"], "+966559876543", key="p_contact")
            p_med = st.text_area(L["medical_label"], "Diabetic - Requires Insulin", key="p_med")

            if st.session_state.last_active_user != p_name:
                st.session_state.last_active_user = p_name
                st.rerun()

            profile_data = {"name": p_name, "id_num": p_id, "group": p_group, "contact": p_contact, "medical": p_med}
            if st.button(L["save_profile"]):
                st.success("Profile saved!")

        nokia_client = st.session_state.agent.nokia
        loc_data = nokia_client.get_device_location(selected_phone)

        st.subheader(L["loc_header"])
        zone_labels = [z["zone"] for z in HAJJ_ZONES]
        current_zone_idx = nokia_client.zone_overrides.get(selected_phone, 0)
        picked_label = st.selectbox("🎬 Demo: Simulate Pilgrim Zone", zone_labels, index=current_zone_idx, key=f"zone_pick_{selected_phone}")
        picked_idx = zone_labels.index(picked_label)
        if picked_idx != current_zone_idx:
            loc_data = nokia_client.set_simulated_zone(selected_phone, picked_idx)
            st.rerun()
        st.markdown(f"**Zone:** `{loc_data['zone']}`\n\n**Landmark:** `{loc_data['nearest_landmark']}`")

        m_preview = folium.Map(location=[loc_data['latitude'], loc_data['longitude']], zoom_start=16)
        folium.Marker([loc_data['latitude'], loc_data['longitude']], popup=f"Pilgrim: {p_name}", icon=folium.Icon(color="red", icon="user")).add_to(m_preview)
        st_folium(m_preview, height=180, width=300)

        st.divider()
        # Two independent, non-conflated signals (previously combined into
        # one boolean that could show "priority active" for a companion
        # report that never actually boosted anything):
        self_incidents = get_active_incidents_for_user(p_name, incident_type="SELF")
        companion_incidents = get_active_incidents_for_user(p_name, incident_type="THIRD_PARTY")
        qos_actually_boosted = nokia_client.check_qos_status(selected_phone)

        st.subheader(L["qod_header"])
        qcol1, qcol2 = st.columns(2)
        with qcol1:
            if self_incidents:
                st.error(f"🔴 {L['incident_active_label']}")
            else:
                st.info(f"⚪ {L['incident_inactive_label']}")
        with qcol2:
            if qos_actually_boosted:
                st.success(f"🟢 {L['qod_active']}")
            else:
                st.info(L["qod_inactive"])

        if companion_incidents:
            st.warning(f"🟡 {L['companion_report_active_label']} ({len(companion_incidents)})")

        st.divider()
        if self_incidents:
            if st.button(L["sos_btn_on"], type="secondary", use_container_width=True):
                nokia_client.resolve_incident(selected_phone, "Manually cancelled by pilgrim", incident_type="SELF")
                st.toast(L["sos_cancelled"])
                st.rerun()
        else:
            if st.button(L["sos_btn_off"], type="primary", use_container_width=True):
                sos_reason = f"Manual Emergency SOS triggered by {p_name} near {loc_data['nearest_landmark']}"
                nokia_client.register_incident(selected_phone, sos_reason, profile_data, loc_data, incident_type="SELF")
                nokia_client.request_qos_boost(selected_phone, duration_minutes=30, reason=sos_reason)
                sms_trace = st.session_state.agent.dispatch_emergency_sms([p_group, p_contact], f"🚨 EMERGENCY SOS: Pilgrim {p_name} near {loc_data['nearest_landmark']}", pilgrim_phone=selected_phone)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"🚨 **EMERGENCY SOS ACTIVATED FOR {p_name}!** Incident registered in Security Command Center & carrier SMS alerts sent.",
                    "trace": [sms_trace]
                })
                st.toast(L["sos_success"])
                st.rerun()

        st.divider()
        st.caption(L["companion_report_caption"])
        if companion_incidents:
            if st.button(L["companion_btn_on"], type="secondary", use_container_width=True, key="btn_companion_resolve"):
                nokia_client.resolve_incident(selected_phone, "Companion confirmed safe (manual)", incident_type="THIRD_PARTY")
                st.toast(L["companion_resolved_toast"])
                st.rerun()
        else:
            with st.form(key="companion_report_form", clear_on_submit=True):
                companion_subject = st.text_input(L["companion_subject_label"], placeholder="e.g. My brother — Mohamed")
                companion_reason = st.text_input(L["companion_reason_label"], placeholder="e.g. Injured leg, needs assistance")
                companion_submitted = st.form_submit_button(L["companion_btn_off"], type="primary", use_container_width=True)
            if companion_submitted:
                subject_text = companion_subject.strip() or "Unnamed companion"
                reason_text = companion_reason.strip() or "Companion reported needing assistance"
                nokia_client.register_incident(
                    selected_phone, reason_text, profile_data, loc_data,
                    incident_type="THIRD_PARTY", subject=subject_text
                )
                st.toast(L["companion_logged_toast"])
                st.rerun()

    with col_chat:
        st.write(f"**{L['quick_actions']}**")
        qc1, qc2, qc3 = st.columns(3)
        if qc1.button(L["qa_loc"], key="btn_qa_loc", use_container_width=True):
            st.session_state.pending_prompt = L["qa_loc"]
            st.rerun()
        if qc2.button(L["qa_sig"], key="btn_qa_sig", use_container_width=True):
            st.session_state.pending_prompt = L["qa_sig"]
            st.rerun()
        if qc3.button(L["qa_gate"], key="btn_qa_gate", use_container_width=True):
            st.session_state.pending_prompt = L["qa_gate"]
            st.rerun()

        with st.expander(L["expand_map"], expanded=False):
            m_large = folium.Map(location=[loc_data['latitude'], loc_data['longitude']], zoom_start=18)
            folium.Marker([loc_data['latitude'], loc_data['longitude']], popup=f"Pilgrim: {p_name}", icon=folium.Icon(color="red")).add_to(m_large)
            folium.Marker([21.4225, 39.8262], popup="Kaaba Center", icon=folium.Icon(color="green")).add_to(m_large)
            st_folium(m_large, height=300, width=650)

        st.divider()

        # --- Chat history (rendered first so a just-sent user message is
        # visible immediately, before the assistant's reply comes back) ---
        chat_box = st.container(height=440)
        with chat_box:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    if message.get("image"):
                        st.image(message["image"], width=200)
                    if message.get("has_audio"):
                        st.caption("🎙️ Voice message sent")
                    st.markdown(message["content"])
                    if message.get("trace") and st.session_state.setting_trace_vis:
                        with st.status("🤖 Agent Reasoning Trace", expanded=True):
                            for i, step in enumerate(message["trace"], start=1):
                                st.markdown(f"**Step {i}: `{step['tool']}`**")
                                st.write(step.get("reasoning", "Called this tool to gather information needed for the reply."))
                                if step.get("args"):
                                    st.caption("Arguments:")
                                    st.json(step["args"])
                                if step.get("result"):
                                    st.caption("Result:")
                                    st.json(step["result"])
                                if i < len(message["trace"]):
                                    st.markdown("---")
                    elif message.get("trace"):
                        tool_names = ", ".join(f"`{s['tool']}`" for s in message["trace"])
                        with st.status(f"🤖 Reasoning Trace — {len(message['trace'])} step(s)", expanded=False):
                            st.write(f"Called: {tool_names}")
                            st.caption("Toggle 'Always Expand AI Reasoning Trace' in settings for full step-by-step detail.")

        # --- Multimodal attachment controls, directly above the input, next
        # to where the message is actually composed and sent ---
        img_bytes, aud_bytes = None, None
        media_key = st.session_state.media_widget_key
        with st.expander(L["multimodal_expander"], expanded=False):
            mcol1, mcol2 = st.columns(2)
            with mcol1:
                uploaded_img = st.file_uploader(
                    L["upload_img"], type=["jpg", "png", "jpeg"], key=f"img_upload_{media_key}"
                )
                if uploaded_img:
                    img_bytes = uploaded_img.getvalue()
                    st.image(img_bytes, width=160)
            with mcol2:
                audio_input = st.audio_input(L["record_audio"], key=f"audio_input_{media_key}")
                if audio_input:
                    aud_bytes = audio_input.getvalue()

            if img_bytes or aud_bytes:
                st.caption("📎 Attached — press **Send** below (or type a message and send) to submit it.")
                send_media_clicked = st.button("📤 Send attachment now", key=f"send_media_{media_key}", type="primary")
            else:
                send_media_clicked = False

        user_input = st.chat_input(L["chat_placeholder"])
        active_prompt = user_input or st.session_state.pending_prompt

        # A media signature (not just presence) so a still-attached-but-
        # already-sent file never fires a second time, even if the widget
        # key reset hasn't visibly cleared it yet on this rerun.
        media_signature = None
        if img_bytes or aud_bytes:
            media_signature = (len(img_bytes) if img_bytes else 0, len(aud_bytes) if aud_bytes else 0, active_prompt)

        should_send_media = (img_bytes or aud_bytes) and (
            active_prompt or send_media_clicked
        ) and media_signature != st.session_state.last_sent_media_signature

        if active_prompt and not (img_bytes or aud_bytes):
            should_send_text_only = True
        else:
            should_send_text_only = False

        if should_send_text_only or should_send_media:
            st.session_state.pending_prompt = None
            prompt_text = active_prompt if active_prompt else "Please analyze the attached media."

            user_message = {"role": "user", "content": prompt_text}
            if img_bytes:
                user_message["image"] = img_bytes
            if aud_bytes:
                user_message["has_audio"] = True
            st.session_state.messages.append(user_message)

            if media_signature is not None:
                st.session_state.last_sent_media_signature = media_signature
            # Reset the uploader/audio widgets now that this attachment has
            # been captured into the message history — prevents resending on
            # the next rerun (the root cause of the analysis loop).
            if img_bytes or aud_bytes:
                st.session_state.media_widget_key += 1

            # Build short-term in-session history (text only) from everything
            # before this new user message, so the agent can recall earlier
            # facts (e.g. a name mentioned a few turns back).
            history_for_agent = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
            ]

            with chat_box:
                with st.chat_message("assistant"):
                    status_placeholder = st.empty()
                    status_placeholder.info("🔎 Analyzing query and calling Nokia APIs…")

                    def _update_status(label):
                        status_placeholder.info(f"🔎 {label}")

                    result = st.session_state.agent.analyze_and_respond(
                        pilgrim_query=prompt_text,
                        phone_number=selected_phone,
                        profile_data=profile_data,
                        language=st.session_state.lang,
                        image_bytes=img_bytes,
                        audio_bytes=aud_bytes,
                        history=history_for_agent,
                        on_status=_update_status,
                    )
                    status_placeholder.empty()

                    resp_text = result.get("response") or result.get("error", "Error processing request.")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": resp_text,
                        "trace": result.get("trace")
                    })
                    st.rerun()

# TAB 2: AUTHORITY COMMAND CENTER
with tab_authority:
    if not st.session_state.cmd_authenticated:
        st.title(L["auth_title"])
        passcode = st.text_input(L["auth_prompt"], type="password")
        if st.button(L["auth_btn"]):
            if passcode in ["1971", "admin", "999"]:
                st.session_state.cmd_authenticated = True
                st.rerun()
            else:
                st.error(L["auth_err"])
    else:
        st.title(L["cmd_title"])
        if st.button("🔒 Lock Command Center"):
            st.session_state.cmd_authenticated = False
            st.rerun()

        st.divider()

        all_alerts = st.session_state.agent.nokia.alerts

        # --- Dashboard stats row: real active/resolved counts + clearly
        # labeled simulated weather (no live weather feed in this build) ---
        weather = st.session_state.agent.nokia.get_simulated_weather()
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        stat_col1.metric("🚨 Active Incidents", len([a for a in all_alerts if a.get("status") == "ACTIVE"]))
        stat_col2.metric("✅ Resolved Incidents", len([a for a in all_alerts if a.get("status") == "RESOLVED"]))
        stat_col3.metric(f"🌡️ {weather['location']} Temp", f"{weather['temperature_c']}°C")
        stat_col4.metric("💧 Humidity", f"{weather['humidity_pct']}%")
        st.caption(f"⚠️ Weather figures are {weather['source']} — {weather['condition']}" + (" — heat advisory in effect" if weather.get("heat_advisory") else ""))

        # --- Demo/testing control: clearly labeled, only for showing the
        # zone-clustering alert live. Not a real emergency intake path. ---
        with st.expander("🧪 DEMO TOOL — Simulate Test Incident (for judging/demo only)", expanded=False):
            st.caption("Creates a fake incident instantly so you can demonstrate the zone-clustering alert without waiting for real chat-triggered emergencies.")
            demo_zone_labels = [z["zone"] for z in HAJJ_ZONES]
            demo_zone_pick = st.selectbox("Zone for simulated incident:", demo_zone_labels, key="demo_zone_pick")
            demo_type = st.radio("Incident type:", ["SELF", "THIRD_PARTY"], horizontal=True, key="demo_type_pick")
            if st.button("➕ Create Simulated Incident", key="btn_demo_incident"):
                demo_zone_idx = demo_zone_labels.index(demo_zone_pick)
                demo_phone = f"+9665DEMO{len(all_alerts):04d}"
                demo_loc = st.session_state.agent.nokia.set_simulated_zone(demo_phone, demo_zone_idx)
                demo_profile = {"name": f"Demo Pilgrim {len(all_alerts)+1}", "id_num": "DEMO-ID", "group": "", "contact": "", "medical": "None"}
                if demo_type == "SELF":
                    st.session_state.agent.nokia.register_incident(
                        demo_phone, "[DEMO] Simulated self-emergency for testing", demo_profile, demo_loc, incident_type="SELF"
                    )
                else:
                    st.session_state.agent.nokia.register_incident(
                        demo_phone, "[DEMO] Simulated companion report for testing", demo_profile, demo_loc,
                        incident_type="THIRD_PARTY", subject="Demo companion"
                    )
                st.toast(f"🧪 Simulated {demo_type} incident created in {demo_zone_pick}.")
                st.rerun()

        # --- Zone-based listing: real counts from user_locations + alerts ---
        with st.expander("🗺️ Zone Summary (Pilgrims & Incidents by Zone)", expanded=False):
            zone_summary = st.session_state.agent.nokia.get_zone_summary()
            for z in zone_summary:
                zc1, zc2, zc3 = st.columns([2, 1, 1])
                zc1.markdown(f"**{z['zone']}**\n\n_{z['nearest_landmark']}_")
                zc2.metric("Pilgrims Tracked", z["pilgrim_count"])
                zc3.metric("Active Incidents", z["active_incident_count"])

        st.divider()

        m_col1, m_col2 = st.columns([1, 1])

        with m_col1:
            st.subheader("📊 Regional Command Map")
            mc1, mc2 = st.columns(2)
            mc1.metric("Active SOS Alerts", len([a for a in all_alerts if a.get("status") == "ACTIVE"]))
            mc2.metric("Resolved Incidents", len([a for a in all_alerts if a.get("status") == "RESOLVED"]))

            map_cmd = folium.Map(location=[21.4225, 39.8262], zoom_start=15)
            for alert in all_alerts:
                loc = alert.get("location", {})
                is_act = alert.get("status") == "ACTIVE"
                folium.Marker(
                    [loc.get("latitude", 21.4225), loc.get("longitude", 39.8262)],
                    popup=f"SOS #{alert['id']}: {alert.get('phone_number')}",
                    icon=folium.Icon(color="red" if is_act else "gray")
                ).add_to(map_cmd)
            st_folium(map_cmd, height=450, width=500)

        with m_col2:
            render_command_feed(L)