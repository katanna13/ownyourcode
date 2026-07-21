"""Contracts for the persisted, authenticated Existing Repository workspace."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ownyourcode.modules.assessments.schemas import (
    ASSESSMENT_DEFINITION_VERSION,
    EXPLAIN_BACK_RUBRIC_VERSION,
    AssessmentAnswers,
    AssessmentQuestionsResponse,
)
from ownyourcode.modules.labs.schemas import FastAPIHealthCheckLabPrepareResponse
from ownyourcode.modules.lessons.schemas import (
    ArchitectureOrientationLessonDraft,
    EvidenceCatalog,
    EvidenceItem,
    LearnerLevel,
    validate_evidence_id,
)
from ownyourcode.modules.oral_defenses.schemas import OralDefensePrepareResponse
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse
from ownyourcode.modules.security_challenges.schemas import (
    FastAPICorsSecurityChallengePrepareResponse,
)


INSPECTION_SNAPSHOT_CONTRACT_VERSION = "project-inspection-snapshot.v1"
WORKSPACE_DEFINITION_CONTRACT_VERSION = "saved-existing-repository-workspace.v1"
LESSON_BUILDER_CONTRACT_VERSION = "architecture-orientation-lesson.v1"
MAX_IDEMPOTENCY_KEY_LENGTH = 128
MAX_LEARNING_GOAL_LENGTH = 240
MAX_STORED_WORKSPACE_DEFINITION_BYTES = 60_000

WorkspaceStage = Literal["inspect", "learn", "assess", "lab", "secure", "defend", "score"]


class StoredInspectionSnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[INSPECTION_SNAPSHOT_CONTRACT_VERSION] = (
        INSPECTION_SNAPSHOT_CONTRACT_VERSION
    )
    inspection: RepositoryInspectionResponse
    evidence_catalog: EvidenceCatalog


class PrivateAssessmentDefinition(BaseModel):
    """Server-only answer mapping for a frozen assessment definition."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[ASSESSMENT_DEFINITION_VERSION] = ASSESSMENT_DEFINITION_VERSION
    multiple_choice_correct_option_id: Literal[
        "option-a", "option-b", "option-c", "option-d"
    ]
    evidence_selection_correct_id: str = Field(min_length=1, max_length=240)
    target_evidence_id: str = Field(min_length=1, max_length=240)

    @field_validator("evidence_selection_correct_id", "target_evidence_id")
    @classmethod
    def validate_evidence(cls, value: str) -> str:
        return validate_evidence_id(value)


class WorkspaceBuilderVersions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson: str = Field(min_length=1, max_length=96)
    assessment: str = Field(min_length=1, max_length=96)
    assessment_rubric: str = Field(min_length=1, max_length=96)
    verified_lab: str = Field(min_length=1, max_length=96)
    security_challenge: str = Field(min_length=1, max_length=96)
    oral_defense: str = Field(min_length=1, max_length=96)


