# Detector and CS Reader Implementation Plan

Last reviewed: 2026-09-20
Status: Implemented and verified

## Objective

Extend icReader so the detector-first icBuilder products can be consumed
through a validated high-level interface rather than ad hoc
`netCDF4.Dataset` calls.

The reader must support these exact live contracts:

| Product type | Representation | Schema | Reader |
| --- | --- | ---: | --- |
| `fuv_detector` | `detector` | 2 | `FUVDetector` |
| `precipitation_detector` | `detector` | 3 | `PrecipitationDetector` |
| `conductance_detector` | `detector` | 2 | `ConductanceDetector` |
| `precipitation_cs` | `cs` | 1 | `PrecipitationCS` |
| `conductance_cs` | `cs` | 1 | `ConductanceCS` |

The existing `binned_fuv`, `precipitation`, `conductance`, direct-conductance,
and spline readers remain supported without changing their field semantics.

## Verified starting point

The live `modular_pipeline` branch at `1fd47ca` is clean. Its public
`icreader.load(filename)` dispatcher currently recognizes only
`binned_fuv`, `precipitation`, and `conductance`. The five detector-first
product types therefore raise `unknown product_type` and are presently read
directly with `netCDF4.Dataset`.

The completed four-orbit test corpus is at:

`/home/bing/Dropbox/work/temp_storage/icBuilder_pipeline_test`

It contains representative files for all five new contracts. These files are
integration evidence, not repository fixtures.

## Design decisions

### 1. Preserve one descriptor-based dispatcher

`icreader.load(filename)` remains the normal entry point. Dispatch uses the
root `product_type`, `representation`, and `schema_version` attributes. It
must not infer a product from its directory or filename and must not silently
accept an older or future schema.

Add `icreader.open_product` as an explicit alias for code that wants to
emphasize the context-managed lifetime. Existing calls to `load(filename)`
remain valid.

Recommended new-product usage:

```python
with icreader.load(filename) as product:
    hall = product.read("H")
    pedersen_frame = product.read("P", 50)
```

The old eager readers may implement a harmless `close()` and context-manager
interface later for complete uniformity, but their current construction and
attributes must not change in this work.

### 2. Read large fields on demand

Detector orbits contain many compressed `(time, 256, 256)` fields. A reader
constructor must not decompress all of them. The new readers keep the
underlying NetCDF file open and load only:

- root descriptors and provenance;
- dimension sizes;
- one-dimensional time, source-index, frame-quality, Kp, and subsolar fields;
- the small fixed CS grid for CS products.

Three-dimensional fields are exposed through a small read-only field proxy
and an explicit `read(name, index=None)` method. The proxy supports shape,
dtype, units, and NumPy-style slicing. `read()` returns an ordinary NumPy
array and normalizes fill values consistently:

- floating point -> `NaN`;
- validity/flag fields -> `False`;
- integer counts/indices -> their documented integer fill value.

The product owns the open NetCDF handle and implements `close()`, `__enter__`,
and `__exit__`. Access after close raises a clear error. No dask dependency or
implicit whole-file cache is needed for the first implementation.

### 3. Validate, but never reinterpret, the product

Each reader has an explicit schema manifest containing required dimensions,
variables, shapes, and essential root attributes. Construction validates the
contract without recalculating precipitation, conductance, coregistration, or
validity.

The reader exposes the stored masks exactly:

- detector sensor and method-valid masks;
- detector conductance central/uncertainty masks;
- CS central/uncertainty masks;
- proton-energy clipping flags or fractions;
- source count and coverage fields.

It must not convert zero coverage into missing data, apply a quality or SNR
threshold, regrid detector pixels, or replace stored conductance with a fresh
Robinson calculation.

### 4. Reconstruct the CS grid and verify it against the file

Detector coordinates are time-dependent fields stored on the WIC detector
geometry. They remain on-demand variables: `glat`, `glon`, `mlat`, `mlon`,
and `mlt`.

