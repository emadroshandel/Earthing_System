"""1.8.4: faster field evaluation and assembly (same answers), studies on
several cores, DXF import and fence outlines."""
import math
import os
import unittest

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None

from earthsys import api, dxfimport, parallel


def _net(rho2=None, h=None, rho3=None, h2=None, fence=False):
    from earthsys import bem
    items = [dict(kind="grid", Lx=30, Ly=20, D=5, depth=0.5, radius=0.005),
             dict(kind="rod", x=0, y=0, top_depth=0.5, length=6, radius=0.008)]
    if fence:
        items.append(dict(kind="fence", x0=-3, y0=-3, Lx=36, Ly=26, post_spacing=3, bonded=True))
    p = dict(rho1=200, IG=1000, items=items)
    if rho2:
        p.update(rho2=rho2, h_layer=h)
    if rho3:
        p.update(rho3=rho3, h_layer2=h2)
    net = bem.build_network(p)
    net.discretise(2.5, 4000, grade_ends=True)
    net.solve()
    return net


def _reference_potential(net, pts):
    """12-point Gauss rule on every segment: the slow, unambiguous sum."""
    from earthsys.bem import _gauss
    t, w = _gauss(12)
    out = np.zeros(len(pts))
    for j, sj in enumerate(net.segments):
        q = sj.p1[None, :] + (sj.p2 - sj.p1)[None, :] * t[:, None]
        out += net.I[j] * (net._green_terms(pts, q, False, sj.layer, sj.radius ** 2) @ w)
    return out


@unittest.skipIf(np is None, "numpy needed")
class TestFieldAndAssembly(unittest.TestCase):

    def _check_field(self, net):
        g = np.linspace(-6, 36, 23)
        X, Y = np.meshgrid(g, np.linspace(-6, 26, 17))
        pts = np.column_stack([X.ravel(), Y.ravel(), np.zeros(X.size)])
        pts = np.vstack([pts, [[0.0, 0.0, 0.0], [2.5, 0.3, 0.0]]])
        v = net.potential_at(pts)
        ref = _reference_potential(net, pts)
        self.assertLess(float(np.max(np.abs(v - ref) / np.abs(ref))), 2e-5)

    def test_field_uniform(self):
        self._check_field(_net())

    def test_field_two_layer(self):
        self._check_field(_net(rho2=50, h=3))

    def test_field_three_layer(self):
        self._check_field(_net(rho2=50, h=2, rho3=800, h2=5))

    def test_field_on_fence_posts(self):
        self._check_field(_net(fence=True))

    def test_tiered_assembly_matches_the_full_rule(self):
        from earthsys import bem
        net = _net(rho2=50, h=3)
        P_fast = net.build_matrix()
        P_full = net.build_matrix(mid_rule=None)
        self.assertLess(float(np.max(np.abs(P_fast - P_full)) / np.max(np.abs(P_full))), 1e-6)


class TestParallel(unittest.TestCase):

    def test_pmap_matches_serial(self):
        self.assertEqual(parallel.pmap(math.sqrt, [4.0, 9.0, 16.0]), [2.0, 3.0, 4.0])

    def test_worker_setting(self):
        old = os.environ.get("ES_WORKERS")
        try:
            os.environ["ES_WORKERS"] = "1"
            self.assertEqual(parallel.max_workers(), 1)
            os.environ["ES_WORKERS"] = "3"
            self.assertEqual(parallel.max_workers(), 3)
        finally:
            if old is None:
                os.environ.pop("ES_WORKERS", None)
            else:
                os.environ["ES_WORKERS"] = old

    @unittest.skipIf(np is None, "numpy needed")
    def test_seasonal_on_two_workers_gives_the_serial_answer(self):
        from earthsys import studies
        p = dict(rho1=100, IG=1000, segment_length=3, nx=15,
                 items=[dict(kind="grid", Lx=10, Ly=10, D=5, depth=0.5)],
                 seasonal=dict(dry_factor=2, dry_depth=1, frozen_rho=2000, frozen_depth=0.3))
        old = os.environ.get("ES_WORKERS")
        try:
            os.environ["ES_WORKERS"] = "1"
            a = studies.seasonal(dict(p))
            os.environ["ES_WORKERS"] = "2"
            b = studies.seasonal(dict(p))
        finally:
            if old is None:
                os.environ.pop("ES_WORKERS", None)
            else:
                os.environ["ES_WORKERS"] = old
        for ca, cb in zip(a["cases"], b["cases"]):
            self.assertAlmostEqual(ca["touch"], cb["touch"], places=9)
            self.assertAlmostEqual(ca["Rg"], cb["Rg"], places=12)


