"""On-demand readers for fixed-grid detector-first products."""

#%% Imports

import hashlib
from types import MappingProxyType

import numpy as np
from secsy import CSgrid, CSprojection

from .product import NetCDFProduct


#%% Fixed-grid contract

TIME = ("time",)
IMAGE = ("time", "dim1", "dim2")

GRID_REGISTRY = MappingProxyType({
    "image_apex_130km_46x46_v1": MappingProxyType({
        "L": 50_000_000.0,
        "W": 50_000_000.0,
        "Lres": 200_000.0,
        "Wres": 200_000.0,
        "shape": (46, 46),
    }),
})


def variable_specs(names, dimensions, kind="float", eager=False):
    return {
        name: (dimensions, kind, eager)
        for name in names
    }


COMMON_TIME_VARIABLES = {
    **variable_specs(
        (
            "time", "wic_source_time", "si12_source_time",
            "si13_source_time", "Kp_interval_start",
        ),
        TIME,
        "time",
        True,
    ),
    **variable_specs(
        ("wic_source_index", "si12_source_index", "si13_source_index"),
        TIME,
        "int",
        True,
    ),
    **variable_specs(
        ("wic_frame_quality", "si12_frame_quality", "si13_frame_quality"),
        TIME,
        "int",
        True,
    ),
    "Kp": (TIME, "float", True),
    "ssalon": (TIME, "float", True),
}


