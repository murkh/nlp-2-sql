"""
Anthropic LLM provider implementation.

Wraps the Anthropic Python SDK for Claude models, mapping the
unified LLMProvider interface to Anthropic's messages API.
"""

import json

from llm.base import LLMProvider
from config import settings


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        # Lazy import — don't fail if anthropic isn't needed
        import anthropic

        self._model = model or settings.ANTHROPIC_MODEL
        self._client = anthropic.Anthropic(
            api_key=api_key or settings.ANTHROPIC_API_KEY
        )

    def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        # Anthropic separates system from messages
        system_text, user_messages = self._split_system(messages)

        response = self._client.messages.create(
            model=self._model,
            system=system_text,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text

    def chat_completion_json(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict:
        json_instruction = (
            "\n\nYou MUST respond with valid JSON only. "
            "Do not include markdown code fences or any other text."
        )
        system_text, user_messages = self._split_system(messages)
        system_text += json_instruction

        response = self._client.messages.create(
            model=self._model,
            system=system_text,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = response.content[0].text
        return json.loads(raw)

    def get_provider_name(self) -> str:
        return f"anthropic/{self._model}"

    @staticmethod
    def _split_system(
        messages: list[dict],
    ) -> tuple[str, list[dict]]:
        """
        Separate system messages from user/assistant messages.

        Anthropic's API takes system as a separate parameter.
        """
        system_parts = []
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                user_messages.append(
                    {"role": msg["role"], "content": msg["content"]}
                )

        return "\n\n".join(system_parts), user_messages
