# OwnYourCode — Product & Software Architecture

> **OwnYourCode turns AI-assisted coding into verified learning.**  
> It teaches students how to design, build, understand, secure, test, scale, and defend real software.

---

## 1. Product Vision

OwnYourCode is an interactive software-engineering learning platform for beginner and junior developers who build with AI but do not yet fully understand the code, architecture, security, or production behavior of what they ship.

The product is not a generic chatbot and it is not an autonomous coding agent. Its goal is to make the learner do the thinking:

**Learn → Predict → Explain → Apply → Execute → Verify → Defend → Adapt**

The system teaches before assessing, gives progressively stronger hints, executes code or tests where possible, checks real evidence, and adapts future lessons to the learner's misconceptions.

---

## 2. Main User

### Primary User

Beginner and junior developers who use AI coding tools to build applications but cannot yet confidently:

- explain the generated code;
- debug failures;
- identify security risks;
- justify architectural decisions;
- modify the project without copying another AI answer;
- explain how the system should change at scale.

### Secondary Users

- students and self-taught developers;
- hackathon participants;
- developers learning a new language or framework;
- teachers and mentors reviewing student progress.

The MVP is designed primarily for one learner working on one project at a time.

---

## 3. Core Product Modes

### Mode A — Understand My Repository

The learner connects a public GitHub repository or uploads a supported project archive.

OwnYourCode:

1. detects the languages, frameworks, folders, entry points, dependencies, APIs, database usage, and deployment configuration;
2. creates a project map and a concept map;
3. identifies likely learning gaps and security/configuration risks;
4. creates a personalized learning path;
5. teaches each concept using examples from the learner's own code;
6. gives quizzes, code-tracing questions, labs, and architecture defenses;
7. verifies code and test results;
8. updates the learner's ownership profile.

### Mode B — Build From Scratch

The learner starts with a product idea, such as a task manager, URL shortener, marketplace, or dating application.

OwnYourCode guides the learner through:

1. users and requirements;
2. core user flows;
3. data model;
4. architecture;
5. technology choices;
6. implementation tasks;
7. testing;
8. security;
9. deployment;
10. scale and reliability challenges;
11. final oral defense.

The application does not immediately generate the complete project. It provides assistance in levels:

**concept → question → hint → pseudocode → partial code → full example**

### Mode C — Ask & Learn

The learner can ask general or project-specific questions.

Two answer modes:

- **Explain generally** — teaches the concept independently of the repository.
- **Apply to my project** — grounds the explanation in files, functions, dependencies, and decisions from the learner's project.

---

## 4. Main Learning Loop

Every substantial learning unit follows the same loop.

### 4.1 Learn

The system explains one concept at the learner's current level.

Examples:

- Python indentation and scope;
- REST APIs;
- environment variables;
- database transactions;
- authentication versus authorization;
- Docker networking;
- caching;
- geospatial indexing;
- system design trade-offs.

### 4.2 Predict

The learner predicts:

- the output of a code snippet;
- the result of an API request;
- what will fail during deployment;
- how a component behaves under a changed condition.

### 4.3 Explain

The learner explains the reasoning in their own words.

The system does not award full credit for a lucky correct answer without a coherent explanation.

### 4.4 Apply

The learner modifies code, writes a test, fixes a configuration, or chooses an architectural approach.

### 4.5 Execute

A deterministic runner executes the supported code, tests, scans, or validation checks.

### 4.6 Verify

The application compares the learner's prediction and solution with real execution evidence.

### 4.7 Defend

The learner answers adaptive follow-up questions:

- Why did you choose this solution?
- What trade-off did you introduce?
- What breaks at one million users?
- Does Redis solve the actual bottleneck?
- What would an attacker try next?

### 4.8 Adapt

The system records misconceptions and chooses the next lesson or challenge.

---

## 5. Architecture Style

### Decision: Modular Monolith Plus an Isolated Execution Worker

The MVP uses one backend codebase divided into strict modules, rather than multiple microservices.

A separate worker handles code execution and security scans because untrusted code must not run inside the main API process.

### Why This Architecture

- fast enough to build during a hackathon;
- easier to test and deploy than microservices;
- clear module boundaries;
- one database and one source of truth;
- supports later extraction of heavy modules;
- isolates the highest-risk responsibility: code execution.

