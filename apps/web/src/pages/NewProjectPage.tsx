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
  paths: {
    inspected_count: number;
    returned: string[];
    truncated: boolean;
  };
  important_files: Array<{ path: string; kind: string }>;
  limitations: string[];
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

  function selectMode(nextMode: ProjectMode) {
    setMode(nextMode);
    setErrors([]);
    setInspectionErrors([]);
    setInspection(null);

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

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "");
    if (!apiBaseUrl) {
      setInspectionErrors(["The API URL is not configured."]);
      setIsInspecting(false);
      return;
    }

    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/repositories/inspect`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
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

          {preview.project.mode === "existing_repository" &&
            preview.project.repository_url && (
              <button
                className="button"
                type="button"
                onClick={inspectRepository}
                disabled={isInspecting}
              >
                {isInspecting ? "Inspecting repository…" : "Inspect repository"}
              </button>
            )}
        </section>
      )}

      {inspectionErrors.length > 0 && (
        <section className="message message--error" role="alert">
          <h2>Repository inspection could not finish</h2>
          <ul>
            {inspectionErrors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </section>
      )}

      {inspection && (
        <section className="message message--success inspection" role="status">
          <h2>Repository inspection</h2>
          <p>{inspection.message}</p>
          <dl>
            <dt>Repository</dt>
            <dd>
              <a href={inspection.repository.html_url}>{inspection.repository.full_name}</a>
            </dd>
            <dt>Default branch</dt>
            <dd>{inspection.repository.default_branch}</dd>
            <dt>Primary language</dt>
            <dd>{inspection.repository.primary_language ?? "Not reported"}</dd>
          </dl>

          <h3>Languages</h3>
          <ul>
            {inspection.languages.map((language) => (
              <li key={language.name}>
                {language.name}: {language.bytes} bytes
              </li>
            ))}
          </ul>

          <h3>Detected technologies</h3>
          <ul>
            {inspection.technologies.map((technology) => (
              <li key={technology.key}>
                <strong>{technology.label}</strong>
                <ul>
                  {technology.evidence.map((evidence) => (
                    <li key={evidence}>{evidence}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>

          <h3>Important files</h3>
          <ul>
            {inspection.important_files.map((file) => (
              <li key={file.path}>
                {file.path} ({file.kind})
              </li>
            ))}
          </ul>

          <h3>Path coverage</h3>
          <p>
            Inspected {inspection.paths.inspected_count} paths
            {inspection.paths.truncated ? "; path results were truncated." : "."}
          </p>

          <h3>Limitations</h3>
          <ul>
            {inspection.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </section>
      )}

      <Link to="/">Back to home</Link>
    </main>
  );
}
