import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

type ProjectMode = "existing_repository" | "new_idea";

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

function validationMessages(payload: unknown): string[] {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return [];
  }

  const { detail } = payload;
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

export function NewProjectPage() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<ProjectMode>("new_idea");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [preview, setPreview] = useState<ProjectPreviewResponse | null>(null);

  function selectMode(nextMode: ProjectMode) {
    setMode(nextMode);
    setErrors([]);

    if (nextMode === "new_idea") {
      setRepositoryUrl("");
    }
  }

  async function submitPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrors([]);
    setPreview(null);

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "");
    if (!apiBaseUrl) {
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
      const response = await fetch(`${apiBaseUrl}/api/v1/projects/preview`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(requestBody)
      });
      const payload: unknown = await response.json().catch(() => null);

      if (!response.ok) {
        const messages = validationMessages(payload);
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

  return (
    <main className="page">
      <p className="eyebrow">Project intake</p>
      <h1>New Project</h1>
      <p>
        Validate a project idea or public repository before anything is saved.
      </p>

      <form className="project-form" onSubmit={submitPreview}>
        <label className="field" htmlFor="project-name">
          Project name
          <input
            id="project-name"
            name="name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setErrors([]);
            }}
            minLength={2}
            maxLength={100}
            required
          />
        </label>

        <label className="field" htmlFor="project-description">
          Short description
          <textarea
            id="project-description"
            name="description"
            value={description}
            onChange={(event) => {
              setDescription(event.target.value);
              setErrors([]);
            }}
            minLength={10}
            maxLength={500}
            required
          />
        </label>

        <fieldset>
          <legend>Project mode</legend>
          <label className="choice">
            <input
              type="radio"
              name="mode"
              value="new_idea"
              checked={mode === "new_idea"}
              onChange={() => selectMode("new_idea")}
            />
            New idea
          </label>
          <label className="choice">
            <input
              type="radio"
              name="mode"
              value="existing_repository"
              checked={mode === "existing_repository"}
              onChange={() => selectMode("existing_repository")}
            />
            Existing repository
          </label>
        </fieldset>

        {mode === "existing_repository" && (
          <label className="field" htmlFor="repository-url">
            Public GitHub repository URL
            <input
              id="repository-url"
              name="repository_url"
              type="url"
              value={repositoryUrl}
              onChange={(event) => {
                setRepositoryUrl(event.target.value);
                setErrors([]);
              }}
              placeholder="https://github.com/owner/repository"
              required
            />
          </label>
        )}

        <button className="button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Validating…" : "Validate project"}
        </button>
      </form>

      {errors.length > 0 && (
        <section className="message message--error" role="alert">
          <h2>Validation needs attention</h2>
          <ul>
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </section>
      )}

      {preview && (
        <section className="message message--success" role="status">
          <h2>Validated preview</h2>
          <p>{preview.message}</p>
          <dl>
            <dt>Name</dt>
            <dd>{preview.project.name}</dd>
            <dt>Mode</dt>
            <dd>{preview.project.mode}</dd>
            {preview.project.repository_url && (
              <>
                <dt>Repository URL</dt>
                <dd>{preview.project.repository_url}</dd>
              </>
            )}
          </dl>
        </section>
      )}

      <Link to="/">Back to home</Link>
    </main>
  );
}
