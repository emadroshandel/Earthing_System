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
A small 2-D drafting kernel for the construction drawings (module 11).

Every sheet is built once, in millimetres on the paper with the origin at the
bottom-left corner of the trimmed sheet, as a list of primitives (lines,
polylines, circles, arcs, solid fills and text).  The same list is then written
out three ways, with nothing but the standard library:

* SVG  — for the preview in the application;
* PDF  — a true vector, multi-page document (PDF 1.4, base-14 Helvetica and
  Symbol fonts, so nothing has to be embedded);
* DXF  — AutoCAD R12 (AC1009) ASCII, the most widely readable CAD exchange
  format, one file per sheet, with ISO 128 line types on named layers.

Drafting conventions followed
-----------------------------
* ISO 5457  — sheet sizes, 20 mm filing margin on the left and 10 mm on the
  other edges, centring marks and a grid-reference border;
* ISO 7200  — title-block data fields (owner, title, identifier, revision,
  date of issue, sheet number, language, document type, status, creator,
  approver);
* ISO 128-2 — line types and the 0.25 / 0.35 / 0.5 / 0.7 mm width series;
* ISO 3098  — lettering: the height ``h`` everywhere in this module is the
  capital height (2.5, 3.5, 5 and 7 mm are used);
* ISO 129-1 — dimensioning: thin extension and dimension lines, closed filled
  arrowheads, text above the dimension line and readable from the bottom or the
  right of the sheet;
