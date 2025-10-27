import math

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

# Example numbers
R0 = 1.0
K = 0.8
d = 0.0
m = 0.5
b = 0.1

pts = conic_line_intersections(m, b, R0, K, d)
#for x, y in pts:
#    print(f"x={x:.6f}, y={y:.6f}")
x2, y2 = pts[1]
print(pts[1][0])
