"""Strict HTTP contracts for the FastAPI health-check teaching fixture."""

import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.lessons.schemas import EvidenceItem, LearnerLevel


FASTAPI_HEALTH_CHECK_LAB_ID = "fastapi-health-check.v1"
MAX_LAB_SOURCE_LENGTH = 1_000
LAB_CONTEXT_ID_LENGTH = 64

SYNTAX_VALID_CHECK_ID = "syntax-valid.v1"
RESTRICTED_STRUCTURE_CHECK_ID = "restricted-structure.v1"
LITERAL_RESPONSE_DICTIONARY_CHECK_ID = "literal-response-dictionary.v1"
HEALTH_CHECK_CONTRACT_CHECK_ID = "health-check-contract.v1"
LabCheckId = Literal[
    SYNTAX_VALID_CHECK_ID,
    RESTRICTED_STRUCTURE_CHECK_ID,
    LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
    HEALTH_CHECK_CONTRACT_CHECK_ID,
]


class LabPrepareRequest(BaseModel):
    """A repository and learner level for one non-persistent lab preview."""

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


class FastAPIHealthCheckLabAvailableResponse(BaseModel):
    """Public fixture metadata, intentionally separate from repository source."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    available: Literal[True] = True
    message: str = "Verified lab prepared. Nothing was saved."
    lab_id: Literal[FASTAPI_HEALTH_CHECK_LAB_ID] = FASTAPI_HEALTH_CHECK_LAB_ID
    lab_context_id: str = Field(
        min_length=LAB_CONTEXT_ID_LENGTH,
        max_length=LAB_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    title: str = Field(min_length=3, max_length=100)
    learning_objective: str = Field(min_length=10, max_length=280)
    instructions: str = Field(min_length=20, max_length=500)
    starter_code: str = Field(min_length=1, max_length=MAX_LAB_SOURCE_LENGTH)
    constraints: list[str] = Field(min_length=2, max_length=4)
    relevant_evidence: list[EvidenceItem] = Field(min_length=2, max_length=2)
    maximum_source_length: Literal[MAX_LAB_SOURCE_LENGTH] = MAX_LAB_SOURCE_LENGTH
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("constraints", "inspection_limitations")
    @classmethod
    def validate_bounded_texts(cls, values: list[str]) -> list[str]:
        for value in values:
            if not 1 <= len(value) <= 360:
                raise ValueError("Text item has an invalid length.")
        return values


class FastAPIHealthCheckLabUnavailableResponse(BaseModel):
    """A normal availability result, not an error, for unsupported stacks."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    available: Literal[False] = False
    message: str = "This lab is unavailable for the inspected repository."
    reason: str = Field(min_length=20, max_length=300)
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("inspection_limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        for value in values:
            if not 1 <= len(value) <= 360:
                raise ValueError("Text item has an invalid length.")
        return values


FastAPIHealthCheckLabPrepareResponse = (
    FastAPIHealthCheckLabAvailableResponse | FastAPIHealthCheckLabUnavailableResponse
)


class LabEvaluationRequest(LabPrepareRequest):
    """One bounded learner submission for AST-only verification."""

    lab_context_id: str = Field(
        min_length=LAB_CONTEXT_ID_LENGTH,
        max_length=LAB_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    source_code: str = Field(min_length=1, max_length=MAX_LAB_SOURCE_LENGTH)

    @field_validator("source_code", mode="before")
    @classmethod
    def normalize_source_code(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        for character in normalized:
            if character in {"\n", "\t"}:
                continue
            if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
                raise ValueError("source_code contains an unsafe control character.")
        return normalized


class LabCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: LabCheckId
    passed: bool
    message: str = Field(min_length=10, max_length=240)


class LabEvaluationResponse(BaseModel):
    """Deterministic AST verification result with no persistence side effect."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    passed: bool
    message: str = "Lab evaluated through AST parsing only. Nothing was saved."
    checks: list[LabCheckResult] = Field(min_length=4, max_length=4)
    feedback: list[str] = Field(min_length=1, max_length=3)
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("checks")
    @classmethod
    def validate_fixed_check_order(cls, values: list[LabCheckResult]) -> list[LabCheckResult]:
        if [check.id for check in values] != [
            SYNTAX_VALID_CHECK_ID,
            RESTRICTED_STRUCTURE_CHECK_ID,
            LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
            HEALTH_CHECK_CONTRACT_CHECK_ID,
        ]:
            raise ValueError("Lab checks must use the fixed ordered IDs.")
        return values

    @model_validator(mode="after")
    def validate_passed_matches_checks(self) -> "LabEvaluationResponse":
        if self.passed != all(check.passed for check in self.checks):
            raise ValueError("passed must match the deterministic check results.")
        return self

    @field_validator("feedback", "inspection_limitations")
    @classmethod
    def validate_bounded_texts(cls, values: list[str]) -> list[str]:
        for value in values:
            if not 1 <= len(value) <= 360:
                raise ValueError("Text item has an invalid length.")
        return values
