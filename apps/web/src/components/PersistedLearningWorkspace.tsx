import { FormEvent, useEffect, useMemo, useState } from "react";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import { apiBaseUrl, authenticatedFetch, AuthenticationRequestError, responseMessages } from "../auth/authenticatedFetch";
import { CheckResultList } from "./CheckResultList";
import { CodeFixtureEditor } from "./CodeFixtureEditor";
import { ProgressStep, ProgressStepper } from "./ProgressStepper";
import { StatusBadge } from "./StatusBadge";
import { LearningStage, LEARNING_STAGE_ORDER } from "../types/workspace";

type Evidence = { id: string; label: string; detail: string };
type Progress = {
  last_viewed_stage: LearningStage;
  unlocked_stages: LearningStage[];
  assessment_attempt_id: string | null;
  verified_lab_attempt_id: string | null;
  security_challenge_attempt_id: string | null;
  oral_defense_attempt_id: string | null;
  assessment_result?: Record<string, unknown> | null;
  verified_lab_result?: Record<string, unknown> | null;
  security_challenge_result?: Record<string, unknown> | null;
  oral_defense_result?: Record<string, unknown> | null;
  summary: {
    assessment_points: number | null;
    verified_lab_passed: boolean;
    security_challenge_passed: boolean;
    oral_defense_points: number | null;
    raw_total: number;
    rounded_total: number;
    label: "Current project learning summary";
    disclaimer: string;
  };
};
type Workspace = {
  active_snapshot: {
    version: number;
    evidence_fingerprint: string;
    inspection: {
      repository: { name: string; full_name: string; description: string | null; html_url: string; default_branch: string };
      technologies: Array<{ key: string; label: string; evidence: string[] }>;
      important_files: Array<{ path: string; kind: string }>;
      limitations: string[];
    };
  } | null;
  active_content: {
    version: number;
    learner_level: "beginner" | "junior" | "intermediate";
    learning_goal: string | null;
    lesson: {
      title: string;
      learning_objective: string;
      repository_summary: string;
      concepts: Array<{ title: string; explanation: string; why_it_matters: string; reflection_question: string }>;
      architecture_walkthrough: Array<{ step: string }>;
      limitations_and_open_questions: string[];
    };
    evidence_catalog: Evidence[];
    inspection_limitations: string[];
  } | null;
  progress: Progress;
};
type ActivityDefinition = Record<string, unknown>;
type AttemptResponse = { result: Record<string, unknown>; progress: Progress };

const stageLabels: Record<LearningStage, string> = {
  inspect: "Inspect",
  learn: "Learn",
  assess: "Assess",
  lab: "Verified lab",
  secure: "Security challenge",
  defend: "Oral defense",
  score: "Summary"
};

function idempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `workspace-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readChoices(value: unknown): Array<{ id: string; label: string }> {
  return Array.isArray(value)
    ? value.filter(isRecord).map((item) => ({ id: readString(item.id), label: readString(item.label) })).filter((item) => item.id && item.label)
    : [];
}

export function PersistedLearningWorkspace({
  projectId,
  workspace,
  onWorkspaceChange,
  onReload
}: {
  projectId: string;
  workspace: Workspace;
  onWorkspaceChange: (progress: Progress) => void;
  onReload: () => Promise<void>;
}) {
  const authentication = useAuthentication();
  const [stage, setStage] = useState<LearningStage>(workspace.progress.last_viewed_stage);
  const [definition, setDefinition] = useState<ActivityDefinition | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [learnerLevel, setLearnerLevel] = useState<"beginner" | "junior" | "intermediate">("beginner");
  const [learningGoal, setLearningGoal] = useState("");
  const [assessmentAnswers, setAssessmentAnswers] = useState({ option: "", evidence: "", explain: "", explainEvidence: [] as string[] });
  const [sourceCode, setSourceCode] = useState("");
  const [oralAnswer, setOralAnswer] = useState("");
  const [attemptResult, setAttemptResult] = useState<Record<string, unknown> | null>(null);

  const request = async (path: string, init: RequestInit = {}) => {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      throw new Error("The API URL is not configured.");
    }
    const response = await authenticatedFetch(`${baseUrl}/api/v1/projects/${projectId}/workspace${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
      getToken: authentication.getToken,
      onUnauthorized: authentication.markSessionExpired
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(responseMessages(payload)[0] ?? "Saved workspace request could not be completed. Please try again.");
    }
    return payload;
  };

  const activeContent = workspace.active_content;
  const progress = workspace.progress;
  const steps = useMemo<ProgressStep[]>(() => LEARNING_STAGE_ORDER.map((id) => ({
    id,
    label: stageLabels[id],
    active: id === stage,
    availability: stageAvailability(id, workspace.active_snapshot !== null, activeContent !== null, progress),
    prerequisite: id === "learn" ? "Inspect the repository first." : "Complete the previous saved activity."
  })), [activeContent, progress, stage, workspace.active_snapshot]);

  useEffect(() => {
    setStage(workspace.progress.last_viewed_stage);
    setDefinition(null);
    setAttemptResult(null);
    setError(null);
    setAssessmentAnswers({ option: "", evidence: "", explain: "", explainEvidence: [] });
    setSourceCode("");
    setOralAnswer("");
  }, [workspace.active_content?.version, workspace.active_snapshot?.version, workspace.progress.last_viewed_stage]);

  useEffect(() => {
    const restoredResult: Partial<Record<LearningStage, Record<string, unknown> | null | undefined>> = {
      assess: progress.assessment_result,
      lab: progress.verified_lab_result,
      secure: progress.security_challenge_result,
      defend: progress.oral_defense_result
    };
    setAttemptResult(restoredResult[stage] ?? null);
  }, [
    progress.assessment_result,
    progress.oral_defense_result,
    progress.security_challenge_result,
    progress.verified_lab_result,
    stage
  ]);

  useEffect(() => {
    if (!activeContent || !["assess", "lab", "secure", "defend"].includes(stage)) {
      return;
    }
    const paths: Partial<Record<LearningStage, string>> = {
      assess: "/assessment",
      lab: "/labs/fastapi-health-check",
      secure: "/security-challenges/fastapi-cors",
      defend: "/oral-defenses/architecture-boundaries"
    };
    const path = paths[stage];
    if (!path) return;
    let cancelled = false;
    setIsPreparing(true);
    setError(null);
    void request(path)
      .then((payload) => {
        if (!cancelled && isRecord(payload) && isRecord(payload.definition)) {
          const nextDefinition = payload.definition;
          setDefinition(nextDefinition);
          setSourceCode(readString(nextDefinition.starter_code));
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled && !(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "Saved activity could not be prepared.");
      })
      .finally(() => { if (!cancelled) setIsPreparing(false); });
    return () => { cancelled = true; };
  }, [activeContent?.version, stage]);

  async function selectStage(nextStage: LearningStage) {
    if (!progress.unlocked_stages.includes(nextStage) || nextStage === stage) return;
    setError(null);
    try {
      const payload = await request("/progress", { method: "PATCH", body: JSON.stringify({ last_viewed_stage: nextStage }) });
      if (isRecord(payload)) {
        onWorkspaceChange(payload as unknown as Progress);
        setStage(nextStage);
        setDefinition(null);
        setAttemptResult(null);
      }
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "The saved stage could not be updated.");
    }
  }

  async function inspect() {
    setIsSubmitting(true); setError(null);
    try { await request("/inspection", { method: "POST", body: "{}" }); await onReload(); }
    catch (requestError) { if (!(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "Repository inspection could not be completed."); }
    finally { setIsSubmitting(false); }
  }

  async function generateContent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setIsSubmitting(true); setError(null);
    try {
      await request("/content", { method: "POST", headers: { "Idempotency-Key": idempotencyKey() }, body: JSON.stringify({ learner_level: learnerLevel, learning_goal: learningGoal || null }) });
      await onReload();
    } catch (requestError) { if (!(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "Learning content could not be generated."); }
    finally { setIsSubmitting(false); }
  }

  async function submitAttempt(path: string, body: Record<string, unknown>) {
    setIsSubmitting(true); setError(null);
    try {
      const payload = await request(path, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(body) });
      if (isRecord(payload) && isRecord(payload.result) && isRecord(payload.progress)) {
        setAttemptResult(payload.result);
        onWorkspaceChange(payload.progress as unknown as Progress);
      }
    } catch (requestError) { if (!(requestError instanceof AuthenticationRequestError)) setError(requestError instanceof Error ? requestError.message : "Saved attempt could not be evaluated."); }
    finally { setIsSubmitting(false); }
  }

  const questions = Array.isArray(definition?.questions) ? definition.questions.filter(isRecord) : [];
  const mcq = questions.find((item) => item.type === "multiple_choice");
  const evidenceQuestion = questions.find((item) => item.type === "evidence_selection");
  const explainQuestion = questions.find((item) => item.type === "explain_back");
  const checks = Array.isArray(attemptResult?.checks) ? attemptResult.checks.filter(isRecord).map((check) => ({ id: readString(check.id), passed: check.passed === true, message: readString(check.message) })) : [];

  return (
    <section className="workspace" aria-labelledby="saved-workspace-title">
      <header className="workspace__header glass-surface">
        <div><p className="eyebrow">Saved learning workspace</p><h2 id="saved-workspace-title">Repository orientation</h2><p className="workspace__value">Stages and completed attempts are saved. Draft answers and fixture edits are not autosaved.</p></div>
        {activeContent && <StatusBadge tone="current">{`Content v${activeContent.version}`}</StatusBadge>}
      </header>
      <ProgressStepper steps={steps} onStageSelect={selectStage} showLockedContext={false} />
      {error && <section className="message message--error" role="alert"><h3>Workspace needs attention</h3><p>{error}</p></section>}

      {stage === "inspect" && <section className="activity-card glass-surface"><h3>Inspect the saved repository</h3>{workspace.active_snapshot ? <><p><strong>{workspace.active_snapshot.inspection.repository.full_name}</strong> was saved as inspection version {workspace.active_snapshot.version}.</p><p>{workspace.active_snapshot.inspection.repository.description ?? "No repository description was supplied."}</p><ul className="technology-chip-list">{workspace.active_snapshot.inspection.technologies.map((technology) => <li key={technology.key}>{technology.label}</li>)}</ul><div className="workspace__stage-actions"><button className="button" type="button" onClick={() => void selectStage("learn")}>Continue to Learn</button><button className="button button--quiet" type="button" onClick={inspect} disabled={isSubmitting}>{isSubmitting ? "Reinspecting..." : "Reinspect repository"}</button></div></> : <><p>Inspection uses only the public repository URL stored on this project. No browser-supplied URL is used.</p><button className="button" type="button" onClick={inspect} disabled={isSubmitting}>{isSubmitting ? "Inspecting repository..." : "Inspect repository"}</button></>}</section>}

      {stage === "learn" && workspace.active_snapshot && !activeContent && <section className="activity-card glass-surface"><h3>Prepare the saved orientation</h3><p>Choose how this immutable workspace should explain the confirmed repository evidence.</p><form className="assessment-form" onSubmit={generateContent}><label className="field" htmlFor="saved-learner-level">Learner level<select id="saved-learner-level" value={learnerLevel} onChange={(event) => setLearnerLevel(event.target.value as typeof learnerLevel)}><option value="beginner">Beginner</option><option value="junior">Junior</option><option value="intermediate">Intermediate</option></select></label><label className="field" htmlFor="saved-learning-goal">Learning goal (optional)<textarea id="saved-learning-goal" maxLength={240} value={learningGoal} onChange={(event) => setLearningGoal(event.target.value)} /></label><button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Generating saved content..." : "Generate saved orientation"}</button></form></section>}

      {stage === "learn" && activeContent && <section className="lesson glass-surface activity-card"><p className="eyebrow">Saved lesson</p><h3>{activeContent.lesson.title}</h3><p><strong>Objective:</strong> {activeContent.lesson.learning_objective}</p><p>{activeContent.lesson.repository_summary}</p>{activeContent.lesson.concepts.map((concept) => <section className="lesson__concept" key={concept.title}><h4>{concept.title}</h4><p>{concept.explanation}</p><p><strong>Why it matters:</strong> {concept.why_it_matters}</p><p className="lesson__reflection">Reflect: {concept.reflection_question}</p></section>)}<h4>Architecture walkthrough</h4><ol className="walkthrough-list">{activeContent.lesson.architecture_walkthrough.map((step, index) => <li key={`${index}-${step.step}`}>{step.step}</li>)}</ol><button className="button" type="button" onClick={() => void selectStage("assess")}>Check my understanding</button></section>}

      {stage === "assess" && <section className="assessment activity-card glass-surface"><h3>Check your understanding of the repository orientation.</h3>{isPreparing && <p role="status">Loading saved assessment…</p>}{mcq && evidenceQuestion && explainQuestion && <form className="assessment-form" onSubmit={(event) => { event.preventDefault(); if (!assessmentAnswers.option || !assessmentAnswers.evidence || !assessmentAnswers.explain.trim() || assessmentAnswers.explainEvidence.length === 0) { setError("Answer every question and select evidence for your explanation."); return; } void submitAttempt("/assessment/attempts", { assessment_context_id: definition?.assessment_context_id, answers: { multiple_choice: { question_id: mcq.id, selected_option_id: assessmentAnswers.option }, evidence_selection: { question_id: evidenceQuestion.id, selected_evidence_id: assessmentAnswers.evidence }, explain_back: { question_id: explainQuestion.id, answer_text: assessmentAnswers.explain, evidence_ids: assessmentAnswers.explainEvidence } } }); }}><fieldset><legend>{readString(mcq.prompt)}</legend>{readChoices(mcq.options).map((option) => <label className="choice" key={option.id}><input type="radio" name="saved-mcq" checked={assessmentAnswers.option === option.id} onChange={() => setAssessmentAnswers((current) => ({ ...current, option: option.id }))} />{option.label}</label>)}</fieldset><fieldset><legend>{readString(evidenceQuestion.prompt)}</legend>{readChoices(evidenceQuestion.evidence_choices).map((choice) => <label className="choice" key={choice.id}><input type="radio" name="saved-evidence" checked={assessmentAnswers.evidence === choice.id} onChange={() => setAssessmentAnswers((current) => ({ ...current, evidence: choice.id }))} />{choice.label}</label>)}</fieldset><fieldset><legend>{readString(explainQuestion.prompt)}</legend><label className="field" htmlFor="saved-explain">Your explanation<textarea id="saved-explain" value={assessmentAnswers.explain} maxLength={600} onChange={(event) => setAssessmentAnswers((current) => ({ ...current, explain: event.target.value }))} /></label>{readChoices(explainQuestion.evidence_choices).map((choice) => <label className="choice" key={choice.id}><input type="checkbox" checked={assessmentAnswers.explainEvidence.includes(choice.id)} onChange={() => setAssessmentAnswers((current) => ({ ...current, explainEvidence: current.explainEvidence.includes(choice.id) ? current.explainEvidence.filter((id) => id !== choice.id) : current.explainEvidence.length < 2 ? [...current.explainEvidence, choice.id] : current.explainEvidence }))} />{choice.label}</label>)}</fieldset><button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving assessment..." : "Submit saved assessment"}</button></form>}{attemptResult && <AttemptFeedback result={attemptResult} />}</section>}

      {stage === "lab" && <FixtureStage title="Verified FastAPI health-check lab" definition={definition} isPreparing={isPreparing} isSubmitting={isSubmitting} sourceCode={sourceCode} onSourceCode={setSourceCode} onSubmit={() => void submitAttempt("/labs/fastapi-health-check/attempts", { lab_context_id: definition?.lab_context_id, source_code: sourceCode })} attemptResult={attemptResult} />}
      {stage === "secure" && <FixtureStage title="Security challenge: CORS configuration" definition={definition} isPreparing={isPreparing} isSubmitting={isSubmitting} sourceCode={sourceCode} onSourceCode={setSourceCode} onSubmit={() => void submitAttempt("/security-challenges/fastapi-cors/attempts", { security_challenge_context_id: definition?.security_challenge_context_id, source_code: sourceCode })} attemptResult={attemptResult} />}
      {stage === "defend" && <section className="oral-defense activity-card glass-surface"><h3>Oral defense</h3>{isPreparing && <p role="status">Loading saved question…</p>}{definition && definition.available !== false && <form className="oral-defense-form" onSubmit={(event) => { event.preventDefault(); if (oralAnswer.trim().length < 40) { setError("Write at least 40 meaningful characters before submitting."); return; } void submitAttempt("/oral-defenses/architecture-boundaries/attempts", { oral_defense_context_id: definition.oral_defense_context_id, question_id: "architecture-boundaries.question.v1", answer_text: oralAnswer }); }}><p>{isRecord(definition.question) ? readString(definition.question.prompt) : "Explain the confirmed repository boundaries."}</p><label className="field" htmlFor="saved-oral-answer">Your answer<textarea id="saved-oral-answer" value={oralAnswer} maxLength={800} onChange={(event) => setOralAnswer(event.target.value)} /></label><button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving oral defense..." : "Submit oral defense"}</button></form>}{attemptResult && <AttemptFeedback result={attemptResult} />}</section>}
      {stage === "score" && <section className="preview-score glass-surface activity-card"><p className="eyebrow">{progress.summary.label}</p><p className="preview-score__number">{progress.summary.rounded_total}<span>/100</span></p><dl><dt>Assessment</dt><dd>{progress.summary.assessment_points ?? "Not completed"} / 4</dd><dt>Verified lab</dt><dd>{progress.summary.verified_lab_passed ? "Demonstrated" : "Not demonstrated"}</dd><dt>Security challenge</dt><dd>{progress.summary.security_challenge_passed ? "Demonstrated" : "Not demonstrated"}</dd><dt>Oral defense</dt><dd>{progress.summary.oral_defense_points ?? "Not completed"} / 4</dd></dl><p className="session-disclaimer">{progress.summary.disclaimer}</p></section>}
    </section>
  );
}

function stageAvailability(
  stage: LearningStage,
  hasSnapshot: boolean,
  hasContent: boolean,
  progress: Progress
): "locked" | "available" | "complete" {
  if (!progress.unlocked_stages.includes(stage)) {
    return "locked";
  }
  if (stage === "inspect") {
    return hasSnapshot ? "complete" : "available";
  }
  if (stage === "learn") {
    return hasContent ? "complete" : "available";
  }
  if (stage === "assess") {
    return progress.assessment_attempt_id ? "complete" : "available";
  }
  if (stage === "lab") {
    return progress.verified_lab_attempt_id ? "complete" : "available";
  }
  if (stage === "secure") {
    return progress.security_challenge_attempt_id ? "complete" : "available";
  }
  if (stage === "defend") {
    return progress.oral_defense_attempt_id ? "complete" : "available";
  }
  return "available";
}

function FixtureStage({ title, definition, isPreparing, isSubmitting, sourceCode, onSourceCode, onSubmit, attemptResult }: { title: string; definition: ActivityDefinition | null; isPreparing: boolean; isSubmitting: boolean; sourceCode: string; onSourceCode: (value: string) => void; onSubmit: () => void; attemptResult: Record<string, unknown> | null }) {
  if (definition?.available === false) return <section className="activity-card glass-surface"><h3>{title}</h3><p>{readString(definition.reason)}</p></section>;
  return <section className="activity-card glass-surface"><h3>{title}</h3>{isPreparing && <p role="status">Loading saved teaching fixture…</p>}{definition && <form className="verified-lab-form" onSubmit={(event) => { event.preventDefault(); onSubmit(); }}><p>{readString(definition.instructions)}</p><CodeFixtureEditor id={title.includes("Security") ? "saved-security-source" : "saved-lab-source"} value={sourceCode} maximumLength={typeof definition.maximum_source_length === "number" ? definition.maximum_source_length : 1000} onChange={onSourceCode} onReset={() => onSourceCode(readString(definition.starter_code))} isSubmitting={isSubmitting} submitLabel="Submit saved attempt" submittingLabel="Saving attempt..." /></form>}{attemptResult && <AttemptFeedback result={attemptResult} />}</section>;
}

function AttemptFeedback({ result }: { result: Record<string, unknown> }) {
  const checks = Array.isArray(result.checks) ? result.checks.filter(isRecord).map((check) => ({ id: readString(check.id), passed: check.passed === true, message: readString(check.message) })) : [];
  const feedback = Array.isArray(result.feedback) ? result.feedback.filter(isRecord) : [];
  return <section className="feedback-panel" role="status"><h4>Saved attempt feedback</h4>{typeof result.passed === "boolean" && <p>{result.passed ? "The deterministic checks passed." : "The deterministic checks found an issue to revise."}</p>}{isRecord(result.score) && <p><strong>Score:</strong> {String(result.score.earned_points ?? "0")} / {String(result.score.total_points ?? "4")}</p>}{checks.length > 0 && <CheckResultList checks={checks} />}{feedback.length > 0 && <ul>{feedback.map((item, index) => <li key={`${readString(item.question_id)}-${index}`}>{readString(item.message)}</li>)}</ul>}{isRecord(result.explain_back_feedback) && <p>{readString(result.explain_back_feedback.feedback)}</p>}{typeof result.feedback === "string" && <p>{result.feedback}</p>}</section>;
}
