import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AssessmentPanel } from "./AssessmentPanel";

const questionsResponse = {
  persisted: false,
  message: "Assessment questions prepared. Nothing was saved.",
  assessment_context_id: "a".repeat(64),
  inspection_limitations: ["Inspection uses a bounded deterministic catalog."],
  questions: [
    {
      id: "architecture-orientation.mcq.statement.v1",
      type: "multiple_choice",
      prompt: "Which statement is supported by the bounded repository orientation evidence?",
      options: [
        { id: "option-a", label: "FastAPI is represented in the deterministic evidence catalog." },
        { id: "option-b", label: "The full source tree was reviewed." },
        { id: "option-c", label: "A security scan ruled out known risks." },
        { id: "option-d", label: "A project and assessment result were saved." }
      ]
    },
    {
      id: "architecture-orientation.evidence.direct-support.v1",
      type: "evidence_selection",
      prompt: "Select the one evidence item that directly supports the target.",
      evidence_choices: [
        { id: "technology:fastapi", label: "FastAPI" },
        { id: "language:python", label: "Language: Python" }
      ]
    },
    {
      id: "architecture-orientation.explain-back.evidence-limitation.v1",
      type: "explain_back",
      prompt: "Explain what the target evidence tells you about this repository.",
      evidence_choices: [
        { id: "technology:fastapi", label: "FastAPI" },
        { id: "language:python", label: "Language: Python" }
      ]
    }
  ]
};

const evaluationResponse = {
  persisted: false,
  message: "Assessment evaluated. Nothing was saved.",
  score: { earned_points: 4, total_points: 4 },
  feedback: [
    {
      question_id: "architecture-orientation.mcq.statement.v1",
      earned_points: 1,
      max_points: 1,
      message: "Your selection matches a claim supported by the deterministic repository orientation."
    },
    {
      question_id: "architecture-orientation.evidence.direct-support.v1",
      earned_points: 1,
      max_points: 1,
      message: "Your selected evidence directly supports the repository-orientation target."
    }
  ],
  explain_back_feedback: {
    question_id: "architecture-orientation.explain-back.evidence-limitation.v1",
    earned_points: 2,
    max_points: 2,
    feedback: "Your explanation clearly connects FastAPI evidence to the repository."
  },
  inspection_limitations: ["Inspection uses a bounded deterministic catalog."]
};

function renderPanel(lessonReady = true) {
  return render(
    <AssessmentPanel
      repositoryUrl="https://github.com/acme/learning-api"
      learnerLevel="beginner"
      lessonReady={lessonReady}
    />
  );
}

async function loadQuestions(fetchMock: ReturnType<typeof vi.fn>) {
  renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Start knowledge check" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  await screen.findByText("Which statement is supported by the bounded repository orientation evidence?");
}

function fillAnswers() {
  fireEvent.click(screen.getByLabelText("FastAPI is represented in the deterministic evidence catalog."));
  const evidenceRadios = screen.getAllByDisplayValue("technology:fastapi");
  fireEvent.click(evidenceRadios[0]);
  fireEvent.change(screen.getByLabelText("Your explanation"), {
    target: { value: "FastAPI is declared as a dependency, so it is strong evidence about the API framework." }
  });
  fireEvent.click(evidenceRadios[1]);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
});

describe("AssessmentPanel", () => {
  it("only appears once a lesson is ready", () => {
    renderPanel(false);
    expect(screen.queryByText("Check your understanding of the repository orientation.")).toBeNull();
  });

  it("loads question previews with the canonical repository URL and learner level", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => questionsResponse
    });
    vi.stubGlobal("fetch", fetchMock);

    await loadQuestions(fetchMock);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.example/api/v1/assessments/architecture-orientation/questions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "beginner"
        })
      }
    );
    expect(screen.getAllByDisplayValue("technology:fastapi")[0].getAttribute("type")).toBe("radio");
  });

  it("keeps radios, evidence selection, and explain-back input interactive through controlled rerenders", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => questionsResponse });
    vi.stubGlobal("fetch", fetchMock);

    await loadQuestions(fetchMock);

    const multipleChoiceOptions = [
      "FastAPI is represented in the deterministic evidence catalog.",
      "The full source tree was reviewed.",
      "A security scan ruled out known risks.",
      "A project and assessment result were saved."
    ];
    const secondOption = multipleChoiceOptions[1]!;
    for (const label of multipleChoiceOptions) {
      const radio = screen.getByRole("radio", { name: label });
      fireEvent.click(radio);
      expect((radio as HTMLInputElement).checked).toBe(true);
    }

    const optionLabel = screen.getByText(secondOption).closest("label");
    fireEvent.click(optionLabel!);
    expect((screen.getByRole("radio", { name: secondOption }) as HTMLInputElement).checked).toBe(true);

    const evidenceRadios = screen.getAllByDisplayValue("technology:fastapi");
    fireEvent.click(evidenceRadios[0]);
    expect((evidenceRadios[0] as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getAllByDisplayValue("language:python")[0]);
    expect((screen.getAllByDisplayValue("language:python")[0] as HTMLInputElement).checked).toBe(true);

    const answer = "The controlled explain-back answer stays editable and retains normal typed text.";
    fireEvent.change(screen.getByLabelText("Your explanation"), { target: { value: answer } });
    expect((screen.getByLabelText("Your explanation") as HTMLTextAreaElement).value).toBe(answer);
  });

  it("shows loading state, submits answers, and renders server-owned feedback", async () => {
    const locationBeforeEvaluation = window.location.href;
    let resolveQuestions: ((value: unknown) => void) | undefined;
    const questionFetch = new Promise((resolve) => {
      resolveQuestions = resolve;
    });
    const fetchMock = vi.fn()
      .mockReturnValueOnce(questionFetch)
      .mockResolvedValueOnce({ ok: true, json: async () => evaluationResponse });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Start knowledge check" }));
    expect((screen.getByRole("button", { name: "Preparing assessment..." }) as HTMLButtonElement).disabled).toBe(true);
    resolveQuestions?.({ ok: true, json: async () => questionsResponse });
    await screen.findByText("Which statement is supported by the bounded repository orientation evidence?");
    fillAnswers();
    fireEvent.click(screen.getByRole("button", { name: "Submit answers" }));
    expect((screen.getByRole("button", { name: "Evaluating explanation..." }) as HTMLButtonElement).disabled).toBe(true);

    await screen.findByText("Assessment feedback");
    expect(window.location.href).toBe(locationBeforeEvaluation);
    expect(screen.getByText("Score:")).not.toBeNull();
    expect(screen.getByText(/4 \/ 4/)).not.toBeNull();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://api.example/api/v1/assessments/architecture-orientation/evaluate",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "beginner",
          assessment_context_id: "a".repeat(64),
          answers: {
            multiple_choice: {
              question_id: "architecture-orientation.mcq.statement.v1",
              selected_option_id: "option-a"
            },
            evidence_selection: {
              question_id: "architecture-orientation.evidence.direct-support.v1",
              selected_evidence_id: "technology:fastapi"
            },
            explain_back: {
              question_id: "architecture-orientation.explain-back.evidence-limitation.v1",
              answer_text: "FastAPI is declared as a dependency, so it is strong evidence about the API framework.",
              evidence_ids: ["technology:fastapi"]
            }
          }
        })
      })
    );
  });

  it("renders useful API validation errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: [{ msg: "Repository orientation evidence changed." }] })
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Start knowledge check" }));

    expect(await screen.findByText("Repository orientation evidence changed.")).not.toBeNull();
  });
});
