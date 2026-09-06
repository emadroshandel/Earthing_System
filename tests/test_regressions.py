"""
Regression tests for defects found in the correctness audit.

Every test here failed before its fix and passes after it.  They are kept
separate from the standards tests on purpose: these are not checks that the
program implements a formula, they are checks that a specific wrong answer
does not come back.  Each one names the wrong value it is guarding against,
so a future change that reintroduces it fails loudly instead of quietly.

    python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import (api, bem, faultcurrent as fc, iec60364 as lv,   # noqa: E402
                      ieee80, materials as M, soil)


class TestBareSoilIsNotCreditedWithACrushedRockLayer(unittest.TestCase):
    """The worst defect found: entering h_s = 0 for bare soil — which the
    field help tells the user to do — returned C_s = 1 while still using the
    crushed-rock resistivity, raising the tolerable touch voltage instead of
    lowering it, and turning a failing design into a pass."""

    def test_no_surface_layer_uses_the_native_soil(self):
        t = ieee80.tolerable_voltages(400.0, 2500.0, 0.0, 0.5, 70)
        expect = (1000.0 + 1.5 * 400.0) * 0.157 / math.sqrt(0.5)
        self.assertAlmostEqual(t["E_touch"], expect, places=6)
        self.assertLess(t["E_touch"], 400.0)          # was 1054.6 V

    def test_it_is_continuous_as_the_layer_becomes_thin(self):
        thin = ieee80.tolerable_voltages(400.0, 2500.0, 1e-4, 0.5, 70)["E_touch"]
        none_ = ieee80.tolerable_voltages(400.0, 2500.0, 0.0, 0.5, 70)["E_touch"]
        self.assertAlmostEqual(thin, none_, delta=5.0)

    def test_a_failing_design_does_not_pass_on_bare_soil(self):
        p = dict(rho=400, rho_s=2500, ts=0.5, Lx=70, Ly=70, D=7, h=0.5,
                 d=0.01, IG_kA=1.908, body_weight=70)
        with_rock = api.api_ieee80(dict(p, hs=0.102))
        bare = api.api_ieee80(dict(p, hs=0.0))
        self.assertFalse(with_rock["passed"])
        self.assertFalse(bare["passed"])              # was True
        self.assertLess(bare["tolerable"]["E_touch"],
                        with_rock["tolerable"]["E_touch"])

    def test_a_thicker_layer_always_helps(self):
        prev = 0.0
        for hs in (0.0, 0.05, 0.10, 0.20, 0.40):
            v = ieee80.tolerable_voltages(400.0, 2500.0, hs, 0.5, 70)["E_touch"]
            self.assertGreater(v, prev)
            prev = v


class TestParallelRodLambdaIndex(unittest.TestCase):
    """The mutual-coupling table is indexed from n = 1, so tab[n] used the
    next rod count's factor and one rod did not equal one rod."""

    def test_one_rod_equals_the_single_rod_formula(self):
        one = lv.rod(100.0, 3.0, 0.016)["R"]
        self.assertAlmostEqual(lv.rods_parallel(100.0, 3.0, 0.016, 1, 6.0)["R"],
                               one, places=9)                 # was 36.145

    def test_lambda_matches_the_closed_form(self):
        """lambda(n) = (2/n) * sum (n-m)/m follows from summing the mutual
        resistance rho/(2*pi*d_ij) over a line of rods.  The tabulated curve
        the module carries is a published rounding of it, so a few hundredths
        of slack is right; a whole index step is not."""
        def lam(n):
            return (2.0 / n) * sum((n - m) / m for m in range(1, n))
        for n in (1, 2, 3, 4, 5, 6):
            got = lv.rods_parallel(100.0, 3.0, 0.016, n, 6.0)["lam"]
            self.assertAlmostEqual(got, lam(n), delta=0.05, msg=f"n={n}")

    def test_more_rods_always_lower_the_resistance(self):
        prev = float("inf")
        for n in range(1, 13):
            R = lv.rods_parallel(100.0, 3.0, 0.016, n, 6.0)["R"]
            self.assertLess(R, prev)
            prev = R


