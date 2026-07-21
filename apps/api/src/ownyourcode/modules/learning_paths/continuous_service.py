"""Owner-scoped continuous learning over immutable Phase 12 path records."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
import unicodedata
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ownyourcode.core.config import get_settings
from ownyourcode.modules.labs.verifier import STARTER_CODE as HEALTH_CHECK_STARTER_CODE
from ownyourcode.modules.labs.verifier import verify_fastapi_health_check
from ownyourcode.modules.learning_paths.continuous_openai import (
    ContinuousLearningConnectivityError,
    ContinuousLearningProviderError,
    ContinuousLearningRateLimitedError,
    ContinuousLearningRefusalError,
    ContinuousLearningTimeoutError,
    ContinuousLearningUpstreamError,
    OpenAIContinuousLearningClient,
)
from ownyourcode.modules.learning_paths.continuous_schemas import (
    CONTINUOUS_EVALUATION_PROMPT_VERSION,
    CONTINUOUS_LESSON_CONTRACT_VERSION,
    CONTINUOUS_LESSON_PROMPT_VERSION,
    MAX_CONTINUOUS_LESSONS_RETURNED,
    ContinuousChoice,
    ContinuousLearningResponse,
    ContinuousLessonAttemptRequest,
    ContinuousLessonAttemptResponse,
    ContinuousLessonCheck,
    ContinuousLessonDraft,
    ContinuousLessonResponse,
    ContinuousLessonReview,
    ContinuousPrivateActivity,
    ContinuousPublicActivity,
    ContinuousStoredLessonDefinition,
    DraftAstActivity,
    DraftChoiceActivity,
    DraftEvidenceActivity,
    DraftOrderingActivity,
    DraftTextActivity,
)
from ownyourcode.modules.learning_paths.models import (
    LearningPathGenerationState,
    ModuleAdaptationKind,
    ModuleAdaptationState,
    ModuleProgressState,
    ProjectLearningModule,
    ProjectLearningPathVersion,
    ProjectModuleAdaptation,
    ProjectModuleAttempt,
    ProjectModuleProgress,
)
from ownyourcode.modules.learning_paths.schemas import fingerprint
from ownyourcode.modules.learning_paths.service import (
    LearningPathActivityUnavailableError,
    LearningPathConflictError,
    LearningPathContextStaleError,
    LearningPathService,
)
from ownyourcode.modules.learning_workspaces.models import ProjectInspectionSnapshot
from ownyourcode.modules.learning_workspaces.repository import LearningWorkspaceRepository
from ownyourcode.modules.learning_workspaces.schemas import StoredInspectionSnapshotPayload
from ownyourcode.modules.lessons.schemas import EvidenceCatalog, LearnerLevel


PENDING_RECORD_TYPE = "continuous-lesson-pending.v1"
FORMAT_ROTATION: tuple[tuple[str, str], ...] = (
    ("explain_confirmed_concept", "explain_back"),
    ("predict_data_flow_outcome", "test_interpretation"),
    ("identify_repository_evidence", "evidence_selection"),
    ("order_architecture_boundaries", "ordering"),
    ("debug_bounded_teaching_fixture", "ast_fixture"),
    ("interpret_deterministic_test_output", "test_interpretation"),
    ("compare_engineering_tradeoffs", "trade_off"),
    ("defend_architecture_decision", "explain_back"),
    ("review_security_configuration", "test_interpretation"),
)
EVALUATOR_KEYS = {
    "evidence_selection": "continuous-evidence-selection.v1",
    "ordering": "continuous-ordering.v1",
    "test_interpretation": "continuous-test-interpretation.v1",
    "ast_fixture": "continuous-fastapi-fixture.v1",
    "explain_back": "continuous-explain-back.v1",
    "trade_off": "continuous-trade-off.v1",
}
EXAMPLE_HEALTHZ_SOLUTION = (
    'def healthz():\n'
    '    return {"status": "ok", "service": "ownyourcode-api"}\n'
)


class ContinuousLearningUnavailableError(Exception):
    pass


class ContinuousLearningDuplicateError(Exception):
    pass


class ContinuousLearningService:
    def __init__(
        self,
        repository: LearningWorkspaceRepository | None = None,
        client: OpenAIContinuousLearningClient | Any | None = None,
    ) -> None:
        self._repository = repository or LearningWorkspaceRepository()
        self._paths = LearningPathService(self._repository)
        self._client = client or OpenAIContinuousLearningClient(get_settings())

    def list_lessons(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
    ) -> ContinuousLearningResponse:
        path, snapshot = self._paths._current_path(session, owner_id, project_id)
        complete, _ = self._completed_anchor(session, path)
        definitions = self._stored_adaptations(session, path)[-MAX_CONTINUOUS_LESSONS_RETURNED:]
        lessons = [self._lesson_response(session, adaptation, definition) for adaptation, definition in definitions]
        active = next((lesson.id for lesson in lessons if not lesson.completed), None)
        resume = active or (lessons[-1].id if lessons else None)
        catalog = self._snapshot_payload(snapshot).evidence_catalog
        return ContinuousLearningResponse(
            available=complete,
            evidence_catalog=catalog.items,
            lessons=lessons,
            resume_lesson_id=resume,
        )

    def generate_lesson(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        idempotency_key: str,
    ) -> ContinuousLearningResponse:
        self._client.ensure_configured()
        request_hash = fingerprint({"operation": "generate-continuous-lesson", "contract": CONTINUOUS_LESSON_CONTRACT_VERSION})
        pending_id: UUID | None = None
        try:
            with session.begin():
                path, snapshot = self._paths._current_path(session, owner_id, project_id, lock=True)
                complete, anchor = self._completed_anchor(session, path)
                if not complete or anchor is None:
                    raise ContinuousLearningUnavailableError()
                records = self._all_continuous_adaptations(session, path)
                existing = self._find_generation(records, idempotency_key)
                if existing is not None:
                    payload = existing.definition_payload or {}
                    if payload.get("generation_request_hash") != request_hash:
                        raise LearningPathConflictError()
                    if payload.get("record_type") == PENDING_RECORD_TYPE:
                        raise LearningPathConflictError()
                    return self.list_lessons(session, owner_id, project_id)
                if any(
                    item.state == ModuleAdaptationState.AVAILABLE
                    and (item.definition_payload or {}).get("record_type") in {PENDING_RECORD_TYPE, CONTINUOUS_LESSON_CONTRACT_VERSION}
                    for item in records
                ):
                    raise ContinuousLearningUnavailableError()
                stored = self._stored_definitions(records)
                sequence = max((definition.sequence for _, definition in stored), default=0) + 1
                trigger = session.scalar(
                    select(ProjectModuleAttempt)
                    .where(
                        ProjectModuleAttempt.path_version_id == path.id,
                        ProjectModuleAttempt.project_id == project_id,
                        ProjectModuleAttempt.state == LearningPathGenerationState.COMPLETED,
                    )
                    .order_by(ProjectModuleAttempt.completed_at.desc().nullslast(), ProjectModuleAttempt.created_at.desc())
                    .limit(1)
                )
                if trigger is None:
                    raise ContinuousLearningUnavailableError()
                pending_id = uuid4()
                pending = ProjectModuleAdaptation(
                    id=pending_id,
                    project_id=project_id,
                    path_version_id=path.id,
                    module_id=anchor.id,
                    trigger_attempt_id=trigger.id,
                    kind=ModuleAdaptationKind.OPTIONAL_STRETCH,
                    rule_id=f"continuous-lesson-{sequence}",
                    rule_version=CONTINUOUS_LESSON_PROMPT_VERSION,
                    learner_reason="Generated after the deterministic path was completed.",
                    required=False,
                    activity_id=f"continuous-pending-{pending_id.hex[:12]}",
                    context_fingerprint=fingerprint({"pending": pending_id.hex, "snapshot": snapshot.evidence_fingerprint}),
                    definition_payload={
                        "record_type": PENDING_RECORD_TYPE,
                        "sequence": sequence,
                        "generation_idempotency_key": idempotency_key,
                        "generation_request_hash": request_hash,
                    },
                    state=ModuleAdaptationState.AVAILABLE,
                )
                session.add(pending)
                catalog = self._snapshot_payload(snapshot).evidence_catalog
                plan = self._generation_plan(sequence, catalog)
                history = self._history_context(session, path, stored)
                generation_context = self._generation_context(path, snapshot, catalog, plan, history)

            definition: ContinuousStoredLessonDefinition | None = None
            rejected: dict[str, Any] | None = None
            for attempt_number in range(2):
                context = dict(generation_context)
                if rejected is not None:
                    context["rejected_duplicate_candidate"] = rejected
                    context["novelty_instruction"] = "Change the focus, framing, or difficulty from this rejected candidate."
                try:
                    candidate = self._client.generate(context)
                except (
                    ContinuousLearningConnectivityError,
                    ContinuousLearningRateLimitedError,
                    ContinuousLearningRefusalError,
                    ContinuousLearningTimeoutError,
                    ContinuousLearningUpstreamError,
                ):
                    raise
                except ContinuousLearningProviderError:
                    if attempt_number == 0:
                        continue
                    break
                try:
                    if candidate.activity.activity_type != plan["activity_type"]:
                        raise ContinuousLearningProviderError()
                    if self._is_duplicate(candidate, history["continuous_lessons"]):
                        rejected = {
                            "title": _safe_text(candidate.title, 100),
                            "focus": _safe_text(candidate.focus, 220),
                            "activity_type": candidate.activity.activity_type,
                        }
                        if attempt_number == 1:
                            raise ContinuousLearningDuplicateError()
                        continue
                    definition = self._build_definition(
                        path=path,
                        snapshot=snapshot,
                        catalog=catalog,
                        sequence=sequence,
                        plan=plan,
                        draft=candidate,
                        history=history,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                    break
                except ContinuousLearningProviderError:
                    if attempt_number == 0:
                        continue
            if definition is None:
                fallback_plan, fallback_draft = self._deterministic_fallback(sequence, catalog, plan["difficulty"])
                definition = self._build_definition(
                    path=path,
                    snapshot=snapshot,
                    catalog=catalog,
                    sequence=sequence,
                    plan=fallback_plan,
                    draft=fallback_draft,
                    history=history,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )

            with session.begin():
                current_path, current_snapshot = self._paths._current_path(session, owner_id, project_id, lock=True)
                if current_path.id != path.id or current_snapshot.id != snapshot.id:
                    raise LearningPathContextStaleError()
                pending = session.get(ProjectModuleAdaptation, pending_id)
                if pending is None or (pending.definition_payload or {}).get("record_type") != PENDING_RECORD_TYPE:
                    raise LearningPathConflictError()
                pending.activity_id = definition.public_activity.id
                pending.context_fingerprint = definition.public_activity.context_id
                pending.definition_payload = definition.model_dump(mode="json")
            return self.list_lessons(session, owner_id, project_id)
        except Exception:
            if pending_id is not None:
                try:
                    with session.begin():
                        pending = session.get(ProjectModuleAdaptation, pending_id)
                        if pending is not None and (pending.definition_payload or {}).get("record_type") == PENDING_RECORD_TYPE:
                            session.delete(pending)
                except Exception:
                    session.rollback()
            raise

    def submit_attempt(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        lesson_id: UUID,
        request: ContinuousLessonAttemptRequest,
        idempotency_key: str,
    ) -> ContinuousLessonAttemptResponse:
        request_hash = fingerprint(request.model_dump(mode="json"))
        with session.begin():
            path, snapshot = self._paths._current_path(session, owner_id, project_id, lock=True)
            complete, _ = self._completed_anchor(session, path)
            if not complete:
                raise ContinuousLearningUnavailableError()
            adaptation, definition = self._lesson(session, path, project_id, lesson_id, lock=True)
            if definition.source_inspection_snapshot_id != snapshot.id or definition.source_evidence_fingerprint != snapshot.evidence_fingerprint:
                raise LearningPathContextStaleError()
            if request.context_id != definition.public_activity.context_id:
                raise LearningPathContextStaleError()
            existing = session.scalar(
                select(ProjectModuleAttempt).where(
                    ProjectModuleAttempt.module_id == adaptation.module_id,
                    ProjectModuleAttempt.activity_id == definition.public_activity.id,
                    ProjectModuleAttempt.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_hash != request_hash or existing.state != LearningPathGenerationState.COMPLETED:
                    raise LearningPathConflictError()
                return ContinuousLessonAttemptResponse(lesson=self._lesson_response(session, adaptation, definition))
            if adaptation.state == ModuleAdaptationState.COMPLETED:
                raise ContinuousLearningUnavailableError()
            self._validate_submission(definition.public_activity, request)
            attempt = ProjectModuleAttempt(
                id=uuid4(),
                project_id=project_id,
                path_version_id=path.id,
                module_id=adaptation.module_id,
                activity_id=definition.public_activity.id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                state=LearningPathGenerationState.PENDING,
                context_fingerprint=request.context_id,
                submitted_payload=request.model_dump(mode="json"),
            )
            session.add(attempt)

        try:
            passed, earned_points, result = self._evaluate(definition, request, snapshot)
        except Exception:
            with session.begin():
                stored = session.get(ProjectModuleAttempt, attempt.id)
                if stored is not None:
                    stored.state = LearningPathGenerationState.FAILED
                    stored.failure_code = "evaluation_failed"
            raise

        with session.begin():
            current_path, current_snapshot = self._paths._current_path(session, owner_id, project_id, lock=True)
            if current_path.id != path.id or current_snapshot.id != snapshot.id:
                raise LearningPathContextStaleError()
            adaptation = session.get(ProjectModuleAdaptation, lesson_id)
            stored = session.get(ProjectModuleAttempt, attempt.id)
            if adaptation is None or stored is None or stored.state != LearningPathGenerationState.PENDING:
                raise LearningPathConflictError()
            now = datetime.now(timezone.utc)
            stored.state = LearningPathGenerationState.COMPLETED
            stored.passed = passed
            stored.earned_points = earned_points
            stored.result_payload = result
            stored.completed_at = now
            if passed:
                adaptation.state = ModuleAdaptationState.COMPLETED
                adaptation.completed_at = now
        return ContinuousLessonAttemptResponse(lesson=self._lesson_response(session, adaptation, definition))

    def _evaluate(
        self,
        definition: ContinuousStoredLessonDefinition,
        request: ContinuousLessonAttemptRequest,
        snapshot: ProjectInspectionSnapshot,
    ) -> tuple[bool, int | None, dict[str, Any]]:
        public = definition.public_activity
        private = definition.private_activity
        if private.evaluator_key in {"continuous-evidence-selection.v1", "continuous-test-interpretation.v1"}:
            passed = request.selected_choice_id == private.expected_choice_id
            return passed, int(passed), {
                "feedback": "Your selection is supported by the frozen lesson definition." if passed else "Compare your selection with the confirmed evidence and teaching explanation.",
                "checks": [{"id": "selected-answer.v1", "passed": passed, "message": "The submitted choice matches the expected teaching answer." if passed else "The submitted choice does not match the expected teaching answer."}],
            }
        if private.evaluator_key == "continuous-ordering.v1":
            passed = request.ordered_step_ids == private.expected_order
            return passed, int(passed), {
                "feedback": "The boundaries are in the expected teaching order." if passed else "Revisit how responsibility crosses the illustrated boundaries.",
                "checks": [{"id": "ordered-boundaries.v1", "passed": passed, "message": "Every step is in the expected order." if passed else "One or more steps are out of order."}],
            }
        if private.evaluator_key == "continuous-fastapi-fixture.v1":
            verification = verify_fastapi_health_check(request.source_code or "")
            return verification.passed, None, {
                "feedback": "The AST-only fixture checks passed." if verification.passed else "Review the failed AST-only checks; the submitted code was never executed.",
                "checks": [item.model_dump(mode="json") for item in verification.checks],
            }
        if private.evaluator_key in {"continuous-explain-back.v1", "continuous-trade-off.v1"}:
            self._client.ensure_configured()
            payload = self._snapshot_payload(snapshot)
            by_id = {item.id: item for item in payload.evidence_catalog.items}
            evaluation = self._client.evaluate({
                "activity_type": public.activity_type,
                "lesson_focus": definition.focus,
                "prompt": public.prompt,
                "reference_answer": private.reference_answer,
                "rubric": private.evaluation_rubric,
                "confirmed_evidence": [by_id[item].model_dump(mode="json") for item in public.evidence_ids if item in by_id],
                "learner_answer": request.answer_text,
            })
            if len(evaluation.evidence_ids) != len(set(evaluation.evidence_ids)) or any(item not in public.evidence_ids for item in evaluation.evidence_ids):
                raise ContinuousLearningProviderError()
            return True, evaluation.points, {
                "feedback": evaluation.feedback,
                "evidence_ids": evaluation.evidence_ids,
                "evaluation_prompt_version": CONTINUOUS_EVALUATION_PROMPT_VERSION,
            }
        raise LearningPathActivityUnavailableError()

    @staticmethod
    def _validate_submission(public: ContinuousPublicActivity, request: ContinuousLessonAttemptRequest) -> None:
        if public.activity_type in {"evidence_selection", "test_interpretation"}:
            allowed = {choice.id for choice in public.choices}
            if request.selected_choice_id not in allowed or any(value is not None for value in (request.ordered_step_ids, request.source_code, request.answer_text)):
                raise LearningPathActivityUnavailableError()
            return
        if public.activity_type == "ordering":
            expected = {choice.id for choice in public.choices}
            submitted = request.ordered_step_ids
            if submitted is None or len(submitted) != len(expected) or set(submitted) != expected or any(value is not None for value in (request.selected_choice_id, request.source_code, request.answer_text)):
                raise LearningPathActivityUnavailableError()
            return
        if public.activity_type == "ast_fixture":
            if request.source_code is None or any(value is not None for value in (request.selected_choice_id, request.ordered_step_ids, request.answer_text)):
                raise LearningPathActivityUnavailableError()
            return
        if public.activity_type in {"explain_back", "trade_off"}:
            if request.answer_text is None or any(value is not None for value in (request.selected_choice_id, request.ordered_step_ids, request.source_code)):
                raise LearningPathActivityUnavailableError()
            return
        raise LearningPathActivityUnavailableError()

    def _lesson_response(
        self,
        session: Session,
        adaptation: ProjectModuleAdaptation,
        definition: ContinuousStoredLessonDefinition,
    ) -> ContinuousLessonResponse:
        attempt = session.scalar(
            select(ProjectModuleAttempt)
            .where(
                ProjectModuleAttempt.module_id == adaptation.module_id,
                ProjectModuleAttempt.activity_id == definition.public_activity.id,
                ProjectModuleAttempt.state == LearningPathGenerationState.COMPLETED,
            )
            .order_by(ProjectModuleAttempt.completed_at.desc().nullslast(), ProjectModuleAttempt.created_at.desc())
            .limit(1)
        )
        review = self._review(definition, attempt) if attempt is not None else None
        return ContinuousLessonResponse(
            id=adaptation.id,
            sequence=definition.sequence,
            title=definition.title,
            focus=definition.focus,
            lesson_format=definition.lesson_format,
            activity_type=definition.activity_type,
            difficulty=definition.difficulty,
            objective=definition.objective,
            explanation=definition.explanation,
            project_connection=definition.project_connection,
            confirmed_evidence_ids=definition.confirmed_evidence_ids,
            illustrative_example=definition.illustrative_example,
            unknown_or_uninspected=definition.unknown_or_uninspected,
            suggested_next_focus=definition.suggested_next_focus,
            activity=definition.public_activity,
            completed=adaptation.state == ModuleAdaptationState.COMPLETED,
            created_at=adaptation.created_at,
            completed_at=adaptation.completed_at,
            review=review,
        )

    @staticmethod
    def _review(definition: ContinuousStoredLessonDefinition, attempt: ProjectModuleAttempt) -> ContinuousLessonReview:
        submitted = attempt.submitted_payload or {}
        public = definition.public_activity
        private = definition.private_activity
        labels = {choice.id: choice.label for choice in public.choices}
        if public.activity_type in {"evidence_selection", "test_interpretation"}:
            submitted_id = submitted.get("selected_choice_id")
            your_answer = labels.get(str(submitted_id), str(submitted_id or "No selection submitted"))
            expected_answer = labels.get(private.expected_choice_id or "", private.reference_answer)
        elif public.activity_type == "ordering":
            submitted_order = submitted.get("ordered_step_ids") or []
            your_answer = " → ".join(labels.get(str(item), str(item)) for item in submitted_order)
            expected_answer = " → ".join(labels.get(item, item) for item in private.expected_order)
        elif public.activity_type == "ast_fixture":
            your_answer = str(submitted.get("source_code") or "No source submitted")
            expected_answer = private.reference_answer
        else:
            your_answer = str(submitted.get("answer_text") or "No answer submitted")
            expected_answer = private.reference_answer
        result = attempt.result_payload or {}
        checks = [
            ContinuousLessonCheck(
                id=str(item.get("id", "check")),
                passed=item.get("passed") is True,
                message=str(item.get("message", "Check result unavailable.")),
            )
            for item in result.get("checks", [])
            if isinstance(item, dict)
        ][:4]
        return ContinuousLessonReview(
            attempt_id=attempt.id,
            passed=attempt.passed is True,
            earned_points=attempt.earned_points,
            submitted_answer=your_answer,
            expected_answer=expected_answer,
            why_correct=private.why_correct,
            project_connection=definition.project_connection,
            evidence_ids=definition.confirmed_evidence_ids,
            feedback=str(result.get("feedback", "The saved lesson attempt was evaluated.")),
            checks=checks,
            can_retry=attempt.passed is not True,
        )

    def _build_definition(
        self,
        *,
        path: ProjectLearningPathVersion,
        snapshot: ProjectInspectionSnapshot,
        catalog: EvidenceCatalog,
        sequence: int,
        plan: dict[str, Any],
        draft: ContinuousLessonDraft,
        history: dict[str, Any],
        idempotency_key: str,
        request_hash: str,
    ) -> ContinuousStoredLessonDefinition:
        allowed = {item.id: item for item in catalog.items if item.id in plan["allowed_evidence_ids"]}
        evidence_ids = draft.confirmed_evidence_ids
        if len(evidence_ids) != len(set(evidence_ids)) or any(item not in allowed for item in evidence_ids):
            raise ContinuousLearningProviderError()
        title = _safe_text(draft.title, 100)
        focus = _safe_text(draft.focus, 220)
        seed = fingerprint({"path": path.id.hex, "sequence": sequence, "snapshot": snapshot.evidence_fingerprint})
        public_id = f"continuous-{sequence}-{plan['activity_type']}.v1"
        activity = draft.activity
        choices: list[ContinuousChoice] = []
        starter_code: str | None = None
        constraints: list[str] = ["This lesson uses only the displayed bounded repository evidence."]
        expected_choice_id: str | None = None
        expected_order: list[str] = []
        reference_answer: str
        why_correct: str
        rubric: list[str] = []

        if isinstance(activity, DraftEvidenceActivity):
            if len(activity.choice_evidence_ids) != len(set(activity.choice_evidence_ids)) or any(item not in allowed for item in activity.choice_evidence_ids) or activity.correct_evidence_id not in activity.choice_evidence_ids:
                raise ContinuousLearningProviderError()
            choices = [ContinuousChoice(id=item, label=allowed[item].label) for item in _stable_order(activity.choice_evidence_ids, seed)]
            expected_choice_id = activity.correct_evidence_id
            reference_answer = allowed[activity.correct_evidence_id].label
            why_correct = _safe_text(activity.why_correct, 700)
        elif isinstance(activity, DraftChoiceActivity):
            normalized_choices = [_safe_text(item, 240) for item in activity.choices]
            if len(normalized_choices) != len(set(normalized_choices)) or activity.correct_choice_index >= len(normalized_choices):
                raise ContinuousLearningProviderError()
            indexed = [(f"option-{chr(97 + index)}", label) for index, label in enumerate(normalized_choices)]
            expected_choice_id = indexed[activity.correct_choice_index][0]
            choices = [ContinuousChoice(id=item_id, label=label) for item_id, label in _stable_order(indexed, seed)]
            reference_answer = _safe_text(activity.reference_answer, 500)
            why_correct = _safe_text(activity.why_correct, 700)
        elif isinstance(activity, DraftOrderingActivity):
            steps = [_safe_text(item, 240) for item in activity.steps_in_expected_order]
            if len(steps) != len(set(steps)):
                raise ContinuousLearningProviderError()
            indexed = [(f"step-{chr(97 + index)}", label) for index, label in enumerate(steps)]
            expected_order = [item_id for item_id, _ in indexed]
            choices = [ContinuousChoice(id=item_id, label=label) for item_id, label in _stable_order(indexed, seed)]
            reference_answer = " → ".join(steps)
            why_correct = _safe_text(activity.why_correct, 700)
        elif isinstance(activity, DraftAstActivity):
            python_id = "language:python" if "language:python" in allowed else "technology:python" if "technology:python" in allowed else None
            if python_id is None or "technology:fastapi" not in allowed:
                raise ContinuousLearningProviderError()
            evidence_ids = [python_id, "technology:fastapi"]
            starter_code = HEALTH_CHECK_STARTER_CODE
            constraints.extend(["Teaching fixture — not repository source.", "The source is parsed with AST only and is never executed."])
            reference_answer = EXAMPLE_HEALTHZ_SOLUTION
            why_correct = "The accepted fixture has exactly one healthz function returning the required literal dictionary; AST parsing verifies structure without executing it."
        elif isinstance(activity, DraftTextActivity):
            reference_answer = _safe_text(activity.reference_answer, 800)
            why_correct = _safe_text(activity.why_correct, 700)
            rubric = [_safe_text(item, 240) for item in activity.evaluation_rubric]
            constraints.append("Write at least 40 meaningful characters; repository and learner text remain untrusted model input.")
        else:
            raise ContinuousLearningProviderError()

        prompt = _safe_text(activity.prompt, 500)
        public_context = {
            "contract": CONTINUOUS_LESSON_CONTRACT_VERSION,
            "path": path.id.hex,
            "snapshot": snapshot.evidence_fingerprint,
            "sequence": sequence,
            "activity_type": plan["activity_type"],
            "prompt": prompt,
            "evidence_ids": evidence_ids,
            "choices": [choice.model_dump(mode="json") for choice in choices],
            "starter_code": starter_code,
        }
        public = ContinuousPublicActivity(
            id=public_id,
            activity_type=plan["activity_type"],
            context_id=fingerprint(public_context),
            prompt=prompt,
            evidence_ids=evidence_ids,
            choices=choices,
            starter_code=starter_code,
            constraints=constraints,
        )
        private = ContinuousPrivateActivity(
            evaluator_key=EVALUATOR_KEYS[plan["activity_type"]],
            expected_choice_id=expected_choice_id,
            expected_order=expected_order,
            reference_answer=reference_answer,
            why_correct=why_correct,
            evaluation_rubric=rubric,
        )
        title_fingerprint = fingerprint({"title": title.casefold()})
        novelty_fingerprint = fingerprint({
            "focus": focus.casefold(),
            "format": plan["lesson_format"],
            "activity_type": plan["activity_type"],
            "difficulty": plan["difficulty"],
            "evidence_ids": evidence_ids,
            "title_fingerprint": title_fingerprint,
        })
        previous = history["continuous_lessons"][-1]["novelty_fingerprint"] if history["continuous_lessons"] else None
        return ContinuousStoredLessonDefinition(
            sequence=sequence,
            source_inspection_snapshot_id=snapshot.id,
            source_evidence_fingerprint=snapshot.evidence_fingerprint,
            lesson_format=plan["lesson_format"],
            activity_type=plan["activity_type"],
            difficulty=plan["difficulty"],
            title=title,
            focus=focus,
            objective=_safe_text(draft.objective, 320),
            explanation=_safe_text(draft.explanation, 900),
            project_connection=_safe_text(draft.project_connection, 500),
            confirmed_evidence_ids=evidence_ids,
            illustrative_example=_safe_text(draft.illustrative_example, 500),
            unknown_or_uninspected=[_safe_text(item, 300) for item in draft.unknown_or_uninspected],
            suggested_next_focus=_safe_text(draft.suggested_next_focus, 240),
            public_activity=public,
            private_activity=private,
            title_fingerprint=title_fingerprint,
            previous_novelty_fingerprint=previous,
            novelty_fingerprint=novelty_fingerprint,
            generation_idempotency_key=idempotency_key,
            generation_request_hash=request_hash,
        )

    @staticmethod
    def _generation_plan(sequence: int, catalog: EvidenceCatalog) -> dict[str, Any]:
        ids = [item.id for item in catalog.items]
        has_python_fastapi = ("language:python" in ids or "technology:python" in ids) and "technology:fastapi" in ids
        boundaries = [item for item in ("technology:react", "technology:nextjs", "technology:fastapi", "technology:docker") if item in ids]
        formats = [item for item in FORMAT_ROTATION if item[1] != "ast_fixture" or has_python_fastapi]
        formats = [item for item in formats if item[1] != "ordering" or len(boundaries) >= 2]
        lesson_format, activity_type = formats[(sequence - 1) % len(formats)]
        difficulty = ("foundation", "applied", "stretch")[(sequence - 1) % 3]
        if activity_type == "ast_fixture":
            python_id = "language:python" if "language:python" in ids else "technology:python"
            selected = [python_id, "technology:fastapi"]
        elif activity_type == "ordering":
            selected = boundaries[:4]
        else:
            start = (sequence - 1) % len(ids)
            selected = [ids[(start + offset) % len(ids)] for offset in range(min(4, len(ids)))]
        return {
            "lesson_format": lesson_format,
            "activity_type": activity_type,
            "difficulty": difficulty,
            "allowed_evidence_ids": selected,
        }

    @staticmethod
    def _deterministic_fallback(
        sequence: int,
        catalog: EvidenceCatalog,
        difficulty: str,
    ) -> tuple[dict[str, Any], ContinuousLessonDraft]:
        evidence = catalog.items[(sequence - 1) % len(catalog.items)]
        plan = {
            "lesson_format": "interpret_deterministic_test_output",
            "activity_type": "test_interpretation",
            "difficulty": difficulty,
            "allowed_evidence_ids": [evidence.id],
        }
        draft = ContinuousLessonDraft(
            title=f"Interpret confirmed evidence: {evidence.label}",
            focus=f"Distinguish what {evidence.label} confirms from behavior the bounded inspection did not inspect.",
            objective="Practice separating one confirmed repository fact from unsupported source-level or runtime assumptions.",
            explanation=f"The active inspection records {evidence.label} as confirmed evidence. This supports only the bounded catalog detail: {evidence.detail}",
            project_connection="This lesson uses one item from the active saved inspection and does not add repository facts from provider output.",
            confirmed_evidence_ids=[evidence.id],
            illustrative_example="Illustrative teaching example: a confirmed technology can guide a question without proving that every route, file, or runtime path was inspected.",
            unknown_or_uninspected=["Exact source-level behavior and runtime execution remain unknown unless the bounded inspection explicitly confirms them."],
            suggested_next_focus="Continue with a different confirmed evidence item or practice explaining the same limitation at greater depth.",
            activity=DraftChoiceActivity(
                activity_type="test_interpretation",
                prompt="Which conclusion is supported by this saved deterministic evidence item?",
                choices=[
                    "The displayed catalog detail is confirmed within the bounded inspection.",
                    "The inspection proves every source file and runtime behavior in the repository.",
                ],
                correct_choice_index=0,
                reference_answer="The displayed catalog detail is confirmed within the bounded inspection.",
                why_correct="The saved evidence supports its displayed bounded detail, while broad source and runtime claims remain uninspected.",
            ),
        )
        return plan, draft

    def _generation_context(
        self,
        path: ProjectLearningPathVersion,
        snapshot: ProjectInspectionSnapshot,
        catalog: EvidenceCatalog,
        plan: dict[str, Any],
        history: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = set(plan["allowed_evidence_ids"])
        return {
            "learner_level": path.learner_level,
            "project_goal": path.learning_goal,
            "source_evidence_fingerprint": snapshot.evidence_fingerprint,
            "required_lesson_format": plan["lesson_format"],
            "required_activity_type": plan["activity_type"],
            "required_difficulty": plan["difficulty"],
            "confirmed_evidence_catalog": [item.model_dump(mode="json") for item in catalog.items if item.id in allowed],
            "inspection_limitations": catalog.catalog_limitations,
            "deterministic_module_history": history["deterministic_modules"],
            "recent_continuous_lesson_summaries": history["continuous_lessons"],
            "recent_learner_results": history["learner_results"],
            "generation_rule": "Use only supplied confirmed evidence; illustrative flow and unknown behavior must be labeled explicitly.",
        }

    def _history_context(
        self,
        session: Session,
        path: ProjectLearningPathVersion,
        stored: list[tuple[ProjectModuleAdaptation, ContinuousStoredLessonDefinition]],
    ) -> dict[str, Any]:
        modules = list(session.scalars(select(ProjectLearningModule).where(ProjectLearningModule.path_version_id == path.id).order_by(ProjectLearningModule.position)))
        deterministic = []
        for module in modules:
            payload = module.definition_payload or {}
            deterministic.append({
                "module_key": module.module_key,
                "title": payload.get("title"),
                "evidence_ids": payload.get("evidence_ids", []),
            })
        continuous = [
            {
                "sequence": definition.sequence,
                "focus": definition.focus,
                "activity_type": definition.activity_type,
                "evidence_ids": definition.confirmed_evidence_ids,
                "difficulty": definition.difficulty,
                "title_fingerprint": definition.title_fingerprint,
                "novelty_fingerprint": definition.novelty_fingerprint,
            }
            for _, definition in stored[-8:]
        ]
        attempts = list(session.scalars(
            select(ProjectModuleAttempt)
            .where(ProjectModuleAttempt.path_version_id == path.id, ProjectModuleAttempt.state == LearningPathGenerationState.COMPLETED)
            .order_by(ProjectModuleAttempt.completed_at.desc().nullslast())
            .limit(20)
        ))
        results = [{"activity_id": item.activity_id, "passed": item.passed, "earned_points": item.earned_points} for item in attempts]
        return {"deterministic_modules": deterministic, "continuous_lessons": continuous, "learner_results": results}

    @staticmethod
    def _is_duplicate(draft: ContinuousLessonDraft, history: list[dict[str, Any]]) -> bool:
        current_title = fingerprint({"title": _safe_text(draft.title, 100).casefold()})
        current_tokens = _tokens(f"{draft.title} {draft.focus}")
        for item in history[-8:]:
            if item.get("title_fingerprint") == current_title:
                return True
            prior_tokens = _tokens(str(item.get("focus", "")))
            union = current_tokens | prior_tokens
            if union and len(current_tokens & prior_tokens) / len(union) >= 0.8:
                return True
        return False

    @staticmethod
    def _completed_anchor(session: Session, path: ProjectLearningPathVersion) -> tuple[bool, ProjectLearningModule | None]:
        modules = list(session.scalars(select(ProjectLearningModule).where(ProjectLearningModule.path_version_id == path.id).order_by(ProjectLearningModule.position)))
        if not modules:
            return False, None
        states = list(session.scalars(select(ProjectModuleProgress.state).where(ProjectModuleProgress.path_version_id == path.id)))
        return len(states) == len(modules) and all(state == ModuleProgressState.DEMONSTRATED for state in states), modules[-1]

    @staticmethod
    def _all_continuous_adaptations(session: Session, path: ProjectLearningPathVersion) -> list[ProjectModuleAdaptation]:
        return list(session.scalars(
            select(ProjectModuleAdaptation)
            .where(
                ProjectModuleAdaptation.path_version_id == path.id,
                ProjectModuleAdaptation.project_id == path.project_id,
                ProjectModuleAdaptation.kind == ModuleAdaptationKind.OPTIONAL_STRETCH,
                ProjectModuleAdaptation.required.is_(False),
            )
            .order_by(ProjectModuleAdaptation.created_at, ProjectModuleAdaptation.id)
        ))

    def _stored_adaptations(self, session: Session, path: ProjectLearningPathVersion) -> list[tuple[ProjectModuleAdaptation, ContinuousStoredLessonDefinition]]:
        return self._stored_definitions(self._all_continuous_adaptations(session, path))

    @staticmethod
    def _stored_definitions(records: list[ProjectModuleAdaptation]) -> list[tuple[ProjectModuleAdaptation, ContinuousStoredLessonDefinition]]:
        values = []
        for record in records:
            if (record.definition_payload or {}).get("record_type") == CONTINUOUS_LESSON_CONTRACT_VERSION:
                values.append((record, ContinuousStoredLessonDefinition.model_validate(record.definition_payload)))
        return sorted(values, key=lambda item: item[1].sequence)

    @staticmethod
    def _find_generation(records: list[ProjectModuleAdaptation], idempotency_key: str) -> ProjectModuleAdaptation | None:
        return next((item for item in records if (item.definition_payload or {}).get("generation_idempotency_key") == idempotency_key), None)

    def _lesson(
        self,
        session: Session,
        path: ProjectLearningPathVersion,
        project_id: UUID,
        lesson_id: UUID,
        *,
        lock: bool = False,
    ) -> tuple[ProjectModuleAdaptation, ContinuousStoredLessonDefinition]:
        statement = select(ProjectModuleAdaptation).where(
            ProjectModuleAdaptation.id == lesson_id,
            ProjectModuleAdaptation.project_id == project_id,
            ProjectModuleAdaptation.path_version_id == path.id,
            ProjectModuleAdaptation.kind == ModuleAdaptationKind.OPTIONAL_STRETCH,
            ProjectModuleAdaptation.required.is_(False),
        )
        adaptation = session.scalar(statement.with_for_update() if lock else statement)
        if adaptation is None or (adaptation.definition_payload or {}).get("record_type") != CONTINUOUS_LESSON_CONTRACT_VERSION:
            raise ContinuousLearningUnavailableError()
        return adaptation, ContinuousStoredLessonDefinition.model_validate(adaptation.definition_payload)

    @staticmethod
    def _snapshot_payload(snapshot: ProjectInspectionSnapshot) -> StoredInspectionSnapshotPayload:
        return StoredInspectionSnapshotPayload.model_validate(snapshot.payload)


def _safe_text(value: str, maximum: int) -> str:
    try:
        normalized = unicodedata.normalize("NFKC", value)
        normalized = "".join(
            " " if unicodedata.category(character) in {"Cc", "Cf", "Cs"} else character
            for character in normalized
        )
        return re.sub(r"\s+", " ", normalized).strip()[:maximum]
    except (TypeError, UnicodeError, ValueError) as error:
        raise ContinuousLearningProviderError() from error


def _tokens(value: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9]+", _safe_text(value, 400).casefold()) if len(item) > 2}


def _stable_order(values: list[Any], seed: str) -> list[Any]:
    return sorted(values, key=lambda item: fingerprint({"seed": seed, "item": item}))
