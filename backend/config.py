"""Shared configuration for the A-Share Trading Agents backend."""

from __future__ import annotations

import os
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    # LLM settings
    "llm_provider": "deepseek",
    "deep_think_llm": "deepseek-v4-pro",
    "quick_think_llm": "deepseek-v4-flash",
    "backend_url": None,

    # Agent settings
    "max_debate_rounds": 1,
    "output_language": "Chinese",

    # Output settings
    "report_dir": "./reports",
}


def _coerce(value_str: str, default: Any) -> Any:
    """Coerce a string env-var value to match the type of the default."""
    if isinstance(default, bool):
        return value_str.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(default, int):
        return int(value_str)
    if isinstance(default, float):
        return float(value_str)
    return value_str


def load_config() -> dict[str, Any]:
    """Load config from defaults, overlaid with TRADINGAGENTS_* environment variables."""
    config = DEFAULT_CONFIG.copy()

    env_overrides = {
        "llm_provider": "TRADINGAGENTS_LLM_PROVIDER",
        "deep_think_llm": "TRADINGAGENTS_DEEP_THINK_LLM",
        "quick_think_llm": "TRADINGAGENTS_QUICK_THINK_LLM",
        "backend_url": "TRADINGAGENTS_LLM_BACKEND_URL",
        "max_debate_rounds": "TRADINGAGENTS_MAX_DEBATE_ROUNDS",
        "output_language": "TRADINGAGENTS_OUTPUT_LANGUAGE",
    }

    for key, env_var in env_overrides.items():
        if env_var in os.environ:
            config[key] = _coerce(os.environ[env_var], config[key])

    return config


def get_config() -> dict[str, Any]:
    """Get the current config (loads on first call, cached thereafter)."""
    if not hasattr(get_config, "_cache"):
        get_config._cache = load_config()  # type: ignore[attr-defined]
    return get_config._cache  # type: ignore[attr-defined]
