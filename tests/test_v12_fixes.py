# Earthing System — earthing system design to IEEE 80, IEC 60364, IEC 62305 and IEEE 142.
# Copyright (C) 2026 Emad Roshandel
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

"""
Regression tests for the six defects found while writing the second edition
of "Earthing System Design — Theory and Practice" (its Appendix D).

Each test fails on version 1.1 and passes on 1.2.  Reference values come
from an independent Galerkin boundary-element solver with the complete
two-layer Green's function, written for the book.

    python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import api, bem, iec60364, ieee80, soil  # noqa: E402

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:                                         # pragma: no cover
    HAVE_NUMPY = False

ANNEX_B = dict(Lx=70, Ly=70, D=7, h=0.5, d=0.01)
# Annex B grid in 2 m of 400 ohm-m: independent two-layer BEM (tutorial Table 6.2)
BEM_REF = {(100, 0): 0.955, (1600, 0): 8.238, (100, 20): 0.777, (1600, 20): 8.061}


class TestEquivalentResistivityForGrids(unittest.TestCase):
    """Fix 1: 'auto' used the burial depth and ignored the grid size."""

    def _closed_form(self, rho2, rods):
        g = ieee80.GridGeometry(**ANNEX_B, n_rods=rods, Lr=7.5)
        e = soil.equivalent_uniform(400, rho2, 2.0, 0.5, 0.0, "auto", g.A, g.LT)
        return ieee80.sverak_resistance(e["rho_equivalent"], g.A, g.LT, g.h)["Rg"], e

    def test_conservative_and_close_for_annex_b(self):
        # v1.1: +191 % (rho2 = 100) and -66 % (rho2 = 1600, unsafe)
        for rho2 in (100, 1600):
            R, e = self._closed_form(rho2, 0)
            ref = BEM_REF[(rho2, 0)]
            self.assertEqual(e["method_used"], "grid")
            self.assertGreaterEqual(R, ref, "must not be optimistic")
            self.assertLess(R / ref - 1.0, 0.15)

    def test_with_rods_still_conservative(self):
        for rho2 in (100, 1600):
            R, _ = self._closed_form(rho2, 20)
            self.assertGreaterEqual(R, BEM_REF[(rho2, 20)])

    def test_uniform_soil_returns_rho1(self):
        e = soil.equivalent_uniform(400, 400, 2.0, 0.5, 0.0, "auto", 4900, 1540)
        self.assertAlmostEqual(e["rho_equivalent"], 400.0, places=6)

    def test_disc_factor_limits(self):
        self.assertAlmostEqual(soil.disc_factor(0.0, 0.1), 1.0)
        # very thick top layer: the disc sees only rho1
        self.assertAlmostEqual(soil.disc_factor(0.6, 1e4), 1.0, places=3)
        # very thin top layer: the disc sees rho2, so F -> rho2/rho1
        K = (1600 - 400) / 2000
        self.assertAlmostEqual(soil.disc_factor(K, 1e-4), 4.0, delta=0.02)
        K = (100 - 400) / 500
        self.assertAlmostEqual(soil.disc_factor(K, 1e-4), 0.25, delta=0.01)

    def test_disc_factor_series_with_tail(self):
        K, q = 0.6, 0.051
        S = sum(K ** n * (math.atan(1 / (n * q))
                          - n * q / 2 * math.log1p(1 / (n * q) ** 2))
                for n in range(1, 100000))
        self.assertAlmostEqual(soil.disc_factor(K, q), 1 + 4 / math.pi * S, places=9)

    def test_api_endpoint_uses_the_grid(self):
        e = api.dispatch("/api/soil/equivalent", dict(
            rho1=400, rho2=1600, h=2.0, Lx=70, Ly=70, D=7, h_grid=0.5))
        self.assertEqual(e["method_used"], "grid")
        self.assertGreater(e["rho_equivalent"], 1200)   # v1.1 gave 400

    def test_without_area_falls_back_with_warning(self):
        e = soil.equivalent_uniform(400, 1600, 2.0, 0.5, 0.0, "auto")
        self.assertEqual(e["rho_equivalent"], 400)
        self.assertIn("grid area", e["note"])

    def test_grid_method_requires_area(self):
        with self.assertRaises(ValueError):
            soil.equivalent_uniform(400, 1600, 2.0, 0.5, 0.0, "grid")


@unittest.skipUnless(HAVE_NUMPY, "numpy required")
class TestTwoLayerKernel(unittest.TestCase):
    """Fix 2: rods below the interface used the upper-layer Green's function."""

    def _net(self, rho2, rods=True, h=2.0):
        g = ieee80.GridGeometry(**ANNEX_B, n_rods=20, Lr=7.5)
        items = [dict(kind="grid", Lx=70, Ly=70, D=7, depth=0.5, radius=0.005)]
        if rods:
            items += [dict(kind="rod", x=x, y=y, top_depth=0.5, length=7.5,
                           radius=0.008) for x, y in g.rod_positions()]
        return bem.build_network(dict(rho1=400, rho2=rho2, h_layer=h,
                                      IG=1000, items=items))

    def test_annex_b_rods_into_conductive_layer(self):
        # v1.1: 0.7606 ohm, 2.1 % low (unsafe)
        R = self._net(100).solve()["Rg"]
        self.assertAlmostEqual(R, BEM_REF[(100, 20)], delta=0.004)

    def test_rod_segments_are_split_and_labelled(self):
        net = self._net(100)
        net.discretise(2.0)
        for s in net.segments:
            lo, hi = sorted((s.p1[2], s.p2[2]))
            self.assertFalse(lo < 2.0 - 1e-9 < hi - 2e-9 and hi > 2.0 + 1e-9,
                             "a segment straddles the interface")
            self.assertEqual(s.layer, 2 if s.mid[2] > 2.0 else 1)

    def test_potential_continuous_across_interface(self):
        net = self._net(100)
        net.solve()
        above = net.potential_at([[35.0, 10.0, 2.0 - 1e-6]])[0]
        below = net.potential_at([[35.0, 10.0, 2.0 + 1e-6]])[0]
        self.assertAlmostEqual(above / below, 1.0, places=5)

    def test_rod_wholly_in_lower_layer_matches_uniform_limit(self):
        # a thin 0.01 m top layer: a rod from 1 m to 4 m is in rho2 soil
        n2 = bem.build_network(dict(rho1=1000, rho2=100, h_layer=0.01, IG=1,
                                    items=[dict(kind="rod", x=0, y=0, top_depth=1.0,
                                                length=3.0, radius=0.008)]))
        nu = bem.build_network(dict(rho1=100, IG=1,
                                    items=[dict(kind="rod", x=0, y=0, top_depth=1.0,
                                                length=3.0, radius=0.008)]))
        r2, ru = n2.solve(0.5)["Rg"], nu.solve(0.5)["Rg"]
        self.assertAlmostEqual(r2 / ru, 1.0, delta=0.02)

    def test_grid_only_unchanged(self):
        # nothing crosses the interface: identical to v1.1
        R = self._net(1600, rods=False).solve()["Rg"]
        self.assertAlmostEqual(R, 8.2362, delta=0.001)


