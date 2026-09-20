# IMAGE Conductance Reader

`icReader` is a lightweight Python package for reading NetCDF files containing ionospheric conductances generated with [`icBuilder`](https://github.com/BingMM/icBuilder).

Estimated ionospheric conductances with associated uncertainties are available [**here**](https://doi.org/10.5281/zenodo.15579301).

## Project Memory

For repository-specific operating guidance and technical continuity, start with
[`AGENTS.md`](AGENTS.md) and
[`vault/START HERE - AI Onboarding.md`](vault/START%20HERE%20-%20AI%20Onboarding.md).

## Dependencies

- [`numpy`](https://numpy.org/)
- [`netCDF4`](https://unidata.github.io/netcdf4-python/)
- [`scipy`](https://scipy.org/)
- [`secsy`](https://github.com/klaundal/secsy) – for cubed-sphere grid generation

## Installation

mamba activate your_environment  
git clone https://github.com/BingMM/icReader.git  
cd icReader  
pip install -e .

## Usage

Open detector-first and fixed-grid products through the descriptor-based
dispatcher. Their three-dimensional variables are read only when requested:

```python
import icreader

with icreader.load("or_0085.nc") as product:
    hall_frame = product.H[50]
    pedersen = product.read("P")
    magnetic_latitude = product.grid.lat  # CS products
```

`product.H` is a lazy, sliceable field. `product.read("H")` or
`numpy.asarray(product.H)` materializes the complete variable. Use the context
manager so the underlying NetCDF file is closed deterministically.

The older eager modular, direct-conductance, and spline readers remain
available. See [`scripts/test_load.py`](scripts/test_load.py) for a legacy
example.

## License

This project is licensed under the MIT License. See the [`LICENSE`](LICENSE) file for details.

## Contact

For questions or feedback, please contact: [michael.madelaire@uib.no](mailto:michael.madelaire@uib.no)
