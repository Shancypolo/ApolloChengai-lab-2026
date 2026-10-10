"""Generate and overwrite anonymization mappings from the supplied raw data.

Fit on raw training data when using an existing fitted model.
Prediction transformations preserve row order. CSV output uses seeded row
shuffling and numbered one-hot columns.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import pickle
import re
import sys
import unicodedata

try:
    import numpy as np
    import pandas as pd
except ImportError:
    sys.stderr.write("Error: Missing dependency. Install requirements.txt.\n")
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parent


class DataError(ValueError):
    """A concise error that is safe to display to the user."""


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Error: Invalid arguments. Use --help.\n")


def error_message(error):
    """Avoid displaying library tracebacks, input values, or internal paths."""
    if isinstance(error, DataError):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "File not found."
    if isinstance(error, PermissionError):
        return "File access denied."
    if isinstance(error, UnicodeError):
        return "Invalid text encoding."
    if isinstance(error, json.JSONDecodeError):
        return "Invalid JSON."
    if isinstance(error, pd.errors.EmptyDataError):
        return "No data rows."
    if isinstance(error, (csv.Error, pd.errors.ParserError)):
        return "Invalid CSV."
    if isinstance(error, (pickle.UnpicklingError, EOFError)):
        return "Invalid model file."
    if isinstance(error, ImportError):
        return "Missing dependency. Install requirements.txt."
    if isinstance(error, OSError):
        return "File operation failed."
    return "Invalid data or settings."


CLI_ERRORS = (OSError, ValueError, LookupError, TypeError, AttributeError,
              csv.Error, EOFError, pickle.UnpicklingError, ImportError)

RAW_COLUMNS = [
    "age", "nationality", "gpa", "financial_aid", "stress_level",
    "sleep_hours", "sport", "leadership_role", "home_distance_miles",
    "counseling_visits", "academic_warning", "next_semester_gpa_change",
    "retained_next_year",
]
NUMERIC = {"age": False, "gpa": True, "sleep_hours": True,
           "home_distance_miles": False, "counseling_visits": False}
BINARY = ["financial_aid", "leadership_role", "academic_warning"]
CORE = [c for c in RAW_COLUMNS[:11] if c not in ("nationality", "sport")]
IDENTITY = {"id", "first_name", "last_name"}
MISSING = {"", "na", "n/a", "nan", "null", "missing", "?", "-"}
YES_NO = {"yes": 1.0, "y": 1.0, "true": 1.0, "t": 1.0,
          "no": 0.0, "n": 0.0, "false": 0.0, "f": 0.0}
ORDINAL = {"low": 0.0, "medium": 0.5, "moderate": 0.5, "med": 0.5,
           "high": 1.0}
UNITS = {"age": r"(?:years?|yrs?)", "sleep_hours": r"(?:hours?|hrs?|h)",
         "home_distance_miles": r"(?:miles?|mi)",
         "counseling_visits": r"(?:visits?|times?)"}


def text_key(value):
    if value is None or pd.isna(value):
        return ""
    return " ".join(unicodedata.normalize("NFKC", str(value)).strip().casefold().split())


def column_key(value):
    value = unicodedata.normalize("NFKC", str(value)).strip().lstrip("\ufeff")
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[\s-]+", "_", value).casefold()


def clean_columns(data):
    result = data.copy()
    result.columns = [column_key(c) for c in result.columns]
    if result.columns.duplicated().any():
        raise DataError("Duplicate column names.")
    return result


def remove_identity_columns(data):
    """Remove identity columns from raw or anonymized input."""
    return clean_columns(data).drop(columns=list(IDENTITY), errors="ignore")


def read_input(input_file, *, delimiter=None, encoding="utf-8-sig"):
    """Read named CSV/TSV/semicolon/pipe tables, JSON records, or JSON Lines.

    Preserve literal 'none': it is a real sport category, not a missing value.
    Malformed rows are rejected rather than silently dropped.
    """
    path = Path(input_file)
    content = path.read_text(encoding=encoding)
    suffix = path.suffix.casefold()
    if suffix in {".jsonl", ".ndjson"}:
        records = [json.loads(line) for line in content.splitlines() if line.strip()]
        data = pd.DataFrame(records)
    elif suffix == ".json":
        records = json.loads(content)
        if isinstance(records, dict):
            records = [records]
        data = pd.DataFrame(records)
    else:
        if delimiter == r"\t":
            delimiter = "\t"
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(content[:65536], delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ","
        rows = csv.reader(io.StringIO(content), delimiter=delimiter)
        header = next((row for row in rows if row), [])
        keys = [column_key(c) for c in header]
        if len(keys) != len(set(keys)):
            raise DataError("Duplicate column names.")
        for row in rows:
            if row and len(row) != len(header):
                raise DataError(f"Invalid CSV row at line {rows.line_num}.")
        data = pd.read_csv(io.StringIO(content), sep=delimiter, dtype=object,
                           keep_default_na=False, skipinitialspace=True,
                           on_bad_lines="error")
    if data.empty:
        raise DataError("No data rows.")
    return clean_columns(data)


def number(value, column=""):
    key = text_key(value).replace("\u2212", "-")
    if key in MISSING:
        return np.nan
    if isinstance(value, (bool, np.bool_)):
        return float(value)
    if column in UNITS:
        key = re.sub(r"\s*" + UNITS[column] + r"$", "", key).strip()
    percent = key.endswith("%")
    if percent:
        key = key[:-1].strip()
    # Commas are thousands separators only when correctly grouped. Decimal
    # commas are accepted when there is exactly one and not a thousands group.
    if re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", key):
        key = key.replace(",", "")
    elif re.fullmatch(r"[+-]?\d+,\d+", key):
        key = key.replace(",", ".")
    key = key.replace(" ", "")
    try:
        result = float(key)
        return result / 100 if percent and math.isfinite(result) else (result if math.isfinite(result) else np.nan)
    except ValueError:
        return np.nan


def mapped_value(value, kind):
    key = text_key(value)
    if kind == "leadership":
        if key in MISSING:
            return np.nan
        if key == "none":
            return 0.0
        if key in YES_NO:
            return YES_NO[key]
        numeric = number(value)
        return numeric if numeric in (0.0, 1.0) else 1.0
    aliases = YES_NO if kind == "binary" else ORDINAL
    if key in aliases:
        return aliases[key]
    numeric = number(value)
    allowed = (0.0, 1.0) if kind == "binary" else (0.0, 0.5, 1.0)
    return numeric if numeric in allowed else np.nan


def schema_id(mappings):
    """Bind a fitted model to category meanings, order, and flipped axes."""
    schema = {"feature_columns": mappings["feature_columns"],
              "categories": mappings["categories"],
              "numeric_flips": {c: s["flip"] for c, s in mappings["numeric"].items()}}
    return hashlib.sha256(json.dumps(schema, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_mappings(path):
    mappings = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(mappings, dict):
        raise DataError("Invalid mappings file.")
    if mappings.get("version") != 1:
        raise DataError("Unsupported mappings version.")
    if not all(k in mappings for k in ("numeric", "categories", "feature_columns", "fill_values")):
        raise DataError("Incomplete mappings file.")
    if mappings.get("schema_id") != schema_id(mappings):
        raise DataError("Invalid mappings checksum.")
    for column, stats in mappings["numeric"].items():
        lo, hi = stats.get("min"), stats.get("max")
        if lo is None and hi is None:
            continue  # The delivered template cannot invent original raw bounds.
        median = stats.get("raw_median")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lo, hi, median)) or hi < lo:
            raise DataError(f"{column}: invalid scaling bounds.")
    return mappings


def save_mappings(mappings, path):
    path = Path(path)
    mappings["schema_id"] = schema_id(mappings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mappings, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fit_mappings(data):
    """Learn fresh bounds, fill values, and category vocabulary from this data."""
    data = remove_identity_columns(data)
    required = CORE + ["nationality", "sport"]
    absent = [c for c in required if c not in data]
    if absent:
        raise DataError("Missing columns: " + ", ".join(absent) + ".")
    mappings = {
        "version": 1, "categories": {}, "numeric": {},
        "feature_columns": [], "fill_values": {},
    }
    for column, flip in NUMERIC.items():
        values = data[column].map(lambda v: number(v, column))
        valid = values.dropna()
        if valid.empty:
            raise DataError(f"{column}: no valid numbers.")
        lo, hi, median = float(valid.min()), float(valid.max()), float(valid.median())
        mappings["numeric"][column] = {"min": lo, "max": hi, "raw_median": median, "flip": flip}
        normalized = 0.0 if hi == lo else (median - lo) / (hi - lo)
        mappings["fill_values"][column] = 1 - normalized if flip else normalized
    for column in BINARY + ["stress_level"]:
        kind = "ordinal" if column == "stress_level" else ("leadership" if column == "leadership_role" else "binary")
        values = data[column].map(lambda v: mapped_value(v, kind)).dropna()
        if values.empty:
            raise DataError(f"{column}: no valid values.")
        mappings["fill_values"][column] = float(values.mode().iloc[0])
    for column in ("nationality", "sport"):
        labels = sorted({str(v).strip() for v in data[column] if text_key(v) not in MISSING})
        mappings["categories"][column] = [
            {"value": v, "key": text_key(v), "column": f"{column}_{i}"}
            for i, v in enumerate(labels, 1)
        ]
        keys = [e["key"] for e in mappings["categories"][column]]
        if len(keys) != len(set(keys)):
            raise DataError(f"{column}: duplicate category labels.")
    mappings["feature_columns"] = CORE + [
        e["column"] for c in ("nationality", "sport") for e in mappings["categories"][c]
    ]
    mappings["raw_bounds_ready"] = True
    mappings["training_rows"] = len(data)
    mappings["numeric_bounds_source"] = "Raw training file supplied to anonymize.py."
    mappings["schema_id"] = schema_id(mappings)
    return mappings


def transform_dataframe(data, mappings, *, input_format="raw", clip=False, strict=False):
    """Return (numeric features, diagnostics), with no writes or row shuffle."""
    data = remove_identity_columns(data)
    if input_format not in {"raw", "anonymized"}:
        raise DataError("Input format must be raw or anonymized.")
    if not set(data).intersection(set(CORE) | {"nationality", "sport"} | set(mappings["feature_columns"])):
        raise DataError("No recognized predictor columns.")
    notes = []

    def diagnostic(message):
        if strict:
            raise DataError(message)
        notes.append(message)

    out = pd.DataFrame(index=data.index)
    for column in CORE:
        if column not in data:
            diagnostic(f"{column}: missing column; using saved fill.")
            out[column] = mappings["fill_values"][column]
            continue
        if input_format == "raw" and column in NUMERIC:
            stats = mappings["numeric"][column]
            lo, hi = stats["min"], stats["max"]
            if lo is None or hi is None:
                raise DataError(f"{column}: missing scaling bounds. Run anonymize.py on training data.")
            values = data[column].map(lambda v: number(v, column))
            missing = int(values.isna().sum())
            if missing:
                diagnostic(f"{column}: {missing} invalid value(s); using saved median.")
            values = values.fillna(stats["raw_median"])
            outside = int(((values < lo) | (values > hi)).sum())
            if outside:
                # strict concerns malformed values, not valid out-of-range numbers.
                notes.append(f"{column}: {outside} value(s) outside range; " +
                             ("clipped." if clip else "scaled."))
            scaled = pd.Series(0.0, index=data.index) if lo == hi else (values - lo) / (hi - lo)
            if stats["flip"]:
                scaled = 1 - scaled
            out[column] = scaled.clip(0, 1) if clip else scaled
        else:
            if column in BINARY or column == "stress_level":
                kind = "ordinal" if column == "stress_level" else ("leadership" if column == "leadership_role" and input_format == "raw" else "binary")
                values = data[column].map(lambda v: mapped_value(v, kind))
            else:
                values = data[column].map(lambda v: number(v, column))
            missing = int(values.isna().sum())
            if missing:
                diagnostic(f"{column}: {missing} invalid value(s); using saved fill.")
            out[column] = values.fillna(mappings["fill_values"][column])
            if clip and column in NUMERIC:
                out[column] = out[column].clip(0, 1)
    for column in ("nationality", "sport"):
        entries = mappings["categories"][column]
        names = [e["column"] for e in entries]
        present = [c for c in names if c in data]
        legacy = [c for c in data if c.startswith(column + "_") and c not in names]
        if legacy:
            raise DataError(f"{column}: use numbered indicator names.")
        if column in data and present:
            raise DataError(f"{column}: raw and indicator columns conflict.")
        if column in data:
            keys = data[column].map(text_key)
            known = {e["key"] for e in entries}
            unknown = int((~keys.isin(known)).sum())
            if unknown:
                diagnostic(f"{column}: {unknown} unknown value(s); using zero indicators.")
            for entry in entries:
                out[entry["column"]] = (keys == entry["key"]).astype(float)
        else:
            if not present:
                diagnostic(f"{column}: missing category; using zero indicators.")
            for name in names:
                if name not in data:
                    out[name] = 0.0
                else:
                    values = data[name].map(lambda v: mapped_value(v, "binary"))
                    missing = int(values.isna().sum())
                    if missing:
                        diagnostic(f"{name}: {missing} invalid indicator(s); using zero.")
                    out[name] = values.fillna(0.0)
            if (out[names].sum(axis=1) > 1).any():
                raise DataError(f"{column}: multiple active indicators.")
    return out.reindex(columns=mappings["feature_columns"]).astype(float), notes


def preprocess_csv(input_file, output_file=None, seed=42, mappings_file=ROOT / "data_mappings.json",
                   *, clip=False, strict=False,
                   shuffle=True, delimiter=None, encoding="utf-8-sig"):
    """Fit from this raw file and overwrite mappings on every successful run."""
    data = remove_identity_columns(read_input(input_file, delimiter=delimiter, encoding=encoding))
    path = Path(mappings_file)
    mappings = fit_mappings(data)
    result, notes = transform_dataframe(data, mappings, input_format="raw", clip=clip, strict=strict)
    # Optional outcomes are preserved only for a training export, never used by run_model.
    for target in ("next_semester_gpa_change", "retained_next_year"):
        if target in data:
            if target == "retained_next_year":
                values = data[target].map(lambda v: mapped_value(v, "binary"))
            else:
                values = data[target].map(number)
                values = (values > 0).astype(float).where(values.notna())
            if values.isna().any():
                raise DataError(f"{target}: invalid values.")
            result[target] = values
    # Match original training-export column order, including optional targets.
    result = result.reindex(columns=CORE + [c for c in RAW_COLUMNS[11:] if c in result] +
                            [c for c in mappings["feature_columns"] if c not in CORE])
    if shuffle:
        result = result.sample(frac=1, random_state=seed).reset_index(drop=True)
    if output_file is not None:
        result.to_csv(output_file, index=False)
    save_mappings(mappings, path)
    return result, mappings, notes


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path)
    parser.add_argument("output_file", type=Path, nargs="?", default=Path("anonymized.csv"),
                        help="Output CSV (default: anonymized.csv)")
    parser.add_argument("--mappings", type=Path, default=ROOT / "data_mappings.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--clip", action="store_true", help="Clip scaled numeric features to [0, 1]")
    parser.add_argument("--strict", action="store_true", help="Reject missing/invalid values and unknown categories")
    parser.add_argument("--delimiter")
    parser.add_argument("--encoding", default="utf-8-sig")
    args = parser.parse_args()
    try:
        result, _, notes = preprocess_csv(
            args.input_file, args.output_file, args.seed, args.mappings,
            clip=args.clip, strict=args.strict, shuffle=not args.no_shuffle,
            delimiter=args.delimiter, encoding=args.encoding,
        )
    except CLI_ERRORS as exc:
        parser.exit(2, f"Error: {error_message(exc)}\n")
    except Exception:
        parser.exit(2, "Error: Processing failed.\n")
    for message in notes:
        print("Warning:", message, file=sys.stderr)
    print(f"Rows: {len(result)}; columns: {len(result.columns)}")
    print(f"Mappings overwritten: {args.mappings}")
    if args.output_file:
        print(f"Processed CSV saved: {args.output_file}")


if __name__ == "__main__":
    main()
