import math
from typing import Tuple

def calc_bs_edge_data(x: float, m: float, b: float, r: float) -> Tuple[Tuple[float, float],
                                                                       Tuple[float, float],
                                                                       Tuple[float, float]]:
    """
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


x = 5.25
rise = 0.19
run = 0.4
m = rise / run
pol = (5.25, 1.8)
b = pol[1] - pol[0] * m
r = 0.06

results = calc_bs_edge_data(x, m, b, r)

print(f"x = {x}")
print(f"m = {m}")
print(f"b = {b}")
print(f"r = {r}")
print(f"center: {results[0]}")
print(f"point tangent to EL: {results[1]}")
print(f"point tangent to VL: {results[2]}")