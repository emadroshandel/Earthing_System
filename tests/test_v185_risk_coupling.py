"""1.8.5: IEC 62305-2:2024 risk management (checked against the worked
examples of its Annex F), the 2024 SPD rules of IEC 62305-4, and the fault
current and coupling extensions — several lines and measured footing
resistances in the shield-wire ladder, induction from a faulted line of any
shape, and earth-fault current returning in cable sheaths."""
import math
import unittest

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None

from earthsys import faultcurrent, risk, spd
from earthsys.api import dispatch

E5 = 1e-5


def _house():
    return dict(NSG=8, k=2, L=15, W=20, H=6, location="isolated", material="masonry",
                environment="rural",
                lines=[dict(name="P", install="aerial", type="lv", length=1000,
                            shielding="aerial_unshielded", Uw=2.5),
                       dict(name="T", install="aerial", type="telecom", length=800,
                            shielding="aerial_unshielded", Uw=1.5)],
                zones=[dict(name="Z2", tz=4380, surface="linoleum", fire_risk="low", loss="low",
                            systems=[dict(line="P", ks3="same_conduit_01"),
                                     dict(line="T", ks3="different_routing")])])


def _office():
    inside = lambda **kw: dict(kw, systems=[dict(line="P", ks3="same_conduit_01"),
                                            dict(line=None, ks3="different_routing", Uw=1.5, CLD=1)])
    return dict(
        NSG=4, k=2, L=20, W=40, H=25, material="reinforced", environment="suburban",
        lines=[dict(name="P", shielding="buried_unshielded", Uw=2.5,
                    sections=[dict(length=1000, install="buried", type="hv"),
                              dict(length=100, install="buried", type="lv")]),
               dict(name="T", fibre=True, Uw=1.5)],
        zones=[dict(name="Z1", tz=175, surface="marble", fire_risk="none", loss="low"),
               dict(name="Z2", tz=18, surface="asphalt", fire_risk="none", loss="low", exposed=True),
               inside(name="Z3", tz=440, surface="linoleum", fire_risk="high",
                      fire_provisions="automatic", loss="normal", FT=0.05),
               inside(name="Z4", tz=2630, surface="linoleum", fire_risk="low",
                      fire_provisions="manual", loss="normal", FT=0.05),
               inside(name="Z5", tz=2200, surface="linoleum", fire_risk="low",
                      fire_provisions="automatic", loss="high", life_systems=False, FT=0.05)])


def _hospital():
    P = lambda ks3: [dict(line="P", ks3=ks3)]
    return dict(
        NSG=8, k=2, L=50, W=150, H=10, material="reinforced", environment="suburban",
        lines=[dict(name="P", shielding="buried_unshielded", Uw=2.5,
                    sections=[dict(length=1000, install="buried", type="hv"),
                              dict(length=50, install="buried", type="lv")])],
        zones=[dict(name="Z1", tz=175, surface="concrete", fire_risk="none", loss="low"),
               dict(name="Z2", tz=90, surface="asphalt", fire_risk="none", loss="low", exposed=True),
               dict(name="Z3", tz=8760, surface="linoleum", fire_risk="ordinary",
                    fire_provisions="automatic", loss="high", life_systems=True, FT=0.05,
                    systems=P("same_conduit_01")),
               dict(name="Z4", tz=3100, surface="linoleum", fire_risk="low",
                    fire_provisions="automatic", loss="very_high", FT=0.01, systems=P("same_cable")),
               dict(name="Z5", tz=8760, surface="linoleum", fire_risk="low",
                    fire_provisions="automatic", loss="very_high", FT=0.01, systems=P("same_cable"))])


