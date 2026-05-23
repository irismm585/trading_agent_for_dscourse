"""Stock data fetching layer — all data via yfinance.

Works for both US stocks and Chinese A-shares.
"""

from .stock_data import get_stock_ohlcv, compute_indicators
from .fundamental_data import get_financial_data
from .news_data import get_stock_news, get_market_news
from .sentiment_data import get_social_sentiment
from .unified_data import fetch_all_data
from .anysearch import search_stock_info, format_search_summary

__all__ = [
    "get_stock_ohlcv",
    "compute_indicators",
    "get_financial_data",
    "get_stock_news",
    "get_market_news",
    "get_social_sentiment",
    "fetch_all_data",
    "search_stock_info",
    "format_search_summary",
]
