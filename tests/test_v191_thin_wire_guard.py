"""1.9.1: no bare-conductor segment shorter than ten conductor radii.

Below about four radii the thin-wire matrix loses positive definiteness and
leakage currents turn negative; where conductors cross the trouble starts
near six.  The solvers now keep such conductors at ten radii and say so."""
import unittest

import numpy as np

from earthsys import bem, hf
from earthsys.api import dispatch


def _net(items, seg, **kw):
    net = bem.build_network(dict(rho1=100, items=items, **kw))
    net.discretise(seg, 20000, grade_ends=False)
    return net


class TestFloor(unittest.TestCase):

    def test_thick_rod_is_kept_at_ten_radii(self):
        rod = [dict(kind="rod", x=0, y=0, top_depth=0.5, length=6, radius=0.05)]
        net = _net(rod, 0.1)                     # asked for 2 radii
        self.assertGreaterEqual(min(s.length for s in net.segments), 0.5 - 1e-9)
        self.assertEqual(net.thick["pieces"], 1)
        bem.clear_cache()
        P = net.build_matrix()
        self.assertGreater(np.linalg.eigvalsh(0.5 * (P + P.T)).min(), 0)
        R1 = net.solve()["Rg"]
        self.assertGreaterEqual(net.I.min(), 0)
        ref = _net(rod, 0.5)                     # the same mesh asked for directly
        bem.clear_cache()
        self.assertAlmostEqual(ref.solve()["Rg"], R1, places=10)
        self.assertIsNone(ref.thick)

    def test_crossing_thick_conductors_leak_positively(self):
        net = _net([dict(kind="grid", Lx=4, Ly=4, D=1, depth=0.5, radius=0.05)], 0.15)
        bem.clear_cache()
        net.solve()
        self.assertGreaterEqual(net.I.min(), 0)

    def test_ordinary_models_and_plates_are_untouched(self):
        net = _net([dict(kind="grid", Lx=20, Ly=20, D=5, depth=0.5, radius=0.005)], 0.5)
        self.assertIsNone(net.thick)
        pl = _net([dict(kind="plate", x0=0, y0=0, Lx=1, Ly=1, depth=0.5)], 0.1)
        self.assertIsNone(pl.thick)              # strips keep their own validated length
        P = pl.build_matrix()
        self.assertGreater(np.linalg.eigvalsh(0.5 * (P + P.T)).min(), 0)

    def test_short_thick_piece_is_one_segment(self):
        net = _net([dict(kind="conductor", p1=[0, 0, 0.5], p2=[0.3, 0, 0.5], radius=0.05)], 0.05)
        self.assertEqual(len(net.segments), 1)    # shorter than ten radii: left whole
        self.assertAlmostEqual(net.thick["length"], 0.3)

    def test_api_warns(self):
        d = dispatch("/api/bem", dict(rho1=100, IG=1000, segment_length=0.1, nx=11, items=[
            dict(kind="rod", x=0, y=0, top_depth=0.5, length=3, radius=0.05)]))
        self.assertTrue(any("ten radii" in w for w in d.get("warnings", [])))
        d = dispatch("/api/bem", dict(rho1=100, IG=1000, segment_length=1, nx=11, items=[
            dict(kind="rod", x=0, y=0, top_depth=0.5, length=3, radius=0.008)]))
        self.assertFalse(d.get("warnings"))


class TestCircuitField(unittest.TestCase):

    def test_wires_floor_and_warnings(self):
        items = [dict(kind="grid", Lx=4, Ly=4, D=1, depth=0.5, radius=0.05)]
        w = hf.Wires.from_items(items)
        w.discretise(0.1)
        self.assertGreaterEqual(w.L.min(), 0.5 - 1e-9)
        self.assertIsNotNone(w.thick)
        m = hf.Model(w, hf.make_soil(100.0, ()), metal="copper")
        _, _, _, IT = m.solve(50.0, 0, 1.0)
        self.assertGreaterEqual(IT.real.min(), 0)
        d = dispatch("/api/bem/powerfreq", dict(rho1=100, IG=1000, nx=11, segment_length=0.1,
                                                items=items))
        self.assertTrue(any("ten radii" in x for x in d.get("warnings", [])))
        w2 = hf.Wires.from_items([dict(kind="grid", Lx=20, Ly=20, D=5, depth=0.5,
                                       radius=0.005)])
        w2.discretise(1.0)
        self.assertIsNone(w2.thick)


if __name__ == "__main__":
    unittest.main(verbosity=2)
