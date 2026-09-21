"""Application settings.

The repo holds the system; your content, brands and database live in a workspace folder
outside it, so nothing you write is ever committed here.

Override any of these with environment variables (CM_WORKSPACE, CM_PORT, ...) or a .env file.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CM_", env_file=".env", extra="ignore")

    workspace: Path = Path(__file__).resolve().parent.parent / "workspace"
    host: str = "127.0.0.1"
    port: int = 8777

    @property
    def db_path(self) -> Path:
        return self.workspace / "content.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def content_dir(self) -> Path:
        return self.workspace / "content"

    @property
    def state_dir(self) -> Path:
        """The app's own files: the access token and the search index. Not content."""
        return self.workspace / ".cm"

    @property
    def trash_dir(self) -> Path:
        """Where a deleted piece's folder goes, so deleting the entry never deletes the work."""
        return self.workspace / "trash"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.workspace.mkdir(parents=True, exist_ok=True)
    return settings