### High-Level Diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                       Web Application                        │
│ Dashboard · Lessons · Editor · Quiz · Progress · Chat       │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / JSON
┌──────────────────────────────▼──────────────────────────────┐
│                 API + Learning Orchestrator                  │
│                                                             │
│  Auth / Projects / Sessions / Learning workflow / Policies  │
└───────────────┬───────────────────┬─────────────────────────┘
                │                   │
        ┌───────▼────────┐   ┌──────▼─────────────────┐
        │ Repository     │   │ LLM Gateway            │
        │ Analyzer       │   │ OpenAI primary         │
        │ + Retrieval    │   │ Groq optional fallback │
        └───────┬────────┘   └──────┬─────────────────┘
                │                   │
        ┌───────▼───────────────────▼─────────────────┐
        │ Learning, Assessment & Progress Modules      │
        │ Lessons · Quizzes · Oral defense · Scoring   │
        └───────┬───────────────────────────────┬──────┘
                │                               │
        ┌───────▼────────────┐          ┌──────▼──────────────┐
        │ PostgreSQL         │          │ Job Queue           │
        │ users/projects/    │          │ execution requests  │
        │ attempts/progress  │          └──────┬──────────────┘
        └────────────────────┘                 │
                                      ┌────────▼──────────────┐
                                      │ Isolated Worker       │
                                      │ tests / run / scans   │
                                      │ strict limits         │
                                      └───────────────────────┘
