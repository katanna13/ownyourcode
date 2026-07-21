"""Strict contracts for one-at-a-time persisted continuous lessons."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
import unicodedata
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ownyourcode.modules.learning_workspaces.schemas import normalize_teaching_source
from ownyourcode.modules.lessons.schemas import EvidenceItem, validate_evidence_id


CONTINUOUS_LESSON_CONTRACT_VERSION = "continuous-lesson.v1"
CONTINUOUS_LESSON_PROMPT_VERSION = "continuous-lesson-prompt.v1"
CONTINUOUS_EVALUATION_PROMPT_VERSION = "continuous-evaluation-prompt.v1"
MAX_CONTINUOUS_LESSONS_RETURNED = 50

ContinuousLessonFormat = Literal[
    "explain_confirmed_concept",
    "predict_data_flow_outcome",
    "identify_repository_evidence",
    "order_architecture_boundaries",
    "debug_bounded_teaching_fixture",
    "interpret_deterministic_test_output",
    "compare_engineering_tradeoffs",
    "defend_architecture_decision",
    "review_security_configuration",
]
ContinuousActivityType = Literal[
    "evidence_selection",
    "ordering",
    "test_interpretation",
    "ast_fixture",
    "explain_back",
    "trade_off",
]
ContinuousDifficulty = Literal["foundation", "applied", "stretch"]
ContinuousEvaluatorKey = Literal[
    "continuous-evidence-selection.v1",
    "continuous-ordering.v1",
    "continuous-test-interpretation.v1",
    "continuous-fastapi-fixture.v1",
    "continuous-explain-back.v1",
    "continuous-trade-off.v1",
]


class ContinuousChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=240)
    label: str = Field(min_length=1, max_length=240)


class ContinuousPublicActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=3, max_length=96)
    activity_type: ContinuousActivityType
    context_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    prompt: str = Field(min_length=20, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)
    choices: list[ContinuousChoice] = Field(default_factory=list, max_length=4)
    starter_code: str | None = Field(default=None, max_length=1_000)
    constraints: list[str] = Field(default_factory=list, max_length=5)
    maximum_answer_length: int = Field(default=800, ge=40, le=1_000)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Continuous lesson evidence IDs must be unique.")
        return [validate_evidence_id(value) for value in values]


class ContinuousPrivateActivity(BaseModel):
    """Stored answer and evaluator configuration; never returned before submission."""

    model_config = ConfigDict(extra="forbid")

    evaluator_key: ContinuousEvaluatorKey
    expected_choice_id: str | None = Field(default=None, max_length=240)
    expected_order: list[str] = Field(default_factory=list, max_length=4)
    reference_answer: str = Field(min_length=10, max_length=1_000)
    why_correct: str = Field(min_length=20, max_length=700)
    evaluation_rubric: list[str] = Field(default_factory=list, max_length=4)


class ContinuousStoredLessonDefinition(BaseModel):
    """Complete immutable definition stored in an optional-stretch record."""

    model_config = ConfigDict(extra="forbid")

    record_type: Literal[CONTINUOUS_LESSON_CONTRACT_VERSION] = CONTINUOUS_LESSON_CONTRACT_VERSION
    sequence: int = Field(ge=1, le=10_000)
    source_inspection_snapshot_id: UUID
    source_evidence_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    contract_version: Literal[CONTINUOUS_LESSON_CONTRACT_VERSION] = CONTINUOUS_LESSON_CONTRACT_VERSION
    prompt_version: Literal[CONTINUOUS_LESSON_PROMPT_VERSION] = CONTINUOUS_LESSON_PROMPT_VERSION
    lesson_format: ContinuousLessonFormat
    activity_type: ContinuousActivityType
    difficulty: ContinuousDifficulty
    title: str = Field(min_length=3, max_length=100)
    focus: str = Field(min_length=10, max_length=220)
    objective: str = Field(min_length=20, max_length=320)
    explanation: str = Field(min_length=40, max_length=900)
    project_connection: str = Field(min_length=20, max_length=500)
    confirmed_evidence_ids: list[str] = Field(min_length=1, max_length=4)
    illustrative_example: str = Field(min_length=20, max_length=500)
    unknown_or_uninspected: list[str] = Field(min_length=1, max_length=4)
    suggested_next_focus: str = Field(min_length=10, max_length=240)
    public_activity: ContinuousPublicActivity
    private_activity: ContinuousPrivateActivity
    title_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    previous_novelty_fingerprint: str | None = Field(default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    novelty_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    generation_idempotency_key: str = Field(min_length=1, max_length=128)
    generation_request_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @field_validator("confirmed_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Continuous lesson evidence IDs must be unique.")
        return [validate_evidence_id(value) for value in values]


class ContinuousLessonCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=96)
    passed: bool
    message: str = Field(min_length=1, max_length=420)


class ContinuousLessonReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    passed: bool
    earned_points: int | None = Field(default=None, ge=0, le=2)
    submitted_answer: str = Field(min_length=1, max_length=1_000)
    expected_answer: str = Field(min_length=1, max_length=1_000)
    why_correct: str = Field(min_length=20, max_length=700)
    project_connection: str = Field(min_length=20, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)
    feedback: str = Field(min_length=1, max_length=700)
    checks: list[ContinuousLessonCheck] = Field(default_factory=list, max_length=4)
    can_retry: bool


class ContinuousLessonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    sequence: int = Field(ge=1, le=10_000)
    title: str
    focus: str
    lesson_format: ContinuousLessonFormat
    activity_type: ContinuousActivityType
    difficulty: ContinuousDifficulty
    objective: str
    explanation: str
    project_connection: str
    confirmed_evidence_ids: list[str]
    illustrative_example: str
    unknown_or_uninspected: list[str]
    suggested_next_focus: str
    activity: ContinuousPublicActivity
    completed: bool
    created_at: datetime
    completed_at: datetime | None
    review: ContinuousLessonReview | None = None


class ContinuousLearningResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    available: bool
    message: str = "Continue learning from confirmed repository evidence and saved learning history."
    evidence_catalog: list[EvidenceItem] = Field(default_factory=list, max_length=40)
    lessons: list[ContinuousLessonResponse] = Field(default_factory=list, max_length=MAX_CONTINUOUS_LESSONS_RETURNED)
    resume_lesson_id: UUID | None = None


class ContinuousLessonAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    selected_choice_id: str | None = Field(default=None, max_length=240)
    ordered_step_ids: list[str] | None = Field(default=None, max_length=4)
    source_code: str | None = Field(default=None, min_length=1, max_length=1_000)
    answer_text: str | None = Field(default=None, max_length=800)

    @field_validator("source_code", mode="before")
    @classmethod
    def normalize_source(cls, value: Any) -> Any:
        return normalize_teaching_source(value) if value is not None else None

    @field_validator("selected_choice_id")
    @classmethod
    def validate_choice_id(cls, value: str | None) -> str | None:
        return validate_evidence_id(value) if value is not None else None

    @field_validator("ordered_step_ids")
    @classmethod
    def validate_step_ids(cls, values: list[str] | None) -> list[str] | None:
        return [validate_evidence_id(value) for value in values] if values is not None else None

    @field_validator("answer_text", mode="before")
    @classmethod
    def normalize_answer_newlines(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return value.replace("\r\n", "\n").replace("\r", "\n")

    @field_validator("answer_text")
    @classmethod
    def validate_answer(cls, value: str | None) -> str | None:
        if value is not None:
            for character in value:
                if character in {"\n", "\t"}:
                    continue
                if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
                    raise ValueError("answer_text contains an unsafe control character.")
            if len(value.strip()) < 40:
                raise ValueError("Explain-back answers must contain at least 40 meaningful characters.")
        return value


class ContinuousLessonAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[True] = True
    lesson: ContinuousLessonResponse


class DraftChoiceActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_type: Literal["test_interpretation"]
    prompt: str = Field(min_length=20, max_length=500)
    choices: list[str] = Field(min_length=2, max_length=4)
    correct_choice_index: int = Field(ge=0, le=3)
    reference_answer: str = Field(min_length=10, max_length=500)
    why_correct: str = Field(min_length=20, max_length=700)


class DraftEvidenceActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_type: Literal["evidence_selection"]
    prompt: str = Field(min_length=20, max_length=500)
    choice_evidence_ids: list[str] = Field(min_length=2, max_length=4)
    correct_evidence_id: str = Field(min_length=1, max_length=240)
    why_correct: str = Field(min_length=20, max_length=700)


class DraftOrderingActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_type: Literal["ordering"]
    prompt: str = Field(min_length=20, max_length=500)
    steps_in_expected_order: list[str] = Field(min_length=2, max_length=4)
    why_correct: str = Field(min_length=20, max_length=700)


class DraftTextActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_type: Literal["explain_back", "trade_off"]
    prompt: str = Field(min_length=20, max_length=500)
    reference_answer: str = Field(min_length=40, max_length=800)
    why_correct: str = Field(min_length=20, max_length=700)
    evaluation_rubric: list[str] = Field(min_length=2, max_length=4)


class DraftAstActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_type: Literal["ast_fixture"]
    prompt: str = Field(min_length=20, max_length=500)


DraftActivity = Annotated[
    DraftChoiceActivity | DraftEvidenceActivity | DraftOrderingActivity | DraftTextActivity | DraftAstActivity,
    Field(discriminator="activity_type"),
]


class ContinuousLessonDraft(BaseModel):
    """Bounded structured generation output; private answers are frozen server-side."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=100)
    focus: str = Field(min_length=10, max_length=220)
    objective: str = Field(min_length=20, max_length=320)
    explanation: str = Field(min_length=40, max_length=900)
    project_connection: str = Field(min_length=20, max_length=500)
    confirmed_evidence_ids: list[str] = Field(min_length=1, max_length=4)
    illustrative_example: str = Field(min_length=20, max_length=500)
    unknown_or_uninspected: list[str] = Field(min_length=1, max_length=4)
    suggested_next_focus: str = Field(min_length=10, max_length=240)
    activity: DraftActivity


class ContinuousTextEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: Literal[0, 1, 2]
    feedback: str = Field(min_length=20, max_length=600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=4)
