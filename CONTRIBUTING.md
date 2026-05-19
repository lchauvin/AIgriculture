# Contributing to AIgriculture

This is a single-author portfolio project at the moment, but it is written
as if a team will join — meaning the disciplines below are real.

## Core disciplines

### 1. Research before code

We do not write implementation files for any modeling concept until the
corresponding **research document** exists in `docs/research/` and the
relevant **Architecture Decision Record (ADR)** has been written in
`docs/decisions/`.

- Decisions are captured in ADRs (one Markdown file per decision, dated,
  numbered, never rewritten — superseded by a new ADR if revisited).
- Exploratory work happens in `backend/notebooks/exploratory/` and is not a
  load-bearing artifact.

### 2. Cite and verify

Every factual claim in `docs/research/*.md` — dataset resolutions, paper
findings, license terms, model behaviors — resolves to a BibTeX entry in
`CITATIONS.bib`. Inline cites use `[@bibkey]`.

- Resolve every DOI you cite.
- Test every dataset URL you reference.
- Do not paraphrase "common knowledge" — cite the primary source.

### 3. Open source and free tier only

No paid APIs, no proprietary datasets as primary dependencies. Commercial
tools are surfaced only in the existing-tools survey, never as production
dependencies.

### 4. Reproducibility

- Every paper-style computation is re-runnable from a CLI script under
  `scripts/`.
- Inputs are pinned by hash (or by STAC item ID) where possible.
- Random seeds are explicit.
- No notebook is the canonical source of an answer — promote it to a
  module + a test, or document it as exploratory.

## Coding standards

- **Formatter + linter:** [Ruff](https://docs.astral.sh/ruff/), configured in
  `pyproject.toml`. Run `ruff check` and `ruff format` before committing.
- **Type checker:** `mypy --strict`.
- **Tests:** `pytest`. Every data loader and every numerical transform has at
  least one unit test against a fixture.
- **Python style:** 3.11+ syntax (`match`, generics, etc.); type hints
  everywhere; docstrings on public functions in Google or NumPy style.

## Commit messages

Imperative mood; one logical change per commit:

```
Add ADR 0001 — language and stack
Refactor data loader to support local Zarr fallback
Fix off-by-one in GDD accumulator
```

If a commit closes a research deliverable or implements a documented ADR,
reference it: `Implements ADR 0004 — local Zarr cache for AgERA5`.

## Branching

- `main` is always shippable (or at least always passes CI).
- Feature branches: `phase1/<deliverable>`, `phase2/<area>`, etc.
- No force-pushes to `main`.

## ADR template

Save new ADRs as `docs/decisions/NNNN-short-slug.md`:

```markdown
# ADR NNNN — short title

- **Status:** proposed | accepted | superseded by ADR XXXX
- **Date:** YYYY-MM-DD

## Context

What problem are we solving? What constraints apply?

## Decision

What did we decide?

## Consequences

What becomes easier; what becomes harder; what we are deferring.

## Alternatives considered

What did we evaluate and reject, and why?
```
