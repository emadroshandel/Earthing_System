# Earthing System — regression tests for the fixes of version 1.3.2.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later.
"""Version 1.3.2 fixes found while preparing edition 2.3 of the tutorial.

1. Schwarz coefficient k2, curve A of IEEE 80 Figure 25, had the wrong sign
   of slope (-0.15x + 5.50 instead of +0.15x + 5.50).
2. The "buried" IEC k factors carried initial/final temperatures that do not
   belong to their k values.
3. The Schlumberger forward model ignored the MN spacing that the data
   reduction uses; it now uses the exact finite-MN expression.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import ieee80, materials, soil  # noqa: E402


class TestSchwarzCoefficients(unittest.TestCase):
    def test_curve_a_at_surface(self):
        # h = 0 is curve A exactly; IEEE 80 Annex B quotes k1 = 1.37, k2 = 5.65
        # for a square grid near the surface.
        k1, k2 = ieee80._schwarz_k(70, 70, 0.0, 4900)
        self.assertAlmostEqual(k1, 1.37, places=6)
        self.assertAlmostEqual(k2, 5.65, places=6)

    def test_curves_b_and_c(self):
        k1, k2 = ieee80._schwarz_k(140, 70, math.sqrt(9800) / 10, 9800)   # h = sqrt(A)/10
        self.assertAlmostEqual(k1, -0.05 * 2 + 1.20, places=6)
        self.assertAlmostEqual(k2, 0.10 * 2 + 4.68, places=6)
        k1, k2 = ieee80._schwarz_k(140, 70, 1e3, 9800)           # below curve C
        self.assertAlmostEqual(k2, -0.05 * 2 + 4.40, places=6)

    def test_k2_grows_with_aspect_ratio_at_the_surface(self):
        _, k2a = ieee80._schwarz_k(70, 70, 0.0, 4900)
        _, k2b = ieee80._schwarz_k(140, 70, 0.0, 9800)
        self.assertGreater(k2b, k2a)

    def test_annex_b_with_rods(self):
        g = ieee80.GridGeometry(70, 70, 7, 0.5, 0.01, n_rods=20, Lr=7.5)
        r = ieee80.schwarz_resistance(400, g)
        self.assertAlmostEqual(r["R1"], 2.8845, places=3)
        self.assertAlmostEqual(r["Rg"], 2.8441, places=3)
        self.assertLess(r["Rg"], r["R1"])


class TestKFactorsConsistent(unittest.TestCase):
    MAT = {"copper": (226.0, 234.5), "aluminium": (148.0, 228.0),
           "steel": (78.0, 202.0)}

    def _k(self, mat, ti, tf):
        c, B = self.MAT[mat]
        return c * math.sqrt(math.log(1.0 + (tf - ti) / (B + ti)))

    def test_every_table_matches_its_temperatures(self):
        for table in (materials.K_FACTORS_SEPARATE, materials.K_FACTORS_IN_CABLE,
                      materials.K_FACTORS_BURIED):
            for (mat, _ins), v in table.items():
                k = self._k(mat, v["Ti"], v["Tf"])
                self.assertLess(abs(k - v["k"]) / v["k"], 0.03,
                                f"{mat} {v['label']}: table {v['k']}, formula {k:.1f}")


class TestSchlumbergerFiniteMN(unittest.TestCase):
    def _direct(self, s, d, r1, r2, h):
        K = (r2 - r1) / (r2 + r1)
        G = lambda r: 1 / r + 2 * sum(K ** n / math.hypot(r, 2 * n * h) for n in range(1, 600))
        dv = r1 / (2 * math.pi) * 2 * (G(s - d / 2) - G(s + d / 2))
        return math.pi * (s * s - d * d / 4) / d * dv

    def test_matches_superposition(self):
        for s, d in ((5, 2), (10, 2), (20, 8)):
            self.assertAlmostEqual(soil.schlumberger_two_layer(s, 300, 80, 3, d),
                                   self._direct(s, d, 300, 80, 3), places=6)

    def test_small_mn_tends_to_ideal(self):
        ideal = soil.schlumberger_two_layer(10, 300, 80, 3)
        self.assertAlmostEqual(soil.schlumberger_two_layer(10, 300, 80, 3, 0.01), ideal, places=4)

    def test_uniform_soil_any_mn(self):
        self.assertAlmostEqual(soil.schlumberger_two_layer(10, 150, 150.0000001, 3, 6), 150, places=4)

    def test_inversion_recovers_model_with_wide_mn(self):
        s = [1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32]
        mn = [0.4 * x for x in s]                    # MN = AB/5
        rho = [soil.schlumberger_two_layer(x, 250, 60, 2.0, m) for x, m in zip(s, mn)]
        r = soil.invert_two_layer(s, rho, "schlumberger", mn)
        self.assertLess(abs(r["rho1"] / 250 - 1), 0.01)
        self.assertLess(abs(r["rho2"] / 60 - 1), 0.01)
        self.assertLess(abs(r["h"] / 2.0 - 1), 0.02)
        self.assertTrue(r["finite_mn"])


if __name__ == "__main__":
    unittest.main()


class TestInversionUncertainty(unittest.TestCase):
    def test_tutorial_traverse(self):
        r = soil.invert_two_layer([1, 2, 4, 6, 10, 16], [320, 245, 182, 162, 168, 182])
        u = r["uncertainty"]
        self.assertEqual(u["dof"], 3)
        self.assertLess(u["corr_rho1_h"], -0.8)            # equivalence
        self.assertLess(u["rho2"]["sd_pct"], u["rho1"]["sd_pct"])
        self.assertLess(u["rho1"]["sd_pct"], u["h"]["sd_pct"])
        self.assertTrue(320 < u["rho1"]["low_68"] < 340)
        self.assertTrue(1.15 < u["h"]["high_68"] < 1.25)

    def test_three_points_have_no_uncertainty(self):
        r = soil.invert_two_layer([1, 4, 16], [300, 200, 150])
        self.assertIsNone(r["uncertainty"])


class TestIEC62305Figures(unittest.TestCase):
    """Values read from the vector drawings of IEC 62305-3:2010 Fig. 1 and 3."""

    def test_l1_lines(self):
        from earthsys import iec62305
        l1 = lambda c, r: iec62305.min_electrode_length(c, r)["l1"]
        self.assertAlmostEqual(l1("I", 500), 5.0)
        self.assertAlmostEqual(l1("I", 2000), 50.0)
        self.assertAlmostEqual(l1("I", 3000), 80.0)
        self.assertAlmostEqual(l1("II", 800), 5.0)
        self.assertAlmostEqual(l1("II", 2000), 29.0)
        self.assertAlmostEqual(l1("II", 3000), 49.0)
        self.assertAlmostEqual(l1("III", 3000), 5.0)
        self.assertAlmostEqual(l1("II", 4000), 69.0)       # last slope kept

    def test_protective_angle(self):
        from earthsys import airterm
        a = lambda c, h: airterm.protective_angle(c, h)["alpha"]
        self.assertAlmostEqual(a("I", 10), 45.4, places=1)
        self.assertAlmostEqual(a("IV", 30), 44.8, places=1)
        self.assertAlmostEqual(a("II", 1.0), a("II", 2.0))  # constant below 2 m
        self.assertFalse(airterm.protective_angle("I", 21)["applicable"])

    def test_kc_three_and_more(self):
        from earthsys import iec62305
        self.assertAlmostEqual(iec62305.separation_distance("II", 10, 3)["kc"], 0.44)
        self.assertAlmostEqual(iec62305.separation_distance("II", 10, 2)["kc"], 0.66)
