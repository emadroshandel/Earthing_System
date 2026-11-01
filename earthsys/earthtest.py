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
Fall-of-potential test planning and interpretation (1.8.0).

IEEE Std 81-2025 clause 8 measures the resistance of an earth electrode by
injecting a current I between the electrode E and a remote current
electrode C, and reading the voltage between E and a potential probe P
moved out along the traverse.  The reading R(x) = V_EP/I equals the true
resistance only where the potential of P equals that of remote earth as
seen from the electrode — the "61.8 % rule" for a hemisphere in uniform
soil.  For a large grid, a layered soil or a probe line at an angle to the
current line, that point moves, and a reading taken at 61.8 % can be in
error by tens of percent.

Here the electrode and a driven current electrode are solved together
with the boundary-element solver (two networks, +I into the grid and −I
into C), so the whole curve R(x) is computed for the real geometry and
soil.  From it:

* the probe position where R(x) equals the true resistance;
* the error of the 61.8 % reading;
* the current-electrode distance needed for a given accuracy;
* and, with measured readings, the scale factor between site and model —
  the resistance the measurements imply and how well their shape agrees.
"""

from __future__ import annotations

import math

from . import bem

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None


def _electrode_frame(net):
    """Centroid and largest plan dimension of the main network."""
    pts = np.array([q for it in net.raw if it[4] == 0 for q in (it[0], it[1])], float)
    c = pts[:, :2].mean(axis=0)
    span = float(np.hypot(*(pts[:, :2].max(axis=0) - pts[:, :2].min(axis=0))))
    return c, max(span, 1.0)


def _edge_distance(net, c, u):
    """Distance from the centroid c to the electrode's edge along u."""
    pts = np.array([q for it in net.raw if it[4] == 0 for q in (it[0], it[1])], float)[:, :2]
    proj = (pts - c[None, :]) @ u
    return float(max(proj.max(), 0.0))


def curve(p: dict, dC: float, bearing_deg: float = 0.0, probe_angle_deg: float = 0.0,
          n: int = 60, rod_length: float = 0.6, rod_radius: float = 0.008,
          from_edge: bool = False):
    """R(x) along the probe line for a current electrode at distance dC.

    Distances are measured from the electrode's centre, as IEEE Std 81 does
    and as the 61.8 % rule assumes, or from its edge in the direction of the
    traverse (from_edge), as is often done on site.
    probe_angle_deg turns the probe line away from the current line (the 90°
    method is probe_angle_deg = 90)."""
    base = bem.build_network({k: v for k, v in p.items() if k != "IG"} | dict(IG=1.0))
    c, span = _electrode_frame(base)
    u = np.array([math.cos(math.radians(bearing_deg)), math.sin(math.radians(bearing_deg))])
    up = np.array([math.cos(math.radians(bearing_deg + probe_angle_deg)),
                   math.sin(math.radians(bearing_deg + probe_angle_deg))])
    e0 = _edge_distance(base, c, u) if from_edge else 0.0
    e0p = _edge_distance(base, c, up) if from_edge else 0.0
    xc = c + u * (e0 + dC)
    # the grid alone, for its true resistance
    seg = float(p.get("segment_length", 2.5))
    g = bool(p.get("grade_ends", True))
    base.discretise(seg, int(p.get("max_segments", bem.MAX_SEGMENTS)), grade_ends=g)
    Rg_true = float(base.solve()["Rg"])
    # grid (+1 A) and current electrode (−1 A) together
    net = bem.build_network({k: v for k, v in p.items() if k != "IG"} | dict(IG=1.0))
    k = net.add_network("current electrode C", injection=-1.0, kind="test")
    net.use_network(k)
    net.add_rod(float(xc[0]), float(xc[1]), 0.0, rod_length, rod_radius, tag="C")
    net.use_network(0)
    net.discretise(seg, int(p.get("max_segments", bem.MAX_SEGMENTS)), grade_ends=g)
    net.solve()
    VE = float(net.Vnet[0])
    xs = np.linspace(0.0, 1.0, n + 1)[1:] * dC
    xs = np.unique(np.concatenate([xs, [0.618 * dC]]))
    pts = np.column_stack([c[0] + up[0] * (e0p + xs), c[1] + up[1] * (e0p + xs), np.zeros(len(xs))])
    VP = np.asarray(net.potential_at(pts))
    R = VE - VP                                     # per ampere
    out = dict(x=xs.tolist(), R=R.tolist(), Rg_true=Rg_true, dC=float(dC),
               bearing=float(bearing_deg), probe_angle=float(probe_angle_deg),
               edge_offset=e0, span=span, from_edge=bool(from_edge),
               current_electrode=[float(xc[0]), float(xc[1])])
    # where the reading equals the true resistance
    diff = R - Rg_true
    cross = None
    for i in range(len(xs) - 1):
        if diff[i] == 0 or diff[i] * diff[i + 1] < 0:
            t = diff[i] / (diff[i] - diff[i + 1]) if diff[i] != diff[i + 1] else 0.0
            cross = float(xs[i] + t * (xs[i + 1] - xs[i]))
            break
    out["x_true"] = cross
    out["x_true_fraction"] = cross / dC if cross is not None else None
    r618 = float(np.interp(0.618 * dC, xs, R))
    out["R_618"] = r618
    out["error_618_pct"] = (r618 / Rg_true - 1.0) * 100.0
    return out