class TestAnnexF(unittest.TestCase):
    """The printed results of IEC 62305-2:2024 Annex F (values × 10⁻⁵ per year)."""

    def assertNear(self, a, b, rel=0.005, absol=0.0015):
        self.assertTrue(abs(a - b) <= max(rel * abs(b), absol), f"{a} vs {b}")

    def test_house_events(self):
        r = risk.assess(_house())
        self.assertNear(r["ND"], 2.06e-2)
        (p, t) = r["lines"]
        self.assertNear(p["NL"], 0.32)
        self.assertNear(p["NI"], 3.07)
        self.assertNear(t["NL"], 0.256)
        self.assertNear(t["NI"], 6.17)
        self.assertNear(r["zones"][0]["NM"], 0.75)

    def test_house_risk_table_f8_and_f9(self):
        z = risk.assess(_house())["zones"][0]
        c = z["components"]
        self.assertNear((c["RB1"] + c["RB2"]) / E5, 0.062)
        self.assertNear(c["RU"] / E5, 0.003)
        self.assertNear((c["RV1"] + c["RV2"]) / E5, 1.728)
        self.assertNear(z["R"] / E5, 1.793)
        # SPDs of LPL IV at the entrance of both lines (P_EB = 0.05)
        zp = risk.assess(_house(), eb="III-IV")["zones"][0]
        self.assertNear((zp["components"]["RV1"] + zp["components"]["RV2"]) / E5, 0.086)
        self.assertNear(zp["R"] / E5, 0.149)

    def test_office_tables_f21_f22(self):
        r = risk.assess(_office())
        self.assertNear(r["ND"], 0.11, rel=0.01)
        R = [z["R"] / E5 for z in r["zones"]]
        for got, want in zip(R, [0.002, 2.259, 6.526, 0.202, 0.156]):
            self.assertNear(got, want)
        z3 = r["zones"][2]
        self.assertNear(z3["F_components"]["FC"], 0.11, rel=0.01)
        self.assertNear(z3["F_components"]["FM"], 0.398)
        self.assertNear(z3["F_components"]["FW"], 0.007, absol=2e-4)
        self.assertNear(z3["F_components"]["FZ"], 0.0692)
        self.assertNear(z3["F"], 0.584)
        self.assertFalse(z3["ok_F"])

    def test_office_protected_tables_f23_f24(self):
        r = risk.assess(_office(), lps="II", spd="II")
        R = [z["R"] / E5 for z in r["zones"]]
        for got, want in zip(R, [0.0, 0.113, 0.592, 0.018, 0.014]):
            self.assertNear(got, want)
        for z in r["zones"][2:]:
            self.assertNear(z["F"], 0.014, absol=6e-4)
        self.assertTrue(r["ok"])

    def test_hospital_table_f35_f36(self):
        r = risk.assess(_hospital())
        R = [z["R"] / E5 for z in r["zones"]]
        for got, want in zip(R, [0.036, 18.357, 36.528, 108.834, 306.787]):
            self.assertNear(got, want)
        c5 = r["zones"][4]["components"]
        self.assertNear(c5["RC1"] / E5, 178.619)
        self.assertNear(c5["RZ1"] / E5, 115.308)
        self.assertNear(r["zones"][2]["F"], 0.325)
        self.assertNear(r["zones"][3]["F"], 0.306)


class TestRiskMethod(unittest.TestCase):

    def test_collection_areas_2024(self):
        AD, AM, AL, AI = risk.collection_areas(40, 20, 15, [1000], Uw=2.5)
        self.assertAlmostEqual(AD, 40 * 20 + 2 * 45 * 60 + math.pi * 45 ** 2)
        rm = 350 / 2.5
        self.assertAlmostEqual(AM, 2 * rm * 60 + math.pi * rm ** 2)
        self.assertEqual(AL, [40000.0])
        self.assertAlmostEqual(AI[0], 2 * 2000 / 2.5 ** 1.8 * 1000)

    def test_buried_line_in_high_resistivity_soil(self):
        p = dict(NSG=2, L=10, W=10, H=5,
                 lines=[dict(name="P", sections=[dict(length=500, install="buried", rho=1600)])],
                 zones=[dict(systems=[dict(line="P")])])
        nl = risk.assess(p)["lines"][0]["NL"]
        self.assertAlmostEqual(nl, 2 * 0.6 * math.sqrt(1600) * 500 * 1e-6)

    def test_pld_tables(self):
        self.assertEqual(risk.p_ld("unshielded", 2.5), 1.0)
        self.assertEqual(risk.p_ld("rs_1_5", 2.5), 0.6)
        self.assertEqual(risk.p_ld(0.5, 4.0), 0.04)          # R_S ≤ 1 Ω/km
        self.assertEqual(risk.p_ld("rs_5_20", 3.0), 0.95)    # 3 kV reads the 2.5 kV column

    def test_lps_replaces_ps(self):
        p = _office()
        a = risk.assess(p, lps="II")["zones"][2]
        self.assertAlmostEqual(a["PB"], 1.0 * 0.05 * 0.1 * 0.2)   # P_S = 1 with an LPS

    def test_tws_reduces_touch_and_line_components(self):
        p = _house()
        a = risk.assess(p)["zones"][0]["components"]
        b = risk.assess(dict(p, ptws=0.1))["zones"][0]["components"]
        self.assertAlmostEqual(b["RV1"], 0.1 * a["RV1"])
        self.assertAlmostEqual(b["RB1"], a["RB1"])                # P_B has no P_TWS

    def test_select_office(self):
        s = risk.select(_office())
        self.assertTrue(s["needed"])
        c = s["choice"]
        self.assertIsNotNone(c)
        self.assertTrue(s["protected"]["ok"])
        # the standard's own solution (LPS II, SPDs LPL II) also meets both criteria,
        # so the cheapest found cannot be more expensive
        self.assertLessEqual(c["rank"], 4 + 2)

    def test_single_zone_inputs_of_earlier_versions(self):
        d = dispatch("/api/risk", dict(NG=2, L=40, W=20, H=15, use="hospital", hours=8760))
        self.assertIn("note", d)
        self.assertEqual(d["standard"], "IEC 62305-2:2024")
        self.assertEqual(len(d["unprotected"]["zones"]), 1)
        quiet = risk.select(dict(NG=0.2, L=10, W=10, H=6, fire_risk="low",
                                 lines=[dict(name="P", install="buried", length=200, Uw=2.5)]))
        self.assertFalse(quiet["needed"])

    def test_errors(self):
        with self.assertRaises(ValueError):
            risk.assess(dict(NG=-1))
        with self.assertRaises(ValueError):
            risk.assess(dict(NG=2, zones=[dict(tz=9000)]))
        with self.assertRaises(ValueError):
            risk.assess(dict(NG=2, zones=[dict(systems=[dict(line="nope")])]))
        with self.assertRaises(ValueError):
            risk.assess(dict(NG=2, zones=[dict(surface="lava")]))


