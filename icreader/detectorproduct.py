"""On-demand readers for detector-first icBuilder products."""

#%% Imports

from types import MappingProxyType

from .product import NetCDFProduct


#%% Schema helpers

TIME = ("time",)
IMAGE = ("time", "row", "column")


def variable_specs(names, dimensions, kind="float", eager=False):
    return {
        name: (dimensions, kind, eager)
        for name in names
    }


def coregistration_names(names):
    return tuple(
        f"{sensor}_coreg_{name}"
        for sensor in ("si12", "si13")
        for name in names
    )


COMMON_TIME_VARIABLES = {
    **variable_specs(
        ("time", "wic_source_time", "si12_source_time", "si13_source_time"),
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
    "detector_row": (("row",), "int", True),
    "detector_column": (("column",), "int", True),
    "ssalon": (TIME, "float", True),
}

GEOMETRY_FIELDS = (
    "glat", "glon", "mlat", "mlon", "mlt", "sza", "dza",
)


#%% Common detector behavior

class DetectorProduct(NetCDFProduct):
    """Common identity and frame access for WIC-geometry products."""

    REPRESENTATION = "detector"
    DIMENSIONS = ("time", "row", "column")

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


#%% Detector Product 1

class FUVDetector(DetectorProduct):
    """Read schema-2 coregistered FUV observations on WIC pixels."""

    PRODUCT_TYPE = "fuv_detector"
    SCHEMA_VERSION = 2
    REQUIRED_ATTRIBUTES = (
        "preprocessing_label", "software_version",
        "time_match_tolerance_seconds", "time_match_rule",
        "source_time_decoding", "quality_weight_method",
        "detector_noise_model", "coordinate_system", "reference_height_km",
        "coregistration_method", "coregistration_footprint_model",
        "coregistration_max_roundtrip_error_km",
        "coregistration_minimum_coverage",
        "coregistration_overlap_operator_stored",
        "source_wic", "source_si12", "source_si13",
        "source_wic_sha256", "source_si12_sha256", "source_si13_sha256",
    )

    _FLOAT_FIELDS = (
        "wic_counts", "si12_counts", "si13_counts",
        "wic_variance", "si12_variance", "si13_variance",
        "wic_quality_weight", "si12_quality_weight", "si13_quality_weight",
        "wic_coverage", "si12_coverage", "si13_coverage",
        *GEOMETRY_FIELDS,
    )
    _BOOL_FIELDS = ("wic_valid", "si12_valid", "si13_valid")
    _COUNT_FIELDS = ("si12_source_count", "si13_source_count")
    _COREG_INT = (
        "valid_source_centres", "valid_source_footprints",
        "accepted_target_pixels",
    )
    _COREG_FLOAT = (
        "roundtrip_median_km", "roundtrip_95th_km",
        "coverage_median", "coverage_95th", "coverage_maximum",
    )

    VARIABLES = {
        **COMMON_TIME_VARIABLES,
        **variable_specs(_FLOAT_FIELDS, IMAGE),
        **variable_specs(_BOOL_FIELDS, IMAGE, "bool"),
        **variable_specs(_COUNT_FIELDS, IMAGE, "int"),
        **variable_specs(
            coregistration_names(_COREG_INT),
            TIME,
            "int",
            True,
        ),
        **variable_specs(
            coregistration_names(_COREG_FLOAT),
            TIME,
            "float",
            True,
        ),
    }

    def _finish_initialization(self):
        super()._finish_initialization()
        self.source_products = MappingProxyType({
            sensor: self.attrs[f"source_{sensor}"]
            for sensor in ("wic", "si12", "si13")
        })


#%% Detector Product 2

class PrecipitationDetector(DetectorProduct):
    """Read schema-3 image-ratio precipitation on WIC pixels."""

    PRODUCT_TYPE = "precipitation_detector"
    SCHEMA_VERSION = 3
    REQUIRED_ATTRIBUTES = (
        "method", "proton_flux_source", "proton_energy_model",
        "proton_energy_uncertainty_method", "proton_energy_coordinate_note",
        "count_uncertainty_mode", "count_uncertainty_method",
        "proton_response_energy_min", "proton_response_energy_max",
        "proton_operation_order", "source_fuv_detector",
        "source_fuv_detector_sha256", "source_preprocessing_label",
        "source_fuv_detector_time_decoding", "coordinate_system",
        "reference_height_km", "software_version",
    )

    _FLOAT_FIELDS = (
        *GEOMETRY_FIELDS,
        "wic_quality_weight", "si12_quality_weight", "si13_quality_weight",
        "method_quality_weight",
        "wic_coverage", "si12_coverage", "si13_coverage",
        "Ep_model", "Ep", "dEp", "Fp", "dFp",
        "wic_corrected", "dwic_corrected",
        "si13_corrected", "dsi13_corrected",
        "R", "dR", "E0", "dE0", "Fe", "dFe", "varE0Fe",
    )
    _BOOL_FIELDS = (
        "wic_valid", "si12_valid", "si13_valid", "method_valid",
        "Ep_clipping_flag",
    )
    _COUNT_FIELDS = ("si12_source_count", "si13_source_count")

    VARIABLES = {
        **COMMON_TIME_VARIABLES,
        "Kp_interval_start": (TIME, "time", True),
        "Kp": (TIME, "float", True),
        **variable_specs(_FLOAT_FIELDS, IMAGE),
        **variable_specs(_BOOL_FIELDS, IMAGE, "bool"),
        **variable_specs(_COUNT_FIELDS, IMAGE, "int"),
    }

    def _finish_initialization(self):
        super()._finish_initialization()
        self.precipitation_method = self.method
        self.source_products = self.attributes_with_prefix("source_")


#%% Detector Product 3

class ConductanceDetector(DetectorProduct):
    """Read schema-2 Robinson conductance on WIC pixels."""

    PRODUCT_TYPE = "conductance_detector"
    SCHEMA_VERSION = 2
    REQUIRED_ATTRIBUTES = (
        "conductance_model", "conductance_uncertainty_method",
        "precipitation_method", "proton_flux_source", "proton_energy_model",
        "proton_energy_uncertainty_method", "proton_energy_coordinate_note",
        "proton_response_energy_min", "proton_response_energy_max",
        "proton_operation_order", "count_uncertainty_mode",
        "count_uncertainty_method", "source_precipitation_detector",
        "source_precipitation_detector_sha256", "source_fuv_detector",
        "source_fuv_detector_sha256", "source_preprocessing_label",
        "source_fuv_detector_time_decoding", "coordinate_system",
        "reference_height_km", "software_version",
    )

    _FLOAT_FIELDS = (
        *GEOMETRY_FIELDS, "method_quality_weight",
        "Ep_model", "Ep", "dEp", "Fp", "dFp",
        "E0", "dE0", "Fe", "dFe", "varE0Fe",
        "P", "H", "dP", "dH",
    )
    _BOOL_FIELDS = (
        "method_valid", "conductance_valid",
        "conductance_uncertainty_valid", "Ep_clipping_flag",
    )

    VARIABLES = {
        **COMMON_TIME_VARIABLES,
        "Kp_interval_start": (TIME, "time", True),
        "Kp": (TIME, "float", True),
        **variable_specs(_FLOAT_FIELDS, IMAGE),
        **variable_specs(_BOOL_FIELDS, IMAGE, "bool"),
    }

    def _finish_initialization(self):
        super()._finish_initialization()
        self.source_products = self.attributes_with_prefix("source_")
