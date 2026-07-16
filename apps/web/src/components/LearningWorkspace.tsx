import { ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { AssessmentPanel } from "./AssessmentPanel";
import { EvidenceChip } from "./EvidenceChip";
import { OralDefensePanel } from "./OralDefensePanel";
import { PreviewOwnershipScorePanel } from "./PreviewOwnershipScorePanel";
import { ProgressStep, ProgressStepper } from "./ProgressStepper";
import { SecurityChallengePanel } from "./SecurityChallengePanel";
import { StatusBadge } from "./StatusBadge";
import { VerifiedLabPanel } from "./VerifiedLabPanel";
import { scrollWorkspaceStageIntoView } from "./workspaceStageNavigation";
import { deriveWorkspaceStages, isStageSelectable } from "./workspaceStages";
import {
  EvidenceItem,
  LEARNING_STAGE_ORDER,
  LearnerLevel,
  LearningStage,
  LessonResponse,
  ProjectPreviewResponse,
  RepositoryInspectionResponse,
  WorkspaceProgress,
  WorkspaceProgressReporter
} from "../types/workspace";

type LearningWorkspaceProps = {
  preview: ProjectPreviewResponse | null;
  inspection: RepositoryInspectionResponse | null;
  lesson: LessonResponse | null;
  learnerLevel: LearnerLevel;
  learningGoal: string;
  isInspecting: boolean;
  inspectionErrors: string[];
  isGeneratingLesson: boolean;
  lessonErrors: string[];
  onInspectRepository: () => void;
  onLearnerLevelChange: (level: LearnerLevel) => void;
  onLearningGoalChange: (goal: string) => void;
  onGenerateLesson: () => void;
  stageScroller?: (stageRegion: HTMLElement) => void;
};

const EMPTY_PROGRESS: WorkspaceProgress = {
  assessment: null,
  verifiedLabPassed: false,
  securityChallengePassed: false,
  oralDefense: null
};

const STAGE_TITLES: Record<LearningStage, string> = {
  inspect: "Inspect repository",
  learn: "Learn the architecture",
  assess: "Check your understanding",
  lab: "Practice with a verified lab",
  secure: "Secure the teaching fixture",
  defend: "Defend your reasoning",
  score: "Review your Preview Ownership Score"
};

function ErrorPanel({ title, messages }: { title: string; messages: string[] }) {
  if (messages.length === 0) {
    return null;
  }

  return (
    <section className="message message--error" role="alert">
      <h3>{title}</h3>
      <ul>{messages.map((message) => <li key={message}>{message}</li>)}</ul>
    </section>
  );
}

function EvidenceReferences({
  evidenceIds,
  evidenceById
}: {
  evidenceIds: string[];
  evidenceById: Map<string, EvidenceItem>;
}) {
  return (
    <ul className="evidence-list" aria-label="Evidence references">
      {evidenceIds.map((evidenceId) => {
        const evidence = evidenceById.get(evidenceId);
        return <EvidenceChip id={evidenceId} key={evidenceId} label={evidence?.label ?? evidenceId} />;
      })}
    </ul>
  );
}

function retainStagesThrough(stage: LearningStage): Set<LearningStage> {
  const lastIndex = LEARNING_STAGE_ORDER.indexOf(stage);
  return new Set(LEARNING_STAGE_ORDER.slice(0, lastIndex + 1));
}

function StageFrame({
  stage,
  active,
  mounted,
  animated,
  stageRef,
  headingRef,
  children
}: {
  stage: LearningStage;
  active: boolean;
  mounted: boolean;
  animated: boolean;
  stageRef: (element: HTMLElement | null) => void;
  headingRef: (element: HTMLHeadingElement | null) => void;
  children: ReactNode;
}) {
  if (!mounted) {
    return null;
  }

  const headingId = `${stage}-stage-title`;
  return (
    <section
      className="workspace__stage"
      data-stage={stage}
      data-explicit-navigation={active && animated ? "true" : undefined}
      hidden={!active}
      aria-labelledby={headingId}
      ref={stageRef}
    >
      <header className="workspace__stage-heading">
        <p className="eyebrow">Learning activity</p>
        <h2 id={headingId} ref={headingRef} tabIndex={-1}>{STAGE_TITLES[stage]}</h2>
      </header>
      {children}
    </section>
  );
}

function StageActions({
  back,
  backLabel,
  continueTo,
  continueLabel,
  onStageSelect
}: {
  back?: LearningStage;
  backLabel?: string;
  continueTo?: LearningStage;
  continueLabel?: string;
  onStageSelect: (stage: LearningStage) => void;
}) {
  if (!back && !continueTo) {
    return null;
  }

  return (
    <nav className="workspace__stage-actions" aria-label="Stage navigation">
      {back && (
        <button className="button button--secondary" type="button" onClick={() => onStageSelect(back)}>
          {backLabel ?? "Back"}
        </button>
      )}
      {continueTo && (
        <button className="button" type="button" onClick={() => onStageSelect(continueTo)}>
          {continueLabel ?? "Continue"}
        </button>
      )}
    </nav>
  );
}

function RepositoryLink({
  displayName,
  href
}: {
  displayName: string;
  href: string;
}) {
  return (
    <a className="repository-link" href={href} aria-label={`Repository ${displayName}. Full URL: ${href}`}>
      {displayName}
    </a>
  );
}

export function LearningWorkspace({
  preview,
  inspection,
  lesson,
  learnerLevel,
  learningGoal,
  isInspecting,
  inspectionErrors,
  isGeneratingLesson,
  lessonErrors,
  onInspectRepository,
  onLearnerLevelChange,
  onLearningGoalChange,
  onGenerateLesson,
  stageScroller = scrollWorkspaceStageIntoView
}: LearningWorkspaceProps) {
  const [progress, setProgress] = useState<WorkspaceProgress>(EMPTY_PROGRESS);
  const [activeStage, setActiveStage] = useState<LearningStage>("inspect");
  const [mountedStages, setMountedStages] = useState<Set<LearningStage>>(() => new Set(["inspect"]));
  const [animatedStage, setAnimatedStage] = useState<LearningStage | null>(null);
  const [lessonVersion, setLessonVersion] = useState(0);
  const [explicitNavigationVersion, setExplicitNavigationVersion] = useState(0);
  const stageRefs = useRef<Partial<Record<LearningStage, HTMLElement | null>>>({});
  const headingRefs = useRef<Partial<Record<LearningStage, HTMLHeadingElement | null>>>({});
  const explicitNavigationStage = useRef<LearningStage | null>(null);
  const previousLabPassed = useRef(progress.verifiedLabPassed);
  const previousSecurityPassed = useRef(progress.securityChallengePassed);
  const previousContext = useRef({
    repositoryUrl: preview?.project.repository_url ?? null,
    learnerLevel,
    inspection,
    lesson
  });
  const repositoryUrl = preview?.project.repository_url;
  const evidenceById = useMemo(
    () => new Map(lesson?.evidence_catalog.map((item) => [item.id, item]) ?? []),
    [lesson]
  );

  const progressReporter = useMemo<WorkspaceProgressReporter>(() => ({
    reportAssessment: (assessment) => setProgress((current) => ({ ...current, assessment })),
    reportVerifiedLab: (verifiedLabPassed) => setProgress((current) => ({ ...current, verifiedLabPassed })),
    reportSecurityChallenge: (securityChallengePassed) => setProgress((current) => ({ ...current, securityChallengePassed })),
    reportOralDefense: (oralDefense) => setProgress((current) => ({ ...current, oralDefense }))
  }), []);

  useEffect(() => {
    const previous = previousContext.current;
    const repositoryChanged = previous.repositoryUrl !== (preview?.project.repository_url ?? null);
    const learnerLevelChanged = previous.learnerLevel !== learnerLevel;
    const inspectionWasCleared = previous.inspection !== null && inspection === null;
    const lessonChanged = previous.lesson !== lesson;

    if (repositoryChanged || inspectionWasCleared) {
      previousLabPassed.current = false;
      previousSecurityPassed.current = false;
      setProgress(EMPTY_PROGRESS);
      setMountedStages(new Set(["inspect"]));
      setActiveStage("inspect");
      setAnimatedStage(null);
    } else if (learnerLevelChanged && inspection) {
      previousLabPassed.current = false;
      previousSecurityPassed.current = false;
      setProgress(EMPTY_PROGRESS);
      setMountedStages(retainStagesThrough("learn"));
      setActiveStage("learn");
      setAnimatedStage(null);
    } else if (lessonChanged) {
      setLessonVersion((current) => current + 1);
      previousLabPassed.current = false;
      previousSecurityPassed.current = false;
      setProgress(EMPTY_PROGRESS);
      if (previous.lesson !== null) {
        setMountedStages(retainStagesThrough("learn"));
        setActiveStage("learn");
        setAnimatedStage(null);
      }
    }

    previousContext.current = {
      repositoryUrl: preview?.project.repository_url ?? null,
      learnerLevel,
      inspection,
      lesson
    };
  }, [inspection, learnerLevel, lesson, preview?.project.repository_url]);

  useEffect(() => {
    if (previousLabPassed.current && !progress.verifiedLabPassed) {
      previousSecurityPassed.current = false;
      setProgress((current) => ({
        ...current,
        securityChallengePassed: false,
        oralDefense: null
      }));
      setMountedStages(retainStagesThrough("lab"));
    }
    previousLabPassed.current = progress.verifiedLabPassed;
  }, [progress.verifiedLabPassed]);

  useEffect(() => {
    if (previousSecurityPassed.current && !progress.securityChallengePassed) {
      setProgress((current) => ({ ...current, oralDefense: null }));
      setMountedStages(retainStagesThrough("secure"));
    }
    previousSecurityPassed.current = progress.securityChallengePassed;
  }, [progress.securityChallengePassed]);

  useEffect(() => {
    const stageToPosition = explicitNavigationStage.current;
    if (!stageToPosition || stageToPosition !== activeStage) {
      return;
    }
    const stageRegion = stageRefs.current[stageToPosition];
    if (!stageRegion) {
      return;
    }

    stageScroller(stageRegion);
    headingRefs.current[stageToPosition]?.focus({ preventScroll: true });
    explicitNavigationStage.current = null;
  }, [activeStage, explicitNavigationVersion, stageScroller]);

  if (!preview) {
    return null;
  }

  const isExistingRepository = preview.project.mode === "existing_repository" && Boolean(repositoryUrl);
  if (!isExistingRepository || !repositoryUrl) {
    return (
      <section className="workspace" aria-label="OwnYourCode learning workspace">
        <section className="workspace__preview" aria-labelledby="validated-preview-title" role="status">
          <p className="eyebrow">Project setup</p>
          <h2 id="validated-preview-title">Validated preview</h2>
          <p>{preview.message}</p>
          <dl>
            <dt>Name</dt><dd>{preview.project.name}</dd>
            <dt>Mode</dt><dd>New idea</dd>
          </dl>
        </section>
      </section>
    );
  }

  const stages = deriveWorkspaceStages({ preview, inspection, lesson, progress });
  const steps: ProgressStep[] = stages.map((stage) => ({ ...stage, active: stage.id === activeStage }));
  const activeStageDefinition = stages.find((stage) => stage.id === activeStage);
  const activeStageTone = activeStageDefinition?.availability === "complete"
    ? "confirmed"
    : activeStageDefinition?.availability === "available"
      ? "current"
      : "locked";
  const sidebarEvidence = lesson?.evidence_catalog.slice(0, 3) ?? [];
  const currentLimitations = lesson?.inspection_limitations ?? inspection?.limitations ?? [];
  const repositoryName = inspection?.repository.full_name ?? repositoryUrl.replace(/^https:\/\/github\.com\//i, "");
  const repositoryHref = inspection?.repository.html_url ?? repositoryUrl;
  const reviewableStages = LEARNING_STAGE_ORDER.filter((stage) => (
    stage !== "score" && mountedStages.has(stage) && stages.some((item) => item.id === stage && item.availability !== "locked")
  ));

  function selectStage(stage: LearningStage) {
    const selected = stages.find((item) => item.id === stage);
    if (!selected || !isStageSelectable(selected)) {
      return;
    }
    explicitNavigationStage.current = stage;
    setMountedStages((current) => new Set([...current, stage]));
    setAnimatedStage(stage);
    setActiveStage(stage);
    setExplicitNavigationVersion((current) => current + 1);
  }

  function stageRef(stage: LearningStage) {
    return (element: HTMLElement | null) => {
      stageRefs.current[stage] = element;
    };
  }

  function headingRef(stage: LearningStage) {
    return (element: HTMLHeadingElement | null) => {
      headingRefs.current[stage] = element;
    };
  }

  return (
    <section className="workspace" aria-label="OwnYourCode learning workspace">
      <header className="workspace__header glass-surface">
        <div>
          <p className="product-wordmark">OwnYourCode</p>
          <p className="workspace__value">Learn how this repository is organized, then verify and defend your understanding.</p>
        </div>
        <ul className="workspace__context" aria-label="Current repository context">
          <li><RepositoryLink displayName={repositoryName} href={repositoryHref} /></li>
          <li>Learner level: {learnerLevel}</li>
          <li>Session-only preview</li>
        </ul>
      </header>

      <ProgressStepper steps={steps} onStageSelect={selectStage} />

      <div className="workspace__grid">
        <div className="workspace__main">
          <StageFrame
            stage="inspect"
            active={activeStage === "inspect"}
            mounted={mountedStages.has("inspect")}
            animated={animatedStage === "inspect"}
            stageRef={stageRef("inspect")}
            headingRef={headingRef("inspect")}
          >
            <section className="workspace__preview" aria-labelledby="validated-preview-title" role="status">
              <p className="eyebrow">Project setup</p>
              <h3 id="validated-preview-title">Validated preview</h3>
              <p>{preview.message}</p>
              <dl>
                <dt>Name</dt><dd>{preview.project.name}</dd>
                <dt>Mode</dt><dd>Existing repository</dd>
                <dt>Repository</dt><dd><RepositoryLink displayName={repositoryName} href={repositoryHref} /></dd>
              </dl>
            </section>

            <section className="inspection activity-card" aria-labelledby="inspection-title">
              <p className="eyebrow">Bounded repository inspection</p>
              <h3 id="inspection-title">Repository inspection</h3>
              {!inspection && <p>Inspect public repository metadata and a bounded, deterministic evidence set before making claims about its stack.</p>}
              {!inspection && (
                <button className="button" type="button" onClick={onInspectRepository} disabled={isInspecting}>
                  {isInspecting ? "Inspecting repository..." : "Inspect repository"}
                </button>
              )}
              <ErrorPanel title="Repository inspection could not finish" messages={inspectionErrors} />

              {inspection && (
                <>
                  <div className="inspection__overview">
                    <h3>Architecture summary</h3>
                    <p>{inspection.message}</p>
                    <dl>
                      <dt>Repository</dt><dd><RepositoryLink displayName={inspection.repository.full_name} href={inspection.repository.html_url} /></dd>
                      <dt>Default branch</dt><dd>{inspection.repository.default_branch}</dd>
                      <dt>Primary language</dt><dd>{inspection.repository.primary_language ?? "Not reported"}</dd>
                      <dt>Path coverage</dt><dd>Inspected {inspection.paths.inspected_count} paths{inspection.paths.truncated ? "; path results were truncated." : "."}</dd>
                    </dl>
                  </div>

                  <div className="inspection__split">
                    <section aria-labelledby="technology-title">
                      <h3 id="technology-title">Confirmed technologies</h3>
                      <ul className="technology-chip-list">
                        {inspection.technologies.map((technology) => <li key={technology.key}>{technology.label}</li>)}
                      </ul>
                      <ul className="technology-list">
                        {inspection.technologies.map((technology) => <li key={`${technology.key}-evidence`}><strong>Detection evidence</strong><ul>{technology.evidence.map((evidence) => <li key={evidence}>{evidence}</li>)}</ul></li>)}
                      </ul>
                    </section>
                    <section aria-labelledby="manifest-title">
                      <h3 id="manifest-title">Languages and important files</h3>
                      <ul className="manifest-list">
                        {inspection.languages.map((language) => <li key={language.name}><code>{language.name}</code> — {language.bytes} bytes reported</li>)}
                        {inspection.important_files.map((file) => <li key={file.path}><code>{file.path}</code> — {file.kind}</li>)}
                      </ul>
                    </section>
                  </div>

                  <section className="limitations-panel" aria-labelledby="inspection-limitations-title">
                    <h3 id="inspection-limitations-title">Inspection limitations</h3>
                    <ul>{inspection.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
                  </section>
                </>
              )}
            </section>
            {inspection && (
              <StageActions
                continueTo="learn"
                continueLabel="Continue to lesson"
                onStageSelect={selectStage}
              />
            )}
          </StageFrame>

          <StageFrame
            stage="learn"
            active={activeStage === "learn"}
            mounted={mountedStages.has("learn")}
            animated={animatedStage === "learn"}
            stageRef={stageRef("learn")}
            headingRef={headingRef("learn")}
          >
            <section className="lesson-controls activity-card" aria-labelledby="lesson-controls-title">
              <p className="eyebrow">Evidence-grounded lesson</p>
              <h3 id="lesson-controls-title">Generate your first lesson</h3>
              <p>This creates a teaching preview from bounded inspection evidence. Deterministic evidence remains the authority; nothing is saved.</p>
              <label className="field" htmlFor="learner-level">
                Learner level
                <select id="learner-level" value={learnerLevel} onChange={(event) => onLearnerLevelChange(event.target.value as LearnerLevel)}>
                  <option value="beginner">Beginner</option>
                  <option value="junior">Junior</option>
                  <option value="intermediate">Intermediate</option>
                </select>
              </label>
              <label className="field" htmlFor="learning-goal">
                Learning goal (optional)
                <textarea id="learning-goal" value={learningGoal} onChange={(event) => onLearningGoalChange(event.target.value)} maxLength={240} />
              </label>
              <button className="button" type="button" onClick={onGenerateLesson} disabled={isGeneratingLesson}>
                {isGeneratingLesson ? "Generating lesson..." : lesson ? "Generate replacement lesson" : "Generate first lesson"}
              </button>
              <ErrorPanel title="Lesson generation could not finish" messages={lessonErrors} />
            </section>

            {lesson && (
              <section className="lesson" aria-labelledby="lesson-title">
                <header className="lesson__orientation">
                  <p className="eyebrow">Architecture orientation</p>
                  <h3 id="lesson-title">{lesson.lesson.title}</h3>
                  <p>{lesson.message}</p>
                  <p className="lesson__metadata"><span>Bounded inspection evidence</span><span>Teaching preview</span><span>Not persisted</span></p>
                  <p className="lesson__authority">The model explains this bounded catalog; deterministic evidence and inspection limitations remain the authority.</p>
                  <h4>Learning objective</h4>
                  <p>{lesson.lesson.learning_objective}</p>
                  <h4>Repository summary</h4>
                  <p>{lesson.lesson.repository_summary}</p>
                  <EvidenceReferences evidenceById={evidenceById} evidenceIds={lesson.lesson.repository_summary_evidence_ids} />
                </header>

                <section className="lesson__section" aria-labelledby="concepts-title">
                  <h3 id="concepts-title">Concepts to orient yourself</h3>
                  {lesson.lesson.concepts.map((concept) => (
                    <article className="lesson__concept" key={concept.title}>
                      <h4>{concept.title}</h4>
                      <p>{concept.explanation}</p>
                      <p><strong>Why it matters:</strong> {concept.why_it_matters}</p>
                      <EvidenceReferences evidenceById={evidenceById} evidenceIds={concept.evidence_ids} />
                      <p className="lesson__reflection"><strong>Reflect:</strong> {concept.reflection_question}</p>
                    </article>
                  ))}
                </section>

                <section className="lesson__section" aria-labelledby="walkthrough-title">
                  <h3 id="walkthrough-title">Architecture walkthrough</h3>
                  <ol className="walkthrough-list">
                    {lesson.lesson.architecture_walkthrough.map((step, index) => <li key={`${index}-${step.step}`}><p>{step.step}</p><EvidenceReferences evidenceById={evidenceById} evidenceIds={step.evidence_ids} /></li>)}
                  </ol>
                </section>

                <section className="lesson__section" aria-labelledby="knowledge-check-title">
                  <h3 id="knowledge-check-title">Before the knowledge check</h3>
                  <ol>{lesson.lesson.knowledge_check_questions.map((question) => <li key={question}>{question}</li>)}</ol>
                </section>

                <section className="limitations-panel" aria-labelledby="lesson-limitations-title">
                  <h3 id="lesson-limitations-title">What remains uncertain</h3>
                  <h4>Inspection limitations (deterministic)</h4>
                  <ul>{lesson.inspection_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
                  <h4>Lesson limitations and open questions</h4>
                  <ul>{lesson.lesson.limitations_and_open_questions.map((item) => <li key={item}>{item}</li>)}</ul>
                </section>
              </section>
            )}
            <StageActions
              back="inspect"
              backLabel="Back to inspection"
              continueTo={lesson ? "assess" : undefined}
              continueLabel="Check my understanding"
              onStageSelect={selectStage}
            />
          </StageFrame>

          <StageFrame
            stage="assess"
            active={activeStage === "assess"}
            mounted={mountedStages.has("assess")}
            animated={animatedStage === "assess"}
            stageRef={stageRef("assess")}
            headingRef={headingRef("assess")}
          >
            <AssessmentPanel
              repositoryUrl={repositoryUrl}
              learnerLevel={learnerLevel}
              lessonReady={Boolean(lesson)}
              assessmentContextVersion={lessonVersion}
              progressReporter={progressReporter}
            />
            <StageActions
              back="learn"
              backLabel="Back to lesson"
              continueTo={progress.assessment ? "lab" : undefined}
              continueLabel="Continue to lab"
              onStageSelect={selectStage}
            />
          </StageFrame>

          <StageFrame
            stage="lab"
            active={activeStage === "lab"}
            mounted={mountedStages.has("lab")}
            animated={animatedStage === "lab"}
            stageRef={stageRef("lab")}
            headingRef={headingRef("lab")}
          >
            <VerifiedLabPanel
              repositoryUrl={repositoryUrl}
              learnerLevel={learnerLevel}
              assessmentReady={Boolean(progress.assessment)}
              progressReporter={progressReporter}
            />
            <StageActions
              back="assess"
              backLabel="Back to assessment"
              continueTo={progress.verifiedLabPassed ? "secure" : undefined}
              continueLabel="Continue to security challenge"
              onStageSelect={selectStage}
            />
          </StageFrame>

          <StageFrame
            stage="secure"
            active={activeStage === "secure"}
            mounted={mountedStages.has("secure")}
            animated={animatedStage === "secure"}
            stageRef={stageRef("secure")}
            headingRef={headingRef("secure")}
          >
            <SecurityChallengePanel
              repositoryUrl={repositoryUrl}
              learnerLevel={learnerLevel}
              verifiedLabPassed={progress.verifiedLabPassed}
              progressReporter={progressReporter}
            />
            <StageActions
              back="lab"
              backLabel="Back to lab"
              continueTo={progress.securityChallengePassed ? "defend" : undefined}
              continueLabel="Continue to oral defense"
              onStageSelect={selectStage}
            />
          </StageFrame>

          <StageFrame
            stage="defend"
            active={activeStage === "defend"}
            mounted={mountedStages.has("defend")}
            animated={animatedStage === "defend"}
            stageRef={stageRef("defend")}
            headingRef={headingRef("defend")}
          >
            <OralDefensePanel
              repositoryUrl={repositoryUrl}
              learnerLevel={learnerLevel}
              verifiedLabPassed={progress.verifiedLabPassed}
              securityChallengePassed={progress.securityChallengePassed}
              progressReporter={progressReporter}
            />
            <StageActions
              back="secure"
              backLabel="Back to security challenge"
              continueTo={progress.oralDefense ? "score" : undefined}
              continueLabel="Review Preview Ownership Score"
              onStageSelect={selectStage}
            />
          </StageFrame>

          <StageFrame
            stage="score"
            active={activeStage === "score"}
            mounted={mountedStages.has("score")}
            animated={animatedStage === "score"}
            stageRef={stageRef("score")}
            headingRef={headingRef("score")}
          >
            <PreviewOwnershipScorePanel
              progress={progress}
              reviewableStages={reviewableStages}
              onReviewStage={selectStage}
            />
          </StageFrame>
        </div>

        <aside className="workspace__sidebar glass-surface" aria-label="Repository learning context">
          <section className="context-summary">
            <h2>Repository context</h2>
            <RepositoryLink displayName={repositoryName} href={repositoryHref} />
            <p className="repository-url">{repositoryHref}</p>
            <p>Learner level: {learnerLevel}</p>
          </section>
          <section className="context-summary">
            <h3>Current stage</h3>
            <StatusBadge tone={activeStageTone}>{activeStageDefinition?.label ?? "Inspect"}</StatusBadge>
            <p>{activeStageDefinition?.prerequisite ?? "Progress reflects only this browser session."}</p>
          </section>
          {sidebarEvidence.length > 0 && (
            <section className="context-summary">
              <h3>Confirmed evidence</h3>
              <ul>{sidebarEvidence.map((evidence) => <li key={evidence.id}>{evidence.label}<br /><code>{evidence.id}</code></li>)}</ul>
            </section>
          )}
          {currentLimitations.length > 0 && (
            <section className="context-summary">
              <h3>Current limitations</h3>
              <ul>{currentLimitations.slice(0, 3).map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
            </section>
          )}
        </aside>
      </div>
    </section>
  );
}
