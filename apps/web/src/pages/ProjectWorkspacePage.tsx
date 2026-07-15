import { Link, useParams } from "react-router-dom";

export function ProjectWorkspacePage() {
  const { projectId } = useParams();

  return (
    <main className="page">
      <p className="eyebrow">Phase 1</p>
      <h1>Project Workspace</h1>
      <p>
        Workspace route requested for <code>{projectId}</code>. Project data is
        not loaded or stored in this foundation.
      </p>
      <Link to="/">Back to home</Link>
    </main>
  );
}
