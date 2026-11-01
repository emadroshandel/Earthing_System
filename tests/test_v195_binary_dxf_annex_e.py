"""1.9.5: binary DXF import, and damage to the surroundings in the
IEC 62305-2:2024 risk assessment (Annex E)."""
import base64
import json
import os
import struct
import unittest

from earthsys import dxfimport as dx
from earthsys import risk
from earthsys.api import dispatch

HERE = os.path.dirname(os.path.abspath(__file__))
MAP = {"EARTH_GRID": "conductor", "RODS": "rod", "FENCE": "fence", "زمین": "conductor"}


def _read(name, mode="rb"):
    with open(os.path.join(HERE, name), mode) as f:
        return f.read()


def _bin_writer(pairs, wide=True):
    """A binary DXF written from (code, value) pairs by the DXF reference."""
    out = bytearray(dx.BINARY_SENTINEL)
    for code, v in pairs:
        if wide:
            out += struct.pack("<H", code)
        elif code > 254:
            out += b"\xff" + struct.pack("<H", code)
        else:
            out.append(code)
        if 10 <= code <= 59:
            out += struct.pack("<d", v)
        elif 60 <= code <= 79:
            out += struct.pack("<h", v)
        elif 90 <= code <= 99:
            out += struct.pack("<i", v)
        elif 310 <= code <= 319:
            out += bytes([len(v)]) + v
        else:
            out += str(v).encode() + b"\x00"
    return bytes(out)


SIMPLE = [(0, "SECTION"), (2, "HEADER"), (9, "$ACADVER"), (1, "AC1032"), (9, "$INSUNITS"),
          (70, 6), (0, "ENDSEC"), (0, "SECTION"), (2, "ENTITIES"),
          (0, "LINE"), (8, "GRID"), (10, 0.1), (20, 1.0 / 3.0), (30, 0.0), (11, 20.0), (21, 7.25),
          (31, 0.0), (0, "LWPOLYLINE"), (8, "GRID"), (90, 3), (70, 0), (10, 0.0), (20, 0.0),
          (10, 5.0), (20, 0.0), (42, 0.5), (10, 5.0), (20, 5.0),
          (0, "POINT"), (8, "RODS"), (10, 2.0), (20, 3.0), (30, 0.0),
          (0, "CIRCLE"), (8, "RODS"), (310, b"\x01\x02\x03"), (10, 4.0), (20, 4.0), (40, 0.01),
          (0, "ENDSEC"), (0, "EOF")]


def _ascii(pairs):
    return "".join(f"{c}\n{v!r}\n" if isinstance(v, float) else f"{c}\n{v}\n"
                   for c, v in pairs if not isinstance(v, bytes))


