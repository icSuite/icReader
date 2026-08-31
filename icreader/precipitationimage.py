"""Reader for modular IMAGE-FUV precipitation products."""

#%% Imports

import numpy as np
from netCDF4 import Dataset, num2date

from .binnedimage import check_product, load_grid, load_time


#%% Small NetCDF helpers

def load_datetime(nc, name):
    """Decode one CF-style datetime variable."""

    if name not in nc.variables:
        raise ValueError(f"precipitation product is missing: {name}")

    variable = nc.variables[name]
    if not hasattr(variable, "units"):
        raise ValueError(f"{name} has no units")

    calendar = getattr(variable, "calendar", "standard")
    values = num2date(
        variable[:], variable.units, calendar,
        only_use_cftime_datetimes=False,
    )
    return np.asarray(values, dtype=object)


def attributes_with_prefix(nc, prefix):
    """Collect root attributes and remove their common prefix."""

    result = {}
    for name in nc.ncattrs():
        if name.startswith(prefix):
            result[name[len(prefix):]] = nc.getncattr(name)
    return result


#%% Precipitation reader

class PrecipitationImage:
    """Load one modular precipitation-orbit product."""

    def __init__(self, filename):
        self.filename = str(filename)

        with Dataset(filename) as nc:
            check_product(nc, "precipitation", schema_version=2)

            # Processing choices and provenance
            self.product_type = nc.product_type
            self.schema_version = int(nc.schema_version)
            self.method = str(nc.method)
            self.precipitation_method = self.method
            self.proton_flux_source = str(nc.proton_flux_source)
            self.proton_energy_model = str(nc.proton_energy_model)
            self.proton_energy_uncertainty_method = str(
                nc.proton_energy_uncertainty_method
            )
            self.proton_energy_coordinate_note = str(
                nc.proton_energy_coordinate_note
            )
            self.proton_response_energy_min = float(nc.proton_response_energy_min)
            self.proton_response_energy_max = float(nc.proton_response_energy_max)
            if self.proton_energy_model == "constant":
                self.proton_energy_constant = float(nc.proton_energy_constant)
                self.proton_energy_uncertainty_constant = float(
                    nc.proton_energy_uncertainty_constant
                )
            self.time_match_tolerance_seconds = float(
                nc.time_match_tolerance_seconds
            )
            self.time_match_rule = str(nc.time_match_rule)
            self.regrid_method = str(nc.regrid_method)
            self.regrid_uncertainty = str(nc.regrid_uncertainty)

            self.physics_provenance = attributes_with_prefix(nc, "physics_")
            self.kp_provenance = attributes_with_prefix(nc, "kp_")
            self.source_products = attributes_with_prefix(nc, "source_")

            self.sensor_provenance = {}
            for sensor in ("wic", "si12", "si13"):
                correction = f"{sensor}_image_correction"
                los_correction = f"{sensor}_los_correction"
                if correction in nc.ncattrs():
                    self.sensor_provenance[sensor] = {
                        "image_correction": str(nc.getncattr(correction)),
                        "los_correction": bool(nc.getncattr(los_correction)),
                    }

            # Time-dependent coordinates
            self.time = load_time(nc)
            self.kp_interval_start = load_datetime(nc, "Kp_interval_start")

            one_dimensional = {
                "kp": "Kp",
                "ssalon": "ssalon",
                "wic_source_index": "wic_source_index",
                "si12_source_index": "si12_source_index",
                "si13_source_index": "si13_source_index",
            }
            for attribute, variable in one_dimensional.items():
                if variable not in nc.variables:
                    raise ValueError(
                        f"precipitation product is missing: {variable}"
                    )
                setattr(self, attribute, np.asarray(nc.variables[variable][:]))

            self.source_indices = {
                "wic": self.wic_source_index,
                "si12": self.si12_source_index,
                "si13": self.si13_source_index,
            }

            # Sensor observations and precipitation estimates
            field_names = (
                "wic", "dwic", "si12", "dsi12", "si13", "dsi13",
                "wic_weight", "si12_weight", "si13_weight",
                "wic_corrected", "dwic_corrected",
                "si13_corrected", "dsi13_corrected",
                "Ep_model", "Ep", "dEp", "Fp", "dFp",
                "E0", "dE0", "Fe", "dFe", "varE0Fe",
            )
            missing = [name for name in field_names if name not in nc.variables]
            if missing:
                raise ValueError(
                    f"precipitation product is missing: {', '.join(missing)}"
                )

            for name in field_names:
                setattr(self, name, np.asarray(nc.variables[name][:]))

            if "Ep_clipping_flag" not in nc.variables:
                raise ValueError("precipitation product is missing: Ep_clipping_flag")
            self.Ep_clipping_flag = np.asarray(
                nc.variables["Ep_clipping_flag"][:], dtype=bool
            )

            # These fields depend on the selected precipitation method/schema.
            for name in ("w", "R", "dR"):
                if name in nc.variables:
                    setattr(self, name, np.asarray(nc.variables[name][:]))

            self.grid = load_grid(nc)

        # All image fields use one common time and spatial grid.
        self.shape = self.E0.shape
        if len(self.shape) != 3:
            raise ValueError("precipitation image fields must be three-dimensional")

        image_fields = list(field_names) + ["Ep_clipping_flag"]
        image_fields += [name for name in ("w", "R", "dR") if hasattr(self, name)]
        for name in image_fields:
            if getattr(self, name).shape != self.shape:
                raise ValueError(
                    f"{name} does not match the precipitation image dimensions"
                )

        if hasattr(self, "R") != hasattr(self, "dR"):
            raise ValueError("R and dR must either both be present or both be absent")

        for name in (
            "time", "kp", "kp_interval_start", "ssalon",
            "wic_source_index", "si12_source_index", "si13_source_index",
        ):
            if getattr(self, name).shape != (self.shape[0],):
                raise ValueError(
                    f"{name} does not match the precipitation time dimension"
                )

        if self.grid.shape != self.shape[1:]:
            raise ValueError("grid does not match the precipitation image dimensions")

    @property
    def nt(self):
        return self.shape[0]

    @property
    def mlat(self):
        return self.grid.lat

    @property
    def mlt(self):
        return np.mod(self.grid.lon / 15, 24)

    @property
    def mlon(self):
        return np.mod(
            self.mlt[None, :, :] * 15 - 180 + self.ssalon[:, None, None],
            360,
        )

    def __repr__(self):
        text = f"<PrecipitationImage: {self.method}>"
        text += f"\nTimespan: {self.time[0]} to {self.time[-1]}"
        text += f"\nTemporal dim: {self.shape[0]}"
        text += f"\nSpatial dim: {self.shape[1]} x {self.shape[2]}"
        return text
