# app.py - FinGenie final
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from groq import Groq
from utils.categorize import categorize
from io import StringIO
import time
import json

# ============== Page config & theme CSS =================
st.set_page_config(page_title="FinGenie - AI Finance Coach", page_icon="💰", layout="wide")

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}

/* -------- Background -------- */
.stApp {
    background: linear-gradient(135deg, #0d0f14 0%, #12141b 100%);
    color: #e8ecf3;
    padding: 0px;
}

/* -------- Titles -------- */
h1, h2, h3, h4 {
    font-weight: 600;
    color: #e9eef7 !important;
}

/* -------- Cards / Containers -------- */
.block-container {
    padding-top: 1rem;
}

div[data-testid="stMetricValue"] {
    color: #fff;
}

.css-1dp5vir, .css-1wivap2 {
    background: rgba(255,255,255,0.06) !important;
    backdrop-filter: blur(12px) !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    box-shadow: 0px 4px 20px rgba(0,0,0,0.35) !important;
}

/* -------- Chat bubbles -------- */
[data-testid="stChatMessage"][data-owner="user"] .markdown-text {
    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    color: white;
    padding: 12px 16px;
    border-radius: 16px;
    margin-top: 6px;
    margin-bottom: 6px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.25);
    max-width: 80%;
    margin-left: auto;
}

[data-testid="stChatMessage"][data-owner="assistant"] .markdown-text {
    background: rgba(255,255,255,0.07);
    padding: 12px 16px;
    border-radius: 16px;
    margin-top: 6px;
    margin-bottom: 6px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.20);
    max-width: 80%;
}

/* -------- Chat input -------- */
textarea, .stChatInputContainer {
    border-radius: 12px !important;
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: white !important;
    padding: 6px 10px !important;
}

.stChatInputContainer > div {
    background-color: transparent !important;
}

/* -------- Sidebar -------- */
section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.05) !important;
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255,255,255,0.08);
}
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3 {
    color: #e6edf5 !important;
}

/* -------- Buttons -------- */
button[kind="primary"], .stButton>button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: white;
    border-radius: 10px;
    padding: 10px 22px;
    border: none;
    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    transition: transform 0.1s ease-in-out;
}

button:hover {
    transform: scale(1.02);
}

/* -------- Plotly Graph -------- */
.plot-container {
    background: rgba(255,255,255,0.04) !important;
    backdrop-filter: blur(10px);
    border-radius: 16px;
    padding: 10px;
    margin-top: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}

/* -------- Input fields / File uploader -------- */
.css-1cpxqw2, .stFileUploader {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
}

.css-1cpxqw2:hover {
    background: rgba(255,255,255,0.10) !important;
}

