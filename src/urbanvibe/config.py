from __future__ import annotations

import pathlib
import textwrap
import tomllib
from dataclasses import dataclass

import pandas as pd


ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
CONFIG_DIR = ROOT_DIR / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "obs_filter.toml"
LEGACY_CONFIG_PATH = DATA_DIR / "obs_filter.toml"


@dataclass(frozen=True)
class FilterConfig:
    output_filename: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    t_start: pd.Timestamp | None
    t_end: pd.Timestamp | None
    descriptor_selector: list | None
    loaded_depth_selector: str | int | float | None
    loaded_charge_selector: str | int | float | None


def normalize_selector(value):
    if value is None or value == "":
        return None
    if isinstance(value, list):
        cleaned = [v for v in value if v is not None and v != ""]
        return cleaned or None
    return [value]


def normalize_optional_value(value):
    if value is None or value == "":
        return None
    return value


def normalize_output_filename(value) -> str:
    default_name = "selection.shp"
    if value is None or value == "":
        return default_name

    if not isinstance(value, str):
        raise ValueError("output.filename must be a string")

    name = value.strip()
    if not name:
        return default_name

    if pathlib.Path(name).name != name:
        raise ValueError("output.filename must be a file name, not a path")

    if not name.lower().endswith(".shp"):
        name = f"{name}.shp"

    return name


def active_config_path() -> pathlib.Path:
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    if LEGACY_CONFIG_PATH.exists():
        return LEGACY_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def write_default_config(
    *,
    path: pathlib.Path,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    t_min: pd.Timestamp | None,
    t_max: pd.Timestamp | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t_min_str = str(t_min)[:19] if t_min is not None else ""
    t_max_str = str(t_max)[:19] if t_max is not None else ""

    content = textwrap.dedent(
        f"""\
        # obs_filter.toml
        # Edit the values below, then re-run:  pixi run obs_filter
        # Set a value to "" (empty string) to use the full data extent.

        [output]
        # Output shapefile name (written to data/processed/). Change to avoid overwrite.
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
        """
    )
    path.write_text(content, encoding="utf-8")


def load_config(
    *,
    path: pathlib.Path,
    x_min_d: float,
    x_max_d: float,
    y_min_d: float,
    y_max_d: float,
    dt_min_d: pd.Timestamp | None,
    dt_max_d: pd.Timestamp | None,
) -> FilterConfig:
    with path.open("rb") as fh:
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
    t_end = pd.Timestamp(time["end"]) if time.get("end") else dt_max_d

    descriptor_sel = normalize_selector(attrs.get("descriptor", ""))
    loaded_depth_sel = normalize_optional_value(attrs.get("loaded_depth", ""))
    loaded_charge_sel = normalize_optional_value(attrs.get("loaded_charge", ""))

    return FilterConfig(
        output_filename=out_name,
        x_min=sel_xmin,
        x_max=sel_xmax,
        y_min=sel_ymin,
        y_max=sel_ymax,
        t_start=t_start,
        t_end=t_end,
        descriptor_selector=descriptor_sel,
        loaded_depth_selector=loaded_depth_sel,
        loaded_charge_selector=loaded_charge_sel,
    )
