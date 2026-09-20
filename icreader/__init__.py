# icreader/__init__.py

from netCDF4 import Dataset

from .binnedimage import BinnedImage
from .conductanceimage import ConductanceImage
from .csproduct import ConductanceCS, PrecipitationCS
from .detectorproduct import (
    ConductanceDetector,
    FUVDetector,
    PrecipitationDetector,
)
from .modularconductanceimage import ModularConductanceImage
from .precipitationimage import PrecipitationImage
from .splineimage import SplineImage

# The direct class remains available for the existing, pre-modular files.
LegacyConductanceImage = ConductanceImage


def load(filename):
    """Load a modular icBuilder product using its NetCDF descriptor."""

    with Dataset(filename) as nc:
        if "product_type" not in nc.ncattrs():
            raise ValueError("NetCDF file has no product_type descriptor")
        product_type = nc.product_type

    if product_type == "binned_fuv":
        return BinnedImage(filename)
    if product_type == "precipitation":
        return PrecipitationImage(filename)
    if product_type == "conductance":
        return ModularConductanceImage(filename)
    if product_type == "fuv_detector":
        return FUVDetector(filename)
    if product_type == "precipitation_detector":
        return PrecipitationDetector(filename)
    if product_type == "conductance_detector":
        return ConductanceDetector(filename)
    if product_type == "precipitation_cs":
        return PrecipitationCS(filename)
    if product_type == "conductance_cs":
        return ConductanceCS(filename)

    raise ValueError(f"unknown product_type '{product_type}'")


open_product = load


__all__ = [
    "load",
    "open_product",
    "BinnedImage",
    "PrecipitationImage",
    "FUVDetector",
    "PrecipitationDetector",
    "ConductanceDetector",
    "PrecipitationCS",
    "ConductanceCS",
    "ConductanceImage",
    "LegacyConductanceImage",
    "ModularConductanceImage",
    "SplineImage"
]
