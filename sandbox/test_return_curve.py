# sandbox/test_return_curve.py
from __future__ import annotations
import math
import sys
from typing import List, Tuple

Point = Tuple[float, float]  # (x, z)

# Project imports
from oiol2.transform2d import Transform2D, chord_transform

# Use your plotting helpers & Curve class if available
_use_project_plotting = True
_use_project_curve = True
try:
    from oiol2.vis.plotting import plot_meridional_curves, Curve
except Exception:
    _use_project_plotting = False
    _use_project_curve = False
    Curve = None  # type: ignore

# --- Minimal fallback Curve/plotting (only used if project plotting isn't importable) ---
if not _use_project_curve:
    class Curve:  # type: ignore
        def __init__(self, label: str, points: List[Point], linestyle: str = "-", linewidth: float = 1.7, marker=None):
            self.label = label
            self.points = points
            self.linestyle = linestyle
            self.linewidth = linewidth
            self.marker = marker
        def get_xz(self):
            xs = [p[0] for p in self.points]
            zs = [p[1] for p in self.points]
            return xs, zs

def _fallback_plot(curves, *, title: str):
    import matplotlib.pyplot as plt
    for c in curves:
        xs, zs = c.get_xz()
        ls = getattr(c, "linestyle", "-")
        lw = getattr(c, "linewidth", 1.7)
        mk = getattr(c, "marker", None)
        lbl = getattr(c, "label", "")
        plt.plot(xs, zs, linestyle=ls, linewidth=lw, marker=mk, label=lbl)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.grid(True, alpha=0.35)
    plt.title(title)
    plt.legend(loc="best")
    plt.show()

def _plot(curves, *, title: str, show: bool = True):
    if _use_project_plotting:
        plot_meridional_curves(curves, title=title, show=show)
    else:
        _fallback_plot(curves, title=title)

# --- Core: cubic Hermite RC built in LCS then mapped back to GCS ---
def sigmoid_segment_with_end_slopes(
    p_start: Point,
    p_end: Point,
    m_slope_start: float,
    m_slope_end: float,
    n: int = 200,
) -> List[Point]:
    """
    Generate a single-inflection cubic Hermite 'return curve' between p_start and p_end,
    matching end slopes defined in the GCS. Internally builds the curve in the chord-aligned
    LCS, then maps back to GCS.
    """
    x0, z0 = p_start
    x1, z1 = p_end
    dx, dz = x1 - x0, z1 - z0
    L = math.hypot(dx, dz)
    if L == 0:
        return [p_start] * n

    theta = math.atan2(dz, dx)

    # Rotate input slopes into LCS (where chord is +x)
    def rotate_slope_to_local(m: float, ang: float) -> float:
        return math.tan(math.atan(m) - ang)

    m0p = rotate_slope_to_local(m_slope_start, theta)
    m1p = rotate_slope_to_local(m_slope_end, theta)

    # Build in LCS
    pts_lcs: List[Point] = []
    for i in range(n):
        x = L * i / (n - 1)
        s = x / L
        y = L * ((s**3 - 2*s**2 + s) * m0p + (s**3 - s**2) * m1p)  # y in LCS
        pts_lcs.append((x, y))

    # Map LCS -> GCS via Transform2D
    tf = Transform2D.from_origin_angle(p_start, theta)
    pts_gcs = tf.points_to_global(pts_lcs)
    return pts_gcs

# --- Small helpers for checks/diagnostics ---
def _num_slope_at_end(points: List[Point], at_start: bool, k: int = 3) -> float:
    """
    Numerical slope dy/dx using a small forward/backward window of k points.
    Assumes points are ordered along the curve.
    """
    k = max(2, min(k, len(points)//2))
    if at_start:
        x0, z0 = points[0]
        x1, z1 = points[k]
    else:
        x0, z0 = points[-k-1]
        x1, z1 = points[-1]
    dx = x1 - x0
    dz = z1 - z0
    return dz / dx if dx != 0 else float("inf")

def _make_chord(p0: Point, p1: Point, n: int = 2) -> List[Point]:
    return [(p0[0] + t*(p1[0]-p0[0]), p0[1] + t*(p1[1]-p0[1])) for t in [i/(n-1) for i in range(n)]]

def main():
    # -------- Given constraints --------
    p_start: Point = (3.0, 0.533)
    p_end:   Point = (4.0, 1.059)
    m_slope_start = 0.367
    m_slope_end   = 0.649
    n_samples = 221

    # -------- Build RC (GCS) --------
    rc_gcs: List[Point] = sigmoid_segment_with_end_slopes(
        p_start, p_end, m_slope_start, m_slope_end, n=n_samples
    )

    # Also visualize the same RC in LCS for sanity
    tf = chord_transform(p_start, p_end)
    rc_lcs: List[Point] = tf.points_to_local(rc_gcs)

    # Optional chord for reference
    chord = _make_chord(p_start, p_end)

    # -------- Plots --------
    # Plot A (GCS): chord + RC
    curves_gcs = [
        Curve(label="Chord (GCS)", points=chord, linestyle="--"),
        Curve(label="Return Curve RC (GCS)", points=rc_gcs, linestyle="-"),
    ]
    _plot(curves_gcs, title="Return Curve • GCS view (Chord + RC)", show=False)

    # Plot B (LCS): RC should start at (0,0) and end at (L,0)
    curves_lcs = [
        Curve(label="RC in LCS (chord-aligned)", points=rc_lcs, linestyle="-"),
        Curve(label="LCS x-axis", points=[(rc_lcs[0][0], 0.0), (rc_lcs[-1][0], 0.0)], linestyle=":"),
    ]
    _plot(curves_lcs, title="Return Curve • LCS view (RC should cross x-axis at ends)", show=True)

    # -------- Checks --------
    # Endpoints
    print("\n[RC] Endpoint checks (GCS)")
    print(f"  Start (expected): {p_start}  (actual): {rc_gcs[0]}")
    print(f"  End   (expected): {p_end}    (actual): {rc_gcs[-1]}")

    # Slope checks (numerical in GCS)
    m0_num = _num_slope_at_end(rc_gcs, at_start=True, k=4)
    m1_num = _num_slope_at_end(rc_gcs, at_start=False, k=4)
    print("\n[RC] Slope checks (GCS, numerical)")
    print(f"  m_start target = {m_slope_start:.6f} ; estimated = {m0_num:.6f} ; Δ = {m0_num - m_slope_start:+.3e}")
    print(f"  m_end   target = {m_slope_end:.6f}   ; estimated = {m1_num:.6f} ; Δ = {m1_num - m_slope_end:+.3e}")

    # LCS flatness at the ends (y ≈ 0 by construction)
    y0_lcs = rc_lcs[0][1]
    y1_lcs = rc_lcs[-1][1]
    print("\n[RC] LCS endpoint y-values (should be ~0)")
    print(f"  y(0)  = {y0_lcs:.3e}")
    print(f"  y(L)  = {y1_lcs:.3e}")

    # Report chord length and rotation angle for context
    dx, dz = (p_end[0] - p_start[0], p_end[1] - p_start[1])
    L = math.hypot(dx, dz)
    theta = math.degrees(math.atan2(dz, dx))
    print(f"\n[RC] Chord length L = {L:.6f} ; chord angle θ (deg) = {theta:.6f}")

if __name__ == "__main__":
    sys.exit(main())
