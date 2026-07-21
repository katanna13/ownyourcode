import { SignIn } from "@clerk/react";
import { Link, useSearchParams } from "react-router-dom";

import { useAuthentication } from "../auth/ClerkProviderBoundary";
import { safeApplicationReturnPath } from "../auth/returnPath";

export function SignInPage() {
  const authentication = useAuthentication();
  const [searchParams] = useSearchParams();
  const returnTo = safeApplicationReturnPath(searchParams.get("returnTo"));

  if (!authentication.isConfigured) {
    return (
      <main className="page auth-state">
        <h1>Sign-in is not configured</h1>
        <p>This local environment has no public Clerk configuration.</p>
        <Link className="button" to="/projects/new">Try the public demo</Link>
      </main>
    );
  }

  return (
    <main className="page auth-state">
      <p className="eyebrow">Saved OwnYourCode projects</p>
      <h1>Sign in</h1>
      <SignIn forceRedirectUrl={returnTo} fallbackRedirectUrl="/app/projects" />
    </main>
  );
}