class TestAutomaticResistanceFormula(unittest.TestCase):
    """Fix 3: Sverak -> Schwarz switch made rods appear to raise R_g."""

    def test_adding_rods_never_raises_rg(self):
        prev = None
        for n in (0, 4, 8, 12, 20, 40):
            g = ieee80.GridGeometry(**ANNEX_B, n_rods=n, Lr=7.5)
            R = ieee80.grid_resistance(400, g)["Rg"]
            if prev is not None:
                self.assertLessEqual(R, prev + 1e-12)
            prev = R

    def test_no_rods_is_sverak(self):
        g = ieee80.GridGeometry(**ANNEX_B)
        self.assertAlmostEqual(ieee80.grid_resistance(400, g)["Rg"], 2.7757, places=3)

    def test_explicit_methods_unchanged(self):
        g = ieee80.GridGeometry(**ANNEX_B, n_rods=20, Lr=7.5)
        self.assertAlmostEqual(ieee80.grid_resistance(400, g, "schwarz")["Rg"], 2.867, places=3)
        self.assertAlmostEqual(ieee80.grid_resistance(400, g, "sverak")["Rg"], 2.753, places=3)


class TestRodGroupFactor(unittest.TestCase):
    """Fix 4: hollow-square lambda held line-like values (3.45 for 8 rods)."""

    def test_bs7430_hollow_square(self):
        for n, lam in ((4, 2.71), (8, 4.51), (12, 5.48), (16, 6.13), (20, 6.63)):
            self.assertAlmostEqual(iec60364.rod_group_lambda(n, "hollow_square")[0], lam)

    def test_computed_lambda_matches_definition(self):
        # three in a line: (1.5 + 2 + 1.5)/3
        pts_lam = iec60364.rod_group_lambda(11, "line")[0]
        exact = sum(sum(1.0 / abs(i - j) for j in range(11) if j != i)
                    for i in range(11)) / 11
        self.assertAlmostEqual(pts_lam, exact)

    def test_filled_square_not_line(self):
        # 3 x 3 filled square couples more strongly than 9 in a line
        self.assertGreater(iec60364.rod_group_lambda(9, "square")[0],
                           iec60364.rod_group_lambda(9, "line")[0] + 1.0)

    def test_eight_rods_resistance_higher_than_v11(self):
        r = iec60364.rods_parallel(100, 3.0, 0.016, 8, 3.0, "hollow_square")
        self.assertEqual(r["lam"], 4.51)


