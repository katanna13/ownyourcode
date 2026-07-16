import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LearningWorkspace } from "./LearningWorkspace";
import { LessonResponse, RepositoryInspectionResponse } from "../types/workspace";

const preview = {
  validated: true,
  persisted: false,
  message: "Project details validated. Nothing was saved.",
  project: {
    name: "Learning API",
    description: "A repository to understand.",
    mode: "existing_repository" as const,
    repository_url: "https://github.com/acme/learning-api"
  }
};

const inspection: RepositoryInspectionResponse = {
  persisted: false,
  message: "Repository inspected. Nothing was saved.",
  repository: {
    name: "learning-api",
    full_name: "acme/learning-api",
    description: "A learning API.",
    default_branch: "main",
    primary_language: "Python",
    html_url: "https://github.com/acme/learning-api"
  },
  languages: [{ name: "Python", bytes: 12 }],
  technologies: [{ key: "fastapi", label: "FastAPI", evidence: ["pyproject.toml"] }],
  paths: { inspected_count: 1, returned: ["pyproject.toml"], truncated: false },
  important_files: [{ path: "pyproject.toml", kind: "manifest" }],
  limitations: ["Inspection is bounded."]
};

const lesson: LessonResponse = {
  persisted: false,
  message: "Lesson generated. Nothing was saved.",
  inspection_limitations: ["Inspection is bounded."],
  evidence_catalog: [{ id: "technology:fastapi", kind: "technology", label: "FastAPI", detail: "Detected." }],
  lesson: {
    title: "FastAPI orientation",
    learning_objective: "Understand the API boundary.",
    repository_summary: "The bounded evidence confirms FastAPI.",
    repository_summary_evidence_ids: ["technology:fastapi"],
    concepts: [],
    architecture_walkthrough: [],
    knowledge_check_questions: ["What does the evidence confirm?"],
    limitations_and_open_questions: ["Inspect more configuration when needed."]
  }
};

function renderWorkspace({
  currentInspection = inspection,
  currentLesson = null,
  stageScroller = vi.fn(),
  learningGoal = ""
}: {
  currentInspection?: RepositoryInspectionResponse | null;
  currentLesson?: LessonResponse | null;
  stageScroller?: (stageRegion: HTMLElement) => void;
  learningGoal?: string;
} = {}) {
  return render(
    <LearningWorkspace
      preview={preview}
      inspection={currentInspection}
      lesson={currentLesson}
      learnerLevel="beginner"
      learningGoal={learningGoal}
      isInspecting={false}
      inspectionErrors={[]}
      isGeneratingLesson={false}
      lessonErrors={[]}
      onInspectRepository={vi.fn()}
      onLearnerLevelChange={vi.fn()}
      onLearningGoalChange={vi.fn()}
      onGenerateLesson={vi.fn()}
      stageScroller={stageScroller}
    />
  );
}