class StoredWorkspaceDefinition(BaseModel):
    """The complete frozen definition used for every saved activity evaluation."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[WORKSPACE_DEFINITION_CONTRACT_VERSION] = (
        WORKSPACE_DEFINITION_CONTRACT_VERSION
    )
    source_inspection_fingerprint: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    learner_level: LearnerLevel
    learning_goal: str | None = Field(default=None, max_length=MAX_LEARNING_GOAL_LENGTH)
    lesson: ArchitectureOrientationLessonDraft
    assessment_public_definition: AssessmentQuestionsResponse
    assessment_private_definition: PrivateAssessmentDefinition
    verified_lab_definition: FastAPIHealthCheckLabPrepareResponse
    security_challenge_definition: FastAPICorsSecurityChallengePrepareResponse
    oral_defense_definition: OralDefensePrepareResponse
    activity_evidence_ids: dict[str, list[str]]
    builder_versions: WorkspaceBuilderVersions

    @field_validator("learning_goal", mode="before")
    @classmethod
    def normalize_goal(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = normalize_safe_display_text(value)
            return normalized or None
        return value

    @field_validator("activity_evidence_ids")
    @classmethod
    def validate_activity_evidence_ids(
        cls, values: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        allowed = {"assessment", "verified_lab", "security_challenge", "oral_defense"}
        if set(values) != allowed:
            raise ValueError("Workspace evidence IDs must cover each fixed activity.")
        for evidence_ids in values.values():
            if len(evidence_ids) > 4 or len(set(evidence_ids)) != len(evidence_ids):
                raise ValueError("Activity evidence IDs must be bounded and unique.")
            for evidence_id in evidence_ids:
                validate_evidence_id(evidence_id)
        return values


class WorkspaceContentGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_level: LearnerLevel
    learning_goal: str | None = Field(default=None, max_length=MAX_LEARNING_GOAL_LENGTH)

    @field_validator("learning_goal", mode="before")
    @classmethod
    def normalize_goal(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = normalize_safe_display_text(value)
            return normalized or None
        return value


class WorkspaceProgressUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_viewed_stage: WorkspaceStage


class WorkspaceAssessmentAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_context_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    answers: AssessmentAnswers


class WorkspaceLabAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lab_context_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    source_code: str = Field(min_length=1, max_length=1_000)

    @field_validator("source_code", mode="before")
    @classmethod
    def normalize_source(cls, value: Any) -> Any:
        return normalize_teaching_source(value)


class WorkspaceSecurityAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    security_challenge_context_id: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    source_code: str = Field(min_length=1, max_length=1_000)

    @field_validator("source_code", mode="before")
    @classmethod
    def normalize_source(cls, value: Any) -> Any:
        return normalize_teaching_source(value)


class WorkspaceOralDefenseAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oral_defense_context_id: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    question_id: Literal["architecture-boundaries.question.v1"]
    answer_text: str = Field(min_length=40, max_length=800)

    @field_validator("answer_text", mode="before")
    @classmethod
    def normalize_answer(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        for character in normalized:
            category = unicodedata.category(character)
            if category in {"Cf", "Cs"} or (category == "Cc" and character not in {"\n", "\t"}):
                raise ValueError("Oral-defense answer contains unsafe control characters.")
        return normalized

    @field_validator("answer_text")
    @classmethod
    def require_meaningful_answer(cls, value: str) -> str:
        if len(value.strip()) < 40:
            raise ValueError("Oral-defense answer must contain at least 40 non-whitespace characters.")
        return value


class CurrentProjectLearningSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_points: int | None = Field(default=None, ge=0, le=4)
    verified_lab_passed: bool = False
    security_challenge_passed: bool = False
    oral_defense_points: int | None = Field(default=None, ge=0, le=4)
    raw_total: float = Field(ge=0, le=100)
    rounded_total: int = Field(ge=0, le=100)
    label: Literal["Current project learning summary"] = "Current project learning summary"
    disclaimer: str = (
        "This saved project summary reflects recorded attempts for the active "
        "learning workspace. It is not a certification or a permanent Ownership Score."
    )


class WorkspaceProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_viewed_stage: WorkspaceStage
    unlocked_stages: list[WorkspaceStage]
    assessment_attempt_id: UUID | None
    verified_lab_attempt_id: UUID | None
    security_challenge_attempt_id: UUID | None
    oral_defense_attempt_id: UUID | None
    assessment_result: dict[str, Any] | None = None
    verified_lab_result: dict[str, Any] | None = None
    security_challenge_result: dict[str, Any] | None = None
    oral_defense_result: dict[str, Any] | None = None
    summary: CurrentProjectLearningSummary


class SavedInspectionSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int = Field(ge=1)
    evidence_fingerprint: str = Field(min_length=64, max_length=64)
    inspection: RepositoryInspectionResponse


class SavedWorkspaceContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int = Field(ge=1)
    source_inspection_fingerprint: str = Field(min_length=64, max_length=64)
    learner_level: LearnerLevel
    learning_goal: str | None
    lesson: ArchitectureOrientationLessonDraft
    evidence_catalog: list[EvidenceItem] = Field(max_length=40)
    inspection_limitations: list[str] = Field(max_length=6)
    builder_versions: WorkspaceBuilderVersions


class PersistedAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    attempt_id: UUID
    result: dict[str, Any]
    progress: WorkspaceProgressResponse


class ProjectWorkspaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    active_snapshot: SavedInspectionSnapshotResponse | None
    active_content: SavedWorkspaceContentResponse | None
    progress: WorkspaceProgressResponse


class PersistedInspectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    reused: bool
    snapshot: SavedInspectionSnapshotResponse
    progress: WorkspaceProgressResponse


class PersistedContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    content: SavedWorkspaceContentResponse
    progress: WorkspaceProgressResponse


class PersistedActivityPreparationResponse(BaseModel):
    """A public activity definition read from frozen content, never rebuilt."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    content_version_id: UUID
    definition: dict[str, Any]


def normalize_safe_display_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_teaching_source(value: Any) -> Any:
    """Keep learner code intact except for newline transport normalization."""

    if not isinstance(value, str):
        return value
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    for character in normalized:
        if character in {"\n", "\t"}:
            continue
        if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
            raise ValueError("source_code contains an unsafe control character.")
    return normalized


def validate_idempotency_key(value: str | None) -> str:
    if not isinstance(value, str):
        raise ValueError("Idempotency-Key is required.")
    candidate = value.strip()
    if not candidate or len(candidate) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError("Idempotency-Key has an invalid length.")
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in candidate):
        raise ValueError("Idempotency-Key contains unsafe characters.")
    return candidate


def canonical_request_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def serialized_size(value: BaseModel) -> int:
    return len(json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True).encode("utf-8"))
