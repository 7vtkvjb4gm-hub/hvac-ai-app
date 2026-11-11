"""Pure-Python logic (no Streamlit imports) so it is reusable and testable."""
import csv, os, re
from datetime import datetime
from pathlib import Path
import requests

LEADS_FILE = Path(os.getenv("LEADS_FILE", "leads.csv"))
LEAD_FIELDS = ["timestamp", "name", "phone", "email", "service", "source", "notes", "score"]

# ---------- Lead capture / CRM (Google Sheets or local CSV) ----------
def valid_email(e): return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e or ""))
def valid_phone(p): return len(re.sub(r"\D", "", p or "")) >= 10

def validate_lead(lead):
    errs = []
    if not (lead.get("name") or "").strip(): errs.append("Enter your name.")
    if not valid_phone(lead.get("phone")): errs.append("Enter a phone number with at least 10 digits.")
    if lead.get("email") and not valid_email(lead["email"]): errs.append("Check the email address format.")
    return errs

def save_lead(lead, sheet=None, path=None):
    path = Path(path or LEADS_FILE)
    row = {k: lead.get(k, "") for k in LEAD_FIELDS}
    row["timestamp"] = datetime.now().isoformat(timespec="seconds")
    if sheet is not None:
        sheet.append_row([row[k] for k in LEAD_FIELDS]); return "sheet"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEAD_FIELDS)
        if new: w.writeheader()
        w.writerow(row)
    return "csv"

def load_leads(sheet=None, path=None):
    path = Path(path or LEADS_FILE)
    if sheet is not None: return sheet.get_all_records()
    if not path.exists(): return []
    with path.open(encoding="utf-8") as f: return list(csv.DictReader(f))

# ---------- ROI calculator ----------
def roi(missed_calls_wk, avg_job, close_rate, recovery_rate, admin_hrs_wk, hourly, admin_cut, tool_cost_mo):
    wk = 4.33
    jobs = missed_calls_wk * wk * recovery_rate * close_rate
    revenue = jobs * avg_job
    labor = admin_hrs_wk * wk * hourly * admin_cut
    gain = revenue + labor
    net = gain - tool_cost_mo
    return {"jobs_recovered": jobs, "revenue": revenue, "labor_saved": labor, "gain": gain,
            "net": net, "roi_pct": (net / tool_cost_mo * 100) if tool_cost_mo > 0 else None}

# ---------- Business assessment ----------
QUESTIONS = [
    {"key": "calls", "text": "What happens to calls when your office is busy or closed?",
     "options": [("They go to voicemail and we call back later", 1), ("A service answers, but can't book jobs", 2), ("Every call is answered or booked automatically", 4)],
     "rec": "Add an AI/text-back system so no missed call becomes a lost job."},
    {"key": "followup", "text": "How do you follow up on quotes?",
     "options": [("We don't, unless the customer calls", 1), ("Manually, when we remember", 2), ("Automatic reminders over text and email", 4)],
     "rec": "Automate quote follow-up at 1, 3, and 7 days. Most quotes close on the second touch."},
    {"key": "maint", "text": "How do you sell maintenance plans?",
     "options": [("We don't have a plan", 1), ("We offer it at the end of a repair", 2), ("Seasonal campaigns plus automatic renewals", 4)],
     "rec": "Run spring A/C and fall furnace tune-up campaigns; recurring plans smooth out slow months."},
    {"key": "reviews", "text": "How do you ask for Google reviews?",
     "options": [("We don't", 1), ("Techs ask sometimes", 2), ("An automatic text goes out after every job", 4)],
     "rec": "Send a review link by text right after each job and use AI to draft replies."},
    {"key": "tracking", "text": "Where do you keep customer and lead info?",
     "options": [("Paper, texts, or memory", 1), ("Spreadsheets", 2), ("A CRM with lead sources tracked", 4)],
     "rec": "Start with a simple lead sheet (this app writes to Google Sheets) and track the source of every lead."},
    {"key": "marketing", "text": "How often do you publish marketing content?",
     "options": [("Rarely", 1), ("Monthly", 2), ("Weekly, planned by season", 4)],
     "rec": "Use the Content Studio to draft a month of seasonal posts and emails in one sitting."},
]

