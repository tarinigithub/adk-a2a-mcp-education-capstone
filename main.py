"""Interactive CLI for the multi-agent system.

Usage:
    python main.py                      # interactive chat
    python main.py "your question"      # single run
"""

import sys
import uuid

from langchain_core.messages import HumanMessage

from multiagent import build_graph


def run(graph, question: str, thread_id: str) -> None:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    inputs = {"messages": [HumanMessage(content=question)], "iterations": 0}

    for update in graph.stream(inputs, config, stream_mode="updates"):
        for node, payload in update.items():
            if node == "supervisor" or not payload:
                continue
            msg = payload["messages"][-1]
            print(f"\n--- {node} ---\n{msg.content}")


def main() -> None:
    graph = build_graph()
    thread_id = str(uuid.uuid4())

    if len(sys.argv) > 1:
        run(graph, " ".join(sys.argv[1:]), thread_id)
        return

    print("Multi-agent system (Groq + LangGraph). Type 'exit' to quit.")
    while True:
        question = input("\nYou: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            run(graph, question, thread_id)


if __name__ == "__main__":
    main()