def coordinate_hash(grid):
    """Return the frozen coordinate fingerprint used by icBuilder."""

    arrays = (
        grid.xi_mesh[0],
        grid.eta_mesh[:, 0],
        grid.xi,
        grid.eta,
        grid.lat,
        np.mod(grid.lon / 15.0, 24.0),
    )
    digest = hashlib.sha256()
    for values in arrays:
        digest.update(np.asarray(values, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


#%% Common CS behavior

class CSProduct(NetCDFProduct):
    """Common metadata and verified secsy grid for fixed-grid products."""

    REPRESENTATION = "cs"
    SCHEMA_VERSION = 1
    DIMENSIONS = ("time", "dim1", "dim2")
    REQUIRED_ATTRIBUTES = (
        "grid_id", "grid_coordinate_sha256", "binning_method",
        "uncertainty_method", "coordinate_system", "reference_height_km",
        "software_version",
    )

    def _finish_initialization(self):
        for name in self.REQUIRED_ATTRIBUTES:
            setattr(self, name, self.attrs[name])

        if self.attrs.get("proton_energy_model") == "constant":
            for name in (
                "proton_energy_constant",
                "proton_energy_uncertainty_constant",
            ):
                if name not in self.attrs:
                    raise ValueError(
                        f"{self.PRODUCT_TYPE} is missing attribute: {name}"
                    )
                setattr(self, name, float(self.attrs[name]))

        self.source_indices = MappingProxyType({
            sensor: getattr(self, f"{sensor}_source_index")
            for sensor in ("wic", "si12", "si13")
        })
        self.source_times = MappingProxyType({
            sensor: getattr(self, f"{sensor}_source_time")
            for sensor in ("wic", "si12", "si13")
        })
        self.frame_quality = MappingProxyType({
            sensor: getattr(self, f"{sensor}_frame_quality")
            for sensor in ("wic", "si12", "si13")
        })
        self.kp_provenance = self.attributes_with_prefix("kp_")
        self.source_products = self.attributes_with_prefix("source_")
        self.grid = self._load_grid()

    def _load_grid(self):
        if "grid" not in self._nc.groups:
            raise ValueError(f"{self.PRODUCT_TYPE} has no grid group")
        group = self._nc.groups["grid"]

        required_attributes = (
            "grid_id", "coordinate_sha256", "position", "orientation",
            "reference_height_km", "radius_metres",
        )
        missing_attributes = [
            name for name in required_attributes if name not in group.ncattrs()
        ]
        if missing_attributes:
            raise ValueError(
                f"grid group is missing attributes: {', '.join(missing_attributes)}"
            )

        required_variables = {
            "xi": ("dim1", "dim2"),
            "eta": ("dim1", "dim2"),
            "mlat": ("dim1", "dim2"),
            "mlt": ("dim1", "dim2"),
            "xi_edge": ("dim2_edge",),
            "eta_edge": ("dim1_edge",),
        }
        missing_variables = [
            name for name in required_variables if name not in group.variables
        ]
        if missing_variables:
            raise ValueError(
                f"grid group is missing variables: {', '.join(missing_variables)}"
            )
        for name, dimensions in required_variables.items():
            if group.variables[name].dimensions != dimensions:
                raise ValueError(
                    f"grid/{name} dimensions are "
                    f"{group.variables[name].dimensions}; expected {dimensions}"
                )

        if group.grid_id != self.grid_id:
            raise ValueError("root and grid-group grid_id differ")
        if group.coordinate_sha256 != self.grid_coordinate_sha256:
            raise ValueError("root and grid-group coordinate hashes differ")
        if not np.isclose(
            float(group.reference_height_km), float(self.reference_height_km)
        ):
            raise ValueError("root and grid-group reference heights differ")
        if self.grid_id not in GRID_REGISTRY:
            raise ValueError(f"unsupported CS grid_id '{self.grid_id}'")

        position = np.asarray(group.position, dtype=float)
        orientation = np.asarray(group.orientation, dtype=float)
        radius = float(group.radius_metres)
        if position.shape != (2,) or orientation.shape != (2,):
            raise ValueError("grid projection position and orientation must be pairs")
        if not np.all(np.isfinite(position)) or not np.all(np.isfinite(orientation)):
            raise ValueError("grid projection contains non-finite values")
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError("grid radius must be positive and finite")

        contract = GRID_REGISTRY[self.grid_id]
        if self.shape[1:] != contract["shape"]:
            raise ValueError(
                f"{self.grid_id} requires shape {contract['shape']}; "
                f"got {self.shape[1:]}"
            )

        stored = {
            name: np.asarray(group.variables[name][:], dtype=float)
            for name in required_variables
        }
        grid = CSgrid(
            CSprojection(
                position,
                orientation,
            ),
            L=contract["L"],
            W=contract["W"],
            Lres=contract["Lres"],
            Wres=contract["Wres"],
            edges=(stored["xi_edge"], stored["eta_edge"]),
            R=radius,
        )

        reconstructed = {
            "xi": np.asarray(grid.xi),
            "eta": np.asarray(grid.eta),
            "mlat": np.asarray(grid.lat),
            "mlt": np.mod(np.asarray(grid.lon) / 15.0, 24.0),
            "xi_edge": np.asarray(grid.xi_mesh[0]),
            "eta_edge": np.asarray(grid.eta_mesh[:, 0]),
        }
        differing = [
            name for name in stored
            if not np.array_equal(reconstructed[name], stored[name])
        ]
        if differing:
            raise ValueError(
                "stored coordinates do not reconstruct the declared CS grid: "
                + ", ".join(differing)
            )

        reconstructed_hash = coordinate_hash(grid)
        if reconstructed_hash != self.grid_coordinate_sha256:
            raise ValueError(
                "reconstructed CS grid coordinate hash does not match the file"
            )
        return grid

    @property
    def mlat(self):
        return self.grid.lat

    @property
    def mlt(self):
        return np.mod(self.grid.lon / 15.0, 24.0)

    @property
    def mlon(self):
        return np.mod(
            self.mlt[None, :, :] * 15.0 - 180.0
            + self.ssalon[:, None, None],
            360.0,
        )


#%% CS Product 2

class PrecipitationCS(CSProduct):
    """Read schema-1 precipitation reduced onto the frozen CS grid."""

    PRODUCT_TYPE = "precipitation_cs"
    REQUIRED_ATTRIBUTES = CSProduct.REQUIRED_ATTRIBUTES + (
        "method", "proton_flux_source", "proton_energy_model",
        "proton_energy_uncertainty_method", "proton_energy_coordinate_note",
        "proton_response_energy_min", "proton_response_energy_max",
        "proton_operation_order", "count_uncertainty_mode",
        "count_uncertainty_method", "source_precipitation_detector",
        "source_precipitation_detector_sha256", "source_fuv_detector",
        "source_fuv_detector_sha256",
    )

    _FLOAT_FIELDS = (
        "sza", "dza", "method_quality_weight",
        "wic_coverage", "si12_coverage", "si13_coverage",
        "Ep_model", "Ep", "Fp", "wic_corrected", "si13_corrected",
        "R", "E0", "Fe",
        "dEp", "dFp", "dwic_corrected", "dsi13_corrected",
        "dR", "dE0", "dFe", "varE0Fe",
        "coverage", "uncertainty_coverage", "Ep_clipping_fraction",
    )
    _COUNT_FIELDS = ("source_count", "uncertainty_source_count")
    _BOOL_FIELDS = (
        "method_valid", "method_uncertainty_valid", "Ep_clipping_any",
    )

    VARIABLES = {
        **COMMON_TIME_VARIABLES,
        **variable_specs(_FLOAT_FIELDS, IMAGE),
        **variable_specs(_COUNT_FIELDS, IMAGE, "int"),
        **variable_specs(_BOOL_FIELDS, IMAGE, "bool"),
    }

    def _finish_initialization(self):
        super()._finish_initialization()
        self.precipitation_method = self.method


#%% CS Product 3

class ConductanceCS(CSProduct):
    """Read schema-1 detector-derived conductance on the frozen CS grid."""

    PRODUCT_TYPE = "conductance_cs"
    REQUIRED_ATTRIBUTES = CSProduct.REQUIRED_ATTRIBUTES + (
        "conductance_model", "conductance_uncertainty_method",
        "precipitation_method", "proton_flux_source", "proton_energy_model",
        "proton_energy_uncertainty_method", "proton_energy_coordinate_note",
        "proton_response_energy_min", "proton_response_energy_max",
        "proton_operation_order", "count_uncertainty_mode",
        "count_uncertainty_method", "source_conductance_detector",
        "source_conductance_detector_sha256", "source_precipitation_detector",
        "source_precipitation_detector_sha256", "companion_precipitation_cs",
        "source_fuv_detector", "source_fuv_detector_sha256",
    )

    _FLOAT_FIELDS = (
        "method_quality_weight", "E0", "Fe", "P", "H",
        "dE0", "dFe", "dP", "dH", "varE0Fe",
        "coverage", "uncertainty_coverage", "Ep_clipping_fraction",
    )
    _COUNT_FIELDS = ("source_count", "uncertainty_source_count")
    _BOOL_FIELDS = (
        "conductance_valid", "conductance_uncertainty_valid",
        "Ep_clipping_any",
    )

    VARIABLES = {
        **COMMON_TIME_VARIABLES,
        **variable_specs(_FLOAT_FIELDS, IMAGE),
        **variable_specs(_COUNT_FIELDS, IMAGE, "int"),
        **variable_specs(_BOOL_FIELDS, IMAGE, "bool"),
    }
