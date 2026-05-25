"""Stock price data and technical indicators.

A-shares → pytdx (primary, TCP direct to Tongdaxin) → akshare → yfinance
US stocks → yfinance
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
import json
import time
import numpy as np
import logging

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from pytdx.hq import TdxHq_API
    _TDX_AVAILABLE = True
except ImportError:
    _TDX_AVAILABLE = False

from backend.data_layer.symbol_utils import to_yfinance_ticker, is_cn_market


logger = logging.getLogger(__name__)


class DataFetchLogger:
    """统一的数据获取日志记录器"""
    
    _logs = []
    _max_logs = 1000
    
    @classmethod
    def log_attempt(cls, source: str, symbol: str, start_time: float, 
                     success: bool, duration_ms: float, 
                     error: Optional[str] = None,
                     details: Optional[dict] = None):
        """记录一次数据获取尝试"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "symbol": symbol,
            "success": success,
            "duration_ms": round(duration_ms, 2),
            "error": error,
            "details": details or {}
        }
        cls._logs.append(log_entry)
        
        if len(cls._logs) > cls._max_logs:
            cls._logs = cls._logs[-cls._max_logs:]
        
        status = "✓" if success else "✗"
        error_str = f" | 错误: {error}" if error else ""
        details_str = f" | {json.dumps(details, ensure_ascii=False)}" if details else ""
        print(f"[数据获取] {status} {source} - {symbol} - {duration_ms:.2f}ms{error_str}{details_str}")
        logger.info(f"[数据获取] {source} - {symbol} - {duration_ms:.2f}ms{error_str}{details_str}")
    
    @classmethod
    def get_recent_logs(cls, limit: int = 50):
        """获取最近的日志"""
        return cls._logs[-limit:]
    
    @classmethod
    def get_failed_logs(cls, symbol: Optional[str] = None, source: Optional[str] = None):
        """获取失败的日志记录
        
        Args:
            symbol: 按股票代码过滤（可选）
            source: 按数据源过滤（可选）
        
        Returns:
            失败的日志列表
        """
        logs = [l for l in cls._logs if not l["success"]]
        if symbol:
            logs = [l for l in logs if l["symbol"] == symbol]
        if source:
            logs = [l for l in logs if l["source"] == source]
        return logs
    
    @classmethod
    def get_logs_by_source(cls, source: str, only_failed: bool = False):
        """按数据源获取日志
        
        Args:
            source: 数据源名称
            only_failed: 是否只返回失败记录
            
        Returns:
            日志列表
        """
        logs = [l for l in cls._logs if l["source"] == source]
        if only_failed:
            logs = [l for l in logs if not l["success"]]
        return logs
    
    @classmethod
    def get_logs_by_symbol(cls, symbol: str, only_failed: bool = False):
        """按股票代码获取日志
        
        Args:
            symbol: 股票代码
            only_failed: 是否只返回失败记录
            
        Returns:
            日志列表
        """
        logs = [l for l in cls._logs if l["symbol"] == symbol]
        if only_failed:
            logs = [l for l in logs if not l["success"]]
        return logs
    
    @classmethod
    def print_failed_summary(cls, symbol: Optional[str] = None):
        """打印失败记录的格式化摘要
        
        Args:
            symbol: 按股票代码过滤（可选）
        """
        failed_logs = cls.get_failed_logs(symbol=symbol)
        if not failed_logs:
            print("\n" + "="*60)
            print("✅ 没有失败的记录")
            print("="*60 + "\n")
            return
        
        print("\n" + "="*60)
        print(f"❌ 失败记录摘要 (共 {len(failed_logs)} 条)")
        print("="*60)
        
        # 按数据源分组
        by_source = {}
        for log in failed_logs:
            source = log["source"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(log)
        
        for source, logs in by_source.items():
            print(f"\n📊 数据源: {source}")
            print(f"   失败次数: {len(logs)}")
            
            # 按错误类型分组
            by_error = {}
            for log in logs:
                error = log.get("error", "未知错误")
                if error not in by_error:
                    by_error[error] = []
                by_error[error].append(log)
            
            for error, error_logs in by_error.items():
                print(f"   错误类型: {error}")
                print(f"   出现次数: {len(error_logs)}")
                
                # 显示最近的几条详细信息
                recent = error_logs[-3:]
                for i, log in enumerate(recent):
                    symbol = log.get("symbol", "N/A")
                    duration = log.get("duration_ms", 0)
                    details = log.get("details", {})
                    print(f"   [{i+1}] {symbol} - {duration:.2f}ms - {json.dumps(details, ensure_ascii=False)}")
        
        print("="*60 + "\n")
    
    @classmethod
    def get_summary(cls, symbol: Optional[str] = None):
        """获取统计摘要"""
        logs = cls._logs
        if symbol:
            logs = [l for l in logs if l["symbol"] == symbol]
        
        if not logs:
            return {"total": 0, "success": 0, "failed": 0}
        
        success = sum(1 for l in logs if l["success"])
        return {
            "total": len(logs),
            "success": success,
            "failed": len(logs) - success,
            "avg_duration_ms": round(sum(l["duration_ms"] for l in logs) / len(logs), 2) if logs else 0
        }


def _log_data_fetch(source: str, symbol: str, func, *args, **kwargs):
    """包装函数，记录数据获取的耗时和结果"""
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        duration_ms = (time.time() - start_time) * 1000
        
        is_valid = False
        if result is not None:
            if isinstance(result, pd.DataFrame):
                is_valid = not result.empty
            else:
                is_valid = True
        
        if is_valid:
            DataFetchLogger.log_attempt(
                source=source,
                symbol=symbol,
                start_time=start_time,
                success=True,
                duration_ms=duration_ms,
                details={"result_type": type(result).__name__}
            )
        else:
            DataFetchLogger.log_attempt(
                source=source,
                symbol=symbol,
                start_time=start_time,
                success=False,
                duration_ms=duration_ms,
                error="返回空数据"
            )
        return result
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        DataFetchLogger.log_attempt(
            source=source,
            symbol=symbol,
            start_time=start_time,
            success=False,
            duration_ms=duration_ms,
            error=str(e)
        )
        raise


# ── A-share stock name/industry via akshare ────────────────────────────

def _get_stock_name_and_industry(symbol: str) -> dict:
    """Get A-share stock Chinese name and industry via akshare."""
    result = {"name": None, "industry": None}
    if ak is None:
        return result
    try:
        df = ak.stock_individual_info_em(symbol=symbol)
        if df is not None and not df.empty:
            info_dict = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
            result["name"] = info_dict.get("股票名称")
            result["industry"] = info_dict.get("行业")
    except Exception as e:
        print(f"[stock_data] akshare name lookup error for {symbol}: {e}")
    return result


# ── US stock quote via yfinance ────────────────────────────────────────

def _get_us_stock_quote(symbol: str) -> Optional[dict]:
    """Get US stock real-time quote via yfinance with retry."""
    if yf is None:
        return None
    ticker_str = to_yfinance_ticker(symbol, "us")
    for attempt in range(3):
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            if info and isinstance(info, dict):
                price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
                prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
                chg_pct = info.get("regularMarketChangePercent")
                volume = info.get("regularMarketVolume")
                return {
                    "price": float(price) if price else None,
                    "open": float(info["regularMarketOpen"]) if info.get("regularMarketOpen") else None,
                    "high": float(info["regularMarketDayHigh"]) if info.get("regularMarketDayHigh") else None,
                    "low": float(info["regularMarketDayLow"]) if info.get("regularMarketDayLow") else None,
                    "last_close": float(prev_close) if prev_close else None,
                    "change_pct": round(float(chg_pct) * 100, 2) if chg_pct else 0.0,
                    "volume": int(volume) if volume else None,
                    "amount": None,
                }
        except Exception as e:
            print(f"[stock_data] yfinance quote error for {ticker_str} (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(1.5 ** attempt)
    return None


# ── Tongdaxin server list ────────────────────────────────────────────
_TDX_SERVERS = [
    ("180.153.18.170", 7709),
    ("119.147.212.81", 7709),
    ("119.147.212.113", 7709),
    ("122.51.120.99", 7709),
    ("106.15.71.152", 7709),
    ("120.79.78.56", 7709),
]


def _tdx_market(symbol: str) -> int:
    """Determine Tongdaxin market code: 1=Shanghai, 0=Shenzhen."""
    symbol = symbol.strip()
    return 1 if symbol.startswith(("6", "9")) else 0


def _tdx_ohlcv(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch A-share OHLCV via pytdx (Tongdaxin TCP protocol, most reliable)."""
    if not _TDX_AVAILABLE:
        DataFetchLogger.log_attempt(
            source="pytdx",
            symbol=symbol,
            start_time=time.time(),
            success=False,
            duration_ms=0,
            error="pytdx 未安装"
        )
        return None

    market = _tdx_market(symbol)
    sd = datetime.strptime(start_date, "%Y-%m-%d")
    ed = datetime.strptime(end_date, "%Y-%m-%d")

    for host, port in _TDX_SERVERS:
        api = TdxHq_API()
        start_time = time.time()
        try:
            connect_start = time.time()
            api.connect(host, port, time_out=5)
            connect_duration = (time.time() - connect_start) * 1000
            
            fetch_start = time.time()
            data = api.get_security_bars(4, market, symbol, 0, 800)
            fetch_duration = (time.time() - fetch_start) * 1000
            
            api.disconnect()
            total_duration = (time.time() - start_time) * 1000

            if not data:
                DataFetchLogger.log_attempt(
                    source=f"pytdx:{host}:{port}",
                    symbol=symbol,
                    start_time=start_time,
                    success=False,
                    duration_ms=total_duration,
                    error="返回空数据",
                    details={"connect_ms": connect_duration, "fetch_ms": fetch_duration}
                )
                continue

            rows = []
            for d in data:
                dt = datetime(d["year"], d["month"], d["day"], d["hour"], d["minute"])
                if sd <= dt <= ed:
                    rows.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "open": float(d["open"]),
                        "high": float(d["high"]),
                        "low": float(d["low"]),
                        "close": float(d["close"]),
                        "volume": int(d["vol"]),
                        "amount": float(d["amount"]),
                    })

            if rows:
                rows.sort(key=lambda r: r["date"])
                df = pd.DataFrame(rows)
                DataFetchLogger.log_attempt(
                    source=f"pytdx:{host}:{port}",
                    symbol=symbol,
                    start_time=start_time,
                    success=True,
                    duration_ms=total_duration,
                    details={
                        "connect_ms": connect_duration,
                        "fetch_ms": fetch_duration,
                        "bars_count": len(df),
                        "date_range": f"{df['date'].iloc[0]} to {df['date'].iloc[-1]}"
                    }
                )
                return df
            else:
                DataFetchLogger.log_attempt(
                    source=f"pytdx:{host}:{port}",
                    symbol=symbol,
                    start_time=start_time,
                    success=False,
                    duration_ms=total_duration,
                    error="日期范围内无数据",
                    details={"connect_ms": connect_duration, "fetch_ms": fetch_duration}
                )

        except Exception as exc:
            total_duration = (time.time() - start_time) * 1000
            DataFetchLogger.log_attempt(
                source=f"pytdx:{host}:{port}",
                symbol=symbol,
                start_time=start_time,
                success=False,
                duration_ms=total_duration,
                error=str(exc)
            )
            try:
                api.disconnect()
            except Exception:
                pass

    DataFetchLogger.log_attempt(
        source="pytdx",
        symbol=symbol,
        start_time=time.time(),
        success=False,
        duration_ms=0,
        error="所有服务器均失败"
    )
    return None


# ═══════════════════════════════════════════════════════════════════════
# A-share: akshare column normalisation
# ═══════════════════════════════════════════════════════════════════════

_COLUMN_CANDIDATES: dict[str, list[str]] = {
    "date":    ["日期", "date"],
    "open":    ["开盘", "open"],
    "high":    ["最高", "high"],
    "low":     ["最低", "low"],
    "close":   ["收盘", "close"],
    "volume":  ["成交量", "成交数量", "volume"],
    "amount":  ["成交额", "amount"],
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename akshare DataFrame columns to canonical English names."""
    mapping: dict[str, str] = {}
    for col in df.columns:
        col_str = str(col).strip()
        col_lower = col_str.lower()
        for canonical, candidates in _COLUMN_CANDIDATES.items():
            for cand in candidates:
                if cand in col_str or cand in col_lower:
                    mapping[col_str] = canonical
                    break
    if mapping:
        df = df.rename(columns=mapping)
    return df


# ═══════════════════════════════════════════════════════════════════════
# OHLCV — dispatches by market
# ═══════════════════════════════════════════════════════════════════════

def get_stock_ohlcv(
    symbol: str,
    start_date: str,
    end_date: str,
    market: str = "cn",
) -> Optional[pd.DataFrame]:
    """Fetch daily OHLCV — pytdx→akshare→yfinance for CN, yfinance for US."""
    if is_cn_market(symbol, market):
        # Priority: pytdx (TCP, most reliable) → akshare → yfinance
        df = _tdx_ohlcv(symbol, start_date, end_date)
        if df is not None and not df.empty:
            return df
        df = _cn_ohlcv_akshare(symbol, start_date, end_date)
        if df is not None and not df.empty:
            return df
        return _cn_ohlcv_yfinance(symbol, start_date, end_date)
    else:
        return _us_ohlcv(symbol, start_date, end_date)


def _us_ohlcv(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch US stock OHLCV via yfinance with retry and download() fallback."""
    if yf is None:
        raise ImportError("yfinance is required. Install with: pip install yfinance")

    ticker_str = to_yfinance_ticker(symbol, "us")
    df = None

    # Approach 1: Ticker.history() with retry
    for attempt in range(2):
        start_time = time.time()
        try:
            ticker = yf.Ticker(ticker_str)
            df = ticker.history(start=start_date, end=end_date)
            duration_ms = (time.time() - start_time) * 1000

            if df is not None and not df.empty:
                DataFetchLogger.log_attempt(
                    source="yfinance:history",
                    symbol=ticker_str,
                    start_time=start_time,
                    success=True,
                    duration_ms=duration_ms,
                    details={"attempt": attempt + 1, "bars_count": len(df)}
                )
                break
            else:
                DataFetchLogger.log_attempt(
                    source="yfinance:history",
                    symbol=ticker_str,
                    start_time=start_time,
                    success=False,
                    duration_ms=duration_ms,
                    error="返回空数据",
                    details={"attempt": attempt + 1}
                )
                if attempt == 0:
                    time.sleep(2)
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            DataFetchLogger.log_attempt(
                source="yfinance:history",
                symbol=ticker_str,
                start_time=start_time,
                success=False,
                duration_ms=duration_ms,
                error=str(exc),
                details={"attempt": attempt + 1}
            )
            if attempt == 0:
                time.sleep(2)
    else:
        # Approach 2: yf.download() as fallback
        print(f"[数据获取] 尝试 yf.download() 回退...")
        start_time = time.time()
        try:
            df = yf.download(ticker_str, start=start_date, end=end_date, progress=False, auto_adjust=True)
            duration_ms = (time.time() - start_time) * 1000
            
            if df is not None and not df.empty:
                DataFetchLogger.log_attempt(
                    source="yfinance:download",
                    symbol=ticker_str,
                    start_time=start_time,
                    success=True,
                    duration_ms=duration_ms,
                    details={"bars_count": len(df)}
                )
            else:
                DataFetchLogger.log_attempt(
                    source="yfinance:download",
                    symbol=ticker_str,
                    start_time=start_time,
                    success=False,
                    duration_ms=duration_ms,
                    error="返回空数据"
                )
                return None
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            DataFetchLogger.log_attempt(
                source="yfinance:download",
                symbol=ticker_str,
                start_time=start_time,
                success=False,
                duration_ms=duration_ms,
                error=str(exc)
            )
            return None

    if df is None or df.empty:
        DataFetchLogger.log_attempt(
            source="yfinance",
            symbol=ticker_str,
            start_time=time.time(),
            success=False,
            duration_ms=0,
            error=f"无数据 ({start_date} to {end_date})"
        )
        return None

    # Normalize columns
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    col_map = {
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    df = df.reset_index()
    if "Date" in df.columns:
        df = df.rename(columns={"Date": "date"})
    df["date"] = df["date"].astype(str)

    wanted = ["date", "open", "high", "low", "close", "volume"]
    keep = [c for c in wanted if c in df.columns]
    if "close" not in keep:
        DataFetchLogger.log_attempt(
            source="yfinance",
            symbol=ticker_str,
            start_time=time.time(),
            success=False,
            duration_ms=0,
            error="缺少必要列 (close)"
        )
        return None

    return df[keep].copy()


def _cn_ohlcv_akshare(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """A-share OHLCV via akshare with retry + intraday aggregation fallback."""
    if ak is None:
        DataFetchLogger.log_attempt(
            source="akshare",
            symbol=symbol,
            start_time=time.time(),
            success=False,
            duration_ms=0,
            error="akshare 未安装"
        )
        return None
    
    sd = start_date.replace("-", "")
    ed = end_date.replace("-", "")

    for attempt in range(5):
        start_time = time.time()
        try:
            df = ak.stock_zh_a_hist(symbol.strip(), "daily", sd, ed, "qfq")
            duration_ms = (time.time() - start_time) * 1000
            
            if df is not None and not df.empty:
                df = _normalise_columns(df)
                wanted = ["date", "open", "high", "low", "close", "volume", "amount"]
                keep = [c for c in wanted if c in df.columns]
                if "close" in keep:
                    result_df = df[keep].copy()
                    DataFetchLogger.log_attempt(
                        source=f"akshare:daily",
                        symbol=symbol,
                        start_time=start_time,
                        success=True,
                        duration_ms=duration_ms,
                        details={
                            "attempt": attempt + 1,
                            "bars_count": len(result_df),
                            "date_range": f"{result_df['date'].iloc[0]} to {result_df['date'].iloc[-1]}" if len(result_df) > 0 else "N/A"
                        }
                    )
                    return result_df
                else:
                    DataFetchLogger.log_attempt(
                        source=f"akshare:daily",
                        symbol=symbol,
                        start_time=start_time,
                        success=False,
                        duration_ms=duration_ms,
                        error="缺少必要列 (close)",
                        details={"attempt": attempt + 1, "columns": list(df.columns)}
                    )
                    return None
            else:
                DataFetchLogger.log_attempt(
                    source=f"akshare:daily",
                    symbol=symbol,
                    start_time=start_time,
                    success=False,
                    duration_ms=duration_ms,
                    error="返回空数据",
                    details={"attempt": attempt + 1}
                )
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            DataFetchLogger.log_attempt(
                source=f"akshare:daily",
                symbol=symbol,
                start_time=start_time,
                success=False,
                duration_ms=duration_ms,
                error=str(exc),
                details={"attempt": attempt + 1}
            )
            if attempt < 4:
                sleep_time = min(2 ** attempt, 15)
                print(f"[数据获取] akshare 重试等待 {sleep_time}s...")
                time.sleep(sleep_time)

    DataFetchLogger.log_attempt(
        source="akshare:daily",
        symbol=symbol,
        start_time=time.time(),
        success=False,
        duration_ms=0,
        error="所有重试均失败"
    )

    # Intraday minute aggregation fallback
    print(f"[数据获取] 尝试 akshare 分时数据回退...")
    start_time = time.time()
    try:
        df_min = ak.stock_zh_a_hist_min_em(symbol.strip(), "5", sd, ed, "qfq")
        duration_ms = (time.time() - start_time) * 1000
        
        if df_min is not None and not df_min.empty:
            df_min = _normalise_columns(df_min)
            if "date" in df_min.columns and "close" in df_min.columns:
                df_min["date_only"] = df_min["date"].astype(str).str[:10]
                agg = df_min.groupby("date_only").agg(
                    open=("open", "first"), high=("high", "max"), low=("low", "min"),
                    close=("close", "last"), volume=("volume", "sum"), amount=("amount", "sum"),
                ).reset_index().rename(columns={"date_only": "date"})
                
                DataFetchLogger.log_attempt(
                    source="akshare:intraday_fallback",
                    symbol=symbol,
                    start_time=start_time,
                    success=True,
                    duration_ms=duration_ms,
                    details={"bars_count": len(agg)}
                )
                return agg
            else:
                DataFetchLogger.log_attempt(
                    source="akshare:intraday_fallback",
                    symbol=symbol,
                    start_time=start_time,
                    success=False,
                    duration_ms=duration_ms,
                    error="缺少必要列"
                )
        else:
            DataFetchLogger.log_attempt(
                source="akshare:intraday_fallback",
                symbol=symbol,
                start_time=start_time,
                success=False,
                duration_ms=duration_ms,
                error="返回空数据"
            )
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        DataFetchLogger.log_attempt(
            source="akshare:intraday_fallback",
            symbol=symbol,
            start_time=start_time,
            success=False,
            duration_ms=duration_ms,
            error=str(exc)
        )
    
    return None


def _cn_ohlcv_yfinance(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """A-share OHLCV via yfinance (last resort for CN stocks)."""
    if yf is None:
        DataFetchLogger.log_attempt(
            source="yfinance",
            symbol=symbol,
            start_time=time.time(),
            success=False,
            duration_ms=0,
            error="yfinance 未安装"
        )
        return None
    
    ticker_str = to_yfinance_ticker(symbol, "cn")
    start_time = time.time()
    
    try:
        df = _us_ohlcv(ticker_str, start_date, end_date)
        duration_ms = (time.time() - start_time) * 1000
        
        if df is not None and not df.empty:
            DataFetchLogger.log_attempt(
                source="yfinance:cn_fallback",
                symbol=ticker_str,
                start_time=start_time,
                success=True,
                duration_ms=duration_ms,
                details={"bars_count": len(df)}
            )
            return df
        else:
            DataFetchLogger.log_attempt(
                source="yfinance:cn_fallback",
                symbol=ticker_str,
                start_time=start_time,
                success=False,
                duration_ms=duration_ms,
                error="返回空数据"
            )
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        DataFetchLogger.log_attempt(
            source="yfinance:cn_fallback",
            symbol=ticker_str,
            start_time=start_time,
            success=False,
            duration_ms=duration_ms,
            error=str(exc)
        )
    return None


# ═══════════════════════════════════════════════════════════════════════
# Technical indicators — pure pandas/numpy (same for both markets)
# ═══════════════════════════════════════════════════════════════════════

def compute_indicators(df: pd.DataFrame) -> dict:
    """Compute 13 common technical indicators from OHLCV data."""
    if df is None or df.empty or "close" not in df.columns:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0, index=df.index)

    result: dict[str, Optional[float]] = {}

    # Moving averages
    for window in (5, 10, 20, 60):
        key = f"close_{window}_sma"
        result[key] = round(float(close.rolling(window).mean().iloc[-1]), 4) if len(close) >= window else None

    # EMA 10
    result["close_10_ema"] = round(float(close.ewm(span=10, adjust=False).mean().iloc[-1]), 4) if len(close) >= 10 else None

    # MACD (12, 26, 9)
    if len(close) >= 26:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        result["macd"] = round(float(dif.iloc[-1]), 4)
        result["macds"] = round(float(dea.iloc[-1]), 4)
        result["macdh"] = round(float(2 * (dif - dea).iloc[-1]), 4)
    else:
        result["macd"] = result["macds"] = result["macdh"] = None

    # RSI (14)
    if len(close) >= 15:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        for i in range(14, len(avg_gain)):
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * 13 + gain.iloc[i]) / 14
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * 13 + loss.iloc[i]) / 14
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        result["rsi_14"] = round(float(rsi.iloc[-1]), 4) if not pd.isna(rsi.iloc[-1]) else None
    else:
        result["rsi_14"] = None

    # Bollinger Bands (20, 2)
    if len(close) >= 20:
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        result["boll"] = round(float(sma20.iloc[-1]), 4)
        result["boll_ub"] = round(float(sma20.iloc[-1] + 2 * std20.iloc[-1]), 4)
        result["boll_lb"] = round(float(sma20.iloc[-1] - 2 * std20.iloc[-1]), 4)
    else:
        result["boll"] = result["boll_ub"] = result["boll_lb"] = None

    # KDJ (9, 3, 3)
    if len(close) >= 9:
        low_9 = low.rolling(9).min()
        high_9 = high.rolling(9).max()
        rsv = ((close - low_9) / (high_9 - low_9).replace(0, np.nan)) * 100
        k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
        d = k.ewm(alpha=1 / 3, adjust=False).mean()
        result["kdjk"] = round(float(k.iloc[-1]), 4) if not pd.isna(k.iloc[-1]) else None
        result["kdjd"] = round(float(d.iloc[-1]), 4) if not pd.isna(d.iloc[-1]) else None
        result["kdjj"] = round(float(3 * k.iloc[-1] - 2 * d.iloc[-1]), 4) if not pd.isna(k.iloc[-1]) else None
    else:
        result["kdjk"] = result["kdjd"] = result["kdjj"] = None

    # VWMA (20)
    if len(close) >= 20 and volume.sum() > 0:
        typical_price = (high + low + close) / 3
        vwma = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()
        result["vwma"] = round(float(vwma.iloc[-1]), 4) if not pd.isna(vwma.iloc[-1]) else None
    else:
        result["vwma"] = None

    # MFI (14)
    if len(close) >= 15 and volume.sum() > 0:
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        pos_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        neg_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        pos_sum = pos_flow.rolling(14).sum()
        neg_sum = neg_flow.rolling(14).sum()
        mfi = 100 - (100 / (1 + pos_sum / neg_sum.replace(0, np.nan)))
        result["mfi"] = round(float(mfi.iloc[-1]), 4) if not pd.isna(mfi.iloc[-1]) else None
    else:
        result["mfi"] = None

    # ATR (14)
    if len(close) >= 15:
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        for i in range(14, len(atr)):
            atr.iloc[i] = (atr.iloc[i - 1] * 13 + tr.iloc[i]) / 14
        result["atr"] = round(float(atr.iloc[-1]), 4) if not pd.isna(atr.iloc[-1]) else None
    else:
        result["atr"] = None

    return result


# ═══════════════════════════════════════════════════════════════════════
# Summary formatters
# ═══════════════════════════════════════════════════════════════════════

INDICATOR_LABELS_CN = {
    "close_5_sma": "5日均线(MA5)",
    "close_10_sma": "10日均线(MA10)",
    "close_20_sma": "20日均线(MA20)",
    "close_60_sma": "60日均线(MA60)",
    "close_10_ema": "10日指数均线(EMA10)",
    "macd": "MACD(DIF)",
    "macds": "MACD信号线(DEA)",
    "macdh": "MACD柱",
    "rsi_14": "相对强弱指标(RSI14)",
    "boll": "布林带中轨(BOLL)",
    "boll_ub": "布林带上轨",
    "boll_lb": "布林带下轨",
    "kdjk": "KDJ-K值",
    "kdjd": "KDJ-D值",
    "kdjj": "KDJ-J值",
    "vwma": "成交量加权均线(VWMA)",
    "mfi": "资金流量指标(MFI)",
    "atr": "平均真实波幅(ATR)",
}


def format_ohlcv_summary(df: Optional[pd.DataFrame]) -> str:
    """Format OHLCV DataFrame as a Chinese summary string."""
    if df is None or df.empty:
        return "### 行情概览\n无行情数据（可能为非交易日或数据源暂不可用）"

    try:
        latest = df.iloc[-1]
        first = df.iloc[0]
        period_high = float(df["high"].max())
        period_low = float(df["low"].min())

        if float(first["close"]) != 0:
            period_return = (float(latest["close"]) - float(first["close"])) / float(first["close"]) * 100
        else:
            period_return = 0.0

        avg_vol = float(df["volume"].mean()) if "volume" in df.columns else 0

        lines = [
            "### 行情概览",
            f"- 数据起始: {df.iloc[0]['date']}  →  {df.iloc[-1]['date']}（共 {len(df)} 个交易日）",
            f"- 最新收盘价: {latest.get('close', 'N/A')}",
            f"- 期间最高价: {period_high}",
            f"- 期间最低价: {period_low}",
            f"- 期间涨跌幅: {period_return:+.2f}%",
            f"- 日均成交量: {avg_vol:,.0f}",
        ]
        return "\n".join(lines)
    except Exception as exc:
        return f"### 行情概览\n数据处理异常: {exc}"


def get_stock_quote(symbol: str) -> Optional[dict]:
    """Get real-time A-share stock quote via pytdx."""
    if not _TDX_AVAILABLE:
        return None
    market = _tdx_market(symbol)
    for host, port in _TDX_SERVERS:
        api = TdxHq_API()
        try:
            api.connect(host, port, time_out=5)
            quotes = api.get_security_quotes([(market, symbol)])
            api.disconnect()
            if quotes:
                q = quotes[0]
                price = float(q["price"])
                last_close = float(q["last_close"])
                change_pct = ((price - last_close) / last_close * 100) if last_close else 0.0
                return {
                    "price": price,
                    "open": float(q["open"]),
                    "high": float(q["high"]),
                    "low": float(q["low"]),
                    "last_close": last_close,
                    "change_pct": round(change_pct, 2),
                    "volume": int(q["vol"]),
                    "amount": float(q["amount"]),
                    "bid": float(q["bid1"]),
                    "ask": float(q["ask1"]),
                }
        except Exception:
            try:
                api.disconnect()
            except Exception:
                pass
    return None


def ohlcv_to_json(df: Optional[pd.DataFrame]) -> list[dict]:
    """Convert OHLCV DataFrame to JSON-serializable list for chart rendering."""
    if df is None or df.empty:
        return []
    rows = []
    for _, row in df.iterrows():
        entry = {}
        for col in ["date", "open", "high", "low", "close", "volume"]:
            val = row.get(col)
            if isinstance(val, (np.integer,)):
                val = int(val)
            elif isinstance(val, (np.floating,)):
                val = float(val)
            entry[col] = val
        rows.append(entry)
    return rows


def format_indicators_summary(indicators: dict) -> str:
    """Format technical indicators as a Chinese summary string."""
    if not indicators:
        return "### 技术指标\n数据不足，无法计算技术指标"

    lines = ["### 技术指标"]
    for key, label in INDICATOR_LABELS_CN.items():
        val = indicators.get(key)
        if val is not None:
            lines.append(f"- {label}: {val}")
        else:
            lines.append(f"- {label}: N/A（数据不足）")
    return "\n".join(lines)
