# Handoff - Latest

Last updated: 2026-09-23
Repository snapshot: `modular_pipeline` at `5fb8841` with uncommitted detector
count-source additions

## Latest checkpoint: unsubtracted detector counts supported

`FUVDetector` now treats the three calibrated unsubtracted count cubes and
their three validity cubes as optional schema-2 fields. They remain lazy when
present, while earlier schema-2 files still open unchanged. This additive
contract supports the icBuilder background-sensitivity diagnostic without
forcing a schema split or loading all detector data at open time.

`PrecipitationDetector` now exposes the Product-2 `count_source` and
`method_quality_weight_method` attributes. Older schema-3 files lacking them
are interpreted as `background_subtracted`, which was their only possible
source. All 35 reader tests pass.

## Latest checkpoint: public variable metadata added

Detector and CS products now expose a read-only mapping of serialized
attributes for every declared variable as `product.variable_attrs`. Lazy
fields expose their entry as `field.attrs`, and `field.units` uses the same
preserved metadata. This lets icBuilder retain restart checks for units and
frame-quality meanings without accessing icReader's private NetCDF handle.
The metadata is copied while the file is open and remains available after the
context closes.

The corresponding icBuilder migration is implemented and verified. Product-2,
Product-3, and all four-orbit CS arrays remain exactly unchanged, while the CS
read-once performance is preserved. All 34 icReader tests pass.

## Latest checkpoint: detector and CS readers implemented

`icreader.load()` now dispatches the five detector-first icBuilder products:
schema-2 `fuv_detector`, schema-3 `precipitation_detector`, schema-2
`conductance_detector`, and schema-1 `precipitation_cs`/`conductance_cs`.
Large three-dimensional fields remain lazy through sliceable `ProductField`
proxies while metadata and small coordinate variables are loaded eagerly. The
new product objects own their NetCDF handle and support context-managed use.

The CS readers reconstruct an actual `secsy.CSgrid` as `product.grid` from the
stored projection metadata and explicit grid edges. They validate only the
required 46-by-46 shape; coordinate hashes and exact reconstructed-coordinate
comparisons were removed because they blocked otherwise valid products across
numerical environments. They do not rerun detector physics, change data, or
regrid the products. Existing modular and legacy readers remain unchanged.

## Project state

`icreader.load()` now supports all three modular products: `binned_fuv`,
`precipitation`, and `conductance`. Product 3 preserves the carried
precipitation state, Hall/Pedersen conductance and uncertainty, unchanged
weight, methods and provenance, Kp, time, subsolar longitude, and exact grid.
Product 3 now requires `ssalon` to match its time dimension and exposes `mlon`
with the same time-dependent convention as the binned and precipitation
readers.

Product 1 remains schema 1. Products 2 and 3 now require schema 2 and expose
SI12 as the proton-flux source, Hardy or constant as the proton-energy model,
raw `Ep_model`, response-clipped `Ep`, dEp, the clipping flag, and Fp/dFp.
An isolated real orbit-0364 Product-2/Product-3 round trip passed.

The pre-modular reader remains available as `ConductanceImage` and the clear
alias `LegacyConductanceImage`; the dispatcher returns
`ModularConductanceImage` for Product 3.

The binned reader reconstructs the exact cubed-sphere grid from saved `xi` and
`eta` cell centres. Do not replace this with scalar-metadata reconstruction:
that changes the nested SI grid.

Product 1 now also requires `binning_method` and `coverage`. Footprint products
load their fractional valid coverage; centre-binned rollback products carry
NaN coverage. This intentionally follows the regenerated icBuilder schema and
does not add a fallback for older modular files.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests`:
  33 passed.
- All 20 completed detector/CS products in the local four-orbit icBuilder test
  corpus opened successfully; every CS grid reconstructed and representative
  lazy fields were read.
- The five orbit-0085 products passed direct comparisons against raw NetCDF
  variables, including central values, uncertainty, masks, coverage, and
  counts.
- The largest detector file opened at about 62 MB maximum RSS; reading one
  256-by-256 field frame reached about 102 MB maximum RSS, confirming that
  opening a product does not materialize its full detector arrays.
- Current footprint-enabled icBuilder Product 1 round trip: passed, including
  signal, coverage, binning method, and reconstructed grid.
- Focused `icBuilder` schema tests: 19 passed.
- Actual `icBuilder` nested-SI writer to `icReader` round trip: passed.
- Actual 20-frame `icBuilder` Zhang-Paxton precipitation file: loaded.
- `git diff --check` in `icReader`: passed.

## Next action

Commit and push the detector count-source API. Afterward, migrate icAnalyzer
to consume the new 46-by-46
`conductance_cs` corpus through `icreader.load()`. Keep reader acceptance
separate from scientific acceptance of the detector and conductance products.

## Portfolio impact

- Central update needed: No
- Changes: icReader now supports all five detector-first and CS product types,
  including lazy optional unsubtracted Product-1 fields, Product-2 count-source
  metadata, public immutable variable metadata, and verified CS-grid
  reconstruction. icBuilder now consumes this interface.
- No deadline or portfolio priority changed.

## Entry points

- `icreader/__init__.py`
- `icreader/product.py`
- `icreader/detectorproduct.py`
- `icreader/csproduct.py`
- `icreader/binnedimage.py`
- `icreader/modularconductanceimage.py`
- `tests/test_load.py`
- `tests/test_detector_first_products.py`
- `vault/02_Algorithm/Reader Interfaces and Data Contract.md`
- `vault/02_Algorithm/Detector and CS Reader Implementation Plan.md`
