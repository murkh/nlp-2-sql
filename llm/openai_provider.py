"""
OpenAI LLM provider implementation.

Wraps the OpenAI Python SDK for chat completions, supporting both
free-form text and JSON-structured responses.
"""

import json
import openai

from llm.base import LLMProvider
from config import settings


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider (gpt-4o-mini, gpt-4o, etc.)."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self._model = model or settings.OPENAI_MODEL
        self._client = openai.OpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def chat_completion_json(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict:
        # Inject JSON instruction into system message if not present
        json_instruction = (
            "You MUST respond with valid JSON only. "
            "Do not include markdown code fences or any other text."
        )
        enriched = list(messages)
        if enriched and enriched[0]["role"] == "system":
            enriched[0] = {
                **enriched[0],
                "content": enriched[0]["content"] + "\n\n" + json_instruction,
            }
        else:
            enriched.insert(0, {"role": "system", "content": json_instruction})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=enriched,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)

    def get_provider_name(self) -> str:
        return f"openai/{self._model}"
