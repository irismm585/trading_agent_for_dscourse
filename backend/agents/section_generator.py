"""On-demand section generator — replaces the monolithic DataCollector.

Each section is generated independently when the user requests it.
The data bundle is fetched once and cached, then individual sections
use the relevant parts of the data for their LLM prompts.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.data_layer.unified_data import fetch_all_data

# ── Section definitions ─────────────────────────────────────────────

SECTION_PROMPTS: dict[str, dict] = {
    "valuation": {
        "title_cn": "估值分析",
        "prompt_template": """你是一位专业的股票估值分析师。请根据以下数据撰写一份中文估值分析报告。

**股票代码**: {symbol}
**分析日期**: {trade_date}

---
{financial_text}
{ohlcv_text}
---

请严格按照以下结构撰写（以 `## 估值分析` 开头）：

## 估值分析
1. **估值水平**: 根据PE、PB、市值等指标评估当前估值
2. **历史分位**: 分析估值的历史分位和同业比较（如数据可用）
3. **估值总结**: 用1-2句话总结估值结论。报告应客观中立，不给出买卖建议。""",
    },
    "technical": {
        "title_cn": "技术面分析",
        "prompt_template": """你是一位专业的技术面分析师。请根据以下数据撰写一份中文技术面分析报告。

**股票代码**: {symbol}
**分析日期**: {trade_date}

---
{ohlcv_text}
{indicators_text}
---

请严格按照以下结构撰写（以 `## 技术面分析` 开头）：

## 技术面分析
1. **趋势分析**: 根据均线排列（MA5/MA10/MA20/MA60）判断当前趋势
2. **技术指标**: 分析MACD、RSI、KDJ、布林带等指标的含义
3. **关键价位**: 识别支撑位和阻力位
4. **技术总结**: 用1-2句话总结技术面结论。报告应客观中立，不给出买卖建议。""",
    },
    "fundamental": {
        "title_cn": "基本面分析",
        "prompt_template": """你是一位专业的基本面分析师。请根据以下数据撰写一份中文基本面分析报告。

**股票代码**: {symbol}
**分析日期**: {trade_date}

---
{financial_text}
---

请严格按照以下结构撰写（以 `## 基本面分析` 开头）：

## 基本面分析
1. **盈利能力**: 分析营收、净利润、毛利率、ROE等指标
2. **财务健康度**: 分析负债权益比、流动比率等
3. **成长性**: 分析营收和盈利增长趋势
4. **基本面总结**: 用1-2句话总结基本面结论。报告应客观中立，不给出买卖建议。""",
    },
    "sentiment": {
        "title_cn": "市场情绪分析",
        "prompt_template": """你是一位专业的市场情绪分析师。请根据以下数据撰写一份中文市场情绪分析报告。

**股票代码**: {symbol}
**分析日期**: {trade_date}

---
{sentiment_text}
{news_text}
{search_text}
---

请严格按照以下结构撰写（以 `## 市场情绪分析` 开头）：

## 市场情绪分析
1. **社交媒体情绪**: 分析社交媒体讨论热度和情绪倾向
2. **新闻情绪**: 分析近期新闻对股价的影响
3. **市场关注焦点**: 总结当前市场对该股的核心关注点
4. **情绪总结**: 用1-2句话总结情绪面结论。报告应客观中立，不给出买卖建议。""",
    },
    "news": {
        "title_cn": "新闻资讯",
        "prompt_template": """你是一位专业的财经新闻分析师。请根据以下数据撰写一份中文新闻资讯分析报告。

**股票代码**: {symbol}
**分析日期**: {trade_date}

---
{news_text}
{search_text}
---

请严格按照以下结构撰写（以 `## 新闻资讯` 开头）：

## 新闻资讯
1. **重要新闻**: 列出并分析影响股价的重要新闻事件
2. **行业动态**: 分析相关行业和市场动态
3. **政策影响**: 分析宏观政策和监管动态的影响（如适用）
4. **新闻总结**: 用1-2句话总结新闻面核心信息。报告应客观中立，不给出买卖建议。""",
    },
    "summary": {
        "title_cn": "总体摘要",
        "prompt_template": """你是一位专业的投资研究摘要员。请根据以下所有数据，撰写一份中文总体分析摘要。

**股票代码**: {symbol}
**分析日期**: {trade_date}

---
{ohlcv_text}
{indicators_text}
{financial_text}
{news_text}
{sentiment_text}
{search_text}
---

请撰写一份2-3句话的总体摘要，总结核心发现。报告应客观中立，不给出买卖建议。""",
    },
}


def _build_prompt(section_key: str, symbol: str, trade_date: str, data_bundle: dict) -> Optional[str]:
    """Build an LLM prompt for a specific section."""
    section_def = SECTION_PROMPTS.get(section_key)
    if not section_def:
        return None

    template = section_def["prompt_template"]

    def _fmt(key: str, fallback: str = "") -> str:
        val = data_bundle.get(key, "")
        return val if val else fallback

    return template.format(
        symbol=symbol,
        trade_date=trade_date,
        ohlcv_text=_fmt("ohlcv_text"),
        indicators_text=_fmt("indicators_text"),
        financial_text=_fmt("financial_text"),
        news_text=_fmt("news_text", "暂无相关新闻数据"),
        sentiment_text=_fmt("sentiment_text", "暂无市场情绪数据"),
        search_text=_fmt("search_text", ""),
    )


# ── Section generator function ──────────────────────────────────────

async def generate_section(
    section: str,
    symbol: str,
    trade_date: str,
    market: str,
    llm: Any,
    data_bundle: Optional[dict] = None,
) -> str:
    """Generate a single section of the research report.

    Args:
        section: One of "valuation", "technical", "fundamental", "sentiment", "news", "summary"
        symbol: Stock ticker symbol
        trade_date: Analysis date
        market: "cn" or "us"
        llm: LangChain LLM instance
        data_bundle: Pre-fetched data (fetched if None)

    Returns:
        The generated section text (markdown).
    """
    # Fetch data if not provided
    if data_bundle is None:
        data_bundle = fetch_all_data(symbol, trade_date, market)

    prompt = _build_prompt(section, symbol, trade_date, data_bundle)
    if prompt is None:
        return f"Error: Unknown section '{section}'"

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip()
    except Exception as e:
        return f"生成失败: {str(e)}"


def get_raw_data_texts(symbol: str, trade_date: str, market: str) -> dict:
    """Get raw data texts without LLM generation (for frontend raw data tabs).

    Returns dict mapping section keys to formatted text strings.
    """
    data = fetch_all_data(symbol, trade_date, market)
    return {
        "raw_ohlcv_text": data["ohlcv_text"],
        "raw_indicators_text": data["indicators_text"],
        "raw_financial_text": data["financial_text"],
        "raw_news_text": data["news_text"],
        "raw_sentiment_text": data["sentiment_text"],
        # Also include the data bundle for later section generation
        "_data_bundle": data,
    }
