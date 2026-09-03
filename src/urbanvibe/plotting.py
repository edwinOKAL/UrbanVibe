from __future__ import annotations

import pathlib

import geopandas as gpd
import matplotlib.lines as mlines
import matplotlib.pyplot as plt

from .config import DATA_DIR


def load_kmls(plot_crs_epsg: int) -> list[tuple[gpd.GeoDataFrame, str]]:
    results = []
    for kml_path in sorted(DATA_DIR.glob("*.kml")):
        try:
            gdf = gpd.read_file(kml_path)
            gdf = gdf.to_crs(epsg=plot_crs_epsg)
            results.append((gdf, kml_path.stem))
        except Exception as exc:
            print(f"  [KML skipped - {kml_path.name}: {exc}]")
    return results


def plot_qc(*, gdf_all: gpd.GeoDataFrame, gdf_sel: gpd.GeoDataFrame, epsg: int) -> None:
    fig, ax = plt.subplots(figsize=(10, 10))

    gdf_all.plot(ax=ax, color="steelblue", markersize=4, alpha=0.3, zorder=1, label="All points")
    gdf_sel.plot(ax=ax, color="crimson", markersize=8, alpha=0.8, zorder=2, label="Selection")

    try:
        import contextily as ctx

        ctx.add_basemap(
            ax,
            source=ctx.providers.OpenStreetMap.Mapnik,
            zoom="auto",
            attribution=False,
            crs=f"EPSG:{epsg}",
        )
        print("  OSM basemap added (reprojected to RD New)")
    except Exception as exc:
        print(f"  [OSM basemap skipped: {exc}]")

    ax.set_xlabel(f"Easting  (EPSG:{epsg} / RD New)  [m]")
    ax.set_ylabel(f"Northing (EPSG:{epsg} / RD New)  [m]")
    ax.grid(True, linestyle=":", color="lightgrey", linewidth=0.7, alpha=0.5, zorder=0)

    kml_colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
    kml_handles = []
    for i, (kdf, name) in enumerate(load_kmls(epsg)):
        color = kml_colors[i % len(kml_colors)]
        kdf.plot(ax=ax, color=color, linewidth=3.5, alpha=0.95, zorder=5)
        kml_handles.append(
            mlines.Line2D([], [], color=color, linewidth=3.5, label=name, marker="", markersize=0)
        )
        print(f"  KML plotted: {name}")

    ax.set_aspect("equal")
    handles, _labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles + kml_handles, loc="best", fontsize=9, framealpha=0.95)

    crs_label = f"EPSG:{epsg} (RD New / Amersfoort)"
    ax.set_title(
        f"QC plot - {len(gdf_sel)} selected / {len(gdf_all)} total\\n"
        f"CRS: {crs_label}"
    )
    plt.tight_layout()
    plt.show()
