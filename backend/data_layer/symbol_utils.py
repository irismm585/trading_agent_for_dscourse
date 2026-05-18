"""Symbol conversion utilities — CN stock codes to yfinance tickers.

yfinance supports Chinese A-shares via suffixes:
    Shanghai: 600519 → 600519.SS
    Shenzhen: 000001 → 000001.SZ

US stocks are used as-is (AAPL, TSLA, etc.).
"""


def to_yfinance_ticker(symbol: str, market: str = "cn") -> str:
    """Convert a raw symbol to a yfinance-compatible ticker.

    Args:
        symbol: Raw stock code (e.g., "600519", "AAPL")
        market: "cn" (A-shares) or "us" (US stocks)

    Returns:
        yfinance ticker string
    """
    symbol = symbol.strip().upper()

    if market == "us":
        return symbol

    # A-share: add exchange suffix
    if symbol.startswith(("6", "9")):
        return f"{symbol}.SS"   # Shanghai
    else:
        return f"{symbol}.SZ"   # Shenzhen


def is_cn_market(symbol: str, market: str) -> bool:
    """Check if this is a Chinese market stock."""
    return market == "cn"
