"""1.9.2: shield wires coupled to each other — two shield wires on one line,
and parallel lines sharing the corridor — in the fault-location sweep."""
import cmath
import math
import unittest

import numpy as np

from earthsys import faultcurrent as fc
from earthsys.api import dispatch


def wire_level(Un, Rg, n, span, Rt, R_rem, rho, wires, Z1l, Z0l, Z1s, Z0s, Z1r, Z0r, j,
               c=1.1, f=50.0):
    """Independent solution: every shield wire of every span is its own
    branch (coupled through the full Carson matrix of the corridor), the
    wires of a line meet at its tower nodes; branch-node incidence A and
    branch impedance Z_b give (A Z_b⁻¹ Aᵀ + Y) V = I − A Z_b⁻¹ E.
    wires: list of (x, line, d_phase); towers of every line Rt[line]."""
    m = len(wires)
    Zkm = np.zeros((m, m), complex)
    zp = np.zeros(m, complex)
    for a, (xa, la, da) in enumerate(wires):
        Zkm[a, a] = fc.carson_self(0.33, 0.004, rho, f)
        zp[a] = fc.carson_mutual(da, rho, f)
        for b, (xb, lb, db) in enumerate(wires):
            if b != a:
                Zkm[a, b] = fc.carson_mutual(abs(xa - xb), rho, f)
    lines = sorted({w[1] for w in wires})
    L = len(lines)

    def node(line, k):
        return 0 if k == 0 else 1 if k == n else 2 + line * (n - 1) + k - 1
    N = 2 + L * (n - 1)
    nb = n * m
    A = np.zeros((N, nb))
    Zb = np.zeros((nb, nb), complex)
    E = np.zeros(nb, complex)
    line_km = n * span
    x = j * span
    Z1a, Z1b = Z1s + Z1l * x, Z1r + Z1l * (line_km - x)
    Z0a, Z0b = Z0s + Z0l * x, Z0r + Z0l * (line_km - x)
    Z1 = Z1a * Z1b / (Z1a + Z1b)
    Z0 = Z0a * Z0b / (Z0a + Z0b)
    If = 3 * c * Un * 1e3 / math.sqrt(3) / (2 * Z1 + Z0)
    Ia = If * Z0b / (Z0a + Z0b)
    Ib = If - Ia
    for k in range(n):
        Iph = Ia if k < j else -Ib
        for a, (xa, la, da) in enumerate(wires):
            br = k * m + a
            A[node(la, k), br] += 1.0          # leaves node k
            A[node(la, k + 1), br] -= 1.0
            E[br] = -zp[a] * span * Iph
        Zb[k * m:(k + 1) * m, k * m:(k + 1) * m] = Zkm * span
    Yb = np.linalg.inv(Zb)
    G = A @ Yb @ A.T
    G[0, 0] += 1 / Rg
    G[1, 1] += 1 / R_rem
    for line in range(L):
        for k in range(1, n):
            G[node(line, k), node(line, k)] += 1 / Rt[line]
    inj = np.zeros(N, complex)
    inj[node(0, j)] += If
    inj[0] -= Ia
    inj[1] -= Ib
    V = np.linalg.solve(G, inj - A @ Yb @ E)
    return abs(V[0] / Rg) / 1e3


BASE = dict(line_km=6.0, span_km=0.3, Rt=12.0, R_remote=0.4, rho=150.0,
            Z1_line=complex(0.06, 0.4), Z0_line=complex(0.25, 1.2),
            Z1_local=complex(0.5, 5.0), Z0_local=complex(0.3, 3.0),
            Z1_remote=complex(0.5, 5.0), Z0_remote=complex(0.5, 5.0), d_phase_sw=8.0)


