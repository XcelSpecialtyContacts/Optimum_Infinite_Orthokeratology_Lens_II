# src/oiol2/geometry/meridional.py
from __future__ import annotations
import re
import math
from math import hypot
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple

from oiol2.geometry_core import (
    slope_and_angle_of_line_tangent_to_curve,
    y_intercept,
    front_curve_radius_from_vertex_power,
    conic_line_intersections,
    distance_between_points,
)

@dataclass
class JTResult:
    ct: float           # final center thickness (mm)
    fcr: float          # final front curve radius (mm)
    jt1: float          # junction thickness at optic-zone edge (mm)
    iterations: int     # how many CT steps used
    converged: bool     # True if jt >= jt_min
    note: str = ""      # optional reason if not converged

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

import numpy as np

def generate_front_optic_zone_meridional(
    x_start: float,
    x_end: float,
    center_thickness: float,
    front_curve_radius: float,
    front_above_base: bool = False,
    num_points: int = 201,
) -> np.ndarray:
    """
    Front-surface meridional line for the optic/treatment zone.

    Geometry:
        - Spherical surface (K = 0) with radius = front_curve_radius.
        - Apex is vertically shifted by CT (center_thickness).
        - Coordinate system matches the back-surface function: (x, z),
          where z is sag from the *back-surface* vertex at (0, 0).
        - Thus front-surface sag is:
              z_front(x) = CT + (R_f - sqrt(R_f^2 - x^2))
          where R_f = front_curve_radius.

    Args:
        x_start (float): starting x (mm) for the front optic zone profile.
        x_end (float): ending x (mm) for the front optic zone profile.
        center_thickness (float): CT at x=0 (mm).
        front_curve_radius (float): front curve radius R_f (mm).
        num_points (int): number of points to generate (default 201).

    Returns:
        np.ndarray of shape (N, 2): columns are (x, z), with z in mm.

    Notes:
        - Domain guard: requires |x| <= R_f so that sqrt(R_f^2 - x^2) is real.
          If x_end > R_f, it is clamped to (R_f - 1e-6) to avoid domain errors.
          Adjust to raising an error if you prefer strict validation.
    """
    Rf = float(front_curve_radius)
    CT = float(center_thickness)

    # Ensure increasing range
    if x_end < x_start:
        x_start, x_end = x_end, x_start

    # Domain guard for sphere: |x| <= Rf
    # Mirror the back-surface helper behavior by clamping just under Rf.
    max_x_allowed = max(0.0, Rf - 1e-6)
    if x_end > Rf:
        x_end = max(0.0, min(x_end, max_x_allowed))

    x = np.linspace(float(x_start), float(x_end), int(num_points))

    # Spherical sag relative to *front apex* is (Rf - sqrt(Rf^2 - x^2)).
    # Shift everything up by CT so apex is at z = CT.
    sqrt_arg = Rf * Rf - x * x
    # Numerical safety: any tiny negatives from rounding go to zero
    sqrt_arg = np.clip(sqrt_arg, 0.0, None)
    if front_above_base:
        z_front = -CT - (Rf - np.sqrt(sqrt_arg))
    else:
        z_front = -CT + (Rf - np.sqrt(sqrt_arg))

    return np.column_stack((x, z_front))

def generate_line_path(
    x_start: float,
    x_end: float,
    m: float,
    b: float,
    num_points: int = 201,
) -> np.ndarray:
    """
    Creates an array of points that represents the junction points in a lens

    Args:
        x_start (float): starting x (mm) for the profile.
        x_end (float): ending x (mm) for the profile.
        m: slope of the line the path transverses.
        b: y-intercept of the line the path transverses.
        num_points (int): number of points to generate (default 201).

    Returns:
        np.ndarray of shape (N, 2): columns are (x, z), with z in mm.
    """
    x = np.linspace(float(x_start), float(x_end), int(num_points))

    y = m * x + b

    return np.column_stack((x, y))

def _back_surface_y_at_x(x: float, R0: float, K: float) -> float:
    """Back/base surface conic sag from vertex: y = x^2 / (R0 + sqrt(R0^2 - (K+1)x^2))."""
    a = K + 1.0
    sqrt_arg = R0 * R0 - a * x * x
    if sqrt_arg < 0:
        raise ValueError(f"Invalid x={x}: sqrt_arg={sqrt_arg} < 0 for R0={R0}, K={K}")
    return (x * x) / (R0 + math.sqrt(sqrt_arg))

