# src/oiol2/geometry/meridional.py
from __future__ import annotations
import re
import math
import numpy as np

_number_re = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")

def _to_float(v) -> float:
    """
    Coerce Lab File values to float.
    Accepts:
      - float/int
      - strings like '8.70', '+0.75', '  10.5 mm', etc.
      - dicts like {'value': '8.70'} or {'value': 8.70}
    Raises ValueError if no numeric content is found.
    """
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict) and "value" in v:
        return _to_float(v["value"])
    s = str(v).strip()
    m = _number_re.search(s)
    if not m:
        raise ValueError(f"Cannot parse numeric value from: {v!r}")
    return float(m.group(0))

def generate_optic_zone_meridional(lab_data: dict, num_points: int = 201) -> np.ndarray:
    """
    Base-surface meridional line for the optic/treatment zone.
    Sphere centered at (0, BC) with radius = BC.
    x spans from 0 to (BCOZDia / 2).

    Returns:
        np.ndarray of shape (N, 2): columns are (x, z), with z = spherical sag.
    """
    # BC (radius) and Optic Zone Diameter (prefer BCOZDia; fallback OpticZoneDia; default 6.0mm)
    R = _to_float(lab_data["BC"])
    oz_dia = None
    if "BCOZDia" in lab_data:
        oz_dia = _to_float(lab_data["BCOZDia"])
    elif "OpticZoneDia" in lab_data:
        oz_dia = _to_float(lab_data["OpticZoneDia"])
    else:
        oz_dia = 6.0
    x_end = oz_dia / 2.0

    # Guard: for a pure sphere, x_end must be <= R (else sqrt goes negative).
    if x_end > R:
        # Clamp just under R to avoid domain issues; you can choose to raise instead if preferred.
        x_end = max(0.0, R - 1e-6)

    x = np.linspace(0.0, x_end, num_points)

    # Spherical sag from vertex (vertex at z=0 when x=0):
    # z = R - sqrt(R^2 - x^2)
    # This already corresponds to a sphere centered at (0, R) in (x,z).
    z = R - np.sqrt(R * R - x * x)

    return np.column_stack((x, z))
