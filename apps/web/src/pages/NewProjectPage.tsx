import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { AssessmentPanel } from "../components/AssessmentPanel";

type ProjectMode = "existing_repository" | "new_idea";
type LearnerLevel = "beginner" | "junior" | "intermediate";

type ProjectPreviewResponse = {
  validated: boolean;
  persisted: boolean;
  message: string;
  project: {
    name: string;
    description: string;
    mode: ProjectMode;
    repository_url: string | null;
  };
};

type RepositoryInspectionResponse = {
  persisted: boolean;
  message: string;
  repository: {
    name: string;
    full_name: string;
    description: string | null;
    default_branch: string;
    primary_language: string | null;
    html_url: string;
  };
  languages: Array<{ name: string; bytes: number }>;
  technologies: Array<{ key: string; label: string; evidence: string[] }>;
  paths: { inspected_count: number; returned: string[]; truncated: boolean };
  important_files: Array<{ path: string; kind: string }>;
  limitations: string[];
};

type EvidenceItem = { id: string; kind: string; label: string; detail: string };

type LessonResponse = {
  persisted: boolean;
  message: string;
  inspection_limitations: string[];
  evidence_catalog: EvidenceItem[];
  lesson: {
    title: string;
    learning_objective: string;
    repository_summary: string;
    repository_summary_evidence_ids: string[];
    concepts: Array<{
      title: string;
      explanation: string;
      why_it_matters: string;
      evidence_ids: string[];
      reflection_question: string;
    }>;
    architecture_walkthrough: Array<{ step: string; evidence_ids: string[] }>;
    knowledge_check_questions: string[];
    limitations_and_open_questions: string[];
  };
};

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

function apiBaseUrl(): string | null {
  return import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || null;
}

