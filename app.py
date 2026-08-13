import streamlit as st
import folium
from streamlit_folium import st_folium
from agent_core import RafiqAgent
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="RAFIQ (رفيق) — Telecom AI Pilgrim Safety Layer",
    page_icon="🕋",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    st.session_state.setting_trace_vis = True

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

def is_sos_active_for_user(user_name):
    alerts = st.session_state.agent.nokia.alerts
    for alert in alerts:
        if alert.get("status") == "ACTIVE" and alert.get("profile", {}).get("name") == user_name:
            return True
    return False

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
        "qod_header": "⚡ 5G Quality on Demand (QoD)", "qod_active": "🟢 Elevated Priority Active",
        "qod_inactive": "⚪ Standard Network QoS", "sos_btn_off": "🚨 EMERGENCY SOS (TAP TO ACTIVATE)",
        "sos_btn_on": "🟢 SOS ACTIVE — TAP TO CANCEL",
        "sos_success": "🚨 SOS Dispatched! Elevated 5G priority activated & carrier SMS alerts sent.",
        "sos_cancelled": "⚠️ SOS Cancelled. 5G network priority restored to standard.",
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
        "qod_header": "⚡ جودة الاتصال عند الطلب (5G QoD)", "qod_active": "🟢 أولوية شبكة 5G العالية مفعّلة حالياً",
        "qod_inactive": "⚪ أولوية الاتصال العادية", "sos_btn_off": "🚨 إرسال بلاغ طوارئ (اضغط للتفعيل)",
        "sos_btn_on": "🟢 البلاغ نشط — اضغط للإلغاء (إنذار خاطئ)",
        "sos_success": "🚨 تم إرسال البلاغ! تم رفع أولوية الشبكة وإرسال رسائل SMS.",
        "sos_cancelled": "⚠️ تم إلغاء البلاغ وإعادة أولوية الشبكة إلى وضعها الطبيعي.",
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
    st.subheader(labels["feed_header"])
    
    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        feed_filter = st.radio("Filter Incidents:", ["All Incidents", "Active Only", "Resolved Only"], horizontal=True, key="cmd_feed_filter")
    
    with f_col2:
        if [a for a in st.session_state.agent.nokia.alerts if a.get("status") == "RESOLVED"]:
            if st.button(labels["clear_all_btn"], key="btn_clear_all_res"):
                st.session_state.agent.nokia.alerts[:] = [a for a in st.session_state.agent.nokia.alerts if a.get("status") == "ACTIVE"]
                st.toast("🧹 Cleared resolved incident records.")
                st.rerun()

    search_query = st.text_input("🔍 Search Incidents (Name, ID, Phone):", key="cmd_search").strip().lower()
    current_alerts = st.session_state.agent.nokia.alerts
    
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
            user_name = prof.get("name", alert.get("phone_number", "Unknown Pilgrim"))
            badge_status = "🟢 ACTIVE 5G BOOST" if is_active else "🔴 RESOLVED"
            alert_id = alert["id"]
            
            with st.expander(f"⚠️ Incident #{alert_id} — Pilgrim: {user_name} ({badge_status})", expanded=is_active):
                st.info(f"**SOS / AI Emergency Message:** *\"{alert.get('reason', 'Direct Emergency SOS triggered.')}\"*")
                
                ic1, ic2 = st.columns(2)
                ic1.markdown(f"**Full Name:** `{user_name}`\n\n**Passport/ID:** `{prof.get('id_num', 'N/A')}`\n\n**MSISDN:** `{alert.get('phone_number')}`")
                ic2.markdown(f"**Group Leader:** `{prof.get('group', 'N/A')}`\n\n**Emergency Contact:** `{prof.get('contact', 'N/A')}`\n\n**Medical Notes:** `{prof.get('medical', 'None Listed')}`")
                
                st.divider()
                loc1, loc2 = st.columns(2)
                loc1.markdown(f"**Zone:** `{loc.get('zone', 'Makkah Core')}`\n\n**Landmark:** `{loc.get('nearest_landmark', 'Masjid al-Haram')}`\n\n**GPS:** `{loc.get('latitude')}, {loc.get('longitude')}`")
                loc2.markdown(f"**Accuracy Radius:** `{loc.get('accuracy_radius_m', 25)} meters`\n\n**Timestamp:** `{alert.get('timestamp', 'N/A')}`")

                st.divider()
                act1, act2 = st.columns(2)
                if is_active:
                    if act1.button(labels["dispatch_btn"], key=f"disp_{alert_id}"):
                        st.success(f"Security unit dispatched to {loc.get('nearest_landmark')} for pilgrim '{user_name}'.")
                    if act2.button(labels["resolve_btn"], key=f"res_{alert_id}", type="primary"):
                        alert["status"] = "RESOLVED"
                        remaining = [a for a in st.session_state.agent.nokia.alerts if a.get("status") == "ACTIVE" and a.get("phone_number") == alert.get("phone_number")]
                        if not remaining:
                            st.session_state.agent.nokia.deactivate_qos_boost(alert.get("phone_number"))
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
        st.markdown(f"**Zone:** `{loc_data['zone']}`\n\n**Landmark:** `{loc_data['nearest_landmark']}`")

        m_preview = folium.Map(location=[loc_data['latitude'], loc_data['longitude']], zoom_start=16)
        folium.Marker([loc_data['latitude'], loc_data['longitude']], popup=f"Pilgrim: {p_name}", icon=folium.Icon(color="red", icon="user")).add_to(m_preview)
        st_folium(m_preview, height=180, width=300)

        st.divider()
        is_user_sos_on = is_sos_active_for_user(p_name) or nokia_client.check_qos_status(selected_phone)
        
        st.subheader(L["qod_header"])
        if is_user_sos_on:
            st.success(f"{L['qod_active']} ({p_name})")
        else:
            st.info(L["qod_inactive"])

        st.divider()
        if is_user_sos_on:
            if st.button(L["sos_btn_on"], type="secondary", use_container_width=True):
                for alert in nokia_client.alerts:
                    if alert.get("status") == "ACTIVE" and alert.get("phone_number") == selected_phone:
                        alert["status"] = "RESOLVED"
                nokia_client.deactivate_qos_boost(selected_phone)
                st.toast(L["sos_cancelled"])
                st.rerun()
        else:
            if st.button(L["sos_btn_off"], type="primary", use_container_width=True):
                sos_reason = f"Manual Emergency SOS triggered by {p_name} near {loc_data['nearest_landmark']}"
                nokia_client.register_incident(selected_phone, sos_reason, profile_data, loc_data)
                nokia_client.request_qos_boost(selected_phone, 30, sos_reason)
                sms_trace = st.session_state.agent.dispatch_emergency_sms([p_group, p_contact], f"🚨 EMERGENCY SOS: Pilgrim {p_name} near {loc_data['nearest_landmark']}")
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"🚨 **EMERGENCY SOS ACTIVATED FOR {p_name}!** Incident registered in Security Command Center & carrier SMS alerts sent.",
                    "trace": [sms_trace]
                })
                st.toast(L["sos_success"])
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

        img_bytes, aud_bytes = None, None
        with st.expander(L["multimodal_expander"], expanded=False):
            uploaded_img = st.file_uploader(L["upload_img"], type=["jpg", "png", "jpeg"])
            if uploaded_img:
                img_bytes = uploaded_img.getvalue()
                st.image(img_bytes, width=200)

            audio_input = st.audio_input(L["record_audio"])
            if audio_input:
                aud_bytes = audio_input.getvalue()

        st.divider()

        chat_box = st.container(height=500)
        with chat_box:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if message.get("trace") and st.session_state.setting_trace_vis:
                        with st.status("🤖 Agent Function Calling Trace", expanded=True):
                            for step in message["trace"]:
                                st.write(f"⚙️ **Tool:** `{step['tool']}`")
                                if step.get("args"): st.json(step["args"])
                                if step.get("result"): st.json(step["result"])
                    elif message.get("trace"):
                        with st.status("🤖 Agent Reasoning Trace", expanded=False):
                            st.write(f"Executed {len(message['trace'])} network tools.")

        user_input = st.chat_input(L["chat_placeholder"])
        active_prompt = user_input or st.session_state.pending_prompt

        if active_prompt or img_bytes or aud_bytes:
            st.session_state.pending_prompt = None
            prompt_text = active_prompt if active_prompt else "Please analyze the attached media."
            st.session_state.messages.append({"role": "user", "content": prompt_text})
            
            with chat_box:
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing query and calling Nokia APIs..."):
                        result = st.session_state.agent.analyze_and_respond(
                            pilgrim_query=prompt_text,
                            phone_number=selected_phone,
                            profile_data=profile_data,
                            language=st.session_state.lang,
                            image_bytes=img_bytes,
                            audio_bytes=aud_bytes
                        )

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
        m_col1, m_col2 = st.columns([1, 1])
        all_alerts = st.session_state.agent.nokia.alerts

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