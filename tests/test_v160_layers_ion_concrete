"""1.6.0: layered soil in the lightning model, soil ionisation and
concrete-encased (foundation) electrodes.

References
  Arnautovski-Toseva, Grcev & El Khamlichi Drissi (2007), "High frequency
    electromagnetic analysis of horizontal grounding conductor ... within
    two-layer soil", Tables 2 and 3 (exact Sommerfeld model).
  Grcev (2009), IEEE Trans. EMC 51(3), Eq. 18, 20, 25 and Table I.
  Fagan and Lee (1970), IEEE Trans. IGA-6(4), Table VII.
  Wiener (1970), IEEE Trans. IGA-6(3): measured footing electrodes.
"""
import math
import unittest

import numpy as np

from earthsys import api, bem, hf, layered


def wire(L, d=0.75, r=0.005):
    w = hf.Wires()
    w.add((0, 0, d), (L, 0, d), r)
    return w


def zsweep(soil, L, freqs):
    w = wire(L)
    w.discretise(hf.default_seg_len(soil, max(freqs), L), z_cuts=soil.depths)
    m = hf.Model(w, soil)
    return m, np.abs([m.solve(f, 0)[0] for f in freqs])


class TestImages(unittest.TestCase):
    def test_complex_tracer_matches_dc_series(self):
        e = layered.LayeredEarth([100, 1000, 30], [1.0, 3.0])
        for src in range(3):
            ref = layered.image_series(e, src + 1, tol=1e-9)
            out = hf.trace_images(e.depths, 1 / np.array(e.rho), 1.0, src, tol=1e-9)
            for lf in range(3):
                s, h, a = ref[lf + 1]
                s2, h2, a2 = out[lf]
                z, zp, r = [0.5, 2.0, 6.0][lf], [0.7, 2.5, 5.0][src], 2.0
                f1 = np.sum(a / np.sqrt(r * r + (z - s * zp - h) ** 2))
                f2 = np.sum(a2 / np.sqrt(r * r + (z - s2 * zp - h2) ** 2))
                self.assertAlmostEqual(f1, f2.real, delta=1e-8 * abs(f1))


class TestLayeredLightning(unittest.TestCase):
    F10 = [1e4, 1e5, 1e6, 1e7]
    REF10 = {"1a": ([100, 1000], [1.0], [35.1, 34.2, 35.5, 58.1]),
             "1b": ([100, 10], [1.0], [8.3, 8.9, 22.9, 57.1]),
             "2a": ([1000, 100], [0.5], [15.6, 16.1, 30.6, 63.8]),
             "2b": ([10, 100], [0.5], [10.8, 10.9, 23.0, 55.0])}
    HOM10 = [14.3, 14.6, 28.6, 59.6]

    def test_uniform_limit(self):
        _, z1 = zsweep(hf.Soil(100, 10), 10, self.F10)
        _, z2 = zsweep(hf.LayeredSoil([100, 100], [1.0], 10), 10, self.F10)
        np.testing.assert_allclose(z2, z1, rtol=3e-3)

    def test_arnautovski_toseva_2007_table2(self):
        # 10 m end-fed wire, r = 5 mm, 0.75 m deep, ε_r = 10.  Below 1 MHz the
        # values must agree; at 10 MHz the layered result, divided by the
        # uniform one, must agree (the uniform model itself is 6.6 % above
        # theirs there, the offset documented in §13.11).
        _, zh = zsweep(hf.Soil(100, 10), 10, self.F10)
        for key, (rho, h, ref) in self.REF10.items():
            _, z = zsweep(hf.make_soil(rho, h, 10.0), 10, self.F10)
            err = z / np.array(ref) - 1
            self.assertLess(np.max(np.abs(err[:2])), 0.015, key)
            self.assertLess(abs(err[2]), 0.04, key)
            rel = (z[3] / zh[3]) / (ref[3] / self.HOM10[3]) - 1
            self.assertLess(abs(rel), 0.03, key)

    def test_arnautovski_toseva_2007_table3(self):
        F = [1e3, 1e4, 1e5, 1e6]
        for rho, h, ref in (([100, 1000], [1.0], [13.9, 14.1, 21.8, 40.2]),
                            ([100, 10], [1.0], [1.8, 2.6, 8.3, 22.9])):
            _, z = zsweep(hf.make_soil(rho, h, 10.0), 50, F)
            err = np.abs(z / np.array(ref) - 1)
            self.assertLess(err.max(), 0.05, (rho, z))

    def test_dc_matches_bem_across_interfaces(self):
        rod = [dict(kind="rod", x=0, y=0, top_depth=0.0, length=6.0, radius=0.008)]
        grid = [dict(kind="grid", Lx=10, Ly=10, D=5, depth=0.5, radius=0.005),
                dict(kind="rod", x=0, y=0, top_depth=0.5, length=5, radius=0.008)]
        for rho, h, items in (([100, 1000], [2.0], rod), ([1000, 100], [3.0], rod),
                              ([50, 500, 20], [1.0, 3.0], grid)):
            soil = hf.make_soil(rho, h, 10.0)
            w = hf.Wires.from_items(items)
            w.discretise(0.6, z_cuts=soil.depths)
            R = hf.Model(w, soil).solve(0.0, 0)[0].real
            spec = dict(rho1=rho[0], items=items, IG=1.0, rho2=rho[1], h_layer=h[0])
            if len(rho) > 2:
                spec.update(rho3=rho[2], h_layer2=h[1])
            net = bem.build_network(spec)
            net.discretise(0.6)
            Rb = net.solve()["Rg"]
            self.assertAlmostEqual(R / Rb, 1.0, delta=5e-3, msg=str(rho))


