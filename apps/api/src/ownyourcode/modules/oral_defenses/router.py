"""HTTP boundary for the preview-only architecture oral defense."""

from fastapi import APIRouter, HTTPException

from ownyourcode.core.config import get_settings
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError
from ownyourcode.modules.oral_defenses.definition import OralDefenseGroundingError
from ownyourcode.modules.oral_defenses.openai_client import (
    OpenAIOralDefenseClient,
    OralDefenseConfigurationError,
    OralDefenseIncompleteError,
    OralDefenseProviderError,
    OralDefenseRateLimitedError,
    OralDefenseRefusalError,
    OralDefenseTimeoutError,
)
from ownyourcode.modules.oral_defenses.schemas import (
    OralDefenseEvaluationRequest,
    OralDefenseEvaluationResponse,
    OralDefensePrepareRequest,
    OralDefensePrepareResponse,
)
from ownyourcode.modules.oral_defenses.service import (
    ArchitectureOralDefenseService,
    OralDefenseContextStaleError,
    OralDefenseEvidenceError,
    OralDefenseUnavailableError,
)
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


router = APIRouter(tags=["oral defenses"])


def create_architecture_oral_defense_service() -> ArchitectureOralDefenseService:
    """Small construction seam for tests; no general dependency framework."""

    settings = get_settings()
    return ArchitectureOralDefenseService(
        repository_inspection_service=PublicRepositoryInspectionService(
            github_token=settings.github_token
        ),
        openai_client=OpenAIOralDefenseClient(settings),
    )


@router.post(
    "/architecture-boundaries/prepare",
    response_model=OralDefensePrepareResponse,
)
def prepare_architecture_oral_defense(
    request: OralDefensePrepareRequest,
) -> OralDefensePrepareResponse:
    try:
        return create_architecture_oral_defense_service().prepare(request)
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except (EvidenceCatalogError, OralDefenseEvidenceError) as error:
        raise HTTPException(
            status_code=502,
            detail="Repository evidence could not be prepared safely for this oral defense.",
        ) from error


@router.post(
    "/architecture-boundaries/evaluate",
    response_model=OralDefenseEvaluationResponse,
)
def evaluate_architecture_oral_defense(
    request: OralDefenseEvaluationRequest,
) -> OralDefenseEvaluationResponse:
    try:
        return create_architecture_oral_defense_service().evaluate(request)
    except OralDefenseConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Oral-defense evaluation is not configured on this server.",
        ) from error
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except OralDefenseUnavailableError as error:
        raise HTTPException(
            status_code=422,
            detail="This oral defense requires at least two deterministic architecture boundary categories.",
        ) from error
    except OralDefenseContextStaleError as error:
        raise HTTPException(
            status_code=409,
            detail="Repository evidence changed. Prepare the oral defense again before submitting.",
        ) from error
    except OralDefenseRateLimitedError as error:
        raise HTTPException(
            status_code=429,
            detail="Oral-defense evaluation is temporarily rate limited. Please try again later.",
        ) from error
    except OralDefenseTimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="Oral-defense evaluation timed out. Please try again.",
        ) from error
    except OralDefenseRefusalError as error:
        raise HTTPException(
            status_code=422,
            detail="The oral-defense response could not be evaluated for this request.",
        ) from error
    except (
        OralDefenseIncompleteError,
        OralDefenseGroundingError,
        EvidenceCatalogError,
        OralDefenseEvidenceError,
    ) as error:
        raise HTTPException(
            status_code=502,
            detail="Oral-defense evaluation returned incomplete or unverifiable output. Please try again.",
        ) from error
    except OralDefenseProviderError as error:
        raise HTTPException(
            status_code=502,
            detail="Oral-defense evaluation is temporarily unavailable. Please try again.",
        ) from error
