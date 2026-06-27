import asyncio
from collections.abc import Callable
from typing import Any

from app.services.ai.base import (
    AIResponse,
    AIProviderConfigurationError,
    AIProviderError,
    EmbeddingDocument,
)


class GeminiService:
    """Google Gemini implementation of the common AI provider interface."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        retry_delay_seconds: float,
    ) -> None:
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
        self._timeout_seconds = max(timeout_seconds, 0)
        self._max_retries = max(max_retries, 0)
        self._retry_delay_seconds = max(retry_delay_seconds, 0)

    @property
    def model_name(self) -> str:
        """Return the configured Gemini model name."""

        return self._model

    async def chat(self, system: str, user: str) -> str:
        """Send one prompt to Gemini and return the text response."""

        response = await self.chat_with_usage(system=system, user=user)
        return response.text

    async def chat_with_usage(self, system: str, user: str) -> AIResponse:
        """Send one prompt to Gemini and return text plus token usage metadata."""

        response = await _call_with_retries(
            self._client.models.generate_content,
            timeout_seconds=self._timeout_seconds,
            max_retries=self._max_retries,
            retry_delay_seconds=self._retry_delay_seconds,
            error_prefix="Gemini request failed",
            model=self._model,
            contents=user,
            config=self._config_factory(system_instruction=system),
        )
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = _get_usage_count(usage, "prompt_token_count")
        completion_tokens = _get_usage_count(usage, "candidates_token_count")
        total_tokens = _get_usage_count(usage, "total_token_count")
        if total_tokens == 0 and (prompt_tokens or completion_tokens):
            total_tokens = prompt_tokens + completion_tokens
        return AIResponse(
            text=(response.text or "").strip(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


class GeminiEmbeddingService:
    """Google Gemini implementation of the embedding provider interface."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        retry_delay_seconds: float,
    ) -> None:
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
        self._timeout_seconds = max(timeout_seconds, 0)
        self._max_retries = max(max_retries, 0)
        self._retry_delay_seconds = max(retry_delay_seconds, 0)

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

        response = await _call_with_retries(
            self._client.models.embed_content,
            timeout_seconds=self._timeout_seconds,
            max_retries=self._max_retries,
            retry_delay_seconds=self._retry_delay_seconds,
            error_prefix="Gemini embedding request failed",
            model=self._model,
            contents=content,
        )

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


async def _call_with_retries(
    operation: Callable[..., Any],
    *,
    timeout_seconds: float,
    max_retries: int,
    retry_delay_seconds: float,
    error_prefix: str,
    **kwargs: Any,
) -> Any:
    """Run a blocking provider SDK call with app-level timeout and retries."""

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            sdk_call = asyncio.to_thread(operation, **kwargs)
            if timeout_seconds > 0:
                return await asyncio.wait_for(sdk_call, timeout=timeout_seconds)
            return await sdk_call
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            if retry_delay_seconds > 0:
                await asyncio.sleep(retry_delay_seconds)

    detail = str(last_exc) if last_exc is not None else "unknown error"
    if not detail and last_exc is not None:
        detail = last_exc.__class__.__name__
    raise AIProviderError(f"{error_prefix}: {detail}") from last_exc


def _get_usage_count(usage: Any, attribute_name: str) -> int:
    """Read an integer token count from Gemini usage metadata."""

    if usage is None:
        return 0
    value = getattr(usage, attribute_name, 0) or 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
