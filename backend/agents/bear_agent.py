"""Bear Agent (空头分析师) — builds a bearish case for A-share investment.

Adapted from the original project's bear_researcher.py.
"""

from typing import Any


def create_bear_agent(llm: Any):
    """Create the Bear agent node for the debate phase."""

    def bear_node(state: dict) -> dict:
        debate_state = state["debate_state"]
        research_report = state["research_report"]

        bull_response = debate_state.get("current_response", "")
        history = debate_state.get("history", "")

        prompt = f"""你是一位看空分析师(空头)。请基于研究报告对多头论点构建有力的看跌反驳。

**研究报告**:
{research_report}

**辩论历史**:
{history}

**多头最新观点**:
{bull_response}

请用中文进行辩论式发言，做到：
- 强调投资该股面临的风险和挑战（估值过高、行业竞争、政策风险、财务隐患等）
- 引用研究报告中的**具体数据**来支撑你的风险论证
- **逐点反驳**多头论证中的逻辑漏洞、过于乐观的假设或数据选择性偏差
- 采用对话式、有说服力的中文表达，而非简单罗列数据
- 控制在300-500字以内"""

        response = llm.invoke(prompt)
        argument = response.content if hasattr(response, "content") else str(response)

        new_debate_state = {
            **debate_state,
            "history": debate_state.get("history", "") + "\n\n" + "**【空头分析师】**" + argument,
            "bear_history": debate_state.get("bear_history", "") + "\n" + argument,
            "current_response": argument,
            "current_speaker": "bull",  # Next turn: bull
            "count": debate_state.get("count", 0) + 1,
        }

        return {"debate_state": new_debate_state}

    return bear_node
