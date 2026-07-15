"""Build deterministic, learner-visible assessment definitions from evidence."""

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, TypeVar

from ownyourcode.modules.lessons.schemas import EvidenceCatalog, EvidenceItem, LearnerLevel

from ownyourcode.modules.assessments.schemas import (
    ASSESSMENT_DEFINITION_VERSION,
    EVIDENCE_SELECTION_QUESTION_ID,
    EXPLAIN_BACK_QUESTION_ID,
    EXPLAIN_BACK_RUBRIC_VERSION,
    MULTIPLE_CHOICE_QUESTION_ID,
    AssessmentEvidenceChoice,
    AssessmentQuestion,
    EvidenceSelectionQuestion,
    ExplainBackQuestion,
    MultipleChoiceOption,
    MultipleChoiceQuestion,
)


T = TypeVar("T")
PUBLIC_OPTION_IDS = ("option-a", "option-b", "option-c", "option-d")
_SUPPORTED_EVIDENCE_STATEMENT = "supported-evidence-statement"


@dataclass(frozen=True)
class AssessmentDefinition:
    """Server-owned answer keys paired with a public question definition."""

    context_id: str
    questions: list[AssessmentQuestion]
    target_evidence: EvidenceItem
    evidence_selection_correct_id: str
    multiple_choice_correct_option_id: str


def build_assessment_definition(
    *, repository_url: str, learner_level: LearnerLevel, catalog: EvidenceCatalog
) -> AssessmentDefinition:
    """Pick one stable target and never include answer keys in public questions."""

    target = _select_target_evidence(catalog)
    ordering_context = _ordering_context(
        repository_url=repository_url,
        learner_level=learner_level,
        target_evidence_id=target.id,
    )
    choice_items = _stable_order(
        _select_choices(catalog, target, maximum=4),
        ordering_context=ordering_context,
        identifier=lambda item: item.id,
    )
    choices = [
        AssessmentEvidenceChoice(id=item.id, label=item.label) for item in choice_items
    ]
    private_multiple_choice_options = [
        (
            _SUPPORTED_EVIDENCE_STATEMENT,
            f"{target.label} is represented in the deterministic evidence catalog.",
        ),
        ("full-source-review-statement", "The full source tree was reviewed."),
        ("security-scan-statement", "A security scan ruled out known risks."),
        ("saved-project-statement", "A project and assessment result were saved."),
    ]
    ordered_multiple_choice_options = _stable_order(
        private_multiple_choice_options,
        ordering_context=ordering_context,
        identifier=lambda option: option[0],
    )
    public_multiple_choice_options = [
        MultipleChoiceOption(id=option_id, label=option[1])
        for option_id, option in zip(PUBLIC_OPTION_IDS, ordered_multiple_choice_options)
    ]
    correct_option_id = next(
        option_id
        for option_id, option in zip(PUBLIC_OPTION_IDS, ordered_multiple_choice_options)
        if option[0] == _SUPPORTED_EVIDENCE_STATEMENT
    )
    wording = _wording_for_level(learner_level)
    questions: list[AssessmentQuestion] = [
        MultipleChoiceQuestion(
            id=MULTIPLE_CHOICE_QUESTION_ID,
            type="multiple_choice",
            prompt=(
                f"{wording} Which statement is supported by the bounded repository "
                "orientation evidence?"
            ),
            options=public_multiple_choice_options,
        ),
        EvidenceSelectionQuestion(
            id=EVIDENCE_SELECTION_QUESTION_ID,
            type="evidence_selection",
            prompt=(
                f"{wording} Select the one evidence item that directly supports "
                f"the target: {target.label}."
            ),
            evidence_choices=choices,
        ),
        ExplainBackQuestion(
            id=EXPLAIN_BACK_QUESTION_ID,
            type="explain_back",
            prompt=(
                f"{wording} In your own words, explain what the target evidence "
                f"({target.label}) tells you about this repository. Cite one or two choices."
            ),
            evidence_choices=choices,
        ),
    ]
    return AssessmentDefinition(
        context_id=_context_fingerprint(
            repository_url=repository_url,
            learner_level=learner_level,
            catalog=catalog,
            target=target,
        ),
        questions=questions,
        target_evidence=target,
        evidence_selection_correct_id=target.id,
        multiple_choice_correct_option_id=correct_option_id,
    )


def _select_target_evidence(catalog: EvidenceCatalog) -> EvidenceItem:
    for kind in ("technology", "language", "repository"):
        if item := next((item for item in catalog.items if item.kind == kind), None):
            return item
    return catalog.items[0]


def _select_choices(
    catalog: EvidenceCatalog, target: EvidenceItem, *, maximum: int
) -> list[EvidenceItem]:
    others = [item for item in catalog.items if item.id != target.id]
    return [target, *others[: maximum - 1]]


def _wording_for_level(learner_level: LearnerLevel) -> str:
    if learner_level is LearnerLevel.BEGINNER:
        return "Start with the confirmed facts."
    if learner_level is LearnerLevel.JUNIOR:
        return "Use the confirmed inspection evidence."
    return "Reason from the bounded inspection evidence."


def _ordering_context(
    *, repository_url: str, learner_level: LearnerLevel, target_evidence_id: str
) -> str:
    """Canonical public context used only to produce a stable display order."""

    return json.dumps(
        {
            "assessment_definition_version": ASSESSMENT_DEFINITION_VERSION,
            "learner_level": learner_level.value,
            "repository_url": repository_url,
            "target_evidence_id": target_evidence_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _stable_order(
    values: list[T], *, ordering_context: str, identifier: Callable[[T], str]
) -> list[T]:
    """Order bounded choices reproducibly without giving the target a fixed index."""

    return sorted(
        values,
        key=lambda value: hashlib.sha256(
            f"{ordering_context}:{identifier(value)}".encode("utf-8")
        ).hexdigest(),
    )


def _context_fingerprint(
    *,
    repository_url: str,
    learner_level: LearnerLevel,
    catalog: EvidenceCatalog,
    target: EvidenceItem,
) -> str:
    """Hash stable context values for freshness only, never authorization."""

    canonical_context = {
        "assessment_definition_version": ASSESSMENT_DEFINITION_VERSION,
        "catalog": catalog.model_dump(mode="json"),
        "learner_level": learner_level.value,
        "repository_url": repository_url,
        "rubric_version": EXPLAIN_BACK_RUBRIC_VERSION,
        "target_evidence": target.model_dump(mode="json"),
    }
    serialized = json.dumps(
        canonical_context,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
