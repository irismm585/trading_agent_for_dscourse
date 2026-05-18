"""Fundamental financial data.

A-shares → akshare (Eastmoney) — stable, free, Chinese-language
US stocks → yfinance — reliable for US markets
"""

import time
from typing import Optional

import pandas as pd

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
# A-share (akshare)
# ═══════════════════════════════════════════════════════════════════════

def _ak_retry(fn, max_attempts: int = 3):
    """Retry akshare call with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"[fundamental] retry {attempt+1}/{max_attempts}: {e}")
                time.sleep(1.5 ** attempt)
            else:
                raise
    return None


def _cn_financial(symbol: str) -> dict:
    """Get A-share financial data via akshare, fallback to yfinance."""
    result = {"info": None, "income": None, "balance": None, "cashflow": None}

    if ak is not None:
        # Valuation indicators
        try:
            info_df = _ak_retry(lambda: ak.stock_individual_info_em(symbol=symbol))
            if info_df is not None and not info_df.empty:
                info_dict = dict(zip(info_df.iloc[:, 0], info_df.iloc[:, 1]))
                key_items = [
                    "总市值", "流通市值", "市盈率-动态", "市净率",
                    "净利润", "营业收入", "每股收益", "每股净资产",
                    "净资产收益率", "毛利率",
                ]
                filtered = {k: info_dict[k] for k in key_items if k in info_dict}
                result["info"] = filtered
        except Exception as e:
            print(f"[fundamental] akshare info error for {symbol}: {e}")

        # Income statement
        try:
            income_df = _ak_retry(lambda: ak.stock_profit_sheet_by_report_em(symbol=symbol))
            if income_df is not None and not income_df.empty:
                result["income"] = income_df.head(5)
        except Exception as e:
            print(f"[fundamental] akshare income error for {symbol}: {e}")

        # Balance sheet
        try:
            balance_df = _ak_retry(lambda: ak.stock_balance_sheet_by_report_em(symbol=symbol))
            if balance_df is not None and not balance_df.empty:
                result["balance"] = balance_df.head(5)
        except Exception as e:
            print(f"[fundamental] akshare balance error for {symbol}: {e}")

        # Cash flow
        try:
            cf_df = _ak_retry(lambda: ak.stock_cash_flow_sheet_by_report_em(symbol=symbol))
            if cf_df is not None and not cf_df.empty:
                result["cashflow"] = cf_df.head(5)
        except Exception as e:
            print(f"[fundamental] akshare cashflow error for {symbol}: {e}")

    # yfinance fallback
    if all(v is None or (isinstance(v, pd.DataFrame) and v.empty) for v in result.values()) and yf is not None:
        try:
            ticker_str = to_yfinance_ticker(symbol, "cn")
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            if info:
                key_items = {
                    "longName": "公司名称", "marketCap": "总市值",
                    "trailingPE": "市盈率-动态", "priceToBook": "市净率",
                    "trailingEps": "每股收益", "returnOnEquity": "净资产收益率",
                    "grossMargins": "毛利率", "totalRevenue": "营业收入",
                    "profitMargins": "净利润率",
                }
                filtered = {}
                for en_key, cn_label in key_items.items():
                    val = info.get(en_key)
                    if val is not None:
                        filtered[cn_label] = val
                result["info"] = filtered

            for name, method in [
                ("income", lambda t: t.quarterly_income_stmt),
                ("balance", lambda t: t.quarterly_balance_sheet),
                ("cashflow", lambda t: t.quarterly_cashflow),
            ]:
                try:
                    df = method(ticker)
                    if df is not None and not df.empty:
                        result[name] = df
                except Exception:
                    pass
            print(f"[fundamental] yfinance fallback succeeded for {ticker_str}")
        except Exception as e:
            print(f"[fundamental] yfinance fallback error for {symbol}: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════
# US stock (yfinance)
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


def _us_financial(symbol: str) -> dict:
    """Get US stock financial data via yfinance."""
    if yf is None:
        raise ImportError("yfinance is required. Install with: pip install yfinance")

    ticker_str = to_yfinance_ticker(symbol, "us")
    result = {"info": None, "income": None, "balance": None, "cashflow": None}

    try:
        ticker = yf.Ticker(ticker_str)

        # Valuation indicators
        try:
            info = _yf_retry(lambda: ticker.info)
            if info:
                key_items = {
                    "longName": "公司名称",
                    "sector": "行业板块",
                    "industry": "细分行业",
                    "marketCap": "总市值",
                    "trailingPE": "市盈率(TTM)",
                    "forwardPE": "远期市盈率",
                    "priceToBook": "市净率",
                    "trailingEps": "每股收益(TTM)",
                    "returnOnEquity": "净资产收益率(ROE)",
                    "returnOnAssets": "总资产收益率(ROA)",
                    "debtToEquity": "负债权益比",
                    "profitMargins": "净利润率",
                    "grossMargins": "毛利率",
                    "revenueGrowth": "营收增长率",
                    "totalRevenue": "总营收",
                    "freeCashflow": "自由现金流",
                    "beta": "Beta系数",
                    "dividendYield": "股息率",
                }
                filtered = {}
                for en_key, cn_label in key_items.items():
                    val = info.get(en_key)
                    if val is not None:
                        filtered[cn_label] = val
                result["info"] = filtered
        except Exception as e:
            print(f"[fundamental] yfinance info error for {ticker_str}: {e}")

        # Financial statements
        for name, method in [
            ("income", lambda t: t.quarterly_income_stmt),
            ("balance", lambda t: t.quarterly_balance_sheet),
            ("cashflow", lambda t: t.quarterly_cashflow),
        ]:
            try:
                df = _yf_retry(lambda: method(ticker))
                if df is not None and not df.empty:
                    result[name] = df
            except Exception:
                pass

    except Exception as e:
        print(f"[fundamental] yfinance error for {ticker_str}: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def get_financial_data(symbol: str, market: str = "cn") -> dict:
    """Get fundamental data — akshare for CN, yfinance for US."""
    if is_cn_market(symbol, market):
        return _cn_financial(symbol)
    else:
        return _us_financial(symbol)


def format_financial_summary(data: dict) -> str:
    """Format financial data as a Chinese summary string."""
    lines = ["### 财务数据"]

    # Valuation info
    info = data.get("info")
    if info:
        lines.append("#### 估值指标")
        for label, value in info.items():
            if isinstance(value, float):
                if any(kw in label for kw in ("市值", "营收", "EBITDA", "现金流")):
                    if abs(value) > 1e8:
                        lines.append(f"- {label}: {value/1e8:.2f}亿")
                    elif abs(value) > 1e4:
                        lines.append(f"- {label}: {value/1e4:.2f}万")
                    else:
                        lines.append(f"- {label}: {value:.2f}")
                else:
                    lines.append(f"- {label}: {value:.4f}")
            else:
                lines.append(f"- {label}: {value}")

    # Financial statements
    for section_name, section_label in [
        ("income", "利润表（近几期）"),
        ("balance", "资产负债表（近几期）"),
        ("cashflow", "现金流量表（近几期）"),
    ]:
        df = data.get(section_name)
        if df is not None and not df.empty:
            lines.append("")
            lines.append(f"#### {section_label}")
            lines.append("```")
            lines.append(df.to_string(max_rows=8))
            lines.append("```")

    return "\n".join(lines)
