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

    const button = screen.getByRole("button", { name: "Validating…" });
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
});
