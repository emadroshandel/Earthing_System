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
Tests for earthsys.standards (new in 1.3.0): the standards registry and the
cross-check calculations taken from BS EN 50522, ENA EG-0, CIGRE TB 781,
EPRI EL-2020, AS/NZS 3835.1 / EREC S34 and IEEE 1100.

    python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import api, ieee80, report, standards as st  # noqa: E402


class Registry(unittest.TestCase):
    def test_ids_unique_and_areas_known(self):
        ids = [s["id"] for s in st.REGISTRY]
        self.assertEqual(len(ids), len(set(ids)))
        for s in st.REGISTRY:
            self.assertIn(s["area"], st.AREAS)
            self.assertIn(s["role"], ("implemented", "cross-check", "reference"))

    def test_every_area_has_an_entry(self):
        for a in st.AREAS:
            self.assertTrue(st.by_area(a), a)

    def test_listed_standards_present(self):
        ids = " ".join(s["id"] for s in st.REGISTRY)
        for key in ("IEEE Std 80-2013", "AS 2067", "EN 50522", "EG-1", "IEEE Std 81",
                    "TS 41-24", "60479", "EG-0", "62305-3", "2760", "2778", "4853",
                    "TB 95", "3000", "7671", "7430", "7000", "TB 781", "TB 839",
                    "EL-2020", "60364-5-548", "1100", "3835.1", "50310", "S34", "TB 347"):
            self.assertIn(key, ids)


class TouchVoltage(unittest.TestCase):
    def test_table_points_reproduced(self):
        for t, u in st.EN50522_UTP:
            self.assertAlmostEqual(st.en50522_touch_limit(t), u, places=6)

    def test_monotone_and_clamped(self):
        ts = [0.01, 0.05, 0.07, 0.15, 0.3, 0.7, 1.5, 3, 7, 10, 30]
        us = [st.en50522_touch_limit(t) for t in ts]
        self.assertTrue(all(a >= b for a, b in zip(us, us[1:])))
        self.assertEqual(us[0], 716.0)
        self.assertEqual(us[-1], 85.0)

    def test_ieee80_bare(self):
        self.assertAlmostEqual(st.ieee80_bare_touch(0.5, 70), 157 / math.sqrt(0.5), places=6)
        self.assertAlmostEqual(st.ieee80_bare_touch(1.0, 50), 116.0, places=6)

    def test_design_carries_cross_check_without_changing_verdict(self):
        g = ieee80.GridGeometry(Lx=70, Ly=70, D=7, h=0.5, d=0.01)
        d = ieee80.design(400, g, 1.908, rho_s=2500, hs=0.102, ts=0.5)
        self.assertAlmostEqual(d["en50522"]["U_Tp"], 220.0, places=6)
        self.assertFalse(any("50522" in c["name"] for c in d["checks"]))
        self.assertIn("EN 50522", d["cross_check"])


class EG0(unittest.TestCase):
    def test_coincidence(self):
        # 1 fault/yr, 500 contacts/yr of 4 s, 0.5 s clearance
        p = st.eg0_coincidence(1, 500, 0.5, 4)
        self.assertAlmostEqual(p, 500 * 4.5 / 31_536_000, places=15)

    def test_bands(self):
        self.assertEqual(st.eg0_risk_band(5e-7), "negligible")
        self.assertEqual(st.eg0_risk_band(1e-5), "ALARP")
        self.assertEqual(st.eg0_risk_band(2e-4), "intolerable")


class SoilFrequency(unittest.TestCase):
    def test_low_frequency_limit(self):
        self.assertAlmostEqual(st.alipio_visacro(1000, 100)["ratio"], 1.0, delta=0.01)

    def test_known_point(self):
        # sigma0 = 1 mS/m: sigma(1 MHz) = 1 + 1.26 = 2.26 mS/m
        self.assertAlmostEqual(st.alipio_visacro(1000, 1e6)["rho"], 1000 / 2.26, places=6)

    def test_more_resistive_soil_drops_more(self):
        self.assertLess(st.alipio_visacro(5000, 1e6)["ratio"],
                        st.alipio_visacro(100, 1e6)["ratio"])


class CouplingAndHVDC(unittest.TestCase):
    def test_carson(self):
        self.assertAlmostEqual(st.carson_depth(100, 50), 931.26, places=1)
        z = st.mutual_impedance_per_km(100, 50)
        self.assertAlmostEqual(z.real, 0.04935, places=5)

    def test_epr_contour_inverts_far_field(self):
        x = st.epr_contour_distance(200, 3000, 430)
        self.assertAlmostEqual(st.far_field_potential(200, 3000, x), 430, places=6)

    def test_hvdc_thermal_round_trip(self):
        V = st.hvdc_max_potential(60, 100, 1.0)
        self.assertAlmostEqual(st.hvdc_temperature_rise(V, 100, 1.0), 60, places=9)

    def test_faraday_iron(self):
        self.assertAlmostEqual(st.faraday_mass_loss(1, 1, "iron"), 9.13, places=2)

    def test_srg(self):
        self.assertAlmostEqual(st.srg_max_aperture(30e6), 0.999, places=3)


class Plumbing(unittest.TestCase):
    def test_api_and_report(self):
        r = api.dispatch("/api/standards", {"t_F": 1, "f_n": 1, "p_n": 100,
                                            "f_d": 1, "t_d": 1, "P_fib": 0.05})
        self.assertAlmostEqual(r["touch"]["U_Tp"], 117.0)
        self.assertIn(r["eg0"]["band"], ("negligible", "ALARP", "intolerable"))
        lt = api.dispatch("/api/lightning", {"rho": 500})
        self.assertLess(lt["soil_frequency"]["ratio"], 1.0)
        html = report.build({"lightning": lt}, "en")
        self.assertIn("Standards and codes of practice", html)
        self.assertIn("IEC 61400-24", html)
        self.assertTrue(api.APP_VERSION.startswith("1.3"))


if __name__ == "__main__":
    unittest.main()
