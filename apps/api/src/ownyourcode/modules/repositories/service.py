"""A narrow reusable boundary for public GitHub repository inspection."""

from collections.abc import Callable

from ownyourcode.core.github_url import parse_public_github_repository_url
from ownyourcode.modules.repositories.github_client import GitHubClient
from ownyourcode.modules.repositories.inspector import RepositoryInspector
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse


class PublicRepositoryInspectionService:
    """Inspect a validated public GitHub URL and always release the HTTP client."""

    def __init__(
        self,
        github_token: str | None,
        client_factory: Callable[..., GitHubClient] = GitHubClient,
    ) -> None:
        self._github_token = github_token
        self._client_factory = client_factory

    def inspect_url(self, repository_url: str) -> RepositoryInspectionResponse:
        reference = parse_public_github_repository_url(repository_url)
        github_client = self._client_factory(token=self._github_token)
        try:
            return RepositoryInspector(github_client).inspect(reference)
        finally:
            github_client.close()
