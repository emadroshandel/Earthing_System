"""Checks against ENA EREC S34:2018 and the foundation/plate definitions (1.3.4)."""
import math
from earthsys.faultcurrent import split_factor_cable_s34
from earthsys.standards import epr_contour_distance_s34, epr_contour_distance
from earthsys import iec60364


def test_s34_p7_worked_example():
    # S34 section 6.1.7: A = 600 m2, EPR 2393 V, 840 V contour -> 12.5 m
    assert abs(epr_contour_distance_s34(600, 2393, 840) - 12.5) < 0.1
    assert epr_contour_distance_s34(600, 2393, 3000) == 0.0


def test_s34_p7_tends_to_far_field():
    # surface disc of radius a at EPR U carries I = 4aU/rho; far away P7 (from
    # the centre) approaches the hemisphere form x = rho I/(2 pi V)
    A, U, rho, V = 400.0, 5000.0, 100.0, 5.0
    a = math.sqrt(A / math.pi)
    I = 4 * a * U / rho
    x_disc = epr_contour_distance_s34(A, U, V) + a
    assert abs(x_disc - epr_contour_distance(rho, I, V)) / x_disc < 0.01


def test_s34_cable_split_local_and_remote():
    zc = 0.249 + 0.632j
    a = split_factor_cable_s34(1.0, zc, 0.2, 0.5, 1.0)
    assert abs(a["Sf"] - 0.1075) < 1e-3 and a["case"] == "D.2.1"
    b = split_factor_cable_s34(1.0, zc, 0.2, 0.5, 1.0, remote_source=True)
    assert b["Sf"] > a["Sf"] and "D.2.3" in b["formula"]
    # long cable tends to the reduction factor r_c/|z_c|
    c = split_factor_cable_s34(200.0, zc, 0.2, 0.5, 1.0)
    assert abs(c["Sf"] - c["reduction_factor"]) < 0.01


def test_foundation_equal_volume_hemisphere():
    rho, V = 150.0, 420.0
    R = iec60364.foundation(rho, V)["R"]
    r = (3 * V / (2 * math.pi)) ** (1 / 3)
    assert abs(R - rho / (2 * math.pi * r)) / R < 0.03
    assert "hemisphere" in iec60364.foundation(rho, V)["formula"]


def test_plate_s34_formula_label():
    out = iec60364.plate(100.0, 0.5, 0.2)
    assert "R2" in out["formula"]



# Run the functions above under plain unittest too (python -m unittest);
# pytest collects them directly and skips this class (__test__ = False).
import unittest as _unittest  # noqa: E402


class TestFunctions(_unittest.TestCase):
    __test__ = False


def _attach(cls, scope):
    for name, fn in list(scope.items()):
        if not (name.startswith("test_") and callable(fn)):
            continue
        params = getattr(fn, "_es_params", None)
        if params is None:             # real pytest installed: read its mark
            for m in getattr(fn, "pytestmark", []):
                if getattr(m, "name", "") == "parametrize":
                    a = m.args
                    params = ([n.strip() for n in a[0].split(",")]
                              if isinstance(a[0], str) else list(a[0]), list(a[1]))
        if params is None:
            setattr(cls, name, staticmethod(fn))
            continue
        names, values = params
        for i, vals in enumerate(values):
            vals = vals if isinstance(vals, tuple) else (vals,)
            kw = dict(zip(names, vals))
            setattr(cls, f"{name}_{i}", staticmethod(lambda fn=fn, kw=kw: fn(**kw)))


_attach(TestFunctions, dict(globals()))
