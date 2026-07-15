# ADR-005: Limited Language Support

## Status

Accepted

## Context

Repository inspection begins with public GitHub metadata and a small,
bounded set of manifest files. The product must make useful, explainable
observations without cloning repositories, downloading source trees, or
claiming support it cannot verify.

## Decision

Phase 3 supports deterministic evidence for Python, FastAPI, Flask, Django,
Node.js, React, Vite, Next.js, TypeScript, Docker, pytest, Vitest, and GitHub
Actions. It parses only `package.json`, `pyproject.toml`, `Pipfile`, and
`requirements.txt`, subject to explicit path and byte limits.

## Consequences

The preview is predictable, safe to bound, and straightforward to test. It is
not a full repository analysis: unsupported stacks and frameworks can be
absent from the result. Support for another technology requires a deliberate
rule, trustworthy evidence, and tests before it is added.
