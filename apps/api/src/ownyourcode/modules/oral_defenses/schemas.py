"""Strict contracts for the architecture-boundaries oral defense preview."""

from typing import Any, Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.lessons.schemas import (
    EvidenceItem,
    LearnerLevel,
    validate_evidence_id,
)


ARCHITECTURE_BOUNDARIES_ORAL_DEFENSE_ID = "architecture-boundaries.v1"
ARCHITECTURE_BOUNDARIES_QUESTION_ID = "architecture-boundaries.question.v1"
ORAL_DEFENSE_QUESTION_DEFINITION_VERSION = "architecture-boundaries-question.v1"
ORAL_DEFENSE_RUBRIC_VERSION = "architecture-boundaries-rubric.v1"
ORAL_DEFENSE_CONTEXT_ID_LENGTH = 64
MAX_ORAL_DEFENSE_ANSWER_LENGTH = 800

SUPPORTED_BOUNDARIES_RUBRIC_ID = "architecture-boundaries.supported-boundaries.v1"
EVIDENCE_GROUNDING_RUBRIC_ID = "architecture-boundaries.evidence-grounding.v1"
LIMITATION_AWARENESS_RUBRIC_ID = "architecture-boundaries.limitation-awareness.v1"
TRADEOFF_OR_NEXT_STEP_RUBRIC_ID = (
    "architecture-boundaries.tradeoff-or-next-step.v1"
)
OralDefenseRubricDimensionId = Literal[
    SUPPORTED_BOUNDARIES_RUBRIC_ID,
    EVIDENCE_GROUNDING_RUBRIC_ID,
    LIMITATION_AWARENESS_RUBRIC_ID,
    TRADEOFF_OR_NEXT_STEP_RUBRIC_ID,
]
BoundaryCategory = Literal["frontend", "backend", "container"]


