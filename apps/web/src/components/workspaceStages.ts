import {
  LEARNING_STAGE_ORDER,
  LessonResponse,
  ProjectPreviewResponse,
  RepositoryInspectionResponse,
  WorkspaceProgress,
  WorkspaceStage
} from "../types/workspace";

const STAGE_LABELS: Record<(typeof LEARNING_STAGE_ORDER)[number], string> = {
  inspect: "Inspect",
  learn: "Learn",
  assess: "Assess",
  lab: "Lab",
  secure: "Secure",
  defend: "Defend",
  score: "Score"
};

type StageInputs = {
  preview: ProjectPreviewResponse;
  inspection: RepositoryInspectionResponse | null;
  lesson: LessonResponse | null;
  progress: WorkspaceProgress;
};

export function deriveWorkspaceStages({
  preview,
  inspection,
  lesson,
  progress
}: StageInputs): WorkspaceStage[] {
  const existingRepository = preview.project.mode === "existing_repository" && Boolean(preview.project.repository_url);
  const inspected = Boolean(inspection);
  const learned = Boolean(lesson);
  const assessed = Boolean(progress.assessment);
  const labPassed = progress.verifiedLabPassed;
  const securityPassed = progress.securityChallengePassed;
  const defended = Boolean(progress.oralDefense);

  return [
    {
      id: "inspect",
      label: STAGE_LABELS.inspect,
      availability: inspected ? "complete" : existingRepository ? "available" : "locked",
      prerequisite: existingRepository ? undefined : "Use an existing public repository."
    },
    {
      id: "learn",
      label: STAGE_LABELS.learn,
      availability: learned ? "complete" : inspected ? "available" : "locked",
      prerequisite: "Inspect a public repository first."
    },
    {
      id: "assess",
      label: STAGE_LABELS.assess,
      availability: assessed ? "complete" : learned ? "available" : "locked",
      prerequisite: "Generate an evidence-grounded lesson first."
    },
    {
      id: "lab",
      label: STAGE_LABELS.lab,
      availability: labPassed ? "complete" : assessed ? "available" : "locked",
      prerequisite: "Complete the knowledge check first."
    },
    {
      id: "secure",
      label: STAGE_LABELS.secure,
      availability: securityPassed ? "complete" : labPassed ? "available" : "locked",
      prerequisite: "Pass the verified lab first."
    },
    {
      id: "defend",
      label: STAGE_LABELS.defend,
      availability: defended ? "complete" : securityPassed ? "available" : "locked",
      prerequisite: "Pass the security challenge first."
    },
    {
      id: "score",
      label: STAGE_LABELS.score,
      availability: defended ? "available" : "locked",
      prerequisite: "Complete the oral defense first."
    }
  ];
}

export function isStageSelectable(stage: WorkspaceStage): boolean {
  return stage.availability !== "locked";
}
