import streamlit as st
from tavily import TavilyClient


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web using Tavily and return simplified results.
    """

    api_key = st.secrets.get("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("TAVILY_API_KEY is not configured.")

    client = TavilyClient(api_key=api_key)

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results
    )

    results = []

    for result in response.get("results", []):
        results.append({
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get("content", "")
        })

    return results