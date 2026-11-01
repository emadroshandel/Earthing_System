"""1.8.7: solver size (symmetry reduction, compressed H-matrix with GMRES,
solution reuse, the larger non-equipotential model) and two-region soil
with a vertical boundary, solved with images."""
import math
import unittest

import numpy as np

from earthsys import bem, hf, hmatrix, studies, powerfreq
from earthsys.api import dispatch


def _annex_h(rods=True, D=14):
    it = [dict(kind="grid", Lx=70, Ly=70, D=D, depth=0.5, radius=0.0105 / 2)]
    if rods:
        pts = sorted({(x, y) for x in range(0, 71, 14) for y in range(0, 71, 14)
                      if x in (0, 70) or y in (0, 70)})
        it += [dict(kind="rod", x=x, y=y, top_depth=0.5, length=7.5,
                    radius=0.0159 / 2) for x, y in pts]
    return it


def _solve(spec, seg=2.0, **kw):
    bem.clear_cache()
    n = bem.build_network(spec)
    n.discretise(seg, 20000)
    s = n.solve(**kw)
    V = s["GPR"]
    p = n.potential_at([[7, 7, 0.0], [0, 0, 0.0], [-0.7071, -0.7071, 0.0]])
    return n, s, V - p[0], p[1] - p[2]


def _rel(a, b):
    return abs(a - b) / max(abs(b), 1e-30)


class TestSymmetry(unittest.TestCase):

    def test_annex_b_grid_reduces_eightfold_and_exactly(self):
        spec = dict(rho1=140, IG=744.8, items=_annex_h(True))
        n0, s0, T0, S0 = _solve(spec, method="dense", symmetry=False)
        n1, s1, T1, S1 = _solve(spec, method="dense", symmetry=True)
        self.assertEqual(s1["solver"]["symmetry"], 8)
        self.assertEqual(s1["solver"]["unknowns"], 66)
        self.assertLess(_rel(s1["Rg"], s0["Rg"]), 1e-12)
        self.assertLess(_rel(T1, T0), 1e-12)
        self.assertLess(_rel(S1, S0), 1e-12)
        self.assertLess(np.abs(n1.I - n0.I).max() / np.abs(n0.I).max(), 1e-11)

    def test_two_layer_and_rectangle(self):
        spec = dict(rho1=300, rho2=100, h_layer=6.096, IG=744.8,
                    items=[dict(kind="grid", Lx=60, Ly=30, D=10, depth=0.5, radius=0.005)])
        _, s0, T0, _ = _solve(spec, method="dense", symmetry=False)
        _, s1, T1, _ = _solve(spec, method="dense")
        self.assertEqual(s1["solver"]["symmetry"], 4)       # mirrors x, y and 180°
        self.assertNotIn("diagonal", s1["solver"]["symmetry_ops"])
        self.assertLess(_rel(s1["Rg"], s0["Rg"]), 1e-12)
        self.assertLess(_rel(T1, T0), 1e-11)

    def test_asymmetric_layout_is_not_reduced(self):
        items = [dict(kind="grid", Lx=40, Ly=40, D=10, depth=0.5, radius=0.005),
                 dict(kind="rod", x=10, y=0, top_depth=0.5, length=3, radius=0.008)]
        net = bem.build_network(dict(rho1=100, items=items))
        net.discretise(2.0, 20000)
        self.assertIsNone(net.symmetry())

    def test_separate_networks(self):
        # a floating fence round a grid: each network maps onto itself
        items = [dict(kind="grid", Lx=40, Ly=40, D=10, depth=0.5, radius=0.005),
                 dict(kind="fence", x0=-5, y0=-5, Lx=50, Ly=50, post_spacing=5.0)]
        spec = dict(rho1=100, IG=1000, items=items)
        n0, s0, _, _ = _solve(spec, method="dense", symmetry=False)
        n1, s1, _, _ = _solve(spec, method="dense")
        self.assertEqual(s1["solver"]["symmetry"], 8)
        self.assertLess(np.abs(n1.Z - n0.Z).max() / np.abs(n0.Z).max(), 1e-11)


