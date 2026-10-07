import logging
import os

import httpx

from app.providers.base import ModelProvider

logger = logging.getLogger(__name__)

ACTIVITY_TYPES = [
    "find_shapes",
    "find_colors",
    "count_things",
    "listen_for_sounds",
    "texture_hunt",
    "look_up_sky",
    "find_numbers_or_letters",
    "nature_pattern_hunt",
    "gentle_movement",
]
MISSION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "missions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "minimum": 1, "maximum": 5},
                    "type": {"type": "string", "enum": ACTIVITY_TYPES},
                    "text": {"type": "string", "minLength": 1, "maxLength": 160},
                    "est_minutes": {"type": "integer", "minimum": 1, "maximum": 30},
                },
                "required": ["id", "type", "text", "est_minutes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["missions"],
    "additionalProperties": False,
}


class ProviderError(RuntimeError):
    pass


class OllamaProvider:
    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        model: str = "gemma3:4b",
        timeout_seconds: float = 300,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Ollama timeout must be greater than zero.")
        self.host = host.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str:
        request_body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": MISSION_RESPONSE_SCHEMA,
            "keep_alive": "10m",
            "options": {"temperature": 0.85, "num_predict": 384},
        }
        response = None
        for attempt in range(2):
            try:
                response = httpx.post(
                    f"{self.host}/api/generate",
                    json=request_body,
                    timeout=httpx.Timeout(self.timeout_seconds, connect=10),
                )
                response.raise_for_status()
                break
            except httpx.TimeoutException as exc:
                if attempt == 0:
                    logger.warning(
                        "Ollama request timed out after %s seconds; retrying once.",
                        self.timeout_seconds,
                    )
                    continue
                raise ProviderError(
                    f"Ollama did not respond within {self.timeout_seconds} seconds after one retry."
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(f"Could not get a response from Ollama: {exc}") from exc

        try:
            if response is None:
                raise ProviderError("Ollama did not return a response.")
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(f"Could not get a valid response from Ollama: {exc}") from exc

        if not isinstance(payload, dict):
            raise ProviderError("Ollama returned an invalid response envelope.")
        result = payload.get("response")
        if not isinstance(result, str) or not result.strip():
            raise ProviderError("Ollama returned an empty or invalid response.")
        return result


def _get_timeout_seconds_from_env() -> float:
    raw_value = os.getenv("OLLAMA_TIMEOUT_SECONDS", "300")
    try:
        timeout_seconds = float(raw_value)
    except ValueError as exc:
        raise ValueError(
            "OLLAMA_TIMEOUT_SECONDS must be a number greater than zero. "
            f"Got {raw_value!r}."
        ) from exc
    if timeout_seconds <= 0:
        raise ValueError("OLLAMA_TIMEOUT_SECONDS must be greater than zero.")
    return timeout_seconds


def create_provider() -> ModelProvider:
    return OllamaProvider(
        host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
        timeout_seconds=_get_timeout_seconds_from_env(),
    )
