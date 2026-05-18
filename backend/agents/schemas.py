"""Simplified Pydantic schemas for the 3-role A-share trading agent system.

Only the Judge agent uses structured output (DebateAgents do free-text).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


class FinalRating(str, Enum):
    """3-tier rating used by the Judge agent."""
    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


class FinalDecision(BaseModel):
    """Structured final decision produced by the Judge agent."""

    rating: FinalRating = Field(
        description=(
            "最终评级。只能是 Buy（买入）、Hold（持有/观望）或 Sell（卖出）三者之一。"
            "只有在多空证据真正平衡时选择 Hold，否则应选择论证更强的一方。"
        ),
    )
    reasoning: str = Field(
        description=(
            "综合评判理由。总结多头和空头双方的核心论点，"
            "说明哪一方的论证更有说服力以及为什么。2-4句话。"
        ),
    )
    key_risks: str = Field(
        description=(
            "主要风险提示。列出需要关注的关键风险因素，"
            "包括政策风险、行业风险、公司特有风险等。多个风险用分号分隔。"
        ),
    )
    suggested_entry_price: Optional[float] = Field(
        default=None,
        description="可选：建议入场价格（人民币元）。",
    )
    suggested_holding_period: Optional[str] = Field(
        default=None,
        description="可选：建议持有周期，如 '短期(1-4周)'、'中期(1-3月)'、'长期(3-6月)'。",
    )

    @field_validator("key_risks", mode="before")
    @classmethod
    def coerce_key_risks(cls, v):
        """Allow LLM to send key_risks as either string or list of strings."""
        if isinstance(v, list):
            return "; ".join(str(item) for item in v)
        return v


def render_final_decision(decision: FinalDecision) -> str:
    """Render a FinalDecision to markdown."""
    rating_cn = {
        "Buy": "买入",
        "Hold": "持有/观望",
        "Sell": "卖出",
    }
    parts = [
        f"**最终评级**: {decision.rating.value}（{rating_cn.get(decision.rating.value, decision.rating.value)}）",
        "",
        f"**评判理由**: {decision.reasoning}",
        "",
        f"**风险提示**: {decision.key_risks}",
    ]
    if decision.suggested_entry_price is not None:
        parts.extend(["", f"**建议入场价**: ¥{decision.suggested_entry_price:.2f}"])
    if decision.suggested_holding_period:
        parts.extend(["", f"**建议持有周期**: {decision.suggested_holding_period}"])
    return "\n".join(parts)
