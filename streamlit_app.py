"""Streamlit demo UI for the Education Insights & Resource Recommender.

Run:
    streamlit run streamlit_app.py

Starts the insights A2A server (port 8001) automatically if it isn't already running.
"""

import asyncio
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "agents"))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from education_agent.agent import root_agent  # noqa: E402
from education_agent.config import INSIGHTS_A2A_URL, MODEL_NAME  # noqa: E402

APP_NAME = "education_agent"
USER_ID = "demo_user"

SAMPLE_QUERIES = {
    "🏛️ Public officials": [
        "Identify the five schools in Fresno County with the highest rate of low-income "
        "students and the lowest per-pupil technology spending, to prioritize grant funding.",
        "Which California counties have the highest average share of low-income students? "
        "Show the top 10 with their average per-pupil spending.",
        "Show a bar chart of the 10 counties with the most students per counselor.",
    ],
    "🍎 Educators": [
        "Find high schools with high graduation rates despite below-average funding, "
        "to discover program models that can be replicated.",
        "Do smaller class sizes go with higher graduation rates? What interventions would you recommend?",
        "Do schools with more AP courses have higher graduation rates? Back it up with data.",
    ],
    "👪 Parents": [
        "Find high schools with strong STEM programs and low class sizes.",
        "Which high schools in San Diego County offer both AP science and calculus with "
        "the lowest student-teacher ratio?",
        "Show a bar chart of the 10 Los Angeles County high schools with the most AP courses.",
    ],
}

AGENT_LABELS = {
    "education_root_agent": "🧭 Root agent",
    "data_agent": "🗄️ Data agent",
    "insights_agent": "💡 Insights agent (A2A)",
}


# ---------- one-time setup (cached across reruns) ----------

@st.cache_resource
def event_loop() -> asyncio.AbstractEventLoop:
    """A single background event loop, so the A2A HTTP client survives Streamlit reruns."""
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    return loop


def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, event_loop()).result()


def a2a_is_up() -> bool:
    try:
        return requests.get(f"{INSIGHTS_A2A_URL}/.well-known/agent-card.json", timeout=2).ok
    except requests.RequestException:
        return False


@st.cache_resource
def start_a2a_server() -> bool:
    if a2a_is_up():
        return True
    subprocess.Popen(
        [sys.executable, "-W", "ignore", "-m", "uvicorn", "education_agent.a2a_server:app",
         "--app-dir", "agents", "--port", "8001"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        if a2a_is_up():
            return True
        time.sleep(1)
    return False


@st.cache_resource
def runner() -> InMemoryRunner:
    return InMemoryRunner(agent=root_agent, app_name=APP_NAME)


def new_session() -> str:
    session = run_async(runner().session_service.create_session(app_name=APP_NAME, user_id=USER_ID))
    return session.id


# ---------- running a turn ----------

async def ask(session_id: str, question: str) -> dict:
    """Send one user message and collect steps, answer text and chart images."""
    steps, answers, images = [], [], []
    message = types.Content(role="user", parts=[types.Part(text=question)])
    async for event in runner().run_async(user_id=USER_ID, session_id=session_id, new_message=message):
        agent = AGENT_LABELS.get(event.author, event.author)
        for part in (event.content.parts if event.content else None) or []:
            if part.function_call:
                call = part.function_call
                args = dict(call.args or {})
                if call.name == "transfer_to_agent":
                    target = AGENT_LABELS.get(args.get("agent_name"), args.get("agent_name"))
                    steps.append(f"{agent} → hands off to **{target}**")
                else:
                    steps.append((f"{agent} → calls `{call.name}`", args))
            elif part.text and not part.thought and event.is_final_response():
                if part.text.strip() and part.text not in answers:  # A2A can repeat the final text
                    answers.append(part.text)
        for filename, version in (event.actions.artifact_delta or {}).items():
            artifact = await runner().artifact_service.load_artifact(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
                filename=filename, version=version,
            )
            if artifact and artifact.inline_data:
                images.append(artifact.inline_data.data)
    return {"steps": steps, "answer": "\n\n".join(answers) or "_(no answer returned)_", "images": images}


def render_steps(steps: list) -> None:
    with st.expander(f"🔍 Agent trace ({len(steps)} steps)", expanded=False):
        for step in steps:
            if isinstance(step, tuple):
                label, args = step
                st.markdown(label)
                if "sql" in args:
                    st.code(args["sql"], language="sql")
                elif args:
                    st.json(args, expanded=False)
            else:
                st.markdown(step)


def render_reply(reply: dict) -> None:
    render_steps(reply["steps"])
    st.markdown(reply["answer"])
    for image in reply["images"]:
        st.image(image)


# ---------- page ----------

st.set_page_config(page_title="Education Insights", page_icon="🎓", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = new_session()
    st.session_state.history = []

with st.sidebar:
    st.header("🎓 Try a question")
    for group, queries in SAMPLE_QUERIES.items():
        st.subheader(group)
        for i, q in enumerate(queries):
            if st.button(q, key=f"{group}-{i}", use_container_width=True):
                st.session_state.pending = q
    st.divider()
    if st.button("🔄 New conversation", use_container_width=True):
        st.session_state.session_id = new_session()
        st.session_state.history = []
        st.rerun()
    a2a_ok = start_a2a_server()
    st.caption(
        f"Model: `{MODEL_NAME}`  \n"
        f"Insights agent (A2A): {'🟢 connected' if a2a_ok else '🔴 not reachable'} at `{INSIGHTS_A2A_URL}`  \n"
        "Data: California public schools, 2017 (technology data 2020)"
    )

st.title("Education Insights & Resource Recommender")
st.markdown(
    "Ask about **California public schools**: low-income rates, funding, class sizes, STEM "
    "offerings and graduation rates. Built with **Google ADK + Gemini**. A root agent routes to a "
    "**data agent** (SQL + charts) and a remote **insights agent** over **A2A**."
)

for turn in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        render_reply(turn["reply"])

question = st.chat_input("Ask about schools, funding, STEM, graduation rates...")
question = question or st.session_state.pop("pending", None)

if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Agents are working... (free-tier rate limits can add ~30s)"):
            try:
                reply = run_async(ask(st.session_state.session_id, question))
            except Exception as exc:
                reply = {"steps": [], "answer": f"⚠️ Error: `{exc}`", "images": []}
        render_reply(reply)
    st.session_state.history.append({"question": question, "reply": reply})
