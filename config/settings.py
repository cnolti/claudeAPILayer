"""Application settings and configuration."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = Field(default="change-me-in-production")
    debug: bool = False

    # Claude Settings
    claude_binary: str = "claude"
    claude_model: str = "claude-sonnet-4-20250514"
    claude_fallback_model: str = "claude-haiku-4-5-20251001"
    claude_max_turns: int = 10
    claude_timeout: int = 300  # seconds

    # Session Settings
    session_ttl: int = 3600 * 24  # 24 hours
    session_cleanup_interval: int = 3600  # 1 hour

    # Database Settings
    database_url: str = "sqlite+aiosqlite:///./data/sessions.db"

    # Sandbox Settings
    sandbox_type: Literal["docker", "subprocess"] = "docker"
    sandbox_timeout: int = 60  # seconds
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0

    # Git Settings
    git_auto_commit: bool = False
    git_commit_prefix: str = "[claude-api]"

    # Paths
    data_dir: Path = Path("./data")
    allowed_paths: list[str] = Field(default_factory=lambda: ["."])

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
