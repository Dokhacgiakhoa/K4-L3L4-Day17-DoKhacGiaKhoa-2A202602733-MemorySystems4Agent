from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from model_provider import ProviderConfig, normalize_provider

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass


@dataclass
class LabConfig:
    """Cấu hình dùng chung của bài lab Memory Systems."""

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig


def load_config(base_dir: Path | None = None) -> LabConfig:
    """Nạp biến môi trường từ .env (nếu có) và trả về LabConfig hoàn chỉnh."""
    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()

    # Load file .env nếu có ở root
    env_path = root / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)

    # Thư mục dữ liệu & lưu trữ state
    data_dir = root / "data"
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "profiles").mkdir(parents=True, exist_ok=True)

    # Cấu hình compact memory
    compact_threshold_tokens = int(os.getenv("COMPACT_THRESHOLD_TOKENS", "600"))
    compact_keep_messages = int(os.getenv("COMPACT_KEEP_MESSAGES", "4"))

    # Cấu hình Model Provider
    provider_str = normalize_provider(os.getenv("LLM_PROVIDER", "openai"))
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # Lấy API key & base URL phù hợp
    api_key: str | None = None
    base_url: str | None = None

    if provider_str == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
    elif provider_str == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    elif provider_str == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
    elif provider_str == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    elif provider_str == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    elif provider_str == "custom":
        api_key = os.getenv("CUSTOM_API_KEY")
        base_url = os.getenv("CUSTOM_BASE_URL")

    main_model_config = ProviderConfig(
        provider=provider_str,
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
    )

    # Cấu hình judge model (nếu có)
    judge_provider = normalize_provider(os.getenv("JUDGE_PROVIDER", provider_str))
    judge_model_name = os.getenv("JUDGE_MODEL", model_name)
    judge_model_config = ProviderConfig(
        provider=judge_provider,
        model_name=judge_model_name,
        temperature=0.0,
        api_key=api_key,
        base_url=base_url,
    )

    return LabConfig(
        base_dir=root,
        data_dir=data_dir,
        state_dir=state_dir,
        compact_threshold_tokens=compact_threshold_tokens,
        compact_keep_messages=compact_keep_messages,
        model=main_model_config,
        judge_model=judge_model_config,
    )
