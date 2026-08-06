# Decision Log

Last reviewed: 2026-07-26

## 2026-07-26 — Treat the project as complete for now

**Decision:** Record `icReader` as completed for the current scope while
preserving an explicit need to revisit it later.

**Rationale:** The user directly confirmed both points. No revisit date,
priority, or trigger was supplied, so none is inferred.

## 2026-07-26 — Record the cross-project reader contract

**Decision:** Treat `icReader` as the reader for `icBuilder` products and as a
code dependency of `icAnalyzer`.

**Rationale:** The user directly confirmed both relationships.

## 2026-07-26 — Preserve and modernize the established vault

**Decision:** Keep `log/icReader/` as the project vault, add the shared live
note architecture within it, and retain older dated notes as historical
evidence.

**Rationale:** The repository already used this Obsidian-backed location. A
second renamed vault would split project memory and continuity.

The architecture migration is documentation-only and does not include or
resolve pre-existing worktree changes.

**Superseded 2026-07-26:** The user subsequently standardized all project
memory at the repository-root `vault/` path. The complete existing vault was
moved intact; only its location and operational references changed.
