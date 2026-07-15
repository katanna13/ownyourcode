import base64
import json
from collections.abc import Callable
from typing import Any

import httpx
from fastapi.testclient import TestClient

from ownyourcode.main import app
from ownyourcode.modules.repositories.github_client import (
    GITHUB_API_BASE_URL,
    GITHUB_API_VERSION,
    GitHubClient,
)
from ownyourcode.modules.repositories.inspector import (
    MAX_MANIFEST_BYTES,
    RepositoryInspector,
)


def encoded_file(content: str, *, declared_size: int | None = None) -> dict[str, Any]:
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(content.encode("utf-8")) if declared_size is None else declared_size,
        "content": encoded_content,
        "download_url": "https://example.invalid/never-followed",
    }


def encoded_bytes_file(content: bytes) -> dict[str, Any]:
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(content),
        "content": base64.b64encode(content).decode("ascii"),
    }


def install_github_mock(
    monkeypatch: Any,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    token: str | None = None,
) -> None:
    mock_client = httpx.Client(
        base_url=GITHUB_API_BASE_URL,
        transport=httpx.MockTransport(handler),
    )
    github_client = GitHubClient(token=token, client=mock_client)
    monkeypatch.setattr(
        "ownyourcode.modules.repositories.router.create_github_client",
        lambda: github_client,
    )


def successful_handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["X-GitHub-Api-Version"] == GITHUB_API_VERSION
    assert request.headers["User-Agent"] == "OwnYourCode/0.1"
    path = request.url.path
    if path == "/repos/acme/learning-api":
        return httpx.Response(
            200,
            json={
                "name": "learning-api",
                "full_name": "acme/learning-api",
                "description": "A small API for learning.",
                "default_branch": "main",
                "language": "Python",
                "html_url": "https://github.com/acme/learning-api",
                "private": False,
            },
        )
    if path == "/repos/acme/learning-api/languages":
        return httpx.Response(200, json={"TypeScript": 200, "Python": 1200})
    if path == "/repos/acme/learning-api/git/trees/main":
        pyproject = "[project]\ndependencies = ['fastapi>=0.115', 'pytest>=8']\n"
        package = json.dumps(
            {
                "dependencies": {"react": "^19", "vite": "^6"},
                "devDependencies": {"vitest": "^3"},
            }
        )
        return httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {"path": "backend/pyproject.toml", "type": "blob", "size": len(pyproject.encode())},
                    {"path": "frontend/package.json", "type": "blob", "size": len(package.encode())},
                    {"path": "Dockerfile", "type": "blob", "size": 20},
                    {"path": ".github/workflows/test.yml", "type": "blob", "size": 20},
                ],
            },
        )
    if path == "/repos/acme/learning-api/contents/backend/pyproject.toml":
        return httpx.Response(
            200,
            json=encoded_file("[project]\ndependencies = ['fastapi>=0.115', 'pytest>=8']\n"),
        )
    if path == "/repos/acme/learning-api/contents/frontend/package.json":
        return httpx.Response(
            200,
            json=encoded_file(
                json.dumps(
                    {
                        "dependencies": {"react": "^19", "vite": "^6"},
                        "devDependencies": {"vitest": "^3"},
                    }
                )
            ),
        )
    return httpx.Response(500)


def inspect(client: TestClient) -> Any:
    return client.post(
        "/api/v1/repositories/inspect",
        json={"repository_url": "https://github.com/acme/learning-api"},
    )


