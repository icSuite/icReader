"""Reader for native-grid IMAGE-FUV binned-image products."""

#%% Imports

import numpy as np
from netCDF4 import Dataset, num2date
from secsy import CSgrid, CSprojection


#%% NetCDF helpers

SCHEMA_VERSION = 1


def check_product(nc, expected_type):
    """Check that a NetCDF file is the expected modular product."""

    if "product_type" not in nc.ncattrs():
        raise ValueError("NetCDF file has no product_type descriptor")
    if nc.product_type != expected_type:
        raise ValueError(
            f"expected product_type '{expected_type}', got '{nc.product_type}'"
        )

    if "schema_version" not in nc.ncattrs():
        raise ValueError("NetCDF file has no schema_version descriptor")
    if int(nc.schema_version) != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported {expected_type} schema_version {nc.schema_version}; "
            f"expected {SCHEMA_VERSION}"
        )


def centers_to_edges(centers):
    """Convert one-dimensional cell centres to cell edges."""

    centers = np.asarray(centers, dtype=float)
    if centers.ndim != 1 or centers.size < 2:
        raise ValueError("grid coordinates must contain at least two cell centres")
    if not np.all(np.isfinite(centers)) or np.any(np.diff(centers) <= 0):
        raise ValueError("grid cell centres must be finite and increasing")

    edges = np.empty(centers.size + 1)
    edges[1:-1] = (centers[:-1] + centers[1:]) / 2
    edges[0] = centers[0] - (edges[1] - centers[0])
    edges[-1] = centers[-1] + (centers[-1] - edges[-2])
    return edges


def load_grid(nc):
    """Rebuild the exact cubed-sphere grid saved in a modular product."""

    if "grid" not in nc.groups:
        raise ValueError("NetCDF file has no grid group")
    group = nc.groups["grid"]

    required = ("xi", "eta", "mlat", "mlt")
    missing = [name for name in required if name not in group.variables]
    if missing:
        raise ValueError(f"grid group is missing: {', '.join(missing)}")

    xi = np.asarray(group.variables["xi"][:], dtype=float)
    eta = np.asarray(group.variables["eta"][:], dtype=float)
    mlat = np.asarray(group.variables["mlat"][:], dtype=float)
    mlt = np.asarray(group.variables["mlt"][:], dtype=float)

    if xi.ndim != 2 or eta.shape != xi.shape:
        raise ValueError("grid xi and eta must be matching two-dimensional arrays")
    if mlat.shape != xi.shape or mlt.shape != xi.shape:
        raise ValueError("grid coordinates do not have matching dimensions")
    if not np.allclose(xi, xi[0:1, :]) or not np.allclose(eta, eta[:, 0:1]):
        raise ValueError("grid xi and eta are not a rectilinear cubed-sphere grid")

    xi_edges = centers_to_edges(xi[0])
    eta_edges = centers_to_edges(eta[:, 0])

    projection = CSprojection(
        np.asarray(group.position, dtype=float),
        np.asarray(group.orientation, dtype=float),
    )
    grid = CSgrid(
        projection,
        L=float(group.L),
        W=float(group.W),
        Lres=float(group.Lres),
        Wres=float(group.Wres),
        edges=(xi_edges, eta_edges),
        R=float(group.R),
    )

    if not np.allclose(grid.xi, xi) or not np.allclose(grid.eta, eta):
        raise ValueError("saved xi and eta do not reconstruct the original grid")
    if not np.allclose(grid.lat, mlat, atol=1e-8):
        raise ValueError("saved magnetic latitude does not match the reconstructed grid")

    reconstructed_mlt = np.mod(grid.lon / 15, 24)
    mlt_difference = np.mod(reconstructed_mlt - mlt + 12, 24) - 12
    if not np.allclose(mlt_difference, 0, atol=1e-8):
        raise ValueError("saved MLT does not match the reconstructed grid")

    return grid


def load_time(nc):
    """Decode the CF-style UTC time coordinate."""

    if "time" not in nc.variables:
        raise ValueError("NetCDF file has no time variable")
    variable = nc.variables["time"]
    if not hasattr(variable, "units"):
        raise ValueError("time variable has no units")

    calendar = getattr(variable, "calendar", "standard")
    values = num2date(
        variable[:], variable.units, calendar,
        only_use_cftime_datetimes=False,
    )
    return np.asarray(values, dtype=object)


#%% Binned-image reader

class BinnedImage:
    """Load one sensor's native-grid binned IMAGE-FUV product."""

    def __init__(self, filename):
        self.filename = str(filename)

        with Dataset(filename) as nc:
            check_product(nc, "binned_fuv")

            self.product_type = nc.product_type
            self.schema_version = int(nc.schema_version)
            self.sensor = str(nc.sensor)
            self.correction = str(nc.image_correction)
            self.los_correction = bool(nc.los_correction)

            field_names = (
                "counts", "mu", "sigma", "w", "sza", "dza", "los_factor"
            )
            missing = [name for name in field_names if name not in nc.variables]
            if missing:
                raise ValueError(f"binned product is missing: {', '.join(missing)}")

            for name in field_names:
                setattr(self, name, np.asarray(nc.variables[name][:]))

            if "ssalon" not in nc.variables:
                raise ValueError("binned product is missing: ssalon")
            self.ssalon = np.asarray(nc.variables["ssalon"][:], dtype=float)
            self.time = load_time(nc)
            self.grid = load_grid(nc)

        self.shape = self.mu.shape
        if len(self.shape) != 3:
            raise ValueError("binned image fields must be three-dimensional")

        for name in field_names:
            if getattr(self, name).shape != self.shape:
                raise ValueError(f"{name} does not match the binned image dimensions")
        if self.time.shape != (self.shape[0],):
            raise ValueError("time does not match the binned image dimensions")
        if self.ssalon.shape != (self.shape[0],):
            raise ValueError("ssalon does not match the binned image dimensions")
        if self.grid.shape != self.shape[1:]:
            raise ValueError("grid does not match the binned image dimensions")

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
        text = f"<BinnedImage: {self.sensor}>"
        text += f"\nTimespan: {self.time[0]} to {self.time[-1]}"
        text += f"\nTemporal dim: {self.shape[0]}"
        text += f"\nSpatial dim: {self.shape[1]} x {self.shape[2]}"
        return text
