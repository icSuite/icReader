"""Shared on-demand access to self-describing icBuilder products."""

#%% Imports

from types import MappingProxyType

import numpy as np
from netCDF4 import Dataset, num2date


#%% NetCDF value conversion

def read_values(variable, index=None, kind="float"):
    """Read one variable selection with a stable missing-value convention."""

    values = variable[:] if index is None else variable[index]
    if np.ma.isMaskedArray(values):
        if kind == "bool":
            fill_value = False
        elif kind == "int":
            fill_value = getattr(variable, "_FillValue", -1)
        else:
            fill_value = np.nan
        values = values.filled(fill_value)

    if kind == "bool":
        dtype = bool
    elif kind == "float":
        dtype = (
            variable.dtype
            if np.issubdtype(variable.dtype, np.floating) else float
        )
    else:
        dtype = variable.dtype
    return np.asarray(values, dtype=dtype)


def decode_time(variable):
    """Decode one CF time variable while preserving missing source times."""

    if not hasattr(variable, "units"):
        raise ValueError(f"{variable.name} has no time units")

    encoded = variable[:]
    missing = np.ma.getmaskarray(encoded)
    numeric = np.asarray(encoded.filled(np.nan) if np.ma.isMaskedArray(encoded) else encoded)
    missing |= ~np.isfinite(numeric)

    decoded = np.full(numeric.shape, None, dtype=object)
    if np.any(~missing):
        decoded[~missing] = num2date(
            numeric[~missing],
            variable.units,
            getattr(variable, "calendar", "standard"),
            only_use_cftime_datetimes=False,
        )
    return decoded


#%% Lazy field proxy

class ProductField:
    """Read-only, sliceable access to one NetCDF variable."""

    def __init__(self, product, name, kind):
        self._product = product
        self.name = name
        self.kind = kind

    @property
    def _variable(self):
        return self._product._get_variable(self.name)

    @property
    def shape(self):
        return self._variable.shape

    @property
    def ndim(self):
        return self._variable.ndim

    @property
    def size(self):
        return self._variable.size

    @property
    def dtype(self):
        if self.kind == "bool":
            return np.dtype(bool)
        if self.kind == "float":
            return np.dtype(self._variable.dtype)
        return np.dtype(self._variable.dtype)

    @property
    def dimensions(self):
        return self._variable.dimensions

    @property
    def units(self):
        return self.attrs.get("units")

    @property
    def attrs(self):
        return self._product.variable_attrs[self.name]

    def __len__(self):
        return self.shape[0]

    def __getitem__(self, index):
        return self._product.read(self.name, index)

    def __array__(self, dtype=None, copy=None):
        values = self._product.read(self.name)
        if dtype is not None:
            values = values.astype(dtype, copy=False)
        if copy:
            values = values.copy()
        return values

    def __repr__(self):
        return (
            f"<ProductField {self.name!r}: shape={self.shape}, "
            f"dtype={self.dtype}>"
        )


#%% Product base class