class TestRingElectrodeUsesTheWireDiameter(unittest.TestCase):
    """Dwight's ring formula takes the wire diameter inside the logarithm;
    passing the radius added ln 2 and over-stated R by about 5 %."""

    def test_matches_dwight(self):
        rho, radius, d, h = 100.0, 6.0, 0.010, 0.7
        D, s = 2 * radius, 2 * h
        want = rho / (2 * math.pi ** 2 * D) * (math.log(8 * D / d) +
                                               math.log(4 * D / s))
        self.assertAlmostEqual(lv.ring(rho, radius, d, h)["R"], want, places=9)

    def test_agrees_with_the_numerical_solver(self):
        """The closed form and the boundary-element solver share no equations,
        so agreement between them is real evidence."""
        rho, radius, d, h = 100.0, 6.0, 0.010, 0.7
        net = bem.Network(bem.SoilModel(rho), IG=1.0)
        net.add_ring(0.0, 0.0, radius, h, d / 2.0, n_sides=192)
        num = net.solve(target=0.25)["Rg"]
        self.assertAlmostEqual(lv.ring(rho, radius, d, h)["R"], num,
                               delta=0.03 * num)              # was 5.7 % out


class TestDoubleLineToEarthFault(unittest.TestCase):
    """The phase and earth currents were swapped, and the earth current was
    computed without the 120 degree rotation between the faulted phases — so
    it came out as exactly zero for the commonest case of all, Z0 = Z2."""

    Un, Z1, Z0, c = 20.0, complex(0.5, 5.0), complex(1.0, 15.0), 1.1

    def _closed_form(self, Z1, Z2, Z0):
        import cmath
        a = cmath.exp(2j * math.pi / 3.0)
        den = abs(Z1 * Z2 + Z1 * Z0 + Z2 * Z0)
        U = self.c * self.Un * 1e3
        return (U * abs(Z0 - a * Z2) / den / 1e3,
                math.sqrt(3) * U * abs(Z2) / den / 1e3)

    def test_matches_iec_60909_0(self):
        r = fc.double_line_to_earth(self.Un, self.Z1, self.Z1, self.Z0, self.c)
        ph, ea = self._closed_form(self.Z1, self.Z1, self.Z0)
        self.assertAlmostEqual(r["Ik2E_kA"], ph, places=9)     # was 1.086
        self.assertAlmostEqual(r["IkE2E_kA"], ea, places=9)    # was 2.164

    def test_the_earth_current_is_not_zero_when_z0_equals_z2(self):
        r = fc.double_line_to_earth(self.Un, self.Z1, self.Z1, self.Z1, self.c)
        self.assertGreater(r["IkE2E_kA"], 1.0)                 # was 0.000
        self.assertAlmostEqual(r["IkE2E_kA"],
                               self._closed_form(self.Z1, self.Z1, self.Z1)[1],
                               places=9)

    def test_a_degenerate_impedance_set_raises_rather_than_dividing_by_zero(self):
        with self.assertRaises(ValueError):
            fc.double_line_to_earth(20.0, 0j, 0j, 0j, 1.1)


class TestMaterialConstants(unittest.TestCase):

    def test_bare_aluminium_k_is_the_published_value(self):
        """148 is the prefactor sqrt(Qc(B+20)/rho20), not k; using it as k
        under-sized every bare aluminium conductor by about 18 %."""
        self.assertEqual(M.K_FACTORS_SEPARATE[("aluminium", "bare")]["k"], 125)

    def test_the_bare_conductor_row_is_internally_consistent(self):
        row = {m: M.K_FACTORS_SEPARATE[(m, "bare")]["k"]
               for m in ("copper", "aluminium", "steel")}
        self.assertEqual(row, {"copper": 228, "aluminium": 125, "steel": 82})

    def test_brazed_joints_agree_with_the_joint_table(self):
        """The material row said 250 C for brazed joints while the joint table
        in the same file said 450 C, so the two code paths disagreed by 27 %
        on the same physical case."""
        self.assertEqual(M.IEEE80_MATERIALS["cu_hard_brazed"]["Tm"],
                         M.JOINT_TM_LIMITS["brazed"])
        self.assertEqual(M.IEEE80_MATERIALS["cu_hard_bolted"]["Tm"],
                         M.JOINT_TM_LIMITS["pressure_bolted"])


