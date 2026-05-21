"""
OpenAI embedding service for RAG retrieval.

Provides both a standalone embedding API and a ChromaDB-compatible
embedding function for seamless integration.
"""

import openai
import chromadb.api.types as chroma_types

from config import settings


class EmbeddingService:
    """Generates embeddings using OpenAI's text-embedding models."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ):
        self._model = model or settings.OPENAI_EMBEDDING_MODEL
        self._client = openai.OpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text string."""
        response = self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of text strings."""
        if not texts:
            return []

        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        # Sort by index to ensure order matches input
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]


class ChromaEmbeddingFunction(chroma_types.EmbeddingFunction):
    """
    ChromaDB-compatible embedding function backed by OpenAI.

    ChromaDB calls this automatically when adding documents or querying.
    """

    def __init__(self, service: EmbeddingService | None = None):
        self._service = service or EmbeddingService()

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._service.embed_batch(input)
