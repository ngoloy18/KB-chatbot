from typing import Protocol


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
