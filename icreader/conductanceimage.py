#%% Import

import numpy as np
from secsy import CSgrid, CSprojection
from netCDF4 import Dataset
from datetime import datetime, timedelta

#%% Conductance Image class

class ConductanceImage:
    """
    Container for loading and accessing conductance data from a NetCDF file.

    This class handles precomputed quantities such as Hall and Pedersen conductances, 
    and associated uncertainties.

    Attributes
    ----------
    E0 : np.ndarray
        Characteristic energy [keV] for each pixel.
    dE0 : np.ndarray
        Uncertainty in E0.
    Fe : np.ndarray
        Electron energy flux [erg/cm^2/s].
    dFe : np.ndarray
        Uncertainty in Fe.
    R : np.ndarray
        WIC and SI13 ratio.
    dR : np.ndarray
        Uncertainty in R.
    P : np.ndarray
        Pedersen conductance [mho].
    H : np.ndarray
        Hall conductance [mho].
    dP : np.ndarray
        Uncertainty in P.
    dH : np.ndarray
        Uncertainty in H.
    dP2 : np.ndarray
        Secondary uncertainty or alternate error metric for P.
    dH2 : np.ndarray
        Secondary uncertainty or alternate error metric for H.
    Ep : float
        Proton characteristic energy [keV]
    dEp : float
        Uncertainty in Ep.
    shape : tuple
        Shape of the conductance arrays (typically [y, x]).
    time : np.ndarray
        Array of datetimes corresponding to the image snapshots, if available.
    grid : CSgrid
        Cubbed sphere grid on which the data is projected.
        Longitude in object is 15*mlt, us ssalon to convert to mlon
    ssalon : np.ndarray
        Apex magnetic longitude of sub-solar point
    """
    def __init__(self, filename: str):
        """
        Load conductance image data from a NetCDF file.

        Parameters
        ----------
        filename : str
            Path to the NetCDF file containing the conductance and grid data.
        """
        with Dataset(filename, "r") as nc:
    
            def load_var(name):
                return np.array(nc.variables[name][:])
    
            # Load main data variables
            for attr in [
                "wic_avg", "wic_std", "s12_avg", "s12_std", "s13_avg",
                "s13_std", "E0", "dE0", "Fe", "dFe", "R", "dR",
                "P", "H", "dP", "dH", "w", "ssalon"
            ]:
                setattr(self, attr, load_var(attr))
    
            # Scalars
            self.Ep = float(nc.Ep)
            self.dEp = float(nc.dEp)
    
            # Shape
            self.shape = self.E0.shape
    
            # Time variable
            if "time" in nc.variables:
                ref = datetime.strptime(nc.reference_time, "%Y-%m-%dT%H:%M:%S")
                self.time = np.array(
                    [ref + timedelta(seconds=int(s)) for s in nc.variables["time"][:]]
                )

            if hasattr(nc, 'varE0Fe'):
                self.varE0Fe = nc.varE0Fe
    
                self.energy_method = nc.electron_energy_method
                if self.energy_method == "zhang_paxton":
                    # Load Kp arrays safely mapping uppercase NC vars to lowercase object attributes
                    for attr in ["Kp", "Kp_lookup", "Kp_interval_start"]:
                        if attr in nc.variables:
                            setattr(self, attr, load_var(attr))
        
                # Load sensor viewing geometry and correction attributes
                for sensor in ["wic", "s12", "s13"]:
                    for suffix in ["sza", "dza", "los_factor"]:
                        var_name = f"{sensor}_{suffix}"
                        if var_name in nc.variables:
                            setattr(self, var_name, load_var(var_name))
                    
                    for suffix in ["los_correction", "image_correction"]:
                        attr_name = f"{sensor}_{suffix}"
                        if hasattr(nc, attr_name):
                            setattr(self, attr_name, getattr(nc, attr_name))
    
            # GRID GROUP
            grid_grp = nc.groups["grid"]

            self.grid = CSgrid(
                CSprojection(
                    np.array(grid_grp.position),
                    np.array(grid_grp.orientation),
                ),
                L=float(grid_grp.L),
                W=float(grid_grp.W),
                Lres=float(grid_grp.Lres),
                Wres=float(grid_grp.Wres),
                R=float(grid_grp.R),
            )

    @property
    def nt(self):
        return self.time.size

    def __repr__(self):
        x = '<ConductanceImage object>'
        x += f'\nTimespan: {self.time[0]} to {self.time[-1]}'
        x += f'\nTemporal dim: {self.shape[0]}'
        x += f'\nSpatial dim: {self.shape[1]} x {self.shape[2]}'                
        return x

    @property
    def mlat(self):
        return self.grid.lat

    @property
    def mlt(self):
        return self.grid.lon / 15 % 24

    @property
    def mlon(self):
        return (self.mlt[None, :, :] * 15 - 180 + self.ssalon[:, None, None]) % 360

    def discard(self, f=None, interval=None):
        """
        Discard (mask out) selected time indices from all time-dependent fields.
    
        This method shrinks all per-time or per-image array attributes in the class
        according to a boolean or integer mask `f`, or according to an index
        interval. All attributes that vary along the time dimension are filtered
        consistently. Scalar attributes and fixed metadata are left untouched.
    
        Parameters
        ----------
        f : array_like of bool or int, optional
            Boolean mask or integer index array selecting the time/image entries
            to keep. Must match the length of the time dimension.
        interval : tuple(int, int), optional
            Inclusive index interval `(i0, i1)` specifying which time indices
            to keep. Only one of `f` or `interval` may be provided.
    
        Notes
        -----
        The following attributes are **not** modified by this method:
        `Ep`, `dEp`, `shape`, and `grid`.
    
        All other attributes that are NumPy arrays whose first dimension matches
        the length of `self.time` are filtered using the mask.
        """
        if f is None and interval is None:
            raise ValueError("f and interval cannot both be None.")
        if f is not None and interval is not None:
            raise ValueError("f and interval cannot both be provided.")
    
        # Convert interval → mask
        if interval is not None:
            idx = np.arange(self.nt)
            f = (interval[0] <= idx) & (idx <= interval[1])
    
        # These must NOT be modified
        exclude = {"Ep", "dEp", "shape", "grid"}
    
        # Apply mask to matching arrays
        for name, value in self.__dict__.items():
            if name in exclude:
                continue
            self.__dict__[name] = value[f]

