"""Ollama Vision LLM implementation for local multimodal inference."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from src.libs.llm.base_llm import ChatResponse, Message
from src.libs.llm.base_vision_llm import BaseVisionLLM, ImageInput


class OllamaVisionLLMError(RuntimeError):
    """Raised when an Ollama vision request fails."""


class OllamaVisionLLM(BaseVisionLLM):
    """Vision provider for Ollama's local `/api/chat` multimodal endpoint."""

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 180.0

    def __init__(
        self,
        settings: Any,
        base_url: str | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        vision_settings = getattr(settings, "vision_llm", None)
        self.model = (
            getattr(vision_settings, "model", None)
            or getattr(settings.llm, "model", None)
            or "qwen2.5vl:7b"
        )
        self.default_temperature = getattr(settings.llm, "temperature", 0.0)
        self.default_max_tokens = getattr(settings.llm, "max_tokens", 2048)
        configured_base_url = getattr(vision_settings, "base_url", None)
        if not isinstance(configured_base_url, str) or not configured_base_url.strip():
            configured_base_url = None

        self.base_url = (
            base_url
            or configured_base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or self.DEFAULT_BASE_URL
        )
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._extra_config = kwargs

    def chat_with_image(
        self,
        text: str,
        image: ImageInput,
        messages: list[Message] | None = None,
        trace: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.validate_text(text)
        self.validate_image(image)

        api_messages = [
            {"role": message.role, "content": message.content}
            for message in (messages or [])
        ]
        api_messages.append(
            {
                "role": "user",
                "content": text,
                "images": [self._image_base64(image)],
            }
        )

        try:
            response_data = self._call_api(
                messages=api_messages,
                model=kwargs.get("model", self.model),
                temperature=kwargs.get("temperature", self.default_temperature),
                max_tokens=kwargs.get("max_tokens", self.default_max_tokens),
            )
            content = response_data.get("message", {}).get("content")
            if not isinstance(content, str):
                raise OllamaVisionLLMError(
                    "[Ollama Vision] Unexpected response format: missing message.content"
                )
            usage = None
            if "eval_count" in response_data or "prompt_eval_count" in response_data:
                usage = {
                    "prompt_tokens": response_data.get("prompt_eval_count", 0),
                    "completion_tokens": response_data.get("eval_count", 0),
                    "total_tokens": response_data.get("prompt_eval_count", 0)
                    + response_data.get("eval_count", 0),
                }
            return ChatResponse(
                content=content,
                model=response_data.get("model", self.model),
                usage=usage,
                raw_response=response_data,
            )
        except Exception as exc:
            if isinstance(exc, OllamaVisionLLMError):
                raise
            raise OllamaVisionLLMError(
                f"[Ollama Vision] API call failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _call_api(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        import httpx

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code != 200:
                    raise OllamaVisionLLMError(
                        f"[Ollama Vision] API error (HTTP {response.status_code}): "
                        f"{self._parse_error_response(response)}"
                    )
                return response.json()
        except httpx.TimeoutException as exc:
            raise OllamaVisionLLMError(
                f"[Ollama Vision] Request timed out after {self.timeout} seconds."
            ) from exc
        except httpx.ConnectError as exc:
            raise OllamaVisionLLMError(
                "[Ollama Vision] Connection failed. Start Ollama with 'ollama serve' "
                f"and pull the model with 'ollama pull {model}'."
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaVisionLLMError(
                f"[Ollama Vision] Request failed: {type(exc).__name__}"
            ) from exc

    def _image_base64(self, image: ImageInput) -> str:
        if image.base64:
            return image.base64
        if image.data:
            return base64.b64encode(image.data).decode("utf-8")
        if image.path:
            return base64.b64encode(Path(image.path).read_bytes()).decode("utf-8")
        raise OllamaVisionLLMError("ImageInput must contain path, data, or base64.")

    @staticmethod
    def _parse_error_response(response: Any) -> str:
        try:
            data = response.json()
            if "error" in data:
                return str(data["error"])
        except Exception:
            pass
        return response.text[:200] if getattr(response, "text", "") else "Unknown error"
