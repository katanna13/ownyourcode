# ADR-004: Model Output Cannot Override Deterministic Evidence

- Status: Accepted
- Date: 2026-07-15

## Context

Phase 4 introduces a model-generated architecture-orientation lesson after a
public repository has been inspected. A structured response can enforce shape,
but it cannot prove that explanatory prose is accurate or that a cited fact
came from the inspected repository.

## Decision

The deterministic repository inspector remains the authority for repository
facts, evidence identifiers, and inspection limitations. The model receives a
bounded evidence catalog as untrusted input and may produce teaching prose,
questions, and citations only to catalog IDs. The API validates every required
citation after the model responds. Server-owned `inspection_limitations` are
copied from deterministic inspection and are never replaced by model output.

The fixed model behavior stays in trusted Responses API `instructions`.
Learner input and repository-controlled catalog values are serialized only in
the untrusted `input` field.

## Consequences

- Lessons are traceable to a small, deterministic catalog and explicitly retain
  inspection limits.
- Invalid, unknown, duplicated, unsafe, or colliding evidence identifiers
  cause the preview to be rejected rather than silently shown.
- This does not prove every sentence of model prose; later code-level learning
  features require their own deterministic verification.