class TestBundle(unittest.TestCase):

    def test_two_wires_equal_one_wire_of_the_bundle_impedance(self):
        rho = BASE["rho"]
        zb = (fc.carson_self(0.33, 0.004, rho) + fc.carson_mutual(9.0, rho)) / 2
        a = fc.fault_location_sweep(66, 0.8, n_wires=2, d_sw=9.0, **BASE)
        b = fc.fault_location_sweep(66, 0.8, zs_km=zb,
                                    zm_km=fc.carson_mutual(8.0, rho), **BASE)
        for p, q in zip(a["rows"], b["rows"]):
            self.assertAlmostEqual(p["Ig_kA"], q["Ig_kA"], places=12)
        # and both agree with every wire solved on its own
        wires = [(-4.5, 0, 8.0), (4.5, 0, 8.0)]
        for j in (0, 5, 12):
            ref = wire_level(66, 0.8, 20, 0.3, [12.0], 0.4, rho, wires,
                             BASE["Z1_line"], BASE["Z0_line"], BASE["Z1_local"],
                             BASE["Z0_local"], BASE["Z1_remote"], BASE["Z0_remote"], j)
            self.assertLess(abs(a["rows"][j]["Ig_kA"] / ref - 1), 1e-10)

    def test_other_line_with_two_wires(self):
        # z_s/2 put that ladder 14–19 % low
        z1 = fc.ladder_line_impedance(5, 0.3, 10, 0.4, 100, 50, 0.33, 0.004, 2, 10.0)
        z_old = fc._ladder_input_list([fc.carson_self(0.33, 0.004, 100) / 2 * 0.3] * 17,
                                      [10.0] * 16, 0.4)
        self.assertGreater(abs(z1) / abs(z_old), 1.13)
        self.assertLess(abs(z1) / abs(z_old), 1.20)