class TestCompressed(unittest.TestCase):

    def test_hmatrix_agrees_with_dense_on_annex_h(self):
        for soil in (dict(rho1=140), dict(rho1=300, rho2=100, h_layer=6.096)):
            spec = dict(soil, IG=744.8, items=_annex_h(True))
            n0, s0, T0, S0 = _solve(spec, method="dense", symmetry=False)
            n1, s1, T1, S1 = _solve(spec, method="hmatrix")
            self.assertEqual(s1["solver"]["method"], "hmatrix")
            self.assertLess(_rel(s1["Rg"], s0["Rg"]), 1e-8, soil)
            self.assertLess(_rel(T1, T0), 1e-7, soil)
            self.assertLess(_rel(S1, S0), 1e-7, soil)
            self.assertLess(s1["solver"]["residual"], 1e-8)

    def test_hmatrix_on_annex_b_with_rods(self):
        rods = [(x, y) for x in (0, 17.5, 35, 52.5, 70) for y in (0, 70)] + \
               [(x, y) for x in (0, 70) for y in (17.5, 35, 52.5)]
        items = [dict(kind="grid", Lx=70, Ly=70, D=7, depth=0.5, radius=0.005)] + [
            dict(kind="rod", x=x, y=y, top_depth=0.5, length=7.5, radius=0.008) for x, y in rods]
        spec = dict(rho1=400, IG=1908, items=items)
        _, s0, T0, S0 = _solve(spec, method="dense", symmetry=False)
        _, s1, T1, S1 = _solve(spec, method="hmatrix")
        self.assertLess(_rel(s1["Rg"], s0["Rg"]), 1e-8)
        self.assertLess(_rel(T1, T0), 1e-7)
        self.assertLess(_rel(S1, S0), 1e-7)

    def test_multiple_networks_and_auto_switch(self):
        items = [dict(kind="grid", Lx=40, Ly=30, D=10, depth=0.5, radius=0.005),
                 dict(kind="rod", x=3, y=2, top_depth=0.5, length=3, radius=0.008),
                 dict(kind="fence", x0=-5, y0=-5, Lx=50, Ly=40, post_spacing=5.0)]
        spec = dict(rho1=100, IG=1000, items=items)
        n0, s0, _, _ = _solve(spec, method="dense", symmetry=False)
        n1, s1, _, _ = _solve(spec, dense_limit=50)            # auto → compressed
        self.assertEqual(s1["solver"]["method"], "hmatrix")
        self.assertLess(np.abs(n1.Z - n0.Z).max() / np.abs(n0.Z).max(), 1e-8)

    def test_three_layer_and_two_region_soils(self):
        items = [dict(kind="grid", Lx=30, Ly=20, D=10, depth=0.5, radius=0.005),
                 dict(kind="rod", x=0, y=0, top_depth=0.5, length=6, radius=0.008)]
        for soil in (dict(rho1=200, rho2=50, h_layer=2, rho3=500, h_layer2=4),
                     dict(rho1=100, rho_v=500, x_v=12, angle_v=30)):
            spec = dict(soil, IG=1000, items=items)
            _, s0, T0, _ = _solve(spec, 1.0, method="dense", symmetry=False)
            _, s1, T1, _ = _solve(spec, 1.0, method="hmatrix")
            self.assertLess(_rel(s1["Rg"], s0["Rg"]), 1e-8, soil)
            self.assertLess(_rel(T1, T0), 1e-7, soil)

    def test_potential_map_through_the_trees(self):
        spec = dict(rho1=300, rho2=100, h_layer=6.096, IG=744.8, items=_annex_h(True, 7))
        net = bem.build_network(spec)
        net.discretise(1.0, 20000)
        net.solve()
        xs = np.linspace(-10, 80, 40)
        X, Y = np.meshgrid(xs, xs)
        P = np.column_stack([X.ravel(), Y.ravel(), 0 * X.ravel()])
        keep = bem.TREE_WORK
        try:
            bem.TREE_WORK = 1e30
            a = net.potential_at(P)
            bem.TREE_WORK = 0
            b = net.potential_at(P)
        finally:
            bem.TREE_WORK = keep
        self.assertLess(np.abs(a - b).max() / np.abs(a).max(), 1e-6)

    def test_layer_table_matches_the_series(self):
        s = bem.SoilModel(300, 100, 6.096)
        net = bem.Network(s, 1.0)
        f = np.column_stack([np.linspace(0.0, 150.0, 400), np.zeros(400), np.full(400, 0.5)])
        q = np.array([[0.0, 0.0, 0.5], [0.3, 0.0, 0.5], [40.0, 7.0, 0.5]])
        a = net._green_terms(f, q, False, 1)               # table (same depth)
        terms = bem.image_terms(s, 1, 1)
        dx = f[:, None, 0] - q[None, :, 0]
        dy = f[:, None, 1] - q[None, :, 1]
        b = bem._image_sum(dx * dx + dy * dy, f[:, 2][:, None], q[None, :, 2], terms)
        b += s.tail_amplitude(1, 1) * s.tail(np.sqrt(dx * dx + dy * dy))
        self.assertLess(np.abs(a - b).max() / np.abs(b).max(), 1e-9)