def edge_normal_line_at_back_surface(x_edge: float, R0: float, K: float) -> Tuple[float, float, float, float]:
    """
    Compute the normal line at the back-surface edge (x_edge).
    Returns (x_edge, y_edge, m_normal, b_normal).
    """
    y_edge = _back_surface_y_at_x(x_edge, R0, K)
    m_tan, _, _ = slope_and_angle_of_line_tangent_to_curve(x_edge, R0, K)
    m_tan = float(m_tan)

    # Handle near-horizontal tangent => vertical normal (not expected for your sphere case)
    if abs(m_tan) < 1e-15:
        raise RuntimeError("Vertical normal encountered; unsupported in this workflow.")
    m_norm = -1.0 / m_tan
    b_norm = y_intercept(x_edge, y_edge, m_norm)
    return x_edge, y_edge, m_norm, b_norm

def _jt_for_given_ct(
    *,
    power_D: float,
    R0_back: float,
    K_back: float,
    index_ri: float,
    ct_mm: float,
    vertex_mm: float,
    x_edge: float,
    front_above_base: bool = False,
) -> Tuple[float, float]:
    """
    Compute (JT_mm, FCR_mm) for a given CT.
    Front optic/treatment zone is spherical (K=0) and shifted by d = CT.

    front_above_base:
        True  -> z_front apex at +CT, points on the same-sag side:  z = CT + (Rf - sqrt(...))
        False -> z_front apex at +CT, but choose the intersection on the opposite side
                 (useful if your z axis increases posteriorly and the front must be "below" the base).
    """
    # 1) front curve radius from power (sanitize sign for sag geometry)
    Rf = abs(front_curve_radius_from_vertex_power(power_D, R0_back, index_ri, ct_mm, vertex_mm))

    # 2) normal at the back-surface edge
    x_e, y_e, m_norm, b_norm = edge_normal_line_at_back_surface(x_edge, R0_back, K_back)

    # 3) choose vertical shift sign for the front surface apex
    d = ct_mm if front_above_base else -ct_mm

    # 4) Intersections with front surface (sphere, K=0) shifted by d=CT
    pts = conic_line_intersections(m_norm, b_norm, Rf, 0.0, d)
    if not pts:
        raise RuntimeError("No intersection found between the normal and front surface.")

    # PICK THE CORRECT SIDE:
    # If we consider "front above base" in our original convention, its apex is at y=CT (> y_e when x=0),
    # so at the edge we want the intersection whose y is >= y_e (same side as +CT).
    # If front_above_base is False, pick the one with y <= y_e.
    if front_above_base:
        candidates = [p for p in pts if p[1] >= y_e - 1e-12]
        if not candidates:
            # Fallback to nearest if numeric noise filtered them out
            candidates = pts
    else:
        candidates = [p for p in pts if p[1] <= y_e + 1e-12]
        if not candidates:
            candidates = pts

    # From the candidates on the intended side, choose nearest to the edge
    p1 = (x_e, y_e)
    p2 = min(candidates, key=lambda q: distance_between_points(p1, q))
    jt_mm = distance_between_points(p1, p2)
    return jt_mm, Rf


def find_ct_fcr_jt_to_meet_jt_min(
    *,
    power_D: float,
    R0_back: float,
    K_back: float,
    index_ri: float,
    ct_init_mm: float,
    vertex_mm: float,
    x_edge: float,
    jt_min_mm: float,
    ct_min_mm: Optional[float] = None,
    ct_max_mm: Optional[float] = None,
    step_mm: float = 0.001,
    max_iter: int = 5000,
    front_above_base: bool = False,
) -> JTResult:
    """
    Increment CT in step_mm until JT >= jt_min_mm (or limits/iterations reached).
    """
    if ct_min_mm is None:
        ct_min_mm = 0.0
    if ct_max_mm is None:
        ct_max_mm = 1.0

    ct = float(ct_init_mm)
    if ct < ct_min_mm:
        ct = ct_min_mm

    iterations = 0
    last_jt = float("nan")
    last_fcr = float("nan")

    while iterations < max_iter:
        iterations += 1
        jt_mm, fcr_mm = _jt_for_given_ct(
            power_D=power_D,
            R0_back=R0_back,
            K_back=K_back,
            index_ri=index_ri,
            ct_mm=ct,
            vertex_mm=vertex_mm,
            x_edge=x_edge,
            front_above_base=front_above_base,
        )
        last_jt, last_fcr = jt_mm, fcr_mm

        if jt_mm >= jt_min_mm - 1e-9:
            return JTResult(ct=ct, fcr=fcr_mm, jt1=jt_mm, iterations=iterations, converged=True)

        ct += step_mm
        if ct > ct_max_mm + 1e-12:
            return JTResult(ct=ct, fcr=fcr_mm, jt1=jt_mm, iterations=iterations,
                            converged=False, note="CT exceeded maximum allowed while searching.")

    return JTResult(ct=ct, fcr=last_fcr, jt1=last_jt, iterations=iterations,
                    converged=False, note="Max iterations reached before meeting JT minimum.")

