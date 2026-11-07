"""Consistency check of 30 September 2026 (1.3.5).

Each test pins a number or behaviour that the documentation states."""
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
from earthsys import api, bem


def _cond(**kw):
    p = dict(I_kA=6.8, tc=0.5, Df=1, Ta=40, material="cu_hard", joint=None,
             iec_material="copper", insulation="bare", installation="buried",
             mechanically_protected=False)
    p.update(kw)
    return api.dispatch("/api/conductor", p)


def test_bare_buried_defaults_to_not_corrosion_protected():
    # IEC 60364-5-54 / BS 7671 Table 54.1: a bare buried conductor is not
    # protected against corrosion -> 25 mm2 copper (Table 54.1).
    d = _cond()
    assert d["min_buried"]["copper_mm2"] == 25.0
    assert d["selected_mm2"] == 35


def test_sheath_claimed_on_bare_conductor_is_warned():
    d = _cond(corrosion_protected=True)
    assert d["min_buried"]["copper_mm2"] == 16.0
    assert any("not protected against corrosion" in w for w in d.get("warnings", []))


def test_design_basis_ieee80_only_realises_welded_saving():
    # 10 kA, 0.5 s, welded copper: IEEE 80 needs 25.4 mm2,
    # the IEC 200 degC criterion about 44.5 mm2.
    both = _cond(I_kA=10, joint="exothermic", basis="both")
    only = _cond(I_kA=10, joint="exothermic", basis="ieee80")
    assert abs(both["ieee80"]["area_mm2"] - 25.4) < 0.2
    assert both["selected_mm2"] == 50 and both["governs"] == "IEC adiabatic"
    assert only["selected_mm2"] == 35 and only["governs"] == "IEEE 80"


def test_bare_buried_minimum_iec_2011():
    # IEC 60364-5-54:2011 542.3.1 / Table 54.1: 50 mm2 Cu with an LPS,
    # hot-dip galvanized steel round wire 10 mm (78.5 mm2).
    d = _cond(lps_connected=True)
    assert d["min_buried"]["copper_mm2"] == 50.0 and d["selected_mm2"] == 50
    assert _cond()["min_buried"]["steel_mm2"] == 78.5


def test_design_basis_rejects_unknown():
    with pytest.raises(ValueError):
        _cond(basis="nec")


def test_en50522_thin_layer_cross_check_annex_b():
    g = dict(rho=400, rho_s=2500, hs=0.102, ts=0.5, IG_kA=1.908, Lx=70, Ly=70,
             D=7, h=0.5, d=0.01)
    x = api.dispatch("/api/ieee80/design", g)["en50522"]
    assert abs(x["U_Tp"] - 225) < 1e-9          # BS EN 50522:2022 Table B.4
    assert abs(x["U_vTp"] - 1175) < 1          # Formula (A.3), R_F2 = 1.5 rho_s
    assert abs(x["U_vTp_thin"] - 982) < 1      # R_F2 = 1.5 Cs rho_s
    assert x["mesh_vs_UvTp_thin"] > 1.0


def test_annex_b_with_20_rods_numerical_rg():
    # Table 8.2: Earthing System cell for "Annex B + 20 rods".
    g = dict(rho=400, rho_s=2500, hs=0.102, ts=0.5, IG_kA=1.908, Lx=70, Ly=70,
             D=7, h=0.5, d=0.01, n_rods=20, Lr=7.5, rods_on_perimeter=True)
    rods = api.dispatch("/api/ieee80/design", g)["layout"]["rods"]
    items = [dict(kind="grid", Lx=70, Ly=70, D=7, depth=0.5, radius=0.005)] + [
        dict(kind="rod", x=p[0], y=p[1], top_depth=0.5, length=7.5, radius=0.008)
        for p in rods]
    n = bem.build_network(dict(rho1=400, IG=1908, items=items))
    n.discretise(2.0, 5000)
    assert abs(n.solve()["Rg"] - 2.490) < 0.003


# ---------------------------------------------------------------------------
# IEEE 80-2013/Cor 1-2015 Annex H benchmarks (Table 8.3) and Annex B.5.
_I = 744.8


def _annex_h_grid(rods):
    it = [dict(kind="grid", Lx=70, Ly=70, D=14, depth=0.5, radius=0.0105 / 2)]
    if rods:
        pts = sorted({(x, y) for x in range(0, 71, 14) for y in range(0, 71, 14)
                      if x in (0, 70) or y in (0, 70)})
        it += [dict(kind="rod", x=x, y=y, top_depth=0.5, length=7.5,
                    radius=0.0159 / 2) for x, y in pts]
    return it


def _solve(spec, seg=2.0):
    n = bem.build_network(spec)
    n.discretise(seg, 8000)
    s = n.solve()
    V = s["GPR"]
    p = n.potential_at([[7, 7, 0.0], [0, 0, 0.0], [-0.7071, -0.7071, 0.0]])
    return s["Rg"], V - p[0], p[1] - p[2]


@pytest.mark.parametrize("soil,rods,ref", [
    (dict(rho1=140), False, (1.0, 194.9, 89.3)),                        # Grid 1, CDEGS
    (dict(rho1=140), True, (0.917, 145.4, 70.7)),                       # Grid 2
    (dict(rho1=300, rho2=100, h_layer=6.096), True, (0.97, 261.0, 101.9)),  # Grid 3
])
def test_ieee80_annex_h_benchmarks(soil, rods, ref):
    Rg, T1, S1 = _solve(dict(soil, IG=_I, items=_annex_h_grid(rods)))
    assert abs(Rg - ref[0]) / ref[0] < 0.01
    assert abs(T1 - ref[1]) / ref[1] < 0.01
    assert abs(S1 - ref[2]) / ref[2] < 0.05


def _b5(rod_len):
    L = 60.96
    items = [dict(kind="grid", Lx=L, Ly=L, D=15.24, depth=0.5, radius=0.005)] + [
        dict(kind="rod", x=x, y=y, top_depth=0.5, length=rod_len, radius=0.00635)
        for x in (0, L / 2, L) for y in (0, L / 2, L)]
    n = bem.build_network(dict(rho1=300, rho2=100, h_layer=4.572, IG=1000, items=items))
    n.discretise(3.0, 6000)
    s = n.solve()
    pc = n.potential_at([[7.62, 7.62, 0.0]])[0]
    return s["Rg"], (s["GPR"] - pc) / s["GPR"]


def test_annex_b5_two_layer_explained():
    # Full 9.144 m rods (crossing the interface): 1.137 ohm, Em 43.6 % of GPR.
    Rg, em = _b5(9.144)
    assert abs(Rg - 1.137) < 0.005 and abs(em - 0.436) < 0.005
    # Rods stopped at the interface reproduce IEEE 80's 1.353 ohm / 49.66 %.
    Rg, em = _b5(4.072)
    assert abs(Rg - 1.353) / 1.353 < 0.01 and abs(em - 0.4966) < 0.01



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
