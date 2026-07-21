"""Freeze the current bounded activity definitions for saved workspaces."""

from __future__ import annotations

from ownyourcode.modules.assessments.definition import build_assessment_definition
from ownyourcode.modules.assessments.schemas import (
    ASSESSMENT_DEFINITION_VERSION,
    EXPLAIN_BACK_RUBRIC_VERSION,
    AssessmentQuestionsResponse,
)
from ownyourcode.modules.labs.schemas import (
    FastAPIHealthCheckLabAvailableResponse,
    FastAPIHealthCheckLabPrepareResponse,
    FastAPIHealthCheckLabUnavailableResponse,
)
from ownyourcode.modules.labs.service import (
    _lab_context_fingerprint,
    _relevant_evidence as lab_relevant_evidence,
)
from ownyourcode.modules.labs.verifier import (
    AST_HEALTH_CHECK_VERIFIER_VERSION,
    FASTAPI_HEALTH_CHECK_FIXTURE_VERSION,
    STARTER_CODE as LAB_STARTER_CODE,
)
from ownyourcode.modules.learning_workspaces.schemas import (
    LESSON_BUILDER_CONTRACT_VERSION,
    PrivateAssessmentDefinition,
    StoredWorkspaceDefinition,
    WorkspaceBuilderVersions,
)
from ownyourcode.modules.lessons.schemas import (
    ArchitectureOrientationLessonDraft,
    EvidenceCatalog,
    LearnerLevel,
)
from ownyourcode.modules.oral_defenses.definition import build_oral_defense_definition
from ownyourcode.modules.oral_defenses.schemas import (
    OralDefenseAvailableResponse,
    OralDefensePrepareResponse,
    OralDefenseUnavailableResponse,
)
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse
from ownyourcode.modules.security_challenges.schemas import (
    FastAPICorsSecurityChallengeAvailableResponse,
    FastAPICorsSecurityChallengePrepareResponse,
    FastAPICorsSecurityChallengeUnavailableResponse,
)
from ownyourcode.modules.security_challenges.service import (
    _challenge_context_fingerprint,
    _relevant_evidence as security_relevant_evidence,
)
from ownyourcode.modules.security_challenges.verifier import (
    AST_FASTAPI_CORS_VERIFIER_VERSION,
    FASTAPI_CORS_FIXTURE_VERSION,
    REQUIRED_ALLOWED_ORIGIN,
    STARTER_CODE as SECURITY_STARTER_CODE,
)


