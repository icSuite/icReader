#%% Import

import numpy as np
from secsy import CSgrid, CSprojection
from netCDF4 import Dataset
from datetime import datetime, timedelta
from scipy.interpolate import BSpline
from scipy.sparse import kron, csc_matrix
import apexpy
from apexpy.helpers import subsol
import warnings

#%% Conductance Image class

class SplineImage:
    """
    Container for loading and accessing spline (conductance) data from a NetCDF file.

    This class handles precomputed quantities such as Hall and Pedersen conductances, 
    and associated uncertainties.

    Attributes
    ----------
    time : np.ndarray, optional
        Array of datetimes corresponding to the image snapshots, if available.
    grid : CSgrid
        Cubbed sphere grid on which the data is projected.
    mH : np.ndarray
        Hall spline model coefficients.
    mP : np.ndarray
        Pedersen spline model coefficients.
    mdH : np.ndarray
        Hall uncertainty spline model coefficients.
    mdP : np.ndarray
        Pedersen uncertainty spline model coefficients.
    kt : int
        Temporal spline degree.
    k : int
        Spatial spline degree.
    nkt : int
        Amount of knots in temporal spline.
    nk : int
        Amount of knots in spatial spline.
        
    """
    def __init__(self, filename: str, spatial_extrapolation_fill=np.nan):
        """
        Load spline image data from a NetCDF file.

        Parameters
        ----------
        filename : str
            Path to the NetCDF file containing the conductance and grid data.
        """
        self.filename = filename
        self.sef = spatial_extrapolation_fill
        self.load_file(filename)
        self.init_splines()
        self.reset_space()
        self.reset_time()
        self.reset_eval()

    def __repr__(self):
        x = '<SplineImage object>'
        x += f'\nGenerated from file: {self.filename}'
        x += f'\nTimespan: {self.time_[0]} to {self.time_[-1]}'
        if self._t is None:
            x += '\nCurrent time: not set!'
        else:
            x += f'\nCurrent time: {self.time}'
        return x

#%% Load file

    def load_file(self, filename: str):
        with Dataset(filename, 'r') as nc:
            
            self.mH = nc.variables['mH'][:].copy()
            self.mP = nc.variables['mP'][:].copy()
            self.mdH = nc.variables['mdH'][:].copy()
            self.mdP = nc.variables['mdP'][:].copy()
            
            ref = datetime.strptime(nc.reference_time, "%Y-%m-%dT%H:%M:%S")
            self.time_ = np.array([self.get_time(s, ref) for s in nc.variables["time"][:]])
            self.ref = self.time_[0]
            
            self.t_ = np.array([self.get_t(t) for t in self.time_])
            
            self.grid = CSgrid(
                CSprojection(nc.position, nc.orientation),
                L=nc.L, W=nc.W, Lres=nc.Lres, Wres=nc.Wres, R=nc.gridR
                )

            self.k, self.nk = nc.k, nc.nk
            self.kt, self.nkt = nc.kt, nc.nkt

    def get_t(self, dt: datetime):
        if (dt < self.ref) or (dt > self.time_[-1]):
            raise ValueError('The requested date is outside the models temporal constraints.')
        
        return (dt - self.ref).total_seconds()
    
    def get_time(self, t: int, ref=None):
        if ref is None:
            return self.ref + timedelta(seconds=int(t))    
        else:
            return ref + timedelta(seconds=int(t))

#%% Splines

    def init_splines(self):
        self.splx = BSpline(self.knots, np.eye(self.ncp), self.k)
        self.splt = BSpline(self.tknots, np.eye(self.ncpt), self.kt)

    @property
    def x_(self):
        return self.grid.xi.flatten()
    
    @property
    def y_(self):
        return self.grid.eta.flatten()

    @property
    def ncp(self):
        return self.nk - self.k - 1
    
    @property
    def ncpt(self):
        return self.nkt - self.kt - 1

    @property
    def knots(self):
        return np.r_[[self.x_.min()]*self.k, np.linspace(self.x_.min(), self.x_.max(), self.nk-2*self.k), [self.x_.max()]*self.k]

    @property
    def tknots(self):
        return np.r_[[self.t_.min()]*self.kt, np.linspace(self.t_.min(), self.t_.max(), self.nkt-2*self.kt), [self.t_.max()]*self.kt]
    
    @property
    def sply(self):
        return self.splx

