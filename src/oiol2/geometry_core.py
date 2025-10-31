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
import sympy as sp
from typing import List, Tuple

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


# ---- Front curve radius calculations ------------------------------------------

def front_curve_radius_from_vertex_power(
    power_D: float,
    base_curve_radius_mm: float,
    refr_index_lens: float,
    center_thickness_mm: float,
    mode: int,
) -> float:
    """
    Compute the Front Curve Radius (mm) for a lens given vertex power type.

    Args:
        power_D (float): Lens power in diopters.
        base_curve_radius_mm (float): Base (back) curve radius in mm.
        refr_index_lens (float): Refractive index of the lens material.
        center_thickness_mm (float): Center thickness in mm.
        mode (int): 1 = Back Vertex Power, 2 = Front Vertex Power.

    Returns:
        float: Front surface radius in mm.

    Raises:
        ValueError: If mode is not 1 or 2.

    Notes:
        Based on standard thick-lens formulas. RIA (index of air) = 1.0.
    """
    RIA = 1.0  # refractive index of air
    k = 0.001  # mm → m conversion

    BCR = float(base_curve_radius_mm)
    RIM = float(refr_index_lens)
    CT = float(center_thickness_mm)
    PWR = float(power_D)

    # Base curve power (air → lens)
    BCD = (RIA - RIM) / (BCR * k)

    if mode == 1:
        # --- From Back Vertex Power (BVP) ---
        FCD = (RIM * (PWR - BCD)) / (RIM - BCD * CT * k + PWR * CT * k)
    elif mode == 2:
        # --- From Front Vertex Power (FVP) ---
        FCD = PWR - BCD / (1.0 - (CT * k / RIM) * BCD)
    else:
        raise ValueError(f"Invalid mode value: {mode}. Use 1 (BVP) or 2 (FVP).")

    # Convert front curve dioptric power to radius (mm)
    FCR = (RIM - RIA) / (FCD * k)
    return FCR

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
        raise ValueError(
            "Non-real conic sag (discriminant < 0). Reduce y or adjust K/R."
        )
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

def sag_sphere_meridional(
    Rx_mm: float, Ry_mm: float, y_mm: float, theta_rad: float
) -> float:
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

# === Tangent and Slope Calculations ===
def slope_and_angle_of_line_tangent_to_curve(x_val, R_val, K_val):
    """
    Calculate the slope and angle of the line tangent to a conic curve
    at a point defined by x_val.

    The conic is defined as:
        y = x^2 / (R + sqrt(R^2 - (K + 1) * x^2))

    Args:
        x_val (float): The x-coordinate of the point of tangency.
        R_val (float): The radius of curvature at the apex (R0).
        K_val (float): The conic constant.

    Returns:
        tuple:
            slope_of_line (sympy.Float): Slope (dy/dx) at x_val.
            angle_radians (sympy.Float): Tangent line angle in radians.
            angle_degrees (sympy.Float): Tangent line angle in degrees.
    """
    # Define symbols
    x, R, K = sp.symbols("x R K")

    # Define the equation
    y = x**2 / (R + sp.sqrt(R**2 - (K + 1) * x**2))

    # First derivative with respect to x
    y_prime = sp.diff(y, x)

    # Slope of a tangent line at point x_val
    slope_of_line = y_prime.subs({x: x_val, R: R_val, K: K_val})

    # Calculate the angle of the tangent line
    angle_radians = sp.atan(slope_of_line)
    angle_degrees = sp.deg(angle_radians)

    return slope_of_line, angle_radians, angle_degrees

# === Y-intercept for a line ===
def y_intercept(x_val, y_val, m_val):
    # (x_val, y_val): point on the line
    # m_val: slope
    return y_val - m_val * x_val

# === Convert the angle of a line ===
def slope_from_angle(theta_degrees):
    theta_radians = math.radians(theta_degrees)
    return math.tan(theta_radians)

