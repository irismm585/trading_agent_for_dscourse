"""News data.

A-shares → akshare (Eastmoney news)
US stocks → yfinance
"""

import time
from typing import Optional

try:
    import akshare as ak
except ImportError:
    ak = None

try:
    import yfinance as yf
except ImportError:
    yf = None

from backend.data_layer.symbol_utils import to_yfinance_ticker, is_cn_market


# ═══════════════════════════════════════════════════════════════════════
# A-share news (akshare)
# ═══════════════════════════════════════════════════════════════════════

def _ak_retry(fn, max_attempts: int = 3):
    """Retry akshare call with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"[news] retry {attempt+1}/{max_attempts}: {e}")
                time.sleep(1.5 ** attempt)
            else:
                raise
    return None


def _cn_stock_news(symbol: str, limit: int = 20) -> list[dict]:
    """Get A-share news via akshare, fallback to yfinance."""
    if ak is not None:
        try:
            df = _ak_retry(lambda: ak.stock_news_em(symbol=symbol))
            if df is not None and not df.empty:
                records = df.head(limit).to_dict(orient="records")
                return _normalize_cn_news(records)
        except Exception as e:
            print(f"[news] akshare news error for {symbol}: {e}")

    # yfinance fallback
    if yf is not None:
        try:
            ticker_str = to_yfinance_ticker(symbol, "cn")
            stock = yf.Ticker(ticker_str)
            news = stock.get_news(count=limit)
            if news:
                return [_extract_article(raw) for raw in news[:limit]]
        except Exception as e:
            print(f"[news] yfinance fallback error for {ticker_str}: {e}")

    return []


def _cn_market_news(limit: int = 10) -> list[dict]:
    """Get A-share market/macro news, fallback to yfinance Search."""
    if ak is not None:
        try:
            df = _ak_retry(lambda: ak.news_economic_baidu())
            if df is not None and not df.empty:
                records = df.head(limit).to_dict(orient="records")
                return _normalize_cn_news(records)
        except Exception as e:
            print(f"[news] akshare market news error: {e}")

    # yfinance fallback — CN-relevant queries
    if yf is not None:
        queries = ["沪深股市", "A股市场", "China stock market"]
        seen = set()
        all_news = []
        for query in queries:
            try:
                search = yf.Search(query=query, news_count=limit, enable_fuzzy_query=True)
                if search and search.news:
                    for article in search.news:
                        art = _extract_article(article)
                        if art["title"] and art["title"] not in seen:
                            seen.add(art["title"])
                            all_news.append(art)
                if len(all_news) >= limit:
                    break
            except Exception:
                continue
        return all_news[:limit]

    return []


def _normalize_cn_news(records: list[dict]) -> list[dict]:
    """Normalize akshare column names to common format."""
    normalized = []
    for r in records:
        item = {}
        for key, val in r.items():
            k = str(key).strip().lower()
            if any(x in k for x in ("title", "标题", "题目")):
                item["title"] = str(val)
            elif any(x in k for x in ("content", "内容", "summary", "摘要")):
                item["content"] = str(val)[:500] if val else ""
            elif any(x in k for x in ("time", "时间", "publish", "date", "日期")):
                item["publish_time"] = str(val)
            elif any(x in k for x in ("source", "来源")):
                item["source"] = str(val)
        if "title" not in item:
            item["title"] = str(list(r.values())[0])[:100] if r else "无标题"
        normalized.append(item)
    return normalized


# ═══════════════════════════════════════════════════════════════════════
# US stock news (yfinance)
# ═══════════════════════════════════════════════════════════════════════

def _yf_retry(fn, max_retries: int = 3):
    import time
    for attempt in range(max_retries):
        try:
            result = fn()
            return result
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(1.5 ** attempt)
    return None


def _extract_article(article: dict) -> dict:
    if "content" in article:
        c = article["content"]
        return {
            "title": c.get("title", "No title"),
            "content": c.get("summary", ""),
            "source": (c.get("provider") or {}).get("displayName", "Unknown"),
        }
    else:
        return {
            "title": article.get("title", "No title"),
            "content": article.get("summary", ""),
            "source": article.get("publisher", "Unknown"),
        }


def _us_stock_news(symbol: str, limit: int = 20) -> list[dict]:
    """Get US stock news via yfinance."""
    if yf is None:
        raise ImportError("yfinance is required. Install with: pip install yfinance")

    ticker_str = to_yfinance_ticker(symbol, "us")
    try:
        stock = yf.Ticker(ticker_str)
        news = _yf_retry(lambda: stock.get_news(count=limit))
        if not news:
            return []
        return [_extract_article(raw) for raw in news[:limit]]
    except Exception as e:
        print(f"[news] yfinance news error for {ticker_str}: {e}")
        return []


def _us_market_news(limit: int = 10) -> list[dict]:
    """Get global market news via yfinance Search."""
    if yf is None:
        return []

    queries = ["stock market today", "Federal Reserve", "S&P 500 earnings"]
    all_news = []
    seen = set()

    for query in queries:
        try:
            search = _yf_retry(
                lambda q=query: yf.Search(query=q, news_count=limit, enable_fuzzy_query=True)
            )
            if search and search.news:
                for article in search.news:
                    art = _extract_article(article)
                    if art["title"] and art["title"] not in seen:
                        seen.add(art["title"])
                        all_news.append(art)
            if len(all_news) >= limit:
                break
        except Exception:
            continue
    return all_news[:limit]


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def get_stock_news(symbol: str, market: str = "cn", limit: int = 20) -> list[dict]:
    """Get stock news — akshare for CN, yfinance for US."""
    if is_cn_market(symbol, market):
        return _cn_stock_news(symbol, limit)
    else:
        return _us_stock_news(symbol, limit)


def get_market_news(market: str = "cn", limit: int = 10) -> list[dict]:
    """Get market/macro news."""
    if market == "cn":
        return _cn_market_news(limit)
    else:
        return _us_market_news(limit)


def format_news_summary(news_list: list[dict], title: str = "新闻资讯") -> str:
    """Format news list as a Chinese summary string.

    Returns empty string when no news is available (caller should handle
    fallback for LLM prompts separately).
    """
    if not news_list:
        return ""

    lines = [f"### {title}"]
    for i, item in enumerate(news_list[:15], 1):
        news_title = item.get("title", "无标题")
        source = item.get("source", item.get("publisher", ""))
        content = item.get("content", "")

        meta = f"来源: {source}" if source else ""
        lines.append(f"**{i}. {news_title}**")
        if meta:
            lines.append(f"  ({meta})")
        if content:
            lines.append(f"  {content[:300]}")
        lines.append("")
    return "\n".join(lines)
