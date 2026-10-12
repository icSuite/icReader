# Current State

Last reviewed: 2026-10-11 (Hardy additive compatibility)
Repository snapshot: `modular_pipeline` at `8f8e7d1`; reader/test/docs and
pre-existing memory work are uncommitted.

## Hardy electron compatibility implemented

Additive `electron_*` provenance is exposed by detector, CS and bin-first
Product 2/3 readers. Optional detector/bin-first `E0_response_range_flag`
retains signed integer codes (-1 unavailable, 0 within, 1 below, 2 above);
CS exposes overlap fraction and any-flag. Lazy detector/CS access and older
products remain supported. [[Reader Interfaces and Data Contract]] owns the
field contract. Full suite 46 tests passes, including malformed-dimension
rejection, optional fields, signed flags and backward compatibility.

All four real 122-frame Hardy orbit 0085 detector/CS products loaded through
`icreader.load()` and agreed with writer/math checks. Product schema versions
remain unchanged because the metadata and fields are additive. This is reader
compatibility, not scientific acceptance of Hardy energy or its conditional
uncertainties. Existing project work remains; no commit or corpus change.

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
- `icreader.load()` now also dispatches schema-2 `fuv_detector`, schema-3/4
  `precipitation_detector`, schema-2/3 `conductance_detector`, schema-1
  `precipitation_cs`, and schema-1/2 `conductance_cs` products.
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
- Schema-3 `precipitation_detector` optionally exposes lazy pre-proton
  `wic_smoothed`, `dwic_smoothed`, `si13_smoothed`, and `dsi13_smoothed`
  fields. Smoothing kernel and WIC/SI13 widths are available as public
  metadata; earlier files default to no smoothing and zero widths.
- Detector Product 2 and `precipitation_cs` optionally expose lazy `si12` and
  `dsi12` fields. CS readers also expose count-source and smoothing provenance.
  This places corrected WIC, corrected SI13, and the SI12 proton channel in one
  fixed-grid reader product while keeping old files readable.
- The real orbit-0085 Gaussian diagnostic at WIC/SI13 sigmas 0.8/1.2 opens
  successfully and reads individual smoothed frames without loading the full
  cubes. A real 122-frame precipitation CS file also reads all three camera
  fields and uncertainties.
- Schema-4 `precipitation_detector` implements the new optional fixed-Gaussian
  contract. It requires the global request, effective WIC/SI12/SI13 widths,
  per-sensor applied flags, smoothing/variance provenance, and geometric Tukey
  propagation metadata. Only the combined `method_quality_weight` is required;
  legacy schema-3 per-sensor weights remain optional when reading old files.
  Optional smoothed fields now include SI12. Explicit dual-schema validation
  allows old and new Product 2 files to be compared without silently assigning
  schema-4 semantics to schema 3.
- Schema-3 `conductance_detector` and schema-2 `conductance_cs` require and
  expose the complete Product-2 count-source, smoothing, variance-propagation,
  and Tukey-weight recipe. Their legacy schemas remain readable with explicit
  unrecorded/unsmoothed fallbacks. All 39 tests under `tests/` pass.

## Preserved interfaces

The existing direct `ConductanceImage` and `SplineImage` classes remain
exported and were not refactored. They are not currently selected by the new
modular dispatcher.

## Next action

Compare the legacy schema-3 and new schema-4 Product 2 files, including
`method_quality_weight`, regenerate Product 3 and its CS representation, then
use `ConductanceCS` as the reader boundary when the 46-by-46 corpus is
introduced to icAnalyzer. Reader support does not
resolve the separate Hardy-clipping, low-signal validity, or E0--Fe covariance
decisions in the source products.

## Known gaps

- The old conductance and spline readers were not revalidated in this task.
- Runtime dependencies remain undeclared in `pyproject.toml`.
- No CI workflow is present.