# === Find the intersections of a line with a conic ===
def conic_line_intersections(m, b, R0, K, d, tol=1e-10):
    """
    Solve intersections between
        y = x^2 / (R0 + sqrt(R0^2 - (K+1) x^2)) + d
    and
        y = m x + b
    Returns a sorted list of (x, y).
    """
    a = K + 1.0
    c = b - d

    # Quadratic coefficients: A x^2 + B x + C = 0
    A = a * m * m + 1.0
    B = 2.0 * m * (a * c - R0)
    C = a * c * c - 2.0 * R0 * c

    xs = []

    # Solve quadratic robustly
    disc = B*B - 4*A*C
    if disc > -tol:
        disc = max(disc, 0.0)
        sqrt_disc = math.sqrt(disc)
        x1 = (-B - sqrt_disc) / (2*A)
        x2 = (-B + sqrt_disc) / (2*A)
        xs.extend([x1, x2])

    # Special-case x=0 root is valid only if b == d (within tol)
    if abs(b - d) <= tol:
        xs.append(0.0)

    # Domain filter and de-duplicate
    x_max = R0 / math.sqrt(a)
    uniq = []
    for x in xs:
        # Deduplicate near-equals
        if any(abs(x - u) <= 1e-9 for u in uniq):
            continue
        # Domain: sqrt argument must be >= 0
        if abs(x) - x_max > 1e-12:
            continue
        uniq.append(x)

    # Verify against the original (unsquared) equation to discard artifacts
    pts = []
    for x in uniq:
        sqrt_arg = R0*R0 - a * x*x
        if sqrt_arg < -1e-12:
            continue
        sqrt_term = math.sqrt(max(sqrt_arg, 0.0))
        y_conic = (x*x) / (R0 + sqrt_term) + d
        y_line = m*x + b
        if abs(y_conic - y_line) <= 1e-7:
            pts.append((x, y_conic))

    # Sort by x
    pts.sort(key=lambda p: p[0])
    return pts

# === Distance between two points ===
def distance_between_points(p1, p2):
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

