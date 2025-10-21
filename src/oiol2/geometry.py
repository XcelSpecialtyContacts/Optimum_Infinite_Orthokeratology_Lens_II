"""
oiol2.geometry
==============
Core geometric & optical primitives for Optimum Infinite Orthokeratology Lens II.

Conventions
-----------
- Distances: millimeters (mm) unless stated otherwise.
- Powers: diopters (D).
- Angles: radians in the API; helpers provided for degrees.
- Refractive indices: unitless (e.g., 1.3375).

This module intentionally avoids global state. All functions are pure and typed.
Where helpful, numerically stable forms are used (e.g., sag calculations).

If you are porting from legacy `geometryfunctions02.py`, see the bottom
of this file for a sample "compat shim" pattern you can extend to keep
old call sites working while you migrate.

Author: oiol2 team
"""

from __future__ import annotations

import math
from typing import Iterable, Tuple

# ---- Constants ----------------------------------------------------------------

MM_PER_M: float = 1000.0
DEG2RAD: float = math.pi / 180.0
RAD2DEG: float = 180.0 / math.pi

# ---- Utilities ----------------------------------------------------------------

def _safe_sqrt(x: float) -> float:
    """Sqrt that treats tiny negative noise as zero."""
    if x < 0 and x > -1e-12:
        return 0.0
    if x < 0:
        raise ValueError(f"sqrt of negative: {x}")
    return math.sqrt(x)

# ---- Optics: power <-> radius --------------------------------------------------

def radius_to_surface_power(n_medium: float, n_lens: float, radius_mm: float) -> float:
    """
    Surface power F (diopters) for a single refracting surface from medium->lens.

    F = (n_lens - n_medium) / R_meters

    Args:
        n_medium: index before surface (air ~ 1.000)
        n_lens: index after surface  (e.g., 1.3375)
        radius_mm: algebraic radius in mm (positive for convex surface
                   seeing incoming light; follow your sign convention)

    Returns:
        Surface power in diopters.
    """
    if radius_mm == 0:
        raise ValueError("radius_mm must be non-zero")
    R_m = radius_mm / MM_PER_M
    return (n_lens - n_medium) / R_m


def surface_power_to_radius(n_medium: float, n_lens: float, power_D: float) -> float:
    """
    Inverse of radius_to_surface_power: radius from surface power.

    R_m = (n_lens - n_medium) / F  =>  R_mm = 1000 * (n_lens - n_medium)/F
    """
    if power_D == 0:
        raise ValueError("power_D must be non-zero")
    return MM_PER_M * (n_lens - n_medium) / power_D

# ---- Geometry: sags ------------------------------------------------------------

def sag_sphere(radius_mm: float, y_mm: float) -> float:
    """
    Sag of a spherical surface of radius R at semi-chord y.

    s = R - sqrt(R^2 - y^2)

    Numerically stable for small y.
    """
    R = float(radius_mm)
    y = abs(float(y_mm))
    if y > abs(R):
        raise ValueError("y_mm must satisfy |y| <= |radius| for real spherical sag.")
    return R - _safe_sqrt(R * R - y * y)


def sag_conic(R_mm: float, K: float, y_mm: float) -> float:
    """
    Conic sag with radius R and conic constant K at semi-chord y.

    Standard form:
        s = (y^2) / ( R * (1 + sqrt(1 - (1+K) * (y^2/R^2))) )

    Reduces to sphere when K = 0.
    """
    R = float(R_mm)
    y = abs(float(y_mm))
    if R == 0:
        raise ValueError("R_mm must be non-zero")

    t = (y * y) / (R * R)
    disc = 1.0 - (1.0 + K) * t
    if disc < -1e-12:
        raise ValueError("Non-real conic sag (discriminant < 0). Reduce y or adjust K/R.")
    denom = R * (1.0 + _safe_sqrt(max(0.0, disc)))
    if denom == 0.0:
        # Extremely edge case; fallback to spherical limit
        return sag_sphere(R, y)
    return (y * y) / denom


def sag_difference_conic_vs_sphere(R_mm: float, K: float, y_mm: float) -> float:
    """Convenience: Δs = s_conic - s_sphere at same R, y."""
    return sag_conic(R_mm, K, y_mm) - sag_sphere(R_mm, y_mm)

# ---- Curvature, vertex relationships ------------------------------------------

def curvature_from_radius(radius_mm: float) -> float:
    """Curvature c = 1/R (1/mm)."""
    if radius_mm == 0:
        raise ValueError("radius_mm must be non-zero")
    return 1.0 / radius_mm


def radius_from_curvature(curvature_per_mm: float) -> float:
    """Radius R = 1/c (mm)."""
    if curvature_per_mm == 0:
        raise ValueError("curvature_per_mm must be non-zero")
    return 1.0 / curvature_per_mm

# ---- Angle helpers -------------------------------------------------------------

def deg_to_rad(deg: float) -> float:
    return float(deg) * DEG2RAD


def rad_to_deg(rad: float) -> float:
    return float(rad) * RAD2DEG

# ---- Toric / meridional helpers (simple forms) --------------------------------

def sag_sphere_meridional(Rx_mm: float, Ry_mm: float, y_mm: float, theta_rad: float) -> float:
    """
    Sag on an orthogonal bi-spherical surface at angle theta where local radius is:
        R(theta) = 1 / (cos^2(theta)/Rx + sin^2(theta)/Ry)
    Then sag = R(theta) - sqrt(R(theta)^2 - y^2)
    """
    ctheta = math.cos(theta_rad)
    stheta = math.sin(theta_rad)
    denom = (ctheta * ctheta) / Rx_mm + (stheta * stheta) / Ry_mm
    if denom == 0:
        raise ValueError("Invalid meridional radii for given theta.")
    Rtheta = 1.0 / denom
    return sag_sphere(Rtheta, y_mm)

# ---- (Optional) Legacy compatibility shim -------------------------------------
# If legacy `geometryfunctions02.py` had names like: Sag(), ConicSag(), Curv(), etc.,
# you can add aliases here to avoid breaking existing call sites while you migrate.
#
# Example (uncomment/edit as needed):
#
# Sag = sag_sphere
# ConicSag = sag_conic
# Curv = curvature_from_radius
# RadiusFromCurv = radius_from_curvature
# PowerFromRadius = lambda n, R: radius_to_surface_power(1.0, n, R)  # air->lens
# RadiusFromPower = lambda n, F: surface_power_to_radius(1.0, n, F)
#
# Keep these temporarily and remove once codebase is fully updated.
