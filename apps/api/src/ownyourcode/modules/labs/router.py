"""HTTP boundary for the AST-only FastAPI health-check teaching fixture."""

from fastapi import APIRouter, HTTPException

from ownyourcode.core.config import get_settings
from ownyourcode.modules.labs.schemas import (
    FastAPIHealthCheckLabPrepareResponse,
    LabEvaluationRequest,
    LabEvaluationResponse,
    LabPrepareRequest,
)
from ownyourcode.modules.labs.service import (
    FastAPIHealthCheckLabService,
    LabContextStaleError,
    LabEvidenceError,
    LabUnavailableError,
)
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


router = APIRouter(tags=["labs"])


def create_fastapi_health_check_lab_service() -> FastAPIHealthCheckLabService:
    """Small construction seam for tests; no execution worker is involved."""

    settings = get_settings()
    return FastAPIHealthCheckLabService(
        PublicRepositoryInspectionService(github_token=settings.github_token)
    )


@router.post(
    "/fastapi-health-check/prepare",
    response_model=FastAPIHealthCheckLabPrepareResponse,
)
def prepare_fastapi_health_check_lab(
    request: LabPrepareRequest,
) -> FastAPIHealthCheckLabPrepareResponse:
    try:
        return create_fastapi_health_check_lab_service().prepare(request)
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except (EvidenceCatalogError, LabEvidenceError) as error:
        raise HTTPException(
            status_code=502,
            detail="Repository evidence could not be prepared safely for this lab.",
        ) from error


@router.post("/fastapi-health-check/evaluate", response_model=LabEvaluationResponse)
def evaluate_fastapi_health_check_lab(
    request: LabEvaluationRequest,
) -> LabEvaluationResponse:
    try:
        return create_fastapi_health_check_lab_service().evaluate(request)
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except LabUnavailableError as error:
        raise HTTPException(
            status_code=422,
            detail="This lab requires deterministic Python and FastAPI evidence.",
        ) from error
    except LabContextStaleError as error:
        raise HTTPException(
            status_code=409,
            detail="Repository evidence changed. Prepare the lab again before submitting.",
        ) from error
    except (EvidenceCatalogError, LabEvidenceError) as error:
        raise HTTPException(
            status_code=502,
            detail="Repository evidence could not be prepared safely for this lab.",
        ) from error
