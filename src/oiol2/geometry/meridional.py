# src/oiol2/geometry/meridional.py
from __future__ import annotations
import re
import math
from math import hypot, sqrt, isclose, inf
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, Iterable, List, Sequence, Union
from bisect import bisect_left, bisect_right

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
    if lab_data['BC_actual']['value'] != "": # BC radius
        R = _to_float(lab_data["BC_actual"])
    else:
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

def generate_lower_semi_circle_path(
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
    y_vals = k - np.sqrt(np.maximum(0.0, r**2 - (x_vals - h)**2))

    return list(zip(x_vals.tolist(), y_vals.tolist()))

def tangent_line_from_external_point(center, r, point, prefer="smallest"):
    """
    Compute the line(s) through an external point that are tangent to a circle.

    Args:
        center: (h, k) center of the circle
        r:      circle radius (>0)
        point:  (xi, yi) external point (must be strictly outside the circle)
        prefer: "smallest" (default), "largest", or "both"
                - "smallest": return the tangent with the numerically smallest slope
                - "largest" : return the tangent with the numerically largest slope
                - "both"    : return both tangents as [(m1, b1, (tx1, ty1)), (m2, b2, (tx2, ty2))]

    Returns:
        If prefer != "both":
            (m, b, (tx, ty))
            - m: slope (float) or None if vertical
            - b: y-intercept (float) or None if vertical (line is x = constant)
            - (tx, ty): tangent point on the circle
        If prefer == "both":
            list of two tuples as above (order not guaranteed)

    Notes:
        - If the chosen tangent is vertical, returns m=None, b=None (line is x=xi).
        - For selection by "smallest"/"largest", vertical slopes are treated as +inf.
    """
    (h, k) = center
    (xi, yi) = point

    # Vector from center to external point
    ux = xi - h
    uy = yi - k
    d2 = ux*ux + uy*uy
    if d2 <= r*r:
        raise ValueError("Point is on or inside the circle; real tangents do not exist.")

    d = sqrt(d2)

    # Build the two tangent points using an orthogonal decomposition:
    # T = C + a * u  ±  b * R90(u), where
    #   u = P - C, R90(u) = (-uy, ux),
    #   a = r^2 / d^2,  b = r*sqrt(d^2 - r^2) / d^2
    a = (r*r) / d2
    b = (r * sqrt(d2 - r*r)) / d2

    # R90(u)
    r90x, r90y = -uy, ux

    # Two candidate tangent points on the circle
    t1x = h + a*ux + b*r90x
    t1y = k + a*uy + b*r90y
    t2x = h + a*ux - b*r90x
    t2y = k + a*uy - b*r90y

    # For each tangent point, compute slope/intercept of line through P and T
    def line_from_points(px, py, qx, qy, eps=1e-14):
        dx = qx - px
        dy = qy - py
        if isclose(dx, 0.0, abs_tol=eps):
            # vertical line: x = const
            return None, None  # m, b undefined; caller can infer x = px
        m = dy / dx
        b = py - m*px
        return m, b

    cand = []
    for (tx, ty) in [(t1x, t1y), (t2x, t2y)]:
        m, b_int = line_from_points(xi, yi, tx, ty)
        # For ordering, treat vertical as +inf slope
        order_key = abs(m) if m is not None else inf
        cand.append((order_key, m, b_int, (tx, ty)))

    if prefer == "both":
        # Return both tangents (drop the ordering key)
        return [(m, b_int, tpt) for (_, m, b_int, tpt) in cand]

    # Choose by slope magnitude ordering; "smallest" or "largest"
    if prefer == "largest":
        chosen = max(cand, key=lambda t: t[0])
    else:  # "smallest"
        chosen = min(cand, key=lambda t: t[0])

    _, m, b_int, tpt = chosen
    return (m, b_int, tpt)

Point = Tuple[float, float]
PointsLike = Union[List[Point], np.ndarray]
PointsLike2 = Union[Sequence[Point], np.ndarray]

def _interp(p0: Point, p1: Point, x: float) -> float:
    """Linear interpolation of y at x between two points p0, p1 with distinct x."""
    (x0, y0), (x1, y1) = p0, p1
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)

