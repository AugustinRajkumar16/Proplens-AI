# frontend_app.py
import streamlit as st
import requests
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, timedelta
from html import escape


load_dotenv()
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Proplens — Lead Nurturing CRM", layout="wide")

# --- CSS tweaks: reduce sidebar button size AND narrow login container (300px) ---
st.markdown(
    """
    <style>
    /* Sidebar buttons uniform size */
    [data-testid="stSidebar"] button {
        width: 160px !important;
        height: 40px !important;
        margin-bottom: 8px;
    }

    /* Centered compact login container */
    .login-container {
        max-width: 300px;                /* <-- shrink to 300px */
        margin-left: auto;
        margin-right: auto;
        padding: 12px 14px;
        border: 1px solid #e6e6e6;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        background-color: #ffffff;
    }

    /* Make form inputs fit container */
    .login-container .stTextInput, .login-container .stButton {
        width: 100% !important;
    }

    /* Slightly smaller heading in container */
    .login-container h3 {
        margin-top: 0.25rem;
        margin-bottom: 0.5rem;
        text-align: center;
        font-weight: 600;
    }

    /* Floating toast (top-right) */
    .backend-toast {
        position: fixed;
        top: 16px;
        right: 16px;
        z-index: 9999;
        padding: 8px 12px;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 6px 18px rgba(0,0,0,0.12);
        color: white;
        font-size: 14px;
    }
    .backend-toast.ok { background: #16a34a; } /* green */
    .backend-toast.err { background: #dc2626; } /* red */

    /* Reduce padding around the app header when on small screens */
    @media (max-width: 760px) {
        .login-container { padding: 10px; max-width: 280px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- safe rerun implementation ---
def safe_rerun():
    """
    Robust rerun helper using st.query_params only.
    Toggles _rerun_marker query param to force rerun once.
    """
    qp = st.query_params or {}
    marker = qp.get("_rerun_marker", "0")
    new_marker = "1" if marker == "0" else "0"
    st.query_params = {**qp, "_rerun_marker": new_marker}

# -------------------------
# API helpers
# -------------------------
def api_post(path, json=None, files=None):
    headers = {}
    if st.session_state.get("jwt"):
        headers["Authorization"] = f"Bearer {st.session_state.jwt}"
    url = API_BASE.rstrip("/") + path
    try:
        if files:
            r = requests.post(url, headers=headers, files=files, timeout=120)
        else:
            r = requests.post(url, headers=headers, json=json, timeout=60)
        return r
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

def api_get(path):
    headers = {}
    if st.session_state.get("jwt"):
        headers["Authorization"] = f"Bearer {st.session_state.jwt}"
    try:
        r = requests.get(API_BASE.rstrip("/") + path, headers=headers, timeout=30)
        return r
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

# Filename utilities
UUID_PREFIX_RE = re.compile(r'^[0-9a-fA-F\-]{8,}_')

def clean_filename_display(fname: str) -> str:
    base = os.path.basename(fname)
    base_no_uuid = UUID_PREFIX_RE.sub("", base)
    name_no_ext = os.path.splitext(base_no_uuid)[0]
    return name_no_ext

def list_local_project_names_raw():
    proj = []
    uploads = Path.cwd() / "uploads"
    if uploads.exists():
        for f in uploads.iterdir():
            if f.is_file() and f.suffix.lower() in (".pdf", ".txt"):
                proj.append(f.name)
    return sorted(proj)

def get_project_names():
    raw_files = []
    try:
        r = api_get("/probe_projects/")
        if r and r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "projects" in data:
                raw_files = data["projects"]
    except Exception:
        pass

    if not raw_files:
        raw_files = list_local_project_names_raw()

    display_names = []
    mapping = {}
    for raw in raw_files:
        disp = clean_filename_display(raw)
        if disp not in mapping:
            mapping[disp] = raw
            display_names.append(disp)

    return display_names, mapping

# -------------------------
# Small helper to show a floating toast (HTML)
# -------------------------
def show_backend_toast(ok: bool, message: str, auto_hide_seconds: int = 6):
    """
    Render a small floating toast in the top-right using inline HTML/CSS.
    auto_hide_seconds is a best-effort (JS) hide — works in many streamlit setups.
    """
    cls = "ok" if ok else "err"
    safe_html = f"""
    <div class="backend-toast {cls}" id="backend-toast">{message}</div>
    <script>
    (function() {{
        const el = document.getElementById("backend-toast");
        if (!el) return;
        setTimeout(()=>{{ el.style.display='none'; }}, {int(auto_hide_seconds*1000)});
    }})();
    </script>
    """
    st.markdown(safe_html, unsafe_allow_html=True)

# --- Login and Logout button callbacks ---
def login_user(username, password):
    try:
        r = requests.post(API_BASE + "/auth/login/", json={"username": username, "password": password})
        if r and r.status_code == 200:
            st.session_state.jwt = r.json().get("access_token")
            st.session_state.current_user = username  # store the logged-in username
            # init per-user chat store if missing
            if "agent_chats" not in st.session_state:
                st.session_state.agent_chats = {}
            if username not in st.session_state.agent_chats:
                st.session_state.agent_chats[username] = []
            st.success("Logged in")
            # Probe backend after login
            try:
                probe = api_get("/probe_projects/")
                if probe and probe.status_code == 200:
                    show_backend_toast(True, "Backend: OK — projects loaded")
                else:
                    show_backend_toast(False, "Backend: Unreachable or no projects")
            except Exception:
                show_backend_toast(False, "Backend: Probe failed")
            safe_rerun()
        else:
            st.error("Login failed")
    except Exception as e:
        st.error(f"Login error: {e}")

def logout_user():
    # Clear current user's chat history (optional: keep but user asked remove)
    cur = st.session_state.get("current_user")
    if cur and "agent_chats" in st.session_state:
        st.session_state.agent_chats.pop(cur, None)
    st.session_state.jwt = None
    st.session_state.current_user = None
    show_backend_toast(True, "Logged out", auto_hide_seconds=3)
    safe_rerun()


# -------------------------
# Session init
# -------------------------
if "jwt" not in st.session_state:
    st.session_state.jwt = None
if "shortlist" not in st.session_state:
    st.session_state.shortlist = []
if "agent_settings" not in st.session_state:
    st.session_state.agent_settings = {
        "follow_up_interval_days": 3,
        "max_follow_ups": 3,
        "messaging_focus": ["Property Features & benefits"],
        "ai_response_style": "Professional & formal",
        "urgency_level": "Medium -Moderate urgency",
        "custom_instructions": "",
    }
if "page" not in st.session_state:
    st.session_state.page = "Create Campaign"

pages = [
    "Create Campaign",
    "Campaign Analytics",
    "Property Visit/Call Scheduled",
    "AI Agent Follow-ups",
    "AI Agent Settings",
    "Upload",
    "Agent Chat",
    "Leads",
    "Campaigns",
    "Chroma",
]


# --- LOGIN PAGE ---
if not st.session_state.jwt:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("<h3>Login</h3>", unsafe_allow_html=True)
    with st.form("login_form"):
        u = st.text_input("Username", value="demo")
        p = st.text_input("Password", type="password", value="demo")
        # Call login_user on form submit to handle login and rerun
        st.form_submit_button("Login", on_click=login_user, args=(u, p))
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- MAIN APP WITH SIDEBAR ---
with st.sidebar:
    st.title("Lead Nurturing CRM")
    for p in pages:
        if st.button(p):
            st.session_state.page = p
    st.markdown("---")
    # Logout button with callback and immediate rerun
    st.button("Logout", on_click=logout_user)

page = st.session_state.page


# ---------------------------
# Agent Chat (WhatsApp-style bubbles)
# ---------------------------
def _clean_agent_answer(raw: str, max_sentences: int = 3) -> str:
    """
    Clean backend answer:
      - remove provenance/source blocks like lines starting with 'Source('
      - remove 'Answer (mock):' artifacts
      - collapse whitespace
      - dedupe repeated consecutive sentences
      - keep up to `max_sentences` sentences for a short, high-quality paragraph
    """
    if not raw:
        return "No answer returned."

    # Normalize newlines & strip typical prefixes
    txt = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Remove lines that look like provenance or "Source(...)" blocks
    # Also remove explicit "Provenance" or "Answer (mock):" segments
    # Heuristic: drop any lines starting with "Source(" or lines that are mostly metadata-like
    cleaned_lines = []
    for line in txt.split("\n"):
        s = line.strip()
        # skip obvious provenance lines
        if not s:
            continue
        if s.lower().startswith("source("):
            continue
        if s.lower().startswith("provenance"):
            continue
        if s.lower().startswith("answer (mock)"):
            # strip the trailing 'Answer (mock):' marker but keep following text if present
            parts = re.split(r"answer\s*\(mock\)\s*:\s*", s, flags=re.I)
            if len(parts) > 1 and parts[1].strip():
                cleaned_lines.append(parts[1].strip())
            continue
        # skip lines that look like 'metadata' or JSON-ish
        if s.startswith('"metadata"') or s.startswith("{") or s.startswith("}"):
            continue
        cleaned_lines.append(s)

    if not cleaned_lines:
        return "No substantive content found in documents."

    txt2 = " ".join(cleaned_lines)
    # collapse multiple spaces
    txt2 = re.sub(r"\s+", " ", txt2).strip()

    # Split into sentences (simple heuristic)
    # Keep sentences ending with .!?  or if none, split on commas as fallback
    sentences = re.split(r'(?<=[\.\!\?])\s+', txt2)
    if len(sentences) == 1:
        # try splitting on semicolons or long commas
        sentences = re.split(r'[;]\s+|\s{2,}', txt2)

    # dedupe consecutive identical sentences
    dedup = []
    prev = None
    for s in sentences:
        s_strip = s.strip()
        if not s_strip:
            continue
        if s_strip == prev:
            continue
        dedup.append(s_strip)
        prev = s_strip

    # Keep first N sentences, join to a small paragraph
    short = " ".join(dedup[:max_sentences])
    # final trim to reasonable length (approx)
    if len(short) > 800:
        short = short[:800].rsplit(" ", 1)[0] + "…"

    return short or "No cleaned answer available."

# Bubble CSS (WhatsApp-like)
CHAT_CSS = """
<style>
.chat-row { display: flex; margin-bottom: 8px; }
.chat-bubble { max-width: 78%; padding: 10px 14px; border-radius: 16px; line-height: 1.35; }
.chat-bubble.user { background: #DCF8C6; margin-left: auto; border-bottom-right-radius: 6px; }
.chat-bubble.agent { background: #ffffff; margin-right: auto; border-bottom-left-radius: 6px; border: 1px solid rgba(0,0,0,0.06); }
.chat-meta { font-size: 11px; color: #666; margin-top: 4px; }
.agent-box { padding: 6px 0; }
.container-agent { padding: 8px 10px 16px 10px; background: linear-gradient(#f7f7f7, #f2f2f2); border-radius: 8px; }
</style>
"""


# -- PAGES --

if page == "Create Campaign":
    st.header("Create New Campaign")
    st.write("Filter leads from your CRM and shortlist for nurturing.")

    projects, project_map = get_project_names()
    with st.form("Shortlist Leads for Campaign"):
        st.subheader("Project name enquired")
        project_selected_disp = st.selectbox("Select project", options=projects)

        st.subheader("Budget Range (in numbers)")
        col1, col2 = st.columns(2)
        with col1:
            min_budget = st.number_input("Min budget", min_value=0, value=0, step=10000, help="Enter minimum budget (integer).")
        with col2:
            max_budget = st.number_input("Max budget", min_value=0, value=1000000, step=10000, help="Enter maximum budget (integer).")

        st.subheader("Unit Type")
        UNIT_TYPES = ["Studio", "1 bed", "2 bed", "2 bed w study", "3 bed", "4 bed", "Duplex", "Penthouse"]
        unit_checks = {}

        cols = st.columns(2)
        for idx, ut in enumerate(UNIT_TYPES):
            col_idx = idx % 2
            with cols[col_idx]:
                unit_checks[ut] = st.checkbox(ut, key=f"ut_{ut}")

        st.markdown("---")

        st.subheader("Lead Status (select multiple)")
        LEAD_STATUSES = ["not connected", "connected", "visit scheduled", "visit done not purchased", "purchased", "not interested"]
        status_cols = st.columns(3)
        status_selected = []
        for i, s in enumerate(LEAD_STATUSES):
            chosen = status_cols[i % 3].checkbox(s, key=f"status_{s}")
            if chosen:
                status_selected.append(s)

        st.markdown("---")

        st.subheader("Last Conversation Date (past 3 years)")
        today = date.today()
        three_years_ago = today - timedelta(days=3*365)
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            last_from = st.date_input("From", value=three_years_ago, min_value=three_years_ago, max_value=today)
        with dcol2:
            last_to = st.date_input("To", value=today, min_value=three_years_ago, max_value=today)

        filters_selected = 0
        if project_selected_disp:
            filters_selected += 1
        if (min_budget > 0) or (max_budget < 1000000):
            filters_selected += 1
        if any(unit_checks.values()):
            filters_selected += 1
        if status_selected:
            filters_selected += 1
        if last_from != three_years_ago or last_to != today:
            filters_selected += 1

        st.info(f"🔎 {filters_selected} filters selected — Ready to search leads")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            submit = st.form_submit_button("Shortlist leads")
            if submit:
                selected_originals = [project_map[d] for d in [project_selected_disp] if d in project_map] if project_selected_disp else []
                payload = {
                    "projects": selected_originals,
                    "min_budget": int(min_budget),
                    "max_budget": int(max_budget),
                    "unit_types": [k for k,v in unit_checks.items() if v],
                    "statuses": status_selected,
                    "last_conv_from": last_from.isoformat(),
                    "last_conv_to": last_to.isoformat(),
                }
                if "shortlist" not in st.session_state:
                    st.session_state.shortlist = ["lead-1", "lead-2"]
                st.success(f"Shortlisted {len(st.session_state.shortlist)} leads (demo)")
                st.write("Payload that would be sent to backend:")
                for key, val in payload.items():
                    st.write(f"**{key}**: {val}")

                st.subheader("Shortlisted Leads Details")
                for idx, lead_id in enumerate(st.session_state.shortlist, 1):
                    st.write(f"Lead {idx}:")
                    st.write(f"- ID: {lead_id}")
                    st.write(f"- Name: Demo Lead {idx}")
                    st.write(f"- Status: Connected")
                    st.write("---")

        with btn_col2:
            clear_filters = st.form_submit_button("Clear all filters")
            if clear_filters:
                for ut in UNIT_TYPES:
                    st.session_state.pop(f"ut_{ut}", None)
                for s in LEAD_STATUSES:
                    st.session_state.pop(f"status_{s}", None)
                safe_rerun()

    st.markdown("---")

    st.subheader("Campaign details")
    campaign_name = st.text_input("Campaign name", value=f"Campaign - {today.isoformat()}")
    email_subject = st.text_input("Email subject", value="About the property you enquired")
    message_prompt = st.text_area(
        "Message prompt (instructions for AI)",
        value="Write a short personalised outreach message highlighting key benefits and CTA to schedule a visit."
    )

    if st.button("Generate campaign messages (AI)"):
        if not st.session_state.shortlist:
            st.warning("No shortlisted leads — shortlist leads first.")
        else:
            selected_originals = [project_map[d] for d in [project_selected_disp] if d in project_map]
            prompt = f"Generate personalized message for leads {st.session_state.shortlist}. Use project(s) {', '.join(selected_originals)}. Instructions: {message_prompt}"
            r = api_post("/agent/query/", json={"query": prompt, "context": {"projects": selected_originals}})
            if r and r.status_code == 200:
                st.success("Generated messages (mock)")
                st.write(r.json().get("answer"))
            else:
                st.error("Agent generation failed or no response. See logs.")

elif page == "Campaign Analytics":
    st.header("Campaign Analytics")
    st.write("Detailed Analytics and performance metrics for your lead nurturing Campaigns")

    st.subheader("Campaign Analytics")

    projects, project_map = get_project_names()
    if not projects:
        st.info("No projects found (uploads/ empty). Upload brochures to populate projects.")

    selected_disp = st.selectbox("Select project", options=projects if projects else ["(no projects)"])

    def fetch_metrics_for_project(original_filename: str | None):
        if not original_filename:
            return None
        try:
            q = f"/campaigns/analytics?project={original_filename}"
            r = api_get(q)
            if r and r.status_code == 200:
                data = r.json()
                if all(k in data for k in ("leads_shortlisted", "messages_sent", "unique_responses", "goals_achieved")):
                    return {
                        "leads_shortlisted": int(data["leads_shortlisted"]),
                        "messages_sent": int(data["messages_sent"]),
                        "unique_responses": int(data["unique_responses"]),
                        "goals_achieved": int(data["goals_achieved"]),
                    }
        except Exception:
            pass
        return None

    selected_original = project_map.get(selected_disp) if project_map else None
    metrics = fetch_metrics_for_project(selected_original) or fetch_metrics_for_project(selected_disp)

    if metrics is None:
        metrics = {
            "leads_shortlisted": 0,
            "messages_sent": 0,
            "unique_responses": 0,
            "goals_achieved": 0,
        }

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    c1.metric("Leads shortlisted", value=metrics["leads_shortlisted"])
    c2.metric("Messages Sent", value=metrics["messages_sent"])
    c3.metric("Unique Responses", value=metrics["unique_responses"])
    c4.metric("Goals Achieved", value=metrics["goals_achieved"])

    st.markdown("---")

elif page == "Property Visit/Call Scheduled":
    st.header("Property Visit / Call Scheduled")
    st.write("This page is intentionally left blank for now — place to manage scheduled visits and calls.")
    st.info("Planned features: calendar view, schedule details, reschedule/cancel actions, assigned agent contact info.")

elif page == "AI Agent Follow-ups":
    st.header("AI Agent Follow-ups")
    st.write("This page is intentionally left blank for now — place to review agent-initiated followups, status, and conversation threads.")
    st.info("Planned features: conversation timeline, re-send message, escalate to human, mark as purchased/not interested.")

elif page == "AI Agent Settings":
    st.header("AI Agent Settings")
    st.write("Configure how your AI agent behaves during lead nurturing conversations.")

    with st.form("agent_settings_form"):
        st.subheader("Nurturing Agent Settings")
        fu_interval = st.number_input("Follow-up interval (days)", min_value=0, value=st.session_state.agent_settings.get("follow_up_interval_days", 3))
        max_followups = st.number_input("Maximum Follow-ups (if no response)", min_value=0, value=st.session_state.agent_settings.get("max_follow_ups", 3))
        st.markdown("**Messaging Focus for Follow-ups**")
        focus_options = ["Property Features & benefits", "Pricing & Investment Opportunities", "Location & Amenities", "Financing Options", "Limited Time Offers"]
        default_focus = st.session_state.agent_settings.get("messaging_focus", ["Property Features & benefits"])
        focus_selected = st.selectbox(
            "Select messaging focus",
            options=focus_options,
            index=focus_options.index(default_focus[0]) if default_focus else 0
        )
        st.markdown("**AI Response style**")
        response_style = st.selectbox("AI Response style", options=["Professional & formal", "Casual & friendly", "Concise & direct"], index=0)
        st.markdown("**Urgency Level**")
        urgency_level = st.selectbox("Urgency Level", options=["Low - Informational", "Medium -Moderate urgency", "High - Immediate action"], index=1)
        st.markdown("**Custom AI instructions**")
        custom_instructions = st.text_area("Enter any specific instructions for the AI agent's behaviour, tone, or conversation handling...", value=st.session_state.agent_settings.get("custom_instructions", ""), height=140)

        st.caption("Provide specific guidance for how the AI should interact with leads. These settings affect automated follow-ups and message tone.")

        st.markdown("### Current configuration")
        agent_settings = st.session_state.agent_settings
        for key, val in agent_settings.items():
            if isinstance(val, list):
                display_val = ", ".join(str(i) for i in val)
            else:
                display_val = str(val)
            st.write(f"**{key}**: {display_val}")

        submitted = st.form_submit_button("Save settings")
        if submitted:
            st.session_state.agent_settings = {
                "follow_up_interval_days": int(fu_interval),
                "max_follow_ups": int(max_followups),
                "messaging_focus": [focus_selected],
                "ai_response_style": response_style,
                "urgency_level": urgency_level,
                "custom_instructions": custom_instructions,
            }
            st.success("Agent settings saved (local session). Use API to persist server-side if available.")

# -------------------------
# Extra pages: Upload, Agent, Leads, Campaigns, Chroma
# -------------------------

# Upload page (replace existing Upload block)
if page == "Upload":
    st.header("Upload Brochure / Document")
    uploaded_list = st.file_uploader("Choose PDF or TXT (you can select multiple)", type=["pdf", "txt"], accept_multiple_files=True)
    if uploaded_list:
        st.write(f"{len(uploaded_list)} file(s) selected.")
        for f in uploaded_list:
            st.write(f"- {f.name} ({f.type or 'n/a'})")
        if st.button("Upload and ingest all (blocking)"):
            for f in uploaded_list:
                with st.spinner(f"Uploading {f.name} ..."):
                    mime = "application/pdf" if f.name.lower().endswith(".pdf") else "text/plain"
                    files = {"file": (f.name, f.getvalue(), mime)}
                    # send blocking request so indexing runs on server (background=false)
                    r = api_post("/documents/upload/?background=false", files=files)
                    if r is None:
                        st.error(f"Upload failed for {f.name} (no response).")
                        continue
                    if r.status_code in (200, 201, 202):
                        try:
                            data = r.json()
                        except Exception:
                            data = None
                        job_id = data.get("job_id") if isinstance(data, dict) else None
                        stored_path = data.get("stored_path") if isinstance(data, dict) else None
                        st.success(f"Uploaded {f.name} — indexing started/completed.")
                        if job_id:
                            st.write(f"Job ID: `{job_id}`")
                        if stored_path:
                            st.write("Stored file:", os.path.basename(stored_path))
                    else:
                        st.error(f"Upload error {r.status_code}: {r.text}")


# Agent Chat page (replace the current Agent / Agent Chat block)
if page == "Agent Chat":
    st.markdown(CHAT_CSS, unsafe_allow_html=True)

    # ensure per-login chat store: key by JWT token for per-login sessions
    # fallback to 'anon' if not logged in
    jwt_key = st.session_state.get("jwt") or "anon"
    if "agent_chats" not in st.session_state:
        st.session_state["agent_chats"] = {}
    if jwt_key not in st.session_state["agent_chats"]:
        st.session_state["agent_chats"][jwt_key] = []

    chats = st.session_state["agent_chats"][jwt_key]

    st.header("Agent Chat")

    # Show conversation area inside a styled container
    st.markdown('<div class="container-agent">', unsafe_allow_html=True)
    if not chats:
        st.info("No messages yet. Ask a question below.")
    else:
        # render each message as bubble
        for m in chats:
            role = m.get("role", "user")
            text = m.get("text", "")
            safe_text = escape(text)  # escape to avoid raw HTML injection
            if role == "user":
                # right-aligned bubble
                html = f'''
                <div class="chat-row">
                  <div class="chat-bubble user">{safe_text}</div>
                </div>
                '''
            else:
                # left-aligned agent bubble
                html = f'''
                <div class="chat-row">
                  <div class="chat-bubble agent">{safe_text}</div>
                </div>
                '''
            st.markdown(html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Input form (safe lifecycle)
    with st.form("agent_form"):
        user_query = st.text_area("Ask anything (RAG or DB)", height=120, key="agent_q_textarea")
        submit = st.form_submit_button("Submit query")
        if submit:
            if not user_query or not user_query.strip():
                st.warning("Type a query first.")
            else:
                # append user message
                st.session_state["agent_chats"][jwt_key].append({"role": "user", "text": user_query.strip()})

                # call backend
                with st.spinner("Querying agent..."):
                    r = api_post("/agent/query/", json={"query": user_query.strip(), "context": {}})
                    if r is None:
                        st.error("No response from backend.")
                    elif r.status_code != 200:
                        st.error(f"Agent error {r.status_code}: {r.text}")
                    else:
                        payload = r.json()
                        raw_answer = payload.get("answer") or ""
                        # Clean and shorten answer (hide provenance)
                        cleaned = _clean_agent_answer(raw_answer, max_sentences=3)
                        # Ensure the answer is presented as a short paragraph (no sources shown)
                        st.session_state["agent_chats"][jwt_key].append({"role": "assistant", "text": cleaned})
                        # refresh UI (toggle query param)
                        safe_rerun()

# Leads page
if page == "Leads":
    st.header("Leads")
    if st.button("Refresh leads"):
        r = api_get("/leads/")
        if r and r.status_code == 200:
            leads = r.json()
            st.dataframe(leads)
        else:
            st.warning("Could not fetch leads")
    with st.expander("Create new lead"):
        name = st.text_input("Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        if st.button("Create lead"):
            if not name or not email:
                st.warning("Name and email required")
            else:
                r = api_post("/leads/", json={"name": name, "email": email, "phone": phone})
                if r and r.status_code in (200,201):
                    st.success("Lead created")
                else:
                    st.error(f"Failed to create lead: {r.status_code if r else 'no response'}")

# Campaigns page (very basic)
if page == "Campaigns":
    st.header("Campaign Composer (MVP)")
    st.write("Select leads by entering comma-separated IDs (e.g. 1,2)")
    ids = st.text_input("Lead IDs")
    brochure = st.text_input("Brochure (optional) — file name in Chroma")
    subject = st.text_input("Email subject", "About property")
    body_prompt = st.text_area("Prompt for agent to generate message", "Write a friendly email highlighting amenities.")
    if st.button("Generate message"):
        if not ids.strip():
            st.warning("Enter at least one lead ID.")
        else:
            prompt = f"""Generate an email for leads {ids}. Use brochure: {brochure}. Instructions: {body_prompt}"""
            r = api_post("/agent/query/", json={"query": prompt, "context": {"brochure": brochure}})
            if r and r.status_code == 200:
                st.subheader("Generated message")
                st.write(r.json().get("answer"))
            else:
                st.error("Failed to generate message")

# Chroma page
if page == "Chroma":
    st.header("Chroma Collections (diagnostic)")
    st.write("If you have a diagnostic endpoint like /probe_chroma/ on the backend, press the button.")
    if st.button("List collections (probe backend)"):
        try:
            r = api_get("/probe_chroma/")
            if r and r.status_code == 200:
                data = r.json()
                cols = data.get("collections") if isinstance(data, dict) else None
                if cols and isinstance(cols, (list, tuple)):
                    # show as table / dataframe
                    try:
                        import pandas as _pd
                        df = _pd.DataFrame({"collection": cols})
                        st.table(df)
                    except Exception:
                        # fallback: key-value list
                        for i, c in enumerate(cols):
                            st.write(f"- **{i+1}.** {c}")
                else:
                    st.info("No collections found.")
            else:
                st.warning("No response from diagnostic endpoint; check backend.")
        except Exception as e:
            st.error(str(e))

