from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderConfig:
    """Cấu hình provider cho chat model dùng chung giữa các agent."""

    provider: str
    model_name: str
    temperature: float = 0.0
    api_key: str | None = None
    base_url: str | None = None


def normalize_provider(value: str) -> str:
    """Chuẩn hóa tên provider từ các alias phổ biến về định danh chuẩn.

    Hỗ trợ các provider chính:
    - openai
    - custom (OpenAI-compatible base URL)
    - gemini
    - anthropic
    - ollama
    - openrouter
    """
    val = value.strip().lower()
    mapping = {
        "openai": "openai",
        "chatgpt": "openai",
        "custom": "custom",
        "openai-compatible": "custom",
        "gemini": "gemini",
        "google": "gemini",
        "google-genai": "gemini",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "anthorpic": "anthropic",
        "ollama": "ollama",
        "openrouter": "openrouter",
    }
    return mapping.get(val, val)


def build_chat_model(config: ProviderConfig) -> Any:
    """Khởi tạo instance Chat Model tương ứng dựa trên provider đã cấu hình.

    Hỗ trợ graceful import: Nếu các package optional chưa cài đặt, thông báo lỗi rõ ràng.
    """
    provider = normalize_provider(config.provider)

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.model_name,
                temperature=config.temperature,
                api_key=config.api_key,
            )
        except ImportError as exc:
            raise ImportError("Vui lòng cài đặt langchain-openai: pip install langchain-openai") from exc

    if provider == "custom":
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.model_name,
                temperature=config.temperature,
                api_key=config.api_key or "EMPTY",
                base_url=config.base_url,
            )
        except ImportError as exc:
            raise ImportError("Vui lòng cài đặt langchain-openai để dùng custom provider: pip install langchain-openai") from exc

    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=config.model_name,
                temperature=config.temperature,
                google_api_key=config.api_key,
            )
        except ImportError as exc:
            raise ImportError("Vui lòng cài đặt langchain-google-genai: pip install langchain-google-genai") from exc

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=config.model_name,
                temperature=config.temperature,
                api_key=config.api_key,
            )
        except ImportError as exc:
            raise ImportError("Vui lòng cài đặt langchain-anthropic: pip install langchain-anthropic") from exc

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=config.model_name,
                temperature=config.temperature,
                base_url=config.base_url or "http://localhost:11434",
            )
        except ImportError as exc:
            raise ImportError("Vui lòng cài đặt langchain-ollama: pip install langchain-ollama") from exc

    if provider == "openrouter":
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.model_name,
                temperature=config.temperature,
                api_key=config.api_key,
                base_url=config.base_url or "https://openrouter.ai/api/v1",
            )
        except ImportError as exc:
            raise ImportError("Vui lòng cài đặt langchain-openai để dùng openrouter: pip install langchain-openai") from exc

    raise ValueError(f"Provider '{config.provider}' không được hỗ trợ. Các lựa chọn: openai, custom, gemini, anthropic, ollama, openrouter")
