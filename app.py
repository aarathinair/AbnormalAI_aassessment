import os
import re
import time
import json
import uuid
import sqlite3
import datetime as dt
import difflib
import concurrent.futures

import streamlit as st
import openai


# ——— STEP 1: INIT LOCAL SQLITE STORE ———
DB_PATH = "eval.db"
conn = sqlite3.connect(DB_PATH)

# Drop old table if it exists
conn.execute("DROP TABLE IF EXISTS eval_log")

# Create new table with 12 columns
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS eval_log (
      id TEXT PRIMARY KEY,
      ts TEXT,
      prompt TEXT,
      response TEXT,
      accuracy INTEGER,
      tone INTEGER,
      latency REAL,
      shadow_accuracy INTEGER,
      shadow_latency REAL,
      lev_ratio REAL,
      rating INTEGER,
      comment TEXT
    )
    """
)
conn.commit()
conn.close()

# ——— CONFIG ———
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
if not openai.api_key:
    st.error("OPENAI_API_KEY not found in Streamlit secrets.")
    st.stop()

# ——— SESSION STATE ———
if "reviews" not in st.session_state:
    st.session_state.reviews = []
if "scores" not in st.session_state:
    st.session_state.scores = []

st.set_page_config(page_title="Abnormal AI Demo", layout="wide")
st.title("🔐 Abnormal Security Incident Comms Demo")
st.write("Generate → Evaluate → Compare → Review → Persist")

# Sidebar
st.sidebar.header("Your Role")
user_role = st.sidebar.radio("Select role", ["Commander", "Support", "Legal"])

# ——— INPUT FORM ———
st.header("1️⃣ Incident Details")
with st.form("incident_form"):
    severity = st.selectbox(
        "Incident Severity",
        ["", "P0 – Critical", "P1 – High", "P2 – Medium", "P3 – Low"],
    )
    components = st.text_input("Impacted Components", placeholder="e.g., auth-service")
    eta = st.text_input("ETA for Resolution", placeholder="e.g., 15 min")
    submit = st.form_submit_button("Generate Draft")

if submit:
    if not (severity and components and eta):
        st.warning("⚠️ Please fill in all fields.")
        st.stop()

    prompt = f"""You are Abnormal’s incident-comms assistant.
Generate INTERNAL SUMMARY and CUSTOMER UPDATE.

Incident Severity: {severity}
Impacted Components: {components}
ETA for Resolution: {eta}

