import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProgressStepper } from "./ProgressStepper";

const onStageSelect = vi.fn();

describe("ProgressStepper", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("communicates complete, available, and locked states with readable prerequisites", () => {
    render(
      <ProgressStepper
        onStageSelect={onStageSelect}
        steps={[
          { id: "inspect", label: "Inspect", availability: "complete", active: false },
          { id: "learn", label: "Learn", availability: "available", active: true },
          { id: "assess", label: "Assess", availability: "locked", active: false, prerequisite: "Complete a lesson first." }
        ]}
      />
    );

    expect(screen.getByRole("navigation", { name: "Learning progress" })).toBeTruthy();
    expect(screen.getByText("Complete")).toBeTruthy();
    expect(screen.getByText("Available")).toBeTruthy();
    expect(screen.getByText("Locked")).toBeTruthy();
    expect(screen.getByText("Complete a lesson first.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Learn: Available" }).getAttribute("aria-current")).toBe("step");
    expect(screen.queryByRole("button", { name: /Assess:/ })).toBeNull();
  });

  it("keeps the document still and scrolls only its horizontal rail when the active stage is outside it", () => {
    const originalScrollIntoView = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
    const originalScrollTo = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollTo");
    const originalScrollWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollWidth");
    const originalClientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    const originalBounds = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "getBoundingClientRect");
    const scrollIntoView = vi.fn();
    const horizontalScroll = vi.fn();
    const windowScroll = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    Object.defineProperty(HTMLElement.prototype, "scrollTo", { configurable: true, value: horizontalScroll });
    Object.defineProperty(HTMLElement.prototype, "scrollWidth", {
      configurable: true,
      get() { return this.classList.contains("progress-stepper") ? 720 : 0; }
    });
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get() { return this.classList.contains("progress-stepper") ? 240 : 0; }
    });
    Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
      configurable: true,
      value: function getBoundingClientRect() {
        if (this.classList.contains("progress-stepper")) {
          return { left: 0, right: 240, width: 240 } as DOMRect;
        }
        if (this.classList.contains("progress-stepper__step--active")) {
          return { left: 420, right: 460, width: 40 } as DOMRect;
        }
        return { left: 0, right: 0, width: 0 } as DOMRect;
      }
    });

    try {
      render(
        <ProgressStepper
          onStageSelect={onStageSelect}
          steps={[
            { id: "inspect", label: "Inspect", availability: "complete", active: false },
            { id: "learn", label: "Learn", availability: "available", active: true },
            { id: "assess", label: "Assess", availability: "locked", active: false, prerequisite: "Inspect first." }
          ]}
        />
      );

      expect(scrollIntoView).not.toHaveBeenCalled();
      expect(windowScroll).not.toHaveBeenCalled();
      expect(horizontalScroll).toHaveBeenCalledWith(expect.objectContaining({ left: expect.any(Number) }));
      expect(horizontalScroll.mock.calls[0][0]).not.toHaveProperty("top");
    } finally {
      function restore(name: string, descriptor: PropertyDescriptor | undefined) {
        if (descriptor) {
          Object.defineProperty(HTMLElement.prototype, name, descriptor);
          return;
        }
        Reflect.deleteProperty(HTMLElement.prototype, name);
      }

      restore("scrollIntoView", originalScrollIntoView);
      restore("scrollTo", originalScrollTo);
      restore("scrollWidth", originalScrollWidth);
      restore("clientWidth", originalClientWidth);
      restore("getBoundingClientRect", originalBounds);
    }
  });
});
