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
Fuse time–current characteristics: the IEC 60269 gates and manufacturers'
curves (1.8.6).

Automatic disconnection (IEC 60364-4-41) needs the current I_a that makes
the protective device operate within the required time.  For a fuse there
are three sources, from the most general to the most exact:

* **IEC 60269 gates.**  Every gG (or gM) fuse-link that complies with
  IEC 60269 has its time–current characteristic inside the gates of
  IEC 60269-1:2006+A2:2014 Table 2 (conventional currents), Table 3
  (I_min(10 s), I_max(5 s), I_min(0.1 s), I_max(0.1 s) for 16–1250 A) and
  Table 7 (pre-arcing I²t at 0.01 s), completed for the small ratings by the
  fuse systems of IEC 60269-2:2013+A1:2016 (system A, Table 102) and
  IEC 60269-3:2010+A1:2013 (systems A, B, C and F, Tables 103, 203, 406 and
  602).  aM fuse-links follow Table 4 of Part 1.  The upper limit of the
  band — I_max(5 s), I_max(0.1 s), the conventional fusing current I_f at the
  conventional time and √(I²t_max/0.01 s) — joined by straight lines on
  log–log axes, gives a current that operates *any* compliant fuse-link of
  that rating within the time: a safe answer for a fuse of unknown make.
  Joining the gate points by straight lines is conservative, because real
  characteristics lie below that chord: for a 32 A gG fuse it gives 259 A
  at 0.4 s against the 221 A of BS 7671 Table 41.2 for BS 88-2 fuses.
* **BS 7671 tables** for BS 88-2/-3 fuses (``iec60364.FUSE_GG``), as before.
* **The manufacturer's curve**, as current–time points (CSV), interpolated on
  log–log axes; a current tolerance (published curves are often the mean
  pre-arcing curve with ±10 % in current) moves it to the safe side.

Times are pre-arcing times; above 0.1 s the arcing time is negligible, which
is how IEC 60364 and BS 7671 use fuse characteristics.  Below the shortest
tabulated time the current is extrapolated at constant I²t, which is safe
(the melting I²t falls slightly as the time shortens).
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------- IEC 60269-1
# Table 3: In -> (I_min(10 s), I_max(5 s), I_min(0.1 s), I_max(0.1 s)), A
GATES_PART1 = {
    16: (33, 65, 85, 150), 20: (42, 85, 110, 200), 25: (52, 110, 150, 260),
    32: (75, 150, 200, 350), 35: (83, 175, 225, 445), 40: (95, 190, 260, 450),
    50: (125, 250, 350, 610), 63: (160, 320, 450, 820), 80: (215, 425, 610, 1100),
    100: (290, 580, 820, 1450), 125: (355, 715, 1100, 1910), 160: (460, 950, 1450, 2590),
    200: (610, 1250, 1910, 3420), 250: (750, 1650, 2590, 4500), 315: (1050, 2200, 3420, 6000),
    400: (1420, 2840, 4500, 8060), 500: (1780, 3800, 6000, 10600),
    630: (2200, 5100, 8060, 14140), 800: (3060, 7000, 10600, 19000),
    1000: (4000, 9500, 14140, 24000), 1250: (5000, 13000, 19000, 35000),
}
# Table 7: pre-arcing I²t at 0.01 s, (min, max) in A²s
I2T_PART1 = {
    16: (0.3e3, 1.0e3), 20: (0.5e3, 1.8e3), 25: (1.0e3, 3.0e3), 32: (1.8e3, 5.0e3),
    35: (2.2e3, 8.0e3), 40: (3.0e3, 9.0e3), 50: (5.0e3, 16.0e3), 63: (9.0e3, 27.0e3),
    80: (16.0e3, 46.0e3), 100: (27.0e3, 86.0e3), 125: (46.0e3, 140.0e3),
    160: (86.0e3, 250.0e3), 200: (140.0e3, 400.0e3), 250: (250.0e3, 760.0e3),
    315: (400.0e3, 1300.0e3), 400: (760.0e3, 2250.0e3), 500: (1300.0e3, 3800.0e3),
    630: (2250.0e3, 7500.0e3), 800: (3800.0e3, 13600.0e3), 1000: (7840.0e3, 25000.0e3),
    1250: (13700.0e3, 47000.0e3),
}
# Table 4: aM gates, multiples of In — operating (upper) and pre-arcing (lower)
AM_UPPER = ((6.3, 60.0), (12.5, 0.5), (19.0, 0.1))
AM_LOWER = ((4.0, 60.0), (8.0, 0.5), (10.0, 0.2))

