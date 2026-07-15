"""HTTP boundary for the non-persistent repository inspection preview."""

from fastapi import APIRouter, HTTPException

from ownyourcode.core.config import get_settings
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.schemas import (
    RepositoryInspectionRequest,
    RepositoryInspectionResponse,
)
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


router = APIRouter(tags=["repositories"])


def create_repository_inspection_service() -> PublicRepositoryInspectionService:
    """Small test seam; this is not a general dependency-injection framework."""

    return PublicRepositoryInspectionService(github_token=get_settings().github_token)


@router.post("/inspect", response_model=RepositoryInspectionResponse)
def inspect_repository(
    request: RepositoryInspectionRequest,
) -> RepositoryInspectionResponse:
    try:
        return create_repository_inspection_service().inspect_url(request.repository_url)
    except GitHubClientError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.public_message,
        ) from error