```

---

## 6. Core Components

## 6.1 Web Application / Student Workspace

### Responsibilities

- onboarding and project selection;
- repository connection or project creation;
- project architecture map;
- lessons and concept cards;
- code editor;
- quizzes and explain-back answers;
- lab status and execution evidence;
- oral-defense chat;
- misconception map and progress dashboard.

### Input

- learner actions;
- code edits;
- answers;
- repository URL;
- project idea;
- selected learning goal.

### Output

- API requests;
- displayed lessons;
- editor changes;
- progress visualizations;
- test and scan evidence.

### Must Not Do

- execute arbitrary code directly in the normal browser thread;
- contain secret API keys;
- calculate authoritative learning scores;
- directly access GitHub tokens from client-side code.

---

## 6.2 API and Learning Orchestrator

### Responsibilities

- validates requests and permissions;
- owns the learning session state;
- chooses the next workflow step;
- calls the analyzer, LLM gateway, assessment engine, and worker;
- stores results;
- enforces business and security rules;
- exposes stable API contracts to the frontend.

### Input

- authenticated HTTP requests;
- analyzer output;
- model output;
- execution results;
- stored learner profile.

### Output

- structured lessons;
- quiz sessions;
- lab jobs;
- progress updates;
- error states.

### Must Not Do

- run untrusted repository code inside the API process;
- trust an LLM claim that code passed;
- send entire repositories or discovered secrets to the model.

---

## 6.3 Repository and Project Analyzer

### Responsibilities

- clones or reads an allowed repository snapshot;
- builds a file tree;
- detects languages, frameworks, package managers, entry points, databases, APIs, tests, containers, and deployment files;
- extracts code symbols and relevant snippets;
- identifies concepts that can become lessons;
- detects suspicious configurations and possible secrets;
- creates a compact repository profile for retrieval.

### MVP Support

Prioritize:

- Python;
- JavaScript and TypeScript;
- FastAPI;
- Flask;
- React;
- Node/Express;
- SQLite/PostgreSQL usage;
- Dockerfile and Compose;
- common environment-variable patterns.

### Output Example

```json
{
  "stack": ["Python", "FastAPI", "React", "SQLite", "Docker"],
  "entry_points": ["backend/api.py", "frontend/src/main.jsx"],
  "concepts": [
    "REST routing",
    "environment variables",
    "database concurrency",
    "CORS",
    "container networking"
  ],
  "findings": [
    {
      "type": "production_localhost",
      "file": "frontend/src/api.js",
      "line": 8,
      "severity": "medium"
    }
  ]
}
```

### Must Not Do

- execute repository code;
- modify the source repository;
- include binary files in the LLM context;
- expose detected secrets.

---

## 6.4 Learning and Assessment Engine

This is one product domain with several internal modules.

### Lesson Planner

Creates a learning path from:

- repository concepts;
- project goals;
- learner level;
- previous misconceptions;
- completed lessons.

### Lesson Generator

Creates concise explanations grounded in specific code spans and project decisions.

### Challenge Generator

Creates:

- output-prediction questions;
- explain-back prompts;
- counterfactual questions;
- architecture questions;
- security drills;
- coding labs.

### Response Evaluator

Evaluates free-form explanations using:

- a strict rubric;
- required concepts;
- contradiction checks;
- comparison with deterministic evidence;
- adaptive follow-up questions.

### Oral Defense Engine

Challenges shallow or memorized responses.

Example:

```text
Learner: "I would add Redis to solve SQLite scaling."
OwnYourCode: "Which workload does Redis reduce here? What happens
to concurrent writes and durable persistence?"
```

### Misconception Engine

Stores recurring learning gaps and selects future practice.

---

## 6.5 Isolated Sandbox and Verification Worker

### Responsibilities

- runs supported code snippets and tests;
- performs syntax/build checks;
- runs predefined security scans;
- applies strict time, memory, filesystem, and process limits;
- returns stdout, stderr, exit code, test summary, and scan results;
- destroys the workspace after the job.

### MVP Execution Strategy

Use two levels.

#### Level 1 — Safe Interactive Snippets

- Python snippets through a restricted runtime;
- JavaScript through an isolated worker/runtime;
- no network;
- short timeout;
- no filesystem outside the temporary workspace.

#### Level 2 — Predefined Repository Fixtures

For the hackathon demo, support complete execution for known demo repositories or supported templates. This keeps the public demo reliable and reproducible.

Arbitrary full-repository execution can remain a documented limitation until a hardened worker environment is ready.

### Worker Result

```json
{
  "status": "passed",
  "exit_code": 0,
  "tests_passed": 8,
  "tests_failed": 0,
  "duration_ms": 1840,
  "stdout": "...",
  "security_findings_after": 0
}
```

### Must Not Do

- receive production credentials;
- use the API server filesystem;
- allow unrestricted network access;
- run indefinitely;
- claim that a fix works without execution evidence.

---

## 6.6 Security Analysis Module

Security findings are transformed into learning exercises, not silently auto-fixed.

### MVP Checks

- hardcoded secrets and tokens;
- committed `.env` patterns;
- permissive CORS;
- production `localhost`;
- missing authentication on selected endpoints;
- vulnerable dependencies where scanner data is available;
- SQL injection patterns;
- command injection patterns;
- path traversal patterns;
- unsafe Docker configuration;
- containers running as root.

### Learning Workflow

```text
Detect
→ Explain the risk
→ Ask the learner to predict impact
→ Give a guided repair task
→ Re-run scan and tests
→ Ask the learner to defend the fix
```

The product must state clearly that it is an educational tool, not a replacement for a professional security audit.

---

## 6.7 LLM Gateway

### Purpose

Provides one controlled interface for all model calls.

### Providers

- OpenAI model as the primary submission/runtime provider;
- Groq/Llama as an optional development fallback;
- deterministic mock provider for tests.

### Responsibilities

- structured JSON output;
- prompt templates;
- provider switching;
- retries and timeouts;
- token limits;
- cache;
- redaction;
- model usage logging;
- validation before accepting output.

### Model Tasks

- personalized lesson generation;
- evaluation of explanations;
- adaptive follow-up questions;
- misconception diagnosis;
- architecture oral defense;
- project-plan generation;
- general and repository-grounded tutoring.

### Model Tasks That Are Forbidden

- claiming tests passed;
- calculating test counts;
- claiming a vulnerability is fixed without a rescan;
- directly executing code;
- receiving raw secrets;
- silently modifying a repository.

---

## 7. AI Versus Deterministic Responsibilities

| Responsibility | LLM | Deterministic system |
|---|---:|---:|
| Detect file tree and framework files | No | Yes |
| Generate a personalized explanation | Yes | Context preparation |
| Predict actual program output | Supporting only | Execution is authoritative |
| Evaluate a free-form explanation | Yes | Rubric and evidence checks |
| Execute code | No | Yes |
| Run tests | No | Yes |
| Detect known dependency vulnerabilities | No | Yes |
| Generate adaptive follow-up questions | Yes | Session rules |
| Verify that a patch builds | No | Yes |
| Calculate pass rate | No | Yes |
| Select the next topic | Yes | Progress constraints |
| Store progress | No | Yes |

The main design principle is:

> **The model can interpret and teach; only the system can prove.**

---

## 8. Evidence-Based Progress Model

The Ownership Score must not be a number invented by the model.

### Dimensions

- Code Execution Understanding — 20%
- Explanation Quality — 15%
- Verified Coding Labs — 25%
- Architecture Reasoning — 15%
- Security Awareness — 15%
- Debugging and Testing — 10%

### Evidence

#### Code Execution Understanding

- correct output predictions;
- correct control-flow explanations;
- performance on counterfactual variants.

#### Explanation Quality

- required concepts mentioned;
- contradictions avoided;
- ability to answer follow-up questions;
- no credit for correct answer without reasoning.

#### Verified Coding Labs

- build/test success;
- number of hints required;
- regressions introduced;
- independent completion.

#### Architecture Reasoning

- quality of trade-off analysis;
- ability to identify bottlenecks;
- response to scale and failure scenarios.

#### Security Awareness

- risks correctly explained;
- complete remediation steps;
- successful rescan;
- understanding that deleting a secret from the latest commit does not remove it from history.

### Example Calculation

```text
Code execution       80 × 0.20 = 16.0
Explanation          70 × 0.15 = 10.5
Verified labs        90 × 0.25 = 22.5
Architecture         60 × 0.15 =  9.0
Security             75 × 0.15 = 11.25
Debugging            70 × 0.10 =  7.0
--------------------------------------
Overall Ownership Score       = 76.25
```

The UI must show the evidence behind every score.

---

## 9. Main Data Model

### users

- id
- email
- display_name
- created_at

### projects

- id
- user_id
- mode: `existing_repo` or `build_from_scratch`
- name
- repository_url
- status
- created_at

### repository_snapshots

- id
- project_id
- commit_sha
- stack_profile
- file_manifest
- analysis_summary
- created_at

### concepts

- id
- key
- title
- category
- difficulty

### project_concepts

- project_id
- concept_id
- source_files
- relevance_score

### learning_paths

- id
- project_id
- learner_level
- goal
- current_step
- status

### learning_units

- id
- learning_path_id
- type: lesson, quiz, trace, lab, defense
- concept_id
- content
- rubric
- order_index

### attempts

- id
- user_id
- learning_unit_id
- answer
- score
- feedback
- hints_used
- created_at

### lab_runs

- id
- attempt_id
- status
- execution_summary
- tests_passed
- tests_failed
- duration_ms
- created_at

### security_findings

- id
- repository_snapshot_id
- finding_type
- severity
- file_path
- line_number
- status
- evidence

### misconception_events

- id
- user_id
- project_id
- concept_key
- evidence
- confidence
- resolved_at

### model_calls

- id
- project_id
- task_type
- provider
- model
- input_tokens
- output_tokens
- latency_ms
- cached
- created_at

Do not store repository secrets or unnecessary full file contents.

---

## 10. API Surface

### Authentication

```text
POST /auth/login
POST /auth/logout
GET  /auth/me
```

### Projects

```text
POST /projects
GET  /projects
GET  /projects/{project_id}
DELETE /projects/{project_id}
```

### Repository Analysis

```text
POST /projects/{project_id}/analyze
GET  /projects/{project_id}/analysis
GET  /projects/{project_id}/architecture-map
GET  /projects/{project_id}/security-findings
```

### Learning Paths

```text
POST /projects/{project_id}/learning-path
GET  /learning-paths/{path_id}
GET  /learning-paths/{path_id}/next
```

### Attempts and Evaluation

```text
POST /learning-units/{unit_id}/attempts
GET  /attempts/{attempt_id}
POST /attempts/{attempt_id}/follow-up
```

### Labs

```text
POST /labs/{lab_id}/run
GET  /lab-runs/{run_id}
```

### Tutor Chat

```text
POST /projects/{project_id}/chat
```

Request mode:

```json
{
  "mode": "general",
  "message": "Why does localhost fail after deployment?"
}
```

or:

```json
{
  "mode": "apply_to_project",
  "message": "Why does localhost fail after deployment?"
}
```

### Progress

```text
GET /projects/{project_id}/progress
GET /projects/{project_id}/misconceptions
```

---

## 11. Main User Flows

## 11.1 Existing Repository Flow

```text
User submits public repository URL
→ API validates host and limits
→ Analyzer creates repository profile
→ Redaction removes secret-like values
→ Security/configuration checks run
→ Project concepts are extracted
→ LLM generates a structured learning path
→ Learner completes first lesson
→ Learner predicts and explains a code path
→ Deterministic runner verifies execution
→ Learner completes a guided lab
→ Tests/scans verify the result
→ Oral defense challenges the reasoning
→ Progress and misconceptions are updated
```

## 11.2 Build-From-Scratch Flow

```text
User enters a product idea
→ Product coach asks for users and main problem
→ Learner defines the core flow
→ Architecture module teaches relevant choices
→ Learner selects and defends an architecture
→ System creates small implementation milestones
→ Each milestone includes lesson, lab, test, and defense
→ Final project receives a security and scale challenge
→ Learner completes a final oral defense
```

---

## 12. Failure Handling

### Invalid Repository

- reject unsupported or inaccessible URLs;
- show a clear reason;
- allow a demo repository fallback.

### Repository Too Large

- apply file/count/size limits;
- analyze selected folders;
- summarize instead of loading everything.

### Model Unavailable

- retry with backoff;
- use cached lesson where possible;
- provide deterministic analysis while clearly marking AI features unavailable.

### Worker Timeout

- mark run as timed out;
- keep logs up to the safe limit;
- explain what the learner can change;
- never block the API request indefinitely.

### Malicious Code

- do not execute arbitrary full repositories in the MVP;
- enforce sandbox limits;
- disable network;
- destroy the environment after execution;
- reject suspicious runtime requests.

### Database Unavailable

- return a stable service error;
- do not lose already submitted answers where client retry is safe;
- log correlation IDs.

### Invalid Model Output

- validate against a schema;
- reject and retry;
- never render unchecked model HTML or executable code automatically.

---

## 13. Security Boundaries

- GitHub credentials remain server-side.
- Only public repositories are supported in the first MVP unless OAuth is implemented safely.
- Secret-like strings are redacted before model calls.
- Untrusted code never runs in the API process.
- Execution jobs have CPU, memory, time, process, and output limits.
- Network access is disabled for execution by default.
- Workspaces are ephemeral.
- The worker cannot access application secrets.
- The application never pushes changes to GitHub automatically in the MVP.
- Learners review and apply changes themselves.
- Model output is treated as untrusted input.

---

## 14. Recommended Technology Stack

### Frontend

- React
- TypeScript
- Monaco Editor
- a diagram library for architecture and repository maps
- a small component library or custom design system

### Backend

- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL

### Background Work

- Redis-backed job queue or a minimal database-backed queue
- separate worker process

### Repository Analysis

- Git CLI or a safe Git library
- language and file detectors
- Tree-sitter for selected languages where needed
- Semgrep-style rules for code findings
- secret scanning rules
- dependency-file inspection

### AI

- provider-agnostic LLM gateway
- OpenAI primary for the submission
- Groq/Llama optional for development fallback
- structured outputs and cached calls

### Testing

- pytest for backend;
- frontend unit and component tests;
- Playwright for the critical end-to-end flow;
- fixture repositories containing known bugs and expected findings.

### Deployment

- one frontend/API service;
- one isolated worker service;
- managed PostgreSQL;
- managed Redis only if needed.

---

## 15. Repository Structure

```text
ownyourcode/
├── apps/
│   ├── web/
│   └── api/
├── worker/
│   ├── runner/
│   ├── scanners/
│   └── policies/
├── backend/
│   ├── auth/
│   ├── projects/
│   ├── repository_analysis/
│   ├── learning/
│   ├── assessment/
│   ├── progress/
│   ├── llm/
│   └── shared/
├── fixtures/
│   ├── vulnerable-fastapi-app/
│   └── broken-react-api-app/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── architecture.md
│   └── adr/
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 16. MVP Scope for the Hackathon

