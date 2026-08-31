"""Tests for the modular NetCDF product dispatcher."""

from datetime import datetime

import numpy as np
import pytest
from netCDF4 import Dataset, date2num
from secsy import CSgrid, CSprojection

import icreader


def write_binned_product(filename):
    """Write a small but complete Product-1 file."""

    xi_edges = np.linspace(-0.18, 0.22, 5)
    eta_edges = np.linspace(-0.16, 0.20, 4)
    grid = CSgrid(
        CSprojection((0, 90), (0, 1)),
        L=8_000_000,
        W=8_000_000,
        Lres=1_000_000,
        Wres=1_000_000,
        edges=(xi_edges, eta_edges),
        R=6_481_200,
    )

    time = [datetime(2001, 2, 3, 4, 5, 6), datetime(2001, 2, 3, 4, 7, 6)]
    shape = (len(time), *grid.shape)

    with Dataset(filename, "w") as nc:
        nc.createDimension("time", shape[0])
        nc.createDimension("dim1", shape[1])
        nc.createDimension("dim2", shape[2])

        nc.product_type = "binned_fuv"
        nc.schema_version = 1
        nc.sensor = "SI12"
        nc.image_correction = "raw"
        nc.los_correction = np.int8(1)
        nc.binning_method = "footprint"

        for name in (
            "mu", "sigma", "w", "sza", "dza", "los_factor", "coverage"
        ):
            variable = nc.createVariable(name, "f4", ("time", "dim1", "dim2"))
            variable[:] = np.arange(np.prod(shape)).reshape(shape)

        counts = nc.createVariable("counts", "i4", ("time", "dim1", "dim2"))
        counts[:] = 3

        time_units = "seconds since 2000-01-01 00:00:00"
        time_variable = nc.createVariable("time", "f8", ("time",))
        time_variable[:] = date2num(time, time_units, calendar="standard")
        time_variable.units = time_units
        time_variable.calendar = "standard"

        ssalon = nc.createVariable("ssalon", "f4", ("time",))
        ssalon[:] = [12.0, 13.0]

        group = nc.createGroup("grid")
        group.position = grid.projection.position
        group.orientation = grid.projection.orientation
        group.L = grid.L
        group.W = grid.W
        group.Lres = grid.Lres
        group.Wres = grid.Wres
        group.R = grid.R

        coordinates = {
            "xi": grid.xi,
            "eta": grid.eta,
            "mlat": grid.lat,
            "mlt": np.mod(grid.lon / 15, 24),
        }
        for name, values in coordinates.items():
            variable = group.createVariable(name, "f8", ("dim1", "dim2"))
            variable[:] = values

    return grid, time


def write_descriptor(filename, product_type=None, schema_version=1):
    """Write only the root attributes needed to test dispatch failures."""

    with Dataset(filename, "w") as nc:
        if product_type is not None:
            nc.product_type = product_type
        nc.schema_version = schema_version


