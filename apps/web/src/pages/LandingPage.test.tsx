import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LandingPage } from "./LandingPage";

describe("LandingPage", () => {
  it("introduces OwnYourCode and links to the new project route", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", {
        name: "Understand the software you build with AI."
      })
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Start a project" })).toHaveProperty(
      "href",
      "http://localhost:3000/projects/new"
    );
  });
});
