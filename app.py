# app.py

import os
import re
import time

import streamlit as st
import openai
from dotenv import load_dotenv

# ——— CONFIG ———
load_dotenv()  # load .env (ensure it’s next to app.py)
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("OPENAI_API_KEY not found in environment. Check your .env file.")
    st.stop()

# ——— SESSION STATE SETUP ———
if "reviews" not in st.session_state:
    st.session_state.reviews = []
if "scores" not in st.session_state:
    st.session_state.scores = []

st.set_page_config(page_title="Abnormal AI Demo", layout="wide")

st.title("🔐 Abnormal Security Incident Comms Demo")
st.write("Generate → Judge → Review → Publish")

# Sidebar role selector for RBAC demo
st.sidebar.header("Your Role")
user_role = st.sidebar.radio("Select role", ["Commander", "Support", "Legal"])

# Communication Lead selector (dynamic stub)
lead = st.selectbox(
    "Communication Lead",
    options=["On-call SRE", "Incident Manager", "Team Lead"],
    help="Select who’s notarizing this communication"
)

# ——— STEP 2: INPUT FORM & GUARDRAILS ———
st.header("1️⃣ Incident Details")
with st.form("incident_form", clear_on_submit=False):
    severity = st.selectbox(
        "Incident Severity",
        options=["", "P0 – Critical", "P1 – High", "P2 – Medium", "P3 – Low"],
    )
    components = st.text_input(
        "Impacted Components",
        placeholder="e.g., auth-service, db-cluster",
    )
    eta = st.text_input(
        "ETA for Resolution",
        placeholder="e.g., 15 min, 3 hr, 2025-05-28T15:00Z",
    )
    submitted = st.form_submit_button("Generate Draft")

if submitted:
    if not (severity and components and eta):
        st.warning("⚠️ Please fill in all fields before generating.")
        st.stop()

    # ——— STEP 3: DRAFT GENERATION + PII SCRUB + LATENCY ———
    start = time.time()
    prompt = f"""
You are Abnormal’s incident-comms assistant.
Generate INTERNAL SUMMARY as two sub-lists:
• **What Happened** (3–4 bullets)  
• **Next Steps** (2–3 bullets)

Then generate CUSTOMER UPDATE as two paragraphs.

Incident Severity: {severity}
Impacted Components: {components}
ETA for Resolution: {eta}

Include a placeholder “[Name/Role]” for Communication Lead.
Tone: professional, concise, reassuring.
"""
    resp = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    full_text = resp.choices[0].message.content

    # Robust parsing on headers
    if re.search(r"INTERNAL SUMMARY", full_text, flags=re.IGNORECASE):
        parts = re.split(r"CUSTOMER UPDATE", full_text, flags=re.IGNORECASE, maxsplit=1)
        internal = parts[0]
        customer = parts[1] if len(parts) > 1 else ""
        internal = re.sub(r"(?i)INTERNAL SUMMARY[:\-\n]*", "", internal).strip()
    else:
        try:
            internal, customer = full_text.split("2)", 1)
            internal = internal.replace("1)", "").strip()
            customer = customer.strip()
        except ValueError:
            internal = "[Could not parse internal summary]"
            customer = full_text

    # Replace placeholder with selected lead
    internal = internal.replace("[Name/Role]", lead)

    # PII scrub
    def scrub_pii(text: str) -> str:
        patterns = [
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            r"\b[a-zA-Z0-9\.-]+\.internal\b",
        ]
        for p in patterns:
            text = re.sub(p, "[REDACTED]", text)
        return text

    internal = scrub_pii(internal)
    customer = scrub_pii(customer)

    # Compute latency
    gen_time = time.time() - start

    # ——— DISPLAY RESULTS ———
    st.header("🔍 Internal Summary")
    st.divider()
    internal = re.sub(r"^\*+", "", internal, flags=re.MULTILINE).strip()
    st.markdown(internal)

    st.header("📢 Customer Update")
    st.divider()
    st.markdown(customer)

    # Metrics in two columns
    col1, col2 = st.columns(2)
    col1.metric("⏱ Gen Latency", f"{gen_time:.1f}s")
    col2.metric("💬 Draft Word Count", f"{len(customer.split())}")

    # ——— STEP 4: LLM-AS-JUDGE TONE SCORING ———
    judge_prompt = (
        "Rate 0–100 how well this CUSTOMER UPDATE matches the brand tone "
        "(professional, concise, reassuring). Return **only** a number."
        f"\n\n{customer}"
    )
    judge_resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": judge_prompt}],
        temperature=0,
    )
    score_match = re.search(r"\d+", judge_resp.choices[0].message.content)
    score = int(score_match.group()) if score_match else 0
    st.metric("🎯 Tone Score", f"{score}/100")
    st.session_state.scores.append(score)

    # ——— STEP 5: MICRO-RBAC & PUBLISH STUB ———
    st.header("🔐 Approval & Publish")
    st.write("Only the **Commander** can publish the customer update.")
    if user_role != "Commander":
        st.warning("You need the Commander role to publish this update.")
    publish_btn = st.button(
        "Publish Customer Update",
        disabled=(user_role != "Commander")
    )
    if publish_btn:
        st.success("✅ Published to Statuspage!")
        st.container().markdown(
            f"---\n\n**Live Statuspage Update:**\n\n{customer}"
        )

    # ——— STEP 6: REVIEW FEEDBACK CAPTURE ———
    st.header("👥 Reviewer Feedback")
    feedback = st.radio(
        label="How’s the customer update?",
        options=["", "👍 Looks good", "👎 Needs work"],
        index=0,
    )
    if feedback and (not st.session_state.reviews or st.session_state.reviews[-1] != feedback):
        st.session_state.reviews.append(feedback)
    if st.session_state.reviews:
        st.write("**Review History:**")
        for idx, fb in enumerate(st.session_state.reviews, start=1):
            st.write(f"{idx}. {fb}")

# ——— STEP 7: SESSION METRICS PANEL ———
with st.sidebar.expander("📊 Session Metrics", expanded=True):
    drafts = len(st.session_state.scores)
    st.write(f"**Drafts Generated:** {drafts}")
    if drafts > 0:
        st.write("**Tone Score Trend:**")
        st.line_chart(st.session_state.scores, height=150)
    reviews = len(st.session_state.reviews)
    st.write(f"**Reviews Given:** {reviews}")
