"""Bounded public and stored contracts for the initial learning-path slice."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ownyourcode.modules.learning_workspaces.schemas import (
    MAX_LEARNING_GOAL_LENGTH,
    canonical_request_hash,
    normalize_safe_display_text,
    normalize_teaching_source,
)
from ownyourcode.modules.lessons.schemas import LearnerLevel, validate_evidence_id


LEARNING_PATH_CONTRACT_VERSION = "learning-path.v1"
LEARNING_MODULE_CONTRACT_VERSION = "learning-module.v1"
LEARNING_PATH_PLANNER_VERSION = "deterministic-module-planner.v1"
MAX_MODULES_PER_PATH = 3

ModuleState = Literal["locked", "available", "in_progress", "remediation_required", "demonstrated"]
PresentationKind = Literal["single_choice", "step_order", "code_fixture"]


class LearningPathCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_level: LearnerLevel
    learning_goal: str | None = Field(default=None, max_length=MAX_LEARNING_GOAL_LENGTH)

    @field_validator("learning_goal", mode="before")
    @classmethod
    def normalize_goal(cls, value: Any) -> Any:
        if isinstance(value, str):
            return normalize_safe_display_text(value) or None
        return value


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=240)
    label: str = Field(min_length=1, max_length=240)

    @field_validator("id")
    @classmethod
    def safe_id(cls, value: str) -> str:
        return validate_evidence_id(value)


class PublicActivityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=3, max_length=96)
    presentation_kind: PresentationKind
    context_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    prompt: str = Field(min_length=20, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)
    choices: list[Choice] = Field(default_factory=list, max_length=4)
    starter_code: str | None = Field(default=None, max_length=1_000)
    constraints: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("evidence_ids")
    @classmethod
    def safe_unique_evidence(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Evidence IDs must be unique.")
        return [validate_evidence_id(value) for value in values]


class PrivateActivityDefinition(BaseModel):
    """Never projected through a public route."""

    model_config = ConfigDict(extra="forbid")

    evaluator_key: Literal[
        "orientation-evidence.v1",
        "architecture-ordering.v1",
        "fastapi-health-fixture.v1",
        "evidence-reading-remediation.v1",
        "fixture-check-remediation.v1",
    ]
    expected_choice_id: str | None = Field(default=None, max_length=240)
    expected_order: list[str] = Field(default_factory=list, max_length=4)


class StoredActivityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public: PublicActivityDefinition
    private: PrivateActivityDefinition
    completion_role: Literal["required_completion", "required_gate", "required_remediation"]


class StoredModuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[LEARNING_MODULE_CONTRACT_VERSION] = LEARNING_MODULE_CONTRACT_VERSION
    module_key: str = Field(min_length=3, max_length=96)
    category: Literal["repository_orientation", "architecture_boundaries", "validation_failure_paths"]
    title: str = Field(min_length=3, max_length=120)
    objective: str = Field(min_length=20, max_length=360)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)
    lesson_sections: list[str] = Field(min_length=1, max_length=3)
    activities: list[StoredActivityDefinition] = Field(min_length=1, max_length=2)
    limitations: list[str] = Field(max_length=6)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Module evidence IDs must be unique.")
        return [validate_evidence_id(value) for value in values]


class ModuleActivityAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    selected_choice_id: str | None = Field(default=None, max_length=240)
    ordered_step_ids: list[str] | None = Field(default=None, max_length=4)
    source_code: str | None = Field(default=None, min_length=1, max_length=1_000)

    @field_validator("selected_choice_id")
    @classmethod
    def validate_choice(cls, value: str | None) -> str | None:
        return validate_evidence_id(value) if value is not None else None

    @field_validator("source_code", mode="before")
    @classmethod
    def normalize_source(cls, value: Any) -> Any:
        return normalize_teaching_source(value) if value is not None else None


class PublicModuleActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    presentation_kind: PresentationKind
    context_id: str
    prompt: str
    evidence_ids: list[str]
    choices: list[Choice]
    starter_code: str | None
    constraints: list[str]
    completion_role: str


class LearningPathModuleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    position: int = Field(ge=1, le=MAX_MODULES_PER_PATH)
    module_key: str
    category: str
    title: str
    objective: str
    evidence_ids: list[str]
    lesson_sections: list[str]
    activities: list[PublicModuleActivity]
    limitations: list[str]
    state: ModuleState
    required_remediation: bool
    remediation_activities: list[PublicModuleActivity] = Field(default_factory=list, max_length=4)


class LearningPathSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules_total: int = Field(ge=0, le=MAX_MODULES_PER_PATH)
    modules_demonstrated: int = Field(ge=0, le=MAX_MODULES_PER_PATH)
    practical_gates_passed: int = Field(ge=0, le=MAX_MODULES_PER_PATH)
    required_remediations_open: int = Field(ge=0, le=20)
    label: Literal["Current project learning summary"] = "Current project learning summary"
    disclaimer: str = "This is server-derived progress for the active learning path, not a certification or Ownership Score."


class LearningPathResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    mode: Literal["none", "legacy", "multi_module"]
    path_id: UUID | None = None
    path_version: int | None = Field(default=None, ge=1)
    source_evidence_fingerprint: str | None = None
    stale: bool = False
    limitations: list[str] = Field(default_factory=list, max_length=8)
    modules: list[LearningPathModuleResponse] = Field(default_factory=list, max_length=MAX_MODULES_PER_PATH)
    resume_module_id: UUID | None = None
    summary: LearningPathSummary | None = None


class ModuleAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    attempt_id: UUID
    passed: bool | None
    earned_points: int | None
    result: dict[str, Any]
    module: LearningPathModuleResponse
    summary: LearningPathSummary


def fingerprint(payload: dict[str, Any]) -> str:
    return canonical_request_hash(payload)