class TestHmatrixModule(unittest.TestCase):

    def test_aca_recovers_a_smooth_block(self):
        x = np.linspace(0, 1, 80)
        y = np.linspace(5, 7, 60)
        F = 1.0 / np.abs(x[:, None] - y[None, :])
        U, V = hmatrix.aca(lambda i: F[i], lambda j: F[:, j], 80, 60, 1e-10)
        self.assertLess(U.shape[1], 15)
        self.assertLess(np.abs(U @ V.T - F).max() / np.abs(F).max(), 1e-9)

    def test_gmres(self):
        rng = np.random.default_rng(3)
        A = rng.normal(size=(120, 120)) + 30 * np.eye(120)
        b = rng.normal(size=120)
        x, it, rel = hmatrix.gmres(lambda v: A @ v, b, tol=1e-12, restart=20)
        self.assertLess(rel, 1e-12)
        self.assertLess(np.abs(x - np.linalg.solve(A, b)).max(), 1e-9)

    def test_tree_is_a_permutation(self):
        rng = np.random.default_rng(1)
        c = rng.uniform(0, 100, size=(1000, 3))
        root, perm = hmatrix.cluster_tree(c, c, c, 32)
        self.assertEqual(sorted(perm.tolist()), list(range(1000)))
        far, near = hmatrix.block_partition(root, root, 1.5, 0.0)
        covered = sum(a.size * b.size for a, b in far + near)
        self.assertEqual(covered, 1000 * 1000)


class TestReuse(unittest.TestCase):

    def test_cache_serves_another_current_and_another_rho(self):
        bem.clear_cache()
        items = [dict(kind="grid", Lx=20, Ly=20, D=5, depth=0.5, radius=0.005),
                 dict(kind="rod", x=0, y=0, top_depth=0.5, length=3, radius=0.008)]
        a = bem.build_network(dict(rho1=100, IG=1000, items=items))
        a.discretise(1.0)
        sa = a.solve()
        self.assertFalse(sa["solver"]["cached"])
        b = bem.build_network(dict(rho1=250, IG=3000, items=items))
        b.discretise(1.0)
        sb = b.solve()
        self.assertTrue(sb["solver"]["cached"])            # uniform: currents do not depend on ρ
        self.assertAlmostEqual(sb["Rg"], 2.5 * sa["Rg"], places=12)
        self.assertAlmostEqual(sb["GPR"], 3 * 2.5 * sa["GPR"], places=8)
        c = bem.build_network(dict(rho1=100, rho2=30, h_layer=2, IG=1000, items=items))
        c.discretise(1.0)
        self.assertFalse(c.solve()["solver"]["cached"])
        d = bem.build_network(dict(rho1=100, rho2=30, h_layer=2, IG=10, items=items))
        d.discretise(1.0)
        sd = d.solve()
        self.assertTrue(sd["solver"]["cached"])
        bem.clear_cache()
        e = bem.build_network(dict(rho1=100, IG=1000, items=items))
        e.discretise(1.0)
        self.assertFalse(e.solve()["solver"]["cached"])

    def test_studies_share_the_measured_case(self):
        studies.clear_summaries()
        p = dict(rho1=100, rho2=300, h_layer=1.5, IG=1000, segment_length=4, nx=15,
                 items=[dict(kind="grid", Lx=20, Ly=20, D=10, depth=0.5, radius=0.005)])
        cv = dispatch("/api/bem/convergence", dict(p))
        self.assertEqual(cv["reused"], [False, False])
        ss = dispatch("/api/bem/seasonal", dict(p, seasonal=dict(dry_factor=2.0, dry_depth=1.0)))
        self.assertAlmostEqual(ss["cases"][0]["Rg"], cv["Rg"]["coarse"], places=12)
        cv2 = dispatch("/api/bem/convergence", dict(p))
        self.assertEqual(cv2["reused"], [True, True])
        self.assertEqual(cv2["Rg"], cv["Rg"])


