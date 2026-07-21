"""
obs_filter.py
=============
Read observations from Obs_log_full_3D.xlsx, filter by bounding box and
time interval, export the selection as a shapefile, and show a QC plot
(with optional OpenStreetMap background and KML cable overlays).

Selection parameters are read from  data/obs_filter.toml.
On first run the file is created with full-extent defaults — edit it and
re-run to apply your filter.

CRS: EPSG 28992 – RD New / Amersfoort
"""

import sys
import re
import tomllib
import pathlib
import textwrap
import warnings

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = pathlib.Path(__file__).parent
EXCEL_PATH  = SCRIPT_DIR / "Obs_log_full_3D.xlsx"
CONFIG_PATH = SCRIPT_DIR / "obs_filter.toml"
OUTPUT_DIR  = SCRIPT_DIR
EPSG        = 28992   # RD New / Amersfoort  (user suggested 28892 – corrected)


# ── Column auto-detection ─────────────────────────────────────────────────────
def detect_columns(df: pd.DataFrame):
    """Return (x_col, y_col, dt_col) by inspecting names and dtypes."""
    x_col = y_col = dt_col = None

    for col in df.columns:
        stripped = col.strip().upper()
        low      = col.strip().lower()

        if stripped == "X" and x_col is None:
            x_col = col
        elif stripped == "Y" and y_col is None:
            y_col = col

        is_dt = pd.api.types.is_datetime64_any_dtype(df[col])
        if is_dt and dt_col is None:
            # Prefer a column whose name contains "shoot" or "datetime"
            if any(k in low for k in ("shoot", "datetime", "date_time")):
                dt_col = col

    # Fallback: first datetime column found
    if dt_col is None:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                dt_col = col
                break

    return x_col, y_col, dt_col


