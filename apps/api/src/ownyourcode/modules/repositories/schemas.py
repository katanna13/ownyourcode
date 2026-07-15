"""Public request and response contracts for repository inspection."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from ownyourcode.core.github_url import parse_public_github_repository_url


class RepositoryInspectionRequest(BaseModel):
    """The one user-provided value accepted by the inspection endpoint."""

    repository_url: str = Field(min_length=1, max_length=2048)

    @field_validator("repository_url", mode="before")
    @classmethod
    def normalize_repository_url(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str) -> str:
        return parse_public_github_repository_url(value).url


class RepositoryMetadata(BaseModel):
    name: str
    full_name: str
    description: str | None
    default_branch: str
    primary_language: str | None
    html_url: str


class DetectedLanguage(BaseModel):
    name: str
    bytes: int = Field(ge=0)


class DetectedTechnology(BaseModel):
    key: str
    label: str
    evidence: list[str]


class InspectedPaths(BaseModel):
    inspected_count: int = Field(ge=0)
    returned: list[str]
    truncated: bool


class ImportantFile(BaseModel):
    path: str
    kind: str


class RepositoryInspectionResponse(BaseModel):
    """A deterministic preview; no project or repository data is stored."""

    persisted: bool = False
    message: str = "Repository inspected. Nothing was saved."
    repository: RepositoryMetadata
    languages: list[DetectedLanguage]
    technologies: list[DetectedTechnology]
    paths: InspectedPaths
    important_files: list[ImportantFile]
    limitations: list[str]
