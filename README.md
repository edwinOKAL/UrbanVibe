# UrbanVibe

Using Urban Fiber Optic Cables to measure ground stability for Resilient Infrastructure

## Getting started

This project uses [pixi](https://pixi.sh) for environment management.

```bash
# Install the environment (first time only)
pixi install
```

## Tools

### obs_filter — Observation filter & shapefile export

Reads observations, filters by bounding box/time/attributes from TOML settings, exports a shapefile (EPSG 28992 - RD New / Amersfoort), and shows a QC plot with optional OpenStreetMap background and KML overlays.

Input/config/output paths:

- Input workbook (preferred): `data/raw/Obs_log_full_3D.xlsx`
- Input workbook (legacy fallback): `data/Obs_log_full_3D.xlsx`
- Config (preferred): `config/obs_filter.toml`
- Config (legacy fallback): `data/obs_filter.toml`
- Output shapefile: `data/processed/<filename>.shp`

```bash
pixi run obs_filter
```

### h5_reader - FEBUS HDF5 DAS reader

Read a file with automatic full-window inference (distance and time):

```bash
python -m urbanvibe.h5_reader data/raw/your_file.h5
```

Read a specific window explicitly:

```bash
python -m urbanvibe.h5_reader data/raw/your_file.h5 0 1000 2025-11-25T00:03:22 2025-11-25T00:04:22
```

Quick help via Pixi task:

```bash
pixi run h5_reader
```

Run tests:

```bash
pixi run test
```

## Demos

- Notebook demos live in `notebooks/`.
- Start with `notebooks/01_obs_filter_demo.ipynb`.
- Keep notebooks focused on usage walkthroughs and visual checks.

## Repository structure

```text
src/urbanvibe/
	cli.py          # workflow entrypoint
	h5_reader.py    # HDF5 reader utilities and CLI
	io.py           # workbook loading and column detection
	filters.py      # selection logic
	export.py       # GeoDataFrame and shapefile export
	plotting.py     # QC plotting and KML overlays
	config.py       # TOML config loading/defaults

scripts/
	obs_filter.py   # thin wrapper entrypoint
	read_h5.py      # thin wrapper for HDF5 reader

config/
	obs_filter.toml # primary workflow config

data/
	raw/            # source input files
	interim/        # intermediate artifacts
	processed/      # outputs (e.g. shapefiles)

notebooks/
	01_obs_filter_demo.ipynb

tests/
	test_filters.py
	test_h5_reader.py
```

Descriptor legend:

- **SP** = normal shallow shot point
- **SPS** = shot point with services/utility clearance
- **DSP** = deep shot point
- **DSP-SPS** = deep shot point with utility clearance
- **SP_HU** = shot point near critical utilities
- **SPS_HU** = utility-cleared shot point requiring insulated/high-resistance wiring
- **VP** = vibroseis point
- **WSP** = water shot point
- **Airgun** = airgun source

Shot depth and shot load selectors:

- Configure these in `config/obs_filter.toml` under `[attributes]`.
- Supported input is intentionally simple: one exact value or one comparison.

```toml
[attributes]
# exact value
loaded_depth = 12.5
loaded_charge = 35

# or single comparison string
loaded_depth = ">=10"
loaded_charge = "<=35"
```

Supported comparison operators: `>`, `>=`, `<`, `<=`, `=`
