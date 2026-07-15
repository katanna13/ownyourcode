"""Deterministically select one evidence-grounded architecture oral defense."""

from dataclasses import dataclass
import hashlib
import json

from ownyourcode.modules.lessons.schemas import EvidenceCatalog, LearnerLevel
from ownyourcode.modules.oral_defenses.schemas import (
    BoundaryCategory,
    BoundaryEvidence,
    EVIDENCE_GROUNDING_RUBRIC_ID,
    ORAL_DEFENSE_QUESTION_DEFINITION_VERSION,
    ORAL_DEFENSE_RUBRIC_VERSION,
    OralDefenseModelEvaluation,
    OralDefenseQuestion,
    SUPPORTED_BOUNDARIES_RUBRIC_ID,
    ARCHITECTURE_BOUNDARIES_QUESTION_ID,
)


_CATEGORY_EVIDENCE_PRIORITIES: tuple[tuple[BoundaryCategory, tuple[str, ...]], ...] = (
    (
        "frontend",
        (
            "technology:react",
            "technology:nextjs",
        ),
    ),
    ("backend", ("technology:fastapi",)),
    ("container", ("technology:docker",)),
)


class OralDefenseGroundingError(Exception):
    """The structured model evaluation conflicts with fresh selected evidence."""


@dataclass(frozen=True)
class OralDefenseDefinition:
    """A server-owned question and its bounded evidence domain."""

    context_id: str
    question: OralDefenseQuestion


def build_oral_defense_definition(
    *,
    repository_url: str,
    learner_level: LearnerLevel,
    catalog: EvidenceCatalog,
) -> OralDefenseDefinition | None:
    """Build one stable template only when two real boundaries are confirmed."""

    boundary_evidence = _select_boundary_evidence(catalog)
    if len(boundary_evidence) < 2:
        return None
    categories = [item.category for item in boundary_evidence]
    question = OralDefenseQuestion(
        id=ARCHITECTURE_BOUNDARIES_QUESTION_ID,
        prompt=_question_prompt(categories, learner_level),
        boundary_evidence=boundary_evidence,
    )
    return OralDefenseDefinition(
        context_id=_context_fingerprint(
            repository_url=repository_url,
            learner_level=learner_level,
            boundary_evidence=boundary_evidence,
        ),
        question=question,
    )


def validate_model_evidence(
    evaluation: OralDefenseModelEvaluation,
    definition: OralDefenseDefinition,
) -> None:
    """Require model citations to be known and consistent with awarded signals."""

    selected_by_id = {
        item.evidence.id: item for item in definition.question.boundary_evidence
    }
    if any(evidence_id not in selected_by_id for evidence_id in evaluation.evidence_ids):
        raise OralDefenseGroundingError("Unknown oral-defense evidence ID.")

    earned_by_id = {
        dimension.id: dimension.earned_points
        for dimension in evaluation.rubric_dimensions
    }
    if earned_by_id[EVIDENCE_GROUNDING_RUBRIC_ID] == 1 and not evaluation.evidence_ids:
        raise OralDefenseGroundingError(
            "Evidence grounding requires at least one selected evidence ID."
        )
    if earned_by_id[SUPPORTED_BOUNDARIES_RUBRIC_ID] == 1:
        covered_categories = {
            selected_by_id[evidence_id].category for evidence_id in evaluation.evidence_ids
        }
        if len(covered_categories) < 2:
            raise OralDefenseGroundingError(
                "Supported boundaries require evidence from two selected categories."
            )


def _select_boundary_evidence(catalog: EvidenceCatalog) -> list[BoundaryEvidence]:
    by_id = {item.id: item for item in catalog.items}
    selected: list[BoundaryEvidence] = []
    for category, priorities in _CATEGORY_EVIDENCE_PRIORITIES:
        evidence = next(
            (by_id[evidence_id] for evidence_id in priorities if evidence_id in by_id),
            None,
        )
        if evidence is not None:
            selected.append(BoundaryEvidence(category=category, evidence=evidence))
    return selected


def _question_prompt(
    categories: list[BoundaryCategory], learner_level: LearnerLevel
) -> str:
    category_phrase = _category_phrase(categories)
    level_direction = {
        LearnerLevel.BEGINNER: "Use plain responsibility words.",
        LearnerLevel.JUNIOR: "Connect responsibilities to the confirmed evidence.",
        LearnerLevel.INTERMEDIATE: "Separate confirmed facts from reasonable assumptions.",
    }[learner_level]
    return (
        f"Using only the confirmed evidence, explain how the detected {category_phrase} "
        f"boundaries could divide responsibilities in this repository. {level_direction} "
        "State one inspection limitation or assumption, then describe one reasonable "
        "engineering trade-off or next investigation step."
    )


def _category_phrase(categories: list[BoundaryCategory]) -> str:
    names = list(categories)
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]}, {names[1]}, and {names[2]}"


def _context_fingerprint(
    *,
    repository_url: str,
    learner_level: LearnerLevel,
    boundary_evidence: list[BoundaryEvidence],
    question_definition_version: str = ORAL_DEFENSE_QUESTION_DEFINITION_VERSION,
    rubric_version: str = ORAL_DEFENSE_RUBRIC_VERSION,
) -> str:
    """Hash freshness values only; the result is neither a secret nor authorization."""

    canonical_context = {
        "learner_level": learner_level.value,
        "question_definition_version": question_definition_version,
        "repository_url": repository_url,
        "rubric_version": rubric_version,
        "selected_boundary_categories": [item.category for item in boundary_evidence],
        "selected_evidence": [
            item.evidence.model_dump(mode="json") for item in boundary_evidence
        ],
    }
    serialized = json.dumps(
        canonical_context,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
