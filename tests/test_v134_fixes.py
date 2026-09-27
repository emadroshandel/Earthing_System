"""Regression tests for the corrections made in version 1.3.4."""
import math
import os
import unittest

from earthsys import api, bem, faultcurrent, report


class TestFaultLimits(unittest.TestCase):
    """IEEE 80 Eq. (84) and the IEC 60909 factor m at X/R = 0 and X/R = inf."""

    def test_decrement_limits(self):
        self.assertAlmostEqual(faultcurrent.decrement_factor(0.5, float("inf"), 50)["Df"],
                               math.sqrt(3.0))
        self.assertAlmostEqual(faultcurrent.decrement_factor(0.5, 0.0, 50)["Df"], 1.0)
        # continuity with the finite formula
        self.assertAlmostEqual(faultcurrent.decrement_factor(0.5, 1e7, 50)["Df"],
                               math.sqrt(3.0), places=4)

    def test_thermal_limit(self):
        th = faultcurrent.thermal_equivalent(10.0, 0.5, float("inf"), 50)
        self.assertAlmostEqual(th["m"], 2.0)
        self.assertAlmostEqual(th["Ith_kA"], 10.0 * math.sqrt(3.0))

    def test_pure_reactance_fault_api(self):
        r = api.dispatch("/api/fault", dict(
            Un_kV=20, tf=0.5, ts=0.5, frequency=50, mode="impedance",
            Z1={"r": 0, "x": 2}, Z0={"r": 0, "x": 6}, Sf=1))
        self.assertAlmostEqual(r["Df"], math.sqrt(3.0))
        self.assertTrue(math.isfinite(r["IG_kA"]))

    def test_resistive_source(self):
        r = api.dispatch("/api/fault", dict(
            Un_kV=20, tf=0.5, ts=0.5, frequency=50, mode="source",
            Sk_MVA=500, xr_source=0))
        # purely resistive loop: no d.c. offset, and not the X/R = 10 default
        self.assertAlmostEqual(r["Df"], 1.0)


class TestJointTemperature(unittest.TestCase):
    """A joint can lower T_m but never raise it above the material's own."""

    def test_weld_on_aluminium(self):
        r = api.dispatch("/api/conductor", dict(I_kA=10, tc=0.5, material="al_ec",
                                                joint="welded_exothermic"))
        self.assertEqual(r["ieee80"]["Tm"], 657.0)
        self.assertAlmostEqual(r["ieee80"]["area_mm2"], 43.4, delta=0.1)

    def test_brazed_zinc_steel(self):
        r = api.dispatch("/api/conductor", dict(I_kA=10, tc=0.5, material="zn_steel_rod",
                                                joint="brazed"))
        self.assertEqual(r["ieee80"]["Tm"], 419.0)

    def test_copper_unchanged(self):
        r = api.dispatch("/api/conductor", dict(I_kA=10, tc=0.5, material="cu_hard",
                                                joint="brazed"))
        self.assertEqual(r["ieee80"]["Tm"], 450.0)


class TestNoSurfaceLayer(unittest.TestCase):
    def test_failing_design_without_surface_layer(self):
        p = dict(rho=400, rho_s=0, hs=0.1, ts=0.5, Lx=70, Ly=70, D=7, h=0.5,
                 d=0.01, IG_kA=1.908)
        r = api.dispatch("/api/ieee80/design", p)
        self.assertFalse(r["passed"])
        mesh = [c for c in r["checks"] if c["name"].startswith("Mesh")][0]
        self.assertTrue(any("No surface layer" in x for x in mesh["remedy"]))

    def test_step_meaning_text(self):
        p = dict(rho=400, rho_s=2500, hs=0.102, ts=0.5, Lx=70, Ly=70, D=7,
                 h=0.5, d=0.01, IG_kA=1.908)
        r = api.dispatch("/api/ieee80/design", p)
        step = [c for c in r["checks"] if c["name"].startswith("Step")][0]
        self.assertNotIn("hand-to-feet", step["meaning"] + step["verdict"])


