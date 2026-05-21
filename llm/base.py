"""
Abstract base class for LLM providers.

All LLM providers must implement this interface so the rest of the
system can swap between OpenAI, Anthropic, etc. without code changes.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Unified interface for language model providers."""

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate a text completion from a list of messages.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            temperature: Sampling temperature (0 = deterministic).
            max_tokens: Maximum tokens in the response.

        Returns:
            The assistant's response text.
        """
        ...

    @abstractmethod
    def chat_completion_json(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict:
        """
        Generate a JSON-structured completion.

        The LLM is instructed to return valid JSON. The provider handles
        parsing and returns a Python dict.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            Parsed JSON as a Python dict.
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this LLM provider (e.g., 'openai')."""
        ...