class TestIonisation(unittest.TestCase):
    def test_ig(self):
        self.assertAlmostEqual(hf.ionisation_current(300, 100, 11), 39.46, places=1)

    def test_formula_25(self):
        r = hf.impulse_coefficient_formula(100, 10, 8.4, 30, 11, 300)
        self.assertAlmostEqual(r["A"], 1.0)
        self.assertAlmostEqual(r["A_ion"], 0.754, places=2)      # Table I: 0.75

    def test_grcev_2009_table1(self):
        # 10 m vertical rod in 100 Ω·m with R ≈ 11 Ω, E0 = 300 kV/m:
        # Z = 8.3 Ω (first stroke), 13.4 Ω (subsequent stroke)
        w = hf.Wires()
        w.add((0, 0, 0), (0, 0, 10), 0.0125)
        r = hf.harmonic_impedance(wires=w, soil=hf.Soil(100, 10), feed=(0, 0, 0),
                                  f_min=100, f_max=1e7, n_f=40)
        self.assertAlmostEqual(r["R"], 11.0, delta=0.3)
        ion = dict(E0=300, rho=100)
        t1 = hf.time_response(r["f"], r["Z"], r["R"], "first_heidler", ionisation=ion)
        t2 = hf.time_response(r["f"], r["Z"], r["R"], "subsequent_heidler", ionisation=ion)
        self.assertAlmostEqual(t1["Z_impulse_ion"] / 8.3, 1.0, delta=0.03)
        self.assertAlmostEqual(t2["Z_impulse_ion"] / 13.4, 1.0, delta=0.06)
        self.assertLess(t1["Z_impulse_ion"], t1["Z_impulse"])
        # ionisation acts on the resistive part only: the inductive spike of
        # the subsequent stroke is hardly reduced
        self.assertGreater(t2["Z_impulse_ion"] / t2["Z_impulse"], 0.9)


