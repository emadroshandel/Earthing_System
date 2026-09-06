"""
Validation of the impulse behaviour of an earth termination.

Run from the application folder:

    python -m unittest discover -s tests -v
    python tests/test_impulse.py

Everything here is checked against the closed form of the published
expression it implements, not against the program's own output, so a change
of coefficient or a change of units breaks a test rather than passing
quietly.  The physical sanity conditions — a shorter front reaches less
electrode, a corner feed uses less area than a centre feed, the effective
radius can never exceed the electrode — are asserted separately, because
those are the properties a designer actually relies on.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import iec62305 as z                       # noqa: E402


class TestEffectiveLength(unittest.TestCase):

    def test_matches_the_closed_form(self):
        for rho, tau in ((100.0, 1.0), (400.0, 0.25), (1000.0, 10.0)):
            for feed, k in (("end", 1.40), ("centre", 1.55)):
                self.assertAlmostEqual(
                    z.effective_length(rho, tau, feed)["L_eff"],
                    k * math.sqrt(rho * tau), places=10,
                    msg=f"{feed} feed, rho={rho}, tau={tau}")

    def test_the_textbook_value(self):
        """100 ohm.m soil, a 1 us front, fed at one end: about 14 m, which is
        why only the first ten or twenty metres of a long radial electrode
        does any work during the front."""
        self.assertAlmostEqual(
            z.effective_length(100.0, 1.0, "end")["L_eff"], 14.0, places=6)

    def test_a_centre_feed_reaches_further_than_an_end_feed(self):
        a = z.effective_length(400.0, 1.0, "centre")["L_eff"]
        b = z.effective_length(400.0, 1.0, "end")["L_eff"]
        self.assertGreater(a, b)
        self.assertAlmostEqual(a / b, 1.55 / 1.40, places=10)

    def test_a_faster_front_reaches_less_electrode(self):
        prev = float("inf")
        for tau in (10.0, 1.0, 0.25):
            L = z.effective_length(200.0, tau)["L_eff"]
            self.assertLess(L, prev)
            prev = L

    def test_zero_or_negative_inputs_are_refused(self):
        for rho, tau in ((0.0, 1.0), (100.0, 0.0), (-1.0, 1.0)):
            with self.assertRaises(ValueError):
                z.effective_length(rho, tau)


class TestEffectiveArea(unittest.TestCase):
    """The 70 x 70 m grid at 7 m spacing that the program offers by default,
    in 400 ohm.m soil — the case worked through in the theory chapter."""

    AREA = 70.0 * 70.0
    RHO = 400.0
    SPACING = 7.0

    def _gt(self, T, injection):
        return z.effective_area(self.RHO, T, self.AREA, self.SPACING,
                                injection)["models"][0]

    def test_gupta_thapar_centre_fed(self):
        m = self._gt(1.0, "centre")
        self.assertEqual(m["name"], "Gupta & Thapar")
        self.assertAlmostEqual(m["K"], 1.45 - 0.05 * self.SPACING, places=12)
        self.assertAlmostEqual(m["r"], 22.0, places=6)
        self.assertAlmostEqual(m["fraction"], math.pi * 22.0 ** 2 / self.AREA,
                               places=9)

    def test_gupta_thapar_corner_fed(self):
        m = self._gt(1.0, "corner")
        self.assertAlmostEqual(m["K"], 0.60 - 0.025 * self.SPACING, places=12)
        self.assertAlmostEqual(m["r"], 8.5, places=6)

    def test_centre_and_corner_are_told_apart(self):
        """They share a first letter; a prefix test on them silently returns
        the optimistic answer for both, which is the dangerous direction."""
        c = z.effective_area(self.RHO, 1.0, self.AREA, self.SPACING, "centre")
        k = z.effective_area(self.RHO, 1.0, self.AREA, self.SPACING, "corner")
        self.assertEqual(c["injection"], "centre")
        self.assertEqual(k["injection"], "corner")
        self.assertGreater(c["r_min"], k["r_min"])

    def test_grcev_matches_its_closed_form(self):
        for inj, K in (("centre", 1.0), ("corner", 0.5)):
            a = z.effective_area(self.RHO, 1.0, self.AREA, self.SPACING, inj)
            m = [x for x in a["models"] if x["name"] == "Grcev"][0]
            self.assertAlmostEqual(
                m["r"], K * math.exp(0.84 * (self.RHO * 1.0) ** 0.22),
                places=9)

    def test_the_effective_radius_never_exceeds_the_electrode(self):
        a = z.effective_area(self.RHO, 60.0, self.AREA, self.SPACING, "centre")
        self.assertTrue(a["fully_used"])
        for m in a["models"]:
            self.assertLessEqual(m["r"], a["geometric_radius"] + 1e-9)
            self.assertLessEqual(m["fraction"], 1.0 + 1e-12)

    def test_a_slow_front_brings_the_whole_grid_into_use(self):
        fast = z.effective_area(self.RHO, 1.0, self.AREA, self.SPACING, "centre")
        slow = z.effective_area(self.RHO, 8.0, self.AREA, self.SPACING, "centre")
        self.assertLess(fast["fraction_min"], 0.5)
        self.assertTrue(slow["fully_used"])

    def test_the_published_estimates_disagree_and_the_spread_is_reported(self):
        a = z.effective_area(1000.0, 1.0, 1e6, 7.0, "centre")
        self.assertGreater(a["spread"], 1.2)
        self.assertAlmostEqual(a["spread"], a["r_max"] / a["r_min"], places=9)
        self.assertEqual(a["governing"],
                         min(a["models"], key=lambda m: m["r"])["name"])

    def test_a_spacing_outside_the_fitted_band_is_flagged(self):
        m = self._gt(1.0, "centre")
        self.assertFalse(m["out_of_range"])
        wide = z.effective_area(self.RHO, 1.0, self.AREA, 25.0,
                                "centre")["models"][0]
        self.assertTrue(wide["out_of_range"])
        self.assertIn("outside", wide["note"])

    def test_bad_inputs_are_refused(self):
        for args in ((0.0, 1.0, 100.0), (100.0, 0.0, 100.0), (100.0, 1.0, 0.0)):
            with self.assertRaises(ValueError):
                z.effective_area(*args)


class TestImpulseResponse(unittest.TestCase):

    def test_the_coefficient_is_the_ratio_of_the_radii(self):
        r = z.impulse_response(400.0, 1.0, 2.0, area=4900.0, spacing=7.0,
                               injection="centre")
        self.assertAlmostEqual(r["impulse_coefficient"],
                               r["r_geometric"] / r["r_effective"], places=10)
        self.assertAlmostEqual(r["Z_impulse"],
                               2.0 * r["impulse_coefficient"], places=10)

    def test_a_corner_feed_is_the_more_onerous_case(self):
        c = z.impulse_response(400.0, 1.0, 2.0, area=4900.0, injection="centre")
        k = z.impulse_response(400.0, 1.0, 2.0, area=4900.0, injection="corner")
        self.assertGreater(k["impulse_coefficient"],
                           c["impulse_coefficient"])
        self.assertGreater(k["EPR_impulse"], c["EPR_impulse"])

    def test_the_coefficient_never_falls_below_one(self):
        """A slow front cannot make the electrode better than it is at d.c."""
        r = z.impulse_response(100.0, 10.0, 2.0, area=400.0, injection="centre")
        self.assertAlmostEqual(r["impulse_coefficient"], 1.0, places=12)
        self.assertAlmostEqual(r["Z_impulse"], r["R_lf"], places=12)

    def test_the_impulse_potential_rise_is_never_the_smaller_one(self):
        r = z.impulse_response(400.0, 0.25, 4.0, area=4900.0, injection="corner",
                               I_kA=100.0)
        self.assertGreaterEqual(r["EPR_impulse"], r["EPR_lf"])
        self.assertAlmostEqual(r["EPR_lf"], 4.0 * 100.0 * 1000.0, places=6)

    def test_wasted_length_is_reported_only_when_there_is_some(self):
        long_ = z.impulse_response(100.0, 1.0, 5.0, extent=40.0,
                                   injection="corner")
        self.assertAlmostEqual(long_["wasted_length"], 40.0 - 14.0, places=6)
        centre = z.impulse_response(100.0, 1.0, 5.0, extent=40.0,
                                    injection="centre")
        self.assertAlmostEqual(centre["wasted_length"], 40.0 - 15.5, places=6)
        short = z.impulse_response(100.0, 1.0, 5.0, extent=8.0)
        self.assertIsNone(short["wasted_length"])

    def test_it_works_without_a_mesh_spacing(self):
        r = z.impulse_response(200.0, 1.0, 6.0, extent=12.0)
        self.assertIsNone(r["area"])
        self.assertAlmostEqual(r["r_effective"], r["linear"]["L_eff"], places=12)


class TestDesignIntegration(unittest.TestCase):

    @staticmethod
    def _d(**kw):
        args = dict(lps_class="III", rho=400.0, area=4900.0, perimeter=280.0,
                    arrangement="B", mesh_spacing=7.0, front_time=1.0,
                    injection="centre")
        args.update(kw)
        return z.design(**args)

    def test_the_design_carries_an_impulse_result(self):
        imp = self._d()["impulse"]
        self.assertAlmostEqual(imp["area"]["models"][0]["r"], 22.0, places=6)
        self.assertAlmostEqual(imp["r_geometric"],
                               math.sqrt(4900.0 / math.pi), places=9)

    def test_the_stroke_current_comes_from_the_class(self):
        for cls, I in (("I", 200.0), ("II", 150.0), ("III", 100.0),
                       ("IV", 100.0)):
            self.assertAlmostEqual(self._d(lps_class=cls)["impulse"]["I_kA"],
                                   I, places=9)

    def test_leaving_the_spacing_out_still_gives_the_effective_length(self):
        imp = self._d(mesh_spacing=None)["impulse"]
        self.assertIsNone(imp["area"])
        self.assertGreater(imp["linear"]["L_eff"], 0.0)

    def test_a_type_a_arrangement_is_measured_by_its_electrode_length(self):
        d = self._d(arrangement="A", mesh_spacing=None)
        self.assertAlmostEqual(d["impulse"]["electrode_extent"],
                               d["earth"]["L_used"], places=12)

    def test_adding_the_impulse_did_not_change_the_verdict(self):
        """The impulse section is advisory; the IEC 62305-3 compliance
        decision must be exactly what it was before it existed."""
        d = self._d()
        self.assertEqual([c["name"] for c in d["checks"]],
                         ["Earth-termination geometry",
                          "Earthing resistance ≤ 10 Ω (recommended)",
                          "Number of down-conductors"])
        self.assertEqual(d["passed"], all(c["passed"] for c in d["checks"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