class TestBinaryDXF(unittest.TestCase):

    def test_files_written_by_another_program(self):
        # R12 (one-byte group codes), R2000 (code page, names escaped as
        # \U+XXXX) and R2018 (two-byte codes, UTF-8), written by ezdxf both
        # ways: the binary drawing gives exactly what the ASCII one gives
        for ver in ("R12", "R2000", "R2018"):
            b = _read(f"data_dxf_{ver}_binary.dxf")
            t = _read(f"data_dxf_{ver}_ascii.dxf").decode("utf-8")
            self.assertEqual(dx.parse(b), dx.parse(t))
            ib, it = dx.inspect(b), dx.inspect(t)
            self.assertEqual(ib, it)
            self.assertIn("زمین", ib["layers"])
            a = dx.to_items(t, MAP, scale=0.001)
            c = dx.to_items(b, MAP, scale=0.001)
            self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))
            self.assertEqual(c["counts"]["rods"], 5)

    def test_coordinates_are_exact(self):
        for wide in (True, False):
            d = dx.parse(_bin_writer(SIMPLE, wide))
            self.assertEqual(d, dx.parse(_ascii(SIMPLE)))
            line = d["entities"][0]
            self.assertEqual(line[20], 1.0 / 3.0)            # bit for bit
            self.assertEqual(d["insunits"], 6)
            self.assertEqual(len(d["entities"]), 4)

    def test_damaged_files_and_dwg(self):
        b = _bin_writer(SIMPLE)
        with self.assertRaises(ValueError):
            dx.parse(b[:len(b) // 2 + 3])
        with self.assertRaises(ValueError) as e:
            dx.parse(b"AC1032\x00\x00\x00\x00junk")
        self.assertIn("DWG", str(e.exception))

    def test_api_takes_the_file_as_base64(self):
        b = _read("data_dxf_R2018_binary.dxf")
        d = dispatch("/api/dxf/inspect", dict(data_b64=base64.b64encode(b).decode()))
        self.assertEqual(d["insunits"], 4)
        i = dispatch("/api/dxf/import", dict(data_b64=base64.b64encode(b).decode(), mapping=MAP))
        self.assertEqual(i["counts"]["rods"], 5)
        with self.assertRaises(ValueError):
            dispatch("/api/dxf/inspect", dict(data_b64="not base64!"))


# --------------------------------------------------------------- Annex E
BASE = dict(NG=4, k=2, L=40, W=20, H=15, location="isolated", environment="rural",
            lines=[dict(name="Power", kind="power", sections=[dict(length=1000, install="aerial",
                                                                   type="lv")],
                        shielding="aerial_unshielded", Uw=2.5),
                   dict(name="Telecom", kind="telecom", sections=[dict(length=800,
                                                                       install="buried",
                                                                       type="telecom")],
                        shielding="buried_unshielded", Uw=1.5)])
ZONE = dict(name="Plant", tz=3000, te=8760, fire_risk="explosion_2_22", loss="very_high",
            systems=[dict(line="Power", ks3="same_conduit_01"),
                     dict(line="Telecom", ks3="different_routing")])


class TestAnnexE(unittest.TestCase):

    def test_table_e1_mirrors_table_3(self):
        # with the surroundings' losses and presence set to the zone's own,
        # every component of Table E.1 equals its Table 3 counterpart
        r0 = risk.assess(dict(BASE, zones=[ZONE]))
        z0 = r0["zones"][0]
        L = z0["losses"]
        sur = dict(scenario="custom", internal=True, PPE=z0["Pp"], LF1E=L["LF1"],
                   LO1E=L["LO1"], LF2E=L["LF2"], LO2E=L["LO2"])
        z = risk.assess(dict(BASE, zones=[dict(ZONE, surroundings=sur)]))["zones"][0]
        c = z["components"]
        n = 0
        for k in ("B1", "C1", "M1", "V1", "W1", "Z1", "B2", "C2", "M2", "V2", "W2", "Z2"):
            self.assertGreater(c["R" + k], 0)
            self.assertAlmostEqual(c["R" + k + "E"], c["R" + k], delta=1e-15 * c["R" + k])
            n += 1
        self.assertEqual(n, 12)
        self.assertAlmostEqual(z["R"], z0["R"] + z["RE"], delta=1e-14)
        self.assertAlmostEqual(z["F"], z0["F"], delta=1e-15)          # F is untouched

    def test_same_as_adding_le_to_the_fire_losses(self):
        # (C.1), (C.2): L_BT = L_B + L_E.  Without internal-system damage and
        # with t_zE = t_z, Annex E gives the same risk
        LE = 0.3
        z0 = risk.assess(dict(BASE, zones=[ZONE]))["zones"][0]
        L = z0["losses"]
        a = risk.assess(dict(BASE, zones=[dict(ZONE, LF1=L["LF1"] + LE, LF2=L["LF2"] + LE)]))
        b = risk.assess(dict(BASE, zones=[dict(ZONE, surroundings=dict(
            scenario="custom", PPE=z0["Pp"], LF1E=LE, LF2E=LE))]))
        self.assertAlmostEqual(a["zones"][0]["R"], b["zones"][0]["R"],
                               delta=1e-13 * a["zones"][0]["R"])

    def test_table_values(self):
        s = risk.surroundings_losses
        self.assertEqual(s(dict(scenario="toxic")), dict(
            LF1E=1.0, LO1E=0.0, LF2E=0.5, LO2E=0.0, PPE=1.0, scenario="toxic",
            spreading=True, internal=False))
        x = s(dict(scenario="water", spreading=False, internal=True, area="railways"))
        self.assertEqual((x["LF1E"], x["LO1E"], x["LF2E"], x["LO2E"], x["PPE"]),
                         (0.25, 0.025, 0.5, 0.05, 0.25))
        x = s(dict(scenario="radioactive", internal=True))
        self.assertEqual((x["LF1E"], x["LO1E"], x["LF2E"], x["LO2E"]), (5.0, 0.5, 1.0, 0.1))
        self.assertIsNone(s(None))
        with self.assertRaises(ValueError):
            s(dict(scenario="flood"))
        with self.assertRaises(ValueError):
            s(dict(scenario="custom", PPE=1.5))

    def test_hand_calculation(self):
        r = risk.assess(dict(BASE, zones=[dict(ZONE, surroundings=dict(
            scenario="explosion", area="residences"))]))
        z = r["zones"][0]
        c = z["components"]
        self.assertAlmostEqual(c["RB1E"], r["ND"] * z["PB"] * 1.0 * 0.5, delta=1e-18)
        self.assertAlmostEqual(c["RB2E"], r["ND"] * z["PB"] * 0.5, delta=1e-18)
        self.assertEqual(c["RC1E"], 0.0)                 # no internal-system scenario
        self.assertAlmostEqual(z["RE"], sum(v for k, v in c.items() if k.endswith("E")))

    def test_selection_and_api(self):
        p = dict(BASE, zones=[dict(ZONE, surroundings=dict(scenario="toxic", internal=True))])
        d = dispatch("/api/risk", p)
        q = dispatch("/api/risk", dict(BASE, zones=[ZONE]))
        self.assertGreater(d["unprotected"]["R"], q["unprotected"]["R"])
        if d.get("choice"):
            self.assertLessEqual(d["protected"]["R"], 1e-5)
        self.assertGreater(d["protected"]["zones"][0]["RE"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