def write_precipitation_product(
    filename, include_ratio=True, ssalon_values=(12.0, 13.0)
):
    """Write a small but complete Product-2 file."""

    xi_edges = np.linspace(-0.18, 0.22, 5)
    eta_edges = np.linspace(-0.16, 0.20, 4)
    grid = CSgrid(
        CSprojection((0, 90), (0, 1)),
        L=8_000_000,
        W=8_000_000,
        Lres=1_000_000,
        Wres=1_000_000,
        edges=(xi_edges, eta_edges),
        R=6_481_200,
    )

    time = [datetime(2001, 2, 3, 4, 5, 6), datetime(2001, 2, 3, 4, 7, 6)]
    kp_start = [datetime(2001, 2, 3, 3), datetime(2001, 2, 3, 3)]
    shape = (len(time), *grid.shape)

    with Dataset(filename, "w") as nc:
        nc.createDimension("time", shape[0])
        nc.createDimension("dim1", shape[1])
        nc.createDimension("dim2", shape[2])

        nc.product_type = "precipitation"
        nc.schema_version = 2
        nc.method = "image_ratio" if include_ratio else "zhang_paxton"
        nc.proton_flux_source = "SI12"
        nc.proton_energy_model = "hardy"
        nc.proton_energy_uncertainty_method = "not modelled by Hardy et al. (1991)"
        nc.proton_energy_coordinate_note = "Modified Apex approximation"
        nc.proton_response_energy_min = 0.47
        nc.proton_response_energy_max = 46.7
        nc.time_match_tolerance_seconds = 10.0
        nc.time_match_rule = "earliest common frame"
        nc.regrid_method = "bilinear"
        nc.regrid_uncertainty = "independent source-cell errors"
        nc.physics_package = "icPhysics"
        nc.physics_version = "0.1"
        nc.kp_source = "GFZ"
        nc.kp_status = "definitive"
        nc.source_wic = "wic/or_0001.nc"
        nc.source_si12 = "si12/or_0001.nc"
        nc.source_si13 = "si13/or_0001.nc"

        for sensor in ("wic", "si12", "si13"):
            nc.setncattr(f"{sensor}_image_correction", "raw")
            nc.setncattr(f"{sensor}_los_correction", np.int8(1))

        time_units = "seconds since 2000-01-01 00:00:00"
        time_variable = nc.createVariable("time", "f8", ("time",))
        time_variable[:] = date2num(time, time_units, calendar="standard")
        time_variable.units = time_units
        time_variable.calendar = "standard"

        kp_time = nc.createVariable("Kp_interval_start", "f8", ("time",))
        kp_time[:] = date2num(kp_start, time_units, calendar="standard")
        kp_time.units = time_units
        kp_time.calendar = "standard"

        one_dimensional = {
            "Kp": [2.0, 2.3],
            "wic_source_index": [3, 4],
            "si12_source_index": [5, 6],
            "si13_source_index": [7, 8],
        }
        for name, values in one_dimensional.items():
            dtype = "i4" if name.endswith("source_index") else "f4"
            variable = nc.createVariable(name, dtype, ("time",))
            variable[:] = values

        if ssalon_values is not None:
            ssalon_dimension = "time"
            if len(ssalon_values) != shape[0]:
                ssalon_dimension = "ssalon_time"
                nc.createDimension(ssalon_dimension, len(ssalon_values))
            ssalon = nc.createVariable("ssalon", "f4", (ssalon_dimension,))
            ssalon[:] = ssalon_values

        fields = (
            "wic", "dwic", "si12", "dsi12", "si13", "dsi13",
            "wic_weight", "si12_weight", "si13_weight", "w",
            "wic_corrected", "dwic_corrected",
            "si13_corrected", "dsi13_corrected",
            "Ep_model", "Ep", "dEp", "Fp", "dFp",
            "E0", "dE0", "Fe", "dFe", "varE0Fe",
        )
        if include_ratio:
            fields += ("R", "dR")

        values = np.arange(np.prod(shape), dtype=float).reshape(shape)
        for offset, name in enumerate(fields):
            variable = nc.createVariable(name, "f4", ("time", "dim1", "dim2"))
            variable[:] = values + offset

        clipped = nc.createVariable(
            "Ep_clipping_flag", "i1", ("time", "dim1", "dim2")
        )
        clipped[:] = 1

        group = nc.createGroup("grid")
        group.position = grid.projection.position
        group.orientation = grid.projection.orientation
        group.L = grid.L
        group.W = grid.W
        group.Lres = grid.Lres
        group.Wres = grid.Wres
        group.R = grid.R

        coordinates = {
            "xi": grid.xi,
            "eta": grid.eta,
            "mlat": grid.lat,
            "mlt": np.mod(grid.lon / 15, 24),
        }
        for name, values in coordinates.items():
            variable = group.createVariable(name, "f8", ("dim1", "dim2"))
            variable[:] = values

    return grid, time, kp_start


