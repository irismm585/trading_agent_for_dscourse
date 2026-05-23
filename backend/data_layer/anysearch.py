"""AnySearch API wrapper — free web search for US stock information.

API: POST https://api.anysearch.com/v1/search
Body: {"query": "...", "max_results": N}
"""

import json
import os
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_API_URL = os.environ.get(
    "TRADINGAGENTS_ANYSEARCH_API_URL",
    "https://api.anysearch.com/v1/search",
)
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"
_DEFAULT_TIMEOUT = 15
_DEFAULT_MAX_RESULTS = 5


def fetch_search_results(
    query: str,
    max_results: int = _DEFAULT_MAX_RESULTS,
    timeout: int = _DEFAULT_TIMEOUT,
) -> list[dict]:
    """POST a search query to AnySearch and return parsed results.

    Defensively handles: dict with 'results'/'data' keys, or a top-level list.
    Returns [] on any error (network, timeout, bad JSON).
    """
    body = json.dumps(
        {"query": query, "max_results": max_results}, ensure_ascii=False
    ).encode("utf-8")

    req = Request(
        _API_URL,
        data=body,
        headers={
            "User-Agent": _UA,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, OSError):
        return []

    # Normalise response shape
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "hits"):
            items = payload.get(key)
            if isinstance(items, list):
                return items
    return []


def search_stock_info(
    symbol: str,
    company_name: str = "",
    max_results: int = _DEFAULT_MAX_RESULTS,
) -> list[dict]:
    """Convenience: search for a US stock's recent news/analysis."""
    query = f"{company_name} {symbol} stock analysis market outlook"
    return fetch_search_results(query.strip(), max_results=max_results)


def format_search_summary(results: list[dict], symbol: str) -> str:
    """Format AnySearch results as Markdown, matching news_data.py style."""
    if not results:
        return ""

    lines = [
        f"### 网络搜索结果 (AnySearch)",
        f"以下是为 {symbol} 检索的实时网络信息：",
        "",
    ]

    for i, item in enumerate(results, 1):
        title = item.get("title") or item.get("name") or f"结果{i}"
        snippet = (
            item.get("snippet")
            or item.get("description")
            or item.get("content")
            or ""
        )
        url = item.get("url") or item.get("link") or ""
        lines.append(f"{i}. **{title}**")
        if snippet:
            lines.append(f"   摘要：{snippet}")
        if url:
            lines.append(f"   来源：{url}")
        lines.append("")

    return "\n".join(lines)