* ISO 5455  — preferred scales (1:1, 1:2, 1:5, 1:10, 1:20, 1:50 … ×10ⁿ);
* ISO 5456-2 — first-angle projection symbol.
"""

from __future__ import annotations

import math
import random
import re
import zlib

# ---------------------------------------------------------------------------
# Sheet sizes (ISO 216 A series) and layers (ISO 128-2 line widths)
# ---------------------------------------------------------------------------

SHEETS = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0),
          "A1": (841.0, 594.0), "A0": (1189.0, 841.0)}

# ISO 5455 preferred scales (reduction), plus 1:25 and 1:250 which are widely
# used for building work and are allowed by ISO 5455 for special purposes.
SCALES = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000]

# name: (line width mm, DXF colour, line type)
# DXF R12 has no line weights, so each layer gets its own colour and the CAD
# plot style maps colour to pen width (the usual CTB convention): the width is
# also written in the layer name table description of the README.
LAYERS = {
    # Two widths per line type in the ratio 2:1 (IEC 61082-1:2014, 5.10), from
    # the series 0.25 / 0.5 / 1.0 mm; the frame is the 1.0 mm extra-wide line.
    "0":        (0.25, 7, "CONTINUOUS"),
    "FRAME":    (1.00, 7, "CONTINUOUS"),
    "TITLE":    (0.50, 7, "CONTINUOUS"),
    "TITLETHIN": (0.25, 8, "CONTINUOUS"),
    "OUTLINE":  (0.50, 7, "CONTINUOUS"),
    "THIN":     (0.25, 8, "CONTINUOUS"),
    "EARTH":    (0.50, 3, "CONTINUOUS"),     # earthing conductors on plans/details
    "ELECTRODE": (0.50, 3, "CONTINUOUS"),
    "HIDDEN":   (0.25, 4, "DASHED"),
    "CENTRE":   (0.25, 1, "CENTER"),
    "PHANTOM":  (0.25, 6, "PHANTOM"),
    "BOUNDARY": (0.25, 6, "CENTER"),     # boundary frame, IEC 60617 S00064 (IEC 61082-1, 7.1.5)
    "DIM":      (0.25, 2, "CONTINUOUS"),
    "TEXT":     (0.25, 7, "CONTINUOUS"),
    "HATCH":    (0.25, 9, "CONTINUOUS"),
    "FENCE":    (0.50, 5, "FENCE"),
}

# Text heights of IEC 61082-1:2014, 5.11 (ISO 3098): every requested height is
# set at the largest of these not exceeding it, so a layout computed for the
# requested height never grows.
TEXT_SERIES = (1.8, 2.5, 3.5, 5.0, 7.0, 10.0)


def std_height(h):
    return max([v for v in TEXT_SERIES if v <= h + 1e-6] or [TEXT_SERIES[0]])


def fit(s, width, h, bold=False):
    """Largest standard height not above h at which s fits in width; at the
    smallest height (1.8 mm) the text is shortened with an ellipsis instead,
    so fitted text can never run past its box."""
    s = str(s)
    for hh in sorted((v for v in TEXT_SERIES if v <= std_height(h)), reverse=True):
        if text_width(s, hh, bold) <= width:
            return s, hh
    hh = TEXT_SERIES[0]
    while len(s) > 1 and text_width(s + "…", hh, bold) > width:
        s = s[:-1].rstrip()
    return s + "…", hh


# ISO 128-2 dash patterns in mm, for a 0.25-0.35 mm line (dash, gap, ...).
DASH = {"CONTINUOUS": None, "DASHED": (6.0, 1.5), "CENTER": (12.0, 1.5, 0.5, 1.5),
        "PHANTOM": (12.0, 1.5, 0.5, 1.5, 0.5, 1.5), "FENCE": (4.0, 1.0, 0.5, 1.0)}

# Helvetica advance widths (1/1000 em), ASCII 32-126 (Adobe AFM).
_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
         556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
         1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
         667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
         333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
         556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_HELVB = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
          556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
          975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
          667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
          333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
          611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]
CAP = 0.718          # Helvetica capital height / em
_SUP = {"²": "2", "³": "3", "¹": "1"}

# Characters outside WinAnsi that the PDF writer takes from the Symbol font.
_SYMBOL = {"µ": 0x6D, "Ω": 0x57, "ρ": 0x72, "λ": 0x6C, "π": 0x70, "Δ": 0x44, "≤": 0xA3, "≥": 0xB3,
           "√": 0xD6, "α": 0x61, "β": 0x62, "θ": 0x71, "φ": 0x66, "σ": 0x73, "τ": 0x74,
           "Σ": 0x53, "∅": 0xC6, "≈": 0xBB, "→": 0xAE, "∞": 0xA5, "η": 0x68, "ε": 0x65}
_SYMW = {"µ": 576, "Ω": 768, "ρ": 549, "λ": 549, "π": 549, "Δ": 612, "≤": 549, "≥": 549, "√": 549,
         "α": 631, "β": 549, "θ": 521, "φ": 521, "σ": 603, "τ": 439, "Σ": 592, "∅": 823,
         "≈": 549, "→": 987, "∞": 713, "η": 603, "ε": 439}
# WinAnsi code points above 127 that are used in the drawings.
_WINANSI = {"²": 0xB2, "³": 0xB3, "°": 0xB0, "±": 0xB1, "×": 0xD7, "·": 0xB7,
            "–": 0x96, "—": 0x97, "Ø": 0xD8, "ø": 0xF8, "½": 0xBD, "¼": 0xBC, "¾": 0xBE,
            "é": 0xE9, "‘": 0x91, "’": 0x92, "“": 0x93, "”": 0x94, "•": 0x95, "©": 0xA9,
            "÷": 0xF7, "¹": 0xB9, "…": 0x85}
_WIDE = {"²": 345, "³": 345, "µ": 576, "°": 400, "±": 584, "µ": 556, "×": 584, "·": 278, "–": 556,
         "—": 1000, "Ø": 778, "ø": 611, "½": 834, "¼": 834, "¾": 834, "é": 556, "‘": 222,
         "’": 222, "“": 333, "”": 333, "•": 350, "©": 737, "÷": 584, "¹": 333, "…": 1000}


_SUB = re.compile(r"(?<=[A-Za-z0-9\u0394\u03c1\u03b8])_([A-Za-z0-9\u0394]{1,3})(?![A-Za-z0-9])")


def _script_pieces(s: str) -> list:
    """Split s into (text, kind) runs: kind 1 superscript (², ³, ¹), -1 an
    index written R_A, I_C0 (one to three letters or digits), 0 normal."""
    out = []

    def put(t, k):
        if not t:
            return
        if out and out[-1][1] == k:
            out[-1] = (out[-1][0] + t, k)
        else:
            out.append((t, k))
    pos = 0
    for m in list(_SUB.finditer(s)) + [None]:
        seg = s[pos:m.start()] if m else s[pos:]
        for c in seg:
            put(_SUP[c], 1) if c in _SUP else put(c, 0)
        if m:
            put(m.group(1), -1)
            pos = m.end()
    return out


def plain(s: str) -> str:
    """The text as it reads when the indices are set: R_A -> RA."""
    return "".join(t for t, _ in _script_pieces(str(s)))


def text_width(s: str, h: float, bold: bool = False) -> float:
    """Width in mm of a string set in Helvetica with capital height h (mm);
    superscripts and indices (R_A) are measured at their reduced size."""
    s = str(s)
    if "_" in s or any(c in _SUP for c in s):
        pcs = _script_pieces(s)
        if not (len(pcs) == 1 and pcs[0][1] == 0):
            return sum(text_width(t, h * (0.62 if k else 1.0), bold) for t, k in pcs)
        s = pcs[0][0] if pcs else ""
    tab = _HELVB if bold else _HELV
    w = 0
    for ch in str(s):
        o = ord(ch)
        if 32 <= o <= 126:
            w += tab[o - 32]
        elif ch in _WIDE:
            w += _WIDE[ch]
        elif ch in _SYMW:
            w += _SYMW[ch]
        else:
            w += 600
    return w / 1000.0 * h / CAP


def wrap(text: str, width: float, h: float, bold: bool = False) -> list:
    """Greedy word wrap to a width in mm.  Explicit newlines are kept."""
    out = []
    for para in str(text).split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            trial = (line + " " + w) if line else w
            if text_width(trial, h, bold) <= width or not line:
                line = trial
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def nice_scale(extent_mm: float, avail_mm: float) -> int:
    """Smallest preferred reduction 1:n with which a model extent fits."""
    for n in SCALES:
        if extent_mm / n <= avail_mm:
            return n
    return SCALES[-1]


def fmt_len(v_mm: float, unit: str = "mm") -> str:
    """Dimension text: millimetres as integers, metres to two decimals."""
    if unit == "m":
        s = f"{v_mm / 1000.0:.2f}"
        return s
    if abs(v_mm - round(v_mm)) < 0.05:
        return str(int(round(v_mm)))
    return f"{v_mm:.1f}"


# ---------------------------------------------------------------------------
# Sheet: a list of primitives in paper millimetres (y up)
# ---------------------------------------------------------------------------

class Sheet:
    def __init__(self, size: str = "A3", number: str = "", title: str = ""):
        if size not in SHEETS:
            raise ValueError(f"Unknown sheet size '{size}'.")
        self.size = size
        self.W, self.H = SHEETS[size]
        self.items = []
        self.number = number
        self.title = title

    # ---- primitives --------------------------------------------------------
    def line(self, x1, y1, x2, y2, layer="THIN"):
        self.items.append(("L", layer, (float(x1), float(y1), float(x2), float(y2))))

    def poly(self, pts, closed=False, layer="THIN", fill=False):
        pts = [(float(x), float(y)) for x, y in pts]
        if len(pts) < 2:
            return
        self.items.append(("P", layer, (pts, bool(closed), bool(fill))))

    def rect(self, x, y, w, h, layer="THIN", fill=False):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True, layer, fill)

    def circle(self, cx, cy, r, layer="THIN", fill=False):
        self.items.append(("C", layer, (float(cx), float(cy), float(r), bool(fill))))

    def arc(self, cx, cy, r, a0, a1, layer="THIN"):
        """Counter-clockwise arc from a0 to a1 (degrees)."""
        self.items.append(("A", layer, (float(cx), float(cy), float(r), float(a0), float(a1))))

    def text(self, x, y, s, h=2.5, anchor="start", valign="baseline", rot=0.0,
             layer="TEXT", bold=False):
        """Text with capital height h.  anchor: start|middle|end; valign:
        baseline|middle|top|bottom.  The insertion point is reduced to the
        left/centre/right of the baseline here, so every writer is identical."""
        s = str(s)
        if s == "":
            return
        h = std_height(h)
        dy = {"baseline": 0.0, "bottom": 0.0, "middle": -h / 2.0, "top": -h}[valign]
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        # shift perpendicular to the text direction
        x += -sa * dy
        y += ca * dy
        if not any(c in _SUP for c in s) and "_" not in s:
            self.items.append(("T", layer, (float(x), float(y), s, float(h), anchor,
                                            float(rot), bool(bold))))
            return
        # Superscript digits (mm², m³) are set as smaller raised text, and an
        # index written as R_A, t_c or 3I_C0 as smaller lowered text, so they
        # look the same in every viewer and in CAD, whatever its font.
        pieces = _script_pieces(s)
        if len(pieces) == 1 and pieces[0][1] == 0:
            self.items.append(("T", layer, (float(x), float(y), pieces[0][0], float(h), anchor,
                                            float(rot), bool(bold))))
            return
        widths = [text_width(t, h * (0.62 if k else 1.0), bold) for t, k in pieces]
        W = sum(widths)
        off = {"start": 0.0, "middle": -W / 2.0, "end": -W}[anchor]
        for (t, k), w in zip(pieces, widths):
            hh = h * (0.62 if k else 1.0)
            rz = {1: 0.48 * h, -1: -0.24 * h, 0: 0.0}[k]
            px, py = x + off * ca - sa * rz, y + off * sa + ca * rz
            self.items.append(("T", layer, (float(px), float(py), t, float(hh), "start",
                                            float(rot), bool(bold))))
            off += w

    def mtext(self, x, y, lines, h=2.5, gap=1.6, layer="TEXT", bold=False, anchor="start"):
        """Lines of text downwards from (x, y = top of first line).  Returns the
        y of the bottom of the block."""
        yy = y
        for ln in lines:
            yy -= h
            self.text(x, yy, ln, h, anchor, layer=layer, bold=bold)
            yy -= gap
        return yy

    # ---- composite ---------------------------------------------------------
    def arrow(self, x, y, ang_deg, length=2.5, width=0.9, layer="DIM"):
        """Closed filled arrowhead with its tip at (x, y) pointing along ang."""
        a = math.radians(ang_deg)
        bx, by = x - length * math.cos(a), y - length * math.sin(a)
        nx, ny = -math.sin(a) * width / 2.0, math.cos(a) * width / 2.0
        self.poly([(x, y), (bx + nx, by + ny), (bx - nx, by - ny)], True, layer, fill=True)

    def dot(self, x, y, r=0.6, layer="THIN"):
        self.circle(x, y, r, layer, fill=True)

    def dim(self, x1, y1, x2, y2, off, text=None, h=2.5, layer="DIM", ext=True,
            arrows="both", tpos="auto"):
        """Aligned dimension between two points, dimension line offset by off
        (mm, positive to the left of p1→p2).  Text above the line, readable
        from the bottom or the right (ISO 129-1).  When the dimension is too
        short for arrows and text inside, the arrows go outside and the text
        is set beyond the start (tpos="start") or the end ("end"/"auto")."""
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L < 1e-6:
            return
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        a1 = (x1 + nx * off, y1 + ny * off)
        a2 = (x2 + nx * off, y2 + ny * off)
        if ext and abs(off) > 0.5:
            sgn = 1 if off > 0 else -1
            g, over = 1.0, 2.0
            self.line(x1 + nx * g * sgn, y1 + ny * g * sgn,
                      a1[0] + nx * over * sgn, a1[1] + ny * over * sgn, layer)
            self.line(x2 + nx * g * sgn, y2 + ny * g * sgn,
                      a2[0] + nx * over * sgn, a2[1] + ny * over * sgn, layer)
        ang = math.degrees(math.atan2(uy, ux))
        txt = text if text is not None else fmt_len(L)
        tw = text_width(txt, h)
        inside = L > 7.0
        fits = L > tw + 6.0
        if tpos == "chain" and not inside:
            # a short dimension in a chain: oblique strokes instead of arrowheads
            # and the value over the middle of the line (ISO 129-1, 5.3)
            self.line(a1[0], a1[1], a2[0], a2[1], layer)
            for q in (a1, a2):
                ca, sa = math.cos(math.radians(ang + 45)), math.sin(math.radians(ang + 45))
                self.line(q[0] - 1.25 * ca, q[1] - 1.25 * sa, q[0] + 1.25 * ca, q[1] + 1.25 * sa, "OUTLINE")
            inside, fits = None, L > tw + 1.0
            if fits:
                arrows = "none"
        if inside:
            self.line(a1[0], a1[1], a2[0], a2[1], layer)
            if arrows in ("both", "start"):
                self.arrow(a1[0], a1[1], ang + 180, layer=layer)
            if arrows in ("both", "end"):
                self.arrow(a2[0], a2[1], ang, layer=layer)
        elif inside is False:   # arrows outside, pointing in
            self.line(a1[0] - ux * 5, a1[1] - uy * 5, a2[0] + ux * 5, a2[1] + uy * 5, layer)
            self.arrow(a1[0], a1[1], ang, layer=layer)
            self.arrow(a2[0], a2[1], ang + 180, layer=layer)
        ta = ang
        if ta > 90.0001 or ta <= -89.999:
            ta = ta - 180 if ta > 0 else ta + 180
        tn = math.radians(ta + 90)
        mx, my = (a1[0] + a2[0]) / 2.0, (a1[1] + a2[1]) / 2.0
        if not fits:
            d = L / 2 + 5.5 + tw / 2
            if tpos == "start":
                mx -= ux * d; my -= uy * d
                self.line(a1[0], a1[1], a1[0] - ux * (5.5 + tw), a1[1] - uy * (5.5 + tw), layer)
            else:
                mx += ux * d; my += uy * d
                self.line(a2[0], a2[1], a2[0] + ux * (5.5 + tw), a2[1] + uy * (5.5 + tw), layer)
        self.text(mx + math.cos(tn) * 0.9, my + math.sin(tn) * 0.9, txt, h, "middle",
                  rot=ta, layer=layer)

    def leader(self, pts, text, h=2.5, layer="DIM", head="arrow", side=None, bold=False):
        """Leader from pts[0] (the feature) through pts[1:] to a horizontal
        landing; text (str or list of lines) sits on the landing."""
        if isinstance(text, str):
            text = [text]
        self.poly(pts, False, layer)
        x0, y0 = pts[0]
        x1, y1 = pts[1]
        if head == "arrow":
            self.arrow(x0, y0, math.degrees(math.atan2(y0 - y1, x0 - x1)), layer=layer)
        elif head == "dot":
            self.dot(x0, y0, 0.5, layer)
        xe, ye = pts[-1]
        xp, yp = pts[-2]
        right = (xe >= xp) if side is None else (side == "right")
        tw = max(text_width(t, h, bold) for t in text)
        land = 2.0
        xl = xe + (land if right else -land)
        self.line(xe, ye, xl, ye, layer)
        anchor = "start" if right else "end"
        xt = xl + (1.0 if right else -1.0)
        n = len(text)
        # centre the block vertically on the landing
        top = ye + (n * h + (n - 1) * 1.4) / 2.0
        yy = top
        for t in text:
            yy -= h
            self.text(xt, yy, t, h, anchor, layer="TEXT", bold=bold)
            yy -= 1.4
        return tw

    def balloon(self, x, y, label, r=2.6, h=2.5, layer="TEXT"):
        self.circle(x, y, r, layer)
        self.text(x, y, str(label), h, "middle", "middle", layer=layer)

    def hatch(self, polys, angle=45.0, spacing=2.0, layer="HATCH", phase=0.0):
        """Parallel-line hatching of the region bounded by polys (a list of
        closed point lists, even-odd rule — holes allowed)."""
        for seg in hatch_lines(polys, angle, spacing, phase):
            self.line(*seg, layer=layer)

    def pattern(self, polys, kind, scale=1.0, layer="HATCH", seed=1):
        """Material symbols for sections (ISO 128-50 style):
        soil, gravel, sand, concrete, backfill, steel, insulation."""
        if kind == "steel":
            self.hatch(polys, 45, 1.2 * scale, layer)
            return
        if kind == "soil":
            # earth: groups of three 45° lines
            for k, seg in enumerate(hatch_lines(polys, 45, 1.1 * scale)):
                if k % 6 < 3:
                    self.line(*seg, layer=layer)
            return
        if kind == "copper":
            self.hatch(polys, 45, 0.8 * scale, layer)
            self.hatch(polys, -45, 0.8 * scale, layer)
            return
        if kind == "insulation":
            self.hatch(polys, -45, 1.0 * scale, layer)
            return
        rnd = random.Random(seed)
        xs = [p[0] for poly in polys for p in poly]
        ys = [p[1] for poly in polys for p in poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        area = (x1 - x0) * (y1 - y0)
        if kind == "concrete":
            n = int(area / (9.0 * scale * scale)) + 1
            for _ in range(min(n, 3000)):
                x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
                if not point_in(polys, x, y):
                    continue
                if rnd.random() < 0.55:
                    self.dot(x, y, 0.18 * scale, layer)
                else:
                    s = rnd.uniform(0.6, 1.2) * scale
                    a = rnd.uniform(0, 2 * math.pi)
                    tri = [(x + s * math.cos(a + k * 2.1), y + s * math.sin(a + k * 2.1)) for k in range(3)]
                    if all(point_in(polys, *p) for p in tri):
                        self.poly(tri, True, layer)
        elif kind in ("gravel", "crushed"):
            n = int(area / (6.0 * scale * scale)) + 1
            for _ in range(min(n, 3000)):
                x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
                r = rnd.uniform(0.35, 0.9) * scale
                if all(point_in(polys, x + dx, y + dy) for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r))):
                    if kind == "crushed":
                        k = rnd.randint(4, 6)
                        a0 = rnd.uniform(0, 6.28)
                        self.poly([(x + r * math.cos(a0 + 6.283 * j / k), y + r * math.sin(a0 + 6.283 * j / k))
                                   for j in range(k)], True, layer)
                    else:
                        self.circle(x, y, r, layer)
        elif kind in ("sand", "backfill", "bentonite"):
            dens = {"sand": 1.2, "backfill": 2.2, "bentonite": 0.8}[kind]
            n = int(area / (dens * scale * scale)) + 1
            for _ in range(min(n, 6000)):
                x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
                if point_in(polys, x, y):
                    self.dot(x, y, 0.13 * scale, layer)
            if kind == "bentonite":
                self.hatch(polys, -45, 2.6 * scale, layer)

    def ground(self, x0, x1, y, depth=2.0, step=2.5, layer="THIN"):
        """Natural ground symbol: a line with short 45° strokes below it."""
        self.line(x0, y, x1, y, "OUTLINE")
        x = x0 + 0.8
        while x < x1 - 0.2:
            self.line(x, y, max(x0, x - depth), y - depth, layer)
            x += step

    def break_line(self, x1, y1, x2, y2, layer="THIN"):
        """ISO 128 freehand-style straight break line with a zig-zag."""
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L < 1e-6:
            return
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        m = L / 2
        z = 1.8
        pts = [(x1 - ux * 2, y1 - uy * 2), (x1 + ux * (m - z), y1 + uy * (m - z)),
               (x1 + ux * (m - z / 3) + nx * 2.5, y1 + uy * (m - z / 3) + ny * 2.5),
               (x1 + ux * (m + z / 3) - nx * 2.5, y1 + uy * (m + z / 3) - ny * 2.5),
               (x1 + ux * (m + z), y1 + uy * (m + z)), (x2 + ux * 2, y2 + uy * 2)]
        self.poly(pts, False, layer)

    def title_label(self, x, y, title, sub=None, h=3.5, maxw=None):
        """Detail title, underlined, centred at x with its baseline at y."""
        while maxw and h > 2.5 and text_width(title, h, True) > maxw:
            h -= 0.1
        self.text(x, y, title, h, "middle", layer="TEXT", bold=True)
        w = text_width(title, h, True)
        self.line(x - w / 2, y - 1.0, x + w / 2, y - 1.0, "OUTLINE")
        if sub:
            self.text(x, y - 1.0 - 1.6 - 2.5, sub, 2.5, "middle")

    # ---- views ---------------------------------------------------------------
    def view(self, ox, oy, scale, mx0=0.0, my0=0.0, unit=1.0):
        return View(self, ox, oy, scale, mx0, my0, unit)


class View:
    """Model space → sheet: sheet = origin + (model − model_origin)·unit/scale.
    unit converts model units to mm (1000 for metres)."""

    def __init__(self, sheet, ox, oy, scale, mx0, my0, unit):
        self.s, self.ox, self.oy = sheet, ox, oy
        self.scale, self.mx0, self.my0, self.unit = scale, mx0, my0, unit
        self.k = unit / scale

    def P(self, x, y):
        return (self.ox + (x - self.mx0) * self.k, self.oy + (y - self.my0) * self.k)

    def L(self, v):
        return v * self.k

    def line(self, x1, y1, x2, y2, layer="OUTLINE"):
        a, b = self.P(x1, y1), self.P(x2, y2)
        self.s.line(a[0], a[1], b[0], b[1], layer)

    def poly(self, pts, closed=False, layer="OUTLINE", fill=False):
        self.s.poly([self.P(x, y) for x, y in pts], closed, layer, fill)

    def rect(self, x, y, w, h, layer="OUTLINE", fill=False):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True, layer, fill)

    def circle(self, cx, cy, r, layer="OUTLINE", fill=False):
        p = self.P(cx, cy)
        self.s.circle(p[0], p[1], r * self.k, layer, fill)

    def arc(self, cx, cy, r, a0, a1, layer="OUTLINE"):
        p = self.P(cx, cy)
        self.s.arc(p[0], p[1], r * self.k, a0, a1, layer)

    def text(self, x, y, s, h=2.5, anchor="start", valign="baseline", rot=0, layer="TEXT", bold=False):
        p = self.P(x, y)
        self.s.text(p[0], p[1], s, h, anchor, valign, rot, layer, bold)

    def dim(self, x1, y1, x2, y2, off, text=None, h=2.5, unit_label="mm", tpos="auto"):
        a, b = self.P(x1, y1), self.P(x2, y2)
        if text is None:
            L = math.hypot(x2 - x1, y2 - y1) * self.unit
            text = fmt_len(L, unit_label)
        self.s.dim(a[0], a[1], b[0], b[1], off, text, h, tpos=tpos)

    def hatch(self, polys, angle=45, spacing=2.0, layer="HATCH"):
        self.s.hatch([[self.P(x, y) for x, y in poly] for poly in polys], angle, spacing, layer)

    def pattern(self, polys, kind, scale=1.0, layer="HATCH", seed=1):
        self.s.pattern([[self.P(x, y) for x, y in poly] for poly in polys], kind, scale, layer, seed)

    def ground(self, x0, x1, y, **kw):
        a, b = self.P(x0, y), self.P(x1, y)
        self.s.ground(a[0], b[0], a[1], **kw)


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def point_in(polys, x, y) -> bool:
    """Even-odd point-in-polygon over several rings."""
    inside = False
    for poly in polys:
        n = len(poly)
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if (yi > y) != (yj > y):
                xc = xi + (y - yi) * (xj - xi) / (yj - yi)
                if x < xc:
                    inside = not inside
            j = i
    return inside


def hatch_lines(polys, angle=45.0, spacing=2.0, phase=0.0):
    """Clip a family of parallel lines to a polygon set (even-odd)."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    # rotate so that the hatch lines are horizontal
    rot = [[(x * ca + y * sa, -x * sa + y * ca) for x, y in poly] for poly in polys]
    ys = [p[1] for poly in rot for p in poly]
    if not ys:
        return []
    y = math.floor((min(ys) - phase) / spacing) * spacing + phase + spacing * 0.5
    out = []
    while y < max(ys):
        xs = []
        for poly in rot:
            n = len(poly)
            for i in range(n):
                (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
                if (y1 > y) != (y2 > y):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            u0, u1 = xs[k], xs[k + 1]
            # rotate back
            out.append((u0 * ca - y * sa, u0 * sa + y * ca, u1 * ca - y * sa, u1 * sa + y * ca))
        y += spacing
    return out


def circle_pts(cx, cy, r, n=48, a0=0.0, a1=360.0):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


# ---------------------------------------------------------------------------
# SVG writer
# ---------------------------------------------------------------------------

def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def to_svg(sh: Sheet, background: bool = True) -> str:
    H = sh.H
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{sh.W}mm" height="{sh.H}mm" '
           f'viewBox="0 0 {sh.W} {sh.H}" font-family="Helvetica, Arial, \'Liberation Sans\', sans-serif">']
    if background:
        out.append(f'<rect x="0" y="0" width="{sh.W}" height="{sh.H}" fill="#fff"/>')
    out.append('<g stroke="#000" fill="none" stroke-linecap="round" stroke-linejoin="round">')

    def st(layer):
        w, _, lt = LAYERS.get(layer, LAYERS["0"])
        s = f'stroke-width="{w}"'
        d = DASH.get(lt)
        if d:
            s += ' stroke-dasharray="' + ",".join(f"{v:g}" for v in d) + '"'
        return s

    for kind, layer, g in sh.items:
        if kind == "L":
            x1, y1, x2, y2 = g
            out.append(f'<line x1="{x1:.3f}" y1="{H - y1:.3f}" x2="{x2:.3f}" y2="{H - y2:.3f}" {st(layer)}/>')
        elif kind == "P":
            pts, closed, fill = g
            d = " ".join(f"{x:.3f},{H - y:.3f}" for x, y in pts)
            tag = "polygon" if closed else "polyline"
            f = ' fill="#000"' if fill else ""
            out.append(f'<{tag} points="{d}" {st(layer)}{f}/>')
        elif kind == "C":
            cx, cy, r, fill = g
            f = ' fill="#000"' if fill else ""
            sw = 'stroke-width="0.1"' if fill else st(layer)
            out.append(f'<circle cx="{cx:.3f}" cy="{H - cy:.3f}" r="{r:.3f}" {sw}{f}/>')
        elif kind == "A":
            cx, cy, r, a0, a1 = g
            sweep = (a1 - a0) % 360 or 360
            x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
            x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
            large = 1 if sweep > 180 else 0
            out.append(f'<path d="M{x0:.3f},{H - y0:.3f} A{r:.3f},{r:.3f} 0 {large} 0 '
                       f'{x1:.3f},{H - y1:.3f}" {st(layer)}/>')
        elif kind == "T":
            x, y, s, h, anchor, rot, bold = g
            fs = h / CAP
            tr = f' transform="rotate({-rot:.2f} {x:.3f} {H - y:.3f})"' if rot else ""
            fw = ' font-weight="bold"' if bold else ""
            out.append(f'<text x="{x:.3f}" y="{H - y:.3f}" font-size="{fs:.3f}" text-anchor="{anchor}" '
                       f'fill="#000" stroke="none"{fw}{tr}>{_esc(s)}</text>')
    out.append("</g></svg>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# PDF writer (vector, base-14 fonts)
# ---------------------------------------------------------------------------

_PT = 72.0 / 25.4      # points per millimetre


def _pdf_str(b: bytes) -> bytes:
    return b"(" + b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _runs(s: str):
    """Split a string into (font, bytes) runs: F1/F2 Helvetica, F3 Symbol."""
    runs = []
    for ch in s:
        o = ord(ch)
        if 32 <= o <= 126:
            f, b = "T", bytes([o])
        elif ch in _WINANSI:
            f, b = "T", bytes([_WINANSI[ch]])
        elif ch in _SYMBOL:
            f, b = "S", bytes([_SYMBOL[ch]])
        else:
            f, b = "T", b"?"
        if runs and runs[-1][0] == f:
            runs[-1][1] += b
        else:
            runs.append([f, bytearray(b)])
    return runs


def _pdf_page(sh: Sheet) -> bytes:
    k = _PT
    c = [b"1 J 1 j 0 0 0 RG 0 0 0 rg"]
    cur = {"w": None, "d": None}

    def style(layer):
        w, _, lt = LAYERS.get(layer, LAYERS["0"])
        if cur["w"] != w:
            c.append(f"{w * k:.3f} w".encode())
            cur["w"] = w
        d = DASH.get(lt)
        if cur["d"] != d:
            if d:
                c.append(("[" + " ".join(f"{v * k:.2f}" for v in d) + "] 0 d").encode())
            else:
                c.append(b"[] 0 d")
            cur["d"] = d

    def P(x, y):
        return f"{x * k:.3f} {y * k:.3f}"

    for kind, layer, g in sh.items:
        if kind == "L":
            style(layer)
            x1, y1, x2, y2 = g
            c.append(f"{P(x1, y1)} m {P(x2, y2)} l S".encode())
        elif kind == "P":
            pts, closed, fill = g
            style(layer)
            s = f"{P(*pts[0])} m " + " ".join(f"{P(x, y)} l" for x, y in pts[1:])
            if fill:
                s += " h B"              # fill and stroke (keeps thin shapes visible)
            else:
                s += " h S" if closed else " S"
            c.append(s.encode())
        elif kind == "C":
            cx, cy, r, fill = g
            style(layer)
            m = 0.5522847498 * r
            s = (f"{P(cx + r, cy)} m {P(cx + r, cy + m)} {P(cx + m, cy + r)} {P(cx, cy + r)} c "
                 f"{P(cx - m, cy + r)} {P(cx - r, cy + m)} {P(cx - r, cy)} c "
                 f"{P(cx - r, cy - m)} {P(cx - m, cy - r)} {P(cx, cy - r)} c "
                 f"{P(cx + m, cy - r)} {P(cx + r, cy - m)} {P(cx + r, cy)} c ")
            s += "f" if fill else "S"
            c.append(s.encode())
        elif kind == "A":
            cx, cy, r, a0, a1 = g
            style(layer)
            sweep = (a1 - a0) % 360 or 360
            n = max(2, int(math.ceil(sweep / 15.0)))
            pts = circle_pts(cx, cy, r, n, a0, a0 + sweep)
            c.append((f"{P(*pts[0])} m " + " ".join(f"{P(x, y)} l" for x, y in pts[1:]) + " S").encode())
        elif kind == "T":
            x, y, s, h, anchor, rot, bold = g
            fs = h / CAP * k
            w = text_width(s, h, bold)
            off = {"start": 0.0, "middle": -w / 2.0, "end": -w}[anchor]
            a = math.radians(rot)
            ca, sa = math.cos(a), math.sin(a)
            x0 = x + off * ca
            y0 = y + off * sa
            parts = [b"BT", f"{ca:.5f} {sa:.5f} {-sa:.5f} {ca:.5f} {x0 * k:.3f} {y0 * k:.3f} Tm".encode()]
            for f, b in _runs(s):
                font = b"/F3" if f == "S" else (b"/F2" if bold else b"/F1")
                parts.append(font + f" {fs:.3f} Tf ".encode() + _pdf_str(bytes(b)) + b" Tj")
            parts.append(b"ET")
            c.append(b" ".join(parts))
    return b"\n".join(c)


def to_pdf(sheets, title: str = "Earthing drawings", author: str = "") -> bytes:
    objs = []

    def add(b):
        objs.append(b)
        return len(objs)

    cat = add(b"")          # placeholder 1
    pages = add(b"")        # placeholder 2
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    f3 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Symbol >>")
    kids = []
    for sh in sheets:
        raw = _pdf_page(sh)
        data = zlib.compress(raw, 9)
        cs = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream")
        pg = add((f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {sh.W * _PT:.2f} {sh.H * _PT:.2f}] "
                  f"/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R /F3 {f3} 0 R >> >> "
                  f"/Contents {cs} 0 R >>").encode())
        kids.append(pg)
    objs[cat - 1] = f"<< /Type /Catalog /Pages {pages} 0 R >>".encode()
    objs[pages - 1] = (f"<< /Type /Pages /Count {len(kids)} /Kids [" +
                       " ".join(f"{k} 0 R" for k in kids) + "] >>").encode()

    def pdftext(s):
        return "(" + "".join(ch if 32 <= ord(ch) < 127 and ch not in "()\\" else "?" for ch in s) + ")"
    info = add(f"<< /Title {pdftext(title)} /Author {pdftext(author)} "
               f"/Producer (Earthing System drawings module) >>".encode())
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = []
    for i, b in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + b + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root {cat} 0 R /Info {info} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


