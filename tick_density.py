# counting, how many ticks mean during INTERVAL period (f.e: 5 seconds intervals unit, during 5 minuts periods)

import csv
import os
import sys
from datetime import datetime, timedelta


INPUT_DATETIME_FORMAT = "%Y.%m.%d %H:%M:%S.%f"
INTERVAL = 60


def floor_to_5_minutes(dt):
    """
    Round datetime down to the beginning of its 5-minute interval.
    """
    return dt.replace(
        minute=(dt.minute // 5) * 5,
        second=0,
        microsecond=0
    )


def process_file(input_path):
    """
    Calculate average ticks per 5 seconds for each 5-minute interval.
    Returns a dictionary:
        {
            "13:00-13:05": 0.523333,
            ...
        }
    """
    interval_counts = {}

    with open(input_path, "r", newline="") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")

        for row in reader:
            dt = datetime.strptime(
                row["datetime"],
                INPUT_DATETIME_FORMAT
            )

            interval_start = floor_to_5_minutes(dt)

            interval_counts[interval_start] = (
                interval_counts.get(interval_start, 0) + 1
            )

    result = {}

    for interval_start in sorted(interval_counts):
        interval_end = interval_start + timedelta(minutes=5)

        interval_label = (
            f"{interval_start.strftime('%H:%M')}"
            f"-"
            f"{interval_end.strftime('%H:%M')}"
        )

        avg_ticks_per_interval = (
            interval_counts[interval_start] / INTERVAL
        )

        result[interval_label] = avg_ticks_per_interval

    return result


def save_results(results, input_path):
    """
    Save results to a CSV file.
    """
    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}_tick_density.csv"

    with open(output_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)

        writer.writerow([
            "interval",
            "average_ticks_per_interval"
        ])

        for interval, value in results.items():
            writer.writerow([
                interval,
                f"{value:.6f}"
            ])

    return output_path


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python3 tick_density.py <file_loc.csv>"
        )
        sys.exit(1)

    input_path = sys.argv[1]

    if not os.path.isfile(input_path):
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    try:
        results = process_file(input_path)
        output_path = save_results(results, input_path)

        print(
            f"Results saved to: {output_path}"
        )

    except Exception as exc:
        print(f"Error while processing the file: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
