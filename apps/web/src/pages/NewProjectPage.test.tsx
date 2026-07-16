import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NewProjectPage } from "./NewProjectPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <NewProjectPage />
    </MemoryRouter>
  );
}

function fillNewIdeaForm() {
  fireEvent.change(screen.getByLabelText("Project name"), {
    target: { value: "Study Planner" }
  });
  fireEvent.change(screen.getByLabelText("Short description"), {
    target: { value: "A focused planner for weekly study sessions." }
  });
}

function fillRepositoryForm() {
  fillNewIdeaForm();
  fireEvent.click(screen.getByLabelText("Existing repository"));
  fireEvent.change(screen.getByLabelText("Public GitHub repository URL"), {
    target: { value: "https://github.com/acme/learning-api" }
  });
}

function repositoryPreviewResponse() {
  return {
    validated: true,
    persisted: false,
    message: "Project details validated. Nothing was saved.",
    project: {
      name: "Study Planner",
      description: "A focused planner for weekly study sessions.",
      mode: "existing_repository",
      repository_url: "https://github.com/acme/learning-api"
    }
  };
}

function inspectionResponse() {
  return {
    persisted: false,
    message: "Repository inspected. Nothing was saved.",
    repository: {
      name: "learning-api",
      full_name: "acme/learning-api",
      description: "Learning API",
      default_branch: "main",
      primary_language: "Python",
      html_url: "https://github.com/acme/learning-api"
    },
    languages: [{ name: "Python", bytes: 1200 }],
    technologies: [
      {
        key: "fastapi",
        label: "FastAPI",
        evidence: ["pyproject.toml: dependency fastapi"]
      }
    ],
    paths: {
      inspected_count: 3,
      returned: ["pyproject.toml"],
      truncated: false
    },
    important_files: [{ path: "pyproject.toml", kind: "manifest" }],
    limitations: ["Inspection uses a bounded tree."]
  };
}

