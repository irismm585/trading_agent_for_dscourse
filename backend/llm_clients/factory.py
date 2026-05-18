from typing import Optional

from .base_client import BaseLLMClient

_OPENAI_COMPATIBLE = (
    "openai", "xai", "deepseek",
    "qwen", "qwen-cn",
    "glm", "glm-cn",
    "minimax", "minimax-cn",
    "ollama", "openrouter",
)


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.

    Provider modules are imported lazily.
    """
    provider_lower = provider.lower()

    if provider_lower in _OPENAI_COMPATIBLE:
        from .openai_client import OpenAIClient
        return OpenAIClient(model, base_url, provider=provider_lower, **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
