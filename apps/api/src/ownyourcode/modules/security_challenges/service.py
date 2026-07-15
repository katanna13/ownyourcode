"""Prepare and verify one server-owned FastAPI CORS teaching challenge."""

import hashlib
import json

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError, build_evidence_catalog
from ownyourcode.modules.lessons.schemas import EvidenceCatalog, EvidenceItem
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService
from ownyourcode.modules.security_challenges.schemas import (
    FastAPICorsSecurityChallengeAvailableResponse,
    FastAPICorsSecurityChallengePrepareResponse,
    FastAPICorsSecurityChallengeUnavailableResponse,
    SecurityChallengeEvaluationRequest,
    SecurityChallengeEvaluationResponse,
    SecurityChallengePrepareRequest,
)
from ownyourcode.modules.security_challenges.verifier import (
    AST_FASTAPI_CORS_VERIFIER_VERSION,
    FASTAPI_CORS_FIXTURE_VERSION,
    REQUIRED_ALLOWED_ORIGIN,
    STARTER_CODE,
    verify_fastapi_cors_fixture,
)


class SecurityChallengeContextStaleError(Exception):
    """Fresh deterministic evidence no longer matches the prepared challenge."""


class SecurityChallengeUnavailableError(Exception):
    """The required deterministic Python/FastAPI evidence is absent."""


class SecurityChallengeEvidenceError(Exception):
    """Inspection metadata could not safely supply a canonical context."""


class FastAPICorsSecurityChallengeService:
    """Reinspect stack evidence and verify the fixture without executing code."""

    def __init__(
        self, repository_inspection_service: PublicRepositoryInspectionService
    ) -> None:
        self._repository_inspection_service = repository_inspection_service

    def prepare(
        self,
        request: SecurityChallengePrepareRequest,
    ) -> FastAPICorsSecurityChallengePrepareResponse:
        inspection, catalog, repository_url = self._fresh_catalog(request.repository_url)
        relevant_evidence = _relevant_evidence(catalog)
        if relevant_evidence is None:
            return FastAPICorsSecurityChallengeUnavailableResponse(
                reason=(
                    "The deterministic inspection must confirm both Python and FastAPI "
                    "before this CORS teaching challenge is available."
                ),
                inspection_limitations=inspection.limitations,
            )
        return FastAPICorsSecurityChallengeAvailableResponse(
            security_challenge_context_id=_challenge_context_fingerprint(
                repository_url=repository_url,
                learner_level=request.learner_level.value,
                relevant_evidence=relevant_evidence,
            ),
            title="Fix a permissive CORS policy",
            learning_objective=(
                "Practice restricting a FastAPI CORS policy to one explicit "
                "development origin."
            ),
            instructions=(
                "This server-owned teaching fixture is not source code from the "
                "inspected repository. Replace its wildcard origin with the required "
                f"literal origin {REQUIRED_ALLOWED_ORIGIN!r}. The submitted source is "
                "parsed structurally and never run. This teaches one CORS concept; it "
                "does not scan the repository or prove a production-ready configuration."
            ),
            starter_code=STARTER_CODE,
            constraints=[
                "Keep exactly the four server-owned fixture statements in their required order.",
                "Use a one-item literal allow_origins list with the required explicit origin.",
                "Keep allow_credentials as the literal boolean True.",
                "Do not add imports, calls, functions, or other configuration.",
            ],
            relevant_evidence=relevant_evidence,
            inspection_limitations=inspection.limitations,
        )

    def evaluate(
        self,
        request: SecurityChallengeEvaluationRequest,
    ) -> SecurityChallengeEvaluationResponse:
        inspection, catalog, repository_url = self._fresh_catalog(request.repository_url)
        relevant_evidence = _relevant_evidence(catalog)
        if relevant_evidence is None:
            raise SecurityChallengeUnavailableError()
        expected_context_id = _challenge_context_fingerprint(
            repository_url=repository_url,
            learner_level=request.learner_level.value,
            relevant_evidence=relevant_evidence,
        )
        if request.security_challenge_context_id != expected_context_id:
            raise SecurityChallengeContextStaleError()

        verification = verify_fastapi_cors_fixture(request.source_code)
        return SecurityChallengeEvaluationResponse(
            passed=verification.passed,
            checks=verification.checks,
            feedback=_feedback_for_verification(verification.passed),
            inspection_limitations=inspection.limitations,
        )

    def _fresh_catalog(
        self, repository_url: str
    ) -> tuple[RepositoryInspectionResponse, EvidenceCatalog, str]:
        inspection = self._repository_inspection_service.inspect_url(repository_url)
        try:
            canonical_repository_url = parse_public_github_repository_url(
                inspection.repository.html_url
            ).url
        except ValueError as error:
            raise SecurityChallengeEvidenceError() from error
        try:
            catalog = build_evidence_catalog(inspection)
        except EvidenceCatalogError:
            raise
        return inspection, catalog, canonical_repository_url


def _relevant_evidence(catalog: EvidenceCatalog) -> list[EvidenceItem] | None:
    """Use exact deterministic identities, never repository-controlled display text."""

    by_id = {item.id: item for item in catalog.items}
    python_evidence = by_id.get("language:python") or by_id.get("technology:python")
    fastapi_evidence = by_id.get("technology:fastapi")
    if python_evidence is None or fastapi_evidence is None:
        return None
    return [python_evidence, fastapi_evidence]


def _challenge_context_fingerprint(
    *, repository_url: str, learner_level: str, relevant_evidence: list[EvidenceItem]
) -> str:
    """Hash freshness values only; this is not authentication or authorization."""

    canonical_context = {
        "fixture_version": FASTAPI_CORS_FIXTURE_VERSION,
        "learner_level": learner_level,
        "relevant_evidence": [item.model_dump(mode="json") for item in relevant_evidence],
        "repository_url": repository_url,
        "required_allowed_origin": REQUIRED_ALLOWED_ORIGIN,
        "verifier_version": AST_FASTAPI_CORS_VERIFIER_VERSION,
    }
    serialized = json.dumps(
        canonical_context,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _feedback_for_verification(passed: bool) -> list[str]:
    if passed:
        return [
            "Your teaching fixture restricts the CORS origin to the required explicit value."
        ]
    return [
        "This challenge parses the submitted fixture but never runs it.",
        "Use only the required server-owned fixture structure and literal CORS settings.",
    ]
