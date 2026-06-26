from app.core.config import settings
from app.services.ai.base import AIProvider, AIProviderConfigurationError
from app.services.ai.gemini_service import GeminiService


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
