# src/oiol2/transform2d.py
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Optional

Point = Tuple[float, float]
Vector = Tuple[float, float]

INF = float("inf")

def _is_inf(x: float) -> bool:
    return math.isinf(x)

def _clamp_angle(a: float) -> float:
    # Normalize to (-pi, pi], helpful for diagnostics
    a = (a + math.pi) % (2 * math.pi) - math.pi
    return a

@dataclass(frozen=True)
class Transform2D:
    """
    Rigid 2D transform parameterized by an origin (x0, y0) and a rotation theta.

    - to_local:   GCS -> LCS (translate by -origin, rotate by -theta)
    - to_global:  LCS -> GCS (rotate by +theta, translate by +origin)

    Notes
    -----
    * Points are affected by translation & rotation.
    * Vectors/tangents are affected ONLY by rotation.
    * Slopes are transformed via angle addition/subtraction, robust for verticals.
    * Lines are handled generically by mapping two sample points.
    """
    x0: float
    y0: float
    theta: float

    @property
    def cos(self) -> float:
        return math.cos(self.theta)

    @property
    def sin(self) -> float:
        return math.sin(self.theta)

    # --------- Constructors ---------
    @staticmethod
    def from_origin_angle(origin: Point, theta: float) -> "Transform2D":
        x0, y0 = origin
        return Transform2D(x0, y0, _clamp_angle(theta))

    @staticmethod
    def from_chord(p_start: Point, p_end: Point) -> "Transform2D":
        """
        Build an LCS whose origin is p_start and whose +x axis points from p_start to p_end.
        If start==end, theta=0 (arbitrary).
        """
        x0, y0 = p_start
        dx, dy = p_end[0] - x0, p_end[1] - y0
        theta = math.atan2(dy, dx) if (dx or dy) else 0.0
        return Transform2D(x0, y0, _clamp_angle(theta))

    # --------- Point / vector transforms ---------
    def point_to_local(self, P: Point) -> Point:
        """GCS point -> LCS point."""
        dx, dy = P[0] - self.x0, P[1] - self.y0
        # rotate by -theta
        x =  self.cos * dx + self.sin * dy
        y = -self.sin * dx + self.cos * dy
        return (x, y)

    def point_to_global(self, p: Point) -> Point:
        """LCS point -> GCS point."""
        # rotate by +theta
        X =  self.cos * p[0] - self.sin * p[1] + self.x0
        Y =  self.sin * p[0] + self.cos * p[1] + self.y0
        return (X, Y)

    def points_to_local(self, pts: Sequence[Point]) -> List[Point]:
        return [self.point_to_local(P) for P in pts]

    def points_to_global(self, pts: Sequence[Point]) -> List[Point]:
        return [self.point_to_global(p) for p in pts]

    def vec_to_local(self, v: Vector) -> Vector:
        """GCS vector/tangent -> LCS vector (no translation)."""
        x, y = v
        return ( self.cos * x + self.sin * y,
                -self.sin * x + self.cos * y)

    def vec_to_global(self, v: Vector) -> Vector:
        """LCS vector/tangent -> GCS vector (no translation)."""
        x, y = v
        return ( self.cos * x - self.sin * y,
                 self.sin * x + self.cos * y)

    # --------- Slope transforms (robust to verticals) ---------
    def slope_to_local(self, m: float) -> float:
        """
        Convert GCS slope to LCS slope.
        We treat slopes via angles: phi' = atan(m) - theta; m' = tan(phi').
        Handles ±inf correctly.
        """
        if _is_inf(m):
            # angle = pi/2 in GCS
            phi = math.pi / 2
        else:
            phi = math.atan(m)
        phi_local = _clamp_angle(phi - self.theta)
        # If exactly vertical after rotation, return ±inf
        if abs(abs(phi_local) - math.pi/2) < 1e-14:
            return INF * (1 if phi_local > 0 else -1)
        return math.tan(phi_local)

    def slope_to_global(self, m_local: float) -> float:
        """
        Convert LCS slope to GCS slope.
        phi = atan(m_local) + theta; m = tan(phi).
        """
        if _is_inf(m_local):
            phi_local = math.pi / 2
        else:
            phi_local = math.atan(m_local)
        phi = _clamp_angle(phi_local + self.theta)
        if abs(abs(phi) - math.pi/2) < 1e-14:
            return INF * (1 if phi > 0 else -1)
        return math.tan(phi)

    # --------- Line transforms (y = m x + b or vertical x = c) ---------
    @staticmethod
    def line_from_two_points(P: Point, Q: Point) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Return a line in either form:
          - non-vertical: (m, b, None) meaning y = m x + b
          - vertical:     (None, None, c) meaning x = c
        """
        (x1, y1), (x2, y2) = P, Q
        if abs(x2 - x1) < 1e-15:
            return (None, None, x1)  # x = const
        m = (y2 - y1) / (x2 - x1)
        b = y1 - m * x1
        return (m, b, None)

    def map_line_to_local(self, m: Optional[float], b: Optional[float], cx: Optional[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Map a GCS line to LCS by transforming two sample points and refitting.
        Input:
          - non-vertical: (m, b, None) for y = m x + b
          - vertical:     (None, None, c) for x = c
        Output uses same convention.
        """
        if cx is None:
            # pick two x to sample in GCS
            xA = 0.0
            yA = m * xA + b
            xB = 1.0
            yB = m * xB + b
        else:
            # vertical line x = c, pick two y
            xA = cx; yA = 0.0
            xB = cx; yB = 1.0

        pA = self.point_to_local((xA, yA))
        pB = self.point_to_local((xB, yB))
        return Transform2D.line_from_two_points(pA, pB)

    def map_line_to_global(self, m: Optional[float], b: Optional[float], cx: Optional[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Map an LCS line to GCS by transforming two sample points and refitting.
        """
        if cx is None:
            xA = 0.0
            yA = m * xA + b
            xB = 1.0
            yB = m * xB + b
        else:
            xA = cx; yA = 0.0
            xB = cx; yB = 1.0

        pA = self.point_to_global((xA, yA))
        pB = self.point_to_global((xB, yB))
        return Transform2D.line_from_two_points(pA, pB)

    # --------- Composition ---------
    def then(self, next_tf: "Transform2D") -> "Transform2D":
        """
        Compose transforms: first apply self, then next_tf.
        Returns a single Transform2D equivalent to next_tf ∘ self.
        """
        # Map this origin into the next_tf frame? Easier: compute combined rotation,
        # and global origin = self.origin mapped by next_tf?
        # We want G_out = next_tf(G_in_after_self). For composition in same GCS:
        # combined rotation = self.theta + next_tf.theta around world origin?
        # Safer route: derive by mapping LCS origin & axes.
        # Here we compute equivalent by mapping our origin to global using next_tf.
        # Actually we need a transform of the same form: origin + angle.
        # Strategy: The combined rotation is theta_c = self.theta + next_tf.theta.
        theta_c = _clamp_angle(self.theta + next_tf.theta)
        # Combined origin is next_tf applied to our origin expressed in next_tf's LCS.
        # But our origin is a GCS point. We want: apply next_tf AFTER self means
        # first go to self's LCS, then to global via self, then via next_tf...
        # Simpler: build matrices; but we can do direct:
        # Let T1 (self): G <-> L1; T2 (next): G <-> L2.
        # We want a single T such that p_L2 = T2.point_to_local( T1.point_to_global(p_L1) )
        # For a practical toolkit, we often don't need chain packed; to avoid confusion, skip compose.
        raise NotImplementedError("Composition is omitted to avoid subtle frame confusion. Use explicit steps.")

# --------- Convenience helpers ---------
def chord_transform(p_start: Point, p_end: Point) -> Transform2D:
    """Alias for Transform2D.from_chord."""
    return Transform2D.from_chord(p_start, p_end)

def rotate_points_about(points: Sequence[Point], about: Point, angle: float) -> List[Point]:
    """Rotate a set of points around `about` by +angle (radians) in GCS."""
    tf = Transform2D.from_origin_angle(about, angle)
    # to LCS: translate to origin and rotate -angle, but we want a pure rotation around 'about':
    # map to local (about, angle=0), then apply vec_to_global with angle, but simpler:
    out = []
    c, s = math.cos(angle), math.sin(angle)
    ax, ay = about
    for X, Y in points:
        dx, dy = X - ax, Y - ay
        x =  c*dx - s*dy + ax
        y =  s*dx + c*dy + ay
        out.append((x, y))
    return out

# --------- Quick self-checks ---------
if __name__ == "__main__":
    # Straight sanity tests
    P0 = (2.0, 3.0)
    P1 = (7.0, 6.0)
    tf = chord_transform(P0, P1)

    # Endpoints map as expected
    p0 = tf.point_to_local(P0)
    p1 = tf.point_to_local(P1)
    assert abs(p0[0]) < 1e-12 and abs(p0[1]) < 1e-12
    assert abs(p1[1]) < 1e-12 and p1[0] > 0

    # Round-trip a random point
    Qg = (5.3, -1.2)
    ql = tf.point_to_local(Qg)
    Qg2 = tf.point_to_global(ql)
    assert abs(Qg2[0] - Qg[0]) < 1e-12 and abs(Qg2[1] - Qg[1]) < 1e-12

    # Slopes: vertical and finite
    for m in [0.0, 0.5, 10.0, INF]:
        ml = tf.slope_to_local(m)
        mg = tf.slope_to_global(ml)
        # Direction equivalence check via angles
        ang = (math.pi/2 if _is_inf(m) else math.atan(m))
        ang_l = ang - tf.theta
        ang_rt = ang_l + tf.theta
        mg_ang = (math.pi/2 if _is_inf(mg) else math.atan(mg))
        assert abs(_clamp_angle(mg_ang - ang_rt)) < 1e-12

    # Lines: vertical and non-vertical
    line = (2.0, -3.0, None)   # y = 2x - 3
    line_l = tf.map_line_to_local(*line)
    line_g = tf.map_line_to_global(*line_l)
    assert (line_g[2] is None) and abs(line_g[0] - 2.0) < 1e-10 and abs(line_g[1] + 3.0) < 1e-10

    vline = (None, None, 4.2)  # x = 4.2
    vline_l = tf.map_line_to_local(*vline)
    vline_g = tf.map_line_to_global(*vline_l)
    assert (vline_g[2] is not None) and abs(vline_g[2] - 4.2) < 1e-10

    print("Transform2D basic checks passed.")
