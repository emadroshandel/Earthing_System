"""1.5.0: frequency response of earth electrodes under lightning (earthsys.hf).

References, all from outside the code under test:
  * the d.c. solver (earthsys.bem) for the low-frequency limit;
  * Grcev (2009), Figs. 6, 7, 9 and 10: |Z(jω)|/R of 10 m and 30 m vertical
    and horizontal electrodes from his Sommerfeld-integral model (values
    read off the published curves, ±3 %);
  * CIGRE TB 781 Figs. 3.6 and 3.7: a 3 m rod under measured impulse
    currents, with the HEM results under constant and frequency-dependent
    soil (curves extracted from the brochure's vector graphics);
  * CIGRE TB 781 Table 4.1 and Alipio & Visacro (2014) Eq. (3): impulse
    coefficient of short horizontal electrodes.
"""
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np                                     # noqa: E402

from earthsys import api, bem, hf                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def z_over_r(kind, L, rho, f, a_image="sommerfeld"):
    if kind == "v":
        w = hf.Wires().add((0, 0, 0), (0, 0, L), 0.0125)
    else:
        w = hf.Wires().add((0, 0, 0.8), (L, 0, 0.8), 0.007)
    soil = hf.Soil(rho, 10)
    w.discretise(hf.default_seg_len(soil, 1e7, L))
    m = hf.Model(w, soil, a_image=a_image)
    R = m.solve(0.0, 0)[0].real
    return abs(m.solve(f, 0)[0]) / R


class LowFrequencyLimit(unittest.TestCase):
    def test_rod_and_wire_match_the_dc_solver(self):
        for a, b, r in (((0, 0, 0), (0, 0, 10), 0.0125), ((0, 0, 0.8), (10, 0, 0.8), 0.007)):
            w = hf.Wires().add(a, b, r)
            w.discretise(0.5)
            Z = hf.Model(w, hf.Soil(100.0)).solve(0.0, 0)[0]
            n = bem.Network(bem.SoilModel(100.0), 1.0)
            n.add_conductor(a, b, r)
            self.assertAlmostEqual(Z.real / n.solve(0.5)["Rg"], 1.0, delta=0.005)
            self.assertAlmostEqual(Z.imag, 0.0)

    def test_grid_junctions_are_connected(self):
        items = [dict(kind="grid", Lx=20, Ly=20, D=10, depth=0.5, radius=0.005)]
        w = hf.Wires.from_items(items)
        w.discretise(2.0)
        self.assertEqual(len(w.nodes), 3 * 3 + 12 * 4)        # 9 crossings, 4 inner nodes per edge...
        Z = hf.Model(w, hf.Soil(100.0)).solve(0.0, 0)[0].real
        n = bem.build_network(dict(rho1=100.0, items=items))
        self.assertAlmostEqual(Z / n.solve(2.0)["Rg"], 1.0, delta=0.01)

    def test_low_frequency_impedance_is_resistive(self):
        w = hf.Wires().add((0, 0, 0.5), (20, 0, 0.5), 0.007)
        w.discretise(1.0)
        m = hf.Model(w, hf.Soil(300.0))
        R = m.solve(0.0, 0)[0].real
        Z = m.solve(100.0, 0)[0]
        self.assertAlmostEqual(abs(Z) / R, 1.0, delta=1e-3)


class Grcev2009(unittest.TestCase):
    """|Z|/R read from the EMF curves of Grcev (2009)."""
    CASES = [
        ("v", 30, 100, 0.316e6, 3.42),
        ("v", 30, 100, 1.26e6, 5.93),
        ("v", 30, 1000, 1.26e6, 2.28),
        ("h", 30, 10, 0.079e6, 4.67),
        ("h", 30, 100, 2.51e6, 7.06),
        ("h", 10, 100, 1.26e6, 2.23),
        ("h", 10, 1000, 2.51e6, 0.456),
    ]

    def test_harmonic_impedance(self):
        for kind, L, rho, f, ref in self.CASES:
            with self.subTest(kind=kind, L=L, rho=rho, f=f):
                self.assertAlmostEqual(z_over_r(kind, L, rho, f) / ref, 1.0, delta=0.06)

    def test_sommerfeld_quadrature(self):
        """With a reflection coefficient of -1 the Sommerfeld integral is a
        closed-form image: -e^{-γR'}/R'.  This checks the λ quadrature the
        corrections use, oscillating Bessel function and all."""
        from earthsys.layered import j0
        f, rho = 1e5, 10.0
        om = 2 * math.pi * f
        k1 = hf.Soil(rho, 10).kappa(f)
        g1 = complex(np.sqrt(1j * om * hf.MU0 * k1))
        k0 = om * math.sqrt(hf.MU0 * hf.EPS0)
        lam, wl = hf.Model._lambda_rule(k0, g1, 30.0, 1.6)
        u1 = np.sqrt(lam * lam + g1 * g1)
        for r in (0.5, 5.0, 15.0, 30.0):
            v = -np.sum(np.exp(-u1 * 1.6) * j0(lam * r) * lam / u1 * wl)
            R = math.hypot(r, 1.6)
            ex = -np.exp(-g1 * R) / R
            self.assertLess(abs(v - ex) / abs(ex), 1e-5)


