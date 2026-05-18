"""State definitions for the simplified LangGraph trading agent graph."""

from typing import Annotated, Any
from typing_extensions import TypedDict


class DebateState(TypedDict, total=False):
    """State for the bull/bear debate loop."""
    bull_history: str
    bear_history: str
    history: str
    current_response: str
    current_speaker: str       # "bull" or "bear"
    judge_decision: str
    count: int


class AgentState(TypedDict, total=False):
    """Top-level state for the trading agent graph."""
    symbol: str
    trade_date: str

    # ── Data collection outputs (one per section) ──
    valuation_report: str      # 估值分析
    technical_report: str      # 技术面分析
    fundamental_report: str    # 基本面分析
    sentiment_report: str      # 市场情绪分析
    news_report: str           # 新闻资讯
    research_summary: str      # 总体摘要

    # Backward-compat combined report (debate agents read this)
    research_report: str
    data_collected: bool

    # Raw data (for the frontend to show data-fetch progress)
    raw_ohlcv_text: str
    raw_indicators_text: str
    raw_financial_text: str
    raw_news_text: str
    raw_sentiment_text: str

    debate_state: DebateState
    final_decision: str
    messages: Annotated[list, lambda x, y: (x or []) + (y or [])]


def create_initial_state(symbol: str, trade_date: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "valuation_report": "",
        "technical_report": "",
        "fundamental_report": "",
        "sentiment_report": "",
        "news_report": "",
        "research_summary": "",
        "research_report": "",
        "data_collected": False,
        "raw_ohlcv_text": "",
        "raw_indicators_text": "",
        "raw_financial_text": "",
        "raw_news_text": "",
        "raw_sentiment_text": "",
        "debate_state": DebateState(
            bull_history="",
            bear_history="",
            history="",
            current_response="",
            current_speaker="bull",
            judge_decision="",
            count=0,
        ),
        "final_decision": "",
        "messages": [],
    }
