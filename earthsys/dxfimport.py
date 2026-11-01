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
Electrode geometry from a DXF site drawing (1.8.4).

Reads an ASCII or binary DXF (any release from R12 on; binary from 1.9.5)
with the standard library only,
so it also runs in the browser build, and turns the plan of the earthing
layout into the electrode table of the numerical page:

* LINE, LWPOLYLINE and POLYLINE (with VERTEX) on a layer marked *conductor*
  become buried conductors, one per straight piece, at the given depth;
* the same entities on a layer marked *fence* become fences, one per
  polyline (closed or open), with their posts placed by the solver;
* POINT, CIRCLE and block INSERT on a layer marked *rod* become driven rods at
  their centre or insertion point; a CIRCLE on a *conductor* layer becomes a
  ring electrode.

Arcs and polyline bulges are replaced by chords of at most 15°.  The drawing
unit comes from $INSUNITS (millimetres, centimetres, metres, inches, feet)
unless a scale is given, and the layout can be moved so that its lower-left
corner is the origin.
"""

from __future__ import annotations

import math

UNITS = {0: None, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 14: 0.1}
UNIT_NAME = {1: "inches", 2: "feet", 4: "millimetres", 5: "centimetres", 6: "metres",
             14: "decimetres"}
KINDS = ("conductor", "rod", "fence", "ignore")


# Binary DXF (1.9.5).  The file starts with this 22-byte sentinel; then come
# group codes (one byte up to R12, with 255 introducing a two-byte code; two
# bytes, little-endian, from R13 on) each followed by its value in the binary
# form that the DXF reference assigns to the group-code range.
BINARY_SENTINEL = b"AutoCAD Binary DXF\r\n\x1a\x00"


def _ranges(*rr):
    out = set()
    for a, b in rr:
        out.update(range(a, b + 1))
    return frozenset(out)


_BIN_DOUBLE = _ranges((10, 59), (110, 149), (210, 239), (460, 469), (1010, 1059))
_BIN_INT16 = _ranges((60, 79), (170, 179), (270, 289), (370, 389), (400, 409), (1060, 1070))
_BIN_INT32 = _ranges((90, 99), (420, 429), (440, 459), (1071, 1071))
_BIN_INT64 = _ranges((160, 169))
_BIN_BOOL = _ranges((290, 299))
_BIN_CHUNK = _ranges((310, 319), (1004, 1004))


def _binary_pairs(data: bytes):
    """(code, value) pairs of a binary DXF, the values as the text an ASCII
    DXF would carry (numbers exactly: repr of a float reads back unchanged)."""
    import struct
    if data[:22] != BINARY_SENTINEL:
        raise ValueError("Not a binary DXF file.")
    n = len(data)
    # a binary DXF opens with group code 0 and "SECTION": one zero byte before
    # the text up to R12, two from R13 on
    wide = n > 23 and data[22] == 0 and data[23] == 0
    raw, i = [], 22
    try:
        while i < n:
            if wide:
                code = data[i] | (data[i + 1] << 8)
                i += 2
            else:
                code = data[i]
                i += 1
                if code == 255:
                    code = data[i] | (data[i + 1] << 8)
                    i += 2
            if code in _BIN_CHUNK:
                ln = data[i]
                raw.append((code, None))
                i += 1 + ln
            elif code in _BIN_DOUBLE:
                raw.append((code, repr(struct.unpack_from("<d", data, i)[0])))
                i += 8
            elif code in _BIN_INT16:
                raw.append((code, str(struct.unpack_from("<h", data, i)[0])))
                i += 2
            elif code in _BIN_INT32:
                raw.append((code, str(struct.unpack_from("<i", data, i)[0])))
                i += 4
            elif code in _BIN_INT64:
                raw.append((code, str(struct.unpack_from("<q", data, i)[0])))
                i += 8
            elif code in _BIN_BOOL:
                raw.append((code, str(data[i])))
                i += 1
            else:                                   # zero-terminated string
                j = data.index(b"\x00", i)
                raw.append((code, data[i:j]))
                i = j + 1
    except (IndexError, ValueError, struct.error):
        raise ValueError("The binary DXF file is cut short or damaged.") from None
    # strings: UTF-8 from AutoCAD 2007 (AC1021) on, before that the code page
    # named in $DWGCODEPAGE (ANSI_1252 when it is missing)
    ver, cp = b"", b"ANSI_1252"
    for k in range(len(raw) - 1):
        if raw[k][0] == 9 and raw[k][1] == b"$ACADVER":
            ver = raw[k + 1][1] if isinstance(raw[k + 1][1], bytes) else b""
        elif raw[k][0] == 9 and raw[k][1] == b"$DWGCODEPAGE":
            cp = raw[k + 1][1] if isinstance(raw[k + 1][1], bytes) else cp
    if ver >= b"AC1021":
        enc = "utf-8"
    else:
        enc = "cp" + cp.decode("ascii", "replace").upper().replace("ANSI_", "")
        try:
            "".encode(enc)
        except LookupError:
            enc = "cp1252"
    out = []
    for code, v in raw:
        if v is None:
            continue
        if isinstance(v, bytes):
            v = v.decode(enc, errors="replace")
        out.append((code, v.strip()))
    return out


def _source_pairs(src):
    """Group-code pairs of a DXF given as text (ASCII DXF) or bytes (ASCII
    or binary DXF)."""
    if isinstance(src, (bytes, bytearray)):
        src = bytes(src)
        if src[:22] == BINARY_SENTINEL:
            return _binary_pairs(src)
        if src[:4] == b"AC10" or src[:4] == b"AC15":
            raise ValueError("This is a DWG drawing, which cannot be read. Save it as DXF "
                             "(ASCII or binary) from the CAD program.")
        try:
            src = src.decode("utf-8")
        except UnicodeDecodeError:
            src = src.decode("cp1252", errors="replace")
    if not src or "SECTION" not in src:
        raise ValueError("This is not a DXF file (no SECTION found). Save the drawing as "
                         "DXF (ASCII or binary), not DWG.")
    return list(_pairs(src))


def _unescape(name: str) -> str:
    """Names in drawings before AutoCAD 2007 carry characters outside the code
    page as \\U+XXXX (1.9.5: shown as the characters)."""
    if "\\U+" not in name:
        return name
    import re
    return re.sub(r"\\U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), name)


def _pairs(text: str):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) % 2:
        lines.append("")
    for i in range(0, len(lines) - 1, 2):
        code = lines[i].strip()
        try:
            yield int(code), lines[i + 1].strip()
        except ValueError:
            continue


def _bulge_points(p, q, bulge, max_deg=15.0):
    """Points along an arc from p to q with DXF bulge = tan(θ/4), excluding p."""
    if abs(bulge) < 1e-9:
        return [q]
    theta = 4.0 * math.atan(bulge)
    dx, dy = q[0] - p[0], q[1] - p[1]
    c = math.hypot(dx, dy)
    if c < 1e-12:
        return [q]
    r = c / (2.0 * math.sin(abs(theta) / 2.0))
    mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
    hd = math.sqrt(max(r * r - (c / 2.0) ** 2, 0.0))
    nx, ny = -dy / c, dx / c
    s = 1.0 if (bulge > 0) == (abs(theta) < math.pi) else -1.0
    cx, cy = mx + s * nx * hd, my + s * ny * hd
    a0 = math.atan2(p[1] - cy, p[0] - cx)
    n = max(1, int(math.ceil(abs(math.degrees(theta)) / max_deg)))
    return [(cx + r * math.cos(a0 + theta * k / n), cy + r * math.sin(a0 + theta * k / n))
            for k in range(1, n + 1)]


def parse(text) -> dict:
    """Entities of the ENTITIES section, by layer, in drawing units.  `text` is
    an ASCII DXF as text, or a DXF file's bytes (ASCII or binary, 1.9.5)."""
    pairs = _source_pairs(text)
    ents, header = [], {}
    section, var, cur = None, None, None
    poly = None                                   # open POLYLINE collecting VERTEXes
    i = 0
    while i < len(pairs):
        code, val = pairs[i]
        if code == 0:
            if cur is not None:
                if cur["type"] == "VERTEX" and poly is not None:
                    poly["pts"].append((cur.get(10, 0.0), cur.get(20, 0.0), cur.get(42, 0.0)))
                elif cur["type"] == "POLYLINE":
                    poly = cur
                    poly["pts"] = []
                elif cur["type"] != "VERTEX":
                    ents.append(cur)
                cur = None
            if val == "SEQEND" and poly is not None:
                ents.append(poly)
                poly = None
                i += 1
                continue
            if val == "SECTION":
                section = None
                if i + 1 < len(pairs) and pairs[i + 1][0] == 2:
                    section = pairs[i + 1][1]
                    i += 2
                    continue
            if val == "ENDSEC":
                section = None
            elif section == "ENTITIES" and val in ("LINE", "LWPOLYLINE", "POLYLINE", "VERTEX",
                                                    "CIRCLE", "ARC", "POINT", "INSERT"):
                cur = dict(type=val, layer="0", lw=[])
            i += 1
            continue
        if section == "HEADER":
            if code == 9:
                var = val
            elif var == "$INSUNITS" and code == 70:
                header["INSUNITS"] = int(float(val))
        elif cur is not None:
            if code == 8:
                cur["layer"] = _unescape(val)
            elif cur["type"] == "LWPOLYLINE" and code in (10, 20, 42):
                if code == 10:
                    cur["lw"].append([float(val), 0.0, 0.0])
                elif code == 20 and cur["lw"]:
                    cur["lw"][-1][1] = float(val)
                elif code == 42 and cur["lw"]:
                    cur["lw"][-1][2] = float(val)
            elif code in (10, 20, 30, 11, 21, 31, 40, 41, 42, 50, 51, 70):
                try:
                    cur[code] = float(val)
                except ValueError:
                    pass
            elif code == 2:
                cur["block"] = val
        i += 1
    if cur is not None and cur["type"] not in ("VERTEX",):
        ents.append(cur)
    return dict(entities=ents, insunits=header.get("INSUNITS"))


