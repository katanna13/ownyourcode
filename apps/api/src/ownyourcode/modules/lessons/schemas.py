"""Typed request, evidence, and structured-lesson contracts."""

from enum import StrEnum
import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ownyourcode.core.github_url import parse_public_github_repository_url


MAX_EVIDENCE_ID_LENGTH = 240


def validate_evidence_id(value: str) -> str:
    """Accept bounded, display-safe deterministic evidence identifiers only."""

    if not value or len(value) > MAX_EVIDENCE_ID_LENGTH:
        raise ValueError("Evidence ID has an invalid length.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Evidence ID cannot contain control characters.")
    return value


class LearnerLevel(StrEnum):
    BEGINNER = "beginner"
    JUNIOR = "junior"
    INTERMEDIATE = "intermediate"


class LessonGenerationRequest(BaseModel):
    """Learner-controlled input for one non-persistent orientation lesson."""

    model_config = ConfigDict(extra="forbid")

    repository_url: str = Field(min_length=1, max_length=2048)
    learner_level: LearnerLevel
    learning_goal: str | None = Field(default=None, max_length=240)

    @field_validator("repository_url", mode="before")
    @classmethod
    def normalize_repository_url(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped_value = value.strip()
            return stripped_value or None
        return value

    @field_validator("learning_goal", mode="before")
    @classmethod
    def normalize_learning_goal(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized_value = _normalize_display_text(value)
            return normalized_value or None
        return value

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Repository URL is required.")
        return parse_public_github_repository_url(value).url


class EvidenceItem(BaseModel):
    """A deterministic catalog item the model may cite by ID only."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=MAX_EVIDENCE_ID_LENGTH)
    kind: str = Field(min_length=1, max_length=48)
    label: str = Field(min_length=1, max_length=240)
    detail: str = Field(min_length=1, max_length=360)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_evidence_id(value)


class EvidenceCatalog(BaseModel):
    """Bounded deterministic facts that are sent as untrusted model input."""

    model_config = ConfigDict(extra="forbid")

    items: list[EvidenceItem] = Field(min_length=1, max_length=40)
    catalog_limitations: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("catalog_limitations")
    @classmethod
    def validate_catalog_limitations(cls, values: list[str]) -> list[str]:
        return _validate_bounded_strings(values, minimum_length=1, maximum_length=360)


class LessonConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=90)
    explanation: str = Field(min_length=30, max_length=500)
    why_it_matters: str = Field(min_length=20, max_length=280)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)
    reflection_question: str = Field(min_length=10, max_length=220)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        return _validate_unique_evidence_ids(values)


class ArchitectureWalkthroughStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str = Field(min_length=15, max_length=300)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        return _validate_unique_evidence_ids(values)


class ArchitectureOrientationLessonDraft(BaseModel):
    """The strict structured output requested from the Responses API."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=90)
    learning_objective: str = Field(min_length=10, max_length=240)
    repository_summary: str = Field(min_length=20, max_length=500)
    repository_summary_evidence_ids: list[str] = Field(min_length=1, max_length=4)
    concepts: list[LessonConcept] = Field(min_length=2, max_length=4)
    architecture_walkthrough: list[ArchitectureWalkthroughStep] = Field(
        min_length=2, max_length=4
    )
    knowledge_check_questions: list[str] = Field(min_length=2, max_length=3)
    limitations_and_open_questions: list[str] = Field(min_length=1, max_length=4)

    @field_validator("repository_summary_evidence_ids")
    @classmethod
    def validate_summary_evidence_ids(cls, values: list[str]) -> list[str]:
        return _validate_unique_evidence_ids(values)

    @field_validator("knowledge_check_questions")
    @classmethod
    def validate_knowledge_check_questions(cls, values: list[str]) -> list[str]:
        return _validate_bounded_strings(values, minimum_length=10, maximum_length=220)

    @field_validator("limitations_and_open_questions")
    @classmethod
    def validate_limitations_and_open_questions(cls, values: list[str]) -> list[str]:
        return _validate_bounded_strings(values, minimum_length=10, maximum_length=240)


class LessonGenerationResponse(BaseModel):
    """A lesson preview. Neither project data nor generated content is stored."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    message: str = "Lesson generated from inspected repository evidence. Nothing was saved."
    inspection_limitations: list[str] = Field(max_length=6)
    evidence_catalog: list[EvidenceItem] = Field(max_length=40)
    lesson: ArchitectureOrientationLessonDraft

    @field_validator("inspection_limitations")
    @classmethod
    def validate_inspection_limitations(cls, values: list[str]) -> list[str]:
        return _validate_bounded_strings(values, minimum_length=1, maximum_length=360)


def _validate_unique_evidence_ids(values: list[str]) -> list[str]:
    validated_values = [validate_evidence_id(value) for value in values]
    if len(set(validated_values)) != len(validated_values):
        raise ValueError("Evidence IDs cannot be duplicated in one citation list.")
    return validated_values


def _validate_bounded_strings(
    values: list[str], *, minimum_length: int, maximum_length: int
) -> list[str]:
    for value in values:
        if not minimum_length <= len(value) <= maximum_length:
            raise ValueError("Text item has an invalid length.")
    return values


def _normalize_display_text(value: str) -> str:
    normalized_value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized_value).strip()