export function NewProjectPage() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<ProjectMode>("new_idea");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [preview, setPreview] = useState<ProjectPreviewResponse | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const [inspectionErrors, setInspectionErrors] = useState<string[]>([]);
  const [inspection, setInspection] =
    useState<RepositoryInspectionResponse | null>(null);
  const [learnerLevel, setLearnerLevel] = useState<LearnerLevel>("beginner");
  const [learningGoal, setLearningGoal] = useState("");
  const [isGeneratingLesson, setIsGeneratingLesson] = useState(false);
  const [lessonErrors, setLessonErrors] = useState<string[]>([]);
  const [lesson, setLesson] = useState<LessonResponse | null>(null);

  function clearLesson() {
    setLessonErrors([]);
    setLesson(null);
  }

  function selectMode(nextMode: ProjectMode) {
    setMode(nextMode);
    setErrors([]);
    setInspectionErrors([]);
    setInspection(null);
    clearLesson();
    if (nextMode === "new_idea") {
      setRepositoryUrl("");
    }
  }

  async function submitPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrors([]);
    setPreview(null);
    setInspectionErrors([]);
    setInspection(null);
    clearLesson();

    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setErrors(["The API URL is not configured."]);
      setIsSubmitting(false);
      return;
    }

    const requestBody = {
      name,
      description,
      mode,
      ...(mode === "existing_repository" ? { repository_url: repositoryUrl } : {})
    };

    try {
      const response = await fetch(`${baseUrl}/api/v1/projects/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody)
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const messages = responseMessages(payload);
        setErrors(
          messages.length > 0
            ? messages
            : ["The server could not validate these project details."]
        );
        return;
      }
      setPreview(payload as ProjectPreviewResponse);
    } catch {
      setErrors(["The API could not be reached. Please try again."]);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function inspectRepository() {
    if (
      preview?.project.mode !== "existing_repository" ||
      !preview.project.repository_url
    ) {
      return;
    }

    setIsInspecting(true);
    setInspectionErrors([]);
    setInspection(null);
    clearLesson();

    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setInspectionErrors(["The API URL is not configured."]);
      setIsInspecting(false);
      return;
    }

    try {
      const response = await fetch(`${baseUrl}/api/v1/repositories/inspect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repository_url: preview.project.repository_url })
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const messages = responseMessages(payload);
        setInspectionErrors(
          messages.length > 0
            ? messages
            : ["The repository could not be inspected. Please try again."]
        );
        return;
      }
      setInspection(payload as RepositoryInspectionResponse);
    } catch {
      setInspectionErrors(["The API could not be reached. Please try again."]);
    } finally {
      setIsInspecting(false);
    }
  }

  async function generateLesson() {
    if (
      !inspection ||
      preview?.project.mode !== "existing_repository" ||
      !preview.project.repository_url
    ) {
      return;
    }

    setIsGeneratingLesson(true);
    setLessonErrors([]);
    setLesson(null);
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setLessonErrors(["The API URL is not configured."]);
      setIsGeneratingLesson(false);
      return;
    }

    const requestBody = {
      repository_url: preview.project.repository_url,
      learner_level: learnerLevel,
      ...(learningGoal.trim() ? { learning_goal: learningGoal.trim() } : {})
    };

    try {
      const response = await fetch(`${baseUrl}/api/v1/lessons/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody)
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const messages = responseMessages(payload);
        setLessonErrors(
          messages.length > 0
            ? messages
            : ["The lesson could not be generated. Please try again."]
        );
        return;
      }
      setLesson(payload as LessonResponse);
    } catch {
      setLessonErrors(["The API could not be reached. Please try again."]);
    } finally {
      setIsGeneratingLesson(false);
    }
  }

  const evidenceById = new Map(
    lesson?.evidence_catalog.map((item) => [item.id, item]) ?? []
  );

  function renderEvidence(evidenceIds: string[]) {
    return (
      <ul className="evidence-list" aria-label="Evidence">
        {evidenceIds.map((evidenceId) => {
          const item = evidenceById.get(evidenceId);
          return (
            <li className="evidence-chip" key={evidenceId}>
              {item ? `${item.label} (${item.id})` : evidenceId}
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <main className="page">
      <p className="eyebrow">Project intake</p>
      <h1>New Project</h1>
      <p>Validate a project idea or public repository before anything is saved.</p>

      <form className="project-form" onSubmit={submitPreview}>
        <label className="field" htmlFor="project-name">
          Project name
          <input id="project-name" name="name" value={name} onChange={(event) => {
            setName(event.target.value);
            setErrors([]);
          }} minLength={2} maxLength={100} required />
        </label>

        <label className="field" htmlFor="project-description">
          Short description
          <textarea id="project-description" name="description" value={description} onChange={(event) => {
            setDescription(event.target.value);
            setErrors([]);
          }} minLength={10} maxLength={500} required />
        </label>

        <fieldset>
          <legend>Project mode</legend>
          <label className="choice">
            <input type="radio" name="mode" value="new_idea" checked={mode === "new_idea"} onChange={() => selectMode("new_idea")} />
            New idea
          </label>
          <label className="choice">
            <input type="radio" name="mode" value="existing_repository" checked={mode === "existing_repository"} onChange={() => selectMode("existing_repository")} />
            Existing repository
          </label>
        </fieldset>

        {mode === "existing_repository" && (
          <label className="field" htmlFor="repository-url">
            Public GitHub repository URL
            <input id="repository-url" name="repository_url" type="url" value={repositoryUrl} onChange={(event) => {
              setRepositoryUrl(event.target.value);
              setErrors([]);
            }} placeholder="https://github.com/owner/repository" required />
          </label>
        )}

        <button className="button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Validating..." : "Validate project"}
        </button>
      </form>

      {errors.length > 0 && <ErrorPanel title="Validation needs attention" messages={errors} />}

      {preview && (
        <section className="message message--success" role="status">
          <h2>Validated preview</h2>
          <p>{preview.message}</p>
          <dl>
            <dt>Name</dt><dd>{preview.project.name}</dd>
            <dt>Mode</dt><dd>{preview.project.mode}</dd>
            {preview.project.repository_url && <><dt>Repository URL</dt><dd>{preview.project.repository_url}</dd></>}
          </dl>
          {preview.project.mode === "existing_repository" && preview.project.repository_url && (
            <button className="button" type="button" onClick={inspectRepository} disabled={isInspecting}>
              {isInspecting ? "Inspecting repository..." : "Inspect repository"}
            </button>
          )}
        </section>
      )}

      {inspectionErrors.length > 0 && <ErrorPanel title="Repository inspection could not finish" messages={inspectionErrors} />}

      {inspection && (
        <section className="message message--success inspection" role="status">
          <h2>Repository inspection</h2>
          <p>{inspection.message}</p>
          <dl>
            <dt>Repository</dt><dd><a href={inspection.repository.html_url}>{inspection.repository.full_name}</a></dd>
            <dt>Default branch</dt><dd>{inspection.repository.default_branch}</dd>
            <dt>Primary language</dt><dd>{inspection.repository.primary_language ?? "Not reported"}</dd>
          </dl>
          <h3>Languages</h3>
          <ul>{inspection.languages.map((language) => <li key={language.name}>{language.name}: {language.bytes} bytes</li>)}</ul>
          <h3>Detected technologies</h3>
          <ul>{inspection.technologies.map((technology) => <li key={technology.key}><strong>{technology.label}</strong><ul>{technology.evidence.map((evidence) => <li key={evidence}>{evidence}</li>)}</ul></li>)}</ul>
          <h3>Important files</h3>
          <ul>{inspection.important_files.map((file) => <li key={file.path}>{file.path} ({file.kind})</li>)}</ul>
          <h3>Path coverage</h3>
          <p>Inspected {inspection.paths.inspected_count} paths{inspection.paths.truncated ? "; path results were truncated." : "."}</p>
          <h3>Limitations</h3>
          <ul>{inspection.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>

          <section className="lesson-controls" aria-labelledby="lesson-controls-title">
            <h3 id="lesson-controls-title">Generate your first lesson</h3>
            <p>This creates a teaching preview from the inspection evidence. Nothing is saved.</p>
            <label className="field" htmlFor="learner-level">
              Learner level
              <select id="learner-level" value={learnerLevel} onChange={(event) => setLearnerLevel(event.target.value as LearnerLevel)}>
                <option value="beginner">Beginner</option>
                <option value="junior">Junior</option>
                <option value="intermediate">Intermediate</option>
              </select>
            </label>
            <label className="field" htmlFor="learning-goal">
              Learning goal (optional)
              <textarea id="learning-goal" value={learningGoal} onChange={(event) => setLearningGoal(event.target.value)} maxLength={240} />
            </label>
            <button className="button" type="button" onClick={generateLesson} disabled={isGeneratingLesson}>
              {isGeneratingLesson ? "Generating lesson..." : "Generate first lesson"}
            </button>
          </section>
        </section>
      )}

      {lessonErrors.length > 0 && <ErrorPanel title="Lesson generation could not finish" messages={lessonErrors} />}

      {lesson && (
        <section className="message message--success lesson" role="status">
          <h2>{lesson.lesson.title}</h2>
          <p>{lesson.message}</p>
          <h3>Learning objective</h3><p>{lesson.lesson.learning_objective}</p>
          <h3>Repository summary</h3><p>{lesson.lesson.repository_summary}</p>
          {renderEvidence(lesson.lesson.repository_summary_evidence_ids)}
          <h3>Concepts</h3>
          {lesson.lesson.concepts.map((concept) => (
            <article key={concept.title}>
              <h4>{concept.title}</h4><p>{concept.explanation}</p><p><strong>Why it matters:</strong> {concept.why_it_matters}</p>
              {renderEvidence(concept.evidence_ids)}
              <p><strong>Reflect:</strong> {concept.reflection_question}</p>
            </article>
          ))}
          <h3>Architecture walkthrough</h3>
          <ol>{lesson.lesson.architecture_walkthrough.map((step, index) => <li key={`${index}-${step.step}`}><p>{step.step}</p>{renderEvidence(step.evidence_ids)}</li>)}</ol>
          <h3>Knowledge check</h3>
          <ol>{lesson.lesson.knowledge_check_questions.map((question) => <li key={question}>{question}</li>)}</ol>
          <h3>Inspection limitations (deterministic)</h3>
          <ul>{lesson.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
          <h3>Lesson limitations and open questions</h3>
          <ul>{lesson.lesson.limitations_and_open_questions.map((item) => <li key={item}>{item}</li>)}</ul>
          {preview?.project.repository_url && (
            <AssessmentPanel
              repositoryUrl={preview.project.repository_url}
              learnerLevel={learnerLevel}
              lessonReady={Boolean(lesson)}
            />
          )}
        </section>
      )}

      <Link to="/">Back to home</Link>
    </main>
  );
}

function ErrorPanel({ title, messages }: { title: string; messages: string[] }) {
  return (
    <section className="message message--error" role="alert">
      <h2>{title}</h2>
      <ul>{messages.map((message) => <li key={message}>{message}</li>)}</ul>
    </section>
  );
}
