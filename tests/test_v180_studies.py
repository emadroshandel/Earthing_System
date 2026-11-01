"""1.8.0: accuracy of the numerical solver's post-processing, and the new
studies — non-equipotential power frequency, robust and multi-traverse soil
fits, soil uncertainty, seasonal soil, grid optimisation, fall-of-potential
test planning, the shield-wire split factor and fault-location sweep,
inductive coupling, IEC 62305-2 risk and SPD coordination."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import bem, earthtest, faultcurrent, powerfreq, risk, spd, studies, transfer  # noqa: E402
from earthsys.api import dispatch  # noqa: E402

try:
    import numpy as np
except ImportError:                                     # pragma: no cover
    np = None

ANNEX_B_RODS = [dict(kind="rod", x=x, y=y, top_depth=0.5, length=7.5, radius=0.01)
                for k in range(5)
                for x, y in [(k * 17.5, 0), (70, k * 17.5), (70 - k * 17.5, 70), (0, 70 - k * 17.5)]]


def annex_b(grade=False, seg=2.5):
    net = bem.build_network(dict(rho1=400, IG=1908, conductor_radius=0.00527,
                                 items=[dict(kind="grid", Lx=70, Ly=70, D=7, depth=0.5)] + ANNEX_B_RODS))
    net.discretise(seg, 6000, grade_ends=grade)
    net.solve()
    return net


@unittest.skipIf(np is None, "numpy needed")
class TestStepAndTouchSearch(unittest.TestCase):
    """1.7.0 differenced in +x and +y only and combined them with hypot():
    480 V at nx = 61 and 603 V at nx = 181 on this model, against 488 V from
    a brute-force search over position and direction."""

    @classmethod
    def setUpClass(cls):
        cls.net = annex_b()
        cls.scans = {n: cls.net.worst_touch_step((-10, 80), (-10, 80), n, n, 1.0) for n in (31, 61, 121)}

    def test_step_does_not_depend_on_resolution(self):
        v = [s["step_max"] for s in self.scans.values()]
        self.assertLess(max(v) - min(v), 0.01 * max(v))

    def test_step_agrees_with_brute_force(self):
        best = 0.0
        ang = np.linspace(0, 2 * np.pi, 72, endpoint=False)
        xs = np.arange(67.0, 73.01, 0.1)
        X, Y = np.meshgrid(xs, xs)
        P = np.column_stack([X.ravel(), Y.ravel(), np.zeros(X.size)])
        V0 = self.net.potential_at(P)
        for a in ang:
            Q = P.copy()
            Q[:, 0] += math.cos(a)
            Q[:, 1] += math.sin(a)
            best = max(best, float(np.abs(V0 - self.net.potential_at(Q)).max()))
        self.assertAlmostEqual(self.scans[61]["step_max"], best, delta=0.01 * best)

    def test_touch_does_not_depend_on_resolution(self):
        v = [s["touch_max"] for s in self.scans.values()]
        self.assertLess(max(v) - min(v), 0.005 * max(v))

    def test_touch_point_is_within_reach_of_metal(self):
        x, y = self.scans[61]["touch_at"]
        self.assertTrue(self.net.touch_region(np.array([x]), np.array([y]), 1.0)[0])


@unittest.skipIf(np is None, "numpy needed")
class TestTouchRegion(unittest.TestCase):

    def test_notch_of_an_l_shaped_grid_is_not_a_touch_location(self):
        net = bem.Network(bem.SoilModel(100.0), 1000.0)
        # an L: 40 x 20 strip plus a 20 x 20 square on its left end
        for y in (0, 10, 20):
            net.add_conductor((0, y, 0.5), (40, y, 0.5), 0.005)
        for y in (30, 40):
            net.add_conductor((0, y, 0.5), (20, y, 0.5), 0.005)
        for x in (0, 10, 20):
            net.add_conductor((x, 0, 0.5), (x, 40, 0.5), 0.005)
        for x in (30, 40):
            net.add_conductor((x, 0, 0.5), (x, 20, 0.5), 0.005)
        inside = net.touch_region(np.array([5.0, 30.0, 35.0]), np.array([35.0, 30.0, 10.0]), 1.0)
        self.assertEqual(list(inside), [True, False, True])

    def test_zones_report_their_own_touch_voltage(self):
        net = annex_b()
        ws = net.worst_touch_step((-10, 80), (-10, 80), 31, 31, 1.0,
                                  zones=[dict(name="TX", x0=30, y0=30, x1=40, y1=36)])
        self.assertEqual(ws["touch_region"], "zones")
        self.assertEqual(ws["zones"][0]["name"], "TX")
        self.assertLess(ws["touch_max"], 0.5 * net.worst_touch_step((-10, 80), (-10, 80), 31, 31)["touch_max"])


@unittest.skipIf(np is None, "numpy needed")
class TestGradedDiscretisation(unittest.TestCase):

    def test_grading_reaches_the_fine_mesh_answer_with_fewer_segments(self):
        def touch(seg, grade):
            net = annex_b(grade, seg)
            v = net.potential_at([[-1.0, -1.0, 0.0]])[0]
            return net.V - v, len(net.segments)
        fine, n_fine = touch(0.5, False)
        coarse, _ = touch(3.0, False)
        graded, n_graded = touch(3.0, True)
        self.assertLess(abs(graded - fine), 0.4 * abs(coarse - fine))
        self.assertLess(n_graded, 0.4 * n_fine)

    def test_graded_grid_lines(self):
        self.assertAlmostEqual(bem.graded_fraction(0.0, 0.5), 0.0)
        self.assertAlmostEqual(bem.graded_fraction(0.5, 0.5), 0.5)
        self.assertAlmostEqual(bem.graded_fraction(1.0, 0.5), 1.0)
        # edge spacing (1 - g) of the mean
        n = 101
        x = [bem.graded_fraction(i / (n - 1), 0.6) for i in range(n)]
        self.assertAlmostEqual((x[1] - x[0]) * (n - 1), 0.4, delta=0.01)

    def test_coarsening_is_reported(self):
        d = dispatch("/api/bem", dict(rho1=100, IG=1000, items=[dict(kind="grid", Lx=70, Ly=70, D=7)],
                                     segment_length=0.5, max_segments=500, nx=21))
        self.assertTrue(d.get("warnings"))


@unittest.skipIf(np is None, "numpy needed")
class TestStudies(unittest.TestCase):
    BASE = dict(rho1=400, IG=1908, items=[dict(kind="grid", Lx=40, Ly=40, D=8, depth=0.5)],
                segment_length=3, nx=25)

    def test_convergence_reports_both_solutions(self):
        c = studies.convergence(dict(self.BASE))
        self.assertEqual(len(c["segments"]), 2)
        self.assertGreater(c["segments"][1], c["segments"][0])
        for k in ("touch", "step", "Rg"):
            self.assertIn("extrapolated", c[k])
        self.assertGreaterEqual(c["touch"]["design"], max(c["touch"]["coarse"], c["touch"]["fine"]))

    def test_seasonal_soils(self):
        cases = studies.seasonal_soils(dict(rho1=300, rho2=110, h_layer=2.5), 2.0, 1.0, 2000, 0.5)
        self.assertEqual(cases[1]["rho"], [600.0, 300.0, 110.0])
        self.assertEqual(cases[1]["h"], [1.0, 1.5])
        self.assertEqual(cases[2]["rho"], [2000.0, 300.0, 110.0])
        many = studies.seasonal_soils(dict(rho1=100, rho2=200, h_layer=1, rho3=50, h_layer2=2,
                                           rho4=400, h_layer3=3), 3.0, 0.5)
        self.assertLessEqual(len(many[1]["rho"]), 4)

    def test_dry_season_raises_the_resistance(self):
        s = studies.seasonal(dict(self.BASE, seasonal=dict(dry_factor=3, dry_depth=1.0)))
        self.assertGreater(s["cases"][1]["Rg"], s["cases"][0]["Rg"])

    def test_soil_samples_follow_the_fit(self):
        fit = dict(n_layers=2, uncertainty=dict(
            rho1=dict(value=300, sd_pct=10), rho2=dict(value=100, sd_pct=20),
            h=dict(value=2.0, sd_pct=15), corr_rho1_h=-0.5))
        smp, capped = studies.soil_samples(fit, 400, seed=3)
        r1 = np.log([s["rho"][0] for s in smp])
        self.assertAlmostEqual(float(np.exp(r1.mean())), 300, delta=15)
        self.assertAlmostEqual(float(r1.std()), 0.10, delta=0.02)
        self.assertEqual(capped, [])

    def test_monte_carlo_small(self):
        fit = dict(n_layers=2, uncertainty=dict(
            rho1=dict(value=300, sd_pct=10), rho2=dict(value=100, sd_pct=20),
            h=dict(value=2.0, sd_pct=15), corr_rho1_h=-0.5))
        p = dict(self.BASE, rho1=300, rho2=100, h_layer=2.0, limits=dict(E_touch=1e6, E_step=1e6))
        m = studies.monte_carlo(p, fit, n=4)
        self.assertEqual(m["n"], 4)
        self.assertEqual(m["p_pass"], 1.0)
        self.assertLessEqual(m["stats"]["touch"]["p05"], m["stats"]["touch"]["p95"])

    def test_optimise_finds_a_feasible_grid(self):
        o = studies.optimise_grid(dict(rho1=100, IG=500, Lx=30, Ly=30, depth=0.5,
                                       limits=dict(E_touch=600, E_step=1500), n_min=3, n_max=7,
                                       gradings=[0.0, 0.5], rod_options=[0], nx=21,
                                       segment_length=3))
        self.assertTrue(o["feasible"])
        self.assertLessEqual(o["best"]["touch"], 600)

    def test_pruned_search_finds_the_exhaustive_optimum(self):
        # 1.8.1: the upward, cost-bounded search must give the same design as
        # solving every candidate
        base = dict(rho1=100, IG=500, Lx=30, Ly=30, depth=0.5,
                    limits=dict(E_touch=600, E_step=1500), n_min=3, n_max=7,
                    gradings=[0.0, 0.5], rod_options=[0, 2], nx=21, segment_length=3)
        o = studies.optimise_grid(dict(base))
        best = None
        for n in range(3, 8):
            for g in (0.0, 0.5):
                for rods in (0, 2):
                    q = dict(base, n_min=n, n_max=n, gradings=[g], rod_options=[rods])
                    r = studies.optimise_grid(q)
                    if r["feasible"] and (best is None or r["best"]["cost"] < best["cost"]):
                        best = r["best"]
        self.assertIsNotNone(best)
        self.assertAlmostEqual(o["best"]["cost"], best["cost"])
        self.assertLessEqual(o["evaluations"], 20)


@unittest.skipIf(np is None, "numpy needed")
class TestPowerFrequency(unittest.TestCase):

    def test_compact_copper_grid_is_equipotential(self):
        r = powerfreq.analyse(dict(rho1=100, IG=10000, items=[dict(kind="grid", Lx=100, Ly=100, D=10, depth=0.6)],
                                   conductor_radius=0.0062, segment_length=5, nx=21, feeds=[dict(x=0, y=0)]))
        self.assertLess(abs(r["impedance_ratio"] - 1), 0.02)
        self.assertFalse(r["significant"])
        self.assertAlmostEqual(r["touch_max"], r["equipotential"]["touch_max"],
                               delta=0.03 * r["equipotential"]["touch_max"])

    def test_large_grid_in_low_resistivity_soil_is_not(self):
        r = powerfreq.analyse(dict(rho1=30, IG=10000, items=[dict(kind="grid", Lx=300, Ly=300, D=20, depth=0.6)],
                                   conductor_radius=0.0062, segment_length=10, nx=21, feeds=[dict(x=0, y=0)]))
        self.assertGreater(r["impedance_ratio"], 1.15)
        self.assertLess(r["V_min_over_feed"], 0.8)
        self.assertTrue(r["significant"])
        self.assertGreater(r["touch_max"], r["equipotential"]["touch_max"])


class TestSoilFits(unittest.TestCase):
    DATA = [[1, 292], [1.5, 279], [2, 272], [3, 229], [4, 202], [6, 156], [8, 132], [12, 120],
            [16, 112], [24, 112], [32, 109], [40, 108]]

    def test_robust_fit_sets_aside_the_bad_reading_only(self):
        rows = [dict(a=a, rho=r) for a, r in self.DATA]
        rows[5] = dict(a=6, rho=260)
        plain = dispatch("/api/soil/invert", dict(array="wenner", rows=rows, robust=False))
        rob = dispatch("/api/soil/invert", dict(array="wenner", rows=rows, robust=True))
        self.assertEqual([e["spacing"] for e in rob["robust"]["excluded"]], [6.0])
        self.assertLess(rob["rms_pct"], 0.3 * plain["rms_pct"])
        self.assertAlmostEqual(rob["h"], 2.5, delta=0.2)

    def test_clean_data_is_left_alone(self):
        rob = dispatch("/api/soil/invert", dict(array="wenner",
                                                rows=[dict(a=a, rho=r) for a, r in self.DATA]))
        self.assertEqual(rob["robust"]["excluded"], [])

    def test_traverses_flag_lateral_variation(self):
        rows = ([dict(a=a, rho=r, traverse="N-S") for a, r in self.DATA]
                + [dict(a=a, rho=1.8 * r, traverse="E-W") for a, r in self.DATA])
        d = dispatch("/api/soil/invert", dict(array="wenner", rows=rows))
        self.assertTrue(d["traverses"]["lateral"])
        same = ([dict(a=a, rho=r, traverse="N-S") for a, r in self.DATA]
                + [dict(a=a, rho=1.05 * r, traverse="E-W") for a, r in self.DATA])
        self.assertFalse(dispatch("/api/soil/invert", dict(array="wenner", rows=same))["traverses"]["lateral"])


@unittest.skipIf(np is None, "numpy needed")
class TestFallOfPotential(unittest.TestCase):

    def test_small_electrode_follows_the_618_rule(self):
        c = earthtest.curve(dict(rho1=100, items=[dict(kind="rod", x=0, y=0, top_depth=0.0,
                                                       length=3.0, radius=0.008)],
                                 segment_length=0.5), 100.0, n=80)
        self.assertAlmostEqual(c["x_true_fraction"], 0.618, delta=0.02)
        self.assertLess(abs(c["error_618_pct"]), 2.0)

    def test_large_grid_needs_a_distant_current_electrode(self):
        grid = [dict(kind="grid", Lx=70, Ly=70, D=7, depth=0.5)]
        # uniform soil, distances from the centre: the rule nearly holds
        r = earthtest.plan(dict(rho1=400, items=grid, segment_length=4), multiples=(1, 5))
        e1, e5 = (abs(s["error_618_pct"]) for s in r["sweep"])
        self.assertLess(e1, 7.0)
        self.assertLess(e5, 0.5)
        # conductive soil over resistive: it fails badly close in
        r = earthtest.plan(dict(rho1=100, rho2=1000, h_layer=5, items=grid, segment_length=4),
                           multiples=(1, 5))
        e1, e5 = (abs(s["error_618_pct"]) for s in r["sweep"])
        self.assertGreater(e1, 20.0)
        self.assertLess(e5, 2.0)
        # distances from the edge: the true reading moves well below 61.8 %
        r = earthtest.plan(dict(rho1=400, items=grid, segment_length=4), multiples=(1,), from_edge=True)
        self.assertGreater(r["sweep"][0]["error_618_pct"], 10.0)

    def test_interpretation_recovers_a_scale_factor(self):
        p = dict(rho1=400, items=[dict(kind="grid", Lx=40, Ly=40, D=8, depth=0.5)], segment_length=4)
        cv = earthtest.curve(p, 200.0, n=40)
        meas = [[x, 1.3 * R] for x, R in zip(cv["x"][::8], cv["R"][::8])]
        r = earthtest.plan(p, multiples=(5,), measured=meas, dC_measured=200.0)
        self.assertAlmostEqual(r["interpretation"]["scale"], 1.3, delta=0.01)


class TestSplitFactorLadder(unittest.TestCase):

    def test_long_ladder_tends_to_the_infinite_ladder(self):
        Zs = complex(0.12, 0.25)
        self.assertAlmostEqual(abs(faultcurrent.ladder_input(Zs, 15.0, 400)),
                               abs(faultcurrent.ladder_infinite(Zs, 15.0)), delta=1e-6)

    def test_without_shield_wire_all_remote_current_enters_the_grid(self):
        r = faultcurrent.fault_location_sweep(132, 0.5, line_km=20, span_km=0.3, Rt=1e9,
                                              R_remote=1e9, zs_km=1e9, zm_km=0)
        st = r["station"]
        self.assertAlmostEqual(st["Ig_kA"], st["I_remote_kA"], delta=1e-3 * st["I_remote_kA"])

    def test_shield_wire_reduces_station_current_and_a_line_fault_can_govern(self):
        r = faultcurrent.fault_location_sweep(132, 0.5, line_km=20, span_km=0.3, Rt=15, R_remote=0.5)
        self.assertLess(r["station"]["Ig_kA"], r["station"]["I_remote_kA"])
        self.assertGreaterEqual(r["worst"]["Ig_kA"], r["station"]["Ig_kA"])

    def test_carson(self):
        z = faultcurrent.carson_self(0.0, 0.004, 100.0, 50.0)
        self.assertAlmostEqual(z.real, math.pi ** 2 * 1e-4 * 50, places=6)   # 0.0493 Ω/km
        self.assertAlmostEqual(z.imag, 4 * math.pi * 1e-4 * 50 * math.log(658.5 * math.sqrt(2) / 0.004), places=6)


@unittest.skipIf(np is None, "numpy needed")
class TestInducedVoltage(unittest.TestCase):

    def test_insulated_open_conductor_carries_the_whole_emf_to_its_far_end(self):
        f = lambda s: 0.0
        r = transfer.transferred_potential(GPR=1e-9, Rg=1.0, IG=1.0, soil_profile=f, length=1000.0,
                                           kind="insulated", radius=0.01, near="bonded", far="open",
                                           induced=dict(I_A=1000.0, d=20.0, s_from=0.0, s_to=1000.0))
        zm = transfer.mutual_earth_return(100.0, 50.0, 20.0)
        self.assertAlmostEqual(r["induced"]["touch_induced_max"], abs(zm) * 1000.0 * 1000.0, delta=1.0)


class TestRisk(unittest.TestCase):

    def test_collection_area(self):
        AD, AM, AL, AI = risk.collection_areas(40, 20, 15, [1000])
        self.assertAlmostEqual(AD, 40 * 20 + 2 * 45 * 60 + math.pi * 45 ** 2)
        self.assertEqual(AL, [40000.0])
        # IEC 62305-2:2024 (A.12): A_I = 2·r_I·L_L with r_I = 2000/U_w^1.8
        self.assertAlmostEqual(AI[0], 2 * 2000 / 2.5 ** 1.8 * 1000)

    def test_protection_lowers_the_risk(self):
        p = dict(NG=4, L=40, W=20, H=15)
        a = risk.assess(p, "none", "none")["R"]
        b = risk.assess(p, "II", "II")["R"]
        self.assertLess(b, a)
        s = risk.select(p)
        self.assertTrue(s["needed"])
        self.assertTrue(s["protected"]["ok"])

    def test_small_rural_building_needs_none(self):
        # the 2024 edition adds the physical-damage risk R_L2, so a small building
        # needs a low flash density, a low fire risk and a short line to need none
        self.assertFalse(risk.select(dict(NG=0.2, L=10, W=10, H=6, fire_risk="low",
                                          lines=[dict(name="P", length=200)]))["needed"])


class TestSPD(unittest.TestCase):

    def test_current_share_and_protection_rules(self):
        r = spd.coordinate(dict(lpl="I", n_services=2, conductors=4, Uw=2.5, circuit_length=5))
        self.assertAlmostEqual(r["Iimp_per_conductor_kA"], 12.5)
        self.assertTrue(r["passed"])
        far = spd.coordinate(dict(lpl="I", Uw=2.5, circuit_length=30, Ui=1.0))
        self.assertFalse(far["passed"])        # (2.5 - 1)/2 = 0.75 kV < 1.8 kV


class TestEndpoints(unittest.TestCase):

    def test_quick_endpoints(self):
        self.assertIn("note", dispatch("/api/risk", dict(NG=2)))
        self.assertIn("checks", dispatch("/api/spd", {}))
        self.assertIn("worst", dispatch("/api/fault/sweep", dict(Un_kV=132, Rg=0.5, line_km=10, span_km=0.3,
                                                                 Rt=10, R_remote=0.5, Z1_local="0.5+5j")))
        with self.assertRaises(ValueError):
            dispatch("/api/fault/sweep", dict(Un_kV=132, Rg=0.5, line_km=1, span_km=2, Rt=10, R_remote=1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
