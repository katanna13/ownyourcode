from functools import lru_cache
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

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
    clerk_jwt_key: SecretStr | None = None
    clerk_issuer: str | None = None
    clerk_audience_value: str | None = Field(
        default=None, validation_alias="CLERK_AUDIENCE"
    )
    clerk_authorized_parties_value: str | None = Field(
        default=None, validation_alias="CLERK_AUTHORIZED_PARTIES"
    )
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

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        return [normalize_origin(value) for value in values]

    @property
    def clerk_audience(self) -> tuple[str, ...]:
        return parse_comma_separated_values(self.clerk_audience_value, "CLERK_AUDIENCE")

    @property
    def clerk_authorized_parties(self) -> tuple[str, ...]:
        values = parse_comma_separated_values(
            self.clerk_authorized_parties_value, "CLERK_AUTHORIZED_PARTIES"
        )
        normalized_values = tuple(normalize_origin(value) for value in values)
        if len(normalized_values) != len(set(normalized_values)):
            raise ValueError("CLERK_AUTHORIZED_PARTIES must not contain duplicate origins")
        return normalized_values

    def clerk_auth_configuration(self) -> "ClerkAuthConfiguration":
        jwt_key = self.clerk_jwt_key.get_secret_value() if self.clerk_jwt_key else ""
        if not jwt_key.strip():
            raise ValueError("CLERK_JWT_KEY is required for protected API routes")
        if not self.clerk_issuer:
            raise ValueError("CLERK_ISSUER is required for protected API routes")

        issuer = normalize_origin(self.clerk_issuer)
        authorized_parties = self.clerk_authorized_parties
        if not authorized_parties:
            raise ValueError(
                "CLERK_AUTHORIZED_PARTIES must contain at least one exact origin"
            )

        return ClerkAuthConfiguration(
            jwt_key=jwt_key,
            issuer=issuer,
            audience=self.clerk_audience,
            authorized_parties=authorized_parties,
        )


@dataclass(frozen=True)
class ClerkAuthConfiguration:
    jwt_key: str
    issuer: str
    audience: tuple[str, ...]
    authorized_parties: tuple[str, ...]


def parse_comma_separated_values(value: str | None, setting_name: str) -> tuple[str, ...]:
    if value is None or not value.strip():
        return ()

    values = tuple(item.strip() for item in value.split(",") if item.strip())
    if len(values) != len(set(values)):
        raise ValueError(f"{setting_name} must not contain duplicate values")
    return values


def normalize_origin(value: str) -> str:
    candidate = value.strip().rstrip("/")
    if not candidate or "*" in candidate:
        raise ValueError("Origins must be exact and must not contain wildcard characters")

    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Origins must be absolute HTTP(S) origins without a path")
    return candidate


@lru_cache
def get_settings() -> Settings:
    return Settings()
