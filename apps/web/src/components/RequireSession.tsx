import { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import { useAuthentication } from "../auth/ClerkProviderBoundary";

export function RequireSession({ children }: { children: ReactNode }) {
  const authentication = useAuthentication();
  const location = useLocation();
  const returnTo = `${location.pathname}${location.search}`;

  if (!authentication.isConfigured) {
    return (
      <main className="page auth-state">
        <h1>Saved projects are not configured</h1>
        <p>Authentication configuration is required before this protected area can open.</p>
        <Link className="button" to="/projects/new">Try the public demo</Link>
      </main>
    );
  }

  if (!authentication.isLoaded) {
    return (
      <main className="page auth-state" aria-live="polite">
        <p>Checking your session…</p>
      </main>
    );
  }

  if (!authentication.isSignedIn) {
    const message = authentication.sessionExpired
      ? "Your session expired. Sign in again to continue."
      : "Sign in to save and resume your projects.";
    return (
      <main className="page auth-state">
        <h1>Sign in to save projects</h1>
        <p>{message}</p>
        <div className="landing-hero__actions">
          <Link className="button" to={`/sign-in?returnTo=${encodeURIComponent(returnTo)}`}>Sign in</Link>
          <Link to="/projects/new">Try the public demo</Link>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
