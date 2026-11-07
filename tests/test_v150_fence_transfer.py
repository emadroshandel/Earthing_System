"""1.5.0: four-layer soil, separate metal networks (fences) and transferred
potential along long conductors.

Benchmarks
  * IEEE Std 80-2013/Cor 1-2015 Annex H, Grid 4 (Table H.8): Grid 3 with a
    separately earthed, isolated fence 3 m outside it and a fence wire 1 m
    outside the fence.  CDEGS / WinIGS values.
  * Annex H, Grid 5 (Table H.9): L-shaped grid with a bonded fence.
  * Closed-form lossy-line solutions for the transferred-potential ladder.
"""
import cmath
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np                                     # noqa: E402

from earthsys import api, bem, layered, soil, transfer  # noqa: E402

GRID4 = dict(Rg=(0.96, 0.97), Rf=(1.60, 1.62), GPR=(717.9, 722.6),
             T1=(259.7, 263.6), T3=(261.1, 264.9), T4=(49.9, 51.1),
             S1=(97.0, 97.4), S2=(37.4, 38.1), X=(309.2, 312.4))


def within(v, rng, tol):
    lo, hi = rng
    return lo * (1 - tol) <= v <= hi * (1 + tol)


def grid3(net):
    net.add_grid(70, 70, 14, 0.5, 0.0105 / 2)
    for i in range(6):
        for j in range(6):
            if i in (0, 5) or j in (0, 5):
                net.add_rod(14 * i, 14 * j, 0.5, 7.5, 0.0159 / 2)


class AnnexHGrid4(unittest.TestCase):
    """Isolated fence: every quantity of Table H.8."""

    @classmethod
    def setUpClass(cls):
        net = bem.Network(bem.SoilModel(300, 100, 6.096), 744.8)
        grid3(net)
        # posts every 10 ft (3.048 m; the figure's "3.28 m (10 ft)" mixes
        # the two units), 0.762 m deep, 51 mm; fence wire 1 m outside
        cls.k = net.add_fence([(-3, -3), (73, -3), (73, 73), (-3, 73)], 3.048,
                              0.762, 0.0255, wire_offset=1.0, wire_depth=0.5,
                              wire_radius=0.0105 / 2)
        cls.sol = net.solve(2.0)
        cls.net = net

    def test_resistances_and_potentials(self):
        n = self.net
        self.assertTrue(within(n.Z[0, 0], GRID4["Rg"], 0.02))
        self.assertTrue(within(n.Z[1, 1], GRID4["Rf"], 0.02))
        self.assertTrue(within(n.V, GRID4["GPR"], 0.01))
        self.assertTrue(within(n.V - n.Vnet[1], GRID4["X"], 0.02))

    def test_touch_and_step(self):
        n, V, Vf = self.net, self.net.V, self.net.Vnet[1]
        c = n.potential_at(np.array([[7, 7, 0], [0, 0, 0], [-0.7071, -0.7071, 0],
                                     [-4, -4, 0], [-4.7071, -4.7071, 0]], float))
        self.assertTrue(within(V - c[0], GRID4["T1"], 0.03))
        self.assertTrue(within(c[1] - c[2], GRID4["S1"], 0.04))
        self.assertTrue(within(Vf - c[3], GRID4["T4"], 0.05))
        self.assertTrue(within(c[3] - c[4], GRID4["S2"], 0.05))
        d = np.linspace(0, 14, 71)
        T = V - n.potential_at(np.column_stack([d, d, 0 * d]))
        self.assertTrue(within(T.max(), GRID4["T3"], 0.03))

    def test_floating_network_carries_no_net_current(self):
        I_f = sum(i for i, s in zip(self.net.I, self.net.segments) if s.net == 1)
        self.assertAlmostEqual(I_f, 0.0, places=6)
        self.assertAlmostEqual(sum(self.net.I), 744.8, places=6)

    def test_mutual_resistance_is_reciprocal(self):
        Z = self.net.Z
        self.assertAlmostEqual(Z[0, 1], Z[1, 0], delta=1e-4 * Z[0, 0])  # collocation is nearly symmetric

    def test_fence_touch_report(self):
        f = self.net.fence_touch(0)
        self.assertFalse(f["bonded"])
        self.assertAlmostEqual(f["V_fence"], self.net.Vnet[1])
        # inside, the grid lifts the soil above the floating fence
        self.assertLess(f["touch_inside"]["touch_max"], 0)
        self.assertGreater(abs(f["touch_max"]), 50)


