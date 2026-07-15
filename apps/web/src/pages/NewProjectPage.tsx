import { Link } from "react-router-dom";

export function NewProjectPage() {
  return (
    <main className="page">
      <p className="eyebrow">Phase 1</p>
      <h1>New Project</h1>
      <p>
        Project creation will be introduced after an authenticated ownership
        model is in place. This page is intentionally a placeholder.
      </p>
      <Link to="/">Back to home</Link>
    </main>
  );
}
