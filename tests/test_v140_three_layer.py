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
Version 1.4.0: three-layer soil — inversion, grid rule and boundary elements.

Every reference value here comes from outside the code under test:

* the two-layer limits come from the validated two-layer code of earlier
  releases (soil.py, bem.py);
* the three-layer Green's function values were computed by solving the
  layered boundary-value problem numerically at each λ and integrating the
  Hankel transform with adaptive quadrature (scipy), a method that shares
  nothing with the image expansion;
* the rod resistances come from an axisymmetric finite-volume solution
  (scipy sparse, 1–1.7 million nodes, far boundary at 20 km, converged to
  0.05 %), again independent of the boundary-element solver;
* the field traverses and the published fits are those of Gonos and
  Stathopulos (IEEE Trans. PWRD 20(1), 2005, Tables III–IV) and Li and Rao
  (IET GTD 12(21), 2018, Tables 4–7).
"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import api, bem, layered as L, soil       # noqa: E402

# (rho, h, source layer, field layer, r, z, z', G in V per A)
GREEN_REF = [
    ([300, 30, 3000], [1.0, 1.5], 1, 1, 3.0, 0.5, 0.8, 12.411974192),
    ([300, 30, 3000], [1.0, 1.5], 1, 2, 5.0, 2.0, 0.5, 10.7790103446),
    ([300, 30, 3000], [1.0, 1.5], 1, 3, 8.0, 4.0, 0.5, 8.95006823466),
    ([300, 30, 3000], [1.0, 1.5], 2, 2, 1.5, 1.5, 2.2, 14.2511313867),
    ([300, 30, 3000], [1.0, 1.5], 2, 3, 6.0, 3.5, 1.8, 9.81712925207),
    ([300, 30, 3000], [1.0, 1.5], 3, 1, 10.0, 0.0, 4.5, 8.30374135156),
    ([300, 30, 3000], [1.0, 1.5], 3, 3, 2.0, 5.0, 6.0, 77.4961457719),
    ([50, 800, 20], [1.0, 2.0], 1, 1, 3.0, 0.5, 0.8, 7.22129264887),
    ([50, 800, 20], [1.0, 2.0], 1, 2, 5.0, 2.0, 0.5, 2.41068959774),
    ([50, 800, 20], [1.0, 2.0], 1, 3, 8.0, 4.0, 0.5, 0.36102105249),
    ([50, 800, 20], [1.0, 2.0], 2, 2, 1.5, 1.5, 2.2, 9.99353701618),
    ([50, 800, 20], [1.0, 2.0], 2, 3, 6.0, 3.5, 1.8, 0.471636073757),
    ([50, 800, 20], [1.0, 2.0], 3, 1, 10.0, 0.0, 4.5, 0.304000920779),
    ([50, 800, 20], [1.0, 2.0], 3, 3, 2.0, 5.0, 6.0, 0.990793772725),
]

# (rho, h, top, length, radius, R by finite volumes)
ROD_REF = [
    ([300, 30, 3000], [1.0, 1.5], 0.3, 4.0, 0.008, 29.885140),
    ([50, 800, 20], [1.0, 2.0], 0.5, 6.0, 0.008, 5.419591),
    ([164.5, 71.6, 203.7], [1.2, 10.6], 0.0, 15.0, 0.008, 8.038000),
    ([1000, 100, 10], [0.5, 2.0], 0.2, 5.0, 0.010, 3.285367),
]

GONOS_A = ([1, 3, 5, 10, 15, 20, 30, 50, 80],
           [214, 256, 273, 307, 284, 250, 225, 210, 186])
GONOS_B = ([1, 3, 6, 8, 10, 15, 20, 40, 60],
           [138, 79, 71, 67, 80, 88, 99, 151, 170])


def rms_of(xs, ys, rho, h):
    m = L.apparent(L.LayeredEarth(rho, h), "wenner", xs)
    y = np.asarray(ys, float)
    return float(np.sqrt(np.mean(((m - y) / y) ** 2)) * 100)


