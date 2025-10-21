import math
import pytest

from oiol2.geometry import (
    sag_sphere,
    sag_conic,
    sag_difference_conic_vs_sphere,
    radius_to_surface_power,
    surface_power_to_radius,
    curvature_from_radius,
    radius_from_curvature,
    deg_to_rad,
    rad_to_deg,
)

TOL = 1e-9


def test_roundtrip_surface_power_radius():
    n_air = 1.0
    n_lens = 1.3375
    Rmm = 8.6  # typical BC radius in mm (sign per convention)
    F = radius_to_surface_power(n_air, n_lens, Rmm)
    Rmm2 = surface_power_to_radius(n_air, n_lens, F)
    assert abs(Rmm - Rmm2) < 1e-9


@pytest.mark.parametrize("Rmm,y", [(8.6, 0.0), (8.6, 3.0), (10.0, 4.5)])
def test_sag_sphere_closed_form(Rmm, y):
    s = sag_sphere(Rmm, y)
    expected = Rmm - math.sqrt(Rmm * Rmm - y * y)
    assert abs(s - expected) < TOL


def test_conic_reduces_to_sphere_when_K_zero():
    Rmm, y = 8.6, 3.0
    assert abs(sag_conic(Rmm, 0.0, y) - sag_sphere(Rmm, y)) < 1e-12


def test_conic_vs_sphere_difference_signals_K_effect():
    Rmm, y = 8.6, 3.5
    k_prolate = -0.5
    k_oblate = +0.5
    ds_prolate = sag_difference_conic_vs_sphere(Rmm, k_prolate, y)
    ds_oblate = sag_difference_conic_vs_sphere(Rmm, k_oblate, y)
    # Typically prolate (K<0) has *less* sag than sphere at same y; oblate more.
    assert ds_prolate < 0
    assert ds_oblate > 0


def test_curvature_roundtrip():
    R = 8.6
    c = curvature_from_radius(R)
    assert abs(radius_from_curvature(c) - R) < TOL


def test_angle_helpers():
    deg = 45.0
    rad = deg_to_rad(deg)
    assert abs(rad - math.pi / 4) < TOL
    assert abs(rad_to_deg(rad) - deg) < TOL