</style>
""", unsafe_allow_html=True)


st.title("💰 FinGenie — AI-Powered Personal Finance Coach")
st.caption("Upload CSV bank statements, explore expenses, and chat with your financial coach.")

# ============== Groq client setup (optional) =================
api_key = st.secrets.get("GROQ_API_KEY")
if api_key:
    client = Groq(api_key=api_key)
else:
    client = None
    st.sidebar.warning("GROQ_API_KEY missing. Chat will show fallback messages unless configured.")

# ============== Sidebar actions =================
st.sidebar.header("Quick actions")
if st.sidebar.button("Show monthly trends"):
    st.session_state["_show_trends"] = True
else:
    # not pressing will remain as-is
    pass

if st.sidebar.button("Show savings ideas"):
    st.session_state["_savings_ideas"] = True

if st.sidebar.button("Clear chat history"):
    st.session_state["messages"] = []

# optional: download chat history
def chat_history_text():
    rows = []
    for m in st.session_state.get("messages", []):
        role = m.get("role", "")
        content = m.get("content", "")
        rows.append(f"{role.upper()}: {content}")
    return "\n\n".join(rows)

# ============== session state init =================
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# ============== File upload panel =================
col_l, col_r = st.columns([3, 1])
with col_l:
    uploaded_file = st.file_uploader("Upload your bank statement (CSV). Required cols: Date, Description, Amount", type=["csv"])
with col_r:
    st.download_button("Download sample CSV", data=pd.DataFrame({
        "Date": ["2025-11-01", "2025-11-03", "2025-11-05"],
        "Description": ["Zomato Order", "Amazon Purchase", "Petrol Pump"],
        "Amount": [-500, -1200, -800]
    }).to_csv(index=False), file_name="sample_bank_statement.csv", mime="text/csv")

# ============== Data processing =================
total_spent = 0.0
income = 0.0
balance = 0.0
category_summary = pd.Series(dtype=float)
monthly_summary = None

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        st.stop()

    # basic validation
    required_cols = {"Description", "Amount"}
    if not required_cols.issubset(df.columns):
        st.error(f"CSV must contain columns: {required_cols}")
    else:
        # convert Amount
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df.dropna(subset=["Amount"], inplace=True)
        # optional parse Date if present
        if "Date" in df.columns:
            try:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            except Exception:
                pass

        df["Category"] = df["Description"].apply(categorize)
        expense_df = df[df["Amount"] < 0].copy()
        income_df = df[df["Amount"] > 0].copy()

        if not expense_df.empty:
            category_summary = expense_df.groupby("Category")["Amount"].sum().abs().sort_values(ascending=False)
        else:
            category_summary = pd.Series(dtype=float)

        total_spent = float(expense_df["Amount"].sum() * -1) if not expense_df.empty else 0.0
        income = float(income_df["Amount"].sum()) if not income_df.empty else 0.0
        balance = income - total_spent

        # monthly summary if Date exists
        if "Date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["Date"]):
            monthly_summary = expense_df.copy()
            monthly_summary["month"] = monthly_summary["Date"].dt.to_period("M").astype(str)
            monthly_summary = monthly_summary.groupby("month")["Amount"].sum().abs().sort_index()

# ============== Dashboard: chart + metrics =================
st.markdown("### Overview")

c1, c2, c3 = st.columns(3)
c1.metric("💵 Total Spent", f"₹{total_spent:,.2f}")
c2.metric("💰 Total Income", f"₹{income:,.2f}")
c3.metric("🏦 Net Balance", f"₹{balance:,.2f}")

st.markdown("### Expense Breakdown")
if not category_summary.empty:
    ch_df = category_summary.reset_index()
    ch_df.columns = ["Category", "Amount"]
    fig = px.bar(ch_df, x="Category", y="Amount", color="Category", text="Amount", height=420)
    fig.update_traces(texttemplate="₹%{text:.0f}", textposition="outside")
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No expense entries detected (negative Amounts).")

# If sidebar quick action requested: monthly trends
if st.session_state.get("_show_trends", False):
    st.session_state["_show_trends"] = False
    if monthly_summary is not None and not monthly_summary.empty:
        ms_df = monthly_summary.reset_index()
        ms_df.columns = ["Month", "Amount"]
        fig2 = px.line(ms_df, x="Month", y="Amount", markers=True, title="Monthly Expense Trend")
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Monthly trend requires a 'Date' column in your CSV with parseable dates.")

# If sidebar quick action requested: savings ideas (generate quick textual ideas based on top categories)
if st.session_state.get("_savings_ideas", False):
    st.session_state["_savings_ideas"] = False
    top = category_summary.head(3).to_dict() if not category_summary.empty else {}
    if top:
        st.markdown("### Quick savings ideas (automatically generated):")
        for cat, amt in top.items():
            st.write(f"- **{cat}**: Spent ₹{amt:.0f}. Suggestion: review subscriptions / set monthly cap / use offers to reduce by 10-20% (save ~₹{amt*0.1:.0f}).")
    else:
        st.info("No expense data to suggest savings.")

# ============== Chat area (native Streamlit chat) =================
st.markdown("---")
st.subheader("🤖 FinGenie — Chat with your financial coach")

# show previous messages as native chat bubbles
for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.write(m["content"])

# chat input (native, guaranteed to stay under messages)
user_input = st.chat_input("Ask FinGenie for advice (e.g., 'How to reduce dining expenses?')")

def ask_fingenie_model(prompt: str) -> str:
    """Call Groq model (if configured) to get assistant response."""
    if client is None:
        # fallback canned response
        return "⚠️ Groq API key not set. To enable AI responses, add GROQ_API_KEY in .streamlit/secrets.toml."
    # prepare compact financial summary
    summary_text = f"Total Spent: ₹{total_spent:,.2f}\nTotal Income: ₹{income:,.2f}\nNet Balance: ₹{balance:,.2f}\nTop Categories: {category_summary.head(5).to_dict() if not category_summary.empty else {}}"
    user_content = f"My financial summary:\n{summary_text}\n\nQuestion: {prompt}"

    # show typing indicator (native)
    placeholder = st.chat_message("assistant")
    with placeholder:
        st.write("FinGenie is thinking... 💭")

    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are FinGenie, an empathetic practical financial coach; give concise actionable advice with steps and small examples."},
                {"role": "user", "content": user_content}
            ],
            max_tokens=400,
            temperature=0.7
        )
        text = resp.choices[0].message.content
    except Exception as e:
        text = f"⚠️ Error generating response: {e}"

    # remove placeholder message and return response (can't truly remove native chat_message; we instead write the actual response below)
    # NOTE: We can't delete previous chat_message; placeholder remains but that's fine — we now append the actual content.
    return text

# handle submission
if user_input:
    # append user bubble
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # call model (shows typing placeholder)
    assistant_text = ask_fingenie_model(user_input)

    # append assistant bubble
    st.session_state["messages"].append({"role": "assistant", "content": assistant_text})
    with st.chat_message("assistant"):
        st.write(assistant_text)

# ============== Chat download =================
if st.button("Download chat history"):
    txt = chat_history_text()
    st.download_button("Download conversation", data=txt, file_name="fingenie_chat.txt", mime="text/plain")
