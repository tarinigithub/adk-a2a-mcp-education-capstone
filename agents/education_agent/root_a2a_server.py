"""Serve the capstone root agent over A2A on port 8002, so other agents (e.g. the voice
agent in ../voice-agent-adk-a2a) can delegate school questions to it.

Needs the insights A2A server (port 8001) running too, since the root agent calls it.

Run from the project root:
    uvicorn education_agent.root_a2a_server:app --app-dir agents --port 8002

Agent card: http://localhost:8002/.well-known/agent-card.json
Registers itself with the Agent Registry (AGENT_REGISTRY_URL, default :8003) on startup.
"""

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import root_agent
from .registry import register_on_startup

app = to_a2a(root_agent, port=8002, lifespan=register_on_startup(8002))
