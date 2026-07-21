import { FormEvent, useEffect, useMemo, useState } from "react";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import {
  apiBaseUrl,
  authenticatedFetch,
  AuthenticationRequestError,
  responseMessages
} from "../auth/authenticatedFetch";
import { StatusBadge } from "./StatusBadge";

type EvidenceItem = { id: string; label: string; detail: string };
type Choice = { id: string; label: string };
type ActivityType = "evidence_selection" | "ordering" | "test_interpretation" | "ast_fixture" | "explain_back" | "trade_off";

type LessonReview = {
  passed: boolean;
  earned_points: number | null;
  submitted_answer: string;
  expected_answer: string;
  why_correct: string;
  project_connection: string;
  evidence_ids: string[];
  feedback: string;
  checks: Array<{ id: string; passed: boolean; message: string }>;
  can_retry: boolean;
};

type ContinuousLesson = {
  id: string;
  sequence: number;
  title: string;
  focus: string;
  lesson_format: string;
  activity_type: ActivityType;
  difficulty: string;
  objective: string;
  explanation: string;
  project_connection: string;
  confirmed_evidence_ids: string[];
  illustrative_example: string;
  unknown_or_uninspected: string[];
  suggested_next_focus: string;
  activity: {
    id: string;
    activity_type: ActivityType;
    context_id: string;
    prompt: string;
    evidence_ids: string[];
    choices: Choice[];
    starter_code: string | null;
    constraints: string[];
    maximum_answer_length: number;
  };
  completed: boolean;
  review: LessonReview | null;
};

type ContinuousLearningResponse = {
  persisted: true;
  available: boolean;
  message: string;
  evidence_catalog: EvidenceItem[];
  lessons: ContinuousLesson[];
  resume_lesson_id: string | null;
};

function idempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `continuous-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function isContinuousResponse(value: unknown): value is ContinuousLearningResponse {
  return typeof value === "object" && value !== null && Array.isArray((value as ContinuousLearningResponse).lessons);
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/^./, (character) => character.toUpperCase());
}

export function ContinuousLearningPanel({
  projectId,
  onReviewLearningPath
}: {
  projectId: string;
  onReviewLearningPath: () => void;
}) {
  const authentication = useAuthentication();
  const [learning, setLearning] = useState<ContinuousLearningResponse | null>(null);
  const [activeLessonId, setActiveLessonId] = useState<string | null>(null);
  const [selectedChoiceId, setSelectedChoiceId] = useState("");
  const [orderedStepIds, setOrderedStepIds] = useState<string[]>([]);
  const [sourceCode, setSourceCode] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = async (suffix = "", init: RequestInit = {}) => {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) throw new Error("The API URL is not configured.");
    const response = await authenticatedFetch(
      `${baseUrl}/api/v1/projects/${projectId}/learning-path/continuous-lessons${suffix}`,
      {
        ...init,
        headers: { "Content-Type": "application/json", ...init.headers },
        getToken: authentication.getToken,
        onUnauthorized: authentication.markSessionExpired
      }
    );
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) throw new Error(responseMessages(payload)[0] ?? "Continuous learning could not be completed safely.");
    return payload;
  };

  useEffect(() => {
    let cancelled = false;
    setLearning(null);
    setActiveLessonId(null);
    setError(null);
    setIsLoading(true);
    void request()
      .then((payload) => {
        if (!cancelled && isContinuousResponse(payload)) {
          setLearning(payload);
          setActiveLessonId(payload.resume_lesson_id);
        }
      })
      .catch((requestError) => {
        if (!cancelled && !(requestError instanceof AuthenticationRequestError)) {
          setError(requestError instanceof Error ? requestError.message : "Saved continuous lessons could not be loaded.");
        }
      })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
    // Authentication callbacks are stable within the provider; project changes reset this section.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const activeLesson = useMemo(
    () => learning?.lessons.find((lesson) => lesson.id === activeLessonId)
      ?? learning?.lessons.find((lesson) => !lesson.completed)
      ?? learning?.lessons.at(-1)
      ?? null,
    [activeLessonId, learning]
  );
  const hasCurrentLesson = learning?.lessons.some((lesson) => !lesson.completed) ?? false;
  const evidence = new Map((learning?.evidence_catalog ?? []).map((item) => [item.id, item]));

  useEffect(() => {
    setSelectedChoiceId("");
    setOrderedStepIds([]);
    setSourceCode(activeLesson?.activity.starter_code ?? "");
    setAnswerText("");
    setError(null);
  }, [activeLesson?.id]);

  async function generateLesson() {
    setIsGenerating(true);
    setError(null);
    try {
      const payload = await request("", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() }
      });
      if (isContinuousResponse(payload)) {
        setLearning(payload);
        setActiveLessonId(payload.resume_lesson_id ?? payload.lessons.at(-1)?.id ?? null);
      }
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) {
        setError(requestError instanceof Error ? requestError.message : "Another lesson could not be generated.");
      }
    } finally {
      setIsGenerating(false);
    }
  }

  async function submitAttempt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeLesson) return;
    const activity = activeLesson.activity;
    if (["evidence_selection", "test_interpretation"].includes(activity.activity_type) && !selectedChoiceId) {
      setError("Choose one answer before submitting.");
      return;
    }
    if (activity.activity_type === "ordering" && (orderedStepIds.length !== activity.choices.length || new Set(orderedStepIds).size !== activity.choices.length)) {
      setError("Place every step exactly once before submitting.");
      return;
    }
    if (["explain_back", "trade_off"].includes(activity.activity_type) && answerText.trim().length < 40) {
      setError("Write at least 40 meaningful characters before submitting.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = await request(`/${activeLesson.id}/attempts`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          context_id: activity.context_id,
          selected_choice_id: ["evidence_selection", "test_interpretation"].includes(activity.activity_type) ? selectedChoiceId : null,
          ordered_step_ids: activity.activity_type === "ordering" ? orderedStepIds : null,
          source_code: activity.activity_type === "ast_fixture" ? sourceCode : null,
          answer_text: ["explain_back", "trade_off"].includes(activity.activity_type) ? answerText : null
        })
      });
      if (typeof payload === "object" && payload !== null && "lesson" in payload) {
        const lesson = (payload as { lesson: ContinuousLesson }).lesson;
        setLearning((current) => current ? {
          ...current,
          lessons: current.lessons.map((item) => item.id === lesson.id ? lesson : item),
          resume_lesson_id: lesson.id
        } : current);
      }
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) {
        setError(requestError instanceof Error ? requestError.message : "The lesson answer could not be evaluated.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="continuous-learning glass-surface" aria-labelledby="continuous-learning-title">
      <header className="continuous-learning__header">
        <div>
          <p className="eyebrow">Continuous Learning Mode</p>
          <h3 id="continuous-learning-title">Keep learning one saved lesson at a time</h3>
          <p>New lessons are generated from confirmed repository evidence and your saved learning history.</p>
          <p className="session-disclaimer">Lessons vary focus, framing, format, or depth; the product does not promise unlimited unique repository facts.</p>
        </div>
        <div className="continuous-learning__actions">
          <button className="button" type="button" onClick={() => void generateLesson()} disabled={isGenerating || isLoading || hasCurrentLesson}>
            {isGenerating ? "Generating one lesson..." : "Generate another lesson"}
          </button>
          <button className="button button--quiet" type="button" onClick={onReviewLearningPath}>Review learning path</button>
        </div>
      </header>

      {hasCurrentLesson && <p className="message">Finish or resume the current generated lesson before creating another.</p>}
      {error && <p className="message message--error" role="alert">{error}</p>}
      {isLoading && <p role="status">Loading saved continuous lessons...</p>}

      {learning && learning.lessons.length > 0 && (
        <div className="continuous-learning__layout">
          <nav className="continuous-learning__history" aria-label="Generated lesson history">
            <h4>Previous generated lessons</h4>
            <ol>
              {learning.lessons.map((lesson) => (
                <li key={lesson.id}>
                  <button type="button" aria-current={lesson.id === activeLesson?.id ? "page" : undefined} onClick={() => setActiveLessonId(lesson.id)}>
                    <span>Lesson {lesson.sequence}</span>
                    <strong>{lesson.title}</strong>
                    <StatusBadge tone={lesson.completed ? "confirmed" : "current"}>{lesson.completed ? "Completed" : "Current"}</StatusBadge>
                  </button>
                </li>
              ))}
            </ol>
            {hasCurrentLesson && (
              <button className="button button--quiet" type="button" onClick={() => setActiveLessonId(learning.lessons.find((lesson) => !lesson.completed)?.id ?? null)}>Resume current lesson</button>
            )}
          </nav>

          {activeLesson && (
            <article className="continuous-learning__lesson activity-card" aria-labelledby={`continuous-lesson-${activeLesson.id}`}>
              <header>
                <p className="eyebrow">Generated lesson {activeLesson.sequence}</p>
                <h4 id={`continuous-lesson-${activeLesson.id}`}>{activeLesson.title}</h4>
                <div className="continuous-learning__metadata">
                  <span><strong>Focus:</strong> {activeLesson.focus}</span>
                  <span><strong>Activity format:</strong> {formatLabel(activeLesson.lesson_format)}</span>
                  <span><strong>Difficulty:</strong> {formatLabel(activeLesson.difficulty)}</span>
                  <span><strong>State:</strong> {activeLesson.completed ? "Completed" : "Ready"}</span>
                </div>
              </header>

              <section><h5>What you will learn</h5><p>{activeLesson.objective}</p></section>
              <section><h5>Evidence-grounded explanation</h5><p>{activeLesson.explanation}</p></section>
              <section><h5>Illustrative teaching example</h5><p>{activeLesson.illustrative_example}</p></section>
              <section><h5>Unknown or uninspected behavior</h5><ul>{activeLesson.unknown_or_uninspected.map((item) => <li key={item}>{item}</li>)}</ul></section>

              {!activeLesson.completed && (
                <form className="assessment-form" onSubmit={submitAttempt}>
                  <fieldset><legend>{activeLesson.activity.prompt}</legend>
                    {["evidence_selection", "test_interpretation"].includes(activeLesson.activity.activity_type) && activeLesson.activity.choices.map((choice) => (
                      <label className="choice" key={choice.id}><input type="radio" name={`continuous-${activeLesson.id}`} checked={selectedChoiceId === choice.id} onChange={() => setSelectedChoiceId(choice.id)} />{choice.label}</label>
                    ))}
                    {activeLesson.activity.activity_type === "ordering" && activeLesson.activity.choices.map((_, index) => (
                      <label className="field" key={index} htmlFor={`continuous-order-${activeLesson.id}-${index}`}>Position {index + 1}
                        <select id={`continuous-order-${activeLesson.id}-${index}`} value={orderedStepIds[index] ?? ""} onChange={(event) => setOrderedStepIds((current) => { const next = [...current]; next[index] = event.target.value; return next; })}>
                          <option value="">Choose a step</option>
                          {activeLesson.activity.choices.map((choice) => <option key={choice.id} value={choice.id} disabled={orderedStepIds.includes(choice.id) && orderedStepIds[index] !== choice.id}>{choice.label}</option>)}
                        </select>
                      </label>
                    ))}
                    {activeLesson.activity.activity_type === "ast_fixture" && <label className="field" htmlFor={`continuous-source-${activeLesson.id}`}>Teaching fixture<textarea id={`continuous-source-${activeLesson.id}`} value={sourceCode} maxLength={1000} spellCheck={false} onChange={(event) => setSourceCode(event.target.value)} /></label>}
                    {["explain_back", "trade_off"].includes(activeLesson.activity.activity_type) && <label className="field" htmlFor={`continuous-answer-${activeLesson.id}`}>Your answer<textarea id={`continuous-answer-${activeLesson.id}`} value={answerText} maxLength={activeLesson.activity.maximum_answer_length} onChange={(event) => setAnswerText(event.target.value)} /></label>}
                  </fieldset>
                  <ul>{activeLesson.activity.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
                  <button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving answer..." : "Submit answer"}</button>
                </form>
              )}

              {activeLesson.review && (
                <section className="feedback-panel continuous-learning__review" aria-label="Saved lesson review">
                  <h5>Submitted answer</h5><pre>{activeLesson.review.submitted_answer}</pre>
                  <h5>Expected or reference answer</h5><pre>{activeLesson.review.expected_answer}</pre>
                  <h5>Why it is correct</h5><p>{activeLesson.review.why_correct}</p>
                  <h5>Connection to this project</h5><p>{activeLesson.review.project_connection}</p>
                  <h5>Feedback</h5><p>{activeLesson.review.feedback}</p>
                  {activeLesson.review.earned_points !== null && <p><strong>Educational feedback points:</strong> {activeLesson.review.earned_points}/2</p>}
                  {activeLesson.review.checks.length > 0 && <ul>{activeLesson.review.checks.map((check) => <li key={check.id}><strong>{check.passed ? "Passed" : "Needs work"}:</strong> {check.message}</li>)}</ul>}
                  <h5>Confirmed evidence used</h5>
                  <ul>{activeLesson.review.evidence_ids.map((id) => <li key={id}><strong>{evidence.get(id)?.label ?? id}</strong>{evidence.get(id)?.detail ? ` — ${evidence.get(id)?.detail}` : ""}</li>)}</ul>
                </section>
              )}

              <section><h5>Suggested next focus</h5><p>{activeLesson.suggested_next_focus}</p></section>
            </article>
          )}
        </div>
      )}
    </section>
  );
}