class TestConductorOffScale(unittest.TestCase):
    """A duty larger than the biggest standard conductor produced
    standard_mm2 = None, which `or 0` turned into the 16 mm2 minimum."""

    def test_an_impossible_duty_is_reported_not_rounded_down(self):
        r = api.api_conductor({"I_kA": 150, "tc": 5, "material": "cu_annealed",
                               "Ta": 40})
        self.assertTrue(r["off_scale"])
        self.assertIsNone(r["selected_mm2"])                   # was 16.0
        self.assertGreater(r["required_mm2"], 1000.0)
        self.assertIn("parallel", r["note"])

    def test_an_ordinary_duty_is_unaffected(self):
        r = api.api_conductor({"I_kA": 19, "tc": 0.5, "material": "cu_annealed",
                               "Ta": 40})
        self.assertFalse(r["off_scale"])
        self.assertGreaterEqual(r["selected_mm2"], r["ieee80"]["area_mm2"])
        self.assertIn(r["selected_mm2"], M.STD_AREAS_MM2)


class TestStepVoltageDoesNotDependOnThePlotResolution(unittest.TestCase):
    """Step voltage was a numerical gradient over two plot cells, so the
    reported value tracked the chart resolution rather than the physics —
    218 V at nx = 31 against 562 V at nx = 181 for the same model."""

    @classmethod
    def setUpClass(cls):
        cls.net = bem.Network(bem.SoilModel(400.0), IG=1908.0)
        cls.net.add_grid(70, 70, 7, 0.5, 0.005)
        cls.net.solve(target=2.5)

    def test_coarse_and_fine_scans_agree(self):
        coarse = self.net.worst_touch_step((-10, 80), (-10, 80), nx=31, ny=31)
        fine = self.net.worst_touch_step((-10, 80), (-10, 80), nx=61, ny=61)
        self.assertAlmostEqual(coarse["step_max"], fine["step_max"],
                               delta=0.15 * fine["step_max"])

    def test_it_is_the_right_order_against_the_closed_form(self):
        """IEEE 80 Eq. (92)-(94) give Es = 610 V for this grid; a numerical
        answer of 360 V was not a different method, it was a wrong one."""
        w = self.net.worst_touch_step((-10, 80), (-10, 80), nx=41, ny=41)
        self.assertGreater(w["step_max"], 450.0)
        self.assertLess(w["step_max"], 800.0)

    def test_touch_voltage_was_never_affected(self):
        a = self.net.worst_touch_step((-10, 80), (-10, 80), nx=31, ny=31)
        b = self.net.worst_touch_step((-10, 80), (-10, 80), nx=61, ny=61)
        self.assertAlmostEqual(a["touch_max"], b["touch_max"], delta=1.0)


class TestSoilEquivalentMethod(unittest.TestCase):

    def test_an_unknown_method_is_refused(self):
        """It used to return rho1 with the note 'electrodes stay in the upper
        layer' even when they plainly did not — a wrong number carrying a
        false explanation."""
        with self.assertRaises(ValueError):
            soil.equivalent_uniform(100.0, 1000.0, 1.0, 0.5, 3.0,
                                    method="harmonic")

    def test_the_documented_methods_still_work(self):
        for m in ("top", "weighted", "auto"):
            r = soil.equivalent_uniform(100.0, 1000.0, 2.0, 0.5, 3.0, method=m)
            self.assertGreater(r["rho_equivalent"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
