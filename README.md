# IMAGE Conductance Reader

`icReader` is a lightweight Python package for reading NetCDF files containing ionospheric conductances generated with [`icBuilder`](https://github.com/BingMM/icBuilder).

Estimated ionospheric conductances with associated uncertainties are available [**here**](https://doi.org/10.5281/zenodo.15579301).

## Project Memory

For repository-specific operating guidance and technical continuity, start with
[`AGENTS.md`](AGENTS.md) and
[`log/icReader/START HERE - AI Onboarding.md`](log/icReader/START%20HERE%20-%20AI%20Onboarding.md).

## Dependencies

- [`numpy`](https://numpy.org/)
- [`scipy`](https://scipy.org/)
- [`secsy`](https://github.com/klaundal/secsy) – for cubed-sphere grid generation

## Installation

mamba activate your_environment  
git clone https://github.com/BingMM/icReader.git  
cd icReader  
pip install -e .

## Usage

See [`scripts/test_load.py`](scripts/test_load.py) for an example of how to load and use the data.

## License

This project is licensed under the MIT License. See the [`LICENSE`](LICENSE) file for details.

## Contact

For questions or feedback, please contact: [michael.madelaire@uib.no](mailto:michael.madelaire@uib.no)
