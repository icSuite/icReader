# Handoff - Latest

Last updated: 2026-08-12
Repository snapshot: `modular_pipeline` at `4b75db0` with uncommitted modular-reader changes

## Project state

`icreader.load()` now supports all three modular products: `binned_fuv`,
`precipitation`, and `conductance`. Product 3 preserves the carried
precipitation state, Hall/Pedersen conductance and uncertainty, unchanged
weight, methods and provenance, Kp, time, subsolar longitude, and exact grid.
Product 3 now requires `ssalon` to match its time dimension and exposes `mlon`
with the same time-dependent convention as the binned and precipitation
readers.

The pre-modular reader remains available as `ConductanceImage` and the clear
alias `LegacyConductanceImage`; the dispatcher returns
`ModularConductanceImage` for Product 3.

The binned reader reconstructs the exact cubed-sphere grid from saved `xi` and
`eta` cell centres. Do not replace this with scalar-metadata reconstruction:
that changes the nested SI grid.

## Verification

- `pytest -q -p no:cacheprovider tests/test_load.py`: 10 passed.
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