class TestNonEquipotential(unittest.TestCase):

    def _full(self, model, f, feed, I=1.0):
        """The 1.8.6 formulation: the whole (Nn + 2N) system."""
        w = model.w
        N, Nn = model.N, model.Nn
        ZT, ZL = model.matrices(f)
        n = Nn + 2 * N
        A = np.zeros((n, n), complex)
        b = np.zeros(n, complex)
        iL = Nn + np.arange(N)
        iT = Nn + N + np.arange(N)
        r1 = np.arange(N)
        A[r1, w.na] += 0.5
        A[r1, w.nb] += 0.5
        A[np.ix_(r1, iT)] -= ZT
        r2 = N + np.arange(N)
        A[r2, w.na] += 1.0
        A[r2, w.nb] -= 1.0
        A[np.ix_(r2, iL)] -= ZL
        r3 = 2 * N
        A[r3 + w.na, iL] += 1.0
        A[r3 + w.nb, iL] -= 1.0
        A[r3 + w.na, iT] += 0.5
        A[r3 + w.nb, iT] += 0.5
        b[r3 + feed] = I
        x = np.linalg.solve(A, b)
        return x[:Nn], x[iL], x[iT]

    def test_eliminated_currents_give_the_same_solution(self):
        items = [dict(kind="grid", Lx=30, Ly=20, D=10, depth=0.5, radius=0.005),
                 dict(kind="rod", x=0, y=0, top_depth=0.5, length=3, radius=0.008)]
        w = hf.Wires.from_items(items)
        w.discretise(2.5)
        for metal in ("copper", "steel"):
            m = hf.Model(w, hf.make_soil(100.0, (), eps_r=10.0, model="constant"), metal=metal)
            for f in (0.0, 50.0, 1e5):
                V0, IL0, IT0 = self._full(m, f, 0)
                _, V1, IL1, IT1 = m.solve(f, 0)
                self.assertLess(np.abs(V1 - V0).max() / np.abs(V0).max(), 1e-10)
                self.assertLess(np.abs(IT1 - IT0).max() / np.abs(IT0).max(), 1e-9)

    def test_cap_raised(self):
        self.assertEqual(powerfreq.MAX_SEGMENTS, 3000)
        self.assertEqual(bem.MAX_SEGMENTS, 20000)


