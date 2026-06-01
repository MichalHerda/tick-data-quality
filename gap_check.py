#!/usr/bin/env python3

import sys
from pathlib import Path

import pandas as pd


def load_ticks(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(
        file_path,
        sep=";",
        parse_dates=["datetime"],
    )

    required_columns = {"datetime", "bid", "ask"}

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )

    return df


def analyze(df: pd.DataFrame) -> None:
    total_rows = len(df)

    print("\n=== TICK DATA QUALITY REPORT ===\n")

    print(f"Rows: {total_rows:,}")

    # ------------------------------------------------------------------
    # Timestamp checks
    # ------------------------------------------------------------------

    monotonic = df["datetime"].is_monotonic_increasing

    duplicate_timestamps = (
        df["datetime"]
        .duplicated()
        .sum()
    )

    print(f"Monotonic timestamps: {monotonic}")
    print(f"Duplicate timestamps: {duplicate_timestamps:,}")

    # ------------------------------------------------------------------
    # Duplicate rows
    # ------------------------------------------------------------------

    duplicate_rows = df.duplicated().sum()

    print(f"Duplicate rows: {duplicate_rows:,}")

    # ------------------------------------------------------------------
    # Bid / Ask validation
    # ------------------------------------------------------------------

    crossed_quotes = (df["bid"] > df["ask"]).sum()

    print(f"Crossed quotes (bid > ask): {crossed_quotes:,}")

    # ------------------------------------------------------------------
    # Spread statistics
    # ------------------------------------------------------------------

    spread = df["ask"] - df["bid"]

    print("\n--- Spread Statistics ---")

    print(f"Min spread:    {spread.min():.5f}")
    print(f"Median spread: {spread.median():.5f}")
    print(f"Mean spread:   {spread.mean():.5f}")
    print(f"Max spread:    {spread.max():.5f}")

    # ------------------------------------------------------------------
    # Gap analysis
    # ------------------------------------------------------------------

    gaps_ms = (
        df["datetime"]
        .diff()
        .dt.total_seconds()
        * 1000.0
    )

    valid_gaps = gaps_ms.dropna()

    q1 = valid_gaps.quantile(0.25)
    q3 = valid_gaps.quantile(0.75)

    iqr = q3 - q1

    anomaly_threshold = q3 + 3.0 * iqr

    anomaly_mask = gaps_ms > anomaly_threshold

    anomalies = df.loc[anomaly_mask, ["datetime"]].copy()
    anomalies["gap_ms"] = gaps_ms[anomaly_mask]

    print("\n--- Gap Statistics ---")

    print(f"Median gap: {valid_gaps.median():.2f} ms")
    print(f"Mean gap:   {valid_gaps.mean():.2f} ms")
    print(f"P95 gap:    {valid_gaps.quantile(0.95):.2f} ms")
    print(f"P99 gap:    {valid_gaps.quantile(0.99):.2f} ms")
    print(f"Max gap:    {valid_gaps.max():.2f} ms")

    print("\n--- Gap Counts ---")

    print(f"> 1 second:  {(valid_gaps > 1000).sum():,}")
    print(f"> 5 seconds: {(valid_gaps > 5000).sum():,}")
    print(f"> 30 seconds:{(valid_gaps > 30000).sum():,}")

    print("\n--- Statistical Gap Detection ---")

    print(f"IQR threshold: {anomaly_threshold:.2f} ms")
    print(f"Anomalous gaps: {len(anomalies):,}")

    if not anomalies.empty:
        print("\nTop 20 largest gaps:\n")

        largest = (
            anomalies
            .sort_values("gap_ms", ascending=False)
            .head(20)
        )

        print(largest.to_string(index=False))

    print("\n=== END REPORT ===\n")


def main() -> None:
    if len(sys.argv) != 2:
        print(
            f"Usage: python {Path(sys.argv[0]).name} <ticks.csv>"
        )
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        df = load_ticks(file_path)
        analyze(df)

    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
