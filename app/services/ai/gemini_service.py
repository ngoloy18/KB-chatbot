import asyncio
from collections.abc import Callable
from typing import Any

from app.services.ai.base import AIProviderConfigurationError, AIProviderError


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
