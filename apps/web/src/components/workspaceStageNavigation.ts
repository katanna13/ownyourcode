const STAGE_TOP_GUTTER_PX = 16;

function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/**
 * Positions a newly selected workspace stage below the workspace's sticky
 * header. This is deliberately called only from explicit learner navigation.
 */
export function scrollWorkspaceStageIntoView(stageRegion: HTMLElement): void {
  const workspace = stageRegion.closest(".workspace");
  const stickyHeader = workspace?.querySelector<HTMLElement>(".workspace__header");
  const headerHeight = stickyHeader?.getBoundingClientRect().height ?? 0;
  const regionTop = stageRegion.getBoundingClientRect().top;
  const documentTop = window.scrollY ?? window.pageYOffset ?? 0;
  const top = Math.max(0, documentTop + regionTop - headerHeight - STAGE_TOP_GUTTER_PX);

  window.scrollTo({
    top,
    behavior: prefersReducedMotion() ? "auto" : "smooth"
  });
}
