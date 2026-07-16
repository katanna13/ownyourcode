import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SecurityChallengePanel } from "./SecurityChallengePanel";

const starterCode = `from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
)
`;

const validCode = starterCode.replace(
  'allow_origins=["*"]',
  'allow_origins=["http://localhost:5173"]'
);

function availablePreparation(contextId = "a".repeat(64)) {
  return {
    persisted: false,
    available: true,
    message: "Security challenge prepared. Nothing was saved.",
    security_challenge_id: "fastapi-cors.v1",
    security_challenge_context_id: contextId,
    title: "Fix a permissive CORS policy",
    learning_objective: "Practice restricting a FastAPI CORS policy to one explicit origin.",
    instructions: "This server-owned teaching fixture is not source code from the inspected repository.",
    starter_code: starterCode,
    constraints: ["Keep four statements.", "Use an explicit origin."],
    relevant_evidence: [
      { id: "language:python", kind: "language", label: "Language: Python", detail: "Detected." },
      { id: "technology:fastapi", kind: "technology", label: "FastAPI", detail: "Detected." }
    ],
    maximum_source_length: 1000,
    inspection_limitations: ["Inspection is bounded."]
  };
}

const passedEvaluation = {
  persisted: false,
  passed: true,
  message: "Security challenge evaluated through AST parsing only. Nothing was saved.",
  checks: [
    { id: "fastapi-cors.syntax-valid.v1", passed: true, message: "Python syntax is valid." },
    { id: "fastapi-cors.fixture-structure.v1", passed: true, message: "The fixture has the supported structure." },
    { id: "fastapi-cors.middleware-configuration.v1", passed: true, message: "CORSMiddleware is configured." },
    { id: "fastapi-cors.allowed-origin.v1", passed: true, message: "The allowed origin is explicit." },
    { id: "fastapi-cors.credentials-setting.v1", passed: true, message: "Credentials remain literal True." }
  ],
  feedback: ["Your fixture restricts the CORS origin."],
  inspection_limitations: ["Inspection is bounded."]
};

function renderPanel({
  repositoryUrl = "https://github.com/acme/learning-api",
  learnerLevel = "beginner",
  verifiedLabPassed = true
}: {
  repositoryUrl?: string;
  learnerLevel?: "beginner" | "junior" | "intermediate";
  verifiedLabPassed?: boolean;
} = {}) {
  return render(
    <SecurityChallengePanel
      repositoryUrl={repositoryUrl}
      learnerLevel={learnerLevel}
      verifiedLabPassed={verifiedLabPassed}
    />
  );
}

async function prepareAvailable(fetchMock: ReturnType<typeof vi.fn>) {
  fireEvent.click(screen.getByRole("button", { name: "Prepare security challenge" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  await screen.findByLabelText("Teaching fixture code");
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
});

describe("SecurityChallengePanel", () => {
  it("is hidden until the verified lab has passed", () => {
    renderPanel({ verifiedLabPassed: false });

    expect(screen.queryByText("Verified security challenge")).toBeNull();
  });

  it("prepares the challenge with native fetch and displays the server-owned fixture", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => availablePreparation()
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    await prepareAvailable(fetchMock);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.example/api/v1/security-challenges/fastapi-cors/prepare",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "beginner"
        })
      }
    );
    expect((screen.getByLabelText("Teaching fixture code") as HTMLTextAreaElement).value).toBe(starterCode);
  });

  it("shows loading, resets code, submits the exact context, and renders a passing result", async () => {
    let resolveEvaluation: ((value: unknown) => void) | undefined;
    const evaluationPromise = new Promise((resolve) => {
      resolveEvaluation = resolve;
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => availablePreparation() })
      .mockReturnValueOnce(evaluationPromise);
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();
    await prepareAvailable(fetchMock);

    const editor = screen.getByLabelText("Teaching fixture code") as HTMLTextAreaElement;
    fireEvent.change(editor, { target: { value: "invalid" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset fixture" }));
    expect(editor.value).toBe(starterCode);
    fireEvent.change(editor, { target: { value: validCode } });
    fireEvent.click(screen.getByRole("button", { name: "Submit fixture" }));
    expect((screen.getByRole("button", { name: "Verifying fixture..." }) as HTMLButtonElement).disabled).toBe(true);
    resolveEvaluation?.({ ok: true, json: async () => passedEvaluation });

    await screen.findByText("Security challenge passed");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://api.example/api/v1/security-challenges/fastapi-cors/evaluate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "beginner",
          security_challenge_context_id: "a".repeat(64),
          source_code: validCode
        })
      }
    );
    expect(screen.getByText("The allowed origin is explicit.")).not.toBeNull();
  });

  it("shows unavailable, failed, and API-error states safely", async () => {
    const unavailableFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        persisted: false,
        available: false,
        message: "This security challenge is unavailable for the inspected repository.",
        reason: "The deterministic inspection must confirm both Python and FastAPI.",
        inspection_limitations: ["Inspection is bounded."]
      })
    });
    vi.stubGlobal("fetch", unavailableFetch);
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Prepare security challenge" }));
    await screen.findByText("Security challenge unavailable");
    expect(screen.queryByLabelText("Teaching fixture code")).toBeNull();

    cleanup();
    const failedEvaluation = {
      ...passedEvaluation,
      passed: false,
      feedback: ["Use the required origin."],
      checks: passedEvaluation.checks.map((check, index) => ({
        ...check,
        passed: index < 3,
        message: index === 3 ? "Use the required explicit origin." : check.message
      }))
    };
    const failureFetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => availablePreparation() })
      .mockResolvedValueOnce({ ok: true, json: async () => failedEvaluation });
    vi.stubGlobal("fetch", failureFetch);
    renderPanel();
    await prepareAvailable(failureFetch);
    fireEvent.click(screen.getByRole("button", { name: "Submit fixture" }));
    await screen.findByText("Security challenge needs another attempt");
    expect(screen.getByText("Use the required origin.")).not.toBeNull();

    cleanup();
    const errorFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Repository evidence changed. Prepare the security challenge again." })
    });
    vi.stubGlobal("fetch", errorFetch);
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Prepare security challenge" }));
    expect(await screen.findByText("Repository evidence changed. Prepare the security challenge again.")).not.toBeNull();
  });

  it("removes and clears prepared state when a passing lab changes to failed", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => availablePreparation()
    });
    vi.stubGlobal("fetch", fetchMock);
    const rendered = renderPanel();
    await prepareAvailable(fetchMock);
    expect(screen.getByLabelText("Teaching fixture code")).not.toBeNull();

    rendered.rerender(
      <SecurityChallengePanel
        repositoryUrl="https://github.com/acme/learning-api"
        learnerLevel="beginner"
        verifiedLabPassed={false}
      />
    );
    expect(screen.queryByText("Verified security challenge")).toBeNull();

    await waitFor(() => expect(screen.queryByLabelText("Teaching fixture code")).toBeNull());
    rendered.rerender(
      <SecurityChallengePanel
        repositoryUrl="https://github.com/acme/learning-api"
        learnerLevel="beginner"
        verifiedLabPassed={true}
      />
    );
    expect(screen.getByRole("button", { name: "Prepare security challenge" })).not.toBeNull();
    expect(screen.queryByLabelText("Teaching fixture code")).toBeNull();
  });
});
