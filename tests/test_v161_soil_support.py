"""1.6.1: the soil page must not present more layers than the readings
support.  A forced three- or four-layer model that fails the F test carries a
warning naming the supported model; unresolved layers and layers below the
reach of the traverse are flagged; the equivalence note is no longer hidden
for four layers; the section's depth line is the median depth of
investigation (Edwards, 1977)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from earthsys import api, layered, report  # noqa: E402

# the built-in example traverse: a genuine two-layer site
A = [1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 40]
R = [292, 279, 272, 229, 202, 156, 132, 120, 112, 112, 109, 108]
ROWS = [dict(a=a, rho=r) for a, r in zip(A, R)]
HERE = os.path.dirname(__file__)


def fit(layers, rows=ROWS, **kw):
    return api.api_soil_invert(dict(rows=rows, layers=layers, array="wenner", **kw))


class ForcedModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d2 = fit("auto")
        cls.d3 = fit("3")
        cls.d4 = fit("4")

    def test_auto_keeps_two_layers_without_warning(self):
        self.assertEqual(self.d2["n_layers"], 2)
        self.assertEqual(self.d2["model_warning"], "")
        self.assertTrue(all(s["resolved"] and not s["below_reach"]
                            for s in self.d2["layer_status"]))

    def test_forced_three_is_shown_but_warned(self):
        d = self.d3
        self.assertEqual(d["n_layers"], 3)
        self.assertEqual(d["model_selection"]["chosen"], 2)
        w = d["model_warning"]
        self.assertIn("do not support a three-layer model", w)
        self.assertIn("supported model is two layers", w)
        self.assertIn("297", w)              # the supported model's values
        self.assertIn("p = 0.78", w)
        self.assertNotIn("simpler model is kept", d["model_selection"]["reason"])
        st = d["layer_status"][2]
        self.assertTrue(st["below_reach"])   # 141 m on a 40 m traverse
        self.assertFalse(st["resolved"])

    def test_forced_four_reports_the_supported_count(self):
        """1.6.0 overwrote 'chosen' with 4 whenever four were requested, so
        the page showed no caution at all."""
        d = self.d4
        self.assertEqual(d["n_layers"], 4)
        self.assertEqual(d["model_selection"]["chosen"], 2)
        self.assertIn("do not support a four-layer model", d["model_warning"])
        self.assertIn("fourth layer", d["model_warning"])
        st = d["layer_status"]
        self.assertTrue(st[3]["below_reach"])
        self.assertFalse(st[2]["top_resolved"])
        self.assertTrue(st[2]["rho_resolved"])

    def test_four_layer_equivalence_note_is_not_hidden(self):
        self.assertIn("Layer 2 is poorly resolved", self.d4["fit_note"])
        self.assertIn("h₂ not at all", self.d4["fit_note"])

    def test_report_prints_the_warning_and_flags(self):
        html = report._sec_soil(report.T["en"], dict(self.d4, rho_equivalent=296.5))
        self.assertIn("do not support a four-layer model", html)
        self.assertIn("below the reach of the traverse", html)


class SupportedModels(unittest.TestCase):
    XS = [0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 100]

    def _rows(self, rr, hh):
        y = layered.apparent(layered.LayeredEarth(rr, hh), "wenner", self.XS)
        return [dict(a=a, rho=float(v)) for a, v in zip(self.XS, y)]

    def test_genuine_three_and_four_layer_sites_raise_no_warning(self):
        for rr, hh in (([300, 50, 1000], [2, 6]), ([100, 1000, 50, 500], [1, 4, 8])):
            d = fit(str(len(rr)), rows=self._rows(rr, hh))
            self.assertEqual(d["n_layers"], len(rr))
            self.assertEqual(d["model_selection"]["chosen"], len(rr))
            self.assertEqual(d["model_warning"], "")
            self.assertTrue(all(s["resolved"] and not s["below_reach"]
                                for s in d["layer_status"]))


class DepthOfInvestigation(unittest.TestCase):
    def test_edwards_medians(self):
        self.assertAlmostEqual(api.depth_of_investigation([40], "wenner")["doi"], 20.8)
        self.assertAlmostEqual(api.depth_of_investigation([40], "schlumberger")["doi"], 15.2)
        self.assertAlmostEqual(api.depth_of_investigation([10, 40])["reach"], 41.6)

    def test_result_carries_it(self):
        self.assertAlmostEqual(fit("auto")["depth_of_investigation"]["doi"], 20.8)


class FTest(unittest.TestCase):
    def test_general_closed_form(self):
        # two extra parameters: identical to the 1.4.0 closed form
        self.assertEqual(layered.f_test_nested(10, 8, 12, 3, 5),
                         layered._f_test_p(10, 8, 12))
        # four extra parameters: scipy.stats.f.sf(F, 4, 8) = 0.33696
        F, p = layered.f_test_nested(10, 6, 15, 3, 7)
        self.assertAlmostEqual(p, 0.33696, places=5)
        self.assertEqual(layered.f_test_nested(10, 12, 15, 3, 7)[1], 1.0)


class Interface(unittest.TestCase):
    def _src(self, name):
        with open(os.path.join(HERE, "..", "web", name), encoding="utf-8") as f:
            return f.read()

    def test_page_shows_the_warning_and_asks_before_using_it(self):
        js = self._src("app.js")
        self.assertIn("Not supported by the readings.", js)
        self.assertIn("S.soil.fit_warning || S.soil.model_warning", js)
        self.assertIn("confirmPoorFit('#nSoilPull'", js)
        self.assertNotIn("treat its extra parameters with caution", js)

    def test_section_veils_layers_and_uses_the_median_depth(self):
        js = self._src("sections.js")
        self.assertIn("median depth of investigation", js)
        self.assertNotIn("≈ a_max =", js)
        self.assertIn("veil: veil(3)", js)
        self.assertIn("i % 2 === 0 && i < 4", self._src("draw.js"))

    def test_version(self):
        self.assertEqual(api.APP_VERSION, "1.6.1")


if __name__ == "__main__":
    unittest.main()
