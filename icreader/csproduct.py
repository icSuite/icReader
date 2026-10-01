"""On-demand readers for fixed-grid detector-first products."""

#%% Imports

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


#%% Common CS behavior

class CSProduct(NetCDFProduct):
    """Common metadata and verified secsy grid for fixed-grid products."""

    REPRESENTATION = "cs"
    SCHEMA_VERSION = 1
    DIMENSIONS = ("time", "dim1", "dim2")
    REQUIRED_ATTRIBUTES = (
        "grid_id", "binning_method", "uncertainty_method",
        "coordinate_system", "reference_height_km", "software_version",
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
            "grid_id", "position", "orientation", "reference_height_km",
            "radius_metres",
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

        if grid.shape != contract["shape"]:
            raise ValueError(
                f"{self.grid_id} reconstructed as shape {grid.shape}; "
                f"expected {contract['shape']}"
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
    OPTIONAL_VARIABLES = variable_specs(("si12", "dsi12"), IMAGE)

    def _finish_initialization(self):
        super()._finish_initialization()
        self.count_source = self.attrs.get(
            "count_source", "background_subtracted"
        )
        legacy_smoothed = (
            self.attrs.get("spatial_smoothing_kernel", "none") != "none"
        )
        self.smoothed = bool(int(
            self.attrs.get("smoothed", legacy_smoothed)
        ))
        self.smoothing_method = self.attrs.get(
            "smoothing_method",
            self.attrs.get("spatial_smoothing_kernel", "none"),
        )
        self.spatial_smoothing_kernel = self.smoothing_method
        self.wic_smoothing_width_pixels = float(
            self.attrs.get("wic_smoothing_width_pixels", 0.0)
        )
        self.si12_smoothing_width_pixels = float(
            self.attrs.get("si12_smoothing_width_pixels", 0.0)
        )
        self.si13_smoothing_width_pixels = float(
            self.attrs.get("si13_smoothing_width_pixels", 0.0)
        )
        for sensor in ("wic", "si12", "si13"):
            width = getattr(self, f"{sensor}_smoothing_width_pixels")
            setattr(
                self,
                f"{sensor}_smoothing_applied",
                bool(int(self.attrs.get(
                    f"{sensor}_smoothing_applied", width > 0
                ))),
            )
        self.method_quality_weight_method = self.attrs.get(
            "method_quality_weight_method", "unrecorded"
        )
        self.method_quality_weight_floor = float(
            self.attrs.get("method_quality_weight_floor", 0.0)
        )
        self.method_quality_weight_spatial_propagation = self.attrs.get(
            "method_quality_weight_spatial_propagation", "none"
        )
        self.precipitation_method = self.method


#%% CS Product 3

class ConductanceCS(CSProduct):
    """Read schema-1 or schema-2 detector-derived conductance on the CS grid."""

    PRODUCT_TYPE = "conductance_cs"
    SCHEMA_VERSION = 2
    SUPPORTED_SCHEMA_VERSIONS = (1, 2)
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

    def _validate_descriptor(self):
        """Accept the legacy and current CS Product-3 schemas."""

        nc = self._nc
        if "product_type" not in nc.ncattrs():
            raise ValueError("NetCDF file has no product_type descriptor")
        if nc.product_type != self.PRODUCT_TYPE:
            raise ValueError(
                f"expected product_type '{self.PRODUCT_TYPE}', "
                f"got '{nc.product_type}'"
            )
        if "representation" not in nc.ncattrs():
            raise ValueError(
                f"{self.PRODUCT_TYPE} has no representation descriptor"
            )
        if nc.representation != self.REPRESENTATION:
            raise ValueError(
                f"expected {self.PRODUCT_TYPE} representation "
                f"'{self.REPRESENTATION}', got '{nc.representation}'"
            )
        if "schema_version" not in nc.ncattrs():
            raise ValueError(
                f"{self.PRODUCT_TYPE} has no schema_version descriptor"
            )
        if int(nc.schema_version) not in self.SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported {self.PRODUCT_TYPE} schema_version "
                f"{nc.schema_version}; expected one of "
                f"{self.SUPPORTED_SCHEMA_VERSIONS}"
            )

    def _validate_attributes(self):
        super()._validate_attributes()
        if int(self._nc.schema_version) != 2:
            return
        required = (
            "count_source", "smoothed", "smoothing_method",
            "wic_smoothing_width_pixels", "si12_smoothing_width_pixels",
            "si13_smoothing_width_pixels", "wic_smoothing_applied",
            "si12_smoothing_applied", "si13_smoothing_applied",
            "smoothing_width_definition", "smoothing_operation_order",
            "smoothing_variance_method", "method_quality_weight_method",
            "method_quality_weight_floor",
            "method_quality_weight_spatial_propagation",
        )
        missing = [name for name in required if name not in self._nc.ncattrs()]
        if missing:
            raise ValueError(
                f"{self.PRODUCT_TYPE} is missing attributes: "
                f"{', '.join(missing)}"
            )

    def _finish_initialization(self):
        super()._finish_initialization()
        self.count_source = self.attrs.get(
            "count_source", "background_subtracted"
        )
        legacy_smoothed = (
            self.attrs.get("spatial_smoothing_kernel", "none") != "none"
        )
        self.smoothed = bool(int(
            self.attrs.get("smoothed", legacy_smoothed)
        ))
        self.smoothing_method = self.attrs.get(
            "smoothing_method",
            self.attrs.get("spatial_smoothing_kernel", "none"),
        )
        self.spatial_smoothing_kernel = self.smoothing_method
        for sensor in ("wic", "si12", "si13"):
            width = float(self.attrs.get(
                f"{sensor}_smoothing_width_pixels", 0.0
            ))
            setattr(self, f"{sensor}_smoothing_width_pixels", width)
            setattr(
                self,
                f"{sensor}_smoothing_applied",
                bool(int(self.attrs.get(
                    f"{sensor}_smoothing_applied", width > 0
                ))),
            )
        self.smoothing_width_definition = self.attrs.get(
            "smoothing_width_definition", "unrecorded"
        )
        self.smoothing_operation_order = self.attrs.get(
            "smoothing_operation_order", "unrecorded"
        )
        self.smoothing_variance_method = self.attrs.get(
            "smoothing_variance_method", "unrecorded"
        )
        self.method_quality_weight_method = self.attrs.get(
            "method_quality_weight_method", "unrecorded"
        )
        self.method_quality_weight_floor = float(
            self.attrs.get("method_quality_weight_floor", 0.0)
        )
        self.method_quality_weight_spatial_propagation = self.attrs.get(
            "method_quality_weight_spatial_propagation", "none"
        )
