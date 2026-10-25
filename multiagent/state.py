"""Shared graph state passed between the supervisor and worker agents."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Full conversation; add_messages appends instead of overwriting.
    messages: Annotated[list[AnyMessage], add_messages]
    # Name of the worker the supervisor picked last (or "FINISH").
    next: str
    # Safety valve against infinite supervisor loops.
    iterations: int