class TestSPD2024(unittest.TestCase):

    def test_lead_drop_follows_the_spd_current(self):
        r = spd.coordinate(dict(lpl="I", n_services=1, conductors=4, Uw=2.5, circuit_length=5,
                                stages=[dict(name="T1", type="1", technology="limiting", Up=1.5,
                                             lead=1.0, Iimp=25.0)]))
        st = r["stages"][0]
        self.assertAlmostEqual(st["I_spd"], 25.0)              # 0.5·200/(1·4)
        self.assertAlmostEqual(st["dU"], 2.5)                  # 0.1 kV/(kA·m) × 25 kA × 1 m
        self.assertFalse(r["passed"])

    def test_simplified_tables_c3_c4(self):
        s = spd.simplified_selection("I", 3, "CT2")
        self.assertEqual(s["Iimp_kA"], {"L-N": 25.0, "N-PE": 100.0})
        s = spd.simplified_selection("II", 1, "CT2")
        self.assertEqual(s["Iimp_kA"]["N-PE"], 37.5)
        s = spd.simplified_selection("III", 3, "CT1")
        self.assertEqual(s["Iimp_kA"], {"L-PE": 12.5, "N-PE": 12.5})
        self.assertEqual(s["In_kA"], {"L-PE": 5.0, "N-PE": 5.0})

    def test_reflection_factor_and_critical_systems(self):
        a = spd.coordinate(dict(lpl="I", Uw=2.5, circuit_length=30, Ui=0.5))
        b = spd.coordinate(dict(lpl="I", Uw=2.5, circuit_length=30, Ui=0.5, k_reflection=1.0))
        lim = lambda r: [c for c in r["checks"] if c["name"].startswith("Protection level")][0]["limit"]
        self.assertAlmostEqual(lim(a), 1.0)
        self.assertAlmostEqual(lim(b), 2.0)
        c = spd.coordinate(dict(lpl="I", Uw=2.5, circuit_length=0, critical=True))
        self.assertTrue(any("Critical" in k["name"] and not k["passed"] for k in c["checks"]))