The MVP must demonstrate one complete and reliable learning journey.

### Required

1. Public GitHub repository analysis.
2. Stack and concept detection.
3. One personalized lesson grounded in repository code.
4. One code-tracing or output-prediction challenge.
5. One free-form explain-back evaluation.
6. One verified coding lab.
7. One security/configuration finding transformed into a lesson.
8. One architecture or scale-defense conversation.
9. Evidence-based progress score.
10. A reproducible demo repository.

### Strong Demo Fixtures

#### Broken React + FastAPI Deployment

Known issues:

- production localhost;
- missing environment variable;
- permissive CORS;
- incorrect health-check path;
- missing test.

#### Vulnerable Beginner Python API

Known issues:

- hardcoded secret;
- SQL injection;
- missing authentication;
- unsafe dependency or configuration.

### Not Required for the MVP

- private repository support;
- automatic GitHub pull requests;
- arbitrary language support;
- arbitrary full-repository execution;
- multiplayer classrooms;
- certificates;
- voice mode;
- microservices;
- autonomous code modification.

---

## 17. Reproducible Acceptance Criteria

The project is demo-ready only when an evaluator can:

1. open the live application;
2. select a public demo repository;
3. receive a real repository map;
4. see at least three detected concepts;
5. complete a lesson;
6. answer a code-tracing question;
7. submit an explanation and receive rubric-based feedback;
8. modify a code snippet in a lab;
9. run a deterministic test;
10. see a security/configuration finding disappear after a correct fix;
11. complete one architecture follow-up;
12. see the Ownership Score update with visible evidence.

