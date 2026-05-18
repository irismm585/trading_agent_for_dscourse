"""Social sentiment data.

US stocks: Reddit + StockTwits (free public APIs).
CN stocks (A-shares): yfinance news-based sentiment proxy.
"""

from backend.data_layer.symbol_utils import to_yfinance_ticker, is_cn_market
from backend.data_layer.reddit import fetch_reddit_posts
from backend.data_layer.stocktwits import fetch_stocktwits_messages
from backend.data_layer.news_data import get_stock_news, format_news_summary


def get_social_sentiment(symbol: str, market: str = "cn") -> dict:
    """Aggregate social sentiment for a stock.

    Returns dict with market-appropriate sentiment data.
    """
    if is_cn_market(symbol, market):
        # A-shares: use news as sentiment proxy
        news = get_stock_news(symbol, market, limit=15)
        return {
            "source": "yfinance_news",
            "news_items": news,
            "news_count": len(news),
        }
    else:
        # US stocks: Reddit + StockTwits
        ticker = to_yfinance_ticker(symbol, market)
        reddit_text = fetch_reddit_posts(ticker)
        stocktwits_text = fetch_stocktwits_messages(ticker)
        return {
            "source": "reddit+stocktwits",
            "reddit_text": reddit_text,
            "stocktwits_text": stocktwits_text,
        }


def format_sentiment_summary(data: dict) -> str:
    """Format social sentiment as a Chinese summary string.

    Returns empty string when no meaningful data is available
    (caller should handle fallback for LLM prompts separately).
    """
    source = data.get("source", "")

    if source == "yfinance_news":
        # CN stocks: news-based sentiment
        news = data.get("news_items", [])
        if not news:
            return ""
        lines = ["### 市场情绪（基于新闻）"]
        lines.append(f"- 相关新闻数: {len(news)}")
        lines.append("")
        lines.append("#### 近期新闻标题")
        for i, item in enumerate(news[:10], 1):
            title = item.get("title", "")[:100]
            lines.append(f"{i}. {title}")
        return "\n".join(lines)

    elif source == "reddit+stocktwits":
        # US stocks
        reddit = data.get("reddit_text", "")
        stocktwits = data.get("stocktwits_text", "")
        if not reddit and not stocktwits:
            return ""
        lines = ["### 社交媒体情绪 (US)"]
        if reddit:
            lines.append("#### Reddit")
            lines.append(reddit)
            lines.append("")
        if stocktwits:
            lines.append("#### StockTwits")
            lines.append(stocktwits)
        return "\n".join(lines)

    return ""