def test_inspection_returns_deterministic_metadata_and_framework_evidence(
    monkeypatch: Any,
) -> None:
    install_github_mock(monkeypatch, successful_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is False
    assert body["repository"]["full_name"] == "acme/learning-api"
    assert body["languages"] == [
        {"name": "Python", "bytes": 1200},
        {"name": "TypeScript", "bytes": 200},
    ]
    assert body["technologies"] == [
        {"key": "docker", "label": "Docker", "evidence": ["Dockerfile"]},
        {
            "key": "fastapi",
            "label": "FastAPI",
            "evidence": ["backend/pyproject.toml: dependency fastapi"],
        },
        {
            "key": "github-actions",
            "label": "GitHub Actions",
            "evidence": [".github/workflows/test.yml"],
        },
        {
            "key": "nodejs",
            "label": "Node.js",
            "evidence": ["frontend/package.json"],
        },
        {
            "key": "pytest",
            "label": "pytest",
            "evidence": ["backend/pyproject.toml: dependency pytest"],
        },
        {
            "key": "python",
            "label": "Python",
            "evidence": ["backend/pyproject.toml", "GitHub language: Python"],
        },
        {
            "key": "react",
            "label": "React",
            "evidence": ["frontend/package.json: dependency react"],
        },
        {
            "key": "typescript",
            "label": "TypeScript",
            "evidence": ["GitHub language: TypeScript"],
        },
        {
            "key": "vite",
            "label": "Vite",
            "evidence": ["frontend/package.json: dependency vite"],
        },
        {
            "key": "vitest",
            "label": "Vitest",
            "evidence": ["frontend/package.json: dependency vitest"],
        },
    ]
    assert body["important_files"] == [
        {"path": ".github/workflows/test.yml", "kind": "continuous integration workflow"},
        {"path": "backend/pyproject.toml", "kind": "manifest"},
        {"path": "Dockerfile", "kind": "container configuration"},
        {"path": "frontend/package.json", "kind": "manifest"},
    ]
    assert body["paths"] == {
        "inspected_count": 4,
        "returned": [
            ".github/workflows/test.yml",
            "Dockerfile",
            "backend/pyproject.toml",
            "frontend/package.json",
        ],
        "truncated": False,
    }


def test_inspection_rejects_a_non_github_url() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/repositories/inspect",
            json={"repository_url": "https://example.com/acme/learning-api"},
        )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_inspection_maps_repository_not_found_to_a_safe_public_error(
    monkeypatch: Any,
) -> None:
    install_github_mock(monkeypatch, lambda request: httpx.Response(404))

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 404
    assert response.json() == {"detail": "The repository was not found or is not public."}


def test_inspection_maps_github_rate_limit_response(monkeypatch: Any) -> None:
    install_github_mock(
        monkeypatch,
        lambda request: httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0"},
            json={"message": "API rate limit exceeded"},
        ),
    )

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 429
    assert response.json() == {"detail": "GitHub rate limit reached. Please try again later."}


def test_inspection_does_not_treat_every_forbidden_response_as_rate_limiting(
    monkeypatch: Any,
) -> None:
    install_github_mock(
        monkeypatch,
        lambda request: httpx.Response(403, json={"message": "Resource forbidden"}),
    )

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "GitHub could not complete the repository inspection."
    }


def test_inspection_maps_github_timeout_to_a_safe_error(monkeypatch: Any) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    install_github_mock(monkeypatch, timeout)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 504
    assert response.json() == {"detail": "GitHub did not respond in time. Please try again."}


