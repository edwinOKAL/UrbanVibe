from __future__ import annotations

import pathlib
import sys

from .config import (
    DATA_DIR,
    active_config_path,
    load_config,
    write_default_config,
)
from .export import to_geodataframe, write_shapefile
from .filters import FilterError, build_numeric_selector_mask, build_selector_mask
from .io import excel_path, load_observations
from .plotting import plot_qc


EPSG = 28992
OUTPUT_DIR = DATA_DIR / "processed"


def main() -> None:
    source_path = excel_path()
    print(f"\\nReading  {source_path} ...")

    try:
        obs = load_observations(source_path)
    except FileNotFoundError:
        sys.exit(
            "ERROR: observation workbook not found. Expected either data/raw/Obs_log_full_3D.xlsx "
            "or data/Obs_log_full_3D.xlsx"
        )
    except ValueError as exc:
        sys.exit(f"ERROR: {exc}")

    df = obs.frame

    print(f"  X column       : '{obs.x_column}'")
    print(f"  Y column       : '{obs.y_column}'")
    print(f"  Datetime column: '{obs.datetime_column}'")
    print(f"  Total records  : {len(df)}")

    x_min_d, x_max_d = df[obs.x_column].min(), df[obs.x_column].max()
    y_min_d, y_max_d = df[obs.y_column].min(), df[obs.y_column].max()
    dt_min_d = df[obs.datetime_column].min() if obs.datetime_column else None
    dt_max_d = df[obs.datetime_column].max() if obs.datetime_column else None

    print("\\n-- Data extent ------------------------------------------------------")
    print(f"  X : {x_min_d:>14.2f}  ->  {x_max_d:.2f}")
    print(f"  Y : {y_min_d:>14.2f}  ->  {y_max_d:.2f}")
    if dt_min_d is not None:
        print(f"  T : {dt_min_d}  ->  {dt_max_d}")

    cfg_path = active_config_path()
    if not cfg_path.exists():
        write_default_config(
            path=cfg_path,
            x_min=x_min_d,
            x_max=x_max_d,
            y_min=y_min_d,
            y_max=y_max_d,
            t_min=dt_min_d,
            t_max=dt_max_d,
        )
        print(f"\\n  Config created -> {cfg_path}")
        print("  Edit it to set your bbox/time filters, then re-run.")
        print("  (Running now with full-extent defaults.)\\n")

    config = load_config(
        path=cfg_path,
        x_min_d=x_min_d,
        x_max_d=x_max_d,
        y_min_d=y_min_d,
        y_max_d=y_max_d,
        dt_min_d=dt_min_d,
        dt_max_d=dt_max_d,
    )

    print(f"\\n-- Active selection (from {pathlib.Path(cfg_path).name}) -------------------------")
    print(f"  X : {config.x_min:.2f}  ->  {config.x_max:.2f}")
    print(f"  Y : {config.y_min:.2f}  ->  {config.y_max:.2f}")
    if obs.datetime_column:
        print(f"  T : {config.t_start}  ->  {config.t_end}")
    print(f"  Output file: {config.output_filename}")
    print(
        "  Descriptor : "
        f"{config.descriptor_selector if config.descriptor_selector is not None else 'ALL'}"
    )
    print(
        "  loaded_depth : "
        f"{config.loaded_depth_selector if config.loaded_depth_selector is not None else 'ALL'}"
    )
    print(
        "  loaded_charge: "
        f"{config.loaded_charge_selector if config.loaded_charge_selector is not None else 'ALL'}"
    )

    mask = (
        (df[obs.x_column] >= config.x_min)
        & (df[obs.x_column] <= config.x_max)
        & (df[obs.y_column] >= config.y_min)
        & (df[obs.y_column] <= config.y_max)
    )
    if obs.datetime_column:
        mask &= (df[obs.datetime_column] >= config.t_start) & (df[obs.datetime_column] <= config.t_end)

    if config.descriptor_selector is not None:
        if obs.descriptor_column is None:
            sys.exit("ERROR: filter 'descriptor' is set, but no Descriptor column was detected.")
        mask &= build_selector_mask(df[obs.descriptor_column], config.descriptor_selector)

    if config.loaded_depth_selector is not None:
        if obs.loaded_depth_column is None:
            sys.exit("ERROR: filter 'loaded_depth' is set, but no loaded depth column was detected.")
        try:
            mask &= build_numeric_selector_mask(
                df[obs.loaded_depth_column], config.loaded_depth_selector, "loaded_depth"
            )
        except FilterError as exc:
            sys.exit(f"ERROR: {exc}")

    if config.loaded_charge_selector is not None:
        if obs.loaded_charge_column is None:
            sys.exit("ERROR: filter 'loaded_charge' is set, but no loaded charge column was detected.")
        try:
            mask &= build_numeric_selector_mask(
                df[obs.loaded_charge_column], config.loaded_charge_selector, "loaded_charge"
            )
        except FilterError as exc:
            sys.exit(f"ERROR: {exc}")

    df_sel = df[mask].copy()
    print(f"\\n  -> {len(df_sel)} records selected out of {len(df)}.")

    if df_sel.empty:
        print("No records matched the selection. Exiting.")
        sys.exit(0)

    gdf_all = to_geodataframe(df, x_column=obs.x_column, y_column=obs.y_column, epsg=EPSG)
    gdf_sel = to_geodataframe(df_sel, x_column=obs.x_column, y_column=obs.y_column, epsg=EPSG)

    out_path = OUTPUT_DIR / config.output_filename
    write_shapefile(gdf_sel, out_path)
    print(f"  Shapefile written -> {out_path}")

    plot_qc(gdf_all=gdf_all, gdf_sel=gdf_sel, epsg=EPSG)


if __name__ == "__main__":
    main()
