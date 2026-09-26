"""Tests for detector-first and fixed-CS product readers."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from netCDF4 import Dataset, date2num
from secsy import CSgrid, CSprojection

import icreader
from icreader.csproduct import GRID_REGISTRY
from icreader.product import ProductField


TIME_UNITS = "seconds since 2000-01-01 00:00:00"
TEST_DATA = Path(
    "/home/bing/Dropbox/work/temp_storage/icBuilder_pipeline_test"
)


PRODUCT_CASES = (
    ("fuv_detector", "detector", 2, icreader.FUVDetector),
    (
        "precipitation_detector", "detector", 3,
        icreader.PrecipitationDetector,
    ),
    (
        "conductance_detector", "detector", 2,
        icreader.ConductanceDetector,
    ),
    ("precipitation_cs", "cs", 1, icreader.PrecipitationCS),
    ("conductance_cs", "cs", 1, icreader.ConductanceCS),
)


REAL_CASES = (
    (
        TEST_DATA / "fuv_detector/fuvpy_bs_directional_v1/or_0085.nc",
        icreader.FUVDetector,
        ("wic_counts", "wic_valid", "mlat"),
    ),
    (
        TEST_DATA / "precipitation_detector/IR_hardy/or_0085.nc",
        icreader.PrecipitationDetector,
        ("E0", "dE0", "method_valid", "Ep_clipping_flag"),
    ),
    (
        TEST_DATA / "conductance_detector/IR_hardy/robinson/or_0085.nc",
        icreader.ConductanceDetector,
        (
            "P", "H", "dP", "dH", "conductance_valid",
            "conductance_uncertainty_valid",
        ),
    ),
    (
        TEST_DATA
        / "precipitation_cs/image_apex_130km_46x46_v1/IR_hardy/or_0085.nc",
        icreader.PrecipitationCS,
        (
            "E0", "dE0", "coverage", "source_count", "method_valid",
            "method_uncertainty_valid",
        ),
    ),
    (
        TEST_DATA
        / "conductance_cs/image_apex_130km_46x46_v1/IR_hardy/robinson/or_0085.nc",
        icreader.ConductanceCS,
        (
            "P", "H", "dP", "dH", "coverage", "source_count",
            "conductance_valid", "conductance_uncertainty_valid",
        ),
    ),
)


def attribute_value(name):
    """Return a realistic scalar for a required synthetic attribute."""

    values = {
        "method": "image_ratio",
        "precipitation_method": "image_ratio",
        "conductance_model": "robinson",
        "proton_flux_source": "SI12",
        "proton_energy_model": "hardy",
        "proton_response_energy_min": 0.47,
        "proton_response_energy_max": 46.7,
        "reference_height_km": 130.0,
        "time_match_tolerance_seconds": 2.0,
        "coregistration_max_roundtrip_error_km": 25.0,
        "coregistration_minimum_coverage": 0.0,
        "coregistration_overlap_operator_stored": np.int8(0),
    }
    return values.get(name, f"test {name}")


def write_variables(nc, reader_class):
    """Write variables matching one reader's explicit schema manifest."""

    for offset, (name, (dimensions, kind, _eager)) in enumerate(
        reader_class.VARIABLES.items()
    ):
        if kind == "time":
            variable = nc.createVariable(name, "f8", dimensions, fill_value=np.nan)
            values = np.asarray(date2num(
                [datetime(2001, 1, 1), datetime(2001, 1, 1, 0, 2)],
                TIME_UNITS,
                calendar="standard",
            ), dtype=float)
            if name == "si13_source_time":
                values[1] = np.nan
            variable[:] = values
            variable.units = TIME_UNITS
            variable.calendar = "standard"
            continue

        dtype = "i1" if kind == "bool" else "i4" if kind == "int" else "f4"
        variable = nc.createVariable(name, dtype, dimensions)
        shape = tuple(len(nc.dimensions[dimension]) for dimension in dimensions)
        if kind == "bool":
            values = np.ones(shape, dtype=np.int8)
            values.reshape(-1)[0] = 0
        elif kind == "int":
            values = np.arange(np.prod(shape), dtype=np.int32).reshape(shape)
            if name.endswith("_frame_quality"):
                variable.flag_meanings = "rejected usable science_ready"
        else:
            values = (
                np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
                + offset
            )
            variable.units = "1"
        variable[:] = values


