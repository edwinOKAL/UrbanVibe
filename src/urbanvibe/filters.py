from __future__ import annotations

import re

import pandas as pd


class FilterError(ValueError):
    pass


def build_selector_mask(series: pd.Series, selector) -> pd.Series:
    if selector is None:
        return pd.Series(True, index=series.index)

    raw_values = selector if isinstance(selector, list) else [selector]
    values = [v for v in raw_values if v is not None and v != ""]
    if not values:
        return pd.Series(True, index=series.index)

    num_values = pd.to_numeric(pd.Series(values), errors="coerce")
    if num_values.notna().all():
        series_num = pd.to_numeric(series, errors="coerce")
        return series_num.isin(num_values.tolist())

    targets = {str(v).strip().lower() for v in values}
    series_txt = series.astype(str).str.strip().str.lower()
    return series_txt.isin(targets)


def _is_plain_numeric_like(value) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    return re.fullmatch(r"[-+]?\d+(?:\.\d+)?", s) is not None


def build_numeric_selector_mask(series: pd.Series, selector, field_name: str) -> pd.Series:
    series_num = pd.to_numeric(series, errors="coerce")

    def from_scalar(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return series_num == float(value)

        if isinstance(value, str):
            s = value.strip()
            if not s:
                return pd.Series(True, index=series.index)

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

            if _is_plain_numeric_like(s):
                return series_num == float(s)

            raise FilterError(
                f"invalid selector '{value}' for {field_name}; "
                "use a number or a single comparison like '>=10'"
            )

        raise FilterError(f"unsupported selector type '{type(value).__name__}' for {field_name}")

    if selector is None:
        return pd.Series(True, index=series.index)

    if isinstance(selector, (list, dict)):
        raise FilterError(
            f"{field_name} does not support lists, ranges, or inline tables; "
            "use a single value like 12.5 or a single comparison like '>=10'"
        )

    return from_scalar(selector)
