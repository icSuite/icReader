# Current State

Last reviewed: 2026-08-12
Repository snapshot: `modular_pipeline` at `4b75db0` with uncommitted modular-reader changes

## Current position

`icReader` is active again to support the modular `icBuilder` data products.
The new public entry point is `icreader.load(filename)`, which dispatches from
the root NetCDF `product_type` attribute.

## Implemented and verified

- `product_type = "binned_fuv"` loads as `icreader.BinnedImage`.
- The binned reader loads counts, image statistics, viewing geometry, time,
  subsolar longitude, sensor, correction metadata, and the cubed-sphere grid.
- The grid is rebuilt from the saved two-dimensional `xi` and `eta` cell
  centres. Reconstructing from scalar grid metadata alone is not exact for the
  nested SI grid.
- Schema version 1 is required; older-file inference and legacy fallbacks were
  deliberately omitted because the modular corpus will be regenerated.
- `product_type = "precipitation"` loads as `icreader.PrecipitationImage`.
  The reader preserves precipitation and proton methods, Kp and its
  provenance, sensor and source provenance, individual and combined weights,
  corrected images, precipitation estimates, and the exact saved grid.
- `product_type = "conductance"` loads as
  `icreader.ModularConductanceImage`, including the carried precipitation
  state, Hall/Pedersen conductance, uncertainties, weight, processing choices,
  provenance, time, Kp, subsolar longitude, and exact grid. Its `mlon`
  property uses the same time-dependent coordinate convention as Products 1
  and 2.
- The old directly instantiated conductance reader remains available as both
  `ConductanceImage` and the explicit alias `LegacyConductanceImage`.
- Ten focused dispatcher/reader tests pass.
- A temporary end-to-end check passed from the actual `icBuilder.BinnedImage`
  writer, using the nested 18-by-18 SI grid, through `icreader.load()`.

## Preserved interfaces

The existing direct `ConductanceImage` and `SplineImage` classes remain
exported and were not refactored. They are not currently selected by the new
modular dispatcher.

## Next action

Use `icreader.load()` for all regenerated modular products. Migrate downstream
code away from direct legacy-reader construction as those workflows move to
the regenerated corpus.

## Known gaps

- The old conductance and spline readers were not revalidated in this task.
- Runtime dependencies remain undeclared in `pyproject.toml`.
- No CI workflow is present.