class TestMutualResistanceOfElectrodes(unittest.TestCase):
    """Fix 5: dissimilar electrodes were combined with coupling 1.0."""

    def test_villa_combination_includes_mutual(self):
        c = iec60364.parallel_combination([4.01, 27.1], 1.0, 150.0)
        self.assertTrue(c["mutual"])
        self.assertGreater(c["R"], 3.493 * 1.05)       # v1.1: 3.493
        self.assertLessEqual(c["R"], 4.01)             # never worse than best alone

    def test_far_apart_is_ideal_parallel(self):
        c = iec60364.parallel_combination([10.0, 10.0], 1.0, 100.0, 1000.0)
        self.assertAlmostEqual(c["R"], 5.0, delta=0.02)

    def test_equal_rods_match_two_rod_formula(self):
        # two equal rods at spacing s: R = (R1 + rho/(2 pi s))/2
        R1, rho, s = 50.0, 150.0, 6.0
        c = iec60364.parallel_combination([R1, R1], 1.0, rho, s)
        self.assertAlmostEqual(c["R"], (R1 + rho / (2 * math.pi * s)) / 2, places=9)

    def test_building_assessment_uses_it(self):
        d = iec60364.assess("TT", 230, 150,
                            [dict(type="foundation", volume_m3=420),
                             dict(type="rods_parallel", L=3, d=0.016, n=2, s=6)],
                            dict(kind="rcd", rating_A=0.03))
        self.assertGreater(d["RA"], 3.6)


class TestSoilFitQuality(unittest.TestCase):
    """Fix 6: an H-type traverse was fitted and used without comment."""

    OLD_DEMO = [(1, 320), (1.5, 245), (2, 182), (3, 162), (4, 168), (6, 182),
                (9, 198), (12, 214), (16, 228), (20, 236)]
    NEW_DEMO = [(1, 292), (1.5, 279), (2, 272), (3, 229), (4, 202), (6, 156),
                (8, 132), (12, 120), (16, 112), (24, 112), (32, 109), (40, 108)]

    def test_three_layer_curve_is_flagged(self):
        a, r = zip(*self.OLD_DEMO)
        f = soil.invert_two_layer(a, r, "wenner")
        self.assertEqual(f["fit_quality"], "poor")
        self.assertTrue(f["three_layer_suspected"])
        self.assertIn("three", f["fit_warning"])

    def test_mild_three_layer_is_a_note_not_a_block(self):
        # the villa example's traverse: 10 % rise, acceptable fit
        f = soil.invert_two_layer([0.5, 1, 2, 4, 8, 16],
                                  [210, 186, 160, 148, 152, 163], "wenner")
        self.assertEqual(f["fit_quality"], "acceptable")
        self.assertFalse(f["fit_warning"])
        self.assertTrue(f["fit_note"])

    def test_new_demo_is_a_good_two_layer_site(self):
        a, r = zip(*self.NEW_DEMO)
        f = soil.invert_two_layer(a, r, "wenner")
        self.assertEqual(f["fit_quality"], "good")
        self.assertFalse(f["fit_warning"])
        self.assertAlmostEqual(f["rho1"], 300, delta=15)
        self.assertAlmostEqual(f["rho2"], 110, delta=6)
        self.assertAlmostEqual(f["h"], 2.5, delta=0.3)


if __name__ == "__main__":
    unittest.main()
