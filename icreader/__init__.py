# icreader/__init__.py

from netCDF4 import Dataset

from .binnedimage import BinnedImage
from .conductanceimage import ConductanceImage
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

    raise ValueError(f"unknown product_type '{product_type}'")


__all__ = [
    "load",
    "BinnedImage",
    "PrecipitationImage",
    "ConductanceImage",
    "LegacyConductanceImage",
    "ModularConductanceImage",
    "SplineImage"
]
