"""TUESDAY server settings — all secrets via environment only."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env", "../.env", "/home/user/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    tuesday_env: Literal["development", "staging", "production"] = "development"
    tuesday_host: str = "0.0.0.0"
    tuesday_port: int = 8000
    tuesday_log_level: str = "INFO"
    tuesday_cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    tuesday_data_dir: Path = Path("./data")
    tuesday_database_url: str = "sqlite+aiosqlite:///./data/tuesday.db"
    tuesday_secret_key: str = "dev-only-change-me"
    tuesday_access_token: str = ""
    tuesday_session_ttl_sec: int = 604_800
    tuesday_rate_limit_per_minute: int = 120
    tuesday_max_request_bytes: int = 12_582_912
    tuesday_allowed_hosts: str = "localhost,127.0.0.1,testserver,test"
    tuesday_allow_mock_model: bool = True

    # NVIDIA / models
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model_primary: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_model_fast: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    nvidia_model_fallback: str = ""

    # Sandbox
    sandbox_provider: Literal["local", "e2b", "cua"] = "local"
    sandbox_idle_timeout_sec: int = 900
    sandbox_max_command_timeout_sec: int = 120
    sandbox_max_output_bytes: int = 1_048_576
    sandbox_max_file_bytes: int = 10_485_760
    sandbox_max_concurrent: int = 5
    workspace_root_in_sandbox: str = "/workspace"

    e2b_api_key: str = ""
    e2b_template_id: str = ""
    e2b_timeout_sec: int = 3600

    cua_api_key: str = ""
    cua_api_url: str = ""

    # Voice
    stt_provider: Literal["none", "whisper", "nemotron_asr"] = "none"
    stt_api_url: str = ""
    stt_model: str = "openai/whisper-large-v3"
    stt_max_audio_bytes: int = 15_728_640
    tts_provider: Literal["none", "fish"] = "none"
    fish_audio_api_url: str = "https://api.fish.audio/v1/tts"
    fish_audio_api_key: str = ""
    fish_audio_voice_id: str = ""
    fish_audio_model: str = "s2.1-pro-free"

    # Memory
    memory_enabled: bool = True
    memory_embeddings_enabled: bool = False

    # Safety
    require_approval_for_network: bool = True
    require_approval_for_destructive: bool = True
    require_approval_for_shell: bool = True
    require_approval_for_gui: bool = True
    block_internal_network: bool = True
    proactive_notifications_enabled: bool = False

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: Path = Path("./data/storage")

    @field_validator("tuesday_data_dir", "storage_local_path", mode="before")
    @classmethod
    def _as_path(cls, v: object) -> Path:
        return Path(str(v)).expanduser()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.tuesday_cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.tuesday_allowed_hosts.split(",") if h.strip()]

    @property
    def has_nvidia(self) -> bool:
        return bool(self.nvidia_api_key and self.nvidia_api_key.strip())

    @property
    def has_e2b(self) -> bool:
        return bool(self.e2b_api_key and self.e2b_api_key.strip())

    @property
    def model_for_coding(self) -> str:
        return self.nvidia_model_primary

    def ensure_dirs(self) -> None:
        self.tuesday_data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_local_path.mkdir(parents=True, exist_ok=True)
        (self.tuesday_data_dir / "workspaces").mkdir(parents=True, exist_ok=True)

    @property
    def auth_required(self) -> bool:
        return bool(self.tuesday_access_token.strip())

    def validate_runtime(self) -> None:
        """Fail closed when production is started with unsafe placeholder settings."""
        if self.tuesday_env != "production":
            return
        errors: list[str] = []
        if (
            len(self.tuesday_secret_key) < 32
            or self.tuesday_secret_key == "dev-only-change-me"
        ):
            errors.append(
                "TUESDAY_SECRET_KEY must be a random value of at least 32 characters"
            )
        if len(self.tuesday_access_token) < 24:
            errors.append("TUESDAY_ACCESS_TOKEN must be at least 24 characters")
        if self.tuesday_allow_mock_model:
            errors.append("TUESDAY_ALLOW_MOCK_MODEL must be false")
        if not self.has_nvidia:
            errors.append("NVIDIA_API_KEY is required")
        if self.sandbox_provider == "local":
            errors.append("SANDBOX_PROVIDER=local is development-only")
        if self.sandbox_provider == "e2b" and not self.has_e2b:
            errors.append("E2B_API_KEY is required for SANDBOX_PROVIDER=e2b")
        if (
            self.sandbox_provider == "e2b"
            and self.sandbox_idle_timeout_sec >= self.e2b_timeout_sec
        ):
            errors.append("SANDBOX_IDLE_TIMEOUT_SEC must be lower than E2B_TIMEOUT_SEC")
        if self.tuesday_database_url.startswith("sqlite"):
            errors.append("PostgreSQL is required in production")
        if "*" in self.cors_origin_list:
            errors.append("Wildcard CORS is forbidden in production")
        if self.stt_provider != "none" and not self.stt_api_url:
            errors.append("STT_API_URL is required when STT is enabled")
        if self.tts_provider == "fish" and not self.fish_audio_api_key:
            errors.append("FISH_AUDIO_API_KEY is required when Fish Audio is enabled")
        if errors:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))

    @property
    def listen_port(self) -> int:
        """Honor Render's PORT without making it a Pydantic field."""
        raw = os.getenv("PORT")
        return int(raw) if raw and raw.isdigit() else self.tuesday_port


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
