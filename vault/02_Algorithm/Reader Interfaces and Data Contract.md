# Reader Interfaces and Data Contract

Last reviewed: 2026-08-12

This note records the current high-level interface visible in the live branch.
It does not claim that all published files or downstream call sites were
retested during the review.

## Modular product dispatch

`icreader.load(filename)` uses two required root NetCDF attributes:

- `product_type`: `binned_fuv`, `precipitation`, or `conductance`;
- `schema_version`: currently `1`.

There is deliberately no filename inference or fallback for older products.
The modular data corpus will be regenerated.

Product 1 (`binned_fuv`) is fully supported by `BinnedImage`. The reader loads
one sensor's native-grid statistics and metadata and reconstructs the exact
cubed-sphere grid from the saved `grid/xi` and `grid/eta` cell centres. Scalar
grid metadata is retained but is insufficient by itself to reproduce the
nested SI grid exactly.

Product 2 (`precipitation`) is supported by `PrecipitationImage`. It loads the
common grid and time axis; Kp values, intervals, and provenance; sensor and
source provenance; proton and precipitation methods; corrected sensor images;
individual and optional combined weights; and the precipitation estimates
`E0`, `dE0`, `Fe`, `dFe`, and `varE0Fe`. Ratio products additionally expose
`R` and `dR`. The combined `w` field is optional so files written immediately
before that field was introduced remain readable.

Product 3 (`conductance`) is supported by `ModularConductanceImage`. It carries
the precipitation state (`E0`, `dE0`, `Fe`, `dFe`, and `varE0Fe`), `P`, `H`,
`dP`, `dH`, the unchanged precipitation weight, processing choices and
provenance, time, Kp, subsolar longitude (`ssalon`), and the exact grid. The
one-dimensional `ssalon` coordinate is required to match the time dimension;
the reader uses it to expose time-dependent magnetic longitude through `mlon`,
consistent with Products 1 and 2. The source precipitation filename is retained
when present.

The pre-modular direct reader remains exported as `ConductanceImage` for old
call sites and has the explicit alias `LegacyConductanceImage`. New modular
files should be opened through `icreader.load()`.

## Direct conductance products

`ConductanceImage(filename)` opens one NetCDF product and reconstructs:

- WIC, SI12, and SI13 summary statistics;
- characteristic energy and electron energy flux with uncertainties;
- Hall and Pedersen conductance with uncertainties;
- weights, times, subsolar longitude, and cubed-sphere grid metadata.

It exposes magnetic latitude, local time, and longitude helpers and supports
in-memory filtering of time-dependent arrays through `discard()`.

## Spline products

`SplineImage(filename)` loads Hall and Pedersen spline coefficients,
uncertainty coefficients, grid metadata, and spatial/temporal basis settings.
After setting evaluation space and time, it exposes `H`, `P`, `dH`, and `dP`.

The committed class also constructs coordinate-aware functions through
`get_H_fun`, `get_P_fun`, `get_dH_fun`, and `get_dP_fun`, intended for
downstream model integration.

An additional `get_geo_grids()` method existed only in the uncommitted
worktree at the 2026-07-26 review. Do not treat it as part of committed API
compatibility until its disposition is resolved.

## Cross-project contract

- `icBuilder` owns product generation and serialization.
- `icReader` owns lightweight loading and evaluation.
- `icAnalyzer` consumes `icReader` classes according to the user's confirmed
  project relationship.

Before changing a variable name, shape, coordinate convention, uncertainty
field, spline basis, or callable signature, inspect both the current builder
schema and analyzer call sites. Coordinate changes deserve particular care:
the direct products use cubed-sphere grids and magnetic-local-time information,
while spline evaluation can accept native, Apex, or geographic coordinates.

## Verification boundary

The Product-1, Product-2, and Product-3 implementations pass ten focused
reader tests.
Product 1 passed a temporary writer round trip on the nested SI grid, and
Product 2 loaded a real 20-frame `icBuilder` Zhang-Paxton example.
The existing direct conductance and spline readers and downstream analyzer
call sites were not revalidated.