def score_assessment(answers):
    """answers: {key: points}. Returns (score 0-100, level, [recommendations])."""
    pts = sum(answers.get(q["key"], 0) for q in QUESTIONS)
    score = round(pts / (4 * len(QUESTIONS)) * 100)
    level = "Getting started" if score < 40 else "Building momentum" if score < 70 else "Well automated"
    recs = [q["rec"] for q in QUESTIONS if answers.get(q["key"], 0) <= 2]
    return score, level, recs

# ---------- Prompt builder + content ----------
TEMPLATES = {
    "Google review reply": "Write a reply to this {rating}-star review for {company}, an HVAC company. Review: \"{details}\". Tone: {tone}. Under 80 words. Thank them by name if given, mention one specific detail, no made-up facts.",
    "Seasonal email": "Write a {tone} marketing email for {company} promoting {service} for the {season} season. Extra details: {details}. Include a subject line, a 120-word body, and one clear call to action to phone or book online.",
    "Maintenance reminder SMS": "Write 3 variations of a {tone} text message (under 300 characters each) from {company} reminding customers it is time for {service} before {season}. Details: {details}. Include opt-out text.",
    "Social media post": "Write a {tone} Facebook post for {company} about {service} in {season}. Details: {details}. Add 3 relevant hashtags and a call to action.",
    "Service page blurb": "Write a {tone} 150-word website section for {company} about {service}. Details: {details}. Lead with the customer's problem, then the benefit, then a call to action.",
}
TONES = ["Friendly", "Professional", "Urgent", "Plain-spoken"]
SEASONS = ["Spring", "Summer", "Fall", "Winter"]
SERVICES = ["A/C tune-up", "Furnace tune-up", "Emergency repair", "New system install", "Duct cleaning", "Indoor air quality", "Maintenance plan"]

def build_prompt(task, company, service, season, tone, rating=5, details=""):
    return TEMPLATES[task].format(company=company or "our company", service=service, season=season,
                                  tone=tone.lower(), rating=rating, details=details or "none")

def offline_draft(task, company, service, season):
    return (f"[Offline template, add a free API key for AI drafts]\n\nHi from {company}! "
            f"{season} is the best time to schedule your {service}. Call us or book online today.")

def ask_llm(prompt, provider, key, model):
    system = "You write concise, friendly marketing copy for a local HVAC contractor. Use only facts given in the request. Never invent prices, licenses, certifications, insurance, years in business, or guarantees. Write plain text only: no markdown, no asterisks, no labels like Body."
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        r = requests.post(url, headers={"x-goog-api-key": key}, timeout=60, json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}]})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if provider == "groq":
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=60,
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    raise ValueError(f"Unknown provider: {provider}")

# ---------- Use case library ----------
USE_CASES = [
    {"name": "Missed-call text-back", "area": "Leads", "effort": "Low", "desc": "Auto-text every missed caller with a booking link."},
    {"name": "AI lead qualifier", "area": "Leads", "effort": "Medium", "desc": "Ask system age, issue, and urgency before dispatch."},
    {"name": "Quote follow-up", "area": "Sales", "effort": "Low", "desc": "Scheduled texts and emails after every estimate."},
    {"name": "Review requests and replies", "area": "Reputation", "effort": "Low", "desc": "Ask after each job; AI drafts replies to reviews."},
    {"name": "Seasonal campaigns", "area": "Marketing", "effort": "Low", "desc": "Spring A/C and fall furnace promotions drafted in minutes."},
    {"name": "Maintenance plan renewals", "area": "Retention", "effort": "Medium", "desc": "Renewal reminders before each plan expires."},
    {"name": "Tech job summaries", "area": "Operations", "effort": "Medium", "desc": "Turn tech voice notes into clean invoices and notes."},
    {"name": "Dispatch route planning", "area": "Operations", "effort": "High", "desc": "Group jobs by location and skill to cut drive time."},
]
