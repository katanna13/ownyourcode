import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { LearningPathResponse, LearningPathWorkspace } from "./LearningPathWorkspace";

type PathModule = LearningPathResponse["modules"][number];
type AttemptReview = PathModule["attempt_reviews"][number];

const orientationActivity = {
  id: "orientation-evidence.v1",
  presentation_kind: "single_choice" as const,
  context_id: "a".repeat(64),
  prompt: "Which confirmed evidence item supports this repository-orientation activity?",
  evidence_ids: ["technology:fastapi", "repository:name"],
  choices: [
    { id: "technology:fastapi", label: "FastAPI" },
    { id: "repository:name", label: "Repository name" }
  ],
  starter_code: null,
  constraints: ["Select one item from confirmed evidence."],
  completion_role: "required_completion"
};

const orientationReview: AttemptReview = {
  attempt_id: "attempt-orientation",
  activity_id: orientationActivity.id,
  passed: true,
  your_answer: "FastAPI (technology:fastapi)",
  expected_answer: "FastAPI (technology:fastapi)",
  why_expected_answer: "FastAPI is the frozen evidence item that directly supports this claim.",
  project_teaching: "Use the most direct confirmed repository evidence before drawing broader conclusions.",
  evidence_ids: ["technology:fastapi"],
  option_feedback: [
    { id: "technology:fastapi", label: "FastAPI", explanation: "This directly supports the claim.", selected: true, expected: true },
    { id: "repository:name", label: "Repository name", explanation: "This is weaker for the framework claim.", selected: false, expected: false }
  ],
  transition_explanations: [],
  checks: [],
  can_retry: false,
  example_solution: null
};

const modules: PathModule[] = [
  {
    id: "module-one",
    position: 1,
    module_key: "repository-orientation.v1",
    category: "repository_orientation",
    title: "Orient yourself in confirmed repository evidence",
    objective: "Identify what bounded inspection confirms before making claims.",
    evidence_ids: ["technology:fastapi"],
    lesson_sections: ["The catalog contains bounded deterministic evidence."],
    activities: [orientationActivity],
    limitations: [],
    state: "available",
    required_remediation: false,
    remediation_activities: [],
    attempt_reviews: []
  },
  {
    id: "module-two",
    position: 2,
    module_key: "architecture-boundaries.v1",
    category: "architecture_boundaries",
    title: "Trace responsibilities across confirmed application boundaries",
    objective: "Trace the illustrative request flow through confirmed boundary categories.",
    evidence_ids: ["technology:react", "technology:fastapi"],
    lesson_sections: ["Confirmed technologies identify boundaries, while the ordered flow remains illustrative."],
    activities: [{
      id: "architecture-ordering.v1",
      presentation_kind: "step_order",
      context_id: "b".repeat(64),
      prompt: "Order the teaching flow from browser action to response.",
      evidence_ids: ["technology:react", "technology:fastapi"],
      choices: [
        { id: "activity:api", label: "API validates" },
        { id: "activity:response", label: "Response returns" },
        { id: "activity:browser", label: "Browser action" }
      ],
      starter_code: null,
      constraints: ["Use every step once."],
      completion_role: "required_gate"
    }],
    limitations: [],
    state: "locked",
    required_remediation: false,
    remediation_activities: [],
    attempt_reviews: []
  },
  {
    id: "module-three",
    position: 3,
    module_key: "validation-failure-paths.v1",
    category: "validation_failure_paths",
    title: "Verify a bounded FastAPI-style response",
    objective: "Practice validating a small server-owned teaching fixture.",
    evidence_ids: ["language:python", "technology:fastapi"],
    lesson_sections: ["The fixture is parsed structurally and never executed."],
    activities: [{
      id: "fastapi-health-fixture.v1",
      presentation_kind: "code_fixture",
      context_id: "c".repeat(64),
      prompt: "Update the healthz teaching fixture.",
      evidence_ids: ["language:python", "technology:fastapi"],
      choices: [],
      starter_code: 'def healthz():\n    return {"status": "ok"}\n',
      constraints: ["Teaching fixture, not repository source."],
      completion_role: "required_gate"
    }],
    limitations: [],
    state: "locked",
    required_remediation: false,
    remediation_activities: [],
    attempt_reviews: []
  }
];

