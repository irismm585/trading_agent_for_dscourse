"""Conditional routing logic for the debate loop and graph edges."""


class ConditionalLogic:
    """Controls debate turn ordering and termination.

    The debate loop is: Bull -> Bear -> Bull -> Bear -> ... -> Judge
    Each "round" = one Bull speech + one Bear speech = 2 turns.
    """

    def __init__(self, max_debate_rounds: int = 1):
        self.max_debate_rounds = max_debate_rounds
        self.max_turns = 2 * max_debate_rounds  # Bull + Bear per round

    def after_data_collection(self, state: dict) -> str:
        """After data collection, always route to Bull to start the debate."""
        return "BullAgent"

    def after_bull(self, state: dict) -> str:
        """After Bull speaks: if rounds exhausted → Judge, else → Bear."""
        debate = state.get("debate_state", {})
        count = debate.get("count", 0)

        if count >= self.max_turns:
            return "JudgeAgent"
        return "BearAgent"

    def after_bear(self, state: dict) -> str:
        """After Bear speaks: if rounds exhausted → Judge, else → Bull."""
        debate = state.get("debate_state", {})
        count = debate.get("count", 0)

        if count >= self.max_turns:
            return "JudgeAgent"
        return "BullAgent"