CS products expose a reconstructed `secsy.CSgrid` as `product.grid`, matching
the established icReader interface. Construct it with the stored projection,
radius, and explicit `xi_edge`/`eta_edge` arrays. The explicit edges, rather
than scalar dimensions alone, determine the reconstructed cells.

The current CS files store:

- `xi`, `eta`, `mlat`, and `mlt` cell centres;
- `xi_edge` and `eta_edge`;
- projection position and orientation;
- reference height and radius;
- `grid_id` and coordinate SHA-256.

They do not currently store `L`, `W`, `Lres`, or `Wres`. For the supported
`image_apex_130km_46x46_v1` identity, use a small explicit registry containing
the canonical icBuilder values of 50,000,000 m for L/W and 200,000 m for
Lres/Wres. Reject an unknown grid identity rather than guessing these values.
A future builder schema can serialize them directly.

After reconstruction, compare `grid.xi`, `grid.eta`, `grid.lat`, the wrapped
`grid.lon / 15`, and both edge arrays against the stored variables. Recompute
the coordinate hash in the same byte order and array order used by icBuilder:
`xi_edge`, `eta_edge`, `xi`, `eta`, `mlat`, then `mlt`. Construction fails if
the root identity, grid-group identity, reconstructed coordinates, stored
coordinates, or hash disagree. The file remains the validation authority,
while consumers receive the requested working `secsy.CSgrid` object.

This reconstruction was checked against the actual orbit-0085
`conductance_cs` file. All six coordinate/edge arrays are bit-for-bit equal
and the reconstructed hash is
`50aa89a6bdefc05a8ef003ad7bffb5ea800d7014fd173e16f88f821b1ed465bf`,
matching the file.

### 5. Keep provenance available without inventing a generic metadata model

Expose all root attributes through a read-only `attrs` mapping and copy the
frequently used descriptors to named attributes: product type,
representation, schema, software version, methods, grid identity, and source
file identities. Preserve `kp_*` and `source_*` attributes verbatim.

Decode CF time variables into object arrays while retaining their original
units and calendar. Missing SI source times remain missing rather than being
converted to a fabricated date.

## Proposed source layout

The implementation is large enough to justify three focused modules rather
than putting every schema into the dispatcher:

- `icreader/product.py`: common descriptor validation, time decoding,
  on-demand field access, fill handling, provenance, and resource lifetime;
- `icreader/detectorproduct.py`: the three detector schema manifests and
  detector reader classes;
- `icreader/csproduct.py`: the canonical-grid registry, secsy reconstruction,
  coordinate hashing, and the two CS reader classes.

Modify:

- `icreader/__init__.py` for dispatch and public exports;
- `tests/test_load.py` only for dispatcher/backward-compatibility checks;
- add focused detector and CS reader test files;
- update README and the reader data-contract note after behavior is verified.

This exceeds the repository's usual two-new-file threshold because common
file lifetime/fill behavior, time-dependent detector geometry, and immutable
CS-grid validation are genuinely separate responsibilities. The public API
remains small.

## Implementation sequence

### Phase 1: Freeze the five manifests

1. Record each required root descriptor, dimension, one-dimensional field,
   large field, mask, and provenance attribute from the live icBuilder writer.
2. Compare those manifests against orbit 0085 in the completed test corpus.
3. Make schema versions explicit constants in icReader; do not import
   icBuilder at runtime.
4. Add small synthetic NetCDF fixtures for each schema. Keep external
   full-orbit data out of the repository.

### Phase 2: Add the common on-demand product reader

1. Open the NetCDF file and validate product type, representation, schema,
   dimensions, required attributes, and variable shapes.
2. Decode small time and frame-identity fields eagerly.
3. Implement the field proxy and `read()` with consistent masked-value and
   dtype handling.
4. Implement `close()` and context-manager behavior.
5. Ensure failed construction closes its NetCDF handle.

### Phase 3: Add detector readers

1. Implement `FUVDetector` for schema-2 Product 1.
2. Implement `PrecipitationDetector` for schema-3 Product 2.
3. Implement `ConductanceDetector` for schema-2 Product 3.
4. Expose detector row/column coordinates, source times and indices, frame
   quality, Kp where present, and all stored large fields on demand.