def build_frozen_workspace_definition(
    *,
    inspection: RepositoryInspectionResponse,
    catalog: EvidenceCatalog,
    source_inspection_fingerprint: str,
    learner_level: LearnerLevel,
    learning_goal: str | None,
    lesson: ArchitectureOrientationLessonDraft,
) -> StoredWorkspaceDefinition:
    """Build once, validate once, then persist this exact workspace definition."""

    repository_url = inspection.repository.html_url
    assessment = build_assessment_definition(
        repository_url=repository_url,
        learner_level=learner_level,
        catalog=catalog,
    )
    assessment_public = AssessmentQuestionsResponse(
        assessment_context_id=assessment.context_id,
        inspection_limitations=inspection.limitations,
        questions=assessment.questions,
    )
    lab_definition = _build_lab_definition(
        inspection=inspection,
        catalog=catalog,
        repository_url=repository_url,
        learner_level=learner_level,
    )
    security_definition = _build_security_definition(
        inspection=inspection,
        catalog=catalog,
        repository_url=repository_url,
        learner_level=learner_level,
    )
    oral_definition = _build_oral_definition(
        inspection=inspection,
        catalog=catalog,
        repository_url=repository_url,
        learner_level=learner_level,
    )

    def ids_from_available(definition: object) -> list[str]:
        relevant = getattr(definition, "relevant_evidence", None)
        if isinstance(relevant, list):
            return [item.id for item in relevant]
        question = getattr(definition, "question", None)
        boundaries = getattr(question, "boundary_evidence", None)
        if isinstance(boundaries, list):
            return [item.evidence.id for item in boundaries]
        return []

    assessment_ids = [assessment.target_evidence.id]
    for question in assessment.questions:
        choices = getattr(question, "evidence_choices", None)
        if isinstance(choices, list):
            assessment_ids.extend(choice.id for choice in choices)

    return StoredWorkspaceDefinition(
        source_inspection_fingerprint=source_inspection_fingerprint,
        learner_level=learner_level,
        learning_goal=learning_goal,
        lesson=lesson,
        assessment_public_definition=assessment_public,
        assessment_private_definition=PrivateAssessmentDefinition(
            multiple_choice_correct_option_id=assessment.multiple_choice_correct_option_id,
            evidence_selection_correct_id=assessment.evidence_selection_correct_id,
            target_evidence_id=assessment.target_evidence.id,
        ),
        verified_lab_definition=lab_definition,
        security_challenge_definition=security_definition,
        oral_defense_definition=oral_definition,
        activity_evidence_ids={
            "assessment": list(dict.fromkeys(assessment_ids)),
            "verified_lab": ids_from_available(lab_definition),
            "security_challenge": ids_from_available(security_definition),
            "oral_defense": ids_from_available(oral_definition),
        },
        builder_versions=WorkspaceBuilderVersions(
            lesson=LESSON_BUILDER_CONTRACT_VERSION,
            assessment=ASSESSMENT_DEFINITION_VERSION,
            assessment_rubric=EXPLAIN_BACK_RUBRIC_VERSION,
            verified_lab=(
                f"{FASTAPI_HEALTH_CHECK_FIXTURE_VERSION}:{AST_HEALTH_CHECK_VERIFIER_VERSION}"
            ),
            security_challenge=(
                f"{FASTAPI_CORS_FIXTURE_VERSION}:{AST_FASTAPI_CORS_VERIFIER_VERSION}"
            ),
            oral_defense="architecture-boundaries-question.v1:architecture-boundaries-rubric.v1",
        ),
    )


def _build_lab_definition(
    *,
    inspection: RepositoryInspectionResponse,
    catalog: EvidenceCatalog,
    repository_url: str,
    learner_level: LearnerLevel,
) -> FastAPIHealthCheckLabPrepareResponse:
    relevant = lab_relevant_evidence(catalog)
    if relevant is None:
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
            learner_level=learner_level.value,
            relevant_evidence=relevant,
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
        starter_code=LAB_STARTER_CODE,
        constraints=[
            "Keep exactly one healthz function with one return statement.",
            "Return a literal dictionary with the required status and service fields.",
            "Imports, calls, extra functions, and unrelated syntax are not accepted.",
        ],
        relevant_evidence=relevant,
        inspection_limitations=inspection.limitations,
    )


def _build_security_definition(
    *,
    inspection: RepositoryInspectionResponse,
    catalog: EvidenceCatalog,
    repository_url: str,
    learner_level: LearnerLevel,
) -> FastAPICorsSecurityChallengePrepareResponse:
    relevant = security_relevant_evidence(catalog)
    if relevant is None:
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
            learner_level=learner_level.value,
            relevant_evidence=relevant,
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
        starter_code=SECURITY_STARTER_CODE,
        constraints=[
            "Keep exactly the four server-owned fixture statements in their required order.",
            "Use a one-item literal allow_origins list with the required explicit origin.",
            "Keep allow_credentials as the literal boolean True.",
            "Do not add imports, calls, functions, or other configuration.",
        ],
        relevant_evidence=relevant,
        inspection_limitations=inspection.limitations,
    )


def _build_oral_definition(
    *,
    inspection: RepositoryInspectionResponse,
    catalog: EvidenceCatalog,
    repository_url: str,
    learner_level: LearnerLevel,
) -> OralDefensePrepareResponse:
    definition = build_oral_defense_definition(
        repository_url=repository_url,
        learner_level=learner_level,
        catalog=catalog,
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
