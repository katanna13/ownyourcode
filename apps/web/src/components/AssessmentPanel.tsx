import { FormEvent, useState } from "react";

import { VerifiedLabPanel } from "./VerifiedLabPanel";

type LearnerLevel = "beginner" | "junior" | "intermediate";

type MultipleChoiceQuestion = {
  id: "architecture-orientation.mcq.statement.v1";
  type: "multiple_choice";
  prompt: string;
  options: Array<{ id: string; label: string }>;
};

type EvidenceChoice = { id: string; label: string };

type EvidenceSelectionQuestion = {
  id: "architecture-orientation.evidence.direct-support.v1";
  type: "evidence_selection";
  prompt: string;
  evidence_choices: EvidenceChoice[];
};

type ExplainBackQuestion = {
  id: "architecture-orientation.explain-back.evidence-limitation.v1";
  type: "explain_back";
  prompt: string;
  evidence_choices: EvidenceChoice[];
};

type AssessmentQuestionsResponse = {
  persisted: false;
  message: string;
  assessment_context_id: string;
  inspection_limitations: string[];
  questions: [
    MultipleChoiceQuestion,
    EvidenceSelectionQuestion,
    ExplainBackQuestion
  ];
};

type AssessmentEvaluationResponse = {
  persisted: false;
  message: string;
  score: { earned_points: number; total_points: 4 };
  feedback: Array<{
    question_id: string;
    earned_points: number;
    max_points: number;
    message: string;
  }>;
  explain_back_feedback: {
    question_id: string;
    earned_points: number;
    max_points: 2;
    feedback: string;
  };
  inspection_limitations: string[];
};

