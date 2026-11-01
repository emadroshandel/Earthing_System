"""1.8.3: Latin hypercube soil sampling with confidence intervals, and fences
in the non-equipotential solution."""
import math
import unittest

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None

from earthsys import api, governing

FIT = dict(n_layers=2, uncertainty=dict(
    rho1=dict(value=300, sd_pct=10), rho2=dict(value=100, sd_pct=20),
    h=dict(value=2.0, sd_pct=15), corr_rho1_h=-0.5))


@unittest.skipIf(np is None, "numpy needed")
class TestSampling(unittest.TestCase):

    def test_inverse_normal(self):
        from statistics import NormalDist
        from earthsys import studies
        u = np.array([1e-6, 0.01, 0.1, 0.5, 0.9, 0.99, 1 - 1e-6])
        ref = np.array([NormalDist().inv_cdf(float(x)) for x in u])
        self.assertLess(float(np.max(np.abs(studies._norm_ppf(u) - ref))), 1e-7)

    def test_latin_hypercube_fills_every_stratum(self):
        from statistics import NormalDist
        from earthsys import studies
        n = 20
        Z = studies.latin_hypercube_normal(n, 3, np.random.default_rng(5))
        for j in range(3):
            strata = sorted(int(NormalDist().cdf(float(z)) * n) for z in Z[:, j])
            self.assertEqual(strata, list(range(n)))

    def test_lhs_mean_is_steadier_than_random(self):
        from earthsys import studies
        err = {}
        for m in ("lhs", "random"):
            e = []
            for seed in range(30):
                smp, _ = studies.soil_samples(FIT, 10, seed=seed, method=m)
                e.append(np.mean(np.log([s["rho"][0] for s in smp])) - math.log(300))
            err[m] = float(np.std(e))
        self.assertLess(err["lhs"], 0.5 * err["random"])

    def test_wilson_interval(self):
        from earthsys import studies
        lo, hi = studies.wilson_interval(10, 20)
        self.assertAlmostEqual(lo, 0.299, places=3)
        self.assertAlmostEqual(hi, 0.701, places=3)
        lo, hi = studies.wilson_interval(20, 20)
        self.assertEqual(hi, 1.0)
        self.assertGreater(lo, 0.8)

    def test_monte_carlo_reports_confidence(self):
        p = dict(rho1=300, rho2=100, h_layer=2.0, IG=1000, segment_length=3, nx=15,
                 items=[dict(kind="grid", Lx=10, Ly=10, D=5, depth=0.5)],
                 limits=dict(E_touch=1e6, E_step=1e6), soil_fit=FIT, samples=6)
        m = api.dispatch("/api/bem/montecarlo", p)
        self.assertEqual(m["method"], "lhs")
        self.assertEqual(m["p_pass"], 1.0)
        lo, hi = m["ci95"]["p_pass"]
        self.assertLess(lo, 1.0)
        self.assertEqual(hi, 1.0)
        self.assertIn("95 % confidence", m["note"])
        self.assertAlmostEqual(m["conf_max_above_p95"], 1 - 0.95 ** 6)
        with self.assertRaises(ValueError):
            api.dispatch("/api/bem/montecarlo", dict(p, sampling="sobol"))


@unittest.skipIf(np is None, "numpy needed")
class TestFencesNonEquipotential(unittest.TestCase):

    GRID = dict(kind="grid", Lx=20, Ly=20, D=5, depth=0.5)

    def _run(self, bonded):
        fence = dict(kind="fence", x0=-2, y0=-2, Lx=24, Ly=24, post_spacing=4, post_depth=0.76,
                     post_radius=0.025, bonded=bonded, name="perimeter fence")
        p = dict(rho1=100, IG=2000, items=[self.GRID, fence], segment_length=4, nx=15,
                 limits=dict(E_touch=500, E_step=2000))
        b = api.dispatch("/api/bem", dict(p))
        pf = api.dispatch("/api/bem/powerfreq", dict(p, metal="copper", feeds=[dict(x=0, y=0)]))
        return b, pf

    def test_isolated_fence_matches_the_equipotential_solution_for_a_compact_grid(self):
        b, pf = self._run(False)
        self.assertEqual(len(pf["fences"]), 1)
        f, fb = pf["fences"][0], b["fences"][0]
        self.assertFalse(f["bonded"])
        self.assertAlmostEqual(f["V_fence"], fb["V_fence"], delta=0.02 * fb["V_fence"])
        self.assertLess(f["V_fence"], 0.9 * pf["GPR_feed"])         # it floats below the GPR
        self.assertAlmostEqual(f["touch_max"], abs(fb["touch_max"]), delta=0.05 * abs(fb["touch_max"]))
        names = [c["name"] for c in pf["checks"]]
        self.assertIn("Fence touch voltage (perimeter fence, non-equipotential)", names)

    def test_bonded_fence_sits_at_the_grid_potential(self):
        b, pf = self._run(True)
        f = pf["fences"][0]
        self.assertTrue(f["bonded"])
        self.assertIsNotNone(f["bond_at"])
        self.assertAlmostEqual(f["V_fence"], pf["GPR_feed"], delta=0.02 * pf["GPR_feed"])

    def test_governing_takes_the_larger_fence_touch(self):
        bem = dict(model_key="k", touch_max=400.0, step_max=100.0, Rg=1.0, GPR=1000.0, checks=[
            dict(name="Maximum touch voltage", value=400.0, limit=500.0, passed=True),
            dict(name="Maximum step voltage", value=100.0, limit=900.0, passed=True),
            dict(name="Fence touch voltage (F1)", value=450.0, limit=500.0, passed=True,
                 fence=dict(name="F1"))])
        pf = dict(model_key="k", touch_max=405.0, step_max=100.0, GPR_feed=1000.0,
                  fences=[dict(name="F1", touch_max=530.0)])
        g = governing.governing(bem, dict(powerfreq=pf))
        fc = [c for c in g["checks"] if c["name"].startswith("Fence touch voltage (F1)")][0]
        self.assertAlmostEqual(fc["value"], 530.0)
        self.assertEqual(fc["source"], "powerfreq")
        self.assertFalse(g["passed"])


if __name__ == "__main__":
    unittest.main()