def _geometry(e):
    """('path', [pts], closed) | ('point', (x, y), radius) | None, drawing units."""
    t = e["type"]
    if t == "LINE":
        return ("path", [(e.get(10, 0.0), e.get(20, 0.0)), (e.get(11, 0.0), e.get(21, 0.0))], False)
    if t in ("LWPOLYLINE", "POLYLINE"):
        raw = e["lw"] if t == "LWPOLYLINE" else [list(q) for q in e.get("pts", [])]
        if len(raw) < 2:
            return None
        closed = bool(int(e.get(70, 0)) & 1)
        pts = [(raw[0][0], raw[0][1])]
        seq = raw + ([raw[0]] if closed else [])
        for a, b in zip(seq[:-1], seq[1:]):
            pts += _bulge_points((a[0], a[1]), (b[0], b[1]), a[2])
        return ("path", pts, closed)
    if t == "ARC":
        cx, cy, r = e.get(10, 0.0), e.get(20, 0.0), e.get(40, 0.0)
        a0, a1 = math.radians(e.get(50, 0.0)), math.radians(e.get(51, 360.0))
        if a1 <= a0:
            a1 += 2 * math.pi
        n = max(1, int(math.ceil(math.degrees(a1 - a0) / 15.0)))
        return ("path", [(cx + r * math.cos(a0 + (a1 - a0) * k / n),
                          cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)], False)
    if t == "CIRCLE":
        return ("circle", (e.get(10, 0.0), e.get(20, 0.0)), e.get(40, 0.0))
    if t in ("POINT", "INSERT"):
        return ("point", (e.get(10, 0.0), e.get(20, 0.0)), 0.0)
    return None


