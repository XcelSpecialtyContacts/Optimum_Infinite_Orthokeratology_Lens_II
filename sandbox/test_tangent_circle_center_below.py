from math import hypot
from typing import Tuple

def tangent_circle_center_below(m1: float, b1: float,
                                m2: float, b2: float,
                                r: float) -> tuple[float, float]:
    """
    Find the center (h, k) of a circle of radius r tangent to both lines
      y = m1*x + b1  and  y = m2*x + b2,
    choosing the solution where the center lies BELOW both lines.

    Returns:
        (h, k)

    Raises:
        ValueError: if the lines are parallel (no unique intersection of the
                    offset lines) or r < 0.
    """
    if r < 0:
        raise ValueError("Radius must be nonnegative.")
    # For a point (h,k) below the line y = m x + b at distance r:
    # distance sign is positive: (m*h - k + b) / sqrt(m^2 + 1) = r
    #  -> k = m*h + b - r*sqrt(m^2 + 1)
    s1 = hypot(m1, 1.0)  # sqrt(m1^2 + 1)
    s2 = hypot(m2, 1.0)  # sqrt(m2^2 + 1)

    denom = (m1 - m2)
    if abs(denom) < 1e-15:
        raise ValueError("Lines are (nearly) parallel; no unique solution.")

    # Solve the two shifted (parallel) lines for their intersection:
    # k = m1*h + b1 - r*s1
    # k = m2*h + b2 - r*s2
    # => (m1 - m2) h = (b2 - b1) + r (s1 - s2)
    h = ((b2 - b1) + r * (s1 - s2)) / denom
    k = m1 * h + b1 - r * s1
    return h, k

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

    center = (h, k)
    p_tangetn_line_1 = (t1x, t1y)
    p_tangetn_line_2 = (t2x, t2y)

    return center, p_tangetn_line_1, p_tangetn_line_2

m1 = 0.812 / 1.25
b1 = 1.87 - m1 * 5.25
m2 = 0.19 / 0.4
b2 = 1.8 - m2 * 5.25
r = 1
center, p1, p2 = tangent_circle_below_with_points(m1, b1, m2, b2, r)

print(f"Center: {center}")
print(f"Tangent Point 1: {p1}")
print(f"Tangent Point 2: {p2}")