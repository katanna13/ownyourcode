import { FormEvent, useEffect, useRef, useState } from "react";

import { CheckResultList } from "./CheckResultList";
import { CodeFixtureEditor } from "./CodeFixtureEditor";
import { LearnerLevel, WorkspaceProgressReporter } from "../types/workspace";


type RelevantEvidence = {
  id: string;
  kind: string;
  label: string;
  detail: string;
};

type AvailableSecurityChallenge = {
  persisted: false;
  available: true;
  message: string;
  security_challenge_id: "fastapi-cors.v1";
  security_challenge_context_id: string;
  title: string;
  learning_objective: string;
  instructions: string;
  starter_code: string;
  constraints: string[];
  relevant_evidence: RelevantEvidence[];
  maximum_source_length: number;
  inspection_limitations: string[];
};

type UnavailableSecurityChallenge = {
  persisted: false;
  available: false;
  message: string;
  reason: string;
  inspection_limitations: string[];
};

type SecurityChallengePreparation =
  | AvailableSecurityChallenge
  | UnavailableSecurityChallenge;

type SecurityChallengeEvaluation = {
  persisted: false;
  passed: boolean;
  message: string;
  checks: Array<{ id: string; passed: boolean; message: string }>;
  feedback: string[];
  inspection_limitations: string[];
};

type SecurityChallengePanelProps = {
  repositoryUrl: string;
  learnerLevel: LearnerLevel;
  verifiedLabPassed: boolean;
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

export function SecurityChallengePanel({
  repositoryUrl,
  learnerLevel,
  verifiedLabPassed,
  progressReporter
}: SecurityChallengePanelProps) {
  const [preparation, setPreparation] =
    useState<SecurityChallengePreparation | null>(null);
  const [sourceCode, setSourceCode] = useState("");
  const [evaluation, setEvaluation] =
    useState<SecurityChallengeEvaluation | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const contextVersion = useRef(0);

  useEffect(() => {
    contextVersion.current += 1;
    setPreparation(null);
    setSourceCode("");
    setEvaluation(null);
    setErrors([]);
    setIsPreparing(false);
    setIsSubmitting(false);
  }, [repositoryUrl, learnerLevel, verifiedLabPassed]);

  useEffect(() => {
    if (evaluation) {
      progressReporter?.reportSecurityChallenge(evaluation.passed);
    }
  }, [evaluation, progressReporter]);

  if (!verifiedLabPassed) {
    return null;
  }

  async function prepareChallenge() {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setErrors(["The API URL is not configured."]);
      return;
    }
    setIsPreparing(true);
    setPreparation(null);
    setSourceCode("");
    setEvaluation(null);
    setErrors([]);
    const requestContextVersion = contextVersion.current;
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/security-challenges/fastapi-cors/prepare`,
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
            : ["The security challenge could not be prepared. Please try again."]
        );
        return;
      }
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      const preparedChallenge = payload as SecurityChallengePreparation;
      setPreparation(preparedChallenge);
      if (preparedChallenge.available) {
        setSourceCode(preparedChallenge.starter_code);
      }
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

  function resetFixture() {
    if (!preparation || !preparation.available) {
      return;
    }
    setSourceCode(preparation.starter_code);
    setEvaluation(null);
    setErrors([]);
  }

  async function evaluateChallenge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preparation || !preparation.available) {
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
        `${baseUrl}/api/v1/security-challenges/fastapi-cors/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            learner_level: learnerLevel,
            security_challenge_context_id: preparation.security_challenge_context_id,
            source_code: sourceCode
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
            : ["The security challenge could not be evaluated. Please try again."]
        );
        return;
      }
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      setEvaluation(payload as SecurityChallengeEvaluation);
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
    <section className="security-challenge activity-card" id="secure" aria-labelledby="security-challenge-title">
      <h3 id="security-challenge-title">Verified security challenge</h3>
      <p>Practice a server-owned CORS teaching fixture for this FastAPI-oriented stack. This is not a repository security scan. Nothing is saved.</p>

      {!preparation && (
        <button className="button" type="button" onClick={prepareChallenge} disabled={isPreparing}>
          {isPreparing ? "Preparing security challenge..." : "Prepare security challenge"}
        </button>
      )}

      {errors.length > 0 && (
        <section className="message message--error" role="alert">
          <h4>Security challenge needs attention</h4>
          <ul>{errors.map((message) => <li key={message}>{message}</li>)}</ul>
        </section>
      )}

      {preparation && !preparation.available && (
        <section className="message" role="status">
          <h4>Security challenge unavailable</h4>
          <p>{preparation.reason}</p>
          <h5>Inspection limitations</h5>
          <ul>{preparation.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        </section>
      )}

      {preparation && preparation.available && (
        <form className="security-challenge-form" onSubmit={evaluateChallenge}>
          <h4>{preparation.title}</h4>
          <p>{preparation.learning_objective}</p>
          <p>{preparation.instructions}</p>
          <h5>Relevant evidence</h5>
          <ul>{preparation.relevant_evidence.map((item) => <li key={item.id}>{item.label} ({item.id})</li>)}</ul>
          <h5>Constraints</h5>
          <ul>{preparation.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
          <CodeFixtureEditor
            id="security-challenge-source"
            value={sourceCode}
            maximumLength={preparation.maximum_source_length}
            onChange={setSourceCode}
            onReset={resetFixture}
            isSubmitting={isSubmitting}
            submitLabel="Submit fixture"
            submittingLabel="Verifying fixture..."
          />
        </form>
      )}

      {evaluation && (
        <section className={`message ${evaluation.passed ? "message--success" : "message--error"}`} role="status">
          <h4>{evaluation.passed ? "Security challenge passed" : "Security challenge needs another attempt"}</h4>
          <p>{evaluation.message}</p>
          <CheckResultList checks={evaluation.checks} />
          <h5>Feedback</h5>
          <ul>{evaluation.feedback.map((item) => <li key={item}>{item}</li>)}</ul>
          <h5>Inspection limitations</h5>
          <ul>{evaluation.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        </section>
      )}
    </section>
  );
}
