"""Serve the insights agent over A2A (Agent-to-Agent protocol) on port 8001.

Run from the project root:
    uvicorn education_agent.a2a_server:app --app-dir agents --port 8001

Agent card: http://localhost:8001/.well-known/agent-card.json
Registers itself with the Agent Registry (AGENT_REGISTRY_URL, default :8003) on startup.
"""

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .insights import insights_agent
from .registry import register_on_startup

app = to_a2a(insights_agent, port=8001, lifespan=register_on_startup(8001))
