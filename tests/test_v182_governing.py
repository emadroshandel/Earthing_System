"""1.8.2: the governing values of the numerical page.

Up to 1.8.1 the studies of page 5 (convergence, seasonal soil, soil
uncertainty, non-equipotential solution) were reported but the verdict, the
report's compliance table and the drawing stamp used the plain solution
alone.  These tests check that the worst applicable value now decides, that
a study from another model is ignored, and that the report and the drawings
carry the governing verdict.
"""
import unittest

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None

from earthsys import api, governing, report

GRID = [dict(kind="grid", Lx=20, Ly=20, D=5, depth=0.5, radius=0.005)]
BASE = dict(rho1=100, IG=1000, items=GRID, segment_length=2.5, nx=21)


def _bem(touch=400.0, step=150.0, Rg=1.5, key="k1", limits=(500.0, 900.0), zones=()):
    checks = [dict(name="Maximum touch voltage", value=touch, limit=limits[0], unit="V",
                   passed=touch <= limits[0]),
              dict(name="Maximum step voltage", value=step, limit=limits[1], unit="V",
                   passed=step <= limits[1])]
    for name, v in zones:
        checks.append(dict(name=f"Touch voltage at {name}", value=v, limit=limits[0], unit="V",
                           passed=v <= limits[0]))
    return dict(model_key=key, touch_max=touch, step_max=step, Rg=Rg, GPR=Rg * 1000,
                checks=checks)


class TestModelKey(unittest.TestCase):

    def test_same_model_same_key(self):
        a = governing.model_key(dict(BASE))
        b = governing.model_key(dict(BASE, nx=61, limits=dict(E_touch=1), segment_length=1))
        self.assertEqual(a, b)

    def test_numbers_written_differently_match(self):
        a = governing.model_key(dict(BASE, rho1=100))
        b = governing.model_key(dict(BASE, rho1="100.0"))
        self.assertEqual(a, b)

    def test_changed_soil_geometry_or_current_change_the_key(self):
        a = governing.model_key(dict(BASE))
        self.assertNotEqual(a, governing.model_key(dict(BASE, rho1=101)))
        self.assertNotEqual(a, governing.model_key(dict(BASE, rho2=300, h_layer=2)))
        self.assertNotEqual(a, governing.model_key(dict(BASE, IG=1100)))
        g2 = [dict(GRID[0], D=4)]
        self.assertNotEqual(a, governing.model_key(dict(BASE, items=g2)))