# === Sigmoid curve between two points - Cubic Hermite  ===
Point = Tuple[float, float]  # (x, z)
def sigmoid_segment_with_end_slopes(
    p_start: Point,
    p_end: Point,
    m_slope_start: float,
    m_slope_end: float,
    n: int = 200,
) -> List[Point]:
    """
    Construct a single-inflection (sigmoid-like) 2D curve between two points with specified end slopes.

    The curve is a cubic Hermite segment built in a chord-aligned local coordinate system (LCS),
    then rotated/translated back to the global coordinate system (GCS).

    Coordinate conventions
    ----------------------
    * Points are (x, z).
    * "Slope" is dz/dx in the current frame.

    Inputs
    ------
    p_start : (x, z)
        Starting point of the segment in GCS.
    p_end   : (x, z)
        Ending point of the segment in GCS.
    m_slope_start : float
        Desired slope (dz/dx) at p_start, specified in GCS.
        Use math.inf / -math.inf for a vertical tangent.
    m_slope_end   : float
        Desired slope (dz/dx) at p_end, specified in GCS.
        Use math.inf / -math.inf for a vertical tangent.
    n : int, default 200
        Number of sample points along the curve (inclusive of both endpoints).

    Returns
    -------
    List[Point]
        A list of (x, z) points in GCS sampling the cubic Hermite segment from p_start to p_end.

    Method (high level)
    -------------------
    1) Build an LCS whose +x axis lies along the chord from p_start to p_end:
       P0_L = (0, 0), P1_L = (L, 0), where L = |p_end - p_start|.
    2) Convert the requested GCS end slopes to LCS slopes (angle subtraction).
    3) Use a cubic Hermite y(x) in LCS with y(0)=y(L)=0 and dy/dx at each end set to the LCS slopes.
       With s = x/L ∈ [0,1], y(s) = L * [(s^3 - 2s^2 + s)*m0' + (s^3 - s^2)*m1'].
       This cubic generally has exactly one inflection → a smooth "S" between the endpoints.
    4) Map all (x, y) in LCS back to GCS via rotation + translation.

    Notes
    -----
    * This construction is robust for vertical chords and/or vertical end slopes because slope
      rotation is performed via angles (atan/tan) in the LCS.
    * Endpoints are explicitly snapped to (p_start, p_end) after evaluation to eliminate any
      accumulated round-off at the boundaries.
    * If p_start == p_end, the function returns n copies of p_start.

    """
    x0, z0 = p_start
    x1, z1 = p_end

    dx, dz = x1 - x0, z1 - z0
    L = math.hypot(dx, dz)
    if L == 0.0:
        return [p_start] * max(1, n)

    # Chord angle: rotate GCS by -theta to make the chord horizontal in LCS
    theta = math.atan2(dz, dx)

    # --- Helper: rotate a GCS slope into LCS by subtracting the chord angle ---
    def slope_to_local(m: float, ang: float) -> float:
        """
        Map a GCS slope m to an LCS slope m' by subtracting 'ang' from the slope angle.
        Handles vertical slopes robustly via angle arithmetic.
        """
        # Convert slope to angle
        if math.isinf(m):
            phi = math.pi / 2 if m > 0 else -math.pi / 2
        else:
            phi = math.atan(m)
        # Rotate into local frame
        phi_l = phi - ang
        # If exactly vertical in LCS, keep it vertical
        # (guard tiny round-off near ±pi/2)
        eps = 1e-15
        if abs(abs(phi_l) - math.pi / 2) < eps:
            return math.copysign(math.inf, phi_l)
        return math.tan(phi_l)

    m0_l = slope_to_local(m_slope_start, theta)  # slope at s=0 in LCS
    m1_l = slope_to_local(m_slope_end,   theta)  # slope at s=1 in LCS

    # --- Build cubic Hermite in LCS: x ∈ [0, L], y(x) matches end slopes ---
    pts_lcs: List[Point] = []
    for i in range(n):
        x = L * i / (n - 1)         # along the chord
        s = x / L                   # normalized parameter in [0, 1]
        # With y0 = y1 = 0, the Hermite reduces to derivative terms only:
        # y(s) = L * [(s^3 - 2s^2 + s) * m0_l + (s^3 - s^2) * m1_l]
        s2 = s * s
        s3 = s2 * s
        y = L * ((s3 - 2*s2 + s) * m0_l + (s3 - s2) * m1_l)
        pts_lcs.append((x, y))

    # --- Map LCS → GCS by rotating + translating back by +theta about p_start ---
    c, s = math.cos(theta), math.sin(theta)
    pts_gcs: List[Point] = []
    for x, y in pts_lcs:
        X =  c * x - s * y + x0
        Z =  s * x + c * y + z0
        pts_gcs.append((X, Z))

    # Snap endpoints exactly to the requested endpoints (eliminate boundary round-off)
    pts_gcs[0]  = p_start
    pts_gcs[-1] = p_end

    return pts_gcs

def point_along_line(slope, y_intercept, distance, x_direction, x_start):
    """
    Computes the x, y values for a point along a line given the slope, y-intercept,
    distance, x direction to move, and starting x value.

    Args:
        slope (float): Slope of the line.
        y_intercept (float): Y-intercept of the line.
        distance (float): Distance to move along the line.
        x_direction (int): Direction to move (1 for positive x, -1 for negative x).
        x_start (float): Starting x value on the line.

    Returns:
        float: The x value of the point after moving the specified distance.
        float: The y value of the point after moving the specified distance.
    """
    # Calculate the change in x based on the distance and direction
    delta_x = distance / math.sqrt(1 + slope**2) * x_direction

    # Calculate the new x and y values
    x_new = x_start + delta_x
    y_new = slope * x_new + y_intercept

    return (x_new, y_new)