def write_conductance_product(filename, ssalon_values=(12.0, 13.0)):
    """Extend the Product-2 fixture into a complete Product-3 file."""

    grid, time, kp_start = write_precipitation_product(
        filename, include_ratio=False, ssalon_values=ssalon_values
    )

    with Dataset(filename, "a") as nc:
        nc.product_type = "conductance"
        nc.precipitation_method = "zhang_paxton"
        nc.conductance_model = "robinson"
        nc.source_precipitation = "precipitation/or_0001.nc"
        nc.precipitation_physics_package = "icPhysics"
        nc.conductance_module = "icphysics.conductance"
        nc.conductance_function = "robinson_conductance"

        shape = (
            len(nc.dimensions["time"]),
            len(nc.dimensions["dim1"]),
            len(nc.dimensions["dim2"]),
        )
        values = np.arange(np.prod(shape), dtype=float).reshape(shape)
        for offset, name in enumerate(("P", "H", "dP", "dH")):
            variable = nc.createVariable(name, "f4", ("time", "dim1", "dim2"))
            variable[:] = values + offset

    return grid, time, kp_start


def test_load_binned_product(tmp_path):
    filename = tmp_path / "si12.nc"
    original_grid, original_time = write_binned_product(filename)

    image = icreader.load(filename)

    assert isinstance(image, icreader.BinnedImage)
    assert image.product_type == "binned_fuv"
    assert image.schema_version == 1
    assert image.sensor == "SI12"
    assert image.correction == "raw"
    assert image.los_correction is True
    assert image.binning_method == "footprint"
    assert image.shape == (2, 3, 4)
    assert image.nt == 2
    assert image.time.tolist() == original_time
    assert image.counts.dtype == np.dtype("int32")
    np.testing.assert_array_equal(image.counts, 3)
    np.testing.assert_allclose(
        image.coverage,
        np.arange(np.prod(image.shape)).reshape(image.shape),
    )
    np.testing.assert_allclose(image.ssalon, [12.0, 13.0])

    # Explicit xi/eta coordinates are needed to recover nested SI grids exactly.
    np.testing.assert_allclose(image.grid.xi, original_grid.xi)
    np.testing.assert_allclose(image.grid.eta, original_grid.eta)
    np.testing.assert_allclose(image.mlat, original_grid.lat)
    np.testing.assert_allclose(image.mlt, np.mod(original_grid.lon / 15, 24))


@pytest.mark.parametrize("include_ratio", [True, False])
def test_load_precipitation_product(tmp_path, include_ratio):
    filename = tmp_path / "precipitation.nc"
    original_grid, original_time, kp_start = write_precipitation_product(
        filename, include_ratio=include_ratio
    )

    image = icreader.load(filename)

    assert isinstance(image, icreader.PrecipitationImage)
    assert image.product_type == "precipitation"
    assert image.schema_version == 2
    assert image.precipitation_method == (
        "image_ratio" if include_ratio else "zhang_paxton"
    )
    assert image.proton_flux_source == "SI12"
    assert image.proton_energy_model == "hardy"
    assert image.proton_response_energy_min == pytest.approx(0.47)
    assert image.Ep_clipping_flag.all()
    assert image.time.tolist() == original_time
    assert image.kp_interval_start.tolist() == kp_start
    np.testing.assert_allclose(image.kp, [2.0, 2.3])
    np.testing.assert_array_equal(image.source_indices["wic"], [3, 4])
    assert image.physics_provenance == {
        "package": "icPhysics", "version": "0.1"
    }
    assert image.kp_provenance == {
        "source": "GFZ", "status": "definitive"
    }
    assert image.source_products["wic"] == "wic/or_0001.nc"
    assert image.sensor_provenance["si12"]["los_correction"] is True
    assert image.shape == (2, 3, 4)
    assert image.w.shape == image.shape
    np.testing.assert_allclose(image.grid.xi, original_grid.xi)
    np.testing.assert_allclose(image.grid.eta, original_grid.eta)
    assert hasattr(image, "R") is include_ratio
    assert hasattr(image, "dR") is include_ratio


