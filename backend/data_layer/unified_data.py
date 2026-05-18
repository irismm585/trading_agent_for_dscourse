"""Unified data layer — all data via yfinance.

Market parameter ("cn" or "us") controls symbol conversion:
  - "cn": 600519 → 600519.SS, 000001 → 000001.SZ
  - "us": AAPL → AAPL (as-is)

All data sources are yfinance-based, no external dependencies beyond yfinance.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

import time

from backend.data_layer.cache import data_cache
from backend.data_layer.stock_data import (
    get_stock_ohlcv,
    get_stock_quote,
    _get_stock_name_and_industry,
    _get_us_stock_quote,
    compute_indicators,
    format_ohlcv_summary,
    format_indicators_summary,
    ohlcv_to_json,
)
from backend.data_layer.fundamental_data import (
    get_financial_data,
    format_financial_summary,
)
from backend.data_layer.news_data import (
    get_stock_news,
    get_market_news,
    format_news_summary,
)
from backend.data_layer.sentiment_data import (
    get_social_sentiment,
    format_sentiment_summary,
)


# ── Market-aware data fetchers ─────────────────────────────────────

def get_ohlcv(symbol: str, start_date: str, end_date: str, market: str = "cn") -> Optional[pd.DataFrame]:
    """Fetch OHLCV data (yfinance, auto-converts CN codes)."""
    return get_stock_ohlcv(symbol, start_date, end_date, market)


def get_fundamentals(symbol: str, market: str = "cn") -> dict:
    """Fetch fundamental/financial data."""
    return get_financial_data(symbol, market)


def get_news_data(symbol: str, market: str = "cn", limit: int = 20) -> list[dict]:
    """Fetch stock-specific news."""
    return get_stock_news(symbol, market, limit=limit)


def get_market_news_data(market: str = "cn", limit: int = 10) -> list[dict]:
    """Fetch macro/market news."""
    return get_market_news(market, limit=limit)


def get_sentiment_data(symbol: str, market: str = "cn") -> dict:
    """Fetch social sentiment data."""
    return get_social_sentiment(symbol, market)


def format_ohlcv_text(df: Optional[pd.DataFrame], market: str = "cn") -> str:
    """Format OHLCV summary text."""
    return format_ohlcv_summary(df)


def format_indicators_text(indicators: dict) -> str:
    """Format technical indicators text."""
    return format_indicators_summary(indicators)


def format_financial_text(data: dict, market: str = "cn") -> str:
    """Format financial data text."""
    return format_financial_summary(data)


def format_news_text(news_list: list[dict], title: str = "新闻", market: str = "cn") -> str:
    """Format news text."""
    return format_news_summary(news_list, title)


def format_sentiment_text(data: dict, market: str = "cn") -> str:
    """Format sentiment data text."""
    return format_sentiment_summary(data)


# ── Full data bundle ────────────────────────────────────────────────

def _fetch_index_data() -> dict:
    """Fetch A-share index data (CSI300, Shanghai, Shenzhen) via pytdx."""
    indices = {}
    try:
        from pytdx.hq import TdxHq_API
        api = TdxHq_API()
        api.connect('180.153.18.170', 7709)
        for mkt, code, name in [(1, '000001', '上证指数'), (1, '000300', '沪深300'), (0, '399001', '深证成指')]:
            bars = api.get_security_bars(4, mkt, code, 0, 3)
            if bars:
                last = bars[-1]
                prev = bars[-2]
                chg = (last["close"] - prev["close"]) / prev["close"] * 100
                indices[name] = {"price": float(last["close"]), "change_pct": round(chg, 2)}
        api.disconnect()
    except Exception:
        pass
    return indices


def _fetch_us_index_data() -> dict:
    """Fetch US index data (S&P 500, Nasdaq, Dow) via yfinance with delays."""
    indices = {}
    if yf is None:
        return indices
    for ticker, name in [("^GSPC", "标普500"), ("^IXIC", "纳斯达克"), ("^DJI", "道琼斯")]:
        try:
            index = yf.Ticker(ticker)
            hist = index.history(period="5d")
            if hist is not None and len(hist) >= 2:
                last = hist.iloc[-1]
                prev = hist.iloc[-2]
                chg = (last["Close"] - prev["Close"]) / prev["Close"] * 100
                indices[name] = {"price": round(float(last["Close"]), 2), "change_pct": round(chg, 2)}
                print(f"[unified_data] index {name} OK")
        except Exception as e:
            print(f"[unified_data] index {name} error: {e}")
        time.sleep(3)
    return indices


# ── US data bundle (single yfinance ticker) ──

def _call_with_timeout(fn, timeout=15):
    """Call fn() with a timeout. Returns result or None on timeout/exception."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None
        except Exception:
            return None