describe("LearningWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("mounts only the visited stage and keeps locked panels out of the DOM", () => {
    renderWorkspace();

    expect(screen.getByRole("region", { name: "OwnYourCode learning workspace" })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Learning progress" })).toBeTruthy();
    expect(document.querySelector('[data-stage="inspect"]')).not.toBeNull();
    expect(document.querySelector('[data-stage="learn"]')).toBeNull();
    expect(document.querySelector('[data-stage="assess"]')).toBeNull();
    expect(screen.getByText("Inspect repository")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Learn: Available" }));

    expect(document.querySelector('[data-stage="learn"]')).not.toBeNull();
    expect(document.querySelector('[data-stage="assess"]')).toBeNull();
    expect(screen.getByRole("heading", { name: "Learn the architecture" })).toBeTruthy();
  });

  it("positions and focuses stages only after explicit Continue, Back, and progress navigation", async () => {
    const stageScroller = vi.fn();
    renderWorkspace({ currentLesson: lesson, stageScroller });

    fireEvent.click(screen.getByRole("button", { name: "Continue to lesson" }));
    await waitFor(() => expect(stageScroller).toHaveBeenLastCalledWith(document.querySelector('[data-stage="learn"]')));
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Learn the architecture" }));

    fireEvent.click(screen.getByRole("button", { name: "Check my understanding" }));
    await waitFor(() => expect(stageScroller).toHaveBeenLastCalledWith(document.querySelector('[data-stage="assess"]')));

    fireEvent.click(screen.getByRole("button", { name: "Back to lesson" }));
    await waitFor(() => expect(stageScroller).toHaveBeenLastCalledWith(document.querySelector('[data-stage="learn"]')));

    fireEvent.click(screen.getByRole("button", { name: "Inspect: Complete" }));
    await waitFor(() => expect(stageScroller).toHaveBeenLastCalledWith(document.querySelector('[data-stage="inspect"]')));
    expect(stageScroller).toHaveBeenCalledTimes(4);
  });

  it("uses native hidden for inactive visited stages without hiding or inverting the active Assess stage", () => {
    renderWorkspace({ currentLesson: lesson });

    fireEvent.click(screen.getByRole("button", { name: "Assess: Available" }));

    const assessStage = document.querySelector<HTMLElement>('[data-stage="assess"]');
    const inspectStage = document.querySelector<HTMLElement>('[data-stage="inspect"]');
    expect(assessStage?.hidden).toBe(false);
    expect(assessStage?.hasAttribute("inert")).toBe(false);
    expect(assessStage?.getAttribute("aria-hidden")).not.toBe("true");
    expect(inspectStage?.hidden).toBe(true);
  });

  it("preserves a visited panel's local state while backward and forward navigation hides it", async () => {
    const questions = {
      persisted: false,
      message: "Questions prepared.",
      assessment_context_id: "a".repeat(64),
      inspection_limitations: [],
      questions: [
        { id: "architecture-orientation.mcq.statement.v1", type: "multiple_choice", prompt: "Choose.", options: [{ id: "option-a", label: "Supported statement" }] },
        { id: "architecture-orientation.evidence.direct-support.v1", type: "evidence_selection", prompt: "Evidence.", evidence_choices: [{ id: "technology:fastapi", label: "FastAPI" }] },
        { id: "architecture-orientation.explain-back.evidence-limitation.v1", type: "explain_back", prompt: "Explain.", evidence_choices: [{ id: "technology:fastapi", label: "FastAPI" }] }
      ]
    };
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => questions }));
    const rendered = renderWorkspace({ currentLesson: lesson });
    fireEvent.click(screen.getByRole("button", { name: "Assess: Available" }));
    fireEvent.click(screen.getByRole("button", { name: "Start knowledge check" }));
    expect(await screen.findByText("Choose.")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("Supported statement"));
    fireEvent.click(screen.getAllByDisplayValue("technology:fastapi")[0]);
    fireEvent.change(screen.getByLabelText("Your explanation"), { target: { value: "The FastAPI evidence is retained while the workspace parent rerenders normally." } });

    rendered.rerender(
      <LearningWorkspace
        preview={preview}
        inspection={inspection}
        lesson={lesson}
        learnerLevel="beginner"
        learningGoal="An unrelated parent value"
        isInspecting={false}
        inspectionErrors={[]}
        isGeneratingLesson={false}
        lessonErrors={[]}
        onInspectRepository={vi.fn()}
        onLearnerLevelChange={vi.fn()}
        onLearningGoalChange={vi.fn()}
        onGenerateLesson={vi.fn()}
        stageScroller={vi.fn()}
      />
    );
    expect((screen.getByLabelText("Supported statement") as HTMLInputElement).checked).toBe(true);
    expect((screen.getAllByDisplayValue("technology:fastapi")[0] as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("Your explanation") as HTMLTextAreaElement).value).toBe("The FastAPI evidence is retained while the workspace parent rerenders normally.");

    fireEvent.click(screen.getByRole("button", { name: "Back to lesson" }));
    expect(screen.getByRole("heading", { name: "Learn the architecture" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Assess: Available" }));
    expect(screen.getByText("Choose.")).toBeTruthy();
  });

  it("exposes an owner/repository link while retaining the full URL accessibly", () => {
    renderWorkspace();

    const links = screen.getAllByRole("link", { name: /Repository acme\/learning-api/ });
    expect(links[0].textContent).toBe("acme/learning-api");
    expect(links[0].getAttribute("href")).toBe("https://github.com/acme/learning-api");
    expect(links[0].getAttribute("aria-label")).toContain("https://github.com/acme/learning-api");
  });

  it("does not change the selected stage when the assessment result makes Lab available", async () => {
    const questions = {
      persisted: false,
      message: "Questions prepared.",
      assessment_context_id: "a".repeat(64),
      inspection_limitations: [],
      questions: [
        { id: "architecture-orientation.mcq.statement.v1", type: "multiple_choice", prompt: "Choose.", options: [{ id: "option-a", label: "Supported statement" }] },
        { id: "architecture-orientation.evidence.direct-support.v1", type: "evidence_selection", prompt: "Evidence.", evidence_choices: [{ id: "technology:fastapi", label: "FastAPI" }] },
        { id: "architecture-orientation.explain-back.evidence-limitation.v1", type: "explain_back", prompt: "Explain.", evidence_choices: [{ id: "technology:fastapi", label: "FastAPI" }] }
      ]
    };
    const evaluation = {
      persisted: false,
      message: "Assessment evaluated.",
      score: { earned_points: 0, total_points: 4 },
      feedback: [],
      explain_back_feedback: { question_id: "architecture-orientation.explain-back.evidence-limitation.v1", earned_points: 0, max_points: 2, feedback: "Try again." },
      inspection_limitations: []
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => questions })
      .mockResolvedValueOnce({ ok: true, json: async () => evaluation });
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    vi.stubGlobal("fetch", fetchMock);
    const stageScroller = vi.fn();
    const documentScroll = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    renderWorkspace({ currentLesson: lesson, stageScroller });
    fireEvent.click(screen.getByRole("button", { name: "Assess: Available" }));
    fireEvent.click(screen.getByRole("button", { name: "Start knowledge check" }));
    expect(await screen.findByText("Choose.")).toBeTruthy();
    stageScroller.mockClear();
    documentScroll.mockClear();
    fireEvent.click(screen.getByLabelText("Supported statement"));
    fireEvent.click(screen.getAllByDisplayValue("technology:fastapi")[0]);
    fireEvent.change(screen.getByLabelText("Your explanation"), { target: { value: "FastAPI is confirmed by the bounded evidence catalog for this repository." } });
    fireEvent.click(screen.getAllByDisplayValue("technology:fastapi")[1]);
    fireEvent.click(screen.getByRole("button", { name: "Submit answers" }));
    expect(await screen.findByText("Assessment feedback")).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("button", { name: "Lab: Available" })).toBeTruthy());
    expect(screen.getByRole("button", { name: "Assess: Complete" }).getAttribute("aria-current")).toBe("step");
    expect(stageScroller).not.toHaveBeenCalled();
    expect(documentScroll).not.toHaveBeenCalled();
  });
});
