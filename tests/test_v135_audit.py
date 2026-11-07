"""Second IEEE 80-2013 (+Cor 1-2015) audit and full-capability test (1.3.4)."""
try:
    import pytest
except ImportError:                    # plain unittest: a minimal stand-in
    import contextlib as _contextlib
    import re as _re

    class pytest:                      # noqa: N801
        @staticmethod
        @_contextlib.contextmanager
        def raises(exc, match=None):
            try:
                yield
            except exc as e:           # noqa: B902
                if match and not _re.search(match, str(e)):
                    raise AssertionError(f"{e!r} does not match {match!r}")
            else:
                raise AssertionError(f"{exc.__name__} was not raised")

        class mark:                    # noqa: N801
            @staticmethod
            def parametrize(names, values):
                def deco(fn):
                    fn._es_params = ([n.strip() for n in names.split(",")], list(values))
                    return fn
                return deco
from earthsys import api, ieee80


def _b4(**kw):
    p = dict(rho=400, rho_s=2500, hs=0.102, ts=0.5, IG_kA=1.908, Lx=70, Ly=105,
             D=7, h=0.5, d=0.01, n_rods=24, Lr=7.5, shape="L", r_method="sverak",
             A_m2=4900, Lp_m=350, Lc_m=1575)
    p.update(kw)
    return p


def test_l_shaped_example_b4_matches_ieee80():
    r = api.api_ieee80(_b4())
    assert abs(r["Rg"] - 2.74) / 2.74 < 0.01
    assert abs(r["mesh"]["Em"] - 761.1) / 761.1 < 0.01
    assert abs(r["mesh"]["n"] - 12.2) < 0.1


def test_l_shape_without_true_area_is_refused():
    with pytest.raises(ValueError, match="Enclosed grid area"):
        api.api_ieee80(_b4(A_m2=0))


def test_rods_start_at_the_corners():
    g = ieee80.GridGeometry(Lx=63, Ly=84, D=7, n_rods=38, Lr=10)
    pts = g.rod_positions()
    assert len(pts) == 38
    for c in ((0, 0), (63, 84), (63, 0), (0, 84)):
        assert c in pts
    g20 = ieee80.GridGeometry(Lx=70, Ly=70, D=7, n_rods=20, Lr=7.5)
    assert sorted(g20.rod_positions()) == sorted(
        [(0, 0), (70, 70), (70, 0), (0, 70)] +
        [(x, 0.0) for x in (14, 28, 42, 56)] + [(70, y) for y in (14, 28, 42, 56)] +
        [(x, 70) for x in (56, 42, 28, 14)] + [(0.0, y) for y in (56, 42, 28, 14)])


def test_gpr_row_is_advisory_so_a_compliant_grid_is_not_red():
    r = api.api_ieee80(dict(rho=400, rho_s=2500, hs=0.102, ts=0.5, IG_kA=1.908,
                            Lx=70, Ly=70, D=5.5, h=0.5, d=0.01))
    gpr = [c for c in r["checks"] if c["name"].startswith("GPR")][0]
    assert gpr["advisory"] and not gpr["passed"] and r["passed"]


@pytest.mark.parametrize("bad,match", [
    (dict(IG_kA=-1.908), "grid current"), (dict(IG_kA=0), "grid current"),
    (dict(rho_s=-5), "cannot be negative"), (dict(body_weight=60), "Body weight"),
])
def test_grid_input_validation(bad, match):
    p = dict(rho=400, ts=0.5, IG_kA=1.908, Lx=70, Ly=70, D=7, h=0.5, d=0.01)
    p.update(bad)
    with pytest.raises(ValueError, match=match):
        api.api_ieee80(p)


def test_optimise_rejects_zero_step():
    p = dict(rho=400, ts=0.5, IG_kA=1.908, Lx=70, Ly=70, D=7, h=0.5, d=0.01,
             D_min=1.5, D_step=0)
    with pytest.raises(ValueError):
        api.api_ieee80_optimise(p)
    with pytest.raises(ValueError):
        ieee80.optimise(400, ieee80.GridGeometry(), 1.9, D_step=0)


def test_fault_direct_mode():
    d = api.api_fault(dict(Un_kV=20, tf=0.5, ts=0.5, frequency=50, mode="direct",
                           three_I0_kA=8.0, Sf=0.6, xr_ratio=16.67))
    assert d["line_to_earth"] is None and d["mode"] == "direct"
    assert abs(d["IG_kA"] - 8.0 * 0.6 * d["Df"]) < 1e-9
    with pytest.raises(ValueError, match="3I0"):
        api.api_fault(dict(Un_kV=20, tf=0.5, ts=0.5, frequency=50, mode="direct"))
    with pytest.raises(ValueError, match="S_f"):
        api.api_fault(dict(Un_kV=20, tf=0.5, ts=0.5, frequency=50, mode="direct",
                           three_I0_kA=8, Sf=-1))


def test_building_and_sysgnd_validation():
    base = dict(system="TT", U0=230, rho=150, electrodes=[dict(type="rod", L=3, d=0.016)])
    with pytest.raises(ValueError, match="rating"):
        api.api_building(dict(base, device=dict(kind="rcd", rating_A=0)))
    with pytest.raises(ValueError, match="System"):
        api.api_building(dict(base, system="XX", device=dict(kind="rcd", rating_A=0.03)))
    with pytest.raises(ValueError, match="negative"):
        api.api_sysgnd(dict(V_ll_kV=6.6, frequency=50, cable_km=-3))
    s = api.api_sysgnd(dict(V_ll_kV=6.6, frequency=50, method="solid"))
    assert abs(s["V_ln"] - 6600 / 3 ** 0.5) < 1e-6


def test_lightning_and_report_choices():
    with pytest.raises(ValueError, match="LPS class"):
        api.api_lightning(dict(rho=100, area=200, perimeter=60, h=0.5, d=0.01, lps_class="V"))
    with pytest.raises(ValueError, match="perimeter|Perimeter"):
        api.api_lightning(dict(rho=100, area=200, perimeter=0, h=0.5, d=0.01))
    with pytest.raises(ValueError, match="language"):
        api.api_report(dict(lang="xx", data={}))


def test_loop_check_reports_value_and_limit():
    from earthsys import iec60364
    c = iec60364.loop_impedance_check(230, 1.0, 80)
    assert c["value"] == 1.0 and abs(c["limit"] - 0.95 * 230 / 80) < 1e-12



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
