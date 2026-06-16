#!/usr/bin/env python3
"""
aggregate_ticks.py — Tick data temporal aggregator
Converts raw tick data (bid/ask) into OHLC candles of arbitrary time periods.

Usage:
    python aggregate_ticks.py <file> <seconds_time_period> <mode: BID|ASK|MEAN>

Example:
    python aggregate_ticks.py EURUSD_ticks.csv 5 BID
    python aggregate_ticks.py EURUSD_ticks.csv 60 MEAN

Output:
    <SYMBOL>_S<period>.csv  (e.g. EURUSD_S5.csv)
    Columns: timestamp;open;high;low;close;volume
"""

import sys
import os
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATETIME_FORMAT_IN = "%Y.%m.%d %H:%M:%S.%f"
DATETIME_FORMAT_OUT = "%Y.%m.%d %H:%M:%S"
VALID_MODES = {"BID", "ASK", "MEAN"}


# ---------------------------------------------------------------------------
# Data classes (no external deps — pure stdlib)
# ---------------------------------------------------------------------------

class Tick:
    __slots__ = ("dt", "bid", "ask", "mid")

    def __init__(self, dt: datetime, bid: float, ask: float, mode: str) -> None:
        self.dt = dt
        self.bid = bid
        self.ask = ask
        if mode == "BID":
            self.mid = bid
        elif mode == "ASK":
            self.mid = ask
        else:  # MEAN
            self.mid = (bid + ask) / 2.0


class Candle:
    __slots__ = ("timestamp", "open", "high", "low", "close", "volume")

    def __init__(self, timestamp: datetime, price: float) -> None:
        self.timestamp = timestamp
        self.open = price
        self.high = price
        self.low = price
        self.close = price
        self.volume = 1

    def update(self, price: float) -> None:
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        self.volume += 1

    def carry_forward(self, new_timestamp: datetime) -> "Candle":
        """Return a synthetic candle for an empty period (OHLC = previous close)."""
        c = Candle(new_timestamp, self.close)
        c.volume = 0
        return c

    def to_row(self, precision: int = 5) -> list:
        fmt = f"{{:.{precision}f}}"
        return [
            self.timestamp.strftime(DATETIME_FORMAT_OUT),
            fmt.format(self.open),
            fmt.format(self.high),
            fmt.format(self.low),
            fmt.format(self.close),
            str(self.volume),
        ]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def bucket_start(dt: datetime, period_seconds: int) -> datetime:
    """Floor a datetime to the nearest period boundary."""
    epoch = datetime(dt.year, dt.month, dt.day)
    delta = (dt - epoch).total_seconds()
    floored = (int(delta) // period_seconds) * period_seconds
    return epoch + timedelta(seconds=floored)


def parse_ticks(filepath: str, mode: str) -> list[Tick]:
    ticks: list[Tick] = []
    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        header = next(reader)  # skip header row

        expected = {"datetime", "bid", "ask"}
        actual = {h.strip().lower() for h in header}
        if not expected.issubset(actual):
            raise ValueError(
                f"CSV header must contain columns: datetime, bid, ask. "
                f"Got: {header}"
            )

        for lineno, row in enumerate(reader, start=2):
            if not row or all(cell.strip() == "" for cell in row):
                continue
            try:
                dt = datetime.strptime(row[0].strip(), DATETIME_FORMAT_IN)
                bid = float(row[1].strip())
                ask = float(row[2].strip())
            except (ValueError, IndexError) as exc:
                raise ValueError(f"Malformed row {lineno}: {row!r}") from exc
            ticks.append(Tick(dt, bid, ask, mode))

    if not ticks:
        raise ValueError("Input file contains no tick data.")

    return ticks


def aggregate(ticks: list[Tick], period_seconds: int) -> list[Candle]:
    candles: list[Candle] = []
    current_candle: Optional[Candle] = None
    current_bucket: Optional[datetime] = None

    for tick in ticks:
        bucket = bucket_start(tick.dt, period_seconds)

        if current_bucket is None:
            # First tick ever
            current_bucket = bucket
            current_candle = Candle(bucket, tick.mid)
            continue

        if bucket == current_bucket:
            # Same period — update existing candle
            current_candle.update(tick.mid)
        else:
            # New period — fill gaps with carry-forward candles
            candles.append(current_candle)
            next_bucket = current_bucket + timedelta(seconds=period_seconds)

            while next_bucket < bucket:
                gap_candle = current_candle.carry_forward(next_bucket)
                candles.append(gap_candle)
                next_bucket += timedelta(seconds=period_seconds)

            current_bucket = bucket
            current_candle = Candle(bucket, tick.mid)

    # Flush the last candle
    if current_candle is not None:
        candles.append(current_candle)

    return candles


def detect_decimal_precision(ticks: list[Tick]) -> int:
    """Detect the number of decimal places used in the source data."""
    max_decimals = 5
    for tick in ticks[:200]:  # sample first 200 ticks
        for val in (tick.bid, tick.ask):
            s = f"{val}"
            if "." in s:
                max_decimals = max(max_decimals, len(s.split(".")[1]))
    return min(max_decimals, 10)


def build_output_path(input_path: str, period_seconds: int) -> str:
    stem = Path(input_path).stem
    # Strip common suffixes like _ticks, _raw, etc. to get the symbol
    symbol = stem.upper()
    for suffix in ("_TICKS", "_RAW", "_DATA", "_TICK"):
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
            break
    return f"{symbol}_S{period_seconds}.csv"


def write_output(candles: list[Candle], output_path: str, precision: int) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for candle in candles:
            writer.writerow(candle.to_row(precision))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> tuple[str, int, str]:
    if len(argv) != 4:
        print(
            "Usage: python aggregate_ticks.py <file> <seconds_time_period> <mode: BID|ASK|MEAN>",
            file=sys.stderr,
        )
        sys.exit(1)

    filepath = argv[1]
    if not os.path.isfile(filepath):
        print(f"Error: file not found: {filepath!r}", file=sys.stderr)
        sys.exit(1)

    try:
        period = int(argv[2])
    except ValueError:
        print(f"Error: <seconds_time_period> must be an integer, got {argv[2]!r}", file=sys.stderr)
        sys.exit(1)

    if period < 1:
        print("Error: <seconds_time_period> must be >= 1.", file=sys.stderr)
        sys.exit(1)

    mode = argv[3].upper()
    if mode not in VALID_MODES:
        print(f"Error: <mode> must be one of {sorted(VALID_MODES)}, got {argv[3]!r}", file=sys.stderr)
        sys.exit(1)

    return filepath, period, mode


def main(argv: list[str]) -> None:
    filepath, period, mode = parse_args(argv)

    print(f"[aggregate_ticks] Reading ticks from: {filepath}")
    ticks = parse_ticks(filepath, mode)
    print(f"[aggregate_ticks] Loaded {len(ticks):,} ticks | mode={mode} | period={period}s")

    precision = detect_decimal_precision(ticks)
    candles = aggregate(ticks, period)
    print(f"[aggregate_ticks] Generated {len(candles):,} candles")

    output_path = build_output_path(filepath, period)
    write_output(candles, output_path, precision)
    print(f"[aggregate_ticks] Output written to: {output_path}")


if __name__ == "__main__":
    main(sys.argv)
