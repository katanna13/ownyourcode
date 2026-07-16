import { afterEach, describe, expect, it, vi } from "vitest";

import { scrollWorkspaceStageIntoView } from "./workspaceStageNavigation";

describe("scrollWorkspaceStageIntoView", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("calculates an exact stage position below the sticky workspace header", () => {
    document.body.innerHTML = '<section class="workspace"><header class="workspace__header"></header><section data-stage="assess"></section></section>';
    const header = document.querySelector<HTMLElement>(".workspace__header")!;
    const stage = document.querySelector<HTMLElement>('[data-stage="assess"]')!;
    vi.spyOn(header, "getBoundingClientRect").mockReturnValue({ height: 80 } as DOMRect);
    vi.spyOn(stage, "getBoundingClientRect").mockReturnValue({ top: 300 } as DOMRect);
    Object.defineProperty(window, "scrollY", { configurable: true, value: 400 });
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    scrollWorkspaceStageIntoView(stage);

    expect(scrollTo).toHaveBeenCalledWith({ top: 604, behavior: "smooth" });
  });

  it("uses immediate scrolling when the learner requests reduced motion", () => {
    document.body.innerHTML = '<section class="workspace"><header class="workspace__header"></header><section data-stage="assess"></section></section>';
    const header = document.querySelector<HTMLElement>(".workspace__header")!;
    const stage = document.querySelector<HTMLElement>('[data-stage="assess"]')!;
    vi.spyOn(header, "getBoundingClientRect").mockReturnValue({ height: 64 } as DOMRect);
    vi.spyOn(stage, "getBoundingClientRect").mockReturnValue({ top: 120 } as DOMRect);
    Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    scrollWorkspaceStageIntoView(stage);

    expect(scrollTo).toHaveBeenCalledWith({ top: 40, behavior: "auto" });
  });
});
