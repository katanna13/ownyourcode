"""Coordinate fresh evidence, one oral-defense evaluation, and no persistence."""

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError, build_evidence_catalog
from ownyourcode.modules.lessons.schemas import EvidenceCatalog, LearnerLevel
from ownyourcode.modules.oral_defenses.definition import (
    OralDefenseDefinition,
    OralDefenseGroundingError,
    build_oral_defense_definition,
    validate_model_evidence,
)
from ownyourcode.modules.oral_defenses.openai_client import OpenAIOralDefenseClient
from ownyourcode.modules.oral_defenses.schemas import (
    OralDefenseAvailableResponse,
    OralDefenseEvaluationRequest,
    OralDefenseEvaluationResponse,
    OralDefensePoints,
    OralDefensePrepareRequest,
    OralDefensePrepareResponse,
    OralDefenseRubricDimension,
    OralDefenseUnavailableResponse,
)
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


class OralDefenseContextStaleError(Exception):
    """Fresh selected evidence no longer matches the displayed question."""


class OralDefenseUnavailableError(Exception):
    """Fewer than two deterministic architecture boundary categories exist."""


class OralDefenseEvidenceError(Exception):
    """Inspection metadata could not safely supply a canonical oral-defense context."""


class ArchitectureOralDefenseService:
    """Prepare a deterministic question and evaluate one answer without storage."""

    def __init__(
        self,
        repository_inspection_service: PublicRepositoryInspectionService,
        openai_client: OpenAIOralDefenseClient,
    ) -> None:
        self._repository_inspection_service = repository_inspection_service
        self._openai_client = openai_client

    def prepare(self, request: OralDefensePrepareRequest) -> OralDefensePrepareResponse:
        inspection, definition = self._fresh_definition(
            request.repository_url,
            request.learner_level,
        )
        if definition is None:
            return OralDefenseUnavailableResponse(
                reason=(
                    "The deterministic inspection must confirm at least two supported "
                    "architecture boundary categories before this oral defense is available."
                ),
                inspection_limitations=inspection.limitations,
            )
        return OralDefenseAvailableResponse(
            oral_defense_context_id=definition.context_id,
            title="Explain the repository boundaries",
            question=definition.question,
            inspection_limitations=inspection.limitations,
        )

    def evaluate(
        self,
        request: OralDefenseEvaluationRequest,
    ) -> OralDefenseEvaluationResponse:
        # Do not perform GitHub work when model configuration cannot evaluate an answer.
        self._openai_client.ensure_configured()
        inspection, definition = self._fresh_definition(
            request.repository_url,
            request.learner_level,
        )
        if definition is None:
            raise OralDefenseUnavailableError()
        if request.oral_defense_context_id != definition.context_id:
            raise OralDefenseContextStaleError()

        evaluation = self._openai_client.evaluate(
            learner_level=request.learner_level,
            question_prompt=definition.question.prompt,
            boundary_evidence=definition.question.boundary_evidence,
            inspection_limitations=inspection.limitations,
            learner_answer=request.answer_text,
        )
        validate_model_evidence(evaluation, definition)
        rubric_dimensions = [
            OralDefenseRubricDimension(
                id=dimension.id,
                earned_points=dimension.earned_points,
                feedback=dimension.feedback,
            )
            for dimension in evaluation.rubric_dimensions
        ]
        earned_points = sum(
            dimension.earned_points for dimension in rubric_dimensions
        )
        return OralDefenseEvaluationResponse(
            oral_defense_points=OralDefensePoints(earned_points=earned_points),
            rubric_dimensions=rubric_dimensions,
            evidence_ids=evaluation.evidence_ids,
            inspection_limitations=inspection.limitations,
        )

    def _fresh_definition(
        self,
        repository_url: str,
        learner_level: LearnerLevel,
    ) -> tuple[RepositoryInspectionResponse, OralDefenseDefinition | None]:
        inspection = self._repository_inspection_service.inspect_url(repository_url)
        try:
            canonical_repository_url = parse_public_github_repository_url(
                inspection.repository.html_url
            ).url
        except ValueError as error:
            raise OralDefenseEvidenceError() from error
        try:
            catalog: EvidenceCatalog = build_evidence_catalog(inspection)
        except EvidenceCatalogError:
            raise
        return inspection, build_oral_defense_definition(
            repository_url=canonical_repository_url,
            learner_level=learner_level,
            catalog=catalog,
        )
