"""1.9.4: cross-bonded cable sheaths in the earth-fault return."""
import math
import unittest

import numpy as np

from earthsys import faultcurrent as fc
from earthsys.api import dispatch

KW = dict(R_A=0.5, R_B=1.0, r_sheath_km=0.2, r_mean=0.03, rho=100.0)


def path_level(If_kA, minor, R_A, R_B, R_major, r_s, r_m, rho, formation, spacing,
               nc=1, sep=0.5, ph=0, f=50.0):
    """Independent solution: nodes named by sheath path (a path keeps its
    identity through a major section and moves one position at each
    cross-bonding joint), every sheath of every minor section a branch of
    the global branch-impedance matrix."""
    if formation == "trefoil":
        pos = [(0.0, 0.0), (spacing, 0.0), (spacing / 2, spacing * math.sqrt(3) / 2)]
    else:
        pos = [(-spacing, 0.0), (0.0, 0.0), (spacing, 0.0)]
    De = 658.5 * math.sqrt(rho / f)
    ke = math.pi ** 2 * 1e-4 * f
    z = lambda d: complex(ke, 2 * math.pi * f * 2e-4 * math.log(De / d))
    names = {"A": 0, "B": 1}

    def nid(key):
        if key not in names:
            names[key] = len(names)
        return names[key]
    branches = []                              # (start, end, wire position xy, circuit, pos)
    nm = len(minor)
    for k in range(nm):
        for c in range(nc):
            for s in range(3):
                p = (s + k % 3) % 3            # position of path s in minor k
                if k == 0:
                    a = "A"
                elif k % 3 == 0:
                    a = ("M", k // 3)
                else:
                    a = ("X", k - 1, c, s)
                if k == nm - 1:
                    b = "B"
                elif (k + 1) % 3 == 0:
                    b = ("M", (k + 1) // 3)
                else:
                    b = ("X", k, c, s)
                xy = (pos[p][0] + c * sep, pos[p][1])
                branches.append((nid(a), nid(b), xy, c, p, k))
    N = len(names)
    nb = len(branches)
    A = np.zeros((N, nb))
    Zb = np.zeros((nb, nb), complex)
    E = np.zeros(nb, complex)
    core = pos[ph]
    for i, (a, b, xy, c, p, k) in enumerate(branches):
        A[a, i] += 1
        A[b, i] -= 1
        dcore = r_m if (c == 0 and p == ph) else math.dist(core, xy)
        E[i] = -z(dcore) * minor[k] * If_kA * 1e3
        for j, (a2, b2, xy2, c2, p2, k2) in enumerate(branches):
            if k2 != k:
                continue
            d = r_m if i == j else math.dist(xy, xy2)
            Zb[i, j] = (z(d) + (r_s if i == j else 0)) * minor[k]
    Yb = np.linalg.inv(Zb)
    G = A @ Yb @ A.T
    G[0, 0] += 1 / R_A
    G[1, 1] += 1 / R_B
    for key, i in names.items():
        if isinstance(key, tuple) and key[0] == "M":
            G[i, i] += 1 / R_major
    inj = np.zeros(N, complex)
    inj[1] += If_kA * 1e3
    inj[0] -= If_kA * 1e3
    V = np.linalg.solve(G, inj - A @ Yb @ E)
    return abs(V[1] / R_B) / 1e3, V, names


class TestCrossBonded(unittest.TestCase):

    def test_equal_minor_sections_equal_the_bonded_model(self):
        # every path visits each position once: the both-ends model with
        # earths at the major joints, exactly
        for form, sp in (("trefoil", 0.09), ("flat", 0.2)):
            for ph in range(3):
                x = fc.cable_sheath_crossbonded(10, minor_km=[0.5] * 6, R_major=5.0,
                                                formation=form, spacing=sp, faulted_phase=ph,
                                                **KW)
                y = fc.cable_sheath_return(10, length_km=3.0, joints=[1.5], R_joint=5.0,
                                           formation=form, spacing=sp, faulted_phase=ph, **KW)
                self.assertLess(abs(x["Ig_kA"] / y["Ig_kA"] - 1), 1e-12)
                self.assertLess(abs(x["I_sheath_kA"] / y["I_sheath_kA"] - 1), 1e-12)

    def test_against_the_path_level_solution(self):
        minor = [0.4, 0.55, 0.55, 0.3, 0.6, 0.6]
        for form, sp, nc in (("flat", 0.2, 1), ("trefoil", 0.09, 2), ("flat", 0.2, 2)):
            x = fc.cable_sheath_crossbonded(10, minor_km=minor, R_major=5.0, formation=form,
                                            spacing=sp, n_circuits=nc, circuit_sep=0.6,
                                            faulted_phase=1, **KW)
            ig, V, names = path_level(10, minor, 0.5, 1.0, 5.0, 0.2, 0.03, 100.0, form, sp,
                                      nc=nc, sep=0.6, ph=1)
            self.assertLess(abs(x["Ig_kA"] / ig - 1), 1e-10)
            vmax = max(abs(V[i]) for k, i in names.items() if isinstance(k, tuple) and k[0] == "X")
            self.assertLess(abs(max(l["V_max"] for l in x["link_boxes"]) / vmax - 1), 1e-10)

    def test_trefoil_total_does_not_depend_on_the_minor_lengths(self):
        # in trefoil every sheath is equally far from the others, so the
        # paths' impedance matrix is the same whatever the minor lengths and
        # only the total induced voltage counts; the link-box voltages do change
        a = fc.cable_sheath_crossbonded(10, minor_km=[0.5] * 6, R_major=5.0, spacing=0.09, **KW)
        b = fc.cable_sheath_crossbonded(10, minor_km=[0.3, 0.6, 0.6, 0.5, 0.45, 0.55],
                                        R_major=5.0, spacing=0.09, **KW)
        self.assertLess(abs(a["Ig_kA"] / b["Ig_kA"] - 1), 1e-12)
        self.assertGreater(abs(a["link_boxes"][0]["V_across_max"]
                               - b["link_boxes"][0]["V_across_max"]), 10.0)

    def test_link_boxes_are_not_earths(self):
        # entering the link boxes as earthed joints takes too much current off
        x = fc.cable_sheath_crossbonded(10, minor_km=[0.5] * 6, R_major=5.0, formation="flat",
                                        spacing=0.2, **KW)
        y = fc.cable_sheath_return(10, length_km=3.0, joints=[0.5, 1, 1.5, 2, 2.5], R_joint=5.0,
                                   formation="flat", spacing=0.2, **KW)
        self.assertGreater(x["Ig_kA"], 1.05 * y["Ig_kA"])

    def test_api_and_guards(self):
        p = dict(If_kA=10, length_km=3, R_A=0.5, R_B=1, r_sheath_km=0.2, r_mean=0.03,
                 formation="flat", spacing=0.2, bonding="cross_bonded",
                 minor_km="0.5, 0.5, 0.5, 0.5, 0.5, 0.5", R_joint=5)
        d = dispatch("/api/cable/sheath", p)
        self.assertEqual(len(d["link_boxes"]), 4)
        with self.assertRaises(ValueError):
            dispatch("/api/cable/sheath", dict(p, minor_km="0.5, 0.5"))
        with self.assertRaises(ValueError):
            dispatch("/api/cable/sheath", dict(p, formation="three_core"))
        with self.assertRaises(ValueError):
            dispatch("/api/cable/sheath", dict(p, minor_km="1, 1, 1"))   # length 3 km, ok
            dispatch("/api/cable/sheath", dict(p, minor_km="1, 1, 1.5"))  # sums to 3.5, not 3


if __name__ == "__main__":
    unittest.main(verbosity=2)