class TestOptimiseLayout(unittest.TestCase):
    def test_added_rods_drawn_on_perimeter(self):
        p = dict(rho=400, rho_s=2500, hs=0.102, ts=0.5, Lx=20, Ly=20, D=7,
                 h=0.5, d=0.01, IG_kA=1.0, rods_on_perimeter=False)
        r = api.dispatch("/api/ieee80/optimise", p)
        self.assertTrue(r["found"])
        best = r["best"]
        self.assertTrue(best["n_rods"])
        for x, y in best["result"]["layout"]["rods"]:
            on_edge = (min(abs(x), abs(x - 20)) < 1e-9 or min(abs(y), abs(y - 20)) < 1e-9)
            self.assertTrue(on_edge, (x, y))


class TestReport(unittest.TestCase):
    def test_conductor_selected_size(self):
        c = api.dispatch("/api/conductor", dict(I_kA=2, tc=0.5, material="cu_hard",
                                                corrosion_protected=False))
        self.assertEqual(c["ieee80"]["standard_mm2"], 6)
        self.assertEqual(c["selected_mm2"], 25.0)
        d = dict(c["ieee80"], selected_mm2=c["selected_mm2"], off_scale=False)
        html = report.build(dict(conductor=d))
        row = html.split("Selected standard size")[1].split("</tr>")[0]
        self.assertIn(">25.00<", row.replace(" ", ""))

    def test_sysgnd_method_name(self):
        s = api.dispatch("/api/system-grounding", dict(V_ll_kV=6.6, frequency=50,
                                                       cable_km=2, continuity_critical=True))
        html = report.build(dict(sysgnd=s))
        self.assertIn("High-resistance grounded", html)
        self.assertNotIn(">high_resistance<", html)


@unittest.skipUnless(bem.HAVE_NUMPY, "numpy required")
class TestBemImageTail(unittest.TestCase):
    """Deep images beyond the explicit 60 are now included (thin soil on rock)."""

    def _rg(self, rho2, max_images=60):
        s = bem.SoilModel(100, rho2, 1.0, max_images=max_images)
        n = bem.Network(s, 1000.0)
        n.add_grid(20, 20, 5, 0.5, 0.005)
        n.discretise(2.5)
        return n.solve()["Rg"]

    def test_high_contrast_matches_full_series(self):
        # Full explicit series (1382 images, 30 s) gives 48.659 ohm; 1.3.3
        # stopped at 60 images and gave 41.53 ohm (-15 %).
        self.assertAlmostEqual(self._rg(20000), 48.659, delta=0.01)

    def test_moderate_contrast(self):
        # full series (277 images) 26.4378 ohm; 60 images gave 26.238
        self.assertAlmostEqual(self._rg(4000), 26.4378, delta=0.005)

    def test_tail_matches_explicit_small_case(self):
        a = self._rg(2000, max_images=60)
        b = self._rg(2000, max_images=100000)
        self.assertAlmostEqual(a, b, delta=1e-4 * b)


class TestVersion(unittest.TestCase):
    def test_version(self):
        self.assertEqual(api.APP_VERSION, "1.3.4")


# ---------------------------------------------------------------------------
# Second batch (coordinator follow-up)
# ---------------------------------------------------------------------------

from earthsys import iec60364  # noqa: E402

_ROD = [{"type": "rod", "L": 3, "d": 0.016}]


class TestValidation(unittest.TestCase):
    def _bem(self, **kw):
        return api.dispatch("/api/bem", dict(
            items=[{"kind": "rod", "x": 0, "y": 0, "length": 3}],
            segment_length=1, **kw))

    def test_bem_rho1(self):
        with self.assertRaisesRegex(ValueError, "rho1"):
            self._bem(rho1=0)

    def test_bem_rho2_and_depth(self):
        with self.assertRaisesRegex(ValueError, "rho2"):
            self._bem(rho1=100, rho2=-5, h_layer=2)
        with self.assertRaisesRegex(ValueError, "thickness"):
            self._bem(rho1=100, rho2=500, h_layer=0)

    def test_strip_and_ring_at_surface(self):
        for e in ({"type": "strip", "L": 20, "w": 0.03, "h": 0},
                  {"type": "ring", "radius": 6, "d": 0.01, "h": 0}):
            with self.assertRaisesRegex(ValueError, "burial depth"):
                api.dispatch("/api/building", dict(system="TT", U0=230, rho=100,
                                                   electrodes=[e]))
            with self.assertRaisesRegex(ValueError, "burial depth"):
                api.dispatch("/api/electrode", dict(e, rho=100))

    def test_plate_at_surface_still_valid(self):
        r = api.dispatch("/api/electrode", dict(type="plate", rho=100, area=1, h=0))
        self.assertAlmostEqual(r["R"], 100 / (4 * math.sqrt(1 / math.pi)))


