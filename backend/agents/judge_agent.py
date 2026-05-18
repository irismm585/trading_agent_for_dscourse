"""Judge Agent (评委) — reviews the debate and issues the final trading decision.

Adapted from the original project's portfolio_manager.py.
Uses structured output (FinalDecision schema) for the 3-tier rating.
"""

from typing import Any

from backend.agents.schemas import FinalDecision, render_final_decision
from backend.agents.utils.structured import bind_structured, invoke_structured_or_freetext


def create_judge_agent(llm: Any):
    """Create the Judge agent node for the final decision phase.

    Uses structured output when the LLM supports it, falls back to free-text.
    """
    structured_llm = bind_structured(llm, FinalDecision, "Judge Agent")

    def judge_node(state: dict) -> dict:
        research_report = state["research_report"]
        debate_state = state["debate_state"]
        debate_history = debate_state.get("history", "")

        prompt = f"""你是一位资深的A股投资决策评委。请审阅以下材料，做出最终的投资决定。

---

**研究报告**:
{research_report}

**多空辩论完整记录**:
{debate_history}

---

**评级标准**（请选择以下三者之一）:
- **Buy（买入）**: 多头论证明显更强，看涨信心充足，建议买入或加仓
- **Hold（持有/观望）**: 多空力量基本平衡，建议维持现有仓位或暂时观望
- **Sell（卖出）**: 空头论证明显更强，风险显著大于收益，建议卖出或规避

请综合评判多头和空头双方论证的逻辑严密性、数据支撑力度和说服力。
只有在多空证据真正平衡时才选择 Hold，否则应将评级倾向于论证更强的一方。
必须引用辩论中的具体论据。

注意：所有金额以人民币元为单位。

请严格按照 JSON 格式输出，包含 rating、reasoning、key_risks 等字段。"""

        final_decision = invoke_structured_or_freetext(
            structured_llm, llm, prompt, render_final_decision, "Judge Agent"
        )

        new_debate_state = {
            **debate_state,
            "judge_decision": final_decision,
        }

        return {
            "final_decision": final_decision,
            "debate_state": new_debate_state,
        }

    return judge_node
