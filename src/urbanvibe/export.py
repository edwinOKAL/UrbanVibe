from __future__ import annotations

import pathlib
import warnings

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def to_geodataframe(frame: pd.DataFrame, *, x_column: str, y_column: str, epsg: int) -> gpd.GeoDataFrame:
    geom = [Point(xi, yi) for xi, yi in zip(frame[x_column], frame[y_column])]
    return gpd.GeoDataFrame(frame, geometry=geom, crs=f"EPSG:{epsg}")


def write_shapefile(gdf: gpd.GeoDataFrame, out_path: pathlib.Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gdf.to_file(out_path)
