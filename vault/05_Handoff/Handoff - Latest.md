# Handoff - Latest

Last updated: 2026-08-31
Repository snapshot: `modular_pipeline` at `eed30f4` with uncommitted schema-2 reader changes

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

- `pytest -q -p no:cacheprovider tests/test_load.py`: 10 passed.
- Current footprint-enabled icBuilder Product 1 round trip: passed, including
  signal, coverage, binning method, and reconstructed grid.
- Focused `icBuilder` schema tests: 19 passed.
- Actual `icBuilder` nested-SI writer to `icReader` round trip: passed.
- Actual 20-frame `icBuilder` Zhang-Paxton precipitation file: loaded.
- `git diff --check` in `icReader`: passed.

## Next action

Use `icreader.load()` in downstream modular workflows and migrate legacy
direct-reader call sites when they begin consuming the regenerated products.

## Portfolio impact

- Central update needed: Yes
- Changes: the modular reader contract now covers Products 1, 2, and 3.
- No deadline or portfolio priority changed.

## Entry points

- `icreader/__init__.py`
- `icreader/binnedimage.py`
- `icreader/modularconductanceimage.py`
- `tests/test_load.py`
- `vault/02_Algorithm/Reader Interfaces and Data Contract.md`