# ---------------------------------------------------------------------------
# DXF writer (AutoCAD R12 / AC1009 ASCII)
# ---------------------------------------------------------------------------

_DXF_LTYPES = {
    "CONTINUOUS": ("Solid line", []),
    "DASHED": ("Dashed __ __ __", [6.0, -1.5]),
    "CENTER": ("Center ____ _ ____", [12.0, -1.5, 0.5, -1.5]),
    "PHANTOM": ("Phantom ____ _ _ ____", [12.0, -1.5, 0.5, -1.5, 0.5, -1.5]),
    "FENCE": ("Fence __ . __ .", [4.0, -1.0, 0.5, -1.0]),
}

_DXF_SAFE = {"°": "%%d", "±": "%%p", "Ø": "%%c", "ø": "%%c"}


def _dxf_text(s):
    """ASCII DXF text: AutoCAD control codes for ° ± Ø, and \\U+XXXX for
    every other character (Ω, ρ, ², µ …), which AutoCAD, BricsCAD,
    LibreCAD and ezdxf all decode."""
    out = []
    for ch in s:
        if 32 <= ord(ch) <= 126:
            out.append(ch)
        elif ch in _DXF_SAFE:
            out.append(_DXF_SAFE[ch])
        else:
            out.append("\\U+%04X" % ord(ch))
    return "".join(out)


