"""Deterministic stack detection over a bounded GitHub repository snapshot."""

import base64
import binascii
import json
import re
import tomllib
from dataclasses import dataclass
from typing import Any

from ownyourcode.core.github_url import GitHubRepositoryReference
from ownyourcode.modules.repositories.github_client import (
    GitHubMalformedResponseError,
    GitHubRepositoryUnavailableError,
    GitHubSafetyLimitError,
    GitHubClient,
)
from ownyourcode.modules.repositories.schemas import (
    DetectedLanguage,
    DetectedTechnology,
    ImportantFile,
    InspectedPaths,
    RepositoryInspectionResponse,
    RepositoryMetadata,
)


MAX_PATHS_INSPECTED = 2_000
MAX_PATHS_RETURNED = 250
MAX_IMPORTANT_FILES_RETURNED = 50
MAX_MANIFEST_CANDIDATES = 6
MAX_MANIFEST_BYTES = 64 * 1024
MAX_TOTAL_MANIFEST_BYTES = 192 * 1024
ALLOWED_MANIFEST_FILENAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "pipfile",
}


class UnreadableManifestContentError(Exception):
    """A repository manifest is validly fetched but cannot be structurally read."""


@dataclass(frozen=True)
class TreeBlob:
    path: str
    size: int

    @property
    def name(self) -> str:
        return self.path.rsplit("/", maxsplit=1)[-1]

    @property
    def depth(self) -> int:
        return self.path.count("/")


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _normalize_dependency_name(value: str) -> str | None:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", value)
    if not match:
        return None
    return re.sub(r"[-_.]+", "-", match.group(1)).casefold()


def _dependencies_from_package_json(text: str) -> set[str]:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise UnreadableManifestContentError() from error
    if not isinstance(document, dict):
        raise UnreadableManifestContentError()

    dependencies: set[str] = set()
    for section in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        values = document.get(section, {})
        if not isinstance(values, dict):
            continue
        for package_name in values:
            if isinstance(package_name, str):
                normalized_name = _normalize_dependency_name(package_name)
                if normalized_name:
                    dependencies.add(normalized_name)
    return dependencies


def _dependency_names_from_values(values: object) -> set[str]:
    dependencies: set[str] = set()
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str):
                normalized_name = _normalize_dependency_name(value)
                if normalized_name:
                    dependencies.add(normalized_name)
    elif isinstance(values, dict):
        for package_name in values:
            if isinstance(package_name, str):
                normalized_name = _normalize_dependency_name(package_name)
                if normalized_name:
                    dependencies.add(normalized_name)
    return dependencies


def _dependencies_from_toml(text: str, manifest_name: str) -> set[str]:
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise UnreadableManifestContentError() from error
    if not isinstance(document, dict):
        raise UnreadableManifestContentError()

    dependencies: set[str] = set()
    if manifest_name == "pyproject.toml":
        project = document.get("project")
        if isinstance(project, dict):
            dependencies.update(_dependency_names_from_values(project.get("dependencies")))
            optional_dependencies = project.get("optional-dependencies")
            if isinstance(optional_dependencies, dict):
                for values in optional_dependencies.values():
                    dependencies.update(_dependency_names_from_values(values))

        build_system = document.get("build-system")
        if isinstance(build_system, dict):
            dependencies.update(_dependency_names_from_values(build_system.get("requires")))

        tool = document.get("tool")
        if isinstance(tool, dict):
            poetry = tool.get("poetry")
            if isinstance(poetry, dict):
                dependencies.update(_dependency_names_from_values(poetry.get("dependencies")))
                groups = poetry.get("group")
                if isinstance(groups, dict):
                    for group in groups.values():
                        if isinstance(group, dict):
                            dependencies.update(
                                _dependency_names_from_values(group.get("dependencies"))
                            )
    elif manifest_name == "pipfile":
        dependencies.update(_dependency_names_from_values(document.get("packages")))
        dependencies.update(_dependency_names_from_values(document.get("dev-packages")))

    return dependencies


def _dependencies_from_requirements(text: str) -> set[str]:
    dependencies: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if not line or line.startswith("-"):
            continue
        normalized_name = _normalize_dependency_name(line)
        if normalized_name:
            dependencies.add(normalized_name)
    return dependencies


