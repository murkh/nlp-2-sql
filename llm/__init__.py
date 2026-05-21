"""
LLM provider factory.

Usage:
    from llm import get_llm_provider
    llm = get_llm_provider()
    response = llm.chat_completion([{"role": "user", "content": "Hello"}])
"""

from llm.base import LLMProvider
from config import settings


def get_llm_provider() -> LLMProvider:
    """
    Create and return the configured LLM provider.

    Reads LLM_PROVIDER from settings and instantiates the matching
    provider class. Defaults to OpenAI.
    """
    provider = settings.LLM_PROVIDER

    if provider == "openai":
        from llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider == "anthropic":
        from llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Supported: openai, anthropic"
        )