class TestCombination(unittest.TestCase):

    def test_plain_solution_alone(self):
        g = governing.governing(_bem(), {})
        self.assertTrue(g["passed"])
        self.assertEqual(g["quantities"]["touch"]["source"], "base")
        self.assertEqual(g["studies_used"], [])

    def test_largest_value_governs_and_is_named(self):
        st = dict(
            convergence=dict(model_key="k1", h=2.5, h_half=1.25,
                             touch=dict(design=420.0, extrapolated=420.0),
                             step=dict(design=151.0, extrapolated=151.0),
                             Rg=dict(extrapolated=1.52), GPR=dict(extrapolated=1520.0)),
            seasonal=dict(model_key="k1", cases=[
                dict(name="As measured", touch=400.0, step=150.0, Rg=1.5, GPR=1500.0),
                dict(name="Dry season", touch=470.0, step=180.0, Rg=1.9, GPR=1900.0)]),
            montecarlo=dict(model_key="k1", n=20, stats=dict(
                touch=dict(p95=455.0), step=dict(p95=190.0), Rg=dict(p95=1.7), GPR=dict(p95=1700.0))),
        )
        g = governing.governing(_bem(), st)
        q = g["quantities"]
        self.assertAlmostEqual(q["touch"]["value"], 470.0)
        self.assertEqual(q["touch"]["source"], "seasonal")
        self.assertEqual(q["touch"]["detail"], "Dry season")
        self.assertAlmostEqual(q["step"]["value"], 190.0)
        self.assertEqual(q["step"]["source"], "montecarlo")
        self.assertTrue(g["passed"])
        self.assertEqual(g["studies_used"], ["convergence", "montecarlo", "seasonal"])

    def test_study_turns_a_pass_into_a_fail(self):
        st = dict(powerfreq=dict(model_key="k1", touch_max=560.0, step_max=160.0,
                                 GPR_feed=1800.0, Z=dict(abs=1.8), metal="steel", f=50))
        g = api.api_bem_governing(dict(bem=_bem(), studies=st))
        self.assertFalse(g["passed"])
        touch = g["checks"][0]
        self.assertFalse(touch["passed"])
        self.assertEqual(touch["source"], "powerfreq")
        self.assertIn("impedance", " ".join(touch["remedy"]))
        self.assertIn("plain solution passes", g["note"])

    def test_study_from_another_model_is_ignored(self):
        st = dict(powerfreq=dict(model_key="OLD", touch_max=900.0, step_max=900.0))
        g = governing.governing(_bem(), st)
        self.assertTrue(g["passed"])
        self.assertEqual(g["studies_stale"], ["powerfreq"])
        self.assertIn("Out of date", g["note"])

    def test_zone_checks_scale_with_the_governing_touch(self):
        st = dict(seasonal=dict(model_key="k1", cases=[dict(name="Dry season", touch=480.0,
                                                            step=150.0, Rg=1.5, GPR=1500.0)]))
        g = governing.governing(_bem(zones=[("Transformer", 450.0)]), st)
        z = [c for c in g["checks"] if c["name"].startswith("Touch voltage at Transformer")][0]
        self.assertAlmostEqual(z["value"], 450.0 * 480.0 / 400.0)
        self.assertFalse(z["passed"])                 # 540 V > 500 V

    def test_no_limits_no_verdict(self):
        b = _bem()
        b.pop("checks")
        g = governing.governing(b, {})
        self.assertIsNone(g["passed"])
        self.assertEqual(g["checks"], [])

    def test_needs_a_solution(self):
        with self.assertRaises(ValueError):
            api.dispatch("/api/bem/governing", dict(studies={}))


class TestOutputs(unittest.TestCase):

    def test_report_prints_the_governing_section(self):
        st = dict(powerfreq=dict(model_key="k1", touch_max=560.0, step_max=160.0,
                                 GPR_feed=1800.0, Z=dict(abs=1.8), metal="steel", f=50))
        g = api.api_bem_governing(dict(bem=_bem(), studies=st))
        b = dict(_bem(), governing=g, soil="uniform", segments=10)
        for lang in ("en", "fa"):
            html = report.build(dict(meta={}, bem=b), lang)
            self.assertIn("560", html)
        self.assertIn("Governing values", report.build(dict(meta={}, bem=b), "en"))

    def test_drawings_stamp_follows_the_governing_verdict(self):
        items = [dict(kind="grid", Lx=30, Ly=20, D=5, depth=0.5, radius=0.005, x0=0, y0=0)]
        meta = dict(owner="Example Owner", designer="Example Consultants",
                    project="Example Project", prefix="T", status="IFA")
        for passed, status in ((True, "OK"), (False, "FAIL")):
            r = api.dispatch("/api/drawings", dict(
                results=dict(bem=dict(_in=dict(items=items), passed=passed)),
                meta=meta, options=dict(fence=False), save=False))
            row = [c for c in r["checks"] if c["item"].startswith("Numerical analysis")]
            self.assertEqual(len(row), 1)
            self.assertEqual(row[0]["status"], status)


@unittest.skipIf(np is None, "numpy needed")
class TestEndToEnd(unittest.TestCase):

    def test_solution_and_study_share_the_model_key(self):
        b = api.dispatch("/api/bem", dict(BASE, limits=dict(E_touch=5000, E_step=9000)))
        cv = api.dispatch("/api/bem/convergence", dict(BASE))
        self.assertEqual(b["model_key"], cv["model_key"])
        g = api.dispatch("/api/bem/governing", dict(bem=b, studies=dict(convergence=cv)))
        self.assertEqual(g["studies_used"], ["convergence"])
        self.assertGreaterEqual(g["quantities"]["touch"]["value"], b["touch_max"] - 1e-9)
        cv2 = api.dispatch("/api/bem/convergence", dict(BASE, rho1=120))
        g2 = api.dispatch("/api/bem/governing", dict(bem=b, studies=dict(convergence=cv2)))
        self.assertEqual(g2["studies_stale"], ["convergence"])


if __name__ == "__main__":
    unittest.main()
