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

This project is currently under active development for OpenAI Build Week.

The README will be updated as features become implemented and verified.

## Current Repository Structure

```text
ownyourcode/
├── docs/
│   └── architecture.md
├── README.md
├── .gitignore
└── .env.example
```

## Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Then add the required local values.

```env
OPENAI_API_KEY=
DATABASE_URL=
GITHUB_TOKEN=
```

Never commit the real `.env` file.

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
