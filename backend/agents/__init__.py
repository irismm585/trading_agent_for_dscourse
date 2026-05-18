"""Agent factory functions for the simplified 3-role trading system."""

from .bull_agent import create_bull_agent
from .bear_agent import create_bear_agent
from .judge_agent import create_judge_agent

__all__ = [
    "create_bull_agent",
    "create_bear_agent",
    "create_judge_agent",
]
