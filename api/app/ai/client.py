"""Talking to the LLM. `LLMClient` is the small interface the rest of the app uses, so tests
can pass a fake one; `GroqClient` is the real implementation.
"""

from typing import Any, Final, Protocol

import groq
from groq.types.chat import ChatCompletionMessageParam
from groq.types.chat.completion_create_params import ResponseFormatResponseFormatJsonSchema

from app.core.config import get_settings
from app.models import DiagnosisError

# gpt-oss models think before answering; "medium" is a balance of quality and speed (~2-4s).
REASONING_EFFORT: Final = "medium"


class LLMError(Exception):
    """The call failed for good (after the SDK's retries). `kind` is stored with the diagnosis."""

    def __init__(self, kind: DiagnosisError, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


class LLMClient(Protocol):
    model: str

    async def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        """Return the model's raw answer (JSON text). Raise `LLMError` on failure."""
        ...


class GroqClient:
    def __init__(self, api_key: str, model: str, timeout_s: float, max_retries: int) -> None:
        self.model = model
        # The SDK retries timeouts, connection errors, 408/409/429 and 5xx by itself, with
        # exponential backoff (0.5s doubling up to 8s) and honoring Groq's `retry-after` header.
        self._client = groq.AsyncGroq(api_key=api_key, timeout=timeout_s, max_retries=max_retries)

    async def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        # Strict mode: Groq constrains generation so the output matches `schema`.
        response_format: ResponseFormatResponseFormatJsonSchema = {
            "type": "json_schema",
            "json_schema": {"name": "diagnosis", "strict": True, "schema": schema},
        }
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                reasoning_effort=REASONING_EFFORT,
            )
        except groq.APIError as error:
            raise to_llm_error(error) from error
        content: str | None = response.choices[0].message.content
        if not content:
            raise LLMError(DiagnosisError.INVALID_OUTPUT, "The model returned an empty answer")
        return content

    async def close(self) -> None:
        await self._client.close()


def to_llm_error(error: groq.APIError) -> LLMError:
    """Sort SDK errors into the few kinds we store and show."""
    # Order matters: APITimeoutError is a kind of APIConnectionError, which is an APIError.
    if isinstance(error, groq.APITimeoutError):
        return LLMError(DiagnosisError.TIMEOUT, "The AI service did not answer in time")
    if isinstance(error, groq.RateLimitError):
        return LLMError(DiagnosisError.RATE_LIMITED, "Rate limit reached at the AI service")
    if isinstance(error, groq.BadRequestError) and "schema" in error.message.lower():
        return LLMError(DiagnosisError.INVALID_OUTPUT, error.message)
    return LLMError(DiagnosisError.API_ERROR, f"{type(error).__name__}: {error.message}")


def llm_client_from_settings() -> GroqClient | None:
    """The configured client, or None when no API key is set (the feature is then off)."""
    settings = get_settings()
    key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
    if not key:
        return None
    return GroqClient(key, settings.groq_model, settings.groq_timeout_s, settings.groq_max_retries)
