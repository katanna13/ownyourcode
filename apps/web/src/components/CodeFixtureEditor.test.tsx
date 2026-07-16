import { fireEvent, render, screen } from "@testing-library/react";
import { type FormEvent } from "react";
import { describe, expect, it, vi } from "vitest";

import { CodeFixtureEditor } from "./CodeFixtureEditor";

describe("CodeFixtureEditor", () => {
  it("labels the server-owned fixture, keeps the editor keyboard-accessible, and exposes clear actions", () => {
    const onChange = vi.fn();
    const onReset = vi.fn();

    const onSubmit = vi.fn((event: FormEvent<HTMLFormElement>) => event.preventDefault());

    render(
      <form onSubmit={onSubmit}>
        <CodeFixtureEditor
          id="fixture"
          value={'def healthz():\n    return {"status": "ok"}\n'}
          maximumLength={1000}
          onChange={onChange}
          onReset={onReset}
          isSubmitting={false}
          submitLabel="Submit fixture"
          submittingLabel="Verifying fixture..."
        />
      </form>
    );

    expect(screen.getByText("Teaching fixture — not repository source")).toBeTruthy();
    expect(screen.getByText("AST parsing only; learner code is never executed.")).toBeTruthy();
    const editor = screen.getByLabelText("Teaching fixture code");
    editor.focus();
    expect(document.activeElement).toBe(editor);
    fireEvent.change(editor, { target: { value: "updated" } });
    expect(onChange).toHaveBeenCalledWith("updated");

    const reset = screen.getByRole("button", { name: "Reset fixture" });
    reset.focus();
    expect(document.activeElement).toBe(reset);
    fireEvent.click(reset);
    expect(onReset).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Submit fixture" })).toBeTruthy();
  });
});
