"""Coordinate deterministic inspection and one bounded lesson model call."""

from ownyourcode.modules.lessons.evidence import (
    build_evidence_catalog,
    validate_lesson_evidence,
)
from ownyourcode.modules.lessons.openai_client import OpenAILessonClient
from ownyourcode.modules.lessons.schemas import (
    LessonGenerationRequest,
    LessonGenerationResponse,
)
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


class LessonGenerationService:
    """Generate a teaching preview without storing a project or lesson."""

    def __init__(
        self,
        repository_inspection_service: PublicRepositoryInspectionService,
        openai_client: OpenAILessonClient,
    ) -> None:
        self._repository_inspection_service = repository_inspection_service
        self._openai_client = openai_client

    def generate(self, request: LessonGenerationRequest) -> LessonGenerationResponse:
        # This check deliberately precedes GitHub inspection so invalid server setup
        # cannot cause an unnecessary external API request.
        self._openai_client.ensure_configured()
        inspection = self._repository_inspection_service.inspect_url(request.repository_url)
        catalog = build_evidence_catalog(inspection)
        lesson = self._openai_client.generate(request, catalog)
        validate_lesson_evidence(lesson, catalog)
        return LessonGenerationResponse(
            inspection_limitations=inspection.limitations,
            evidence_catalog=catalog.items,
            lesson=lesson,
        )
