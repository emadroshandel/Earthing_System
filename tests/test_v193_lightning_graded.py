"""1.9.3: graded mesh of the lightning model for electrodes larger than its
segment limit — fine at the injection, growing with the distance from it."""
import unittest

import numpy as np

from earthsys import hf
from earthsys.api import dispatch


GRID = [dict(kind="grid", Lx=60, Ly=60, D=20, depth=0.5, radius=0.005)]


def sweep(cap, graded, seg=0.5, rho=100.0):
    w = hf.Wires.from_items(GRID)
    r = hf.harmonic_impedance(wires=w, soil=hf.Soil(rho, 10.0), feed=[0, 0, 0.5],
                              f_min=1e3, f_max=5e6, n_f=8, max_segments=cap,
                              graded=graded, seg_len=seg)
    return r


class TestGraded(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ref = sweep(10 ** 6, True)                 # uniform 0.5 m, within the limit

    def test_mesh(self):
        r = sweep(200, True)
        self.assertLessEqual(r["segments"], 200)
        g = r["grading"]
        w = r["model"].w
        d = np.linalg.norm(w.mid - np.array([0, 0, 0.5]), axis=1)
        near = w.L[d < 1.0]
        self.assertTrue(np.all(near <= 0.5 * 1.3 + 1e-9))
        self.assertGreater(w.L.max(), 4 * near.max())
        self.assertIsNone(self.ref["grading"])          # nothing graded within the limit

    def test_close_to_the_fine_mesh_where_the_coarse_one_is_not(self):
        Zr = self.ref["Z"]
        g = sweep(200, True)
        c = sweep(200, False)
        eg = np.abs(g["Z"] - Zr) / np.abs(Zr)
        ec = np.abs(c["Z"] - Zr) / np.abs(Zr)
        self.assertLess(eg.max(), 0.005)
        self.assertGreater(ec.max(), 2 * eg.max())
        self.assertLess(abs(g["R"] / self.ref["R"] - 1), 0.003)

    def test_crossings_above_the_limit_keep_a_fine_injection(self):
        # 84 pieces between crossings: a limit of 60 cannot hold them; the
        # limit gives way and half of it stays for the fine mesh at the feed
        w = hf.Wires.from_items([dict(kind="grid", Lx=60, Ly=60, D=10, depth=0.5,
                                      radius=0.005)])
        r = hf.harmonic_impedance(wires=w, soil=hf.Soil(100.0, 10.0), feed=[0, 0, 0.5],
                                  f_min=1e3, f_max=1e6, n_f=3, max_segments=60, seg_len=0.5)
        self.assertLessEqual(r["segments"], 84 + 30)
        d = np.linalg.norm(w.mid - np.array([0, 0, 0.5]), axis=1)
        self.assertLessEqual(w.L[d < 0.6].max(), 0.5 * 1.3)

    def test_api(self):
        d = dispatch("/api/hf", dict(rho0=100, items=GRID, f_max=2e6, max_segments=150))
        self.assertLessEqual(d["segments"], 150)
        self.assertIsNotNone(d["grading"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
