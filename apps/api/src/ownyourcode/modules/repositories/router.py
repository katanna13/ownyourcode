"""HTTP boundary for the non-persistent repository inspection preview."""

from fastapi import APIRouter, HTTPException

from ownyourcode.core.config import get_settings
from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.repositories.github_client import GitHubClient, GitHubClientError
from ownyourcode.modules.repositories.inspector import RepositoryInspector
from ownyourcode.modules.repositories.schemas import (
    RepositoryInspectionRequest,
    RepositoryInspectionResponse,
)


router = APIRouter(tags=["repositories"])


def create_github_client() -> GitHubClient:
    """Small test seam; this is not a general dependency-injection framework."""

    return GitHubClient(token=get_settings().github_token)


@router.post("/inspect", response_model=RepositoryInspectionResponse)
def inspect_repository(
    request: RepositoryInspectionRequest,
) -> RepositoryInspectionResponse:
    github_client = create_github_client()
    try:
        reference = parse_public_github_repository_url(request.repository_url)
        return RepositoryInspector(github_client).inspect(reference)
    except GitHubClientError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.public_message,
        ) from error
    finally:
        github_client.close()
