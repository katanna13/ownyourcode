import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthenticationTestProvider } from "../auth/ClerkProviderBoundary";
import { ContinuousLearningPanel } from "./ContinuousLearningPanel";


const lesson = {
  id: "continuous-one",
  sequence: 1,
  title: "Explain one confirmed boundary",
  focus: "Connect FastAPI evidence to one bounded backend claim.",
  lesson_format: "explain_confirmed_concept",
  activity_type: "explain_back",
  difficulty: "foundation",
  objective: "Explain one confirmed concept without inventing uninspected behavior.",
  explanation: "FastAPI evidence confirms a backend framework signal, while exact routes remain outside the bounded inspection.",
  project_connection: "This project contains deterministic FastAPI evidence in its saved catalog.",
  confirmed_evidence_ids: ["technology:fastapi"],
  illustrative_example: "A browser-to-API request is an illustrative flow, not a confirmed route.",
  unknown_or_uninspected: ["Exact endpoint behavior was not inspected."],
  suggested_next_focus: "Practice the same evidence through a failure-path question.",
  activity: {
    id: "continuous-1-explain_back.v1",
    activity_type: "explain_back",
    context_id: "a".repeat(64),
    prompt: "Explain how confirmed FastAPI evidence supports one bounded backend claim.",
    evidence_ids: ["technology:fastapi"],
    choices: [],
    starter_code: null,
    constraints: ["Write at least 40 meaningful characters."],
    maximum_answer_length: 800
  },
  completed: false,
  created_at: "2026-07-22T00:00:00Z",
  completed_at: null,
  review: null
};

const review = {
  attempt_id: "attempt-one",
  passed: true,
  earned_points: 2,
  submitted_answer: "FastAPI confirms a backend framework, while exact route behavior remains uninspected.",
  expected_answer: "Connect the confirmed FastAPI evidence to a bounded backend claim and state an inspection limitation.",
  why_correct: "The answer uses confirmed evidence without turning an illustrative flow into a repository fact.",
  project_connection: lesson.project_connection,
  evidence_ids: ["technology:fastapi"],
  feedback: "Clear evidence grounding and limitation awareness.",
  checks: [],
  can_retry: false
};

function response(lessons: Array<Record<string, unknown>>, resumeLessonId: string | null) {
  return {
    persisted: true,
    available: true,
    message: "Continue learning from confirmed repository evidence and saved learning history.",
    evidence_catalog: [{ id: "technology:fastapi", label: "FastAPI", detail: "Confirmed from pyproject.toml." }],
    lessons,
    resume_lesson_id: resumeLessonId
  };
}

function renderPanel(onReviewLearningPath = vi.fn()) {
  render(
    <AuthenticationTestProvider value={{
      isConfigured: true,
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => "current-token",
      markSessionExpired: vi.fn()
    }}>
      <ContinuousLearningPanel projectId="project-one" onReviewLearningPath={onReviewLearningPath} />
    </AuthenticationTestProvider>
  );
  return onReviewLearningPath;
}

describe("ContinuousLearningPanel", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "http://api.test"));
  afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

  it("generates one lesson, hides its reference answer, and reveals saved feedback after submission", async () => {
    const completedLesson = { ...lesson, completed: true, completed_at: "2026-07-22T00:10:00Z", review };
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/attempts")) {
        return Promise.resolve(new Response(JSON.stringify({ persisted: true, lesson: completedLesson }), { status: 200 }));
      }
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify(response([lesson], lesson.id)), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(response([], null)), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const onReview = renderPanel();

    const generate = await screen.findByRole("button", { name: "Generate another lesson" });
    await waitFor(() => expect((generate as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(generate);

    expect(await screen.findByRole("heading", { name: lesson.title })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Resume current lesson" })).toBeTruthy();
    expect(screen.queryByText(review.expected_answer)).toBeNull();
    expect(screen.getByText("Exact endpoint behavior was not inspected.")).toBeTruthy();
    const answer = "FastAPI confirms a backend framework, while exact route behavior remains uninspected.";
    fireEvent.change(screen.getByLabelText("Your answer"), { target: { value: answer } });
    fireEvent.click(screen.getByRole("button", { name: "Submit answer" }));

    expect(await screen.findByText("Expected or reference answer")).toBeTruthy();
    expect(screen.getByText(review.expected_answer)).toBeTruthy();
    expect(screen.getByText("Clear evidence grounding and limitation awareness.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Generate another lesson" })).toBeTruthy();
    const attemptCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/attempts"));
    expect(attemptCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        context_id: lesson.activity.context_id,
        selected_choice_id: null,
        ordered_step_ids: null,
        source_code: null,
        answer_text: answer
      })
    }));

    fireEvent.click(screen.getByRole("button", { name: "Review learning path" }));
    expect(onReview).toHaveBeenCalledTimes(1);
  });

  it("restores a completed generated lesson and its answer review from the initial response", async () => {
    const completedLesson = { ...lesson, completed: true, completed_at: "2026-07-22T00:10:00Z", review };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response([completedLesson], lesson.id)), { status: 200 })
    ));
    renderPanel();

    expect(await screen.findByText("Expected or reference answer")).toBeTruthy();
    expect(screen.getByText(review.submitted_answer)).toBeTruthy();
    expect(screen.getByText(review.expected_answer)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Submit answer" })).toBeNull();
  });
});