def plan(p: dict, bearing_deg: float = 0.0, probe_angle_deg: float = 0.0,
         multiples=(1, 2, 3, 5, 7, 10), accuracy_pct: float = 2.0,
         measured=None, dC_measured: float | None = None, from_edge: bool = False) -> dict:
    """Fall-of-potential study.

    Sweeps the current-electrode distance in multiples of the electrode's
    largest dimension D, reports for each the 61.8 % error and where the
    probe must stand, recommends the shortest distance whose 61.8 % reading
    is within `accuracy_pct`, and — given measured (x, R) pairs taken with
    the current electrode at dC_measured — scales the model to them.
    """
    base = bem.build_network(dict(p) | dict(IG=1.0))
    _, D = _electrode_frame(base)
    sweep = []
    for m in multiples:
        cv = curve(p, m * D, bearing_deg, probe_angle_deg, n=40, from_edge=from_edge)
        sweep.append(dict(multiple=m, dC=cv["dC"], error_618_pct=cv["error_618_pct"],
                          x_true_fraction=cv["x_true_fraction"], R_618=cv["R_618"]))
    Rg = curve(p, multiples[0] * D, bearing_deg, probe_angle_deg, n=4, from_edge=from_edge)["Rg_true"]
    rec = next((s for s in sweep if abs(s["error_618_pct"]) <= accuracy_pct), None)
    ref = "edge" if from_edge else "centre"
    out = dict(D=D, Rg_model=Rg, sweep=sweep, accuracy_pct=accuracy_pct,
               bearing=bearing_deg, probe_angle=probe_angle_deg,
               recommended=rec, measured_from=ref)
    if rec:
        out["note"] = (f"With the current electrode {rec['dC']:.0f} m from the electrode's {ref} "
                       f"({rec['multiple']:g} × its largest dimension, D = {D:.0f} m) the 61.8 % "
                       f"reading is within {abs(rec['error_618_pct']):.1f} % of the true "
                       f"resistance; the reading equals it with the probe at "
                       f"{100 * (rec['x_true_fraction'] or 0.618):.1f} % of the distance.")
    else:
        last = sweep[-1]
        out["note"] = (f"Even at {last['dC']:.0f} m ({last['multiple']:g} D) the 61.8 % reading "
                       f"is {last['error_618_pct']:+.1f} % out. Take the reading at the computed "
                       f"position ({100 * (last['x_true_fraction'] or 0.618):.1f} % of the "
                       f"distance), or use the slope or intersecting-curves methods of "
                       f"IEEE Std 81.")
    dCp = dC_measured or (rec["dC"] if rec else sweep[-1]["dC"])
    cv = curve(p, dCp, bearing_deg, probe_angle_deg, n=60, from_edge=from_edge)
    out["curve"] = cv
    if measured:
        xm = np.array([float(m[0]) for m in measured])
        Rm = np.array([float(m[1]) for m in measured])
        Rmod = np.interp(xm, cv["x"], cv["R"])
        k = float((Rm * Rmod).sum() / (Rmod * Rmod).sum())
        resid = (Rm - k * Rmod) / np.maximum(Rm, 1e-12) * 100.0
        out["interpretation"] = dict(
            scale=k, R_true_estimate=k * cv["Rg_true"],
            rms_shape_pct=float(math.sqrt(float((resid ** 2).mean()))),
            residual_pct=resid.tolist(), x=xm.tolist(), R=Rm.tolist(),
            note=(f"The measured curve is {k:.3f} times the computed one, so the electrode's "
                  f"resistance is about {k * cv['Rg_true']:.4g} Ω and the soil about {k:.2f} times "
                  f"as resistive as modelled. "
                  + ("The shape agrees (RMS "
                     f"{math.sqrt(float((resid ** 2).mean())):.1f} %): the layering is right and "
                     "only the level differs." if math.sqrt(float((resid ** 2).mean())) <= 5 else
                     "The shape does not agree (RMS "
                     f"{math.sqrt(float((resid ** 2).mean())):.1f} %): the soil layering, the "
                     "electrode geometry or buried metal near the traverse differ from the model; "
                     "do not rely on a single scale factor.")))
    return out