def write_grid(nc):
    """Write the frozen 46-by-46 CS grid used by the live products."""

    contract = GRID_REGISTRY["image_apex_130km_46x46_v1"]
    edges = np.linspace(-0.7207488608392238, 0.693928331919758, 47)
    grid = CSgrid(
        CSprojection((0, 90), (0, 1)),
        contract["L"],
        contract["W"],
        contract["Lres"],
        contract["Wres"],
        edges=(edges, edges),
        R=6_501_200.0,
    )
    nc.grid_id = "image_apex_130km_46x46_v1"
    group = nc.createGroup("grid")
    group.grid_id = nc.grid_id
    group.position = grid.projection.position
    group.orientation = grid.projection.orientation
    group.reference_height_km = 130.0
    group.radius_metres = grid.R

    coordinates = {
        "xi": (grid.xi, ("dim1", "dim2")),
        "eta": (grid.eta, ("dim1", "dim2")),
        "mlat": (grid.lat, ("dim1", "dim2")),
        "mlt": (np.mod(grid.lon / 15, 24), ("dim1", "dim2")),
        "xi_edge": (grid.xi_mesh[0], ("dim2_edge",)),
        "eta_edge": (grid.eta_mesh[:, 0], ("dim1_edge",)),
    }
    for name, (values, dimensions) in coordinates.items():
        variable = group.createVariable(name, "f8", dimensions)
        variable[:] = values
    return grid


def write_product(filename, product_type, representation, schema, reader_class):
    """Write a small complete product for dispatch and access tests."""

    with Dataset(filename, "w") as nc:
        if representation == "detector":
            sizes = {"time": 2, "row": 3, "column": 4}
        else:
            sizes = {
                "time": 2,
                "dim1": 46,
                "dim2": 46,
                "dim1_edge": 47,
                "dim2_edge": 47,
            }
        for name, size in sizes.items():
            nc.createDimension(name, size)

        nc.product_type = product_type
        nc.representation = representation
        nc.schema_version = schema
        for name in reader_class.REQUIRED_ATTRIBUTES:
            nc.setncattr(name, attribute_value(name))
        nc.software_version = "test-revision"
        nc.kp_source = "test Kp"
        nc.source_test = "source.nc"

        if representation == "cs":
            grid = write_grid(nc)
        else:
            grid = None
        write_variables(nc, reader_class)
    return grid


@pytest.mark.parametrize(
    "product_type,representation,schema,reader_class", PRODUCT_CASES
)
def test_dispatch_and_lazy_field_access(
    tmp_path, product_type, representation, schema, reader_class
):
    filename = tmp_path / f"{product_type}.nc"
    write_product(filename, product_type, representation, schema, reader_class)

    product = icreader.load(filename)
    assert isinstance(product, reader_class)
    assert icreader.open_product is icreader.load
    assert product.product_type == product_type
    assert product.representation == representation
    assert product.schema_version == schema
    assert product.time.shape == (2,)
    assert product.si13_source_time[1] is None
    assert product.variable_attrs["wic_frame_quality"]["flag_meanings"] == (
        "rejected usable science_ready"
    )
    with pytest.raises(TypeError):
        product.variable_attrs["wic_frame_quality"]["flag_meanings"] = "changed"
    with pytest.raises(TypeError):
        product.variable_attrs["new_variable"] = {}

    name = next(iter(product.fields))
    field = product.fields[name]
    assert isinstance(field, ProductField)
    assert getattr(product, name) is field
    assert field.shape == product.shape
    expected_dtype = (
        np.dtype(bool) if field.kind == "bool" else np.dtype(field._variable.dtype)
    )
    assert field.dtype == expected_dtype
    assert field.attrs is product.variable_attrs[name]
    assert product.read(name, 0).shape == product.shape[1:]
    np.testing.assert_array_equal(field[0], product.read(name, 0))

    product.close()
    assert product.closed
    assert product.variable_attrs["wic_frame_quality"]["flag_meanings"] == (
        "rejected usable science_ready"
    )
    with pytest.raises(RuntimeError, match="product is closed"):
        product.read(name, 0)


