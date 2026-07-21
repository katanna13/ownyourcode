import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { AppProjectWorkspacePage } from "./AppProjectWorkspacePage";

const project = {
  id: "project-one",
  name: "Learning API",
  description: "Understand a public API project.",
  mode: "existing_repository",
  status: "active",
  created_at: "2026-07-16T10:00:00Z",
  updated_at: "2026-07-16T10:00:00Z",
  last_activity_at: "2026-07-16T10:05:00Z",
  source: { mode: "existing_repository", repository_url: "https://github.com/example/learning-api", idea_brief: null }
};

const workspace = {
  persisted: true,
  active_snapshot: null,
  active_content: null,
  progress: {
    last_viewed_stage: "inspect",
    unlocked_stages: ["inspect"],
    assessment_attempt_id: null,
    verified_lab_attempt_id: null,
    security_challenge_attempt_id: null,
    oral_defense_attempt_id: null,
    summary: {
      assessment_points: null,
      verified_lab_passed: false,
      security_challenge_passed: false,
      oral_defense_points: null,
      raw_total: 0,
      rounded_total: 0,
      label: "Current project learning summary",
      disclaimer: "Saved attempts are not a certification."
    }
  }
};

function renderDetail() {
  return render(
    <AuthenticationTestProvider value={{
      isConfigured: true,
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => "current-token",
      signOut: async () => undefined,
      markSessionExpired: vi.fn()
    }}>
      <MemoryRouter initialEntries={["/app/projects/project-one"]}>
        <Routes><Route path="/app/projects/:projectId" element={<AppProjectWorkspacePage />} /></Routes>
      </MemoryRouter>
    </AuthenticationTestProvider>
  );
}

describe("AppProjectWorkspacePage", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "http://api.test"));
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("loads the owner-scoped workspace and starts with an explicit inspection action", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(
      JSON.stringify(url.endsWith("/workspace") ? workspace : project),
      { status: 200 }
    ))));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Learning API" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Inspect repository" })).toBeTruthy();
    expect(screen.getByText(/Stages and completed attempts are saved/i)).toBeTruthy();
    expect(screen.queryByText(/Preview Ownership Score/i)).toBeNull();
  });

  it("keeps a saved New Idea truthful without rendering a repository workflow", async () => {
    const ideaProject = {
      ...project,
      mode: "new_idea",
      source: {
        mode: "new_idea",
        repository_url: null,
        idea_brief: {
          problem: "Help learners plan one small product idea.",
          intended_user: "Learners",
          first_outcome: "A bounded first step.",
          constraints: []
        }
      }
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(ideaProject), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    expect(await screen.findByText(/Build From Scratch learning workspaces are planned/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Inspect repository" })).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
