"""1.8.8: automatic refinement at the worst touch and step points, the
transferred potential solved together with the station, and two fixes (the
lossy-line node merge, the blocked Sommerfeld tables)."""
import cmath
import math
import unittest

import numpy as np

from earthsys import bem, hf, transfer
from earthsys.api import dispatch


def _grid(rods=False):
    it = [dict(kind="grid", Lx=70, Ly=70, D=14, depth=0.5, radius=0.0105 / 2)]
    if rods:
        pts = sorted({(x, y) for x in range(0, 71, 14) for y in range(0, 71, 14)
                      if x in (0, 70) or y in (0, 70)})
        it += [dict(kind="rod", x=x, y=y, top_depth=0.5, length=7.5, radius=0.0159 / 2)
               for x, y in pts]
    return it


WS = dict(xlim=[-10, 80], ylim=[-10, 80], nx=31, ny=31, step=1.0, touch_box=None,
          touch_margin=1.0)


class TestAutoRefine(unittest.TestCase):

    def test_converges_and_keeps_the_symmetry(self):
        bem.clear_cache()
        net = bem.build_network(dict(rho1=140, IG=744.8, items=_grid(True)))
        net.discretise(7.0, grade_ends=True)
        n0 = len(net.segments)
        sol, ws, r = net.auto_refine(WS, tol=0.005, max_levels=4)
        L = r["levels"]
        self.assertTrue(r["converged"])
        self.assertGreater(len(L), 1)
        self.assertEqual(L[0]["segments"], n0)
        self.assertGreater(L[-1]["segments"], n0)
        self.assertLess(abs(L[-1]["touch_change"]), 0.005)
        self.assertEqual(sol["solver"]["symmetry"], 8)       # refined symmetrically
        self.assertAlmostEqual(ws["touch_max"], L[-1]["touch"])

    def test_refined_values_approach_a_fine_mesh(self):
        # 7 m graded and refined at the worst points against a uniform 0.5 m mesh
        spec = dict(rho1=140, IG=744.8, items=_grid(True))
        fine = bem.build_network(spec)
        fine.discretise(0.5)
        fine.solve()
        wf = fine.worst_touch_step(**WS)
        net = bem.build_network(spec)
        net.discretise(7.0, grade_ends=True)
        _, ws, r = net.auto_refine(WS, tol=0.002, max_levels=4)
        self.assertLess(abs(ws["step_max"] / wf["step_max"] - 1), 0.01)
        self.assertLess(abs(ws["touch_max"] / wf["touch_max"] - 1), 0.015)

    def test_refine_near_respects_the_thin_wire_limit(self):
        net = bem.Network(bem.SoilModel(100.0), 1.0)
        net.add_conductor((0, 0, 0.5), (1, 0, 0.5), 0.02)
        net.discretise(1.0)
        self.assertEqual(len(net.segments), 1)
        net.refine_near([[0.5, 0.0]], 2.0, levels=5)
        self.assertEqual(len(net.segments), 4)                # 0.25 m >= 10 radii

    def test_api(self):
        p = dict(rho1=100, IG=1000, segment_length=4, nx=21, auto_refine=0.5,
                 items=[dict(kind="grid", Lx=30, Ly=20, D=10, depth=0.5, radius=0.005)])
        d = dispatch("/api/bem", p)
        self.assertIn("refinement", d)
        self.assertEqual(d["segments"], d["refinement"]["levels"][-1]["segments"])
        with self.assertRaises(ValueError):
            dispatch("/api/bem", dict(p, auto_refine=50))


class TestLadderFix(unittest.TestCase):

    def test_input_admittance_of_a_uniform_line(self):
        # soil at 0 V and an open far end: a = tanh(γL)/Z0 exactly (the
        # node set of this length used to contain two nodes 4e-16 m apart)
        L, z, g = 800.0, 2.683e-4 + 7.782e-4j, 3.5204e-3
        u = transfer.solve_ladder(L, z, g, lambda x: 0.0, near="bonded", V_near=1.0, far="open")
        gam, Z0 = cmath.sqrt(z * g), cmath.sqrt(z / g)
        self.assertGreater(np.diff(u["x"]).min(), 1e-6)
        self.assertLess(abs(u["I_near"] / (cmath.tanh(gam * L) / Z0) - 1), 2e-3)


