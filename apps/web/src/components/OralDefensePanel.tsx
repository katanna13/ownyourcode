import { FormEvent, useEffect, useRef, useState } from "react";

import { LearnerLevel, WorkspaceProgressReporter } from "../types/workspace";

type BoundaryEvidence = {
  category: "frontend" | "backend" | "container";
  evidence: { id: string; kind: string; label: string; detail: string };
};

type OralDefenseQuestion = {
  id: "architecture-boundaries.question.v1";
  prompt: string;
  boundary_evidence: BoundaryEvidence[];
};

type AvailableOralDefense = {
  persisted: false;
  available: true;
  message: string;
  oral_defense_id: "architecture-boundaries.v1";
  oral_defense_context_id: string;
  title: string;
  question: OralDefenseQuestion;
  maximum_answer_length: number;
  inspection_limitations: string[];
};

type UnavailableOralDefense = {
  persisted: false;
  available: false;
  message: string;
  reason: string;
  inspection_limitations: string[];
};

type OralDefensePreparation = AvailableOralDefense | UnavailableOralDefense;

type OralDefenseEvaluation = {
  persisted: false;
  message: string;
  oral_defense_points: { earned_points: number; max_points: number };
  rubric_dimensions: Array<{
    id: string;
    earned_points: number;
    max_points: number;
    feedback: string;
  }>;
  evidence_ids: string[];
  inspection_limitations: string[];
};

type OralDefensePanelProps = {
  repositoryUrl: string;
  learnerLevel: LearnerLevel;
  verifiedLabPassed: boolean;
  securityChallengePassed: boolean;
  progressReporter?: WorkspaceProgressReporter;
};

function apiBaseUrl(): string | null {
  return import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || null;
}

function responseMessages(payload: unknown): string[] {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return [];
  }
  const { detail } = payload;
  if (typeof detail === "string") {
    return [detail];
  }
  if (!Array.isArray(detail)) {
    return [];
  }
  return detail.flatMap((issue) => {
    if (
      typeof issue === "object" &&
      issue !== null &&
      "msg" in issue &&
      typeof issue.msg === "string"
    ) {
      return [issue.msg];
    }
    return [];
  });
}