class RepositoryInspector:
    """Inspect metadata, a capped tree, and a strict manifest allow-list only."""

    def __init__(self, github_client: GitHubClient) -> None:
        self._github_client = github_client

    def inspect(
        self, reference: GitHubRepositoryReference
    ) -> RepositoryInspectionResponse:
        metadata = self._metadata(reference)
        languages = self._languages(reference)
        tree_data = self._github_client.get_tree(reference, metadata.default_branch)
        blobs, upstream_tree_truncated = self._validated_tree(tree_data)
        inspected_blobs = blobs[:MAX_PATHS_INSPECTED]
        path_truncated = upstream_tree_truncated or len(blobs) > MAX_PATHS_INSPECTED

        (
            manifest_dependencies,
            manifest_limit_skipped,
            unreadable_manifest_skipped,
        ) = (
            self._manifest_dependencies(reference, metadata.default_branch, inspected_blobs)
        )
        technologies = self._detect_technologies(
            languages,
            inspected_blobs,
            manifest_dependencies,
        )
        limitations = [
            "Inspection uses GitHub metadata, a bounded file tree, and a small "
            "manifest allow-list; it does not clone or broadly read source files.",
            "Results are a deterministic stack preview, not a security scan or "
            "a complete architecture analysis.",
        ]
        if path_truncated:
            limitations.append(
                "Only the first 2,000 repository paths were inspected, so results "
                "may omit files outside that bounded set."
            )
        if manifest_limit_skipped:
            limitations.append(
                "One or more manifest candidates exceeded the six-file count or "
                "byte download limits and were not read."
            )
        if unreadable_manifest_skipped:
            limitations.append(
                "One or more downloaded manifests could not be parsed and were skipped."
            )

        returned_paths = sorted(blob.path for blob in inspected_blobs)[:MAX_PATHS_RETURNED]
        return RepositoryInspectionResponse(
            repository=metadata,
            languages=languages,
            technologies=technologies,
            paths=InspectedPaths(
                inspected_count=len(inspected_blobs),
                returned=returned_paths,
                truncated=path_truncated,
            ),
            important_files=self._important_files(inspected_blobs),
            limitations=limitations,
        )

    def _metadata(self, reference: GitHubRepositoryReference) -> RepositoryMetadata:
        payload = self._github_client.get_repository(reference)
        if not isinstance(payload, dict):
            raise GitHubMalformedResponseError()
        is_private = payload.get("private")
        if is_private is True:
            raise GitHubRepositoryUnavailableError()
        if is_private is not False:
            raise GitHubMalformedResponseError()

        required_strings = ("name", "full_name", "default_branch", "html_url")
        if not all(isinstance(payload.get(field), str) for field in required_strings):
            raise GitHubMalformedResponseError()
        description = payload.get("description")
        primary_language = payload.get("language")
        if description is not None and not isinstance(description, str):
            raise GitHubMalformedResponseError()
        if primary_language is not None and not isinstance(primary_language, str):
            raise GitHubMalformedResponseError()

        return RepositoryMetadata(
            name=payload["name"],
            full_name=payload["full_name"],
            description=description,
            default_branch=payload["default_branch"],
            primary_language=primary_language,
            html_url=payload["html_url"],
        )

    def _languages(self, reference: GitHubRepositoryReference) -> list[DetectedLanguage]:
        payload = self._github_client.get_languages(reference)
        if not isinstance(payload, dict):
            raise GitHubMalformedResponseError()

        language_items: list[tuple[str, int]] = []
        for name, byte_count in payload.items():
            if not isinstance(name, str) or not _is_nonnegative_int(byte_count):
                raise GitHubMalformedResponseError()
            language_items.append((name, byte_count))

        return [
            DetectedLanguage(name=name, bytes=byte_count)
            for name, byte_count in sorted(
                language_items, key=lambda item: (-item[1], item[0].casefold(), item[0])
            )
        ]

    def _validated_tree(self, payload: Any) -> tuple[list[TreeBlob], bool]:
        if not isinstance(payload, dict) or not isinstance(payload.get("tree"), list):
            raise GitHubMalformedResponseError()
        upstream_truncated = payload.get("truncated", False)
        if not isinstance(upstream_truncated, bool):
            raise GitHubMalformedResponseError()

        blobs: list[TreeBlob] = []
        for entry in payload["tree"]:
            if not isinstance(entry, dict) or entry.get("type") != "blob":
                continue
            path = entry.get("path")
            size = entry.get("size")
            if not isinstance(path, str) or not path or not _is_nonnegative_int(size):
                continue
            blobs.append(TreeBlob(path=path, size=size))

        blobs.sort(key=lambda blob: (blob.depth, blob.path.casefold(), blob.path))
        return blobs, upstream_truncated

    def _manifest_dependencies(
        self,
        reference: GitHubRepositoryReference,
        branch: str,
        blobs: list[TreeBlob],
    ) -> tuple[dict[str, set[str]], bool, bool]:
        candidates = [
            blob
            for blob in blobs
            if blob.name.casefold() in ALLOWED_MANIFEST_FILENAMES
        ]
        candidates.sort(key=lambda blob: (blob.depth, blob.path.casefold(), blob.path))

        dependencies: dict[str, set[str]] = {}
        total_downloaded_bytes = 0
        limit_skipped = len(candidates) > MAX_MANIFEST_CANDIDATES
        unreadable_manifest_skipped = False
        for candidate in candidates[:MAX_MANIFEST_CANDIDATES]:
            if candidate.size > MAX_MANIFEST_BYTES:
                limit_skipped = True
                continue
            if total_downloaded_bytes + candidate.size > MAX_TOTAL_MANIFEST_BYTES:
                limit_skipped = True
                continue

            content = self._github_client.get_file_content(
                reference, candidate.path, branch
            )
            try:
                decoded_content = self._decode_manifest_content(content, candidate)
            except UnreadableManifestContentError:
                total_downloaded_bytes += candidate.size
                unreadable_manifest_skipped = True
                continue
            if total_downloaded_bytes + len(decoded_content) > MAX_TOTAL_MANIFEST_BYTES:
                raise GitHubSafetyLimitError()
            total_downloaded_bytes += len(decoded_content)
            try:
                manifest_dependencies = self._parse_manifest(
                    candidate.name.casefold(), decoded_content
                )
            except UnreadableManifestContentError:
                unreadable_manifest_skipped = True
                continue
            for dependency in manifest_dependencies:
                dependencies.setdefault(dependency, set()).add(candidate.path)

        return dependencies, limit_skipped, unreadable_manifest_skipped

    @staticmethod
    def _decode_manifest_content(payload: Any, candidate: TreeBlob) -> str:
        if not isinstance(payload, dict) or payload.get("type") != "file":
            raise GitHubMalformedResponseError()
        if payload.get("encoding") != "base64":
            raise GitHubMalformedResponseError()
        declared_size = payload.get("size")
        content = payload.get("content")
        if not _is_nonnegative_int(declared_size) or not isinstance(content, str):
            raise GitHubMalformedResponseError()
        if declared_size > MAX_MANIFEST_BYTES:
            raise GitHubSafetyLimitError()

        try:
            encoded_content = "".join(content.split())
            decoded_content = base64.b64decode(encoded_content, validate=True)
        except (ValueError, binascii.Error) as error:
            raise GitHubMalformedResponseError() from error
        if len(decoded_content) > MAX_MANIFEST_BYTES:
            raise GitHubSafetyLimitError()
        if declared_size != len(decoded_content) or candidate.size != len(decoded_content):
            raise GitHubMalformedResponseError()
        try:
            return decoded_content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise UnreadableManifestContentError() from error

    @staticmethod
    def _parse_manifest(manifest_name: str, content: str) -> set[str]:
        if manifest_name == "package.json":
            return _dependencies_from_package_json(content)
        if manifest_name in {"pyproject.toml", "pipfile"}:
            return _dependencies_from_toml(content, manifest_name)
        if manifest_name == "requirements.txt":
            return _dependencies_from_requirements(content)
        raise GitHubMalformedResponseError()

    @staticmethod
    def _detect_technologies(
        languages: list[DetectedLanguage],
        blobs: list[TreeBlob],
        dependencies: dict[str, set[str]],
    ) -> list[DetectedTechnology]:
        paths = {blob.path for blob in blobs}
        language_names = {language.name.casefold() for language in languages}
        detections: dict[str, set[str]] = {}

        def add(key: str, label: str, evidence: str) -> None:
            detections.setdefault(f"{key}|{label}", set()).add(evidence)

        def paths_named(*names: str) -> list[str]:
            accepted_names = {name.casefold() for name in names}
            return sorted(
                (path for path in paths if path.rsplit("/", maxsplit=1)[-1].casefold() in accepted_names),
                key=lambda path: (path.casefold(), path),
            )

        python_manifest_paths = paths_named(
            "pyproject.toml", "requirements.txt", "pipfile"
        )
        if "python" in language_names or python_manifest_paths:
            for path in python_manifest_paths:
                add("python", "Python", path)
            if "python" in language_names:
                add("python", "Python", "GitHub language: Python")
        for path in paths_named("package.json"):
            add("nodejs", "Node.js", path)
        if "typescript" in language_names:
            add("typescript", "TypeScript", "GitHub language: TypeScript")
        for path in paths_named("tsconfig.json"):
            add("typescript", "TypeScript", path)

        dependency_technologies = {
            "fastapi": ("fastapi", "FastAPI"),
            "flask": ("flask", "Flask"),
            "django": ("django", "Django"),
            "react": ("react", "React"),
            "vite": ("vite", "Vite"),
            "next": ("nextjs", "Next.js"),
            "pytest": ("pytest", "pytest"),
            "vitest": ("vitest", "Vitest"),
        }
        for dependency, (key, label) in dependency_technologies.items():
            if dependency in dependencies:
                for path in sorted(dependencies[dependency]):
                    add(key, label, f"{path}: dependency {dependency}")

        for path in paths_named("vite.config.js", "vite.config.mjs", "vite.config.ts"):
            add("vite", "Vite", path)
        for path in paths_named("next.config.js", "next.config.mjs", "next.config.ts"):
            add("nextjs", "Next.js", path)
        for path in paths_named("pytest.ini", "tox.ini"):
            add("pytest", "pytest", path)
        for path in paths_named("vitest.config.js", "vitest.config.mjs", "vitest.config.ts"):
            add("vitest", "Vitest", path)
        for path in paths_named("dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            add("docker", "Docker", path)
        for path in sorted(
            (
                path
                for path in paths
                if path.startswith(".github/workflows/")
                and path.casefold().endswith((".yml", ".yaml"))
            ),
            key=lambda path: (path.casefold(), path),
        ):
            add("github-actions", "GitHub Actions", path)

        return [
            DetectedTechnology(
                key=key,
                label=label,
                evidence=sorted(evidence, key=lambda item: (item.casefold(), item)),
            )
            for key, label, evidence in sorted(
                (
                    (combined_key.split("|", maxsplit=1)[0], combined_key.split("|", maxsplit=1)[1], evidence)
                    for combined_key, evidence in detections.items()
                ),
                key=lambda item: (item[1].casefold(), item[0]),
            )
        ]

    @staticmethod
    def _important_files(blobs: list[TreeBlob]) -> list[ImportantFile]:
        important: list[ImportantFile] = []
        for blob in blobs:
            name = blob.name.casefold()
            kind: str | None = None
            if name in ALLOWED_MANIFEST_FILENAMES:
                kind = "manifest"
            elif name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
                kind = "container configuration"
            elif name in {"vite.config.js", "vite.config.mjs", "vite.config.ts", "next.config.js", "next.config.mjs", "next.config.ts"}:
                kind = "application configuration"
            elif name in {"pytest.ini", "tox.ini", "vitest.config.js", "vitest.config.mjs", "vitest.config.ts"}:
                kind = "test configuration"
            elif blob.path.startswith(".github/workflows/") and blob.path.casefold().endswith(
                (".yml", ".yaml")
            ):
                kind = "continuous integration workflow"
            if kind:
                important.append(ImportantFile(path=blob.path, kind=kind))

        return sorted(
            important,
            key=lambda item: (item.path.casefold(), item.path, item.kind),
        )[:MAX_IMPORTANT_FILES_RETURNED]