class TB781Rod(unittest.TestCase):
    """3 m rod, 8.65 mm radius, under the measured currents of TB 781."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "data_tb781_fig36_37.json"), encoding="utf-8") as fh:
            cls.d = json.load(fh)

    def _peak(self, rho, model, panel):
        r = hf.harmonic_impedance(wires=hf.Wires().add((0, 0, 0), (0, 0, 3), 0.00865),
                                  soil=hf.Soil(rho, 10, model=model), feed=(0, 0, 0),
                                  f_min=100, f_max=2e7, n_f=50)
        D = self.d[panel]
        t = np.arange(0, D["t"][-1], 0.002)
        i = np.interp(t, D["t"], D["i_A"]) / 1000.0
        return hf.time_response(r["f"], r["Z"], r["R"], i_t=i, t_us=t)["V_peak"] * 1000

    def test_against_hem_and_measurement(self):
        for rho, panel in ((2000, "36a"), (2000, "36b"), (410, "37a")):
            D = self.d[panel]
            with self.subTest(panel=panel):
                vc = self._peak(rho, "constant", panel)
                va = self._peak(rho, "alipio_visacro", panel)
                self.assertAlmostEqual(vc / max(D["v_rho0"]), 1.0, delta=0.05)
                self.assertAlmostEqual(va / max(D["v_visacro_alipio"]), 1.0, delta=0.05)
                self.assertAlmostEqual(va / max(D["v_measured"]), 1.0, delta=0.12)


class ImpulseCoefficient(unittest.TestCase):
    """Short horizontal electrode (5 m, 7 mm, 0.5 m deep), frequency-
    dependent soil: CIGRE TB 781 Table 4.1."""
    TABLE = {300: (0.95, 0.84), 2000: (0.82, 0.60)}

    def test_table_4_1(self):
        for rho, (ic1, ic2) in self.TABLE.items():
            w = hf.Wires().add((0, 0, 0.5), (5, 0, 0.5), 0.007)
            r = hf.harmonic_impedance(wires=w, soil=hf.Soil(rho, 10, "alipio_visacro"),
                                      feed=(0, 0, 0.5), f_max=1e7, n_f=40)
            a = hf.time_response(r["f"], r["Z"], r["R"], "first_tb781")["IC"]
            b = hf.time_response(r["f"], r["Z"], r["R"], "subsequent_tb781")["IC"]
            with self.subTest(rho=rho):
                self.assertAlmostEqual(a, ic1, delta=0.03)
                self.assertAlmostEqual(b, ic2, delta=0.03)
                self.assertAlmostEqual(a, hf.alipio_ic(rho, 5, "first")["IC0"], delta=0.04)
                self.assertAlmostEqual(b, hf.alipio_ic(rho, 5, "subsequent")["IC0"], delta=0.04)


class Waveforms(unittest.TestCase):
    def test_heidler_subsequent_matches_grcev(self):
        t = np.linspace(0, 20, 200001)
        i = hf.waveform("subsequent_heidler", t)
        k = int(np.argmax(i))
        self.assertAlmostEqual(i[k], 12.0, delta=0.1)
        self.assertAlmostEqual(t[k], 0.8, delta=0.05)
        self.assertAlmostEqual(np.gradient(i, t).max(), 40.0, delta=1.0)

    def test_tb781_peaks(self):
        t = np.linspace(0, 100, 100001)
        self.assertAlmostEqual(hf.waveform("first_tb781", t).max(), 31.0, delta=0.2)
        self.assertAlmostEqual(hf.waveform("subsequent_tb781", t).max(), 12.0, delta=0.1)
        self.assertAlmostEqual(hf.waveform("first_tb781", t, 20.0).max(), 20.0, delta=1e-9)

    def test_time_response_of_a_resistance(self):
        f = np.geomspace(100, 1e7, 30)
        tr = hf.time_response(f, np.full(30, 10.0 + 0j), 10.0, "first_tb781")
        self.assertAlmostEqual(tr["IC"], 1.0, delta=1e-9)


class API(unittest.TestCase):
    def test_api_hf(self):
        d = api.api_hf(dict(items=[dict(kind="rod", x=0, y=0, top_depth=0, length=3,
                                        radius=0.00865)], rho0=500,
                            soil_model="alipio_visacro", f_max=5e6, n_f=25))
        self.assertIn("narrative", d)
        self.assertEqual(set(d["responses"]), {"first_tb781", "subsequent_tb781"})
        self.assertLess(d["responses"]["subsequent_tb781"]["IC"], 1.0)
        with self.assertRaises(ValueError):
            api.api_hf(dict(items=[dict(kind="fence", x0=0, y0=0, Lx=5, Ly=5)], rho0=100))
        with self.assertRaises(ValueError):
            api.api_hf(dict(items=[dict(kind="rod", x=0, y=0, length=3)], rho0=100, f_max=1e9))


if __name__ == "__main__":
    unittest.main()