class TestCoupledTransfer(unittest.TestCase):
    rho, Lw, a, d = 100.0, 150.0, 0.005, 0.5

    @classmethod
    def setUpClass(cls):
        bem.clear_cache()
        n = bem.Network(bem.SoilModel(cls.rho), 1000.0)
        n.add_grid(40, 40, 10, 0.5, cls.a)
        n.discretise(2.0)
        n.solve()
        cls.n0 = n

    def test_equals_the_solver_without_series_impedance(self):
        at, _ = transfer._polyline([[40, 20], [40 + self.Lw, 20]], self.Lw)
        r = transfer.coupled_transferred_potential(
            self.n0, route_at=at, length=self.Lw, depth=self.d, radius=self.a, kind="bare",
            z=1e-9 + 0j, ds0=2.0, ds_max=2.0)
        n1 = bem.Network(bem.SoilModel(self.rho), 1000.0)
        n1.add_grid(40, 40, 10, 0.5, self.a)
        n1.discretise(2.0)
        n1.segments = list(n1.segments) + [bem.Segment(s.p1, s.p2, s.radius, "w", 1, 0, 0.0)
                                           for s in r["net"].segments[len(n1.segments):]]
        self.assertLess(abs(abs(r["GPR"]) / n1.solve()["GPR"] - 1), 1e-5)
        # the same wire floating 2 m away: a separate network of the solver
        at2, _ = transfer._polyline([[42, 20], [42 + self.Lw, 20]], self.Lw)
        r2 = transfer.coupled_transferred_potential(
            self.n0, route_at=at2, length=self.Lw, depth=self.d, radius=self.a, kind="bare",
            z=1e-9 + 0j, near="insulated", ds0=2.0, ds_max=2.0)
        n2 = bem.Network(bem.SoilModel(self.rho), 1000.0)
        n2.add_grid(40, 40, 10, 0.5, self.a)
        k = n2.add_network("pipe")
        n2.discretise(2.0)
        n2.segments = list(n2.segments) + [bem.Segment(s.p1, s.p2, s.radius, "w", 1, k, 0.0)
                                           for s in r2["net"].segments[len(n2.segments):]]
        n2.solve()
        self.assertLess(abs(np.abs(r2["U"]).mean() / n2.Vnet[1] - 1), 1e-5)
        self.assertLess(abs(abs(r2["GPR"]) / n2.V - 1), 1e-5)

    def test_against_the_circuit_field_model(self):
        # a 400 m bare copper wire bonded to a 30 m grid in 100 Ω·m at 50 Hz:
        # hf.py solves grid and wire as one network of impedances
        L = 400.0
        base = dict(rho1=100, IG=1000, segment_length=3,
                    items=[dict(kind="grid", Lx=30, Ly=30, D=10, depth=0.5, radius=0.005)])
        r = dispatch("/api/transfer", dict(base, route=dict(
            start=[30, 20], direction=[1, 0], length=L, radius=0.005, kind="bare",
            metal="copper", depth=0.5, access_points=[20, 100])))
        self.assertEqual(r["model"], "coupled")
        items = base["items"] + [dict(kind="conductor", p1=[30, 20, 0.5],
                                      p2=[30 + L, 20, 0.5], radius=0.005)]
        w = hf.Wires.from_items(items)
        w.discretise(5.0)
        m = hf.Model(w, hf.make_soil(100.0, (), eps_r=10.0, model="constant"), metal="copper")
        k = w.nearest_node([15, 15, 0.5])
        _, V, IL, IT = m.solve(50.0, k, 1000.0)
        wire = np.where(w.raw_idx == len(w.raw) - 1)[0]
        first = wire[np.argmin(np.abs(w.mid[wire, 0] - 30))]
        kf = w.nearest_node([30 + L, 20, 0.5])
        self.assertLess(abs(r["GPR"] / abs(V[k]) - 1), 0.03)
        self.assertLess(abs(r["I_diverted"] / abs(IL[first]) - 1), 0.03)
        self.assertLess(abs(r["V_far_pct"] - 100 * abs(V[kf]) / abs(V[k])), 3.0)
        net = bem.Network(bem.SoilModel(100.0), 1000.0)
        net.segments = [bem.Segment(w.p1[i], w.p2[i], float(w.rad[i]), "", 1, 0, 0.0)
                        for i in range(m.N)]
        for acc in r["access"][:2]:
            x = 30 + acc["s"]
            kn = w.nearest_node([x, 20, 0.5])
            q = np.array([[x, 21.0, 0.0], [x, 19.0, 0.0]])
            Vs = net.potential_at(q, currents=IT.real) + 1j * net.potential_at(q, currents=IT.imag)
            t_hf = max(abs(V[kn] - Vs[0]), abs(V[kn] - Vs[1]))
            self.assertLess(abs(acc["touch"] / t_hf - 1), 0.06, acc)

    def test_coated_pipe_agrees_with_the_line_model(self):
        base = dict(rho1=100, IG=1000, segment_length=3,
                    items=[dict(kind="grid", Lx=30, Ly=30, D=10, depth=0.5, radius=0.005)])
        route = dict(start=[30, 15], direction=[1, 0], length=1500, radius=0.1, kind="coated",
                     coating_res=1e5, metal="steel", wall=0.006, depth=1.0,
                     access_points=[200, 800])
        c = dispatch("/api/transfer", dict(base, route=route))
        o = dispatch("/api/transfer", dict(base, route=dict(route, coupled=False)))
        self.assertEqual(o.get("model"), None)
        self.assertLess(abs(c["GPR"] / o["GPR"] - 1), 0.005)
        self.assertLess(abs(c["V_far_pct"] - o["V_far_pct"]), 0.5)
        for a, b in zip(c["access"], o["access"]):
            self.assertLess(abs(a["touch"] / b["touch"] - 1), 0.01)

    def test_induction_and_guards(self):
        base = dict(rho1=100, IG=1000, segment_length=3,
                    items=[dict(kind="grid", Lx=30, Ly=30, D=10, depth=0.5, radius=0.005)])
        route = dict(start=[30, 15], direction=[1, 0], length=1500, radius=0.1, kind="coated",
                     coating_res=1e5, metal="steel", wall=0.006, depth=1.0,
                     induced=dict(I_A=2000, d=30, s_from=200, s_to=1200))
        c = dispatch("/api/transfer", dict(base, route=route))
        o = dispatch("/api/transfer", dict(base, route=dict(route, coupled=False)))
        self.assertLess(abs(c["induced"]["touch_induced_max"] / o["induced"]["touch_induced_max"] - 1),
                        0.02)
        r = dispatch("/api/transfer", dict(base, route=dict(
            start=[30, 15], direction=[1, 0], length=1500, radius=0.01, kind="insulated",
            metal="copper", r_dc_per_km=0.5, far="remote", R_far=20.0)))
        self.assertIsNone(r.get("model"))                     # line model for screens
        with self.assertRaises(ValueError):
            dispatch("/api/transfer", dict(base, route=dict(route, coating_res=None)))


class TestSommerfeldBlocks(unittest.TestCase):

    def test_large_uniform_layout(self):
        # 830 m across in uniform soil: the J0(rλ) table alone was gigabytes
        items = [dict(kind="grid", Lx=30, Ly=30, D=10, depth=0.5, radius=0.005),
                 dict(kind="conductor", p1=[30, 20, 0.5], p2=[830, 20, 0.5], radius=0.005)]
        w = hf.Wires.from_items(items)
        w.discretise(20.0)
        m = hf.Model(w, hf.make_soil(100.0, (), eps_r=10.0, model="constant"), metal="copper")
        Z, V, _, _ = m.solve(50.0, w.nearest_node([15, 15, 0.5]), 1.0)
        self.assertTrue(0.1 < abs(Z) < 2.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
