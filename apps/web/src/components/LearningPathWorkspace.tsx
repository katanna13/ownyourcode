import { FormEvent, useEffect, useMemo, useState } from "react";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import {
  apiBaseUrl,
  authenticatedFetch,
  AuthenticationRequestError,
  responseMessages
} from "../auth/authenticatedFetch";
import { CheckResultList } from "./CheckResultList";
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
  module: Module;
};

function idempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `path-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readChecks(value: unknown): Array<{ id: string; passed: boolean; message: string }> {
  return Array.isArray(value)
    ? value.filter(isRecord).map((item) => ({
      id: typeof item.id === "string" ? item.id : "check",
      passed: item.passed === true,
      message: typeof item.message === "string" ? item.message : ""
    }))
    : [];
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
  const [learnerLevel, setLearnerLevel] = useState<LearnerLevel>("beginner");
  const [learningGoal, setLearningGoal] = useState("");
  const [activeModuleId, setActiveModuleId] = useState<string | null>(path.resume_module_id);
  const [choiceId, setChoiceId] = useState("");
  const [orderedIds, setOrderedIds] = useState<string[]>([]);
  const [sourceCode, setSourceCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

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
    () => path.modules.find((module) => module.id === activeModuleId) ?? path.modules.find((module) => module.state !== "locked") ?? null,
    [activeModuleId, path.modules]
  );
  const activeActivity = activeModule?.required_remediation
    ? activeModule.remediation_activities[0] ?? activeModule.activities[0]
    : activeModule?.activities[0];

  useEffect(() => {
    setActiveModuleId(path.resume_module_id);
  }, [path.path_id, path.resume_module_id]);

  useEffect(() => {
    setChoiceId("");
    setOrderedIds([]);
    setSourceCode(activeActivity?.starter_code ?? "");
    setResult(null);
    setError(null);
  }, [activeActivity?.context_id]);

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
        setResult(attempt.result);
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

  if (path.mode !== "multi_module" || path.stale || !activeModule || !activeActivity) {
    return null;
  }

  const evidence = new Map(path.evidence_catalog.map((item) => [item.id, item]));
  const checks = readChecks(result?.checks);
  return (
    <section className="workspace learning-path" aria-labelledby="learning-path-title">
      <header className="workspace__header glass-surface">
        <div><p className="eyebrow">Saved learning path</p><h2 id="learning-path-title">Current repository path</h2><p className="workspace__value">Module definitions and attempts are saved for this authenticated project. Draft answers are not autosaved.</p></div>
        <StatusBadge tone="current">{`Path v${path.path_version ?? "current"}`}</StatusBadge>
      </header>
      <nav className="progress-stepper" aria-label="Saved learning modules"><ol>{path.modules.map((module) => <li key={module.id}><button type="button" className="progress-step" disabled={module.state === "locked"} aria-current={module.id === activeModule.id ? "step" : undefined} onClick={() => { setActiveModuleId(module.id); }}><span>{module.position}. {module.title}</span><span>{module.state.replaceAll("_", " ")}</span></button></li>)}</ol></nav>
      {error && <section className="message message--error" role="alert"><h3>Learning path needs attention</h3><p>{error}</p></section>}
      <article className="activity-card glass-surface">
        <p className="eyebrow">Module {activeModule.position}</p><h3>{activeModule.title}</h3><p><strong>Objective:</strong> {activeModule.objective}</p>
        {activeModule.lesson_sections.map((section) => <p key={section}>{section}</p>)}
        <h4>Confirmed evidence used here</h4><ul>{activeModule.evidence_ids.map((id) => <li key={id}><strong>{evidence.get(id)?.label ?? id}</strong>{evidence.get(id)?.detail ? ` — ${evidence.get(id)?.detail}` : ""}</li>)}</ul>
        {activeModule.required_remediation && <p className="workspace__stage-actions"><StatusBadge tone="limited">Required remediation</StatusBadge> Complete this short correction before retrying the main activity.</p>}
        <form className="assessment-form" onSubmit={submitActivity}>
          <fieldset><legend>{activeActivity.prompt}</legend>
            {activeActivity.presentation_kind === "single_choice" && activeActivity.choices.map((choice) => <label className="choice" key={choice.id}><input type="radio" name={`path-choice-${activeActivity.id}`} checked={choiceId === choice.id} onChange={() => setChoiceId(choice.id)} />{choice.label}</label>)}
            {activeActivity.presentation_kind === "step_order" && activeActivity.choices.map((choice, index) => <label className="field" key={choice.id} htmlFor={`path-order-${index}`}>Position {index + 1}<select id={`path-order-${index}`} value={orderedIds[index] ?? ""} onChange={(event) => setOrderedIds((current) => { const next = [...current]; next[index] = event.target.value; return next; })}><option value="">Choose a step</option>{activeActivity.choices.map((option) => <option key={option.id} value={option.id} disabled={orderedIds.includes(option.id) && orderedIds[index] !== option.id}>{option.label}</option>)}</select></label>)}
            {activeActivity.presentation_kind === "code_fixture" && <label className="field" htmlFor="path-source-code">Teaching fixture<textarea id="path-source-code" value={sourceCode} maxLength={1000} spellCheck={false} onChange={(event) => setSourceCode(event.target.value)} /></label>}
          </fieldset>
          <ul>{activeActivity.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
          <button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving attempt..." : "Submit saved activity"}</button>
        </form>
        {result && <section className="feedback-panel" role="status"><h4>Saved attempt feedback</h4>{typeof result.feedback === "string" && <p>{result.feedback}</p>}{checks.length > 0 && <CheckResultList checks={checks} />}</section>}
      </article>
      <section className="preview-score glass-surface activity-card"><p className="eyebrow">{path.summary?.label}</p><p>{path.summary?.modules_demonstrated ?? 0} of {path.summary?.modules_total ?? 0} modules demonstrated; {path.summary?.practical_gates_passed ?? 0} practical gates passed.</p><p className="session-disclaimer">{path.summary?.disclaimer}</p>{path.limitations.length > 0 && <details><summary>Inspection and path limitations</summary><ul>{path.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details>}</section>
    </section>
  );
}