# the small ratings of the fuse systems in Parts 2 and 3
SYSTEMS = {
    "general": dict(name="IEC 60269-1 (16–1250 A)", extra={}, source="IEC 60269-1 Table 3"),
    "industrial_A": dict(
        name="Industrial fuse system A (NH), IEC 60269-2", source="IEC 60269-2 Table 102",
        extra={2: (3.7, 9.2, 6.0, 23.0), 4: (7.8, 18.5, 14.0, 47.0), 6: (11.0, 28.0, 26.0, 72.0),
               8: (16.0, 35.2, 41.6, 92.0), 10: (22.0, 46.5, 58.0, 110.0), 12: (24.0, 55.2, 69.6, 140.4),
               224: (680, 1450, 2240, 3980)}),
    "D_type": dict(
        name="D-type fuse system (Diazed), IEC 60269-3 system A", source="IEC 60269-3 Table 103",
        extra={2: (3.7, 9.2, 6.0, 23.0), 4: (7.8, 18.5, 14.0, 47.0), 6: (11.0, 28.0, 26.0, 72.0),
               10: (22.0, 46.5, 58.0, 111.0), 13: (26.0, 59.8, 75.4, 144.3), 35: (89.0, 175.0, 255.0, 445.0)}),
    "NF_cylindrical": dict(
        name="NF cylindrical fuse system, IEC 60269-3 system B", source="IEC 60269-3 Table 203",
        extra={6: (11.0, 28.0, 26.0, 72.0), 10: (22.0, 46.5, 47.0, 110.0)}),
    "BS_cylindrical": dict(
        name="BS cylindrical fuse system (BS 88-3), IEC 60269-3 system C", source="IEC 60269-3 Table 406",
        extra={2: (3.7, 8.5, 6.0, 23.0), 4: (8.0, 18.0, 14.0, 45.0), 6: (12.0, 26.0, 28.0, 75.0),
               10: (22.0, 38.0, 50.0, 85.0)}),
    "plugtop": dict(
        name="BS plug-top fuse-links (BS 1362), IEC 60269-3 system F", source="IEC 60269-3 Table 602",
        extra={3: (5.5, 9.5, 7.0, 19.0), 13: (30.0, 55.0, 70.0, 140.0)}, only_extra=True),
}


def _conventional(In, system):
    """(I_nf, I_f, conventional time in s), IEC 60269-1 Table 2 and the
    small-rating rows of Parts 2 and 3."""
    if system == "plugtop":
        return 1.6 * In, 1.9 * In, 0.5 * 3600
    if In <= 4:
        return 1.5 * In, 2.1 * In, 3600.0
    if In < 16:
        return 1.5 * In, 1.9 * In, 3600.0
    h = 1 if In <= 63 else 2 if In <= 160 else 3 if In <= 400 else 4
    return 1.25 * In, 1.6 * In, h * 3600.0


def ratings(system="general"):
    s = SYSTEMS[system]
    r = set(s["extra"])
    if not s.get("only_extra"):
        r |= set(GATES_PART1)
    return sorted(r)


def gates(In, system="general"):
    """The gates of one rating: dict with the four gate currents, the I²t
    at 0.01 s (≥ 16 A) and the conventional currents."""
    if system not in SYSTEMS:
        raise ValueError(f"Unknown fuse system '{system}'. Use one of: {', '.join(SYSTEMS)}.")
    s = SYSTEMS[system]
    In_f = float(In)
    key = int(round(In_f)) if abs(In_f - round(In_f)) < 1e-9 else None
    if key in s["extra"]:
        g, src = s["extra"][key], s["source"]
    elif key in GATES_PART1 and not s.get("only_extra"):
        g, src = GATES_PART1[key], "IEC 60269-1 Table 3"
    else:
        raise ValueError(f"{In_f:g} A is not a rating with gates in {s['name']}; "
                         f"standard ratings: {', '.join(str(r) for r in ratings(system))} A.")
    Inf, If, tc = _conventional(In_f, system)
    i2t = I2T_PART1.get(key) if src == "IEC 60269-1 Table 3" or key in I2T_PART1 else None
    return dict(In=In_f, system=system, I_min_10s=float(g[0]), I_max_5s=float(g[1]),
                I_min_01s=float(g[2]), I_max_01s=float(g[3]), I_nf=Inf, I_f=If,
                t_conventional=tc, I2t_001s=i2t, source=src)


