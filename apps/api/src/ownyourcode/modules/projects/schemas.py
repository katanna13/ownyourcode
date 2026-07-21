from typing import Any
from uuid import UUID
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.projects.models import ProjectMode, ProjectStatus


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


class NewIdeaBrief(BaseModel):
    """A bounded learner-authored brief; it does not generate a plan in Phase 11A."""

    model_config = ConfigDict(extra="forbid")

    problem: str = Field(min_length=10, max_length=400)
    intended_user: str = Field(min_length=2, max_length=160)
    first_outcome: str = Field(min_length=10, max_length=400)
    constraints: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("problem", "intended_user", "first_outcome", mode="before")
    @classmethod
    def normalize_brief_text(cls, value: Any) -> Any:
        return normalize_safe_text(value)

    @field_validator("constraints", mode="before")
    @classmethod
    def normalize_constraints(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return [normalize_safe_text(item) for item in value]

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) < 2 or len(item) > 160:
                raise ValueError("Each constraint must contain between 2 and 160 characters")
        return value


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=500)
    mode: ProjectMode
    repository_url: str | None = Field(default=None, max_length=2048)
    idea_brief: NewIdeaBrief | None = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_project_text(cls, value: Any) -> Any:
        return normalize_safe_text(value)

    @field_validator("repository_url", mode="before")
    @classmethod
    def normalize_project_repository_url(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized_value = value.strip()
            return normalized_value or None
        return value

    @model_validator(mode="after")
    def validate_source(self) -> "ProjectCreateRequest":
        if self.mode == ProjectMode.EXISTING_REPOSITORY:
            if self.repository_url is None:
                raise ValueError(
                    "repository_url is required when mode is existing_repository"
                )
            if self.idea_brief is not None:
                raise ValueError(
                    "idea_brief is only allowed when mode is new_idea"
                )
            self.repository_url = parse_public_github_repository_url(
                self.repository_url
            ).url
        elif self.repository_url is not None:
            raise ValueError(
                "repository_url is only allowed when mode is existing_repository"
            )
        elif self.idea_brief is None:
            raise ValueError("idea_brief is required when mode is new_idea")
        return self


class ProjectPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, min_length=10, max_length=500)

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_project_text(cls, value: Any) -> Any:
        return normalize_safe_text(value)

    @model_validator(mode="after")
    def require_change(self) -> "ProjectPatchRequest":
        if self.name is None and self.description is None:
            raise ValueError("At least one project field must be provided")
        return self


class ProjectSourceResponse(BaseModel):
    mode: ProjectMode
    repository_url: str | None
    idea_brief: NewIdeaBrief | None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str
    mode: ProjectMode
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    source: ProjectSourceResponse


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    next_cursor: str | None


def normalize_safe_text(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split())
    return value
