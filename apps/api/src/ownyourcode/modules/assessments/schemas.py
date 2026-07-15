"""Strict contracts for the architecture-orientation assessment."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.lessons.schemas import LearnerLevel, validate_evidence_id


ASSESSMENT_DEFINITION_VERSION = "architecture-orientation-assessment.v1"
EXPLAIN_BACK_RUBRIC_VERSION = "explain-back-rubric.v1"
MULTIPLE_CHOICE_QUESTION_ID = "architecture-orientation.mcq.statement.v1"
EVIDENCE_SELECTION_QUESTION_ID = (
    "architecture-orientation.evidence.direct-support.v1"
)
EXPLAIN_BACK_QUESTION_ID = "architecture-orientation.explain-back.evidence-limitation.v1"

MAX_CONTEXT_ID_LENGTH = 64
MAX_EXPLAIN_BACK_ANSWER_LENGTH = 600

MultipleChoiceOptionId = Literal[
    "option-a",
    "option-b",
    "option-c",
    "option-d",
]


class AssessmentQuestionsRequest(BaseModel):
    """Learner input used to prepare a non-persistent question preview."""

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


class AssessmentEvidenceChoice(BaseModel):
    """A small learner-visible subset of deterministic catalog evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=240)
    label: str = Field(min_length=1, max_length=240)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_evidence_id(value)


class MultipleChoiceOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: MultipleChoiceOptionId
    label: str = Field(min_length=10, max_length=280)


class MultipleChoiceQuestion(BaseModel):
    """A public question definition intentionally without a correct-answer field."""

    model_config = ConfigDict(extra="forbid")

    id: Literal[MULTIPLE_CHOICE_QUESTION_ID]
    type: Literal["multiple_choice"]
    prompt: str = Field(min_length=20, max_length=360)
    options: list[MultipleChoiceOption] = Field(min_length=4, max_length=4)

    @field_validator("options")
    @classmethod
    def validate_option_ids(cls, values: list[MultipleChoiceOption]) -> list[MultipleChoiceOption]:
        expected = {
            "option-a",
            "option-b",
            "option-c",
            "option-d",
        }
        if {option.id for option in values} != expected or len(
            {option.id for option in values}
        ) != len(values):
            raise ValueError("Multiple-choice options must use the fixed allowed IDs.")
        return values


class EvidenceSelectionQuestion(BaseModel):
    """A one-choice question; server-side state retains its single answer key."""

    model_config = ConfigDict(extra="forbid")

    id: Literal[EVIDENCE_SELECTION_QUESTION_ID]
    type: Literal["evidence_selection"]
    prompt: str = Field(min_length=20, max_length=360)
    evidence_choices: list[AssessmentEvidenceChoice] = Field(min_length=1, max_length=4)

    @field_validator("evidence_choices")
    @classmethod
    def validate_unique_choices(
        cls, values: list[AssessmentEvidenceChoice]
    ) -> list[AssessmentEvidenceChoice]:
        _validate_unique_evidence_ids([choice.id for choice in values])
        return values


class ExplainBackQuestion(BaseModel):
    """A bounded free-text question with a restricted evidence-choice set."""

    model_config = ConfigDict(extra="forbid")

    id: Literal[EXPLAIN_BACK_QUESTION_ID]
    type: Literal["explain_back"]
    prompt: str = Field(min_length=20, max_length=420)
    evidence_choices: list[AssessmentEvidenceChoice] = Field(min_length=1, max_length=4)

    @field_validator("evidence_choices")
    @classmethod
    def validate_unique_choices(
        cls, values: list[AssessmentEvidenceChoice]
    ) -> list[AssessmentEvidenceChoice]:
        _validate_unique_evidence_ids([choice.id for choice in values])
        return values


AssessmentQuestion = (
    MultipleChoiceQuestion | EvidenceSelectionQuestion | ExplainBackQuestion
)


