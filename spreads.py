#!/usr/bin/env python3

import argparse
import csv
from decimal import Decimal


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Converts bid/ask ticks into a chronological list "
            "of spread intervals."
        )
    )
    parser.add_argument(
        "input_csv",
        help="Path to the input CSV file"
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Path to the output CSV file "
            "(default: <input>_spreads.csv)"
        )
    )

    return parser.parse_args()


def main():
    args = parse_args()

    input_path = args.input_csv

    if args.output:
        output_path = args.output
    else:
        if input_path.lower().endswith(".csv"):
            output_path = input_path[:-4] + "_spreads.csv"
        else:
            output_path = input_path + "_spreads.csv"

    intervals = []

    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")

        previous_timestamp = None
        current_spread = None

        for row in reader:
            timestamp = row["datetime"].strip()

            bid = Decimal(row["bid"])
            ask = Decimal(row["ask"])
            spread = ask - bid

            if previous_timestamp is None:
                previous_timestamp = timestamp
                current_spread = spread
                continue

            if spread != current_spread:
                intervals.append({
                    "from": previous_timestamp,
                    "to": timestamp,
                    "spread": f"{current_spread:.5f}",
                })

                previous_timestamp = timestamp
                current_spread = spread

        # Save the final interval
        if previous_timestamp is not None:
            intervals.append({
                "from": previous_timestamp,
                "to": timestamp,
                "spread": f"{current_spread:.5f}",
            })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["from", "to", "spread"]
        )

        writer.writeheader()
        writer.writerows(intervals)

    print(f"Saved {len(intervals)} intervals to: {output_path}")


if __name__ == "__main__":
    main()
