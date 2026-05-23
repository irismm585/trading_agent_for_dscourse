"""Mock data module — generates realistic simulated data for offline operation.

When TRADINGAGENTS_MOCK_DATA=true, all external API calls are bypassed and
this module generates synthetic data (OHLCV, profiles, financials, news, etc.)
using seeded random walks and static templates.

All format functions from the real data modules are reused directly.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.data_layer.fundamental_data import (
    extract_key_metrics,
    format_financial_summary,
)
from backend.data_layer.stock_data import (
    compute_indicators,
    format_ohlcv_summary,
    format_indicators_summary,
    ohlcv_to_json,
)
from backend.data_layer.news_data import format_news_summary
from backend.data_layer.sentiment_data import format_sentiment_summary
from backend.data_layer.anysearch import format_search_summary


# ── Known stock profiles (symbol → {name, base_price, industry}) ──────

KNOWN_STOCKS: dict[str, dict[str, Any]] = {
    # A-shares
    "600519": {"name": "贵州茅台", "base_price": 1520.0, "industry": "白酒", "exchange": "SH"},
    "000001": {"name": "平安银行", "base_price": 11.5, "industry": "银行", "exchange": "SZ"},
    "000002": {"name": "万科A", "base_price": 8.2, "industry": "房地产", "exchange": "SZ"},
    "600036": {"name": "招商银行", "base_price": 38.0, "industry": "银行", "exchange": "SH"},
    "600276": {"name": "恒瑞医药", "base_price": 42.0, "industry": "医药", "exchange": "SH"},
    "300750": {"name": "宁德时代", "base_price": 195.0, "industry": "新能源", "exchange": "SZ"},
    "000858": {"name": "五粮液", "base_price": 135.0, "industry": "白酒", "exchange": "SZ"},
    "601318": {"name": "中国平安", "base_price": 48.0, "industry": "保险", "exchange": "SH"},
    "600887": {"name": "伊利股份", "base_price": 28.0, "industry": "食品饮料", "exchange": "SH"},
    "002415": {"name": "海康威视", "base_price": 32.0, "industry": "安防", "exchange": "SZ"},
    # US stocks
    "AAPL": {"name": "Apple Inc.", "base_price": 185.0, "industry": "Technology", "exchange": "NASDAQ"},
    "MSFT": {"name": "Microsoft Corporation", "base_price": 420.0, "industry": "Technology", "exchange": "NASDAQ"},
    "GOOGL": {"name": "Alphabet Inc.", "base_price": 175.0, "industry": "Technology", "exchange": "NASDAQ"},
    "AMZN": {"name": "Amazon.com Inc.", "base_price": 195.0, "industry": "E-Commerce", "exchange": "NASDAQ"},
    "TSLA": {"name": "Tesla Inc.", "base_price": 260.0, "industry": "Automotive", "exchange": "NASDAQ"},
    "NVDA": {"name": "NVIDIA Corporation", "base_price": 880.0, "industry": "Semiconductor", "exchange": "NASDAQ"},
    "META": {"name": "Meta Platforms Inc.", "base_price": 510.0, "industry": "Technology", "exchange": "NASDAQ"},
    "JPM": {"name": "JPMorgan Chase & Co.", "base_price": 210.0, "industry": "Banking", "exchange": "NYSE"},
    "V": {"name": "Visa Inc.", "base_price": 280.0, "industry": "Financial Services", "exchange": "NYSE"},
    "BABA": {"name": "Alibaba Group Holding Ltd.", "base_price": 110.0, "industry": "E-Commerce", "exchange": "NYSE"},
}


# ═══════════════════════════════════════════════════════════════════════
# OHLCV generation (seeded random walk)
# ═══════════════════════════════════════════════════════════════════════

def _make_seed(symbol: str) -> int:
    """Deterministic seed from symbol string."""
    return abs(hash(symbol)) % (2**31)


def _generate_ohlcv_df(symbol: str, trade_date: str, market: str, days: int = 60) -> pd.DataFrame:
    """Generate realistic OHLCV data using a seeded random walk.

    Price starts at a known base price for well-known symbols,
    or defaults to 20.0 for unknown symbols. A small drift (+0.03%)
    and volatility (1.2% daily) produce realistic-looking price series.
    """
    info = KNOWN_STOCKS.get(symbol.upper(), {})
    base = info.get("base_price", 20.0)

    rng = np.random.default_rng(_make_seed(symbol))

    # Daily log returns: small positive drift + noise
    n = days
    drift = 0.0003
    volatility = 0.012
    log_returns = rng.normal(drift, volatility, n)

    # Random walk price path
    prices = base * np.exp(np.cumsum(log_returns))
    prices = np.maximum(prices, base * 0.7)  # floor at 70% of base

    # Generate OHLC from adjusted random walk
    rows = []
    end_date = datetime.strptime(trade_date, "%Y-%m-%d")
    for i in range(n):
        d = (end_date - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d")
        c = float(prices[i])
        daily_vol = c * volatility * 0.6
        o = float(rng.uniform(c - daily_vol, c + daily_vol))
        h = float(max(o, c) + rng.uniform(0, daily_vol * 0.5))
        l_ = float(min(o, c) - rng.uniform(0, daily_vol * 0.5))
        v = int(rng.integers(1000000, 50000000))
        rows.append({"date": d, "open": round(o, 2), "high": round(h, 2),
                     "low": round(l_, 2), "close": round(c, 2), "volume": v})

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════════

def _get_mock_profile(symbol: str, market: str, ohlcv_df: pd.DataFrame) -> dict:
    """Build stock profile from known info + last OHLCV row."""
    info = KNOWN_STOCKS.get(symbol.upper(), {})
    name = info.get("name", symbol.upper())
    industry = info.get("industry", "")
    exchange = info.get("exchange", "SH" if market == "cn" else "NASDAQ")

    last = ohlcv_df.iloc[-1] if not ohlcv_df.empty else None
    prev = ohlcv_df.iloc[-2] if ohlcv_df is not None and len(ohlcv_df) > 1 else None

    if last is not None:
        change_pct = round((last["close"] - prev["close"]) / prev["close"] * 100, 2) if prev is not None else 0.0
        profile: dict = {
            "symbol": symbol.upper(),
            "name": name,
            "price": float(last["close"]),
            "open": float(last["open"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "last_close": float(last["close"]),
            "change_pct": change_pct,
            "volume": int(last["volume"]),
            "amount": None,
            "industry": industry,
            "exchange": exchange,
        }
    else:
        profile = {"symbol": symbol.upper(), "name": name, "price": None}

    return profile


# ═══════════════════════════════════════════════════════════════════════
# Index data
# ═══════════════════════════════════════════════════════════════════════

def _get_mock_index_data(market: str) -> dict:
    """Return static index data."""
    if market == "cn":
        return {
            "上证指数": {"price": 3150.45, "change_pct": 0.35},
            "沪深300": {"price": 3780.22, "change_pct": 0.42},
            "深证成指": {"price": 10450.88, "change_pct": -0.12},
        }
    else:
        return {
            "标普500": {"price": 5320.15, "change_pct": 0.28},
            "纳斯达克": {"price": 16780.50, "change_pct": 0.55},
            "道琼斯": {"price": 39850.30, "change_pct": -0.08},
        }


# ═══════════════════════════════════════════════════════════════════════
# Fundamentals
# ═══════════════════════════════════════════════════════════════════════

def _get_mock_fundamentals(symbol: str, market: str) -> dict:
    """Return static fundamental/financial data matching get_financial_data() structure."""
    info = KNOWN_STOCKS.get(symbol.upper(), {})
    base = info.get("base_price", 20.0)
    name = info.get("name", symbol.upper())
    industry = info.get("industry", "")

    # Scale market cap by base price
    shares_outstanding = 1e9 if base > 100 else 5e9  # rough shares outstanding
    market_cap = base * shares_outstanding

    if market == "cn":
        info_dict = {
            "总市值": market_cap,
            "流通市值": market_cap * 0.7,
            "市盈率-动态": round(18.0 + np.random.default_rng(_make_seed(symbol)).uniform(-5, 5), 2),
            "市净率": round(3.0 + np.random.default_rng(_make_seed(symbol + "_pb")).uniform(-1, 2), 2),
            "净利润": market_cap * 0.05,
            "营业收入": market_cap * 0.3,
            "每股收益": round(base / 20, 2),
            "每股净资产": round(base / 5, 2),
            "净资产收益率": round(12.0 + np.random.default_rng(_make_seed(symbol + "_roe")).uniform(-4, 8), 2),
            "毛利率": round(45.0 + np.random.default_rng(_make_seed(symbol + "_gm")).uniform(-15, 20), 2),
        }
    else:
        pe = round(25.0 + np.random.default_rng(_make_seed(symbol)).uniform(-8, 8), 2)
        info_dict = {
            "longName": name,
            "sector": industry or "Technology",
            "industry": industry or "Software",
            "marketCap": market_cap,
            "trailingPE": pe,
            "forwardPE": round(pe * 0.9, 2),
            "priceToBook": round(6.0 + np.random.default_rng(_make_seed(symbol + "_pb")).uniform(-2, 4), 2),
            "trailingEps": round(base / pe, 2),
            "returnOnEquity": round(22.0 + np.random.default_rng(_make_seed(symbol + "_roe")).uniform(-8, 10), 2),
            "profitMargins": round(0.20 + np.random.default_rng(_make_seed(symbol + "_pm")).uniform(-0.08, 0.10), 4),
            "grossMargins": round(0.45 + np.random.default_rng(_make_seed(symbol + "_gm")).uniform(-0.15, 0.20), 4),
            "totalRevenue": market_cap * 0.4,
            "freeCashflow": market_cap * 0.04,
            "beta": round(1.0 + np.random.default_rng(_make_seed(symbol + "_beta")).uniform(-0.3, 0.5), 2),
            "dividendYield": round(0.005 + np.random.default_rng(_make_seed(symbol + "_div")).uniform(0, 0.015), 4),
            "revenueGrowth": round(0.08 + np.random.default_rng(_make_seed(symbol + "_rg")).uniform(-0.05, 0.10), 4),
        }

    # Income statement mock data (DataFrame)
    income_data = {
        "报表日期": ["2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"],
        "营业收入": [market_cap * 0.3, market_cap * 0.22, market_cap * 0.14, market_cap * 0.06, market_cap * 0.28],
        "净利润": [market_cap * 0.05, market_cap * 0.038, market_cap * 0.025, market_cap * 0.01, market_cap * 0.045],
        "基本每股收益": [round(base / 20, 2)] * 5,
    }
    income_df = pd.DataFrame(income_data)

    balance_data = {
        "报表日期": ["2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"],
        "总资产": [market_cap * 1.5] * 5,
        "总负债": [market_cap * 0.6] * 5,
        "股东权益合计": [market_cap * 0.9] * 5,
    }
    balance_df = pd.DataFrame(balance_data)

    cf_data = {
        "报表日期": ["2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"],
        "经营活动现金流净额": [market_cap * 0.08] * 5,
        "投资活动现金流净额": [-market_cap * 0.03] * 5,
        "筹资活动现金流净额": [-market_cap * 0.02] * 5,
    }
    cf_df = pd.DataFrame(cf_data)

    return {
        "info": info_dict,
        "income": income_df,
        "balance": balance_df,
        "cashflow": cf_df,
    }


# ═══════════════════════════════════════════════════════════════════════
# News
# ═══════════════════════════════════════════════════════════════════════

def _get_mock_news(symbol: str, market: str) -> list[dict]:
    """Return pre-written mock news items."""
    name = KNOWN_STOCKS.get(symbol.upper(), {}).get("name", symbol.upper())

    if market == "cn":
        return [
            {"title": f"{name}发布最新财报，营收同比增长8.5%", "summary": f"{name}发布季度报告显示营收增长超预期，净利润同比提升12.3%。", "url": "https://finance.sina.com.cn/mock", "source": "新浪财经", "date": "2026-05-20"},
            {"title": f"机构维持{name}买入评级，目标价上调10%", "summary": "多家券商发布研究报告，认为公司基本面良好，给予买入评级。", "url": "https://finance.eastmoney.com/mock", "source": "东方财富", "date": "2026-05-18"},
            {"title": f"{name}宣布新一轮股票回购计划", "summary": f"{name}董事会批准了总额50亿元的回购计划，彰显对公司长期发展的信心。", "url": "https://www.mock.cn/news2", "source": "证券时报", "date": "2026-05-15"},
            {"title": "北向资金持续流入，市场情绪回暖", "summary": "近期北向资金连续多日净流入，对A股市场形成支撑。", "url": "https://www.mock.cn/news3", "source": "中国证券报", "date": "2026-05-14"},
            {"title": "行业政策利好，板块整体走强", "summary": "相关部门出台支持政策，对行业形成实质性利好。", "url": "https://www.mock.cn/news4", "source": "上海证券报", "date": "2026-05-12"},
        ]
    else:
        return [
            {"title": f"{name} Reports Strong Q2 Earnings Beat", "summary": f"{name} exceeded analyst expectations with Q2 EPS of $2.45 vs $2.28 consensus, driven by robust services growth.", "url": "https://finance.yahoo.com/mock1", "source": "Yahoo Finance", "date": "2026-05-21"},
            {"title": f"Analysts Raise {name} Price Target", "summary": "Several analysts raised their price targets citing strong growth outlook and margin expansion.", "url": "https://www.bloomberg.com/mock2", "source": "Bloomberg", "date": "2026-05-19"},
            {"title": f"{name} Announces $10B Share Buyback Program", "summary": f"The Board authorized a new $10 billion share repurchase program, signaling confidence in long-term prospects.", "url": "https://www.reuters.com/mock3", "source": "Reuters", "date": "2026-05-16"},
            {"title": "Fed Signals Potential Rate Cut, Markets Rally", "summary": "Federal Reserve Chair indicated potential rate cuts later this year, boosting market sentiment across sectors.", "url": "https://www.cnbc.com/mock4", "source": "CNBC", "date": "2026-05-14"},
            {"title": "Tech Sector Leads Market Recovery", "summary": "Technology stocks rallied this week as investor confidence returned amid easing inflation concerns.", "url": "https://www.marketwatch.com/mock5", "source": "MarketWatch", "date": "2026-05-13"},
        ]


# ═══════════════════════════════════════════════════════════════════════
# Sentiment
# ═══════════════════════════════════════════════════════════════════════

def _get_mock_sentiment(symbol: str, market: str) -> dict:
    """Return mock social sentiment data."""
    name = KNOWN_STOCKS.get(symbol.upper(), {}).get("name", symbol.upper())

    if market == "cn":
        return {
            "reddit": [
                {"content": f"分析{name}技术面，MACD金叉形成，短期看多", "sentiment": "bullish", "score": 45, "subreddit": "stock_analysis"},
                {"content": f"{name}估值仍然偏高，PE超过行业平均，建议观望", "sentiment": "bearish", "score": 32, "subreddit": "value_investing"},
                {"content": f"{name}最近成交量放大，资金流入明显，突破前期高点", "sentiment": "bullish", "score": 28, "subreddit": "wallstreetbets"},
                {"content": "大盘震荡调整，控制仓位注意风险", "sentiment": "neutral", "score": 55, "subreddit": "investing"},
                {"content": f"{name}回调就是上车机会，长期看好", "sentiment": "bullish", "score": 18, "subreddit": "stock_analysis"},
            ],
            "stocktwits": [
                {"content": f"$SYM {name} looking strong today! 🚀", "sentiment": "bullish", "likes": 120, "date": "2026-05-21"},
                {"content": f"$SYM taking profits here, resistance at ${int(KNOWN_STOCKS.get(symbol.upper(), {}).get('base_price', 20) * 1.1)}", "sentiment": "bearish", "likes": 45, "date": "2026-05-20"},
                {"content": "$SYM consolidation before next leg up", "sentiment": "bullish", "likes": 78, "date": "2026-05-19"},
            ],
            "summary": f"市场对{name}整体情绪偏乐观，多头观点占主导。技术面指标显示短期有上涨动能。",
        }
    else:
        return {
            "reddit": [
                {"content": f"${symbol} Q2 earnings were incredible, margins expanding faster than expected. Long and strong.", "sentiment": "bullish", "score": 234, "subreddit": "investing"},
                {"content": f"${symbol} is overbought on the daily chart. RSI above 70, expect a pullback soon.", "sentiment": "bearish", "score": 156, "subreddit": "technicalanalysis"},
                {"content": f"Added to my ${symbol} position. The services segment is a cash cow.", "sentiment": "bullish", "score": 89, "subreddit": "wallstreetbets"},
                {"content": "Market breadth is improving, VIX dropping. Good time to be in risk-on assets.", "sentiment": "bullish", "score": 312, "subreddit": "stocks"},
                {"content": f"${symbol} PE compression is concerning if growth slows next quarter.", "sentiment": "neutral", "score": 67, "subreddit": "value_investing"},
            ],
            "stocktwits": [
                {"content": f"${symbol} breakout above resistance! Next stop: all-time highs", "sentiment": "bullish", "likes": 245, "date": "2026-05-21"},
                {"content": f"${symbol} taking some off the table here, 20% gain this month", "sentiment": "bearish", "likes": 89, "date": "2026-05-20"},
                {"content": f"${symbol} looking like a buy-the-dip setup if we get a 5% correction", "sentiment": "bullish", "likes": 134, "date": "2026-05-19"},
            ],
            "summary": f"Overall market sentiment for {name} is bullish with strong retail investor interest. Technical indicators suggest short-term momentum is positive.",
        }


# ═══════════════════════════════════════════════════════════════════════
# Web search results
# ═══════════════════════════════════════════════════════════════════════

def _get_mock_search_results(symbol: str, company_name: str) -> list[dict]:
    """Return mock web search results about the stock."""
    return [
        {"title": f"{company_name} ({symbol}) Stock Analysis & Outlook 2026",
         "snippet": f"Comprehensive analysis of {company_name} including financial health, market position, growth catalysts and risk factors for 2026.",
         "url": f"https://example.com/analysis/{symbol}"},
        {"title": f"{company_name} Q2 2026 Earnings Preview",
         "snippet": f"Analysts expect {company_name} to report revenue growth of 8-12% YoY, with margin expansion driven by operational efficiencies.",
         "url": f"https://example.com/earnings/{symbol}"},
        {"title": f"{company_name} Market Share Analysis — Competitive Position",
         "snippet": f"{company_name} maintains a strong competitive position with expanding market share in key segments, driven by innovation and brand strength.",
         "url": f"https://example.com/competitive/{symbol}"},
        {"title": f"Industry Trends Impacting {company_name} in 2026",
         "snippet": "Regulatory developments, technological shifts, and changing consumer preferences are reshaping the industry landscape.",
         "url": f"https://example.com/industry/{symbol}"},
    ]


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def get_mock_data_bundle(symbol: str, trade_date: str, market: str) -> dict:
    """Generate a full data bundle dict matching fetch_all_data() output.

    All external API calls are bypassed — instead we generate synthetic
    data that looks realistic enough for LLM analysis.
    """
    symbol = symbol.upper()

    # 1. Generate OHLCV data
    ohlcv_df = _generate_ohlcv_df(symbol, trade_date, market)
    ohlcv_json = ohlcv_to_json(ohlcv_df)

    # 2. Technical indicators
    indicators = compute_indicators(ohlcv_df) if ohlcv_df is not None and not ohlcv_df.empty else {}

    # 3. Profile
    profile = _get_mock_profile(symbol, market, ohlcv_df)

    # 4. Index data
    index_data = _get_mock_index_data(market)

    # 5. Fundamentals
    fundamentals = _get_mock_fundamentals(symbol, market)
    fin_text = format_financial_summary(fundamentals)
    financial_metrics = extract_key_metrics(fundamentals)

    # 6. News
    stock_news = _get_mock_news(symbol, market)
    news_text = format_news_summary(stock_news, "个股新闻" if market == "cn" else "Stock News")

    # 7. Sentiment
    sentiment = _get_mock_sentiment(symbol, market)
    sent_text = format_sentiment_summary(sentiment)

    # 8. Search results
    company_name = profile.get("name", symbol)
    search_results = _get_mock_search_results(symbol, company_name)
    search_text = format_search_summary(search_results, symbol)

    # Formatted summaries
    ohlcv_text = format_ohlcv_summary(ohlcv_df)
    ind_text = format_indicators_summary(indicators)

    result = {
        "ohlcv_df": ohlcv_df,
        "ohlcv_json": ohlcv_json,
        "profile": profile,
        "index_data": index_data,
        "indicators": indicators,
        "fundamentals": fundamentals,
        "stock_news": stock_news,
        "market_news": [],
        "sentiment": sentiment,
        "search_results": search_results,
        "ohlcv_text": ohlcv_text,
        "indicators_text": ind_text,
        "financial_text": fin_text,
        "news_text": news_text,
        "sentiment_text": sent_text,
        "search_text": search_text,
        "financial_metrics": financial_metrics,
        "market": market,
    }

    print(f"[mock_data] Generated mock bundle for {symbol} ({market})")
    return result


def get_mock_search_results(query: str, market: str) -> list[dict]:
    """Return mock stock search results matching known symbols."""
    query = query.strip().lower()
    results = []

    for sym, info in KNOWN_STOCKS.items():
        sym_lower = sym.lower()
        name_lower = info.get("name", "").lower()

        # Filter by market
        if market == "cn" and not sym.isdigit():
            continue
        if market == "us" and sym.isdigit():
            continue

        # Match by symbol or name
        if query in sym_lower or query in name_lower:
            results.append({
                "symbol": sym,
                "name": info.get("name", sym),
                "market": market,
                "exchange": info.get("exchange", "SH" if market == "cn" else "NASDAQ"),
            })

        if len(results) >= 10:
            break

    # If no match, return a default entry for unknown symbols
    if not results:
        if market == "cn" and query.isdigit() and len(query) == 6:
            results.append({
                "symbol": query.upper(),
                "name": f"A股股票{query}",
                "market": "cn",
                "exchange": "SH",
            })
        elif market == "us":
            results.append({
                "symbol": query.upper(),
                "name": query.upper(),
                "market": "us",
                "exchange": "NYSE",
            })

    return results