class OralDefensePrepareRequest(BaseModel):
    """Fresh repository context for one non-persistent oral-defense preview."""

    model_config = ConfigDict(extra="forbid")

    repository_url: str = Field(min_length=1, max_length=2048)
    learner_level: LearnerLevel

    @field_validator("repository_url", mode="before")
    @classmethod
    def normalize_repository_url(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Repository URL is required.")
        return parse_public_github_repository_url(value).url


class BoundaryEvidence(BaseModel):
    """One server-selected category and its deterministic supporting evidence."""

    model_config = ConfigDict(extra="forbid")

    category: BoundaryCategory
    evidence: EvidenceItem


class OralDefenseQuestion(BaseModel):
    """A public question definition with evidence but no reference answer."""

    model_config = ConfigDict(extra="forbid")

    id: Literal[ARCHITECTURE_BOUNDARIES_QUESTION_ID]
    prompt: str = Field(min_length=40, max_length=600)
    boundary_evidence: list[BoundaryEvidence] = Field(min_length=2, max_length=3)

    @field_validator("boundary_evidence")
    @classmethod
    def validate_categories_and_evidence(
        cls, values: list[BoundaryEvidence]
    ) -> list[BoundaryEvidence]:
        categories = [item.category for item in values]
        evidence_ids = [item.evidence.id for item in values]
        if len(set(categories)) != len(categories):
            raise ValueError("Boundary categories must be unique.")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Boundary evidence IDs must be unique.")
        return values


class OralDefenseAvailableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    available: Literal[True] = True
    message: str = "Oral defense prepared. Nothing was saved."
    oral_defense_id: Literal[ARCHITECTURE_BOUNDARIES_ORAL_DEFENSE_ID] = (
        ARCHITECTURE_BOUNDARIES_ORAL_DEFENSE_ID
    )
    oral_defense_context_id: str = Field(
        min_length=ORAL_DEFENSE_CONTEXT_ID_LENGTH,
        max_length=ORAL_DEFENSE_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    title: str = Field(min_length=3, max_length=100)
    question: OralDefenseQuestion
    maximum_answer_length: Literal[MAX_ORAL_DEFENSE_ANSWER_LENGTH] = (
        MAX_ORAL_DEFENSE_ANSWER_LENGTH
    )
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("inspection_limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return _validate_bounded_texts(values)


class OralDefenseUnavailableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    available: Literal[False] = False
    message: str = "This oral defense is unavailable for the inspected repository."
    reason: str = Field(min_length=20, max_length=300)
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("inspection_limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return _validate_bounded_texts(values)


OralDefensePrepareResponse = OralDefenseAvailableResponse | OralDefenseUnavailableResponse


class OralDefenseEvaluationRequest(OralDefensePrepareRequest):
    """One short answer for a freshly rebuilt oral-defense definition."""

    oral_defense_context_id: str = Field(
        min_length=ORAL_DEFENSE_CONTEXT_ID_LENGTH,
        max_length=ORAL_DEFENSE_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    question_id: Literal[ARCHITECTURE_BOUNDARIES_QUESTION_ID]
    answer_text: str = Field(min_length=40, max_length=MAX_ORAL_DEFENSE_ANSWER_LENGTH)

    @field_validator("answer_text", mode="before")
    @classmethod
    def normalize_and_validate_safe_answer_text(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        for character in normalized:
            category = unicodedata.category(character)
            if category in {"Cf", "Cs"} or (
                category == "Cc" and character not in {"\n", "\t"}
            ):
                raise ValueError("Oral-defense answer contains unsafe control characters.")
        return normalized

    @field_validator("answer_text")
    @classmethod
    def require_meaningful_answer_length(cls, value: str) -> str:
        if len(value.strip()) < 40:
            raise ValueError(
                "Oral-defense answer must contain at least 40 non-whitespace characters."
            )
        return value


class OralDefenseModelRubricDimension(BaseModel):
    """One model-evaluated signal, with all numeric bounds fixed by the server."""

    model_config = ConfigDict(extra="forbid")

    id: OralDefenseRubricDimensionId
    earned_points: Literal[0, 1]
    feedback: str = Field(min_length=20, max_length=260)


class OralDefenseModelEvaluation(BaseModel):
    """The exact structured output allowed from the one model evaluation call."""

    model_config = ConfigDict(extra="forbid")

    rubric_dimensions: list[OralDefenseModelRubricDimension] = Field(
        min_length=4,
        max_length=4,
    )
    evidence_ids: list[str] = Field(max_length=3)

    @field_validator("rubric_dimensions")
    @classmethod
    def validate_fixed_dimension_order(
        cls,
        values: list[OralDefenseModelRubricDimension],
    ) -> list[OralDefenseModelRubricDimension]:
        if [dimension.id for dimension in values] != [
            SUPPORTED_BOUNDARIES_RUBRIC_ID,
            EVIDENCE_GROUNDING_RUBRIC_ID,
            LIMITATION_AWARENESS_RUBRIC_ID,
            TRADEOFF_OR_NEXT_STEP_RUBRIC_ID,
        ]:
            raise ValueError("Rubric dimensions must use the fixed ordered IDs.")
        return values

    @field_validator("evidence_ids")
    @classmethod
    def validate_unique_evidence_ids(cls, values: list[str]) -> list[str]:
        validated = [validate_evidence_id(value) for value in values]
        if len(set(validated)) != len(validated):
            raise ValueError("Evidence IDs cannot be duplicated.")
        return validated


class OralDefenseRubricDimension(BaseModel):
    """Server-validated feedback presented for one fixed rubric dimension."""

    model_config = ConfigDict(extra="forbid")

    id: OralDefenseRubricDimensionId
    earned_points: Literal[0, 1]
    max_points: Literal[1] = 1
    feedback: str = Field(min_length=20, max_length=260)


class OralDefensePoints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    earned_points: int = Field(ge=0, le=4)
    max_points: Literal[4] = 4


class OralDefenseEvaluationResponse(BaseModel):
    """One evaluated response; neither answer nor result is stored."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    message: str = "Oral defense evaluated. Nothing was saved."
    oral_defense_points: OralDefensePoints
    rubric_dimensions: list[OralDefenseRubricDimension] = Field(
        min_length=4,
        max_length=4,
    )
    evidence_ids: list[str] = Field(max_length=3)
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("rubric_dimensions")
    @classmethod
    def validate_fixed_dimension_order(
        cls,
        values: list[OralDefenseRubricDimension],
    ) -> list[OralDefenseRubricDimension]:
        if [dimension.id for dimension in values] != [
            SUPPORTED_BOUNDARIES_RUBRIC_ID,
            EVIDENCE_GROUNDING_RUBRIC_ID,
            LIMITATION_AWARENESS_RUBRIC_ID,
            TRADEOFF_OR_NEXT_STEP_RUBRIC_ID,
        ]:
            raise ValueError("Rubric dimensions must use the fixed ordered IDs.")
        return values

    @field_validator("evidence_ids")
    @classmethod
    def validate_unique_evidence_ids(cls, values: list[str]) -> list[str]:
        validated = [validate_evidence_id(value) for value in values]
        if len(set(validated)) != len(validated):
            raise ValueError("Evidence IDs cannot be duplicated.")
        return validated

    @field_validator("inspection_limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return _validate_bounded_texts(values)

    @model_validator(mode="after")
    def validate_earned_points_match_dimensions(self) -> "OralDefenseEvaluationResponse":
        dimension_points = sum(
            dimension.earned_points for dimension in self.rubric_dimensions
        )
        if self.oral_defense_points.earned_points != dimension_points:
            raise ValueError(
                "oral_defense_points must match the rubric dimension points."
            )
        return self


def _validate_bounded_texts(values: list[str]) -> list[str]:
    for value in values:
        if not 1 <= len(value) <= 360:
            raise ValueError("Text item has an invalid length.")
    return values
