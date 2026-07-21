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

Reads `data/Obs_log_full_3D.xlsx`, lets you filter observations by a bounding box and time interval, exports the selection as a shapefile (`data/selection.shp`, EPSG 28992 – RD New / Amersfoort), and shows a QC plot with an OpenStreetMap background.

```bash
pixi run obs_filter
```

The script will prompt for:

- **Bounding box** – X min/max and Y min/max in RD New coordinates (press Enter to use the full data extent)
- **Time interval** – start and end datetime (press Enter to use the full range)

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

- Configure these in `data/obs_filter.toml` under `[attributes]`.
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