def inspect(text) -> dict:
    """What each layer holds, and a suggested use for it."""
    d = parse(text)
    lay = {}
    for e in d["entities"]:
        L = lay.setdefault(e["layer"], dict(lines=0, polylines=0, circles=0, points=0, arcs=0))
        t = e["type"]
        L[{"LINE": "lines", "LWPOLYLINE": "polylines", "POLYLINE": "polylines",
           "CIRCLE": "circles", "ARC": "arcs", "POINT": "points", "INSERT": "points"}[t]] += 1
    for name, L in lay.items():
        nm = name.lower()
        if "fence" in nm or "حصار" in name:
            L["suggest"] = "fence"
        elif "rod" in nm or "electrode" in nm or "میله" in name:
            L["suggest"] = "rod"
        elif any(k in nm for k in ("earth", "ground", "grid", "cond", "mesh", "زمین")):
            L["suggest"] = "conductor"
        elif L["points"] and not (L["lines"] or L["polylines"]):
            L["suggest"] = "rod"
        else:
            L["suggest"] = "ignore"
    u = d["insunits"]
    return dict(layers=lay, insunits=u, unit=UNIT_NAME.get(u, "unitless"),
                scale=UNITS.get(u) if u is not None else None,
                entities=len(d["entities"]))


def to_items(text, mapping: dict, depth: float = 0.6, conductor_radius: float = 0.005,
             rod_length: float = 3.0, rod_radius: float = 0.008, scale: float | None = None,
             to_origin: bool = True, fence: dict | None = None, ring_min_radius: float = 1.0) -> dict:
    """Electrode items for the numerical solver from the layers marked in `mapping`
    ({layer: 'conductor' | 'rod' | 'fence' | 'ignore'})."""
    d = parse(text)
    if scale in (None, "", 0):
        scale = UNITS.get(d["insunits"]) or 1.0
    scale = float(scale)
    for k, v in mapping.items():
        if v not in KINDS:
            raise ValueError(f"Layer {k}: use conductor, rod, fence or ignore.")
    fence = fence or {}
    geo = []
    for e in d["entities"]:
        kind = mapping.get(e["layer"], "ignore")
        if kind == "ignore":
            continue
        g = _geometry(e)
        if g:
            geo.append((kind, g))
    if not geo:
        raise ValueError("No entity on the layers marked for import.")
    xs, ys = [], []
    for _, g in geo:
        pts = g[1] if g[0] == "path" else [g[1]]
        xs += [q[0] for q in pts]
        ys += [q[1] for q in pts]
    ox = min(xs) if to_origin else 0.0
    oy = min(ys) if to_origin else 0.0

    def tr(q):
        return [round((q[0] - ox) * scale, 4), round((q[1] - oy) * scale, 4)]

    items, counts = [], dict(conductors=0, rods=0, fences=0, rings=0)
    for kind, g in geo:
        if kind == "conductor" and g[0] == "path":
            pts = [tr(q) for q in g[1]]
            for a, b in zip(pts[:-1], pts[1:]):
                if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
                    items.append(dict(kind="conductor", p1=[a[0], a[1], depth], p2=[b[0], b[1], depth],
                                      radius=conductor_radius))
                    counts["conductors"] += 1
        elif kind == "conductor" and g[0] == "circle" and g[2] * scale >= ring_min_radius:
            c = tr(g[1])
            items.append(dict(kind="ring", cx=c[0], cy=c[1], r=round(g[2] * scale, 4), depth=depth,
                              radius=conductor_radius, n_sides=32))
            counts["rings"] += 1
        elif kind == "rod" and g[0] in ("point", "circle"):
            c = tr(g[1])
            items.append(dict(kind="rod", x=c[0], y=c[1], top_depth=depth, length=rod_length,
                              radius=rod_radius))
            counts["rods"] += 1
        elif kind == "fence" and g[0] == "path":
            pts = [tr(q) for q in g[1]]
            closed = bool(g[2]) or (len(pts) > 2 and math.hypot(pts[0][0] - pts[-1][0],
                                                               pts[0][1] - pts[-1][1]) < 1e-3)
            if closed and pts[0] == pts[-1]:
                pts = pts[:-1]
            counts["fences"] += 1
            items.append(dict(kind="fence", path=pts, closed=1 if closed else 0,
                              post_spacing=float(fence.get("post_spacing", 3.0)),
                              post_depth=float(fence.get("post_depth", 0.76)),
                              post_radius=float(fence.get("post_radius", 0.025)),
                              wire=0, bonded=1 if fence.get("bonded") else 0,
                              name=f"fence {counts['fences']}"))
    if not items:
        raise ValueError("The marked layers hold nothing that can be imported "
                         "(lines and polylines for conductors and fences, points, "
                         "circles or blocks for rods).")
    return dict(items=items, counts=counts, scale=scale, origin=[ox, oy],
                unit=UNIT_NAME.get(d["insunits"], "unitless"))