def test_path_limit_returns_a_truncated_preview_instead_of_failing(
    monkeypatch: Any,
) -> None:
    def many_paths_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": None,
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {"path": f"src/file-{index:04}.txt", "type": "blob", "size": 0}
                        for index in range(2_001)
                    ],
                },
            )
        return httpx.Response(500)

    install_github_mock(monkeypatch, many_paths_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 200
    body = response.json()
    assert body["paths"]["inspected_count"] == 2_000
    assert len(body["paths"]["returned"]) == 250
    assert body["paths"]["truncated"] is True
    assert any("first 2,000 repository paths" in item for item in body["limitations"])


def test_tree_blob_order_is_depth_then_casefold_then_exact_path() -> None:
    inspector = RepositoryInspector(None)  # type: ignore[arg-type]
    blobs, truncated = inspector._validated_tree(
        {
            "truncated": False,
            "tree": [
                {"path": "aardvark/deep.txt", "type": "blob", "size": 0},
                {"path": "root.txt", "type": "blob", "size": 0},
                {"path": "alpha.txt", "type": "blob", "size": 0},
                {"path": "Alpha.txt", "type": "blob", "size": 0},
            ],
        }
    )

    assert truncated is False
    assert [blob.path for blob in blobs] == [
        "Alpha.txt",
        "alpha.txt",
        "root.txt",
        "aardvark/deep.txt",
    ]


def test_bounded_path_selection_keeps_root_manifests_and_configuration(
    monkeypatch: Any,
) -> None:
    package = "{}"
    pyproject = "[project]\n"

    def shallow_first_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": None,
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/trees/main"):
            nested_paths = [
                {"path": f"aaa/deep/file-{index:04}.txt", "type": "blob", "size": 0}
                for index in range(2_000)
            ]
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": nested_paths
                    + [
                        {"path": "package.json", "type": "blob", "size": len(package)},
                        {"path": "pyproject.toml", "type": "blob", "size": len(pyproject)},
                        {"path": "vite.config.ts", "type": "blob", "size": 0},
                    ],
                },
            )
        if request.url.path.endswith("/contents/package.json"):
            return httpx.Response(200, json=encoded_file(package))
        if request.url.path.endswith("/contents/pyproject.toml"):
            return httpx.Response(200, json=encoded_file(pyproject))
        return httpx.Response(500)

    install_github_mock(monkeypatch, shallow_first_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 200
    body = response.json()
    assert body["paths"]["inspected_count"] == 2_000
    assert body["paths"]["truncated"] is True
    technology_labels = {technology["label"] for technology in body["technologies"]}
    assert {"Node.js", "Python", "Vite"}.issubset(technology_labels)
    assert {file["path"] for file in body["important_files"]} >= {
        "package.json",
        "pyproject.toml",
        "vite.config.ts",
    }


def test_manifest_candidate_count_limit_adds_a_limitation_before_stopping(
    monkeypatch: Any,
) -> None:
    downloaded_paths: list[str] = []

    def candidate_limit_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": None,
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {
                            "path": f"manifests/{index}/package.json",
                            "type": "blob",
                            "size": 2,
                        }
                        for index in range(7)
                    ],
                },
            )
        if "/contents/" in request.url.path:
            downloaded_paths.append(request.url.path)
            return httpx.Response(200, json=encoded_file("{}"))
        return httpx.Response(500)

    install_github_mock(monkeypatch, candidate_limit_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 200
    assert downloaded_paths == [
        f"/repos/acme/learning-api/contents/manifests/{index}/package.json"
        for index in range(6)
    ]
    assert any(
        "six-file count or byte download limits" in limitation
        for limitation in response.json()["limitations"]
    )


def test_invalid_repository_manifests_are_skipped_without_hiding_tree_evidence(
    monkeypatch: Any,
) -> None:
    package = "{not valid JSON"
    pyproject = "[project"
    requirements = "fastapi==0.115\n"
    unreadable_pipfile = b"\xff"

    def unreadable_manifest_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": None,
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {"path": "package.json", "type": "blob", "size": len(package)},
                        {"path": "pyproject.toml", "type": "blob", "size": len(pyproject)},
                        {"path": "requirements.txt", "type": "blob", "size": len(requirements)},
                        {"path": "Pipfile", "type": "blob", "size": len(unreadable_pipfile)},
                    ],
                },
            )
        if request.url.path.endswith("/contents/package.json"):
            return httpx.Response(200, json=encoded_file(package))
        if request.url.path.endswith("/contents/pyproject.toml"):
            return httpx.Response(200, json=encoded_file(pyproject))
        if request.url.path.endswith("/contents/requirements.txt"):
            return httpx.Response(200, json=encoded_file(requirements))
        if request.url.path.endswith("/contents/Pipfile"):
            return httpx.Response(200, json=encoded_bytes_file(unreadable_pipfile))
        return httpx.Response(500)

    install_github_mock(monkeypatch, unreadable_manifest_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 200
    body = response.json()
    technology_by_label = {
        technology["label"]: technology for technology in body["technologies"]
    }
    assert technology_by_label["Node.js"]["evidence"] == ["package.json"]
    assert technology_by_label["Python"]["evidence"] == [
        "Pipfile",
        "pyproject.toml",
        "requirements.txt",
    ]
    assert technology_by_label["FastAPI"]["evidence"] == [
        "requirements.txt: dependency fastapi"
    ]
    assert any(
        "downloaded manifests could not be parsed" in limitation
        for limitation in body["limitations"]
    )


def test_invalid_github_manifest_envelope_still_fails_inspection(
    monkeypatch: Any,
) -> None:
    def invalid_envelope_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": None,
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [{"path": "package.json", "type": "blob", "size": 1}],
                },
            )
        if request.url.path.endswith("/contents/package.json"):
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "encoding": "base64",
                    "size": 1,
                    "content": "not valid base64!",
                },
            )
        return httpx.Response(500)

    install_github_mock(monkeypatch, invalid_envelope_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "GitHub returned an unexpected response for this repository."
    }