#%% evaluation space

    def reset_space(self):
        self._lon = None
        self._lat = None
        self._x = None
        self._y = None
        self._G = None
        self._Gt = None
        self._coord_sys = None
        self._mask = None

    def set_space(self, lon=None, lat=None, x=None, y=None, coord_sys = 'native'):
        self.reset_space()
        self.reset_eval()

        coord_sys = coord_sys.lower()
        if not coord_sys in ['geo', 'apex', 'native']:
            raise ValueError('coord_sys has to be geo or apex.')
        self._coord_sys = coord_sys
        
        if x is not None and y is not None:
            self._x, self._y = x, y
        
        self._lon = lon
        self._lat = lat
    
    def get_geo_grids(self):
        glats = []
        glons = []
        for dt in self.time_:
            self.set_time(dt)
            mlt = self.grid.lon/15%24
            mlon = self.apex.mlt2mlon(mlt, dt)
            mlat = self.grid.lat
            glat, glon, _ = self.apex.apex2geo(mlat, mlon, 110)
            glats.append(glat)
            glons.append(glon)
        return glats, glons

    def convert_space(self, lat, lon, h=110):
        # Convert from geo to apex
        if self._coord_sys == 'geo':
            lat, lon = self.apex.geo2apex(lat, lon, h)
        
        # Convert from apex (lat, lon) to apex (lat, mlt)
        lon = self.apex.mlon2mlt(lon, self.time) * 15
        
        return self.grid.projection.geo2cube(lon, lat)
    
    def _set_space(self):
        if self._lon is None or self._lat is None:
            self._x, self._y = self.grid.xi, self.grid.eta
        else:
            self._x, self._y = self.convert_space(self._lat, self._lon)
        
        self._mask = (self.grid.xi.min() <= self._x) & (self._x <= self.grid.xi.max()) & (self.grid.eta.min() <= self._y) & (self._y <= self.grid.eta.max())
        if not np.all(self._mask):
            warnings.warn("The grid used for prediction is outside of the spline model domain.", RuntimeWarning)
    
    @property
    def mask(self):
        if self._mask is None:
            self._set_space()
        return self._mask    
    
    @property
    def x(self):
        if self._x is None:
            self._set_space()
        return self._x

    @property
    def y(self):
        if self._y is None:
            self._set_space()
        return self._y

    @property
    def G(self):
        if self._G is None:
            self._G = self.generate_G_2d(return_sparse=True)
        return self._G

    def generate_G_2d(self, return_sparse=False):
        """
        Optimized generation of the Design Matrix (G).
        Speedup: ~100x-1000x compared to looping.
        """
        # 1. Get Basis matrices for ALL points at once
        # Scipy BSpline evaluates the whole array efficiently in C
        # Shape: (N_points, ncp)
        Bx = self.splx(self.x.flatten()) 
        By = self.sply(self.y.flatten())

        # 2. Compute Row-wise Kronecker product via Broadcasting
        # We want: G[i] = Bx[i] (outer_product) By[i]
        
        # Reshape to allow broadcasting: 
        # (N, ncp, 1) * (N, 1, ncp) -> (N, ncp, ncp)
        G_3d = Bx[:, :, np.newaxis] * By[:, np.newaxis, :]
        
        # 3. Flatten the last two dimensions to get the 2D design matrix
        # Shape: (N_points, ncp * ncp)
        G = G_3d.reshape(self.x.size, self.ncp**2)

        if return_sparse:
            return csc_matrix(G)
        return G

