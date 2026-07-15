"""Build and validate the bounded, deterministic lesson evidence catalog."""

import json
import re
import unicodedata

from ownyourcode.modules.lessons.schemas import (
    ArchitectureOrientationLessonDraft,
    EvidenceCatalog,
    EvidenceItem,
    validate_evidence_id,
)
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse


MAX_EVIDENCE_CATALOG_CHARACTERS = 12_000
MAX_LANGUAGE_EVIDENCE = 8
MAX_TECHNOLOGY_EVIDENCE = 13
MAX_FILE_EVIDENCE = 12


class EvidenceCatalogError(Exception):
    """Deterministic inspection facts could not be represented safely."""


class EvidenceGroundingError(Exception):
    """A structured model lesson did not cite the supplied catalog correctly."""


def build_evidence_catalog(
    inspection: RepositoryInspectionResponse,
) -> EvidenceCatalog:
    """Create a compact deterministic catalog without reading more repository data."""

    items: list[EvidenceItem] = []
    normalized_ids: set[str] = set()
    unsafe_path_omitted = False

    def add(item: EvidenceItem) -> None:
        normalized_id = unicodedata.normalize("NFKC", item.id).casefold()
        if normalized_id in normalized_ids:
            raise EvidenceCatalogError("Evidence ID normalization collision.")
        normalized_ids.add(normalized_id)
        items.append(
            EvidenceItem(
                id=item.id,
                kind=item.kind,
                label=_bounded_text(item.label, 240),
                detail=_bounded_text(item.detail, 360),
            )
        )

    add(
        EvidenceItem(
            id="repository:name",
            kind="repository",
            label=f"Repository: {_bounded_text(inspection.repository.full_name, 180)}",
            detail="Public repository metadata returned by the deterministic inspection.",
        )
    )
    add(
        EvidenceItem(
            id="repository:default-branch",
            kind="repository",
            label="Default branch",
            detail=_bounded_text(inspection.repository.default_branch, 180),
        )
    )
    if inspection.repository.description:
        add(
            EvidenceItem(
                id="repository:description",
                kind="repository",
                label="Repository description",
                detail=_bounded_text(inspection.repository.description, 300),
            )
        )

    for language in inspection.languages[:MAX_LANGUAGE_EVIDENCE]:
        language_id = f"language:{_normalize_id_fragment(language.name)}"
        add(
            EvidenceItem(
                id=language_id,
                kind="language",
                label=f"Language: {_bounded_text(language.name, 180)}",
                detail=f"GitHub reported {language.bytes} bytes for this language.",
            )
        )

    for technology in inspection.technologies[:MAX_TECHNOLOGY_EVIDENCE]:
        technology_id = f"technology:{_normalize_id_fragment(technology.key)}"
        add(
            EvidenceItem(
                id=technology_id,
                kind="technology",
                label=_bounded_text(technology.label, 180),
                detail=_bounded_text(
                    "Deterministically detected from: "
                    + "; ".join(technology.evidence[:3]),
                    340,
                ),
            )
        )

    for important_file in inspection.important_files[:MAX_FILE_EVIDENCE]:
        evidence_id = f"file:{important_file.path}"
        if not _is_safe_path_evidence_id(evidence_id):
            unsafe_path_omitted = True
            continue
        add(
            EvidenceItem(
                id=evidence_id,
                kind="file",
                label=_bounded_text(important_file.path, 220),
                detail=f"Deterministic classification: {_bounded_text(important_file.kind, 160)}.",
            )
        )

    catalog_limitations = list(inspection.limitations[:5])
    if unsafe_path_omitted:
        catalog_limitations.append(
            "Unsafe path-based evidence was omitted from the lesson catalog."
        )

    catalog = EvidenceCatalog(items=items, catalog_limitations=catalog_limitations[:6])
    while _serialized_catalog_length(catalog) > MAX_EVIDENCE_CATALOG_CHARACTERS:
        file_index = next(
            (
                index
                for index in range(len(catalog.items) - 1, -1, -1)
                if catalog.items[index].kind == "file"
            ),
            None,
        )
        if file_index is None:
            raise EvidenceCatalogError("Evidence catalog exceeded its bounded size.")
        catalog.items.pop(file_index)
        if "File evidence was reduced to fit the bounded lesson catalog." not in catalog.catalog_limitations:
            catalog.catalog_limitations.append(
                "File evidence was reduced to fit the bounded lesson catalog."
            )
            catalog.catalog_limitations = catalog.catalog_limitations[:6]

    return catalog


def validate_lesson_evidence(
    lesson: ArchitectureOrientationLessonDraft,
    catalog: EvidenceCatalog,
) -> None:
    """Ensure every model citation references one unique known catalog item."""

    known_ids = {item.id for item in catalog.items}
    citation_lists = [lesson.repository_summary_evidence_ids]
    citation_lists.extend(concept.evidence_ids for concept in lesson.concepts)
    citation_lists.extend(step.evidence_ids for step in lesson.architecture_walkthrough)

    for citation_ids in citation_lists:
        if not citation_ids:
            raise EvidenceGroundingError("Each explanatory section needs evidence.")
        if len(set(citation_ids)) != len(citation_ids):
            raise EvidenceGroundingError("Duplicate evidence IDs are not allowed.")
        for evidence_id in citation_ids:
            try:
                validate_evidence_id(evidence_id)
            except ValueError as error:
                raise EvidenceGroundingError("Unsafe evidence ID.") from error
            if evidence_id not in known_ids:
                raise EvidenceGroundingError("Unknown evidence ID.")


def _normalize_id_fragment(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or "unnamed"


def _is_safe_path_evidence_id(value: str) -> bool:
    try:
        validate_evidence_id(value)
    except ValueError:
        return False
    return value == value.strip()


def _bounded_text(value: str, maximum_length: int) -> str:
    normalized_value = unicodedata.normalize("NFKC", value)
    normalized_value = "".join(
        " " if character.isspace() or unicodedata.category(character) == "Cc" else character
        for character in normalized_value
    )
    normalized_value = re.sub(r"\s+", " ", normalized_value).strip()
    return normalized_value[:maximum_length]


def _serialized_catalog_length(catalog: EvidenceCatalog) -> int:
    return len(
        json.dumps(
            catalog.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        )
    )
