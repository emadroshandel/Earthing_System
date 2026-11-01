"""1.8.6: fuse time–current characteristics from the IEC 60269 gates and from
manufacturers' curves, used for automatic disconnection (IEC 60364-4-41)."""
import math
import unittest

from earthsys import fuses, iec60364
from earthsys.api import dispatch


class TestGates(unittest.TestCase):

    def test_transcription_of_part1_tables(self):
        g = fuses.gates(16)
        self.assertEqual((g["I_min_10s"], g["I_max_5s"], g["I_min_01s"], g["I_max_01s"]), (33, 65, 85, 150))
        g = fuses.gates(1250)
        self.assertEqual((g["I_min_10s"], g["I_max_5s"], g["I_min_01s"], g["I_max_01s"]),
                         (5000, 13000, 19000, 35000))
        self.assertEqual(fuses.gates(32)["I2t_001s"], (1.8e3, 5.0e3))
        g = fuses.gates(100)                       # Table 2: 63 < In <= 160 A, 2 h
        self.assertEqual((g["I_nf"], g["I_f"], g["t_conventional"]), (125.0, 160.0, 7200.0))

    def test_small_ratings_of_parts_2_and_3(self):
        self.assertEqual(fuses.gates(12, "industrial_A")["I_max_01s"], 140.4)
        self.assertEqual(fuses.gates(224, "industrial_A")["I_max_5s"], 1450)
        self.assertEqual(fuses.gates(13, "D_type")["I_min_01s"], 75.4)
        self.assertEqual(fuses.gates(10, "BS_cylindrical")["I_max_01s"], 85.0)
        g = fuses.gates(13, "plugtop")
        self.assertEqual((g["I_max_5s"], g["t_conventional"]), (55.0, 1800.0))
        with self.assertRaises(ValueError):
            fuses.gates(12)                          # not a Part 1 rating
        with self.assertRaises(ValueError):
            fuses.gates(32, "plugtop")
        with self.assertRaises(ValueError):
            fuses.gates(32, "nowhere")

    def test_every_band_is_a_valid_curve(self):
        for system in fuses.SYSTEMS:
            for r in fuses.ratings(system):
                b = fuses.band(r, "gG", system)
                fuses._check_curve(b["upper"])
                fuses._check_curve(b["lower"])
                for t in (5.0, 0.4, 0.1):
                    hi = fuses.current_at(b["upper"], t)[0]
                    lo = fuses.current_at(b["lower"], t)[0]
                    self.assertGreater(hi, lo, (system, r, t))

    def test_upper_limit_passes_through_the_gates(self):
        b = fuses.band(63)
        self.assertAlmostEqual(fuses.current_at(b["upper"], 5.0)[0], 320.0)
        self.assertAlmostEqual(fuses.current_at(b["upper"], 0.1)[0], 820.0)
        self.assertAlmostEqual(fuses.current_at(b["upper"], 0.01)[0], math.sqrt(27e3 / 0.01))
        # log-log straight line between 5 s and 0.1 s
        I = fuses.current_at(b["upper"], 0.4)[0]
        f = math.log(5 / 0.4) / math.log(5 / 0.1)
        self.assertAlmostEqual(I, 320 * (820 / 320) ** f)
        # constant I²t below the shortest point
        self.assertAlmostEqual(fuses.current_at(b["upper"], 0.0025)[0],
                               math.sqrt(27e3 / 0.01) * 2.0)

    def test_bs7671_values_lie_inside_the_gates(self):
        for t in (0.4, 5.0):
            for r in iec60364.FUSE_GG_BS7671[t]:
                system = "general" if r >= 16 else "industrial_A"
                b = fuses.band(r, "gG", system)
                Ia = iec60364.device_Ia("fuse", r, t)["Ia"]
                hi = fuses.current_at(b["upper"], t)[0]
                lo = fuses.current_at(b["lower"], t)[0] if t <= 10 else 0
                self.assertLessEqual(Ia, hi * 1.0001, (r, t))
                self.assertGreaterEqual(Ia, lo * 0.9999, (r, t))

    def test_am_gates(self):
        b = fuses.band(100, "aM")
        self.assertEqual(b["upper"], [(630.0, 60.0), (1250.0, 0.5), (1900.0, 0.1)])
        self.assertEqual(b["lower"][0], (400.0, 60.0))


