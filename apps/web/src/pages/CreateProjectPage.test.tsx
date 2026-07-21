import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { CreateProjectPage } from "./CreateProjectPage";

function renderCreatePage() {
  return render(
    <AuthenticationTestProvider value={{
      isConfigured: true,
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => "current-token",
      signOut: async () => undefined,
      markSessionExpired: vi.fn()
    }}>
      <MemoryRouter initialEntries={["/app/projects/new"]}>
        <Routes>
          <Route path="/app/projects/new" element={<CreateProjectPage />} />
          <Route path="/app/projects/:projectId" element={<p>Saved detail route</p>} />
        </Routes>
      </MemoryRouter>
    </AuthenticationTestProvider>
  );
}

function fillCommonFields() {
  fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "Learning API" } });
  fireEvent.change(screen.getByLabelText("Short description"), { target: { value: "Understand a public FastAPI project." } });
}

describe("CreateProjectPage", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "http://api.test"));
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("creates an Existing Repository project without inspecting GitHub", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "project-one" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    renderCreatePage();
    fillCommonFields();
    fireEvent.change(screen.getByLabelText("Public GitHub repository URL"), { target: { value: "https://github.com/example/learning-api" } });
    fireEvent.click(screen.getByRole("button", { name: "Save project" }));
    expect(await screen.findByText("Saved detail route")).toBeTruthy();
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(options.body))).toEqual({
      name: "Learning API",
      description: "Understand a public FastAPI project.",
      mode: "existing_repository",
      repository_url: "https://github.com/example/learning-api"
    });
  });

  it("creates a bounded New Idea project", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "project-idea" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    renderCreatePage();
    fillCommonFields();
    fireEvent.click(screen.getByLabelText("New Idea"));
    fireEvent.change(screen.getByLabelText("Problem"), { target: { value: "Learners need a better weekly study plan." } });
    fireEvent.change(screen.getByLabelText("Intended user"), { target: { value: "Independent learners" } });
    fireEvent.change(screen.getByLabelText("First outcome"), { target: { value: "Create a focused plan for the next session." } });
    fireEvent.change(screen.getByLabelText("Optional constraint"), { target: { value: "Keep it small" } });
    fireEvent.click(screen.getByRole("button", { name: "Add constraint" }));
    fireEvent.click(screen.getByRole("button", { name: "Save project" }));
    await screen.findByText("Saved detail route");
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(options.body))).toEqual({
      name: "Learning API",
      description: "Understand a public FastAPI project.",
      mode: "new_idea",
      idea_brief: {
        problem: "Learners need a better weekly study plan.",
        intended_user: "Independent learners",
        first_outcome: "Create a focused plan for the next session.",
        constraints: ["Keep it small"]
      }
    });
  });

  it("shows backend validation errors without pretending a project was created", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: "repository_url must be valid" }] }), { status: 422 })));
    renderCreatePage();
    fillCommonFields();
    fireEvent.change(screen.getByLabelText("Public GitHub repository URL"), { target: { value: "https://github.com/example/repository" } });
    fireEvent.click(screen.getByRole("button", { name: "Save project" }));
    expect(await screen.findByText("repository_url must be valid")).toBeTruthy();
    await waitFor(() => expect(screen.queryByText("Saved detail route")).toBeNull());
  });
});
