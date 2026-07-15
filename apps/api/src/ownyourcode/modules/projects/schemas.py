from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from ownyourcode.core.github_url import parse_public_github_repository_url


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
            return parse_public_github_repository_url(value).url

        if mode == ProjectMode.NEW_IDEA and value is not None:
            raise ValueError(
                "repository_url is only allowed when mode is existing_repository"
            )

        return value

class ProjectPreviewResponse(BaseModel):
    """A successful validation result with no persistence side effect."""

    validated: bool = True
    persisted: bool = False
    message: str = "Project details validated. Nothing was saved."
    project: ProjectPreviewRequest
