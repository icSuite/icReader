"""Reader for modular Hall and Pedersen conductance products."""

#%% Imports

import numpy as np
from netCDF4 import Dataset

from .binnedimage import check_product, load_grid, load_time
from .precipitationimage import attributes_with_prefix, load_datetime


#%% Conductance reader

class ModularConductanceImage:
    """Load one modular conductance-orbit product."""

    def __init__(self, filename):
        self.filename = str(filename)

        with Dataset(filename) as nc:
            check_product(nc, "conductance")

            # Processing choices and provenance
            self.product_type = nc.product_type
            self.schema_version = int(nc.schema_version)
            self.precipitation_method = str(nc.precipitation_method)
            self.proton_method = str(nc.proton_method)
            self.proton_energy = float(nc.proton_energy)
            self.proton_energy_uncertainty = float(
                nc.proton_energy_uncertainty
            )
            self.conductance_model = str(nc.conductance_model)
            self.source_precipitation = getattr(
                nc, "source_precipitation", None
            )

            self.precipitation_provenance = attributes_with_prefix(
                nc, "precipitation_physics_"
            )
            self.conductance_provenance = attributes_with_prefix(
                nc, "conductance_"
            )
            self.conductance_provenance.pop("model", None)
            self.kp_provenance = attributes_with_prefix(nc, "kp_")

            # Time-dependent coordinates
            self.time = load_time(nc)
            self.kp_interval_start = load_datetime(nc, "Kp_interval_start")
            one_dimensional = {
                "kp": "Kp",
                "ssalon": "ssalon",
            }
            for attribute, variable in one_dimensional.items():
                if variable not in nc.variables:
                    raise ValueError(
                        f"conductance product is missing: {variable}"
                    )
                setattr(self, attribute, np.asarray(nc.variables[variable][:]))

            # Precipitation state, conductance, uncertainties, and weight
            field_names = (
                "E0", "dE0", "Fe", "dFe", "varE0Fe",
                "P", "H", "dP", "dH", "w",
            )
            missing = [name for name in field_names if name not in nc.variables]
            if missing:
                raise ValueError(
                    f"conductance product is missing: {', '.join(missing)}"
                )

            for name in field_names:
                setattr(self, name, np.asarray(nc.variables[name][:]))

            self.grid = load_grid(nc)

        self.shape = self.P.shape
        if len(self.shape) != 3:
            raise ValueError("conductance image fields must be three-dimensional")

        for name in field_names:
            if getattr(self, name).shape != self.shape:
                raise ValueError(
                    f"{name} does not match the conductance image dimensions"
                )

        for name in ("time", "kp", "kp_interval_start", "ssalon"):
            if getattr(self, name).shape != (self.shape[0],):
                raise ValueError(
                    f"{name} does not match the conductance time dimension"
                )

        if self.grid.shape != self.shape[1:]:
            raise ValueError("grid does not match the conductance image dimensions")

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
        text = f"<ModularConductanceImage: {self.conductance_model}>"
        text += f"\nTimespan: {self.time[0]} to {self.time[-1]}"
        text += f"\nTemporal dim: {self.shape[0]}"
        text += f"\nSpatial dim: {self.shape[1]} x {self.shape[2]}"
        return text