def test_load_conductance_product(tmp_path):
    filename = tmp_path / "conductance.nc"
    original_grid, original_time, kp_start = write_conductance_product(filename)

    image = icreader.load(filename)

    assert isinstance(image, icreader.ModularConductanceImage)
    assert icreader.LegacyConductanceImage is icreader.ConductanceImage
    assert image.product_type == "conductance"
    assert image.schema_version == 2
    assert image.precipitation_method == "zhang_paxton"
    assert image.proton_flux_source == "SI12"
    assert image.proton_energy_model == "hardy"
    assert image.Ep_clipping_flag.all()
    assert image.conductance_model == "robinson"
    assert image.source_precipitation == "precipitation/or_0001.nc"
    assert image.time.tolist() == original_time
    assert image.kp_interval_start.tolist() == kp_start
    np.testing.assert_allclose(image.kp, [2.0, 2.3])
    np.testing.assert_allclose(image.ssalon, [12.0, 13.0])
    assert image.precipitation_provenance["package"] == "icPhysics"
    assert image.conductance_provenance == {
        "module": "icphysics.conductance",
        "function": "robinson_conductance",
    }
    assert image.kp_provenance["source"] == "GFZ"
    assert image.shape == (2, 3, 4)
    assert image.nt == 2
    for name in (
        "Ep_model", "Ep", "dEp", "Fp", "dFp", "E0", "dE0", "Fe",
        "dFe", "varE0Fe", "P", "H", "dP", "dH", "w",
    ):
        assert getattr(image, name).shape == image.shape
    np.testing.assert_allclose(image.grid.xi, original_grid.xi)
    np.testing.assert_allclose(image.grid.eta, original_grid.eta)
    expected_mlon = np.mod(
        image.mlt[None, :, :] * 15 - 180
        + np.asarray([12.0, 13.0])[:, None, None],
        360,
    )
    np.testing.assert_allclose(image.mlon, expected_mlon)


def test_conductance_loader_requires_ssalon(tmp_path):
    filename = tmp_path / "conductance_without_ssalon.nc"
    write_conductance_product(filename, ssalon_values=None)

    with pytest.raises(ValueError, match="conductance product is missing: ssalon"):
        icreader.load(filename)


def test_conductance_loader_validates_ssalon_time_shape(tmp_path):
    filename = tmp_path / "conductance_with_bad_ssalon.nc"
    write_conductance_product(filename, ssalon_values=(12.0,))

    with pytest.raises(
        ValueError, match="ssalon does not match the conductance time dimension"
    ):
        icreader.load(filename)


def test_conductance_loader_rejects_an_unknown_schema(tmp_path):
    filename = tmp_path / "future_conductance.nc"
    write_descriptor(filename, "conductance", schema_version=3)

    with pytest.raises(
        ValueError, match="unsupported conductance schema_version 3"
    ):
        icreader.load(filename)


def test_precipitation_loader_rejects_an_unknown_schema(tmp_path):
    filename = tmp_path / "future_precipitation.nc"
    write_descriptor(filename, "precipitation", schema_version=3)

    with pytest.raises(
        ValueError, match="unsupported precipitation schema_version 3"
    ):
        icreader.load(filename)


def test_load_rejects_missing_or_unknown_product_type(tmp_path):
    missing = tmp_path / "missing.nc"
    unknown = tmp_path / "unknown.nc"
    write_descriptor(missing)
    write_descriptor(unknown, "mystery")

    with pytest.raises(ValueError, match="no product_type"):
        icreader.load(missing)
    with pytest.raises(ValueError, match="unknown product_type"):
        icreader.load(unknown)


def test_binned_loader_rejects_an_unknown_schema(tmp_path):
    filename = tmp_path / "future.nc"
    write_descriptor(filename, "binned_fuv", schema_version=2)

    with pytest.raises(ValueError, match="unsupported binned_fuv schema_version 2"):
        icreader.load(filename)
