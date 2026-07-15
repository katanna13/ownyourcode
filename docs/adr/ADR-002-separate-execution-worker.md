# ADR-002: Separate Execution Worker

## Status

Accepted

## Context

OwnYourCode will eventually run learner code, tests, and security checks.
Those workloads may contain untrusted code and must not have access to the API
process, application secrets, or unrestricted network and filesystem access.

## Decision

When execution or scanning is implemented, it will run in a separately
isolated worker with strict resource and access limits. It will not run inside
the FastAPI process.

## Consequences

Phase 1 deliberately creates no worker service and exposes no execution or
scan endpoint. Future work must provide isolation, ephemeral workspaces,
network restrictions, and deterministic evidence before execution is enabled.
