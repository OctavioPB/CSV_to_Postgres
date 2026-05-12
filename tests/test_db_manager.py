import pandas as pd
import pytest

from app.services.db_manager import (
    POSTGRES_RESERVED_KEYWORDS,
    build_column_map,
    coerce_dataframe,
    sanitize_column_name,
)


# ---------------------------------------------------------------------------
# sanitize_column_name
# ---------------------------------------------------------------------------

class TestSanitizeColumnName:
    def test_lowercase(self):
        assert sanitize_column_name("Name") == "name"

    def test_spaces_to_underscores(self):
        assert sanitize_column_name("First Name") == "first_name"

    def test_special_chars_removed(self):
        assert sanitize_column_name("Price ($)") == "price"

    def test_reserved_keyword_gets_suffix(self):
        assert sanitize_column_name("table") == "table_col"
        assert sanitize_column_name("select") == "select_col"

    def test_digit_prefix_gets_col_prefix(self):
        assert sanitize_column_name("1column") == "col_1column"

    def test_empty_string_becomes_column(self):
        assert sanitize_column_name("") == "column"

    def test_all_reserved_keywords_are_handled(self):
        for kw in POSTGRES_RESERVED_KEYWORDS:
            result = sanitize_column_name(kw)
            assert result not in POSTGRES_RESERVED_KEYWORDS


# ---------------------------------------------------------------------------
# build_column_map
# ---------------------------------------------------------------------------

class TestBuildColumnMap:
    def _profile(self, names_and_types: list[tuple[str, str]]) -> list[dict]:
        return [{"name": n, "inferred_type": t} for n, t in names_and_types]

    def test_basic_mapping(self):
        profile = self._profile([("First Name", "str"), ("Age", "int64")])
        col_map = build_column_map(profile)
        assert col_map["First Name"]["sanitized"] == "first_name"
        assert col_map["Age"]["type"] == "int64"

    def test_type_override(self):
        profile = self._profile([("amount", "int64")])
        col_map = build_column_map(profile, type_overrides={"amount": "float64"})
        assert col_map["amount"]["type"] == "float64"

    def test_no_override_keeps_inferred(self):
        profile = self._profile([("score", "float64")])
        col_map = build_column_map(profile)
        assert col_map["score"]["type"] == "float64"


# ---------------------------------------------------------------------------
# coerce_dataframe
# ---------------------------------------------------------------------------

class TestCoerceDataframe:
    def _make_df(self, data: dict) -> pd.DataFrame:
        return pd.DataFrame({k: pd.Series(v, dtype=str) for k, v in data.items()})

    def test_renames_columns(self):
        df = self._make_df({"First Name": ["Alice", "Bob"]})
        col_map = {"First Name": {"sanitized": "first_name", "type": "str"}}
        result = coerce_dataframe(df, col_map)
        assert "first_name" in result.columns
        assert "First Name" not in result.columns

    def test_int_coercion(self):
        df = self._make_df({"age": ["25", "30", ""]})
        col_map = {"age": {"sanitized": "age", "type": "int64"}}
        result = coerce_dataframe(df, col_map)
        assert pd.api.types.is_integer_dtype(result["age"])

    def test_float_coercion(self):
        df = self._make_df({"price": ["1.5", "2.99", "abc"]})
        col_map = {"price": {"sanitized": "price", "type": "float64"}}
        result = coerce_dataframe(df, col_map)
        assert pd.api.types.is_float_dtype(result["price"])
        assert pd.isna(result["price"].iloc[2])

    def test_bool_coercion(self):
        df = self._make_df({"active": ["yes", "no", "true"]})
        col_map = {"active": {"sanitized": "active", "type": "bool"}}
        result = coerce_dataframe(df, col_map)
        # Use == not `is` — numpy booleans are not Python singletons
        assert result["active"].iloc[0] == True   # noqa: E712
        assert result["active"].iloc[1] == False  # noqa: E712

    def test_str_preserves_none_for_empty(self):
        df = self._make_df({"note": ["hello", ""]})
        col_map = {"note": {"sanitized": "note", "type": "str"}}
        result = coerce_dataframe(df, col_map)
        assert result["note"].iloc[0] == "hello"
        assert pd.isna(result["note"].iloc[1])

    def test_output_columns_ordered_by_col_map(self):
        df = self._make_df({"b": ["2"], "a": ["1"]})
        col_map = {
            "a": {"sanitized": "a", "type": "str"},
            "b": {"sanitized": "b", "type": "str"},
        }
        result = coerce_dataframe(df, col_map)
        assert list(result.columns) == ["a", "b"]
