# sandbox/test_2d_transforms.py
from __future__ import annotations
import math
import sys
from typing import List, Tuple

Point = Tuple[float, float]  # (x, z)

from oiol2.transform2d import Transform2D, chord_transform

_use_project_linegen = True
_use_project_plotting = True
_use_project_curve = True

try:
    from oiol2.geometry.meridional import generate_line_path  # signature: (p0, p1, n=? / num=?)
except Exception:
    _use_project_linegen = False

try:
    from oiol2.vis.plotting import plot_meridional_curves, Curve  # use your Curve class
except Exception:
    _use_project_plotting = False
    _use_project_curve = False
    Curve = None  # type: ignore

# -------- Fallbacks (only used if project helpers unavailable) --------
def _fallback_generate_line_path(p0: Point, p1: Point, n: int = 101) -> List[Point]:
    x0, z0 = p0
    x1, z1 = p1
    return [(x0 + t * (x1 - x0), z0 + t * (z1 - z0)) for t in [i/(n-1) for i in range(n)]]

def _fallback_plot(curves, title):
    import matplotlib.pyplot as plt
    for c in curves:
        xs, zs = c.get_xz()
        ls = getattr(c, "linestyle", "-")
        lw = getattr(c, "linewidth", 1.5)
        mk = getattr(c, "marker", None)
        lbl = getattr(c, "label", "")
        plt.plot(xs, zs, linestyle=ls, linewidth=lw, marker=mk, label=lbl)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.grid(True, alpha=0.3)
    plt.title(title)
    plt.legend(loc="best")
    plt.show()

# Minimal adapter only if Curve isn’t available
if not _use_project_curve:
    class Curve:  # type: ignore
        def __init__(self, label: str, points: List[Point], linestyle: str = "-", linewidth: float = 1.5, marker=None):
            self.label = label
            self.points = points
            self.linestyle = linestyle
            self.linewidth = linewidth
            self.marker = marker
        def get_xz(self):
            xs = [p[0] for p in self.points]
            zs = [p[1] for p in self.points]
            return xs, zs

def _plot(curves, *, title: str, show: bool = True):
    if _use_project_plotting:
        plot_meridional_curves(curves, title=title, show=show)
    else:
        _fallback_plot(curves, title)

def _error_stats(a: List[Point], b: List[Point]):
    """Return per-axis max error, max radial error, RMS radial error."""
    assert len(a) == len(b)
    n = len(a)
    max_dx = max_dz = max_dr = rms_acc = 0.0
    worst_idx = 0
    for i, (pa, pb) in enumerate(zip(a, b)):
        dx = pb[0] - pa[0]
        dz = pb[1] - pa[1]
        dr = math.hypot(dx, dz)
        if abs(dx) > abs(max_dx): max_dx = dx
        if abs(dz) > abs(max_dz): max_dz = dz
        if dr > max_dr:
            max_dr = dr
            worst_idx = i
        rms_acc += dr*dr
    rms = math.sqrt(rms_acc / n)
    return max_dx, max_dz, max_dr, rms, worst_idx

def main():
    # Inputs
    p_start: Point = (2.0, 3.0)
    p_end:   Point = (7.5, 6.2)
    n_samples = 151

    # Generate a simple test line in GCS
    if _use_project_linegen:
        try:
            pts_gcs: List[Point] = generate_line_path(p_start, p_end, n=n_samples)
        except TypeError:
            try:
                pts_gcs = generate_line_path(p_start, p_end, num=n_samples)
            except Exception:
                pts_gcs = _fallback_generate_line_path(p_start, p_end, n=n_samples)
    else:
        pts_gcs = _fallback_generate_line_path(p_start, p_end, n=n_samples)

    # Transform
    tf = chord_transform(p_start, p_end)
    pts_lcs: List[Point] = tf.points_to_local(pts_gcs)
    pts_back_to_gcs: List[Point] = tf.points_to_global(pts_lcs)

    # -------------------- Plot #1: Original GCS --------------------
    curves_gcs = [
        Curve(label="Original (GCS)", points=pts_gcs, linestyle="-"),
    ]
    _plot(curves_gcs, title="Plot 1 • GCS: Original line", show=False)

    # -------------------- Plot #2: LCS -----------------------------
    curves_lcs = [
        Curve(label="Mapped to LCS (should lie on x-axis)", points=pts_lcs, linestyle="-"),
    ]
    _plot(curves_lcs, title="Plot 2 • LCS: Line in chord-aligned frame", show=False)

    # -------------------- Plot #3: Round-trip back to GCS ----------
    curves_roundtrip = [
        Curve(label="Round-trip (LCS→GCS)", points=pts_back_to_gcs, linestyle="--"),
    ]
    _plot(curves_roundtrip, title="Plot 3 • GCS: Round-trip only", show=True)

    # -------------------- Numeric error check ----------------------
    max_dx, max_dz, max_dr, rms, worst_idx = _error_stats(pts_gcs, pts_back_to_gcs)
    print("\n[Transform2D] Round-trip error report (Plot 1 vs Plot 3)")
    print(f"  Max |Δx|: {abs(max_dx):.3e}  (signed Δx={max_dx:.3e})")
    print(f"  Max |Δz|: {abs(max_dz):.3e}  (signed Δz={max_dz:.3e})")
    print(f"  Max radial error: {max_dr:.3e} at index {worst_idx}")
    print(f"  RMS radial error: {rms:.3e}")

    # Also keep the earlier endpoint + LCS flatness checks
    max_abs_z = max(abs(p[1]) for p in pts_lcs)
    L = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])
    p0_l = tf.point_to_local(p_start)
    p1_l = tf.point_to_local(p_end)

    print(f"\n[Transform2D] LCS check: max |z| along mapped line = {max_abs_z:.3e} (should be ~0)")
    print(f"[Transform2D] p_start -> LCS {p0_l} (expect ~ (0, 0))")
    print(f"[Transform2D] p_end   -> LCS {p1_l} (expect ~ ({L:.6f}, 0))")

if __name__ == "__main__":
    sys.exit(main())
