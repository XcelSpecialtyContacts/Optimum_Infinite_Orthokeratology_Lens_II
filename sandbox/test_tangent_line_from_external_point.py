from math import sqrt, isclose, inf

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

r = 0.06
c = (5.19, 1.7056771314517107)
p = (4.931695855252253, 1.4848013157363509)
m, b, t_p = tangent_line_from_external_point(c, r, p)
print(f"m = {m}")
print(f"b = {b}")
print(f"t_p = {t_p}")