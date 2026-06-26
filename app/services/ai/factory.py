from app.core.config import settings
from app.services.ai.base import (
    AIProvider,
    AIProviderConfigurationError,
    EmbeddingProvider,
)
from app.services.ai.gemini_service import GeminiEmbeddingService, GeminiService


def create_ai_provider() -> AIProvider:
    """Build the configured AI provider."""

    if not settings.ai_provider:
        raise AIProviderConfigurationError("AI_PROVIDER is not configured.")
    if settings.ai_provider == "gemini":
        return GeminiService(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
    raise AIProviderConfigurationError(
        f"Unsupported AI_PROVIDER '{settings.ai_provider}'."
    )


def create_embedding_provider() -> EmbeddingProvider:
    """Build the configured embedding provider."""

    if not settings.embedding_provider:
        raise AIProviderConfigurationError("EMBEDDING_PROVIDER is not configured.")
    if settings.embedding_provider == "gemini":
        return GeminiEmbeddingService(
            api_key=settings.gemini_api_key,
            model=settings.gemini_embedding_model,
        )
    raise AIProviderConfigurationError(
        f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'."
    )