def _lookup_us_name(symbol: str) -> str:
    """Lightweight company name lookup via yfinance Search (avoids heavy info endpoint)."""
    try:
        search = yf.Search(symbol, news_count=0, enable_fuzzy_query=False)
        if search and search.quotes:
            q = search.quotes[0]
            return q.get("shortname") or q.get("longname") or symbol
    except Exception:
        pass
    return symbol


def _fetch_us_bundle(symbol: str, start_date: str, trade_date: str, lookback_days: int) -> dict:
    """Fetch ALL US stock data — history is critical, everything else is best-effort.

    Strategy:
      1. history()  → OHLCV + indicators (primary data, with retry + yf.download fallback)
      2. name       → lightweight yf.Search() lookup (avoids rate-limited info endpoint)
      3. quarterly_* → financial statements (best-effort, single attempt)
      4. get_news() → news (single attempt, 15s timeout)
    """
    from backend.data_layer.news_data import _extract_article
    from backend.data_layer.stock_data import ohlcv_to_json

    ticker = yf.Ticker(symbol)

    # ═══════════════════════════════════════════════════
    # 1. HISTORY (critical — multi-layer fallback)
    # ═══════════════════════════════════════════════════
    ohlcv_df = None

    # Layer 1: ticker.history() with exponential backoff
    backoff = [3, 10, 30]
    for attempt, wait in enumerate(backoff):
        try:
            ohlcv_df = ticker.history(start=start_date, end=trade_date)
            if ohlcv_df is not None and not ohlcv_df.empty:
                print(f"[unified_data] US history OK for {symbol}: {len(ohlcv_df)} rows (attempt {attempt+1})")
                break
            print(f"[unified_data] US history empty for {symbol} (attempt {attempt+1}), retrying in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            err_str = str(e)
            if "rate" in err_str.lower() or "too many" in err_str.lower():
                print(f"[unified_data] US history RATE LIMITED for {symbol} (attempt {attempt+1}), waiting {wait}s...")
            else:
                print(f"[unified_data] US history error for {symbol} (attempt {attempt+1}): {e}")
            time.sleep(wait)

    # Layer 2: yf.download() fallback
    if ohlcv_df is None or ohlcv_df.empty:
        try:
            print(f"[unified_data] trying yf.download() fallback for {symbol}")
            dl_df = yf.download(symbol, start=start_date, end=trade_date, progress=False, auto_adjust=True)
            if dl_df is not None and not dl_df.empty:
                ohlcv_df = dl_df
                print(f"[unified_data] yf.download() OK for {symbol}: {len(ohlcv_df)} rows")
        except Exception as e:
            print(f"[unified_data] yf.download() fallback failed for {symbol}: {e}")

    # Layer 3: Direct Yahoo chart API via requests (different TLS stack, no curl_cffi)
    if ohlcv_df is None or ohlcv_df.empty:
        try:
            print(f"[unified_data] trying direct Yahoo chart API for {symbol}")
            import requests as req_lib
            from datetime import datetime as dt_lib
            p1 = int(dt_lib.strptime(start_date, "%Y-%m-%d").timestamp())
            p2 = int(dt_lib.strptime(trade_date, "%Y-%m-%d").timestamp())
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"period1": p1, "period2": p2, "interval": "1d"}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = req_lib.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            chart_data = resp.json()
            result = chart_data.get("chart", {}).get("result", [])
            if result:
                timestamps = result[0].get("timestamp", [])
                quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
                rows = []
                for i, ts in enumerate(timestamps):
                    rows.append({
                        "date": dt_lib.fromtimestamp(ts).strftime("%Y-%m-%d"),
                        "open": quotes.get("open", [None])[i],
                        "high": quotes.get("high", [None])[i],
                        "low": quotes.get("low", [None])[i],
                        "close": quotes.get("close", [None])[i],
                        "volume": quotes.get("volume", [None])[i],
                    })
                ohlcv_df = pd.DataFrame(rows)
                print(f"[unified_data] direct chart API OK for {symbol}: {len(ohlcv_df)} rows")
        except Exception as e:
            print(f"[unified_data] direct chart API fallback failed for {symbol}: {e}")

    # Normalize
    if ohlcv_df is not None and not ohlcv_df.empty:
        if ohlcv_df.index.tz is not None:
            ohlcv_df.index = ohlcv_df.index.tz_localize(None)
        col_map = {"Open": "open", "High": "high", "Low": "low",
                    "Close": "close", "Volume": "volume"}
        ohlcv_df = ohlcv_df.rename(columns={k: v for k, v in col_map.items() if k in ohlcv_df.columns})
        ohlcv_df = ohlcv_df.reset_index()
        if "Date" in ohlcv_df.columns:
            ohlcv_df = ohlcv_df.rename(columns={"Date": "date"})
        ohlcv_df["date"] = ohlcv_df["date"].astype(str)

    indicators = {}
    if ohlcv_df is not None and not ohlcv_df.empty and "close" in ohlcv_df.columns:
        indicators = compute_indicators(ohlcv_df)

    ohlcv_text = format_ohlcv_text(ohlcv_df, "us")
    ind_text = format_indicators_text(indicators)
    ohlcv_json = ohlcv_to_json(ohlcv_df)

    # Profile from history (always available if history succeeded)
    last_row = ohlcv_df.iloc[-1] if ohlcv_df is not None and not ohlcv_df.empty else None
    profile = {
        "symbol": symbol,
        "name": symbol,
        "price": float(last_row["close"]) if last_row is not None else None,
        "open": float(last_row["open"]) if last_row is not None else None,
        "high": float(last_row["high"]) if last_row is not None else None,
        "low": float(last_row["low"]) if last_row is not None else None,
        "last_close": float(last_row["close"]) if last_row is not None else None,
        "change_pct": 0.0,
        "volume": int(last_row["volume"]) if last_row is not None else None,
        "amount": None,
    }

    # ═══════════════════════════════════════════════════
    # 2. COMPANY NAME (lightweight yf.Search, avoids heavy info endpoint)
    # ═══════════════════════════════════════════════════
    time.sleep(2)
    name = _call_with_timeout(lambda: _lookup_us_name(symbol), timeout=10)
    if name:
        profile["name"] = name
        print(f"[unified_data] US name OK for {symbol}: {name}")
    else:
        print(f"[unified_data] US name lookup skipped for {symbol}")

    # ═══════════════════════════════════════════════════
    # 3. FINANCIAL STATEMENTS (best-effort, single attempt per statement)
    # ═══════════════════════════════════════════════════
    time.sleep(2)
    financials = {"info": {}, "income": None, "balance": None, "cashflow": None}
    try:
        for sname, method in [
            ("income", lambda t: t.quarterly_income_stmt),
            ("balance", lambda t: t.quarterly_balance_sheet),
            ("cashflow", lambda t: t.quarterly_cashflow),
        ]:
            df = _call_with_timeout(lambda m=method: m(ticker), timeout=15)
            if df is not None and not df.empty:
                financials[sname] = df
            time.sleep(1)
    except Exception as e:
        print(f"[unified_data] US financials error: {e}")
    fin_text = format_financial_text(financials, "us")

    # ═══════════════════════════════════════════════════
    # 4. NEWS (single attempt, 15s timeout — don't block on rate limits)
    # ═══════════════════════════════════════════════════
    stock_news = []
    news_result = _call_with_timeout(
        lambda: ticker.get_news(count=20) or [], timeout=15
    )
    if news_result:
        stock_news = [_extract_article(a) for a in news_result[:20]]
        print(f"[unified_data] US news OK for {symbol}: {len(stock_news)} items")
    else:
        print(f"[unified_data] US news skipped for {symbol} (timeout or error)")

    time.sleep(2)
    market_news = _call_with_timeout(_fetch_us_news_fallback, timeout=10) or []
    news_text = format_news_text(stock_news, "个股新闻", "us")
    if market_news:
        news_text += "\n\n" + format_news_text(market_news, "宏观/市场新闻", "us")

    # ═══════════════════════════════════════════════════
    # 5. SENTIMENT (Reddit + StockTwits — separate APIs, no yfinance)
    # ═══════════════════════════════════════════════════
    sentiment = get_social_sentiment(symbol, "us")
    sent_text = format_sentiment_text(sentiment, "us")

    # ═══════════════════════════════════════════════════
    # 6. INDEX DATA (best-effort)
    # ═══════════════════════════════════════════════════
    index_data = _fetch_us_index_data()

    # Market news
    market_news = _fetch_us_news_fallback()
    news_text = format_news_text(stock_news, "个股新闻", "us")
    if market_news:
        news_text += "\n\n" + format_news_text(market_news, "宏观/市场新闻", "us")

    # ── 5. Sentiment ──
    sentiment = get_social_sentiment(symbol, "us")
    sent_text = format_sentiment_text(sentiment, "us")

    # ── 6. Index data ──
    index_data = _fetch_us_index_data()

    result = {
        "ohlcv_df": ohlcv_df, "ohlcv_json": ohlcv_json,
        "profile": profile, "index_data": index_data,
        "indicators": indicators, "fundamentals": financials,
        "stock_news": stock_news, "market_news": market_news,
        "sentiment": sentiment,
        "ohlcv_text": ohlcv_text, "indicators_text": ind_text,
        "financial_text": fin_text, "news_text": news_text,
        "sentiment_text": sent_text, "market": "us",
    }

    # Cache it
    cache_key = f"{symbol}:us:{trade_date}"
    data_cache.set(cache_key, result)
    return result


