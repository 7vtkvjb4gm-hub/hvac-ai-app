import pandas as pd
import streamlit as st
import core

st.set_page_config(page_title="HVAC Growth Assistant", page_icon="🌡️", layout="wide")

# ---------- Branding / CSS ----------
st.markdown("""<style>
h1, h2, h3 {letter-spacing:-0.01em;}
.hero {background:#0B3C4D; color:#F7FAFB; padding:1.6rem 1.8rem; border-radius:6px; margin-bottom:1rem;}
.hero h1 {color:#F7FAFB; margin:0 0 .3rem 0;}
.hero p {margin:0; color:#BFE3EE; font-size:1.05rem;}
.big {font-size:2.2rem; font-weight:700; color:#0B6E8A; line-height:1.1;}
div[data-testid="stMetricValue"] {color:#0B6E8A;}
</style>""", unsafe_allow_html=True)

def secret(key, default=""):
    try: return st.secrets.get(key, default)
    except Exception: return default

COMPANY = secret("COMPANY_NAME", "Your HVAC Company")

@st.cache_resource
def get_sheet():
    """Optional free Google Sheets CRM. Returns None (-> local CSV) if not configured."""
    try:
        import gspread
        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        return gc.open(secret("SHEET_NAME", "HVAC Leads")).sheet1
    except Exception:
        return None

def llm_generate(prompt, task, service, season):
    provider = secret("LLM_PROVIDER", "gemini")
    key = secret("GEMINI_API_KEY") if provider == "gemini" else secret("GROQ_API_KEY")
    model = secret("GEMINI_MODEL", "gemini-2.5-flash") if provider == "gemini" else secret("GROQ_MODEL", "llama-3.3-70b-versatile")
    if not key:
        return core.offline_draft(task, COMPANY, service, season)
    try:
        return core.ask_llm(prompt, provider, key, model)
    except Exception as e:
        detail = getattr(getattr(e, "response", None), "text", "")[:300]
        st.error(f"The AI request failed: {e} {detail}")
        return core.offline_draft(task, COMPANY, service, season)

# ---------- Session state + sidebar navigation ----------
PAGES = ["Home", "Business Assessment", "ROI Calculator", "Content Studio", "Use Case Library", "Request Service", "Leads (Admin)"]
ss = st.session_state
ss.setdefault("page", "Home"); ss.setdefault("answers", {}); ss.setdefault("score", None); ss.setdefault("draft", "")

def go(page): ss.page = page

with st.sidebar:
    st.header(COMPANY)
    for p in PAGES:
        st.button(p, key=f"nav_{p}", on_click=go, args=(p,), use_container_width=True,
                  type="primary" if ss.page == p else "secondary")
    st.caption("Runs free: Streamlit Cloud, Google Sheets, Gemini or Groq free tier.")

page = ss.page

def lead_form(source, service_default=None, notes_default=""):
    with st.form(f"lead_{source}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name"); phone = c2.text_input("Phone")
        email = c1.text_input("Email (optional)")
        service = c2.selectbox("What do you need?", core.SERVICES, index=core.SERVICES.index(service_default) if service_default in core.SERVICES else 0)
        notes = st.text_area("Anything we should know?", value=notes_default)
        if st.form_submit_button("Send request", type="primary"):
            lead = dict(name=name, phone=phone, email=email, service=service, notes=notes, source=source, score=ss.score[0] if ss.score else "")
            errs = core.validate_lead(lead)
            if errs:
                for e in errs: st.error(e)
            else:
                core.save_lead(lead, get_sheet())
                st.success("Thanks. We will call you within one business day.")

