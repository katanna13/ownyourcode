import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OralDefensePanel } from "./OralDefensePanel";

const answer = "The frontend can own browser interaction while the FastAPI backend can own API routing. The bounded inspection cannot prove every deployment relationship, so I would inspect container configuration before choosing an integration trade-off.";

function availablePreparation(contextId = "a".repeat(64)) {
  return {
    persisted: false,
    available: true,
    message: "Oral defense prepared. Nothing was saved.",
    oral_defense_id: "architecture-boundaries.v1",
    oral_defense_context_id: contextId,
    title: "Explain the repository boundaries",
    question: {
      id: "architecture-boundaries.question.v1",
      prompt: "Using only confirmed evidence, explain how the detected frontend and backend boundaries could divide responsibilities. State a limitation and one trade-off.",
      boundary_evidence: [
        { category: "frontend", evidence: { id: "technology:react", kind: "technology", label: "React", detail: "Detected." } },
        { category: "backend", evidence: { id: "technology:fastapi", kind: "technology", label: "FastAPI", detail: "Detected." } }
      ]
    },
    maximum_answer_length: 800,
    inspection_limitations: ["Inspection is bounded."]
  };
}

const evaluationResponse = {
  persisted: false,
  message: "Oral defense evaluated. Nothing was saved.",
  oral_defense_points: { earned_points: 3, max_points: 4 },
  rubric_dimensions: [
    { id: "architecture-boundaries.supported-boundaries.v1", earned_points: 1, max_points: 1, feedback: "You identified two supported boundaries." },
    { id: "architecture-boundaries.evidence-grounding.v1", earned_points: 1, max_points: 1, feedback: "You connected claims to confirmed evidence." },
    { id: "architecture-boundaries.limitation-awareness.v1", earned_points: 1, max_points: 1, feedback: "You stated a bounded-inspection limitation." },
    { id: "architecture-boundaries.tradeoff-or-next-step.v1", earned_points: 0, max_points: 1, feedback: "Add a more concrete trade-off or next investigation step." }
  ],
  evidence_ids: ["technology:react", "technology:fastapi"],
  inspection_limitations: ["Inspection is bounded."]
};

function renderPanel({
  repositoryUrl = "https://github.com/acme/learning-api",
  learnerLevel = "junior",
  assessmentScore = { earned_points: 3, total_points: 4 },
  verifiedLabPassed = true,
  securityChallengePassed = true
}: {
  repositoryUrl?: string;
  learnerLevel?: "beginner" | "junior" | "intermediate";
  assessmentScore?: { earned_points: number; total_points: number } | null;
  verifiedLabPassed?: boolean;
  securityChallengePassed?: boolean;
} = {}) {
  return render(
    <OralDefensePanel
      repositoryUrl={repositoryUrl}
      learnerLevel={learnerLevel}
      assessmentScore={assessmentScore}
      verifiedLabPassed={verifiedLabPassed}
      securityChallengePassed={securityChallengePassed}
    />
  );
}