class NetCDFProduct:
    """Validated, context-managed view of one detector-first product."""

    PRODUCT_TYPE = None
    REPRESENTATION = None
    SCHEMA_VERSION = None
    DIMENSIONS = ()
    REQUIRED_ATTRIBUTES = ()
    VARIABLES = {}

    def __init__(self, filename):
        self.filename = str(filename)
        self._nc = Dataset(filename)
        self._closed = False

        try:
            self._validate_descriptor()
            self._validate_dimensions()
            self._validate_attributes()
            self._validate_variables()
            self._load_identity()
            self._load_fields()
            self._finish_initialization()
        except Exception:
            self.close()
            raise

    def _validate_descriptor(self):
        nc = self._nc
        if "product_type" not in nc.ncattrs():
            raise ValueError("NetCDF file has no product_type descriptor")
        if nc.product_type != self.PRODUCT_TYPE:
            raise ValueError(
                f"expected product_type '{self.PRODUCT_TYPE}', "
                f"got '{nc.product_type}'"
            )
        if "representation" not in nc.ncattrs():
            raise ValueError(f"{self.PRODUCT_TYPE} has no representation descriptor")
        if nc.representation != self.REPRESENTATION:
            raise ValueError(
                f"expected {self.PRODUCT_TYPE} representation "
                f"'{self.REPRESENTATION}', got '{nc.representation}'"
            )
        if "schema_version" not in nc.ncattrs():
            raise ValueError(f"{self.PRODUCT_TYPE} has no schema_version descriptor")
        if int(nc.schema_version) != self.SCHEMA_VERSION:
            raise ValueError(
                f"unsupported {self.PRODUCT_TYPE} schema_version "
                f"{nc.schema_version}; expected {self.SCHEMA_VERSION}"
            )

    def _validate_dimensions(self):
        missing = [name for name in self.DIMENSIONS if name not in self._nc.dimensions]
        if missing:
            raise ValueError(
                f"{self.PRODUCT_TYPE} is missing dimensions: {', '.join(missing)}"
            )
        sizes = tuple(len(self._nc.dimensions[name]) for name in self.DIMENSIONS)
        if any(size == 0 for size in sizes):
            raise ValueError(f"{self.PRODUCT_TYPE} dimensions must be non-empty")
        self.shape = sizes

    def _validate_attributes(self):
        missing = [
            name for name in self.REQUIRED_ATTRIBUTES
            if name not in self._nc.ncattrs()
        ]
        if missing:
            raise ValueError(
                f"{self.PRODUCT_TYPE} is missing attributes: {', '.join(missing)}"
            )

    def _validate_variables(self):
        missing = [name for name in self.VARIABLES if name not in self._nc.variables]
        if missing:
            raise ValueError(
                f"{self.PRODUCT_TYPE} is missing variables: {', '.join(missing)}"
            )

        for name, (dimensions, _kind, _eager) in self.VARIABLES.items():
            variable = self._nc.variables[name]
            if variable.dimensions != dimensions:
                raise ValueError(
                    f"{name} dimensions are {variable.dimensions}; "
                    f"expected {dimensions}"
                )

    def _load_identity(self):
        nc = self._nc
        self.product_type = str(nc.product_type)
        self.representation = str(nc.representation)
        self.schema_version = int(nc.schema_version)
        self.attrs = MappingProxyType(
            {name: nc.getncattr(name) for name in nc.ncattrs()}
        )
        self.software_version = self.attrs.get("software_version")

    def _load_fields(self):
        self.fields = {}
        self.time_encoding = {}
        self.variable_attrs = {}
        for name, (_dimensions, kind, eager) in self.VARIABLES.items():
            variable = self._nc.variables[name]
            self.variable_attrs[name] = MappingProxyType({
                attribute: variable.getncattr(attribute)
                for attribute in variable.ncattrs()
            })
            if eager:
                if kind == "time":
                    values = decode_time(variable)
                    self.time_encoding[name] = MappingProxyType({
                        "units": variable.units,
                        "calendar": getattr(variable, "calendar", "standard"),
                    })
                else:
                    values = read_values(variable, kind=kind)
                setattr(self, name, values)
            else:
                field = ProductField(self, name, kind)
                self.fields[name] = field
                setattr(self, name, field)
        self.fields = MappingProxyType(self.fields)
        self.time_encoding = MappingProxyType(self.time_encoding)
        self.variable_attrs = MappingProxyType(self.variable_attrs)

    def _finish_initialization(self):
        """Hook for product-specific metadata or grid loading."""

    def _get_variable(self, name):
        if self._closed:
            raise RuntimeError(f"{self.product_type} product is closed")
        if name not in self._nc.variables:
            raise KeyError(f"{self.product_type} has no variable {name!r}")
        return self._nc.variables[name]

    def read(self, name, index=None):
        """Materialize one complete field or selection as a NumPy array."""

        variable = self._get_variable(name)
        kind = self.VARIABLES.get(name, (None, "float", None))[1]
        if kind == "time":
            if index is None:
                return decode_time(variable)
            return decode_time_selection(variable, index)
        return read_values(variable, index=index, kind=kind)

    def attributes_with_prefix(self, prefix):
        """Return root attributes after removing one common prefix."""

        return MappingProxyType({
            name[len(prefix):]: value
            for name, value in self.attrs.items()
            if name.startswith(prefix)
        })

    @property
    def nt(self):
        return self.shape[0]

    @property
    def closed(self):
        return self._closed

    def close(self):
        if not self._closed:
            self._nc.close()
            self._closed = True

    def __enter__(self):
        if self._closed:
            raise RuntimeError(f"{self.product_type} product is closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self):
        return (
            f"<{type(self).__name__}: shape={self.shape}, "
            f"schema={self.schema_version}>"
        )


def decode_time_selection(variable, index):
    """Decode a selected time slice without reading the complete variable."""

    encoded = variable[index]
    scalar = np.ndim(encoded) == 0
    if scalar and np.ma.is_masked(encoded):
        return None
    encoded_array = np.asarray([encoded], dtype=float) if scalar else encoded
    if np.ma.isMaskedArray(encoded_array):
        missing = np.ma.getmaskarray(encoded_array)
        numeric = np.asarray(encoded_array.filled(np.nan))
    else:
        numeric = np.asarray(encoded_array)
        missing = ~np.isfinite(numeric)

    decoded = np.full(numeric.shape, None, dtype=object)
    if np.any(~missing):
        decoded[~missing] = num2date(
            numeric[~missing],
            variable.units,
            getattr(variable, "calendar", "standard"),
            only_use_cftime_datetimes=False,
        )
    return decoded[0] if scalar else decoded