def band(In, kind="gG", system="general"):
    """Upper (operates for certain) and lower (does not yet melt) limits of
    the time–current band, each a list of (current A, time s), current
    rising and time falling."""
    kind = kind.upper() if kind.lower() != "gg" else "gG"
    if kind in ("GG", "gG", "GM"):
        g = gates(In, system)
        up = [(g["I_f"], g["t_conventional"]), (g["I_max_5s"], 5.0), (g["I_max_01s"], 0.1)]
        lo = [(g["I_nf"], g["t_conventional"]), (g["I_min_10s"], 10.0), (g["I_min_01s"], 0.1)]
        if g["I2t_001s"]:
            up.append((math.sqrt(g["I2t_001s"][1] / 0.01), 0.01))
            lo.append((math.sqrt(g["I2t_001s"][0] / 0.01), 0.01))
        src = g["source"] + (", Table 7" if g["I2t_001s"] else "") + ", Table 2"
        return dict(kind="gM" if kind == "GM" else "gG", In=float(In), system=system,
                    upper=up, lower=lo, gates=g, source=src)
    if kind == "AM":
        In = float(In)
        return dict(kind="aM", In=In, system="general",
                    upper=[(m * In, t) for m, t in AM_UPPER],
                    lower=[(m * In, t) for m, t in AM_LOWER],
                    source="IEC 60269-1 Table 4 (aM, k₀ = 1.5, k₁ = 4, k₂ = 6.3)")
    raise ValueError("Fuse class must be gG, gM or aM.")


# ------------------------------------------------------- interpolation helpers
def _check_curve(pts):
    if len(pts) < 2:
        raise ValueError("A time–current curve needs at least two points.")
    for i in range(1, len(pts)):
        if not (pts[i][0] > pts[i - 1][0] and pts[i][1] < pts[i - 1][1]):
            raise ValueError("The time must fall as the current rises at every point of the curve "
                             f"(check the points near {pts[i][0]:g} A).")


def current_at(pts, t):
    """Current for a time t on a curve of (I, t) points, log–log; below the
    shortest time at constant I²t, above the longest time None."""
    t = float(t)
    if t <= 0:
        raise ValueError("The time must be positive.")
    if t > pts[0][1]:
        return None, "longer than the curve"
    if t < pts[-1][1]:
        I, tt = pts[-1]
        return I * math.sqrt(tt / t), "extrapolated at constant I²t"
    for (I1, t1), (I2, t2) in zip(pts[:-1], pts[1:]):
        if t2 <= t <= t1:
            if t1 == t2:
                return I1, "on the curve"
            f = math.log(t1 / t) / math.log(t1 / t2)
            return I1 * (I2 / I1) ** f, "interpolated"
    return None, "outside the curve"


def time_at(pts, I):
    """Time for a current I on a curve of (I, t) points, log–log; above the
    largest current at constant I²t, below the smallest current None (the
    fuse is not shown to operate)."""
    I = float(I)
    if I < pts[0][0]:
        return None, "below the curve"
    if I > pts[-1][0]:
        I2, t2 = pts[-1]
        return t2 * (I2 / I) ** 2, "extrapolated at constant I²t"
    for (I1, t1), (I2, t2) in zip(pts[:-1], pts[1:]):
        if I1 <= I <= I2:
            f = math.log(I / I1) / math.log(I2 / I1)
            return t1 * (t2 / t1) ** f, "interpolated"
    return None, "outside the curve"


