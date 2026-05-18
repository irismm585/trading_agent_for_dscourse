"""Bull Agent (多头分析师) — builds a bullish case for A-share investment.

Adapted from the original project's bull_researcher.py.
"""

from typing import Any


def create_bull_agent(llm: Any):
    """Create the Bull agent node for the debate phase."""

    def bull_node(state: dict) -> dict:
        debate_state = state["debate_state"]
        research_report = state["research_report"]

        bear_response = debate_state.get("current_response", "")
        history = debate_state.get("history", "")

        prompt = f"""你是一位看多分析师(多头)。请基于研究报告为空头论点构建有力的看涨反驳。

**研究报告**:
{research_report}

**辩论历史**:
{history if history else "（辩论刚开始，你是第一个发言）"}

**空头最新观点**:
{bear_response if bear_response else "（空头尚未发言，请先阐述看涨的主要理由）"}

请用中文进行辩论式发言，做到：
- 强调公司的增长潜力和竞争优势（如行业地位、品牌壁垒、创新能力等）
- 引用研究报告中的**具体数据**（估值、财务、技术指标）来支撑你的论点
- 如果空头有发言，请**逐点反驳**空头论证中的逻辑漏洞或过于悲观的假设
- 采用对话式、有说服力的中文表达，而非简单罗列数据
- 控制在300-500字以内"""

        response = llm.invoke(prompt)
        argument = response.content if hasattr(response, "content") else str(response)

        new_debate_state = {
            **debate_state,
            "history": (history + "\n\n" + "**【多头分析师】**" + argument) if history else "**【多头分析师】**" + argument,
            "bull_history": debate_state.get("bull_history", "") + "\n" + argument,
            "current_response": argument,
            "current_speaker": "bear",  # Next turn: bear
            "count": debate_state.get("count", 0) + 1,
        }

        return {"debate_state": new_debate_state}

    return bull_node
