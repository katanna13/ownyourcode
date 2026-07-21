import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { ProjectsDashboardPage } from "./ProjectsDashboardPage";

const project = {
  id: "b5f41a81-efcd-4f3e-8d32-65f2c54d7f8d",
  name: "Learning API",
  description: "Understand a public API project.",
  mode: "existing_repository",
  status: "active",
  created_at: "2026-07-16T10:00:00Z",
  updated_at: "2026-07-16T10:00:00Z",
  last_activity_at: "2026-07-16T10:05:00Z",
  source: { mode: "existing_repository", repository_url: "https://github.com/example/learning-api", idea_brief: null }
};

function renderDashboard() {
  return render(
    <AuthenticationTestProvider value={{
      isConfigured: true,
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => "current-token",
      signOut: async () => undefined,
      markSessionExpired: vi.fn()
    }}>
      <MemoryRouter><ProjectsDashboardPage /></MemoryRouter>
    </AuthenticationTestProvider>
  );
}

describe("ProjectsDashboardPage", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("shows a loading state, then a truthful empty first-project state", async () => {
    let resolveResponse: (response: Response) => void;
    const fetchMock = vi.fn(() => new Promise<Response>((resolve) => { resolveResponse = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    renderDashboard();
    expect(screen.getByText("Loading saved projects…")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    resolveResponse!(new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 }));
    expect(await screen.findByRole("heading", { name: "Create your first saved project" })).toBeTruthy();
  });

  it("renders stored cards only and sends a fresh bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [project], next_cursor: null }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderDashboard();
    expect(await screen.findByRole("heading", { name: "Learning API" })).toBeTruthy();
    expect(screen.getByText("example/learning-api")).toBeTruthy();
    expect(screen.queryByText(/Ownership Score/i)).toBeNull();
    expect(screen.queryByText(/completion/i)).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test/api/v1/projects");
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer current-token");
  });

  it("shows a safe API error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Project list unavailable." }), { status: 500 })));
    renderDashboard();
    expect(await screen.findByText("Project list unavailable.")).toBeTruthy();
  });

  it("confirms before archiving and removes only the archived project", async () => {
    const secondProject = { ...project, id: "second-project", name: "Second project" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [project, secondProject], next_cursor: null }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    renderDashboard();
    await screen.findByRole("heading", { name: "Learning API" });

    fireEvent.click(screen.getByRole("button", { name: "Archive project Learning API" }));
    expect(screen.getByRole("dialog").textContent).toContain("Archive Learning API?");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Archive project Learning API" }));
    fireEvent.click(screen.getByRole("button", { name: "Archive project" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [url, options] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe(`http://api.test/api/v1/projects/${project.id}`);
    expect(options.method).toBe("DELETE");
    expect(screen.queryByRole("heading", { name: "Learning API" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Second project" })).toBeTruthy();
  });

  it("keeps the card visible and reports a safe error when archive fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [project], next_cursor: null }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Archive unavailable." }), { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);
    renderDashboard();
    await screen.findByRole("heading", { name: "Learning API" });
    fireEvent.click(screen.getByRole("button", { name: "Archive project Learning API" }));
    fireEvent.click(screen.getByRole("button", { name: "Archive project" }));
    expect(await screen.findByText("Archive unavailable.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Learning API" })).toBeTruthy();
  });

  it("shows the empty state after the final active project is archived", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [project], next_cursor: null }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    renderDashboard();
    await screen.findByRole("heading", { name: "Learning API" });
    fireEvent.click(screen.getByRole("button", { name: "Archive project Learning API" }));
    fireEvent.click(screen.getByRole("button", { name: "Archive project" }));
    expect(await screen.findByRole("heading", { name: "Create your first saved project" })).toBeTruthy();
  });
});
