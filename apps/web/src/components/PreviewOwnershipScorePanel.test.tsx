import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PreviewOwnershipScorePanel } from "./PreviewOwnershipScorePanel";

describe("PreviewOwnershipScorePanel", () => {
  it("labels the score as a session-only preview and offers reviews only for visited unlocked stages", () => {
    const onReviewStage = vi.fn();
    render(
      <PreviewOwnershipScorePanel
        progress={{
          assessment: { earned_points: 3, total_points: 4 },
          verifiedLabPassed: true,
          securityChallengePassed: true,
          oralDefense: { earned_points: 3, max_points: 4 }
        }}
        reviewableStages={["inspect", "learn", "assess"]}
        onReviewStage={onReviewStage}
      />
    );

    expect(screen.getByText(/not an authenticated certification/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Review Inspection" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Review Lesson" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Review Assessment" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Review Verified lab" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Review Lesson" }));
    expect(onReviewStage).toHaveBeenCalledWith("learn");
    expect(screen.getByText("Preview Ownership Score").closest("section")?.className).toContain("message--success");
  });
});
