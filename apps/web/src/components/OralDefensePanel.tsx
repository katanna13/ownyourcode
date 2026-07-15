import { FormEvent, useEffect, useRef, useState } from "react";

import { calculatePreviewOwnershipScore } from "./previewOwnershipScore";

type LearnerLevel = "beginner" | "junior" | "intermediate";

type AssessmentScore = {
  earned_points: number;
  total_points: number;
};

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
  assessmentScore: AssessmentScore | null;
  verifiedLabPassed: boolean;
  securityChallengePassed: boolean;
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

function formatPoints(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

export function OralDefensePanel({
  repositoryUrl,
  learnerLevel,
  assessmentScore,
  verifiedLabPassed,
  securityChallengePassed
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
    assessmentScore?.earned_points,
    assessmentScore?.total_points,
    verifiedLabPassed,
    securityChallengePassed
  ]);

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

  const score = evaluation
    ? assessmentScore
      ? calculatePreviewOwnershipScore({
        assessmentEarnedPoints: assessmentScore.earned_points,
        assessmentTotalPoints: assessmentScore.total_points,
        verifiedLabPassed,
        securityChallengePassed,
        oralDefenseEarnedPoints: evaluation.oral_defense_points.earned_points,
        oralDefenseMaxPoints: evaluation.oral_defense_points.max_points
      })
      : {
        valid: false as const,
        message: "The current browser-session assessment score is unavailable."
      }
    : null;

  return (
    <section className="oral-defense" aria-labelledby="oral-defense-title">
      <h3 id="oral-defense-title">Architecture oral defense</h3>
      <p>Defend your reasoning from bounded repository evidence. Nothing is saved.</p>
      <p className="session-disclaimer">Preview Ownership Score is a non-persistent summary of this browser’s current in-memory demo session. It is not an authenticated certification and cannot prove completion after refresh, another browser, or another device.</p>

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
          <ul>
            {preparation.question.boundary_evidence.map((item) => (
              <li key={item.evidence.id}>{item.category}: {item.evidence.label} ({item.evidence.id})</li>
            ))}
          </ul>
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
        <section className="message" role="status">
          <h4>Oral-defense feedback</h4>
          <p>{evaluation.message}</p>
          <p><strong>Oral-defense points:</strong> {evaluation.oral_defense_points.earned_points} / {evaluation.oral_defense_points.max_points}</p>
          <ul>
            {evaluation.rubric_dimensions.map((dimension) => (
              <li key={dimension.id}>{dimension.feedback} ({dimension.earned_points}/{dimension.max_points})</li>
            ))}
          </ul>
          <h5>Inspection limitations</h5>
          <ul>{evaluation.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        </section>
      )}

      {score && !score.valid && (
        <section className="message message--error" role="alert">
          <h4>Preview Ownership Score unavailable</h4>
          <p>{score.message}</p>
        </section>
      )}

      {score && score.valid && (
        <section className="message message--success preview-score" role="status">
          <h4>Preview Ownership Score: {score.breakdown.previewScore} / 100</h4>
          <p>Raw total: {formatPoints(score.breakdown.rawTotal)}. The non-negative final value uses Math.round.</p>
          <ul>
            <li>Assessment: {formatPoints(score.breakdown.assessment)} / 30</li>
            <li>Verified lab: {formatPoints(score.breakdown.verifiedLab)} / 25</li>
            <li>Security challenge: {formatPoints(score.breakdown.securityChallenge)} / 20</li>
            <li>Oral defense: {formatPoints(score.breakdown.oralDefense)} / 25</li>
          </ul>
          <p><strong>Demo session complete.</strong> This score is session-only and was not saved.</p>
        </section>
      )}
    </section>
  );
}
