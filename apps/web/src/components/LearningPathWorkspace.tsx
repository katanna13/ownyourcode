import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import {
  apiBaseUrl,
  authenticatedFetch,
  AuthenticationRequestError,
  responseMessages
} from "../auth/authenticatedFetch";
import { CheckResultList } from "./CheckResultList";
import { ContinuousLearningPanel } from "./ContinuousLearningPanel";
import { StatusBadge } from "./StatusBadge";

type LearnerLevel = "beginner" | "junior" | "intermediate";
type ModuleState = "locked" | "available" | "in_progress" | "remediation_required" | "demonstrated";

type Activity = {
  id: string;
  presentation_kind: "single_choice" | "step_order" | "code_fixture";
  context_id: string;
  prompt: string;
  evidence_ids: string[];
  choices: Array<{ id: string; label: string }>;
  starter_code: string | null;
  constraints: string[];
  completion_role: string;
};

type AttemptReview = {
  attempt_id: string;
  activity_id: string;
  passed: boolean;
  your_answer: string;
  expected_answer: string;
  why_expected_answer: string;
  project_teaching: string;
  evidence_ids: string[];
  option_feedback: Array<{
    id: string;
    label: string;
    explanation: string;
    selected: boolean;
    expected: boolean;
  }>;
  transition_explanations: string[];
  checks: Array<{ id: string; passed: boolean; message: string }>;
  can_retry: boolean;
  example_solution: string | null;
};

type Module = {
  id: string;
  position: number;
  module_key: string;
  category: string;
  title: string;
  objective: string;
  evidence_ids: string[];
  lesson_sections: string[];
  activities: Activity[];
  limitations: string[];
  state: ModuleState;
  required_remediation: boolean;
  remediation_activities: Activity[];
  attempt_reviews: AttemptReview[];
};

export type LearningPathResponse = {
  persisted: true;
  mode: "none" | "legacy" | "multi_module";
  path_id: string | null;
  path_version: number | null;
  source_evidence_fingerprint: string | null;
  stale: boolean;
  limitations: string[];
  evidence_catalog: Array<{ id: string; label: string; detail: string }>;
  modules: Module[];
  resume_module_id: string | null;
  summary: {
    modules_total: number;
    modules_demonstrated: number;
    practical_gates_passed: number;
    required_remediations_open: number;
    label: string;
    disclaimer: string;
  } | null;
};

type AttemptResponse = {
  result: Record<string, unknown>;
  review: AttemptReview;
  module: Module;
};

function idempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `path-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isIncomplete(module: Module): boolean {
  return ["available", "in_progress", "remediation_required"].includes(module.state);
}

export function continueLearningModule(path: LearningPathResponse): Module | null {
  return path.modules.find(isIncomplete)
    ?? path.modules.find((module) => module.id === path.resume_module_id && module.state !== "locked")
    ?? path.modules[0]
    ?? null;
}

function moduleStatusLabel(state: ModuleState): string {
  const labels: Record<ModuleState, string> = {
    locked: "Locked",
    available: "Available",
    in_progress: "In progress",
    remediation_required: "Remediation required",
    demonstrated: "Demonstrated"
  };
  return labels[state];
}

export function LearningPathWorkspace({
  projectId,
  path,
  hasInspection,
  onPathChange
}: {
  projectId: string;
  path: LearningPathResponse;
  hasInspection: boolean;
  onPathChange: (path: LearningPathResponse) => void;
}) {
  const authentication = useAuthentication();
  const initialModule = continueLearningModule(path);
  const [learnerLevel, setLearnerLevel] = useState<LearnerLevel>("beginner");
  const [learningGoal, setLearningGoal] = useState("");
  const [activeModuleId, setActiveModuleId] = useState<string | null>(initialModule?.id ?? null);
  const [choiceId, setChoiceId] = useState("");
  const [orderedIds, setOrderedIds] = useState<string[]>([]);
  const [sourceCode, setSourceCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestReview, setLatestReview] = useState<AttemptReview | null>(null);
  const [showSolution, setShowSolution] = useState(false);
  const activityFormRef = useRef<HTMLFormElement>(null);

  const request = async (suffix: string, init: RequestInit = {}) => {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) throw new Error("The API URL is not configured.");
    const response = await authenticatedFetch(`${baseUrl}/api/v1/projects/${projectId}/learning-path${suffix}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
      getToken: authentication.getToken,
      onUnauthorized: authentication.markSessionExpired
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) throw new Error(responseMessages(payload)[0] ?? "The learning path could not be completed safely.");
    return payload;
  };

  const activeModule = useMemo(
    () => path.modules.find((module) => module.id === activeModuleId && module.state !== "locked")
      ?? continueLearningModule(path),
    [activeModuleId, path]
  );
  const activeActivity = activeModule?.required_remediation
    ? activeModule.remediation_activities[0] ?? activeModule.activities[0]
    : activeModule?.activities[0];
  const savedReview = activeModule?.attempt_reviews[0] ?? null;
  const review = latestReview ?? savedReview;

  useEffect(() => {
    setActiveModuleId((current) => {
      const currentModule = path.modules.find((module) => module.id === current);
      return currentModule && currentModule.state !== "locked"
        ? current
        : continueLearningModule(path)?.id ?? null;
    });
  }, [path]);

  useEffect(() => {
    setChoiceId("");
    setOrderedIds([]);
    setSourceCode(activeActivity?.starter_code ?? "");
  }, [activeActivity?.context_id]);

  useEffect(() => {
    setLatestReview(null);
    setShowSolution(false);
    setError(null);
  }, [activeModuleId]);

  async function createPath(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = await request("", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ learner_level: learnerLevel, learning_goal: learningGoal || null })
      });
      if (isRecord(payload) && payload.mode === "multi_module") onPathChange(payload as unknown as LearningPathResponse);
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "The learning path could not be generated.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function openModule(module: Module | null) {
    if (!module || module.state === "locked") return;
    setActiveModuleId(module.id);
    setLatestReview(null);
    setShowSolution(false);
    setError(null);
    try {
      await request(`/modules/${module.id}/view`, { method: "PATCH" });
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "The viewed module could not be saved.");
    }
  }

  async function submitActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeModule || !activeActivity) return;
    if (activeActivity.presentation_kind === "single_choice" && !choiceId) {
      setError("Choose one response before submitting.");
      return;
    }
    if (activeActivity.presentation_kind === "step_order" && (orderedIds.length !== activeActivity.choices.length || new Set(orderedIds).size !== orderedIds.length)) {
      setError("Place every teaching-flow step once before submitting.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setShowSolution(false);
    try {
      const payload = await request(`/modules/${activeModule.id}/activities/${activeActivity.id}/attempts`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          context_id: activeActivity.context_id,
          selected_choice_id: activeActivity.presentation_kind === "single_choice" ? choiceId : null,
          ordered_step_ids: activeActivity.presentation_kind === "step_order" ? orderedIds : null,
          source_code: activeActivity.presentation_kind === "code_fixture" ? sourceCode : null
        })
      });
      if (isRecord(payload)) {
        const attempt = payload as unknown as AttemptResponse;
        setLatestReview(attempt.review);
        const refreshed = await request("");
        if (isRecord(refreshed) && refreshed.mode === "multi_module") onPathChange(refreshed as unknown as LearningPathResponse);
      }
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "The activity could not be evaluated.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (path.mode === "none" || path.stale) {
    if (!hasInspection) return null;
    return (
      <section className="workspace learning-path glass-surface" aria-labelledby="learning-path-setup-title">
        <p className="eyebrow">Saved learning path</p>
        <h2 id="learning-path-setup-title">{path.stale ? "Refresh the saved learning path" : "Create the current project learning path"}</h2>
        <p>{path.stale ? "The saved repository inspection changed. The earlier immutable path remains historical; create a new path from the current saved evidence." : "Use the already saved deterministic inspection to freeze a small, sequential learning path. This does not replace the public session-only demo."}</p>
        {error && <p className="message message--error" role="alert">{error}</p>}
        <form className="assessment-form" onSubmit={createPath}>
          <label className="field" htmlFor="path-learner-level">Learner level
            <select id="path-learner-level" value={learnerLevel} onChange={(event) => setLearnerLevel(event.target.value as LearnerLevel)}>
              <option value="beginner">Beginner</option><option value="junior">Junior</option><option value="intermediate">Intermediate</option>
            </select>
          </label>
          <label className="field" htmlFor="path-learning-goal">Learning goal (optional)
            <textarea id="path-learning-goal" maxLength={240} value={learningGoal} onChange={(event) => setLearningGoal(event.target.value)} />
          </label>
          <button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving learning path..." : path.stale ? "Create fresh saved learning path" : "Create saved learning path"}</button>
        </form>
      </section>
    );
  }

  if (path.mode !== "multi_module" || !activeModule || !activeActivity) return null;

  const evidence = new Map(path.evidence_catalog.map((item) => [item.id, item]));
  const continueTarget = continueLearningModule(path);
  const previousModule = [...path.modules].reverse().find((module) => module.position < activeModule.position && module.state !== "locked") ?? null;
  const nextUnlockedModule = path.modules.find((module) => module.position > activeModule.position && module.state !== "locked") ?? null;
  const allComplete = path.modules.length > 0 && path.modules.every((module) => module.state === "demonstrated");
  const hasFailedMainAttempt = activeModule.attempt_reviews.some((item) => item.activity_id === activeModule.activities[0]?.id && !item.passed);
  const submitLabel = activeModule.required_remediation
    ? "Complete required micro-lesson"
    : hasFailedMainAttempt
      ? "Retry saved activity"
      : "Submit saved activity";

  return (
    <section className="workspace learning-path" aria-labelledby="learning-path-title">
      <header className="workspace__header glass-surface">
        <div>
          <p className="eyebrow">Saved learning path</p>
          <h2 id="learning-path-title">Current repository path</h2>
          <p className="workspace__value">Module definitions and attempts are saved for this authenticated project. Draft answers are not autosaved.</p>
        </div>
        <div className="learning-path__header-actions">
          <StatusBadge tone="current">{`Path v${path.path_version ?? "current"}`}</StatusBadge>
          {!allComplete && continueTarget && <button className="button button--quiet" type="button" onClick={() => void openModule(continueTarget)}>Continue learning</button>}
        </div>
      </header>

      {allComplete && <p className="message">Learning path complete — review any module or create a fresh path after a new repository inspection.</p>}

      <nav className="learning-path__module-nav glass-surface" aria-label="Saved learning modules">
        <ol>
          {path.modules.map((module) => (
            <li className={`learning-path__module-item learning-path__module-item--${module.state}${module.id === activeModule.id ? " learning-path__module-item--current" : ""}`} key={module.id}>
              <button
                type="button"
                disabled={module.state === "locked"}
                aria-current={module.id === activeModule.id ? "step" : undefined}
                aria-label={`Module ${module.position}: ${module.title}. ${module.id === activeModule.id ? "Current. " : ""}${moduleStatusLabel(module.state)}`}
                onClick={() => void openModule(module)}
              >
                <span className="learning-path__module-number">Module {module.position}</span>
                <span className="learning-path__module-title">{module.title}</span>
                <span className="learning-path__module-state">{module.id === activeModule.id && <span className="learning-path__current-label">Current</span>}{moduleStatusLabel(module.state)}</span>
              </button>
            </li>
          ))}
        </ol>
      </nav>

      {error && <section className="message message--error" role="alert"><h3>Learning path needs attention</h3><p>{error}</p></section>}

      <article className="activity-card glass-surface learning-path__module" aria-labelledby={`module-title-${activeModule.id}`}>
        <header className="learning-path__module-heading">
          <p className="learning-path__module-number">Module {activeModule.position}</p>
          <h3 id={`module-title-${activeModule.id}`}>{activeModule.title}</h3>
          <span className={`learning-path__status learning-path__status--${activeModule.state}`}>{moduleStatusLabel(activeModule.state)}</span>
        </header>
        <p><strong>Objective:</strong> {activeModule.objective}</p>
        {activeModule.lesson_sections.map((section) => <p key={section}>{section}</p>)}
        <h4>Confirmed evidence used here</h4>
        <ul className="learning-path__evidence-list">{activeModule.evidence_ids.map((id) => <li key={id}><strong>{evidence.get(id)?.label ?? id}</strong>{evidence.get(id)?.detail ? ` — ${evidence.get(id)?.detail}` : ""}</li>)}</ul>

        {activeModule.required_remediation && <p className="workspace__stage-actions"><StatusBadge tone="limited">Required remediation</StatusBadge> Complete this short correction before retrying the main activity.</p>}

        {activeModule.state !== "demonstrated" && (
          <form className="assessment-form" id="learning-path-activity-form" ref={activityFormRef} onSubmit={submitActivity}>
            <fieldset><legend>{activeActivity.prompt}</legend>
              {activeActivity.presentation_kind === "single_choice" && activeActivity.choices.map((choice) => <label className="choice" key={choice.id}><input type="radio" name={`path-choice-${activeActivity.id}`} checked={choiceId === choice.id} onChange={() => setChoiceId(choice.id)} />{choice.label}</label>)}
              {activeActivity.presentation_kind === "step_order" && activeActivity.choices.map((choice, index) => <label className="field" key={choice.id} htmlFor={`path-order-${index}`}>Position {index + 1}<select id={`path-order-${index}`} value={orderedIds[index] ?? ""} onChange={(event) => setOrderedIds((current) => { const next = [...current]; next[index] = event.target.value; return next; })}><option value="">Choose a step</option>{activeActivity.choices.map((option) => <option key={option.id} value={option.id} disabled={orderedIds.includes(option.id) && orderedIds[index] !== option.id}>{option.label}</option>)}</select></label>)}
              {activeActivity.presentation_kind === "code_fixture" && <label className="field" htmlFor="path-source-code">Teaching fixture<textarea id="path-source-code" value={sourceCode} maxLength={1000} spellCheck={false} onChange={(event) => setSourceCode(event.target.value)} /></label>}
            </fieldset>
            <ul>{activeActivity.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
            <button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving attempt..." : submitLabel}</button>
          </form>
        )}

        {review && <AttemptTeachingReview review={review} evidence={evidence} showSolution={showSolution} onShowSolution={() => setShowSolution(true)} onRetry={() => activityFormRef.current?.querySelector<HTMLElement>("input, select, textarea")?.focus()} remediationRequired={activeModule.required_remediation} />}

        <div className="learning-path__module-actions" aria-label="Module navigation actions">
          {previousModule && <button className="button button--quiet" type="button" onClick={() => void openModule(previousModule)}>Previous module</button>}
          {!allComplete && activeModule.state === "demonstrated" && continueTarget && continueTarget.id !== activeModule.id && <button className="button" type="button" aria-label={`Next available module: Continue to Module ${continueTarget.position}`} onClick={() => void openModule(continueTarget)}>Continue to Module {continueTarget.position}</button>}
          {nextUnlockedModule && (allComplete || activeModule.state !== "demonstrated") && <button className="button button--quiet" type="button" onClick={() => void openModule(nextUnlockedModule)}>Next available module</button>}
        </div>
      </article>

      <section className="preview-score glass-surface activity-card">
        <p className="eyebrow">{path.summary?.label}</p>
        <p>{path.summary?.modules_demonstrated ?? 0} of {path.summary?.modules_total ?? 0} modules demonstrated; {path.summary?.practical_gates_passed ?? 0} practical gates passed.</p>
        <p className="session-disclaimer">{path.summary?.disclaimer}</p>
        {path.limitations.length > 0 && <details><summary>Inspection and path limitations</summary><ul>{path.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details>}
      </section>

      {allComplete && continueTarget && (
        <ContinuousLearningPanel
          projectId={projectId}
          onReviewLearningPath={() => { void openModule(continueTarget); }}
        />
      )}
    </section>
  );
}

function AttemptTeachingReview({
  review,
  evidence,
  showSolution,
  onShowSolution,
  onRetry,
  remediationRequired
}: {
  review: AttemptReview;
  evidence: Map<string, { id: string; label: string; detail: string }>;
  showSolution: boolean;
  onShowSolution: () => void;
  onRetry: () => void;
  remediationRequired: boolean;
}) {
  return (
    <section className={`feedback-panel learning-path-review learning-path-review--${review.passed ? "passed" : "needs-work"}`} aria-labelledby={`attempt-review-${review.attempt_id}`}>
      <header><p className="eyebrow">Post-attempt review</p><h4 id={`attempt-review-${review.attempt_id}`}>{review.passed ? "What you demonstrated" : "What to revise next"}</h4></header>
      <dl className="learning-path-review__answers">
        <div><dt>Your answer</dt><dd><pre>{review.your_answer}</pre></dd></div>
        <div><dt>Correct or expected answer</dt><dd><pre>{review.expected_answer}</pre></dd></div>
      </dl>
      <section><h5>Why it is correct</h5><p>{review.why_expected_answer}</p></section>
      <section><h5>What this teaches about the project</h5><p>{review.project_teaching}</p></section>
      {review.option_feedback.length > 0 && <section><h5>Evidence option review</h5><ul className="learning-path-review__options">{review.option_feedback.map((item) => <li className={`${item.selected ? "is-selected" : ""} ${item.expected ? "is-expected" : ""}`.trim()} key={item.id}><strong>{item.label}</strong><span>{item.selected ? "Your selection" : "Not selected"}{item.expected ? " · Expected evidence" : ""}</span><p>{item.explanation}</p></li>)}</ul></section>}
      {review.transition_explanations.length > 0 && <section><h5>Boundary transitions</h5><ol>{review.transition_explanations.map((item) => <li key={item}>{item}</li>)}</ol></section>}
      {review.checks.length > 0 && <section><h5>Deterministic checks</h5><CheckResultList checks={review.checks} /></section>}
      <section><h5>Confirmed repository evidence used</h5><ul>{review.evidence_ids.map((id) => <li key={id}><strong>{evidence.get(id)?.label ?? id}</strong>{evidence.get(id)?.detail ? ` — ${evidence.get(id)?.detail}` : ""}</li>)}</ul></section>
      {review.example_solution && <section className="learning-path-review__solution"><button className="button button--quiet" type="button" onClick={onShowSolution} aria-expanded={showSolution}>{showSolution ? "Solution shown" : "Show solution"}</button>{showSolution && <div><p><strong>Example solution — teaching fixture, not repository source.</strong></p><pre>{review.example_solution}</pre><p>Python AST parsing validates the literal structure without executing the submitted module.</p></div>}</section>}
      {review.can_retry && <button className="button button--quiet" type="button" onClick={onRetry}>{remediationRequired ? "Continue with required micro-lesson" : "Retry activity"}</button>}
    </section>
  );
}
