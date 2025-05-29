# Abnormal Security Incident Comms Demo

**PRD Reference:** This prototype was built to meet the PRD for Abnormal Security’s Incident Communications workflow, covering guardrails, AI-native draft generation, LLM-as-judge evaluation, RBAC gating, human-in-the-loop feedback, and executive metrics. The PRD is added in the Respository as '_AbnormalAI_TakeHomeAssignment_PRD_AarathiNair.pdf_'

**Video Demo:** A short walkthrough video showcasing the end-to-end flow—from incident input, draft generation, tone scoring, approval gating, publishing, to feedback capture—is available at: [Demo Video Link](#) 


---

## 🚀 Features

1. **Incident Input Form & Guardrails** – Severity, Components, ETA fields with required validation  
2. **AI-Native Draft Generation** – GPT-4o produces Internal Summary + Customer Update  
3. **PII Scrubbing** – Regex redaction of IPs and internal hostnames  
4. **Real-Time Metrics** – Generation latency and draft word count displayed  
5. **LLM-as-Judge Tone Scoring** – GPT-3.5-turbo scores tone, targeting ≥ 95 / 100  
6. **Micro-RBAC & Publish Stub** – Only “Commander” role can publish to mock Statuspage  
7. **Human-in-the-Loop Feedback** – 👍 / 👎 reviewer feedback captured in session  
8. **Session Metrics Dashboard** – Draft count, tone-score trend chart, review count  

---

## 🛠 Tech Stack

- **Streamlit** – rapid UI prototyping  
- **OpenAI Python SDK (v1.x)** – GPT-4o for generation; GPT-3.5-turbo for evaluation  
- **python-dotenv** – loads `OPENAI_API_KEY` from `.env`  

---

## 📥 Getting Started

```bash
# 1. Clone the repo
git clone https://github.com/your-org/abnormal-incident-comms-demo.git
cd abnormal-incident-comms-demo

# 2. Install dependencies
pip install -r requirements.txt
Create a .env in the project root:
OPENAI_API_KEY=sk-...

# 3. Run the app
streamlit run app.py
# App will be available at http://localhost:8501
``` 

🎯 Usage
Choose your Role in the sidebar (Commander, Support, Legal)

1. Select a Communication Lead
2. Enter Severity, Impacted Components, ETA
3. Click Generate Draft → view Internal Summary & Customer Update
4. Inspect Latency, Word Count, and Tone Score
5. As Commander, click Publish to push to the mock Statuspage panel
6. Provide 👍 / 👎 feedback; review history shows all iterations
7. Watch the Session Metrics panel update in real time

🔮 Future Enhancements
- Live integrations (PagerDuty, Statuspage)
- Expanded RBAC with audit logging
- OpenAI Moderation endpoint for advanced content filtering
- Persistent storage (DynamoDB / Postgres) for drafts & feedback
- Real-time multi-reviewer collaboration