class AssessmentQuestionsResponse(BaseModel):
    """Questions are previews: no answer key or assessment state is persisted."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    message: str = "Assessment questions prepared. Nothing was saved."
    assessment_context_id: str = Field(
        min_length=MAX_CONTEXT_ID_LENGTH,
        max_length=MAX_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    inspection_limitations: list[str] = Field(max_length=6)
    questions: list[AssessmentQuestion] = Field(min_length=3, max_length=3)

    @field_validator("inspection_limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return _validate_bounded_texts(values, minimum_length=1, maximum_length=360)

    @field_validator("questions")
    @classmethod
    def validate_fixed_question_set(
        cls, values: list[AssessmentQuestion]
    ) -> list[AssessmentQuestion]:
        if {question.id for question in values} != {
            MULTIPLE_CHOICE_QUESTION_ID,
            EVIDENCE_SELECTION_QUESTION_ID,
            EXPLAIN_BACK_QUESTION_ID,
        }:
            raise ValueError("Assessment must contain the three fixed question IDs.")
        return values


class MultipleChoiceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Literal[MULTIPLE_CHOICE_QUESTION_ID]
    selected_option_id: MultipleChoiceOptionId


class EvidenceSelectionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Literal[EVIDENCE_SELECTION_QUESTION_ID]
    selected_evidence_id: str = Field(min_length=1, max_length=240)

    @field_validator("selected_evidence_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_evidence_id(value)


class ExplainBackAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Literal[EXPLAIN_BACK_QUESTION_ID]
    answer_text: str = Field(min_length=20, max_length=MAX_EXPLAIN_BACK_ANSWER_LENGTH)
    evidence_ids: list[str] = Field(min_length=1, max_length=2)

    @field_validator("answer_text")
    @classmethod
    def require_nonblank_answer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Explain-back answer cannot be blank.")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def validate_ids(cls, values: list[str]) -> list[str]:
        _validate_unique_evidence_ids(values)
        return values


class AssessmentAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    multiple_choice: MultipleChoiceAnswer
    evidence_selection: EvidenceSelectionAnswer
    explain_back: ExplainBackAnswer


class AssessmentEvaluationRequest(AssessmentQuestionsRequest):
    """Answers for a freshly recomputed, non-persistent assessment definition."""

    assessment_context_id: str = Field(
        min_length=MAX_CONTEXT_ID_LENGTH,
        max_length=MAX_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    answers: AssessmentAnswers


class ExplainBackEvaluation(BaseModel):
    """The only score a model may return: free-text explanation quality."""

    model_config = ConfigDict(extra="forbid")

    earned_points: Literal[0, 1, 2]
    feedback: str = Field(min_length=20, max_length=360)


class DeterministicFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Literal[
        MULTIPLE_CHOICE_QUESTION_ID, EVIDENCE_SELECTION_QUESTION_ID
    ]
    earned_points: Literal[0, 1]
    max_points: Literal[1] = 1
    message: str = Field(min_length=20, max_length=360)


class AssessmentScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    earned_points: int = Field(ge=0, le=4)
    total_points: Literal[4] = 4


class ExplainBackFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Literal[EXPLAIN_BACK_QUESTION_ID]
    earned_points: Literal[0, 1, 2]
    max_points: Literal[2] = 2
    feedback: str = Field(min_length=20, max_length=360)


class AssessmentEvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    message: str = "Assessment evaluated. Nothing was saved."
    score: AssessmentScore
    feedback: list[DeterministicFeedback] = Field(min_length=2, max_length=2)
    explain_back_feedback: ExplainBackFeedback
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("inspection_limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        return _validate_bounded_texts(values, minimum_length=1, maximum_length=360)


def _validate_unique_evidence_ids(values: list[str]) -> list[str]:
    validated_values = [validate_evidence_id(value) for value in values]
    if len(set(validated_values)) != len(validated_values):
        raise ValueError("Evidence IDs cannot be duplicated in one answer.")
    return validated_values


def _validate_bounded_texts(
    values: list[str], *, minimum_length: int, maximum_length: int
) -> list[str]:
    for value in values:
        if not minimum_length <= len(value) <= maximum_length:
            raise ValueError("Text item has an invalid length.")
    return values
