import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { LearningWorkspace } from "../components/LearningWorkspace";
import {
  LearnerLevel,
  LessonResponse,
  ProjectMode,
  ProjectPreviewResponse,
  RepositoryInspectionResponse
} from "../types/workspace";

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

function ErrorPanel({ title, messages }: { title: string; messages: string[] }) {
  if (messages.length === 0) {
    return null;
  }

  return (
    <section className="message message--error" role="alert">
      <h2>{title}</h2>
      <ul>{messages.map((message) => <li key={message}>{message}</li>)}</ul>
    </section>
  );
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
  const [inspection, setInspection] = useState<RepositoryInspectionResponse | null>(null);
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
        setErrors(messages.length > 0 ? messages : ["The server could not validate these project details."]);
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
    if (preview?.project.mode !== "existing_repository" || !preview.project.repository_url) {
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
        setInspectionErrors(messages.length > 0 ? messages : ["The repository could not be inspected. Please try again."]);
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
    if (!inspection || preview?.project.mode !== "existing_repository" || !preview.project.repository_url) {
      return;
    }

    setIsGeneratingLesson(true);
    setLessonErrors([]);
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
        setLessonErrors(messages.length > 0 ? messages : ["The lesson could not be generated. Please try again."]);
        return;
      }
      setLesson(payload as LessonResponse);
    } catch {
      setLessonErrors(["The API could not be reached. Please try again."]);
    } finally {
      setIsGeneratingLesson(false);
    }
  }

  function changeLearnerLevel(level: LearnerLevel) {
    setLearnerLevel(level);
    clearLesson();
  }

  return (
    <main className="page page--onboarding">
      <header className="product-header">
        <p className="product-wordmark">OwnYourCode</p>
        <p className="eyebrow">Project intake</p>
        <h1>New Project</h1>
        <p>Validate a project idea or public repository before anything is saved.</p>
      </header>

      <form className="project-form glass-surface" id="project-setup" onSubmit={submitPreview}>
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

        <fieldset className="mode-selector">
          <legend>Project mode</legend>
          <label className="choice choice--segmented">
            <input type="radio" name="mode" value="new_idea" checked={mode === "new_idea"} onChange={() => selectMode("new_idea")} />
            <span>New idea</span>
          </label>
          <label className="choice choice--segmented">
            <input type="radio" name="mode" value="existing_repository" checked={mode === "existing_repository"} onChange={() => selectMode("existing_repository")} />
            <span>Existing repository</span>
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

        <div className="project-form__submit">
          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Validating..." : "Validate project"}
          </button>
          <p>Validation checks the supplied details only. It does not create or save a project.</p>
        </div>
      </form>

      <ErrorPanel title="Validation needs attention" messages={errors} />

      <LearningWorkspace
        preview={preview}
        inspection={inspection}
        lesson={lesson}
        learnerLevel={learnerLevel}
        learningGoal={learningGoal}
        isInspecting={isInspecting}
        inspectionErrors={inspectionErrors}
        isGeneratingLesson={isGeneratingLesson}
        lessonErrors={lessonErrors}
        onInspectRepository={inspectRepository}
        onLearnerLevelChange={changeLearnerLevel}
        onLearningGoalChange={setLearningGoal}
        onGenerateLesson={generateLesson}
      />

      <Link className="back-link" to="/">Back to home</Link>
    </main>
  );
}
