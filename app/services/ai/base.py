from typing import Protocol
from dataclasses import dataclass


class AIProviderError(Exception):
    """Base error for AI provider failures."""


class AIProviderConfigurationError(AIProviderError):
    """Raised when the selected AI provider is not configured correctly."""


class AIProvider(Protocol):
    """Common interface for chat-capable AI providers."""

    @property
    def model_name(self) -> str:
        """Return the concrete model name used for this provider."""

    async def chat(self, system: str, user: str) -> str:
        """Return one assistant response for a system instruction and user prompt."""


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
