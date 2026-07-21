import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { AuthenticationTestProvider } from "./auth/ClerkProviderBoundary";
import { AppShell } from "./components/AppShell";

describe("application routing", () => {
  it("renders the placeholder routes", () => {
    const newProject = render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", { name: "New Project" })
    ).toBeTruthy();

    newProject.unmount();

    render(
      <MemoryRouter initialEntries={["/projects/example-project"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", { name: "Project Workspace" })
    ).toBeTruthy();
    expect(screen.getByText("example-project")).toBeTruthy();
  });

  it("keeps the public demo accessible when no authentication provider is configured", () => {
    render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "New Project" })).toBeTruthy();
    expect(screen.queryByText("Sign in to save projects")).toBeNull();
  });

  it("renders a signed-out protected state instead of exposing an app route", () => {
    render(
      <AuthenticationTestProvider value={{ isConfigured: true, isLoaded: true, isSignedIn: false }}>
        <MemoryRouter initialEntries={["/app/projects"]}>
          <App />
        </MemoryRouter>
      </AuthenticationTestProvider>
    );

    expect(screen.getByRole("heading", { name: "Sign in to save projects" })).toBeTruthy();
  });

  it("signs out through the provider boundary without retaining a browser token", async () => {
    const signOut = vi.fn().mockResolvedValue(undefined);
    const markSessionExpired = vi.fn();
    render(
      <AuthenticationTestProvider value={{
        isConfigured: true,
        isLoaded: true,
        isSignedIn: true,
        getToken: async () => "current-token",
        signOut,
        markSessionExpired
      }}>
        <MemoryRouter><AppShell /></MemoryRouter>
      </AuthenticationTestProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(signOut).toHaveBeenCalledTimes(1));
    expect(markSessionExpired).toHaveBeenCalledTimes(1);
  });
});