# ---------- Pages ----------
if page == "Home":
    st.markdown(f"<div class='hero'><h1>{COMPANY}</h1><p>Find out where an AI toolkit can win you more jobs, then put it to work.</p></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.subheader("Assess"); c1.write("Six questions show where your shop loses leads and time.")
    c1.button("Take the assessment", on_click=go, args=("Business Assessment",))
    c2.subheader("Calculate"); c2.write("See what recovered calls and saved admin hours are worth each month.")
    c2.button("Open ROI calculator", on_click=go, args=("ROI Calculator",))
    c3.subheader("Create"); c3.write("Draft review replies, seasonal emails, and texts in seconds.")
    c3.button("Open Content Studio", on_click=go, args=("Content Studio",))

elif page == "Business Assessment":
    st.title("Business assessment")
    with st.form("assessment"):
        picks = {}
        for q in core.QUESTIONS:
            labels = [o[0] for o in q["options"]]
            picks[q["key"]] = (q["text"], dict(q["options"]), st.radio(q["text"], labels, index=None))
        done = st.form_submit_button("See my score", type="primary")
    if done:
        if any(v[2] is None for v in picks.values()):
            st.warning("Answer all six questions to get your score.")
        else:
            ss.answers = {k: v[1][v[2]] for k, v in picks.items()}
            ss.score = core.score_assessment(ss.answers)
    if ss.score:
        score, level, recs = ss.score
        st.markdown(f"<div class='big'>{score}/100</div><b>{level}</b>", unsafe_allow_html=True)
        st.progress(score / 100)
        st.subheader("Your top recommendations")
        for r in recs: st.write("• " + r)
        if not recs: st.write("You are covering the basics. Next, measure lead sources and tune your campaigns.")
        st.subheader("Want help with these?")
        lead_form("assessment", notes_default=f"Assessment score {score}")

elif page == "ROI Calculator":
    st.title("ROI calculator")
    c1, c2 = st.columns(2)
    with c1:
        missed = st.number_input("Missed calls per week", 0, 500, 10)
        avg_job = st.number_input("Average job value ($)", 0, 50000, 450, step=50)
        close = st.slider("Close rate on answered leads", 0, 100, 40) / 100
        recov = st.slider("Share of missed calls you would recover", 0, 100, 50) / 100
    with c2:
        hrs = st.number_input("Admin hours per week (scheduling, follow-up)", 0.0, 200.0, 10.0)
        rate = st.number_input("Admin hourly cost ($)", 0.0, 500.0, 25.0)
        cut = st.slider("Admin time automated", 0, 100, 30) / 100
        tool = st.number_input("Monthly tool cost ($)", 0.0, 10000.0, 50.0)
    r = core.roi(missed, avg_job, close, recov, hrs, rate, cut, tool)
    m = st.columns(4)
    m[0].metric("Jobs recovered / mo", f"{r['jobs_recovered']:.1f}")
    m[1].metric("Revenue recovered / mo", f"${r['revenue']:,.0f}")
    m[2].metric("Labor saved / mo", f"${r['labor_saved']:,.0f}")
    m[3].metric("Net gain / mo", f"${r['net']:,.0f}")
    st.caption(f"ROI: {r['roi_pct']:,.0f}%" if r["roi_pct"] is not None else "Enter a tool cost to see ROI %.")
    st.caption("These are estimates from your inputs, not guarantees.")

elif page == "Content Studio":
    st.title("Content Studio")
    st.caption("Prompt Builder: pick the options, review the prompt, edit it, then generate.")
    c1, c2 = st.columns([1, 2])
    with c1:
        task = st.selectbox("Content type", list(core.TEMPLATES))
        service = st.selectbox("Service", core.SERVICES)
        season = st.selectbox("Season", core.SEASONS)
        tone = st.selectbox("Tone", core.TONES)
        rating = st.slider("Review rating", 1, 5, 5) if task == "Google review reply" else 5
        details = st.text_area("Details (review text, offer, price you actually charge)")
    with c2:
        prompt = st.text_area("Prompt (editable)", core.build_prompt(task, COMPANY, service, season, tone, rating, details), height=180,
                              key=f"prompt_{task}_{service}_{season}_{tone}_{rating}_{hash(details)}")
        if st.button("Generate", type="primary"):
            with st.spinner("Writing..."):
                ss.draft = llm_generate(prompt, task, service, season)
        if ss.draft:
            st.text_area("Draft", ss.draft, height=240)
            st.download_button("Download draft", ss.draft, "draft.txt")

elif page == "Use Case Library":
    st.title("AI use cases for HVAC")
    areas = ["All"] + sorted({u["area"] for u in core.USE_CASES})
    pick = st.radio("Area", areas, horizontal=True)
    rows = [u for u in core.USE_CASES if pick == "All" or u["area"] == pick]
    st.dataframe(pd.DataFrame(rows).rename(columns=str.title), hide_index=True, use_container_width=True)

elif page == "Request Service":
    st.title("Request service or a free quote")
    lead_form("website")

elif page == "Leads (Admin)":
    st.title("Leads")
    pw = secret("ADMIN_PASSWORD")
    if pw and st.text_input("Admin password", type="password") != pw:
        st.info("Enter the admin password to view leads."); st.stop()
    leads = core.load_leads(get_sheet())
    if leads:
        df = pd.DataFrame(leads); st.dataframe(df, hide_index=True, use_container_width=True)
        st.download_button("Download CSV", df.to_csv(index=False), "leads.csv")
        st.caption("Stored in Google Sheets." if get_sheet() else "Stored in local leads.csv (resets on Streamlit Cloud restarts). Connect Google Sheets to keep leads.")
    else:
        st.info("No leads yet. Submit one from Request Service.")
