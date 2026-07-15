# ADR-001: Modular Monolith

## Status

Accepted

## Context

OwnYourCode needs a small, reliable MVP while preserving clear boundaries for
future product domains such as projects, repository analysis, learning, and
progress.

## Decision

Use one FastAPI backend codebase with explicit domain modules. The frontend,
API, and PostgreSQL database run as separate local Compose services, but the
backend does not split ordinary product domains into independently deployed
services.

## Consequences

The MVP has one backend deployment and one source of truth, which reduces
operational overhead and makes tests and local development straightforward.
Module boundaries must remain deliberate so that a future high-cost or
high-risk responsibility can be extracted without spreading its logic across
the application.