def trim_curve_by_x(
    points: Sequence[Point],
    x_start: Optional[float] = None,
    x_end: Optional[float] = None,
    *,
    require_strict_x_increase: bool = True
) -> List[Point]:
    """
    Trim a 2D curve (list of (x, y) points) to the closed interval [x_start, x_end].
    - If x_start is None, use the first x in `points`.
    - If x_end is None, use the last x in `points`.
    - If x_start/x_end aren’t exact vertices, the corresponding y is linearly interpolated.
    - Assumes the x values are monotonic increasing (strict by default).

    Returns a new list beginning at x_start and ending at x_end (inclusive).

    Raises:
      ValueError for invalid inputs (range, monotonicity, etc.).
    """
    if len(points) < 2:
        raise ValueError("Need at least two points.")

    xs = [p[0] for p in points]

    # Monotonicity check
    for i in range(1, len(xs)):
        if require_strict_x_increase:
            if not (xs[i] > xs[i-1]):
                raise ValueError("x values must be strictly increasing.")
        else:
            if not (xs[i] >= xs[i-1]):
                raise ValueError("x values must be non-decreasing.")

    # Default bounds if omitted
    if x_start is None:
        x_start = xs[0]
    if x_end is None:
        x_end = xs[-1]

    if x_start > x_end:
        raise ValueError("x_start must be <= x_end.")
    if x_start < xs[0] or x_end > xs[-1]:
        raise ValueError("x_start/x_end must lie within the input x-range.")

    def y_at(x: float) -> float:
        j = bisect_left(xs, x)
        if j < len(xs) and xs[j] == x:
            return points[j][1]
        i0 = j - 1
        i1 = j
        return _interp(points[i0], points[i1], x)

    y_s = y_at(x_start)
    y_e = y_at(x_end)

    trimmed: List[Point] = [(x_start, y_s)]

    left = bisect_right(xs, x_start)   # first index with x > x_start
    right = bisect_left(xs, x_end)     # first index with x >= x_end
    for i in range(left, right):
        trimmed.append(points[i])

    if trimmed[-1][0] != x_end:
        trimmed.append((x_end, y_e))

    return trimmed

def concat_point_lists(points1: PointsLike, points2: PointsLike) -> np.ndarray:
    """
    Concatenate two sequences of (x, y) points (lists or numpy arrays).

    - Accepts either Python lists of tuples or numpy arrays of shape (N, 2).
    - If the last point of points1 equals the first point of points2,
      that duplicate is omitted.
    - Returns a numpy array of shape (M, 2).

    Example:
        >>> concat_point_lists([(0,0), (1,1)], [(1,1), (2,2)])
        array([[0., 0.],
               [1., 1.],
               [2., 2.]])
    """
    # Convert to numpy arrays
    arr1 = np.asarray(points1, dtype=float).reshape(-1, 2)
    arr2 = np.asarray(points2, dtype=float).reshape(-1, 2)

    # Handle empty inputs safely
    if arr1.size == 0:
        return arr2.copy()
    if arr2.size == 0:
        return arr1.copy()

    # Check for duplicate join point
    if np.allclose(arr1[-1], arr2[0]):
        return np.vstack((arr1, arr2[1:]))
    else:
        return np.vstack((arr1, arr2))

def reverse_points(points: PointsLike) -> PointsLike:
    """
    Reverse the order of a list or numpy array of (x, y) points.

    Accepts:
        - list of (x, y) tuples
        - numpy array of shape (N, 2)

    Returns:
        A new object of the same type with reversed order.

    Example:
        >>> reverse_points([(0,0), (1,1), (2,2)])
        [(2.0, 2.0), (1.0, 1.0), (0.0, 0.0)]

        >>> reverse_points(np.array([[0,0],[1,1],[2,2]]))
        array([[2., 2.],
               [1., 1.],
               [0., 0.]])
    """
    if isinstance(points, np.ndarray):
        # Reverse rows along the first axis
        return points[::-1].copy()
    else:
        # Assume sequence of tuples/lists
        return list(reversed(points))

