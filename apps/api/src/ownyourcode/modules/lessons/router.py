"""HTTP boundary for a non-persistent architecture-orientation lesson."""

from fastapi import APIRouter, HTTPException

from ownyourcode.core.config import get_settings
from ownyourcode.modules.lessons.evidence import (
    EvidenceCatalogError,
    EvidenceGroundingError,
)
from ownyourcode.modules.lessons.openai_client import (
    LessonConfigurationError,
    LessonIncompleteError,
    LessonProviderError,
    LessonRateLimitedError,
    LessonRefusalError,
    LessonTimeoutError,
    OpenAILessonClient,
)
from ownyourcode.modules.lessons.schemas import (
    LessonGenerationRequest,
    LessonGenerationResponse,
)
from ownyourcode.modules.lessons.service import LessonGenerationService
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


router = APIRouter(tags=["lessons"])


def create_lesson_generation_service() -> LessonGenerationService:
    """Small construction seam for tests; no dependency-injection framework."""

    settings = get_settings()
    return LessonGenerationService(
        repository_inspection_service=PublicRepositoryInspectionService(
            github_token=settings.github_token
        ),
        openai_client=OpenAILessonClient(settings),
    )


@router.post("/generate", response_model=LessonGenerationResponse)
def generate_lesson(request: LessonGenerationRequest) -> LessonGenerationResponse:
    try:
        return create_lesson_generation_service().generate(request)
    except LessonConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Lesson generation is not configured on this server.",
        ) from error
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except LessonRateLimitedError as error:
        raise HTTPException(
            status_code=429,
            detail="Lesson generation is temporarily rate limited. Please try again later.",
        ) from error
    except LessonTimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="Lesson generation timed out. Please try again.",
        ) from error
    except LessonRefusalError as error:
        raise HTTPException(
            status_code=422,
            detail="The lesson could not be generated for this request.",
        ) from error
    except (LessonIncompleteError, EvidenceCatalogError, EvidenceGroundingError) as error:
        raise HTTPException(
            status_code=502,
            detail="Lesson generation returned incomplete or unverifiable output. Please try again.",
        ) from error
    except LessonProviderError as error:
        raise HTTPException(
            status_code=502,
            detail="Lesson generation is temporarily unavailable. Please try again.",
        ) from error
