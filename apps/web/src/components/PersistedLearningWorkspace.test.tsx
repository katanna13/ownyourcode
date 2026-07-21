import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { PersistedLearningWorkspace } from "./PersistedLearningWorkspace";

type Workspace = ComponentProps<typeof PersistedLearningWorkspace>["workspace"];

const inspectedWorkspace: Workspace = {
  active_snapshot: {
    version: 1,
    evidence_fingerprint: "evidence-fingerprint",
    inspection: {
      repository: {
        name: "learning-api",
        full_name: "example/learning-api",
        description: "A saved repository orientation.",
        html_url: "https://github.com/example/learning-api",
        default_branch: "main"
      },
      technologies: [{ key: "fastapi", label: "FastAPI", evidence: ["pyproject.toml"] }],
      important_files: [{ path: "pyproject.toml", kind: "manifest" }],
      limitations: []
    }
  },
  active_content: null,
  progress: {
    last_viewed_stage: "inspect",
    unlocked_stages: ["inspect", "learn"],
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

function renderWorkspace(workspace: Workspace = inspectedWorkspace) {
  const onWorkspaceChange = vi.fn();
  const onReload = vi.fn(async () => undefined);
  render(
    <AuthenticationTestProvider value={{
      isConfigured: true,
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => "current-token",
      signOut: async () => undefined,
      markSessionExpired: vi.fn()
    }}>
      <PersistedLearningWorkspace
        projectId="project-one"
        workspace={workspace}
        onWorkspaceChange={onWorkspaceChange}
        onReload={onReload}
      />
    </AuthenticationTestProvider>
  );
  return { onReload, onWorkspaceChange };
}

describe("PersistedLearningWorkspace inspection progression", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("marks inspection complete, unlocks Learn, and opens the saved lesson controls explicitly", async () => {
    const learnProgress = { ...inspectedWorkspace.progress, last_viewed_stage: "learn" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(learnProgress), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkspace();

    expect(screen.getByRole("button", { name: "Inspect: Complete" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Learn: Available" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Assess:/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Continue to Learn" })).toBeTruthy();
    expect(screen.queryByText(/Locked next:/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Continue to Learn" }));

    expect(await screen.findByRole("heading", { name: "Prepare the saved orientation" })).toBeTruthy();
    expect(screen.getByLabelText("Learner level")).toBeTruthy();
    expect(screen.getByLabelText("Learning goal (optional)")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Generate saved orientation" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/projects/project-one/workspace/progress",
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("restores the Learn stage after refresh when inspection is saved but content is not", async () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWorkspace({
      ...inspectedWorkspace,
      progress: { ...inspectedWorkspace.progress, last_viewed_stage: "learn" }
    });

    expect(await screen.findByRole("heading", { name: "Prepare the saved orientation" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Inspect: Complete" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Learn: Available" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Assess:/ })).toBeNull();
  });

  it("keeps Learn locked when no persisted inspection exists", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWorkspace({
      ...inspectedWorkspace,
      active_snapshot: null,
      progress: { ...inspectedWorkspace.progress, unlocked_stages: ["inspect"] }
    });

    expect(screen.getByRole("button", { name: "Inspect: Available" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Learn:/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Continue to Learn" })).toBeNull();
  });
});
