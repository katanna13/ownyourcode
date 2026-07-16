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

type AvailableLab = {
  persisted: false;
  available: true;
  message: string;
  lab_id: "fastapi-health-check.v1";
  lab_context_id: string;
  title: string;
  learning_objective: string;
  instructions: string;
  starter_code: string;
  constraints: string[];
  relevant_evidence: RelevantEvidence[];
  maximum_source_length: number;
  inspection_limitations: string[];
};

type UnavailableLab = {
  persisted: false;
  available: false;
  message: string;
  reason: string;
  inspection_limitations: string[];
};

type LabPreparation = AvailableLab | UnavailableLab;

type LabEvaluation = {
  persisted: false;
  passed: boolean;
  message: string;
  checks: Array<{ id: string; passed: boolean; message: string }>;
  feedback: string[];
  inspection_limitations: string[];
};

type VerifiedLabPanelProps = {
  repositoryUrl: string;
  learnerLevel: LearnerLevel;
  assessmentReady: boolean;
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

export function VerifiedLabPanel({
  repositoryUrl,
  learnerLevel,
  assessmentReady,
  progressReporter
}: VerifiedLabPanelProps) {
  const [preparation, setPreparation] = useState<LabPreparation | null>(null);
  const [sourceCode, setSourceCode] = useState("");
  const [evaluation, setEvaluation] = useState<LabEvaluation | null>(null);
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
  }, [repositoryUrl, learnerLevel, assessmentReady]);

  useEffect(() => {
    if (evaluation) {
      progressReporter?.reportVerifiedLab(evaluation.passed);
    }
  }, [evaluation, progressReporter]);

  if (!assessmentReady) {
    return null;
  }

  async function prepareLab() {
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
        `${baseUrl}/api/v1/labs/fastapi-health-check/prepare`,
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
            : ["The verified lab could not be prepared. Please try again."]
        );
        return;
      }
      const preparedLab = payload as LabPreparation;
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      setPreparation(preparedLab);
      if (preparedLab.available) {
        setSourceCode(preparedLab.starter_code);
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

  async function evaluateLab(event: FormEvent<HTMLFormElement>) {
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
        `${baseUrl}/api/v1/labs/fastapi-health-check/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            learner_level: learnerLevel,
            lab_context_id: preparation.lab_context_id,
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
            : ["The verified lab could not be evaluated. Please try again."]
        );
        return;
      }
      if (contextVersion.current !== requestContextVersion) {
        return;
      }
      setEvaluation(payload as LabEvaluation);
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
    <section className="verified-lab activity-card" id="lab" aria-labelledby="verified-lab-title">
      <h3 id="verified-lab-title">Verified coding lab</h3>
      <p>Practice a small server-owned teaching fixture after your assessment. Nothing is saved.</p>

      {!preparation && (
        <button className="button" type="button" onClick={prepareLab} disabled={isPreparing}>
          {isPreparing ? "Preparing verified lab..." : "Prepare verified lab"}
        </button>
      )}

      {errors.length > 0 && (
        <section className="message message--error" role="alert">
          <h4>Verified lab needs attention</h4>
          <ul>{errors.map((message) => <li key={message}>{message}</li>)}</ul>
        </section>
      )}

      {preparation && !preparation.available && (
        <section className="message" role="status">
          <h4>Lab unavailable</h4>
          <p>{preparation.reason}</p>
          <h5>Inspection limitations</h5>
          <ul>{preparation.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        </section>
      )}

      {preparation && preparation.available && (
        <form className="verified-lab-form" onSubmit={evaluateLab}>
          <h4>{preparation.title}</h4>
          <p>{preparation.learning_objective}</p>
          <p>{preparation.instructions}</p>
          <h5>Relevant evidence</h5>
          <ul>{preparation.relevant_evidence.map((item) => <li key={item.id}>{item.label} ({item.id})</li>)}</ul>
          <h5>Constraints</h5>
          <ul>{preparation.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
          <CodeFixtureEditor
            id="verified-lab-source"
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
          <h4>{evaluation.passed ? "Lab passed" : "Lab needs another attempt"}</h4>
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