class BondedFence(unittest.TestCase):
    def test_bonded_fence_is_part_of_the_main_network(self):
        soil_m = bem.SoilModel(100)
        a = bem.Network(soil_m, 100.0)
        a.add_grid(20, 20, 10, 0.5, 0.005)
        k = a.add_fence([(-2, -2), (22, -2), (22, 22), (-2, 22)], 3.0, 0.8,
                        0.025, bonded=True)
        self.assertEqual(k, 0)
        ra = a.solve(2.0)
        self.assertNotIn("networks", ra)
        self.assertAlmostEqual(a.fence_touch(0)["V_fence"], a.V)
        # the same metal entered as plain conductors gives the same answer
        b = bem.Network(soil_m, 100.0)
        b.add_grid(20, 20, 10, 0.5, 0.005)
        for x, y in [(q[0][0], q[0][1]) for q in a.raw if q[3] == "fence_post"]:
            b.add_rod(x, y, 0.0, 0.8, 0.025)
        self.assertAlmostEqual(b.solve(2.0)["Rg"], ra["Rg"], places=9)

    def test_annex_h_grid5_resistance(self):
        net = bem.Network(bem.SoilModel(300, 100, 6.096), 744.8)
        r = 0.0105 / 2
        for j in range(16):
            net.add_conductor((0, 7 * j, .5), (70 if j <= 5 else 35, 7 * j, .5), r)
        for i in range(11):
            net.add_conductor((7 * i, 0, .5), (7 * i, 105 if i <= 5 else 35, .5), r)
        L = [(0, 0), (70, 0), (70, 35), (35, 35), (35, 105), (0, 105)]
        for a, b in zip(L, L[1:] + L[:1]):
            n = int(round(max(abs(b[0] - a[0]), abs(b[1] - a[1])) / 7))
            for k in range(n):
                x = a[0] + (b[0] - a[0]) * k / n
                y = a[1] + (b[1] - a[1]) * k / n
                if (round(x / 7) + round(y / 7)) % 2 == 0:
                    net.add_rod(x, y, 0.5, 7.5, 0.0159 / 2)
        net.add_fence(bem._offset_path(L + [L[0]], -1.0)[:-1], 3.048, 0.762,
                      0.0255, bonded=True)
        s = net.solve(2.0)
        self.assertAlmostEqual(s["Rg"], 0.81, delta=0.015)       # CDEGS, ETAP, WinIGS
        self.assertTrue(600.0 <= s["GPR"] <= 612.0)              # 602.7 ... 606.4

    def test_offset_path(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        out = bem._offset_path(sq + [sq[0]], 1.0)
        self.assertEqual(out[0], (-1.0, -1.0))
        self.assertEqual(bem._offset_path(sq[::-1] + [sq[-1]], 1.0)[0], (-1.0, 11.0))

    def test_empty_network_is_reported(self):
        n = bem.Network(bem.SoilModel(100), 10.0)
        n.add_rod(0, 0, 0, 3, 0.008)
        n.add_network("nothing")
        with self.assertRaises(ValueError):
            n.solve(1.0)


class LossyLine(unittest.TestCase):
    z = complex(2e-4, 6e-4)
    g = 1 / 5000.0
    L = 3000.0

    def test_open_end_matches_closed_form(self):
        r = transfer.solve_ladder(self.L, self.z, self.g, lambda x: 0.0,
                                  near="bonded", V_near=1.0, far="open", n=3000)
        gam = cmath.sqrt(self.z * self.g)
        ex = np.array([cmath.cosh(gam * (self.L - x)) / cmath.cosh(gam * self.L)
                       for x in r["x"]])
        self.assertLess(np.max(np.abs(r["V"] - ex)), 1e-6)
        Zin = cmath.sqrt(self.z / self.g) / cmath.tanh(gam * self.L)
        self.assertLess(abs(r["I_near"] - 1 / Zin) / abs(1 / Zin), 1e-5)

    def test_insulated_conductor_is_a_divider(self):
        r = transfer.solve_ladder(self.L, self.z, 0.0, lambda x: 0.0,
                                  near="bonded", V_near=1.0, far="remote", R_far=10.0)
        self.assertLess(abs(r["V"][-1] - 10 / (10 + self.z * self.L)), 1e-9)

    def test_disconnected_conductor_rejected(self):
        with self.assertRaises(ValueError):
            transfer.solve_ladder(100, self.z, 0.0, lambda x: 0.0,
                                  near="insulated", far="open")

    def test_steel_skin_effect(self):
        zi = transfer.internal_impedance(0.1, 50.0, "steel", wall=0.006)
        rdc = 1.8e-7 / (math.pi * (0.1 ** 2 - 0.094 ** 2))
        self.assertGreater(zi.real, 3 * rdc)
        self.assertAlmostEqual(zi.real, zi.imag, delta=0.05 * zi.real)

    def test_leakage_formula_against_the_solver(self):
        n = bem.Network(bem.SoilModel(100.0), 1.0)
        n.add_conductor((0, 0, 0.5), (150, 0, 0.5), 0.005)
        R = n.solve(1.0)["Rg"]
        Rs = 1 / (transfer.soil_leakage(100.0, 0.005, 0.5, 150.0) * 150.0)
        self.assertLess(abs(Rs / R - 1), 0.02)


class TransferAgainstSolver(unittest.TestCase):
    """A short bare wire is nearly equipotential, so the full solver with
    the wire as part of the metal is the reference for the ladder."""

    @classmethod
    def setUpClass(cls):
        cls.rho, cls.Lw, cls.a, cls.d = 100.0, 150.0, 0.005, 0.5
        n0 = bem.Network(bem.SoilModel(cls.rho), 1000.0)
        n0.add_grid(40, 40, 10, 0.5, cls.a)
        cls.s0 = n0.solve(2.0)
        cls.n0 = n0

    def _ladder(self, start, near):
        g = transfer.soil_leakage(self.rho, self.a, self.d, self.Lw)
        prof = transfer.soil_profile_from_network(self.n0, start, (1, 0),
                                                  self.Lw, depth=self.d)
        return transfer.transferred_potential(
            GPR=self.s0["GPR"], Rg=self.s0["Rg"], IG=1000.0, soil_profile=prof,
            length=self.Lw, kind="custom", rho_soil=self.rho, radius=self.a,
            depth=self.d, z_per_km=1e-6, leak_ohm_km=1 / (g * 1000), near=near,
            far="open")

    def test_bonded_wire_lowers_gpr_like_the_solver(self):
        n1 = bem.Network(bem.SoilModel(self.rho), 1000.0)
        n1.add_grid(40, 40, 10, 0.5, self.a)
        n1.add_conductor((40, 20, self.d), (40 + self.Lw, 20, self.d), self.a)
        ref = n1.solve(2.0)["GPR"]
        r = self._ladder((40, 20), "bonded")
        self.assertLess(abs(r["GPR"] / ref - 1), 0.03)
        self.assertLess(r["GPR"], self.s0["GPR"])

    def test_floating_wire_picks_up_soil_potential(self):
        n2 = bem.Network(bem.SoilModel(self.rho), 1000.0)
        n2.add_grid(40, 40, 10, 0.5, self.a)
        k = n2.add_network("pipe")
        n2.use_network(k)
        n2.add_conductor((42, 20, self.d), (42 + self.Lw, 20, self.d), self.a)
        n2.use_network(0)
        n2.solve(2.0)
        r = self._ladder((42, 20), "insulated")
        self.assertLess(abs(r["V_far_pct"] - 100 * n2.Vnet[1] / n2.V), 2.0)


class TransferAPI(unittest.TestCase):
    base = dict(rho1=100, IG=1000,
                items=[dict(kind="grid", Lx=30, Ly=30, D=10, depth=0.5, radius=0.005)],
                segment_length=3, limits=dict(E_touch=400))

    def test_insulated_screen_transfers_nearly_full_gpr(self):
        p = dict(self.base)
        p["route"] = dict(start=[30, 15], direction=[1, 0], length=1500, radius=0.01,
                          kind="insulated", metal="copper", r_dc_per_km=0.5,
                          near="bonded", far="remote", R_far=20.0, depth=0.8)
        r = api.api_transfer(p)
        self.assertGreater(r["V_far_pct"], 90)
        self.assertGreater(r["transfer_far"], 400)
        self.assertFalse(r["passed"])
        self.assertTrue(r["remedy"])
        self.assertIn("narrative", r)

    def test_validation(self):
        p = dict(self.base)
        p["route"] = dict(start=[30, 15], length=0, radius=0.1)
        with self.assertRaises(ValueError):
            api.api_transfer(p)
        p["route"] = dict(start=[30, 15], length=500, radius=0.1, kind="coated")
        with self.assertRaises(ValueError):                     # no coating value
            api.api_transfer(p)

    def test_bem_api_reports_fence(self):
        p = dict(self.base, nx=21, ny=21)
        p["items"] = p["items"] + [dict(kind="fence", x0=-3, y0=-3, Lx=36, Ly=36,
                                        post_spacing=4, post_depth=0.76,
                                        post_radius=0.025, wire=0, bonded=0)]
        d = api.api_bem(p)
        self.assertEqual(len(d["networks"]), 2)
        self.assertEqual(len(d["fences"]), 1)
        self.assertTrue(any(c["name"].startswith("Fence touch") for c in d["checks"]))
        p["items"][-1] = dict(p["items"][-1], wire=1, wire_offset="")
        with self.assertRaises(ValueError):
            api.api_bem(p)


class FourLayer(unittest.TestCase):
    def test_recovers_a_four_layer_earth(self):
        xs = [0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 100]
        y = list(layered.apparent(layered.LayeredEarth([100, 1000, 50, 500], [1, 4, 8]),
                                  "wenner", xs))
        two = soil.invert_two_layer(xs, y, "wenner")
        s3 = layered.select_three(xs, y, two)
        s4 = layered.select_four(xs, y, s3["three"])
        self.assertTrue(s4["chosen"])
        for a, b in zip(s4["four"]["rho"], [100, 1000, 50, 500]):
            self.assertAlmostEqual(a / b, 1.0, delta=0.01)
        for a, b in zip(s4["four"]["h"], [1, 4, 8]):
            self.assertAlmostEqual(a / b, 1.0, delta=0.01)

    def test_degenerate_fourth_layer_equals_three(self):
        a = bem.Network(bem.SoilModel(100, 300, 2, rho3=50, h2=5), 1.0)
        a.add_rod(0, 0, 0, 6, 0.008)
        b = bem.Network(bem.SoilModel(100, 300, 2, rho3=50, h2=5, rho4=50, h3=4), 1.0)
        b.add_rod(0, 0, 0, 6, 0.008)
        self.assertAlmostEqual(a.solve(1.0)["Rg"], b.solve(1.0)["Rg"], places=6)

    def test_version(self):
        self.assertEqual(api.APP_VERSION, "1.11.0")


if __name__ == "__main__":
    unittest.main()
