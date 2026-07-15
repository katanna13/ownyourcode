import { describe, expect, it } from "vitest";

import { calculatePreviewOwnershipScore } from "./previewOwnershipScore";

describe("calculatePreviewOwnershipScore", () => {
  it("calculates the transparent 100-point formula and rounds the non-negative total with Math.round", () => {
    const result = calculatePreviewOwnershipScore({
      assessmentEarnedPoints: 3,
      assessmentTotalPoints: 4,
      verifiedLabPassed: true,
      securityChallengePassed: true,
      oralDefenseEarnedPoints: 3,
      oralDefenseMaxPoints: 4
    });

    expect(result).toEqual({
      valid: true,
      breakdown: {
        assessment: 22.5,
        verifiedLab: 25,
        securityChallenge: 20,
        oralDefense: 18.75,
        rawTotal: 86.25,
        previewScore: 86
      }
    });
  });

  it("returns 100 only for the complete current-session maximum", () => {
    const result = calculatePreviewOwnershipScore({
      assessmentEarnedPoints: 4,
      assessmentTotalPoints: 4,
      verifiedLabPassed: true,
      securityChallengePassed: true,
      oralDefenseEarnedPoints: 4,
      oralDefenseMaxPoints: 4
    });

    expect(result).toEqual({
      valid: true,
      breakdown: {
        assessment: 30,
        verifiedLab: 25,
        securityChallenge: 20,
        oralDefense: 25,
        rawTotal: 100,
        previewScore: 100
      }
    });
  });

  it("rejects malformed inputs instead of silently clamping them", () => {
    for (const input of [
      {
        assessmentEarnedPoints: 5,
        assessmentTotalPoints: 4,
        verifiedLabPassed: true,
        securityChallengePassed: true,
        oralDefenseEarnedPoints: 4,
        oralDefenseMaxPoints: 4
      },
      {
        assessmentEarnedPoints: 2,
        assessmentTotalPoints: 3,
        verifiedLabPassed: true,
        securityChallengePassed: true,
        oralDefenseEarnedPoints: 2,
        oralDefenseMaxPoints: 4
      },
      {
        assessmentEarnedPoints: 2,
        assessmentTotalPoints: 4,
        verifiedLabPassed: "true",
        securityChallengePassed: true,
        oralDefenseEarnedPoints: 2,
        oralDefenseMaxPoints: 4
      }
    ]) {
      const result = calculatePreviewOwnershipScore(input as never);
      expect(result.valid).toBe(false);
    }
  });

  it("never returns a score below zero or above 100 for valid input", () => {
    for (let assessment = 0; assessment <= 4; assessment += 1) {
      for (let defense = 0; defense <= 4; defense += 1) {
        const result = calculatePreviewOwnershipScore({
          assessmentEarnedPoints: assessment,
          assessmentTotalPoints: 4,
          verifiedLabPassed: assessment % 2 === 0,
          securityChallengePassed: defense % 2 === 0,
          oralDefenseEarnedPoints: defense,
          oralDefenseMaxPoints: 4
        });
        expect(result.valid).toBe(true);
        if (result.valid) {
          expect(result.breakdown.previewScore).toBeGreaterThanOrEqual(0);
          expect(result.breakdown.previewScore).toBeLessThanOrEqual(100);
        }
      }
    }
  });
});
