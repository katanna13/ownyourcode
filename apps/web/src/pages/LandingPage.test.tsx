import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LandingPage } from "./LandingPage";

describe("LandingPage", () => {
  it("introduces OwnYourCode with a public demo and saved-project sign-in route", () => {
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
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Learn.*Verify.*Defend/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Try the demo" })).toHaveProperty(
      "href",
      "http://localhost:3000/projects/new"
    );
    expect(screen.getByRole("link", { name: "Sign in to save projects" })).toHaveProperty(
      "href",
      "http://localhost:3000/app/projects"
    );
  });
});
