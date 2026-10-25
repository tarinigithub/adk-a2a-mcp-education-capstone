"""Tools available to worker agents. Replace the stubs with real implementations."""

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web for information about a query."""
    # TODO: plug in a real search API (e.g. Tavily, DuckDuckGo, SerpAPI).
    return f"[stub] No live search configured. Pretend results for: {query}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '2 * (3 + 4)'."""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "Error: only numbers and + - * / ( ) are allowed."
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as exc:
        return f"Error: {exc}"


@tool
def word_count(text: str) -> int:
    """Count the number of words in a piece of text."""
    return len(text.split())
