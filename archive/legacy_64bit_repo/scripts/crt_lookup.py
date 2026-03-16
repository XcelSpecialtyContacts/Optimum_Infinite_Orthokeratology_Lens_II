#!/usr/bin/env python3
"""
CRT SKU lookup tool (fixed-path version)

Given Flat K and Spherical Error (MRS), look up Base Curve radius (from BC_Code/10),
Return Zone Depth (from RZD_Code/1000), and Landing Zone Angle (LZA) from the table
located at data/CRT_SKU.csv.

Usage:
    python scripts/crt_lookup.py --flat-k 39.07 --se -3.33

Behavior:
- Flat K is rounded to nearest 0.125 before lookup.
- Spherical Error is rounded to nearest 0.25 before lookup.
- The CSV path is fixed (no argument).
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Tuple, Optional

# Hard-coded path relative to project root
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "CRT_SKUs.csv"
REQUIRED_HEADERS = {"Flat K", "MRS", "BC_Code", "RZD_Code", "LZA"}

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Look up CRT parameters from CRT_SKU.csv by Flat K and Spherical Error."
    )
    p.add_argument("--flat-k", type=float, required=True, help="Flat K value (e.g., 39.07)")
    p.add_argument("--se", "--mrs", dest="mrs", type=float, required=True,
                   help="Spherical Error (MRS), negative for myopia (e.g., -3.33)")
    p.add_argument("--json", action="store_true",
                   help="Output JSON instead of human-readable text.")
    return p.parse_args()

def read_rows(csv_path: Path):
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header row.")
            missing = REQUIRED_HEADERS - set(reader.fieldnames)
            if missing:
                raise ValueError(f"CSV missing required headers: {', '.join(sorted(missing))}")
            for row in reader:
                yield row
    except Exception as e:
        print(f"ERROR: Failed to read CSV: {e}", file=sys.stderr)
        sys.exit(2)

def coerce_float(v: str, field: str) -> float:
    try:
        return float(v)
    except Exception:
        raise ValueError(f"Non-numeric value in '{field}': {v!r}")

def round_to_nearest(value: float, step: float) -> float:
    """Round to nearest specified step (e.g., 0.125 or 0.25)."""
    return round(value / step) * step

def find_exact(csv_path: Path, flat_k: float, mrs: float) -> Optional[dict]:
    for row in read_rows(csv_path):
        try:
            rk = coerce_float(row["Flat K"], "Flat K")
            rm = coerce_float(row["MRS"], "MRS")
        except ValueError:
            continue
        if rk == flat_k and rm == mrs:
            return row
    return None

def compute_values(row: dict) -> Tuple[float, float, int]:
    bc_code = int(float(row["BC_Code"]))
    rzd_code = int(float(row["RZD_Code"]))
    lza = int(float(row["LZA"]))
    bc = bc_code / 10.0
    rzd = rzd_code / 1000.0
    return bc, rzd, lza

def main():
    args = parse_args()

    if not CSV_PATH.exists():
        print(f"ERROR: CSV file not found at {CSV_PATH}", file=sys.stderr)
        sys.exit(2)

    # Round to nearest step values
    flat_k_rounded = round_to_nearest(args.flat_k, 0.125)
    mrs_rounded = round_to_nearest(args.mrs, 0.25)

    row = find_exact(CSV_PATH, flat_k_rounded, mrs_rounded)
    if row is None:
        print(f"No match found for Flat K={flat_k_rounded}, MRS={mrs_rounded}", file=sys.stderr)
        sys.exit(1)

    try:
        bc, rzd, lza = compute_values(row)
    except Exception as e:
        print(f"ERROR: Failed to compute values from row: {e}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps({
            "FlatK": flat_k_rounded,
            "MRS": mrs_rounded,
            "BC": bc,
            "RZD": rzd,
            "LZA": lza
        }))
    else:
        print(f"Flat K (rounded): {flat_k_rounded:.3f}")
        print(f"Spherical Error (rounded): {mrs_rounded:.2f}")
        print(f"Base Curve radius (BC): {bc:.3f} mm")
        print(f"Return Zone Depth (RZD): {rzd:.3f} mm")
        print(f"Landing Zone Angle (LZA): {lza}°")

    sys.exit(0)

if __name__ == "__main__":
    main()
