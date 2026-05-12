import io
from pathlib import Path

import pandas as pd
import pytest

from app.services.csv_processor import (
    _try_bool,
    _try_datetime,
    _try_float,
    _try_int,
    infer_column_type,
    parse_csv,
    profile_csv,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _series(values: list) -> pd.Series:
    return pd.Series(values, dtype=str)


def _write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test.csv"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Type inference — unit tests
# ---------------------------------------------------------------------------

class TestTryInt:
    def test_pure_integers(self):
        assert _try_int(_series(["1", "2", "3"]))

    def test_floats_fail(self):
        assert not _try_int(_series(["1.5", "2.0"]))

    def test_mixed_fail(self):
        assert not _try_int(_series(["1", "foo"]))

    def test_empty_series(self):
        assert not _try_int(_series([]))

    def test_ignores_nulls(self):
        assert _try_int(pd.Series(["1", None, "3"], dtype=object))


class TestTryFloat:
    def test_floats(self):
        assert _try_float(_series(["1.1", "2.2"]))

    def test_integers_pass(self):
        assert _try_float(_series(["1", "2"]))

    def test_alpha_fails(self):
        assert not _try_float(_series(["1.1", "abc"]))


class TestTryDatetime:
    def test_iso_dates(self):
        fmt = _try_datetime(_series(["2024-01-01", "2024-06-15"]))
        assert fmt == "%Y-%m-%d"

    def test_datetime_with_time(self):
        fmt = _try_datetime(_series(["2024-01-01 12:00:00"]))
        assert fmt == "%Y-%m-%d %H:%M:%S"

    def test_mixed_fails(self):
        assert _try_datetime(_series(["2024-01-01", "not-a-date"])) is None

    def test_empty_returns_none(self):
        assert _try_datetime(_series([])) is None


class TestTryBool:
    def test_true_false(self):
        assert _try_bool(_series(["True", "False", "true", "false"]))

    def test_yes_no(self):
        assert _try_bool(_series(["yes", "no", "Yes", "No"]))

    def test_one_zero(self):
        assert _try_bool(_series(["1", "0"]))

    def test_mixed_fails(self):
        assert not _try_bool(_series(["yes", "maybe"]))


class TestInferColumnType:
    def test_int_column(self):
        result = infer_column_type(_series(["1", "2", "3"]))
        assert result["type"] == "int64"
        assert result["date_format"] is None

    def test_float_column(self):
        result = infer_column_type(_series(["1.5", "2.5"]))
        assert result["type"] == "float64"

    def test_datetime_column(self):
        result = infer_column_type(_series(["2024-01-01", "2024-06-01"]))
        assert result["type"] == "datetime"
        assert result["date_format"] == "%Y-%m-%d"

    def test_bool_column(self):
        result = infer_column_type(_series(["true", "false"]))
        assert result["type"] == "bool"

    def test_str_fallback(self):
        result = infer_column_type(_series(["hello", "world"]))
        assert result["type"] == "str"

    def test_all_null_falls_back_to_str(self):
        result = infer_column_type(pd.Series([None, None, None], dtype=object))
        assert result["type"] == "str"


# ---------------------------------------------------------------------------
# parse_csv — integration
# ---------------------------------------------------------------------------

class TestParseCsv:
    def test_returns_dataframe_with_str_columns(self, tmp_path):
        p = _write_csv(tmp_path, "a,b\n1,hello\n2,world")
        df = parse_csv(p)
        assert list(df.columns) == ["a", "b"]
        # pandas 2+ may use StringDtype; both are string-like
        assert pd.api.types.is_string_dtype(df["a"]) or df["a"].dtype == object

    def test_strips_whitespace(self, tmp_path):
        p = _write_csv(tmp_path, "name\n  Alice  \n  Bob  ")
        df = parse_csv(p)
        assert df["name"].tolist() == ["Alice", "Bob"]

    def test_handles_empty_file(self, tmp_path):
        p = _write_csv(tmp_path, "a,b\n")
        df = parse_csv(p)
        assert df.shape == (0, 2)


# ---------------------------------------------------------------------------
# profile_csv
# ---------------------------------------------------------------------------

class TestProfileCsv:
    def test_shape_reported(self, tmp_path):
        p = _write_csv(tmp_path, "a,b,c\n1,2,3\n4,5,6")
        df = parse_csv(p)
        profile = profile_csv(df)
        assert profile["row_count"] == 2
        assert profile["col_count"] == 3

    def test_null_counts(self, tmp_path):
        # Use a two-column CSV so the null cell is real (not a blank line)
        # pandas skips blank lines by default; use a comma to produce an empty cell
        p = _write_csv(tmp_path, "a,x\n1,one\n2,\n3,three")
        df = parse_csv(p)
        profile = profile_csv(df)
        col = next(c for c in profile["columns"] if c["name"] == "x")
        assert col["null_count"] == 1
        assert col["null_pct"] == pytest.approx(33.3, abs=0.2)

    def test_high_null_warning(self, tmp_path):
        # Row index column 'a' keeps the rows alive; 'x' is >95% null
        rows = "\n".join(f"{i}," for i in range(20))  # 20 rows, x is always empty
        p = _write_csv(tmp_path, f"a,x\n{rows}")
        df = parse_csv(p)
        profile = profile_csv(df)
        col = next(c for c in profile["columns"] if c["name"] == "x")
        assert col["high_null_warning"] is True

    def test_no_high_null_warning_for_normal_column(self, tmp_path):
        p = _write_csv(tmp_path, "x\n1\n2\n3")
        df = parse_csv(p)
        profile = profile_csv(df)
        assert profile["columns"][0]["high_null_warning"] is False

    def test_sample_values_capped_at_five(self, tmp_path):
        rows = "\n".join(str(i) for i in range(20))
        p = _write_csv(tmp_path, f"n\n{rows}")
        df = parse_csv(p)
        profile = profile_csv(df)
        assert len(profile["columns"][0]["sample_values"]) <= 5
