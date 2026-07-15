# OwnYourCode

> **AI helped you build it. OwnYourCode helps you understand, secure, and defend it.**

OwnYourCode is an adaptive software-engineering learning platform for beginner and junior developers who use AI coding tools but do not yet fully understand the code they build.

The platform transforms an existing repository—or a new project idea—into a personalized learning path with lessons, code-tracing exercises, quizzes, verified coding labs, security challenges, and architecture oral defenses.

## The Problem

AI coding tools allow developers to build applications faster than ever, but many users ship code they cannot confidently explain, debug, secure, or scale.

This can lead to:

- hardcoded secrets and exposed `.env` files;
- insecure configurations;
- misunderstood code execution;
- deployment failures;
- vulnerable dependencies;
- architectural decisions the developer cannot defend;
- complete dependence on AI for every future change.

OwnYourCode turns AI-assisted development into an active learning process.

## How It Works

```text
Learn
  ↓
Predict
  ↓
Explain
  ↓
Apply
  ↓
Execute
  ↓
Verify
  ↓
Defend
  ↓
Adapt the next lesson
```

The model can teach and interpret, but only deterministic tests, code execution, and security scans can prove that a solution works.

## Planned MVP

### Understand My Repository

- Analyze a public GitHub repository
- Detect the stack, architecture, and important concepts
- Generate repository-grounded lessons
- Create code prediction and explain-back challenges
- Detect selected security and configuration risks
- Turn findings into guided learning exercises
- Verify coding labs with real execution and tests
- Track misconceptions and progress

### Build From Scratch

- Start from a project idea
- Define users, requirements, and core flows
- Learn architecture and technology choices
- Build the project through guided milestones
- Complete testing, security, and scaling challenges
- Defend the final architecture

### Ask & Learn

- Ask general software-engineering questions
- Apply concepts directly to the learner's project
- Receive adaptive explanations based on current progress

## What Makes It Different

A generic AI tutor answers questions.

OwnYourCode requires evidence that the learner understands:

- code-output prediction;
- line-by-line explanations;
- counterfactual questions;
- verified coding labs;
- security remediation;
- architecture trade-offs;
- scaling and reliability defenses.

## Ownership Score

Progress will be based on measurable evidence, including:

- correct code predictions;
- explanation quality;
- completed labs;
- tests passed;
- number of hints required;
- security findings understood and fixed;
- architecture decisions successfully defended.

The score will not be invented by the language model.

## Architecture

OwnYourCode uses a modular monolith with a separate isolated execution worker for running supported code, tests, and security checks.

See the full architecture document:

[docs/architecture.md](docs/architecture.md)

## Planned Technology Stack

### Frontend

- React
- TypeScript
- Monaco Editor

### Backend

- FastAPI
- PostgreSQL
- Pydantic
- SQLAlchemy

### AI

- OpenAI models for personalized learning, evaluation, and adaptive questioning
- Provider-agnostic LLM gateway
- Structured model outputs

### Verification

- Isolated execution worker
- Deterministic tests
- Security and configuration checks
- Reproducible demo repositories

## Project Status

Phase 5 adds a preview-only knowledge check after an architecture-orientation
lesson. It prepares three repository-evidence-grounded questions, grades the
multiple-choice and single-evidence answers deterministically, and makes one
bounded OpenAI Responses API request only to evaluate the learner's explain-back
answer. A recomputed context fingerprint detects stale inspection evidence;
deterministic inspection limitations remain server-owned. No project,
repository result, prompt, lesson, question, answer, or score is saved.

The following are intentionally not implemented: authentication, GitHub
repository cloning, code execution, security scanning, Ownership Score, demo
data, database models, or migrations. The New Project flow does not create a
project, project ID, or workspace.

## Initial Repository Structure

```text
ownyourcode/
├── docs/
│   └── architecture.md
├── README.md
├── .gitignore
└── .env.example
```

## Local Development

Prerequisite: Docker Desktop with Docker Compose v2.

In PowerShell, create your local development configuration and start the
services:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Verify the API and run the tests:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
docker compose exec api pytest
docker compose exec web npm run test -- --run
```

The frontend is available at `http://localhost:5173`; the FastAPI docs are at
`http://localhost:8000/docs`. Stop the stack with `docker compose down`.

## Environment Variables

Copy `.env.example` to `.env` and retain local values only. The API uses
`CORS_ORIGINS` for the browser allow-list and `VITE_API_BASE_URL` for the
browser's public API address. `GITHUB_TOKEN` is optional and backend-only: it
can improve GitHub API limits, but is never sent to the browser or returned by
the API. `OPENAI_API_KEY` and `OPENAI_MODEL` are backend-only and required only
for lesson generation; never expose them through Vite variables or commit them.

## Development Principles

- The learner must do the thinking.
- The model may teach, guide, and evaluate explanations.
- Tests and execution provide the final proof.
- Untrusted code must never run inside the main API process.
- Repository secrets must not be sent to the model.
- Roadmap features must not be presented as implemented.

## Built During OpenAI Build Week

OwnYourCode is being designed and developed during OpenAI Build Week.

Architecture, product scope, learning methodology, security boundaries, and implementation decisions are documented throughout the repository.

## Author

Mihai Catana
