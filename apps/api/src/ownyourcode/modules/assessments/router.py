"""HTTP boundary for preview-only repository-orientation assessment."""

from fastapi import APIRouter, HTTPException

from ownyourcode.core.config import get_settings
from ownyourcode.modules.assessments.openai_client import (
    AssessmentConfigurationError,
    AssessmentIncompleteError,
    AssessmentProviderError,
    AssessmentRateLimitedError,
    AssessmentRefusalError,
    AssessmentTimeoutError,
    OpenAIAssessmentClient,
)
from ownyourcode.modules.assessments.schemas import (
    AssessmentEvaluationRequest,
    AssessmentEvaluationResponse,
    AssessmentQuestionsRequest,
    AssessmentQuestionsResponse,
)
from ownyourcode.modules.assessments.service import (
    ArchitectureOrientationAssessmentService,
    AssessmentAnswerError,
    AssessmentContextStaleError,
)
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


router = APIRouter(tags=["assessments"])


def create_assessment_service() -> ArchitectureOrientationAssessmentService:
    """Small test seam; no general dependency-injection framework is introduced."""

    settings = get_settings()
    return ArchitectureOrientationAssessmentService(
        repository_inspection_service=PublicRepositoryInspectionService(
            github_token=settings.github_token
        ),
        openai_client=OpenAIAssessmentClient(settings),
    )


@router.post("/architecture-orientation/questions", response_model=AssessmentQuestionsResponse)
def prepare_assessment_questions(
    request: AssessmentQuestionsRequest,
) -> AssessmentQuestionsResponse:
    try:
        return create_assessment_service().prepare_questions(request)
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except EvidenceCatalogError as error:
        raise HTTPException(
            status_code=502,
            detail="Repository evidence could not be prepared safely. Please try again.",
        ) from error


@router.post("/architecture-orientation/evaluate", response_model=AssessmentEvaluationResponse)
def evaluate_assessment(
    request: AssessmentEvaluationRequest,
) -> AssessmentEvaluationResponse:
    try:
        return create_assessment_service().evaluate(request)
    except AssessmentConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Assessment evaluation is not configured on this server.",
        ) from error
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except AssessmentContextStaleError as error:
        raise HTTPException(
            status_code=409,
            detail="Repository orientation evidence changed. Refresh the assessment and try again.",
        ) from error
    except AssessmentAnswerError as error:
        raise HTTPException(
            status_code=422,
            detail="Submitted answers do not match the available assessment choices.",
        ) from error
    except AssessmentRateLimitedError as error:
        raise HTTPException(
            status_code=429,
            detail="Assessment evaluation is temporarily rate limited. Please try again later.",
        ) from error
    except AssessmentTimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="Assessment evaluation timed out. Please try again.",
        ) from error
    except AssessmentRefusalError as error:
        raise HTTPException(
            status_code=422,
            detail="The explain-back response could not be evaluated for this request.",
        ) from error
    except (AssessmentIncompleteError, EvidenceCatalogError) as error:
        raise HTTPException(
            status_code=502,
            detail="Assessment evaluation returned incomplete or unverifiable output. Please try again.",
        ) from error
    except AssessmentProviderError as error:
        raise HTTPException(
            status_code=502,
            detail="Assessment evaluation is temporarily unavailable. Please try again.",
        ) from error
