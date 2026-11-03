# Decision Log

Last reviewed: 2026-11-02

## 2026-11-02 — Treat Fang as a conditional additive Product-3 contract

**Decision:** Keep current Product-3 schema numbers. Expose Fang fields lazily
when present, but require the complete Fang metadata and field group whenever
`conductance_model=fang`. Preserve Robinson and legacy compatibility. Use
Product 2's stored geographic coordinates at 130 km directly, then evaluate
IGRF at 150 km at that geographic latitude/longitude without field-line
mapping or a redundant Apex conversion. Use ApexPy's compiled IGRF magnitude
evaluation and retain its package/coefficient provenance.

**Rationale:** Fang is a selectable Product-3 calculation rather than a new
representation. Conditional validation prevents partially described Fang
files while avoiding an unnecessary schema break for existing consumers.

## 2026-10-01 — Read legacy and current detector Product 2 explicitly

**Decision:** Accept both schema-3 and schema-4 `precipitation_detector`
products through the same public reader, with schema-specific validation.
Schema 4 requires the optional-Gaussian and Tukey-propagation contract; schema
3 retains its legacy fields and defaults. Keep
`spatial_smoothing_kernel` as a compatibility alias for the new
`smoothing_method` property.

**Rationale:** The immediate scientific task is a direct old/new Product-2
comparison, and icAnalyzer depends on icReader. Explicit dual-schema support
allows that comparison without silently interpreting old files according to
new preprocessing semantics or breaking established consumer code.

**Downstream amendment:** Accept detector Product-3 schemas 2/3 and
Product-3-CS schemas 1/2 explicitly. Require the complete Product-2
preprocessing and Tukey-weight provenance in the current schemas, since both
products carry `method_quality_weight` and must remain interpretable without
opening Product 2.

## 2026-08-11 — Dispatch modular products from explicit NetCDF metadata

**Decision:** Use `icreader.load(filename)` with required root attributes
`product_type` and `schema_version`. Do not infer product type from filenames
or support old modular files through a fallback.

**Rationale:** The modular branch will regenerate the data. An explicit file
contract is simpler and avoids silent misclassification.

## 2026-08-11 — Implement only the stable Product-1 reader

**Decision:** Fully support `binned_fuv` now. Recognize `precipitation` and
`conductance`, but raise `NotImplementedError` until those `icBuilder` products
are complete.

**Rationale:** This keeps the public boundary visible without encoding schemas
that are still being designed.

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
