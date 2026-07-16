export type ProjectMode = "existing_repository" | "new_idea";
export type LearnerLevel = "beginner" | "junior" | "intermediate";

export const LEARNING_STAGE_ORDER = [
  "inspect",
  "learn",
  "assess",
  "lab",
  "secure",
  "defend",
  "score"
] as const;

export type LearningStage = (typeof LEARNING_STAGE_ORDER)[number];
export type StageAvailability = "locked" | "available" | "complete";

export type WorkspaceStage = {
  id: LearningStage;
  label: string;
  availability: StageAvailability;
  prerequisite?: string;
};

export type ProjectPreviewResponse = {
  validated: boolean;
  persisted: boolean;
  message: string;
  project: {
    name: string;
    description: string;
    mode: ProjectMode;
    repository_url: string | null;
  };
};

export type RepositoryInspectionResponse = {
  persisted: boolean;
  message: string;
  repository: {
    name: string;
    full_name: string;
    description: string | null;
    default_branch: string;
    primary_language: string | null;
    html_url: string;
  };
  languages: Array<{ name: string; bytes: number }>;
  technologies: Array<{ key: string; label: string; evidence: string[] }>;
  paths: { inspected_count: number; returned: string[]; truncated: boolean };
  important_files: Array<{ path: string; kind: string }>;
  limitations: string[];
};

export type EvidenceItem = {
  id: string;
  kind: string;
  label: string;
  detail: string;
};

export type LessonResponse = {
  persisted: boolean;
  message: string;
  inspection_limitations: string[];
  evidence_catalog: EvidenceItem[];
  lesson: {
    title: string;
    learning_objective: string;
    repository_summary: string;
    repository_summary_evidence_ids: string[];
    concepts: Array<{
      title: string;
      explanation: string;
      why_it_matters: string;
      evidence_ids: string[];
      reflection_question: string;
    }>;
    architecture_walkthrough: Array<{ step: string; evidence_ids: string[] }>;
    knowledge_check_questions: string[];
    limitations_and_open_questions: string[];
  };
};

export type AssessmentSummary = {
  earned_points: number;
  total_points: number;
};

export type OralDefenseSummary = {
  earned_points: number;
  max_points: number;
};

export type WorkspaceProgress = {
  assessment: AssessmentSummary | null;
  verifiedLabPassed: boolean;
  securityChallengePassed: boolean;
  oralDefense: OralDefenseSummary | null;
};

export type WorkspaceProgressReporter = {
  reportAssessment: (summary: AssessmentSummary | null) => void;
  reportVerifiedLab: (passed: boolean) => void;
  reportSecurityChallenge: (passed: boolean) => void;
  reportOralDefense: (summary: OralDefenseSummary | null) => void;
};