function lessonResponse() {
  return {
    persisted: false,
    message: "Lesson generated from inspected repository evidence. Nothing was saved.",
    inspection_limitations: ["Inspection uses a bounded tree."],
    evidence_catalog: [
      {
        id: "technology:fastapi",
        kind: "technology",
        label: "FastAPI",
        detail: "Deterministically detected from a manifest."
      },
      {
        id: "repository:name",
        kind: "repository",
        label: "Repository: acme/learning-api",
        detail: "Public repository metadata."
      },
      {
        id: "repository:default-branch",
        kind: "repository",
        label: "Default branch",
        detail: "main"
      },
      {
        id: "language:python",
        kind: "language",
        label: "Language: Python",
        detail: "GitHub reported Python."
      },
      {
        id: "file:pyproject.toml",
        kind: "file",
        label: "pyproject.toml",
        detail: "A manifest."
      }
    ],
    lesson: {
      title: "Understand the learning API",
      learning_objective: "Identify the framework and key architecture evidence.",
      repository_summary: "This repository contains deterministic FastAPI evidence.",
      repository_summary_evidence_ids: ["repository:name"],
      concepts: [
        {
          title: "API framework",
          explanation: "FastAPI is detected from a declared dependency in the bounded manifest evidence.",
          why_it_matters: "Framework conventions guide routes and validation.",
          evidence_ids: ["technology:fastapi"],
          reflection_question: "Which route would you inspect first?"
        },
        {
          title: "Python runtime",
          explanation: "Python is reported by the deterministic inspection, giving a starting point for backend investigation.",
          why_it_matters: "The runtime affects tooling and commands.",
          evidence_ids: ["language:python"],
          reflection_question: "Which Python command would you use?"
        }
      ],
      architecture_walkthrough: [
        {
          step: "Start with the default branch and repository metadata before making assumptions.",
          evidence_ids: ["repository:default-branch"]
        },
        {
          step: "Then connect the manifest with the framework dependency evidence.",
          evidence_ids: ["file:pyproject.toml"]
        }
      ],
      knowledge_check_questions: [
        "Which evidence proves FastAPI?",
        "Why inspect a manifest first?"
      ],
      limitations_and_open_questions: [
        "The model did not perform a full source-code review."
      ]
    }
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("NewProjectPage", () => {
  it("renders the project-intake form", () => {
    renderPage();

    expect(screen.getByLabelText("Project name")).toBeTruthy();
    expect(screen.getByLabelText("Short description")).toBeTruthy();
    expect(screen.getByLabelText("New idea")).toBeTruthy();
    expect(screen.getByLabelText("Existing repository")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Validate project" })).toBeTruthy();
  });

  it("shows a required repository URL only for repository mode", () => {
    renderPage();

    expect(screen.queryByLabelText("Public GitHub repository URL")).toBeNull();

    fireEvent.click(screen.getByLabelText("Existing repository"));

    const repositoryUrl = screen.getByLabelText("Public GitHub repository URL");
    expect(repositoryUrl).toBeTruthy();
    expect((repositoryUrl as HTMLInputElement).required).toBe(true);
  });

  it("clears a repository URL when switching back to a new idea", () => {
    renderPage();
    fireEvent.click(screen.getByLabelText("Existing repository"));
    fireEvent.change(screen.getByLabelText("Public GitHub repository URL"), {
      target: { value: "https://github.com/example/learning-api" }
    });

    fireEvent.click(screen.getByLabelText("New idea"));
    fireEvent.click(screen.getByLabelText("Existing repository"));

    expect(
      (screen.getByLabelText("Public GitHub repository URL") as HTMLInputElement)
        .value
    ).toBe("");
  });

  it("posts the form, disables submission while loading, and renders a preview", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    let resolveFetch: ((response: Response) => void) | undefined;
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    const fetchMock = vi.fn(() => fetchPromise);
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fillNewIdeaForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));

    const button = screen.getByRole("button", { name: "Validating..." });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.example/api/v1/projects/preview",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Study Planner",
          description: "A focused planner for weekly study sessions.",
          mode: "new_idea"
        })
      }
    );

    resolveFetch?.(
      new Response(
        JSON.stringify({
          validated: true,
          persisted: false,
          message: "Project details validated. Nothing was saved.",
          project: {
            name: "Study Planner",
            description: "A focused planner for weekly study sessions.",
            mode: "new_idea",
            repository_url: null
          }
        }),
        { status: 200 }
      )
    );

    expect(await screen.findByRole("status")).toBeTruthy();
    expect(screen.getByText("Project details validated. Nothing was saved.")).toBeTruthy();
    expect(screen.getByText("Study Planner")).toBeTruthy();
  });

  it("displays every available backend validation message", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              { msg: "Repository URL is required." },
              { msg: "Description is too short." }
            ]
          }),
          { status: 422 }
        )
      )
    );

    renderPage();
    fillNewIdeaForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });
    expect(screen.getByText("Repository URL is required.")).toBeTruthy();
    expect(screen.getByText("Description is too short.")).toBeTruthy();
  });

  it("shows inspection only after an existing-repository preview", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            validated: true,
            persisted: false,
            message: "Project details validated. Nothing was saved.",
            project: {
              name: "Study Planner",
              description: "A focused planner for weekly study sessions.",
              mode: "new_idea",
              repository_url: null
            }
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(repositoryPreviewResponse()), { status: 200 })
      );
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fillNewIdeaForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));
    await screen.findByText("Validated preview");
    expect(screen.queryByRole("button", { name: "Inspect repository" })).toBeNull();

    cleanup();
    renderPage();
    fillRepositoryForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));
    expect(await screen.findByRole("button", { name: "Inspect repository" })).toBeTruthy();
  });

  it("posts an inspection request, shows loading, and renders the result", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    let resolveInspection: ((response: Response) => void) | undefined;
    const inspectionPromise = new Promise<Response>((resolve) => {
      resolveInspection = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(repositoryPreviewResponse()), { status: 200 })
      )
      .mockImplementationOnce(() => inspectionPromise);
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fillRepositoryForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));
    fireEvent.click(await screen.findByRole("button", { name: "Inspect repository" }));

    const loadingButton = screen.getByRole("button", {
      name: "Inspecting repository..."
    });
    expect((loadingButton as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://api.example/api/v1/repositories/inspect",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api"
        })
      }
    );

    resolveInspection?.(
      new Response(JSON.stringify(inspectionResponse()), { status: 200 })
    );

    expect(await screen.findByText("Repository inspection")).toBeTruthy();
    expect(screen.getAllByText("acme/learning-api").length).toBeGreaterThan(0);
    expect(screen.getByText("FastAPI")).toBeTruthy();
    expect(
      screen.getByText("pyproject.toml: dependency fastapi")
    ).toBeTruthy();
    expect(screen.getByText("pyproject.toml").closest("li")?.textContent).toContain("manifest");
    expect(screen.getAllByText("Inspection uses a bounded tree.")).toHaveLength(2);
  });

  it("renders a useful repository-inspection API error", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(repositoryPreviewResponse()), { status: 200 })
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ detail: "GitHub rate limit reached. Please try again later." }),
            { status: 429 }
          )
        )
    );

    renderPage();
    fillRepositoryForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));
    fireEvent.click(await screen.findByRole("button", { name: "Inspect repository" }));

    expect(
      await screen.findByText("GitHub rate limit reached. Please try again later.")
    ).toBeTruthy();
  });

  it("generates a lesson with the selected learner context, loading state, and evidence", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    let resolveLesson: ((response: Response) => void) | undefined;
    const lessonPromise = new Promise<Response>((resolve) => {
      resolveLesson = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(repositoryPreviewResponse()), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(inspectionResponse()), { status: 200 })
      )
      .mockImplementationOnce(() => lessonPromise);
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fillRepositoryForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));
    fireEvent.click(await screen.findByRole("button", { name: "Inspect repository" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue to lesson" }));
    expect(await screen.findByText("Generate your first lesson")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Learner level"), {
      target: { value: "junior" }
    });
    fireEvent.change(screen.getByLabelText("Learning goal (optional)"), {
      target: { value: "Understand request validation." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate first lesson" }));

    const loadingButton = screen.getByRole("button", {
      name: "Generating lesson..."
    });
    expect((loadingButton as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://api.example/api/v1/lessons/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: "https://github.com/acme/learning-api",
          learner_level: "junior",
          learning_goal: "Understand request validation."
        })
      }
    );

    resolveLesson?.(new Response(JSON.stringify(lessonResponse()), { status: 200 }));

    expect(
      await screen.findByRole("heading", { name: "Understand the learning API" })
    ).toBeTruthy();
    expect(screen.getAllByText("technology:fastapi")).toHaveLength(2);
    expect(screen.getByText("Inspection limitations (deterministic)")).toBeTruthy();
    expect(screen.getAllByText("Inspection uses a bounded tree.")).toHaveLength(3);
    expect(
      screen.getByText("The model did not perform a full source-code review.")
    ).toBeTruthy();
  });

  it("does not show lesson generation for a new idea and displays lesson API errors", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api.example");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            validated: true,
            persisted: false,
            message: "Project details validated. Nothing was saved.",
            project: {
              name: "Study Planner",
              description: "A focused planner for weekly study sessions.",
              mode: "new_idea",
              repository_url: null
            }
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(repositoryPreviewResponse()), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(inspectionResponse()), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ detail: "Lesson generation is not configured on this server." }),
          { status: 503 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fillNewIdeaForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));
    await screen.findByText("Validated preview");
    expect(screen.queryByText("Generate your first lesson")).toBeNull();

    cleanup();
    renderPage();
    fillRepositoryForm();
    fireEvent.click(screen.getByRole("button", { name: "Validate project" }));
    fireEvent.click(await screen.findByRole("button", { name: "Inspect repository" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue to lesson" }));
    fireEvent.click(await screen.findByRole("button", { name: "Generate first lesson" }));

    expect(
      await screen.findByText("Lesson generation is not configured on this server.")
    ).toBeTruthy();
  });
});
