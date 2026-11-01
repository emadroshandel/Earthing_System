"""1.8.9: the two-scale non-equipotential solution for models larger than
the circuit-field model takes (coarse circuit-field model for the metal
potentials, fine boundary-element leakage for the surface)."""
import unittest

import numpy as np

from earthsys import bem, hf, powerfreq
from earthsys.api import dispatch


class TestPieces(unittest.TestCase):

    def test_leakage_for_potentials_dense_and_compressed(self):
        net = bem.build_network(dict(rho1=100, IG=1000, items=[
            dict(kind="grid", Lx=40, Ly=30, D=10, depth=0.5, radius=0.005),
            dict(kind="rod", x=3, y=2, top_depth=0.5, length=3, radius=0.008)]))
        net.discretise(2.0)
        bem.clear_cache()
        s = net.solve(method="dense", symmetry=False)
        ref = net.Ibasis[:, 0] / net.Z[0, 0]            # P⁻¹·1
        V = np.full(len(net.segments), 2.0 - 1.0j)
        I = net.leakage_for_potentials(V)
        self.assertLess(np.abs(I - (2.0 - 1.0j) * ref).max() / np.abs(ref).max(), 1e-10)
        keep = bem.DENSE_LIMIT
        try:
            bem.DENSE_LIMIT = 50
            I2 = net.leakage_for_potentials(V)
        finally:
            bem.DENSE_LIMIT = keep
        self.assertLess(np.abs(I2 - I).max() / np.abs(I).max(), 1e-7)

    def test_interpolation_along_the_conductors(self):
        items = [dict(kind="grid", Lx=40, Ly=40, D=10, depth=0.5, radius=0.005)]
        w = hf.Wires.from_items(items)
        w.discretise(10.0)
        Vn = (w.nodes[:, 0] * 2.0 + w.nodes[:, 1] * (1 - 0.5j)).astype(complex)  # linear
        net = bem.build_network(dict(rho1=100, items=items))
        net.discretise(2.5)
        got = powerfreq.metal_on_segments(w, Vn, net)
        mids = np.array([sg.mid for sg in net.segments])
        exp = mids[:, 0] * 2.0 + mids[:, 1] * (1 - 0.5j)
        self.assertLess(np.abs(got - exp).max(), 1e-9)


class TestCircuitFieldMemory(unittest.TestCase):

    def test_limit_counts_the_cuts(self):
        # rods and crossings cut the conductors: the count stays within the cap
        items = [dict(kind="grid", Lx=120, Ly=80, D=10, depth=0.5, radius=0.005)] + [
            dict(kind="rod", x=x, y=y, top_depth=0.5, length=6, radius=0.008)
            for x in (0, 40, 80, 120) for y in (0, 40, 80)]
        d = dispatch("/api/bem/powerfreq", dict(
            rho1=200, rho2=50, h_layer=3.0, IG=1000, metal="copper", nx=11,
            segment_length=2.0, max_segments=300, items=items))
        self.assertLessEqual(d["segments"], 300)
        self.assertIsNotNone(d["two_scale"])
        with self.assertRaises(ValueError):
            dispatch("/api/bem/powerfreq", dict(rho1=100, IG=1000, nx=11, max_segments=50,
                                                items=items))

    def test_near_image_blocks_without_the_cache(self):
        # the layered matrices are the same whether the near-image blocks are
        # kept between frequencies or not
        items = [dict(kind="grid", Lx=30, Ly=20, D=10, depth=0.5, radius=0.005),
                 dict(kind="rod", x=0, y=0, top_depth=0.5, length=6, radius=0.008)]
        soil = hf.make_soil([200, 50], [3.0])
        out = []
        keep = hf.NEARBLK_BYTES
        try:
            for b in (keep, 0):
                hf.NEARBLK_BYTES = b
                w = hf.Wires.from_items(items)
                w.discretise(2.5, z_cuts=soil.depths)
                m = hf.Model(w, soil, metal="steel")
                out.append([m.matrices(f) for f in (50.0, 1e5, 50.0)])
        finally:
            hf.NEARBLK_BYTES = keep
        for a, b in zip(out[0], out[1]):
            for x, y in zip(a, b):
                self.assertLess(np.abs(x - y).max() / np.abs(x).max(), 1e-13)
        self.assertLess(np.abs(out[0][0][0] - out[0][2][0]).max(), 1e-12 * np.abs(out[0][0][0]).max())


class TestAgainstTheFineCircuitField(unittest.TestCase):
    """A 100 m steel grid in 30 Ω·m fed at a corner: the full circuit-field
    model at 2.5 m against the two-scale solution with a 5 m and a 10 m
    coarse model, and against the coarse model alone."""

    base = dict(rho1=30, IG=5000, metal="steel", f=50, nx=31, segment_length=2.5,
                grade_ends=False, feeds=[dict(x=0, y=0, share=1.0)],
                items=[dict(kind="grid", Lx=100, Ly=100, D=10, depth=0.5, radius=0.005)])

    @classmethod
    def setUpClass(cls):
        cls.ref = dispatch("/api/bem/powerfreq", dict(cls.base, max_segments=3000))

    def test_two_scale_is_close_to_the_fine_model(self):
        ref = self.ref
        self.assertIsNone(ref.get("two_scale"))
        for cap in (440, 220):                           # coarse 5 m and 10 m
            d = dispatch("/api/bem/powerfreq", dict(self.base, max_segments=cap))
            c = dispatch("/api/bem/powerfreq", dict(self.base, max_segments=cap, two_scale=False))
            ts = d["two_scale"]
            self.assertIsNotNone(ts)
            self.assertLess(abs(ts["current_balance"] - 1), 0.01)
            self.assertEqual(ts["fine_segments"], ref["segments"])
            for k in ("touch_max", "step_max"):
                e2 = abs(d[k] / ref[k] - 1)
                e1 = abs(c[k] / ref[k] - 1)
                self.assertLess(e2, 0.01, (cap, k, d[k], ref[k]))
                self.assertLessEqual(e2, e1 + 1e-9, (cap, k))
            self.assertLess(abs(d["Z"]["abs"] / ref["Z"]["abs"] - 1), 0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