class TestCorridor(unittest.TestCase):

    def test_against_the_wire_level_solution(self):
        pl = [dict(separation=30.0, Rt=20.0, n_wires=2, d_sw=8.0, d_phase=31.0),
              dict(separation=55.0, Rt=8.0, d_phase=56.0)]
        r = fc.fault_location_sweep(132, 0.5, n_wires=1, parallel_lines=pl, **BASE)
        wires = [(0.0, 0, 8.0), (26.0, 1, 31.0), (34.0, 1, 31.0), (55.0, 2, 56.0)]
        for j in (0, 1, 7, 19):
            ref = wire_level(132, 0.5, 20, 0.3, [12.0, 20.0, 8.0], 0.4, BASE["rho"], wires,
                             BASE["Z1_line"], BASE["Z0_line"], BASE["Z1_local"],
                             BASE["Z0_local"], BASE["Z1_remote"], BASE["Z0_remote"], j)
            self.assertLess(abs(r["rows"][j]["Ig_kA"] / ref - 1), 1e-10, j)

    def test_induced_currents_far_from_the_ends(self):
        # with the towers far from either end, the longitudinal drop of every
        # wire vanishes: Z·i = −z_p·I_phase, the classical coupling factor
        # (the wires carry part of the phase current back)
        rho = 100.0
        pl = [dict(separation=40.0, Rt=10.0, d_phase=41.0)]
        cor = fc._corridor(1, 10.0, 8.0, 0.33, 0.004, [10.0] * 199, pl, rho, 50.0)
        n = 200
        sps = [0.3] * n
        Iph = [1000.0 + 0j] * n                 # fault at the far end, fed from here
        P, Isp = fc.corridor_nodes(cor, sps, 0.5, 0j, 0.4, Iph, n, 1000.0, 1000.0, 0.0,
                                   full=True)
        expect = -np.linalg.solve(cor["Z"], cor["zp"]) * 1000.0    # wire currents
        mid = Isp[n // 2]
        self.assertLess(np.abs(mid - expect).max() / abs(expect).max(), 1e-6)
        # the farther wire picks up less
        self.assertLess(abs(expect[1]), abs(expect[0]))

    def test_parallel_line_takes_current_away_from_the_grid(self):
        a = fc.fault_location_sweep(132, 0.5, **BASE)
        b = fc.fault_location_sweep(132, 0.5, parallel_lines=[dict(separation=30.0, Rt=12.0)],
                                    **BASE)
        self.assertLess(b["station"]["Ig_kA"], a["station"]["Ig_kA"])

    def test_api_and_guards(self):
        p = dict(Un_kV=132, Rg=0.5, line_km=6, span_km=0.3, Rt=12, R_remote=0.4, rho=150,
                 n_wires=2, d_sw=9, parallel_lines=["30, 20", "55, 8, 2, 8"])
        d = dispatch("/api/fault/sweep", p)
        self.assertEqual(len(d["parallel_lines"]), 2)
        with self.assertRaises(ValueError):
            dispatch("/api/fault/sweep", dict(p, n_wires=3))
        with self.assertRaises(ValueError):
            dispatch("/api/fault/sweep", dict(p, parallel_lines=["0, 20"]))
        with self.assertRaises(ValueError):           # beyond Carson's range
            dispatch("/api/fault/sweep", dict(p, rho=5, parallel_lines=["300, 20"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCircuitFieldCheck(unittest.TestCase):
    """1.9.2: the transferred potential checked by the circuit-field model
    (station and route with conductor impedance and mutual inductance)."""

    base = dict(rho1=100, IG=1000, segment_length=3,
                items=[dict(kind="grid", Lx=30, Ly=30, D=10, depth=0.5, radius=0.005)])

    def test_bare_wire_agrees_and_design_takes_the_larger(self):
        d = dispatch("/api/transfer", dict(self.base, limits=dict(E_touch=1000.0), route=dict(
            start=[30, 20], direction=[1, 0], length=400, radius=0.005, kind="bare",
            metal="copper", depth=0.5, access_points=[20, 100])))
        cf = d["circuit_field"]
        self.assertFalse(cf.get("skipped"))
        self.assertLess(abs(cf["I_diverted"] / d["I_diverted"] - 1), 0.02)
        self.assertLess(abs(cf["V_far_pct"] - d["V_far_pct"]), 3.0)
        for a in d["access"]:
            self.assertLess(abs(a["touch_check"] / a["touch"] - 1), 0.03)
            self.assertEqual(a["touch_design"], max(a["touch"], a["touch_check"]))
            self.assertTrue(a["passed"])
        self.assertGreaterEqual(d["touch_max_design"], d["touch_max"])

    def test_coated_pipe_agrees(self):
        d = dispatch("/api/transfer", dict(self.base, route=dict(
            start=[30, 15], direction=[1, 0], length=1500, radius=0.1, kind="coated",
            coating_res=1e5, metal="steel", wall=0.006, depth=1.0, access_points=[200, 800])))
        for a in d["access"]:
            self.assertLess(abs(a["touch_check"] / a["touch"] - 1), 0.01)

    def test_skipped_where_the_model_does_not_apply(self):
        route = dict(start=[30, 20], direction=[1, 0], length=400, radius=0.005, kind="bare",
                     metal="copper", depth=0.5)
        d = dispatch("/api/transfer", dict(self.base, route=dict(route, far="remote", R_far=5)))
        self.assertIn("skipped", d["circuit_field"])
        d = dispatch("/api/transfer", dict(self.base, route=dict(route, check=False)))
        self.assertNotIn("circuit_field", d)

    def test_internal_impedance_per_wire(self):
        from earthsys import hf
        items = [dict(kind="conductor", p1=[0, 0, 0.5], p2=[50, 0, 0.5], radius=0.005)]
        soil = hf.make_soil(100.0, ())
        out = []
        for zi in (None, "own", 0.01 + 0.02j):
            w = hf.Wires.from_items(items)
            m0 = None
            if zi == "own":
                w.discretise(5.0)
                m0 = hf.Model(w, soil, metal="copper")
                zi = complex(m0._zint(50.0)[0])
                w = hf.Wires.from_items(items)
            if zi is not None:
                w.zint[0] = zi
            w.discretise(5.0)
            out.append(hf.Model(w, soil, metal="copper").solve(50.0, 0, 1.0)[0])
        self.assertAlmostEqual(abs(out[0] - out[1]), 0.0, places=12)
        self.assertGreater(abs(out[2] - out[0]), 1e-3)


class TestFenceSections(unittest.TestCase):

    def test_two_open_outlines_are_two_sections(self):
        g = dict(kind="grid", Lx=40, Ly=40, D=10, depth=0.5, radius=0.005)
        common = dict(kind="fence", closed=0, post_spacing=3, post_depth=0.76,
                      post_radius=0.025, wire=0)
        f1 = dict(common, path=[[-3, 20], [-3, -3], [43, -3], [43, 20]], bonded=1, name="south")
        f2 = dict(common, path=[[43, 24], [43, 43], [-3, 43], [-3, 24]], bonded=0, name="north")
        d = dispatch("/api/bem", dict(rho1=100, IG=1000, segment_length=3, nx=21,
                                      items=[g, f1, f2]))
        names = {f["name"]: f for f in d["fences"]}
        self.assertEqual(set(names), {"south", "north"})
        self.assertAlmostEqual(names["south"]["V_fence"], d["GPR"], delta=1e-6 * d["GPR"])
        self.assertLess(names["north"]["V_fence"], 0.8 * d["GPR"])
        north = [n for n in d["networks"] if n["name"] == "north"][0]
        self.assertAlmostEqual(north["transfer_from_main"], d["GPR"] - north["V"], places=6)
