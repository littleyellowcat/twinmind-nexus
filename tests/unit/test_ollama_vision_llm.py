from __future__ import annotations

import base64
from typing import Any
from unittest.mock import Mock

from src.libs.llm.base_llm import Message
from src.libs.llm.base_vision_llm import ImageInput
from src.libs.llm.llm_factory import LLMFactory
from src.libs.llm.ollama_vision_llm import OllamaVisionLLM


class CapturingOllamaVisionLLM(OllamaVisionLLM):
    def __init__(self, settings: Any, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)
        self.last_payload: dict[str, Any] | None = None

    def _call_api(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        self.last_payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return {
            "model": model,
            "message": {"content": "这是一张项目架构图。"},
            "prompt_eval_count": 11,
            "eval_count": 7,
        }


def make_settings() -> Any:
    settings = Mock()
    settings.llm = Mock()
    settings.llm.model = "deepseek-v4-pro"
    settings.llm.temperature = 0.2
    settings.llm.max_tokens = 2000
    settings.vision_llm = Mock()
    settings.vision_llm.enabled = True
    settings.vision_llm.provider = "ollama"
    settings.vision_llm.model = "qwen2.5vl:7b"
    settings.vision_llm.base_url = "http://ollama.local:11434"
    return settings


def test_chat_with_image_sends_ollama_chat_payload_with_images() -> None:
    llm = CapturingOllamaVisionLLM(make_settings())
    response = llm.chat_with_image(
        text="请分析这张架构图",
        image=ImageInput(data=b"fake-image-bytes"),
        messages=[Message(role="system", content="只返回简洁说明")],
    )

    assert response.content == "这是一张项目架构图。"
    assert response.model == "qwen2.5vl:7b"
    assert response.usage == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert llm.last_payload is not None
    assert llm.last_payload["model"] == "qwen2.5vl:7b"
    assert llm.last_payload["temperature"] == 0.2
    assert llm.last_payload["max_tokens"] == 2000
    assert llm.last_payload["messages"][0] == {
        "role": "system",
        "content": "只返回简洁说明",
    }
    user_message = llm.last_payload["messages"][-1]
    assert user_message["role"] == "user"
    assert user_message["content"] == "请分析这张架构图"
    assert user_message["images"] == [
        base64.b64encode(b"fake-image-bytes").decode("utf-8")
    ]


def test_image_base64_prefers_existing_base64() -> None:
    llm = CapturingOllamaVisionLLM(make_settings())
    encoded = "already-encoded-image"

    response = llm.chat_with_image(
        text="描述图片",
        image=ImageInput(base64=encoded),
    )

    assert response.content
    assert llm.last_payload is not None
    assert llm.last_payload["messages"][-1]["images"] == [encoded]


def test_image_path_is_encoded(tmp_path) -> None:
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"png-bytes")
    llm = CapturingOllamaVisionLLM(make_settings())

    llm.chat_with_image(text="描述图片", image=ImageInput(path=image_path))

    assert llm.last_payload is not None
    assert llm.last_payload["messages"][-1]["images"] == [
        base64.b64encode(b"png-bytes").decode("utf-8")
    ]


def test_factory_can_create_ollama_vision_provider() -> None:
    LLMFactory.register_vision_provider("ollama", OllamaVisionLLM)

    vision_llm = LLMFactory.create_vision_llm(
        make_settings(),
        timeout=3,
    )

    assert isinstance(vision_llm, OllamaVisionLLM)
    assert vision_llm.model == "qwen2.5vl:7b"
    assert vision_llm.base_url == "http://ollama.local:11434"
    assert vision_llm.timeout == 3
