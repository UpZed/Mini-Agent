"""Web search tool using DuckDuckGo (free, no API key required)."""

import json
from core.tool_system import BaseTool

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using DuckDuckGo. Input: a search query string. Returns title, snippet, and URL for each result."

    def run(self, query: str = "", max_results: int = 5) -> str:
        if not query:
            return "Error: 'query' argument is required."
        if DDGS is None:
            return "Error: ddgs is not installed. Run: pip install ddgs"

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            return f"Error searching DuckDuckGo: {e}"

        if not results:
            return f"No results found for query: {query}"

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   URL: {r['href']}")
            lines.append(f"   {r['body']}")
            lines.append("")

        return "\n".join(lines).strip()
