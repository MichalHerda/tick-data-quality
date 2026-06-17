#!/usr/bin/env python3
"""
aggregate_quant.py — Quantity-based tick aggregator (Tick Bars)
Aggregates raw tick data into fixed-size tick bars where every bar
contains exactly N ticks. This produces equal-weight bars that
naturally adapt to market activity — dense during volatility,
sparse during quiet periods.

Usage:
    python aggregate_quant.py <file_or_dir> <ticks_per_bar>

Arguments:
    file_or_dir     Path to a single CSV tick file, or a directory
                    containing multiple CSV tick files (processed in
                    lexicographic order, treated as one continuous stream).
    ticks_per_bar   Number of ticks per bar (positive integer).

Output:
    <SYMBOL>_T<n>.csv
    Columns: timestamp;open;high;low;close

    timestamp = datetime of the FIRST tick in the bar
    open      = price of the first tick
    high      = max price in the bar
    low       = min price in the bar
    close     = price of the last tick

Price used: mid = (bid + ask) / 2
"""

import sys
# import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATETIME_FORMAT_IN = "%Y.%m.%d %H:%M:%S.%f"
DATETIME_FORMAT_OUT = "%Y.%m.%d %H:%M:%S.%f"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class TickBar:
    """Accumulates ticks and emits a completed OHLC bar."""

    __slots__ = ("open_time", "open", "high", "low", "close", "_count", "_target")

    def __init__(self, target: int) -> None:
        self._target = target
        self._count = 0
        self.open_time: datetime | None = None
        self.open = 0.0
        self.high = 0.0
        self.low = 0.0
        self.close = 0.0

    # Returns True when the bar is complete
    def push(self, dt: datetime, price: float) -> bool:
        if self._count == 0:
            self.open_time = dt
            self.open = self.high = self.low = price
        else:
            if price > self.high:
                self.high = price
            if price < self.low:
                self.low = price
        self.close = price
        self._count += 1
        return self._count >= self._target

    def reset(self) -> None:
        self._count = 0
        self.open_time = None

    def to_row(self, precision: int) -> list[str]:
        fmt = f"{{:.{precision}f}}"
        return [
            self.open_time.strftime(DATETIME_FORMAT_OUT),
            fmt.format(self.open),
            fmt.format(self.high),
            fmt.format(self.low),
            fmt.format(self.close),
        ]


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def collect_files(path: str) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        files = sorted(p.glob("*.csv"))
        if not files:
            raise FileNotFoundError(f"No CSV files found in directory: {path}")
        return files
    raise FileNotFoundError(f"Path not found: {path}")


# ---------------------------------------------------------------------------
# Tick streaming
# ---------------------------------------------------------------------------

def stream_ticks(files: list[Path]) -> Iterator[tuple[datetime, float]]:
    """Yield (datetime, mid_price) for every tick across all files in order."""
    for filepath in files:
        with open(filepath, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter=";")
            header = [h.strip().lower() for h in next(reader)]

            required = {"datetime", "bid", "ask"}
            if not required.issubset(set(header)):
                raise ValueError(
                    f"{filepath.name}: header must contain datetime, bid, ask. "
                    f"Got: {header}"
                )

            dt_idx = header.index("datetime")
            bid_idx = header.index("bid")
            ask_idx = header.index("ask")

            for lineno, row in enumerate(reader, start=2):
                if not row or all(c.strip() == "" for c in row):
                    continue
                try:
                    dt = datetime.strptime(row[dt_idx].strip(), DATETIME_FORMAT_IN)
                    bid = float(row[bid_idx].strip())
                    ask = float(row[ask_idx].strip())
                except (ValueError, IndexError) as exc:
                    raise ValueError(
                        f"{filepath.name} line {lineno}: malformed row {row!r}"
                    ) from exc
                yield dt, (bid + ask) / 2.0


# ---------------------------------------------------------------------------
# Precision detection
# ---------------------------------------------------------------------------

def detect_precision(files: list[Path], sample: int = 300) -> int:
    """Estimate decimal precision from the first <sample> rows."""
    count = 0
    max_dec = 5
    try:
        for _, price in stream_ticks(files):
            s = f"{price}"
            if "." in s:
                max_dec = max(max_dec, len(s.split(".")[1]))
            count += 1
            if count >= sample:
                break
    except StopIteration:
        pass
    return min(max_dec, 10)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(files: list[Path], ticks_per_bar: int, precision: int) -> list[list[str]]:
    bar = TickBar(ticks_per_bar)
    completed: list[list[str]] = []

    total_ticks = 0
    for dt, price in stream_ticks(files):
        total_ticks += 1
        if bar.push(dt, price):
            completed.append(bar.to_row(precision))
            bar.reset()

    # Partial bar at end of data — emit if it has any ticks
    if bar._count > 0:
        completed.append(bar.to_row(precision))

    return completed, total_ticks


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_output_path(input_path: str, ticks_per_bar: int) -> str:
    p = Path(input_path)
    stem = p.stem if p.is_file() else p.name
    symbol = stem.upper()
    for suffix in ("_TICKS", "_TICK", "_RAW", "_DATA"):
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
            break
    return f"{symbol}_T{ticks_per_bar}.csv"


def write_output(rows: list[list[str]], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["timestamp", "open", "high", "low", "close"])
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> tuple[str, int]:
    if len(argv) != 3:
        print(
            "Usage: python aggregate_quant.py <file_or_dir> <ticks_per_bar>",
            file=sys.stderr,
        )
        sys.exit(1)

    path = argv[1]

    try:
        n = int(argv[2])
    except ValueError:
        print(f"Error: <ticks_per_bar> must be a positive integer, got {argv[2]!r}", file=sys.stderr)
        sys.exit(1)

    if n < 1:
        print("Error: <ticks_per_bar> must be >= 1.", file=sys.stderr)
        sys.exit(1)

    return path, n


def main(argv: list[str]) -> None:
    path, ticks_per_bar = parse_args(argv)

    try:
        files = collect_files(path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[aggregate_quant] Source files  : {[f.name for f in files]}")
    print(f"[aggregate_quant] Ticks per bar : {ticks_per_bar}")

    try:
        precision = detect_precision(files)
        rows, total_ticks = aggregate(files, ticks_per_bar, precision)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = build_output_path(path, ticks_per_bar)
    write_output(rows, output_path)

    print(f"[aggregate_quant] Total ticks   : {total_ticks:,}")
    print(f"[aggregate_quant] Bars generated: {len(rows):,}")
    print(f"[aggregate_quant] Output        : {output_path}")


if __name__ == "__main__":
    main(sys.argv)