async function prepareAvailable(fetchMock: ReturnType<typeof vi.fn>) {
  fireEvent.click(screen.getByRole("button", { name: "Prepare oral defense" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  await screen.findByLabelText("Your defense");
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
});

describe("OralDefensePanel", () => {
  it("is hidden before the security challenge passes", () => {
    renderPanel({ securityChallengePassed: false });

    expect(screen.queryByText("Architecture oral defense")).toBeNull();
  });

  it("is hidden when the verified lab is not passing even if security is true", () => {
    renderPanel({ verifiedLabPassed: false, securityChallengePassed: true });

    expect(screen.queryByText("Architecture oral defense")).toBeNull();
  });

  it("prepares a grounded question without exposing a reference answer", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => availablePreparation()
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    await prepareAvailable(fetchMock);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.example/api/v1/oral-defenses/architecture-boundaries/prepare",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "junior"
        })
      }
    );
    expect(screen.getByText(/frontend and backend boundaries/)).not.toBeNull();
    expect(screen.queryByText(/reference answer/i)).toBeNull();
    expect(screen.getByText(/not an authenticated certification/i)).not.toBeNull();
  });

  it("shows loading, submits only oral-defense input, and renders rubric feedback with the score breakdown", async () => {
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

    fireEvent.change(screen.getByLabelText("Your defense"), { target: { value: answer } });
    fireEvent.click(screen.getByRole("button", { name: "Submit oral defense" }));
    expect((screen.getByRole("button", { name: "Evaluating oral defense..." }) as HTMLButtonElement).disabled).toBe(true);
    resolveEvaluation?.({ ok: true, json: async () => evaluationResponse });

    await screen.findByText("Oral-defense feedback");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://api.example/api/v1/oral-defenses/architecture-boundaries/evaluate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "junior",
          oral_defense_context_id: "a".repeat(64),
          question_id: "architecture-boundaries.question.v1",
          answer_text: answer
        })
      }
    );
    const body = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(body.assessment_score).toBeUndefined();
    expect(body.verified_lab_passed).toBeUndefined();
    expect(body.security_challenge_passed).toBeUndefined();
    expect(screen.getByText(/Oral-defense points:/)).not.toBeNull();
    expect(screen.getByText(/Preview Ownership Score: 86 \/ 100/)).not.toBeNull();
    expect(screen.getByText(/Raw total: 86.25/)).not.toBeNull();
    expect(screen.getByText("Demo session complete.")).not.toBeNull();
    expect(screen.getByText(/Preview Ownership Score:/).closest("section")?.className).toContain("message--success");
  });

  it("does not submit an answer shorter than 40 meaningful characters", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => availablePreparation()
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();
    await prepareAvailable(fetchMock);

    fireEvent.change(screen.getByLabelText("Your defense"), { target: { value: "Too short" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit oral defense" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Write at least 40 meaningful characters before submitting.")).not.toBeNull();
  });

  it("does not allow whitespace padding to satisfy the meaningful-answer minimum", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => availablePreparation()
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();
    await prepareAvailable(fetchMock);

    fireEvent.change(screen.getByLabelText("Your defense"), { target: { value: "A" + " ".repeat(39) } });
    fireEvent.click(screen.getByRole("button", { name: "Submit oral defense" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Write at least 40 meaningful characters before submitting.")).not.toBeNull();
  });

  it("submits a meaningful 40-character answer without trimming it", async () => {
    const meaningfulAnswer = "A".repeat(40);
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => availablePreparation() })
      .mockResolvedValueOnce({ ok: true, json: async () => evaluationResponse });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();
    await prepareAvailable(fetchMock);

    fireEvent.change(screen.getByLabelText("Your defense"), { target: { value: meaningfulAnswer } });
    fireEvent.click(screen.getByRole("button", { name: "Submit oral defense" }));
    await screen.findByText("Oral-defense feedback");

    expect(JSON.parse(fetchMock.mock.calls[1][1].body).answer_text).toBe(meaningfulAnswer);
  });

  it("uses a neutral style for zero-point oral-defense feedback", async () => {
    const zeroPointEvaluation = {
      ...evaluationResponse,
      oral_defense_points: { earned_points: 0, max_points: 4 },
      rubric_dimensions: evaluationResponse.rubric_dimensions.map((dimension) => ({
        ...dimension,
        earned_points: 0
      }))
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => availablePreparation() })
      .mockResolvedValueOnce({ ok: true, json: async () => zeroPointEvaluation });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();
    await prepareAvailable(fetchMock);

    fireEvent.change(screen.getByLabelText("Your defense"), { target: { value: answer } });
    fireEvent.click(screen.getByRole("button", { name: "Submit oral defense" }));
    const feedbackHeading = await screen.findByText("Oral-defense feedback");

    expect(feedbackHeading.closest("section")?.className).toBe("message");
    expect(screen.getByText("Oral-defense points:").parentElement?.textContent).toBe(
      "Oral-defense points: 0 / 4"
    );
  });

  it("shows unavailable and API-error states safely", async () => {
    const unavailableFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        persisted: false,
        available: false,
        message: "This oral defense is unavailable for the inspected repository.",
        reason: "The deterministic inspection must confirm two boundary categories.",
        inspection_limitations: ["Inspection is bounded."]
      })
    });
    vi.stubGlobal("fetch", unavailableFetch);
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Prepare oral defense" }));
    await screen.findByText("Oral defense unavailable");
    expect(screen.queryByLabelText("Your defense")).toBeNull();

    cleanup();
    const errorFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Repository evidence changed. Prepare the oral defense again." })
    });
    vi.stubGlobal("fetch", errorFetch);
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Prepare oral defense" }));
    expect(await screen.findByText("Repository evidence changed. Prepare the oral defense again.")).not.toBeNull();
  });

  it("removes and clears all downstream score state when security changes from passed to failed", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => availablePreparation()
    });
    vi.stubGlobal("fetch", fetchMock);
    const rendered = renderPanel();
    await prepareAvailable(fetchMock);
    fireEvent.change(screen.getByLabelText("Your defense"), { target: { value: answer } });

    rendered.rerender(
      <OralDefensePanel
        repositoryUrl="https://github.com/acme/learning-api"
        learnerLevel="junior"
        assessmentScore={{ earned_points: 3, total_points: 4 }}
        verifiedLabPassed={true}
        securityChallengePassed={false}
      />
    );
    expect(screen.queryByText("Architecture oral defense")).toBeNull();

    await waitFor(() => expect(screen.queryByLabelText("Your defense")).toBeNull());
    rendered.rerender(
      <OralDefensePanel
        repositoryUrl="https://github.com/acme/learning-api"
        learnerLevel="junior"
        assessmentScore={{ earned_points: 3, total_points: 4 }}
        verifiedLabPassed={true}
        securityChallengePassed={true}
      />
    );
    expect(screen.getByRole("button", { name: "Prepare oral defense" })).not.toBeNull();
    expect(screen.queryByLabelText("Your defense")).toBeNull();
    expect(screen.queryByText(/Preview Ownership Score:/)).toBeNull();
  });
});