#%% Evaluation time

    def reset_time(self):
        self._t = None
        self._apex = None
        self._ssalon = None
        
        self._mH_s = None
        self._mP_s = None
        self._mdH_s = None
        self._mdP_s = None

    def set_time(self, t):
        self.reset_time()
        self.reset_eval()
        self._t = self.get_t(t)
        self.set_spatial_model_coefficients()
    
    def set_spatial_model_coefficients(self):
        Gt2G = kron(np.eye(self.ncp**2), self.splt(self.t), format='csr')
        self._mH_s  = Gt2G@self.mH
        self._mP_s  = Gt2G@self.mP
        self._mdH_s = Gt2G@self.mdH
        self._mdP_s = Gt2G@self.mdP
    
    @property
    def mH_s(self):
        if self._mH_s is None:
            self.set_spatial_model_coefficients()
        return self._mH_s
    
    @property
    def mP_s(self):
        if self._mP_s is None:
            self.set_spatial_model_coefficients()
        return self._mP_s
    
    @property
    def mdH_s(self):
        if self._mdH_s is None:
            self.set_spatial_model_coefficients()
        return self._mdH_s
    
    @property
    def mdP_s(self):
        if self._mdP_s is None:
            self.set_spatial_model_coefficients()
        return self._mdP_s
        
    @property
    def t(self):
        if self._t is None:
            raise ValueError("Set time first")
        return self._t

    @property
    def time(self):
        return self.get_time(self.t)
    
    @property
    def apex(self):
        if self._apex is None:
            self._apex = apexpy.Apex(self.get_time(self.t))
        return self._apex
    
    @property
    def ssalon(self):
        if self._ssalon is None:
            ssglat, ssglon = subsol(self.time)
            _, self._ssalon = self.apex.geo2apex(ssglat, ssglon, 318550)
        return self._ssalon

#%% Model evaluation

    def reset_eval(self):
        self._H = None
        self._P = None
        self._dH = None
        self._dP = None
    
    def _ev2D(self, m):
        #var = (self.Gt@m).reshape(self.x.shape)
        var = (self.G@m).reshape(self.x.shape)
        var[var < 0] = 0
        if self.sef is not None:
            var[~self.mask] = self.sef
        return var
    
    @property
    def H(self):
        if self._H is None:
            self._H = self._ev2D(self.mH_s)
        return self._H

    @property
    def P(self):
        if self._P is None:
            self._P = self._ev2D(self.mP_s)
        return self._P

    @property
    def dH(self):
        if self._dH is None:
            self._dH = self._ev2D(self.mdH_s)
        return self._dH

    @property
    def dP(self):
        if self._dP is None:
            self._dP = self._ev2D(self.mdP_s)
        return self._dP
    
#%% Function generator for Lompe

    def get_H_fun(self, coord_sys='geo'):
        """
        Returns a function(lon, lat) that calculates Hall conductance 
        using the existing class logic.
        """
        def interpolator(lon, lat):
            self.set_space(lon=lon, lat=lat, coord_sys=coord_sys)
            return self.H
        return interpolator
    
    def get_P_fun(self, coord_sys='geo'):
        """
        Returns a function(lon, lat) that calculates Pedersen conductance 
        using the existing class logic.
        """
        def interpolator(lon, lat):
            self.set_space(lon=lon, lat=lat, coord_sys=coord_sys)
            return self.P
        return interpolator
    
    def get_dH_fun(self, coord_sys='geo'):
        """
        Returns a function(lon, lat) that calculates Hall conductance uncertainty 
        using the existing class logic.
        """
        def interpolator(lon, lat):
            self.set_space(lon=lon, lat=lat, coord_sys=coord_sys)
            return self.dH
        return interpolator
    
    def get_dP_fun(self, coord_sys='geo'):
        """
        Returns a function(lon, lat) that calculates Pedersen conductance uncertainty
        using the existing class logic.
        """
        def interpolator(lon, lat):
            self.set_space(lon=lon, lat=lat, coord_sys=coord_sys)
            return self.dP
        return interpolator







