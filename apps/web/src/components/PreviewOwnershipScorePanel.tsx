import { LearningStage, WorkspaceProgress } from "../types/workspace";

import { calculatePreviewOwnershipScore, PreviewOwnershipScoreBreakdown } from "./previewOwnershipScore";

const STAGE_LABELS: Record<LearningStage, string> = {
  inspect: "Inspection",
  learn: "Lesson",
  assess: "Assessment",
  lab: "Verified lab",
  secure: "Security challenge",
  defend: "Oral defense",
  score: "Preview Ownership Score"
};

function formatPoints(points: number, maximum: number): string {
  return `${points.toFixed(2).replace(/\.00$/, "")} / ${maximum}`;
}

function ScoreBreakdown({ breakdown }: { breakdown: PreviewOwnershipScoreBreakdown }) {
  const rows = [
    { label: "Assessment", value: breakdown.assessment, maximum: 30 },
    { label: "Verified lab", value: breakdown.verifiedLab, maximum: 25 },
    { label: "Security challenge", value: breakdown.securityChallenge, maximum: 20 },
    { label: "Oral defense", value: breakdown.oralDefense, maximum: 25 }
  ];

  return (
    <div className="score-breakdown" aria-label="Preview Ownership Score breakdown">
      {rows.map((row) => (
        <div className="score-breakdown__row" key={row.label}>
          <span className="score-breakdown__label">{row.label}</span>
          <span className="score-breakdown__value">{formatPoints(row.value, row.maximum)}</span>
          <div
            className="score-breakdown__track"
            role="progressbar"
            aria-label={`${row.label} contribution`}
            aria-valuemin={0}
            aria-valuemax={row.maximum}
            aria-valuenow={row.value}
          >
            <div className="score-breakdown__fill" style={{ width: `${(row.value / row.maximum) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function PreviewOwnershipScorePanel({
  progress,
  reviewableStages,
  onReviewStage
}: {
  progress: WorkspaceProgress;
  reviewableStages: LearningStage[];
  onReviewStage: (stage: LearningStage) => void;
}) {
  if (!progress.assessment || !progress.oralDefense) {
    return null;
  }

  const score = calculatePreviewOwnershipScore({
    assessmentEarnedPoints: progress.assessment.earned_points,
    assessmentTotalPoints: progress.assessment.total_points,
    verifiedLabPassed: progress.verifiedLabPassed,
    securityChallengePassed: progress.securityChallengePassed,
    oralDefenseEarnedPoints: progress.oralDefense.earned_points,
    oralDefenseMaxPoints: progress.oralDefense.max_points
  });

  if (!score.valid) {
    return <section className="message message--error" role="alert"><p>{score.message}</p></section>;
  }

  return (
    <section className="preview-score glass-surface message message--success" aria-labelledby="preview-score-title">
      <p className="eyebrow">Current in-memory demo session</p>
      <h3 id="preview-score-title">Preview Ownership Score</h3>
      <p className="preview-score__number">{score.breakdown.previewScore} / 100</p>
      <p>Demo session complete.</p>
      <p className="session-disclaimer">This Preview Ownership Score is not an authenticated certification and is not persisted. It summarizes this browser’s current in-memory demo session; it cannot prove completion after a refresh or on another device.</p>
      <ScoreBreakdown breakdown={score.breakdown} />
      <p className="score-breakdown__value">Raw total: {score.breakdown.rawTotal.toFixed(2)} before rounding.</p>
      {reviewableStages.length > 0 && (
        <nav className="workspace__stage-actions" aria-label="Review completed learning activities">
          {reviewableStages.map((stage) => (
            <button className="button button--secondary" type="button" key={stage} onClick={() => onReviewStage(stage)}>
              Review {STAGE_LABELS[stage]}
            </button>
          ))}
        </nav>
      )}
    </section>
  );
}
