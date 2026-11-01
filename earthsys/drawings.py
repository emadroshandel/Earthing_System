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
Construction drawings (module 11): the design turned into a drawing set that a
contractor can build from and a manufacturer can quote from.

The set is generated from the results of the calculation modules — the IEEE 80
grid, the conductor size, the earth pits, the building electrodes, the
lightning earth termination, the air termination and the neutral earthing — and
from a few drafting options.  Nothing here repeats a calculation: every number
on a sheet is either a result, an input, or an installation rule quoted with its
clause, and the design-rule verification on the first sheet lists each rule.

Sheets
------
  000  Drawing register, general notes, legend and design-rule verification
  101  Earth grid layout plan               (IEEE 80 grid or numerical layout)
  102  Typical installation sections        (trench, rod, riser, fence)
  201  Earth pit and test link details      (BS 7430, IEC 62561-5)
  202  Main earthing terminal / earth bar   (IEC 60364-5-54, 542.4)
  301  Earthing connection details          (IEEE 837, IEC 62561-1)
  302  Equipment bonding details and conductor selection chart
  401  Lightning protection earth termination plan and details (IEC 62305-3)
  501  Earthing arrangement schematics      (IEC 60364-1 system types, IEEE 142)
  901  Bill of materials

The drafting kernel is earthsys.cad; output is SVG (preview), one vector PDF
for the whole set, and one DXF (R12) per sheet.
"""

from __future__ import annotations

import base64
import datetime as _dt
import io
import math
import zipfile

from . import cad
from .cad import Sheet, text_width, wrap

# ---------------------------------------------------------------------------
# reference data
# ---------------------------------------------------------------------------

STD_MM2 = [16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630]
# Approximate overall diameter of IEC 60228 class 2 bare stranded copper (mm),
# used only to draw the conductor to scale.
OD_MM = {16: 5.1, 25: 6.4, 35: 7.6, 50: 9.0, 70: 10.7, 95: 12.6, 120: 14.2, 150: 15.8,
         185: 17.6, 240: 20.0, 300: 22.4, 400: 25.9, 500: 29.0, 630: 32.6}

# Earth rods.  Minimum diameters from BS EN 50522:2022 Table C.1 and
# IEC 60364-5-54:2011+A1:2021 Table 54.1 (identical rows); a value in brackets
# there (min_d_shock) applies to protection against electric shock only.
ROD_MATERIALS = {
    "copper_bonded_steel": dict(
        label="COPPER-BONDED STEEL EARTH ROD",
        spec="Low-carbon steel core, ≥ 250 µm radial 99.9 % Cu, molecularly bonded",
        min_d=14.0, min_d_shock=14.0,
        std="EN 50522 Table C.1; IEC 60364-5-54 Table 54.1; IEC 62561-2 Table 3"),
    "copper": dict(label="SOLID COPPER EARTH ROD", spec="Hard-drawn copper",
                   min_d=15.0, min_d_shock=12.0,
                   std="EN 50522 Table C.1; IEC 60364-5-54 Table 54.1 (12 mm shock only)"),
    "galvanized_steel": dict(label="HOT-DIP GALVANIZED STEEL EARTH ROD",
                             spec="≥ 350 g/m² zinc; threads cut before galvanizing", min_d=16.0,
                             min_d_shock=16.0, std="EN 50522 Table C.1; IEC 60364-5-54 Table 54.1"),
    "stainless_steel": dict(label="STAINLESS STEEL EARTH ROD", spec="Cr ≥ 16 %, Ni ≥ 5 %, Mo ≥ 2 %",
                            min_d=16.0, min_d_shock=16.0,
                            std="EN 50522 Table C.1; IEC 60364-5-54 Table 54.1"),
}

# Buried bare copper earth electrode (stranded or round wire laid horizontally):
# BS EN 50522:2022 Table C.1 and IEC 60364-5-54 Table 54.1 — 50 mm² where the
# electrode also serves lightning protection, (25) mm² for protection against
# electric shock only, 16 mm² (footnote d) where experience shows the risk of
# corrosion and mechanical damage is extremely low.  IEC 62305-3 Table 7 and
# IEC 62561-2 Table 3 require 50 mm² for every lightning earth conductor.
ELECTRODE_DUTY = {
    "lightning": dict(min=50, label="lightning and shock protection",
                      ref="EN 50522 Table C.1; IEC 60364-5-54 Table 54.1; IEC 62305-3 Table 7"),
    "shock": dict(min=25, label="shock protection only",
                  ref="EN 50522 Table C.1; IEC 60364-5-54 Table 54.1 (value in brackets)"),
    "shock_low": dict(min=16, label="shock protection only, low corrosion risk",
                      ref="EN 50522 Table C.1 / IEC 60364-5-54 Table 54.1, footnote d"),
}

# IEC 62305-3:2024 Table 5 (down-conductor spacing) and Table 2 (mesh)
LPS_TABLE = {"I": dict(down=10, mesh=5, sphere=20), "II": dict(down=10, mesh=10, sphere=30),
             "III": dict(down=15, mesh=15, sphere=45), "IV": dict(down=20, mesh=20, sphere=60)}

STATUS = {"IFC": "ISSUED FOR CONSTRUCTION", "IFA": "ISSUED FOR APPROVAL",
          "IFR": "ISSUED FOR REVIEW", "IFI": "ISSUED FOR INFORMATION",
          "IFT": "ISSUED FOR TENDER", "PRE": "PRELIMINARY"}

# equipment bonding defaults: tails per item and whether the tail carries
# fault current (full-size) or is a protective bonding conductor.
EQUIPMENT = {
    "transformer": dict(name="Power transformer (tank)", tails=2, full=True,
                        note="Two leads, opposite directions (IEEE 80, 9.6)"),
    "neutral": dict(name="Transformer / generator neutral", tails=1, full=True,
                    note="Via NER where resistance earthed (IEEE 142)"),
    "arrester": dict(name="Surge arrester", tails=1, full=True,
                     note="Shortest straight route to the grid (IEEE 80, 17.7)"),
    "switchgear": dict(name="MV/HV switchgear line-up", tails=2, full=True,
                       note="Earth bar at both ends (IEEE 80, 9.6)"),
    "structure": dict(name="Steel structure / column", tails=1, full=True,
                      note="Base-plate lug, per column shown on plan"),
    "lv_panel": dict(name="LV switchboard / MCC", tails=2, full=False,
                     note="Earth bar both ends; PE per IEC 60364-5-54 Table 54.2"),
    "motor": dict(name="Motor frame", tails=1, full=False, note="Frame earth terminal"),
    "cable_tray": dict(name="Cable tray / ladder", tails=2, full=False,
                       note="Both ends; continuity jumper at every joint"),
    "fence": dict(name="Fence post / gate", tails=1, full=True,
                  note="Corners, gate posts and bonding interval (IEEE 80, 17.3)"),
    "pipe": dict(name="Metallic service pipe (water, gas)", tails=1, full=False,
                 note="Main protective bonding at entry (IEC 60364-5-54, 544.1)"),
}


def _f(v, d=2):
    """Number for a drawing: trailing zeros removed."""
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if not math.isfinite(v):
        return "—"
    s = f"{v:.{d}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _std_size(a):
    for s in STD_MM2:
        if s >= a - 1e-9:
            return s
    return STD_MM2[-1]


def _num(d, key, default=None):
    if not d:
        return default
    v = d.get(key)
    if v in (None, ""):
        return default
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


# ---------------------------------------------------------------------------
# normalised design context
# ---------------------------------------------------------------------------

class Ctx:
    """Everything the sheets need, pulled out of the module results once."""

    def __init__(self, data: dict):
        S = data.get("results") or {}
        opt = data.get("options") or {}
        meta = data.get("meta") or {}
        self.S, self.opt = S, opt
        self.version = data.get("version", "")
        today = _dt.date.today().isoformat()
        self.meta = dict(
            owner=meta.get("owner") or "",
            designer=meta.get("designer") or "",
            contractor=meta.get("contractor") or "",
            project=meta.get("project") or "EARTHING SYSTEM",
            location=meta.get("location") or "",
            prefix=(meta.get("prefix") or "ES-DWG").strip(),
            rev=str(meta.get("rev") or "0"),
            rev_desc=meta.get("rev_desc") or "",
            status=(meta.get("status") or "IFA").upper(),
            drawn=meta.get("drawn") or "", checked=meta.get("checked") or "",
            approved=meta.get("approved") or "", date=meta.get("date") or today,
            size=(meta.get("size") or "A3").upper(), lang="EN",
            engineer=meta.get("engineer") or "")
        if self.meta["size"] not in ("A3", "A2", "A1"):
            raise ValueError("Sheet size must be A3, A2 or A1.")
        if self.meta["status"] not in STATUS:
            raise ValueError(f"Status must be one of {', '.join(STATUS)}.")
        self.joint = (opt.get("joint") or "exothermic").lower()
        if self.joint not in ("exothermic", "compression"):
            raise ValueError("Connection method must be exothermic or compression.")
        self.lps_connected = bool(S.get("lightning") or S.get("airterm"))
        self.notes_extra = []

        # ---- grid ----------------------------------------------------------
        g = S.get("grid")
        self.grid = None
        if g and g.get("layout") and g.get("geometry"):
            geo = g["geometry"]
            gin = g.get("_in") or {}
            tol = g.get("tolerable") or {}
            mesh = g.get("mesh") or {}
            self.grid = dict(
                Lx=float(geo["Lx"]), Ly=float(geo["Ly"]), D=float(geo["D"]), h=float(geo["h"]),
                d=float(geo["d"]), n_rods=int(geo.get("n_rods") or 0), Lr=float(geo.get("Lr") or 0),
                d_rod=float(geo.get("d_rod") or 0.016), shape=geo.get("shape", "rectangular"),
                Lc=float(geo.get("Lc") or 0), LR=float(geo.get("LR") or 0),
                A=float(geo.get("A") or geo["Lx"] * geo["Ly"]),
                conductors=[[tuple(p) for p in seg] for seg in g["layout"].get("conductors", [])],
                rods=[tuple(r) for r in g["layout"].get("rods", [])],
                outline=[tuple(p) for p in (g["layout"].get("outline") or
                                            [(0, 0), (geo["Lx"], 0), (geo["Lx"], geo["Ly"]), (0, geo["Ly"])])],
                notch=g["layout"].get("notch"),
                rho=_num(tol, "rho", _num(gin, "rho")), rho_s=_num(tol, "rho_s", _num(gin, "rho_s")),
                hs=_num(tol, "hs", _num(gin, "hs")), ts=_num(tol, "ts", _num(gin, "ts")),
                IG_kA=_num(g, "IG_kA"), Rg=_num(g, "Rg"), GPR=_num(g, "GPR"),
                Em=_num(mesh, "Em"), Es=_num(mesh, "Es"), Et=_num(tol, "E_touch"),
                Est=_num(tol, "E_step"), body=tol.get("body_weight"), passed=bool(g.get("passed")))

        # ---- numerical layout (when there is no IEEE 80 grid) ---------------
        self.bem_items = []
        b = S.get("bem")
        if not self.grid and b:
            items = (b.get("_in") or {}).get("items") or b.get("items") or []
            self.bem_items = [it for it in items if isinstance(it, dict)]

        # ---- conductor -----------------------------------------------------
        c = S.get("conductor") or {}
        calc = _num(c, "selected_mm2")
        self.cond_calc = calc
        mat_key = ((c.get("_in") or {}).get("material") or "cu_hard")
        self.cond_material = (c.get("ieee80") or {}).get("material") or "Copper, commercial hard-drawn"
        self.cond_is_copper = mat_key.startswith("cu") and "clad" not in mat_key
        # duty of the buried electrode decides its minimum size
        duty = str(opt.get("electrode_duty") or "auto").lower()
        if duty not in ELECTRODE_DUTY:
            eq_opt = opt.get("equipment") if isinstance(opt.get("equipment"), dict) else None
            arresters = (int(eq_opt.get("arrester") or 0) if eq_opt is not None
                         else (3 if (S.get("grid") or S.get("bem")) else 0))
            duty = "lightning" if (self.lps_connected or arresters > 0) else "shock"
            self.duty_auto = (("a lightning protection system is designed" if self.lps_connected
                               else "surge arresters discharge into it") if duty == "lightning"
                              else "no lightning current is expected")
        else:
            self.duty_auto = None
        self.duty = duty
        dd_ = ELECTRODE_DUTY[duty]
        self.cond_min = float(dd_["min"])
        override = _num(opt, "conductor_mm2")
        if override:
            size = _std_size(override)
            self.cond_basis = "drafting option"
        elif calc:
            size = _std_size(max(calc, self.cond_min))
            self.cond_basis = ("calculated" if calc >= self.cond_min - 1e-9 else
                               f"raised from the calculated {_f(calc)} mm² to the {int(self.cond_min)} mm² "
                               f"minimum for {dd_['label']}")
        else:
            size = _std_size(self.cond_min)
            self.cond_basis = f"minimum for {dd_['label']} (no conductor calculation run)"
        if self.grid and not override and not calc:
            # size from the grid conductor diameter if that is all we have
            a = math.pi * (self.grid["d"] * 1000) ** 2 / 4
            size = _std_size(max(a * 0.8, self.cond_min))
            self.cond_basis = "from the grid conductor diameter"
        self.cond = size
        self.cond_od = OD_MM.get(size, 1.2 * math.sqrt(size))

        # ---- rods ----------------------------------------------------------
        ep = S.get("earthpit") or {}
        epin = ep.get("_in") or {}
        rod_mat = (opt.get("rod_material") or epin.get("material") or "copper_bonded_steel")
        if rod_mat not in ROD_MATERIALS:
            rod_mat = "copper_bonded_steel"
        self.rod_mat = rod_mat
        self.rod_min_d = ROD_MATERIALS[rod_mat]["min_d" if self.duty == "lightning" else "min_d_shock"]
        if self.grid and self.grid["n_rods"] > 0:
            Lr, dr = self.grid["Lr"], self.grid["d_rod"]
        elif epin.get("electrode", "rod") == "rod" and epin.get("L"):
            Lr, dr = float(epin["L"]), float(epin.get("d") or 0.016)
        else:
            Lr, dr = 3.0, 0.016
            for e in ((S.get("building") or {}).get("_in") or {}).get("electrodes") or []:
                if e.get("type") in ("rod", "rods_parallel"):
                    Lr, dr = float(e.get("L") or 3), float(e.get("d") or 0.016)
                    break
        self.rod_L, self.rod_d = Lr, dr * 1000.0
        sec = _num(opt, "rod_section_m", 1.5)
        self.rod_section = sec if sec and sec > 0 else 1.5
        self.rod_nsec = max(1, int(math.ceil(Lr / self.rod_section - 1e-6)))

        # ---- earth pit -----------------------------------------------------
        self.pit = None
        if ep:
            el = epin.get("electrode", "rod")
            self.pit = dict(
                electrode=el, L=float(epin.get("L") or Lr), d=float(epin.get("d") or dr) * 1000,
                D=float(epin.get("D") or 0.3) * 1000, fill_top=float(epin.get("fill_top") or 0) * 1000,
                fill_bottom=(float(epin["fill_bottom"]) * 1000 if epin.get("fill_bottom") not in (None, "")
                             else None),
                area=_num(epin, "area"), top=_num(epin, "top", 0.0), n=int(epin.get("n") or 1),
                s=_num(epin, "s", 6.0), housing=(ep.get("housing") or {}).get("cls") or
                (epin.get("housing_class") or "L"), backfill=ep.get("backfill") or "",
                rho_c=_num(ep, "rho_c"), R_pit=_num(ep, "R_pit"), R_dry=_num(ep, "R_dry"),
                R_group=_num(ep.get("group") or {}, "R"), volume=_num(ep, "backfill_volume_m3"),
                retest=_num(ep.get("maintenance") or {}, "retest_limit"),
                load_kN=_num(ep.get("housing") or {}, "load_kN"))
        hc = (opt.get("pit_housing") or (self.pit or {}).get("housing") or "L").upper()
        self.housing = hc if hc in ("L", "M", "H") else "L"

        # ---- building ------------------------------------------------------
        bl = S.get("building")
        self.building = None
        if bl:
            bin_ = bl.get("_in") or {}
            self.building = dict(system=str(bl.get("system") or bin_.get("system") or "TT").upper(),
                                 RA=_num(bl, "RA"), U0=_num(bl, "U0", _num(bin_, "U0", 230)),
                                 device=bl.get("device") or {}, passed=bool(bl.get("passed")),
                                 electrodes=bin_.get("electrodes") or [], rho=_num(bl, "rho"))

        # ---- lightning protection -------------------------------------------
        L = S.get("lightning")
        A = S.get("airterm")
        self.lps = None
        if L or A:
            cls = str((L or A).get("lps_class") or "III").upper()
            st = (A or {}).get("structure") or {}
            W = _num(st, "width")
            Dp = _num(st, "depth")
            H = _num(st, "height")
            earth = (L or {}).get("earth") or {}
            if not (W and Dp):
                area = _num((L or {}).get("_in") or {}, "area", 400.0)
                per = _num((L or {}).get("_in") or {}, "perimeter", 4 * math.sqrt(area))
                # rectangle with the same area and perimeter where possible
                disc = (per / 2) ** 2 - 4 * area
                if disc > 0:
                    W = (per / 2 + math.sqrt(disc)) / 2
                    Dp = area / W
                else:
                    W = Dp = math.sqrt(area)
            self.lps = dict(
                cls=cls, W=W, D=Dp, H=H or 10.0, table=LPS_TABLE.get(cls, LPS_TABLE["III"]),
                arrangement=(earth.get("arrangement") or "Type B"),
                l1=_num(earth, "l1", _num(earth.get("l1_data") or {}, "l1")),
                re=_num(earth, "mean_radius"), radius_ok=earth.get("radius_ok"),
                supplementary=earth.get("supplementary"),
                R=_num(earth, "R_total"), n_down=_num((L or {}).get("down_conductors") or {}, "n_down"),
                terminals=(A or {}).get("terminals") or [],
                x0=_num(st, "x0", -(W or 0) / 2), mesh=_num(A or {}, "mesh_size"),
                ring_depth=_num((L or {}).get("_in") or {}, "h", 0.5),
                passed=bool((L or {}).get("passed", True)))

        # ---- neutral earthing ----------------------------------------------
        sg = S.get("sysgnd")
        self.ner = None
        if sg:
            self.ner = dict(method=sg.get("method"), R=_num(sg, "R_ohm"), I=_num(sg, "I_target"),
                            V_ln=_num(sg, "V_ln"), t=_num(sg, "time_rating_s"),
                            V_ll=_num(sg.get("_in") or {}, "V_ll_kV"),
                            three_IC0=_num(sg, "three_IC0"), X=_num(sg, "X_ohm"))

        # ---- equipment and drafting options --------------------------------
        eq = opt.get("equipment")
        if not isinstance(eq, dict):
            eq = {}
            if self.grid or self.bem_items:
                eq = dict(transformer=1, neutral=1, arrester=3, switchgear=1, structure=4, fence=1)
            if self.building:
                eq.update(lv_panel=1, pipe=2, cable_tray=1)
        self.equipment = {k: int(v) for k, v in eq.items() if k in EQUIPMENT and int(v or 0) > 0}
        self.fence = bool(opt.get("fence", bool(self.grid)))
        self.fence_off = _num(opt, "fence_offset", 1.0)
        self.fence_bond = _num(opt, "fence_bond_m", 15.0)
        self.wastage = _num(opt, "wastage_pct", 10.0)
        self.met_ways = int(_num(opt, "met_ways", 10))
        self.n_test_pits = int(_num(opt, "test_pits", 4 if self.grid else (self.pit or {}).get("n", 0) or 0))

        # main earthing terminal bar: smallest standard bar with a section not
        # less than the main earthing conductor and at least 50 x 6
        bars = [(50, 6), (50, 10), (75, 10), (100, 10)]
        need = max(self.cond, 300)
        self.met_bar = next((b for b in bars if b[0] * b[1] >= need), bars[-1])
        self.met_bolt = "M12" if self.cond > 35 else "M10"

    # -- conveniences ----------------------------------------------------------
    @property
    def cond_label(self):
        return f"BARE STRANDED COPPER {self.cond} mm²" if self.cond_is_copper else \
            f"EARTH CONDUCTOR {self.cond} mm² ({self.cond_material})"

    @property
    def rod_label(self):
        return (f"{ROD_MATERIALS[self.rod_mat]['label']} Ø{_f(self.rod_d, 1)} mm × "
                f"{_f(self.rod_L)} m")

    def joint_name(self, kind):
        if self.joint == "exothermic":
            return {"X": "EXOTHERMIC WELD, CROSS (X) TYPE", "T": "EXOTHERMIC WELD, TEE (T) TYPE",
                    "L": "EXOTHERMIC WELD, CORNER / BEND", "S": "EXOTHERMIC WELD, STRAIGHT SPLICE",
                    "R": "EXOTHERMIC WELD, CABLE TO EARTH ROD",
                    "P": "EXOTHERMIC WELD, CABLE TO STEEL SURFACE"}[kind]
        return {"X": "COMPRESSION CONNECTOR, CROSS (X) TYPE", "T": "COMPRESSION C-TAP, TEE",
                "L": "COMPRESSION C-TAP, CORNER", "S": "COMPRESSION SPLICE SLEEVE",
                "R": "COMPRESSION ROD-TO-CABLE CONNECTOR",
                "P": "TWO-HOLE COMPRESSION LUG, BOLTED"}[kind]


# ---------------------------------------------------------------------------
# geometry: joints of the grid
# ---------------------------------------------------------------------------

def grid_joints(conductors, rods, tol=1e-6):
    """Classify every node of the conductor network.

    Each segment contributes two arms at every interior node it passes through
    and one arm at each of its ends.  4 arms → cross (X); 3 → tee (T);
    2 at an angle → corner (L); 2 in line at a segment end → straight splice.
    Rods are counted separately (cable-to-rod)."""
    segs = [((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))) for a, b in conductors]
    pts = {}

    def key(p):
        return (round(p[0] / 1e-3) * 1e-3, round(p[1] / 1e-3) * 1e-3)

    def add(p, ang):
        pts.setdefault(key(p), []).append(ang)

    # all candidate nodes: segment ends and pairwise intersections
    cand = set()
    for a, b in segs:
        cand.add(key(a)); cand.add(key(b))
    for i in range(len(segs)):
        (x1, y1), (x2, y2) = segs[i]
        for j in range(i + 1, len(segs)):
            (x3, y3), (x4, y4) = segs[j]
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(den) < 1e-12:
                continue
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
            if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
                cand.add(key((x1 + t * (x2 - x1), y1 + t * (y2 - y1))))
    for (a, b) in segs:
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        for p in cand:
            # distance along and from the segment
            t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)
            if t < -1e-6 or t > 1 + 1e-6:
                continue
            q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if math.hypot(q[0] - p[0], q[1] - p[1]) > 2e-3:
                continue
            if t <= 1e-6:
                add(p, ang)
            elif t >= 1 - 1e-6:
                add(p, ang + 180)
            else:
                add(p, ang); add(p, ang + 180)
    out = dict(X=[], T=[], L=[], S=[], E=[])
    for p, arms in pts.items():
        # merge duplicate arms (overlapping segments)
        uniq = []
        for a in arms:
            a = a % 360
            if not any(abs(((a - u) + 180) % 360 - 180) < 1 for u in uniq):
                uniq.append(a)
        n = len(uniq)
        if n >= 4:
            out["X"].append(p)
        elif n == 3:
            out["T"].append(p)
        elif n == 2:
            d = abs(((uniq[0] - uniq[1]) + 180) % 360 - 180)
            (out["S"] if abs(d - 180) < 1 else out["L"]).append(p)
        else:
            out["E"].append(p)
    out["R"] = list(rods)
    return out


def offset_orthogonal(poly, d):
    """Offset an orthogonal (rectilinear) polygon inwards by d: every vertex
    moves by d along both inward edge normals."""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0          # CCW: inward normal is to the left
    out = []
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        nx = ny = 0.0
        for a, b in ((p0, p1), (p1, p2)):
            ex, ey = b[0] - a[0], b[1] - a[1]
            L = math.hypot(ex, ey) or 1.0
            nx += -ey / L * sgn
            ny += ex / L * sgn
        out.append((p1[0] + d * nx, p1[1] + d * ny))
    return out


def outward_normal(poly, p, tol=1e-6):
    """Unit outward normal of polygon poly at a point p on its boundary (the
    sum of the normals of the edges through p, so a vertex gets the diagonal);
    None when p is not on the boundary."""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    nx = ny = 0.0
    hit = False
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ex, ey)
        if L < tol:
            continue
        t = ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L ** 2
        if -tol <= t <= 1 + tol and abs((p[0] - a[0]) * ey - (p[1] - a[1]) * ex) / L < tol * 10:
            nx += ey / L * sgn
            ny += -ex / L * sgn
            hit = True
    if not hit:
        return None
    L = math.hypot(nx, ny)
    return (nx / L, ny / L) if L > 1e-9 else None


def total_length(conductors):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in conductors)


# ---------------------------------------------------------------------------
# sheet frame and title block (ISO 5457 / ISO 7200)
# ---------------------------------------------------------------------------

ZONES = {"A3": (8, 6), "A2": (12, 8), "A1": (16, 12)}


class Frame:
    """Geometry of the sheet: drawing area and the right-hand panel."""

    def __init__(self, sh: Sheet):
        self.sh = sh
        W, H = sh.W, sh.H
        self.fx0, self.fy0, self.fx1, self.fy1 = 20.0, 10.0, W - 10.0, H - 10.0
        self.pw = 125.0 if sh.size == "A3" else 150.0
        self.px0 = self.fx1 - self.pw
        self.tb_h = 104.0
        # drawing area
        # 6 mm clear of the frame at the left and top, where the centring marks
        # reach 5 mm into the sheet (ISO 5457)
        self.ax0, self.ay0, self.ax1, self.ay1 = self.fx0 + 6, self.fy0 + 4, self.px0 - 4, self.fy1 - 6

    @property
    def area(self):
        return (self.ax0, self.ay0, self.ax1 - self.ax0, self.ay1 - self.ay0)


def draw_frame(sh: Sheet, ctx: Ctx, fr: Frame, sheet_no: int, total: int, scale_txt: str,
               notes: list, bom: list, title2: str = ""):
    W, H = sh.W, sh.H
    # trimmed sheet edge, frame, grid-reference border (ISO 5457)
    sh.rect(0, 0, W, H, "TITLETHIN")
    sh.rect(fr.fx0, fr.fy0, fr.fx1 - fr.fx0, fr.fy1 - fr.fy0, "FRAME")
    ox0, oy0, ox1, oy1 = fr.fx0 - 5, fr.fy0 - 5, fr.fx1 + 5, fr.fy1 + 5
    sh.rect(ox0, oy0, ox1 - ox0, oy1 - oy0, "TITLETHIN")
    # reference grid: 50 mm fields measured from the centring marks
    # (ISO 5457; IEC 61082-1, 5.7.3.4 — 20M with M = 2.5 mm), rows lettered
    # from the top without I and O, columns numbered from the left
    def bounds(lo, hi):
        c = (lo + hi) / 2
        cuts = {c}
        k = 1
        while c - 50 * k > lo + 5:
            cuts.add(c - 50 * k); cuts.add(c + 50 * k); k += 1
        return [lo] + sorted(cuts) + [hi]
    xb = bounds(fr.fx0, fr.fx1)
    yb = bounds(fr.fy0, fr.fy1)[::-1]
    for i, x in enumerate(xb):
        if 0 < i < len(xb) - 1:
            sh.line(x, oy0, x, fr.fy0, "TITLETHIN"); sh.line(x, fr.fy1, x, oy1, "TITLETHIN")
        if i < len(xb) - 1:
            xm = (x + xb[i + 1]) / 2
            sh.text(xm, (oy0 + fr.fy0) / 2, str(i + 1), 2.5, "middle", "middle")
            sh.text(xm, (oy1 + fr.fy1) / 2, str(i + 1), 2.5, "middle", "middle")
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    for j, y in enumerate(yb):
        if 0 < j < len(yb) - 1:
            sh.line(ox0, y, fr.fx0, y, "TITLETHIN"); sh.line(fr.fx1, y, ox1, y, "TITLETHIN")
        if j < len(yb) - 1:
            ym = (y + yb[j + 1]) / 2
            sh.text((ox0 + fr.fx0) / 2, ym, letters[j], 2.5, "middle", "middle")
            sh.text((ox1 + fr.fx1) / 2, ym, letters[j], 2.5, "middle", "middle")
    # centring marks
    cx, cy = (fr.fx0 + fr.fx1) / 2, (fr.fy0 + fr.fy1) / 2
    for (x1, y1, x2, y2) in ((cx, 0, cx, fr.fy0 + 5), (cx, H, cx, fr.fy1 - 5),
                             (0, cy, fr.fx0 + 5, cy), (W, cy, fr.fx1 - 5, cy)):
        sh.line(x1, y1, x2, y2, "FRAME")

    # right-hand panel
    px0, px1 = fr.px0, fr.fx1
    sh.line(px0, fr.fy0, px0, fr.fy1, "FRAME")
    tb_top = fr.fy0 + fr.tb_h
    _title_block(sh, ctx, px0, fr.fy0, px1, tb_top, sheet_no, total, scale_txt, title2)

    y = fr.fy1
    # a failed design-rule check is stamped on every sheet, at the head of the
    # panel, where it can never cover the drawing
    if getattr(ctx, "failed", None):
        sh.rect(px0 + 2, y - 19, px1 - px0 - 4, 17, "FRAME")
        sh.text((px0 + px1) / 2, y - 9, "NOT FOR CONSTRUCTION", 5.0, "middle", bold=True)
        n_ = ctx.failed
        t_, h_ = cad.fit(f"DESIGN-RULE CHECK FAILED ({n_}) — SEE SHEET 000", px1 - px0 - 8, 2.5, True)
        sh.text((px0 + px1) / 2, y - 15.5, t_, h_, "middle", bold=True)
        y -= 21
        sh.line(px0, y, px1, y, "FRAME")

    # NOTES and the item list fill the panel above the title block
    sh.rect(px0, y - 8, px1 - px0, 8, "TITLE")
    sh.text((px0 + px1) / 2, y - 4, "NOTES", 3.5, "middle", "middle", bold=True)
    y -= 8
    bom_h = (len(bom) + 1) * 5.0 + 1 if bom else 0
    avail_notes = (y - tb_top) - bom_h - 2
    yy = y - 2
    h = 2.5
    wmax = px1 - px0 - 14          # clear of the centring mark on the right
    lines = []
    for i, n in enumerate(notes, 1):
        wl = wrap(n, wmax, h)
        lines.append((f"{i}.", wl))
    used = sum(len(wl) * (h + 1.25) + 0.6 for _, wl in lines)
    if used > avail_notes and lines:
        # shrink the lettering slightly before truncating (ISO 3098: ≥ 1.8 mm)
        h = 1.8
        wmax = px1 - px0 - 14
        lines = [(f"{i}.", wrap(n, wmax, h)) for i, n in enumerate(notes, 1)]
    for num, wl in lines:
        if yy - len(wl) * (h + 1.25) < tb_top + bom_h + 2:
            sh.text(px0 + 2, yy - h, "(notes continue on sheet 000)", h)
            break
        yy -= h
        sh.text(px0 + 2, yy, num, h)
        for k, t in enumerate(wl):
            if k:
                yy -= h
            sh.text(px0 + 7, yy, t, h)
            yy -= 1.25
        yy -= 0.6
    if bom:
        _panel_bom(sh, px0, px1, tb_top + bom_h, bom)


def _panel_bom(sh, x0, x1, ytop, bom):
    rh = 5.0
    cols = [x0, x0 + 8, x1 - 28, x1 - 16, x1]
    y = ytop
    sh.line(x0, y, x1, y, "TITLE")
    hdr = ["No.", "DESCRIPTION", "QTY", "UNIT"]
    sh.line(x0, y - rh, x1, y - rh, "TITLE")
    for i, t in enumerate(hdr):
        if i == 3:      # left-aligned, clear of the centring mark at the frame
            sh.text(cols[3] + 1.5, y - rh / 2, t, 2.2, "start", "middle", bold=True)
        else:
            sh.text((cols[i] + cols[i + 1]) / 2, y - rh / 2, t, 2.2, "middle", "middle", bold=True)
    y -= rh
    for it in bom:
        d, h = cad.fit(it[1], cols[2] - cols[1] - 2, 1.9)
        sh.balloon((cols[0] + cols[1]) / 2, y - rh / 2, it[0], r=1.9, h=1.9)
        sh.text(cols[1] + 1, y - rh / 2, d, h, "start", "middle")
        sh.text((cols[2] + cols[3]) / 2, y - rh / 2, it[2], 1.9, "middle", "middle")
        sh.text(cols[3] + 1.5, y - rh / 2, it[3], 1.9, "start", "middle")
        y -= rh
        sh.line(x0, y, x1, y, "TITLETHIN")
    for c in cols[1:-1]:
        sh.line(c, ytop, c, y, "TITLETHIN")


def _cell(sh, x0, y0, x1, y1, label, value, vh=2.5, bold=False, lh=1.8, align="start", maxw=None):
    sh.rect(x0, y0, x1 - x0, y1 - y0, "TITLE")
    sh.text(x0 + 1, y1 - 1 - lh, label, lh, layer="TEXT")
    if value in (None, ""):
        return
    lines = value if isinstance(value, list) else [value]
    w = (x1 - x0 - 2) if maxw is None else maxw
    out = []
    for ln in lines:
        out.append(cad.fit(ln, w, vh, bold))
    n = len(out)
    avail = y1 - y0 - lh - 2
    total = sum(h for _, h in out) + (n - 1) * 1.2
    y = y0 + (avail - total) / 2 + total
    for ln, h in out:
        y -= h
        if align == "middle":
            sh.text((x0 + x1) / 2, y, ln, h, "middle", bold=bold)
        else:
            sh.text(x0 + 2, y, ln, h, bold=bold)
        y -= 1.2


def _projection_symbol(sh, x, y, s=1.0):
    """ISO 5456-2 first-angle projection symbol centred at (x, y)."""
    # truncated cone side view (left) and end view (right) — first angle
    h = 6 * s
    sh.poly([(x - 9 * s, y - h / 2 * 0.55), (x - 9 * s, y + h / 2 * 0.55),
             (x - 2 * s, y + h / 2), (x - 2 * s, y - h / 2)], True, "TITLE")
    sh.line(x - 10.5 * s, y, x - 0.5 * s, y, "CENTRE")
    sh.circle(x + 5 * s, y, h / 2, "TITLE")
    sh.circle(x + 5 * s, y, h / 2 * 0.55, "TITLE")
    sh.line(x + 0.5 * s, y, x + 9.5 * s, y, "CENTRE")
    sh.line(x + 5 * s, y - h / 2 - 1, x + 5 * s, y + h / 2 + 1, "CENTRE")


def _title_block(sh, ctx: Ctx, x0, y0, x1, y1, sheet_no, total, scale_txt, title2):
    m = ctx.meta
    W = x1 - x0
    y = y0
    # row 1: drawing number / revision / sheet
    r1 = 13
    _cell(sh, x0, y, x0 + W * 0.62, y + r1, "DRAWING No.", sh.number, 4.0, True)
    _cell(sh, x0 + W * 0.62, y, x0 + W * 0.76, y + r1, "REV.", m["rev"], 4.0, True, align="middle")
    _cell(sh, x0 + W * 0.76, y, x1, y + r1, "SHEET", f"{sheet_no} OF {total}", 2.5, align="middle")
    y += r1
    # row 2: scale / size / projection / date / language
    r2 = 10
    _cell(sh, x0, y, x0 + W * 0.26, y + r2, "SCALE", scale_txt, 2.5)
    _cell(sh, x0 + W * 0.26, y, x0 + W * 0.40, y + r2, "SIZE", sh.size, 2.5)
    sh.rect(x0 + W * 0.40, y, W * 0.22, r2, "TITLE")
    _projection_symbol(sh, x0 + W * 0.51, y + r2 / 2 - 0.5, 0.62)
    _cell(sh, x0 + W * 0.62, y, x0 + W * 0.86, y + r2, "DATE OF ISSUE", m["date"], 2.5)
    _cell(sh, x0 + W * 0.86, y, x1, y + r2, "LANG.", m["lang"], 2.5)
    y += r2
    # row 3: title
    r3 = 18
    t_lines = wrap(sh.title, W - 4, 3.5, True)
    if title2:
        t_lines.append(title2)
    _cell(sh, x0, y, x1, y + r3, "TITLE", t_lines[:3], 3.5, True)
    y += r3
    # row 4: project
    r4 = 10
    proj = m["project"] + (f" — {m['location']}" if m["location"] else "")
    _cell(sh, x0, y, x1, y + r4, "PROJECT", proj, 2.5)
    y += r4
    # row 5: document type / status
    r5 = 9
    _cell(sh, x0, y, x0 + W * 0.45, y + r5, "DOCUMENT TYPE", "CONSTRUCTION DRAWING", 2.5)
    _cell(sh, x0 + W * 0.45, y, x1, y + r5, "STATUS", STATUS[m["status"]], 2.5, True)
    y += r5
    # row 6: responsibility (ISO 7200: creator, approval person)
    r6 = 10
    third = W / 3
    _cell(sh, x0, y, x0 + third, y + r6, "DRAWN", m["drawn"], 2.5)
    _cell(sh, x0 + third, y, x0 + 2 * third, y + r6, "CHECKED", m["checked"], 2.5)
    _cell(sh, x0 + 2 * third, y, x1, y + r6, "APPROVED", m["approved"], 2.5)
    y += r6
    # row 7: owner / designer
    r7 = 13
    _cell(sh, x0, y, x0 + W / 2, y + r7, "OWNER / CLIENT", wrap(m["owner"], W / 2 - 4, 2.5)[:2] or "", 2.5)
    _cell(sh, x0 + W / 2, y, x1, y + r7, "DESIGNED BY", wrap(m["designer"], W / 2 - 4, 2.5)[:2] or "", 2.5)
    y += r7
    # row 8: revision history (3 lines)
    rh = 4.5
    cols = [x0, x0 + 10, x0 + 30, x1 - 30, x1 - 20, x1 - 10, x1]
    heads = ["REV", "DATE", "DESCRIPTION", "BY", "CHK", "APP"]
    rows = [[m["rev"], m["date"], (m["rev_desc"] or STATUS[m["status"]]),
             m["drawn"][:6], m["checked"][:6], m["approved"][:6]], ["", "", "", "", "", ""],
            ["", "", "", "", "", ""]]
    yy = y
    for k in range(3, -1, -1):
        row = heads if k == 3 else rows[2 - k]
        for i in range(6):
            sh.rect(cols[i], yy, cols[i + 1] - cols[i], rh, "TITLETHIN")
            t, hh = cad.fit(row[i], cols[i + 1] - cols[i] - 1, 1.8) if row[i] else ("", 1.8)
            sh.text((cols[i] + cols[i + 1]) / 2, yy + rh / 2, t, hh, "middle", "middle", bold=(k == 3))
        yy += rh
    sh.rect(x0, y, W, yy - y, "TITLE")
    # thin disclaimer under the frame line
    sh.text(x1, 1.6, f"Generated by Earthing System {ctx.version} — check every dimension "
            f"on site; do not scale from this drawing.", 1.8, "end")


# ---------------------------------------------------------------------------
# small drawing helpers
# ---------------------------------------------------------------------------

def scale_text(n):
    return "NTS" if not n else f"1:{n}"


def earth_symbol(sh, x, y, s=1.0, layer="OUTLINE"):
    """IEC 60617 S00200 (earth, general) — the stem ends at (x, y)."""
    sh.line(x, y, x, y - 3 * s, layer)
    for i, w in enumerate((3.0, 2.0, 1.0)):
        yy = y - 3 * s - i * 1.0 * s
        sh.line(x - w * s, yy, x + w * s, yy, layer)


def pe_symbol(sh, x, y, s=1.0):
    """IEC 60617 S00202 protective earthing: the earth symbol in a circle."""
    sh.circle(x, y, 3.2 * s, "OUTLINE")
    sh.line(x, y + 2.0 * s, x, y + 0.2 * s, "OUTLINE")
    for i, w in enumerate((1.8, 1.2, 0.6)):
        yy = y + 0.2 * s - i * 0.8 * s
        sh.line(x - w * s, yy, x + w * s, yy, "OUTLINE")


def rod_symbol(sh, x, y, r=1.6):
    sh.circle(x, y, r, "ELECTRODE")
    sh.line(x - r, y, x + r, y, "ELECTRODE")
    sh.line(x, y - r, x, y + r, "ELECTRODE")


def pit_symbol(sh, x, y, s=2.6):
    sh.rect(x - s, y - s, 2 * s, 2 * s, "ELECTRODE")
    rod_symbol(sh, x, y, s * 0.55)


def table(sh, x, ytop, cols, rows, header=None, rh=5.0, h=2.2, head_h=None, aligns=None,
          wrap_cols=None):
    """Simple ruled table; cols are widths.  Returns the bottom y."""
    h = cad.std_height(h)          # wrap at the height that is drawn
    xs = [x]
    for w in cols:
        xs.append(xs[-1] + w)
    y = ytop
    aligns = aligns or ["start"] * len(cols)
    if header:
        hh = head_h or rh
        sh.rect(x, y - hh, xs[-1] - x, hh, "TITLE")
        for i, t in enumerate(header):
            ls = t.split("\n")
            yy = y - hh / 2 + (len(ls) - 1) * (h + 0.8) / 2
            for ln in ls:
                sh.text((xs[i] + xs[i + 1]) / 2, yy, ln, h, "middle", "middle", bold=True)
                yy -= h + 0.8
        y -= hh
    for row in rows:
        # row height grows with wrapped cells
        cells = []
        nl = 1
        for i, t in enumerate(row):
            t = "" if t is None else str(t)
            if wrap_cols and i in wrap_cols:
                ls = wrap(t, cols[i] - 2, h)
            else:
                ls = [t]
            cells.append(ls)
            nl = max(nl, len(ls))
        hrow = max(rh, nl * (h + 1.1) + 1.6)
        for i, ls in enumerate(cells):
            yy = y - (hrow - (len(ls) * (h + 1.1) - 1.1)) / 2 - h
            for ln in ls:
                ln, hh = cad.fit(ln, cols[i] - 1.5, h)
                if aligns[i] == "middle":
                    sh.text((xs[i] + xs[i + 1]) / 2, yy, ln, hh, "middle")
                elif aligns[i] == "end":
                    sh.text(xs[i + 1] - 1, yy, ln, hh, "end")
                else:
                    sh.text(xs[i] + 1, yy, ln, hh)
                yy -= h + 1.1
        y -= hrow
        sh.line(x, y, xs[-1], y, "TITLETHIN")
    top = ytop - (head_h or rh) if header else ytop
    for xx in xs[1:-1]:
        sh.line(xx, ytop, xx, y, "TITLETHIN")
    sh.rect(x, y, xs[-1] - x, ytop - y, "TITLE")
    return y


def flag(sh, x, y, num, tx=None, ty=None):
    """Flag note: a numbered triangle referring to a note in the panel, with an
    optional short leader to the feature at (tx, ty)."""
    r = 2.9
    if tx is not None:
        sh.line(tx, ty, x, y - r * 0.5, "DIM")
        sh.dot(tx, ty, 0.45, "DIM")
    sh.poly([(x - r, y - r * 0.55), (x + r, y - r * 0.55), (x, y + r * 1.05)], True, "OUTLINE")
    sh.text(x, y - r * 0.5 + 0.55, str(num), 2.0, "middle", bold=True)


def north_arrow(sh, x, y, s=1.0):
    sh.circle(x, y, 6 * s, "THIN")
    sh.poly([(x, y + 6 * s), (x + 2.2 * s, y - 3.5 * s), (x, y - 1.5 * s)], True, "OUTLINE", fill=True)
    sh.poly([(x, y + 6 * s), (x - 2.2 * s, y - 3.5 * s), (x, y - 1.5 * s)], True, "OUTLINE")
    sh.text(x, y + 7.5 * s, "N", 3.5, "middle", bold=True)


def scale_bar(sh, x, y, n, unit_m=True, length_mm=60.0):
    """Graphic scale: alternate black/white blocks, labelled in metres."""
    # choose a round model length that is about length_mm on paper
    model = length_mm * n / 1000.0
    nice = [0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500]
    step = min(nice, key=lambda v: abs(v * 5 - model))
    seg = step * 1000.0 / n
    for i in range(5):
        sh.rect(x + i * seg, y, seg, 1.6, "THIN", fill=(i % 2 == 0))
        sh.text(x + i * seg, y + 2.6, _f(step * i), 2.0, "middle")
    sh.text(x + 5 * seg, y + 2.6, _f(step * 5) + " m", 2.0, "middle")
    sh.text(x, y - 3.5, f"SCALE 1:{n}", 2.2)


# ---------------------------------------------------------------------------
# sheet 000 — register, notes, legend, verification
# ---------------------------------------------------------------------------

def general_notes(ctx: Ctx):
    rm = ROD_MATERIALS[ctx.rod_mat]
    n = [
        "All dimensions are in millimetres and levels in metres, unless stated otherwise. "
        "Do not scale; confirm all setting-out on site.",
        "Read with the earthing design report (IEEE Std 80-2013, IEC 60364-5-54, IEC 62305-3 and "
        "BS 7430 calculations) and the equipment layout drawings.",
        f"Earthing conductor: {ctx.cond_label.lower()}, IEC 60228 class 2, unless noted. Buried bare "
        f"copper used as an earth electrode for {ELECTRODE_DUTY[ctx.duty]['label']} shall be not less than "
        f"{int(ctx.cond_min)} mm² ({ELECTRODE_DUTY[ctx.duty]['ref']}); earthing conductors not in the soil "
        f"not less than 16 mm² Cu (EN 50522, 5.2.2).",
        f"Earth rods: {rm['label'].lower()}, Ø ≥ {_f(ctx.rod_min_d)} mm ({rm['std']}). {rm['spec']}. "
        "Couplings of silicon bronze or aluminium bronze, ≥ 75 % Cu (BS 7430, 9.10).",
        "Underground and concealed joints: exothermic weld or compression connector qualified to "
        "IEEE Std 837 / IEC 62561-1. Soldered joints shall not be used (IEEE Std 80, 9.6; "
        "IEC 60364-5-54, 542.3.2).",
        "Bolted joints: stainless or copper-alloy hardware (copper alloys ≤ 15 % zinc), able to "
        "withstand a torque of at least 20 N·m (BS 7430, 9.10); contact faces cleaned and coated with "
        "joint compound.",
        "Transformer tanks, breaker and switch frames and surge arrester pads: two earthing leads run "
        "in opposite directions to the grid (IEEE Std 80, 9.6).",
        "Every conductor at a main earthing terminal shall be individually disconnectable, by a tool "
        "only (IEC 60364-5-54, 542.4.2).",
        "Fix the notice 'SAFETY ELECTRICAL CONNECTION — DO NOT REMOVE' at every connection of an "
        "earthing conductor to an earth electrode and at every main bonding connection "
        "(BS 7671, 514.13.1).",
        "Aluminium shall not be used for earthing conductors in contact with soil (IEC 60364-5-54, "
        "542.3.1).",
        "On completion measure the earth resistance by the fall-of-potential method (IEEE Std 81; "
        "BS 7430, Clause 10) and record continuity of every bond; the measured value shall not exceed "
        "the design value.",
    ]
    if ctx.grid:
        g = ctx.grid
        n.insert(5, f"Grid conductors buried {_f(g['h'] * 1000, 0)} mm below the native grade "
                    f"(IEEE Std 80, 9.4: typically 0.3 m to 0.5 m; IEC 62305-3, 5.4.3: ≥ 0.5 m for lightning "
                    f"earth electrodes).")
        if g.get("hs"):
            n.insert(6, f"Surface layer: crushed rock {_f(g['hs'] * 1000, 0)} mm thick, resistivity "
                        f"≥ {_f(g['rho_s'], 0)} Ω·m (wet), over the whole switchyard"
                        + (f" and 1 m beyond the fence" if ctx.fence else "") +
                        " (IEEE Std 80, 12.5).")
    if ctx.lps:
        n.append("Lightning protection: a test joint, openable only with a tool, on every "
                 "down-conductor (IEC 62305-3, 5.3.6).")
    return n


def legend_items(ctx):
    return [
        ("cond", f"EARTH CONDUCTOR, {ctx.cond_label}, BURIED"),
        ("rod", "EARTH ROD (DRIVEN)"),
        ("pit", "EARTH ROD IN INSPECTION PIT WITH TEST LINK"),
        ("joint", "BURIED JOINT — " + ("EXOTHERMIC WELD" if ctx.joint == "exothermic" else "COMPRESSION")),
        ("bolt", "BOLTED / MECHANICAL CONNECTION (ACCESSIBLE)"),
        ("riser", "EARTHING TAIL TO EQUIPMENT OR FENCE POST (IEC 60617 S00204)"),
        ("fence", "FENCE LINE; THE TRIANGLES MARK BONDED POSTS AND GATES"),
        ("dc", "LIGHTNING DOWN-CONDUCTOR WITH TEST JOINT"),
        ("earth", "EARTH, GENERAL SYMBOL (IEC 60617 S00200)"),
        ("pe", "PROTECTIVE EARTHING (IEC 60617 S00202)"),
        ("sec", "CUTTING PLANE A–A: SECTION A ON SHEET 102"),
    ]


def draw_legend_symbol(sh, kind, x, y):
    if kind == "cond":
        sh.line(x - 7, y, x + 7, y, "EARTH")
    elif kind == "rod":
        rod_symbol(sh, x, y)
    elif kind == "pit":
        pit_symbol(sh, x, y)
    elif kind == "joint":
        sh.line(x - 7, y, x + 7, y, "EARTH"); sh.line(x, y - 5, x, y + 5, "EARTH")
        sh.dot(x, y, 1.1, "EARTH")
    elif kind == "bolt":
        sh.line(x - 7, y, x - 1.2, y, "EARTH"); sh.line(x + 1.2, y, x + 7, y, "EARTH")
        sh.circle(x, y, 1.2, "OUTLINE")
    elif kind == "riser":
        # protective equipotential bonding, IEC 60617 S00204: the conductor
        # meets the middle of the base, the apex points away from it
        sh.line(x - 7, y, x - 1.4, y, "EARTH")
        sh.poly([(x - 1.4, y + 2.0), (x - 1.4, y - 2.0), (x + 2.1, y)], True, "OUTLINE")
    elif kind == "fence":
        sh.line(x - 7, y, x + 7, y, "FENCE")
    elif kind == "dc":
        sh.circle(x, y, 1.8, "OUTLINE"); sh.dot(x, y, 0.7, "OUTLINE")
        sh.text(x + 2.5, y + 1.5, "DC", 1.8)
    elif kind == "earth":
        earth_symbol(sh, x, y + 3, 0.8)
    elif kind == "pe":
        pe_symbol(sh, x, y, 0.8)
    elif kind == "sec":
        # cutting plane as drawn on the plan (ISO 128-3): thick ends, arrows
        # in the direction of view, the section letter at each end
        for sx_ in (-1, 1):
            q = (x + sx_ * 5.5, y - 1.2)
            sh.line(q[0], q[1], q[0] - sx_ * 2.5, q[1], "OUTLINE")
            sh.line(q[0], q[1], q[0], q[1] + 1.2, "OUTLINE")
            sh.arrow(q[0], q[1] + 3.0, 90, 1.8, 0.9, "OUTLINE")
        sh.text(x - 6.5, y - 1.2, "A", 2.5, "end", "middle", bold=True)
        sh.text(x + 6.5, y - 1.2, "A", 2.5, "start", "middle", bold=True)


def design_checks(ctx: Ctx):
    """Design-rule verification of what the drawings show, with the clause."""
    out = []

    def add(item, required, actual, ok, ref, level=None):
        out.append(dict(item=item, required=required, actual=actual,
                        status=level or ("OK" if ok else "FAIL"), ref=ref))

    c = ctx.S.get("conductor") or {}
    th = [v for v in ((c.get("ieee80") or {}).get("area_mm2"), (c.get("iec") or {}).get("area_mm2"))
          if isinstance(v, (int, float))]
    calc = max(th) if th else None
    dd_ = ELECTRODE_DUTY[ctx.duty]
    add("Buried bare copper electrode (" + dd_["label"] + ")", f"≥ {int(ctx.cond_min)} mm²",
        f"{ctx.cond} mm²", ctx.cond >= ctx.cond_min, dd_["ref"])
    if calc:
        add("Conductor thermal size (fault current)", f"≥ {_f(calc, 1)} mm² (IEEE 80 / IEC adiabatic)",
            f"{ctx.cond} mm²", ctx.cond >= calc - 1e-9, "IEEE Std 80 Eq. (37); IEC 60364-5-54 543.1.2")
    rm = ROD_MATERIALS[ctx.rod_mat]
    add("Earth rod diameter", f"≥ {_f(ctx.rod_min_d)} mm", f"{_f(ctx.rod_d, 1)} mm",
        ctx.rod_d >= ctx.rod_min_d - 1e-6, rm["std"])
    if ctx.rod_mat == "copper_bonded_steel":
        add("Copper coating of copper-bonded rods", "≥ 250 µm radial, 99.9 % Cu", "specified (note 4)", True,
            "EN 50522 Table C.1; IEC 62561-2 Table 3; BS 7430 9.10")
    if ctx.grid:
        g = ctx.grid
        h = g["h"]
        add("Grid burial depth", "0.3–0.5 m typical; ≥ 0.5 m if also the lightning earth",
            f"{_f(h)} m", h >= 0.5 or (h >= 0.3 and not ctx.lps_connected),
            "IEEE Std 80, 9.4 c); IEC 62305-3, 5.4.3",
            None if h >= 0.3 else "FAIL")
        # mesh aspect ratio
        xs = sorted({round(a[0], 3) for seg in g["conductors"] for a in seg if seg[0][0] == seg[1][0]})
        ys = sorted({round(a[1], 3) for seg in g["conductors"] for a in seg if seg[0][1] == seg[1][1]})
        dx = min((b - a for a, b in zip(xs, xs[1:])), default=g["D"])
        dy = min((b - a for a, b in zip(ys, ys[1:])), default=g["D"])
        ratio = max(dx, dy) / max(min(dx, dy), 1e-9)
        add("Mesh side ratio", "1:1 to 1:3", f"1:{_f(ratio, 2)}", ratio <= 3.0 + 1e-9,
            "IEEE Std 80, 9.4 e)")
        add("Grid spacing", "3–7 m typical", f"{_f(g['D'])} m", True, "IEEE Std 80, 9.4 c)",
            "OK" if 3 <= g["D"] <= 7 else "INFO")
        if g.get("hs"):
            add("Surface layer thickness", "0.08–0.15 m typical", f"{_f(g['hs'], 3)} m", True,
                "IEEE Std 80, 12.5", "OK" if 0.08 <= g["hs"] <= 0.15 + 1e-9 else "INFO")
        if g.get("Em") is not None and g.get("Et"):
            add("Mesh (touch) voltage", f"≤ {_f(g['Et'], 0)} V", f"{_f(g['Em'], 0)} V",
                g["Em"] <= g["Et"], "IEEE Std 80, Eq. (32)/(85)")
        if g.get("Es") is not None and g.get("Est"):
            add("Step voltage", f"≤ {_f(g['Est'], 0)} V", f"{_f(g['Es'], 0)} V", g["Es"] <= g["Est"],
                "IEEE Std 80, Eq. (29)/(97)")
        if g["n_rods"] >= 2:
            rs = g["rods"]
            dmin = min((math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(rs) for b in rs[i + 1:]),
                       default=0)
            add("Rod spacing vs rod length", "spacing ≥ rod length for full benefit",
                f"{_f(dmin)} m vs {_f(g['Lr'])} m", True, "BS 7430, 9.5.4 and Figure 14a",
                "OK" if dmin >= g["Lr"] else "INFO")
        if ctx.fence:
            add("Fence earthing", "perimeter conductor ≈ 1 m outside the fence, fence bonded to grid",
                f"fence {_f(ctx.fence_off)} m inside the perimeter conductor", ctx.fence_off >= 0.9,
                "IEEE Std 80, 17.3 (0.91 m case)", "OK" if 0.9 <= ctx.fence_off <= 1.5 else "INFO")
    if ctx.pit:
        p = ctx.pit
        add("Inspection housing load class", "to suit traffic at the location",
            f"class {ctx.housing} ({_f(p.get('load_kN') or {'L': 4, 'M': 15, 'H': 30}[ctx.housing])} kN test load)",
            True, "IEC 62561-5:2023, 4.1 and 6.4.2", "INFO")
    if ctx.lps:
        L = ctx.lps
        per = 2 * (L["W"] + L["D"])
        n_dc = max(4, int(math.ceil(per / L["table"]["down"])))
        add("Down-conductor spacing", f"≤ {L['table']['down']} m (class {L['cls']})",
            f"{n_dc} down-conductors, {_f(per / n_dc, 1)} m", per / n_dc <= L["table"]["down"] + 1e-9,
            "IEC 62305-3, 5.3.3 and Table 4")
        add("Test joint on each down-conductor", "one per down-conductor", f"{n_dc}", True,
            "IEC 62305-3, 5.3.6")
        add("Down-conductor / earth conductor (Cu)", "≥ 50 mm²", f"{max(50, ctx.cond if ctx.cond < 70 else 50)} mm²",
            True, "IEC 62305-3 Table 6 and Table 7")
        if L.get("re") and L.get("l1") is not None:
            add("Ring earth mean radius r_e", f"≥ l_1 = {_f(L['l1'], 1)} m or add electrodes",
                f"{_f(L['re'], 1)} m", True, "IEC 62305-3, 5.4.2.2 Eq. (1)–(3)",
                "OK" if L.get("radius_ok") else "INFO")
        add("Ring earth electrode position", "≥ 0.5 m deep, about 1 m from the walls",
            f"{_f(L['ring_depth'])} m deep, 1 m from walls", L["ring_depth"] >= 0.5, "IEC 62305-3, 5.4.3")
    # the verdicts of the calculation modules the drawings are built from
    S = ctx.S
    for key, name, ref in (("grid", "Substation grid design (module 4)", "IEEE Std 80-2013"),
                           ("bem", "Numerical analysis, governing values (module 5)",
                            "IEEE Std 80-2013, 16.6 and 17.3; module 5 studies"),
                           ("building", "Building earthing (module 6)", "IEC 60364-4-41 / -5-54"),
                           ("lightning", "Lightning earth termination (module 7)", "IEC 62305-3, 5.4"),
                           ("airterm", "Air-termination protection zone (module 8)", "IEC 62305-3, 5.2")):
        r = S.get(key)
        if r and "passed" in r:
            add(name, "all module checks met", "met" if r.get("passed") else "not met",
                bool(r.get("passed")), ref)
    add("Main earthing terminal", "each conductor disconnectable by tool", "bolted links (sheet 202)",
        True, "IEC 60364-5-54, 542.4.2")
    add("Main protective bonding conductor", "≥ 6 mm² Cu and ≥ half largest PE; need not exceed 25 mm²",
        "25 mm² Cu (max. required)" if ctx.building else "per chart, sheet 302", True,
        "IEC 60364-5-54, 544.1")
    add("Permanent connections", "qualified to IEEE Std 837 / IEC 62561-1", ctx.joint, True,
        "IEEE Std 80, 11.4")
    return out


def sheet_register(sh, fr, ctx, register):
    x0, y0, w, h = fr.area
    top = fr.ay1
    # --- drawing register (top left) ---
    sh.text(x0, top - 4, "DRAWING REGISTER", 3.5, bold=True)
    rows = [[r["number"], r["title"], r["rev"], r["scale"]] for r in register]
    wreg = min(150.0, w * 0.56)
    yb = table(sh, x0, top - 7, [30, wreg - 30 - 9 - 19, 9, 19], rows, ["DRAWING No.", "TITLE", "REV", "SCALE"],
               rh=4.8, h=2.0, aligns=["start", "start", "middle", "middle"], wrap_cols={1})
    # --- design basis (top right) ---
    xr = x0 + wreg + 6
    wr = fr.ax1 - xr
    sh.text(xr, top - 4, "DESIGN BASIS", 3.5, bold=True)
    data = []
    g = ctx.grid
    if g:
        data += [("Soil resistivity (uniform)", f"{_f(g['rho'], 1)} Ω·m"),
                 ("Surface layer", f"{_f(g['rho_s'], 0)} Ω·m, {_f((g['hs'] or 0) * 1000, 0)} mm"),
                 ("Grid current I_G / t_s", f"{_f(g['IG_kA'], 3)} kA / {_f(g['ts'], 2)} s"),
                 ("R_g / GPR", f"{_f(g['Rg'], 3)} Ω / {_f(g['GPR'], 0)} V"),
                 ("Touch E_m / tolerable", f"{_f(g['Em'], 0)} / {_f(g['Et'], 0)} V"),
                 ("Step E_s / tolerable", f"{_f(g['Es'], 0)} / {_f(g['Est'], 0)} V")]
    data.append(("Earth conductor", f"{ctx.cond} mm² Cu — {ctx.cond_basis}"))
    data.append(("Earth rods", f"Ø{_f(ctx.rod_d, 1)} mm × {_f(ctx.rod_L)} m ({ctx.rod_nsec} × "
                               f"{_f(ctx.rod_section)} m)"))
    if ctx.pit and ctx.pit.get("R_pit"):
        data.append(("Earth pit R (one / group)",
                     f"{_f(ctx.pit['R_pit'], 2)} / {_f(ctx.pit['R_group'], 2)} Ω"))
    if ctx.building:
        b = ctx.building
        data.append(("Building system / R_A", f"{b['system']} / {_f(b['RA'], 2)} Ω"))
    if ctx.lps:
        L = ctx.lps
        data.append(("LPS class / earth", f"{L['cls']} / {L['arrangement']}"
                     + (f", {_f(L['R'], 2)} Ω" if L.get("R") else "")))
    if ctx.ner and ctx.ner.get("R"):
        data.append(("Neutral earthing resistor", f"{_f(ctx.ner['R'], 2)} Ω, {_f(ctx.ner['I'], 0)} A, "
                                                    f"{_f(ctx.ner['t'], 0)} s"))
    yb2 = table(sh, xr, top - 7, [wr * 0.42, wr * 0.58], [[a, b] for a, b in data], None, rh=4.6, h=2.0,
                wrap_cols={1})
    # --- legend and abbreviations (middle band) ---
    yl = min(yb, yb2) - 7
    sh.text(x0, yl, "LEGEND", 3.5, bold=True)
    items = legend_items(ctx)
    half = (len(items) + 1) // 2
    colw = (w - 62) / 2
    for i, (kind, txt) in enumerate(items):
        cx = x0 + (i // half) * colw
        yy = yl - 7 - (i % half) * 7.4
        draw_legend_symbol(sh, kind, cx + 9, yy)
        tl = wrap(txt, colw - 24, 2.0)
        sh.mtext(cx + 20, yy + 1.0 + (len(tl) - 1) * 1.6, tl, 2.0, 1.2)
    xa = x0 + w - 60
    sh.text(xa, yl, "ABBREVIATIONS", 3.5, bold=True)
    ab = [("FGL", "finished ground level"), ("MET", "main earthing terminal"), ("TP", "test / inspection pit"),
          ("TL", "test link"), ("DC", "down-conductor"), ("TJ", "test joint"),
          ("NER", "neutral earthing resistor"), ("CPC", "circuit protective cond."), ("AR", "as required"),
          ("NTS", "not to scale")]
    for i, (k_, t) in enumerate(ab):
        sh.text(xa, yl - 6 - i * 4.0, k_, 2.0, bold=True)
        sh.text(xa + 11, yl - 6 - i * 4.0, t, 2.0)
    # --- verification (bottom, full width) ---
    yv = yl - 7 - half * 7.4 - 4
    sh.text(x0, yv, "DESIGN-RULE VERIFICATION OF THE DRAWINGS", 3.5, bold=True)
    checks = design_checks(ctx)
    rows = [[c["item"], c["required"], c["actual"], c["status"], c["ref"]] for c in checks]
    cw = [w * 0.22, w * 0.28, w * 0.20, 10, w * 0.30 - 10]
    table(sh, x0, yv - 3, cw, rows, ["ITEM", "REQUIRED", "DRAWN", "", "REFERENCE"], rh=4.0, h=1.75,
          aligns=["start", "start", "start", "middle", "start"], wrap_cols={0, 1, 2, 4})
    return checks


# ---------------------------------------------------------------------------
# sheet 101 — layout plan
# ---------------------------------------------------------------------------

def plate_outline(it):
    """Plan outline of a plate item (1.9.0): the four corners of a horizontal
    plate, the two ends of a vertical one."""
    a = math.radians(float(it.get("angle", 0) or 0))
    c, sn = math.cos(a), math.sin(a)
    x0, y0 = float(it.get("x0", 0)), float(it.get("y0", 0))
    if str(it.get("orientation", "horizontal")).lower().startswith("v"):
        L = float(it.get("length", 0))
        return [(x0, y0), (x0 + L * c, y0 + L * sn)]
    Lx, Ly = float(it.get("Lx", 0)), float(it.get("Ly", 0))
    return [(x0, y0), (x0 + Lx * c, y0 + Lx * sn),
            (x0 + Lx * c - Ly * sn, y0 + Lx * sn + Ly * c), (x0 - Ly * sn, y0 + Ly * c)]


def plan_extents(ctx):
    if ctx.grid:
        pts = [p for seg in ctx.grid["conductors"] for p in seg]
    else:
        pts = []
        for it in ctx.bem_items:
            k = it.get("kind")
            if k == "grid":
                x0, y0 = float(it.get("x0", 0)), float(it.get("y0", 0))
                pts += [(x0, y0), (x0 + float(it.get("Lx", 0)), y0 + float(it.get("Ly", 0)))]
            elif k in ("rectangle", "fence"):
                x0, y0 = float(it.get("x0", 0)), float(it.get("y0", 0))
                pts += [(x0, y0), (x0 + float(it.get("Lx", 0)), y0 + float(it.get("Ly", 0)))]
            elif k == "ring":
                cx, cy, r = float(it.get("cx", 0)), float(it.get("cy", 0)), float(it.get("r", 1))
                pts += [(cx - r, cy - r), (cx + r, cy + r)]
            elif k == "rod":
                pts.append((float(it.get("x", 0)), float(it.get("y", 0))))
            elif k == "conductor":
                pts += [tuple(it.get("p1", [0, 0])[:2]), tuple(it.get("p2", [0, 0])[:2])]
            elif k == "plate":
                pts += plate_outline(it)
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def bem_conductors(items):
    """Turn numerical-solver items into plan conductor segments and rods."""
    segs, rods, rings = [], [], []
    for it in items:
        k = it.get("kind")
        if k == "grid":
            x0, y0 = float(it.get("x0", 0)), float(it.get("y0", 0))
            Lx, Ly, D = float(it.get("Lx", 0)), float(it.get("Ly", 0)), float(it.get("D", 1))
            nx = max(1, int(round(Lx / D))); ny = max(1, int(round(Ly / D)))
            for i in range(nx + 1):
                x = x0 + Lx * i / nx; segs.append(((x, y0), (x, y0 + Ly)))
            for j in range(ny + 1):
                y = y0 + Ly * j / ny; segs.append(((x0, y), (x0 + Lx, y)))
        elif k == "rectangle":
            x0, y0 = float(it.get("x0", 0)), float(it.get("y0", 0))
            Lx, Ly = float(it.get("Lx", 0)), float(it.get("Ly", 0))
            c = [(x0, y0), (x0 + Lx, y0), (x0 + Lx, y0 + Ly), (x0, y0 + Ly)]
            segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
        elif k == "ring":
            cx, cy, r = float(it.get("cx", 0)), float(it.get("cy", 0)), float(it.get("r", 1))
            n = int(it.get("n_sides", 32))
            p = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
            rings.append(p)
            segs += [(p[i], p[(i + 1) % n]) for i in range(n)]
        elif k == "conductor":
            a, b = it.get("p1", [0, 0]), it.get("p2", [0, 0])
            segs.append(((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
        elif k == "rod":
            rods.append((float(it.get("x", 0)), float(it.get("y", 0))))
    return segs, rods


def sheet_plan(sh, fr, ctx):
    ext = plan_extents(ctx)
    if ctx.grid:
        segs, rods = ctx.grid["conductors"], ctx.grid["rods"]
    else:
        segs, rods = bem_conductors(ctx.bem_items)
    x0, y0, x1, y1 = ext
    fo = ctx.fence_off if ctx.fence else 0.0
    mx0, my0, mx1, my1 = x0 - fo - 1, y0 - fo - 1, x1 + 1, y1 + 1
    ax0, ay0, aw, ah = fr.area
    # leave room: axis bubbles + dimension chains (≈ 30 mm), tables below (≈ 62 mm)
    plan_w = aw - 52
    plan_h = ah - 104
    n = max(cad.nice_scale((mx1 - mx0) * 1000, plan_w), cad.nice_scale((my1 - my0) * 1000, plan_h))
    k = 1000.0 / n
    ox = ax0 + 34 + (plan_w - (mx1 - mx0) * k) / 2
    oy = ay0 + 88 + (plan_h - (my1 - my0) * k) / 2
    v = sh.view(ox, oy, n, mx0, my0, 1000.0)

    # fence: inside the perimeter conductor by fence_off (IEEE 80, 17.3)
    if ctx.fence and ctx.grid:
        fpoly = offset_orthogonal(ctx.grid["outline"], ctx.fence_off)
        v.poly(fpoly, True, "FENCE")
        # gate in the middle of the lowest edge
        edges = [(fpoly[i], fpoly[(i + 1) % len(fpoly)]) for i in range(len(fpoly))]
        bot = min((e for e in edges if abs(e[0][1] - e[1][1]) < 1e-9), key=lambda e: (e[0][1], -abs(e[1][0] - e[0][0])))
        ex0, ex1 = sorted((bot[0][0], bot[1][0]))
        fy0 = bot[0][1]
        gw = min(6.0, (ex1 - ex0) / 4)
        gx = (ex0 + ex1) / 2
        p0, p1 = v.P(gx - gw / 2, fy0), v.P(gx + gw / 2, fy0)
        sh.text((p0[0] + p1[0]) / 2, p0[1] + 2, "GATE", 2.0, "middle")
        for (bx, by) in list(fpoly) + [(gx - gw / 2, fy0), (gx + gw / 2, fy0)]:
            p = v.P(bx, by)
            sh.poly([(p[0] - 1.4, p[1] + 1.2), (p[0] + 1.4, p[1] + 1.2), (p[0], p[1] - 1.2)], True, "OUTLINE")
        right = max((e for e in edges if abs(e[0][0] - e[1][0]) < 1e-9), key=lambda e: (e[0][0], abs(e[1][1] - e[0][1])))
        ya, yb2 = sorted((right[0][1], right[1][1]))
        # keep clear of flag 3, which marks the middle rod of the right edge
        rr = [r for r in rods if abs(r[0] - x1) < 1e-6 and y0 < r[1] < y1] or rods
        ry = rr[len(rr) // 2][1] if rr else None
        fy = max((ya + (yb2 - ya) * f for f in (0.62, 0.3, 0.82)),
                 key=lambda t: 1e9 if ry is None else min(abs(t - ry), 0.18 * (yb2 - ya) + 1e-9))
        pf = v.P(right[0][0], fy)
        flag(sh, pf[0] - 6, pf[1] + 4, 6, pf[0], pf[1])
    for it in ctx.bem_items:
        if it.get("kind") == "fence" and "path" not in it:
            fx0, fy0 = float(it.get("x0", 0)), float(it.get("y0", 0))
            fx1, fy1 = fx0 + float(it.get("Lx", 0)), fy0 + float(it.get("Ly", 0))
            v.poly([(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)], True, "FENCE")
    # plates (1.9.0): outline in plan, not conductor (no joints, not in the bill of conductor)
    for it in ctx.bem_items:
        if it.get("kind") == "plate":
            c = plate_outline(it)
            if len(c) > 2:
                v.poly(c, True, "EARTH")
            else:
                v.line(c[0][0], c[0][1], c[1][0], c[1][1], "EARTH")
    # conductors
    for a, b in segs:
        v.line(a[0], a[1], b[0], b[1], "EARTH")
    # joints
    J = grid_joints(segs, rods)
    for kind in ("X", "T", "L"):
        for p in J[kind]:
            q = v.P(*p)
            sh.dot(q[0], q[1], 0.75, "EARTH")
    # rods and test pits (corners first)
    pits = set()
    outline = ctx.grid["outline"] if ctx.grid else None
    if rods and ctx.n_test_pits:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        # the outer (convex) corners of the outline first, then the furthest rods
        convex = set()
        if outline:
            m = len(outline)
            ar = sum(outline[i][0] * outline[(i + 1) % m][1] - outline[(i + 1) % m][0] * outline[i][1]
                     for i in range(m))
            for i in range(m):
                a, b, c = outline[i - 1], outline[i], outline[(i + 1) % m]
                cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
                if cr * ar > 0:                 # turns the same way as the outline: convex
                    convex.add((round(b[0], 6), round(b[1], 6)))
        order = sorted(range(len(rods)), key=lambda i: ((round(rods[i][0], 6), round(rods[i][1], 6)) not in convex,
                                                        -math.hypot(rods[i][0] - cx, rods[i][1] - cy)))
        pits = set(order[:ctx.n_test_pits])
    for i, r in enumerate(rods):
        q = v.P(*r)
        if i in pits:
            pit_symbol(sh, q[0], q[1], 2.2)
        else:
            rod_symbol(sh, q[0], q[1], 1.5)
    # rod tags (outside the grid where possible)
    for i, r in enumerate(rods):
        q = v.P(*r)
        dx = -1 if r[0] <= (x0 + x1) / 2 else 1
        dy = -1 if r[1] <= (y0 + y1) / 2 else 1
        on_edge_x = abs(r[0] - x0) < 1e-6 or abs(r[0] - x1) < 1e-6
        nv = outward_normal(outline, r) if outline else None
        if nv:
            # tag on the outside of the outline: across a vertical edge, beside it;
            # on a horizontal edge, above or below it
            if abs(nv[0]) > 0.3:
                dx = 1 if nv[0] > 0 else -1
                on_edge_x = True
            if abs(nv[1]) > 0.3:
                dy = 1 if nv[1] > 0 else -1
        tx = q[0] + dx * (3.6 if on_edge_x else 2.6)
        ty = q[1] + dy * 3.4
        # a rod on a vertical edge but between two conductor rows: tag beside it,
        # where no axis line or conductor runs
        if nv and abs(nv[0]) > 0.3 and abs(nv[1]) <= 0.3 and ctx.grid:
            rows_y = {round(a_[1], 4) for a_, b_ in segs if abs(a_[1] - b_[1]) < 1e-9}
            if all(abs(r[1] - yy) > 1e-6 for yy in rows_y):
                ty = q[1]
        sh.text(tx, ty, f"{'TP' if i in pits else 'R'}{i + 1}", 1.9, "start" if dx > 0 else "end", "middle")
    # grid axis bubbles (structural style) and dimension chains
    if ctx.grid:
        vlines, hlines = {}, {}
        for a_, b_ in segs:
            if abs(a_[0] - b_[0]) < 1e-9:
                lo, hi = sorted((a_[1], b_[1]))
                k_ = round(a_[0], 4)
                o = vlines.get(k_, (hi, lo))
                vlines[k_] = (min(o[0], lo), max(o[1], hi))
            elif abs(a_[1] - b_[1]) < 1e-9:
                lo, hi = sorted((a_[0], b_[0]))
                k_ = round(a_[1], 4)
                o = hlines.get(k_, (hi, lo))
                hlines[k_] = (min(o[0], lo), max(o[1], hi))
        xs, ys = sorted(vlines), sorted(hlines)
        top_y = v.P(0, my1)[1] + 9
        for i, xg in enumerate(xs):
            p = v.P(xg, vlines[xg][1])
            sh.line(p[0], p[1] + 1, p[0], top_y - 3, "CENTRE")
            sh.circle(p[0], top_y, 3.0, "THIN")
            sh.text(p[0], top_y, str(i + 1), 2.2, "middle", "middle")
        lx = v.P(mx0, 0)[0] - 11
        for j, yg in enumerate(ys):
            p = v.P(hlines[yg][0], yg)
            sh.line(p[0] - 1, p[1], lx + 3, p[1], "CENTRE")
            sh.circle(lx, p[1], 3.0, "THIN")
            sh.text(lx, p[1], "ABCDEFGHJKLMNPQRSTUVWXYZ"[j % 24] + ("" if j < 24 else str(j // 24)),
                    2.2, "middle", "middle")
        yb = v.P(0, my0)[1] - 6
        if len(xs) > 1:
            for a_, b_ in zip(xs, xs[1:]):
                pa, pb = v.P(a_, y0), v.P(b_, y0)
                sh.dim(pa[0], yb, pb[0], yb, 0, f"{_f(b_ - a_)}", h=1.9, ext=False, tpos="chain")
            for xg in xs:
                p = v.P(xg, vlines[xg][0])
                y_from = p[1] - 1 if vlines[xg][0] <= y0 + 1e-6 else yb + 2.5
                sh.line(p[0], y_from, p[0], yb - 1.5, "DIM")
            pa, pb = v.P(x0, y0), v.P(x1, y0)
            sh.dim(pa[0], yb - 8, pb[0], yb - 8, 0, f"{_f(x1 - x0)} m", h=2.2, ext=False)
            sh.line(pa[0], yb - 1.5, pa[0], yb - 9.5, "DIM"); sh.line(pb[0], yb - 1.5, pb[0], yb - 9.5, "DIM")
        xr = v.P(mx1, 0)[0] + 10
        if len(ys) > 1:
            for a_, b_ in zip(ys, ys[1:]):
                pa, pb = v.P(x1, a_), v.P(x1, b_)
                sh.dim(xr, pa[1], xr, pb[1], 0, f"{_f(b_ - a_)}", h=1.9, ext=False, tpos="chain")
            for yg in ys:
                p = v.P(hlines[yg][1], yg)
                # a row that stops short of the right edge (L or T grid) gets a
                # short tick at the chain, never a line across the empty notch
                x_from = p[0] + 1 if hlines[yg][1] >= x1 - 1e-6 else xr - 2.5
                sh.line(x_from, p[1], xr + 1.5, p[1], "DIM")
            pa, pb = v.P(x1, y0), v.P(x1, y1)
            sh.dim(xr + 8, pa[1], xr + 8, pb[1], 0, f"{_f(y1 - y0)} m", h=2.2, ext=False)
            sh.line(xr + 1.5, pa[1], xr + 9.5, pa[1], "DIM"); sh.line(xr + 1.5, pb[1], xr + 9.5, pb[1], "DIM")
        # notch dimensions of an L- or T-shaped grid
        nt = ctx.grid.get("notch")
        if nt:
            olp = ctx.grid["outline"]
            inner = [q for q in olp if x0 + 1e-6 < q[0] < x1 - 1e-6 and y0 + 1e-6 < q[1] < y1 - 1e-6]
            for (qx, qy) in inner[:1]:
                # horizontal and vertical extent of the notch, measured from its re-entrant corner
                ex = x1 if abs(qx - (x1 - nt["a"])) < 1e-6 else x0
                ey = y1 if abs(qy - (y1 - nt["b"])) < 1e-6 else y0
                pa, pb = v.P(qx, qy), v.P(ex, qy)
                sh.dim(pa[0], pa[1], pb[0], pb[1], 9 if ey > qy else -9, f"{_f(abs(ex - qx))}", h=2.2)
                pa, pb = v.P(qx, qy), v.P(qx, ey)
                sh.dim(pa[0], pa[1], pb[0], pb[1], -12 if ex > qx else 12, f"{_f(abs(ey - qy))}", h=2.2)
    # flag notes: conductor (2), rods (3) — set inside a mesh, clear of the tags
    if segs:
        vert = [sg for sg in segs if abs(sg[0][0] - sg[1][0]) < 1e-9]
        sg = sorted(vert, key=lambda t: t[0][0])[min(1, len(vert) - 1)] if vert else segs[0]
        ym = sg[0][1] + (sg[1][1] - sg[0][1]) * 0.5
        q = v.P(sg[0][0], ym)
        flag(sh, q[0] + 5.5, q[1] + 4.5, 2, q[0], q[1])
    if rods:
        right = [r for r in rods if abs(r[0] - x1) < 1e-6 and y0 < r[1] < y1] or rods
        r0 = right[len(right) // 2]
        q = v.P(*r0)
        flag(sh, q[0] - 6.5, q[1] + 5.0, 3, q[0] - 1.1, q[1] + 1.1)
    # section marker A–A, cutting the first vertical conductor at mid-length
    if segs and ctx.grid:
        vert = sorted((sg for sg in segs if abs(sg[0][0] - sg[1][0]) < 1e-9), key=lambda t: (t[0][0], -abs(t[1][1] - t[0][1])))
        if len(vert) >= 2:
            dxs = sorted({round(t[0][0], 4) for t in vert})
            x2nd = dxs[1] if len(dxs) > 1 else dxs[0]
            sg = max((t for t in vert if abs(t[0][0] - x2nd) < 1e-6), key=lambda t: abs(t[1][1] - t[0][1]))
            xa = sg[0][0]
            step = (dxs[1] - dxs[0]) if len(dxs) > 1 else 5.0
            yc = min(sg[0][1], sg[1][1]) + abs(sg[1][1] - sg[0][1]) * 0.42
            # cut through the middle of a mesh, clear of the crossings and rod tags
            hy = sorted({round(t[0][1], 4) for t in segs if abs(t[0][1] - t[1][1]) < 1e-9
                         and min(t[0][0], t[1][0]) - 1e-6 <= xa <= max(t[0][0], t[1][0]) + 1e-6})
            mids = [(a + b) / 2 for a, b in zip(hy, hy[1:])]
            if mids:
                yc = min(mids, key=lambda m: abs(m - yc))
            pL, pR = v.P(xa - 0.45 * step, yc), v.P(xa + 0.45 * step, yc)
            sh.line(pL[0], pL[1], pL[0] + 3, pL[1], "OUTLINE")
            sh.line(pR[0] - 3, pR[1], pR[0], pR[1], "OUTLINE")
            for q in (pL, pR):
                sh.line(q[0], q[1], q[0], q[1] + 1.5, "OUTLINE")
                sh.arrow(q[0], q[1] + 3.5, 90, 2.0, 1.0, "OUTLINE")
            sh.text(pL[0] - 1.2, pL[1] - 1, "A", 3.5, "end", "middle", bold=True)
            sh.text(pR[0] + 1.2, pR[1] - 1, "A", 3.5, "start", "middle", bold=True)

    # north arrow and scale bar
    north_arrow(sh, fr.ax1 - 10, fr.ay1 - 12)
    # bottom band: rod schedule, design data, scale bar
    yt = ay0 + 58
    pc = v.P((mx0 + mx1) / 2, my0)
    sh.title_label(pc[0], ay0 + 70.5, "EARTH GRID LAYOUT PLAN", f"SCALE 1:{n}")
    # rod schedule: 11 rows a column, up to three columns; every rod is also
    # written to rod_schedule.csv in the drawing-set ZIP
    rows = []
    for i, r in enumerate(rods):
        rows.append([f"{'TP' if i in pits else 'R'}{i + 1}", _f(r[0]), _f(r[1]),
                     _f(ctx.rod_L), "YES" if i in pits else "—"])
    ctx.rod_schedule = rows
    PER, CW = 11, 66.0
    ncol = min(3, max(1, int(math.ceil(len(rows) / PER)))) if rows else 0
    xx = ax0 + 92
    if ncol == 3:
        xx = max(ax0 + 8, fr.ax1 - 4 - 3 * CW)
        scale_bar(sh, ax0 + 8, fr.ay1 - 10, n)      # bottom band is full: scale bar top left
    else:
        scale_bar(sh, ax0 + 8, ay0 + 52, n)
    if rows:
        sh.text(xx, yt + 2, "EARTH ROD SCHEDULE (CO-ORDINATES FROM GRID ORIGIN, m)", 2.5, bold=True)
        for c in range(ncol):
            part = rows[c * PER:(c + 1) * PER]
            if part:
                table(sh, xx + c * CW, yt - 1, [11, 14, 14, 13, 12], part,
                      ["ROD", "X", "Y", "L (m)", "PIT"], rh=4.2, h=1.8,
                      aligns=["middle"] * 5)
        if len(rows) > ncol * PER:
            sh.text(xx, ay0 + 1, f"{ncol * PER} of {len(rows)} rods shown; the complete schedule is "
                                 f"rod_schedule.csv in the drawing-set ZIP.", 1.8)
    return n


# ---------------------------------------------------------------------------
# detail drawings (model in millimetres)
# ---------------------------------------------------------------------------

def _fit(box, ext_w, ext_h, title_h=12.0, pad=8.0, nts=False):
    """Pick a preferred scale for a detail of model size ext (mm) in a box."""
    x, y, w, h = box
    n = max(cad.nice_scale(ext_w, w - 2 * pad), cad.nice_scale(ext_h, h - title_h - 2 * pad))
    return n


class Detail:
    """One scaled detail in a cell: picks the preferred scale that fits the
    model box, centres it, and sets the annotation in callout columns beside
    the drawing so that no text runs over the linework or out of the cell."""

    TH = 2.5        # callout lettering (IEC 61082-1, 5.11)
    GAP = 1.2

    def __init__(self, sh, box, bbox, title, left=0.0, right=48.0, pad=3.0, title_h=15.0,
                 scale=None, sub=None, nts=False):
        x, y, w, h = box
        mx0, my0, mx1, my1 = bbox
        bw, bh = mx1 - mx0, my1 - my0
        aw = w - left - right - 2 * pad
        ah = h - title_h - 2 * pad
        if scale:
            n = scale
        elif nts:
            n = max(bw / aw, bh / ah)
        else:
            n = max(cad.nice_scale(bw, aw), cad.nice_scale(bh, ah))
        k = 1.0 / n
        ox = x + left + pad + (aw - bw * k) / 2
        oy = y + title_h + pad + (ah - bh * k) / 2
        self.sh, self.box, self.n, self.title, self.sub, self.nts = sh, box, n, title, sub, nts
        self.v = sh.view(ox, oy, n, mx0, my0, 1.0)
        self.dx0, self.dx1, self.dy0, self.dy1 = ox, ox + bw * k, oy, oy + bh * k
        self.left, self.right = left, right
        self.notes = []

    def P(self, x, y):
        return self.v.P(x, y)

    def note(self, mx, my, text, side="right", head="arrow", balloon=None):
        lines = text if isinstance(text, list) else ([] if text is None else [text])
        self.notes.append((side, self.v.P(mx, my), lines, head, balloon))

    def finish(self):
        sh = self.sh
        x, y, w, h = self.box
        top, bot = y + h - 3, y + 16
        for side in ("left", "right"):
            items = [it for it in self.notes if it[0] == side]
            if not items:
                continue
            if side == "right":
                c0 = max(self.dx1 + 6, x + w - self.right)
                c1 = x + w - 2
            else:
                c0 = x + 2
                c1 = min(self.dx0 - 6, x + self.left)
            cw = c1 - c0 - 4
            blocks = []
            for (_, p, lines, head, bal) in items:
                if bal is not None:
                    blocks.append([p, None, 5.4, head, bal])
                else:
                    wl = [w_ for ln in lines for w_ in wrap(ln, cw, self.TH)]
                    hb = len(wl) * self.TH + (len(wl) - 1) * self.GAP
                    blocks.append([p, wl, hb, head, None])
            blocks.sort(key=lambda b: -b[0][1])
            # greedy top-down placement at the feature height, then lift if needed
            cur = top
            ys = []
            for b in blocks:
                c = min(b[0][1], cur - b[2] / 2)
                ys.append(c)
                cur = c - b[2] / 2 - 2.6
            over = bot - (ys[-1] - blocks[-1][2] / 2) if ys else 0
            if over > 0:
                ys = [min(top - blocks[i][2] / 2, yv + over) for i, yv in enumerate(ys)]
                # re-run downwards to keep the order and spacing
                cur = top
                for i, b in enumerate(blocks):
                    ys[i] = min(ys[i], cur - b[2] / 2)
                    cur = ys[i] - b[2] / 2 - 2.6
            for b, yc in zip(blocks, ys):
                p, wl, hb, head, bal = b
                if side == "right":
                    xl0, xl1 = c0, c0 + 2.0
                else:
                    xl0, xl1 = c1, c1 - 2.0
                sh.line(p[0], p[1], xl0, yc, "DIM")
                if head == "arrow":
                    sh.arrow(p[0], p[1], math.degrees(math.atan2(p[1] - yc, p[0] - xl0)), 2.2, 0.8)
                elif head == "dot":
                    sh.dot(p[0], p[1], 0.45, "DIM")
                if bal is not None:
                    bx = xl0 + (2.7 if side == "right" else -2.7)
                    sh.balloon(bx, yc, bal, r=2.7, h=2.2)
                    continue
                sh.line(xl0, yc, xl1, yc, "DIM")
                yy = yc + hb / 2
                for ln in wl:
                    yy -= self.TH
                    if side == "right":
                        sh.text(xl1 + 0.8, yy, ln, self.TH)
                    else:
                        sh.text(xl1 - 0.8, yy, ln, self.TH, "end")
                    yy -= self.GAP
        sub = self.sub or ("NOT TO SCALE" if self.nts else f"SCALE 1:{self.n}")
        sh.title_label(x + w / 2, y + 9.5, self.title, sub, maxw=w - 6)


def _fgl(d, x0, x1, z=0.0, label=True):
    d.v.line(x0, z, x1, z, "OUTLINE")
    if label:
        p = d.P(x0, z)
        d.sh.text(p[0] + 0.5, p[1] + 1.2, "FGL", 2.0)


def det_trench(sh, box, ctx, no):
    """Typical trench section for a grid conductor (Section A)."""
    g = ctx.grid or {}
    h = (g.get("h") or 0.5) * 1000
    hs = (g.get("hs") or 0) * 1000
    tw = 300.0
    W = 900.0
    Hm = hs + h + 220
    zc = -hs - h
    od = ctx.cond_od
    zb = zc - od / 2
    d = Detail(sh, box, (-60, -Hm - 30, W, 120), f"SECTION A  GRID CONDUCTOR TRENCH", left=20, right=42)
    v = d.v
    tx0, tx1 = W / 2 - tw / 2, W / 2 + tw / 2
    if hs > 0:
        v.pattern([[(0, 0), (W, 0), (W, -hs), (0, -hs)]], "crushed", 1.0, seed=2)
        v.line(0, -hs, W, -hs, "THIN")
    v.pattern([[(0, -hs), (tx0, -hs), (tx0, -Hm), (0, -Hm)]], "soil", 1.0)
    v.pattern([[(tx1, -hs), (W, -hs), (W, -Hm), (tx1, -Hm)]], "soil", 1.0)
    v.pattern([[(tx0, zb), (tx1, zb), (tx1, -Hm), (tx0, -Hm)]], "soil", 1.0)
    v.pattern([[(tx0, -hs), (tx1, -hs), (tx1, zb), (tx0, zb)]], "backfill", 1.0, seed=4)
    v.poly([(tx0, -hs), (tx0, zb), (tx1, zb), (tx1, -hs)], False, "OUTLINE")
    _fgl(d, -60, W)
    sh.break_line(*v.P(0, 30), *v.P(0, -Hm - 10))
    sh.break_line(*v.P(W, 30), *v.P(W, -Hm - 10))
    v.circle(W / 2, zc, max(od / 2, 0.8 * d.n), "EARTH", fill=True)
    # dimensions: trench width under the section, depths at the left
    v.dim(tx0, zb, tx1, zb, -((zb + Hm) / d.n + 5), "≥ 300")
    xd = tx0 - 120                  # clear of the break line at the section edge
    pc = v.P(W / 2 - od, zc)
    sh.line(pc[0], pc[1], v.P(xd, zc)[0] - 1.5, pc[1], "DIM")
    if hs > 0:
        v.dim(xd, 0, xd, -hs, 0, f"{_f(hs, 0)}", tpos="start")
        v.dim(xd, -hs, xd, zc, 0, f"{_f(h, 0)}")
    else:
        v.dim(xd, 0, xd, zc, 0, f"{_f(h, 0)}")
    if hs > 0:
        d.note(W - 100, -hs / 2, [f"CRUSHED ROCK {_f(hs, 0)} mm,", f"ρ_s ≥ {_f(g.get('rho_s'), 0)} Ω·m WET"])
    d.note(W / 2 + 60, -hs - h * 0.45, ["SELECTED FINE SOIL, STONE-FREE,", "COMPACTED IN 150 mm LAYERS"])
    d.note(W / 2 + od * 0.4, zc + od * 0.3, [ctx.cond_label], head="dot")
    d.note(W - 80, -Hm + 60, ["UNDISTURBED SOIL"], head="dot")
    d.finish()


def det_rod(sh, box, ctx, no):
    """Driven earth rod connected to the grid, with a break in the length."""
    g = ctx.grid or {}
    h = (g.get("h") or 0.6) * 1000
    hs = (g.get("hs") or 0) * 1000
    dd = ctx.rod_d
    od = ctx.cond_od
    zc = -hs - h
    W = 700.0
    shown_top, shown_bot = 700.0, 350.0
    # first pass for the scale, assuming a 160 mm (paper 8 mm at 1:20) gap
    est = hs + h + shown_top + 160 + shown_bot + 120
    n = Detail(Sheet(sh.size), box, (-80, -est, W, 80), "", left=26, right=44).n
    gap = 8.0 * n
    z1 = zc - shown_top
    z2 = z1 - gap
    ztip = z2 - shown_bot
    d = Detail(sh, box, (-80, ztip - 60, W, 80), f"DETAIL {no}  DRIVEN EARTH ROD AT GRID", left=26,
               right=44, scale=n)
    v = d.v
    cx = W / 2
    if hs > 0:
        v.pattern([[(0, 0), (W, 0), (W, -hs), (0, -hs)]], "crushed", 1.0, seed=3)
        v.line(0, -hs, W, -hs, "THIN")
    _fgl(d, -80, W)
    for (za, zb_) in ((-hs, z1), (z2, ztip - 60)):
        v.pattern([[(0, za), (cx - dd / 2 - 3, za), (cx - dd / 2 - 3, zb_), (0, zb_)]], "soil")
        v.pattern([[(cx + dd / 2 + 3, za), (W, za), (W, zb_), (cx + dd / 2 + 3, zb_)]], "soil")
    sh.break_line(*v.P(0, 30), *v.P(0, z1))
    sh.break_line(*v.P(W, 30), *v.P(W, z1))
    # rod: upper part
    v.line(cx - dd / 2, zc, cx - dd / 2, z1, "OUTLINE")
    v.line(cx + dd / 2, zc, cx + dd / 2, z1, "OUTLINE")
    v.line(cx, zc + 60, cx, ztip - 40, "CENTRE")
    sec = ctx.rod_section * 1000
    if ctx.rod_nsec > 1 and sec < shown_top - 80:
        v.rect(cx - dd, zc - sec - 45, 2 * dd, 90, "OUTLINE")
        d.note(cx + dd, zc - sec, ["THREADED COUPLING, SILICON OR", "ALUMINIUM BRONZE ≥ 75 % Cu"])
    # break across the rod
    for zz in (z1, z2):
        sh.break_line(*v.P(cx - 60, zz), *v.P(cx + 60, zz))
    # lower part with the point
    v.poly([(cx - dd / 2, z2), (cx - dd / 2, ztip + 2.5 * dd), (cx, ztip), (cx + dd / 2, ztip + 2.5 * dd),
            (cx + dd / 2, z2)], False, "OUTLINE")
    if ctx.rod_nsec > 1:
        v.rect(cx - dd, z2 - 120 - 45, 2 * dd, 90, "OUTLINE")
    # grid conductor (side elevation) across the rod top, and the joint body
    v.rect(40, zc, W - 80, od, "EARTH")
    bw = max(dd * 3.5, 80)
    body = [(cx - bw / 2, zc - 50), (cx + bw / 2, zc - 50), (cx + bw / 2 + 12, zc + od + 25),
            (cx - bw / 2 - 12, zc + od + 25)]
    v.poly(body, True, "OUTLINE")
    v.hatch([body], 45, 1.0)
    # dimensions on the left
    xd = 60
    pz = v.P(cx - bw / 2 - 12, zc)
    sh.line(pz[0] - 1, pz[1], v.P(xd, zc)[0] - 1.5, pz[1], "DIM")
    v.dim(xd, 0, xd, zc, 0, f"{_f(h + hs, 0)}")
    pa, pb = v.P(xd, zc), v.P(xd, ztip)
    sh.dim(pa[0] - 6, pa[1], pb[0] - 6, pb[1], 0, f"L = {_f(ctx.rod_L)} m ({ctx.rod_nsec} × {_f(ctx.rod_section)} m)",
           ext=False)
    sh.line(pa[0] - 1.5, pa[1], pa[0] - 7.5, pa[1], "DIM")
    pt = v.P(cx, ztip)
    sh.line(pt[0] - 1, pt[1], pb[0] - 7.5, pt[1], "DIM")
    d.note(cx + bw / 2, zc + od / 2, [ctx.joint_name("R") + ";", "ROD TOP AT GRID DEPTH"])
    d.note(cx + dd / 2, zc - shown_top * 0.55, [ROD_MATERIALS[ctx.rod_mat]["label"],
                                                 f"Ø{_f(dd, 1)} mm, DRIVEN VERTICALLY"])
    d.note(W - 60, zc + od / 2, [f"GRID CONDUCTOR {ctx.cond} mm² Cu"], head="dot")
    d.finish()


def det_riser(sh, box, ctx, no):
    """Equipment earthing riser through a PVC sleeve beside a concrete plinth."""
    g = ctx.grid or {}
    h = (g.get("h") or 0.5) * 1000
    hs = (g.get("hs") or 0) * 1000
    od = ctx.cond_od
    zc = -hs - h
    px0, px1 = 520.0, 880.0
    d = Detail(sh, box, (-160, zc - 120, px1 + 10, 360), f"DETAIL {no}  EQUIPMENT EARTHING RISER",
               left=30, right=34, pad=1.5)
    v = d.v
    # plinth, base frame, earth pad
    v.pattern([[(px0, -500), (px1, -500), (px1, 200), (px0, 200)]], "concrete", 1.0, seed=5)
    v.rect(px0, -500, px1 - px0, 700, "OUTLINE")
    frame = [(px0 + 60, 200), (px1 + 10, 200), (px1 + 10, 260), (px0 + 60, 260)]
    v.poly(frame, True, "OUTLINE"); v.hatch([frame], 45, 1.0)
    pad_ = [(px0 + 10, 210), (px0 + 60, 210), (px0 + 60, 250), (px0 + 10, 250)]
    v.poly(pad_, True, "OUTLINE")
    # ground
    if hs > 0:
        v.pattern([[(-120, 0), (px0, 0), (px0, -hs), (-120, -hs)]], "crushed", seed=6)
        v.line(-120, -hs, px0, -hs, "THIN")
    v.pattern([[(-120, -hs), (px0 - 4, -hs), (px0 - 4, zc - 100), (-120, zc - 100)]], "soil")
    _fgl(d, -160, px0)
    sh.break_line(*v.P(-120, 40), *v.P(-120, zc - 100))
    # riser: grid conductor (end-on) → tee → up the sleeve → over the plinth → lug
    rx = px0 - 150
    v.circle(rx - 260, zc, max(od / 2, 0.8 * d.n), "EARTH", fill=True)
    v.line(rx - 260, zc, rx, zc, "EARTH")
    v.poly([(rx, zc), (rx, 330), (px0 - 40, 330), (px0 + 10, 230)], False, "EARTH")
    tee = [(rx - 40, zc - 30), (rx + 40, zc - 30), (rx + 40, zc + 60), (rx - 40, zc + 60)]
    v.poly(tee, True, "OUTLINE"); v.hatch([tee], 45, 0.8)
    sl = 50.0
    v.rect(rx - sl / 2, -300, sl, 450, "OUTLINE")
    seal = [(rx - sl / 2, 110), (rx + sl / 2, 110), (rx + sl / 2, 150), (rx - sl / 2, 150)]
    v.hatch([seal], -45, 0.7)
    lug = [(px0 + 12, 222), (px0 + 52, 222), (px0 + 52, 238), (px0 + 12, 238)]
    v.poly(lug, True, "OUTLINE")
    # dimensions
    xq = rx - sl / 2 - 140
    v.dim(xq, 0, xq, 150, 0, "≥ 150", tpos="end")
    v.dim(xq, 0, xq, -300, 0, "≥ 300")
    sh.line(*v.P(rx - sl / 2, 150), v.P(xq, 0)[0] - 1.5, v.P(0, 150)[1], "DIM")
    sh.line(*v.P(rx - sl / 2, -300), v.P(xq, 0)[0] - 1.5, v.P(0, -300)[1], "DIM")
    v.dim(rx - 330, 0, rx - 330, zc, 0, f"{_f(h + hs, 0)}")
    sh.line(*v.P(rx - 260, zc), v.P(rx - 330, 0)[0] + 1.5, v.P(0, zc)[1], "DIM")
    d.note(rx + sl / 2, 130, ["SEAL WITH NON-HARDENING", "COMPOUND"])
    d.note(rx + sl / 2, -150, ["PVC SLEEVE Ø50 mm"])
    d.note(rx - 40, zc + 20, [ctx.joint_name("T")], side="left")
    d.note(px0 + 32, 238, ["TWO-HOLE LUG, 2 × " + ctx.met_bolt, "STAINLESS (DETAIL 9/301)"])
    d.note(px1 - 60, 230, ["EQUIPMENT BASE FRAME"], head="dot")
    d.note(px1 - 100, -250, ["CONCRETE PLINTH"], head="dot")
    sh.break_line(*v.P(px1, -520), *v.P(px1, 280))
    d.finish()


def det_fence(sh, box, ctx, no):
    """Section across the fence line: perimeter conductor outside (IEEE 80, 17.3)."""
    g = ctx.grid or {}
    h = (g.get("h") or 0.5) * 1000
    hs = (g.get("hs") or 0) * 1000
    off = ctx.fence_off * 1000
    od = ctx.cond_od
    zc = -hs - h
    fx = 700.0
    gx = fx + off
    xi = fx - 550.0                 # a grid conductor inside the fence
    ext = fx + 1000.0               # surface layer extends 1 m outside the fence
    W = max(gx, ext) + 350
    Hp = 1100.0                     # post drawn to this height, then broken
    d = Detail(sh, box, (-40, zc - 330, W, Hp + 260), f"DETAIL {no}  FENCE EARTHING", left=30, right=40)
    v = d.v
    if hs > 0:
        v.pattern([[(0, 0), (ext, 0), (ext, -hs), (0, -hs)]], "crushed", seed=8)
        v.poly([(0, -hs), (ext, -hs), (ext, 0)], False, "THIN")
    gl = -hs if hs else 0.0
    v.pattern([[(0, gl), (fx - 160, gl), (fx - 160, zc - 260), (0, zc - 260)]], "soil")
    v.pattern([[(fx + 160, gl), (ext, gl), (ext, 0), (W, 0), (W, zc - 260), (fx + 160, zc - 260)]], "soil")
    _fgl(d, -40, W)
    sh.break_line(*v.P(0, 60), *v.P(0, zc - 260))
    sh.break_line(*v.P(W, 60), *v.P(W, zc - 260))
    foot = [(fx - 150, -800), (fx + 150, -800), (fx + 150, 0), (fx - 150, 0)]
    v.pattern([foot], "concrete", seed=9)
    v.poly(foot, True, "OUTLINE")
    v.rect(fx - 30, -700, 60, Hp + 700, "OUTLINE")
    sh.break_line(*v.P(fx - 90, Hp), *v.P(fx + 90, Hp))
    v.line(fx, -760, fx, Hp - 40, "CENTRE")
    v.circle(xi, zc, max(od / 2, 0.8 * d.n), "EARTH", fill=True)
    v.circle(gx, zc, max(od / 2, 0.8 * d.n), "EARTH", fill=True)
    v.poly([(gx, zc), (fx + 230, zc), (fx + 230, 300), (fx + 30, 300)], False, "EARTH")
    bolt = [(fx + 30, 270), (fx + 80, 270), (fx + 80, 330), (fx + 30, 330)]
    v.poly(bolt, True, "OUTLINE")
    yd = Hp + 160
    v.dim(fx, yd, gx, yd, 0, f"{_f(off, 0)}")
    sh.line(*v.P(gx, zc + od), v.P(gx, 0)[0], v.P(0, yd)[1] + 1.5, "DIM")
    sh.line(*v.P(fx + 30, Hp - 60), v.P(fx, 0)[0], v.P(0, yd)[1] + 1.5, "DIM")
    if abs(ext - gx) > 1.0:
        # extent of the surface layer, unless it ends at the perimeter conductor,
        # which the dimension above already gives (no duplicate dimensions)
        yb = zc - 200
        v.dim(fx, yb, ext, yb, 0, "1000")
        sh.line(*v.P(ext, -hs if hs else 0), v.P(ext, 0)[0], v.P(0, yb)[1] - 1.5, "DIM")
        sh.line(*v.P(fx, -800), v.P(fx, 0)[0], v.P(0, yb)[1] - 1.5, "DIM")
    v.dim(W - 120, 0, W - 120, zc, 0, f"{_f(h + hs, 0)}")
    d.note(fx + 55, 330, ["BOLTED OR WELDED", "CONNECTION TO POST"])
    d.note(gx, zc, ["PERIMETER CONDUCTOR", "OUTSIDE THE FENCE"], head="dot")
    d.note(fx + 120, -650, ["POST FOOTING"], head="dot")
    d.note(xi, zc, ["GRID CONDUCTOR"], side="left", head="dot")
    if hs > 0:
        d.note(fx - 400, -hs / 2, ["CRUSHED ROCK TO 1 m", "OUTSIDE THE FENCE"], side="left")
    d.note(fx - 30, Hp * 0.6, ["FENCE POST"], side="left", head="dot")
    d.finish()


def sheet_sections(sh, fr, ctx):
    x0, y0, w, h = fr.area
    hw = w / 2
    boxes = [(x0, y0 + h / 2, hw, h / 2), (x0 + hw, y0 + h / 2, hw, h / 2),
             (x0, y0, hw, h / 2), (x0 + hw, y0, hw, h / 2)]
    sh.line(x0 + hw, y0 + 4, x0 + hw, y0 + h - 4, "TITLETHIN")
    sh.line(x0 + 4, y0 + h / 2, x0 + w - 4, y0 + h / 2, "TITLETHIN")
    det_trench(sh, boxes[0], ctx, "")
    det_rod(sh, boxes[1], ctx, "2")
    det_riser(sh, boxes[2], ctx, "3")
    det_fence(sh, boxes[3], ctx, "4")


# ---------------------------------------------------------------------------
# sheet 201 — earth pit
# ---------------------------------------------------------------------------

HOUSING = {   # internal size and wall (mm), cover description
    "L": dict(inner=300, wall=60, depth=300, cover="POLYMER CONCRETE COVER, CLASS L (4 kN)"),
    "M": dict(inner=350, wall=80, depth=350, cover="DUCTILE IRON COVER, CLASS M (15 kN)"),
    "H": dict(inner=400, wall=100, depth=400, cover="DUCTILE IRON COVER, CLASS H (30 kN)"),
}


def sheet_pit(sh, fr, ctx):
    x0, y0, w, h = fr.area
    p = ctx.pit or dict(electrode="rod", L=ctx.rod_L, d=ctx.rod_d, D=0.0, fill_top=0.0,
                        fill_bottom=None, backfill="", n=ctx.n_test_pits or 1)
    hc = HOUSING[ctx.housing]
    inner, wall, Hh = hc["inner"], hc["wall"], hc["depth"] + 100
    L = (p.get("L") or ctx.rod_L) * 1000
    dd = p.get("d") or ctx.rod_d
    D = p.get("D") or 0.0
    hx0, hx1 = -inner / 2 - wall, inner / 2 + wall
    z_top = -Hh + 100 + 120           # rod top 120 mm above the gravel base
    shown_top, shown_bot = 700.0, 300.0
    box = (x0, y0, w * 0.5, h)
    est = Hh + shown_top + 200 + shown_bot + 150
    n = Detail(Sheet(sh.size), box, (hx0 - 170, -est, hx1 + 150, 80), "", left=0, right=18).n
    gap = 8.0 * n
    zb1 = z_top - shown_top
    zb2 = zb1 - gap
    ztip = zb2 - shown_bot
    d = Detail(sh, box, (hx0 - 170, ztip - 150, hx1 + 150, 80), "SECTION A–A  EARTH PIT", left=0,
               right=18, scale=n)
    v = d.v
    W2 = hx1 + 130
    # soil, with a break below the housing
    soil_l = [(-W2, 0), (hx0, 0), (hx0, -Hh), (-max(D, 60) / 2 - 2, -Hh), (-max(D, 60) / 2 - 2, zb1), (-W2, zb1)]
    v.pattern([soil_l], "soil")
    v.pattern([[(-x_, y_) for x_, y_ in soil_l]], "soil")
    for side in (-1, 1):
        v.pattern([[(side * W2, zb2), (side * (max(D, 60) / 2 + 2), zb2), (side * (max(D, 60) / 2 + 2), ztip - 120),
                    (side * W2, ztip - 120)]], "soil")
    _fgl(d, -W2 - 20, W2)
    for zz in (zb1, zb2):
        sh.break_line(*v.P(-W2, zz), *v.P(W2, zz))
    # housing walls and cover
    for xa in (hx0, inner / 2):
        wl_ = [(xa, -Hh), (xa + wall, -Hh), (xa + wall, -40), (xa, -40)]
        v.pattern([wl_], "concrete", seed=11)
        v.poly(wl_, True, "OUTLINE")
    cov = [(hx0, -40), (hx1, -40), (hx1, 0), (hx0, 0)]
    v.poly(cov, True, "OUTLINE")
    v.hatch([cov], 45, 0.8)
    grav = [(-inner / 2, -Hh), (inner / 2, -Hh), (inner / 2, -Hh + 100), (-inner / 2, -Hh + 100)]
    v.pattern([grav], "gravel", seed=12)
    v.poly(grav, True, "THIN")
    # backfill column below the housing
    if D and D > dd:
        for (za, zb_) in ((-Hh, zb1), (zb2, ztip - 100)):
            col = [(-D / 2, za), (D / 2, za), (D / 2, zb_), (-D / 2, zb_)]
            v.pattern([col], "bentonite", seed=13)
            v.line(-D / 2, za, -D / 2, zb_, "THIN"); v.line(D / 2, za, D / 2, zb_, "THIN")
        v.line(-D / 2, ztip - 100, D / 2, ztip - 100, "THIN")
    # rod
    v.line(-dd / 2, z_top, -dd / 2, zb1, "OUTLINE"); v.line(dd / 2, z_top, dd / 2, zb1, "OUTLINE")
    v.line(-dd / 2, z_top, dd / 2, z_top, "OUTLINE")
    v.poly([(-dd / 2, zb2), (-dd / 2, ztip + 2.5 * dd), (0, ztip), (dd / 2, ztip + 2.5 * dd), (dd / 2, zb2)],
           False, "OUTLINE")
    v.line(0, z_top + 30, 0, ztip - 40, "CENTRE")
    # clamp, tail to the link, link on the wall, out through the duct
    clamp = [(-dd / 2 - 16, z_top - 75), (dd / 2 + 16, z_top - 75), (dd / 2 + 16, z_top - 15), (-dd / 2 - 16, z_top - 15)]
    v.poly(clamp, True, "OUTLINE")
    lx = inner / 2 - 20
    v.poly([(dd / 2 + 16, z_top - 45), (lx - 70, z_top - 45), (lx - 70, -170), (lx - 22, -170)], False, "EARTH")
    v.rect(lx - 22, -215, 22, 150, "OUTLINE")
    v.rect(lx - 6, -230, 6, 180, "THIN")
    v.circle(lx - 11, -170, 6, "OUTLINE"); v.circle(lx - 11, -110, 6, "OUTLINE")
    zduct = -Hh + 70
    v.poly([(lx - 22, -110), (lx - 50, -110), (lx - 50, zduct + 25), (hx1 + 125, zduct + 25)], False, "EARTH")
    v.rect(inner / 2, zduct, wall, 50, "OUTLINE")
    # dimensions
    v.dim(hx0, 0, hx1, 0, 9, f"{_f(hx1 - hx0, 0)}")
    v.dim(-inner / 2, -40, inner / 2, -40, -6, f"{_f(inner, 0)}")
    v.dim(hx0 - 60, 0, hx0 - 60, -Hh, 0, f"{_f(Hh, 0)}")
    sh.line(*v.P(hx0, -Hh), v.P(hx0 - 60, 0)[0] - 1.5, v.P(0, -Hh)[1], "DIM")
    if D:
        v.dim(-D / 2, ztip - 100, D / 2, ztip - 100, -7, f"Ø{_f(D, 0)}")
    xr = hx0 - 140
    pa, pb = v.P(xr, z_top), v.P(xr, ztip)
    sh.dim(pa[0], pa[1], pb[0], pb[1], 0, f"L = {_f(L / 1000)} m", ext=False)
    sh.line(*v.P(-dd / 2 - 16, z_top), pa[0] - 1.5, pa[1], "DIM")
    sh.line(*v.P(0, ztip), pb[0] - 1.5, pb[1], "DIM")
    d.note(hx1 - 60, -20, None, balloon=1)
    d.note(hx1 - wall / 2, -Hh * 0.55, None, balloon=2)
    d.note(dd / 2, z_top - shown_top * 0.6, None, balloon=3)
    d.note(dd / 2 + 16, z_top - 30, None, balloon=4)
    d.note(lx - 11, -140, None, balloon=5)
    d.note(hx1 + 90, zduct + 25, None, balloon=6, head="dot")
    d.note(hx1 - wall / 2, zduct + 10, None, balloon=7)
    if D:
        d.note(D / 2 - 20, zb2 - shown_bot * 0.5, None, balloon=8)
    d.note(inner / 2 - 60, -Hh + 40, None, balloon=9)
    d.finish()

    # ---- plan, cover removed (top right) ----
    px, pw = x0 + w * 0.5, w * 0.5
    pbox = (px, y0 + h * 0.58, pw, h * 0.42)
    d2 = Detail(sh, pbox, (hx0 - 150, hx0 - 30, hx1 + 150, hx1 + 30), "PLAN — COVER REMOVED",
                left=0, right=38)
    v2 = d2.v
    v2.rect(hx0, hx0, hx1 - hx0, hx1 - hx0, "OUTLINE")
    v2.rect(-inner / 2, -inner / 2, inner, inner, "OUTLINE")
    v2.pattern([[(hx0, hx0), (hx1, hx0), (hx1, hx1), (hx0, hx1)],
                [(-inner / 2, -inner / 2), (inner / 2, -inner / 2), (inner / 2, inner / 2), (-inner / 2, inner / 2)]],
               "concrete", seed=14)
    v2.circle(0, 0, dd / 2 + 16, "OUTLINE")
    v2.circle(0, 0, dd / 2, "OUTLINE")
    if D:
        v2.circle(0, 0, D / 2, "HIDDEN")
    v2.rect(inner / 2 - 28, -75, 22, 150, "OUTLINE")
    v2.poly([(dd / 2 + 16, 0), (inner / 2 - 60, 0), (inner / 2 - 60, 40), (inner / 2 - 28, 40)], False, "EARTH")
    v2.poly([(inner / 2 - 28, -40), (inner / 2 - 60, -40), (inner / 2 - 60, -100), (hx1 + 120, -100)], False, "EARTH")
    v2.line(0, hx0 - 40, 0, hx1 + 40, "CENTRE"); v2.line(hx0 - 40, 0, hx1 + 40, 0, "CENTRE")
    pa, pb = v2.P(hx0 - 110, 0), v2.P(hx1 + 110, 0)
    for q, s_ in ((pa, 1), (pb, -1)):
        sh.line(q[0], q[1], q[0] + 4 * s_, q[1], "OUTLINE")
        sh.line(q[0] + 2 * s_, q[1], q[0] + 2 * s_, q[1] - 1.5, "OUTLINE")
        sh.arrow(q[0] + 2 * s_, q[1] - 3.6, -90, 2.1, 1.0, "OUTLINE")
    sh.text(pa[0] - 1, pa[1], "A", 3, "end", "middle", bold=True)
    sh.text(pb[0] + 1, pb[1], "A", 3, "start", "middle", bold=True)
    v2.dim(hx0, hx1, hx1, hx1, 7, f"{_f(hx1 - hx0, 0)}")
    v2.dim(hx1, hx0, hx1, hx1, -7, f"{_f(hx1 - hx0, 0)}")
    d2.note(inner / 2 - 17, -60, None, balloon=5)
    d2.note(hx1 + 60, -100, None, balloon=6, head="dot")
    if D:
        d2.note(D / 2 * 0.7071, -D / 2 * 0.7071, ["BACKFILL COLUMN", "BELOW (HIDDEN)"])
    d2.finish()

    # ---- test link detail (middle right) ----
    _det_test_link(sh, (px, y0 + h * 0.30, pw, h * 0.28), ctx)
    # ---- warning label and pit data (bottom right) ----
    lw, lh = 60.0, 24.0
    lx0, ly0 = px + (pw - lw) / 2, y0 + 19
    sh.rect(lx0, ly0, lw, lh, "OUTLINE")
    sh.rect(lx0 + 1.2, ly0 + 1.2, lw - 2.4, lh - 2.4, "THIN")
    for i, t in enumerate(("SAFETY ELECTRICAL", "CONNECTION —", "DO NOT REMOVE")):
        sh.text(lx0 + lw / 2, ly0 + lh - 6.6 - i * 5.2, t, 2.8, "middle", bold=True)
    sh.title_label(lx0 + lw / 2, ly0 - 7, "WARNING LABEL", "BS 7671, 514.13.1 — NTS")
    if ctx.pit:
        rows = [["Backfill", (p.get("backfill") or "—")],
                ["ρc / volume per pit", f"{_f(p.get('rho_c'), 2)} Ω·m / {_f(p.get('volume'), 3)} m³"],
                ["R one pit / dry season", f"{_f(p.get('R_pit'), 2)} / {_f(p.get('R_dry'), 2)} Ω"],
                [f"R of {p.get('n', 1)} pits at {_f(p.get('s'))} m", f"{_f(p.get('R_group'), 2)} Ω"],
                ["Service the pit above", f"{_f(p.get('retest'), 2)} Ω"]]
        tx = px + 6
        ty = y0 + h * 0.30 - 2
        sh.text(tx, ty, "EARTH PIT DESIGN DATA", 2.5, bold=True)
        table(sh, tx, ty - 2, [44, pw - 56], rows, None, rh=4.4, h=1.9, wrap_cols={1})
    rod_txt = (f"{ROD_MATERIALS[ctx.rod_mat]['label'].replace('EARTH ROD', 'ROD')} Ø{_f(dd, 1)} mm × "
               f"{_f(L / 1000)} m")
    return n, [
        (1, f"{hc['cover']}, MARKED 'EARTH'", "1", "No."),
        (2, f"PRECAST CONCRETE HOUSING {inner}×{inner} mm (IEC 62561-5)", "1", "No."),
        (3, rod_txt, "1", "No."),
        (4, "ROD-TO-CABLE CLAMP, BRONZE, IEC 62561-1", "1", "No."),
        (5, "TEST LINK ON INSULATORS (SEE DETAIL)", "1", "No."),
        (6, f"EARTHING CONDUCTOR TO GRID / MET, {ctx.cond} mm² Cu", "AR", "m"),
        (7, "PVC DUCT Ø50 mm THROUGH THE HOUSING WALL", "1", "No."),
        (8, f"BACKFILL: {(p.get('backfill') or 'LOW-RESISTIVITY COMPOUND').upper()}",
         _f(p.get('volume'), 3) if p.get('volume') else "AR", "m³"),
        (9, "CLEAN GRAVEL BASE 100 mm (DRAINAGE)", "AR", "m³"),
    ]


def _det_test_link(sh, box, ctx):
    bar_w, bar_t = 30.0, 5.0
    Lb = 140.0
    d = Detail(sh, box, (-Lb / 2 - 75, -40, Lb / 2 + 75, 40), "TEST LINK DETAIL", left=27, right=33)
    v = d.v
    base = [(-Lb / 2 - 15, -bar_w / 2 - 12), (Lb / 2 + 15, -bar_w / 2 - 12), (Lb / 2 + 15, bar_w / 2 + 12),
            (-Lb / 2 - 15, bar_w / 2 + 12)]
    v.poly(base, True, "THIN")
    for xi in (-Lb / 2 + 15, Lb / 2 - 15):
        v.rect(xi - 10, -10, 20, 20, "HIDDEN")
    bar = [(-Lb / 2, -bar_w / 2), (Lb / 2, -bar_w / 2), (Lb / 2, bar_w / 2), (-Lb / 2, bar_w / 2)]
    v.poly(bar, True, "OUTLINE")
    v.hatch([bar], 45, 1.4)
    for xb in (-Lb / 2 + 35, Lb / 2 - 35):
        side = -1 if xb < 0 else 1
        lug = [(xb - side * 9, -7), (xb - side * 9, 7), (xb + side * 50, 7), (xb + side * 56, 4),
               (xb + side * 56, -4), (xb + side * 50, -7)]
        v.poly(lug, True, "OUTLINE")
        v.circle(xb, 0, 8.5, "OUTLINE")
        v.circle(xb, 0, 5, "OUTLINE")
        v.line(xb + side * 56, 0, xb + side * 75, 0, "EARTH")
    v.dim(-Lb / 2, bar_w / 2 + 12, Lb / 2, bar_w / 2 + 12, 6, f"{_f(Lb, 0)}")
    v.dim(-Lb / 2 + 35, -bar_w / 2 - 12, Lb / 2 - 35, -bar_w / 2 - 12, -6, f"{_f(Lb - 70, 0)}")
    d.note(Lb / 2 - 35, 6, [f"{ctx.met_bolt} STAINLESS BOLT, NUT,", "FLAT AND SPRING WASHERS"])
    d.note(Lb / 2 + 60, 0, ["TO GRID / MET"], head="dot")
    d.note(-Lb / 2 + 10, bar_w / 2 - 6, [f"TINNED Cu LINK {_f(bar_w, 0)}×{_f(bar_t, 0)}"], side="left")
    d.note(-Lb / 2 - 60, 0, ["TO EARTH ROD"], side="left", head="dot")
    d.note(-Lb / 2 + 5, -bar_w / 2 - 6, ["INSULATING BASE"], side="left")
    d.finish()


# ---------------------------------------------------------------------------
# sheet 202 — main earthing terminal
# ---------------------------------------------------------------------------

def sheet_met(sh, fr, ctx):
    x0, y0, w, h = fr.area
    bw, bt = ctx.met_bar
    nways = max(4, ctx.met_ways)
    pitch = 50.0 if ctx.met_bolt == "M12" else 40.0
    hole = 14.0 if ctx.met_bolt == "M12" else 11.0
    end = 60.0
    Lbar = 2 * end + (nways - 1) * pitch
    so = 40.0                                  # insulator stand-off
    xs = [-Lbar / 2 + end + i * pitch for i in range(nways)]
    xi = (-Lbar / 2 + 25, Lbar / 2 - 25)
    ytop = y0 + h
    # ---- front elevation (looking at the wall) ----
    fb = (x0, ytop - h * 0.40, w * 0.64, h * 0.40)
    d = Detail(sh, fb, (-Lbar / 2 - 28, -bw / 2 - 55, Lbar / 2 + 28, bw / 2 + 50),
               f"FRONT ELEVATION — MAIN EARTHING TERMINAL, {nways} WAYS", left=0, right=34, pad=1.0)
    v = d.v
    bar = [(-Lbar / 2, -bw / 2), (Lbar / 2, -bw / 2), (Lbar / 2, bw / 2), (-Lbar / 2, bw / 2)]
    v.poly(bar, True, "OUTLINE")
    for xc in xi:
        v.rect(xc - 15, -15, 30, 30, "HIDDEN")
        v.circle(xc, 0, 5.5, "OUTLINE")
    for i, xh in enumerate(xs):
        v.circle(xh, 0, hole / 2, "OUTLINE")
        v.line(xh, -bw / 2 - 5, xh, bw / 2 + 5, "CENTRE")
        q = v.P(xh, bw / 2 + 18)
        sh.balloon(q[0], q[1], i + 1, r=2.3, h=2.0)
    v.line(-Lbar / 2 - 20, 0, Lbar / 2 + 20, 0, "CENTRE")
    v.dim(-Lbar / 2, -bw / 2, Lbar / 2, -bw / 2, -13, f"{_f(Lbar, 0)}")
    v.dim(-Lbar / 2, -bw / 2, xs[0], -bw / 2, -6, f"{_f(end, 0)}", tpos="start")
    v.dim(xs[0], -bw / 2, xs[1], -bw / 2, -6, f"{_f(pitch, 0)}")
    v.dim(Lbar / 2, -bw / 2, Lbar / 2, bw / 2, -7, f"{_f(bw, 0)}")
    # section mark B-B through the last way
    xb = (xs[-2] + xs[-1]) / 2 if nways > 1 else xs[-1] + 20
    for zz, s_ in ((bw / 2 + 36, 1), (-bw / 2 - 12, -1)):
        q = v.P(xb, zz)
        sh.line(q[0], q[1], q[0], q[1] + 3 * s_, "OUTLINE")
        sh.line(q[0], q[1] + 3 * s_, q[0] + 3.5, q[1] + 3 * s_, "OUTLINE")
        sh.arrow(q[0] + 5.5, q[1] + 3 * s_, 0, 2.1, 1.0, "OUTLINE")
        sh.text(q[0] - 1.2, q[1] + 3 * s_, "B", 3.0, "end", "middle", bold=True)
    d.note(xs[-1], -hole / 2, [f"Ø{_f(hole, 0)} HOLES FOR {ctx.met_bolt} (TYP.)"])
    d.note(xi[1] + 15, -15, ["INSULATOR BEHIND", "(HIDDEN)"])
    d.note(Lbar / 2 - 10, bw / 2 - 5, [f"TINNED Cu BAR {bw}×{bt} mm"])
    d.finish()
    # ---- plan (top view) ----
    pb = (x0, ytop - h * 0.40 - h * 0.24, w * 0.64, h * 0.24)
    d2 = Detail(sh, pb, (-Lbar / 2 - 28, -30, Lbar / 2 + 28, so + bt + 40), "PLAN", left=0, right=34,
                pad=1.0, scale=d.n)
    v2 = d2.v
    wall = [(-Lbar / 2 - 28, -25), (Lbar / 2 + 28, -25), (Lbar / 2 + 28, 0), (-Lbar / 2 - 28, 0)]
    v2.pattern([wall], "concrete", 0.7, seed=21)
    v2.line(-Lbar / 2 - 28, 0, Lbar / 2 + 28, 0, "OUTLINE")
    for xc in xi:
        ins = [(xc - 15, 0), (xc + 15, 0), (xc + 15, so), (xc - 15, so)]
        v2.poly(ins, True, "OUTLINE")
        v2.hatch([ins], -45, 1.4)
    barp = [(-Lbar / 2, so), (Lbar / 2, so), (Lbar / 2, so + bt), (-Lbar / 2, so + bt)]
    v2.poly(barp, True, "OUTLINE")
    v2.hatch([barp], 45, 0.6)
    for xh in xs:
        v2.rect(xh - 9, so + bt, 18, 8, "THIN")         # bolt head / lug
    v2.dim(xi[1] + 30, 0, xi[1] + 30, so, -1, f"{_f(so, 0)}")
    v2.dim(Lbar / 2, so, Lbar / 2, so + bt, -12, f"{_f(bt, 0)}", tpos="end")
    d2.note(xi[1] + 15, so / 2, ["LV EPOXY INSULATOR 40 mm,", "M10, FIXED TO THE WALL"])
    d2.note(xs[2], so + bt + 8, ["LUG AND BOLT, EACH WAY"])
    d2.finish()
    # ---- section B-B ----
    sb = (x0 + w * 0.64, ytop - h * 0.64, w * 0.36, h * 0.64)
    d3 = Detail(sh, sb, (-22, -bw / 2 - 25, so + bt + 52, bw / 2 + 25), "SECTION B–B", left=0, right=32,
                pad=1.0)
    v3 = d3.v
    wall3 = [(-20, -bw / 2 - 25), (0, -bw / 2 - 25), (0, bw / 2 + 25), (-20, bw / 2 + 25)]
    v3.pattern([wall3], "concrete", 0.6, seed=22)
    v3.line(0, -bw / 2 - 25, 0, bw / 2 + 25, "OUTLINE")
    bar3 = [(so, -bw / 2), (so + bt, -bw / 2), (so + bt, bw / 2), (so, bw / 2)]
    v3.poly(bar3, True, "OUTLINE")
    v3.hatch([bar3], 45, 0.7)
    lug = [(so + bt, -10), (so + bt + 6, -10), (so + bt + 6, 10), (so + bt, 10)]
    v3.poly(lug, True, "OUTLINE")
    v3.poly([(so + bt + 6, -6), (so + bt + 45, -6), (so + bt + 45, 6), (so + bt + 6, 6)], True, "OUTLINE")
    v3.line(so + bt + 45, 0, so + bt + 52, 0, "EARTH")
    v3.rect(so - 12, -9, 12, 18, "OUTLINE")                  # nut
    v3.line(so - 18, 0, so + bt + 12, 0, "CENTRE")
    v3.dim(so, bw / 2, so + bt, bw / 2, 8, f"{_f(bt, 0)}", tpos="start")
    v3.dim(so, -bw / 2, so, bw / 2, 12, f"{_f(bw, 0)}")
    v3.dim(0, -bw / 2 - 12, so, -bw / 2 - 12, 0, f"{_f(so, 0)}", tpos="chain")
    d3.note(so + bt + 3, 10, ["TWO-HOLE OR ONE-HOLE", "COMPRESSION LUG"])
    d3.note(so - 6, -9, [f"{ctx.met_bolt} NUT, FLAT AND", "SPRING WASHER"])
    d3.note(so + bt + 50, 0, ["CONDUCTOR"], head="dot")
    d3.finish()

    # ---- terminal schedule ----
    sched = [["1", "Earthing conductor to earth electrode / grid (via test link)", f"{ctx.cond}", "542.3"],
             ["2", "Main protective conductor from the source / transformer", "S/2, Table 54.2", "543.1"],
             ["3", "Main bonding — water service pipe", "6–25", "544.1"],
             ["4", "Main bonding — gas service pipe", "6–25", "544.1"],
             ["5", "Main bonding — structural steel / reinforcement", "6–25", "544.1"],
             ["6", "Lightning protection system (equipotential bonding)", "16 (Table 8)", "IEC 62305-3, 6.2"],
             ["7", "Functional earthing (ICT) — if required", "per design", "545"]]
    while len(sched) < nways:
        sched.append([str(len(sched) + 1), "Spare", "—", ""])
    sched = sched[:nways]
    n = d.n
    xs_ = x0 + 2
    sh.text(xs_, y0 + h * 0.36 - 4, "TERMINAL SCHEDULE", 3.0, bold=True)
    table(sh, xs_, y0 + h * 0.36 - 7, [12, w - 84, 34, 34], sched,
          ["WAY", "CONNECTION", "Cu mm²", "IEC 60364-5-54"], rh=5.0, h=2.0,
          aligns=["middle", "start", "middle", "middle"])
    return n, [
        (1, f"TINNED HARD-DRAWN COPPER BAR {bw}×{bt}×{_f(Lbar, 0)} mm, {nways} HOLES Ø{_f(hole, 0)}", "1", "No."),
        (2, "LV EPOXY INSULATOR 40 mm WITH M10 INSERTS", "2", "No."),
        (3, f"{ctx.met_bolt} STAINLESS BOLT, NUT, 2 FLAT + 1 SPRING WASHER", str(nways + 2), "set"),
        (4, "TWO-HOLE / ONE-HOLE COMPRESSION LUGS TO SUIT CONDUCTORS", "AR", "No."),
        (5, "LABEL 'SAFETY ELECTRICAL CONNECTION — DO NOT REMOVE'", "1", "No."),
        (6, "CIRCUIT IDENTIFICATION TAGS AT EACH WAY", str(nways), "No."),
    ]


# ---------------------------------------------------------------------------
# sheet 301 — connections (not to scale, proportioned to the conductor)
# ---------------------------------------------------------------------------

def _cable_h(v, x0, x1, y, od, layer="OUTLINE"):
    v.line(x0, y - od / 2, x1, y - od / 2, layer)
    v.line(x0, y + od / 2, x1, y + od / 2, layer)
    # strand lay lines
    step = od * 0.9
    xx = x0 + step / 2
    while xx < x1 - od * 0.3:
        v.line(xx, y - od / 2, min(xx + od * 0.45, x1), y + od / 2, "HATCH")
        xx += step


def _cable_v(v, x, y0, y1, od, layer="OUTLINE"):
    v.line(x - od / 2, y0, x - od / 2, y1, layer)
    v.line(x + od / 2, y0, x + od / 2, y1, layer)
    step = od * 0.9
    yy = min(y0, y1) + step / 2
    while yy < max(y0, y1) - od * 0.3:
        v.line(x - od / 2, yy, x + od / 2, min(yy + od * 0.45, max(y0, y1)), "HATCH")
        yy += step


def _end_cut(v, x, y, od, vertical=False):
    if vertical:
        v.circle(x, y, od / 2, "OUTLINE")
    else:
        v.arc(x, y, od / 2, 270, 90, "THIN")


def _weld(v, pts, n=1.0):
    v.poly(pts, True, "OUTLINE")
    v.hatch([pts], 45, 1.1)


def sheet_connections(sh, fr, ctx):
    x0, y0, w, h = fr.area
    od = ctx.cond_od
    dd = ctx.rod_d
    cols, rows = 3, 3
    top = y0 + 52
    cw, chh = w / cols, (h - 52) / rows
    for i in range(1, cols):
        sh.line(x0 + i * cw, top + 2, x0 + i * cw, y0 + h - 2, "TITLETHIN")
    for j in range(0, rows):
        sh.line(x0 + 2, top + j * chh, x0 + w - 2, top + j * chh, "TITLETHIN")
    exo = ctx.joint == "exothermic"
    L = od * 9.0
    b = od * 1.9

    def cell(i, j, title, sub):
        box = (x0 + i * cw, top + (rows - 1 - j) * chh, cw, chh)
        return Detail(sh, box, (-L, -L, L, L), f"{3 * j + i + 1}  {title}", left=0, right=33,
                      sub=sub + " — NTS", scale=max(1, od * 18 / (min(cw - 33, chh - 15) - 8)))
    # 1 cross
    d = cell(0, 0, "CROSS (X) CONNECTION", "GRID CROSSINGS")
    _cable_h(d.v, -L, L, 0, od); _cable_v(d.v, 0, -L, L, od)
    body = ([(-b, -b * 0.7), (-b * 0.7, -b), (b * 0.7, -b), (b, -b * 0.7), (b, b * 0.7), (b * 0.7, b),
             (-b * 0.7, b), (-b, b * 0.7)] if exo else [(-b, -b), (b, -b), (b, b), (-b, b)])
    _weld(d.v, body)
    d.note(b * 0.8, b * 0.5, [ctx.joint_name("X")])
    d.note(L * 0.8, od / 2, ["RUN CONDUCTOR"], head="dot")
    d.note(od / 2, -L * 0.75, ["CROSSING CONDUCTOR"], head="dot")
    d.finish()
    # 2 tee
    d = cell(1, 0, "TEE (T) CONNECTION", "PERIMETER JUNCTIONS, TAILS")
    yr = L * 0.3
    _cable_h(d.v, -L, L, yr, od); _cable_v(d.v, 0, -L, yr, od)
    body = [(-b * 1.2, yr - b * 0.9), (b * 1.2, yr - b * 0.9), (b * 1.2, yr + b * 0.8), (-b * 1.2, yr + b * 0.8)]
    _weld(d.v, body)
    d.note(b * 1.2, yr + b * 0.3, [ctx.joint_name("T")])
    d.note(L * 0.8, yr + od / 2, ["RUN CONDUCTOR"], head="dot")
    d.note(od / 2, -L * 0.7, ["BRANCH / TAIL"], head="dot")
    d.finish()
    # 3 straight splice
    d = cell(2, 0, "STRAIGHT SPLICE", "DRUM-LENGTH JOINTS")
    _cable_h(d.v, -L, -od * 0.2, 0, od); _cable_h(d.v, od * 0.2, L, 0, od)
    body = [(-b * 1.6, -od * 0.95), (b * 1.6, -od * 0.95), (b * 1.6, od * 0.95), (-b * 1.6, od * 0.95)]
    _weld(d.v, body)
    d.note(b, od * 0.9, [ctx.joint_name("S")])
    d.note(L * 0.8, od / 2, ["CONDUCTOR ENDS, CLEAN", "AND DRY, BUTTED"], head="dot")
    d.finish()
    # 4 cable to rod
    d = cell(0, 1, "CABLE TO EARTH ROD", "ROD TOP, THROUGH CONDUCTOR")
    v = d.v
    rd = max(dd, od * 1.3)
    v.line(-rd / 2, -L, -rd / 2, 0, "OUTLINE"); v.line(rd / 2, -L, rd / 2, 0, "OUTLINE")
    v.line(0, -L - od, 0, od * 2, "CENTRE")
    _cable_h(v, -L, L, od / 2 + 1, od)
    body = [(-b * 1.3, -b * 1.4), (b * 1.3, -b * 1.4), (b * 1.5, od * 1.6), (-b * 1.5, od * 1.6)]
    _weld(v, body)
    sh.break_line(*v.P(-rd * 1.6, -L * 0.95), *v.P(rd * 1.6, -L * 0.95))
    d.note(b * 1.4, 0, [ctx.joint_name("R")])
    d.note(L * 0.8, od, ["GRID CONDUCTOR"], head="dot")
    d.note(rd / 2, -L * 0.6, [f"EARTH ROD Ø{_f(dd, 1)} mm"], head="dot")
    d.finish()
    # 5 cable to steel
    d = cell(1, 1, "CABLE TO STEEL SURFACE", "COLUMN, TANK, FENCE POST")
    v = d.v
    stl = [(-L * 0.25, -L), (0, -L), (0, L), (-L * 0.25, L)]
    v.poly(stl, True, "OUTLINE"); v.hatch([stl], 45, 1.4)
    yc = -L * 0.15
    _cable_h(v, 0, L, yc, od)
    body = [(0, yc - od * 1.1), (b * 2.4, yc - od * 0.8), (b * 2.4, yc + od * 0.8), (0, yc + od * 1.1)]
    _weld(v, body)
    d.note(b * 1.5, yc + od * 0.9, [ctx.joint_name("P") if exo else "BOLTED LUG (DETAIL 9)"])
    d.note(-L * 0.12, L * 0.6, ["STEEL, PAINT REMOVED"], head="dot")
    d.note(L * 0.8, yc + od / 2, ["EARTHING TAIL"], head="dot")
    d.finish()
    # 6 parallel
    d = cell(2, 1, "PARALLEL CONNECTION", "DOUBLED CONDUCTORS / BYPASS")
    _cable_h(d.v, -L, L, od * 0.55, od); _cable_h(d.v, -L, L, -od * 0.55, od)
    body = [(-b * 1.4, -od * 1.6), (b * 1.4, -od * 1.6), (b * 1.4, od * 1.6), (-b * 1.4, od * 1.6)]
    _weld(d.v, body)
    d.note(b, od * 1.5, [("EXOTHERMIC WELD, PARALLEL TYPE" if exo else "COMPRESSION H-TAP")])
    d.note(L * 0.8, od * 1.05, ["CONDUCTORS SIDE BY SIDE"], head="dot")
    d.finish()
    # 7 compression C-tap
    d = cell(0, 2, "COMPRESSION C-TAP", "ABOVE-GROUND BRANCHES")
    v = d.v
    _cable_h(v, -L, L, od * 0.6, od); _cable_h(v, -L * 0.2, L, -od * 0.6, od)
    ct = [(-b * 1.1, -od * 1.4), (b * 1.1, -od * 1.4), (b * 1.1, od * 1.6), (b * 0.6, od * 1.9),
          (-b * 0.6, od * 1.9), (-b * 1.1, od * 1.6)]
    v.poly(ct, True, "OUTLINE")
    for xx in (-b * 0.55, 0, b * 0.55):
        v.line(xx, -od * 1.4, xx, od * 1.9, "THIN")
    d.note(b * 1.1, od * 1.2, ["C-TAP, COMPRESSED WITH", "THE SPECIFIED DIE"])
    d.note(L * 0.8, od * 1.1, ["RUN CONDUCTOR"], head="dot")
    d.note(L * 0.8, -od * 0.1, ["TAP CONDUCTOR"], head="dot")
    d.finish()
    # 8 bolted rod clamp
    d = cell(1, 2, "BOLTED ROD CLAMP (IN PIT)", "INSPECTABLE ROD CONNECTION")
    v = d.v
    rd = max(dd, od * 1.3)
    v.line(-rd / 2, -L, -rd / 2, L * 0.5, "OUTLINE"); v.line(rd / 2, -L, rd / 2, L * 0.5, "OUTLINE")
    v.line(-rd / 2, L * 0.5, rd / 2, L * 0.5, "OUTLINE")
    cb = [(-rd * 1.6, -rd * 0.6), (rd * 1.6, -rd * 0.6), (rd * 1.6, rd * 2.2), (-rd * 1.6, rd * 2.2)]
    v.poly(cb, True, "OUTLINE")
    v.circle(-rd * 0.9, rd * 1.1, od * 0.55, "OUTLINE")       # cable groove (end-on)
    v.rect(rd * 1.6, rd * 0.4, rd * 0.9, rd * 0.9, "OUTLINE")  # bolt head
    v.line(rd * 2.5, rd * 0.85, rd * 3.4, rd * 0.85, "THIN")
    _cable_h(v, -L, -rd * 0.9 - od * 0.6, rd * 1.1, od)
    d.note(rd * 1.6, rd * 1.8, ["BRONZE CLAMP BODY", "(IEC 62561-1)"])
    d.note(rd * 2.95, rd * 0.85, ["BOLT, TORQUE ≥ 20 N·m"], head="dot")
    d.note(rd / 2, -L * 0.6, [f"EARTH ROD Ø{_f(dd, 1)} mm"], head="dot")
    d.finish()
    # 9 two-hole lug
    d = cell(2, 2, "TWO-HOLE LUG TO EQUIPMENT PAD", f"{ctx.met_bolt} STAINLESS, 2 BOLTS")
    v = d.v
    pad_ = [(-L * 0.2, -L * 0.9), (0, -L * 0.9), (0, L * 0.9), (-L * 0.2, L * 0.9)]
    v.poly(pad_, True, "OUTLINE"); v.hatch([pad_], 45, 1.4)
    lw = od * 2.4
    lug = [(0, -lw / 2), (L * 0.55, -lw / 2), (L * 0.62, -od * 0.7), (L * 0.95, -od * 0.7),
           (L * 0.95, od * 0.7), (L * 0.62, od * 0.7), (L * 0.55, lw / 2), (0, lw / 2)]
    v.poly(lug, True, "OUTLINE")
    for xb in (L * 0.15, L * 0.4):
        v.circle(xb, 0, od * 0.55, "OUTLINE")
        v.circle(xb, 0, od * 0.85, "THIN")
    _cable_h(v, L * 0.95, L, 0, od)
    d.note(L * 0.15, od * 0.85, [f"{ctx.met_bolt} BOLT, 2 FLAT + 1", "SPRING WASHER, NUT"])
    d.note(L * 0.75, -od * 0.7, [f"COMPRESSION LUG {ctx.cond} mm²"])
    d.note(-L * 0.1, -L * 0.6, ["EQUIPMENT EARTH PAD,", "CLEANED BRIGHT"], head="dot")
    d.finish()
    # schedule
    rows_ = [["1–3, 6", "Buried grid joints", ("Exothermic weld" if exo else "Compression, irreversible"),
              "IEEE 837; IEC 62561-1 class H", "Mould / die to suit conductor size and type"],
             ["4", "Rod to grid", ("Exothermic weld" if exo else "Compression"), "IEEE 837; IEC 62561-1",
              "Rod top at grid depth"],
             ["5", "Conductor to steelwork", "Exothermic weld or bolted lug", "IEEE 80, 9.6",
              "Remove paint; coat with joint compound"],
             ["7–9", "Above-ground and inspectable", "Compression / bolted", "IEC 62561-1; BS 7430, 9.10",
              "Torque ≥ 20 N·m; stainless hardware"]]
    table(sh, x0 + 2, y0 + 48, [16, 46, 50, 62, w - 178], rows_,
          ["DETAIL", "APPLICATION", "METHOD", "STANDARD", "REMARKS"], rh=4.6, h=2.0,
          aligns=["middle", "start", "start", "start", "start"])
    return [
        (1, f"{'EXOTHERMIC WELD MOULD, X TYPE' if exo else 'COMPRESSION X-CONNECTOR'} {ctx.cond}×{ctx.cond} mm²", "AR", "No."),
        (2, f"{'EXOTHERMIC WELD MOULD, T TYPE' if exo else 'COMPRESSION C-TAP'} {ctx.cond}×{ctx.cond} mm²", "AR", "No."),
        (3, "WELD METAL CARTRIDGES / COMPRESSION DIES TO SUIT", "AR", "No."),
        (4, f"ROD-TO-CABLE CONNECTOR Ø{_f(ctx.rod_d, 1)} mm / {ctx.cond} mm²", "AR", "No."),
        (5, f"TWO-HOLE COMPRESSION LUG {ctx.cond} mm², {ctx.met_bolt}", "AR", "No."),
        (6, "JOINT COMPOUND (CONTACT GREASE)", "AR", "—"),
    ]


# ---------------------------------------------------------------------------
# sheet 302 — equipment bonding details and conductor selection chart
# ---------------------------------------------------------------------------

def conductor_chart(ctx):
    full = ctx.cond
    rows = []
    for key, n in ctx.equipment.items():
        e = EQUIPMENT[key]
        if e["full"]:
            size = f"{full}"
        elif key == "pipe":
            size = "6 – 25 (544.1)"
        elif key == "lv_panel":
            size = "Table 54.2"
        else:
            size = "≥ 16"
        rows.append([e["name"], str(e["tails"]), size, e["note"]])
    rows.append(["Main earth grid / ring (buried electrode)", "—", f"{full}",
                 f"Thermal size, ≥ {int(ctx.cond_min)} mm² for {ELECTRODE_DUTY[ctx.duty]['label']} "
                 f"({ELECTRODE_DUTY[ctx.duty]['ref'].split(';')[0]})"])
    if ctx.lps:
        rows.append(["LPS down-conductor / ring", "1 per DC", "50", "IEC 62305-3 Tables 6 and 7"])
        rows.append(["Bonding bar to earth termination", "—", "16", "IEC 62305-3 Table 8"])
        rows.append(["Internal metal to bonding bar", "—", "6", "IEC 62305-3 Table 9"])
    return rows


def _box(v, x, y, w, h, hatch=False):
    v.rect(x, y, w, h, "OUTLINE")
    if hatch:
        v.hatch([[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]], 45, 2.5)


def sheet_bonding(sh, fr, ctx):
    x0, y0, w, h = fr.area
    cols, rows = 2, 3
    cw, chh = w / cols, h / rows
    yb0 = y0
    for i in range(1, cols):
        sh.line(x0 + i * cw, yb0 + 2, x0 + i * cw, y0 + h - 2, "TITLETHIN")
    for j in range(1, rows):
        sh.line(x0 + 2, yb0 + j * chh, x0 + w - 2, yb0 + j * chh, "TITLETHIN")
    BB = (-2500, -2000, 2500, 2200)
    order = [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)]
    counter = [0]

    def cell(i, j, title, sub):
        ci, cj = order[counter[0]]
        counter[0] += 1
        box = (x0 + ci * cw, yb0 + (rows - 1 - cj) * chh, cw, chh)
        return Detail(sh, box, BB, f"{counter[0]}  {title}", left=0, right=40, sub=sub + " — NTS", pad=2,
                      nts=True)

    def grid_end(d, xx, yy):
        d.v.circle(xx, yy, 0.9 * d.n, "EARTH", fill=True)

    def ground(d, xa=-2500, xb=2500, yy=-1200):
        d.v.ground(xa, xb, yy, depth=1.4, step=2.0)

    # 1 transformer
    d = cell(0, 0, "POWER TRANSFORMER", "TANK AND NEUTRAL")
    v = d.v
    ground(d)
    v.rect(-1600, -1200, 3200, 300, "OUTLINE")
    v.rect(-1300, -900, 2600, 1900, "OUTLINE")
    for xx in (-900, 0, 900):
        v.rect(xx - 90, 1000, 180, 600, "OUTLINE")
    v.rect(1300, -700, 300, 1300, "OUTLINE")
    v.rect(-1420, -820, 120, 100, "OUTLINE"); v.rect(1300, -820, 120, 100, "OUTLINE")
    v.poly([(-1420, -770), (-1900, -770), (-1900, -1800), (-2300, -1800)], False, "EARTH")
    v.poly([(1420, -770), (1500, -770), (1500, -1000), (1900, -1000), (1900, -1800), (2300, -1800)], False, "EARTH")
    grid_end(d, -2300, -1800); grid_end(d, 2300, -1800)
    v.poly([(900, 1600), (900, 1900), (2200, 1900), (2200, -1100)], False, "EARTH")
    v.rect(2100, -1100, 200, 400, "OUTLINE")
    d.note(1900, -1400, ["TWO LEADS, OPPOSITE", "DIRECTIONS (IEEE 80, 9.6)"])
    d.note(2200, 900, ["NEUTRAL CONDUCTOR", "(VIA NER IF RESISTANCE", "EARTHED, SHEET 501)"])
    d.note(1300, -770, ["EARTH PADS ON TANK"], head="dot")
    d.note(2300, -1800, ["TO GRID"], head="dot")
    d.finish()
    # 2 switchgear / panels
    d = cell(1, 0, "SWITCHGEAR / PANEL LINE-UP", "EARTH BAR AT BOTH ENDS")
    v = d.v
    ground(d)
    for i in range(4):
        v.rect(-2000 + i * 1000, -1200, 1000, 2600, "OUTLINE")
        v.rect(-1850 + i * 1000, 400, 700, 600, "THIN")
    v.rect(-1900, -1010, 3800, 60, "OUTLINE")
    v.poly([(-1900, -980), (-2200, -980), (-2200, -1800)], False, "EARTH")
    v.poly([(1900, -980), (2200, -980), (2200, -1800)], False, "EARTH")
    grid_end(d, -2200, -1800); grid_end(d, 2200, -1800)
    d.note(1500, -950, ["PANEL EARTH BAR"])
    d.note(2200, -1400, ["TAIL AT EACH END OF", "THE BAR TO THE GRID"])
    d.finish()
    # 3 motor
    d = cell(2, 0, "MOTOR", "FRAME TERMINAL TO GRID")
    v = d.v
    ground(d)
    v.rect(-1800, -1200, 3000, 300, "OUTLINE")
    v.rect(-1300, -900, 1900, 1300, "OUTLINE")
    v.circle(-350, -250, 500, "THIN")
    v.rect(600, -350, 500, 200, "OUTLINE")
    v.rect(-1000, 400, 700, 450, "OUTLINE")
    v.rect(-1420, -820, 120, 100, "OUTLINE")
    v.poly([(-1420, -770), (-2000, -770), (-2000, -1800), (-2300, -1800)], False, "EARTH")
    grid_end(d, -2300, -1800)
    v.poly([(-650, 850), (-650, 1700), (1800, 1700)], False, "OUTLINE")
    d.note(-1420, -770, ["FRAME EARTH TERMINAL"], head="dot")
    d.note(-650, 1300, ["POWER CABLE: ARMOUR", "BONDED AT THE GLAND"])
    d.note(-2000, -1300, [f"TAIL TO GRID (SEE CHART)"])
    d.finish()
    # 4 steel column
    d = cell(0, 1, "STEEL STRUCTURE / COLUMN", "EVERY EARTHED COLUMN")
    v = d.v
    ground(d)
    ped = [(-900, -1900), (900, -1900), (900, -1200), (-900, -1200)]
    v.pattern([ped], "concrete", 3.0, seed=31)
    v.poly(ped, True, "OUTLINE")
    v.rect(-500, -1000, 1000, 60, "OUTLINE")
    v.rect(-150, -940, 300, 3000, "OUTLINE")
    v.line(-500, -1000, -500, -1200, "THIN"); v.line(500, -1000, 500, -1200, "THIN")
    v.rect(150, -600, 220, 80, "OUTLINE")
    v.poly([(370, -560), (1200, -560), (1200, -1900), (2000, -1900)], False, "EARTH")
    grid_end(d, 2000, -1900)
    d.note(260, -520, ["WELDED EARTH BOSS +", "TWO-HOLE LUG"])
    d.note(0, 1200, ["STEEL COLUMN"], head="dot")
    d.note(2000, -1900, ["TO GRID"], head="dot")
    d.finish()
    # 5 fence and gate
    d = cell(1, 1, "FENCE AND GATE", "POSTS TO GRID, BRAID ON GATES")
    v = d.v
    ground(d)
    for xp in (-2000, -300, 300, 2000):
        v.rect(xp - 60, -1200, 120, 2700, "OUTLINE")
    v.rect(-2000, -900, 1700, 2200, "THIN")
    v.rect(300, -900, 1700, 2200, "THIN")
    v.rect(-240, -1000, 480, 2300, "OUTLINE")
    v.line(-240, -1000, 240, 1300, "THIN")
    v.poly([(-300, 300), (-280, 380), (-260, 220), (-240, 300)], False, "EARTH")
    v.poly([(-300, -600), (-280, -520), (-260, -680), (-240, -600)], False, "EARTH")
    v.poly([(-2000, -1100), (-2000, -1800), (2000, -1800), (2000, -1100)], False, "EARTH")
    v.poly([(-300, -1100), (-300, -1800)], False, "EARTH"); v.poly([(300, -1100), (300, -1800)], False, "EARTH")
    d.note(-270, 330, ["FLEXIBLE TINNED Cu BRAID", "ACROSS EVERY HINGE"])
    d.note(300, -1500, ["GATE POSTS BONDED"])
    d.note(2000, -1500, ["FENCE POSTS TO GRID"])
    d.finish()
    # 6 cable tray
    d = cell(2, 1, "CABLE TRAY / LADDER", "CONTINUITY AND EARTHING")
    v = d.v
    v.rect(-2400, 0, 2300, 300, "OUTLINE"); v.rect(100, 0, 2300, 300, "OUTLINE")
    for xr in range(-2300, 2400, 400):
        v.line(xr, 0, xr, 300, "THIN")
    v.rect(-200, -30, 400, 360, "THIN")
    v.poly([(-150, 330), (-80, 520), (0, 440), (80, 520), (150, 330)], False, "EARTH")
    v.line(-2400, 1500, 2400, 1500, "THIN")
    for xs_ in (-1800, 1800):
        v.line(xs_, 300, xs_, 1500, "OUTLINE")
    v.poly([(-2350, 150), (-2350, -1800)], False, "EARTH")
    ground(d, yy=-1200)
    grid_end(d, -2350, -1800)
    d.note(0, 480, ["BONDING JUMPER AT", "EVERY JOINT"])
    d.note(1800, 1500, ["SUPPORT STEEL"], head="dot")
    d.note(-2350, -600, ["TRAY EARTHED AT BOTH", "ENDS (FAR END SIMILAR)"])
    d.finish()
    return [
        (1, f"EARTHING TAIL, {ctx.cond} mm² Cu (BARE BELOW / PVC GREEN-YELLOW ABOVE GRADE)", "AR", "m"),
        (2, "FLEXIBLE TINNED COPPER BRAID WITH CRIMPED LUGS (GATES)", "AR", "No."),
        (3, "BONDING JUMPER, TRAY JOINTS, 16 mm² GREEN-YELLOW", "AR", "No."),
        (4, "WELDED EARTH BOSS / LUG PLATE ON STEELWORK", "AR", "No."),
    ]


# ---------------------------------------------------------------------------
# sheet 303 — conductor selection chart and sizing references
# ---------------------------------------------------------------------------

def sheet_chart(sh, fr, ctx):
    x0, y0, w, h = fr.area
    top = y0 + h
    chart = conductor_chart(ctx)
    sh.text(x0, top - 4, "EARTHING CONDUCTOR SELECTION CHART (COPPER)", 3.5, bold=True)
    yb = table(sh, x0, top - 7, [w * 0.30, w * 0.12, w * 0.14, w * 0.44], chart,
               ["EQUIPMENT", "No. OF\nCONNECTIONS", "SIZE mm²", "BASIS / REMARK"], rh=5.0, h=2.1,
               head_h=8, aligns=["start", "middle", "middle", "start"], wrap_cols={3})
    # thermal sizing summary
    c = ctx.S.get("conductor") or {}
    ie, iec = c.get("ieee80") or {}, c.get("iec") or {}
    xl, wl = x0, w * 0.48
    y = yb - 9
    sh.text(xl, y, "CONDUCTOR THERMAL SIZING (FROM MODULE 3)", 3.0, bold=True)
    rows = []
    if ie:
        rows += [["Fault current through the conductor", f"{_f(ie.get('I_kA'), 3)} kA (incl. D_f = {_f(ie.get('Df'), 3)})"],
                 ["Duration t_c", f"{_f(ie.get('tc'), 2)} s"],
                 ["Material / fusing temperature", f"{ie.get('material', '')} / {_f(ie.get('Tm'), 0)} °C"],
                 ["IEEE 80 Eq. (37) minimum area", f"{_f(ie.get('area_mm2'), 1)} mm²"]]
    if iec:
        rows += [["IEC 60364-5-54 adiabatic S = √(I²t)/k", f"{_f(iec.get('area_mm2'), 1)} mm² (k = {_f(iec.get('k'), 0)})"]]
    rows += [[f"Mechanical / corrosion minimum, buried bare Cu ({ELECTRODE_DUTY[ctx.duty]['label']})",
              f"{int(ctx.cond_min)} mm² ({ELECTRODE_DUTY[ctx.duty]['ref']})"],
             ["Size used on the drawings", f"{ctx.cond} mm² — {ctx.cond_basis}"]]
    yth = table(sh, xl, y - 3, [wl * 0.55, wl * 0.45], rows, None, rh=4.8, h=2.0, wrap_cols={0, 1})
    # Table 54.2
    xr, wr = x0 + w * 0.52, w * 0.48
    sh.text(xr, y, "PROTECTIVE CONDUCTORS — IEC 60364-5-54 TABLE 54.2", 3.0, bold=True)
    yy = table(sh, xr, y - 3, [wr * 0.40, wr * 0.60],
               [["S ≤ 16", "S"], ["16 < S ≤ 35", "16"], ["S > 35", "S / 2"]],
               ["LINE CONDUCTOR S (mm² Cu)", "MINIMUM PE (mm² Cu, same material)"], rh=5.0, h=2.0,
               aligns=["middle", "middle"])
    sh.text(xr, yy - 4, "Main protective bonding (544.1): ≥ half the largest PE, ≥ 6 mm² Cu; need not "
                        "exceed 25 mm² Cu.", 2.0)
    sh.text(xr, yy - 8, "Earthing conductor (542.3.1): ≥ 6 mm² Cu; buried bare to Table 54.1.", 2.0)
    # IEC 62561-2 minimum electrode sizes
    y2 = min(yy - 16, yth - 9)
    sh.text(x0, y2, "MINIMUM SIZES OF EARTH ELECTRODES — BS EN 50522:2022 TABLE C.1 / IEC 60364-5-54 TABLE 54.1 "
                    "(EXTRACT)", 3.0, bold=True)
    mins = [["Copper", "Stranded or round wire, laid horizontally", "50 mm²", "25 mm²",
             "16 mm² where corrosion and mechanical risk are extremely low (footnote d)"],
            ["Copper", "Strip", "50 mm², 2 mm thick", "50 mm², 2 mm thick", ""],
            ["Copper", "Solid round rod, driven vertically", "Ø15 mm", "Ø12 mm", ""],
            ["Copper", "Pipe / solid plate", "Ø20 mm, 2 mm wall / 2 mm", "Ø20 mm / 1.5 mm", ""],
            ["Copper, tinned", "Stranded (EN 50522 only)", "25 mm²", "25 mm²", "Ø1.8 mm strands, ≥ 1 µm tin"],
            ["Steel, electro-deposited Cu", "Round rod, driven vertically", "Ø14 mm, 250 µm Cu", "Ø14 mm, 250 µm Cu",
             "100 µm with protected driving (footnote e)"],
            ["Steel, hot-dip galvanized", "Round rod, vertical / wire, horizontal", "Ø16 mm / Ø10 mm",
             "Ø16 mm / Ø10 mm", "350 g/m² zinc"],
            ["Steel, hot-dip galvanized", "Strip", "90 mm², 3 mm", "90 mm², 3 mm", "500 g/m² zinc"],
            ["Stainless steel", "Rod, vertical / wire, horizontal / strip", "Ø16 / Ø10 mm / 90 mm²",
             "Ø16 / Ø10 mm / 90 mm²", "Cr ≥ 16 %, Ni ≥ 5 %, Mo ≥ 2 %"]]
    y3 = table(sh, x0, y2 - 3, [w * 0.15, w * 0.24, w * 0.17, w * 0.15, w * 0.29], mins,
               ["MATERIAL", "SHAPE", "LIGHTNING + SHOCK", "SHOCK ONLY", "NOTE"], rh=4.8, h=2.0,
               wrap_cols={0, 1, 2, 3, 4})
    if ctx.lps:
        y4 = y3 - 9
        sh.text(x0, y4, "LIGHTNING EQUIPOTENTIAL BONDING — IEC 62305-3 TABLES 8 AND 9", 3.0, bold=True)
        table(sh, x0, y4 - 3, [w * 0.40, w * 0.15, w * 0.15, w * 0.15],
              [["Between bonding bars / bar to earth termination (Table 8)", "16", "25", "50"],
               ["Internal metal installations to bonding bar (Table 9)", "6", "10", "16"]],
              ["CONNECTION", "Cu mm²", "Al mm²", "Steel mm²"], rh=5.0, h=2.0,
              aligns=["start", "middle", "middle", "middle"])


# ---------------------------------------------------------------------------
# sheet 401 — lightning protection earth termination
# ---------------------------------------------------------------------------

def lps_layout(ctx):
    L = ctx.lps
    W, D = L["W"], L["D"]
    per = 2 * (W + D)
    n = max(4, int(math.ceil(per / L["table"]["down"] - 1e-9)))
    # corners first, then equally along the perimeter
    pts = []
    for i in range(n):
        s = per * i / n
        if s <= W:
            pts.append((s, 0.0))
        elif s <= W + D:
            pts.append((W, s - W))
        elif s <= 2 * W + D:
            pts.append((W - (s - W - D), D))
        else:
            pts.append((0.0, D - (s - 2 * W - D)))
    corners = [(0, 0), (W, 0), (W, D), (0, D)]
    for c in corners:
        if not any(math.hypot(c[0] - p[0], c[1] - p[1]) < 0.5 for p in pts):
            # snap the nearest point to the corner (IEC 62305-3, 5.3.3)
            j = min(range(len(pts)), key=lambda i: math.hypot(c[0] - pts[i][0], c[1] - pts[i][1]))
            pts[j] = c
    return pts


def sheet_lps(sh, fr, ctx):
    L = ctx.lps
    W, Dd = L["W"], L["D"]
    x0, y0, w, h = fr.area
    dcs = lps_layout(ctx)
    ro = 1.0
    typeB = "B" in str(L["arrangement"]).upper()
    K = 1000.0
    # ---- plan (top, full width) ----
    m_ = 5.0
    pbox = (x0, y0 + h * 0.42, w, h * 0.58)
    d = Detail(sh, pbox, (-(ro + m_) * K, -(ro + m_) * K, (W + ro + m_) * K, (Dd + ro + m_) * K),
               "LIGHTNING PROTECTION — ROOF AND EARTH TERMINATION PLAN", left=0, right=52)
    v = d.v
    n = d.n
    v.poly([(0, 0), (W * K, 0), (W * K, Dd * K), (0, Dd * K)], True, "OUTLINE")
    mesh = L["table"]["mesh"]
    nx = max(1, int(math.ceil(W / mesh - 1e-9))); ny = max(1, int(math.ceil(Dd / mesh - 1e-9)))
    for i in range(1, nx):
        v.line(W * K * i / nx, 0, W * K * i / nx, Dd * K, "PHANTOM")
    for j in range(1, ny):
        v.line(0, Dd * K * j / ny, W * K, Dd * K * j / ny, "PHANTOM")
    at_pts = []
    for t in L["terminals"]:
        xt = float(t.get("x", 0)) - float(L.get("x0") or 0)
        yt = float(t["y"]) if t.get("y") is not None else Dd / 2
        if -1e-6 <= xt <= W + 1e-6 and -1e-6 <= yt <= Dd + 1e-6:
            at_pts.append((xt, yt))
            p = v.P(xt * K, yt * K)
            sh.circle(p[0], p[1], 1.7, "OUTLINE")
            sh.line(p[0] - 2.6, p[1], p[0] + 2.6, p[1], "OUTLINE")
            sh.line(p[0], p[1] - 2.6, p[0], p[1] + 2.6, "OUTLINE")
    if typeB:
        v.poly([(-ro * K, -ro * K), ((W + ro) * K, -ro * K), ((W + ro) * K, (Dd + ro) * K), (-ro * K, (Dd + ro) * K)],
               True, "EARTH")
    for i, (px, py) in enumerate(dcs):
        p = v.P(px * K, py * K)
        sh.circle(p[0], p[1], 1.8, "OUTLINE"); sh.dot(p[0], p[1], 0.7, "OUTLINE")
        nxv = -1 if px <= 1e-6 else (1 if px >= W - 1e-6 else 0)
        nyv = -1 if py <= 1e-6 else (1 if py >= Dd - 1e-6 else 0)
        if nxv and nyv:
            nyv = 0
        q = v.P((px + nxv * ro) * K, (py + nyv * ro) * K)
        sh.line(p[0], p[1], q[0], q[1], "EARTH")
        if not typeB or not L.get("radius_ok", True):
            rod_symbol(sh, q[0], q[1], 1.5)
        # tag outside the ring
        cx, cy = W / 2, Dd / 2
        ux, uy = px - cx, py - cy
        ln = math.hypot(ux, uy) or 1
        if nxv or nyv:
            ux, uy = (nxv, nyv)
            ln = 1
        t = (q[0] + ux / ln * 5.5, q[1] + uy / ln * 4.0)
        if nxv:     # beside a wall: set the tag just above the extension and leader lines
            t = (t[0], q[1] + 2.8)
        anchor = "middle" if not nxv else ("start" if nxv > 0 else "end")
        sh.text(t[0] + (0 if not nxv else 0), t[1], f"DC{i + 1}", 2.0, anchor, "middle", bold=True)
    pa, pb = v.P(0, -(ro + 4.5) * K), v.P(W * K, -(ro + 4.5) * K)
    sh.dim(pa[0], pa[1], pb[0], pb[1], 0, f"{_f(W, 1)} m", ext=False)
    for q in (v.P(0, 0), v.P(W * K, 0)):
        sh.line(q[0], q[1] - 1, q[0], pa[1] - 1.5, "DIM")
    pa, pb = v.P(-(ro + 4.5) * K, 0), v.P(-(ro + 4.5) * K, Dd * K)
    sh.dim(pa[0], pa[1], pb[0], pb[1], 0, f"{_f(Dd, 1)} m", ext=False)
    for q in (v.P(0, 0), v.P(0, Dd * K)):
        sh.line(q[0] - 1, q[1], pa[0] - 1.5, q[1], "DIM")
    if typeB:
        d.note(W * 0.62 * K, -ro * K, [f"RING EARTH ELECTRODE {max(50, ctx.cond if ctx.cond < 70 else 50)} mm² Cu, "
                                       f"{_f(L['ring_depth'] * 1000, 0)} mm DEEP, 1 m FROM THE WALLS (TYPE B)"])
    else:
        d.note(dcs[0][0] * K, dcs[0][1] * K, [f"TYPE A: EARTH ROD AT EACH DOWN-CONDUCTOR, L ≥ 0.5·l1 + 0.5 m = "
                                              f"{_f(0.5 * (L['l1'] or 5) + 0.5, 1)} m"])
    d.note((W * K) * (1 - 0.5 / nx) if nx > 1 else W * K * 0.75, Dd * K * 0.5,
           [f"ROOF MESH ≤ {mesh} × {mesh} m (CLASS {L['cls']}), 50 mm² Cu"], head="dot")
    if at_pts:
        # point at a rod clear of the walls where there is one, else the east-most
        inner_ = [p_ for p_ in at_pts if 0.5 < p_[0] < W - 0.5 and 0.5 < p_[1] < Dd - 0.5]
        pt_ = max(inner_ or at_pts, key=lambda p_: p_[0])
        d.note(pt_[0] * K, pt_[1] * K, ["AIR-TERMINATION ROD (MODULE 8)"])
    d.note(dcs[0][0] * K, dcs[0][1] * K, ["DOWN-CONDUCTOR WITH TEST JOINT (TYP.)"])
    d.finish()
    north_arrow(sh, x0 + w - 10, y0 + h - 12)
    # ---- elevation (bottom left), broken between 1.8 m and H - 0.8 m ----
    Hs = L["H"] * K
    lo, hi = 1800.0, max(Hs - 800.0, 1900.0)
    ebox = (x0, y0, w * 0.56, h * 0.42)
    zr = -L["ring_depth"] * K
    wx, wt = 0.0, 300.0
    BBx = (wx - 1350, wx + wt + 450)
    ne = Detail(Sheet(sh.size), ebox, (BBx[0], zr - 300, BBx[1], 1800 + 400 + 800 + 500), "", left=34,
                right=40).n
    gap = 8.0 * ne
    off = hi - lo - gap
    top = Hs - off
    d2 = Detail(sh, ebox, (BBx[0], zr - 300, BBx[1], top + 400), "TYPICAL DOWN-CONDUCTOR ELEVATION",
                left=34, right=40, scale=ne)
    v2 = d2.v
    for (za, zb_) in ((0, lo), (lo + gap, top)):
        wall_ = [(wx, za), (wx + wt, za), (wx + wt, zb_), (wx, zb_)]
        v2.pattern([wall_], "concrete", 1.0, seed=41)
        v2.poly([(wx, za), (wx, zb_)], False, "OUTLINE")
        v2.poly([(wx + wt, za), (wx + wt, zb_)], False, "OUTLINE")
    v2.line(wx - 60, top, wx + wt, top, "OUTLINE")
    for zz in (lo, lo + gap):
        sh.break_line(*v2.P(wx - 250, zz), *v2.P(wx + wt + 150, zz))
    v2.ground(BBx[0], BBx[1], 0, depth=1.6, step=2.4)
    tj = 1000.0
    dcx = wx - 40
    v2.line(dcx, top + 250, dcx, lo + gap, "EARTH")
    v2.line(dcx, top + 250, dcx + 200, top + 250, "EARTH")
    v2.line(dcx, lo, dcx, tj + 120, "EARTH")
    v2.rect(dcx - 60, tj - 120, 120, 240, "OUTLINE")
    v2.line(dcx, tj - 120, dcx, -150, "EARTH")
    for zz in (1600.0, top - 400):
        v2.rect(dcx - 30, zz - 30, 60, 60, "THIN")
    v2.rect(dcx - 45, -300, 90, 600, "THIN")
    v2.poly([(dcx, -150), (dcx, zr), (wx - 1000, zr)], False, "EARTH")
    v2.circle(wx - 1000, zr, 0.9 * ne, "EARTH", fill=True)
    v2.dim(wx - 1000, zr - 180, wx, zr - 180, 0, "1000")
    sh.line(*v2.P(wx, -40), v2.P(wx, 0)[0], v2.P(0, zr - 180)[1] - 1.5, "DIM")
    sh.line(*v2.P(wx - 1000, zr - 60), v2.P(wx - 1000, 0)[0], v2.P(0, zr - 180)[1] - 1.5, "DIM")
    v2.dim(wx - 1250, 0, wx - 1250, zr, 0, f"{_f(-zr, 0)}")
    sh.line(*v2.P(wx - 1000, zr), v2.P(wx - 1250, 0)[0] + 1.5, v2.P(0, zr)[1], "DIM")
    v2.dim(wx + wt + 250, 0, wx + wt + 250, tj, 0, "≈1000")
    sh.line(*v2.P(dcx + 60, tj), v2.P(wx + wt + 250, 0)[0] + 1.5, v2.P(0, tj)[1], "DIM")
    d2.note(dcx - 60, tj, ["TEST JOINT, OPENED ONLY WITH A TOOL (5.3.6)"], side="left")
    d2.note(dcx, 1400, ["DOWN-CONDUCTOR 50 mm² Cu"], side="left", head="dot")
    d2.note(dcx - 45, 150, ["PVC SLEEVE AT GROUND ENTRY"], side="left")
    d2.note(wx - 1000, zr, ["RING EARTH" if typeB else "TO EARTH ROD"], side="left", head="dot")
    d2.note(dcx + 30, 1600, ["CONDUCTOR CLIPS ≈ 1 m"])
    d2.note(wx + wt / 2, top - 700, ["EXTERNAL WALL"], head="dot")
    d2.note(dcx + 150, top + 250, ["TO ROOF CONDUCTOR"], head="dot")
    d2.finish()
    # data
    rows = [["LPS class", L["cls"]], ["Rolling-sphere radius", f"{L['table']['sphere']} m"],
            ["Mesh size", f"{L['table']['mesh']} × {L['table']['mesh']} m"],
            ["Typical down-conductor spacing", f"{L['table']['down']} m"],
            ["Down-conductors drawn", f"{len(dcs)}"],
            ["Earth arrangement", str(L["arrangement"])]]
    if L.get("l1") is not None:
        rows.append(["Minimum length l_1 (Figure 3)", f"{_f(L['l1'], 1)} m"])
    if L.get("re"):
        rows.append(["Mean radius of the ring r_e", f"{_f(L['re'], 1)} m"])
    if L.get("R"):
        rows.append(["Earth-termination resistance", f"{_f(L['R'], 2)} Ω"])
    sup = L.get("supplementary")
    if sup and isinstance(sup, dict):
        lr = sup.get("lr") or sup.get("l_r")
        lv = sup.get("lv") or sup.get("l_v")
        if lr or lv:
            rows.append(["Additional electrode per DC", f"lr = {_f(lr, 1)} m or lv = {_f(lv, 1)} m"])
    ex = x0 + w * 0.58
    ew = w * 0.42
    table(sh, ex, y0 + h * 0.42 - 4, [ew * 0.58, ew * 0.40], rows,
          ["IEC 62305-3 DESIGN DATA", ""], rh=4.6, h=2.0)
    return n, [
        (1, "AIR-TERMINATION ROD / MESH CONDUCTOR 50 mm² Cu", "AR", "—"),
        (2, f"DOWN-CONDUCTOR 50 mm² Cu (OR 8 mm SOLID ROUND)", _f(len(dcs) * (L['H'] + 1.5) * 1.1, 0), "m"),
        (3, "TEST JOINT, COPPER ALLOY, IEC 62561-1", str(len(dcs)), "No."),
        (4, "CONDUCTOR CLIPS, ≈1 m SPACING", _f(len(dcs) * math.ceil(L['H']), 0), "No."),
        (5, f"RING EARTH {max(50, ctx.cond if ctx.cond < 70 else 50)} mm² Cu" if typeB else ctx.rod_label,
         _f(2 * (W + Dd + 4 * ro) * 1.05, 0) if typeB else str(len(dcs)), "m" if typeB else "No."),
        (6, "PVC SLEEVE AT GROUND ENTRY, 2 m", str(len(dcs)), "No."),
    ]


# ---------------------------------------------------------------------------
# sheet 501 — schematics
# ---------------------------------------------------------------------------

def _resistor(sh, x, y, w=4, h=10):
    sh.rect(x - w / 2, y - h / 2, w, h, "OUTLINE")


def _winding_star(sh, x, y, r=7, neutral=0.0):
    """Three-phase winding, star (IEC 60617 S00808).  With neutral > 0 the
    neutral is brought out (S00809): a dot at the star point and a line of
    that length.  The symbol is turned so the neutral leaves downwards; its
    arms then point at 60°, 180° and 300°, as in S00809 turned by 90°."""
    for a in (60, 180, 300):
        sh.line(x, y, x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a)), "OUTLINE")
    if neutral:
        sh.dot(x, y, 0.8, "OUTLINE")
        sh.line(x, y, x, y - neutral, "OUTLINE")


def test_link_symbol(sh, x, y, w=8.0):
    """Connecting link, closed — test terminal (IEC 60617 S00044): a bar with
    a stud at each end, centred on (x, y) along the conductor."""
    r = 1.2
    sh.line(x - w / 2 + r, y + r, x + w / 2 - r, y + r, "OUTLINE")
    sh.line(x - w / 2 + r, y - r, x + w / 2 - r, y - r, "OUTLINE")
    sh.arc(x - w / 2 + r, y, r, 90, 270, "OUTLINE")
    sh.arc(x + w / 2 - r, y, r, -90, 90, "OUTLINE")
    sh.circle(x - w / 2 + r, y, r * 0.55, "OUTLINE")
    sh.circle(x + w / 2 - r, y, r * 0.55, "OUTLINE")


def sheet_schematic(sh, fr, ctx):
    x0, y0, w, h = fr.area
    blocks = []
    if ctx.building:
        blocks.append("lv")
    if ctx.ner:
        blocks.append("ner")
    if not blocks:
        blocks = ["lv"]
    bw = w / len(blocks)
    for bi, kind in enumerate(blocks):
        bx = x0 + bi * bw
        if bi:
            sh.line(bx, y0 + 4, bx, y0 + h - 4, "TITLETHIN")
        if kind == "lv":
            _schem_lv(sh, (bx, y0, bw, h), ctx)
        else:
            _schem_ner(sh, (bx, y0, bw, h), ctx)


def _schem_lv(sh, box, ctx):
    x, y, w, h = box
    b = ctx.building or dict(system="TN-S", RA=None, U0=230, device={}, passed=True)
    sysn = b["system"]
    tn = sysn.startswith("TN")
    pen = sysn.startswith("TN-C")
    X0, X1 = x + 10, x + w - 14
    yT = y + h - 26
    sp = 8.0
    yl = [yT - i * sp for i in range(3)]
    yN = yT - 3 * sp
    yPE = yT - 4 * sp
    # source transformer secondary
    sx = X0 + 14
    sh.circle(sx, yT - sp, 11, "OUTLINE")
    _winding_star(sh, sx, yT - sp, 7.5, neutral=0.1)
    sh.text(sx, yT + 13, "SUPPLY", 2.2, "middle", bold=True)
    for i, yy in enumerate(yl):
        sh.line(sx + 11 * math.cos(math.asin(min(1, abs(yy - (yT - sp)) / 11))), yy, X1, yy, "OUTLINE")
        sh.text(X1 + 1.5, yy, f"L{i + 1}", 2.2, valign="middle")
    org = x + w * 0.38                      # origin of the installation
    sh.line(sx, yT - sp, sx, yN, "OUTLINE")
    if pen:
        sh.line(sx, yN, org, yN, "OUTLINE")
        sh.text((sx + org) / 2, yN + 1.2, "PEN", 2.0, "middle", bold=True)
        sh.line(org, yN, X1, yN, "OUTLINE")
        sh.line(org, yN, org, yPE, "OUTLINE"); sh.line(org, yPE, X1, yPE, "OUTLINE")
        sh.dot(org, yN, 0.8)
    else:
        sh.line(sx, yN, X1, yN, "OUTLINE")
        if tn:
            sh.line(sx, yN, sx, yPE, "OUTLINE"); sh.line(sx, yPE, X1, yPE, "OUTLINE")
            sh.dot(sx, yN, 0.8)
    sh.text(X1 + 1.5, yN, "N", 2.2, valign="middle")
    if tn:
        sh.text(X1 + 1.5, yPE, "PE", 2.2, valign="middle")
    # source earthing
    ex_ = sx - 8
    if sysn == "IT":
        sh.line(sx, yN, ex_, yN, "OUTLINE")
        sh.line(ex_, yN, ex_, yN - 6, "OUTLINE")
        _resistor(sh, ex_, yN - 11, 3.4, 10)
        sh.line(ex_, yN - 16, ex_, yN - 22, "OUTLINE")
        earth_symbol(sh, ex_, yN - 22, 0.9)
        sh.text(ex_, yN - 30, "HIGH IMPEDANCE", 1.9, "middle")
        sh.text(ex_, yN - 33.5, "OR ISOLATED", 1.9, "middle")
    else:
        yy0 = yPE if tn and not pen else yN
        sh.line(sx, yy0, ex_, yy0, "OUTLINE")
        sh.line(ex_, yy0, ex_, yy0 - 10, "OUTLINE")
        earth_symbol(sh, ex_, yy0 - 10, 0.9)
        sh.text(ex_, yy0 - 18, "SOURCE EARTH", 1.9, "middle")
    # installation boundary
    bx0 = org - 4
    ybot = yPE - 30 - 34 - 44
    sh.poly([(bx0, yT + 10), (X1 - 2, yT + 10), (X1 - 2, ybot), (bx0, ybot)], True, "BOUNDARY")
    sh.text(X1 - 4, ybot + 3, "CONSUMER'S INSTALLATION", 2.0, "end", bold=True)
    # main device
    dev = (b.get("device") or {})
    rx0 = x + w * 0.52
    sh.rect(rx0, yN - 3, 16, (yT + 3) - (yN - 3), "OUTLINE")
    is_rcd = bool(sysn.startswith("TT") or "RCD" in str(dev.get("basis", "")).upper())
    sh.text(rx0 + 8, yT + 5, "RCD" if is_rcd else "MAIN DEVICE", 2.0, "middle", bold=True)
    ia = dev.get("Ia")
    if ia:
        lab = f"I_Δn = {_f(ia * 1000, 0)} mA" if is_rcd and ia < 5 else f"I_a = {_f(ia, 0)} A"
        sh.text(rx0 + 8, yN - 6.5, lab, 1.9, "middle")
    # class I equipment
    exx, eyy = X1 - 34, yPE - 30
    sh.rect(exx, eyy, 26, 16, "OUTLINE")
    sh.text(exx + 11, eyy + 11, "CLASS I", 2.0, "middle")
    sh.text(exx + 11, eyy + 7, "EQUIPMENT", 2.0, "middle")
    for xx, yy in ((exx + 6, yl[0]), (exx + 13, yN)):
        sh.line(xx, yy, xx, eyy + 16, "OUTLINE"); sh.dot(xx, yy, 0.7)
    # exposed-conductive-part terminal
    pe_symbol(sh, exx + 22, eyy + 3.2, 0.55)
    # MET
    mx0, my = org + 1.0, eyy - 34
    sh.rect(mx0, my - 2.5, 46, 5, "OUTLINE", fill=False)
    sh.text(mx0 + 23, my + 5.5, "MET", 2.4, "middle", bold=True)
    # CPC from the equipment
    sh.poly([(exx + 22, eyy), (exx + 22, my), (mx0 + 46, my)], False, "OUTLINE")
    sh.text(exx + 23.5, (eyy + my) / 2, "CPC", 2.0, valign="middle")
    if tn:
        sh.poly([(exx - 8, yPE), (exx - 8, my + 9), (mx0 + 40, my + 9), (mx0 + 40, my + 2.5)], False, "OUTLINE")
        sh.dot(exx - 8, yPE, 0.7)
        sh.text(exx - 9.5, (yPE + my) / 2 + 6, "MAIN PE", 2.0, "end")
    # main protective bonding
    svcs = [("WATER", "PIPE"), ("GAS", "PIPE"), ("STRUCTURAL", "STEEL")]
    for i, (a1, a2) in enumerate(svcs):
        bxx = mx0 + 8 + i * 15
        sh.line(bxx, my - 2.5, bxx, my - 20, "OUTLINE")
        sh.rect(bxx - 4, my - 24, 8, 4, "THIN")
        sh.text(bxx, my - 28, a1, 1.8, "middle")
        sh.text(bxx, my - 31, a2, 1.8, "middle")
    sh.text(mx0 + 23, my - 36, "MAIN PROTECTIVE BONDING (544.1)", 1.9, "middle")
    # earthing conductor via test link to the installation electrode
    tlx = mx0 - 14
    sh.line(mx0, my, tlx + 4, my, "OUTLINE")
    test_link_symbol(sh, tlx, my, 8.0)
    sh.text(tlx, my + 3.4, "TEST LINK", 1.8, "middle")
    elx = tlx - 14
    sh.line(tlx - 4, my, elx, my, "OUTLINE")
    sh.line(elx, my, elx, my - 12, "OUTLINE")
    earth_symbol(sh, elx, my - 12, 1.0)
    sh.text(elx, my - 21, "INSTALLATION", 1.9, "middle")
    sh.text(elx, my - 24.5, "EARTH ELECTRODE", 1.9, "middle")
    if b.get("RA"):
        sh.text(elx, my - 28, f"R_A = {_f(b['RA'], 2)} Ω", 1.9, "middle", bold=True)
    # rules and data
    ty = max(y + 30, y + h - 192)          # under the diagram, level with the panel beside it
    sh.title_label(x + w / 2, ty, f"EARTHING ARRANGEMENT — {sysn} SYSTEM", "IEC 60364-1, 312.2 — NTS")
    rules = {"TT": "R_A · I_a ≤ 50 V (IEC 60364-4-41, 411.5.3); an RCD is required.",
             "TN-S": "Separate N and PE throughout; Z_s · I_a ≤ U_0 (IEC 60364-4-41, 411.4.4).",
             "TN-C-S": "PEN split at the origin, N and PE separate downstream (411.4.3).",
             "TN-C": "Combined PEN conductor throughout (411.4.3).",
             "IT": "First fault signalled by an insulation monitor; R_A · I_d ≤ 50 V (411.6.2)."}
    sh.text(x + w / 2, ty - 13, rules.get(sysn, ""), 2.0, "middle")
    if b.get("U0"):
        sh.text(x + w / 2, ty - 17.5, f"U_0 = {_f(b['U0'], 0)} V; installation check: "
                                     f"{'PASSED' if b.get('passed') else 'NOT PASSED'} (module 6).", 2.0, "middle")


def _schem_ner(sh, box, ctx):
    x, y, w, h = box
    nr = ctx.ner
    cx = x + w * 0.42
    top = y + h - 40
    sh.text(cx, top + 26, (f"{_f(nr.get('V_ll'), 1)} kV " if nr.get("V_ll") else "") + "TRANSFORMER / GENERATOR",
            2.4, "middle", bold=True)
    sh.circle(cx, top, 14, "OUTLINE")
    _winding_star(sh, cx, top, 9, neutral=0.1)
    for a in (60, 180, 300):
        xx = cx + 14 * math.cos(math.radians(a))
        yy = top + 14 * math.sin(math.radians(a))
        sh.line(xx, yy, xx + 9 * math.cos(math.radians(a)), yy + 9 * math.sin(math.radians(a)), "OUTLINE")
    sh.text(cx - 2.5, top - 19, "STAR POINT", 1.9, "end")
    # neutral bushing → CT → NER → grid
    sh.line(cx, top, cx, top - 70, "OUTLINE")
    sh.circle(cx, top - 28, 3.4, "OUTLINE")
    sh.line(cx + 3.4, top - 28, cx + 20, top - 28, "THIN")
    sh.rect(cx + 20, top - 32, 16, 8, "OUTLINE")
    sh.text(cx + 28, top - 28, "51N", 2.2, "middle", "middle", bold=True)
    sh.text(cx + 28, top - 35.5, "EARTH-FAULT RELAY", 1.9, "middle")
    method = nr.get("method") or "solid"
    sh.poly([(cx - 16, top - 40), (cx + 16, top - 40), (cx + 16, top - 78), (cx - 16, top - 78)], True, "BOUNDARY")
    if method in ("low_resistance", "high_resistance"):
        _resistor(sh, cx, top - 59, 7, 22)
        lab = ["NEUTRAL EARTHING RESISTOR", f"R = {_f(nr.get('R'), 2)} Ω",
               f"I = {_f(nr.get('I'), 0)} A for {_f(nr.get('t'), 0)} s",
               f"U = {_f(nr.get('V_ln'), 0)} V phase-to-earth"]
    elif method == "reactance":
        for i in range(5):
            sh.arc(cx, top - 49 - i * 4, 2.2, 270, 90, "OUTLINE")
        lab = ["NEUTRAL EARTHING REACTOR", f"I = {_f(nr.get('I'), 0)} A"]
    else:
        sh.line(cx, top - 40, cx, top - 78, "EARTH")
        lab = ["SOLIDLY EARTHED NEUTRAL"]
    yy = top - 46
    for i, t in enumerate(lab):
        sh.text(cx + 20, yy - i * 4.4, t, 2.2 if i == 0 else 2.0, bold=(i == 0))
    sh.line(cx, top - 78, cx, top - 96, "EARTH")
    sh.line(cx - 34, top - 96, cx + 34, top - 96, "EARTH")
    for xx in (cx - 34, cx + 34):
        sh.line(xx, top - 96, xx, top - 104, "EARTH")
        rod_symbol(sh, xx, top - 106, 1.8)
    sh.dot(cx, top - 96, 0.9, "EARTH")
    sh.text(cx, top - 113, f"TO MAIN EARTH GRID BY TWO ROUTES — {ctx.cond} mm² Cu", 2.0, "middle")
    sh.text(cx + 18, top - 87, "NER FRAME EARTHED", 1.9)
    sh.title_label(x + w / 2, max(y + 30, y + h - 192), "SYSTEM NEUTRAL EARTHING", "IEEE Std 142 — NTS")
    rows = [["Method", str(method).replace("_", " ")]]
    if nr.get("three_IC0") is not None:
        rows.append(["System charging current 3I_C0", f"{_f(nr['three_IC0'], 2)} A"])
    if nr.get("R"):
        rows.append(["Resistor / current / time", f"{_f(nr['R'], 2)} Ω / {_f(nr['I'], 0)} A / {_f(nr['t'], 0)} s"])
    table(sh, x + 8, top - 122, [w * 0.5, w * 0.4], rows, None, rh=4.6, h=2.0)


# ---------------------------------------------------------------------------
# sheet 901 — bill of materials
# ---------------------------------------------------------------------------

def _sentence(t):
    """'EXOTHERMIC WELD, CROSS (X) TYPE' -> 'Exothermic weld, cross (X) type'."""
    out = []
    for i, wd in enumerate(t.split(" ")):
        core = wd.strip("(),")
        keep = len(core) <= 1 or any(c.isdigit() for c in core) or core in ("IEC", "IEEE", "MET", "PVC", "NER")
        out.append(wd if keep else (wd.capitalize() if i == 0 else wd.lower()))
    return " ".join(out)


def bill_of_materials(ctx):
    rows = []
    wf = 1 + (ctx.wastage or 0) / 100.0

    def add(desc, spec, qty, unit, basis):
        rows.append([str(len(rows) + 1), desc, spec, qty, unit, basis])

    if ctx.grid or ctx.bem_items:
        segs, rods = (ctx.grid["conductors"], ctx.grid["rods"]) if ctx.grid else bem_conductors(ctx.bem_items)
        Lc = total_length(segs)
        J = grid_joints(segs, rods)
        add(f"Bare stranded copper conductor {ctx.cond} mm² (grid)", "IEC 60228 class 2",
            _f(math.ceil(round(Lc * wf, 6)), 0), "m", f"{_f(Lc, 1)} m on plan + {_f(ctx.wastage, 0)} %")
        if rods:
            add(f"{_sentence(ROD_MATERIALS[ctx.rod_mat]['label'])} Ø{_f(ctx.rod_d, 1)} mm, "
                f"{_f(ctx.rod_section)} m sections", ROD_MATERIALS[ctx.rod_mat]["std"],
                str(len(rods) * ctx.rod_nsec), "No.", f"{len(rods)} rods × {ctx.rod_nsec} sections")
            if ctx.rod_nsec > 1:
                add("Rod coupling, silicon / aluminium bronze", "BS 7430, 9.10",
                    str(len(rods) * (ctx.rod_nsec - 1)), "No.", "between sections")
            add("Driving head / stud (re-usable)", "—", str(max(2, len(rods) // 10)), "No.", "installation tool")
        for kind, n in (("X", len(J["X"])), ("T", len(J["T"])), ("L", len(J["L"])), ("S", len(J["S"]))):
            if n:
                add(_sentence(ctx.joint_name(kind)), "IEEE 837 / IEC 62561-1", str(n), "No.",
                    "counted from the plan")
        if rods:
            add(_sentence(ctx.joint_name("R")), "IEEE 837 / IEC 62561-1", str(len(rods) - min(ctx.n_test_pits, len(rods))),
                "No.", "rods not in inspection pits")
        if ctx.grid and ctx.grid.get("hs"):
            g = ctx.grid
            # the layer covers the switchyard and runs 1 m beyond the fence (sheet 102,
            # detail 4); with the fence fo inside the perimeter conductor that is the
            # grid outline grown by (1 - fo) on every side
            ext = 2.0 * max(0.0, 1.0 - ctx.fence_off) if ctx.fence else 0.0
            area = (g["Lx"] + ext) * (g["Ly"] + ext) if g["shape"] in ("rectangular", "square") else g["A"]
            add("Crushed rock surface layer", f"ρ ≥ {_f(g['rho_s'], 0)} Ω·m wet",
                _f(area * g["hs"] * wf, 1), "m³", f"{_f(area, 0)} m² × {_f(g['hs'] * 1000, 0)} mm")
        if ctx.fence and ctx.grid:
            g = ctx.grid
            f = ctx.fence_off
            per = 2 * ((g["Lx"] - 2 * f) + (g["Ly"] - 2 * f))
            nb = 6 + int(per // max(ctx.fence_bond, 1))
            add(f"Fence bonding tail {ctx.cond} mm² Cu with connector", "IEEE 80, 17.3", str(nb), "No.",
                f"corners, gate posts, every {_f(ctx.fence_bond)} m")
            add("Flexible tinned copper braid for gates", "—", "2", "No.", "one per gate leaf")
    npits = (ctx.pit or {}).get("n") or 0
    npits = max(npits, ctx.n_test_pits if (ctx.grid or ctx.bem_items) else 0)
    if npits:
        hc = HOUSING[ctx.housing]
        add(f"Earth inspection pit {hc['inner']}×{hc['inner']} mm, class {ctx.housing} cover",
            "IEC 62561-5", str(npits), "No.", "sheet 201")
        add("Test link (disconnecting link) on insulators", "BS 7430; IEC 60364-5-54 542.4.2", str(npits), "No.", "")
        add("Rod-to-cable clamp, bronze", "IEC 62561-1", str(npits), "No.", "")
        if ctx.pit and ctx.pit.get("volume"):
            add(f"Backfill: {ctx.pit.get('backfill') or 'low-resistivity material'}", "IEC 62561-7",
                _f(ctx.pit["volume"] * npits * wf, 2), "m³", f"{_f(ctx.pit['volume'], 3)} m³ per pit")
    if not (ctx.grid or ctx.bem_items) and (ctx.pit or ctx.building):
        add(_sentence(ctx.rod_label), ROD_MATERIALS[ctx.rod_mat]["std"], str(max(1, npits)), "No.", "")
    # equipment tails
    for key, n in ctx.equipment.items():
        e = EQUIPMENT[key]
        size = ctx.cond if e["full"] else 16
        add(f"Earthing tail: {e['name']}, {size} mm² Cu, with lug", "sheet 302",
            str(n * e["tails"]), "No.", f"{n} × {e['tails']} connections")
    # MET
    bw, bt = ctx.met_bar
    nways = max(4, ctx.met_ways)
    pitch = 50.0 if ctx.met_bolt == "M12" else 40.0
    Lbar = 2 * 60 + (nways - 1) * pitch
    add(f"Main earthing terminal bar {bw}×{bt}×{_f(Lbar, 0)} mm tinned Cu, {nways} ways",
        "IEC 60364-5-54, 542.4", "1", "No.", "sheet 202")
    add("LV epoxy insulators 40 mm", "—", "2", "No.", "")
    if ctx.lps:
        L = ctx.lps
        dcs = lps_layout(ctx)
        add("Down-conductor 50 mm² Cu", "IEC 62305-3 Table 6", _f(len(dcs) * (L["H"] + 1.5) * wf, 0), "m",
            f"{len(dcs)} × (H + 1.5 m)")
        add("Test joint", "IEC 62305-3, 5.3.6", str(len(dcs)), "No.", "")
        if "B" in str(L["arrangement"]).upper():
            add("Ring earth electrode 50 mm² Cu", "IEC 62305-3, 5.4.2.2",
                _f(2 * (L["W"] + L["D"] + 4) * wf, 0), "m", "1 m from the walls")
        add("Air-termination mesh conductor 50 mm² Cu", "IEC 62305-3, Table 6", "AR", "m",
            f"mesh ≤ {L['table']['mesh']} m")
    if ctx.ner and ctx.ner.get("R") and ctx.ner.get("method") in ("low_resistance", "high_resistance"):
        add(f"Neutral earthing resistor {_f(ctx.ner['R'], 2)} Ω, {_f(ctx.ner['I'], 0)} A, {_f(ctx.ner['t'], 0)} s",
            "IEEE 32 / IEEE 142", "1", "No.", "sheet 501")
    add("Warning label 'Safety electrical connection — do not remove'", "BS 7671, 514.13.1",
        str(max(1, npits) + 1), "No.", "each electrode connection and MET")
    add("Joint compound, PVC tape, stainless fixings", "—", "AR", "lot", "")
    return rows


def sheet_bom(sh, fr, ctx, rows):
    x0, y0, w, h = fr.area
    sh.text(x0, y0 + h - 4, "BILL OF MATERIALS — EARTHING SYSTEM", 3.5, bold=True)
    sh.text(x0, y0 + h - 9.5, f"Quantities measured from the drawings; conductor and consumables include "
                              f"{_f(ctx.wastage, 0)} % allowance. Contractor to verify before ordering.", 2.1)
    table(sh, x0, y0 + h - 13, [10, w * 0.40, w * 0.22, 16, 12, w - 38 - w * 0.62], rows,
          ["ITEM", "DESCRIPTION", "SPECIFICATION / STANDARD", "QTY", "UNIT", "BASIS"],
          rh=5.0, h=2.0, aligns=["middle", "start", "start", "end", "middle", "start"], wrap_cols={1, 2, 5})


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def _plan_sheets(ctx):
    sel = ctx.opt.get("sheets")
    want = (lambda c: True) if not sel else (lambda c: c in sel)
    out = [("000", "DRAWING REGISTER, GENERAL NOTES, LEGEND AND DESIGN VERIFICATION")]
    if ctx.grid or ctx.bem_items:
        out.append(("101", "EARTH GRID LAYOUT PLAN"))
        out.append(("102", "TYPICAL INSTALLATION SECTIONS"))
    out.append(("201", "EARTH PIT AND TEST LINK DETAILS"))
    out.append(("202", "MAIN EARTHING TERMINAL (EARTH BAR) DETAILS"))
    out.append(("301", "EARTHING CONNECTION DETAILS"))
    out.append(("302", "EQUIPMENT BONDING DETAILS"))
    out.append(("303", "EARTHING CONDUCTOR SELECTION CHART AND SIZING DATA"))
    if ctx.lps:
        out.append(("401", "LIGHTNING PROTECTION — EARTH TERMINATION PLAN AND DETAILS"))
    if ctx.building or ctx.ner:
        out.append(("501", "EARTHING ARRANGEMENT SCHEMATICS"))
    out.append(("901", "BILL OF MATERIALS"))
    return [s for s in out if s[0] == "000" or want(s[0])]


def build(data: dict) -> dict:
    """Generate the drawing set.  data = {results, options, meta, version}."""
    ctx = Ctx(data)
    plan = _plan_sheets(ctx)
    total = len(plan)
    pre = ctx.meta["prefix"]
    sheets = []
    register = []
    checks = []
    bom_rows = bill_of_materials(ctx)
    # register first (scales known after drawing, so build in two passes)
    built = []
    for i, (code, title) in enumerate(plan, 1):
        sh = Sheet(ctx.meta["size"], f"{pre}-{code}", title)
        fr = Frame(sh)
        scale = "AS SHOWN"
        notes, bom = [], []
        if code == "000":
            scale = "—"
        elif code == "101":
            n = sheet_plan(sh, fr, ctx)
            scale = f"1:{n}"
            notes = [f"Grid co-ordinates in metres from the grid origin (bottom-left corner).",
                     f"{ctx.cond_label}, buried {_f((ctx.grid or {}).get('h', 0.5) * 1000, 0)} mm below "
                     f"native grade; joints at every crossing (sheet 301).",
                     f"Earth rods {ctx.rod_label}; rods marked TP are in inspection pits with test links "
                     f"(sheet 201).",
                     "Connect every item of equipment shown on the equipment layout to the nearest grid "
                     "conductor with the tails of sheet 302.",
                     "Where a conductor meets an obstruction, keep the mesh connected and record the "
                     "as-built route; do not reduce the conductor size."]
            if ctx.fence:                 # note 6: flag 6 on the plan points to it
                notes.append(f"Fence {_f(ctx.fence_off)} m inside the perimeter conductor, bonded to the grid "
                             f"(IEEE Std 80, 17.3). Gates bonded with flexible braid.")
            if ctx.grid and ctx.grid.get("notch"):
                nt = ctx.grid["notch"]
                g_ = ctx.grid
                shp = "L" if str(g_["shape"]).lower() == "l" else "T"
                notes.append(f"{shp}-shaped outline: {_f(g_['Lx'])} × {_f(g_['Ly'])} m less "
                             f"{'one notch' if shp == 'L' else 'two notches'} of {_f(nt['a'])} × {_f(nt['b'])} m, "
                             f"set on the conductor lines to match the design area and conductor length "
                             f"(drawn: {_f(nt['area'], 0)} m², {_f(nt['Lc'], 0)} m; design: {_f(g_['A'], 0)} m², "
                             f"{_f(g_['Lc'], 0)} m). Confirm the notch position against the site layout.")
            elif ctx.grid and str(ctx.grid["shape"]).lower() == "irregular":
                notes.append("Irregular outline: the IEEE 80 module uses only its area, perimeter and conductor "
                             "length, so the plan shows the bounding grid. Draw from the numerical solver "
                             "(module 5) layout before issue.")
        elif code == "102":
            sheet_sections(sh, fr, ctx)
            notes = ["Trench bottom to be level and free of stones; lay the conductor taut and straight.",
                     "Backfill with selected excavated soil or imported fine soil, never with rubble, "
                     "cement or salt; compact in layers.",
                     "Rod top at grid depth; drive vertically; where rock prevents driving, inform the "
                     "engineer — do not cut the rod.",
                     "Above-ground tails: green-yellow PVC-covered conductor or bare copper protected "
                     "against mechanical damage.",
                     "Section A: see plan sheet 101 for location."]
            bom = [(1, f"BARE STRANDED Cu CONDUCTOR {ctx.cond} mm²", "AR", "m"),
                   (2, ctx.rod_label.replace("EARTH ROD", "ROD"), "AR", "No."),
                   (3, "PVC SLEEVE Ø50 mm, 450 mm LONG", "AR", "No."),
                   (4, "NON-HARDENING SEALING COMPOUND", "AR", "—")]
        elif code == "201":
            n, bom = sheet_pit(sh, fr, ctx)
            notes = ["Install the housing level with the finished surface; the cover shall be removable "
                     "with a tool only and marked 'EARTH'.",
                     f"Housing class {ctx.housing} to IEC 62561-5 for the traffic at its location "
                     "(L: walkways; M: slow cars; H: slow multi-axle vehicles).",
                     "The test link allows the rod to be disconnected and measured without disturbing "
                     "the grid (BS 7430, 9.10 note 1).",
                     "Mix and place the backfill to the manufacturer's instructions (IEC 62561-7); "
                     "keep it moist during curing.",
                     "Record the resistance of each pit at commissioning and in the dry season."]
            scale = f"AS SHOWN"
        elif code == "202":
            n, bom = sheet_met(sh, fr, ctx)
            notes = ["Mount at an accessible height in the main switchroom; keep 50 mm clear of the wall.",
                     "Each conductor terminated with its own lug and bolt so that it can be removed "
                     "individually with a tool (IEC 60364-5-54, 542.4.2).",
                     "Label every way with the destination of its conductor.",
                     "Protective bonding conductors to IEC 60364-5-54, 544.1: not less than half the "
                     "largest PE, 6 mm² Cu minimum, need not exceed 25 mm² Cu.",
                     "Fix the 'SAFETY ELECTRICAL CONNECTION — DO NOT REMOVE' label beside the bar."]
        elif code == "301":
            bom = sheet_connections(sh, fr, ctx)
            scale = "NTS"
            notes = ["Connections drawn to the proportions of the conductor; not to scale.",
                     "Exothermic moulds, cartridges and handle clamps from one manufacturer, sized for the "
                     "conductor and rod; follow the manufacturer's procedure, dry and preheat the mould.",
                     "Compression connectors: irreversible, installed with the specified die and tool.",
                     "Inspect every buried joint before backfilling and record it on the as-built plan.",
                     "Above-ground bolted joints: clean bright, apply joint compound, torque ≥ 20 N·m."]
        elif code == "302":
            bom = sheet_bonding(sh, fr, ctx)
            scale = "NTS"
            notes = ["Equipment details are diagrammatic; locate earth pads per the manufacturer's drawings.",
                     "High-current items (transformers, breakers, switches, arresters) have two leads run "
                     "in opposite directions (IEEE Std 80, 9.6).",
                     "Surge arrester earth leads: as short and straight as possible.",
                     "Cable tray: earth at both ends; continuity jumper across every joint unless the "
                     "manufacturer declares the joint as a protective conductor.",
                     "Sizes in the chart are the minimum; do not reduce below them."]
        elif code == "303":
            sheet_chart(sh, fr, ctx)
            scale = "—"
            notes = ["Sizes are minimum copper cross-sections; equivalent conductance is required for "
                     "other materials.",
                     "Fault-current conductors (grid, HV equipment tails, arrester and neutral leads) are "
                     "sized for the full fault current: equal division between parallel leads shall not "
                     "be assumed (IEEE Std 80, 9.6).",
                     "Above-ground tails: green-yellow PVC-covered copper, or bare copper where exposed "
                     "to the same conditions as the grid.",
                     "Where the connected system has a larger PE, the larger size governs."]
        elif code == "401":
            n, bom = sheet_lps(sh, fr, ctx)
            scale = "AS SHOWN"
            notes = ["Down-conductors equally spaced, one at each exposed corner (IEC 62305-3, 5.3.3).",
                     "Test joint on every down-conductor, opened only with a tool (5.3.6).",
                     "Ring earth electrode ≥ 0.5 m deep, about 1 m from the external walls (5.4.3); "
                     "connect it to the main earth grid / MET.",
                     "Keep the separation distance s from internal installations or bond them "
                     "(IEC 62305-3, 6.3).",
                     "Air-termination positions from module 8; roof conductors fixed at ≈ 1 m spacing."]
        elif code == "501":
            sheet_schematic(sh, fr, ctx)
            scale = "NTS"
            notes = ["Schematics show the earthing principle only; see the single-line diagrams for ratings.",
                     "Main protective bonding of water, gas and structural steel at the point of entry "
                     "(IEC 60364-5-54, 544.1).",
                     "Earth electrode connected to the MET through a test link (542.4.2)."]
            if ctx.ner:
                notes.append("Neutral earthing resistor rated for the stated current and time; "
                             "earth its frame and the neutral side to the grid by two routes.")
        elif code == "901":
            sheet_bom(sh, fr, ctx, bom_rows)
            scale = "—"
            notes = ["Quantities are for estimating; the contractor shall measure the as-built quantities.",
                     "All materials to carry the manufacturer's test certificates against the standards "
                     "listed.", "AR = as required."]
        built.append((code, title, sh, fr, scale, notes, bom))
        register.append(dict(number=sh.number, title=title, rev=ctx.meta["rev"], scale=scale))
    # second pass: register sheet content and frames
    fails = [c["item"] for c in design_checks(ctx) if c["status"] == "FAIL"]
    ctx.failed = (fails[0] if len(fails) == 1 else f"{len(fails)} items") if fails else None
    for i, (code, title, sh, fr, scale, notes, bom) in enumerate(built, 1):
        if code == "000":
            checks = sheet_register(sh, fr, ctx, register)
            notes = general_notes(ctx)
            scale = "—"
        draw_frame(sh, ctx, fr, i, total, scale, notes, bom)
        sheets.append(sh)
    pdf = cad.to_pdf(sheets, title=f"{ctx.meta['project']} — earthing drawings", author=ctx.meta["engineer"])
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{pre}_drawings.pdf", pdf)
        for sh in sheets:
            z.writestr(f"dxf/{sh.number}.dxf", cad.to_dxf(sh))
            z.writestr(f"svg/{sh.number}.svg", cad.to_svg(sh))
        z.writestr("register.csv", "Drawing No.,Title,Rev,Scale\n" + "\n".join(
            f'{r["number"]},"{r["title"]}",{r["rev"]},{r["scale"]}' for r in register) + "\n")
        z.writestr("bill_of_materials.csv", "Item,Description,Specification,Qty,Unit,Basis\n" + "\n".join(
            ",".join('"' + str(c).replace('"', "'") + '"' for c in r) for r in bom_rows) + "\n")
        if getattr(ctx, "rod_schedule", None):
            z.writestr("rod_schedule.csv", "Rod,X (m),Y (m),L (m),Inspection pit\n" + "\n".join(
                ",".join(str(c).replace("—", "no") for c in r) for r in ctx.rod_schedule) + "\n")
        z.writestr("README.txt", _readme(ctx))
    return dict(
        sheets=[dict(number=s.number, title=s.title, svg=cad.to_svg(s)) for s in sheets],
        register=register, checks=checks, bom=bom_rows,
        pdf_b64=base64.b64encode(pdf).decode("ascii"),
        zip_b64=base64.b64encode(zbuf.getvalue()).decode("ascii"),
        filename=pre, conductor=dict(size=ctx.cond, basis=ctx.cond_basis))


def _readme(ctx):
    lay = "\n".join(f"  {k:<10} {w:.2f} mm   colour {c:<3} {lt}" for k, (w, c, lt) in cad.LAYERS.items())
    return f"""Earthing System — construction drawing set
Project : {ctx.meta['project']}
Status  : {STATUS[ctx.meta['status']]}, revision {ctx.meta['rev']}, {ctx.meta['date']}

Contents
  {ctx.meta['prefix']}_drawings.pdf   all sheets, vector PDF ({ctx.meta['size']})
  dxf/                    one AutoCAD R12 DXF per sheet, paper units = mm, 1 unit = 1 mm
  svg/                    one SVG per sheet
  register.csv            drawing register
  bill_of_materials.csv   quantities
{"  rod_schedule.csv        every earth rod with its co-ordinates (sheet 101)" + chr(10) if getattr(ctx, "rod_schedule", None) else ""}
DXF layers (DXF R12 carries no line weight: plot by colour with these pens, ISO 128-2)
{lay}

Each sheet is drawn at 1:1 on paper; the scale of every view is written under its title.
"""
