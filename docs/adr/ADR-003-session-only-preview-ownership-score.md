# ADR-003: Session-only Preview Ownership Score

## Status

Accepted

## Context

Phase 5 already introduced a temporary assessment score. Phase 8 aggregates
the current browser's assessment, verified-lab, security-challenge, and oral-
defense results into a demonstration-oriented summary. The application has no
accounts, persistence, signed result tokens, or cross-device progress.

## Decision

The frontend calculates a **Preview Ownership Score** from only the current
in-memory UI state. It displays the unrounded component breakdown and rounds
the non-negative total with `Math.round`. The oral-defense backend evaluates
only fresh repository evidence and the learner's answer; it never accepts the
prior assessment, lab, security, or requested total values.

The score is explicitly labelled as non-persistent, session-only, and not an
authenticated certification. A refresh, another browser, or another device
does not preserve or prove any result.

## Consequences

- The demo is small, transparent, and needs no database or authentication
  system.
- Browser-held prior results are useful for a current-session preview but are
  not trustworthy historical records.
- A future authenticated score would require separate server-authoritative
  result storage and product decisions; this preview must not be represented
  as that capability.
