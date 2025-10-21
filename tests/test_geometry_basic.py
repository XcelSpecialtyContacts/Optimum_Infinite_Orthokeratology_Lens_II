import math
import importlib
import os
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
    assert abs(rad - math.pi/4) < TOL
    assert abs(rad_to_deg(rad) - deg) < TOL


# ---------- Golden-master comparison (optional) ----------
# If the legacy module is importable (e.g., placed anywhere on PYTHONPATH),
# we compare outputs to ensure the port matches historical behavior.
LEGACY_MODULE_NAME = "oiol2.geometryfunctions02"

legacy_available = False
try:
    _legacy = importlib.import_module(LEGACY_MODULE_NAME)
    legacy_available = True
except Exception:
    pass

legacy = pytest.mark.skipif(not legacy_available, reason="legacy module not available")


@legacy
@pytest.mark.parametrize("Rmm,y", [(8.0, 0.0), (8.6, 3.0), (10.0, 4.0)])
def test_legacy_sag_sphere_equivalence(Rmm, y):
    # Adjust this if legacy used different function name or units.
    new = sag_sphere(Rmm, y)
    old = _legacy.sag_sphere(Rmm, y) if hasattr(_legacy, "sag_sphere") else _legacy.Sag(Rmm, y)
    assert abs(new - old) < 1e-10


@legacy
def test_legacy_power_radius_equivalence():
    n_air, n_lens, Rmm = 1.0, 1.3375, 8.4
    newF = radius_to_surface_power(n_air, n_lens, Rmm)
    # Adjust if legacy signature differed
    if hasattr(_legacy, "radius_to_surface_power"):
        oldF = _legacy.radius_to_surface_power(n_air, n_lens, Rmm)
    else:
        # example fallback if old code assumed air->lens and had PowerFromRadius(n, R)
        oldF = _legacy.PowerFromRadius(n_lens, Rmm)
    assert abs(newF - oldF) < 1e-10
