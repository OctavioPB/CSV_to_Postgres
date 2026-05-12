import logging
import re

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000

POSTGRES_RESERVED_KEYWORDS = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc",
    "asymmetric", "authorization", "binary", "both", "case", "cast",
    "check", "collate", "column", "constraint", "create", "cross",
    "current_catalog", "current_date", "current_role", "current_schema",
    "current_time", "current_timestamp", "current_user", "default",
    "deferrable", "deferred", "desc", "distinct", "do", "else", "end",
    "except", "false", "fetch", "for", "foreign", "freeze", "from", "full",
    "grant", "group", "having", "ilike", "in", "initially", "inner",
    "intersect", "into", "is", "isnull", "join", "lateral", "leading",
    "left", "like", "limit", "localtime", "localtimestamp", "natural",
    "not", "notnull", "null", "offset", "on", "only", "or", "order",
    "outer", "overlaps", "placing", "primary", "references", "returning",
    "right", "select", "session_user", "similar", "some", "symmetric",
    "table", "tablesample", "then", "to", "trailing", "true", "union",
    "unique", "user", "using", "variadic", "verbose", "when", "where",
    "window", "with",
}

TYPE_MAP = {
    "int64": Integer(),
    "float64": Float(),
    "datetime": DateTime(),
    "bool": Boolean(),
    "str": String(),
}


def sanitize_column_name(name: str) -> str:
    """Lowercase, replace non-alphanumeric characters with underscores."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if name in POSTGRES_RESERVED_KEYWORDS:
        name = f"{name}_col"
    if name and name[0].isdigit():
        name = f"col_{name}"
    return name or "column"


def build_column_map(
    profile_columns: list[dict],
    type_overrides: dict | None = None,
) -> dict[str, dict]:
    """Map original column names to sanitized names and resolved types."""
    col_map: dict[str, dict] = {}
    for col in profile_columns:
        original = col["name"]
        sanitized = sanitize_column_name(original)
        resolved_type = (type_overrides or {}).get(original, col["inferred_type"])
        col_map[original] = {"sanitized": sanitized, "type": resolved_type}
    return col_map


def create_table_if_not_exists(
    engine: Engine, table_name: str, col_map: dict[str, dict]
) -> Table:
    """Create target table using SQLAlchemy Core. Never drops existing tables."""
    metadata = MetaData()
    columns = [Column("id", Integer, primary_key=True, autoincrement=True)]
    for info in col_map.values():
        sa_type = TYPE_MAP.get(info["type"], String())
        columns.append(Column(info["sanitized"], sa_type, nullable=True))
    table = Table(table_name, metadata, *columns)
    metadata.create_all(engine, checkfirst=True)
    return table


def coerce_dataframe(df: pd.DataFrame, col_map: dict[str, dict]) -> pd.DataFrame:
    """Rename columns to sanitized names and coerce values to target types."""
    rename_map = {orig: info["sanitized"] for orig, info in col_map.items()}
    df = df.rename(columns=rename_map).copy()

    for orig, info in col_map.items():
        col = info["sanitized"]
        col_type = info["type"]
        if col not in df.columns:
            continue

        series = df[col].replace("", pd.NA)
        if col_type == "int64":
            df[col] = pd.to_numeric(series, errors="coerce").astype("Int64")
        elif col_type == "float64":
            df[col] = pd.to_numeric(series, errors="coerce")
        elif col_type == "datetime":
            df[col] = pd.to_datetime(series, errors="coerce")
        elif col_type == "bool":
            true_vals = {"true", "yes", "1", "t", "y"}
            df[col] = series.str.lower().isin(true_vals).where(series.notna(), other=None)
        else:
            # Convert to object dtype so None is a real Python None, not pd.NA
            df[col] = series.astype(object).where(series.notna(), other=None)

    return df[[info["sanitized"] for info in col_map.values()]]


def bulk_insert(
    engine: Engine, table: Table, df: pd.DataFrame
) -> tuple[int, int]:
    """Insert DataFrame in chunks of CHUNK_SIZE. Returns (rows_inserted, rows_failed)."""
    rows_inserted = 0
    rows_failed = 0
    records = df.to_dict(orient="records")

    for i in range(0, len(records), CHUNK_SIZE):
        batch = records[i : i + CHUNK_SIZE]
        clean_batch = [
            {
                k: (None if (v is pd.NA or (isinstance(v, float) and pd.isna(v))) else v)
                for k, v in row.items()
            }
            for row in batch
        ]
        try:
            with engine.begin() as conn:
                conn.execute(table.insert(), clean_batch)
            rows_inserted += len(batch)
        except Exception as exc:
            logger.error("Batch insert failed at offset %d: %s", i, exc)
            rows_failed += len(batch)

    return rows_inserted, rows_failed
