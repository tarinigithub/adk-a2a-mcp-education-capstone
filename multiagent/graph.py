"""Assemble the supervisor + workers into a LangGraph StateGraph."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from multiagent.agents import WORKERS, make_worker_node
from multiagent.state import AgentState
from multiagent.supervisor import supervisor_node


def build_graph(with_memory: bool = True):
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", supervisor_node)
    for spec in WORKERS:
        builder.add_node(spec.name, make_worker_node(spec))
        # Every worker reports back to the supervisor when done.
        builder.add_edge(spec.name, "supervisor")

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["next"],
        {**{w.name: w.name for w in WORKERS}, "FINISH": END},
    )

    # InMemorySaver keeps per-thread conversation state; swap for SQLite/Postgres to persist.
    return builder.compile(checkpointer=InMemorySaver() if with_memory else None)
