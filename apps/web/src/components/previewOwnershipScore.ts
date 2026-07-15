export type PreviewOwnershipScoreInput = {
  assessmentEarnedPoints: number;
  assessmentTotalPoints: number;
  verifiedLabPassed: boolean;
  securityChallengePassed: boolean;
  oralDefenseEarnedPoints: number;
  oralDefenseMaxPoints: number;
};

export type PreviewOwnershipScoreBreakdown = {
  assessment: number;
  verifiedLab: number;
  securityChallenge: number;
  oralDefense: number;
  rawTotal: number;
  previewScore: number;
};

export type PreviewOwnershipScoreResult =
  | { valid: true; breakdown: PreviewOwnershipScoreBreakdown }
  | { valid: false; message: string };

function isPointValue(value: number): boolean {
  return Number.isInteger(value) && value >= 0 && value <= 4;
}

export function calculatePreviewOwnershipScore(
  input: PreviewOwnershipScoreInput
): PreviewOwnershipScoreResult {
  if (
    !isPointValue(input.assessmentEarnedPoints) ||
    input.assessmentTotalPoints !== 4 ||
    !isPointValue(input.oralDefenseEarnedPoints) ||
    input.oralDefenseMaxPoints !== 4 ||
    typeof input.verifiedLabPassed !== "boolean" ||
    typeof input.securityChallengePassed !== "boolean"
  ) {
    return {
      valid: false,
      message: "The current browser-session score data is invalid."
    };
  }

  const assessment = (input.assessmentEarnedPoints / 4) * 30;
  const verifiedLab = input.verifiedLabPassed ? 25 : 0;
  const securityChallenge = input.securityChallengePassed ? 20 : 0;
  const oralDefense = (input.oralDefenseEarnedPoints / 4) * 25;
  const rawTotal = assessment + verifiedLab + securityChallenge + oralDefense;
  const previewScore = Math.round(rawTotal);

  if (rawTotal < 0 || rawTotal > 100 || previewScore < 0 || previewScore > 100) {
    return {
      valid: false,
      message: "The current browser-session score is outside its valid range."
    };
  }

  return {
    valid: true,
    breakdown: {
      assessment,
      verifiedLab,
      securityChallenge,
      oralDefense,
      rawTotal,
      previewScore
    }
  };
}
