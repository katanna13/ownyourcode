import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuthentication } from "../auth/ClerkProviderBoundary";

export function AppShell() {
  const { markSessionExpired, signOut } = useAuthentication();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    markSessionExpired();
    navigate("/", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="app-shell__header glass-surface">
        <Link className="product-wordmark" to="/app/projects">OwnYourCode</Link>
        <nav aria-label="Saved project navigation">
          <Link to="/app/projects">Projects</Link>
          <Link to="/app/projects/new">Create project</Link>
          <button className="button button--quiet" type="button" onClick={handleSignOut}>Sign out</button>
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
