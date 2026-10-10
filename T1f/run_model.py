"""Predict new local data; print predictions to stdout without saving any files."""
from __future__ import annotations

import sys

# Keep prediction runs read-only, including Python's import bytecode cache.
sys.dont_write_bytecode = True

from pathlib import Path
import warnings

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.exceptions import InconsistentVersionWarning
    import anonymize
except ImportError:
    sys.stderr.write("Error: Missing dependency. Install requirements.txt.\n")
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parent


def predict_file(input_file, mappings_file=ROOT / "data_mappings.json",
                 model_file=ROOT / "model.joblib", *, input_format="raw",
                 clip=False, strict=False, delimiter=None, encoding="utf-8-sig"):
    mappings = anonymize.load_mappings(mappings_file)
    # Identity columns are dropped BEFORE entering the anonymization function.
    data = anonymize.remove_identity_columns(
        anonymize.read_input(input_file, delimiter=delimiter, encoding=encoding)
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        try:
            model = joblib.load(model_file)
        except (ValueError, KeyError, AttributeError, TypeError, EOFError, anonymize.pickle.UnpicklingError):
            raise anonymize.DataError("Invalid model file.") from None
    if getattr(model, "mapping_schema_id_", None) != mappings["schema_id"]:
        raise anonymize.DataError("Model and mappings do not match.")
    target = "next_semester_gpa_change"
    labels = data[target].map(anonymize.number) if target in data else None
    features, notes = anonymize.transform_dataframe(
        data.drop(columns=[target, "retained_next_year"], errors="ignore"),
        mappings, input_format=input_format, clip=clip, strict=strict
    )
    expected = list(model.feature_names_in_)
    if set(expected) != set(features):
        raise anonymize.DataError("Model feature names do not match.")
    features = features.reindex(columns=expected)
    prediction = model.predict(features)
    columns = {"row_number": np.arange(1, len(features) + 1), "predicted_class": prediction}
    result = pd.DataFrame(columns)
    if labels is not None:
        invalid = int(labels.isna().sum())
        if invalid:
            message = f"{target}: {invalid} invalid value(s); excluded from comparison."
            if strict:
                raise anonymize.DataError(message)
            notes.append(message)
        result[target] = (labels > 0).astype("Int64").where(labels.notna()).to_numpy()
        result[target] = result[target].astype("Int64")
        result["matches"] = result["predicted_class"].eq(result[target]).astype("boolean")
    return result, notes


def main():
    parser = anonymize.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path, help="New CSV/TSV/JSON/JSONL file with named columns")
    parser.add_argument("--mappings", type=Path, default=ROOT / "data_mappings.json")
    parser.add_argument("--model", type=Path, default=ROOT / "model.joblib")
    parser.add_argument("--input-format", choices=["raw", "anonymized"], default="raw",
                        help="Use anonymized for already transformed numeric data")
    parser.add_argument("--clip", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--delimiter")
    parser.add_argument("--encoding", default="utf-8-sig")
    args = parser.parse_args()
    try:
        result, notes = predict_file(args.input_file, args.mappings, args.model,
                                    input_format=args.input_format, clip=args.clip,
                                    strict=args.strict, delimiter=args.delimiter,
                                    encoding=args.encoding)
    except InconsistentVersionWarning:
        parser.exit(2, "Error: Install scikit-learn 1.8.0.\n")
    except anonymize.CLI_ERRORS as exc:
        parser.exit(2, f"Error: {anonymize.error_message(exc)}\n")
    except Exception:
        parser.exit(2, "Error: Prediction failed.\n")
    for message in notes:
        print("Warning:", message, file=sys.stderr)
    print(result.to_string(index=False))
    if "matches" in result:
        total = int(result["matches"].notna().sum())
        if total:
            correct = int(result["matches"].sum())
            print(f"Accuracy: {correct / total:.2%} ({correct}/{total})")
        else:
            print("Accuracy: unavailable (no valid labels).")


if __name__ == "__main__":
    main()