class TestElvDisconnection(unittest.TestCase):
    def test_no_requirement_at_or_below_50V(self):
        for sysname in ("TN-S", "TT"):
            t = iec60364.max_disconnection_time(sysname, 48.0)
            self.assertIsNone(t["t"])
            self.assertFalse(t["required"])
        self.assertEqual(iec60364.max_disconnection_time("TN-S", 230)["t"], 0.4)

    def test_assessment_and_report(self):
        r = api.dispatch("/api/building", dict(system="TN-S", U0=48, rho=100,
                                               electrodes=_ROD,
                                               device=dict(kind="mcb", rating_A=32)))
        self.assertTrue(r["passed"])
        self.assertEqual(len(r["checks"]), 1)
        html = report.build(dict(building=r))
        row = html.split("Maximum disconnection time")[1].split("</tr>")[0]
        self.assertIn("not required", row)


class TestGridApplicability(unittest.TestCase):
    P = dict(rho=400, rho_s=2500, hs=0.102, ts=0.5, Lx=70, Ly=70, D=7, d=0.01,
             IG_kA=1.908)

    def test_depth_warning(self):
        self.assertEqual(api.dispatch("/api/ieee80/design", dict(self.P, h=0.5))["warnings"], [])
        for h in (0.2, 3.0):
            r = api.dispatch("/api/ieee80/design", dict(self.P, h=h))
            self.assertEqual(len(r["warnings"]), 1)
            self.assertIn("0.25–2.5", r["warnings"][0])

    def test_report_formula_follows_method(self):
        def formula(extra):
            r = api.dispatch("/api/ieee80/design", dict(self.P, h=0.5, **extra))
            html = report.build(dict(grid=r))
            return html.split("<div class='formula'>")[1].split("</div>")[0]
        self.assertIn("Eq. (57)", formula(dict(r_method="sverak")))
        self.assertNotIn("Eq. (57)", formula(dict(r_method="schwarz")))
        self.assertIn("Schwarz", formula(dict(r_method="schwarz", n_rods=20, Lr=7.5)))
        self.assertIn("rod factor", formula(dict(r_method="auto", n_rods=20, Lr=7.5)))


class TestTTOvercurrent(unittest.TestCase):
    """IEC 60364-4-41:2005 411.5.4 for MCB/fuse, 411.5.3 for RCD."""

    def _tt(self, device, **kw):
        return iec60364.assess("TT", 230.0, 100.0,
                               [{"type": "foundation", "volume_m3": 8000.0}],
                               device, **kw)

    def test_mcb_uses_loop_impedance(self):
        # R_A = 0.2*100/20 = 1.0 ohm; Ze 0.2, line 0.1 -> Zs = 1.3 ohm;
        # B32: Ia = 160 A, Zs_max = 0.95*230/160 = 1.366 ohm -> passes.
        # The 1.3.3 rule R_A*Ia = 160 V > 50 V failed it.
        d = self._tt(dict(kind="mcb", rating_A=32, curve="B"),
                     Z_source=0.2, Z_line=0.1)
        c = d["checks"][0]
        self.assertTrue(c["name"].startswith("TT loop"))
        self.assertAlmostEqual(d["Zs"], 1.3, places=6)
        self.assertAlmostEqual(c["Zs_max"], 0.95 * 230 / 160)
        self.assertTrue(d["passed"])

    def test_rcd_keeps_electrode_rule(self):
        d = self._tt(dict(kind="rcd", rating_A=0.03))
        self.assertTrue(d["checks"][0]["name"].startswith("TT electrode"))
        self.assertAlmostEqual(d["checks"][0]["RA_max"], 50 / 0.03)


if __name__ == "__main__":
    unittest.main()


