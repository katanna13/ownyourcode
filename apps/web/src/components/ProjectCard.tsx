import { Link } from "react-router-dom";

import { SavedProject } from "../types/projects";

function repositoryLabel(repositoryUrl: string): string {
  return repositoryUrl.replace(/^https:\/\/github\.com\//i, "");
}

export function ProjectCard({
  project,
  onArchive
}: {
  project: SavedProject;
  onArchive: (project: SavedProject) => void;
}) {
  const sourceLabel = project.mode === "existing_repository"
    ? repositoryLabel(project.source.repository_url ?? "Public repository")
    : project.source.idea_brief?.problem ?? "New idea";

  return (
    <article className="project-card glass-surface">
      <p className="eyebrow">{project.mode === "existing_repository" ? "Existing Repository" : "New Idea"}</p>
      <h2>{project.name}</h2>
      <p>{project.description}</p>
      <p><strong>Source:</strong> {sourceLabel}</p>
      <p><strong>Last activity:</strong> <time dateTime={project.last_activity_at}>{new Date(project.last_activity_at).toLocaleString()}</time></p>
      <div className="project-card__actions">
        <Link className="button" to={`/app/projects/${project.id}`}>Open project</Link>
        <button
          className="button button--quiet"
          type="button"
          aria-label={`Archive project ${project.name}`}
          onClick={() => onArchive(project)}
        >
          Archive project
        </button>
      </div>
    </article>
  );
}
