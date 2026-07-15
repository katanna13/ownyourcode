from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = (
        "postgresql+psycopg://ownyourcode:ownyourcode@localhost:5432/ownyourcode"
    )
    cors_origins: list[str] = ["http://localhost:5173"]
    github_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
