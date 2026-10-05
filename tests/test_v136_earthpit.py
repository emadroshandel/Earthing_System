"""Earth pits (1.3.6): the axisymmetric solver, BS 7430 9.5.7, groups of pits,
current density, size checks and the API.  The numbers are those of the
tutorial, Section 11.7."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import api, earthpit as ep, report, standards as st  # noqa: E402


class Solver(unittest.TestCase):
    def test_bare_rod_matches_dwight(self):
        # BEM gives 33.15 ohm; Dwight's formula 33.49 ohm (1 % high for a 3 m rod)
        R = ep.solve_pit(100, 100, L=3, d=0.016, D=0.3)["R"]
        self.assertAlmostEqual(R, 33.12, delta=0.1)
        self.assertLess(abs(R / ep.rod_dwight(100, 3, 0.016) - 1), 0.015)

    def test_bare_plate_matches_buried_plate_formula(self):
        from earthsys import iec60364
        R = ep.solve_pit(100, 100, electrode="plate", area=0.5, top=5.4, D=0.8,
                         fill_top=4.7, fill_bottom=6.0)["R"]
        Rp = iec60364.plate(100, 0.5, 5.4)["R"]
        self.assertLess(abs(R / Rp - 1), 0.01)

    def test_bs7430_backfill_is_close_and_conservative(self):
        for rc, D in ((2.5, 0.1), (2.5, 0.3), (8.7, 0.3), (2.5, 1.0), (30, 0.3)):
            fv = ep.solve_pit(100, rc, L=3, d=0.016, D=D)["R"]
            bs = ep.bs7430_backfilled(100, rc, 3, 0.016, D)["R"]
            self.assertLess(abs(bs / fv - 1), 0.03, (rc, D))
            self.assertGreaterEqual(bs, fv * 0.995, (rc, D))

    def test_book_values(self):
        cases = [
            (dict(rho=100, rho_c=8.7, L=3, d=0.016, D=0.3), 18.92),
            (dict(rho=100, rho_c=8.7, electrode="plate", area=0.5, top=5.4, D=0.8,
                  fill_top=4.7, fill_bottom=6.0), 17.24),
            (dict(rho=100, rho_c=8.7, L=6, d=0.016, D=0.8), 8.95),
            (dict(rho=100, rho_c=100, L=6, d=0.016, D=0.8), 18.43),
        ]
        for kw, ref in cases:
            self.assertAlmostEqual(ep.solve_pit(**kw)["R"], ref, delta=0.05, msg=kw)

    def test_resistance_scales_with_resistivity(self):
        a = ep.solve_pit(100, 10, L=3, D=0.3)["R"]
        b = ep.solve_pit(200, 20, L=3, D=0.3)["R"]
        self.assertAlmostEqual(b / a, 2.0, places=6)

    def test_better_backfill_lowers_resistance(self):
        Rs = [ep.solve_pit(100, rc, L=3, D=0.3)["R"] for rc in (100, 30, 8.7, 2.5)]
        self.assertEqual(Rs, sorted(Rs, reverse=True))


class ClosedForms(unittest.TestCase):
    def test_bs7430_reduces_to_dwight(self):
        r = ep.bs7430_backfilled(100, 100, 3, 0.016, 0.3)
        self.assertAlmostEqual(r["R"], ep.rod_dwight(100, 3, 0.016), places=9)

    def test_bs7430_is_two_shells_in_series(self):
        r = ep.bs7430_backfilled(100, 8.7, 3, 0.016, 0.3)
        self.assertAlmostEqual(r["R_soil"], ep.rod_dwight(100, 3, 0.3), places=9)
        self.assertAlmostEqual(r["R"], r["R_soil"] + r["R_backfill"], places=12)

    def test_group_seven_wells(self):
        g = ep.pit_group(9.1, 100, 7, 12)
        self.assertAlmostEqual(g["lam"], 3.1857, places=4)
        self.assertAlmostEqual(g["R"], 1.90, delta=0.01)

    def test_pits_required(self):
        r = ep.pits_required(8.95, 100, 2.0, 12)
        self.assertEqual(r["n"], 7)
        self.assertFalse(ep.pits_required(30, 1000, 0.5, 3, max_n=20)["reachable"])

    def test_current_density_limit(self):
        self.assertAlmostEqual(ep.jmax_bs7430(8.7, 1), 2575.3, delta=0.5)
        self.assertAlmostEqual(ep.jmax_bs7430(100, 1), 759.6, delta=0.5)


class Checks(unittest.TestCase):
    def test_rod_sizes(self):
        ok = ep.size_checks("rod", "copper_bonded_steel", d=0.016)
        self.assertTrue(all(c["ok"] for c in ok))
        small = ep.size_checks("rod", "galvanized_steel", d=0.012)
        self.assertFalse(any(c["ok"] for c in small))

    def test_plate_sizes(self):
        c = ep.size_checks("plate", "copper", area=0.5, thickness_mm=2)
        self.assertTrue(all(x["ok"] for x in c))
        c = ep.size_checks("plate", "copper", area=0.25, thickness_mm=1.5)
        self.assertEqual([x["ok"] for x in c], [True, False])   # IEC yes, Iranian Art. 15 no


class Api(unittest.TestCase):
    def test_endpoint(self):
        d = api.dispatch("/api/earthpit", dict(rho=100, L=6, d=0.016, D=0.8, n=7, s=12,
                                               target=2, season_factor=1, I_fault=5000, t_fault=1,
                                               housing_class="m"))
        self.assertAlmostEqual(d["R_pit"], 8.95, delta=0.05)
        self.assertAlmostEqual(d["group"]["R"], 1.88, delta=0.02)
        self.assertEqual(d["required"]["n"], 7)
        self.assertEqual(d["housing"]["load_kN"], 15.0)
        self.assertIn("bs7430", d)
        self.assertAlmostEqual(d["maintenance"]["retest_limit"], 1.5 * d["R_pit"])

    def test_plate_endpoint(self):
        d = api.dispatch("/api/earthpit", dict(electrode="plate", rho=100, area=0.5, top=5.4,
                                               D=0.8, fill_top=4.7, fill_bottom=6.0,
                                               material="copper", thickness_mm=2))
        self.assertAlmostEqual(d["R_pit"], 17.24, delta=0.05)
        self.assertNotIn("bs7430", d)

    def test_validation(self):
        bad = [dict(rho=0, L=3, d=0.016, D=0.3), dict(rho=100, L=3, d=0.016, D=0.01),
               dict(rho=100, L=3, d=0.016, D=0.3, backfill="custom"),
               dict(rho=100, L=3, d=0.016, D=0.3, backfill="salt"),
               dict(rho=100, L=3, d=0.016, D=0.3, season_factor=0.5),
               dict(rho=100, L=3, d=0.016, D=0.3, fill_top=2, fill_bottom=1),
               dict(rho=100, L=3, d=0.016, D=0.3, housing_class="X")]
        for p in bad:
            with self.assertRaises(ValueError, msg=p):
                api.dispatch("/api/earthpit", p)

    def test_report_and_registry(self):
        d = api.dispatch("/api/earthpit", dict(rho=100, L=3, d=0.016, D=0.3))
        for lang in ("en", "fa"):
            html = report.build({"earthpit": d}, lang)
            self.assertIn("BS 7430 9.5.7", html)
            self.assertIn("IEC 62561-5:2023", html)
        ids = " ".join(s["id"] for s in st.REGISTRY)
        for key in ("62561-2", "62561-5", "62561-7", "CBIP", "Iranian"):
            self.assertIn(key, ids)


if __name__ == "__main__":
    unittest.main()