class TestConcrete(unittest.TestCase):
    L, R0, R1 = 3.048, 0.009525, 0.2032     # 10 ft, 3/4 in rod, 16 in concrete

    def R(self, rho_c, rho_s, seg=0.5):
        it = dict(kind="foundation", shape="pier", x=0, y=0, top_depth=0.0, length=self.L,
                  diameter=2 * self.R1, bars=1, bar_diameter=2 * self.R0, rho_c=rho_c)
        net = bem.build_network(dict(rho1=rho_s, items=[it], IG=1.0))
        net.discretise(seg)
        return net.solve()["Rg"]

    def test_fagan_lee_table_vii(self):
        table = {(30, 5): 5.46, (30, 100): 20.85, (30, 500): 85.7,
                 (50, 20): 11.0, (50, 500): 88.75, (80, 50): 20.5, (80, 500): 93.4}
        for (rc, rs), ref in table.items():
            self.assertAlmostEqual(self.R(rc, rs) / ref, 1.0, delta=0.035, msg=(rc, rs))

    def test_monotonic_and_stable(self):
        a = [self.R(rc, 500) for rc in (30, 50, 80)]
        self.assertTrue(a[0] < a[1] < a[2])
        for seg in (0.3, 1.0):
            self.assertAlmostEqual(self.R(50, 500, seg) / self.R(50, 500), 1.0, delta=0.02)

    def test_concrete_helps_in_resistive_soil(self):
        bare = bem.build_network(dict(rho1=500, IG=1.0, items=[dict(
            kind="rod", x=0, y=0, top_depth=0, length=self.L, radius=self.R0)]))
        bare.discretise(0.5)
        self.assertLess(self.R(50, 500), 0.6 * bare.solve()["Rg"])
        bare = bem.build_network(dict(rho1=5, IG=1.0, items=[dict(
            kind="rod", x=0, y=0, top_depth=0, length=self.L, radius=self.R0)]))
        bare.discretise(0.5)
        self.assertGreater(self.R(50, 5), bare.solve()["Rg"])

    def test_wiener_footing_in_measured_range(self):
        # 20 ft x 2 ft x 1 ft footing, No. 4 copper, soil 970-5000 Ω·cm:
        # measured 6-13 Ω over 14 months
        for rs in (9.7, 30, 50):
            it = dict(kind="foundation", shape="strip", x0=0, y0=0, x1=6.096, y1=0,
                      depth=0.3, width=0.61, height=0.305, bars=1, bar_diameter=0.0052,
                      rho_c=50)
            net = bem.build_network(dict(rho1=rs, items=[it], IG=1.0))
            net.discretise(0.5)
            self.assertTrue(6.0 <= net.solve()["Rg"] <= 13.5)

    def test_geometry(self):
        g = bem.foundation_geometry(dict(shape="pier", diameter=0.4, bars=1,
                                         bar_diameter=0.02, rho_c=40))
        self.assertAlmostEqual(g["rc"], 0.2)
        self.assertAlmostEqual(g["shell_ohm_m"], 40 * math.log(20) / (2 * math.pi))
        g = bem.foundation_geometry(dict(shape="strip", width=0.6, height=0.6, bars=4,
                                         bar_diameter=0.016))
        self.assertAlmostEqual(g["rc"], 0.354, places=3)
        with self.assertRaises(ValueError):
            bem.foundation_geometry(dict(shape="pier", diameter=0.1, bars=8,
                                         bar_diameter=0.04, cover=0.0))
        with self.assertRaises(ValueError):
            bem.foundation_geometry(dict(shape="pier", diameter=0.4, rho_c=0))

    def test_lightning_low_frequency_matches_bem(self):
        it = dict(kind="foundation", shape="pier", x=0, y=0, top_depth=0.0, length=3.0,
                  diameter=0.4, bars=4, bar_diameter=0.016, rho_c=50)
        net = bem.build_network(dict(rho1=100, items=[it], IG=1.0))
        net.discretise(0.5)
        Rb = net.solve()["Rg"]
        r = hf.harmonic_impedance(items=[it], soil=hf.Soil(100, 10), feed=(0, 0, 0),
                                  f_min=1e3, f_max=1e6, n_f=3)
        self.assertAlmostEqual(r["R"] / Rb, 1.0, delta=0.02)


class TestApi(unittest.TestCase):
    def test_api_hf_layers_and_ionisation(self):
        p = dict(items=[dict(kind="rod", x=0, y=0, top_depth=0, length=3, radius=0.008)],
                 rho0=300, eps_r=10, soil_model="constant", f_max=2e6, n_f=12,
                 layers=dict(rho=[50], h=[1.5]), E0=400,
                 waveforms=["first_heidler", "subsequent_heidler"])
        d = api.api_hf(p)
        self.assertEqual(d["layers"], 2)
        self.assertIn("ionisation", d)
        x = d["responses"]["first_heidler"]
        self.assertLess(x["Z_impulse_ion"], x["Z_impulse"])
        self.assertTrue(any("Ionisation" in n for n in d["notes"]))
        with self.assertRaises(ValueError):
            api.api_hf(dict(p, E0=10))
        with self.assertRaises(ValueError):
            api.api_hf(dict(p, layers=dict(rho=[50], h=[])))

    def test_api_bem_foundation(self):
        p = dict(rho1=200, IG=1000, segment_length=1.0, nx=21, ny=21,
                 items=[dict(kind="foundation", shape="strip", x0=0, y0=0, x1=10, y1=0,
                             depth=0.8, width=0.6, height=0.4, bars=4,
                             bar_diameter=0.016, rho_c=50)])
        d = api.api_bem(p)
        self.assertGreater(d["Rg"], 0)


if __name__ == "__main__":
    unittest.main()