5. Validate central and uncertainty mask shapes without imposing scientific
   thresholds.

### Phase 4: Add CS readers

1. Reconstruct `secsy.CSprojection` and `secsy.CSgrid` from the stored
   projection, radius, explicit edges, and canonical grid registry.
2. Verify root and group grid identities, every reconstructed coordinate, and
   the coordinate hash against the stored grid group.
3. Implement `PrecipitationCS` and `ConductanceCS`.
4. Preserve coverage, contributor counts, clipping diagnostics, and separate
   central/uncertainty masks.
5. Preserve the Product-3 companion Product-2 path and both source identities.

### Phase 5: Extend dispatch without breaking old products

1. Add the five new product types to `icreader.load()`.
2. Export the five classes and `open_product`; expose each CS grid through the
   reader's existing-style `grid` attribute.
3. Leave `ConductanceImage`, `LegacyConductanceImage`, `SplineImage`, and the
   three existing modular readers unchanged.
4. Keep unknown products and unsupported schemas as hard errors.

### Phase 6: Verify synthetic and real products

Run focused tests covering:

- dispatch to all eight modular product types;
- rejection of the wrong representation or schema;
- required-variable and required-attribute errors with useful messages;
- time decoding, including missing SI source times;
- float, integer, boolean, and sliced field reads;
- no three-dimensional field read during construction;
- context-manager closure and access-after-close errors;
- exact CS coordinate arrays and coordinate hash;
- Product-2/Product-3 source and companion provenance;
- continued success of the existing ten reader tests.

Then open one real orbit-0085 file for every new product type and compare:

- descriptors and dimensions;
- selected first/middle/last frames against direct `netCDF4.Dataset` reads;
- validity masks and fill handling;
- P/H/dP/dH for detector and CS conductance;
- all stored CS coordinates and grid identity.

Finally profile opening the largest local detector orbit. Constructor memory
and time must not scale with the number of three-dimensional variables; only
an explicit field read may incur decompression and array allocation.

## Implementation result

All six phases are complete in the current worktree. The shared reader lives
in `icreader/product.py`; detector and CS contracts are implemented in
`icreader/detectorproduct.py` and `icreader/csproduct.py`; the public dispatch
is in `icreader/__init__.py`.

The focused suite passes 34 tests. All 20 products in the four-orbit local
integration corpus open successfully, and selected values, uncertainties,
masks, coverage, and contributor counts in all five orbit-0085 products agree
with direct NetCDF reads. Opening the largest local detector file reached
61,764 KB maximum RSS; reading one 256-by-256 field frame reached 102,064 KB.
This confirms that construction does not materialize the full detector cubes.

## Acceptance criteria

The work is complete when:

1. `icreader.load()` recognizes all five detector-first product types.
2. All contracts are validated by product type, representation, and exact
   schema version.
3. Detector construction is on-demand and does not load full image cubes.
4. Selected reads match direct NetCDF values, masks, and dtypes.
5. CS readers expose a `secsy.CSgrid` whose edges and coordinates match the
   file and pass the frozen coordinate hash.
6. No reader recalculates physics, validity, or spatial mapping.
7. Existing public readers and their ten focused tests still pass.
8. All five real orbit-0085 products pass an end-to-end reader smoke test.
9. README, current state, handoff, and data-contract documentation describe
   the verified interface and resource lifetime.

## Explicitly deferred

- changing Hardy clipping or low-signal validity;
- calculating nonzero E0--Fe covariance;
- regridding or combining detector and CS products;
- multi-orbit catalogs, globbing, concatenation, or dataset indexing;
- dask-backed distributed reads;
- migrating icAnalyzer scripts;
- redesigning legacy 36-by-36 conductance or spline readers;
- accepting an unknown CS grid identity or reconstructing one from guessed
  scalar metadata.

Those are separate scientific or downstream tasks. This implementation is a
strict, lightweight boundary around data already serialized by icBuilder.
