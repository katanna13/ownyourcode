"""Deterministic eligibility and frozen definitions for the initial three modules."""

from __future__ import annotations

from dataclasses import dataclass

from ownyourcode.modules.labs.verifier import STARTER_CODE as HEALTH_CHECK_STARTER_CODE
from ownyourcode.modules.learning_paths.schemas import (
    Choice,
    LEARNING_PATH_PLANNER_VERSION,
    PrivateActivityDefinition,
    PublicActivityDefinition,
    StoredActivityDefinition,
    StoredModuleDefinition,
    fingerprint,
)
from ownyourcode.modules.lessons.schemas import EvidenceCatalog, LearnerLevel


@dataclass(frozen=True)
class PlannedModule:
    definition: StoredModuleDefinition
    definition_fingerprint: str


@dataclass(frozen=True)
class PlannedLearningPath:
    modules: list[PlannedModule]
    limitations: list[str]


def plan_learning_path(*, catalog: EvidenceCatalog, learner_level: LearnerLevel) -> PlannedLearningPath:
    """Choose supported modules before any learner-facing prose is constructed."""

    by_id = {item.id: item for item in catalog.items}
    modules = [_orientation_module(catalog, learner_level)]
    architecture = _architecture_module(by_id, learner_level)
    if architecture is None:
        architecture_limitation = "No architecture-boundaries module was created because fewer than two supported boundary categories were confirmed."
    else:
        modules.append(architecture)
        architecture_limitation = None
    validation = _validation_module(by_id, learner_level)
    if validation is None:
        validation_limitation = "No validation module was created because deterministic inspection did not confirm both Python and FastAPI."
    else:
        modules.append(validation)
        validation_limitation = None

    limitations = list(catalog.catalog_limitations)
    limitations.append("Testing and security modules are intentionally outside this first three-module Phase 12 vertical slice.")
    if architecture_limitation:
        limitations.append(architecture_limitation)
    if validation_limitation:
        limitations.append(validation_limitation)
    return PlannedLearningPath(modules=modules, limitations=limitations[:8])


def _orientation_module(catalog: EvidenceCatalog, learner_level: LearnerLevel) -> PlannedModule:
    target = next((item for item in catalog.items if item.kind == "technology"), catalog.items[0])
    choices = [target, *[item for item in catalog.items if item.id != target.id][:3]]
    evidence_ids = [item.id for item in choices]
    activity = StoredActivityDefinition(
        public=PublicActivityDefinition(
            id="orientation-evidence.v1",
            presentation_kind="single_choice",
            context_id=fingerprint({"activity": "orientation-evidence.v1", "level": learner_level.value, "evidence": evidence_ids}),
            prompt="Which one confirmed evidence item directly supports the highlighted repository-orientation claim?",
            evidence_ids=evidence_ids,
            choices=[Choice(id=item.id, label=item.label) for item in choices],
            constraints=["Select one item from the bounded deterministic evidence catalog."],
        ),
        private=PrivateActivityDefinition(evaluator_key="orientation-evidence.v1", expected_choice_id=target.id),
        completion_role="required_completion",
    )
    definition = StoredModuleDefinition(
        module_key="repository-orientation.v1",
        category="repository_orientation",
        title="Orient yourself in the confirmed repository evidence",
        objective="Identify what the bounded inspection actually confirms before making claims about the repository.",
        evidence_ids=evidence_ids,
        lesson_sections=[
            "This module uses a bounded deterministic evidence catalog. Confirmed technologies are useful starting points, not proof that every source file was reviewed.",
        ],
        activities=[activity],
        limitations=list(catalog.catalog_limitations),
    )
    return PlannedModule(definition=definition, definition_fingerprint=fingerprint(definition.model_dump(mode="json")))


def _architecture_module(by_id: dict[str, object], learner_level: LearnerLevel) -> PlannedModule | None:
    selected = [
        evidence_id
        for evidence_id in ("technology:react", "technology:nextjs", "technology:fastapi", "technology:docker")
        if evidence_id in by_id
    ]
    frontend = next((value for value in ("technology:react", "technology:nextjs") if value in selected), None)
    categories = [value for value in (frontend, "technology:fastapi", "technology:docker") if value]
    if len(categories) < 2:
        return None
    steps = [
        Choice(id="activity:browser", label="Browser boundary receives the learner action."),
        Choice(id="activity:api", label="API boundary validates the request."),
        Choice(id="activity:response", label="A JSON response returns across the boundary."),
    ]
    activity = StoredActivityDefinition(
        public=PublicActivityDefinition(
            id="architecture-ordering.v1",
            presentation_kind="step_order",
            context_id=fingerprint({"activity": "architecture-ordering.v1", "level": learner_level.value, "evidence": categories}),
            prompt="Order this teaching flow from learner action to the validated response. It practices detected boundaries; it does not claim a specific uninspected route exists.",
            evidence_ids=categories,
            choices=[steps[1], steps[2], steps[0]],
            constraints=["Use each teaching-flow step exactly once."],
        ),
        private=PrivateActivityDefinition(evaluator_key="architecture-ordering.v1", expected_order=[step.id for step in steps]),
        completion_role="required_gate",
    )
    definition = StoredModuleDefinition(
        module_key="architecture-boundaries.v1",
        category="architecture_boundaries",
        title="Trace responsibilities across confirmed boundaries",
        objective="Practice distinguishing browser, API, and optional container responsibilities from confirmed boundary evidence.",
        evidence_ids=categories,
        lesson_sections=[
            "Confirmed framework and container evidence can identify likely responsibility boundaries. It cannot prove a complete runtime request path without source-level inspection.",
        ],
        activities=[activity],
        limitations=["The ordered flow is a server-owned teaching example, not a claim about a specific repository endpoint."],
    )
    return PlannedModule(definition=definition, definition_fingerprint=fingerprint(definition.model_dump(mode="json")))


def _validation_module(by_id: dict[str, object], learner_level: LearnerLevel) -> PlannedModule | None:
    python = "language:python" if "language:python" in by_id else "technology:python" if "technology:python" in by_id else None
    if python is None or "technology:fastapi" not in by_id:
        return None
    evidence_ids = [python, "technology:fastapi"]
    activity = StoredActivityDefinition(
        public=PublicActivityDefinition(
            id="fastapi-health-fixture.v1",
            presentation_kind="code_fixture",
            context_id=fingerprint({"activity": "fastapi-health-fixture.v1", "level": learner_level.value, "evidence": evidence_ids}),
            prompt="Update this teaching fixture so healthz returns the required literal response.",
            evidence_ids=evidence_ids,
            starter_code=HEALTH_CHECK_STARTER_CODE,
            constraints=[
                "Teaching fixture — not repository source.",
                "The source is parsed with AST only and is never executed.",
            ],
        ),
        private=PrivateActivityDefinition(evaluator_key="fastapi-health-fixture.v1"),
        completion_role="required_gate",
    )
    definition = StoredModuleDefinition(
        module_key="validation-failure-paths.v1",
        category="validation_failure_paths",
        title="Verify a bounded FastAPI-style response",
        objective="Practice a predictable literal response for a confirmed Python and FastAPI-oriented stack.",
        evidence_ids=evidence_ids,
        lesson_sections=[
            "A deterministic verifier can check this small teaching fixture structurally. It does not run the learner code or inspect repository source files.",
        ],
        activities=[activity],
        limitations=["This fixture teaches a FastAPI-style concept and does not prove the repository has this exact health-check implementation."],
    )
    return PlannedModule(definition=definition, definition_fingerprint=fingerprint(definition.model_dump(mode="json")))
