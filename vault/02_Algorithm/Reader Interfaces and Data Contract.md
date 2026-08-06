# Reader Interfaces and Data Contract

Last reviewed: 2026-07-26

This note records the stable high-level interface visible in the README and
committed code. It does not claim that all published files or downstream call
sites were retested during the review.

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

The 2026-07-26 vault migration inspected code and paths but did not open the
NetCDF examples or run downstream analysis. A future compatibility check should
be non-writing, representative, and explicit about the builder commit, product
file, reader commit, and analyzer call site used.
