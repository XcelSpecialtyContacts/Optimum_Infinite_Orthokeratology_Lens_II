# main.py
from __future__ import annotations
import argparse
import logging
import sys
import re
from pathlib import Path

from labfile_parser import load_config, load_lab_data

# Try to import your geometry module (filename you mentioned)
try:
    import geometryfunctions02 as gfn
except ModuleNotFoundError:
    # Fallback if the file happens to be named geometryfunctions2.py
    import geometryfunctions2 as gfn  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Verify Lab File parsing and compute Front Curve Radius (FCR)."
    )
    p.add_argument("--config", "-c", default="config.toml", help="Path to config.toml")
    p.add_argument("--wo", required=True, help="Work order number, e.g., 9359766")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def setup_logging(verbose: bool) -> None:
    lvl = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=lvl, format="%(asctime)s %(levelname)-7s %(message)s")


_num_rx = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def to_float(val: str | float | int, default: float | None = None) -> float:
    """
    Robust float parser for lab values that might include units or stray chars.
    Examples: '8.60', '+8.60', '-3.00D', '1.423 (wet)'
    """
    if isinstance(val, (float, int)):
        return float(val)
    if not isinstance(val, str):
        if default is None:
            raise ValueError(f"Cannot parse non-string value: {val!r}")
        return default
    m = _num_rx.search(val.replace(",", "."))
    if not m:
        if default is None:
            raise ValueError(f"Could not parse numeric value from: {val!r}")
        return default
    return float(m.group(0))


def compute_fcr(lab: dict) -> tuple[float, str]:
    """
    Computes Front Curve Radius (mm) using geometryfunctions02.py.
    Decision:
      - If Vertex_Code == 1: use FCRFromBVP(BVP, BCR, RIM, CT)
      - If Vertex_Code == 2: use FCRFromFVP(FVP, BCR, RIM, CT)
    Returns: (FCR_mm, method_str)
    """
    # Pull values from parsed lab dict
    bc_s = lab.get("BC", {}).get("value", "")
    pwr_s = lab.get("Power", {}).get("value", "")
    ct_s = lab.get("Min_CT", {}).get("value", "") or lab.get("CT_min", {}).get(
        "value", ""
    )
    ri_s = lab.get("Mat_RI", {}).get("value", "")
    vcode = lab.get("Vertex_Code", {}).get("value", "")

    # Convert to numbers
    BCR = to_float(bc_s)
    CT = to_float(ct_s, default=0.0)  # mm
    RIM = to_float(ri_s)  # refractive index (unitless)

    # Decide which vertex convention we’re using
    try:
        vcode_int = int(to_float(vcode))
    except Exception:
        raise ValueError(
            f"Vertex_Code is missing or invalid: {vcode!r} (expected 1 or 2)"
        )

    if vcode_int == 1:
        # Power is Back Vertex Power (BVP)
        BVP = to_float(pwr_s)
        FCR = gfn.FCRFromBVP(BVP, BCR, RIM, CT)
        return FCR, "FCRFromBVP (Vertex_Code=1)"
    elif vcode_int == 2:
        # Power is Front Vertex Power (FVP)
        FVP = to_float(pwr_s)
        FCR = gfn.FCRFromFVP(FVP, BCR, RIM, CT)
        return FCR, "FCRFromFVP (Vertex_Code=2)"
    else:
        raise ValueError(f"Unsupported Vertex_Code={vcode_int} (expected 1 or 2)")


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    cfg = load_config(args.config)
    lab_data = load_lab_data(cfg, args.wo)

    print("\n=== LAB FILE PARSE RESULT ===")
    print(f"Work Order: {args.wo}\n")
    print(
        f"Lab File Path: {Path(cfg['paths']['labfile_root']) / (cfg['labfile']['prefix'] + str(args.wo))}\n"
    )
    print("Extracted Parameters:")
    print("----------------------")

    if not lab_data:
        print("No data found or unable to parse Lab File.")
        return 1

    for key, entry in lab_data.items():
        title = entry.get("title", key)
        value = entry.get("value", "")
        seg = entry.get("seg", "")
        print(f"{title:<25} (Seg {seg}) : {value}")

    # Compute Front Curve Radius
    print("\nComputed Values:")
    print("----------------")
    try:
        fcr_mm, method = compute_fcr(lab_data)
        print(f"Front Curve Radius (mm): {fcr_mm:.5f}   [{method}]")
    except Exception as e:
        print(f"Front Curve Radius (mm): ERROR -> {e}")

    print("\n==============================\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.exception("Fatal error")
        sys.exit(1)