class TwoLayerLimit(unittest.TestCase):
    """With two layers every new routine must reproduce the old code."""

    CASES = [(300, 100, 2.0), (50, 1000, 1.0), (400, 10, 0.5), (100, 5000, 3.0)]

    def test_wenner_and_schlumberger(self):
        xs = [0.5, 1, 2, 3, 5, 8, 12, 20, 40, 80]
        for r1, r2, h in self.CASES:
            e = L.LayeredEarth([r1, r2], [h])
            w = L.apparent(e, "wenner", xs)
            s = L.apparent(e, "schlumberger", xs, [0.2 * x for x in xs])
            for i, a in enumerate(xs):
                self.assertAlmostEqual(w[i] / soil.wenner_two_layer(a, r1, r2, h), 1, delta=1e-6)
                self.assertAlmostEqual(
                    s[i] / soil.schlumberger_two_layer(a, r1, r2, h, 0.2 * a), 1, delta=1e-6)

    def test_surface_images_are_K_to_the_n(self):
        e = L.LayeredEarth([300, 100], [2.0])
        D, c = L.surface_images(e)
        K = -0.5
        for n in (1, 2, 3, 4):
            self.assertAlmostEqual(D[n - 1], 4.0 * n, places=9)
            self.assertAlmostEqual(c[n - 1], K ** n, places=12)

    def test_disc_factor(self):
        for r1, r2, h in self.CASES:
            K = (r2 - r1) / (r2 + r1)
            for r in (5.0, 10.0, 40.0):
                self.assertAlmostEqual(L.disc_factor(L.LayeredEarth([r1, r2], [h]), r),
                                       soil.disc_factor(K, h / r), delta=1e-7)

    def test_image_series_matches_bem(self):
        rng = np.random.default_rng(1)
        r1, r2, h = 300.0, 100.0, 2.0
        e = L.LayeredEarth([r1, r2], [h])
        sm = bem.SoilModel(r1, r2, h, tol=1e-12)
        for sl in (1, 2):
            ser = L.image_series(e, sl, tol=1e-13)
            for fl in (1, 2):
                for _ in range(10):
                    r = rng.uniform(0.1, 30)
                    zp = rng.uniform(0.05, h - 0.01) if sl == 1 else rng.uniform(h + .01, 8)
                    z = rng.uniform(0, h) if fl == 1 else rng.uniform(h, 8)
                    s, sh, a = ser[fl]
                    g = e.rho[sl - 1] / (4 * math.pi) * np.sum(
                        a / np.sqrt(r * r + (z - s * zp - sh) ** 2))
                    ref = sum(c / math.sqrt(r * r + (z - (sg * zp + shf)) ** 2)
                              for c, sg, shf in bem.image_terms(sm, sl, fl))
                    self.assertAlmostEqual(g / ref, 1, delta=1e-9)


class ThreeLayerGreen(unittest.TestCase):
    """Image expansion and the solver's compressed form against an
    independent spectral computation."""

    def test_image_series_exact(self):
        """The full series (no pruning).  The 300/30/3000 earth needs some
        17 000 bounces and was checked offline to 3.5·10⁻¹⁰; here the
        resistive-middle earth is checked."""
        cache = {}
        for rho, h, sl, fl, r, z, zp, G in GREEN_REF:
            if rho[1] == 30:
                continue
            key = (tuple(rho), sl)
            if key not in cache:
                cache[key] = L.image_series(L.LayeredEarth(rho, h), sl, tol=1e-11)
            s, sh, a = cache[key][fl]
            g = rho[sl - 1] / (4 * math.pi) * np.sum(a / np.sqrt(r * r + (z - s * zp - sh) ** 2))
            self.assertAlmostEqual(g / G, 1, delta=1e-7, msg=f"{rho} {sl}->{fl}")

    def test_compressed_green_for_solver(self):
        greens = {}
        for rho, h, sl, fl, r, z, zp, G in GREEN_REF:
            if tuple(rho) not in greens:
                greens[tuple(rho)] = L.LayeredGreen(L.LayeredEarth(rho, h), 6.0, 60.0)
            g = greens[tuple(rho)].sum_terms(sl, fl, np.array([[r * r]]),
                                             np.array([[z]]), np.array([[zp]]))[0, 0]
            g *= rho[sl - 1] / (4 * math.pi)
            self.assertAlmostEqual(g / G, 1, delta=1e-4, msg=f"{rho} {sl}->{fl}")

    def test_slow_series_is_fast(self):
        """A conductive layer between resistive ones (300/30/3000) needs
        thousands of bounces; the solver's tables must still build quickly."""
        import time
        t = time.time()
        L.LayeredGreen(L.LayeredEarth([300, 30, 3000], [1.0, 4.0]), 8.0, 200.0)
        self.assertLess(time.time() - t, 10.0)


