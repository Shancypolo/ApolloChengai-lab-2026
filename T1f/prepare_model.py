"""Export a fitted model for numbered, flipped anonymizer features.

This does NOT retrain the classifier. It fits only a column selector, renames
category inputs, and changes the coordinate system for GPA and sleep hours.
For x_new = 1 - x_old: beta_new = -beta_old; intercept_new += beta_old.
"""
import copy
from pathlib import Path
import sys
import warnings

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.exceptions import InconsistentVersionWarning
    from sklearn.pipeline import Pipeline
    import anonymize
except ImportError:
    sys.stderr.write("Error: Missing dependency. Install requirements.txt.\n")
    raise SystemExit(2)


def export_model(reference_csv, source_model, output_dir):
    data = pd.read_csv(reference_csv)
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        original = joblib.load(source_model)
    mappings = {"version": 1, "raw_bounds_ready": False,
                "numeric_bounds_source": "Not fitted.",
                "numeric": {c: {"min": None, "max": None, "raw_median": None, "flip": flip}
                            for c, flip in anonymize.NUMERIC.items()},
                "categories": {}, "fill_values": {}, "feature_columns": []}
    rename = {}
    for category in ("nationality", "sport"):
        columns = [c for c in data if c.startswith(category + "_")]
        entries = []
        for index, column in enumerate(columns, 1):
            label = column[len(category) + 1:]
            name = f"{category}_{index}"
            rename[column] = name
            entries.append({"value": label, "key": anonymize.text_key(label), "column": name})
        mappings["categories"][category] = entries
    converted = data.rename(columns=rename).copy()
    for column, flip in anonymize.NUMERIC.items():
        if flip:
            converted[column] = 1 - converted[column]
    for column in anonymize.CORE:
        values = converted[column]
        mappings["fill_values"][column] = float(
            values.median() if column in anonymize.NUMERIC else values.mode().iloc[0]
        )
    mappings["feature_columns"] = anonymize.CORE + list(rename.values())
    mappings["schema_id"] = anonymize.schema_id(mappings)
    original_selector = original.named_steps["features"]
    selected = original_selector.transformers[0][2]
    names = [rename.get(c, c) for c in selected]
    x = converted[mappings["feature_columns"]]
    selector = ColumnTransformer([("retained", "passthrough", names)], remainder="drop")
    selector.fit(x)
    classifier = copy.deepcopy(original.named_steps["model"])
    for column, flip in anonymize.NUMERIC.items():
        if flip and column in selected:
            index = selected.index(column)
            beta = classifier.coef_[:, index].copy()
            classifier.coef_[:, index] = -beta
            classifier.intercept_ += beta
    model = Pipeline([("features", selector), ("model", classifier)])
    model.mapping_schema_id_ = mappings["schema_id"]
    model.target_name_ = "next_semester_gpa_change"
    model.input_convention_ = "Numbered one-hot names; gpa/sleep_hours use 1-minus-minmax."
    source_x = data.drop(columns=anonymize.RAW_COLUMNS[11:], errors="ignore")
    if not np.array_equal(original.predict(source_x), model.predict(x)) or not np.allclose(
            original.predict_proba(source_x), model.predict_proba(x), rtol=0, atol=1e-14):
        raise anonymize.DataError("Prediction verification failed.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    anonymize.save_mappings(mappings, output_dir / "data_mappings.json")
    joblib.dump(model, output_dir / "model.joblib")
    return model, mappings


if __name__ == "__main__":
    parser = anonymize.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("source_model", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        export_model(args.reference_csv, args.source_model, args.output_dir)
    except InconsistentVersionWarning:
        parser.exit(2, "Error: Install scikit-learn 1.8.0.\n")
    except anonymize.CLI_ERRORS as exc:
        parser.exit(2, f"Error: {anonymize.error_message(exc)}\n")
    except Exception:
        parser.exit(2, "Error: Model export failed.\n")
    print("Exported model.joblib and data_mappings.json; all reference predictions preserved.")