def normalize_column_name(name: str) -> str:
    """Normalize a column name for loose matching."""
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def find_optional_column(df: pd.DataFrame, aliases: set[str]):
    """Return the first matching column for the normalized alias set."""
    normalized = {normalize_column_name(col): col for col in df.columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def normalize_selector(value):
    """Normalize selector input from TOML into a flat list or None."""
    if value is None or value == "":
        return None
    if isinstance(value, list):
        cleaned = [v for v in value if v is not None and v != ""]
        return cleaned or None
    return [value]


def normalize_optional_value(value):
    """Normalize optional TOML values: empty string means disabled."""
    if value is None or value == "":
        return None
    return value


def normalize_output_filename(value) -> str:
    """Validate and normalize output shapefile name from TOML."""
    default_name = "selection.shp"
    if value is None or value == "":
        return default_name

    if not isinstance(value, str):
        raise ValueError("output.filename must be a string")

    name = value.strip()
    if not name:
        return default_name

    # Keep outputs in OUTPUT_DIR; only allow file names, not paths.
    if pathlib.Path(name).name != name:
        raise ValueError("output.filename must be a file name, not a path")

    if not name.lower().endswith(".shp"):
        name = f"{name}.shp"

    return name


def build_selector_mask(series: pd.Series, selector) -> pd.Series:
    """Build a boolean mask for exact-match selection (scalar or list)."""
    if selector is None:
        return pd.Series(True, index=series.index)

    raw_values = selector if isinstance(selector, list) else [selector]
    values = [v for v in raw_values if v is not None and v != ""]
    if not values:
        return pd.Series(True, index=series.index)

    # Use numeric matching when all selectors are numeric.
    num_values = pd.to_numeric(pd.Series(values), errors="coerce")
    if num_values.notna().all():
        series_num = pd.to_numeric(series, errors="coerce")
        return series_num.isin(num_values.tolist())

    # Fallback to case-insensitive text matching.
    targets = {str(v).strip().lower() for v in values}
    series_txt = series.astype(str).str.strip().str.lower()
    return series_txt.isin(targets)


def _is_plain_numeric_like(value) -> bool:
    """Return True when value represents a plain numeric value (no operators)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    return re.fullmatch(r"[-+]?\d+(?:\.\d+)?", s) is not None


def build_numeric_selector_mask(series: pd.Series, selector, field_name: str) -> pd.Series:
    """Build numeric selection masks with exact or single inequality support."""
    series_num = pd.to_numeric(series, errors="coerce")

    def from_scalar(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return series_num == float(value)

        if isinstance(value, str):
            s = value.strip()
            if not s:
                return pd.Series(True, index=series.index)

            # Comparison syntax: ">10", ">= 10", "< 5", "<=20", "=12.5"
            m = re.fullmatch(r"(<=|>=|<|>|=)\s*([-+]?\d+(?:\.\d+)?)", s)
            if m:
                op = m.group(1)
                val = float(m.group(2))
                if op == "<":
                    return series_num < val
                if op == "<=":
                    return series_num <= val
                if op == ">":
                    return series_num > val
                if op == ">=":
                    return series_num >= val
                return series_num == val

            # Plain numeric string equals exact match.
            if _is_plain_numeric_like(s):
                return series_num == float(s)

            raise ValueError(
                f"invalid selector '{value}' for {field_name}; "
                "use a number or a single comparison like '>=10'"
            )

        raise ValueError(
            f"unsupported selector type '{type(value).__name__}' for {field_name}"
        )

    if selector is None:
        return pd.Series(True, index=series.index)

    if isinstance(selector, (list, dict)):
        raise ValueError(
            f"{field_name} does not support lists, ranges, or inline tables; "
            "use a single value like 12.5 or a single comparison like '>=10'"
        )

    return from_scalar(selector)


# ── Config file ───────────────────────────────────────────────────────────────
def write_default_config(x_min, x_max, y_min, y_max, t_min, t_max):
    """Write a template config with data-extent defaults."""
    t_min_str = str(t_min)[:19] if t_min is not None else ""
    t_max_str = str(t_max)[:19] if t_max is not None else ""
    content = textwrap.dedent(f"""\
        # obs_filter.toml
        # Edit the values below, then re-run:  pixi run obs_filter
        # Set a value to "" (empty string) to use the full data extent.

        [output]
        # Output shapefile name (written to data/). Change to avoid overwrite.
        filename = "selection.shp"

        [bbox]
        # Coordinates in EPSG 28992 (RD New / Amersfoort) – metres
        x_min = {x_min:.2f}
        x_max = {x_max:.2f}
        y_min = {y_min:.2f}
        y_max = {y_max:.2f}

        [time]
        # ISO-8601 format: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
        start = "{t_min_str}"
        end   = "{t_max_str}"

        [attributes]
        # Optional attribute filters. Use "" to disable a filter.
        # Descriptor can be a single value or a list.
        # Available Descriptor values in Obs_log_full_3D.xlsx:
        # Airgun, DSP, DSP-SPS, SP, SPS, SPS_HU, SP_HU, VP, WSP
        # descriptor = "VP"
        # descriptor = ["VP", "SPS", "DSP"]
        descriptor = ""

        # loaded_depth supports:
        # - exact value: 12.5
        # - single comparison: ">10", ">=10", "<20", "<=20"
        # loaded_depth = 12.5
        # loaded_depth = ">=10"
        loaded_depth = ""

        # loaded_charge supports the same selector syntax as loaded_depth.
        # loaded_charge = 35
        # loaded_charge = "<=35"
        loaded_charge = ""
    """)
    CONFIG_PATH.write_text(content, encoding="utf-8")


def load_config(x_min_d, x_max_d, y_min_d, y_max_d, dt_min_d, dt_max_d):
    """Load config and return bbox/time/attribute selectors."""
    with open(CONFIG_PATH, "rb") as fh:
        cfg = tomllib.load(fh)

    output = cfg.get("output", {})
    bbox = cfg.get("bbox", {})
    time = cfg.get("time", {})
    attrs = cfg.get("attributes", {})

    out_name = normalize_output_filename(output.get("filename", "selection.shp"))

    sel_xmin = float(bbox.get("x_min", x_min_d))
    sel_xmax = float(bbox.get("x_max", x_max_d))
    sel_ymin = float(bbox.get("y_min", y_min_d))
    sel_ymax = float(bbox.get("y_max", y_max_d))

    t_start = pd.Timestamp(time["start"]) if time.get("start") else dt_min_d
    t_end   = pd.Timestamp(time["end"])   if time.get("end")   else dt_max_d

    descriptor_sel = normalize_selector(attrs.get("descriptor", ""))
    loaded_depth_sel = normalize_optional_value(attrs.get("loaded_depth", ""))
    loaded_charge_sel = normalize_optional_value(attrs.get("loaded_charge", ""))

    return (
        out_name,
        sel_xmin, sel_xmax, sel_ymin, sel_ymax,
        t_start, t_end,
        descriptor_sel, loaded_depth_sel, loaded_charge_sel,
    )


# ── KML helpers ───────────────────────────────────────────────────────────────
def load_kmls(plot_crs_epsg: int) -> list[tuple[gpd.GeoDataFrame, str]]:
    """Load all KML files from SCRIPT_DIR, reproject, return [(gdf, stem), …]."""
    results = []
    for kml_path in sorted(SCRIPT_DIR.glob("*.kml")):
        try:
            gdf = gpd.read_file(kml_path)
            gdf = gdf.to_crs(epsg=plot_crs_epsg)
            results.append((gdf, kml_path.stem))
        except Exception as e:
            print(f"  [KML skipped – {kml_path.name}: {e}]")
    return results


# ── Core ──────────────────────────────────────────────────────────────────────
def main():
    # 1. Load Excel ────────────────────────────────────────────────────────────
    print(f"\nReading  {EXCEL_PATH} …")
    df = pd.read_excel(EXCEL_PATH)

    x_col, y_col, dt_col = detect_columns(df)
    if x_col is None or y_col is None:
        sys.exit("ERROR: could not detect X/Y coordinate columns.")

    print(f"  X column       : '{x_col}'")
    print(f"  Y column       : '{y_col}'")
    print(f"  Datetime column: '{dt_col}'")
    print(f"  Total records  : {len(df)}")

    descriptor_col = find_optional_column(df, {
        "descriptor", "descr", "description", "type", "obstype", "observationtype",
    })
    loaded_depth_col = find_optional_column(df, {
        "loadeddepth", "loaddepth", "loadeddep", "depthloaded",
    })
    loaded_charge_col = find_optional_column(df, {
        "loadedcharge", "loadcharge", "chargeloaded",
    })

    df = df.dropna(subset=[x_col, y_col]).reset_index(drop=True)

    x_min_d, x_max_d = df[x_col].min(), df[x_col].max()
    y_min_d, y_max_d = df[y_col].min(), df[y_col].max()
    dt_min_d = df[dt_col].min() if dt_col else None
    dt_max_d = df[dt_col].max() if dt_col else None

    print("\n── Data extent ───────────────────────────────────────────────────────")
    print(f"  X : {x_min_d:>14.2f}  →  {x_max_d:.2f}")
    print(f"  Y : {y_min_d:>14.2f}  →  {y_max_d:.2f}")
    if dt_min_d:
        print(f"  T : {dt_min_d}  →  {dt_max_d}")

    # 2. Config file ───────────────────────────────────────────────────────────
    if not CONFIG_PATH.exists():
        write_default_config(x_min_d, x_max_d, y_min_d, y_max_d, dt_min_d, dt_max_d)
        print(f"\n  Config created → {CONFIG_PATH}")
        print("  Edit it to set your bbox / time filter, then re-run.")
        print("  (Running now with full-extent defaults.)\n")

    (
        out_name,
        sel_xmin, sel_xmax, sel_ymin, sel_ymax,
        t_start, t_end,
        descriptor_sel, loaded_depth_sel, loaded_charge_sel,
    ) = load_config(x_min_d, x_max_d, y_min_d, y_max_d, dt_min_d, dt_max_d)

    print(f"\n── Active selection (from {CONFIG_PATH.name}) ────────────────────────")
    print(f"  X : {sel_xmin:.2f}  →  {sel_xmax:.2f}")
    print(f"  Y : {sel_ymin:.2f}  →  {sel_ymax:.2f}")
    if dt_col:
        print(f"  T : {t_start}  →  {t_end}")
    print(f"  Output file: {out_name}")
    print(f"  Descriptor : {descriptor_sel if descriptor_sel is not None else 'ALL'}")
    print(f"  loaded_depth : {loaded_depth_sel if loaded_depth_sel is not None else 'ALL'}")
    print(f"  loaded_charge: {loaded_charge_sel if loaded_charge_sel is not None else 'ALL'}")

    # 3. Apply filter ──────────────────────────────────────────────────────────
    mask = (
        (df[x_col] >= sel_xmin) & (df[x_col] <= sel_xmax) &
        (df[y_col] >= sel_ymin) & (df[y_col] <= sel_ymax)
    )
    if dt_col:
        mask &= (df[dt_col] >= t_start) & (df[dt_col] <= t_end)

    if descriptor_sel is not None:
        if descriptor_col is None:
            sys.exit("ERROR: filter 'descriptor' is set, but no Descriptor column was detected.")
        mask &= build_selector_mask(df[descriptor_col], descriptor_sel)

    if loaded_depth_sel is not None:
        if loaded_depth_col is None:
            sys.exit("ERROR: filter 'loaded_depth' is set, but no loaded depth column was detected.")
        try:
            mask &= build_numeric_selector_mask(df[loaded_depth_col], loaded_depth_sel, "loaded_depth")
        except ValueError as e:
            sys.exit(f"ERROR: {e}")

    if loaded_charge_sel is not None:
        if loaded_charge_col is None:
            sys.exit("ERROR: filter 'loaded_charge' is set, but no loaded charge column was detected.")
        try:
            mask &= build_numeric_selector_mask(df[loaded_charge_col], loaded_charge_sel, "loaded_charge")
        except ValueError as e:
            sys.exit(f"ERROR: {e}")

    df_sel = df[mask].copy()
    print(f"\n  → {len(df_sel)} records selected out of {len(df)}.")

    if df_sel.empty:
        print("No records matched the selection. Exiting.")
        sys.exit(0)

    # 4. Build GeoDataFrames ───────────────────────────────────────────────────
    def to_gdf(frame: pd.DataFrame) -> gpd.GeoDataFrame:
        geom = [Point(xi, yi) for xi, yi in zip(frame[x_col], frame[y_col])]
        return gpd.GeoDataFrame(frame, geometry=geom, crs=f"EPSG:{EPSG}")

    gdf_all = to_gdf(df)
    gdf_sel = to_gdf(df_sel)

    # 5. Export shapefile ──────────────────────────────────────────────────────
    out_shp = OUTPUT_DIR / out_name
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # suppress 10-char column name truncation noise
        gdf_sel.to_file(out_shp)
    print(f"  Shapefile written → {out_shp}")

    # 6. QC plot ───────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 10))
    osm_ok = False

    # Plot in native RD New (EPSG 28992)
    gdf_all.plot(ax=ax, color="steelblue", markersize=4, alpha=0.3,
                 zorder=1, label="All points")
    gdf_sel.plot(ax=ax, color="crimson", markersize=8, alpha=0.8,
                 zorder=2, label="Selection")

    try:
        import contextily as ctx

        # Add OSM basemap, reprojecting to RD New
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom="auto",
                        attribution=False, crs=f"EPSG:{EPSG}")
        osm_ok = True
        print("  OSM basemap added (reprojected to RD New)")

    except Exception as e:
        print(f"  [OSM basemap skipped: {e}]")

    ax.set_xlabel(f"Easting  (EPSG:{EPSG} / RD New)  [m]")
    ax.set_ylabel(f"Northing (EPSG:{EPSG} / RD New)  [m]")

    # Add light grey dotted grid
    ax.grid(True, linestyle=":", color="lightgrey", linewidth=0.7, alpha=0.5, zorder=0)

    # 7. KML overlays – emphasized with thick lines & distinct colors ─────────────
    kml_colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
    kml_handles = []
    for i, (kdf, name) in enumerate(load_kmls(EPSG)):
        color = kml_colors[i % len(kml_colors)]
        # Draw with thick lines, high opacity, and high zorder for emphasis
        kdf.plot(ax=ax, color=color, linewidth=3.5, alpha=0.95, zorder=5)
        kml_handles.append(
            mlines.Line2D([], [], color=color, linewidth=3.5, label=name,
                         marker="", markersize=0)
        )
        print(f"  KML plotted: {name}")

    # 8. Final formatting ──────────────────────────────────────────────────────
    ax.set_aspect("equal")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles + kml_handles, loc="best", fontsize=9, framealpha=0.95)

    crs_label = f"EPSG:{EPSG} (RD New / Amersfoort)"
    ax.set_title(
        f"QC plot – {len(df_sel)} selected / {len(df)} total\n"
        f"CRS: {crs_label}"
    )
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