def _dxf(units=4):
    L = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", str(units), "0", "ENDSEC",
         "0", "SECTION", "2", "ENTITIES"]

    def ent(t, layer, kv):
        L.extend(["0", t, "8", layer])
        for k, v in kv:
            L.extend([str(k), str(v)])
    ent("LINE", "EARTH-GRID", [(10, 1000), (20, 1000), (30, 0), (11, 21000), (21, 1000), (31, 0)])
    # an open LWPOLYLINE whose first piece is a semicircle (bulge 1, CCW)
    L.extend(["0", "LWPOLYLINE", "8", "EARTH-GRID", "90", "3", "70", "0",
              "10", "0", "20", "0", "42", "1", "10", "2000", "20", "0", "10", "4000", "20", "0"])
    ent("POINT", "RODS", [(10, 1000), (20, 1000)])
    ent("CIRCLE", "RODS", [(10, 21000), (20, 1000), (40, 40)])
    ent("INSERT", "RODS", [(2, "ROD"), (10, 11000), (20, 1000)])
    ent("CIRCLE", "EARTH-GRID", [(10, 11000), (20, 11000), (40, 5000)])
    L.extend(["0", "POLYLINE", "8", "FENCE", "66", "1", "70", "1"])
    for x, y in [(-2000, -2000), (24000, -2000), (24000, 14000), (-2000, 14000)]:
        L.extend(["0", "VERTEX", "8", "FENCE", "10", str(x), "20", str(y)])
    L.extend(["0", "SEQEND", "8", "FENCE"])
    ent("LINE", "NOTES", [(10, 0), (20, 0), (11, 5), (21, 5)])
    L.extend(["0", "ENDSEC", "0", "EOF"])
    return "\r\n".join(L) + "\r\n"


class TestDxf(unittest.TestCase):

    def test_inspect_suggests_layer_uses(self):
        i = api.dispatch("/api/dxf/inspect", dict(text=_dxf()))
        self.assertEqual(i["unit"], "millimetres")
        self.assertEqual(i["scale"], 0.001)
        sug = {k: v["suggest"] for k, v in i["layers"].items()}
        self.assertEqual(sug, {"EARTH-GRID": "conductor", "RODS": "rod", "FENCE": "fence",
                               "NOTES": "ignore"})

    def test_import_builds_the_electrodes(self):
        m = {"EARTH-GRID": "conductor", "RODS": "rod", "FENCE": "fence", "NOTES": "ignore"}
        r = api.dispatch("/api/dxf/import", dict(text=_dxf(), mapping=m, depth=0.5, rod_length=2.4,
                                                 fence=dict(bonded=True)))
        c = r["counts"]
        self.assertEqual((c["rods"], c["fences"], c["rings"]), (3, 1, 1))
        self.assertEqual(r["origin"], [-2000.0, -2000.0])
        f = [it for it in r["items"] if it["kind"] == "fence"][0]
        self.assertEqual(f["path"], [[0.0, 0.0], [26.0, 0.0], [26.0, 16.0], [0.0, 16.0]])
        self.assertEqual((f["closed"], f["bonded"]), (1, 1))
        ring = [it for it in r["items"] if it["kind"] == "ring"][0]
        self.assertAlmostEqual(ring["r"], 5.0)
        rods = sorted((it["x"], it["y"]) for it in r["items"] if it["kind"] == "rod")
        self.assertEqual(rods, [(3.0, 3.0), (13.0, 3.0), (23.0, 3.0)])
        self.assertTrue(all(it["length"] == 2.4 for it in r["items"] if it["kind"] == "rod"))

    def test_bulge_becomes_a_semicircle(self):
        r = dxfimport.to_items(_dxf(), {"EARTH-GRID": "conductor"}, to_origin=False)
        pts = [tuple(it["p1"][:2]) for it in r["items"] if it["kind"] == "conductor"]
        # the arc from (0,0) to (2,0) counter-clockwise passes below the chord, through (1, -1)
        self.assertTrue(any(abs(x - 1.0) < 1e-6 and abs(y + 1.0) < 1e-6 for x, y in pts))
        self.assertTrue(all(abs(math.hypot(x - 1.0, y) - 1.0) < 1e-4
                            for x, y in pts if 0 < x < 2 and y < 0))

    def test_scale_override_and_errors(self):
        r = dxfimport.to_items(_dxf(units=0), {"RODS": "rod"}, scale=0.01, to_origin=False)
        self.assertEqual(sorted(it["x"] for it in r["items"]), [10.0, 110.0, 210.0])
        with self.assertRaises(ValueError):
            api.dispatch("/api/dxf/inspect", dict(text="AC1018 binary"))
        with self.assertRaises(ValueError):
            api.dispatch("/api/dxf/import", dict(text=_dxf(), mapping={"NOTES": "ignore"}))
        with self.assertRaises(ValueError):
            api.dispatch("/api/dxf/import", dict(text=_dxf(), mapping={"RODS": "pipe"}))

    @unittest.skipIf(np is None, "numpy needed")
    def test_imported_layout_solves(self):
        m = {"EARTH-GRID": "conductor", "RODS": "rod", "FENCE": "fence"}
        r = api.dispatch("/api/dxf/import", dict(text=_dxf(), mapping=m))
        b = api.dispatch("/api/bem", dict(rho1=100, IG=1000, items=r["items"], segment_length=3, nx=15))
        self.assertGreater(b["Rg"], 0)
        self.assertEqual(len(b.get("fences", [])), 1)

    def test_reads_the_drawings_this_program_writes(self):
        from earthsys import cad
        sh = cad.Sheet("A3") if hasattr(cad, "Sheet") else None
        if sh is None or not hasattr(cad, "to_dxf"):
            self.skipTest("cad writer API differs")
        sh.line(0, 0, 100, 0)
        info = dxfimport.inspect(cad.to_dxf(sh))
        self.assertGreaterEqual(info["entities"], 1)


if __name__ == "__main__":
    unittest.main()
