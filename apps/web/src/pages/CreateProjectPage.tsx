import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import {
  AuthenticationRequestError,
  apiBaseUrl,
  authenticatedFetch,
  responseMessages
} from "../auth/authenticatedFetch";
import { NewIdeaBrief, ProjectMode, SavedProject } from "../types/projects";

const EMPTY_IDEA_BRIEF: NewIdeaBrief = {
  problem: "",
  intended_user: "",
  first_outcome: "",
  constraints: []
};

export function CreateProjectPage() {
  const authentication = useAuthentication();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<ProjectMode>("existing_repository");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [ideaBrief, setIdeaBrief] = useState<NewIdeaBrief>(EMPTY_IDEA_BRIEF);
  const [constraintText, setConstraintText] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function selectMode(nextMode: ProjectMode) {
    setMode(nextMode);
    setErrors([]);
    if (nextMode === "new_idea") {
      setRepositoryUrl("");
    } else {
      setIdeaBrief(EMPTY_IDEA_BRIEF);
      setConstraintText("");
    }
  }

  function updateIdeaBrief(field: keyof Omit<NewIdeaBrief, "constraints">, value: string) {
    setIdeaBrief((current) => ({ ...current, [field]: value }));
    setErrors([]);
  }

  function addConstraint() {
    const nextConstraint = constraintText.trim();
    if (!nextConstraint || ideaBrief.constraints.length >= 5) {
      return;
    }
    setIdeaBrief((current) => ({ ...current, constraints: [...current.constraints, nextConstraint] }));
    setConstraintText("");
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setErrors(["The API URL is not configured."]);
      return;
    }

    const requestBody = {
      name,
      description,
      mode,
      ...(mode === "existing_repository"
        ? { repository_url: repositoryUrl }
        : { idea_brief: ideaBrief })
    };
    setIsSubmitting(true);
    setErrors([]);
    try {
      const response = await authenticatedFetch(`${baseUrl}/api/v1/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        getToken: authentication.getToken,
        onUnauthorized: authentication.markSessionExpired
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const messages = responseMessages(payload);
        setErrors(messages.length > 0 ? messages : ["The project could not be saved. Please try again."]);
        return;
      }
      navigate(`/app/projects/${(payload as SavedProject).id}`);
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) {
        setErrors(["The API could not be reached. Please try again."]);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="page page--onboarding">
      <header className="product-header">
        <p className="eyebrow">Saved project setup</p>
        <h1>Create project</h1>
        <p>This saves project details only. It does not inspect a repository or generate a learning path yet.</p>
      </header>

      <form className="project-form glass-surface" onSubmit={createProject}>
        <label className="field" htmlFor="saved-project-name">Project name
          <input id="saved-project-name" value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={100} required />
        </label>
        <label className="field" htmlFor="saved-project-description">Short description
          <textarea id="saved-project-description" value={description} onChange={(event) => setDescription(event.target.value)} minLength={10} maxLength={500} required />
        </label>
        <fieldset className="mode-selector">
          <legend>Project source</legend>
          <label className="choice choice--segmented"><input type="radio" name="saved-mode" checked={mode === "existing_repository"} onChange={() => selectMode("existing_repository")} /><span>Existing Repository</span></label>
          <label className="choice choice--segmented"><input type="radio" name="saved-mode" checked={mode === "new_idea"} onChange={() => selectMode("new_idea")} /><span>New Idea</span></label>
        </fieldset>

        {mode === "existing_repository" ? (
          <label className="field" htmlFor="saved-repository-url">Public GitHub repository URL
            <input id="saved-repository-url" type="url" value={repositoryUrl} onChange={(event) => setRepositoryUrl(event.target.value)} placeholder="https://github.com/owner/repository" required />
          </label>
        ) : (
          <section className="idea-brief" aria-labelledby="idea-brief-title">
            <h2 id="idea-brief-title">New Idea brief</h2>
            <label className="field" htmlFor="idea-problem">Problem
              <textarea id="idea-problem" value={ideaBrief.problem} onChange={(event) => updateIdeaBrief("problem", event.target.value)} minLength={10} maxLength={400} required />
            </label>
            <label className="field" htmlFor="idea-user">Intended user
              <input id="idea-user" value={ideaBrief.intended_user} onChange={(event) => updateIdeaBrief("intended_user", event.target.value)} minLength={2} maxLength={160} required />
            </label>
            <label className="field" htmlFor="idea-outcome">First outcome
              <textarea id="idea-outcome" value={ideaBrief.first_outcome} onChange={(event) => updateIdeaBrief("first_outcome", event.target.value)} minLength={10} maxLength={400} required />
            </label>
            <label className="field" htmlFor="idea-constraint">Optional constraint
              <input id="idea-constraint" value={constraintText} onChange={(event) => setConstraintText(event.target.value)} maxLength={160} />
            </label>
            <button className="button button--quiet" type="button" onClick={addConstraint} disabled={ideaBrief.constraints.length >= 5}>Add constraint</button>
            {ideaBrief.constraints.length > 0 && <ul>{ideaBrief.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>}
          </section>
        )}

        <button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving project…" : "Save project"}</button>
      </form>

      {errors.length > 0 && <section className="message message--error" role="alert"><h2>Project needs attention</h2><ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul></section>}
    </main>
  );
}
