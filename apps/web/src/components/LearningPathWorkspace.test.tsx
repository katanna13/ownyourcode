import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { LearningPathResponse, LearningPathWorkspace } from "./LearningPathWorkspace";

const orientationActivity = {
  id: "orientation-evidence.v1",
  presentation_kind: "single_choice" as const,
  context_id: "a".repeat(64),
  prompt: "Which confirmed evidence item supports this repository-orientation activity?",
  evidence_ids: ["technology:fastapi"],
  choices: [
    { id: "technology:fastapi", label: "FastAPI" },
    { id: "repository:name", label: "Repository name" }
  ],
  starter_code: null,
  constraints: ["Select one item from confirmed evidence."],
  completion_role: "required_completion"
};

const multiPath: LearningPathResponse = {
  persisted: true,
  mode: "multi_module",
  path_id: "path-one",
  path_version: 1,
  source_evidence_fingerprint: "b".repeat(64),
  stale: false,
  limitations: ["The path uses bounded inspection evidence."],
  evidence_catalog: [{ id: "technology:fastapi", label: "FastAPI", detail: "Confirmed from pyproject.toml." }],
  modules: [{
    id: "module-one",
    position: 1,
    module_key: "repository-orientation.v1",
    category: "repository_orientation",
    title: "Orient yourself in confirmed evidence",
    objective: "Identify what bounded inspection confirms before making claims.",
    evidence_ids: ["technology:fastapi"],
    lesson_sections: ["The catalog contains bounded deterministic evidence."],
    activities: [orientationActivity],
    limitations: [],
    state: "available",
    required_remediation: false,
    remediation_activities: []
  }],
  resume_module_id: "module-one",
  summary: {
    modules_total: 1,
    modules_demonstrated: 0,
    practical_gates_passed: 0,
    required_remediations_open: 0,
    label: "Current project learning summary",
    disclaimer: "This is server-derived progress, not a certification."
  }
};

const noPath: LearningPathResponse = {
  ...multiPath,
  mode: "none",
  path_id: null,
  path_version: null,
  modules: [],
  resume_module_id: null,
  summary: null
};

function renderWorkspace(path: LearningPathResponse = multiPath, onPathChange = vi.fn()) {
  render(
    <AuthenticationTestProvider value={{
      isConfigured: true,
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => "current-token",
      signOut: async () => undefined,
      markSessionExpired: vi.fn()
    }}>
      <LearningPathWorkspace projectId="project-one" path={path} hasInspection onPathChange={onPathChange} />
    </AuthenticationTestProvider>
  );
  return onPathChange;
}

describe("LearningPathWorkspace", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "http://api.test"));
  afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

  it("creates a path only after a saved inspection and sends the selected learner inputs", async () => {
    const onPathChange = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(multiPath), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderWorkspace(noPath, onPathChange);

    fireEvent.change(screen.getByLabelText("Learner level"), { target: { value: "junior" } });
    fireEvent.change(screen.getByLabelText("Learning goal (optional)"), { target: { value: "Trace saved boundaries." } });
    fireEvent.click(screen.getByRole("button", { name: "Create saved learning path" }));

    await screen.findByRole("button", { name: "Create saved learning path" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/projects/project-one/learning-path",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ learner_level: "junior", learning_goal: "Trace saved boundaries." }) })
    );
    expect(onPathChange).toHaveBeenCalledWith(multiPath);
  });

  it("renders frozen public evidence and saves a deterministic activity without answer keys", async () => {
    const completed = { ...multiPath, modules: [{ ...multiPath.modules[0], state: "demonstrated" }], summary: { ...multiPath.summary!, modules_demonstrated: 1 } };
    const fetchMock = vi.fn((_: string, init?: RequestInit) => Promise.resolve(new Response(
      JSON.stringify(init?.method === "POST" ? { result: { passed: true, feedback: "Your selection matches the server-owned evidence-reading activity." }, module: completed.modules[0] } : completed),
      { status: 200 }
    )));
    vi.stubGlobal("fetch", fetchMock);
    const onPathChange = renderWorkspace();

    fireEvent.click(screen.getByLabelText("FastAPI"));
    fireEvent.click(screen.getByRole("button", { name: "Submit saved activity" }));

    expect(await screen.findByText(/Your selection matches/i)).toBeTruthy();
    expect(onPathChange).toHaveBeenCalledWith(completed);
    expect(screen.queryByText(/expected_choice_id/i)).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/projects/project-one/learning-path/modules/module-one/activities/orientation-evidence.v1/attempts",
      expect.objectContaining({ method: "POST" })
    );
  });
});
