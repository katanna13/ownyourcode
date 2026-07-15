import re
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class ProjectMode(StrEnum):
    EXISTING_REPOSITORY = "existing_repository"
    NEW_IDEA = "new_idea"


class ProjectPreviewRequest(BaseModel):
    """Validated project details that are intentionally not persisted."""

    model_config = ConfigDict(validate_default=True)

    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=500)
    mode: ProjectMode
    repository_url: str | None = Field(default=None, max_length=2048)

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return " ".join(value.split())
        return value

    @field_validator("repository_url", mode="before")
    @classmethod
    def normalize_repository_url(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized_value = value.strip()
            return normalized_value or None
        return value

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        mode = info.data.get("mode")

        if mode == ProjectMode.EXISTING_REPOSITORY:
            if value is None:
                raise ValueError(
                    "repository_url is required when mode is existing_repository"
                )
            return cls._canonical_github_url(value)

        if mode == ProjectMode.NEW_IDEA and value is not None:
            raise ValueError(
                "repository_url is only allowed when mode is existing_repository"
            )

        return value

    @staticmethod
    def _canonical_github_url(value: str) -> str:
        parsed_url = urlparse(value)

        try:
            port = parsed_url.port
        except ValueError as error:
            raise ValueError("repository_url must be a valid GitHub URL") from error

        path_parts = [part for part in parsed_url.path.split("/") if part]
        valid_path_part = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "github.com"
            or parsed_url.username is not None
            or parsed_url.password is not None
            or port is not None
            or parsed_url.params
            or parsed_url.query
            or parsed_url.fragment
            or len(path_parts) != 2
            or not all(valid_path_part.fullmatch(part) for part in path_parts)
        ):
            raise ValueError(
                "repository_url must be an HTTPS GitHub repository URL such as "
                "https://github.com/owner/repository"
            )

        owner, repository = path_parts
        return f"https://github.com/{owner}/{repository}"


class ProjectPreviewResponse(BaseModel):
    """A successful validation result with no persistence side effect."""

    validated: bool = True
    persisted: bool = False
    message: str = "Project details validated. Nothing was saved."
    project: ProjectPreviewRequest
