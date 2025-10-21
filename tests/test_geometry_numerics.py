import math
import pytest
from oiol2.geometry import sag_conic


@pytest.mark.parametrize(
    "Rmm,K,y",
    [
        (8.6, -0.5, 0.0),
        (8.6, -0.5, 2.0),
        (8.6, 0.0, 3.0),
        (8.6, +0.5, 3.0),
        (10.0, -0.8, 4.0),
    ],
)
def test_conic_sag_is_finite_and_nonnegative(Rmm, K, y):
    s = sag_conic(Rmm, K, y)
    assert math.isfinite(s)
    assert s >= 0.0
