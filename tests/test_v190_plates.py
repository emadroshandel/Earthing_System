"""1.9.0: thin metal plates (earth plates, a raft's reinforcement as one sheet)
in the numerical solver, checked against an independent panel solution and
the capacitance of the unit square (Read 2004)."""
import math
import unittest

import numpy as np

from earthsys import bem
from earthsys.api import dispatch


# --------------------------------------------------------------------------
# Independent reference: constant-charge rectangular panels, cosine-graded,
# with the exact potential of a uniform rectangle, collocation at the panel
# centres; the same-sign image of the soil surface.  Nothing is shared with
# bem.py.  Richardson in 1/n² from n and 2n panels per side.
# --------------------------------------------------------------------------

def _F(x, y, w):
    r = np.sqrt(x * x + y * y + w * w)
    out = x * np.log(np.abs(y + r) + 1e-300) + y * np.log(np.abs(x + r) + 1e-300)
    if w != 0:
        out = out - w * np.arctan2(x * y, w * r)       # w > 0: = atan(xy/wr)
    return out


def _rect(px, py, w, x1, x2, y1, y2):
    return (_F(x2 - px, y2 - py, w) - _F(x1 - px, y2 - py, w)
            - _F(x2 - px, y1 - py, w) + _F(x1 - px, y1 - py, w))


def _panels(Lx, Ly, n):
    def cosd(m):
        return 0.5 - 0.5 * np.cos(np.pi * np.arange(m + 1) / m)
    ny = max(4, int(round(n * Ly / Lx)))
    tx, ty = cosd(n) * Lx, cosd(ny) * Ly
    X1, Y1 = np.meshgrid(tx[:-1], ty[:-1])
    X2, Y2 = np.meshgrid(tx[1:], ty[1:])
    return X1.ravel(), X2.ravel(), Y1.ravel(), Y2.ravel()


def _panel_solution(Lx, Ly, depth, n):
    """Charge density for V = 1 (in units of ρ/4π) of a horizontal plate."""
    x1, x2, y1, y2 = _panels(Lx, Ly, n)
    px, py = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
    A = (_rect(px[:, None], py[:, None], 0.0, x1[None], x2[None], y1[None], y2[None])
         + _rect(px[:, None], py[:, None], 2 * depth, x1[None], x2[None], y1[None], y2[None]))
    q = np.linalg.solve(A, np.ones(len(px)))
    return q, (x1, x2, y1, y2)


def panel_R(Lx, Ly, depth, rho, n=20):
    vals = []
    for m in (n, 2 * n):
        q, (x1, x2, y1, y2) = _panel_solution(Lx, Ly, depth, m)
        vals.append(rho / (4 * math.pi * float((q * (x2 - x1) * (y2 - y1)).sum())))
    return (4 * vals[1] - vals[0]) / 3


def panel_surface(Lx, Ly, depth, pts, n=40):
    """Surface potential / plate potential."""
    q, (x1, x2, y1, y2) = _panel_solution(Lx, Ly, depth, n)
    pts = np.asarray(pts, float)
    return 2 * _rect(pts[:, 0, None], pts[:, 1, None], depth,
                     x1[None], x2[None], y1[None], y2[None]) @ q


def es_plate(item, rho=100.0, **soil):
    net = bem.build_network(dict(rho1=rho, items=[item], **soil))
    net.discretise(2.0, 20000, grade_ends=True)
    bem.clear_cache()
    sol = net.solve()
    return net, sol