const multiPath: LearningPathResponse = {
  persisted: true,
  mode: "multi_module",
  path_id: "path-one",
  path_version: 1,
  source_evidence_fingerprint: "d".repeat(64),
  stale: false,
  limitations: ["The path uses bounded inspection evidence."],
  evidence_catalog: [
    { id: "technology:fastapi", label: "FastAPI", detail: "Confirmed from pyproject.toml." },
    { id: "technology:react", label: "React", detail: "Confirmed from package.json." },
    { id: "language:python", label: "Python", detail: "Reported by GitHub languages." },
    { id: "repository:name", label: "Repository name", detail: "Confirmed repository metadata." }
  ],
  modules,
  resume_module_id: "module-one",
  summary: {
    modules_total: 3,
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

function defaultViewResponse() {
  return new Response(JSON.stringify(modules[0]), { status: 200 });
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

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/projects/project-one/learning-path",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ learner_level: "junior", learning_goal: "Trace saved boundaries." }) })
    ));
    expect(onPathChange).toHaveBeenCalledWith(multiPath);
  });

  it("opens the first available incomplete module when Continue learning is selected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(defaultViewResponse()));
    const path = {
      ...multiPath,
      resume_module_id: "module-one",
      modules: [
        { ...modules[0], state: "demonstrated" as const, attempt_reviews: [orientationReview] },
        { ...modules[1], state: "available" as const },
        modules[2]
      ]
    };
    renderWorkspace(path);

    expect(screen.getByRole("heading", { name: modules[1].title })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Keep learning one saved lesson at a time" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Continue learning" }));
    expect(await screen.findByRole("heading", { name: modules[1].title })).toBeTruthy();
  });

  it("revisits a demonstrated module with frozen content and its saved attempt review", async () => {
    const fetchMock = vi.fn().mockResolvedValue(defaultViewResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWorkspace({
      ...multiPath,
      modules: [
        { ...modules[0], state: "demonstrated", attempt_reviews: [orientationReview] },
        { ...modules[1], state: "available" },
        modules[2]
      ],
      resume_module_id: "module-two"
    });

    fireEvent.click(screen.getByRole("button", { name: /Module 1: Orient yourself.*Demonstrated/i }));
    expect(await screen.findByRole("heading", { name: modules[0].title })).toBeTruthy();
    expect(screen.getByText("Correct or expected answer")).toBeTruthy();
    expect(screen.getAllByText(orientationReview.expected_answer)).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/projects/project-one/learning-path/modules/module-one/view",
      expect.objectContaining({ method: "PATCH" })
    );
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit | undefined)?.method !== "POST")).toBe(true);
  });

  it("uses a prominent next-module action after completion", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(defaultViewResponse()));
    renderWorkspace({
      ...multiPath,
      modules: [
        { ...modules[0], state: "demonstrated", attempt_reviews: [orientationReview] },
        { ...modules[1], state: "available" },
        modules[2]
      ],
      resume_module_id: "module-two"
    });
    fireEvent.click(screen.getByRole("button", { name: /Module 1: Orient yourself.*Demonstrated/i }));
    const continueButton = await screen.findByRole("button", { name: "Next available module: Continue to Module 2" });
    fireEvent.click(continueButton);
    expect(await screen.findByRole("heading", { name: modules[1].title })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Previous module" })).toBeTruthy();
  });

  it("keeps expected answers hidden before submission and reveals structured teaching feedback afterward", async () => {
    const failedReview: AttemptReview = {
      ...orientationReview,
      attempt_id: "attempt-failed",
      passed: false,
      your_answer: "Repository name (repository:name)",
      can_retry: true,
      option_feedback: orientationReview.option_feedback.map((item) => ({ ...item, selected: item.id === "repository:name" }))
    };
    const fetchMock = vi.fn((_: string, init?: RequestInit) => Promise.resolve(new Response(
      JSON.stringify(init?.method === "POST" ? { result: { passed: false }, review: failedReview, module: modules[0] } : multiPath),
      { status: 200 }
    )));
    vi.stubGlobal("fetch", fetchMock);
    renderWorkspace();

    expect(screen.queryByText("Correct or expected answer")).toBeNull();
    expect(screen.queryByText(orientationReview.expected_answer)).toBeNull();
    fireEvent.click(screen.getByLabelText("Repository name"));
    fireEvent.click(screen.getByRole("button", { name: "Submit saved activity" }));

    expect(await screen.findByText("Correct or expected answer")).toBeTruthy();
    expect(screen.getByText(failedReview.your_answer)).toBeTruthy();
    expect(screen.getByText(failedReview.expected_answer)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry activity" })).toBeTruthy();
    expect(screen.getByText("Expected evidence", { exact: false })).toBeTruthy();
  });

  it("shows the Module 3 example solution only after an attempt and only after explicit reveal", async () => {
    const validation = { ...modules[2], state: "available" as const };
    const failedReview: AttemptReview = {
      attempt_id: "attempt-health",
      activity_id: validation.activities[0].id,
      passed: false,
      your_answer: validation.activities[0].starter_code ?? "",
      expected_answer: 'One healthz function returning exactly {"status": "ok", "service": "ownyourcode-api"}.',
      why_expected_answer: "The literal dictionary needs both required fields.",
      project_teaching: "AST validates literal structure without executing code.",
      evidence_ids: validation.evidence_ids,
      option_feedback: [],
      transition_explanations: [],
      checks: [{ id: "health-check-contract.v1", passed: false, message: "The service field is missing." }],
      can_retry: true,
      example_solution: 'def healthz():\n    return {"status": "ok", "service": "ownyourcode-api"}\n'
    };
    vi.stubGlobal("fetch", vi.fn((_: string, init?: RequestInit) => Promise.resolve(new Response(
      JSON.stringify(init?.method === "POST" ? { result: { passed: false }, review: failedReview, module: validation } : { ...multiPath, modules: [validation], resume_module_id: validation.id }),
      { status: 200 }
    ))));
    renderWorkspace({ ...multiPath, modules: [validation], resume_module_id: validation.id });

    expect(screen.queryByRole("button", { name: "Show solution" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Submit saved activity" }));
    const showSolution = await screen.findByRole("button", { name: "Show solution" });
    expect(screen.queryByText(/Example solution — teaching fixture/i)).toBeNull();
    fireEvent.click(showSolution);
    expect(screen.getByText("Example solution — teaching fixture, not repository source.")).toBeTruthy();
    expect(document.querySelector(".learning-path-review__solution pre")?.textContent).toBe(failedReview.example_solution);
    expect(screen.getByText(/without executing the submitted module/i)).toBeTruthy();
  });

  it("offers Review learning path after all modules are demonstrated", async () => {
    const fetchMock = vi.fn().mockResolvedValue(defaultViewResponse());
    vi.stubGlobal("fetch", fetchMock);
    const completePath: LearningPathResponse = {
      ...multiPath,
      modules: modules.map((module, index) => ({
        ...module,
        state: "demonstrated",
        attempt_reviews: index === 0 ? [orientationReview] : []
      })),
      resume_module_id: "module-three",
      summary: { ...multiPath.summary!, modules_demonstrated: 3, practical_gates_passed: 2 }
    };
    renderWorkspace(completePath);

    expect(screen.getByRole("heading", { name: modules[2].title })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Continue learning" })).toBeNull();
    expect(screen.getByText("Learning path complete — review any module or create a fresh path after a new repository inspection.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Keep learning one saved lesson at a time" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Review learning path" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/projects/project-one/learning-path/modules/module-three/view",
      expect.objectContaining({ method: "PATCH" })
    ));
    expect(screen.getByRole("heading", { name: modules[2].title })).toBeTruthy();
  });

  it("keeps module number, wrapping title, and state in separate navigation elements", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWorkspace();
    const moduleButton = screen.getByRole("button", { name: /Module 1: Orient yourself/i });
    expect(within(moduleButton).getByText("Module 1").className).toContain("learning-path__module-number");
    expect(within(moduleButton).getByText(modules[0].title).className).toContain("learning-path__module-title");
    expect(within(moduleButton).getByText("Available").className).toContain("learning-path__module-state");
    expect(moduleButton.querySelectorAll(":scope > span")).toHaveLength(3);
    expect((screen.getByRole("button", { name: /Module 2:.*Locked/i }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers a new immutable path when the active inspection makes an older path stale", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWorkspace({ ...multiPath, stale: true });
    expect(screen.getByRole("heading", { name: "Refresh the saved learning path" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create fresh saved learning path" })).toBeTruthy();
  });
});