@pytest.mark.parametrize(
    "product_type,representation,schema,reader_class", PRODUCT_CASES
)
def test_context_manager_closes_new_products(
    tmp_path, product_type, representation, schema, reader_class
):
    filename = tmp_path / f"{product_type}.nc"
    write_product(filename, product_type, representation, schema, reader_class)

    with icreader.load(filename) as product:
        assert not product.closed
    assert product.closed


def test_detector_boolean_and_sliced_reads(tmp_path):
    filename = tmp_path / "conductance_detector.nc"
    write_product(
        filename,
        "conductance_detector",
        "detector",
        2,
        icreader.ConductanceDetector,
    )

    with icreader.load(filename) as product:
        valid = product.read("conductance_valid")
        assert valid.dtype == np.dtype(bool)
        assert valid.shape == (2, 3, 4)
        assert not valid.reshape(-1)[0]
        np.testing.assert_array_equal(product.conductance_valid[1], valid[1])
        assert product.source_indices["wic"].shape == (2,)
        assert product.kp_provenance["source"] == "test Kp"


def test_fuv_detector_loads_optional_unsubtracted_fields_when_present(tmp_path):
    filename = tmp_path / "fuv_detector.nc"
    write_product(
        filename, "fuv_detector", "detector", 2, icreader.FUVDetector
    )

    with Dataset(filename, "a") as nc:
        dimensions = ("time", "row", "column")
        for name, (_dimensions, kind, _eager) in (
            icreader.FUVDetector.OPTIONAL_VARIABLES.items()
        ):
            dtype = "i1" if kind == "bool" else "f4"
            variable = nc.createVariable(name, dtype, dimensions)
            variable[:] = 1
            if kind == "float":
                variable.units = "counts"

    with icreader.load(filename) as product:
        assert product.wic_unsubtracted_counts.shape == product.shape
        assert product.wic_unsubtracted_valid.dtype == np.dtype(bool)
        assert product.read("wic_unsubtracted_valid").dtype == np.dtype(bool)
        assert "wic_unsubtracted_counts" in product.fields
        assert "wic_unsubtracted_valid" in product.variable_attrs


def test_detector_optional_fields_and_count_source_are_backward_compatible(
    tmp_path,
):
    fuv_filename = tmp_path / "fuv_detector.nc"
    write_product(
        fuv_filename, "fuv_detector", "detector", 2, icreader.FUVDetector
    )
    with icreader.load(fuv_filename) as product:
        assert not hasattr(product, "wic_unsubtracted_counts")

    precipitation_filename = tmp_path / "precipitation_detector.nc"
    write_product(
        precipitation_filename,
        "precipitation_detector",
        "detector",
        3,
        icreader.PrecipitationDetector,
    )
    with icreader.load(precipitation_filename) as product:
        assert product.count_source == "background_subtracted"
        assert product.spatial_smoothing_kernel == "none"
        assert product.wic_smoothing_width_pixels == 0.0
        assert product.si13_smoothing_width_pixels == 0.0
        assert not hasattr(product, "wic_smoothed")

    with Dataset(precipitation_filename, "a") as nc:
        nc.count_source = "unsubtracted"
        nc.method_quality_weight_method = "uniform test weight"
        nc.spatial_smoothing_kernel = "gaussian"
        nc.wic_smoothing_width_pixels = 0.8
        nc.si13_smoothing_width_pixels = 1.2
        dimensions = ("time", "row", "column")
        for name in icreader.PrecipitationDetector.OPTIONAL_VARIABLES:
            variable = nc.createVariable(name, "f4", dimensions)
            variable[:] = 1
            variable.units = "counts"
    with icreader.load(precipitation_filename) as product:
        assert product.count_source == "unsubtracted"
        assert product.method_quality_weight_method == "uniform test weight"
        assert product.spatial_smoothing_kernel == "gaussian"
        assert product.wic_smoothing_width_pixels == 0.8
        assert product.si13_smoothing_width_pixels == 1.2
        assert product.si12.shape == product.shape
        assert product.dsi12.units == "counts"
        assert product.wic_smoothed.shape == product.shape
        assert product.dsi13_smoothed.units == "counts"


