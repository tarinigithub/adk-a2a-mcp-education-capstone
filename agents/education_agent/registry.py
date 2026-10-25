"""Self-registration with the Agent Registry (see ../voice-agent-adk-a2a/registry).

Pass `register_on_startup(port)` as the `lifespan` of `to_a2a`. ADK runs it before the
server accepts requests, so registration happens in a background task once this server's
own Agent Card is reachable. If no registry is running, the agent still works; it just
isn't discoverable.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import httpx

REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:8003")


async def _register(card_url: str, attempts: int = 30) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        for _ in range(attempts):
            try:
                (await client.get(card_url)).raise_for_status()  # our server is serving
                resp = await client.post(f"{REGISTRY_URL}/agents", json={"card_url": card_url})
                resp.raise_for_status()
                print(f"Registered with agent registry at {REGISTRY_URL}: {resp.json()['name']}")
                return
            except httpx.HTTPError:
                await asyncio.sleep(1)
    print(f"Agent registry not reachable at {REGISTRY_URL}; continuing unregistered.")


def register_on_startup(port: int, host: str = "localhost"):
    card_url = f"http://{host}:{port}/.well-known/agent-card.json"

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(_register(card_url))
        yield
        task.cancel()

    return lifespan
