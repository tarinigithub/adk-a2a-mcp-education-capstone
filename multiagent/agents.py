"""Worker agents. Each one is a tool-calling agent with its own prompt and tools.

To add a new agent: define it in WORKERS below. The supervisor and graph pick it up
automatically.
"""

from dataclasses import dataclass, field

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from multiagent.config import get_llm
from multiagent.state import AgentState
from multiagent.tools import calculator, web_search, word_count


@dataclass
class WorkerSpec:
    name: str
    description: str  # shown to the supervisor so it knows when to route here
    system_prompt: str
    tools: list[BaseTool] = field(default_factory=list)


WORKERS: list[WorkerSpec] = [
    WorkerSpec(
        name="researcher",
        description="Gathers facts and does calculations. Use first for any question needing information.",
        system_prompt=(
            "You are a research specialist. Use your tools to gather facts and compute "
            "numbers. Return a concise bullet list of findings. Do not write the final answer."
        ),
        tools=[web_search, calculator],
    ),
    WorkerSpec(
        name="writer",
        description="Turns research findings into a clear, well-structured answer for the user.",
        system_prompt=(
            "You are a writer. Using the research already in the conversation, write a clear, "
            "well-organized answer to the user's original request."
        ),
        tools=[word_count],
    ),
    WorkerSpec(
        name="reviewer",
        description="Checks the writer's draft for accuracy and completeness. Use after the writer.",
        system_prompt=(
            "You are a critical reviewer. Check the latest draft against the user's request and "
            "the research. Reply 'APPROVED' if it is good, otherwise list specific fixes."
        ),
    ),
]


def make_worker_node(spec: WorkerSpec):
    """Wrap a create_agent agent as a graph node that appends one named message."""
    agent = create_agent(model=get_llm(), tools=spec.tools, system_prompt=spec.system_prompt)

    def node(state: AgentState) -> dict:
        result = agent.invoke({"messages": state["messages"]})
        final = result["messages"][-1]
        # Return only the worker's final reply, tagged with its name, so the shared
        # history stays readable for the supervisor and the other workers.
        return {"messages": [AIMessage(content=final.content, name=spec.name)]}

    return node
