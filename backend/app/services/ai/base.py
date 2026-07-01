from dataclasses import dataclass
from typing import Protocol


class AIProviderError(Exception):
    """Base error for AI provider failures."""


class AIProviderConfigurationError(AIProviderError):
    """Raised when the selected AI provider is not configured correctly."""


@dataclass(frozen=True)
class AIResponse:
    """Normalized chat response plus provider usage metadata when available."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AIProvider(Protocol):
    """Common interface for chat-capable AI providers."""

    @property
    def model_name(self) -> str:
        """Return the concrete model name used for this provider."""

    async def chat(self, system: str, user: str) -> str:
        """Return one assistant response for a system instruction and user prompt."""

    async def chat_with_usage(self, system: str, user: str) -> AIResponse:
        """Return one assistant response with token usage when the provider exposes it."""


async def call_chat_with_usage(
    provider: AIProvider,
    system: str,
    user: str,
) -> AIResponse:
    """Call a provider with usage metadata when available, otherwise plain text."""

    chat_with_usage = getattr(provider, "chat_with_usage", None)
    if callable(chat_with_usage):
        return await chat_with_usage(system=system, user=user)
    answer = await provider.chat(system=system, user=user)
    return AIResponse(text=answer)


@dataclass(frozen=True)
class EmbeddingDocument:
    """Text chunk metadata used to generate retrieval document embeddings."""

    title: str
    content: str


class EmbeddingProvider(Protocol):
    """Common interface for embedding-capable AI providers."""

    @property
    def provider_name(self) -> str:
        """Return the provider name used for stored embedding metadata."""

    @property
    def model_name(self) -> str:
        """Return the concrete embedding model name."""

    async def embed_query(self, query: str) -> list[float]:
        """Embed one user query for retrieval."""

    async def embed_documents(self, documents: list[EmbeddingDocument]) -> list[list[float]]:
        """Embed document chunks for retrieval."""
