import pandas as pd
import numpy as np
import argparse

def preprocess_csv(input_file, output_file, seed=42):
    df = pd.read_csv(input_file)

    # Save original column positions (1-indexed)
    cols = df.columns.tolist()

    # Normalize columns 1, 3, 6, 9, 10
    for i in [1, 3, 6, 9, 10]:
        col = cols[i - 1]
        values = pd.to_numeric(df[col], errors="raise")

        min_val = values.min()
        max_val = values.max()

        if max_val == min_val:
            df[col] = 0.0
        else:
            df[col] = (values - min_val) / (max_val - min_val)

    # Yes/No: No = 0, Yes = 1
    for i in [4, 11, 13]:
        col = cols[i - 1]
        values = df[col].astype("string").str.strip().str.lower()

        df[col] = values.map({
            "no": 0,
            "yes": 1
        }).astype("Int64")

    # Low/Medium/High: 0, 0.5, 1
    col = cols[5 - 1]
    values = df[col].astype("string").str.strip().str.lower()

    df[col] = values.map({
        "low": 0.0,
        "medium": 0.5,
        "high": 1.0
    })

    # Column 8: None = 0, everything else = 1
    col = cols[8 - 1]
    df[col] = (
        df[col].astype("string")
        .str.strip()
        .str.lower()
        .ne("none")
        .astype(int)
    )

    # Column 12: <= 0 becomes 0, > 0 becomes 1
    col = cols[12 - 1]
    values = pd.to_numeric(df[col], errors="raise")
    df[col] = (values > 0).astype(int)

    # One-hot encode columns 2 and 7
    one_hot_cols = [cols[2 - 1], cols[7 - 1]]

    df = pd.get_dummies(
        df,
        columns=one_hot_cols,
        prefix=one_hot_cols,
        prefix_sep="_",
        dtype=int
    )

    # Shuffle rows reproducibly
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    # Save CSV without adding an index column
    df.to_csv(output_file, index=False)

    print(f"Processed CSV saved to: {output_file}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="Input CSV file")
    parser.add_argument("output_file", help="Output CSV file")
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    preprocess_csv(
        args.input_file,
        args.output_file,
        args.seed
    )