type AssessmentPanelProps = {
  repositoryUrl: string;
  learnerLevel: LearnerLevel;
  lessonReady: boolean;
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

export function AssessmentPanel({
  repositoryUrl,
  learnerLevel,
  lessonReady
}: AssessmentPanelProps) {
  const [questions, setQuestions] = useState<AssessmentQuestionsResponse | null>(null);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [selectedOptionId, setSelectedOptionId] = useState("");
  const [selectedEvidenceId, setSelectedEvidenceId] = useState("");
  const [explainBack, setExplainBack] = useState("");
  const [explainEvidenceIds, setExplainEvidenceIds] = useState<string[]>([]);
  const [result, setResult] = useState<AssessmentEvaluationResponse | null>(null);

  if (!lessonReady) {
    return null;
  }

  async function loadQuestions() {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setErrors(["The API URL is not configured."]);
      return;
    }
    setIsLoadingQuestions(true);
    setErrors([]);
    setQuestions(null);
    setResult(null);
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/assessments/architecture-orientation/questions`,
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
        const messages = responseMessages(payload);
        setErrors(
          messages.length > 0
            ? messages
            : ["The assessment questions could not be prepared. Please try again."]
        );
        return;
      }
      setSelectedOptionId("");
      setSelectedEvidenceId("");
      setExplainBack("");
      setExplainEvidenceIds([]);
      setQuestions(payload as AssessmentQuestionsResponse);
    } catch {
      setErrors(["The API could not be reached. Please try again."]);
    } finally {
      setIsLoadingQuestions(false);
    }
  }

  function toggleExplainEvidence(evidenceId: string) {
    setExplainEvidenceIds((current) => {
      if (current.includes(evidenceId)) {
        return current.filter((id) => id !== evidenceId);
      }
      return current.length >= 2 ? current : [...current, evidenceId];
    });
  }

  async function submitAnswers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!questions || !selectedOptionId || !selectedEvidenceId || !explainBack.trim() || explainEvidenceIds.length === 0) {
      setErrors(["Answer every question and select evidence for your explanation."]);
      return;
    }
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setErrors(["The API URL is not configured."]);
      return;
    }
    setIsSubmitting(true);
    setErrors([]);
    setResult(null);
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/assessments/architecture-orientation/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            learner_level: learnerLevel,
            assessment_context_id: questions.assessment_context_id,
            answers: {
              multiple_choice: {
                question_id: "architecture-orientation.mcq.statement.v1",
                selected_option_id: selectedOptionId
              },
              evidence_selection: {
                question_id: "architecture-orientation.evidence.direct-support.v1",
                selected_evidence_id: selectedEvidenceId
              },
              explain_back: {
                question_id: "architecture-orientation.explain-back.evidence-limitation.v1",
                answer_text: explainBack,
                evidence_ids: explainEvidenceIds
              }
            }
          })
        }
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const messages = responseMessages(payload);
        setErrors(
          messages.length > 0
            ? messages
            : ["The assessment could not be evaluated. Please try again."]
        );
        return;
      }
      setResult(payload as AssessmentEvaluationResponse);
    } catch {
      setErrors(["The API could not be reached. Please try again."]);
    } finally {
      setIsSubmitting(false);
    }
  }

  const multipleChoice = questions?.questions.find(
    (question): question is MultipleChoiceQuestion => question.type === "multiple_choice"
  );
  const evidenceSelection = questions?.questions.find(
    (question): question is EvidenceSelectionQuestion => question.type === "evidence_selection"
  );
  const explainBackQuestion = questions?.questions.find(
    (question): question is ExplainBackQuestion => question.type === "explain_back"
  );

  return (
    <section className="assessment" aria-labelledby="assessment-title">
      <h3 id="assessment-title">Check your understanding of the repository orientation.</h3>
      <p>This evaluates the confirmed repository evidence. Nothing is saved.</p>
      {!questions && (
        <button className="button" type="button" onClick={loadQuestions} disabled={isLoadingQuestions}>
          {isLoadingQuestions ? "Preparing assessment..." : "Start knowledge check"}
        </button>
      )}
      {errors.length > 0 && (
        <section className="message message--error" role="alert">
          <h4>Assessment needs attention</h4>
          <ul>{errors.map((message) => <li key={message}>{message}</li>)}</ul>
        </section>
      )}
      {questions && multipleChoice && evidenceSelection && explainBackQuestion && (
        <form className="assessment-form" onSubmit={submitAnswers}>
          <fieldset>
            <legend>{multipleChoice.prompt}</legend>
            {multipleChoice.options.map((option) => (
              <label className="choice" key={option.id}>
                <input
                  type="radio"
                  name="assessment-multiple-choice"
                  value={option.id}
                  checked={selectedOptionId === option.id}
                  onChange={() => setSelectedOptionId(option.id)}
                />
                {option.label}
              </label>
            ))}
          </fieldset>
          <fieldset>
            <legend>{evidenceSelection.prompt}</legend>
            {evidenceSelection.evidence_choices.map((choice) => (
              <label className="choice" key={choice.id}>
                <input
                  type="radio"
                  name="assessment-evidence-selection"
                  value={choice.id}
                  checked={selectedEvidenceId === choice.id}
                  onChange={() => setSelectedEvidenceId(choice.id)}
                />
                {choice.label}
              </label>
            ))}
          </fieldset>
          <fieldset>
            <legend>{explainBackQuestion.prompt}</legend>
            <label className="field" htmlFor="explain-back-answer">
              Your explanation
              <textarea
                id="explain-back-answer"
                value={explainBack}
                minLength={20}
                maxLength={600}
                onChange={(event) => setExplainBack(event.target.value)}
              />
            </label>
            <p>Select one or two evidence items used in your explanation.</p>
            {explainBackQuestion.evidence_choices.map((choice) => (
              <label className="choice" key={choice.id}>
                <input
                  type="checkbox"
                  name="assessment-explain-evidence"
                  value={choice.id}
                  checked={explainEvidenceIds.includes(choice.id)}
                  disabled={!explainEvidenceIds.includes(choice.id) && explainEvidenceIds.length >= 2}
                  onChange={() => toggleExplainEvidence(choice.id)}
                />
                {choice.label}
              </label>
            ))}
          </fieldset>
          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Evaluating explanation..." : "Submit answers"}
          </button>
        </form>
      )}
      {result && (
        <section className="message message--success" role="status">
          <h4>Assessment feedback</h4>
          <p>{result.message}</p>
          <p><strong>Score:</strong> {result.score.earned_points} / {result.score.total_points}</p>
          <ul>
            {result.feedback.map((feedback) => (
              <li key={feedback.question_id}>{feedback.message} ({feedback.earned_points}/{feedback.max_points})</li>
            ))}
            <li>{result.explain_back_feedback.feedback} ({result.explain_back_feedback.earned_points}/{result.explain_back_feedback.max_points})</li>
          </ul>
          <h4>Inspection limitations</h4>
          <ul>{result.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        </section>
      )}
      <VerifiedLabPanel
        repositoryUrl={repositoryUrl}
        learnerLevel={learnerLevel}
        assessmentReady={Boolean(result)}
      />
    </section>
  );
}
