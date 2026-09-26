# Reader Interfaces and Data Contract

Last reviewed: 2026-09-25

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

Serialized attributes for every declared variable are copied at open time to
the immutable `product.variable_attrs[name]` mapping. A lazy
`ProductField.attrs` property returns that same mapping, and `field.units` is
the convenience view of its `units` entry. This metadata remains usable after
the context closes; reading array data after close remains an error.

Detector geometry remains in its stored time-dependent `glat`, `glon`,
`mlat`, `mlon`, and `mlt` fields. The reader does not regrid it.

Schema-2 `fuv_detector` products may contain the optional fields
`wic_unsubtracted_counts`, `si12_unsubtracted_counts`,
`si13_unsubtracted_counts`, and their corresponding `*_unsubtracted_valid`
masks. The reader exposes whichever complete fields are present as ordinary
lazy `ProductField` objects. Their absence does not invalidate an older
schema-2 file.

Schema-3 `precipitation_detector` products expose `count_source` as either
`background_subtracted` or `unsubtracted`, together with the recorded method
used for `method_quality_weight`. Older schema-3 files without these additive
attributes are read as `background_subtracted`, because no other count source
existed when they were written.

Schema-3 `precipitation_detector` products may also contain the optional lazy
fields `wic_smoothed`, `dwic_smoothed`, `si13_smoothed`, and
`dsi13_smoothed`. They are pre-proton Product-2 diagnostic inputs. The reader
exposes `spatial_smoothing_kernel`, `wic_smoothing_width_pixels`, and
`si13_smoothing_width_pixels`; earlier files default to `none`, `0`, and `0`.
Their absence remains valid and does not change the unsmoothed contract.

New detector Product-2 files also add optional lazy `si12` and `dsi12` fields.
These are the mapped SI12 counts and measurement uncertainty on the common
method support actually supplied to proton correction. They accompany the
required proton-corrected WIC and SI13 fields. Earlier schema-3 products remain
readable without them.

New `precipitation_cs` files carry the same `si12` and `dsi12` fields through
the fixed-grid overlap reduction. The reader also exposes `count_source`,
`spatial_smoothing_kernel`, `wic_smoothing_width_pixels`, and
`si13_smoothing_width_pixels`, with backward-compatible unsmoothed defaults.
Together with `wic_corrected` and `si13_corrected`, these provide the three
camera fields requested by corrected-camera analysis without opening Product
1. Corrected WIC must not receive the SI12 proton correction a second time.

For CS products, `product.grid` is a reconstructed `secsy.CSgrid`. The reader
uses the stored projection, radius, and explicit xi/eta edges together with
the canonical metadata identified by `grid_id`. It validates only that the CS
product and reconstructed grid have the required 46-by-46 shape. It does not
calculate or enforce a coordinate hash.

The reader exposes stored central/uncertainty masks, coverage, contributor
counts, clipping diagnostics, provenance, and physical fields without
recalculating validity, precipitation, conductance, or spatial mapping.

icBuilder now uses these detector and CS readers for Product-2/Product-3
construction, paired CS reduction, and restart validation. Complete-orbit
calculations materialize each needed cube once; restart checks use validated
metadata without decompressing full detector arrays.

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
five detector-first readers pass their focused tests. The detector-first file
contains 26 passing tests, including optional Product-2 smoothing and SI12
fields; all 36 repository tests pass.
Product 1 passed a temporary footprint-writer round trip on the current WIC
grid, and Product 2 loaded a real 20-frame `icBuilder` Zhang-Paxton example.
All 20 detector-first products in the local four-orbit pipeline test tree
opened successfully, reconstructed their CS grids where applicable, and read
a representative frame on demand. Selected fields from all five orbit-0085
products agree exactly with direct NetCDF reads.
The existing direct conductance and spline readers and downstream analyzer
call sites were not revalidated.
