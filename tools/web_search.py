from __future__ import annotations

from tavily import TavilyClient

from tools.config import get_secret


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web with Tavily and return simplified results.

    NOTE: the previous version never returned anything (no `return` statement),
    so the agent always received None and silently ignored all web research.
    """
    api_key = get_secret("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("TAVILY_API_KEY is not configured.")

    client = TavilyClient(api_key=api_key)

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
    )

    results: list[dict] = []

    for item in response.get("results", []):
        results.append(
            {
                "title": item.get("title", "") or "",
                "url": item.get("url", "") or "",
                "content": item.get("content", "") or "",
            }
        )

    return results