class ThreeLayerSolver(unittest.TestCase):

    ITEMS = ([dict(kind="grid", Lx=40, Ly=40, D=8, depth=0.5, radius=0.006)] +
             [dict(kind="rod", x=x, y=y, top_depth=0.5, length=6, radius=0.008)
              for x in (0, 40) for y in (0, 40)])

    def solve(self, spec, seg=2.0):
        net = bem.build_network(dict(spec, items=self.ITEMS))
        net.discretise(seg)
        return net.solve()["Rg"]

    def test_degenerate_three_layer_equals_two_layer(self):
        pairs = [(dict(rho1=200, rho2=50, h_layer=2.0),
                  dict(rho1=200, rho2=50, h_layer=2.0, rho3=50, h_layer2=3.0)),
                 (dict(rho1=100, rho2=1000, h_layer=3.0),
                  dict(rho1=100, rho2=100, h_layer=1.0, rho3=1000, h_layer2=2.0))]
        for two, three in pairs:
            self.assertAlmostEqual(self.solve(three) / self.solve(two), 1, delta=1e-4)

    def test_rod_against_finite_volumes(self):
        for rho, h, top, Lr, a, R in ROD_REF:
            spec = dict(rho1=rho[0], rho2=rho[1], h_layer=h[0], rho3=rho[2], h_layer2=h[1],
                        items=[dict(kind="rod", x=0, y=0, top_depth=top, length=Lr, radius=a)])
            net = bem.build_network(spec)
            net.discretise(0.25)
            Rg = net.solve()["Rg"]
            self.assertAlmostEqual(Rg / R, 1, delta=0.005, msg=f"{rho}")

    def test_segments_split_at_both_interfaces(self):
        net = bem.build_network(dict(rho1=100, rho2=10, h_layer=1.0, rho3=1000, h_layer2=2.0,
                                     items=[dict(kind="rod", x=0, y=0, top_depth=0.5,
                                                 length=4.0, radius=0.008)]))
        net.discretise(10.0)
        self.assertEqual(sorted(set(s.layer for s in net.segments)), [1, 2, 3])
        for s in net.segments:
            zs = sorted((s.p1[2], s.p2[2]))
            self.assertFalse(zs[0] < 1.0 < zs[1] or zs[0] < 3.0 < zs[1])


