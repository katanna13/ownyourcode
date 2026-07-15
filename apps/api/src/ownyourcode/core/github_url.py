"""Validation for the small, public GitHub URL surface accepted by the API."""

import re
from dataclasses import dataclass
from urllib.parse import urlparse


_GITHUB_PATH_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class GitHubRepositoryReference:
    """A canonical repository reference derived from a validated GitHub URL."""

    owner: str
    repository: str
    url: str


def parse_public_github_repository_url(value: str) -> GitHubRepositoryReference:
    """Accept only canonicalizable HTTPS github.com owner/repository URLs."""

    parsed_url = urlparse(value)

    try:
        port = parsed_url.port
    except ValueError as error:
        raise ValueError("repository_url must be a valid GitHub URL") from error

    path_parts = [part for part in parsed_url.path.split("/") if part]
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or parsed_url.username is not None
        or parsed_url.password is not None
        or port is not None
        or parsed_url.params
        or parsed_url.query
        or parsed_url.fragment
        or len(path_parts) != 2
        or not all(_GITHUB_PATH_PART.fullmatch(part) for part in path_parts)
    ):
        raise ValueError(
            "repository_url must be an HTTPS GitHub repository URL such as "
            "https://github.com/owner/repository"
        )

    owner, repository = path_parts
    return GitHubRepositoryReference(
        owner=owner,
        repository=repository,
        url=f"https://github.com/{owner}/{repository}",
    )