class TestPlateResistance(unittest.TestCase):

    def test_unit_square_far_from_the_surface(self):
        # R of a thin square of side a in a full space: ρ/(4π·0.3667896·a)
        # (Read 2004); 1000 m deep, the image adds ρ/(4π·2h)
        a, h, rho = 10.0, 1000.0, 100.0
        ref = rho / (4 * math.pi * 0.3667896 * a) + rho / (4 * math.pi * 2 * h)
        _, s = es_plate(dict(kind="plate", x0=0, y0=0, Lx=a, Ly=a, depth=h))
        e = s["Rg"] / ref - 1
        self.assertTrue(0 < e < 0.004, e)                 # slightly high, within 0.4 %

    def test_against_the_panel_solution(self):
        for Lx, Ly, d in ((1.0, 1.0, 0.5), (4.0, 1.0, 0.8), (6.0, 6.0, 1.0)):
            ref = panel_R(Lx, Ly, d, 100.0)
            _, s = es_plate(dict(kind="plate", x0=0, y0=0, Lx=Lx, Ly=Ly, depth=d))
            e = s["Rg"] / ref - 1
            self.assertTrue(0 < e < 0.004, (Lx, Ly, d, s["Rg"], ref))

    def test_vertical_and_layered_against_recorded_panel_values(self):
        # panel solutions with 48–120 panels per side and Richardson
        # extrapolation (the vertical plate's images lie in its own plane;
        # in two-layer soil the series of K^n images)
        cases = [(dict(kind="plate", orientation="vertical", x0=0, y0=0, length=1, height=1,
                       top_depth=0.5), {}, 25.74686),
                 (dict(kind="plate", orientation="vertical", x0=0, y0=0, length=2, height=0.5,
                       top_depth=0.6, angle=90), {}, 23.91217),
                 (dict(kind="plate", x0=0, y0=0, Lx=10, Ly=1, depth=0.5), {}, 8.32856),
                 (dict(kind="plate", x0=0, y0=0, Lx=1, Ly=1, depth=0.5),
                  dict(rho2=400, h_layer=2.0), 35.79506)]
        for item, soil, ref in cases:
            _, s = es_plate(item, **soil)
            e = s["Rg"] / ref - 1
            self.assertTrue(0 < e < 0.003, (item, s["Rg"], ref))

    def test_more_strips_converge(self):
        errs = []
        ref = panel_R(1.0, 1.0, 0.5, 100.0)
        for n in (8, 16, 32):
            _, s = es_plate(dict(kind="plate", x0=0, y0=0, Lx=1, Ly=1, depth=0.5, strips=n))
            errs.append(s["Rg"] / ref - 1)
        self.assertTrue(errs[0] > errs[1] > errs[2] > 0, errs)
        self.assertLess(errs[1] / errs[2], 4.5)
        self.assertGreater(errs[1] / errs[2], 3.0)      # about 1/n²

    def test_turned_plate_and_symmetry(self):
        _, s0 = es_plate(dict(kind="plate", x0=0, y0=0, Lx=2, Ly=1, depth=0.5))
        _, s1 = es_plate(dict(kind="plate", x0=5, y0=-3, Lx=2, Ly=1, depth=0.5, angle=37))
        self.assertAlmostEqual(s0["Rg"], s1["Rg"], delta=1e-5 * s0["Rg"])
        self.assertEqual(s0["solver"]["symmetry"], 4)


class TestPlateSurface(unittest.TestCase):

    def test_surface_potential_over_a_shallow_plate(self):
        Lx = Ly = 6.0
        d = 0.5
        xs = np.linspace(-2, 8, 41)
        pts = np.vstack([np.column_stack([xs, np.full_like(xs, 3.0)]),
                         np.column_stack([xs, np.full_like(xs, 0.3)])])
        ref = panel_surface(Lx, Ly, d, pts)
        net, s = es_plate(dict(kind="plate", x0=0, y0=0, Lx=Lx, Ly=Ly, depth=d))
        got = net.potential_at(np.column_stack([pts, np.zeros(len(pts))])) / s["GPR"]
        self.assertLess(np.abs(got - ref).max(), 0.01)     # within 1 % of the GPR


class TestPlateUse(unittest.TestCase):

    def test_api_with_a_grid(self):
        d = dispatch("/api/bem", dict(rho1=100, IG=1000, segment_length=3, nx=21, items=[
            dict(kind="grid", Lx=20, Ly=20, D=5, depth=0.5, radius=0.005),
            dict(kind="plate", orientation="vertical", x0=25, y0=10, length=1, height=1,
                 top_depth=0.5)]))
        self.assertGreater(d["Rg"], 0)
        tags = {g["tag"] for g in d["geometry"]}
        self.assertIn("plate", tags)

    def test_refused_by_the_wire_models(self):
        it = [dict(kind="grid", Lx=20, Ly=20, D=10, depth=0.5, radius=0.005),
              dict(kind="plate", x0=0, y0=0, Lx=1, Ly=1, depth=0.5)]
        for ep in ("/api/bem/powerfreq", "/api/hf"):
            with self.assertRaises(ValueError):
                dispatch(ep, dict(rho1=100, rho0=100, IG=1000, items=it))

    def test_plates_keep_their_segments(self):
        net = bem.build_network(dict(rho1=100, items=[
            dict(kind="plate", x0=0, y0=0, Lx=2, Ly=2, depth=0.5)]))
        n1 = net.discretise(3.0)
        n2 = net.discretise(0.5)
        self.assertEqual(n1, n2)                          # the convergence check leaves it alone
        with self.assertRaises(ValueError):
            net.discretise(1.0, max_segments=100)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            bem.build_network(dict(rho1=100, items=[dict(kind="plate", x0=0, y0=0, Lx=0, Ly=1)]))
        with self.assertRaises(ValueError):
            bem.build_network(dict(rho1=100, items=[dict(kind="plate", x0=0, y0=0, Lx=1, Ly=1,
                                                         strips=2)]))
        with self.assertRaises(ValueError):
            bem.build_network(dict(rho1=100, items=[dict(kind="plate", orientation="diagonal",
                                                         x0=0, y0=0, Lx=1, Ly=1)]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
