"""
Validation suite for EarthSystem.

Run from the application folder:

    python -m unittest discover -s tests -v
    python tests/test_validation.py

The reference values come from published worked examples and from closed-form
solutions that the numerical solver must reproduce.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import conductor, faultcurrent, iec60364, iec62305, ieee80, soil  # noqa: E402

try:
    from earthsys import bem
    HAVE_NUMPY = bem.HAVE_NUMPY
except Exception:                                        # pragma: no cover
    HAVE_NUMPY = False


class TestIEEE80AnnexB(unittest.TestCase):
    """IEEE Std 80-2013, Annex B — square grid without ground rods.

    ρ = 400 Ω·m, ρ_s = 2500 Ω·m, h_s = 0.102 m, t_s = 0.5 s,
    70 m × 70 m grid, D = 7 m, h = 0.5 m, d = 0.01 m, I_G = 1908 A.
    """

    def setUp(self):
        self.g = ieee80.GridGeometry(Lx=70, Ly=70, D=7, h=0.5, d=0.01,
                                     n_rods=0, shape="rectangular")
        self.r = ieee80.design(400.0, self.g, 1.908, 2500.0, 0.102, 0.5, 70,
                               r_method="sverak")

    def test_geometry(self):
        self.assertEqual(self.g.Nx, 11)
        self.assertEqual(self.g.Ny, 11)
        self.assertAlmostEqual(self.g.Lc, 1540.0, places=6)
        self.assertAlmostEqual(self.g.A, 4900.0, places=6)
        self.assertAlmostEqual(self.g.Lp, 280.0, places=6)

    def test_surface_derating(self):
        self.assertAlmostEqual(self.r["tolerable"]["Cs"], 0.74, places=2)

    def test_tolerable_voltages(self):
        # published: E_touch70 = 838.2 V, E_step70 = 2686.6 V (with C_s = 0.74)
        self.assertAlmostEqual(self.r["tolerable"]["E_touch"], 838.2, delta=4.0)
        self.assertAlmostEqual(self.r["tolerable"]["E_step"], 2686.6, delta=12.0)

    def test_grid_resistance(self):
        self.assertAlmostEqual(self.r["Rg"], 2.78, places=2)

    def test_gpr(self):
        self.assertAlmostEqual(self.r["GPR"], 5304.0, delta=15.0)

    def test_geometric_factors(self):
        m = self.r["mesh"]
        self.assertAlmostEqual(m["n"], 11.0, places=6)
        self.assertAlmostEqual(m["Km"], 0.89, places=2)
        self.assertAlmostEqual(m["Ki"], 2.272, places=3)
        self.assertAlmostEqual(m["Ks"], 0.406, places=3)

    def test_mesh_voltage(self):
        # published: E_m = 1002.1 V, which exceeds the 838 V tolerable value
        self.assertAlmostEqual(self.r["mesh"]["Em"], 1002.1, delta=6.0)
        self.assertFalse(self.r["passed"])

    def test_effective_lengths(self):
        self.assertAlmostEqual(self.r["mesh"]["LM"], 1540.0, places=6)
        self.assertAlmostEqual(self.r["mesh"]["LS"], 1155.0, places=6)

    def test_optimiser_finds_a_compliant_design(self):
        opt = ieee80.optimise(400.0, self.g, 1.908, 2500.0, 0.102, 0.5, 70,
                              D_min=1.5, D_step=0.5, allow_rods=True)
        self.assertTrue(opt["found"])
        best = opt["best"]["result"]
        self.assertLessEqual(best["mesh"]["Em"], best["tolerable"]["E_touch"])
        self.assertLessEqual(best["mesh"]["Es"], best["tolerable"]["E_step"])


class TestConductorSizing(unittest.TestCase):

    def test_ieee80_round_trip(self):
        """Sizing and the fusing-time inverse must be consistent."""
        r = conductor.ieee80_conductor_area(20.0, 0.5, "cu_hard", 40.0)
        t = conductor.ieee80_fusing_time(r["area_mm2"], 20.0, "cu_hard", 40.0)
        self.assertAlmostEqual(t, 0.5, places=6)

    def test_ieee80_scales_with_sqrt_time(self):
        a1 = conductor.ieee80_conductor_area(10.0, 0.5)["area_mm2"]
        a2 = conductor.ieee80_conductor_area(10.0, 2.0)["area_mm2"]
        self.assertAlmostEqual(a2 / a1, 2.0, places=6)

    def test_iec_adiabatic(self):
        r = conductor.adiabatic_area(1000.0, 0.4, "copper", "pvc70", "separate")
        self.assertAlmostEqual(r["area_mm2"], math.sqrt(1000.0 ** 2 * 0.4) / 143.0,
                               places=9)

    def test_pe_selection_rules(self):
        self.assertAlmostEqual(conductor.pe_from_line_conductor(10)["area_mm2"], 10)
        self.assertAlmostEqual(conductor.pe_from_line_conductor(25)["area_mm2"], 16)
        self.assertAlmostEqual(conductor.pe_from_line_conductor(120)["area_mm2"], 60)

    def test_min_buried_sizes(self):
        r = conductor.min_buried_earthing_conductor(False, False)
        self.assertEqual(r["copper_mm2"], 25.0)
        self.assertEqual(r["steel_mm2"], 50.0)


class TestFaultCurrent(unittest.TestCase):

    def test_decrement_factor_tends_to_one(self):
        self.assertAlmostEqual(faultcurrent.decrement_factor(30.0, 10.0)["Df"],
                               1.0, places=2)

    def test_decrement_factor_greater_than_one(self):
        self.assertGreater(faultcurrent.decrement_factor(0.1, 30.0)["Df"], 1.2)

    def test_grid_current(self):
        r = faultcurrent.grid_current(10.0, 0.5, 1.1, 1.2)
        self.assertAlmostEqual(r["Ig_kA"], 6.0, places=9)
        self.assertAlmostEqual(r["IG_kA"], 6.6, places=9)

    def test_line_to_earth_symmetric_case(self):
        """With Z1 = Z2 = Z0 the earth fault equals the three-phase fault."""
        Z = complex(1.0, 10.0)
        lg = faultcurrent.line_to_earth_fault(20.0, Z, Z, Z)
        tp = faultcurrent.three_phase_fault(20.0, Z)
        self.assertAlmostEqual(lg["Ik1_kA"], tp["Ik_kA"], places=9)


class TestSoil(unittest.TestCase):

    def test_wenner_reduction(self):
        self.assertAlmostEqual(soil.wenner_rho(10.0, 5.0), 2 * math.pi * 5 * 10)

    def test_two_layer_forward_reduces_to_uniform(self):
        self.assertAlmostEqual(soil.wenner_two_layer(5.0, 250.0, 250.0, 2.0),
                               250.0, places=6)

    def test_inversion_recovers_a_synthetic_model(self):
        rho1, rho2, h = 300.0, 80.0, 2.5
        a = [0.5, 1, 2, 3, 5, 8, 12, 20, 30]
        y = [soil.wenner_two_layer(x, rho1, rho2, h) for x in a]
        r = soil.invert_two_layer(a, y, "wenner")
        self.assertLess(r["rms_pct"], 1.0)
        self.assertAlmostEqual(r["rho1"], rho1, delta=0.02 * rho1)
        self.assertAlmostEqual(r["rho2"], rho2, delta=0.05 * rho2)
        self.assertAlmostEqual(r["h"], h, delta=0.1 * h)

    def test_schlumberger_inversion(self):
        rho1, rho2, h = 120.0, 600.0, 1.8
        a = [1, 2, 3, 5, 8, 12, 20, 30, 50]
        y = [soil.schlumberger_two_layer(x, rho1, rho2, h) for x in a]
        r = soil.invert_two_layer(a, y, "schlumberger")
        self.assertLess(r["rms_pct"], 1.0)


class TestElectrodes(unittest.TestCase):

    def test_rod_dwight(self):
        r = iec60364.rod(100.0, 3.0, 0.016)["R"]
        expect = 100.0 / (2 * math.pi * 3.0) * (math.log(8 * 3.0 / 0.016) - 1.0)
        self.assertAlmostEqual(r, expect, places=9)

    def test_parallel_rods_are_worse_than_ideal(self):
        one = iec60364.rod(100.0, 3.0, 0.016)["R"]
        four = iec60364.rods_parallel(100.0, 3.0, 0.016, 4, 6.0)["R"]
        self.assertGreater(four, one / 4.0)
        self.assertLess(four, one)

    def test_resistance_scales_with_resistivity(self):
        a = iec60364.horizontal_strip(100.0, 30.0, 0.03, 0.8)["R"]
        b = iec60364.horizontal_strip(300.0, 30.0, 0.03, 0.8)["R"]
        self.assertAlmostEqual(b / a, 3.0, places=9)

    def test_tt_criterion(self):
        r = iec60364.tt_electrode_check(100.0, 1.0, 50.0)
        self.assertFalse(r["passed"])            # 100 Ω × 1 A = 100 V > 50 V
        self.assertAlmostEqual(r["RA_max"], 50.0, places=9)
        self.assertTrue(iec60364.tt_electrode_check(100.0, 0.3, 50.0)["passed"])

    def test_rcd_selection(self):
        r = iec60364.rcd_selection(100.0)          # 50/100 = 0.5 A
        self.assertAlmostEqual(r["selected_IdN"], 0.5, places=9)

    def test_disconnection_times(self):
        self.assertAlmostEqual(
            iec60364.max_disconnection_time("TN-S", 230.0)["t"], 0.4)
        self.assertAlmostEqual(
            iec60364.max_disconnection_time("TT", 230.0)["t"], 0.2)
        self.assertAlmostEqual(
            iec60364.max_disconnection_time("TN-S", 230.0, "distribution")["t"], 5.0)


class TestLightning(unittest.TestCase):

    def test_l1_breakpoints(self):
        self.assertAlmostEqual(iec62305.min_electrode_length("I", 500)["l1"], 5.0)
        self.assertAlmostEqual(iec62305.min_electrode_length("I", 3000)["l1"], 80.0)
        self.assertAlmostEqual(iec62305.min_electrode_length("III", 3000)["l1"], 5.0)

    def test_type_b_requires_supplementary_electrodes(self):
        d = iec62305.type_b("I", 3000.0, area=200.0, perimeter=60.0)
        self.assertFalse(d["radius_ok"])
        self.assertIsNotNone(d["supplementary"])

    def test_separation_distance(self):
        d = iec62305.separation_distance("I", 10.0, 4, "air")
        self.assertAlmostEqual(d["s"], 0.08 * 0.44 * 10.0, places=9)


@unittest.skipUnless(HAVE_NUMPY, "numpy is not installed")
class TestNumericalSolver(unittest.TestCase):
    """The boundary-element solver must reproduce the closed-form results.

    The numerical answer is expected to be slightly LOWER than the classical
    formulas, because those assume a uniform leakage-current density whereas
    the solver enforces a single electrode potential.
    """

    def _solve(self, build, seg):
        net = bem.Network(bem.SoilModel(100.0), 1000.0)
        build(net)
        net.discretise(seg)
        return net.solve()["Rg"]

    def test_single_segment_reproduces_dwight_exactly(self):
        net = bem.Network(bem.SoilModel(100.0), 1000.0)
        net.add_rod(0, 0, 0.0, 3.0, 0.008)
        net.discretise(10.0)                     # one segment
        Rg = net.solve()["Rg"]
        ref = iec60364.rod(100.0, 3.0, 0.016)["R"]
        self.assertAlmostEqual(Rg / ref, 1.0, delta=0.01)

    def test_vertical_rod(self):
        Rg = self._solve(lambda n: n.add_rod(0, 0, 0.0, 3.0, 0.008), 0.5)
        ref = iec60364.rod(100.0, 3.0, 0.016)["R"]
        self.assertLess(abs(Rg / ref - 1.0), 0.05)

    def test_horizontal_conductor(self):
        Rg = self._solve(lambda n: n.add_conductor((0, 0, 0.8), (30, 0, 0.8), 0.005), 1.0)
        ref = iec60364.horizontal_round(100.0, 30.0, 0.010, 0.8)["R"]
        self.assertLess(abs(Rg / ref - 1.0), 0.05)

    def test_ring(self):
        Rg = self._solve(lambda n: n.add_ring(0, 0, 10.0, 0.6, 0.005, 64), 0.6)
        ref = iec60364.ring(100.0, 10.0, 0.010, 0.6)["R"]
        self.assertLess(abs(Rg / ref - 1.0), 0.08)

    def test_grid_agrees_with_sverak(self):
        net = bem.Network(bem.SoilModel(400.0), 1908.0)
        net.add_grid(70, 70, 7, 0.5, 0.005)
        net.discretise(3.5)
        Rg = net.solve()["Rg"]
        ref = ieee80.sverak_resistance(400.0, 4900.0, 1540.0, 0.5)["Rg"]
        self.assertLess(abs(Rg / ref - 1.0), 0.10)

    def test_two_layer_reduces_to_uniform(self):
        a = bem.Network(bem.SoilModel(200.0), 1000.0)
        a.add_rod(0, 0, 0.0, 3.0, 0.008)
        a.discretise(0.5)
        Ra = a.solve()["Rg"]
        b = bem.Network(bem.SoilModel(200.0, 200.0, 4.0), 1000.0)
        b.add_rod(0, 0, 0.0, 3.0, 0.008)
        b.discretise(0.5)
        Rb = b.solve()["Rg"]
        self.assertAlmostEqual(Ra, Rb, places=6)

    def test_two_layer_direction_is_physical(self):
        """A conductive lower layer must reduce the resistance."""
        def R(rho2):
            n = bem.Network(bem.SoilModel(500.0, rho2, 2.0), 1000.0)
            n.add_rod(0, 0, 0.0, 6.0, 0.008)
            n.discretise(0.5)
            return n.solve()["Rg"]
        self.assertLess(R(50.0), R(500.0))
        self.assertGreater(R(5000.0), R(500.0))

    def test_mesh_voltage_cross_check(self):
        """Corner-mesh touch voltage should be close to the IEEE 80 E_m."""
        net = bem.Network(bem.SoilModel(400.0), 1908.0)
        net.add_grid(70, 70, 7, 0.5, 0.005)
        net.discretise(3.5)
        net.solve()
        v = net.potential_at([[3.5, 3.5, 0.0]])[0]
        touch = net.V - v
        g = ieee80.GridGeometry(Lx=70, Ly=70, D=7, h=0.5, d=0.01)
        Em = ieee80.mesh_step_voltages(400.0, g, 1908.0)["Em"]
        self.assertLess(abs(touch / Em - 1.0), 0.25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
