from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    openai_api_key: SecretStr | None = None
    openai_model: str | None = Field(default=None, max_length=128)
    openai_reasoning_effort: Literal[
        "none", "minimal", "low", "medium", "high", "xhigh"
    ] = "low"
    openai_timeout_seconds: float = Field(default=45, gt=0, le=60)
    openai_max_output_tokens: int = Field(default=2000, ge=256, le=2000)

    @field_validator("openai_api_key", "openai_model", mode="before")
    @classmethod
    def treat_blank_openai_settings_as_missing(cls, value: object) -> object:
        if isinstance(value, str):
            stripped_value = value.strip()
            return stripped_value or None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