# --- BS 7671:2018+A2:2022 Tables 41.2(a) and 41.4(a) (1.3.5) ---------------
def test_gg_fuse_Ia_from_bs7671_tables():
    from earthsys import iec60364 as m
    t412 = {2: 33.1, 4: 15.6, 6: 7.80, 10: 4.65, 16: 2.43, 20: 1.68, 25: 1.29,
            32: 0.99, 40: 0.75, 50: 0.57, 63: 0.44}
    t414 = {2: 44, 4: 21, 6: 12, 10: 6.8, 16: 4.0, 20: 2.8, 25: 2.2, 32: 1.7,
            40: 1.3, 50: 0.99, 63: 0.78, 80: 0.55, 100: 0.42, 125: 0.32,
            160: 0.27, 200: 0.18}
    for tab, t in ((t412, 0.4), (t414, 5.0)):
        for r, z in tab.items():
            Ia = m.device_Ia("fuse", r, t)["Ia"]
            assert abs(0.95 * 230 / Ia - z) < 1e-9, (r, t)
            assert "BS 7671:2018+A2:2022" in m.device_Ia("fuse", r, t)["basis"]
    assert "indicative" in m.device_Ia("fuse", 125, 0.4)["basis"]


def test_gg_fuse_small_rating_5s_from_table_414():
    from earthsys import iec60364 as m
    d = m.device_Ia("fuse", 2, 5.0)
    assert abs(d["Ia"] - 0.95 * 230 / 44) < 1e-9 and "Table 41.2/41.4" in d["basis"]


def test_tt_electrode_above_200_ohm_advisory():
    from earthsys import api
    r = api.api_building(dict(system="TT", U0=230, rho=3000,
                              electrodes=[dict(type="rod", L=1.2, d=0.016)],
                              device=dict(kind="rcd", rating_A=0.03)))
    txt = str(r)
    assert "TT electrode stability (advisory)" in txt
    r2 = api.api_building(dict(system="TT", U0=230, rho=100,
                               electrodes=[dict(type="rod", L=3, d=0.016)],
                               device=dict(kind="rcd", rating_A=0.03)))
    assert "TT electrode stability (advisory)" not in str(r2)


def test_gg_fuse_shorter_than_04s_is_scaled_up():
    from earthsys import iec60364 as m
    a04 = m.device_Ia("fuse", 32, 0.4)["Ia"]
    a02 = m.device_Ia("fuse", 32, 0.2)
    assert abs(a02["Ia"] - a04 * 2 ** 0.5) < 1e-6
    assert "I²t" in a02["basis"]


def test_lightning_10_ohm_is_recommendation_not_verdict():
    from earthsys import iec62305
    # Type B ring that meets r_e >= l1 in high-resistivity soil: R > 10 ohm
    r = iec62305.design("III", 2000.0, area=400.0, perimeter=80.0)
    rows = {c["name"]: c for c in r["checks"]}
    geo = rows["Earth-termination geometry"]
    ten = rows["Earthing resistance ≤ 10 Ω (recommended)"]
    assert geo["passed"] and not ten["passed"] and ten.get("advisory")
    assert r["passed"] is True


def test_hrg_recommendation_uses_total_fault_current():
    from earthsys import ieee142, api
    r = ieee142.recommend(6.6, True, False, 7.18)
    assert r["method"] == "low_resistance"          # total 10.16 A > 10 A
    r2 = ieee142.recommend(6.6, True, False, 6.5)    # total 9.19 A
    assert r2["method"] == "high_resistance"
    d = api.api_sysgnd(dict(V_ll_kV=6.6, frequency=50, cable_km=8, C0_uF_per_km=0.25,
                            continuity_critical=True, method="high_resistance"))
    assert abs(d["total_fault_current"] - 10.16) < 0.01 and d["warnings"]


def test_report_sysgnd_prints_total_current():
    from earthsys import api, report
    d = api.api_sysgnd(dict(V_ll_kV=6.6, frequency=50, cable_km=8, C0_uF_per_km=0.25,
                            continuity_critical=True, method="high_resistance"))
    html = report._sec_sysgnd(report.T["en"] if hasattr(report, "T") else report.STRINGS["en"], d)
    assert "Total earth-fault current" in html and "10 A" in html
