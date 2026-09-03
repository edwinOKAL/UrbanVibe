from __future__ import annotations

import pathlib
from dataclasses import dataclass

import pandas as pd

from .config import DATA_DIR


DEFAULT_RAW_EXCEL_PATH = DATA_DIR / "raw" / "Obs_log_full_3D.xlsx"
LEGACY_EXCEL_PATH = DATA_DIR / "Obs_log_full_3D.xlsx"


@dataclass(frozen=True)
class ObservationsData:
    frame: pd.DataFrame
    x_column: str
    y_column: str
    datetime_column: str | None
    descriptor_column: str | None
    loaded_depth_column: str | None
    loaded_charge_column: str | None


def excel_path() -> pathlib.Path:
    if DEFAULT_RAW_EXCEL_PATH.exists():
        return DEFAULT_RAW_EXCEL_PATH
    return LEGACY_EXCEL_PATH


def detect_columns(df: pd.DataFrame):
    x_col = y_col = dt_col = None

    for col in df.columns:
        stripped = col.strip().upper()
        low = col.strip().lower()

        if stripped == "X" and x_col is None:
            x_col = col
        elif stripped == "Y" and y_col is None:
            y_col = col

        is_dt = pd.api.types.is_datetime64_any_dtype(df[col])
        if is_dt and dt_col is None:
            if any(k in low for k in ("shoot", "datetime", "date_time")):
                dt_col = col

    if dt_col is None:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                dt_col = col
                break

    return x_col, y_col, dt_col


def normalize_column_name(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def find_optional_column(df: pd.DataFrame, aliases: set[str]):
    normalized = {normalize_column_name(col): col for col in df.columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def load_observations(path: pathlib.Path) -> ObservationsData:
    df = pd.read_excel(path)

    x_col, y_col, dt_col = detect_columns(df)
    if x_col is None or y_col is None:
        raise ValueError("could not detect X/Y coordinate columns")

    descriptor_col = find_optional_column(
        df,
        {"descriptor", "descr", "description", "type", "obstype", "observationtype"},
    )
    loaded_depth_col = find_optional_column(
        df,
        {"loadeddepth", "loaddepth", "loadeddep", "depthloaded"},
    )
    loaded_charge_col = find_optional_column(
        df,
        {"loadedcharge", "loadcharge", "chargeloaded"},
    )

    df = df.dropna(subset=[x_col, y_col]).reset_index(drop=True)

    return ObservationsData(
        frame=df,
        x_column=x_col,
        y_column=y_col,
        datetime_column=dt_col,
        descriptor_column=descriptor_col,
        loaded_depth_column=loaded_depth_col,
        loaded_charge_column=loaded_charge_col,
    )
