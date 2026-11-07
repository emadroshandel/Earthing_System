"""1.7.0: construction drawings (module 11).

The drawing set is built from module results; these tests check that every
kind of project produces a complete, well-formed set (PDF, DXF, SVG), that the
quantities are counted from the geometry, that the drafting rules quoted on the
sheets are applied (50 mm² minimum buried copper, rod diameters, IEC 62305-3
down-conductor spacing), and that no lettering runs off a sheet or over the
title panel."""

import base64
import io
import math
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earthsys import api, cad, drawings  # noqa: E402


def call(path, p):
    d = api.dispatch(path, p)
    d["_in"] = p
    return d


def full_results():
    S = {}
    S["conductor"] = call("/api/conductor", dict(I_kA=3.18, tc=0.5, Df=1.026, Ta=40, material="cu_hard",
                                                 joint="exothermic", iec_material="copper", insulation="bare",
                                                 installation="buried", corrosion_protected=False,
                                                 mechanically_protected=False, basis="both"))
    S["grid"] = call("/api/ieee80/design", dict(rho=400, Lx=70, Ly=70, D=7, h=0.5, d=0.01, n_rods=20, Lr=7.5,
                                                d_rod=0.016, IG_kA=1.908, rho_s=2500, hs=0.102, ts=0.5,
                                                body_weight=70, shape="rectangular", rods_on_perimeter=True))
    S["earthpit"] = call("/api/earthpit", dict(electrode="rod", rho=400, D=0.3, backfill="bentonite_4to1",
                                               material="copper_bonded_steel", fill_top=0, season_factor=1.5,
                                               n=4, s=6, housing_class="M", t_fault=1, L=3, d=0.016,
                                               I_fault=2000, target=5))
    S["building"] = call("/api/building", dict(system="TT", U0=230, rho=100,
                                               electrodes=[dict(type="rod", L=3, d=0.016)],
                                               device=dict(kind="rcd", rating_A=0.03), circuit="final"))
    S["lightning"] = call("/api/lightning", dict(lps_class="II", rho=400, area=600, perimeter=100,
                                                 arrangement="B", d=0.01, h=0.5, rod_d=0.016))
    S["airterm"] = call("/api/airterm", dict(lps_class="II", structure=dict(width=30, height=12, depth=20),
                                             roof_depth=20, terminals=[dict(x=-15, y=0, height=5),
                                                                       dict(x=15, y=0, height=5),
                                                                       dict(x=0, y=0, height=5)]))
    S["sysgnd"] = call("/api/system-grounding", dict(V_ll_kV=6.6, frequency=50, cable_km=8,
                                                     C0_uF_per_km=0.25, method="low_resistance",
                                                     I_target_A=400, t_rating_s=10))
    return S


META = dict(owner="Example Owner", designer="Example Consultants", project="Example Project", prefix="T",
            status="IFA")


def draw(**kw):
    """The drawings endpoint without writing to the outputs folder."""
    kw.setdefault("meta", META)
    return api.dispatch("/api/drawings", dict(kw, save=False))


def text_overflows(sheet):
    """Lettering that leaves the trimmed sheet, or crosses from the drawing
    area into the notes / title panel."""
    fr = drawings.Frame(sheet)
    bad = []
    for kind, layer, g in sheet.items:
        if kind != "T":
            continue
        x, y, s, h, anchor, rot, bold = g
        w = cad.text_width(s, h, bold)
        a = math.radians(rot)
        x0 = x - {"start": 0, "middle": w / 2, "end": w}[anchor] * math.cos(a)
        x1 = x0 + w * math.cos(a)
        lo, hi = min(x0, x1), max(x0, x1)
        if lo < -0.1 or hi > sheet.W + 0.1 or y < -0.1 or y > sheet.H + 0.1:
            bad.append(("off sheet", s))
        elif lo < fr.px0 - 1.0 and hi > fr.px0 + 0.6 and fr.fy0 < y < fr.fy1:
            bad.append(("into panel", s))
    return bad


class DrawingSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = full_results()
        cls.r = draw(**dict(results=cls.S, meta=META, options={}))

    def test_sheets_and_files(self):
        nums = [s["number"] for s in self.r["sheets"]]
        self.assertEqual(nums, ["T-000", "T-101", "T-102", "T-201", "T-202", "T-301", "T-302", "T-303",
                                "T-401", "T-501", "T-901"])
        pdf = base64.b64decode(self.r["pdf_b64"])
        self.assertTrue(pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF"))
        self.assertEqual(pdf.count(b"/Type /Page "), len(nums))
        z = zipfile.ZipFile(io.BytesIO(base64.b64decode(self.r["zip_b64"])))
        names = z.namelist()
        for n in nums:
            self.assertIn(f"dxf/{n}.dxf", names)
            self.assertIn(f"svg/{n}.svg", names)
            dxf = z.read(f"dxf/{n}.dxf").decode("ascii")       # R12 must be plain ASCII
            self.assertIn("AC1009", dxf)
            self.assertTrue(dxf.rstrip().endswith("EOF"))
        self.assertIn("bill_of_materials.csv", names)

    def test_conductor_raised_to_50(self):
        # module 3 selects 25 mm² (Table 54.1 value in brackets, shock only); with a
        # lightning protection system the buried electrode needs 50 mm²
        # (BS EN 50522 Table C.1, IEC 60364-5-54 Table 54.1, IEC 62305-3 Table 7)
        self.assertEqual(self.S["conductor"]["selected_mm2"], 25)
        self.assertEqual(self.r["conductor"]["size"], 50)
        ok = [c for c in self.r["checks"] if c["item"].startswith("Buried bare copper electrode")][0]
        self.assertEqual(ok["status"], "OK")
        self.assertIn("lightning", ok["item"])

    def test_electrode_duty(self):
        S = {k: self.S[k] for k in ("conductor", "grid")}
        no_arr = dict(equipment=dict(transformer=1))
        r = draw(**dict(results=S, meta=META, options=no_arr))
        self.assertEqual(r["conductor"]["size"], 25)          # shock protection only
        r = draw(**dict(results=S, meta=META, options=dict(no_arr, electrode_duty="shock_low")))
        self.assertEqual(r["conductor"]["size"], 25)          # 25 calculated by module 3 still governs
        r = draw(**dict(results=S, meta=META))   # default: arresters bonded
        self.assertEqual(r["conductor"]["size"], 50)

    def test_frame_and_lettering(self):
        sh = _sheets(self.S, META)[1]
        hs = {round(g[3], 3) for k, _, g in sh.items if k == "T"}
        allowed = set(cad.TEXT_SERIES) | {round(v * 0.62, 3) for v in cad.TEXT_SERIES}
        self.assertTrue(hs <= allowed, hs - allowed)
        widths = {cad.LAYERS[l][0] for k, l, g in sh.items}
        self.assertTrue(widths <= {0.25, 0.5, 1.0})

    def test_override_and_compression(self):
        r = draw(**dict(results=self.S, meta=META,
                                               options=dict(conductor_mm2=120, joint="compression")))
        self.assertEqual(r["conductor"]["size"], 120)
        self.assertTrue(any("Compression" in b[1] for b in r["bom"]))

    def test_joint_count_from_geometry(self):
        segs = [((0, 0), (0, 2)), ((1, 0), (1, 2)), ((2, 0), (2, 2)),
                ((0, 0), (2, 0)), ((0, 1), (2, 1)), ((0, 2), (2, 2))]
        J = drawings.grid_joints(segs, [])
        self.assertEqual((len(J["X"]), len(J["T"]), len(J["L"])), (1, 4, 4))
        bom = {b[1].split(",")[1].strip() if "," in b[1] else b[1]: b[3] for b in self.r["bom"]}
        # 11 × 11 conductors: 81 crossings, 36 tees, 4 corners
        self.assertEqual(bom.get("cross (X) type"), "81")
        self.assertEqual(bom.get("tee (T) type"), "36")
        self.assertEqual(bom.get("corner / bend"), "4")

    def test_lps_down_conductor_spacing(self):
        chk = [c for c in self.r["checks"] if c["item"] == "Down-conductor spacing"][0]
        self.assertEqual(chk["status"], "OK")
        self.assertIn("10 down-conductors", chk["actual"])      # 100 m perimeter, class II: 10 m

    def test_no_text_overflow(self):
        ctx = drawings.Ctx(dict(results=self.S, meta=META, options={}, version="t"))
        self.assertIsNotNone(ctx)
        for size in ("A3", "A1"):
            for sh in _sheets(self.S, dict(META, size=size)):
                self.assertEqual(text_overflows(sh), [], f"{size} {sh.number}")


def _sheets(S, meta, options=None):
    """Build the sheets and return the Sheet objects (re-runs build internals)."""
    captured = []
    real = cad.to_pdf

    def grab(sheets, **kw):
        captured.extend(sheets)
        return real(sheets, **kw)
    drawings.cad.to_pdf = grab
    try:
        drawings.build(dict(results=S, meta=meta, options=options or {}, version="t"))
    finally:
        drawings.cad.to_pdf = real
    return captured


class Scenarios(unittest.TestCase):
    def test_building_only(self):
        S = dict(building=call("/api/building", dict(system="TN-C-S", U0=230, rho=80,
                                                     electrodes=[dict(type="rod", L=2.4, d=0.0142)],
                                                     device=dict(kind="mcb", rating_A=32, curve="B"))))
        r = draw(**dict(results=S, meta=META))
        nums = [s["number"] for s in r["sheets"]]
        self.assertNotIn("T-101", nums)
        self.assertIn("T-501", nums)
        rod = [c for c in r["checks"] if c["item"] == "Earth rod diameter"][0]
        self.assertEqual(rod["status"], "OK")      # 14.2 mm copper-bonded ≥ 14 mm
        for sh in _sheets(S, META):
            self.assertEqual(text_overflows(sh), [], sh.number)

    def test_thin_rod_fails(self):
        S = dict(earthpit=call("/api/earthpit", dict(electrode="rod", rho=100, D=0.3, L=3, d=0.012,
                                                     material="copper_bonded_steel")))
        r = draw(**dict(results=S, meta=META))
        rod = [c for c in r["checks"] if c["item"] == "Earth rod diameter"][0]
        self.assertEqual(rod["status"], "FAIL")
        # every sheet carries the warning stamp
        self.assertTrue(all("NOT FOR CONSTRUCTION" in s["svg"] for s in r["sheets"]))

    def test_type_a_lightning_only(self):
        S = dict(lightning=call("/api/lightning", dict(lps_class="IV", rho=200, area=150, perimeter=50,
                                                       arrangement="A", d=0.01, h=0.5, rod_d=0.016)))
        r = draw(**dict(results=S, meta=dict(META, size="A2")))
        self.assertIn("T-401", [s["number"] for s in r["sheets"]])
        for sh in _sheets(S, META):
            self.assertEqual(text_overflows(sh), [], sh.number)

    def test_ieee80_example_b4_outline(self):
        # IEEE Std 80-2013 Example B.4: 70 m x 105 m, A = 4900 m², L_C = 1575 m, D = 7 m
        from earthsys.ieee80 import GridGeometry
        g = GridGeometry(Lx=70, Ly=105, D=7, shape="L", A_m2=4900, Lp_m=350, Lc_m=1575, n_rods=24, Lr=7.5)
        a, b, area, Lc = g.notch()
        self.assertEqual((a, b, area, Lc), (35.0, 70.0, 4900.0, 1575.0))
        segs = g.conductor_paths()
        self.assertAlmostEqual(sum(abs(q[0] - p[0]) + abs(q[1] - p[1]) for p, q in segs), 1575.0)
        self.assertEqual(len(g.rod_positions()), 24)
        for x, y in g.rod_positions():         # every rod on the L outline, none in the notch
            self.assertFalse(x > 35 + 1e-9 and y > 35 + 1e-9)
        J = drawings.grid_joints(segs, [])
        self.assertEqual(len(J["L"]), 5)       # the re-entrant corner is a crossing

    def test_rod_schedule_complete_and_flags(self):
        # Example B.4 with 24 rods: every rod is scheduled on sheet 101 (three
        # columns) and in rod_schedule.csv; the fence flag 6 points at the fence note
        g = call("/api/ieee80/design", dict(rho=400, Lx=70, Ly=105, D=7, h=0.5, d=0.01, n_rods=24, Lr=7.5,
                                            d_rod=0.016, IG_kA=1.908, rho_s=2500, hs=0.102, ts=0.5,
                                            body_weight=70, shape="l", A_m2=4900, Lp_m=350, Lc_m=1575,
                                            rods_on_perimeter=True))
        r = draw(**dict(results=dict(grid=g), meta=META, options=dict(fence=True)))
        z = zipfile.ZipFile(io.BytesIO(base64.b64decode(r["zip_b64"])))
        rows = z.read("rod_schedule.csv").decode().strip().split("\n")[1:]
        self.assertEqual(len(rows), 24)
        sh = _sheets(dict(grid=g), META, dict(fence=True))[1]
        texts = [g_[2] for k, _, g_ in sh.items if k == "T"]
        for i in range(24):
            self.assertTrue(any(t in (f"R{i + 1}", f"TP{i + 1}") for t in texts), i + 1)
        k6 = texts.index("6.")
        self.assertTrue(texts[k6 + 1].startswith("Fence"), texts[k6 + 1])

    def test_l_shaped_grid(self):
        g = call("/api/ieee80/design", dict(rho=200, Lx=60, Ly=40, D=6, h=0.6, d=0.012, n_rods=8, Lr=3,
                                            IG_kA=2.0, rho_s=3000, hs=0.1, ts=0.5, shape="l",
                                            A_m2=1800, Lp_m=200, Lc_m=700))
        S = dict(grid=g)
        r = draw(**dict(results=S, meta=META))
        self.assertIn("T-101", [s["number"] for s in r["sheets"]])
        for sh in _sheets(S, META):
            self.assertEqual(text_overflows(sh), [], sh.number)

    def test_numerical_layout(self):
        items = [dict(kind="grid", Lx=30, Ly=20, D=5, depth=0.5, radius=0.005, x0=0, y0=0),
                 dict(kind="rod", x=0, y=0, top_depth=0.5, length=3, radius=0.008),
                 dict(kind="ring", cx=15, cy=10, r=25, depth=0.6, radius=0.005, n_sides=32),
                 dict(kind="fence", x0=-3, y0=-3, Lx=36, Ly=26, post_spacing=3, post_depth=0.76,
                      post_radius=0.025)]
        S = dict(bem=dict(_in=dict(items=items)))
        r = draw(**dict(results=S, meta=META, options=dict(fence=False)))
        self.assertIn("T-101", [s["number"] for s in r["sheets"]])

    def test_sheet_selection_and_errors(self):
        S = full_results()
        r = draw(**dict(results=S, meta=META, options=dict(sheets=["201", "901"])))
        self.assertEqual([s["number"] for s in r["sheets"]], ["T-000", "T-201", "T-901"])
        with self.assertRaises(ValueError):
            draw(**dict(results={}, meta=META))
        with self.assertRaises(ValueError):
            draw(**dict(results=S, meta=dict(META, size="B5")))
        with self.assertRaises(ValueError):
            draw(**dict(results=S, meta=META, options=dict(wastage_pct=500)))


class Kernel(unittest.TestCase):
    def test_superscripts_and_symbols(self):
        sh = cad.Sheet("A4")
        sh.text(10, 10, "50 mm² at 8.7 Ω·m, Ø16", 2.5)
        texts = [g[2] for k, _, g in sh.items if k == "T"]
        self.assertEqual(texts, ["50 mm", "2", " at 8.7 Ω·m, Ø16"])
        dxf = cad.to_dxf(sh)
        self.assertIn("\\U+03A9", dxf)
        self.assertIn("%%c16", dxf)
        pdf = cad.to_pdf([sh])
        self.assertIn(b"/BaseFont /Symbol", pdf)

    def test_indices_and_iec_forms(self):
        sh = cad.Sheet("A4")
        sh.text(10, 10, "R_A · I_Δn ≤ 50 V; file EX-DWG_drawings.pdf", 2.5)
        runs = [(g[2], round(g[3], 2)) for k, _, g in sh.items if k == "T"]
        self.assertEqual([t for t, _ in runs], ["R", "A", " · I", "Δn", " ≤ 50 V; file EX-DWG_drawings.pdf"])
        self.assertEqual(runs[1][1], round(2.5 * 0.62, 2))
        self.assertEqual(cad.plain("3I_C0"), "3IC0")
        # boundary frames are dash-dot (IEC 60617 S00064, IEC 61082-1 7.1.5)
        self.assertEqual(cad.LAYERS["BOUNDARY"][2], "CENTER")
        # a short dimension in a chain keeps its value over the middle of the line
        sh = cad.Sheet("A4")
        sh.dim(0, 0, 5, 0, 0, "7", h=1.9, ext=False, tpos="chain")
        t = [g for k, _, g in sh.items if k == "T"][0]
        self.assertTrue(0 < t[0] < 5)

    def test_hatch_clips_to_polygon(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        segs = cad.hatch_lines([sq], 45, 1.0)
        self.assertTrue(segs)
        for x1, y1, x2, y2 in segs:
            for x, y in ((x1, y1), (x2, y2)):
                self.assertTrue(-1e-6 <= x <= 10 + 1e-6 and -1e-6 <= y <= 10 + 1e-6)

    def test_preferred_scales(self):
        self.assertEqual(cad.nice_scale(70000, 200), 500)
        self.assertEqual(cad.nice_scale(900, 50), 20)


if __name__ == "__main__":
    unittest.main()