class TestCurves(unittest.TestCase):
    TXT = "Current (A), Time (s)\n100, 10\n160, 1\n250, 0.1\n400, 0.01\n"

    def test_parse_variants(self):
        a = fuses.parse_curve(self.TXT)
        b = fuses.parse_curve("time;current\n10;100\n1;160\n0.1;250\n0.01;400")
        c = fuses.parse_curve("I (kA)\tt (s)\n0.1\t10\n0.16\t1\n0.25\t0.1\n0.4\t0.01")
        d = fuses.parse_curve([(400, 0.01), (100, 10), (250, 0.1), (160, 1)])
        self.assertEqual(a, b)
        self.assertEqual(a, d)
        for (I1, t1), (I2, t2) in zip(a, c):
            self.assertAlmostEqual(I1, I2)
            self.assertAlmostEqual(t1, t2)

    def test_bad_curves(self):
        with self.assertRaises(ValueError):
            fuses.parse_curve("100, 10\n160, 20")         # time rises with current
        with self.assertRaises(ValueError):
            fuses.parse_curve("100, 10")                  # one point
        with self.assertRaises(ValueError):
            fuses.parse_curve("100, -1\n200, 0.1")

    def test_interpolation_and_tolerance(self):
        r0 = fuses.operating_current(1.0, points=self.TXT)
        self.assertAlmostEqual(r0["Ia"], 160.0)
        r = fuses.operating_current(1.0, points=self.TXT, tolerance_pct=10)
        self.assertAlmostEqual(r["Ia"], 176.0)
        t = fuses.operating_time(160.0, points=self.TXT)["t"]
        self.assertAlmostEqual(t, 1.0)
        self.assertIsNone(fuses.operating_time(50.0, points=self.TXT)["t"])
        with self.assertRaises(ValueError):
            fuses.operating_current(100.0, points=self.TXT)


class TestDisconnection(unittest.TestCase):
    EL = [dict(type="rod", L=3, d=0.016)]

    def _assess(self, dev, Zl=0.3):
        return iec60364.assess("TN-S", 230, 100, self.EL, dev, "final", Zl, 0.3, 0.2)

    def test_kinds(self):
        for kind in ("fuse_iec", "fuse_gm", "fuse_am"):
            r = self._assess(dict(kind=kind, rating_A=32))
            self.assertIn("IEC 60269", r["device"]["basis"])
            self.assertIsNotNone(r["device"]["If_min"])
        r = self._assess(dict(kind="fuse_curve", points=TestCurves.TXT, tolerance_pct=10))
        self.assertIn("manufacturer", r["device"]["basis"])

    def test_operating_time_agrees_with_the_loop_check(self):
        for Zl in (0.1, 0.3, 0.6, 1.0, 2.0):
            r = self._assess(dict(kind="fuse_iec", rating_A=32), Zl)
            loop = r["checks"][0]["passed"]
            t = r["device"]["t_operate"]
            self.assertEqual(loop, t is not None and t <= 0.4 + 1e-9, Zl)

    def test_bs88_rating_not_in_bs7671_uses_the_gates(self):
        d = iec60364.device_Ia("fuse", 160, 0.4)
        self.assertIn("IEC 60269", d["basis"])
        self.assertAlmostEqual(d["Ia"], fuses.operating_current(0.4, rating=160)["Ia"])

    def test_endpoints(self):
        f = dispatch("/api/fuse", dict(kind="gG", rating=40, I=500))
        self.assertEqual(len(f["Ia_table"]), 5)
        self.assertIsNotNone(f["at_current"]["t"])
        f = dispatch("/api/fuse", dict(points=TestCurves.TXT, tolerance_pct=5))
        self.assertIsNotNone(f["lines"]["curve_tol"])
        b = dispatch("/api/building", dict(system="TN-S", U0=230, rho=100, electrodes=self.EL,
                                           device=dict(kind="fuse_iec", rating_A=10,
                                                       system="BS_cylindrical"),
                                           Z_line=0.5, Z_pe=0.5, Z_source=0.35))
        self.assertIn("BS cylindrical", b["device"]["basis"])
        with self.assertRaises(ValueError):
            dispatch("/api/building", dict(system="TN-S", U0=230, rho=100, electrodes=self.EL,
                                           device=dict(kind="fuse_curve", points=" ")))
        meta = dispatch("/api/meta", {})
        self.assertIn("fuse_systems", meta)


if __name__ == "__main__":
    unittest.main(verbosity=2)
