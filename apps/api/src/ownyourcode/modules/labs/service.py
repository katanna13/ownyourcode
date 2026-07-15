"""Reinspect deterministic evidence and verify one fixed teaching fixture."""

import hashlib
import json

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.labs.schemas import (
    FastAPIHealthCheckLabAvailableResponse,
    FastAPIHealthCheckLabPrepareResponse,
    FastAPIHealthCheckLabUnavailableResponse,
    LabEvaluationRequest,
    LabEvaluationResponse,
    LabPrepareRequest,
)
from ownyourcode.modules.labs.verifier import (
    AST_HEALTH_CHECK_VERIFIER_VERSION,
    FASTAPI_HEALTH_CHECK_FIXTURE_VERSION,
    STARTER_CODE,
    verify_fastapi_health_check,
)
from ownyourcode.modules.lessons.evidence import (
    EvidenceCatalogError,
    build_evidence_catalog,
)
from ownyourcode.modules.lessons.schemas import EvidenceCatalog, EvidenceItem
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


class LabContextStaleError(Exception):
    """The fresh deterministic evidence no longer matches the prepared lab."""


class LabUnavailableError(Exception):
    """The supported deterministic Python/FastAPI evidence is absent."""


class LabEvidenceError(Exception):
    """Inspection metadata could not safely supply a canonical lab context."""


class FastAPIHealthCheckLabService:
    """Prepare and verify the fixed fixture without storing or executing code."""

    def __init__(
        self, repository_inspection_service: PublicRepositoryInspectionService
    ) -> None:
        self._repository_inspection_service = repository_inspection_service

    def prepare(
        self, request: LabPrepareRequest
    ) -> FastAPIHealthCheckLabPrepareResponse:
        inspection, catalog, repository_url = self._fresh_catalog(request.repository_url)
        relevant_evidence = _relevant_evidence(catalog)
        if relevant_evidence is None:
            return FastAPIHealthCheckLabUnavailableResponse(
                reason=(
                    "The deterministic inspection must confirm both Python and FastAPI "
                    "before this teaching fixture is available."
                ),
                inspection_limitations=inspection.limitations,
            )
        return FastAPIHealthCheckLabAvailableResponse(
            lab_context_id=_lab_context_fingerprint(
                repository_url=repository_url,
                learner_level=request.learner_level.value,
                relevant_evidence=relevant_evidence,
            ),
            title="FastAPI-style health check",
            learning_objective=(
                "Practice returning a predictable literal health-check response for a "
                "Python and FastAPI-oriented stack."
            ),
            instructions=(
                "This server-owned teaching fixture is not source code from the "
                "inspected repository. Edit the small healthz function, then submit "
                "it for AST-only verification; no server is run."
            ),
            starter_code=STARTER_CODE,
            constraints=[
                "Keep exactly one healthz function with one return statement.",
                "Return a literal dictionary with the required status and service fields.",
                "Imports, calls, extra functions, and unrelated syntax are not accepted.",
            ],
            relevant_evidence=relevant_evidence,
            inspection_limitations=inspection.limitations,
        )

    def evaluate(self, request: LabEvaluationRequest) -> LabEvaluationResponse:
        inspection, catalog, repository_url = self._fresh_catalog(request.repository_url)
        relevant_evidence = _relevant_evidence(catalog)
        if relevant_evidence is None:
            raise LabUnavailableError()
        expected_context_id = _lab_context_fingerprint(
            repository_url=repository_url,
            learner_level=request.learner_level.value,
            relevant_evidence=relevant_evidence,
        )
        if request.lab_context_id != expected_context_id:
            raise LabContextStaleError()

        verification = verify_fastapi_health_check(request.source_code)
        return LabEvaluationResponse(
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
            raise LabEvidenceError() from error
        try:
            catalog = build_evidence_catalog(inspection)
        except EvidenceCatalogError:
            raise
        return inspection, catalog, canonical_repository_url


def _relevant_evidence(catalog: EvidenceCatalog) -> list[EvidenceItem] | None:
    """Use exact server-owned catalog IDs, never labels or detail text."""

    by_id = {item.id: item for item in catalog.items}
    python_evidence = by_id.get("language:python") or by_id.get("technology:python")
    fastapi_evidence = by_id.get("technology:fastapi")
    if python_evidence is None or fastapi_evidence is None:
        return None
    return [python_evidence, fastapi_evidence]


def _lab_context_fingerprint(
    *, repository_url: str, learner_level: str, relevant_evidence: list[EvidenceItem]
) -> str:
    canonical_context = {
        "fixture_version": FASTAPI_HEALTH_CHECK_FIXTURE_VERSION,
        "learner_level": learner_level,
        "relevant_evidence": [item.model_dump(mode="json") for item in relevant_evidence],
        "repository_url": repository_url,
        "verifier_version": AST_HEALTH_CHECK_VERIFIER_VERSION,
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
        return ["Your healthz teaching fixture matches the required deterministic response."]
    return [
        "This lab parses the submitted fixture but never runs it.",
        "Use one healthz function that returns the required literal response fields.",
    ]
