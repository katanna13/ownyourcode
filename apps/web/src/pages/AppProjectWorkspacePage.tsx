import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import {
  AuthenticationRequestError,
  apiBaseUrl,
  authenticatedFetch,
  responseMessages
} from "../auth/authenticatedFetch";
import { PersistedLearningWorkspace } from "../components/PersistedLearningWorkspace";
import { SavedProject } from "../types/projects";

type SavedWorkspace = React.ComponentProps<typeof PersistedLearningWorkspace>["workspace"];

export function AppProjectWorkspacePage() {
  const { projectId } = useParams();
  const authentication = useAuthentication();
  const [project, setProject] = useState<SavedProject | null>(null);
  const [workspace, setWorkspace] = useState<SavedWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      setError("The requested project could not be found.");
      return;
    }
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setError("The API URL is not configured.");
      return;
    }
    let cancelled = false;
    async function loadProject() {
      setProject(null);
      setError(null);
      try {
        const response = await authenticatedFetch(`${baseUrl}/api/v1/projects/${projectId}`, {
          getToken: authentication.getToken,
          onUnauthorized: authentication.markSessionExpired
        });
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          if (!cancelled) {
            setError(responseMessages(payload)[0] ?? "The project could not be loaded.");
          }
          return;
        }
        if (!cancelled) {
          setProject(payload as SavedProject);
        }
      } catch (requestError) {
        if (!cancelled && !(requestError instanceof AuthenticationRequestError)) {
          setError("The API could not be reached. Please try again.");
        }
      }
    }
    void loadProject();
    return () => {
      cancelled = true;
    };
  }, [authentication.getToken, authentication.markSessionExpired, projectId]);

  async function reloadWorkspace() {
    if (!projectId) return;
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setError("The API URL is not configured.");
      return;
    }
    try {
      const response = await authenticatedFetch(`${baseUrl}/api/v1/projects/${projectId}/workspace`, {
        getToken: authentication.getToken,
        onUnauthorized: authentication.markSessionExpired
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(responseMessages(payload)[0] ?? "The saved workspace could not be loaded.");
        return;
      }
      setWorkspace(payload as SavedWorkspace);
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) setError("The API could not be reached. Please try again.");
    }
  }

  useEffect(() => {
    if (project?.mode === "existing_repository") {
      void reloadWorkspace();
    } else {
      setWorkspace(null);
    }
  }, [project?.id, project?.mode]);

  return (
    <main className="page page--workspace-foundation">
      {!project && !error && <p role="status">Loading saved project…</p>}
      {error && <section className="message message--error" role="alert"><h1>Project needs attention</h1><p>{error}</p><Link to="/app/projects">Back to projects</Link></section>}
      {project && (
        <section className="workspace-foundation glass-surface">
          <p className="eyebrow">{project.mode === "existing_repository" ? "Existing Repository" : "New Idea"}</p>
          <h1>{project.name}</h1>
          <p>{project.description}</p>
          {project.source.repository_url ? (
            <p><strong>Repository:</strong> <a href={project.source.repository_url} target="_blank" rel="noreferrer">{project.source.repository_url}</a></p>
          ) : (
            <section aria-labelledby="saved-idea-title">
              <h2 id="saved-idea-title">Idea summary</h2>
              <p><strong>Problem:</strong> {project.source.idea_brief?.problem}</p>
              <p><strong>For:</strong> {project.source.idea_brief?.intended_user}</p>
              <p><strong>First outcome:</strong> {project.source.idea_brief?.first_outcome}</p>
            </section>
          )}
          <dl>
            <dt>Created</dt><dd><time dateTime={project.created_at}>{new Date(project.created_at).toLocaleString()}</time></dd>
            <dt>Last activity</dt><dd><time dateTime={project.last_activity_at}>{new Date(project.last_activity_at).toLocaleString()}</time></dd>
          </dl>
          {project.mode === "new_idea" && (
            <p className="workspace-foundation__notice">Build From Scratch learning workspaces are planned for a later phase. This saved idea has no fake learning workflow.</p>
          )}
          {project.mode === "existing_repository" && !workspace && <p role="status">Loading saved learning workspace…</p>}
          {project.mode === "existing_repository" && workspace && (
            <PersistedLearningWorkspace
              projectId={project.id}
              workspace={workspace}
              onWorkspaceChange={(progress) => setWorkspace((current) => current ? { ...current, progress } : current)}
              onReload={reloadWorkspace}
            />
          )}
          <Link to="/app/projects">Back to projects</Link>
        </section>
      )}
    </main>
  );
}