def parse_curve(text_or_points):
    """Current–time points from CSV text (two columns, current first unless a
    header names time first; ',' ';' tab or spaces; a header with 'kA'
    scales by 1000; '#' starts a comment) or from a list of pairs."""
    if not isinstance(text_or_points, str):
        pts = [(float(a), float(b)) for a, b in text_or_points]
    else:
        pts, swap, scale = [], False, 1.0
        for raw in text_or_points.replace("\r", "\n").split("\n"):
            line = raw.split("#")[0].strip()
            if not line:
                continue
            parts = [q for q in line.replace(";", ",").replace("\t", ",").replace(" ", ",").split(",") if q]
            if len(parts) < 2:
                continue
            try:
                a, b = float(parts[0]), float(parts[1])
            except ValueError:
                head = [q.lower() for q in parts[:2]]
                swap = head[0].startswith("t") or head[0].startswith("time")
                scale = 1000.0 if any("ka" in q for q in head) else 1.0
                continue
            pts.append((b * scale, a) if swap else (a * scale, b))
    if any(not (math.isfinite(I) and math.isfinite(t)) or I <= 0 or t <= 0 for I, t in pts):
        raise ValueError("Every current and time of the curve must be a positive number.")
    pts.sort()
    _check_curve(pts)
    return pts


def operating_current(t, *, kind="gG", rating=None, system="general", points=None,
                      tolerance_pct=0.0):
    """I_a for operation within t: from the manufacturer's points when given,
    otherwise from the upper limit of the IEC 60269 band."""
    tol = 1.0 + float(tolerance_pct or 0) / 100.0
    if points is not None:
        pts = parse_curve(points)
        I, how = current_at(pts, t)
        if I is None:
            raise ValueError(f"The curve's longest time is {pts[0][1]:g} s; it does not reach {t:g} s.")
        return dict(Ia=I * tol, how=how, curve=pts, tolerance_pct=float(tolerance_pct or 0),
                    basis=(f"manufacturer's curve, {t:g} s ({how})"
                           + (f", +{float(tolerance_pct):g} % current tolerance" if tolerance_pct else "")))
    b = band(rating, kind, system)
    I, how = current_at(b["upper"], t)
    if I is None:
        raise ValueError(f"{t:g} s is longer than the conventional time of the fuse.")
    name = SYSTEMS[system]["name"] if b["kind"] != "aM" else "IEC 60269-1"
    return dict(Ia=I, how=how, band=b,
                basis=(f"{b['kind']} fuse {float(rating):g} A, {t:g} s: upper limit of the "
                       f"IEC 60269 gates ({b['source']}; {name}), {how} on log–log axes — "
                       "valid for any compliant fuse-link, conservative"))


def operating_time(I, *, kind="gG", rating=None, system="general", points=None,
                   tolerance_pct=0.0):
    """Time within which the fuse is certain to operate at current I (upper
    limit of the band, or the manufacturer's curve with the tolerance)."""
    tol = 1.0 + float(tolerance_pct or 0) / 100.0
    pts = parse_curve(points) if points is not None else band(rating, kind, system)["upper"]
    t, how = time_at(pts, float(I) / tol)
    return dict(t=t, how=how)


def describe(p: dict) -> dict:
    """Everything the fuse card shows: the band or curve sampled for a plot,
    I_a at the usual disconnection times and the time at a given current."""
    kind = str(p.get("kind", "gG"))
    system = p.get("system", "general")
    pts_in = p.get("points")
    if isinstance(pts_in, str) and not pts_in.strip():
        pts_in = None
    tol = float(p.get("tolerance_pct", 0) or 0)
    rating = p.get("rating")
    out = dict(kind=kind, system=system)
    if pts_in is not None:
        pts = parse_curve(pts_in)
        out.update(curve=pts, source="manufacturer's curve", tolerance_pct=tol)
        lines = dict(curve=pts, curve_tol=[(I * (1 + tol / 100.0), t) for I, t in pts] if tol else None)
    else:
        if rating in (None, ""):
            raise ValueError("Give the fuse rating.")
        b = band(float(rating), kind, system)
        out.update(band=b, source=b["source"])
        lines = dict(upper=b["upper"], lower=b["lower"])
    kw = dict(kind=kind, rating=rating, system=system, points=pts_in, tolerance_pct=tol)
    rows = []
    for t in (0.1, 0.2, 0.4, 1.0, 5.0):
        try:
            r = operating_current(t, **kw)
            rows.append(dict(t=t, Ia=r["Ia"], how=r["how"]))
        except ValueError:
            rows.append(dict(t=t, Ia=None, how="outside the curve"))
    out["Ia_table"] = rows
    if p.get("I") not in (None, ""):
        out["at_current"] = dict(I=float(p["I"]), **operating_time(float(p["I"]), **kw))
    out["lines"] = lines
    return out
