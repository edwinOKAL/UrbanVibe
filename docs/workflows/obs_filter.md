# obs_filter workflow

Run the observation filter workflow from the project root:

```bash
pixi run obs_filter
```

The workflow reads:

- data/raw/Obs_log_full_3D.xlsx (preferred)
- data/Obs_log_full_3D.xlsx (legacy fallback)

Selection settings are read from:

- config/obs_filter.toml (preferred)
- data/obs_filter.toml (legacy fallback)

Output shapefile is written to:

- data/processed/<filename>.shp
