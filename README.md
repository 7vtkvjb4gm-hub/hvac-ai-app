# HVAC Growth Assistant (100% free stack)

Assessment, ROI calculator, AI Content Studio with a Prompt Builder, use-case library, lead capture, and an admin lead list.

## Free replacements for the paid parts
| Course item | Free option used here |
|---|---|
| OpenAI API | Google Gemini free tier or Groq free tier (key from aistudio.google.com/apikey or console.groq.com) |
| Google Sheets CRM | Free Google Sheet via a service account; falls back to local `leads.csv` |
| Hosting | Streamlit Community Cloud |
| Version control | GitHub free |
| Editor | VS Code |

No key? The app still runs and uses offline templates. Free tiers have rate limits and may use your prompts for training, so don't paste customer personal data.

## Run locally
1. Install Python 3.11+ from python.org, and VS Code.
2. In a terminal: `cd hvac-ai-app && python -m venv .venv`
3. Activate: Windows `.venv\Scripts\activate`, Mac/Linux `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add a key.
6. `pytest` to check the logic, then `streamlit run app.py`

## Google Sheets CRM (optional, free)
Google Cloud Console > create project > enable Sheets and Drive APIs > create a service account > download its JSON key. Create a sheet named `HVAC Leads`, put these headers in row 1: `timestamp, name, phone, email, service, source, notes, score`, and share it with the service account's email as Editor. Paste the JSON fields under `[gcp_service_account]` in secrets.

## Deploy free
1. Create a GitHub repo and push this folder (`git init`, `git add .`, `git commit`, `git push`). Secrets are git-ignored.
2. Go to share.streamlit.io, sign in with GitHub, pick the repo, main file `app.py`.
3. App settings > Secrets: paste your secrets. Set `ADMIN_PASSWORD` to protect the Leads page.