No manual database edits or hidden preparation should be required during the demo.

---

## 18. Architectural Decision Records

Create these ADRs before implementation:

### ADR-001 — Modular Monolith

Why one backend codebase is better for the MVP than microservices.

### ADR-002 — Separate Execution Worker

Why untrusted code cannot run in the API process.

### ADR-003 — Evidence-Based Scoring

Why model-generated scores are insufficient.

### ADR-004 — Model Versus Deterministic Authority

Which conclusions require real execution evidence.

### ADR-005 — Limited Language Support

Why the MVP deliberately supports a small number of stacks well.

### ADR-006 — No Automatic Repository Writes

Why learners must review and apply their own changes.

---

## 19. Implementation Order

### Phase 1 — Product Skeleton

- project creation;
- demo repository selection;
- database models;
- stable API contracts;
- basic frontend flow.

### Phase 2 — Repository Analyzer

- file tree;
- stack detection;
- concept extraction;
- known configuration findings.

### Phase 3 — Learning Loop

- lesson generation;
- prediction;
- explain-back;
- rubric evaluation;
- misconception recording.

### Phase 4 — Verified Lab

- code editor;
- execution job;
- deterministic result;
- before/after evidence.

### Phase 5 — Architecture Defense and Scoring

- adaptive follow-up;
- scale scenario;
- evidence-based progress dashboard.

### Phase 6 — Hardening

- fixtures;
- end-to-end tests;
- error states;
- caching;
- deployment;
- README and demo video.

---

## 20. Is OwnYourCode Like DataCamp?

**Yes, at the interaction level—but not as a copy.**

DataCamp-style elements:

- short lessons;
- an embedded code editor;
- immediate exercises;
- quizzes;
- progress tracking;
- a structured learning path.

OwnYourCode's differentiation:

- the course can be generated from the learner's own repository;
- it teaches architecture, security, testing, deployment, and scale—not only syntax;
- it verifies execution and scans;
- it asks the learner to defend decisions;
- it tracks misconceptions rather than only lesson completion;
- it can guide a project from an empty repository to a defended architecture.

A simple positioning statement:

> **DataCamp teaches a curriculum. OwnYourCode turns your code and project ideas into the curriculum—and requires proof that you understand them.**

---

## 21. Final Product Statement

> **OwnYourCode is an adaptive software-engineering learning platform that transforms existing repositories and new project ideas into personalized lessons, code-tracing exercises, verified labs, security challenges, and architecture oral defenses. It helps AI-assisted developers prove they understand the software they build.**
