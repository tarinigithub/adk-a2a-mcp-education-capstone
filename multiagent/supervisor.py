"""Supervisor: decides which worker acts next, or when to finish."""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from multiagent.agents import WORKERS
from multiagent.config import get_llm
from multiagent.state import AgentState

MAX_ITERATIONS = 8
WORKER_NAMES = [w.name for w in WORKERS]
# Literal built dynamically so the LLM can only pick a valid route.
Route = Literal[tuple(WORKER_NAMES + ["FINISH"])]  # type: ignore[valid-type]


class RouteDecision(BaseModel):
    next: Route = Field(description="The worker to act next, or FINISH when the task is done.")
    reason: str = Field(description="One short sentence explaining the choice.")


def _system_prompt() -> str:
    roster = "\n".join(f"- {w.name}: {w.description}" for w in WORKERS)
    return (
        "You are a supervisor managing a team of agents:\n"
        f"{roster}\n\n"
        "Given the conversation so far, choose who should act next. "
        "A typical flow is researcher -> writer -> reviewer. If the reviewer requests fixes, "
        "send it back to the writer. Choose FINISH once the reviewer has APPROVED the answer."
    )


def supervisor_node(state: AgentState) -> dict:
    iterations = state.get("iterations", 0) + 1
    if iterations > MAX_ITERATIONS:
        return {"next": "FINISH", "iterations": iterations}

    # Groq drops the `name` field on messages, so state who has spoken explicitly.
    history = [m.name for m in state["messages"] if m.name in WORKER_NAMES]
    progress = (
        f"Workers that have already responded, in order: {' -> '.join(history) or 'none'}. "
        "Do not re-run a worker unless its output was missing or rejected."
    )

    router = get_llm().with_structured_output(RouteDecision)
    decision: RouteDecision = router.invoke(
        [SystemMessage(content=_system_prompt()), *state["messages"], HumanMessage(content=progress)]
    )
    print(f"  [supervisor] -> {decision.next}: {decision.reason}")
    return {"next": decision.next, "iterations": iterations}
