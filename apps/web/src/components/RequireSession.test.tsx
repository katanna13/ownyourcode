import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { RequireSession } from "./RequireSession";

function renderGuard(value: Parameters<typeof AuthenticationTestProvider>[0]["value"]) {
  return render(
    <AuthenticationTestProvider value={value}>
      <MemoryRouter initialEntries={["/app/projects/example"]}>
        <RequireSession><p>Protected content</p></RequireSession>
      </MemoryRouter>
    </AuthenticationTestProvider>
  );
}

describe("RequireSession", () => {
  it("distinguishes configuration loading, signed-out, expired, and authenticated states", () => {
    const loading = renderGuard({ isConfigured: true, isLoaded: false });
    expect(screen.getByText("Checking your session…")).toBeTruthy();
    loading.unmount();

    const signedOut = renderGuard({ isConfigured: true, isLoaded: true, isSignedIn: false });
    expect(screen.getByRole("heading", { name: "Sign in to save projects" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign in" }).getAttribute("href")).toContain("returnTo=%2Fapp%2Fprojects%2Fexample");
    signedOut.unmount();

    const expired = renderGuard({ isConfigured: true, isLoaded: true, isSignedIn: false, sessionExpired: true });
    expect(screen.getByText("Your session expired. Sign in again to continue.")).toBeTruthy();
    expired.unmount();

    renderGuard({
      isConfigured: true,
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => "current-token",
      signOut: async () => undefined,
      markSessionExpired: vi.fn()
    });
    expect(screen.getByText("Protected content")).toBeTruthy();
  });

  it("fails closed when protected authentication configuration is absent while offering the public demo", () => {
    renderGuard({ isConfigured: false });
    expect(screen.getByRole("heading", { name: "Saved projects are not configured" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Try the public demo" }).getAttribute("href")).toBe("/projects/new");
  });
});