def to_dxf(sh: Sheet) -> str:
    L = []

    def g(code, val):
        L.append(f"{code:>3}")
        if isinstance(val, float):
            L.append(f"{val:.4f}")
        else:
            L.append(str(val))

    # HEADER
    g(0, "SECTION"); g(2, "HEADER")
    g(9, "$ACADVER"); g(1, "AC1009")
    g(9, "$INSBASE"); g(10, 0.0); g(20, 0.0); g(30, 0.0)
    g(9, "$EXTMIN"); g(10, 0.0); g(20, 0.0); g(30, 0.0)
    g(9, "$EXTMAX"); g(10, float(sh.W)); g(20, float(sh.H)); g(30, 0.0)
    g(9, "$LIMMIN"); g(10, 0.0); g(20, 0.0)
    g(9, "$LIMMAX"); g(10, float(sh.W)); g(20, float(sh.H))
    g(9, "$LTSCALE"); g(40, 1.0)
    g(9, "$MEASUREMENT"); g(70, 1)
    g(9, "$TEXTSTYLE"); g(7, "ISO")
    g(9, "$DIMSCALE"); g(40, 1.0)
    g(0, "ENDSEC")
    # TABLES
    g(0, "SECTION"); g(2, "TABLES")
    g(0, "TABLE"); g(2, "LTYPE"); g(70, len(_DXF_LTYPES))
    for name, (desc, pat) in _DXF_LTYPES.items():
        g(0, "LTYPE"); g(2, name); g(70, 0); g(3, desc); g(72, 65); g(73, len(pat))
        g(40, float(sum(abs(v) for v in pat)))
        for v in pat:
            g(49, float(v))
    g(0, "ENDTAB")
    g(0, "TABLE"); g(2, "LAYER"); g(70, len(LAYERS))
    for name, (w, col, lt) in LAYERS.items():
        g(0, "LAYER"); g(2, name); g(70, 0); g(62, col); g(6, lt)
    g(0, "ENDTAB")
    g(0, "TABLE"); g(2, "STYLE"); g(70, 1)
    g(0, "STYLE"); g(2, "ISO"); g(70, 0); g(40, 0.0); g(41, 1.0); g(50, 0.0); g(71, 0)
    g(42, 2.5); g(3, "arial.ttf"); g(4, "")
    g(0, "ENDTAB")
    g(0, "ENDSEC")
    # BLOCKS (empty, required by some readers)
    g(0, "SECTION"); g(2, "BLOCKS"); g(0, "ENDSEC")
    # ENTITIES
    g(0, "SECTION"); g(2, "ENTITIES")
    for kind, layer, gg in sh.items:
        lay = layer if layer in LAYERS else "0"
        if kind == "L":
            x1, y1, x2, y2 = gg
            g(0, "LINE"); g(8, lay); g(10, x1); g(20, y1); g(30, 0.0); g(11, x2); g(21, y2); g(31, 0.0)
        elif kind == "P":
            pts, closed, fill = gg
            if fill and len(pts) in (3, 4) and closed:
                q = pts if len(pts) == 4 else pts + [pts[-1]]
                # SOLID vertex order is 1-2-4-3
                order = [q[0], q[1], q[3], q[2]]
                g(0, "SOLID"); g(8, lay)
                for i, (x, y) in enumerate(order):
                    g(10 + i, x); g(20 + i, y); g(30 + i, 0.0)
                continue
            g(0, "POLYLINE"); g(8, lay); g(66, 1); g(10, 0.0); g(20, 0.0); g(30, 0.0)
            g(70, 1 if closed else 0)
            for x, y in pts:
                g(0, "VERTEX"); g(8, lay); g(10, x); g(20, y); g(30, 0.0)
            g(0, "SEQEND"); g(8, lay)
        elif kind == "C":
            cx, cy, r, fill = gg
            if fill:
                # filled disc: closed polyline of two half-circle arcs (bulge 1)
                # with width equal to the radius — the classic DONUT.
                w = r
                rr = r / 2.0
                g(0, "POLYLINE"); g(8, lay); g(66, 1); g(10, 0.0); g(20, 0.0); g(30, 0.0)
                g(70, 1); g(40, w); g(41, w)
                for (x, y) in ((cx - rr, cy), (cx + rr, cy)):
                    g(0, "VERTEX"); g(8, lay); g(10, x); g(20, y); g(30, 0.0); g(42, 1.0)
                g(0, "SEQEND"); g(8, lay)
            else:
                g(0, "CIRCLE"); g(8, lay); g(10, cx); g(20, cy); g(30, 0.0); g(40, r)
        elif kind == "A":
            cx, cy, r, a0, a1 = gg
            g(0, "ARC"); g(8, lay); g(10, cx); g(20, cy); g(30, 0.0); g(40, r)
            g(50, a0 % 360.0); g(51, a1 % 360.0)
        elif kind == "T":
            x, y, s, h, anchor, rot, bold = gg
            g(0, "TEXT"); g(8, lay); g(10, x); g(20, y); g(30, 0.0); g(40, h)
            g(1, _dxf_text(s)); g(50, rot % 360.0); g(7, "ISO")
            hj = {"start": 0, "middle": 1, "end": 2}[anchor]
            if hj:
                g(72, hj); g(11, x); g(21, y); g(31, 0.0)
    g(0, "ENDSEC")
    g(0, "EOF")
    return "\n".join(L) + "\n"
