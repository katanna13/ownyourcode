import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VerifiedLabPanel } from "./VerifiedLabPanel";

const starterCode = 'def healthz():\n    return {"status": "ok"}\n';
const validCode = 'def healthz():\n    return {"status": "ok", "service": "ownyourcode-api"}\n';
const assessmentScore = { earned_points: 4, total_points: 4 };

function availablePreparation(contextId = "a".repeat(64)) {
  return {
    persisted: false,
    available: true,
    message: "Verified lab prepared. Nothing was saved.",
    lab_id: "fastapi-health-check.v1",
    lab_context_id: contextId,
    title: "FastAPI-style health check",
    learning_objective: "Practice a predictable health-check response.",
    instructions: "This server-owned teaching fixture is not source code from the repository.",
    starter_code: starterCode,
    constraints: ["Keep one healthz function.", "Return literal response fields."],
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
  message: "Lab evaluated through AST parsing only. Nothing was saved.",
  checks: [
    { id: "syntax-valid.v1", passed: true, message: "Python syntax is valid." },
    { id: "restricted-structure.v1", passed: true, message: "The fixture uses the supported function structure." },
    { id: "literal-response-dictionary.v1", passed: true, message: "healthz returns a two-field literal dictionary." },
    { id: "health-check-contract.v1", passed: true, message: "The health-check response matches the required fields." }
  ],
  feedback: ["Your healthz teaching fixture matches the required deterministic response."],
  inspection_limitations: ["Inspection is bounded."]
};

function renderPanel({
  repositoryUrl = "https://github.com/acme/learning-api",
  learnerLevel = "beginner",
  assessmentReady = true
}: {
  repositoryUrl?: string;
  learnerLevel?: "beginner" | "junior" | "intermediate";
  assessmentReady?: boolean;
} = {}) {
  return render(
    <VerifiedLabPanel
      repositoryUrl={repositoryUrl}
      learnerLevel={learnerLevel}
      assessmentReady={assessmentReady}
      assessmentScore={assessmentScore}
    />
  );
}

async function prepareAvailable(fetchMock: ReturnType<typeof vi.fn>) {
  fireEvent.click(screen.getByRole("button", { name: "Prepare verified lab" }));
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

describe("VerifiedLabPanel", () => {
  it("stays hidden before a successful assessment evaluation", () => {
    renderPanel({ assessmentReady: false });

    expect(screen.queryByText("Verified coding lab")).toBeNull();
    expect(screen.queryByText("Verified security challenge")).toBeNull();
  });

  it("prepares the lab with native fetch and shows the starter fixture", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => availablePreparation()
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    await prepareAvailable(fetchMock);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.example/api/v1/labs/fastapi-health-check/prepare",
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

  it("resets edited source, submits, shows loading, and renders a passing result", async () => {
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
    fireEvent.change(editor, { target: { value: "def healthz():\n    return {}\n" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset fixture" }));
    expect(editor.value).toBe(starterCode);
    fireEvent.change(editor, { target: { value: validCode } });
    fireEvent.click(screen.getByRole("button", { name: "Submit fixture" }));
    expect((screen.getByRole("button", { name: "Verifying fixture..." }) as HTMLButtonElement).disabled).toBe(true);
    resolveEvaluation?.({ ok: true, json: async () => passedEvaluation });

    await screen.findByText("Lab passed");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://api.example/api/v1/labs/fastapi-health-check/evaluate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "beginner",
          lab_context_id: "a".repeat(64),
          source_code: validCode
        })
      }
    );
    expect(screen.getByText("The health-check response matches the required fields.")).not.toBeNull();
    expect(screen.getByText("Verified security challenge")).not.toBeNull();
  });

  it("shows unavailable, failed, and API-error states safely", async () => {
    const unavailableFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        persisted: false,
        available: false,
        message: "This lab is unavailable for the inspected repository.",
        reason: "The deterministic inspection must confirm both Python and FastAPI.",
        inspection_limitations: ["Inspection is bounded."]
      })
    });
    vi.stubGlobal("fetch", unavailableFetch);
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Prepare verified lab" }));
    await waitFor(() => expect(unavailableFetch).toHaveBeenCalledTimes(1));
    await screen.findByText("Lab unavailable");
    expect(screen.getByText("Lab unavailable")).not.toBeNull();
    expect(screen.queryByLabelText("Teaching fixture code")).toBeNull();

    cleanup();
    const failedEvaluation = {
      ...passedEvaluation,
      passed: false,
      feedback: ["Use the required service value."],
      checks: passedEvaluation.checks.map((check, index) => ({
        ...check,
        passed: index < 3,
        message: index === 3 ? "Use the required status and service string values." : check.message
      }))
    };
    const failureFetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => availablePreparation() })
      .mockResolvedValueOnce({ ok: true, json: async () => failedEvaluation });
    vi.stubGlobal("fetch", failureFetch);
    renderPanel();
    await prepareAvailable(failureFetch);
    fireEvent.click(screen.getByRole("button", { name: "Submit fixture" }));
    await screen.findByText("Lab needs another attempt");
    expect(screen.getByText("Use the required service value.")).not.toBeNull();

    cleanup();
    const errorFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Repository evidence changed. Prepare the lab again." })
    });
    vi.stubGlobal("fetch", errorFetch);
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Prepare verified lab" }));
    expect(await screen.findByText("Repository evidence changed. Prepare the lab again.")).not.toBeNull();
  });

  it("clears prepared source, context, result, and errors when repository or learner level changes", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => availablePreparation("a".repeat(64)) })
      .mockResolvedValueOnce({ ok: true, json: async () => availablePreparation("b".repeat(64)) });
    vi.stubGlobal("fetch", fetchMock);
    const rendered = renderPanel();
    await prepareAvailable(fetchMock);
    expect(screen.getByLabelText("Teaching fixture code")).not.toBeNull();

    rendered.rerender(
      <VerifiedLabPanel
        repositoryUrl="https://github.com/acme/other-api"
        learnerLevel="beginner"
        assessmentReady={true}
        assessmentScore={assessmentScore}
      />
    );
    await waitFor(() => expect(screen.queryByLabelText("Teaching fixture code")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Prepare verified lab" }));
    await screen.findByLabelText("Teaching fixture code");
    fireEvent.click(screen.getByRole("button", { name: "Submit fixture" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetchMock.mock.calls[2][1].body).lab_context_id).toBe("b".repeat(64));

    rendered.rerender(
      <VerifiedLabPanel
        repositoryUrl="https://github.com/acme/other-api"
        learnerLevel="junior"
        assessmentReady={true}
        assessmentScore={assessmentScore}
      />
    );
    await waitFor(() => expect(screen.queryByLabelText("Teaching fixture code")).toBeNull());
  });
});
