import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

NULL_THRESHOLD = 0.95

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
]


def parse_csv(file_path: Path) -> pd.DataFrame:
    """Read CSV with all columns as string; strip whitespace from string columns."""
    df = pd.read_csv(file_path, dtype=str)
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            df[col] = df[col].str.strip()
    return df


def _try_int(series: pd.Series) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False
    try:
        non_null.astype("int64")
        return True
    except (ValueError, OverflowError):
        return False


def _try_float(series: pd.Series) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False
    try:
        non_null.astype("float64")
        return True
    except ValueError:
        return False


def _try_datetime(series: pd.Series) -> Optional[str]:
    non_null = series.dropna()
    if non_null.empty:
        return None
    for fmt in DATE_FORMATS:
        try:
            pd.to_datetime(non_null, format=fmt, errors="raise")
            return fmt
        except (ValueError, TypeError):
            continue
    return None


def _try_bool(series: pd.Series) -> bool:
    bool_values = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}
    non_null = series.dropna()
    if non_null.empty:
        return False
    return non_null.str.lower().isin(bool_values).all()


def infer_column_type(series: pd.Series) -> dict:
    """Infer most specific type for a series. Returns dict with 'type' and 'date_format'."""
    non_null = series.replace("", pd.NA).dropna()

    if _try_int(non_null):
        return {"type": "int64", "date_format": None}
    if _try_float(non_null):
        return {"type": "float64", "date_format": None}
    date_fmt = _try_datetime(non_null)
    if date_fmt:
        return {"type": "datetime", "date_format": date_fmt}
    if _try_bool(non_null):
        return {"type": "bool", "date_format": None}
    return {"type": "str", "date_format": None}


def profile_csv(df: pd.DataFrame) -> dict:
    """Compute shape, null counts, inferred types, and sample values for each column."""
    n_rows, n_cols = df.shape
    columns = []

    for col in df.columns:
        series = df[col].replace("", pd.NA)
        null_count = int(series.isna().sum())
        null_frac = null_count / n_rows if n_rows > 0 else 0.0
        inferred = infer_column_type(series)
        sample_values = series.dropna().head(5).tolist()

        columns.append({
            "name": col,
            "inferred_type": inferred["type"],
            "date_format": inferred["date_format"],
            "null_count": null_count,
            "null_pct": round(null_frac * 100, 1),
            "high_null_warning": null_frac > NULL_THRESHOLD,
            "sample_values": sample_values,
        })

    return {
        "row_count": n_rows,
        "col_count": n_cols,
        "columns": columns,
    }
