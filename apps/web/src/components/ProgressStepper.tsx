import { useEffect, useRef } from "react";

import { LearningStage, StageAvailability, WorkspaceStage } from "../types/workspace";

export type ProgressStep = WorkspaceStage & { active: boolean };

const STATE_LABELS: Record<StageAvailability, string> = {
  complete: "Complete",
  available: "Available",
  locked: "Locked"
};

export function ProgressStepper({
  steps,
  onStageSelect
}: {
  steps: ProgressStep[];
  onStageSelect: (stage: LearningStage) => void;
}) {
  const currentStep = steps.find((step) => step.active);
  const progressRailRef = useRef<HTMLElement>(null);
  const nextLockedStep = steps.find((step) => step.availability === "locked");
  const currentStepRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    const progressRail = progressRailRef.current;
    const currentItem = currentStepRef.current;
    if (!progressRail || !currentItem || progressRail.scrollWidth <= progressRail.clientWidth) {
      return;
    }

    const railBounds = progressRail.getBoundingClientRect();
    const itemBounds = currentItem.getBoundingClientRect();
    const itemIsOutsideRail = itemBounds.left < railBounds.left || itemBounds.right > railBounds.right;
    if (!itemIsOutsideRail) {
      return;
    }

    const centeredLeft = itemBounds.left - railBounds.left + progressRail.scrollLeft
      + (itemBounds.width / 2) - (progressRail.clientWidth / 2);
    const maximumLeft = progressRail.scrollWidth - progressRail.clientWidth;
    const nextLeft = Math.max(0, Math.min(centeredLeft, maximumLeft));

    if (typeof progressRail.scrollTo === "function") {
      progressRail.scrollTo({ left: nextLeft });
      return;
    }
    progressRail.scrollLeft = nextLeft;
  }, [currentStep?.id]);

  return (
    <nav className="progress-stepper glass-surface" aria-label="Learning progress" ref={progressRailRef}>
      <ol>
        {steps.map((step, index) => {
          const content = (
            <>
              <span className="progress-stepper__number">{index + 1}</span>
              <span className="progress-stepper__label">{step.label}</span>
              <span className="sr-only">{STATE_LABELS[step.availability]}</span>
            </>
          );

          return (
            <li
              className={`progress-stepper__step progress-stepper__step--${step.availability}${step.active ? " progress-stepper__step--active" : ""}`}
              key={step.id}
              ref={step.active ? currentStepRef : undefined}
            >
              {step.availability === "locked" ? (
                <span aria-label={`${step.label}: ${STATE_LABELS[step.availability]}. ${step.prerequisite ?? ""}`}>{content}</span>
              ) : (
                <button
                  type="button"
                  aria-current={step.active ? "step" : undefined}
                  aria-label={`${step.label}: ${STATE_LABELS[step.availability]}`}
                  onClick={() => onStageSelect(step.id)}
                >
                  {content}
                </button>
              )}
            </li>
          );
        })}
      </ol>
      {nextLockedStep?.prerequisite && (
        <p className="progress-stepper__context"><strong>Locked next:</strong> {nextLockedStep.prerequisite}</p>
      )}
    </nav>
  );
}
