"""Configuration and LLM factory."""

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def get_llm(temperature: float = 0.0, model: str = DEFAULT_MODEL) -> ChatGroq:
    """Return a Groq chat model. Reads GROQ_API_KEY from the environment."""
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
    return ChatGroq(model=model, temperature=temperature)