class TestVerticalBoundary(unittest.TestCase):
    ROD = [dict(kind="rod", x=0, y=0, top_depth=0.0, length=3, radius=0.008)]

    def _rg(self, spec, seg=0.5):
        bem.clear_cache()
        n = bem.build_network(spec)
        n.discretise(seg, 20000)
        return n, n.solve()

    def test_equal_resistivities_are_uniform_soil(self):
        _, a = self._rg(dict(rho1=100, items=self.ROD))
        n, b = self._rg(dict(rho1=100, rho_v=100, x_v=1, items=self.ROD))
        self.assertIsNone(n.soil.vertical)
        self.assertEqual(a["Rg"], b["Rg"])

    def test_electrode_in_the_boundary_sees_the_harmonic_mean(self):
        # exact: an electrode lying in the plane sees 2ρρ'/(ρ + ρ') everywhere
        re = 2 * 100 * 400 / 500
        _, a = self._rg(dict(rho1=re, items=self.ROD))
        _, b = self._rg(dict(rho1=100, rho_v=400, x_v=0, items=self.ROD))
        self.assertLess(_rel(b["Rg"], a["Rg"]), 1e-12)
        wire = [dict(kind="conductor", p1=[-10, 0, 0.5], p2=[10, 0, 0.5])]
        _, a = self._rg(dict(rho1=re, items=wire))
        for ang in (90, -90):
            _, b = self._rg(dict(rho1=100, rho_v=400, y_v=0, angle_v=ang, items=wire))
            self.assertLess(_rel(b["Rg"], a["Rg"]), 1e-12)

    def test_electrode_symmetric_about_the_boundary_is_exact(self):
        # an electrode symmetric about the plane: the uniform solution in the
        # harmonic mean has no current across the plane, so it is exact
        items = [dict(kind="grid", Lx=20, Ly=20, D=5, depth=0.5, radius=0.005),
                 dict(kind="rod", x=0, y=0, top_depth=0.5, length=3, radius=0.008),
                 dict(kind="rod", x=20, y=0, top_depth=0.5, length=3, radius=0.008)]
        re = 2 * 400 * 1500 / 1900
        _, a = self._rg(dict(rho1=re, items=items), 1.0)
        _, b = self._rg(dict(rho1=400, rho_v=1500, x_v=10, items=items), 1.0)
        self.assertLess(_rel(b["Rg"], a["Rg"]), 2e-5)

    def test_rod_near_the_boundary_against_its_image(self):
        # to first order in K the rod sees its mirror image carrying K times
        # its current: R ≈ Z11 + K Z12 of the rod and its image in uniform soil
        K = (400 - 100) / 500
        for d in (1.0, 5.0):
            net = bem.build_network(dict(rho1=100, items=self.ROD))
            k = net.add_network("image", 0.0)
            net.use_network(k)
            net.add_rod(2 * d, 0, 0.0, 3, 0.008)
            net.discretise(0.5, 20000)
            net.solve()
            approx = net.Z[0, 0] + K * net.Z[0, 1]
            _, s = self._rg(dict(rho1=100, rho_v=400, x_v=d, items=self.ROD))
            self.assertLess(_rel(s["Rg"], approx), 5e-4, d)

    def test_far_limits(self):
        _, u1 = self._rg(dict(rho1=100, items=self.ROD))
        _, u2 = self._rg(dict(rho1=400, items=self.ROD))
        _, a = self._rg(dict(rho1=100, rho_v=400, x_v=300, items=self.ROD))
        _, b = self._rg(dict(rho1=100, rho_v=400, x_v=-300, items=self.ROD))
        self.assertLess(_rel(a["Rg"], u1["Rg"]), 1e-3)
        self.assertLess(_rel(b["Rg"], u2["Rg"]), 1e-3)

    def test_crossing_conductor_continuity_and_reciprocity(self):
        wire = [dict(kind="conductor", p1=[-10, 0, 0.5], p2=[10, 0, 0.5])]
        n, s = self._rg(dict(rho1=100, rho_v=400, x_v=0.3, items=wire))
        self.assertEqual({sg.layer for sg in n.segments}, {1, 2})
        self.assertTrue(any(abs(sg.p2[0] - 0.3) < 1e-9 for sg in n.segments))
        # reciprocity of the Green's function across and along the boundary
        a = np.array([[-2.0, 1.0, 0.7]])
        b = np.array([[3.5, -0.4, 1.9]])
        c = np.array([[-0.5, 4.0, 0.2]])
        g = lambda f, q: float(n._green_terms(f, q, False, n.soil.zone_of(q[0]))[0, 0])
        self.assertAlmostEqual(g(a, b), g(b, a), places=14)
        self.assertAlmostEqual(g(a, c), g(c, a), places=14)
        x = 0.3 + np.array([-1e-4, -1e-7, 0.0, 1e-7, 1e-4])
        V = n.potential_at(np.column_stack([x, np.full(5, 2.0), np.zeros(5)]))
        self.assertLess(np.ptp(V) / V.mean(), 1e-4)
        # most of the current leaves into the conductive side, about in the
        # ratio of the conductivities away from the boundary
        lay = np.array([sg.layer for sg in n.segments])
        L = np.array([sg.length for sg in n.segments])
        far1 = (lay == 1) & (np.array([sg.mid[0] for sg in n.segments]) < -5)
        far2 = (lay == 2) & (np.array([sg.mid[0] for sg in n.segments]) > 5.6)
        ratio = (n.I[far1] / L[far1]).mean() / (n.I[far2] / L[far2]).mean()
        self.assertGreater(ratio, 2.0)
        self.assertLess(ratio, 4.5)

    def test_api_and_guards(self):
        items = [dict(kind="grid", Lx=20, Ly=20, D=10, depth=0.5, radius=0.005)]
        p = dict(rho1=100, rho_v=1000, x_v=10, y_v=0, angle_v=0, IG=1000, items=items,
                 segment_length=2, nx=21)
        d = dispatch("/api/bem", dict(p))
        self.assertIn("Two-region soil", d["soil"])
        self.assertEqual(d["solver"]["symmetry"], 2)        # mirror y only
        with self.assertRaises(ValueError):
            dispatch("/api/bem", dict(p, rho2=50, h_layer=2))
        with self.assertRaises(ValueError):
            dispatch("/api/bem", dict(p, rho_v=-5))
        for ep in ("/api/bem/seasonal", "/api/bem/powerfreq"):
            with self.assertRaises(ValueError):
                dispatch(ep, dict(p))
        cv = dispatch("/api/bem/convergence", dict(p))
        self.assertIn("Rg", cv)


if __name__ == "__main__":
    unittest.main(verbosity=2)
