"""Owner-scoped orchestration for the initial persisted learning-path slice."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ownyourcode.modules.labs.verifier import verify_fastapi_health_check
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
from ownyourcode.modules.learning_paths.planner import plan_learning_path
from ownyourcode.modules.learning_paths.schemas import (
    ActivityAttemptReview,
    AttemptReviewCheck,
    AttemptReviewOption,
    Choice,
    LEARNING_PATH_CONTRACT_VERSION,
    LEARNING_PATH_PLANNER_VERSION,
    LearningPathCreateRequest,
    LearningPathModuleResponse,
    LearningPathResponse,
    LearningPathSummary,
    ModuleActivityAttemptRequest,
    ModuleAttemptResponse,
    PrivateActivityDefinition,
    PublicActivityDefinition,
    PublicModuleActivity,
    StoredActivityDefinition,
    StoredModuleDefinition,
    fingerprint,
)
from ownyourcode.modules.learning_workspaces.models import (
    ProjectInspectionSnapshot,
    ProjectLearningContentVersion,
    ProjectLearningProgress,
)
from ownyourcode.modules.learning_workspaces.repository import LearningWorkspaceRepository
from ownyourcode.modules.learning_workspaces.schemas import StoredInspectionSnapshotPayload
from ownyourcode.modules.projects.models import ProjectMode


EXAMPLE_HEALTHZ_SOLUTION = (
    'def healthz():\n'
    '    return {"status": "ok", "service": "ownyourcode-api"}\n'
)


class LearningPathNotFoundError(Exception):
    pass


class LearningPathInspectionRequiredError(Exception):
    pass


class LearningPathExistingRepositoryRequiredError(Exception):
    pass


class LearningPathContextStaleError(Exception):
    pass


class LearningPathConflictError(Exception):
    pass


class LearningPathActivityUnavailableError(Exception):
    pass


class LearningPathService:
    def __init__(self, repository: LearningWorkspaceRepository | None = None) -> None:
        self._repository = repository or LearningWorkspaceRepository()

    def get_path(self, session: Session, owner_id: UUID, project_id: UUID) -> LearningPathResponse:
        self._owned(session, owner_id, project_id)
        progress = self._progress(session, project_id)
        snapshot = self._snapshot(session, project_id, progress)
        path = self._active_path(session, project_id)
        if path is None:
            legacy = bool(progress and progress.active_content_version_id)
            return LearningPathResponse(mode="legacy" if legacy else "none")
        if snapshot is None or path.inspection_snapshot_id != snapshot.id:
            return LearningPathResponse(
                mode="multi_module", path_id=path.id, path_version=path.version,
                source_evidence_fingerprint=path.source_evidence_fingerprint, stale=True,
                limitations=["The saved inspection changed. This historical path is read-only until a new path is generated."],
            )
        return self._response(session, path, snapshot)

    def create_path(self, session: Session, owner_id: UUID, project_id: UUID, request: LearningPathCreateRequest, idempotency_key: str) -> LearningPathResponse:
        request_hash = fingerprint(request.model_dump(mode="json"))
        with session.begin():
            self._owned(session, owner_id, project_id, lock=True)
            progress = self._progress(session, project_id, lock=True)
            snapshot = self._snapshot(session, project_id, progress)
            if snapshot is None:
                raise LearningPathInspectionRequiredError()
            existing = session.scalar(select(ProjectLearningPathVersion).where(ProjectLearningPathVersion.project_id == project_id, ProjectLearningPathVersion.idempotency_key == idempotency_key))
            if existing is not None:
                if existing.request_hash != request_hash or existing.generation_state != LearningPathGenerationState.COMPLETED:
                    raise LearningPathConflictError()
                return self._response(session, existing, snapshot)
            next_version = int(session.scalar(select(func.coalesce(func.max(ProjectLearningPathVersion.version), 0)).where(ProjectLearningPathVersion.project_id == project_id)) or 0) + 1
            path = ProjectLearningPathVersion(
                id=uuid4(), project_id=project_id, inspection_snapshot_id=snapshot.id, version=next_version,
                idempotency_key=idempotency_key, request_hash=request_hash,
                generation_state=LearningPathGenerationState.PENDING,
                contract_version=LEARNING_PATH_CONTRACT_VERSION, planner_version=LEARNING_PATH_PLANNER_VERSION,
                source_evidence_fingerprint=snapshot.evidence_fingerprint,
                learner_level=request.learner_level.value, learning_goal=request.learning_goal,
            )
            session.add(path)
            payload = self._snapshot_payload(snapshot)

        try:
            plan = plan_learning_path(catalog=payload.evidence_catalog, learner_level=request.learner_level)
        except Exception:
            with session.begin():
                stored = session.get(ProjectLearningPathVersion, path.id)
                if stored is not None:
                    stored.generation_state = LearningPathGenerationState.FAILED
                    stored.failure_code = "planning_failed"
            raise

        with session.begin():
            self._owned(session, owner_id, project_id, lock=True)
            stored = session.get(ProjectLearningPathVersion, path.id)
            if stored is None:
                raise LearningPathNotFoundError()
            for prior in session.scalars(select(ProjectLearningPathVersion).where(ProjectLearningPathVersion.project_id == project_id, ProjectLearningPathVersion.is_active.is_(True))):
                prior.is_active = False
            stored.is_active = True
            stored.generation_state = LearningPathGenerationState.COMPLETED
            stored.path_limitations = plan.limitations
            stored.definition_fingerprint = fingerprint({"modules": [item.definition_fingerprint for item in plan.modules], "limitations": plan.limitations})
            stored.completed_at = datetime.now(timezone.utc)
            for position, item in enumerate(plan.modules, start=1):
                module = ProjectLearningModule(
                    id=uuid4(), project_id=project_id, path_version_id=stored.id, position=position,
                    module_key=item.definition.module_key, category=item.definition.category,
                    contract_version=item.definition.contract_version, definition_fingerprint=item.definition_fingerprint,
                    definition_payload=item.definition.model_dump(mode="json"),
                )
                session.add(module)
                session.flush()
                session.add(ProjectModuleProgress(
                    id=uuid4(), project_id=project_id, path_version_id=stored.id, module_id=module.id,
                    state=ModuleProgressState.AVAILABLE if position == 1 else ModuleProgressState.LOCKED,
                ))
            snapshot = self._snapshot(session, project_id, self._progress(session, project_id))
        if snapshot is None:
            raise LearningPathContextStaleError()
        return self._response(session, stored, snapshot)

    def get_module(self, session: Session, owner_id: UUID, project_id: UUID, module_id: UUID) -> LearningPathModuleResponse:
        path, snapshot = self._current_path(session, owner_id, project_id)
        module = self._module(session, path, project_id, module_id)
        return self._module_response(session, module)

    def view_module(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        module_id: UUID,
    ) -> LearningPathModuleResponse:
        with session.begin():
            path, _ = self._current_path(session, owner_id, project_id, lock=True)
            module = self._module(session, path, project_id, module_id, lock=True)
            progress = self._module_progress(session, module.id, lock=True)
            if progress.state == ModuleProgressState.LOCKED:
                raise LearningPathActivityUnavailableError()
            now = datetime.now(timezone.utc)
            progress.last_viewed_at = now
            progress.updated_at = now
        return self._module_response(session, module)

    def submit_attempt(self, session: Session, owner_id: UUID, project_id: UUID, module_id: UUID, activity_id: str, request: ModuleActivityAttemptRequest, idempotency_key: str) -> ModuleAttemptResponse:
        request_hash = fingerprint(request.model_dump(mode="json"))
        with session.begin():
            path, _ = self._current_path(session, owner_id, project_id, lock=True)
            module = self._module(session, path, project_id, module_id, lock=True)
            progress = self._module_progress(session, module.id, lock=True)
            if progress.state == ModuleProgressState.LOCKED:
                raise LearningPathActivityUnavailableError()
            activity, adaptation = self._activity(session, module, activity_id)
            if activity.public.context_id != request.context_id:
                raise LearningPathContextStaleError()
            existing = session.scalar(select(ProjectModuleAttempt).where(ProjectModuleAttempt.module_id == module.id, ProjectModuleAttempt.activity_id == activity_id, ProjectModuleAttempt.idempotency_key == idempotency_key))
            if existing is not None:
                if existing.request_hash != request_hash or existing.state != LearningPathGenerationState.COMPLETED:
                    raise LearningPathConflictError()
                return self._attempt_response(session, path, existing)
            attempt = ProjectModuleAttempt(
                id=uuid4(), project_id=project_id, path_version_id=path.id, module_id=module.id,
                activity_id=activity_id, idempotency_key=idempotency_key, request_hash=request_hash,
                state=LearningPathGenerationState.PENDING, context_fingerprint=request.context_id,
                submitted_payload=request.model_dump(mode="json"),
            )
            session.add(attempt)

        passed, earned_points, result = self._evaluate(activity, request)
        with session.begin():
            path, _ = self._current_path(session, owner_id, project_id, lock=True)
            module = self._module(session, path, project_id, module_id, lock=True)
            stored = session.get(ProjectModuleAttempt, attempt.id)
            if stored is None or stored.state != LearningPathGenerationState.PENDING:
                raise LearningPathConflictError()
            stored.state = LearningPathGenerationState.COMPLETED
            stored.passed, stored.earned_points, stored.result_payload = passed, earned_points, result
            now = datetime.now(timezone.utc)
            stored.completed_at = now
            viewed_progress = self._module_progress(session, module.id, lock=True)
            viewed_progress.last_viewed_at = now
            viewed_progress.updated_at = now
            if adaptation is not None and passed:
                adaptation = session.get(ProjectModuleAdaptation, adaptation.id)
                if adaptation is not None:
                    adaptation.state = ModuleAdaptationState.COMPLETED
                    adaptation.completed_at = datetime.now(timezone.utc)
            elif adaptation is None and not passed:
                self._create_remediation(session, path, module, stored, activity, result)
            # The session intentionally uses autoflush=False. Persist newly-created
            # remediation before deriving the server-owned progress projection.
            session.flush()
            self._recompute_path_progress(session, path)
        return self._attempt_response(session, path, stored)

    def _evaluate(self, activity: StoredActivityDefinition, request: ModuleActivityAttemptRequest) -> tuple[bool, int | None, dict[str, Any]]:
        key = activity.private.evaluator_key
        if key in {"orientation-evidence.v1", "evidence-reading-remediation.v1", "fixture-check-remediation.v1"}:
            passed = request.selected_choice_id == activity.private.expected_choice_id
            return passed, int(passed), {"passed": passed, "feedback": "Your selection matches the server-owned evidence-reading activity." if passed else "Review the bounded evidence and try again."}
        if key == "architecture-ordering.v1":
            passed = request.ordered_step_ids == activity.private.expected_order
            return passed, int(passed), {"passed": passed, "feedback": "The teaching flow is ordered from browser action through validation to response." if passed else "Use each teaching-flow step once, from browser action to validated response."}
        if key == "fastapi-health-fixture.v1":
            verification = verify_fastapi_health_check(request.source_code or "")
            return verification.passed, None, {"passed": verification.passed, "checks": [item.model_dump(mode="json") for item in verification.checks], "feedback": "The AST-only health-check verifier passed." if verification.passed else "The fixture was parsed but never executed. Review the failed deterministic checks."}
        raise LearningPathActivityUnavailableError()

    def _create_remediation(self, session: Session, path: ProjectLearningPathVersion, module: ProjectLearningModule, attempt: ProjectModuleAttempt, activity: StoredActivityDefinition, result: dict[str, Any]) -> None:
        if activity.private.evaluator_key == "orientation-evidence.v1":
            target = activity.private.expected_choice_id
            if target is None:
                return
            public = PublicActivityDefinition(
                id="evidence-reading-remediation.v1", presentation_kind="single_choice",
                context_id=fingerprint({"remediation": attempt.id.hex, "target": target}),
                prompt="Read the confirmed evidence again, then select the item that directly supports this orientation activity.",
                evidence_ids=[target], choices=[next(choice for choice in activity.public.choices if choice.id == target)],
                constraints=["This required remediation uses the same confirmed evidence."],
            )
            private = PrivateActivityDefinition(evaluator_key="evidence-reading-remediation.v1", expected_choice_id=target)
            reason = "Why this is next: the submitted evidence did not directly support the confirmed repository-orientation claim."
            rule_id = "wrong-evidence-selection"
        elif activity.private.evaluator_key == "fastapi-health-fixture.v1":
            failed = [item.get("id") for item in result.get("checks", []) if isinstance(item, dict) and item.get("passed") is False]
            public = PublicActivityDefinition(
                id="fixture-check-remediation.v1", presentation_kind="single_choice",
                context_id=fingerprint({"remediation": attempt.id.hex, "checks": failed}),
                prompt="Before retrying, acknowledge that the displayed failed AST check IDs describe a teaching fixture that was not executed.",
                evidence_ids=activity.public.evidence_ids,
                choices=[Choice(id="activity:review", label="I will use the deterministic checks to revise the teaching fixture.")],
                constraints=["Complete this micro-lesson, then retry the original fixture."],
            )
            private = PrivateActivityDefinition(evaluator_key="fixture-check-remediation.v1", expected_choice_id="activity:review")
            reason = "Why this is next: one or more deterministic fixture checks failed. Review their stable IDs before retrying."
            rule_id = "failed-fixture-check"
        else:
            return
        session.add(ProjectModuleAdaptation(
            id=uuid4(), project_id=module.project_id, path_version_id=path.id, module_id=module.id,
            trigger_attempt_id=attempt.id, kind=ModuleAdaptationKind.REMEDIATION,
            rule_id=rule_id, rule_version="remediation-rules.v1", learner_reason=reason, required=True,
            activity_id=public.id, context_fingerprint=public.context_id,
            definition_payload=StoredActivityDefinition(public=public, private=private, completion_role="required_remediation").model_dump(mode="json"),
            state=ModuleAdaptationState.AVAILABLE,
        ))

    def _recompute_path_progress(self, session: Session, path: ProjectLearningPathVersion) -> None:
        modules = list(session.scalars(select(ProjectLearningModule).where(ProjectLearningModule.path_version_id == path.id).order_by(ProjectLearningModule.position)))
        prior_demonstrated = True
        for module in modules:
            progress = self._module_progress(session, module.id)
            definition = self._definition(module)
            attempts = list(session.scalars(select(ProjectModuleAttempt).where(ProjectModuleAttempt.module_id == module.id, ProjectModuleAttempt.state == LearningPathGenerationState.COMPLETED)))
            adaptations = list(session.scalars(select(ProjectModuleAdaptation).where(ProjectModuleAdaptation.module_id == module.id, ProjectModuleAdaptation.required.is_(True))))
            open_adaptations = any(item.state != ModuleAdaptationState.COMPLETED for item in adaptations)
            passed_activity_ids = {item.activity_id for item in attempts if item.passed is True}
            required = [item.public.id for item in definition.activities]
            gates_passed = all(activity_id in passed_activity_ids for activity_id in required)
            if not prior_demonstrated:
                progress.state = ModuleProgressState.LOCKED
            elif open_adaptations:
                progress.state = ModuleProgressState.REMEDIATION_REQUIRED
            elif gates_passed:
                progress.state = ModuleProgressState.DEMONSTRATED
                progress.completed_at = progress.completed_at or datetime.now(timezone.utc)
            elif attempts:
                progress.state = ModuleProgressState.IN_PROGRESS
            else:
                progress.state = ModuleProgressState.AVAILABLE
            prior_demonstrated = progress.state == ModuleProgressState.DEMONSTRATED

    def _response(self, session: Session, path: ProjectLearningPathVersion, snapshot: ProjectInspectionSnapshot) -> LearningPathResponse:
        snapshot_payload = self._snapshot_payload(snapshot)
        modules = list(session.scalars(select(ProjectLearningModule).where(ProjectLearningModule.path_version_id == path.id).order_by(ProjectLearningModule.position)))
        responses = [self._module_response(session, item) for item in modules]
        summary = self._summary(session, path, responses)
        resume = next((item.id for item in responses if item.state in {"available", "in_progress", "remediation_required"}), None)
        if resume is None:
            resume = session.scalar(
                select(ProjectModuleProgress.module_id)
                .where(
                    ProjectModuleProgress.path_version_id == path.id,
                    ProjectModuleProgress.state != ModuleProgressState.LOCKED,
                    ProjectModuleProgress.last_viewed_at.is_not(None),
                )
                .order_by(
                    ProjectModuleProgress.last_viewed_at.desc(),
                    ProjectModuleProgress.module_id,
                )
                .limit(1)
            )
        if resume is None and responses:
            resume = responses[0].id
        return LearningPathResponse(mode="multi_module", path_id=path.id, path_version=path.version, source_evidence_fingerprint=path.source_evidence_fingerprint, limitations=path.path_limitations or [], evidence_catalog=snapshot_payload.evidence_catalog.items, modules=responses, resume_module_id=resume, summary=summary)

    def _module_response(self, session: Session, module: ProjectLearningModule) -> LearningPathModuleResponse:
        definition = self._definition(module)
        progress = self._module_progress(session, module.id)
        required_adaptations = list(session.scalars(select(ProjectModuleAdaptation).where(
            ProjectModuleAdaptation.module_id == module.id,
            ProjectModuleAdaptation.required.is_(True),
        )))
        adaptations = [
            item for item in required_adaptations
            if item.state == ModuleAdaptationState.AVAILABLE
        ]
        review_activity_ids = [
            *[item.public.id for item in definition.activities],
            *[item.activity_id for item in required_adaptations],
        ]
        attempts = list(
            session.scalars(
                select(ProjectModuleAttempt)
                .where(
                    ProjectModuleAttempt.module_id == module.id,
                    ProjectModuleAttempt.state == LearningPathGenerationState.COMPLETED,
                    ProjectModuleAttempt.activity_id.in_(review_activity_ids),
                )
                .order_by(
                    ProjectModuleAttempt.completed_at.desc().nullslast(),
                    ProjectModuleAttempt.created_at.desc(),
                    ProjectModuleAttempt.id,
                )
                .limit(10)
            )
        )
        return LearningPathModuleResponse(
            id=module.id, position=module.position, module_key=module.module_key, category=module.category,
            title=definition.title, objective=definition.objective, evidence_ids=definition.evidence_ids,
            lesson_sections=definition.lesson_sections, activities=[self._public_activity(item) for item in definition.activities], limitations=definition.limitations,
            state=progress.state.value, required_remediation=any(item.required for item in adaptations),
            remediation_activities=[self._public_activity(StoredActivityDefinition.model_validate(item.definition_payload)) for item in adaptations],
            attempt_reviews=[self._attempt_review(session, module, attempt) for attempt in attempts],
        )

    @staticmethod
    def _public_activity(activity: StoredActivityDefinition) -> PublicModuleActivity:
        return PublicModuleActivity(**activity.public.model_dump(mode="json"), completion_role=activity.completion_role)

    def _summary(self, session: Session, path: ProjectLearningPathVersion, modules: list[LearningPathModuleResponse]) -> LearningPathSummary:
        open_remediations = int(session.scalar(select(func.count()).select_from(ProjectModuleAdaptation).where(ProjectModuleAdaptation.path_version_id == path.id, ProjectModuleAdaptation.required.is_(True), ProjectModuleAdaptation.state != ModuleAdaptationState.COMPLETED)) or 0)
        demonstrated = sum(item.state == "demonstrated" for item in modules)
        gates = sum(item.state == "demonstrated" and item.category != "repository_orientation" for item in modules)
        return LearningPathSummary(modules_total=len(modules), modules_demonstrated=demonstrated, practical_gates_passed=gates, required_remediations_open=open_remediations)

    def _attempt_response(self, session: Session, path: ProjectLearningPathVersion, attempt: ProjectModuleAttempt) -> ModuleAttemptResponse:
        module = self._module(session, path, attempt.project_id, attempt.module_id)
        return ModuleAttemptResponse(attempt_id=attempt.id, passed=attempt.passed, earned_points=attempt.earned_points, result=attempt.result_payload or {}, review=self._attempt_review(session, module, attempt), module=self._module_response(session, module), summary=self._summary(session, path, [self._module_response(session, item) for item in session.scalars(select(ProjectLearningModule).where(ProjectLearningModule.path_version_id == path.id).order_by(ProjectLearningModule.position))]))

    def _attempt_review(
        self,
        session: Session,
        module: ProjectLearningModule,
        attempt: ProjectModuleAttempt,
    ) -> ActivityAttemptReview:
        activity = self._stored_activity_for_review(
            session,
            module,
            attempt.activity_id,
            attempt.context_fingerprint,
        )
        key = activity.private.evaluator_key
        submitted = attempt.submitted_payload or {}
        passed = attempt.passed is True

        if key in {
            "orientation-evidence.v1",
            "evidence-reading-remediation.v1",
            "fixture-check-remediation.v1",
        }:
            selected_id = submitted.get("selected_choice_id")
            selected_id = selected_id if isinstance(selected_id, str) else "No selection was submitted"
            expected_id = activity.private.expected_choice_id or "Unavailable"
            selected_choice = next((item for item in activity.public.choices if item.id == selected_id), None)
            expected_choice = next((item for item in activity.public.choices if item.id == expected_id), None)
            selected_label = selected_choice.label if selected_choice else selected_id
            expected_label = expected_choice.label if expected_choice else expected_id
            is_orientation = key == "orientation-evidence.v1"
            option_feedback = [
                AttemptReviewOption(
                    id=choice.id,
                    label=choice.label,
                    selected=choice.id == selected_id,
                    expected=choice.id == expected_id,
                    explanation=(
                        "This is the frozen evidence item that most directly supports the highlighted repository-orientation claim."
                        if choice.id == expected_id
                        else "This may be confirmed catalog evidence, but it is weaker or unrelated to the specific claim targeted by this activity."
                    ),
                )
                for choice in activity.public.choices
            ] if is_orientation else []
            return ActivityAttemptReview(
                attempt_id=attempt.id,
                activity_id=attempt.activity_id,
                passed=passed,
                your_answer=f"{selected_label} ({selected_id})",
                expected_answer=f"{expected_label} ({expected_id})",
                why_expected_answer=(
                    "The expected item is the frozen deterministic evidence selected for this exact repository-orientation claim."
                    if is_orientation
                    else "This acknowledgement connects the next retry to the saved deterministic evidence or failed checks."
                ),
                project_teaching=(
                    "Repository claims should begin with the most direct confirmed evidence, while broader metadata stays supporting context."
                    if is_orientation
                    else "The required micro-lesson keeps remediation tied to the saved attempt instead of changing the answer key."
                ),
                evidence_ids=activity.public.evidence_ids,
                option_feedback=option_feedback,
                can_retry=not passed,
            )

        if key == "architecture-ordering.v1":
            submitted_ids = submitted.get("ordered_step_ids")
            submitted_ids = submitted_ids if isinstance(submitted_ids, list) else []
            labels = {choice.id: choice.label for choice in activity.public.choices}
            expected_ids = activity.private.expected_order
            return ActivityAttemptReview(
                attempt_id=attempt.id,
                activity_id=attempt.activity_id,
                passed=passed,
                your_answer=" → ".join(labels.get(str(item), str(item)) for item in submitted_ids) or "No complete order was submitted",
                expected_answer=" → ".join(labels.get(item, item) for item in expected_ids),
                why_expected_answer="The learner action begins at the browser boundary, the API validates the request, and the response crosses back to the browser.",
                project_teaching="React or Next.js, FastAPI, and Docker evidence can confirm available architecture categories. This ordered request flow is illustrative and does not claim that a specific uninspected repository route exists.",
                evidence_ids=activity.public.evidence_ids,
                transition_explanations=[
                    "Browser to API: a learner action becomes an HTTP request crossing the frontend/backend boundary.",
                    "API to response: backend validation completes before a JSON result returns to the browser boundary.",
                ],
                can_retry=not passed,
            )

        if key == "fastapi-health-fixture.v1":
            source = submitted.get("source_code")
            source = source if isinstance(source, str) and source else "No source was submitted"
            raw_checks = (attempt.result_payload or {}).get("checks", [])
            checks = [
                AttemptReviewCheck(
                    id=str(item.get("id", "check")),
                    passed=item.get("passed") is True,
                    message=str(item.get("message", "Check result unavailable.")),
                )
                for item in raw_checks
                if isinstance(item, dict)
            ][:4]
            return ActivityAttemptReview(
                attempt_id=attempt.id,
                activity_id=attempt.activity_id,
                passed=passed,
                your_answer=source,
                expected_answer='One healthz function returning exactly {"status": "ok", "service": "ownyourcode-api"}.',
                why_expected_answer="The response must be one literal dictionary with the two required string keys and values, independent of dictionary key order.",
                project_teaching="This practices a FastAPI-style health response appropriate to confirmed Python and FastAPI evidence. The AST verifier checks literal structure without executing learner code, and the fixture is not repository source.",
                evidence_ids=activity.public.evidence_ids,
                checks=checks,
                can_retry=not passed,
                example_solution=EXAMPLE_HEALTHZ_SOLUTION,
            )

        raise LearningPathActivityUnavailableError()

    def _stored_activity_for_review(
        self,
        session: Session,
        module: ProjectLearningModule,
        activity_id: str,
        context_fingerprint: str,
    ) -> StoredActivityDefinition:
        definition = self._definition(module)
        activity = next((item for item in definition.activities if item.public.id == activity_id), None)
        if activity is not None:
            return activity
        adaptation = session.scalar(
            select(ProjectModuleAdaptation).where(
                ProjectModuleAdaptation.module_id == module.id,
                ProjectModuleAdaptation.activity_id == activity_id,
                ProjectModuleAdaptation.context_fingerprint == context_fingerprint,
                ProjectModuleAdaptation.required.is_(True),
            )
        )
        if adaptation is None:
            raise LearningPathActivityUnavailableError()
        return StoredActivityDefinition.model_validate(adaptation.definition_payload)

    def _current_path(self, session: Session, owner_id: UUID, project_id: UUID, *, lock: bool = False) -> tuple[ProjectLearningPathVersion, ProjectInspectionSnapshot]:
        self._owned(session, owner_id, project_id, lock=lock)
        progress = self._progress(session, project_id, lock=lock)
        snapshot = self._snapshot(session, project_id, progress)
        path = self._active_path(session, project_id, lock=lock)
        if path is None:
            raise LearningPathNotFoundError()
        if snapshot is None or path.inspection_snapshot_id != snapshot.id:
            raise LearningPathContextStaleError()
        return path, snapshot

    def _owned(self, session: Session, owner_id: UUID, project_id: UUID, *, lock: bool = False):
        owned = self._repository.get_owned_project(session, owner_id, project_id, lock=lock)
        if owned is None:
            raise LearningPathNotFoundError()
        if owned.project.mode != ProjectMode.EXISTING_REPOSITORY:
            raise LearningPathExistingRepositoryRequiredError()
        return owned

    @staticmethod
    def _progress(session: Session, project_id: UUID, *, lock: bool = False) -> ProjectLearningProgress | None:
        statement = select(ProjectLearningProgress).where(ProjectLearningProgress.project_id == project_id)
        return session.scalar(statement.with_for_update() if lock else statement)

    @staticmethod
    def _snapshot(session: Session, project_id: UUID, progress: ProjectLearningProgress | None) -> ProjectInspectionSnapshot | None:
        return session.get(ProjectInspectionSnapshot, progress.active_snapshot_id) if progress and progress.active_snapshot_id else None

    @staticmethod
    def _active_path(session: Session, project_id: UUID, *, lock: bool = False) -> ProjectLearningPathVersion | None:
        statement = select(ProjectLearningPathVersion).where(ProjectLearningPathVersion.project_id == project_id, ProjectLearningPathVersion.is_active.is_(True), ProjectLearningPathVersion.generation_state == LearningPathGenerationState.COMPLETED)
        return session.scalar(statement.with_for_update() if lock else statement)

    @staticmethod
    def _module(session: Session, path: ProjectLearningPathVersion, project_id: UUID, module_id: UUID, *, lock: bool = False) -> ProjectLearningModule:
        statement = select(ProjectLearningModule).where(ProjectLearningModule.id == module_id, ProjectLearningModule.path_version_id == path.id, ProjectLearningModule.project_id == project_id)
        module = session.scalar(statement.with_for_update() if lock else statement)
        if module is None:
            raise LearningPathNotFoundError()
        return module

    @staticmethod
    def _module_progress(session: Session, module_id: UUID, *, lock: bool = False) -> ProjectModuleProgress:
        statement = select(ProjectModuleProgress).where(ProjectModuleProgress.module_id == module_id)
        progress = session.scalar(statement.with_for_update() if lock else statement)
        if progress is None:
            raise LearningPathNotFoundError()
        return progress

    def _activity(self, session: Session, module: ProjectLearningModule, activity_id: str) -> tuple[StoredActivityDefinition, ProjectModuleAdaptation | None]:
        remediation = session.scalar(
            select(ProjectModuleAdaptation).where(
                ProjectModuleAdaptation.module_id == module.id,
                ProjectModuleAdaptation.required.is_(True),
                ProjectModuleAdaptation.state == ModuleAdaptationState.AVAILABLE,
            )
        )
        if remediation is not None and remediation.activity_id != activity_id:
            raise LearningPathActivityUnavailableError()
        definition = self._definition(module)
        activity = next((item for item in definition.activities if item.public.id == activity_id), None)
        if activity is not None:
            return activity, None
        adaptation = session.scalar(select(ProjectModuleAdaptation).where(
            ProjectModuleAdaptation.module_id == module.id,
            ProjectModuleAdaptation.activity_id == activity_id,
            ProjectModuleAdaptation.required.is_(True),
            ProjectModuleAdaptation.state == ModuleAdaptationState.AVAILABLE,
        ))
        if adaptation is None:
            raise LearningPathActivityUnavailableError()
        return StoredActivityDefinition.model_validate(adaptation.definition_payload), adaptation

    @staticmethod
    def _definition(module: ProjectLearningModule) -> StoredModuleDefinition:
        return StoredModuleDefinition.model_validate(module.definition_payload)

    @staticmethod
    def _snapshot_payload(snapshot: ProjectInspectionSnapshot) -> StoredInspectionSnapshotPayload:
        return StoredInspectionSnapshotPayload.model_validate(snapshot.payload)
