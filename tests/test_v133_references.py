"""Checks against the reference texts supplied for the 1.3.3 review:
IEEE Std 80-2013 (+Cor 1-2015), BS 7430:2011+A1:2015, CIGRE TB 781."""
import unittest

from earthsys import faultcurrent, iec60364, iec62305, materials, standards


class TestIeee80Table1(unittest.TestCase):
    def test_2013_material_constants(self):
        m = materials.IEEE80_MATERIALS
        self.assertAlmostEqual(m["cu_hard"]["TCAP"], 3.4)
        self.assertAlmostEqual(m["steel_1020"]["TCAP"], 3.8)
        self.assertAlmostEqual(m["steel_1020"]["alpha_r"], 0.00377)
        self.assertEqual(m["steel_1020"]["K0"], 245)
        self.assertAlmostEqual(m["ccs_rod_17"]["rho_r"], 10.1)


class TestTableC1(unittest.TestCase):
    """IEEE 80-2013 Annex C worked examples."""

    def test_example_C4(self):
        # 1 line, 2 feeders, Rg = 5 ohm, 1600 A -> Ig = 182 A
        sf = faultcurrent.split_factor_table_c1(5.0, 1, 2)["Sf"]
        self.assertAlmostEqual(1600 * sf, 182, delta=0.6)

    def test_example_C3(self):
        self.assertAlmostEqual(faultcurrent.split_factor_table_c1(1.0, 2, 2)["Sf"], 0.349, places=3)
        self.assertAlmostEqual(faultcurrent.split_factor_table_c1(1.0, 2, 4)["Sf"], 0.247, places=3)

    def test_missing_row(self):
        with self.assertRaises(ValueError):
            faultcurrent.split_factor_table_c1(1.0, 3, 2)


class TestBs7430Lambda(unittest.TestCase):
    def test_line_formula(self):
        # 9.5.4: lambda = 2(1/2 + ... + 1/n)
        for n, lam in ((2, 1.0), (3, 1.667), (4, 2.167), (6, 2.9), (10, 3.858)):
            self.assertAlmostEqual(iec60364.rod_group_lambda(n, "line")[0], lam, places=3)

    def test_line_equals_neighbour_sum(self):
        for n in (4, 7, 12):
            exact = sum(sum(1.0 / abs(i - j) for j in range(n) if j != i) for i in range(n)) / n
            self.assertAlmostEqual(iec60364.rod_group_lambda(n, "line")[0], exact)

    def test_hollow_table2(self):
        lam, src = iec60364.rod_group_lambda(36, "hollow_square")
        self.assertAlmostEqual(lam, 7.90)
        self.assertIn("Table 2", src)


class TestCigre781(unittest.TestCase):
    def test_engineering_expressions(self):
        # TB 781 Eq. 5.3-5.4: rho = rho0/(1 + 4.7e-6 rho0^0.73 f^0.54),
        # eps_r = 9.5e4 rho0^-0.27 f^-0.46 + 12
        for rho0, f in ((300, 1e5), (1000, 2.5e5), (3000, 1e6)):
            d = standards.alipio_visacro(rho0, f)
            self.assertAlmostEqual(d["rho"] / (rho0 / (1 + 4.7e-6 * rho0 ** 0.73 * f ** 0.54)), 1, delta=0.01)
            self.assertAlmostEqual(d["eps_r"] / (9.5e4 * rho0 ** -0.27 * f ** -0.46 + 12), 1, delta=0.01)

    def test_conservative_levels_ordered(self):
        r = [standards.alipio_visacro(1000, 2.5e5, level=l)["rho"]
             for l in ("mean", "relatively_conservative", "conservative")]
        self.assertTrue(r[0] < r[1] < r[2] < 1000)

    def test_table_4_1(self):
        self.assertAlmostEqual(standards.tb781_impulse_reduction(1000, "first")["factor"], 0.89)
        self.assertAlmostEqual(standards.tb781_impulse_reduction(4000, "subsequent")["factor"], 0.50)
        self.assertIn("mandatory", standards.tb781_impulse_reduction(1000)["relevance"])
        self.assertIn("ignore", standards.tb781_impulse_reduction(200)["relevance"])

    def test_counterpoise_and_tower(self):
        self.assertAlmostEqual(standards.tb781_counterpoise_zp1st(600, 30)["Z_P1st"], 0.16 * 600 * 30 ** -0.687)
        self.assertAlmostEqual(standards.tb781_counterpoise_zp1st(2000, 60)["Z_P1st"], 0.4 * 2000 ** 0.89 * 60 ** -0.75)
        self.assertAlmostEqual(standards.tb781_tower_ic1st(1000)["IC_1st"], 0.84)

    def test_lps_reports_factor(self):
        d = iec62305.design("III", 1000, 400, 80, arrangement="B")
        sf = d["soil_frequency"]
        self.assertGreater(sf["Zp_factor_first"], sf["ratio"])


if __name__ == "__main__":
    unittest.main()