def curve_length(points: PointsLike2) -> float:
    """
    Compute the total length of a 2D polyline defined by (x, y) points.
    Accepts: list/tuple of points or a NumPy array of shape (N, 2).
    Returns 0.0 for fewer than 2 points.
    """
    arr = np.asarray(points, dtype=float)
    if arr.size == 0:
        return 0.0
    arr = arr.reshape(-1, 2)
    if arr.shape[0] < 2:
        return 0.0

    diffs = np.diff(arr, axis=0)
    seglens = np.hypot(diffs[:, 0], diffs[:, 1])  # sqrt(dx^2 + dy^2)
    return float(seglens.sum())

def adaptive_curve_length(
    points: PointsLike2,
    tol: float = 1e-6,
    max_iter: int = 8
) -> float:
    """
    Refines the polyline by inserting midpoints iteratively until
    the total length converges within `tol` or `max_iter` is reached.
    Useful for curves with high curvature (e.g., spirals).

    Returns a scalar length.
    """
    arr = np.asarray(points, dtype=float).reshape(-1, 2)
    if arr.shape[0] < 2:
        return 0.0

    prev_len = curve_length(arr)
    for _ in range(max_iter):
        # Insert midpoints between every consecutive pair
        mids = (arr[:-1] + arr[1:]) / 2.0
        arr = np.column_stack([arr[:-1].ravel(), mids.ravel()]).reshape(-1, 2)
        arr = np.vstack((arr, points[-1]))  # append original last point

        new_len = curve_length(arr)
        if abs(new_len - prev_len) <= tol:
            return float(new_len)
        prev_len = new_len

    return float(prev_len)

def resample_curve_by_arclength(points: np.ndarray, num_points: int) -> np.ndarray:
    """
    Resample a 2D curve so that `num_points` points are evenly spaced by arc length.

    Parameters
    ----------
    points : np.ndarray
        Array of shape (N, 2) containing the original curve points in order.
        The curve may loop back on itself (x is not required to be monotonic).
    num_points : int
        Number of points in the resampled curve (must be >= 2).
        The first and last points of the result will match the first and last
        points of the input.

    Returns
    -------
    np.ndarray
        Array of shape (num_points, 2) with evenly spaced points along the curve.

    Notes
    -----
    - Uses piecewise-linear interpolation along cumulative arc length.
    - Handles zero-length segments by collapsing them before interpolation.
    """
    pts = np.asarray(points, dtype=float)

    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"`points` must have shape (N, 2); got {pts.shape}")
    if num_points < 2:
        raise ValueError("`num_points` must be at least 2.")

    # Compute segment lengths and cumulative arc length
    deltas = pts[1:] - pts[:-1]           # (N-1, 2)
    seg_lengths = np.sqrt((deltas ** 2).sum(axis=1))  # (N-1,)
    cumlen = np.concatenate([[0.0], np.cumsum(seg_lengths)])  # (N,)

    total_length = cumlen[-1]
    if total_length == 0:
        # All points identical — just repeat the same point
        return np.tile(pts[0], (num_points, 1))

    # Remove any zero-length segments so cumlen is strictly increasing for interp
    mask = np.concatenate([[True], cumlen[1:] > cumlen[:-1]])
    pts_clean = pts[mask]
    cumlen_clean = cumlen[mask]

    if pts_clean.shape[0] < 2:
        # Degenerate after cleaning; fall back to repeating endpoints
        return np.vstack([
            np.tile(pts[0], (num_points - 1, 1)),
            pts[-1],
        ])

    # Target arc-length positions, evenly spaced from 0 to total_length
    s_target = np.linspace(0.0, total_length, num_points)

    # Interpolate x(s) and y(s) separately
    x_new = np.interp(s_target, cumlen_clean, pts_clean[:, 0])
    y_new = np.interp(s_target, cumlen_clean, pts_clean[:, 1])

    result = np.column_stack([x_new, y_new])

    # Ensure exact match for endpoints (avoids any tiny floating error)
    result[0] = pts[0]
    result[-1] = pts[-1]

    return result