def _fetch_us_news_fallback(limit: int = 10) -> list:
    """Fallback market news via generic search."""
    try:
        if yf is None:
            return []
        search = yf.Search(query="stock market today SPY", news_count=limit)
        if search and search.news:
            from backend.data_layer.news_data import _extract_article
            return [_extract_article(a) for a in search.news[:limit]]
    except Exception:
        pass
    return []


def fetch_all_data(symbol: str, trade_date: str, market: str = "cn", lookback_days: int = 365) -> dict:
    """Fetch all data for a stock.

    Returns a dict of raw data and formatted text strings.
    Uses TTL cache to avoid redundant data calls within the same session.
    For US stocks, uses a single yfinance ticker with delays to avoid rate limiting.
    """
    cache_key = f"{symbol}:{market}:{trade_date}"

    # Check cache
    cached = data_cache.get(cache_key)
    if cached is not None:
        return cached

    start_date = _lookback_start(trade_date, lookback_days)

    if market == "us":
        return _fetch_us_bundle(symbol, start_date, trade_date, lookback_days)

    # ── CN market ────────────────────────────────────────────────────
    # Stock profile (real-time quote)
    quote = get_stock_quote(symbol)
    name_info = _get_stock_name_and_industry(symbol)
    profile = {
        "symbol": symbol,
        "name": name_info.get("name") or symbol,
        "industry": name_info.get("industry"),
        **(quote or {}),
    }

    # Index data
    index_data = _fetch_index_data()

    # OHLCV + indicators
    ohlcv_df = get_ohlcv(symbol, start_date, trade_date, market)
    indicators = {}
    if ohlcv_df is not None and not ohlcv_df.empty:
        indicators = compute_indicators(ohlcv_df)

    ohlcv_text = format_ohlcv_text(ohlcv_df, market)
    ind_text = format_indicators_text(indicators)

    # Fundamentals
    fundamentals = get_fundamentals(symbol, market)
    fin_text = format_financial_text(fundamentals, market)

    # News
    stock_news = get_news_data(symbol, market)
    market_news = get_market_news_data(market)
    news_text = format_news_text(stock_news, "个股新闻", market)
    if market_news:
        news_text += "\n\n" + format_news_text(market_news, "宏观/市场新闻", market)

    # Sentiment
    sentiment = get_sentiment_data(symbol, market)
    sent_text = format_sentiment_text(sentiment, market)

    ohlcv_json = ohlcv_to_json(ohlcv_df)

    result = {
        "ohlcv_df": ohlcv_df, "ohlcv_json": ohlcv_json,
        "profile": profile, "index_data": index_data,
        "indicators": indicators, "fundamentals": fundamentals,
        "stock_news": stock_news, "market_news": market_news,
        "sentiment": sentiment,
        "ohlcv_text": ohlcv_text, "indicators_text": ind_text,
        "financial_text": fin_text, "news_text": news_text,
        "sentiment_text": sent_text, "market": market,
    }

    data_cache.set(cache_key, result)
    return result


def _lookback_start(trade_date_str: str, days: int = 365) -> str:
    trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d")
    start = trade_date - timedelta(days=days)
    return start.strftime("%Y-%m-%d")
