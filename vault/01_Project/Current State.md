# Current State

Last reviewed: 2026-09-23
Repository snapshot: `modular_pipeline` at `5fb8841` with uncommitted detector
count-source additions

## Current position

`icReader` is active again to support the modular `icBuilder` data products.
The new public entry point is `icreader.load(filename)`, which dispatches from
the root NetCDF `product_type` attribute.

## Implemented and verified

- `product_type = "binned_fuv"` loads as `icreader.BinnedImage`.
- The binned reader loads counts, fractional footprint coverage, provisional
  image statistics, viewing geometry, time, subsolar longitude, sensor,
  correction and binning metadata, and the cubed-sphere grid.
- The grid is rebuilt from the saved two-dimensional `xi` and `eta` cell
  centres. Reconstructing from scalar grid metadata alone is not exact for the
  nested SI grid.
- Product 1 requires schema version 1. Products 2 and 3 require schema version
  2; older-file inference and legacy fallbacks remain deliberately omitted.
- `product_type = "precipitation"` loads as `icreader.PrecipitationImage`.
  The reader preserves the precipitation method, separate proton-flux source
  and proton-energy model, raw and response-clipped Ep, dEp, clipping flags,
  Fp/dFp, Kp and its
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
- A real orbit-0364 schema-2 Product-2/Product-3 round trip passes.
- A temporary end-to-end check passed from the current footprint-enabled
  `icBuilder.BinnedImage` writer through `icreader.load()`; signal, coverage,
  method, and the reconstructed 46-by-46 WIC grid agreed.
- `icreader.load()` now also dispatches schema-2 `fuv_detector`, schema-3
  `precipitation_detector`, schema-2 `conductance_detector`, and schema-1
  `precipitation_cs`/`conductance_cs` products.
- Detector-first three-dimensional fields are lazy `ProductField` proxies.
  Slicing or `read()` materializes only the requested variable selection;
  product objects are context-managed and close their NetCDF handle.
- Every declared variable exposes its serialized attributes through the
  immutable `product.variable_attrs[name]` mapping. Lazy fields expose the
  same mapping as `field.attrs`, so callers can validate units and flags
  without accessing the private NetCDF handle. Metadata remains available
  after the product closes.
- CS readers reconstruct a `secsy.CSgrid` from stored projection, radius, and
  explicit edges, then validate only that the CS data and reconstructed grid
  are 46 by 46. Coordinate-hash enforcement has been removed.
- All 35 focused tests pass. All 20 products in the local four-orbit test tree
  open successfully; selected fields in every orbit-0085 product match direct
  NetCDF reads. Opening the largest local detector orbit uses 61,764-KB peak
  RSS; reading one frame uses 102,064 KB.
- Schema-2 `fuv_detector` files may add the three calibrated unsubtracted
  count cubes and their three validity cubes. The reader exposes these lazily
  when present and continues to open earlier schema-2 files without them.
- Schema-3 `precipitation_detector` exposes `count_source` and
  `method_quality_weight_method`. Files created before these attributes are
  interpreted as `background_subtracted`, the only former implementation.

## Preserved interfaces

The existing direct `ConductanceImage` and `SplineImage` classes remain
exported and were not refactored. They are not currently selected by the new
modular dispatcher.

## Next action

Commit and push the detector count-source additions. Afterward, use
`ConductanceCS` as the reader boundary when the 46-by-46 corpus is introduced
to icAnalyzer. Reader support does not resolve the separate Hardy-clipping,
low-signal validity, or E0--Fe covariance decisions in the source products.

## Known gaps

- The old conductance and spline readers were not revalidated in this task.
- Runtime dependencies remain undeclared in `pyproject.toml`.
- No CI workflow is present.
