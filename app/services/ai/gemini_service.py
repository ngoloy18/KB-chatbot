import asyncio
from collections.abc import Callable
from typing import Any

from app.services.ai.base import (
    AIProviderConfigurationError,
    AIProviderError,
    EmbeddingDocument,
)


class GeminiService:
    """Google Gemini implementation of the common AI provider interface."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise AIProviderConfigurationError("GEMINI_API_KEY is not configured.")
        if not model:
            raise AIProviderConfigurationError("GEMINI_MODEL is not configured.")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIProviderConfigurationError(
                "google-genai is not installed. Run pip install -r requirements.txt."
            ) from exc

        self._model = model
        self._client = genai.Client(api_key=api_key)
        self._config_factory: Callable[..., Any] = types.GenerateContentConfig

    @property
    def model_name(self) -> str:
        """Return the configured Gemini model name."""

        return self._model

    async def chat(self, system: str, user: str) -> str:
        """Send one prompt to Gemini and return the text response."""

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self._model,
                contents=user,
                config=self._config_factory(system_instruction=system),
            )
        except Exception as exc:
            raise AIProviderError(f"Gemini request failed: {exc}") from exc
        return (response.text or "").strip()


class GeminiEmbeddingService:
    """Google Gemini implementation of the embedding provider interface."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise AIProviderConfigurationError("GEMINI_API_KEY is not configured.")
        if not model:
            raise AIProviderConfigurationError(
                "GEMINI_EMBEDDING_MODEL is not configured."
            )

        try:
            from google import genai
        except ImportError as exc:
            raise AIProviderConfigurationError(
                "google-genai is not installed. Run pip install -r requirements.txt."
            ) from exc

        self._model = model
        self._client = genai.Client(api_key=api_key)

    @property
    def provider_name(self) -> str:
        """Return the provider label stored with chunk embeddings."""

        return "gemini"

    @property
    def model_name(self) -> str:
        """Return the configured Gemini embedding model name."""

        return self._model

    async def embed_query(self, query: str) -> list[float]:
        """Embed one user query using Gemini retrieval formatting."""

        return await self._embed(self._format_query(query))

    async def embed_documents(
        self,
        documents: list[EmbeddingDocument],
    ) -> list[list[float]]:
        """Embed document chunks using Gemini retrieval formatting."""

        embeddings: list[list[float]] = []
        for document in documents:
            embeddings.append(
                await self._embed(
                    self._format_document(
                        title=document.title,
                        content=document.content,
                    )
                )
            )
        return embeddings

    async def _embed(self, content: str) -> list[float]:
        """Send one embedding request and return the vector values."""

        try:
            response = await asyncio.to_thread(
                self._client.models.embed_content,
                model=self._model,
                contents=content,
            )
        except Exception as exc:
            raise AIProviderError(f"Gemini embedding request failed: {exc}") from exc

        if not response.embeddings:
            raise AIProviderError("Gemini embedding response did not include embeddings.")
        values = response.embeddings[0].values
        if not values:
            raise AIProviderError("Gemini embedding response did not include values.")
        return [float(value) for value in values]

    @staticmethod
    def _format_query(query: str) -> str:
        """Format a question for asymmetric retrieval embeddings."""

        return f"task: question answering | query: {query.strip()}"

    @staticmethod
    def _format_document(title: str, content: str) -> str:
        """Format a chunk for asymmetric retrieval embeddings."""

        return f"title: {title.strip() or 'none'} | text: {content.strip()}"
