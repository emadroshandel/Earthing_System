"""
Validation of the air-termination module against IEC 62305-3.

Run from the application folder:

    python -m unittest discover -s tests -v
    python tests/test_airterm.py

The numerical rolling sphere and the closed forms of Annex A are two
independent routes to the same geometry, so each is used to check the other.
Where the standard states a value directly — the sphere radius, the mesh size,
the down-conductor spacing — that value is asserted on its own.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import airterm as at                        # noqa: E402


class TestClassParameters(unittest.TestCase):
    """IEC 62305-3:2010 Table 2 and Table 4."""

    def test_rolling_sphere_radius(self):
        self.assertEqual(at.ROLLING_SPHERE_R,
                         {"I": 20.0, "II": 30.0, "III": 45.0, "IV": 60.0})

    def test_mesh_size(self):
        self.assertEqual(at.MESH_SIZE,
                         {"I": 5.0, "II": 10.0, "III": 15.0, "IV": 20.0})

    def test_down_conductor_spacing(self):
        self.assertEqual(at.DOWN_SPACING,
                         {"I": 10.0, "II": 10.0, "III": 15.0, "IV": 20.0})

    def test_unknown_class_falls_back_to_iii(self):
        self.assertEqual(at.class_data("nonsense")["lps_class"], "III")


class TestClosedFormRollingSphere(unittest.TestCase):
    """Annex A.2, derived from the circle the resting sphere describes."""

    def test_protection_radius_matches_the_formula(self):
        for cls, h in (("I", 5.0), ("II", 10.0), ("III", 12.0), ("IV", 25.0)):
            R = at.ROLLING_SPHERE_R[cls]
            self.assertAlmostEqual(at.protection_radius(R, h, 0.0),
                                   math.sqrt(2 * R * h - h * h), places=10,
                                   msg="class " + cls)

    def test_protection_radius_at_a_raised_reference_plane(self):
        R, h, hx = 45.0, 20.0, 5.0
        expected = math.sqrt(2 * R * h - h * h) - math.sqrt(2 * R * hx - hx * hx)
        self.assertAlmostEqual(at.protection_radius(R, h, hx), expected, places=10)

    def test_a_mast_taller_than_the_sphere_saturates_at_R(self):
        """Once the mast is as tall as the sphere, its own body holds the
        sphere off at exactly R and the protected radius stops growing."""
        R = 30.0
        for h in (R, 1.5 * R, 3.0 * R):
            self.assertAlmostEqual(at.protection_radius(R, h, 0.0), R, places=9)

    def test_nothing_is_protected_below_the_reference_plane(self):
        self.assertEqual(at.protection_radius(45.0, 2.0, 5.0), 0.0)

    def test_sag_known_value(self):
        """Two terminations 40 m apart under a class II sphere."""
        self.assertAlmostEqual(at.sphere_sag(30.0, 40.0),
                               30.0 - math.sqrt(900.0 - 400.0), places=10)

    def test_sag_and_max_span_are_inverses(self):
        R, h = 45.0, 6.0
        d = at.max_span(R, h, 0.0)
        self.assertAlmostEqual(at.sphere_sag(R, d), h, places=9)


class TestNumericalRoll(unittest.TestCase):
    """The march over the capture points must reproduce the closed forms."""

    def test_single_mast_protected_radius(self):
        R, h = 45.0, 10.0
        pts, _ = at.build_geometry({"width": 0, "height": 0},
                                   [{"x": 0.0, "height": h, "base": 0.0}], R=R)
        prof = at.roll_sphere(pts, R, -80, 80, samples=3201)
        edge = max(x for x, z in zip(prof["x"], prof["z"]) if z > 1e-6)
        self.assertAlmostEqual(edge, at.protection_radius(R, h, 0.0), delta=0.1)

    def test_sag_between_two_masts(self):
        R, h, d = 45.0, 10.0, 30.0
        pts, _ = at.build_geometry(
            {"width": 0, "height": 0},
            [{"x": -d / 2, "height": h, "base": 0.0},
             {"x": d / 2, "height": h, "base": 0.0}], R=R)
        prof = at.roll_sphere(pts, R, -80, 80, samples=3201)
        mid = at._profile_height(prof, 0.0)
        self.assertAlmostEqual(mid, h - at.sphere_sag(R, d), delta=0.05)

    def test_the_boundary_never_dips_below_the_plane(self):
        pts, _ = at.build_geometry({"width": 12, "height": 8},
                                   [{"x": 0.0, "height": 3.0}], R=45.0)
        prof = at.roll_sphere(pts, 45.0, -60, 60)
        self.assertGreaterEqual(min(prof["z"]), 0.0)


class TestDesignAssessment(unittest.TestCase):

    @staticmethod
    def _named(d):
        return {c["name"]: c["passed"] for c in d["checks"]}

    def test_a_central_rod_leaves_the_roof_edges_exposed(self):
        """A sphere resting on the ground beside the wall reaches the roof edge
        long before it reaches the middle, which is why IEC 62305-3 asks for
        terminations on the corners and along the exposed edges."""
        d = at.design("III", {"width": 20, "height": 10},
                      [{"x": 0, "height": 5}], roof_depth=15)
        n = self._named(d)
        self.assertTrue(n["Rolling sphere — roof surface"])
        self.assertFalse(n["Rolling sphere — roof edges and corners"])

    def test_corner_terminations_tall_enough_protect_the_roof(self):
        d = at.design("III", {"width": 20, "height": 10},
                      [{"x": -10, "y": -7.5, "height": 2},
                       {"x": 10, "y": -7.5, "height": 2},
                       {"x": 10, "y": 7.5, "height": 2},
                       {"x": -10, "y": 7.5, "height": 2},
                       {"x": 0, "y": 0, "height": 2}], roof_depth=15)
        n = self._named(d)
        self.assertTrue(n["Rolling sphere — roof surface"])
        self.assertTrue(n["Rolling sphere — roof edges and corners"])

    def test_terminations_sharing_a_station_are_one_support(self):
        """The elevation is a section, so two rods on the same x collapse."""
        d = at.design("III", {"width": 20, "height": 10},
                      [{"x": -10, "y": -7.5, "height": 1},
                       {"x": -10, "y": 7.5, "height": 1},
                       {"x": 10, "y": -7.5, "height": 1},
                       {"x": 10, "y": 7.5, "height": 1}], roof_depth=15)
        self.assertEqual(len(d["spans"]), 1)
        self.assertAlmostEqual(d["spans"][0]["d"], 20.0, places=6)

    def test_the_required_tip_height_closes_a_failing_span(self):
        d = at.design("III", {"width": 20, "height": 10},
                      [{"x": -10, "y": 0, "height": 1},
                       {"x": 10, "y": 0, "height": 1}], roof_depth=15)
        span = d["spans"][0]
        self.assertFalse(span["clears_reference"])
        need = span["required_tip"] - d["structure"]["height"]
        better = at.design("III", {"width": 20, "height": 10},
                           [{"x": -10, "y": 0, "height": need + 0.05},
                            {"x": 10, "y": 0, "height": need + 0.05}],
                           roof_depth=15)
        self.assertTrue(better["spans"][0]["clears_reference"])

    def test_two_masts_protect_a_tank_between_them(self):
        d = at.design("II", {"width": 0, "height": 0},
                      [{"x": -20, "y": 0, "height": 25, "base": 0},
                       {"x": 20, "y": 0, "height": 25, "base": 0}],
                      reference_plane=0.0,
                      equipment=[{"x": 0, "z": 6, "name": "tank shell"}])
        self.assertEqual(d["exposed_count"], 0)
        self.assertAlmostEqual(d["spans"][0]["sag"],
                               at.sphere_sag(30.0, 40.0), places=6)

    def test_design_needs_some_geometry(self):
        with self.assertRaises(ValueError):
            at.design("III", {"width": 0, "height": 0}, [])


class TestProtectiveAngle(unittest.TestCase):

    def test_refused_above_the_sphere_radius(self):
        r = at.protective_angle("III", 50.0)              # R = 45 m
        self.assertFalse(r["applicable"])
        self.assertIsNone(r["alpha"])

    def test_decreases_with_height(self):
        prev = 91.0
        for h in (2, 5, 10, 15, 20):
            a = at.protective_angle("III", h)["alpha"]
            self.assertLess(a, prev)
            prev = a

    def test_wider_for_the_lower_classes(self):
        """A larger sphere means a wider cone at the same height."""
        angles = [at.protective_angle(c, 10.0)["alpha"]
                  for c in ("I", "II", "III", "IV")]
        self.assertEqual(angles, sorted(angles))


class TestMeshMethod(unittest.TestCase):

    def test_spacing_and_down_conductors(self):
        m = at.mesh_method("III", 30.0, 20.0)
        self.assertEqual(m["mesh_required"], 15.0)
        self.assertLessEqual(m["actual_spacing_x"], 15.0 + 1e-9)
        self.assertLessEqual(m["actual_spacing_y"], 15.0 + 1e-9)
        self.assertTrue(m["compliant"])
        # perimeter 100 m at a 15 m typical spacing -> 7 down-conductors
        self.assertEqual(m["n_down"], 7)
        self.assertAlmostEqual(m["actual_down_spacing"], 100.0 / 7, places=9)

    def test_a_mesh_coarser_than_the_class_allows_is_flagged(self):
        self.assertFalse(at.mesh_method("I", 30.0, 20.0, mesh=12.0)["compliant"])


class TestPlanCoverage(unittest.TestCase):

    def test_corner_terminations_cover_the_roof(self):
        masts = [{"x": x, "y": y, "height": 2.0}
                 for x in (-10, 10) for y in (-7.5, 7.5)]
        pl = at.plan_coverage(45.0, masts, {"width": 20, "depth": 15})
        self.assertAlmostEqual(pl["covered_fraction"], 1.0, places=9)
        self.assertTrue(all(c["protected"] for c in pl["corners"]))

    def test_an_uncovered_area_is_found_and_located(self):
        pl = at.plan_coverage(45.0, [{"x": -30, "y": -30, "height": 1.0}],
                              {"width": 40, "depth": 40})
        self.assertLess(pl["covered_fraction"], 1.0)
        self.assertTrue(pl["uncovered"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