def test_github_actions_requires_a_workflow_yaml_blob(monkeypatch: Any) -> None:
    def workflow_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": None,
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {"path": ".github/workflows/build.yml", "type": "blob", "size": 0},
                        {"path": ".github/workflows/release.yaml", "type": "blob", "size": 0},
                        {"path": ".github/workflows/notes.txt", "type": "blob", "size": 0},
                        {"path": ".github/workflows/not-a-file.yml", "type": "tree", "size": 0},
                        {"path": ".github/workflows/submodule.yaml", "type": "commit", "size": 0},
                    ],
                },
            )
        return httpx.Response(500)

    install_github_mock(monkeypatch, workflow_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 200
    body = response.json()
    assert body["technologies"] == [
        {
            "key": "github-actions",
            "label": "GitHub Actions",
            "evidence": [
                ".github/workflows/build.yml",
                ".github/workflows/release.yaml",
            ],
        }
    ]
    assert body["important_files"] == [
        {
            "path": ".github/workflows/build.yml",
            "kind": "continuous integration workflow",
        },
        {
            "path": ".github/workflows/release.yaml",
            "kind": "continuous integration workflow",
        },
    ]


def test_oversized_manifest_content_is_rejected_with_a_safety_limit(
    monkeypatch: Any,
) -> None:
    def oversized_manifest_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": "JavaScript",
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={"JavaScript": 1})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [{"path": "package.json", "type": "blob", "size": 1}],
                },
            )
        if request.url.path.endswith("/contents/package.json"):
            return httpx.Response(
                200,
                json=encoded_file("x", declared_size=MAX_MANIFEST_BYTES + 1),
            )
        return httpx.Response(500)

    install_github_mock(monkeypatch, oversized_manifest_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 413
    assert response.json() == {
        "detail": "GitHub returned more data than this preview can safely inspect."
    }


def test_tree_response_size_limit_is_enforced_while_streaming(
    monkeypatch: Any,
) -> None:
    import ownyourcode.modules.repositories.github_client as github_client_module

    monkeypatch.setattr(github_client_module, "TREE_RESPONSE_MAX_BYTES", 100)

    def oversized_tree_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/learning-api":
            return httpx.Response(
                200,
                json={
                    "name": "learning-api",
                    "full_name": "acme/learning-api",
                    "description": None,
                    "default_branch": "main",
                    "language": None,
                    "html_url": "https://github.com/acme/learning-api",
                    "private": False,
                },
            )
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(200, json={"truncated": False, "tree": ["x" * 200]})
        return httpx.Response(500)

    install_github_mock(monkeypatch, oversized_tree_handler)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 413


def test_private_repository_is_rejected_and_the_token_never_reaches_the_response(
    monkeypatch: Any,
) -> None:
    received_authorization: list[str | None] = []

    def private_handler(request: httpx.Request) -> httpx.Response:
        received_authorization.append(request.headers.get("Authorization"))
        return httpx.Response(
            200,
            json={
                "name": "learning-api",
                "full_name": "acme/learning-api",
                "description": None,
                "default_branch": "main",
                "language": None,
                "html_url": "https://github.com/acme/learning-api",
                "private": True,
            },
        )

    token = "phase-three-test-token"
    install_github_mock(monkeypatch, private_handler, token=token)

    with TestClient(app) as client:
        response = inspect(client)

    assert response.status_code == 404
    assert received_authorization == [f"Bearer {token}"]
    assert token not in response.text
    assert response.json() == {"detail": "The repository was not found or is not public."}