class Inversion(unittest.TestCase):

    def test_noise_free_recovery(self):
        truth = L.LayeredEarth([120, 15, 600], [1.5, 4.0])
        xs = [0.5, 1, 1.5, 2, 3, 5, 7, 10, 15, 20, 30, 50]
        y = L.apparent(truth, "wenner", xs)
        fit = L.invert_layers(xs, y, 3)
        self.assertLess(fit["rms_pct"], 0.05)
        self.assertAlmostEqual(fit["rho"][0] / 120, 1, delta=0.01)
        self.assertAlmostEqual(fit["rho"][2] / 600, 1, delta=0.05)
        # a conductive middle layer: its conductance h/ρ is what is fixed
        self.assertAlmostEqual(fit["h"][1] / fit["rho"][1] / (4.0 / 15), 1, delta=0.05)

    def test_gonos_case_B_h_type(self):
        """H-type field traverse.  Published fits: Gonos & Stathopulos (GA)
        164.5/71.6/203.7, 1.2/10.6; Pereira et al. (DE) 169.6/65.83/236.78,
        0.91/12.21; Li & Rao (SA) 165.85/63.76/242.13, 0.96/11.85."""
        xs, ys = GONOS_B
        fit = L.invert_layers(xs, ys, 3)
        self.assertLessEqual(fit["rms_pct"], rms_of(xs, ys, [165.85, 63.76, 242.13], [0.96, 11.85]) + 0.01)
        self.assertLess(fit["rms_pct"], rms_of(xs, ys, [169.6, 65.83, 236.78], [0.91, 12.21]))
        self.assertAlmostEqual(fit["rho"][1] / 63.76, 1, delta=0.05)
        self.assertAlmostEqual(fit["depths"][1] / (0.96 + 11.85), 1, delta=0.05)

    def test_gonos_case_A_k_type_and_selection(self):
        xs, ys = GONOS_A
        two = soil.invert_two_layer(xs, ys, "wenner")
        sel = L.select_three(xs, ys, two)
        self.assertEqual(sel["chosen"], 3)
        self.assertLess(sel["p_value"], 0.05)
        fit = sel["three"]
        for rho, h in (([196.9, 351.7, 185.2], [1.7, 8.4]), ([198.7, 352.0, 186.3], [1.7, 8.5])):
            self.assertLess(fit["rms_pct"], rms_of(xs, ys, rho, h))
        eq = fit["uncertainty"]["equivalence"]
        self.assertLess(eq["corr_rho2_h2"], -0.9)     # resistive layer: ρ₂ traded against h₂

    def test_f_test_closed_form(self):
        # P(F > f) for (2, d2) degrees of freedom against direct integration
        f, d2 = 3.1, 7
        F, p = L._f_test_p(1.0 + 2 * f / d2, 1.0, d2 + 5)
        self.assertAlmostEqual(F, f, places=12)
        trap = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
        x = np.linspace(0.0, 4000.0, 4000001)
        pdf = (1 + 2 * x / d2) ** (-(d2 + 2) / 2)          # ∝ F(2, d2) density
        self.assertAlmostEqual(p, trap(pdf[x >= f], x[x >= f]) / trap(pdf, x), delta=1e-4)


class GridRule(unittest.TestCase):

    def test_equivalent_two_layer_keeps_disc_resistance(self):
        e = L.LayeredEarth([211.5, 374.5, 186.5], [2.21, 7.67])
        two = L.equivalent_two_layer(e, 1600.0, 0.5)
        F2 = L.disc_factor(L.LayeredEarth([two["rho1"], two["rho2"]], [two["h"]]),
                           math.sqrt(1600.0 / math.pi))
        self.assertAlmostEqual(F2, two["F"], delta=1e-6)
        self.assertEqual(two["rho1"], 211.5)

    def test_api_round_trip(self):
        xs, ys = GONOS_A
        r = api.api_soil_invert(dict(array="wenner", layers="auto", grid_area=1600,
                                     rows=[dict(a=a, rho=v) for a, v in zip(xs, ys)]))
        self.assertEqual(r["n_layers"], 3)
        for k in ("rho1", "rho2", "rho3", "h", "h2", "two_layer", "model_selection"):
            self.assertIn(k, r)
        e = api.api_soil_equivalent(dict(rho1=r["rho1"], rho2=r["rho2"], h=r["h"],
                                         rho3=r["rho3"], h2=r["h2"], Lx=40, Ly=40, D=8,
                                         h_grid=0.5))
        self.assertIn("equivalent_two_layer", e)
        self.assertGreater(e["rho_equivalent"], 0)
        with self.assertRaises(ValueError):
            api.api_bem(dict(rho1=100, rho3=50, h_layer2=2, segment_length=2,
                             items=[dict(kind="rod", x=0, y=0, length=3)]))

    def test_two_layer_site_stays_two_layer_and_fast(self):
        # the built-in example traverse (a genuine two-layer site)
        xs = [1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 40]
        ys = [292, 279, 272, 229, 202, 156, 132, 120, 112, 112, 109, 108]
        r = api.api_soil_invert(dict(array="wenner", rows=[dict(a=a, rho=v) for a, v in zip(xs, ys)]))
        self.assertEqual(r["n_layers"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
