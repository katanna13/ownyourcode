import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("application routing", () => {
  it("renders the placeholder routes", () => {
    const newProject = render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", { name: "New Project" })
    ).toBeTruthy();

    newProject.unmount();

    render(
      <MemoryRouter initialEntries={["/projects/example-project"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", { name: "Project Workspace" })
    ).toBeTruthy();
    expect(screen.getByText("example-project")).toBeTruthy();
  });
});