def test_precipitation_cs_loads_optional_si12_fields(tmp_path):
    filename = tmp_path / "precipitation_cs.nc"
    write_product(
        filename,
        "precipitation_cs",
        "cs",
        1,
        icreader.PrecipitationCS,
    )
    with icreader.load(filename) as product:
        assert not hasattr(product, "si12")
        assert product.count_source == "background_subtracted"
        assert product.spatial_smoothing_kernel == "none"

    with Dataset(filename, "a") as nc:
        nc.count_source = "unsubtracted"
        nc.spatial_smoothing_kernel = "gaussian"
        nc.wic_smoothing_width_pixels = 0.8
        nc.si13_smoothing_width_pixels = 1.2
        dimensions = ("time", "dim1", "dim2")
        for name in ("si12", "dsi12"):
            variable = nc.createVariable(name, "f4", dimensions)
            variable[:] = 1
            variable.units = "counts"

    with icreader.load(filename) as product:
        assert product.si12.shape == product.shape
        assert product.dsi12.units == "counts"
        assert product.count_source == "unsubtracted"
        assert product.spatial_smoothing_kernel == "gaussian"
        assert product.wic_smoothing_width_pixels == 0.8
        assert product.si13_smoothing_width_pixels == 1.2


@pytest.mark.parametrize(
    "product_type,representation,schema,reader_class", PRODUCT_CASES
)
def test_rejects_wrong_representation_or_schema(
    tmp_path, product_type, representation, schema, reader_class
):
    filename = tmp_path / f"{product_type}.nc"
    write_product(filename, product_type, representation, schema, reader_class)

    with Dataset(filename, "a") as nc:
        nc.schema_version = schema + 1
    with pytest.raises(ValueError, match="unsupported .* schema_version"):
        icreader.load(filename)

    with Dataset(filename, "a") as nc:
        nc.schema_version = schema
        nc.representation = "wrong"
    with pytest.raises(ValueError, match="expected .* representation"):
        icreader.load(filename)


@pytest.mark.parametrize("reader_class", (icreader.PrecipitationCS, icreader.ConductanceCS))
def test_cs_reader_reconstructs_46_by_46_secsy_grid(tmp_path, reader_class):
    product_type = (
        "precipitation_cs"
        if reader_class is icreader.PrecipitationCS else "conductance_cs"
    )
    filename = tmp_path / f"{product_type}.nc"
    original = write_product(filename, product_type, "cs", 1, reader_class)

    with icreader.load(filename) as product:
        assert isinstance(product.grid, CSgrid)
        np.testing.assert_array_equal(product.grid.xi, original.xi)
        np.testing.assert_array_equal(product.grid.eta, original.eta)
        np.testing.assert_array_equal(product.mlat, original.lat)
        np.testing.assert_array_equal(product.mlt, np.mod(original.lon / 15, 24))
        assert product.grid.shape == (46, 46)


@pytest.mark.skipif(
    not all(path.is_file() for path, _reader, _fields in REAL_CASES),
    reason="local detector-first integration corpus is unavailable",
)
@pytest.mark.parametrize("filename,reader_class,fields", REAL_CASES)
def test_real_orbit_0085_matches_direct_netcdf(filename, reader_class, fields):
    with icreader.load(filename) as product, Dataset(filename) as nc:
        assert isinstance(product, reader_class)
        assert set(product.VARIABLES) == set(nc.variables)
        for field in fields:
            for frame in (0, product.nt // 2, product.nt - 1):
                direct = nc.variables[field][frame]
                if np.ma.isMaskedArray(direct):
                    direct = direct.filled(np.nan)
                expected = np.asarray(direct)
                if product.VARIABLES[field][1] == "bool":
                    expected = expected.astype(bool)
                np.testing.assert_array_equal(product.read(field, frame), expected)

        if product.representation == "cs":
            group = nc.groups["grid"]
            np.testing.assert_array_equal(product.grid.xi, group.variables["xi"][:])
            np.testing.assert_array_equal(product.grid.eta, group.variables["eta"][:])