Tone: professional, concise, reassuring."""

    # ——— Production call ———
    prod_start = time.time()
    resp_prod = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    prod_latency = time.time() - prod_start
    prod_text = resp_prod.choices[0].message.content

    # ——— Shadow call ———
    def call_shadow():
        t0 = time.time()
        r = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return r.choices[0].message.content, time.time() - t0

    with concurrent.futures.ThreadPoolExecutor() as ex:
        shadow_text, shadow_latency = ex.submit(call_shadow).result()

    # ——— Shadow accuracy scoring ———
    jr_shadow = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": f'Return JSON {{"accuracy":0-100}} for:\n{shadow_text}',
            }
        ],
        temperature=0,
    )
    try:
        shadow_accuracy = int(json.loads(jr_shadow.choices[0].message.content)["accuracy"])
    except Exception:
        shadow_accuracy = 0

    # ——— Parse production text ———
    if re.search(r"CUSTOMER UPDATE", prod_text, re.IGNORECASE):
        pre, post = re.split(
            r"CUSTOMER UPDATE", prod_text, flags=re.IGNORECASE, maxsplit=1
        )
        internal = re.sub(r"(?i)INTERNAL SUMMARY[:\-\n]*", "", pre).strip()
        customer = post.strip()
    else:
        try:
            internal, customer = prod_text.split("2)", 1)
            internal = internal.replace("1)", "").strip()
            customer = customer.strip()
        except ValueError:
            internal, customer = "[Parse failed]", prod_text

    # ——— PII scrub ———
    def scrub(text: str) -> str:
        for ptn in [
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            r"\b[A-Za-z0-9.-]+\.internal\b",
        ]:
            text = re.sub(ptn, "[REDACTED]", text)
        return text

    internal = scrub(internal)
    customer = scrub(customer)

        # ——— REMOVE LLM-EMITTED “**” MARKERS ———
    def remove_sep_markers(text: str) -> str:
        lines = text.splitlines()
        cleaned = [ln for ln in lines if ln.strip() != "**"]
        return "\n".join(cleaned)

    internal = remove_sep_markers(internal)
    customer = remove_sep_markers(customer)

    # ——— Display draft ———
    st.header("🔍 Internal Summary")
    st.markdown(internal)

    st.header("📢 Customer Update")
    st.divider()
    st.markdown(customer)

    # ——— Base metrics ———
    col1, col2 = st.columns(2)
    col1.metric("⏱ Prod Latency", f"{prod_latency:.1f}s")
    col2.metric("💬 Word Count", f"{len(customer.split())}")

    # ——— Automated accuracy & tone ———
    judge_payload = (
        'Return JSON with "accuracy" (0-100) and "tone" (0-100) for the text below.\n\n'
        + customer
    )
    jr = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": judge_payload}],
        temperature=0,
    )
    try:
        js = json.loads(jr.choices[0].message.content)
        accuracy = int(js.get("accuracy", 0))
        tone = int(js.get("tone", 0))
    except Exception:
        accuracy, tone = 0, 0

    col3, col4 = st.columns(2)
    col3.metric("🔍 Accuracy", f"{accuracy}/100")
    col4.metric("🎨 Tone", f"{tone}/100")
    st.session_state.scores.append(tone)

    # ——— Shadow comparison display ———
    st.subheader("🕵️ Shadow-Mode Comparison")
    st.caption("🔍 Prod = GPT-4o • 🕵️ Shadow = GPT-3.5-turbo (cheaper model)")
    s1, s2 = st.columns(2)
    s1.metric("Prod Acc", f"{accuracy}/100", delta=accuracy - shadow_accuracy)
    s1.metric("Prod Lat", f"{prod_latency:.1f}s")
    s2.metric(
        "Shadow Acc", f"{shadow_accuracy}/100", delta=shadow_accuracy - accuracy
    )
    s2.metric("Shadow Lat", f"{shadow_latency:.1f}s")
    if shadow_accuracy >= accuracy and shadow_latency < prod_latency:
        st.success("🚀 Shadow model wins on accuracy & speed!")

    # ——— STEP 4: HUMAN FEEDBACK & EDIT-DISTANCE ———
    st.header("👥 Reviewer Feedback")

    with st.form("feedback_form", clear_on_submit=False):
        # 1) Rating via radio (stars)
        # Numeric rating 1–5
        rating = st.number_input(
        "Score (out of 5)",
        min_value=1,
        max_value=5,
        value=5,
        step=1,
        format="%d",
        help="Enter a score from 1 (poor) to 5 (excellent)."
        )


        # 2) Free-form comment
        comment = st.text_area("Any comments or suggestions?", height=100)

        # 3) Submit button for this form
        submit_fb = st.form_submit_button("Submit Feedback")

    # Only record feedback when the user actually clicks the form’s submit button
    if submit_fb:
        if not comment.strip():
            st.warning("Please add a comment before submitting feedback.")
        else:
            lev_ratio = 1 - difflib.SequenceMatcher(None, customer, comment).ratio()
            st.session_state.reviews.append({
                "rating": rating,
                "comment": comment,
                "lev": lev_ratio
            })
            # (Optionally) clear the form fields
            # st.experimental_set_query_params()  # or just let the form keep its values

    # ——— display feedback history (unchanged) ———
    if st.session_state.reviews:
        st.write("**Feedback History:**")
        for i, fb in enumerate(st.session_state.reviews, 1):
            stars = "⭐" * fb["rating"] + f" ({fb['rating']}/5)"
            st.write(f"{i}. {stars} — {fb['comment']}")
        avg_rating = sum(fb["rating"] for fb in st.session_state.reviews) / len(st.session_state.reviews)
        avg_lev    = sum(fb["lev"]     for fb in st.session_state.reviews) / len(st.session_state.reviews)
        cr1, cr2 = st.columns(2)
        cr1.metric("⭐ Avg Rating",      f"{avg_rating:.2f}/5")
        cr2.metric("✂️ Avg Edit-Distance", f"{avg_lev:.2%}")

    # ——— Persist run ———
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO eval_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            str(uuid.uuid4()),
            dt.datetime.utcnow().isoformat(),
            prompt,
            customer,
            accuracy,
            tone,
            prod_latency,
            shadow_accuracy,
            shadow_latency,
            lev_ratio if 'lev_ratio' in locals() else None,
            rating,
            comment,
        ),
    )
    conn.commit()
    conn.close()

# Sidebar session metrics
with st.sidebar.expander("📊 Session Metrics", expanded=True):
    st.write(f"Drafts Generated: {len(st.session_state.scores)}")
    if st.session_state.scores:
        st.line_chart(st.session_state.scores, height=120)
    st.write(f"Reviews Given: {len(st.session_state.reviews)}")