export function OralDefensePanel({
  repositoryUrl,
  learnerLevel,
  verifiedLabPassed,
  securityChallengePassed,
  progressReporter
}: OralDefensePanelProps) {
  const [preparation, setPreparation] = useState<OralDefensePreparation | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [evaluation, setEvaluation] = useState<OralDefenseEvaluation | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const contextVersion = useRef(0);

  useEffect(() => {
    contextVersion.current += 1;
    setPreparation(null);
    setAnswerText("");
    setEvaluation(null);
    setErrors([]);
    setIsPreparing(false);
    setIsSubmitting(false);
  }, [
    repositoryUrl,
    learnerLevel,
    verifiedLabPassed,
    securityChallengePassed
  ]);

  useEffect(() => {
    if (evaluation) {
      progressReporter?.reportOralDefense(evaluation.oral_defense_points);
    }
  }, [evaluation, progressReporter]);

  if (!verifiedLabPassed || !securityChallengePassed) {
    return null;
  }

  async function prepareOralDefense() {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setErrors(["The API URL is not configured."]);
      return;
    }
    setIsPreparing(true);
    setPreparation(null);
    setAnswerText("");
    setEvaluation(null);
    setErrors([]);
    const requestContextVersion = contextVersion.current;
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/oral-defenses/architecture-boundaries/prepare`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            learner_level: learnerLevel
          })
        }
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        if (contextVersion.current !== requestContextVersion) {
          return;
        }
        const messages = responseMessages(payload);
        setErrors(
          messages.length > 0
            ? messages
            : ["The oral defense could not be prepared. Please try again."]
        );
        return;
      }
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      setPreparation(payload as OralDefensePreparation);
    } catch {
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      setErrors(["The API could not be reached. Please try again."]);
    } finally {
      if (contextVersion.current === requestContextVersion) {
        setIsPreparing(false);
      }
    }
  }

  async function evaluateOralDefense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preparation || !preparation.available) {
      return;
    }
    if (answerText.trim().length < 40) {
      setErrors(["Write at least 40 meaningful characters before submitting."]);
      return;
    }
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setErrors(["The API URL is not configured."]);
      return;
    }
    setIsSubmitting(true);
    setEvaluation(null);
    setErrors([]);
    const requestContextVersion = contextVersion.current;
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/oral-defenses/architecture-boundaries/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            learner_level: learnerLevel,
            oral_defense_context_id: preparation.oral_defense_context_id,
            question_id: preparation.question.id,
            answer_text: answerText
          })
        }
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        if (contextVersion.current !== requestContextVersion) {
          return;
        }
        const messages = responseMessages(payload);
        setErrors(
          messages.length > 0
            ? messages
            : ["The oral defense could not be evaluated. Please try again."]
        );
        return;
      }
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      setEvaluation(payload as OralDefenseEvaluation);
    } catch {
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      setErrors(["The API could not be reached. Please try again."]);
    } finally {
      if (contextVersion.current === requestContextVersion) {
        setIsSubmitting(false);
      }
    }
  }

  return (
    <section className="oral-defense activity-card" id="defend" aria-labelledby="oral-defense-title">
      <h3 id="oral-defense-title">Architecture oral defense</h3>
      <p>Defend your reasoning from bounded repository evidence. Nothing is saved.</p>

      {!preparation && (
        <button className="button" type="button" onClick={prepareOralDefense} disabled={isPreparing}>
          {isPreparing ? "Preparing oral defense..." : "Prepare oral defense"}
        </button>
      )}

      {errors.length > 0 && (
        <section className="message message--error" role="alert">
          <h4>Oral defense needs attention</h4>
          <ul>{errors.map((message) => <li key={message}>{message}</li>)}</ul>
        </section>
      )}

      {preparation && !preparation.available && (
        <section className="message" role="status">
          <h4>Oral defense unavailable</h4>
          <p>{preparation.reason}</p>
          <h5>Inspection limitations</h5>
          <ul>{preparation.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        </section>
      )}

      {preparation && preparation.available && (
        <form className="oral-defense-form" onSubmit={evaluateOralDefense}>
          <h4>{preparation.title}</h4>
          <p>{preparation.question.prompt}</p>
          <h5>Confirmed boundary evidence</h5>
          <div className="oral-defense__evidence">
            {preparation.question.boundary_evidence.map((item) => (
              <section className="oral-defense__boundary" key={item.evidence.id}>
                <h5>{item.category}</h5>
                <p>{item.evidence.label}</p>
                <code>{item.evidence.id}</code>
              </section>
            ))}
          </div>
          <label className="field" htmlFor="oral-defense-answer">
            Your defense
            <textarea
              id="oral-defense-answer"
              value={answerText}
              minLength={40}
              maxLength={preparation.maximum_answer_length}
              onChange={(event) => setAnswerText(event.target.value)}
            />
          </label>
          <p>Maximum answer length: {preparation.maximum_answer_length} characters.</p>
          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Evaluating oral defense..." : "Submit oral defense"}
          </button>
        </form>
      )}

      {evaluation && (
        <section className="oral-defense__feedback" role="status">
          <h4>Oral-defense feedback</h4>
          <p>{evaluation.message}</p>
          <p><strong>Oral-defense points:</strong> {evaluation.oral_defense_points.earned_points} / {evaluation.oral_defense_points.max_points}</p>
          <ul className="oral-defense__rubric">
            {evaluation.rubric_dimensions.map((dimension) => (
              <li key={dimension.id}>
                <span>{dimension.feedback}</span>
                <strong>{dimension.earned_points}/{dimension.max_points}</strong>
              </li>
            ))}
          </ul>
          <h5>Inspection limitations</h5>
          <ul>{evaluation.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        </section>
      )}
    </section>

  );
}
