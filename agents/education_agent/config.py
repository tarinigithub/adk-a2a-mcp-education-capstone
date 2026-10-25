"""Shared settings: loads .env and builds the Gemini model used by every agent."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models import Gemini
from google.genai import types

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
INSIGHTS_A2A_URL = os.getenv("INSIGHTS_A2A_URL", "http://localhost:8001")


def gemini() -> Gemini:
    # The free tier allows only a few requests per minute; back off and retry on 429/503.
    return Gemini(
        model=MODEL_NAME,
        retry_options=types.HttpRetryOptions(
            attempts=6, initial_delay=5, max_delay=60, http_status_codes=[429, 503]
        ),
    )
