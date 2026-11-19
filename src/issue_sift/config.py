"""Application settings, read from environment variables or a local .env file."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ISSUE_SIFT_",
        env_file=".env",
        extra="ignore",
    )

    github_token: SecretStr | None = None
    source_repo: str | None = None
    data_dir: Path = Path("data")
    database_url: str = "postgresql://issue_sift:issue_sift@localhost:5432/issue_sift"


def get_settings() -> Settings:
    return Settings()
