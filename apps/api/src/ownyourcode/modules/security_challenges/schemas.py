"""Strict HTTP contracts for the FastAPI CORS teaching fixture."""

import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.lessons.schemas import EvidenceItem, LearnerLevel


FASTAPI_CORS_SECURITY_CHALLENGE_ID = "fastapi-cors.v1"
MAX_SECURITY_CHALLENGE_SOURCE_LENGTH = 1_000
SECURITY_CHALLENGE_CONTEXT_ID_LENGTH = 64

SYNTAX_VALID_CHECK_ID = "fastapi-cors.syntax-valid.v1"
FIXTURE_STRUCTURE_CHECK_ID = "fastapi-cors.fixture-structure.v1"
MIDDLEWARE_CONFIGURATION_CHECK_ID = "fastapi-cors.middleware-configuration.v1"
ALLOWED_ORIGIN_CHECK_ID = "fastapi-cors.allowed-origin.v1"
CREDENTIALS_SETTING_CHECK_ID = "fastapi-cors.credentials-setting.v1"
SecurityChallengeCheckId = Literal[
    SYNTAX_VALID_CHECK_ID,
    FIXTURE_STRUCTURE_CHECK_ID,
    MIDDLEWARE_CONFIGURATION_CHECK_ID,
    ALLOWED_ORIGIN_CHECK_ID,
    CREDENTIALS_SETTING_CHECK_ID,
]


class SecurityChallengePrepareRequest(BaseModel):
    """A repository and learner level for one non-persistent challenge preview."""

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


class FastAPICorsSecurityChallengeAvailableResponse(BaseModel):
    """Public metadata for a server-owned CORS teaching fixture."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    available: Literal[True] = True
    message: str = "Security challenge prepared. Nothing was saved."
    security_challenge_id: Literal[FASTAPI_CORS_SECURITY_CHALLENGE_ID] = (
        FASTAPI_CORS_SECURITY_CHALLENGE_ID
    )
    security_challenge_context_id: str = Field(
        min_length=SECURITY_CHALLENGE_CONTEXT_ID_LENGTH,
        max_length=SECURITY_CHALLENGE_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    title: str = Field(min_length=3, max_length=100)
    learning_objective: str = Field(min_length=10, max_length=280)
    instructions: str = Field(min_length=20, max_length=500)
    starter_code: str = Field(
        min_length=1,
        max_length=MAX_SECURITY_CHALLENGE_SOURCE_LENGTH,
    )
    constraints: list[str] = Field(min_length=2, max_length=4)
    relevant_evidence: list[EvidenceItem] = Field(min_length=2, max_length=2)
    maximum_source_length: Literal[MAX_SECURITY_CHALLENGE_SOURCE_LENGTH] = (
        MAX_SECURITY_CHALLENGE_SOURCE_LENGTH
    )
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("constraints", "inspection_limitations")
    @classmethod
    def validate_bounded_texts(cls, values: list[str]) -> list[str]:
        for value in values:
            if not 1 <= len(value) <= 360:
                raise ValueError("Text item has an invalid length.")
        return values


class FastAPICorsSecurityChallengeUnavailableResponse(BaseModel):
    """A normal availability result for an unsupported repository stack."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    available: Literal[False] = False
    message: str = "This security challenge is unavailable for the inspected repository."
    reason: str = Field(min_length=20, max_length=300)
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("inspection_limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        for value in values:
            if not 1 <= len(value) <= 360:
                raise ValueError("Text item has an invalid length.")
        return values


FastAPICorsSecurityChallengePrepareResponse = (
    FastAPICorsSecurityChallengeAvailableResponse
    | FastAPICorsSecurityChallengeUnavailableResponse
)


class SecurityChallengeEvaluationRequest(SecurityChallengePrepareRequest):
    """One bounded learner submission for AST-only CORS fixture verification."""

    security_challenge_context_id: str = Field(
        min_length=SECURITY_CHALLENGE_CONTEXT_ID_LENGTH,
        max_length=SECURITY_CHALLENGE_CONTEXT_ID_LENGTH,
        pattern=r"^[0-9a-f]{64}$",
    )
    source_code: str = Field(min_length=1, max_length=MAX_SECURITY_CHALLENGE_SOURCE_LENGTH)

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


class SecurityChallengeCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SecurityChallengeCheckId
    passed: bool
    message: str = Field(min_length=10, max_length=240)


class SecurityChallengeEvaluationResponse(BaseModel):
    """Deterministic AST verification result with no persistence side effect."""

    model_config = ConfigDict(extra="forbid")

    persisted: Literal[False] = False
    passed: bool
    message: str = (
        "Security challenge evaluated through AST parsing only. Nothing was saved."
    )
    checks: list[SecurityChallengeCheckResult] = Field(min_length=5, max_length=5)
    feedback: list[str] = Field(min_length=1, max_length=3)
    inspection_limitations: list[str] = Field(max_length=6)

    @field_validator("checks")
    @classmethod
    def validate_fixed_check_order(
        cls, values: list[SecurityChallengeCheckResult]
    ) -> list[SecurityChallengeCheckResult]:
        if [check.id for check in values] != [
            SYNTAX_VALID_CHECK_ID,
            FIXTURE_STRUCTURE_CHECK_ID,
            MIDDLEWARE_CONFIGURATION_CHECK_ID,
            ALLOWED_ORIGIN_CHECK_ID,
            CREDENTIALS_SETTING_CHECK_ID,
        ]:
            raise ValueError("Security challenge checks must use the fixed ordered IDs.")
        return values

    @model_validator(mode="after")
    def validate_passed_matches_checks(self) -> "SecurityChallengeEvaluationResponse":
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
