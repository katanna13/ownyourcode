import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import {
  AuthenticationRequestError,
  apiBaseUrl,
  authenticatedFetch,
  responseMessages
} from "../auth/authenticatedFetch";
import { ProjectCard } from "../components/ProjectCard";
import { ProjectListResponse, SavedProject } from "../types/projects";

export function ProjectsDashboardPage() {
  const authentication = useAuthentication();
  const [projects, setProjects] = useState<ProjectListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [projectToArchive, setProjectToArchive] = useState<SavedProject | null>(null);
  const [isArchiving, setIsArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const cancelArchiveRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (projectToArchive) {
      cancelArchiveRef.current?.focus();
    }
  }, [projectToArchive]);

  useEffect(() => {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setError("The API URL is not configured.");
      return;
    }
    let cancelled = false;

    async function loadProjects() {
      setError(null);
      setProjects(null);
      try {
        const response = await authenticatedFetch(`${baseUrl}/api/v1/projects`, {
          getToken: authentication.getToken,
          onUnauthorized: authentication.markSessionExpired
        });
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          if (!cancelled) {
            const messages = responseMessages(payload);
            setError(messages[0] ?? "Saved projects could not be loaded. Please try again.");
          }
          return;
        }
        if (!cancelled) {
          setProjects(payload as ProjectListResponse);
        }
      } catch (requestError) {
        if (!cancelled && !(requestError instanceof AuthenticationRequestError)) {
          setError("The API could not be reached. Please try again.");
        }
      }
    }

    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, [authentication.getToken, authentication.markSessionExpired]);

  async function archiveProject() {
    if (!projectToArchive || isArchiving) {
      return;
    }
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      setArchiveError("The API URL is not configured.");
      return;
    }
    setIsArchiving(true);
    setArchiveError(null);
    try {
      const response = await authenticatedFetch(
        `${baseUrl}/api/v1/projects/${projectToArchive.id}`,
        {
          method: "DELETE",
          getToken: authentication.getToken,
          onUnauthorized: authentication.markSessionExpired
        }
      );
      if (!response.ok) {
        const payload: unknown = await response.json().catch(() => null);
        const messages = responseMessages(payload);
        setArchiveError(messages[0] ?? "The project could not be archived. Please try again.");
        return;
      }
      setProjects((current) => current
        ? { ...current, items: current.items.filter((project) => project.id !== projectToArchive.id) }
        : current
      );
      setProjectToArchive(null);
    } catch (requestError) {
      if (!(requestError instanceof AuthenticationRequestError)) {
        setArchiveError("The API could not be reached. Please try again.");
      }
    } finally {
      setIsArchiving(false);
    }
  }

  return (
    <main className="page page--dashboard">
      <header className="product-header">
        <p className="eyebrow">Your saved work</p>
        <h1>Projects</h1>
        <p>Saved project foundations are ready. Existing Repository learning workspaces can be resumed here.</p>
        <Link className="button" to="/app/projects/new">Create project</Link>
      </header>

      {!projects && !error && <p role="status">Loading saved projects…</p>}
      {error && <section className="message message--error" role="alert"><h2>Projects need attention</h2><p>{error}</p></section>}
      {projects?.items.length === 0 && (
        <section className="empty-projects glass-surface">
          <h2>Create your first saved project</h2>
          <p>Save a public repository or a bounded New Idea brief, then return to it later.</p>
          <Link className="button" to="/app/projects/new">Create project</Link>
        </section>
      )}
      {projects && projects.items.length > 0 && (
        <section className="project-card-grid" aria-label="Saved projects">
          {projects.items.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onArchive={(selectedProject) => {
                setArchiveError(null);
                setProjectToArchive(selectedProject);
              }}
            />
          ))}
        </section>
      )}
      {projectToArchive && (
        <section
          className="archive-dialog message"
          role="dialog"
          aria-modal="true"
          aria-labelledby="archive-project-title"
          aria-describedby="archive-project-description"
        >
          <h2 id="archive-project-title">Archive project?</h2>
          <p id="archive-project-description">
            Archive <strong>{projectToArchive.name}</strong>? It will be removed from your active projects and can no longer be opened here.
          </p>
          {archiveError && <p className="message--error" role="alert">{archiveError}</p>}
          <div className="project-card__actions">
            <button ref={cancelArchiveRef} className="button button--quiet" type="button" disabled={isArchiving} onClick={() => setProjectToArchive(null)}>Cancel</button>
            <button className="button" type="button" disabled={isArchiving} onClick={archiveProject}>
              {isArchiving ? "Archiving project..." : "Archive project"}
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