def calc_bs_edge_data(x: float, m: float, b: float, r: float) -> Tuple[Tuple[float, float],
                                                                       Tuple[float, float],
                                                                       Tuple[float, float]]:
    """
    This is for computing the point of tangency for the base surface peripheral edge curve
    and the edge radius, the point that represents the lens diameter, and the center of the
    edge radius.
    Compute the center and tangency points of a circle of radius r that is tangent to:
      1) the vertical line x = x (given), and
      2) the slanted line EL: y = m*x + b,
    specifically for the **lower-left** wedge formed by these two lines.

    Returns
    -------
    center : (h, k)
    t_el   : (x_el, y_el)  # tangency point on EL
    t_vert : (x, k)        # tangency point on the vertical line
    """
    if r <= 0:
        raise ValueError("Circle radius r must be > 0.")
    if not math.isfinite(m):
        raise ValueError("Slope m must be finite (EL cannot be vertical here).")

    # Circle center: intersection of (x = x - r) and the r-downward offset of EL
    h = x - r
    k = m * (x - r) + b - r * math.hypot(m, 1.0)  # sqrt(m^2 + 1)

    # Tangency on the vertical line
    t_vert = (x, k)

    # Tangency on EL: orthogonal projection of (h,k) onto m*x - y + b = 0
    denom = m * m + 1.0
    delta = (m * h - k + b) / denom
    x_el = h - m * delta
    y_el = k + delta
    t_el = (x_el, y_el)

    center = (h, k)
    return center, t_el, t_vert

def tangent_circle_below_with_points(
    m1: float, b1: float, m2: float, b2: float, r: float
) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    """
    For lines y = m1*x + b1 and y = m2*x + b2 that intersect in Q1,
    find the center (h, k) of the circle of radius r tangent to both,
    choosing the solution where the center lies BELOW both lines.
    Also return the tangent points on each line.

    Returns:
        (h, k), (t1x, t1y), (t2x, t2y)
        where (t1x, t1y) is the tangent point on line 1,
              (t2x, t2y) is the tangent point on line 2.

    Raises:
        ValueError: if lines are (nearly) parallel or r < 0.
    """
    if r < 0:
        raise ValueError("Radius must be nonnegative.")

    s1 = hypot(m1, 1.0)  # sqrt(m1^2 + 1)
    s2 = hypot(m2, 1.0)

    denom = (m1 - m2)
    if abs(denom) < 1e-15:
        raise ValueError("Lines are (nearly) parallel; no unique solution.")

    # Intersection of the two "offset-down" parallels (center is below both):
    # k = m1*h + b1 - r*s1
    # k = m2*h + b2 - r*s2
    h = ((b2 - b1) + r * (s1 - s2)) / denom
    k = m1 * h + b1 - r * s1

    # Tangent point formula (for "below" configuration):
    # Line as ax + by + c = 0 with a=m, b=-1, c=b
    # Unit normal n̂ = (m, -1)/sqrt(m^2+1); signed distance d = r (>0)
    # Tangent point T = (h, k) - d * n̂
    t1x = h - r * (m1 / s1)
    t1y = k + r * (1.0 / s1)

    t2x = h - r * (m2 / s2)
    t2y = k + r * (1.0 / s2)

    p1, p2 = (t1x, t1y), (t2x, t2y)
    p_sorted = sorted([p1, p2], key=lambda p: p[0])

    center = (h, k)

    return center, p_sorted[0], p_sorted[1]

import numpy as np
from typing import Tuple, List

def generate_upper_semi_circle_path(
    r: float,
    center_point: Tuple[float, float],
    x_start: float,
    x_end: float,
    number_of_points: int
) -> List[Tuple[float, float]]:
    """
    Generate (x, y) points along the **upper** semicircle between x_start and x_end.

    Args:
        r (float): Radius of the circle.
        center_point (tuple): (h, k) coordinates of the circle center.
        x_start (float): Starting x position along the circle.
        x_end (float): Ending x position along the circle.
        number_of_points (int): Number of points to generate.

    Returns:
        list[tuple[float, float]]: List of (x, y) coordinates along the upper semicircle.
    """
    if number_of_points < 2:
        raise ValueError("number_of_points must be at least 2")
    if abs(x_start - center_point[0]) > r or abs(x_end - center_point[0]) > r:
        raise ValueError("x_start and x_end must be within the circle bounds (center_x ± r)")

    h, k = center_point

    # Linearly spaced x values between x_start and x_end
    x_vals = np.linspace(x_start, x_end, number_of_points)

    # Equation of circle: (x - h)^2 + (y - k)^2 = r^2
    # Upper semicircle => y = k + sqrt(r^2 - (x - h)^2)
    y_vals = k + np.sqrt(np.maximum(0.0, r**2 - (x_vals - h)**2))

    return list(zip(x_vals.tolist(), y_vals.tolist()))
