# Reader Interfaces and Data Contract

Last reviewed: 2026-09-20

This note records the current high-level interface visible in the live branch.
It does not claim that all published files or downstream call sites were
retested during the review.

## Modular product dispatch

`icreader.load(filename)` uses two required root NetCDF attributes:

- `product_type`: `binned_fuv`, `precipitation`, or `conductance`;
- `schema_version`: `1` for Product 1 and `2` for Products 2 and 3.

There is deliberately no filename inference or fallback for older products.
The modular data corpus will be regenerated.

Product 1 (`binned_fuv`) is fully supported by `BinnedImage`. The reader loads
one sensor's native-grid statistics, intersecting-footprint count, fractional
coverage, `binning_method`, and metadata. It reconstructs the exact
cubed-sphere grid from the saved `grid/xi` and `grid/eta` cell centres. Scalar
grid metadata is retained but is insufficient by itself to reproduce nested
sensor grids exactly. For centre-binned rollback products, `coverage` is
present but contains NaN.

Product 2 (`precipitation`) is supported by `PrecipitationImage`. It loads the
common grid and time axis; Kp values, intervals, and provenance; sensor and
source provenance; the separate proton-flux source and proton-energy model;
corrected sensor images; individual and combined weights; and the
precipitation estimates `E0`, `dE0`, `Fe`, `dFe`, and `varE0Fe`. The proton
state contains raw model energy `Ep_model`, response-clipped energy `Ep`,
`dEp`, clipping flags, and SI12-derived `Fp`/`dFp`. Ratio products additionally
expose `R` and `dR`.

Product 3 (`conductance`) is supported by `ModularConductanceImage`. It carries
the proton and precipitation state, `P`, `H`, `dP`, `dH`, the unchanged
precipitation weight, processing choices and provenance, time, Kp, subsolar
longitude (`ssalon`), and the exact grid. The
one-dimensional `ssalon` coordinate is required to match the time dimension;
the reader uses it to expose time-dependent magnetic longitude through `mlon`,
consistent with Products 1 and 2. The source precipitation filename is retained
when present.

The pre-modular direct reader remains exported as `ConductanceImage` for old
call sites and has the explicit alias `LegacyConductanceImage`. New modular
files should be opened through `icreader.load()`.

## Detector-first products

The same dispatcher now recognizes five exact detector-first contracts:

| Product type | Representation | Schema | Reader |
| --- | --- | ---: | --- |
| `fuv_detector` | `detector` | 2 | `FUVDetector` |
| `precipitation_detector` | `detector` | 3 | `PrecipitationDetector` |
| `conductance_detector` | `detector` | 2 | `ConductanceDetector` |
| `precipitation_cs` | `cs` | 1 | `PrecipitationCS` |
| `conductance_cs` | `cs` | 1 | `ConductanceCS` |

These readers are context-managed because they retain an open NetCDF handle.
One-dimensional time, source-index, frame-quality, Kp, and subsolar fields are
loaded at construction. Three-dimensional variables remain compressed until
the caller slices their `ProductField` proxy or calls
`product.read(name, index=None)`. Float dtype is preserved, validity fields
are returned as Boolean arrays, and masked float values become NaN.

Detector geometry remains in its stored time-dependent `glat`, `glon`,
`mlat`, `mlon`, and `mlt` fields. The reader does not regrid it.

For CS products, `product.grid` is a reconstructed `secsy.CSgrid`. The reader
uses the stored projection, radius, and explicit xi/eta edges together with
the canonical metadata identified by `grid_id`. It then requires exact
agreement with the stored xi, eta, MLAT, MLT, and edge arrays and verifies the
coordinate SHA-256. An unknown grid identity or any coordinate drift is a
hard error.

The reader exposes stored central/uncertainty masks, coverage, contributor
counts, clipping diagnostics, provenance, and physical fields without
recalculating validity, precipitation, conductance, or spatial mapping.

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

The legacy modular Product-1, Product-2, and Product-3 implementations and the
five detector-first readers pass 34 focused tests.
Product 1 passed a temporary footprint-writer round trip on the current WIC
grid, and Product 2 loaded a real 20-frame `icBuilder` Zhang-Paxton example.
All 20 detector-first products in the local four-orbit pipeline test tree
opened successfully, reconstructed their CS grids where applicable, and read
a representative frame on demand. Selected fields from all five orbit-0085
products agree exactly with direct NetCDF reads.
The existing direct conductance and spline readers and downstream analyzer
call sites were not revalidated.