class TestShieldWireLadder(unittest.TestCase):
    base = dict(Un_kV=132, Rg=0.5, line_km=6, span_km=0.3, Rt=10, R_remote=0.5)

    def test_uniform_lists_reproduce_the_scalar_inputs(self):
        a = dispatch("/api/fault/sweep", dict(self.base))
        n = 20
        b = dispatch("/api/fault/sweep", dict(self.base, spans_km=[0.3] * n, Rt_list=[10] * (n - 1)))
        self.assertAlmostEqual(a["worst"]["Ig_kA"], b["worst"]["Ig_kA"], places=9)
        self.assertAlmostEqual(a["station"]["Ig_kA"], b["station"]["Ig_kA"], places=9)

    def test_measured_footings_matter(self):
        n = 20
        good = dispatch("/api/fault/sweep", dict(self.base, Rt_list=[5] * (n - 1)))
        bad = dispatch("/api/fault/sweep", dict(self.base, Rt_list=[5] * 3 + [80] * (n - 4)))
        # poor footings divert less of a station fault into the line...
        self.assertGreater(bad["station"]["Ig_kA"], good["station"]["Ig_kA"])
        # ...and move the governing fault along the line
        self.assertNotEqual(bad["governs"], good["governs"])
        with self.assertRaises(ValueError):
            dispatch("/api/fault/sweep", dict(self.base, Rt_list=[5, 5, 5]))

    def test_other_lines_divert_current(self):
        a = dispatch("/api/fault/sweep", dict(self.base))
        b = dispatch("/api/fault/sweep", dict(self.base, other_lines=["10, 0.3, 10, 0.5", "4, 0.25, 15, 1"]))
        self.assertLess(b["station"]["Ig_kA"], a["station"]["Ig_kA"])
        self.assertEqual(len(b["other_lines"]), 2)
        self.assertGreater(abs(complex(*b["Z_other_total"]) if isinstance(b["Z_other_total"], list)
                               else complex(b["Z_other_total"])), 0)
        with self.assertRaises(ValueError):
            dispatch("/api/fault/sweep", dict(self.base, other_lines=["10, 0.3"]))


class TestCableSheath(unittest.TestCase):

    def test_three_core_matches_s34(self):
        r = faultcurrent.cable_sheath_return(10.0, length_km=3.0, R_A=0.2, R_B=1.0,
                                             r_sheath_km=0.5, r_mean=0.03, formation="three_core")
        zs = complex(*r["zs_km"])
        s34 = faultcurrent.split_factor_cable_s34(3.0, zs, 0.5, 0.2, 1.0)
        self.assertAlmostEqual(r["Sf"], s34["Sf"], places=6)
        rb = faultcurrent.cable_sheath_return(10.0, length_km=3.0, R_A=0.2, R_B=1.0, r_sheath_km=0.5,
                                              r_mean=0.03, formation="three_core", source_beyond=True)
        s34b = faultcurrent.split_factor_cable_s34(3.0, complex(*rb["zs_km"]), 0.5, 0.2, 1.0,
                                                   remote_source=True)
        self.assertAlmostEqual(rb["Sf"], s34b["Sf"], places=6)

    def test_single_point_bonding_returns_nothing_in_the_sheath(self):
        r = faultcurrent.cable_sheath_return(10.0, length_km=1.0, R_A=0.2, R_B=1.0, r_sheath_km=0.5,
                                             r_mean=0.03, bonding="single_point_A")
        self.assertEqual(r["Sf"], 1.0)
        self.assertEqual(r["I_sheath_kA"], 0.0)

    def test_joints_and_endpoint(self):
        d = dispatch("/api/cable/sheath", dict(If_kA=12, length_km=2.4, R_A=0.3, R_B=0.8,
                                                r_sheath_km=0.2, r_mean=0.04, formation="trefoil",
                                                spacing=0.09, joints="0.8, 1.6", R_joint=5))
        self.assertEqual(len(d["joints"]), 2)
        self.assertTrue(0 < d["Sf"] < 1)
        self.assertAlmostEqual(d["Ig_kA"] + 0.0, d["Sf"] * 12, places=6)
        with self.assertRaises(ValueError):
            dispatch("/api/cable/sheath", dict(If_kA=12, length_km=2.4, R_A=0.3, R_B=0.8,
                                                r_sheath_km=0.2, r_mean=0.04, joints="1.0"))


@unittest.skipIf(np is None, "numpy needed")
class TestInductionGeometry(unittest.TestCase):

    def test_parallel_and_crossing(self):
        from earthsys import transfer
        L = 1000.0
        route_at, _ = transfer._polyline([[0, 0], [L, 0]], L)
        f, info = transfer.induced_emf_profile(route_at, L, [[0, 30], [L, 30]], 1000.0, 100.0)
        zm = transfer.mutual_earth_return(100.0, 50.0, 30.0)
        self.assertAlmostEqual(info["emf_total"], abs(zm) * 1000.0 * L, delta=abs(zm) * 1000.0 * L * 0.01)
        f2, info2 = transfer.induced_emf_profile(route_at, L, [[500, -2000], [500, 2000]], 1000.0, 100.0)
        self.assertLess(info2["emf_total"], 1e-6 * info["emf_total"] + 1e-9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
