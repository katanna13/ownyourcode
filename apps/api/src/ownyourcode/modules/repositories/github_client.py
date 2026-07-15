"""A deliberately narrow client for GitHub's fixed REST API host."""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from ownyourcode.core.github_url import GitHubRepositoryReference


GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
TREE_RESPONSE_MAX_BYTES = 8 * 1024 * 1024
JSON_RESPONSE_MAX_BYTES = 1024 * 1024
MANIFEST_RESPONSE_MAX_BYTES = 128 * 1024


class GitHubClientError(Exception):
    status_code = 502
    public_message = "GitHub could not complete the repository inspection."


class GitHubRepositoryUnavailableError(GitHubClientError):
    status_code = 404
    public_message = "The repository was not found or is not public."


class GitHubRateLimitedError(GitHubClientError):
    status_code = 429
    public_message = "GitHub rate limit reached. Please try again later."


class GitHubTimeoutError(GitHubClientError):
    status_code = 504
    public_message = "GitHub did not respond in time. Please try again."


class GitHubSafetyLimitError(GitHubClientError):
    status_code = 413
    public_message = "GitHub returned more data than this preview can safely inspect."


class GitHubMalformedResponseError(GitHubClientError):
    public_message = "GitHub returned an unexpected response for this repository."


class GitHubUpstreamError(GitHubClientError):
    pass


class GitHubClient:
    """Make only fixed-path GET requests to api.github.com.

    The token is attached inside this class only. It is intentionally absent
    from return values and exception messages.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "OwnYourCode/0.1",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=GITHUB_API_BASE_URL,
            headers=headers,
            timeout=httpx.Timeout(timeout=5.0, connect=2.0),
            follow_redirects=False,
        )
        if client is not None:
            self._client.headers.update(headers)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get_repository(self, reference: GitHubRepositoryReference) -> Any:
        return self._get_json(
            self._repository_path(reference),
            max_bytes=JSON_RESPONSE_MAX_BYTES,
        )

    def get_languages(self, reference: GitHubRepositoryReference) -> Any:
        return self._get_json(
            f"{self._repository_path(reference)}/languages",
            max_bytes=JSON_RESPONSE_MAX_BYTES,
        )

    def get_tree(self, reference: GitHubRepositoryReference, branch: str) -> Any:
        return self._get_json(
            f"{self._repository_path(reference)}/git/trees/{quote(branch, safe='')}",
            params={"recursive": "1"},
            max_bytes=TREE_RESPONSE_MAX_BYTES,
        )

    def get_file_content(
        self,
        reference: GitHubRepositoryReference,
        path: str,
        branch: str,
    ) -> Any:
        return self._get_json(
            f"{self._repository_path(reference)}/contents/{quote(path, safe='/')}",
            params={"ref": branch},
            max_bytes=MANIFEST_RESPONSE_MAX_BYTES,
        )

    @staticmethod
    def _repository_path(reference: GitHubRepositoryReference) -> str:
        return (
            f"/repos/{quote(reference.owner, safe='')}/"
            f"{quote(reference.repository, safe='')}"
        )

    def _get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        max_bytes: int,
    ) -> Any:
        try:
            # iter_bytes enforces the cap before an entire response is retained.
            with self._client.stream("GET", path, params=params) as response:
                response_body = self._read_limited_body(response, max_bytes)
                self._raise_for_error_status(response, response_body)
        except GitHubClientError:
            raise
        except httpx.TimeoutException as error:
            raise GitHubTimeoutError() from error
        except httpx.RequestError as error:
            raise GitHubUpstreamError() from error

        try:
            return json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GitHubMalformedResponseError() from error

    @staticmethod
    def _read_limited_body(response: httpx.Response, max_bytes: int) -> bytes:
        chunks: list[bytes] = []
        received_bytes = 0
        for chunk in response.iter_bytes():
            received_bytes += len(chunk)
            if received_bytes > max_bytes:
                raise GitHubSafetyLimitError()
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _raise_for_error_status(response: httpx.Response, body: bytes) -> None:
        if 200 <= response.status_code < 300:
            return
        if response.status_code == 404:
            raise GitHubRepositoryUnavailableError()
        if response.status_code == 429:
            raise GitHubRateLimitedError()
        if response.status_code == 403 and GitHubClient._is_rate_limited(response, body):
            raise GitHubRateLimitedError()
        raise GitHubUpstreamError()

    @staticmethod
    def _is_rate_limited(response: httpx.Response, body: bytes) -> bool:
        if response.headers.get("X-RateLimit-Remaining") == "0":
            return True

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        message = payload.get("message") if isinstance(payload, dict) else None
        if not isinstance(message, str):
            return False

        normalized = message.casefold()
        return (
            normalized.startswith("api rate limit exceeded")
            or "secondary rate limit" in normalized
            or "rate limit exceeded" in normalized
        )
