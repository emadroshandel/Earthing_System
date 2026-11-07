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
JSON API layer.

Every endpoint is a plain function taking a dict of parameters and returning a
dict of results.  The layer is deliberately transport-agnostic: `server.py`
exposes it over HTTP for the desktop application, and `web/pyodide-boot.js`
calls exactly the same functions inside the browser when Earthing System runs from
GitHub Pages with no server at all.
"""

from __future__ import annotations

import json
import math
import os

from . import (airterm, bem, dxfimport, earthtest, fuses, governing, hf, layered, powerfreq, risk, spd, studies, transfer, conductor, drawings, earthpit, faultcurrent, iec60364,
               iec62305, ieee80, ieee142, materials, reasoning, report, soil, standards)

APP_VERSION = "1.11.0"

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.path.join(BASE, "projects")
OUTPUTS = os.path.join(BASE, "outputs")


# --------------------------------------------------------------------------
# input validation
#
# The engineering formulas divide by spacings, durations and resistivities, so
# a zero or a blank arrives as a ZeroDivisionError and the user is shown
# "float division by zero" — true, and useless. Each endpoint declares which of
# its inputs the physics needs to be positive, and the message names the field.
# --------------------------------------------------------------------------

def _require_positive(p, spec):
    """spec: {payload_key: "human name (unit)"} — each must be finite and > 0."""
    for key, label in spec.items():
        raw = p.get(key)
        if raw is None or raw == "":
            raise ValueError(f"{label} is required.")
        try:
            v = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a number.")
        if not math.isfinite(v):
            raise ValueError(f"{label} must be a number.")
        if v <= 0:
            raise ValueError(f"{label} must be greater than zero — the "
                             f"calculation divides by it.")


def _require_rows(rows, label="measurement"):
    """A survey or geometry table needs at least one usable row."""
    if not rows:
        raise ValueError(f"Add at least one {label} row before running this.")


def _require_spacings(rows):
    """Every pin spacing divides into the array formula, so a zero or a blank
    in the table has to be caught by name rather than deep in the maths."""
    for i, r in enumerate(rows or [], 1):
        for key, label in (("a", "pin spacing"), ("s", "spacing")):
            if key in r:
                try:
                    v = float(r[key])
                except (TypeError, ValueError):
                    raise ValueError(f"Row {i}: the {label} must be a number.")
                if not math.isfinite(v) or v <= 0:
                    raise ValueError(
                        f"Row {i}: the {label} must be greater than zero.")
                break
        mn = r.get("d", 1)
        if mn is not None and float(mn) <= 0:
            raise ValueError(f"Row {i}: the potential-pin spacing MN must be "
                             f"greater than zero.")


def clean(obj):
    """Make a value JSON-safe (NaN/Inf -> None, numpy scalars -> float)."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if hasattr(obj, "item") and hasattr(obj, "dtype"):
        try:
            return clean(obj.item())
        except Exception:
            return str(obj)
    if isinstance(obj, complex):
        return dict(r=obj.real, x=obj.imag, mag=abs(obj))
    return obj


def _cplx(d):
    """Accept {'r':..,'x':..} or a number and return a complex."""
    if d is None:
        return 0j
    if isinstance(d, dict):
        return complex(float(d.get("r", 0.0)), float(d.get("x", 0.0)))
    return complex(float(d), 0.0)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

def api_meta(_):
    return dict(
        version=APP_VERSION,
        materials=materials.material_list(),
        soil_types=materials.SOIL_TYPES,
        surface_materials=materials.SURFACE_MATERIALS,
        std_areas=materials.STD_AREAS_MM2,
        std_awg=materials.STD_AWG,
        std_tapes=materials.STD_TAPES,
        std_rods=materials.STD_RODS,
        joint_limits=materials.JOINT_TM_LIMITS,
        k_separate={f"{a}|{b}": v for (a, b), v in materials.K_FACTORS_SEPARATE.items()},
        k_in_cable={f"{a}|{b}": v for (a, b), v in materials.K_FACTORS_IN_CABLE.items()},
        k_buried={f"{a}|{b}": v for (a, b), v in materials.K_FACTORS_BURIED.items()},
        split_factor_guide=faultcurrent.SPLIT_FACTOR_GUIDE,
        split_factor_table_c1=[dict(lines=k[0], neutrals=k[1], z15=[v[0].real, v[0].imag], z100=[v[1].real, v[1].imag]) for k, v in faultcurrent.SPLIT_FACTOR_TABLE_C1.items()],
        c_factors=faultcurrent.C_FACTORS,
        system_types=iec60364.SYSTEM_TYPES,
        disconnection_times=iec60364.DISCONNECTION_TIMES,
        fuse_gg={str(k): v for k, v in iec60364.FUSE_GG.items()},
        fuse_systems={k: dict(name=v["name"], ratings=fuses.ratings(k)) for k, v in fuses.SYSTEMS.items()},
        mcb_multipliers=iec60364.MCB_MULTIPLIERS,
        lps_classes=iec62305.LPS_CLASS,
        impulse_fronts=iec62305.IMPULSE_FRONTS,
        lps_l1={"rho": materials.LPS_L1_RHO, "l1": materials.LPS_L1},
        lps_electrodes=materials.LPS_ELECTRODE_MIN,
        grounding_methods=ieee142.GROUNDING_METHODS,
        have_numpy=bem.HAVE_NUMPY,
        standards=standards.REGISTRY,
        standard_areas=standards.AREAS,
    )


def api_soil_reduce(p):
    _require_rows(p.get("rows"), "survey")
    _require_spacings(p.get("rows"))
    _require_readings(p.get("rows"))

    rows = soil.reduce_survey(p.get("rows", []), p.get("array", "wenner"))
    return dict(rows=rows)


def _require_readings(rows):
    for i, r in enumerate(rows or [], 1):
        for k in ("rho", "R", "value"):
            if r.get(k) not in (None, ""):
                try:
                    v = float(r[k])
                except (TypeError, ValueError):
                    raise ValueError(f"Reading {i}: '{r[k]}' is not a number.")
                if not math.isfinite(v) or v <= 0:
                    raise ValueError(f"Reading {i}: the measured value must be "
                                     f"greater than zero.")


def api_soil_invert(p):
    _require_rows(p.get("rows"), "survey")
    _require_spacings(p.get("rows"))
    _require_readings(p.get("rows"))

    rows = p.get("rows")
    array = p.get("array", "wenner")
    mn = None
    labels = None
    if rows:
        red = soil.reduce_survey(rows, array)
        sp = [r["spacing"] for r in red]
        rh = [r["rho"] for r in red]
        labels = [r.get("traverse") for r in red]
        if array == "schlumberger":
            mn = [r.get("d") for r in red]
    else:
        sp = p["spacings"]
        rh = p["rho"]
        if array == "schlumberger" and p.get("mn"):
            mn = p["mn"]
    res = _soil_invert_core(p, sp, rh, mn, array)
    if _truthy(p.get("robust", True)) and len(sp) >= 5:
        res = _robust_refit(p, res, sp, rh, mn, array)
    if labels and len({t for t in labels if t}) >= 2:
        res["traverses"] = _traverse_fits(sp, rh, mn, labels, array)
    return res


def _model_rho(res, array, xs, mn=None):
    """Apparent resistivity of a fitted model at spacings xs."""
    if res.get("n_layers", 2) >= 3:
        rr = [res["rho1"], res["rho2"], res["rho3"]] + ([res["rho4"]] if res.get("rho4") else [])
        hh = [res["h"], res["h2"]] + ([res["h3"]] if res.get("h3") else [])
        return [float(v) for v in layered.apparent(layered.LayeredEarth(rr, hh), array, xs, mn)]
    fwd = soil.FORWARD.get(array, soil.wenner_two_layer)
    out = []
    for i, a in enumerate(xs):
        if array == "schlumberger" and mn is not None:
            out.append(float(fwd(a, res["rho1"], res["rho2"], res["h"], mn[i])))
        else:
            out.append(float(fwd(a, res["rho1"], res["rho2"], res["h"])))
    return out


def _robust_refit(p, res, sp, rh, mn, array):
    """Reject readings the model cannot explain, and refit without them.

    A single bad reading (a pin in a stone, a buried pipe, a misread range)
    pulls a least-squares fit towards itself.  The residuals of the first fit
    are scaled by their median absolute deviation, σ ≈ 1.4826·MAD, and a
    reading more than max(3σ, 5 %) from the median is set aside — at most a
    fifth of them, and never so many that the model loses its spare
    degrees of freedom.  The refit is reported with the excluded readings,
    their value under the refitted model, and the RMS before and after.
    One reading is set aside at a time and the model refitted, since a large
    outlier distorts the residuals of its neighbours."""
    keep = list(range(len(sp)))
    excluded = []
    cur = res
    need = {2: 4, 3: 6, 4: 9}
    for _ in range(max(1, len(sp) // 5)):
        r = [cur["residual_pct"][i] for i in range(len(keep))]
        med = sorted(r)[len(r) // 2]
        mad = sorted(abs(v - med) for v in r)[len(r) // 2] * 1.4826
        thr = max(3.0 * mad, 5.0)
        bad = sorted(((abs(r[i] - med), i) for i in range(len(keep)) if abs(r[i] - med) > thr),
                     reverse=True)
        room = min(len(sp) // 5 - len(excluded),
                   len(keep) - need.get(int(cur.get("n_layers", 2)), 4))
        # one at a time: the worst reading drags the fit, so the residuals of
        # its neighbours are only meaningful once it has been set aside
        bad = bad[:min(1, max(room, 0))]
        if not bad:
            break
        for _, i in bad:
            excluded.append(keep[i])
        keep = [k for k in range(len(sp)) if k not in excluded]
        cur = _soil_invert_core(p, [sp[k] for k in keep], [rh[k] for k in keep],
                                [mn[k] for k in keep] if mn else None, array)
    if not excluded:
        res["robust"] = dict(applied=True, excluded=[],
                             note="No reading lies further from the fitted curve than the scatter of "
                                  "the others explains (3 × the robust standard deviation, at least 5 %).")
        return res
    ex = sorted(excluded)
    xs = [sp[k] for k in ex]
    model = _model_rho(cur, array, xs, [mn[k] for k in ex] if mn else None)
    cur["robust"] = dict(
        applied=True, rms_all=res["rms_pct"], rms_kept=cur["rms_pct"],
        excluded=[dict(index=k + 1, spacing=sp[k], measured=rh[k], model=m,
                       residual_pct=(m - rh[k]) / rh[k] * 100.0)
                  for k, m in zip(ex, model)],
        note=(f"{len(ex)} reading{'s' if len(ex) > 1 else ''} set aside as inconsistent with the "
              f"rest (more than 3 robust standard deviations, at least 5 %, from the fitted "
              f"curve); the RMS error falls from {res['rms_pct']:.2f} % to {cur['rms_pct']:.2f} %. "
              "Check the field sheet for those spacings — re-measure them if you can — before "
              "accepting the refit."))
    return cur


def _traverse_fits(sp, rh, mn, labels, array):
    """A two-layer fit of each traverse on its own, and how much they differ.

    The inversion assumes horizontal layers; traverses in different
    directions or places that disagree show lateral variation, which no
    layered model represents.  IEEE Std 81 recommends several traverses for
    exactly this reason."""
    groups = {}
    for i, t in enumerate(labels):
        groups.setdefault(t or "(unlabelled)", []).append(i)
    fits = []
    for name, idx in groups.items():
        if len(idx) < 3:
            fits.append(dict(name=name, n=len(idx), fitted=False))
            continue
        r = soil.invert_two_layer([sp[i] for i in idx], [rh[i] for i in idx], array,
                                  [mn[i] for i in idx] if mn else None)
        fits.append(dict(name=name, n=len(idx), fitted=True, rho1=r["rho1"], rho2=r["rho2"],
                         h=r["h"], rms_pct=r["rms_pct"], curve_x=r["curve_x"],
                         curve_y=r["curve_y"], spacings=r["spacings"], measured=r["measured"]))
    ok = [f for f in fits if f["fitted"]]
    out = dict(fits=fits)
    if len(ok) >= 2:
        sp1 = max(f["rho1"] for f in ok) / min(f["rho1"] for f in ok)
        sp2 = max(f["rho2"] for f in ok) / min(f["rho2"] for f in ok)
        # apparent resistivity at the spacings the traverses share
        common = None
        for f in ok:
            s_ = {round(x, 6) for x in f["spacings"]}
            common = s_ if common is None else common & s_
        worst = 1.0
        for x in sorted(common or []):
            vals = [f["measured"][[round(v, 6) for v in f["spacings"]].index(x)] for f in ok]
            worst = max(worst, max(vals) / min(vals))
        out.update(spread_rho1=sp1, spread_rho2=sp2, spread_apparent=worst,
                   lateral=bool(max(sp1, sp2, worst) > 1.5))
        out["note"] = (
            f"The traverses give ρ₁ within a factor {sp1:.2f} and ρ₂ within {sp2:.2f}"
            + (f", and their readings at shared spacings differ by up to a factor {worst:.2f}"
               if common else "") + ". "
            + ("That is more than 1.5: the soil varies laterally, which a layered model cannot "
               "represent. Design with the worst traverse (the highest resistivity where the "
               "electrode is), or model the zones separately." if out["lateral"] else
               "The site is laterally uniform enough for one layered model."))
    return out


def _soil_invert_core(p, sp, rh, mn, array):
    layers = _require_choice(str(p.get("layers", "auto")).lower(),
                             {"auto", "2", "3", "4"}, "Number of soil layers")
    res = soil.invert_two_layer(sp, rh, array, mn)
    res["n_layers"] = 2
    run3 = layers in ("3", "4") or (layers == "auto" and len(sp) >= 6 and (
        res["rms_pct"] > 3.0 or res.get("three_layer_suspected")))
    if layers == "3" and len(sp) < 6:
        raise ValueError(f"A three-layer fit has five parameters and needs at "
                         f"least six readings; {len(sp)} were given.")
    if layers == "4" and len(sp) < 9:
        raise ValueError(f"A four-layer fit has seven parameters and needs at "
                         f"least nine readings; {len(sp)} were given.")
    if run3:
        sel = layered.select_three(sp, rh, res, array, mn)
        res["model_selection"] = dict(
            requested=layers, chosen=sel["chosen"], F=sel["F"],
            p_value=sel["p_value"], reason=sel["reason"],
            rms_two=sel.get("rms_two"), rms_three=sel.get("rms_three"))
        three = sel["three"]
        use3 = three is not None and (sel["chosen"] == 3 or layers in ("3", "4"))
        sel4 = None
        if use3 and (layers == "4" or (layers == "auto" and len(sp) >= 9
                                       and three["rms_pct"] > 3.0)):
            sel4 = layered.select_four(sp, rh, three, array, mn)
            res["model_selection"].update(
                four_reason=sel4["reason"], F4=sel4["F"], p_value4=sel4["p_value"],
                rms_four=sel4.get("rms_four"))
        # The number of layers the readings actually support (F tests at the
        # 5 % level), whatever was requested.  A fourth layer is tested
        # against three; if three were not supported it is tested against
        # the two-layer fit directly (four extra parameters).
        supported = sel["chosen"]
        if sel4 is not None and sel4["four"] is not None and sel4["chosen"] == 4:
            if supported == 3:
                supported = 4
            else:
                n = len(sp)
                ss2 = (float(sel["rms_two"]) / 100.0) ** 2 * n
                F24, p24 = layered.f_test_nested(ss2, sel4["four"]["ss"], n, 3, 7)
                ok = (p24 is not None and p24 < 0.05
                      and sel4["four"]["rms_pct"] < 0.8 * float(sel["rms_two"]))
                if ok:
                    supported = 4
                res["model_selection"]["four_reason"] = (
                    sel4["reason"] + f" Against the two-layer fit the F test of "
                    f"the four extra parameters gives p = {p24:.2g}, so the four-"
                    f"layer model is {'supported' if ok else 'not supported'}.")
        res["model_selection"]["chosen"] = supported
        if sel4 is not None and sel4["four"] is not None and (
                sel4["chosen"] == 4 or layers == "4"):
            res = _three_layer_result(res, sel4["four"], layers)
            res["three_layer"] = dict(rho=three["rho"], h=three["h"],
                                      rms_pct=three["rms_pct"],
                                      curve_x=three["curve_x"], curve_y=three["curve_y"])
        elif use3:
            res = _three_layer_result(res, three, layers)
            if sel4 is not None and sel4["four"] is not None:
                f4 = sel4["four"]
                res["four_layer_alternative"] = dict(
                    rho=f4["rho"], h=f4["h"], rms_pct=f4["rms_pct"],
                    curve_x=f4["curve_x"], curve_y=f4["curve_y"])
        elif three is not None:
            res["three_layer_alternative"] = dict(
                rho=three["rho"], h=three["h"], rms_pct=three["rms_pct"],
                curve_x=three["curve_x"], curve_y=three["curve_y"])
    _flag_unsupported(res, sp, array)
    res["uniform_average"] = sum(rh) / len(rh)
    if array == "wenner" and min(sp) < 1.0:
        # The forward model treats the pins as points on the surface.  At short
        # spacings a driven pin reads high: 43 % at a = 0.3 m for 0.15 m pins
        # (IEEE Std 80-2013 Annex H, Table H.1 data).
        res["pin_depth_note"] = (
            "Spacings below about 1 m are sensitive to how deep the pins were "
            "driven, which the two-layer model ignores (it treats them as points "
            "on the surface). If the pins were driven more than a few "
            "centimetres, check the residuals at those spacings and consider "
            "refitting without them.")
    area = p.get("grid_area")
    area = float(area) if area not in (None, "", 0, "0") else None
    if res["n_layers"] >= 3:
        rr = [res["rho1"], res["rho2"], res["rho3"]] + ([res["rho4"]] if res.get("rho4") else [])
        hh = [res["h"], res["h2"]] + ([res["h3"]] if res.get("h3") else [])
        earth = layered.LayeredEarth(rr, hh)
        method = p.get("equivalent_method", "auto")
        depth = float(p.get("grid_depth", 0.5)) + float(p.get("rod_length", 0.0))
        if area and method in ("auto", "grid"):
            eq = layered.equivalent_uniform(earth, area)
            eq["note"] = (f"Grid-size rule on the {earth.N}-layer model: a disc of "
                          f"the grid's area (r = {eq['r_equiv']:.1f} m) has "
                          f"F = {eq['F']:.3f} times its resistance on uniform "
                          f"ρ₁, so ρ = ρ₁F (far field only). Preliminary: the "
                          f"grid page's Pull inputs recomputes it with the "
                          f"grid's buried length, and that value is the one to "
                          f"design with. Use the numerical solver, which takes "
                          f"the layers directly, for the final design.")
            eq["penetration"] = depth
        elif method == "grid":
            raise ValueError("The grid-size rule needs the grid area (m²).")
        else:
            eq = layered.equivalent_simple(earth, depth, method)
        res["equivalent"] = eq
        return res
    res["equivalent"] = soil.equivalent_uniform(
        res["rho1"], res["rho2"], res["h"],
        float(p.get("grid_depth", 0.5)), float(p.get("rod_length", 0.0)),
        p.get("equivalent_method", "auto"), area)
    if area:
        res["equivalent"]["note"] = (str(res["equivalent"].get("note") or "") +
            " Preliminary: computed from the grid area alone. The grid page's "
            "Pull inputs recomputes it with the actual grid, including its "
            "buried conductor length, and that value is the one to design with.").strip()
    return res


def depth_of_investigation(spacings, array: str = "wenner") -> dict:
    """Median depth of investigation of the longest spread (Edwards, 1977):
    0.52·a for Wenner, 0.19·AB = 0.38·s for Schlumberger.  The readings
    carry little information about anything deeper than about twice that,
    so a layer whose top lies below ``reach`` is an extrapolation."""
    smax = max(spacings)
    k = 0.38 if array == "schlumberger" else 0.52
    doi = k * smax
    return dict(doi=doi, reach=2.0 * doi, factor=k, spacing_max=smax)


def _flag_unsupported(res: dict, sp, array: str) -> None:
    """Mark what the readings do not support: layers beyond the number the
    F tests accept, layers whose resistivity or top is unresolved, and layers
    that start below the reach of the traverse.  Adds ``layer_status``,
    ``depth_of_investigation`` and, when needed, ``model_warning``."""
    n = int(res.get("n_layers") or 2)
    di = depth_of_investigation(sp, array)
    res["depth_of_investigation"] = di
    U = res.get("uncertainty") or {}
    bound = list(res.get("at_bound") or [])
    def fac(k):
        u = U.get(k) or {}
        if u.get("factor") is not None:
            return float(u["factor"])
        lo, hi = u.get("low_68"), u.get("high_68")
        return math.sqrt(hi / lo) if lo and hi and lo > 0 else 1.0
    rho_k = ["rho1", "rho2", "rho3", "rho4"][:n]
    h_k = (["h", "h2", "h3"])[:n - 1]
    names = rho_k + h_k
    hit = lambda k: bool(bound) and bound[names.index(k)]
    depths = list(res.get("depths") or ([res["h"]] if res.get("h") else []))
    r1 = not (fac("rho1") >= 20 or hit("rho1"))
    status = [dict(layer=1, top=0.0, resolved=r1, rho_resolved=r1,
                   top_resolved=True, below_reach=False)]
    for i in range(2, n + 1):
        top = float(depths[i - 2]) if len(depths) >= i - 1 else None
        rk, hk = rho_k[i - 1], h_k[i - 2]
        r_ok = not (fac(rk) >= 20 or hit(rk))
        t_ok = not (fac(hk) >= 20 or hit(hk))
        status.append(dict(layer=i, top=top, resolved=r_ok and t_ok,
                           rho_resolved=r_ok, top_resolved=t_ok,
                           below_reach=bool(top is not None and top > di["reach"])))
    res["layer_status"] = status
    ms = res.get("model_selection")
    sup = ms.get("chosen") if ms else n
    bad = [s for s in status if not s["resolved"] or s["below_reach"]]
    parts = []
    if ms and sup is not None and n > sup:
        if sup == 2:
            t = res.get("two_layer") or res
            alt = (f"ρ₁ ≈ {t['rho1']:.0f} Ω·m to {t['h']:.2f} m over "
                   f"ρ₂ ≈ {t['rho2']:.0f} Ω·m")
        else:
            t = res.get("three_layer") or {}
            r_, h_ = t.get("rho") or [], t.get("h") or []
            alt = (f"ρ = {' / '.join(f'{v:.0f}' for v in r_)} Ω·m with "
                   f"thicknesses {' / '.join(f'{v:.2f}' for v in h_)} m"
                   if r_ else "")
        names_n = {2: "two", 3: "three", 4: "four"}
        pv = [("third", ms.get("p_value")), ("fourth", ms.get("p_value4"))][:n - 2]
        pv = ", ".join(f"p = {v:.2g} for the {w} layer" for w, v in pv if v is not None)
        parts.append(
            f"The readings do not support a {names_n[n]}-layer model: the "
            f"extra layers do not improve the fit significantly (F test at "
            f"the 5 % level{': ' + pv if pv else ''}), so the "
            f"supported model is {names_n[sup]} layers"
            + (f" ({alt})" if alt else "") + ". The model below is shown "
            f"because {names_n[n]} layers were requested; its extra layers "
            f"are one of many that fit equally well.")
    if bad:
        desc = []
        for s_ in bad:
            if s_["below_reach"]:
                desc.append(f"layer {s_['layer']} starts at {s_['top']:.0f} m, "
                            f"below the reach of the traverse (about "
                            f"{di['reach']:.0f} m for a longest spacing of "
                            f"{di['spacing_max']:g} m)")
            else:
                what = ("neither its resistivity nor the depth of its top"
                        if not s_["rho_resolved"] and not s_["top_resolved"] else
                        "its resistivity" if not s_["rho_resolved"] else
                        "the depth of its top")
                desc.append(f"layer {s_['layer']} is not resolved: the "
                            f"readings do not fix {what}")
        parts.append("In this model " + "; ".join(desc) + ".")
    if parts:
        parts.append("Design with the supported model, or confirm the deeper "
                     "layers independently (a longer traverse, a borehole "
                     "log) first: a layer that is not really there changes "
                     "the computed grid resistance and GPR, and a spurious "
                     "conductive one makes them too low, which is unsafe.")
        res["model_warning"] = " ".join(parts)
    else:
        res["model_warning"] = ""


def _three_layer_result(two: dict, three: dict, requested: str) -> dict:
    """Recast a three-layer fit in the soil page's result layout, keeping the
    two-layer fit alongside for comparison."""
    rho, h = three["rho"], three["h"]
    unc = three.get("uncertainty") or {}
    par = unc.get("params", {})
    rename = {"rho1": "rho1", "rho2": "rho2", "rho3": "rho3", "rho4": "rho4",
              "h1": "h", "h2": "h2", "h3": "h3"}
    u = {rename[k]: v for k, v in par.items()} if par else None
    if u is not None:
        u.update(dof=unc.get("dof"), corr=unc.get("corr"), names=unc.get("names"),
                 equivalence=unc.get("equivalence"),
                 equivalences=unc.get("equivalences"))
    worst = max(abs(r) for r in three["residual_pct"])
    rms = three["rms_pct"]
    q = ("good" if (rms <= 3.0 and worst <= 6.0) else
         "acceptable" if (rms <= 5.0 and worst <= 10.0) else "poor")
    warn = note = ""
    if q == "poor":
        nl = len(rho)
        warn = (f"Even the {'three' if nl == 3 else 'four'}-layer model leaves an "
                f"RMS misfit of {rms:.1f} % (largest residual {worst:.0f} %). "
                f"Check the readings for outliers or lateral changes along the "
                f"traverse; a second traverse at right angles may be needed.")
    eqs = (u or {}).get("equivalences") or [(u or {}).get("equivalence") or {}]
    def _poor(e):
        # every statement except "resolved separately" carries a caution
        return e and e.get("statement") and (
            e.get("determined") != "both" or e.get("unresolved")
            or e.get("rho2_factor", 1) >= 3 or e.get("h2_factor", 1) >= 3)
    note = " ".join(e["statement"] for e in eqs if _poor(e))
    out = dict(two)
    out.update(
        n_layers=len(rho), rho1=rho[0], rho2=rho[1], rho3=rho[2], h=h[0], h2=h[1],
        depths=three["depths"], K=three["K"][0], K23=three["K"][1],
        rho4=rho[3] if len(rho) > 3 else None, h3=h[2] if len(h) > 2 else None,
        K34=three["K"][2] if len(rho) > 3 else None,
        rms_pct=rms, fitted=three["fitted"], residual_pct=three["residual_pct"],
        curve_x=three["curve_x"], curve_y=three["curve_y"],
        uncertainty=u, fit_quality=q, max_residual_pct=worst,
        three_layer_suspected=False, fit_warning=warn, fit_note=note,
        at_bound=three.get("at_bound"),
        two_layer=dict(rho1=two["rho1"], rho2=two["rho2"], h=two["h"], K=two["K"],
                       rms_pct=two["rms_pct"], fitted=two["fitted"],
                       residual_pct=two["residual_pct"],
                       curve_x=two["curve_x"], curve_y=two["curve_y"],
                       fit_quality=two.get("fit_quality")))
    if any(three.get("at_bound") or []):
        nl = len(rho)
        names = ["ρ₁", "ρ₂", "ρ₃", "ρ₄"][:nl] + ["h₁", "h₂", "h₃"][:nl - 1]
        hit = [names[i] for i, b in enumerate(three["at_bound"]) if b]
        out["fit_note"] = (out["fit_note"] + " " if out["fit_note"] else "") + (
            f"{', '.join(hit)} reached the edge of the search range: the "
            f"readings do not constrain {'it' if len(hit) == 1 else 'them'} — "
            f"extend the traverse (longer or shorter spacings) to resolve it.")
    return out


def api_soil_equivalent(p):
    """Equivalent uniform resistivity for a specific grid.

    Called by the grid page's "Pull inputs" so that the two-layer model is
    collapsed with the grid it will actually be used for (area and total
    buried length), not with a depth that ignores the grid's size.
    """
    _require_positive(p, {"rho1": "Upper-layer resistivity rho1 (ohm.m)",
                          "rho2": "Lower-layer resistivity rho2 (ohm.m)",
                          "h": "Upper-layer thickness h (m)"})
    g = ieee80.GridGeometry(
        Lx=float(p.get("Lx", 70)), Ly=float(p.get("Ly", 70)),
        D=float(p.get("D", 7)), h=float(p.get("h_grid", 0.5)),
        n_rods=int(p.get("n_rods", 0) or 0), Lr=float(p.get("Lr", 0) or 0))
    method = p.get("equivalent_method", "auto")
    if method == "auto":
        method = "grid"
    if p.get("rho3") not in (None, "") or p.get("h2") not in (None, ""):
        _require_positive(p, {"rho3": "Third-layer resistivity rho3 (ohm.m)",
                              "h2": "Second-layer thickness h2 (m)"})
        rr = [float(p["rho1"]), float(p["rho2"]), float(p["rho3"])]
        hh = [float(p["h"]), float(p["h2"])]
        if p.get("rho4") not in (None, "") and p.get("h3") not in (None, ""):
            _require_positive(p, {"rho4": "Fourth-layer resistivity rho4 (ohm.m)",
                                  "h3": "Third-layer thickness h3 (m)"})
            rr.append(float(p["rho4"]))
            hh.append(float(p["h3"]))
        earth = layered.LayeredEarth(rr, hh)
        if method != "grid":
            return layered.equivalent_simple(earth, g.h, method)
        eq = layered.equivalent_uniform(earth, g.A, g.LT)
        two = layered.equivalent_two_layer(earth, g.A, g.h)
        eq["equivalent_two_layer"] = two
        eq["note"] = (
            f"Grid-size rule on the {earth.N}-layer model: the grid is treated as a "
            f"disc of radius r = √(A/π) = {eq['r_equiv']:.1f} m, F = "
            f"{eq['F']:.3f}, and the conductor term ρ₁/L_T stays in the top "
            f"layer, so ρ = ρ₁ (F/4r + 1/L_T)/(1/4r + 1/L_T) = ρ₁ × "
            f"{eq['ratio']:.3f}. For this grid the {earth.N} layers act like two: "
            f"ρ₁ = {two['rho1']:.4g} Ω·m to {two['h']:.3g} m over "
            f"{two['rho2']:.4g} Ω·m. Use the numerical solver, which takes the "
            f"layers directly, for the final design.")
        return eq
    return soil.equivalent_uniform(
        float(p["rho1"]), float(p["rho2"]), float(p["h"]),
        g.h, 0.0, method, g.A, g.LT)


def api_fault(p):
    _require_positive(p, {"Un_kV": "Nominal voltage Un (kV)",
                          "tf": "Fault duration tf (s)",
                          "ts": "Shock duration ts (s)",
                          "frequency": "Frequency (Hz)"})

    Un = float(p.get("Un_kV", 20.0))
    c = float(p.get("c", 1.1))
    mode = _require_choice(p.get("mode", "impedance"),
                           {"impedance", "source", "direct"}, "Fault input mode")
    _require_positive(p, {k: v for k, v in (("Sf", "Split factor S_f"),
                                            ("Cp", "Growth factor C_p"))
                          if p.get(k) not in (None, "")})
    if p.get("Sf") not in (None, "") and float(p["Sf"]) > 1.0:
        raise ValueError("Split factor S_f cannot exceed 1.")
    if mode == "source":
        _require_positive(p, {"Sk_MVA": "Source short-circuit power S_k (MVA)"})
    if mode == "direct":
        # 3I0 entered directly: no sequence impedances are used or shown
        # (up to 1.3.4 the hidden Z fields were still evaluated).
        _require_positive(p, {"three_I0_kA": "Earth-fault current 3I0 (kA)"})
        three_I0 = float(p["three_I0_kA"])
        tf = float(p.get("tf", 0.5))
        f = float(p.get("frequency", 50.0))
        xr = float(p.get("xr_ratio") or 10.0)
        dfd = faultcurrent.decrement_factor(tf, xr, f)
        Sf = float(p.get("Sf", 1.0))
        sfd = dict(Sf=Sf, note="User-specified split factor.")
        gc = faultcurrent.grid_current(three_I0, Sf, dfd["Df"], float(p.get("Cp", 1.0)))
        th = faultcurrent.thermal_equivalent(three_I0, tf, xr, f)
        return dict(Un_kV=Un, line_to_earth=None, three_phase=None,
                    decrement=dfd, split=sfd, grid=gc, thermal=th,
                    ts=float(p.get("ts", tf)), tc=float(p.get("tc", tf)), tf=tf,
                    three_I0_kA=three_I0, Sf=Sf, Df=dfd["Df"],
                    Cp=float(p.get("Cp", 1.0)), mode="direct",
                    Ig_kA=gc["Ig_kA"], IG_kA=gc["IG_kA"])

    if mode == "source":
        Z1 = faultcurrent.grid_source_impedance(
            Un, float(p.get("Sk_MVA", 500.0)), float(p.get("xr_source", 10.0)), c)
        if p.get("transformer"):
            tr = p["transformer"]
            Z1 = Z1 + faultcurrent.transformer_impedance(
                float(tr.get("Sr_MVA", 10)), Un, float(tr.get("ukr_pct", 10)),
                tr.get("urr_pct"), tr.get("pk_kW"))
        Z2 = Z1
        Z0 = complex(float(p.get("R0_factor", 1.0)) * Z1.real,
                     float(p.get("X0_factor", 3.0)) * Z1.imag)
    else:
        Z1 = _cplx(p.get("Z1"))
        Z2 = _cplx(p.get("Z2")) or Z1
        Z0 = _cplx(p.get("Z0"))

    Zf = _cplx(p.get("Zf"))
    lg = faultcurrent.line_to_earth_fault(Un, Z1, Z2, Z0, Zf, c)
    tp = faultcurrent.three_phase_fault(Un, Z1, c)

    tf = float(p.get("tf", 0.5))
    # X/R of the earth-fault loop.  A computed 0 (purely resistive loop) is a
    # real value, not a missing one, so it must not fall through to 10.
    if p.get("xr_ratio") not in (None, "", 0, "0"):
        xr = float(p["xr_ratio"])
    elif lg.get("xr_ratio") is not None:
        xr = float(lg["xr_ratio"])
    else:
        xr = 10.0
    f = float(p.get("frequency", 50.0))
    dfd = faultcurrent.decrement_factor(tf, xr, f)

    if p.get("Z_return") not in (None, "", 0):
        sfd = faultcurrent.split_factor_simple(float(p.get("Rg_estimate", 1.0)),
                                               _cplx(p.get("Z_return")))
        Sf = sfd["Sf"]
    else:
        Sf = float(p.get("Sf", 1.0))
        sfd = dict(Sf=Sf, note="User-specified split factor.")

    three_I0 = float(p.get("three_I0_kA") or lg["three_I0_kA"])
    gc = faultcurrent.grid_current(three_I0, Sf, dfd["Df"], float(p.get("Cp", 1.0)))
    th = faultcurrent.thermal_equivalent(three_I0, tf, xr, f)

    return dict(Un_kV=Un, line_to_earth=lg, three_phase=tp, decrement=dfd,
                split=sfd, grid=gc, thermal=th, ts=float(p.get("ts", tf)),
                tc=float(p.get("tc", tf)), tf=tf,
                three_I0_kA=three_I0, Sf=Sf, Df=dfd["Df"],
                Cp=float(p.get("Cp", 1.0)),
                Ig_kA=gc["Ig_kA"], IG_kA=gc["IG_kA"])


def api_conductor(p):
    _require_positive(p, {"I_kA": "Fault current through the conductor (kA)",
                          "tc": "Duration tc (s)"})

    out = {}
    if p.get("standard", "ieee80") == "ieee80":
        Tm = p.get("Tm")
        if p.get("joint") and p["joint"] in materials.JOINT_TM_LIMITS:
            # A joint can only LOWER the permissible temperature: it can never
            # let the conductor run hotter than its own fusing point.  Taking
            # the joint limit as-is put Tm = 1083 degC on aluminium (657) and
            # zinc-coated steel (419) with an exothermic weld, and 450 degC on
            # zinc-coated steel with a brazed joint — areas up to 27 % too small.
            mat_tm = materials.IEEE80_MATERIALS.get(
                p.get("material", "cu_hard"), {}).get("Tm", float("inf"))
            Tm = min(materials.JOINT_TM_LIMITS[p["joint"]], mat_tm)
        r = conductor.ieee80_conductor_area(
            float(p.get("I_kA", 10.0)) * float(p.get("Df", 1.0)),
            float(p.get("tc", 0.5)), p.get("material", "cu_hard"),
            float(p.get("Ta", 40.0)), Tm)
        r["Df"] = float(p.get("Df", 1.0))
        out["ieee80"] = r
    out["iec"] = conductor.adiabatic_area(
        float(p.get("I_kA", 10.0)) * 1000.0, float(p.get("tc", 0.5)),
        p.get("iec_material", "copper"), p.get("insulation", "bare"),
        p.get("installation", "buried" if p.get("buried", True) else "separate"))
    # IEC 60364-5-54 / BS 7671 Table 54.1: "protected against corrosion"
    # means a sheath.  A bare conductor buried in soil is NOT protected, so
    # its floor is 25 mm2 copper / 50 mm2 steel.  Up to 1.3.4 the default was
    # "corrosion protected" (16 mm2) even for the default bare buried
    # conductor, which contradicted the table (see docs/THEORY.md §4.4).
    bare_buried = (p.get("insulation", "bare") == "bare" and
                   p.get("installation", "buried" if p.get("buried", True)
                         else "separate") == "buried")
    corr = p.get("corrosion_protected")
    corr = (not bare_buried) if corr is None else bool(corr)
    out["min_buried"] = conductor.min_buried_earthing_conductor(
        corr, bool(p.get("mechanically_protected", False)),
        bool(p.get("lps_connected", False)))
    if corr and bare_buried:
        out.setdefault("warnings", []).append(
            "A bare conductor buried in soil is not protected against "
            "corrosion (BS 7671 Table 54.1 means protection by a sheath): its "
            "minimum is 25 mm² copper (50 mm² with a lightning protection "
            "system connected, IEC 60364-5-54:2011 Table 54.1) or 50 mm² steel "
            "(78.5 mm² hot-dip galvanized round wire to IEC 60364-5-54:2011), "
            "not 16 mm². Select 'Not protected against corrosion' unless the "
            "conductor is sheathed.")
    # Design basis (docs/THEORY.md §4).  'both' (default) selects the larger of
    # the IEEE 80 and IEC areas; 'ieee80' sizes an HV grid to IEEE 80 alone,
    # where the joint temperature T_m is what the design relies on; 'iec'
    # sizes an LV protective/earthing conductor to IEC 60364-5-54 alone.
    basis = str(p.get("basis", "both")).lower()
    _require_choice(basis, {"both", "ieee80", "iec"}, "Design basis")
    if basis == "ieee80" and "ieee80" not in out:
        basis = "both"
    out["basis"] = basis
    if p.get("S_line_mm2"):
        out["pe"] = conductor.pe_from_line_conductor(float(p["S_line_mm2"]))
        out["bonding"] = conductor.bonding_conductors(out["pe"]["area_mm2"])
    chosen = out.get("ieee80", out["iec"])
    # A requirement larger than the biggest standard conductor comes back as
    # standard_mm2 = None.  Folding that into `or 0` used to hand the user the
    # 16 mm2 minimum for a duty needing over 1000 mm2 — a wrong answer that
    # looks like a right one.  Carry the requirement through instead and say
    # plainly that no single conductor covers it.
    # The thermal areas that enter the selection, according to the basis.
    therm = ([chosen] if basis == "ieee80" else
             [out["iec"]] if basis == "iec" else [chosen, out["iec"]])
    required = max((x.get("area_mm2") or 0.0) for x in therm)
    floor = (out["min_buried"]["copper_mm2"]
             if p.get("iec_material", "copper") == "copper"
             else out["min_buried"]["steel_mm2"])
    std = max((x.get("standard_mm2") or 0) for x in therm)
    if std <= 0 and required > 0:
        out["selected_mm2"] = None
        out["required_mm2"] = required
        out["off_scale"] = True
        out["note"] = (
            f"The duty needs {required:.0f} mm², which is larger than the "
            f"largest single conductor in the standard table "
            f"({materials.STD_AREAS_MM2[-1]:.0f} mm²). Use two or more "
            f"conductors in parallel, or reduce the fault duration.")
        out["diameter_m"] = materials.diameter_from_area(required) / 1000.0
        return out
    out["selected_mm2"] = max(std, floor)
    out["governs"] = ("Table 54.1 minimum" if floor >= std else
                      "IEEE 80" if basis == "ieee80" else
                      "IEC adiabatic" if basis == "iec" else
                      ("IEEE 80" if (chosen.get("standard_mm2") or 0) >=
                       (out["iec"].get("standard_mm2") or 0) else "IEC adiabatic"))
    out["off_scale"] = False
    out["diameter_m"] = materials.diameter_from_area(out["selected_mm2"]) / 1000.0
    return out


def _require_nonneg(p, spec):
    """spec: {key: label} — optional values that, if given, must be >= 0."""
    for key, label in spec.items():
        raw = p.get(key)
        if raw in (None, ""):
            continue
        try:
            v = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a number.")
        if not math.isfinite(v) or v < 0:
            raise ValueError(f"{label} cannot be negative.")


def _require_choice(value, allowed, label):
    """Unknown choices used to be replaced silently by a default (1.3.4)."""
    v = str(value)
    if v not in allowed and v.upper() not in allowed:
        raise ValueError(f"{label} must be one of {', '.join(sorted(allowed))} "
                         f"(got '{value}').")
    return v


def _require_grid(p):
    _require_positive(p, {
        "rho": "Soil resistivity (ohm.m)",
        "ts": "Shock duration (s)",
        "Lx": "Grid length Lx (m)",
        "Ly": "Grid width Ly (m)",
        "D": "Conductor spacing D (m)",
        "h": "Burial depth h (m)",
        "d": "Conductor diameter d (m)"})
    if float(p.get("n_rods", 0) or 0) > 0 and float(p.get("Lr", 0) or 0) <= 0:
        raise ValueError("Rod length Lr (m) must be greater than zero when "
                         "ground rods are included.")
    if float(p.get("D", 7)) > max(float(p.get("Lx", 70)), float(p.get("Ly", 70))):
        raise ValueError("Conductor spacing D (m) cannot be larger than the "
                         "grid itself.")
    _require_positive(p, {"IG_kA": "Maximum grid current I_G (kA)"})
    _require_nonneg(p, {"rho_s": "Surface-layer resistivity (ohm.m)",
                        "hs": "Surface-layer thickness (m)"})
    if p.get("body_weight") not in (None, ""):
        _require_choice(int(float(p["body_weight"])), {"50", "70"}, "Body weight (kg)")
    shape = str(p.get("shape", "rectangular") or "rectangular").lower()
    _require_choice(shape, {"rectangular", "square", "l", "t", "irregular"}, "Grid shape")
    if shape not in ("rectangular", "square"):
        # IEEE Std 80-2013 Eq. (91)-(93) and Example B.4 need the true area,
        # perimeter and conductor length.  Up to 1.3.4 an L or T grid was
        # computed as its bounding rectangle, which understated E_m by about
        # 24 % for Example B.4 (unsafe).
        _require_positive(p, {"A_m2": "Enclosed grid area A (m²) of the non-rectangular grid",
                              "Lp_m": "Peripheral length L_p (m) of the non-rectangular grid",
                              "Lc_m": "Total horizontal conductor length L_C (m) of the non-rectangular grid"})
        if float(p["A_m2"]) > float(p.get("Lx", 70)) * float(p.get("Ly", 70)) * (1 + 1e-9):
            raise ValueError("The enclosed area A cannot exceed Lx × Ly, the "
                             "maximum dimensions of the grid.")


def _geometry(p) -> ieee80.GridGeometry:
    return ieee80.GridGeometry(
        Lx=float(p.get("Lx", 70)), Ly=float(p.get("Ly", 70)),
        D=float(p.get("D", 7)), h=float(p.get("h", 0.5)),
        d=float(p.get("d", 0.01)), n_rods=int(p.get("n_rods", 0)),
        Lr=float(p.get("Lr", 0.0)), d_rod=float(p.get("d_rod", 0.016)),
        rods_on_perimeter=bool(p.get("rods_on_perimeter", True)),
        shape=p.get("shape", "rectangular"), Dm=float(p.get("Dm", 0.0) or 0.0),
        A_m2=float(p.get("A_m2", 0.0) or 0.0), Lp_m=float(p.get("Lp_m", 0.0) or 0.0),
        Lc_m=float(p.get("Lc_m", 0.0) or 0.0))


def api_ieee80(p):
    _require_grid(p)

    g = _geometry(p)
    res = ieee80.design(
        float(p.get("rho", 100.0)), g, float(p.get("IG_kA", 1.0)),
        float(p.get("rho_s", 3000.0)), float(p.get("hs", 0.1)),
        float(p.get("ts", 0.5)), int(p.get("body_weight", 70)),
        p.get("r_method", "auto"))
    res["layout"] = dict(conductors=g.conductor_paths(), rods=g.rod_positions(), outline=g.outline())
    nt = g.notch()
    if nt is not None:
        res["layout"]["notch"] = dict(a=nt[0], b=nt[1], area=nt[2], Lc=nt[3])
    return reasoning.explain_ieee80(res)


def api_ieee80_optimise(p):
    _require_grid(p)
    q = {"D_min": p.get("D_min", 1.5), "D_step": p.get("D_step", 0.5)}
    _require_positive(q, {"D_min": "Smallest spacing to try D_min (m)",
                          "D_step": "Spacing step (m)"})
    if (float(p.get("D", 7)) - float(q["D_min"])) / float(q["D_step"]) > 2000:
        raise ValueError("Spacing step too small: more than 2000 designs "
                         "would be evaluated.")

    g = _geometry(p)
    res = ieee80.optimise(
        float(p.get("rho", 100.0)), g, float(p.get("IG_kA", 1.0)),
        float(p.get("rho_s", 3000.0)), float(p.get("hs", 0.1)),
        float(p.get("ts", 0.5)), int(p.get("body_weight", 70)),
        float(p.get("D_min", 1.5)), float(p.get("D_step", 0.5)),
        bool(p.get("allow_rods", True)), int(p.get("max_rods", 200)),
        p.get("r_method", "auto"))
    if res.get("best"):
        best = res["best"]["result"]
        # Draw the geometry the optimiser actually evaluated: when it added
        # rods it put them on the perimeter (ieee80.optimise sets
        # rods_on_perimeter = True), whatever the request said.
        added = bool(res["best"].get("n_rods"))
        gg = _geometry({**p, "D": res["best"]["D"],
                        "n_rods": res["best"].get("n_rods", g.n_rods),
                        "Lr": (best["geometry"]["Lr"] if added else p.get("Lr", 0)),
                        "rods_on_perimeter": (True if added
                                              else p.get("rods_on_perimeter", True))})
        best["layout"] = dict(conductors=gg.conductor_paths(),
                              rods=gg.rod_positions(), outline=gg.outline())
        reasoning.explain_ieee80(best)
    return res


def _clean_fences(p):
    """Validate fence items and turn the table's 0/1 and blank entries into
    the booleans and None the solver expects."""
    for i, it in enumerate(p.get("items") or [], 1):
        if it.get("kind") != "fence":
            continue
        if "path" not in it:
            for k in ("Lx", "Ly"):
                if not _finite_pos(it.get(k)):
                    raise ValueError(f"Fence {i}: {k} must be a positive length (m).")
        for k, lab in (("post_spacing", "post spacing"), ("post_depth", "post depth"),
                       ("post_radius", "post radius")):
            if k in it and not _finite_pos(it.get(k)):
                raise ValueError(f"Fence {i}: the {lab} must be positive.")
        it["bonded"] = _truthy(it.get("bonded", 0))
        wo = it.get("wire_offset")
        wire = _truthy(it.get("wire", 1 if wo not in (None, "") else 0))
        try:
            wo = float(wo)
        except (TypeError, ValueError):
            wo = None
        if wire and (wo is None or not math.isfinite(wo)):
            raise ValueError(f"Fence {i}: give the offset of the fence wire "
                             f"from the fence line (m, positive outwards).")
        it["wire_offset"] = wo if wire else None
        it["wire"] = bool(wire)


def _finite_pos(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v) and v > 0


def _truthy(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    try:
        return bool(v) and not (isinstance(v, float) and math.isnan(v))
    except Exception:
        return False


def api_transfer(p):
    """Transferred potential along a pipe, rail, cable screen or earth wire
    that leaves the station (IEEE Std 80 clause 17.3)."""
    _require_rows(p.get("items"), "electrode")
    route = p.get("route") or {}
    for k, lab in (("length", "Route length (m)"), ("radius", "Conductor radius (m)")):
        if not _finite_pos(route.get(k)):
            raise ValueError(f"{lab} must be positive.")
    if not bem.HAVE_NUMPY:
        raise RuntimeError("The transferred-potential solver needs numpy.")
    _clean_fences(p)
    net = bem.build_network(p)
    net.discretise(float(p.get("segment_length", 2.5)),
                   int(p.get("max_segments", bem.MAX_SEGMENTS)),
                   grade_ends=_truthy(p.get("grade_ends", True)))
    sol = net.solve()
    L = float(route["length"])
    start = route.get("start") or [0.0, 0.0]
    if route.get("end"):
        e = route["end"]
        direction = [float(e[0]) - float(start[0]), float(e[1]) - float(start[1])]
    else:
        direction = route.get("direction") or [1.0, 0.0]
    if math.hypot(*direction[:2]) == 0:
        raise ValueError("The route needs a direction.")
    depth = float(route.get("depth", 1.0))
    path = route.get("path") or None
    if path:
        path = [[float(q[0]), float(q[1])] for q in path]
        if len(path) < 2:
            raise ValueError("A route path needs at least two points.")
        start = path[0]
    prof = transfer.soil_profile_from_network(net, start, direction, L, depth, path=path)
    # the route's own geometry, for induction from a faulted line of any shape
    route_at, _ = transfer._polyline(path or [
        [float(start[0]), float(start[1])],
        [float(start[0]) + float(direction[0]) / math.hypot(*direction[:2]) * L,
         float(start[1]) + float(direction[1]) / math.hypot(*direction[:2]) * L]], L)
    ind = route.get("induced")
    if ind and ind.get("line_path"):
        lp = ind["line_path"]
        if len(lp) < 2 or any(len(q) < 2 for q in lp):
            raise ValueError("The faulted line's route needs at least two x, y points.")
    lim = p.get("limits") or {}
    kind = route.get("kind", "bare")
    coupled = _truthy(route.get("coupled", True)) and kind in ("bare", "coated")
    if coupled and len(net.segments) + 400 > transfer.COUPLED_LIMIT:
        coupled = False
    if coupled:
        if kind == "coated" and (route.get("coating_res") in (None, "")
                                 or float(route.get("coating_res")) <= 0):
            raise ValueError("Give the coating specific resistance (ohm.m²).")
        res = transfer.transferred_potential_coupled(
            net, route_at=route_at, soil_profile=prof, length=L, kind=kind,
            rho_soil=float(route.get("rho_soil") or p.get("rho1", 100.0)),
            radius=float(route["radius"]), depth=depth,
            f=float(route.get("f", 50.0)), metal=route.get("metal", "steel"),
            wall=route.get("wall"), r_dc_per_km=route.get("r_dc_per_km"),
            coating_res=route.get("coating_res"), z_per_km=route.get("z_per_km"),
            near=route.get("near", "bonded"), R_bond=float(route.get("R_bond") or 0.0),
            far=route.get("far", "open"),
            R_far=(float(route["R_far"]) if route.get("R_far") not in (None, "") else None),
            E_touch=lim.get("E_touch"), access_points=route.get("access_points"),
            induced=route.get("induced"))
    else:
        res = transfer.transferred_potential(
            GPR=sol["GPR"], Rg=sol["Rg"], IG=sol["IG"], soil_profile=prof,
            length=L, kind=route.get("kind", "bare"),
            rho_soil=float(route.get("rho_soil") or p.get("rho1", 100.0)),
            radius=float(route["radius"]), depth=depth,
            f=float(route.get("f", 50.0)), metal=route.get("metal", "steel"),
            wall=route.get("wall"), r_dc_per_km=route.get("r_dc_per_km"),
            coating_res=route.get("coating_res"), leak_ohm_km=route.get("leak_ohm_km"),
            z_per_km=route.get("z_per_km"),
            near=route.get("near", "bonded"), R_bond=float(route.get("R_bond") or 0.0),
            far=route.get("far", "open"),
            R_far=(float(route["R_far"]) if route.get("R_far") not in (None, "") else None),
            E_touch=lim.get("E_touch"), access_points=route.get("access_points"),
            induced=route.get("induced"), route_at=route_at)
    # circuit-field check (1.9.2): station and route as one network of
    # conductors with their impedance and mutual inductance; the larger touch
    # voltage of the two models is the design value
    if coupled and _truthy(route.get("check", True)):
        why = None
        if route.get("near", "bonded") != "bonded" or float(route.get("R_bond") or 0) > 0:
            why = "the route is not bonded directly to the station"
        elif route.get("far", "open") != "open":
            why = "the route ends on an earth (the circuit-field model has no lumped resistor)"
        elif res.get("induced"):
            why = "induction from a faulted line is not in the circuit-field model"
        elif route.get("z_per_km") not in (None, ""):
            why = "the series impedance was given directly"
        if why:
            chk = dict(skipped=why)
        else:
            chk = transfer.circuit_field_check(
                p, route_at=route_at, length=L, depth=depth, radius=float(route["radius"]),
                kind=kind, coating_res=route.get("coating_res"),
                metal=route.get("metal", "steel"), wall=route.get("wall"),
                r_dc_per_km=route.get("r_dc_per_km"), f=float(route.get("f", 50.0)),
                access_points=route.get("access_points"),
                grid_metal=str(p.get("grid_metal", "copper")))
        res["circuit_field"] = chk
        if not chk.get("skipped"):
            for a, b in zip(res["access"], chk["access"]):
                a["touch_check"] = b["touch"]
                a["touch_design"] = max(a["touch"], b["touch"])
                if lim.get("E_touch"):
                    a["passed"] = bool(a["touch_design"] <= float(lim["E_touch"]))
            res["touch_max_design"] = max(res["touch_max"], chk["touch_max"])
            if lim.get("E_touch"):
                res["passed"] = all(a["passed"] for a in res["access"])
    res["station"] = dict(Rg=sol["Rg"], GPR=sol["GPR"], IG=sol["IG"],
                          soil=sol["soil"], segments=sol["segments"])
    if sol.get("networks"):
        res["station"]["networks"] = sol["networks"]
    res["route"] = dict(start=list(map(float, start[:2])),
                        direction=list(map(float, direction[:2])), depth=depth,
                        path=path)
    return reasoning.explain_transfer(res)


def api_hf(p):
    """Harmonic impedance and lightning response of the electrodes of the
    numerical page: uniform or layered soil (each layer constant or
    frequency dependent), optional soil ionisation, concrete-encased
    foundation elements."""
    _require_rows(p.get("items"), "electrode")
    if any(it.get("kind") == "fence" for it in p.get("items") or []):
        raise ValueError("Remove the fence: the lightning response is computed "
                         "for the electrode alone.")
    _require_positive(p, {"rho0": "Soil resistivity rho0 (ohm.m)"})
    eps = float(p.get("eps_r", 10.0))
    if not (1.0 <= eps <= 200.0):
        raise ValueError("Relative permittivity must lie between 1 and 200.")
    model = p.get("soil_model", "constant")
    _require_choice(model, {"constant", "alipio_visacro"}, "Soil model")
    level = p.get("level", "mean")
    _require_choice(level, {"mean", "relatively_conservative", "conservative"},
                    "Alipio-Visacro parameter set")
    f_max = float(p.get("f_max", 10e6))
    if not (1e5 <= f_max <= 2e7):
        raise ValueError("The highest frequency must lie between 100 kHz and 20 MHz.")
    if not hf.HAVE_NUMPY:
        raise RuntimeError("The frequency-response solver needs numpy.")
    feed = p.get("feed")
    if feed is not None:
        feed = [float(v) for v in feed][:3]
        if len(feed) == 2:
            feed.append(0.0)
    peaks = {k: float(v) for k, v in (p.get("peaks") or {}).items() if v not in (None, "")}
    wfs = p.get("waveforms") or ["first_tb781", "subsequent_tb781"]
    for w in wfs:
        _require_choice(w, set(hf.WAVEFORMS), "Lightning current")
    layers = None
    lay = p.get("layers") or {}
    if lay.get("rho"):
        rl = [float(v) for v in lay["rho"]]
        hl = [float(v) for v in lay.get("h") or []]
        if len(hl) != len(rl):
            raise ValueError("Every layer below the top one needs the thickness "
                             "of the layer above it.")
        if min(rl) <= 0 or min(hl) <= 0:
            raise ValueError("Layer resistivities and thicknesses must be positive.")
        if len(rl) > 3:
            raise ValueError("The lightning model takes at most four layers.")
        layers = dict(rho=rl, h=hl)
    E0 = p.get("E0")
    if E0 not in (None, "", 0, False):
        E0 = float(E0)
        if not (50.0 <= E0 <= 3000.0):
            raise ValueError("The critical field E0 must lie between 50 and 3000 kV/m "
                             "(300 kV/m IEEE, 400 kV/m CIGRE).")
    else:
        E0 = None
    out = hf.analyse(p["items"], float(p["rho0"]), eps, model, level, feed,
                     f_max, int(p.get("n_f", 40)), peaks,
                     int(p.get("max_segments", 800)), waveforms=tuple(wfs),
                     layers=layers, E0=E0)
    return reasoning.explain_hf(out)


def api_bem(p):
    _require_rows(p.get("items"), "electrode")
    _require_positive(p, {"segment_length": "Segment length (m)",
                          "rho1": "Upper-layer resistivity rho1 (ohm.m)"})
    # A second layer is used only when both rho2 and its depth are given
    # (bem.SoilModel treats a blank or zero as uniform soil), so validate
    # them together: a zero or negative value must not silently fall back to
    # a uniform model, nor give negative resistances.
    if p.get("rho2") not in (None, "") or p.get("h_layer") not in (None, ""):
        _require_positive(p, {"rho2": "Lower-layer resistivity rho2 (ohm.m)",
                              "h_layer": "Upper-layer thickness (m)"})
    if p.get("rho3") not in (None, "") or p.get("h_layer2") not in (None, ""):
        if p.get("rho2") in (None, "") or p.get("h_layer") in (None, ""):
            raise ValueError("A third layer needs the second layer first: give "
                             "ρ₂ and the top-layer thickness as well.")
        _require_positive(p, {"rho3": "Third-layer resistivity rho3 (ohm.m)",
                              "h_layer2": "Second-layer thickness (m)"})
    if p.get("rho4") not in (None, "") or p.get("h_layer3") not in (None, ""):
        if p.get("rho3") in (None, "") or p.get("h_layer2") in (None, ""):
            raise ValueError("A fourth layer needs the third layer first: give "
                             "ρ₃ and the second-layer thickness as well.")
        _require_positive(p, {"rho4": "Fourth-layer resistivity rho4 (ohm.m)",
                              "h_layer3": "Third-layer thickness (m)"})

    _require_vertical(p)
    if not bem.HAVE_NUMPY:
        raise RuntimeError("The numerical solver needs numpy. "
                           "Install it with:  pip install numpy")
    _clean_fences(p)
    key = governing.model_key(p)
    net = bem.build_network(p)
    zones = _zones(p.get("zones"))
    seg = net.discretise(float(p.get("segment_length", 2.5)),
                         int(p.get("max_segments", bem.MAX_SEGMENTS)),
                         grade_ends=_truthy(p.get("grade_ends", True)))
    sol = net.solve()

    xs = [c for it in net.raw for c in (it[0][0], it[1][0])]
    ys = [c for it in net.raw for c in (it[0][1], it[1][1])]
    pad = float(p.get("margin", 10.0))
    xlim = p.get("xlim") or [min(xs) - pad, max(xs) + pad]
    ylim = p.get("ylim") or [min(ys) - pad, max(ys) + pad]
    nx = int(p.get("nx", 61))
    ny = int(p.get("ny", 61))

    wsa = dict(xlim=xlim, ylim=ylim, nx=nx, ny=ny, step=float(p.get("step_distance", 1.0)),
               touch_box=p.get("touch_box"), touch_margin=float(p.get("touch_margin", 1.0)),
               zones=zones)
    refinement = None
    if p.get("auto_refine") not in (None, "", False, 0, "0"):
        tol = float(p.get("auto_refine"))
        if not 0.05 <= tol <= 10:
            raise ValueError("The refinement tolerance must be between 0.05 % and 10 %.")
        sol, ws, refinement = net.auto_refine(wsa, tol / 100.0,
                                              int(p.get("refine_levels", 4)),
                                              int(p.get("max_segments", bem.MAX_SEGMENTS)))
        seg = len(net.segments)
    else:
        ws = net.worst_touch_step(**wsa)
    prof = net.profile(p.get("profile_start", [xlim[0], (ylim[0] + ylim[1]) / 2]),
                       p.get("profile_end", [xlim[1], (ylim[0] + ylim[1]) / 2]),
                       int(p.get("profile_points", 240)),
                       step=float(p.get("step_distance", 1.0)))

    probes = list(p.get("probes") or [])
    if not probes:
        # default probes: corner-mesh centre and grid centre of the first grid
        for it in p.get("items", []):
            if it.get("kind") == "grid":
                x0, y0 = float(it.get("x0", 0)), float(it.get("y0", 0))
                D = float(it["D"])
                probes = [
                    dict(x=x0 + D / 2, y=y0 + D / 2, label="Corner mesh centre"),
                    dict(x=x0 + float(it["Lx"]) / 2, y=y0 + float(it["Ly"]) / 2,
                         label="Grid centre"),
                    dict(x=x0 - 1.0, y=y0 - 1.0, label="1 m outside the corner"),
                ]
                break
    if probes:
        pts = [[float(q["x"]), float(q["y"]), 0.0] for q in probes]
        vals = net.potential_at(pts)
        for q, v in zip(probes, vals):
            q["V"] = float(v)
            q["touch"] = float(net.V - v)

    out = dict(sol)
    out["solver_text"] = bem.describe_solver(sol.get("solver"))
    if refinement:
        out["refinement"] = refinement
    if net.soil.vertical:
        v = net.soil.vertical
        out["soil_boundary"] = dict(x=v["x"], y=v["y"], angle=v["angle"], rho=v["rho"])
    out.update(model_key=key, segments=seg, surface=ws["surface"], probes=probes,
               touch_box=ws.get("touch_box"),
               touch_max=ws["touch_max"], touch_at=ws["touch_at"],
               step_max=ws["step_max"], step_at=ws["step_at"],
               step_direction_deg=ws.get("step_direction_deg"),
               touch_region=ws.get("touch_region"), zones=ws.get("zones"),
               graded=bool(getattr(net, "graded", False)),
               profile=prof, geometry=net.geometry_json(),
               current=net.current_distribution(), xlim=xlim, ylim=ylim)
    if ws.get("fences"):
        out["fences"] = ws["fences"]
    warnings = []
    if getattr(net, "coarsened", None):
        c = net.coarsened
        warnings.append(
            f"The model has more conductor than {c['max_segments']} segments of "
            f"{c['requested']:g} m allow, so the segments were lengthened to "
            f"{c['used']:.2f} m. Accuracy falls with segment length: run the convergence "
            f"check, or raise the segment limit.")
    if getattr(net, "thick", None):
        warnings.append(bem.thick_warning(net.thick))
    if warnings:
        out["warnings"] = warnings

    lim = p.get("limits") or {}
    if lim.get("E_touch") or lim.get("E_step"):
        out["checks"] = [
            dict(name="Maximum touch voltage", value=ws["touch_max"],
                 limit=lim.get("E_touch"), unit="V",
                 passed=(lim.get("E_touch") or 1e18) >= ws["touch_max"]),
            dict(name="Maximum step voltage", value=ws["step_max"],
                 limit=lim.get("E_step"), unit="V",
                 passed=(lim.get("E_step") or 1e18) >= ws["step_max"]),
        ]
        for z in ws.get("zones") or []:
            zl = z.get("limit") or lim.get("E_touch")
            out["checks"].append(dict(
                name=f"Touch voltage at {z['name']}", value=z["touch_max"],
                limit=zl, unit="V", passed=(zl or 1e18) >= z["touch_max"], zone=z))
        for f in ws.get("fences") or []:
            v = abs(f["touch_max"])
            out["checks"].append(dict(
                name=f"Fence touch voltage ({f['name']})", value=v,
                limit=lim.get("E_touch"), unit="V",
                passed=(lim.get("E_touch") or 1e18) >= v,
                fence=f))
    return reasoning.explain_bem(out)


def _zones(zs):
    """Touch zones from the page: list of dict(name, x0, y0, x1, y1[, limit])."""
    out = []
    for i, z in enumerate(zs or [], 1):
        try:
            q = dict(name=str(z.get("name") or f"Zone {i}"),
                     x0=float(z["x0"]), y0=float(z["y0"]),
                     x1=float(z["x1"]), y1=float(z["y1"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Touch zone {i}: give x0, y0, x1 and y1 in metres.")
        if z.get("limit") not in (None, ""):
            q["limit"] = float(z["limit"])
        out.append(q)
    return out


def _require_vertical(p):
    """A vertical soil boundary (1.8.7): ρ' positive, uniform soil each side."""
    if p.get("rho_v") in (None, ""):
        return False
    _require_positive(p, {"rho_v": "Resistivity beyond the vertical boundary ρ' (ohm.m)"})
    for k, lab in (("x_v", "Boundary point x"), ("y_v", "Boundary point y"),
                   ("angle_v", "Boundary normal angle")):
        v = p.get(k)
        if v not in (None, ""):
            try:
                ok = math.isfinite(float(v))
            except (TypeError, ValueError):
                ok = False
            if not ok:
                raise ValueError(f"{lab} must be a number.")
    if p.get("rho2") not in (None, "") and p.get("h_layer") not in (None, ""):
        raise ValueError("A vertical soil boundary is solved with uniform soil on each side: "
                         "clear the lower layers, or the boundary.")
    return True


def _no_vertical(p, what):
    if p.get("rho_v") not in (None, ""):
        raise ValueError(f"The {what} is computed for horizontally layered soil only: "
                         "clear the vertical soil boundary to run it.")


def _bem_prepare(p):
    """Validation shared by the numerical-study endpoints."""
    _require_rows(p.get("items"), "electrode")
    _require_positive(p, {"rho1": "Upper layer resistivity rho1 (ohm.m)"})
    _require_vertical(p)
    if not bem.HAVE_NUMPY:
        raise RuntimeError("The numerical solver needs numpy. Install it with:  pip install numpy")
    _clean_fences(p)
    p["zones"] = _zones(p.get("zones"))
    p["_model_key"] = governing.model_key(p)
    return p


def _keyed(p, result):
    """Stamp a study result with the model it solved (see governing.py)."""
    result["model_key"] = p.get("_model_key")
    return result


def api_bem_convergence(p):
    """Discretisation error of the numerical solution (1.8.0)."""
    _bem_prepare(p)
    return _keyed(p, studies.convergence(p))


def api_bem_seasonal(p):
    """The same electrodes under a dry and a frozen top layer (1.8.0)."""
    _bem_prepare(p)
    _no_vertical(p, "seasonal study")
    return _keyed(p, studies.seasonal(p))


def api_bem_montecarlo(p):
    """Soil-model uncertainty carried through to R_g, touch and step (1.8.0)."""
    _bem_prepare(p)
    _no_vertical(p, "soil-uncertainty study")
    fit = p.get("soil_fit")
    if not fit:
        raise ValueError("Fit the soil model on page 1 first: the uncertainty comes from it.")
    n = int(p.get("samples", 24))
    if not 4 <= n <= 400:
        raise ValueError("Use between 4 and 400 samples.")
    method = str(p.get("sampling", "lhs"))
    if method not in ("lhs", "random"):
        raise ValueError("Sampling must be 'lhs' (Latin hypercube) or 'random'.")
    return _keyed(p, studies.monte_carlo(p, fit, n, int(p.get("seed", 1)), method))


def api_bem_powerfreq(p):
    """Power-frequency solution with the conductors' own impedance (1.8.0)."""
    _bem_prepare(p)
    _no_vertical(p, "power-frequency (non-equipotential) solution")
    for fd in p.get("feeds") or []:
        for k in ("x", "y"):
            if fd.get(k) in (None, ""):
                raise ValueError("Every injection point needs x and y.")
    return _keyed(p, powerfreq.analyse(p))


def api_bem_governing(p):
    """Governing touch, step, R_g and GPR: the plain numerical solution
    combined with every study run on the same model (1.8.2)."""
    b = p.get("bem")
    if not b:
        raise ValueError("Run the numerical solution first.")
    out = governing.governing(b, p.get("studies") or {}, p.get("limits"))
    return reasoning.explain_governing(out)


def _dxf_source(p):
    """The drawing: ASCII DXF text, or the file's bytes in base64 (binary DXF, 1.9.5)."""
    if p.get("data_b64"):
        import base64
        try:
            return base64.b64decode(str(p["data_b64"]), validate=True)
        except ValueError:
            raise ValueError("The drawing could not be read (bad base64 data).") from None
    return str(p.get("text") or "")


def api_dxf_inspect(p):
    """Layers of a DXF site drawing and what they hold (1.8.4)."""
    return dxfimport.inspect(_dxf_source(p))


def api_dxf_import(p):
    """Electrode items from the layers of a DXF drawing (1.8.4)."""
    mapping = p.get("mapping") or {}
    if not any(v != "ignore" for v in mapping.values()):
        raise ValueError("Mark at least one layer as conductor, rod or fence.")
    for k, lab in (("depth", "Burial depth"), ("conductor_radius", "Conductor radius"),
                   ("rod_length", "Rod length"), ("rod_radius", "Rod radius")):
        if k in p and not _finite_pos(p.get(k)):
            raise ValueError(f"{lab} must be positive.")
    sc = p.get("scale")
    if sc not in (None, "") and not _finite_pos(sc):
        raise ValueError("The scale (metres per drawing unit) must be positive.")
    return dxfimport.to_items(
        _dxf_source(p), mapping, depth=float(p.get("depth", 0.6)),
        conductor_radius=float(p.get("conductor_radius", 0.005)),
        rod_length=float(p.get("rod_length", 3.0)), rod_radius=float(p.get("rod_radius", 0.008)),
        scale=float(sc) if sc not in (None, "") else None,
        to_origin=_truthy(p.get("to_origin", True)), fence=p.get("fence") or {})


def api_bem_optimise(p):
    """Cheapest grid meeting the touch and step limits, by the numerical solver (1.8.0)."""
    _require_positive(p, {"rho1": "Upper layer resistivity rho1 (ohm.m)",
                          "Lx": "Grid length Lx (m)", "Ly": "Grid width Ly (m)",
                          "IG": "Injected current I_G (A)"})
    if not bem.HAVE_NUMPY:
        raise RuntimeError("The numerical solver needs numpy.")
    p["zones"] = _zones(p.get("zones"))
    return studies.optimise_grid(p)


def api_earthtest(p):
    """Fall-of-potential test planning and interpretation (1.8.0)."""
    _bem_prepare(p)
    mult = p.get("multiples") or [1, 2, 3, 5, 7, 10]
    meas = p.get("measured") or None
    if meas:
        try:
            meas = [[float(m[0]), float(m[1])] for m in meas]
        except (TypeError, ValueError, IndexError):
            raise ValueError("Measured readings must be pairs of probe distance (m) and resistance (Ω).")
    dCm = p.get("dC_measured")
    return earthtest.plan(p, float(p.get("bearing", 0.0)), float(p.get("probe_angle", 0.0)),
                          [float(m) for m in mult], float(p.get("accuracy_pct", 2.0)),
                          meas, float(dCm) if dCm not in (None, "") else None,
                          from_edge=str(p.get("measured_from", "centre")) == "edge")


def _cx(v, label):
    if v in (None, ""):
        return None
    if isinstance(v, dict):
        return complex(float(v.get("re", 0)), float(v.get("im", 0)))
    if isinstance(v, (list, tuple)):
        return complex(float(v[0]), float(v[1]))
    try:
        return complex(str(v).replace(" ", "").replace("i", "j"))
    except ValueError:
        raise ValueError(f"{label}: enter a complex value such as 0.5+5j.")


def api_fault_sweep(p):
    """Grid current for faults along an outgoing line with a shield wire (1.8.0)."""
    _require_positive(p, {"Un_kV": "Nominal voltage (kV)", "Rg": "Grid resistance R_g (Ω)",
                          "line_km": "Line length (km)", "span_km": "Span length (km)",
                          "Rt": "Tower footing resistance (Ω)", "R_remote": "Remote station earth (Ω)"})
    kw = dict(line_km=float(p["line_km"]), span_km=float(p["span_km"]), Rt=float(p["Rt"]),
              R_remote=float(p["R_remote"]), rho=float(p.get("rho", 100.0)),
              f=float(p.get("f", 50.0)), c=float(p.get("c", 1.1)),
              sw_r_km=float(p.get("sw_r_km", 0.33)), sw_gmr=float(p.get("sw_gmr", 0.004)),
              d_phase_sw=float(p.get("d_phase_sw", 8.0)))
    for k, lab in (("Z1_line", "Line Z₁ per km"), ("Z0_line", "Line Z₀ per km"),
                   ("Z1_local", "Local source Z₁"), ("Z0_local", "Local source Z₀"),
                   ("Z1_remote", "Remote source Z₁"), ("Z0_remote", "Remote source Z₀"),
                   ("Z_other", "Other shield wires and neutrals")):
        v = _cx(p.get(k), lab)
        if v is not None:
            kw[k] = v
    if float(kw["span_km"]) > float(kw["line_km"]) and not p.get("spans_km"):
        raise ValueError("The span cannot be longer than the line.")
    if p.get("spans_km"):
        kw["spans_km"] = _num_list(p["spans_km"], "Span lengths")
    if p.get("Rt_list"):
        kw["Rt_list"] = _num_list(p["Rt_list"], "Footing resistances")
    if p.get("other_lines"):
        ol = []
        for i, row in enumerate(p["other_lines"], 1):
            if isinstance(row, dict):
                ol.append(row)
                continue
            v = _num_list(row, f"Other line {i}")
            if len(v) < 4:
                raise ValueError(f"Other line {i}: give length, span, footing resistance and "
                                 f"remote earth.")
            ol.append(dict(line_km=v[0], span_km=v[1], Rt=v[2], R_remote=v[3],
                           n_wires=int(v[4]) if len(v) > 4 else 1, name=f"line {i}"))
        kw["other_lines"] = ol
    # 1.9.2: two shield wires on the faulted line, and lines sharing its corridor
    if p.get("n_wires") not in (None, ""):
        kw["n_wires"] = int(float(p["n_wires"]))
        if kw["n_wires"] not in (1, 2):
            raise ValueError("The faulted line has one or two shield wires.")
    if p.get("d_sw") not in (None, ""):
        _require_positive(p, {"d_sw": "Spacing of the two shield wires (m)"})
        kw["d_sw"] = float(p["d_sw"])
    if p.get("parallel_lines"):
        pls = []
        for i, row in enumerate(p["parallel_lines"], 1):
            if isinstance(row, dict):
                pls.append(row)
                continue
            v = _num_list(row, f"Parallel line {i}")
            if len(v) < 2:
                raise ValueError(f"Parallel line {i}: give the separation (m) and the footing "
                                 f"resistance (Ω).")
            q = dict(separation=v[0], Rt=v[1], name=f"parallel line {i}")
            if len(v) > 2:
                q["n_wires"] = int(v[2])
            if len(v) > 3:
                q["d_sw"] = v[3]
            if len(v) > 4:
                q["d_phase"] = v[4]
            pls.append(q)
        kw["parallel_lines"] = pls
    r = faultcurrent.fault_location_sweep(float(p["Un_kV"]), float(p["Rg"]), **kw)
    r["Df"] = float(p.get("Df", 1.0) or 1.0)
    r["IG_design_kA"] = r["worst"]["Ig_kA"] * r["Df"]
    return r


def _num_list(v, label):
    """A list of positive numbers from a list or a comma/semicolon string."""
    if isinstance(v, str):
        v = [t for t in v.replace(";", ",").split(",") if t.strip()]
    try:
        out = [float(t) for t in v]
    except (TypeError, ValueError):
        raise ValueError(f"{label}: give numbers separated by commas.")
    if not out or any(not math.isfinite(t) or t <= 0 for t in out):
        raise ValueError(f"{label}: every value must be a positive number.")
    return out


def api_cable_sheath(p):
    """Earth-fault current returning in cable sheaths (1.8.5)."""
    _require_positive(p, {"If_kA": "Earth-fault current (kA)", "length_km": "Cable length (km)",
                          "R_A": "Earth resistance at A (Ω)", "R_B": "Earth resistance at B (Ω)",
                          "r_sheath_km": "Sheath resistance (Ω/km)", "r_mean": "Sheath mean radius (m)"})
    joints = _num_list(p["joints"], "Joint distances") if p.get("joints") else None
    form = p.get("formation", "trefoil")
    _require_choice(form, ("trefoil", "flat", "three_core"), "Formation")
    _require_choice(p.get("bonding", "both_ends"), ("both_ends", "single_point_A", "single_point_B",
                                                   "cross_bonded"), "Sheath bonding")
    minor = None
    if p.get("bonding") == "cross_bonded":
        if not p.get("minor_km"):
            raise ValueError("Give the minor section lengths of the cross-bonded cable.")
        minor = _num_list(p["minor_km"], "Minor section lengths")
        if abs(sum(minor) - float(p["length_km"])) > 1e-6 * float(p["length_km"]):
            raise ValueError(f"The minor sections add up to {sum(minor):g} km, not the cable "
                             f"length of {float(p['length_km']):g} km.")
        if joints:
            raise ValueError("With cross-bonding the earthed joints are the major-section joints, "
                             "set by the minor sections; leave the joint list empty.")
    ph = int(float(p.get("faulted_phase", 0) or 0))
    if ph not in (0, 1, 2):
        raise ValueError("The faulted phase is 1, 2 or 3 (entered as 0, 1 or 2).")
    _require_choice(p.get("fault_at", "B"), ("A", "B"), "Fault location")
    if form != "three_core" and not _finite_pos(p.get("spacing", 0.1)):
        raise ValueError("The phase spacing must be positive.")
    ra = p.get("r_armour_km")
    return faultcurrent.cable_sheath_return(
        float(p["If_kA"]), length_km=float(p["length_km"]), R_A=float(p["R_A"]),
        R_B=float(p["R_B"]), r_sheath_km=float(p["r_sheath_km"]), r_mean=float(p["r_mean"]),
        formation=form, spacing=float(p.get("spacing", 0.1)),
        n_circuits=int(p.get("n_circuits", 1) or 1), joints=joints,
        R_joint=(float(p["R_joint"]) if p.get("R_joint") not in (None, "") else None),
        bonding=p.get("bonding", "both_ends"), rho=float(p.get("rho", 100.0)),
        f=float(p.get("f", 50.0)), fault_at=p.get("fault_at", "B"),
        r_armour_km=(float(ra) if ra not in (None, "") else None),
        source_beyond=_truthy(p.get("source_beyond", False)), minor_km=minor,
        circuit_sep=float(p.get("circuit_sep") or 0.5), faulted_phase=ph)


def api_fuse(p):
    """Fuse time–current band (IEC 60269 gates) or manufacturer's curve, I_a at
    the usual disconnection times and the operating time at a current (1.8.6)."""
    if p.get("I") not in (None, ""):
        _require_positive(p, {"I": "Current (A)"})
    return fuses.describe(p)


def api_risk(p):
    """IEC 62305-2:2024 risk R and frequency of damage F, zone by zone, and the
    least protection that meets R_T and F_T (1.8.0; the 2024 edition in 1.8.5)."""
    return risk.select(p)


def api_spd(p):
    """SPD selection and coordination, IEC 62305-4:2024 Annex C (1.8.0, 1.8.5)."""
    return spd.coordinate(p)


# Geometric inputs each electrode formula divides by or takes the logarithm
# of.  The Dwight strip and ring formulas contain ln(4l/s) and ln(4D/s) with
# s = 2h, so they have no finite surface limit (h = 0): a conductor laid ON the
# surface needs its own formula, and a zero depth used to surface as a raw
# "float division by zero".  The plate (ENA shallow form) and the mesh
# (Sverak) are valid at h = 0, so only h < 0 is rejected there.
_ELECTRODE_POSITIVE = {
    "rod": ("L", "d"), "rods_parallel": ("L", "d", "n", "s"),
    "strip": ("L", "w", "h"), "round": ("L", "d", "h"),
    "ring": ("radius", "d", "h"), "plate": ("area",),
    "foundation": ("volume_m3",), "mesh": ("area", "total_length"),
}
_ELECTRODE_NAMES = {"L": "length L (m)", "d": "diameter d (m)", "n": "number of rods",
                    "s": "spacing s (m)", "w": "width w (m)", "h": "burial depth h (m)",
                    "radius": "radius (m)", "area": "area (m²)",
                    "volume_m3": "volume (m³)", "total_length": "total length (m)"}


def _require_electrodes(items):
    for i, e in enumerate(items or [], 1):
        kind = e.get("type", "rod")
        if kind not in iec60364.ELECTRODE_FUNCS:
            raise ValueError(f"Electrode {i}: unknown type '{kind}'.")
        if e.get("rho") not in (None, ""):
            _require_positive(e, {"rho": f"Electrode {i} ({kind}): soil resistivity (ohm.m)"})
        for key in _ELECTRODE_POSITIVE.get(kind, ()):
            if key not in e:
                continue            # the formula's own default applies
            label = f"Electrode {i} ({kind}): {_ELECTRODE_NAMES.get(key, key)}"
            if key == "h":
                try:
                    hv = float(e["h"])
                except (TypeError, ValueError):
                    hv = None
                if hv is not None and math.isfinite(hv) and hv <= 0:
                    raise ValueError(
                        f"{label} must be greater than zero: the buried-"
                        f"conductor formula (Dwight, IEEE Std 142) contains a "
                        f"term ln(·/2h) and has no limit at the surface. Enter the "
                        f"actual depth of cover (typically 0.5–0.8 m).")
            _require_positive(e, {key: label})
        if kind in ("plate", "mesh") and e.get("h") not in (None, ""):
            if float(e["h"]) < 0:
                raise ValueError(f"Electrode {i} ({kind}): burial depth h (m) "
                                 f"cannot be negative.")


def api_building(p):
    _require_positive(p, {"rho": "Soil resistivity (ohm.m)",
                          "U0": "Voltage to earth U0 (V)"})
    _require_rows(p.get("electrodes"), "electrode")
    _require_electrodes(p.get("electrodes"))
    sysname = str(p.get("system", "TT")).upper()
    if not (sysname.startswith("TT") or sysname.startswith("TN") or sysname.startswith("IT")):
        raise ValueError(f"System must be TT, TN (TN-S, TN-C-S) or IT (got '{p.get('system')}').")
    dev = p.get("device") or {}
    if dev:
        _require_choice(str(dev.get("kind", "mcb")).lower(),
                        {"mcb", "breaker", "mccb", "fuse", "gg", "fuse_gg", "rcd", "rcbo",
                         "fuse_iec", "fuse_gm", "fuse_am", "fuse_curve"},
                        "Protective device")
        if str(dev.get("kind")).lower() != "fuse_curve":
            _require_positive(dev, {"rating_A": "Device rating (A, or A for IΔn)"})
        elif not dev.get("points") or (isinstance(dev.get("points"), str) and not dev["points"].strip()):
            raise ValueError("Paste the fuse's time–current points (current A, time s), one pair per line.")
    _require_nonneg(p, {"Z_line": "Line impedance (ohm)", "Z_pe": "PE impedance (ohm)",
                        "Z_source": "Source impedance (ohm)"})
    if p.get("separation") not in (None, "", 0, "0"):
        _require_positive(p, {"separation": "Electrode separation D (m)"})

    return reasoning.explain_building(iec60364.assess(
        p.get("system", "TT"), float(p.get("U0", 230.0)),
        float(p.get("rho", 100.0)), p.get("electrodes", []),
        p.get("device", dict(kind="mcb", rating_A=32, curve="B")),
        p.get("circuit", "final"),
        float(p.get("Z_line", 0.0)), float(p.get("Z_pe", 0.0)),
        float(p.get("Z_source", 0.0)), float(p.get("UL", 50.0)),
        float(p.get("coupling", 1.0)),
        (float(p["separation"]) if p.get("separation") not in (None, "", 0)
         else None)), float(p.get("rho", 100.0)))


def api_electrode(p):
    kind = p.get("type", "rod")
    fn = iec60364.ELECTRODE_FUNCS.get(kind)
    if not fn:
        raise ValueError(f"Unknown electrode type '{kind}'.")
    _require_electrodes([p])
    params = {k: v for k, v in p.items() if k not in ("type",)}
    return fn(**params)


def api_rods_required(p):
    _require_positive(p, {"rho": "Soil resistivity (ohm.m)",
                          "target_R": "Target resistance (ohm)",
                          "L": "Rod length (m)", "d": "Rod diameter (m)"})

    return iec60364.rods_required(
        float(p.get("rho", 100.0)), float(p.get("target_R", 10.0)),
        float(p.get("L", 3.0)), float(p.get("d", 0.016)),
        float(p.get("s", 6.0)), int(p.get("max_n", 60)))


def api_earthpit(p):
    """Earth pit: an electrode in a hole of low-resistivity backfill (1.3.6)."""
    electrode = _require_choice(p.get("electrode", "rod"), {"rod", "plate"}, "Electrode")
    _require_choice(p.get("backfill", "bentonite_4to1"), set(earthpit.BACKFILLS), "Backfill")
    spec = {"rho": "Soil resistivity (ohm.m)", "D": "Backfill diameter (m)"}
    if electrode == "rod":
        spec.update(L="Rod length (m)", d="Rod diameter (m)")
    else:
        spec.update(area="Plate area (m²)", top="Plate depth (m)")
    _require_positive(p, spec)
    _require_nonneg(p, {"fill_top": "Top of backfill (m)", "fill_bottom": "Bottom of backfill (m)",
                        "top": "Depth of rod top (m)", "thickness_mm": "Plate thickness (mm)"})
    for key, label in (("rho_c", "Backfill resistivity (ohm.m)"), ("s", "Spacing between pits (m)"),
                       ("target", "Target resistance (ohm)"), ("I_fault", "Fault current (A)"),
                       ("t_fault", "Fault duration (s)"), ("season_factor", "Seasonal factor")):
        if p.get(key) not in (None, ""):
            _require_positive(p, {key: label})
    if p.get("backfill") == "custom" and p.get("rho_c") in (None, ""):
        raise ValueError("Backfill resistivity (ohm.m) is required for a custom backfill.")
    n = int(p.get("n", 1) or 1)
    if not 1 <= n <= 100:
        raise ValueError("Number of pits must be between 1 and 100.")
    if electrode == "rod" and float(p["D"]) <= float(p["d"]):
        raise ValueError("Backfill diameter must be larger than the rod diameter.")
    if p.get("season_factor") not in (None, "") and float(p["season_factor"]) < 1:
        raise ValueError("Seasonal factor must be 1 or more (dry-season resistivity / measured).")
    ft, fb = p.get("fill_top"), p.get("fill_bottom")
    if ft not in (None, "") and fb not in (None, "") and float(fb) <= float(ft):
        raise ValueError("The bottom of the backfill must be deeper than its top.")
    _require_choice(str(p.get("housing_class", "L")).upper(), set(earthpit.HOUSING_CLASSES),
                    "Inspection housing class")
    return earthpit.design(p)


def api_lightning(p):
    _require_positive(p, {"rho": "Soil resistivity (ohm.m)"})
    _require_positive(p, {k: v for k, v in (
        ("area", "Area enclosed by the earth electrode (m²)"), ("perimeter", "Perimeter (m)"),
        ("h", "Burial depth (m)"), ("d", "Conductor diameter (m)")) if k in p})
    _require_choice(str(p.get("lps_class", "III")).upper(), {"I", "II", "III", "IV"}, "LPS class")
    _require_choice(str(p.get("arrangement", "B")).upper(), {"A", "B"}, "Earth-termination arrangement")
    if p.get("foundation_volume") not in (None, "", 0, "0"):
        _require_positive(p, {"foundation_volume": "Foundation volume (m³)"})
    if p.get("front_time") not in (None, ""):
        _require_positive(p, {"front_time": "Impulse front time (us)"})

    mesh = p.get("mesh_spacing")
    if mesh is not None and str(mesh) != "":
        if float(mesh) <= 0:
            raise ValueError("Earthing-system conductor spacing (m) must be "
                             "greater than zero, or left blank.")
    else:
        mesh = None

    return reasoning.explain_lightning(iec62305.design(
        p.get("lps_class", "III"), float(p.get("rho", 100.0)),
        float(p.get("area", 200.0)), float(p.get("perimeter", 60.0)),
        p.get("arrangement", "B"), float(p.get("d", 0.01)),
        float(p.get("h", 0.5)), float(p.get("rod_d", 0.016)),
        p.get("foundation_volume"), float(p.get("separation_length", 10.0)),
        p.get("separation_material", "air"),
        float(p.get("front_time", 1.0)), p.get("injection", "centre"),
        None if mesh is None else float(mesh)))


def api_airterm(p):
    _require_choice(str(p.get("lps_class", "III")).upper(), {"I", "II", "III", "IV"}, "LPS class")
    return reasoning.explain_airterm(airterm.design(
        p.get("lps_class", "III"),
        p.get("structure") or {},
        p.get("terminals") or [],
        p.get("catenaries"),
        p.get("reference_plane"),
        p.get("roof_depth"),
        p.get("equipment"),
        p.get("mesh")))


def api_sysgnd(p):
    _require_positive(p, {"V_ll_kV": "Line voltage (kV)",
                          "frequency": "Frequency (Hz)"})
    _require_nonneg(p, {"cable_km": "Cable length (km)", "overhead_km": "Overhead line length (km)",
                        "motors_kVA": "Connected motors (kVA)",
                        "transformers_kVA": "Connected transformers (kVA)",
                        "C0_uF_per_km": "Cable capacitance (µF/km)"})
    _require_choice(p.get("method", "auto"),
                    {"auto", "solid", "low_resistance", "high_resistance", "reactance", "ungrounded"},
                    "Grounding method")
    if p.get("method") in ("low_resistance", "reactance"):
        _require_positive(p, {"I_target_A": "Target earth-fault current (A)"})

    cc = ieee142.charging_current(
        float(p.get("V_ll_kV", 6.6)), float(p.get("cable_km", 0.0)),
        float(p.get("C0_uF_per_km", 0.25)), float(p.get("motors_kVA", 0.0)),
        float(p.get("transformers_kVA", 0.0)), float(p.get("frequency", 50.0)),
        float(p.get("overhead_km", 0.0)))
    out = dict(charging=cc, three_IC0=cc["three_IC0"])
    method = p.get("method", "auto")
    if method == "auto":
        rec = ieee142.recommend(float(p.get("V_ll_kV", 6.6)),
                                bool(p.get("continuity_critical", False)),
                                bool(p.get("ln_loads", False)),
                                cc["three_IC0"],
                                margin=float(p.get("margin", 1.0)))
        method = rec["method"]
        out["recommendation"] = rec
    out["method"] = method
    out["V_ln"] = float(p.get("V_ll_kV", 6.6)) * 1000.0 / math.sqrt(3.0)
    if method == "high_resistance":
        out.update(ieee142.hrg_resistor(float(p.get("V_ll_kV", 6.6)),
                                        cc["three_IC0"],
                                        float(p.get("margin", 1.0))))
    elif method == "low_resistance":
        out.update(ieee142.lrg_resistor(float(p.get("V_ll_kV", 6.6)),
                                        float(p.get("I_target_A", 400.0)),
                                        float(p.get("t_rating_s", 10.0))))
    elif method == "reactance":
        out.update(ieee142.reactor_grounding(float(p.get("V_ll_kV", 6.6)),
                                             float(p.get("I_target_A", 400.0)),
                                             p.get("X1")))
    if method == "high_resistance" and cc["three_IC0"] <= 0:
        out["warnings"] = list(out.get("warnings") or []) + [
            "The charging current is zero, so the neutral resistor cannot be "
            "sized: enter the cable length, overhead line, motors or "
            "transformers connected to the system."]
    if p.get("X0") and p.get("X1"):
        out["effective"] = ieee142.effectively_grounded(
            float(p["X0"]), float(p["X1"]), float(p.get("R0", 0.0)))
    out["methods"] = ieee142.GROUNDING_METHODS
    return out


def api_standards(p):
    """The standards registry, and the cross-check calculations of
    earthsys.standards for the values supplied (all optional)."""
    out = dict(registry=standards.REGISTRY, areas=standards.AREAS)
    if p.get("t_F") not in (None, ""):
        t = float(p["t_F"])
        out["touch"] = dict(U_Tp=standards.en50522_touch_limit(t),
                            ieee80_50kg=standards.ieee80_bare_touch(t, 50),
                            ieee80_70kg=standards.ieee80_bare_touch(t, 70))
    if all(p.get(k) not in (None, "") for k in ("f_n", "p_n", "f_d", "t_d")):
        pc = standards.eg0_coincidence(float(p["f_n"]), float(p["p_n"]),
                                       float(p["f_d"]), float(p["t_d"]))
        out["eg0"] = dict(P_coinc=pc)
        if p.get("P_fib") not in (None, ""):
            risk = pc * float(p["P_fib"])
            out["eg0"].update(risk=risk, band=standards.eg0_risk_band(risk))
    if p.get("rho") not in (None, "") and p.get("f") not in (None, ""):
        lvl = p.get("level") or "mean"
        if lvl not in standards.ALIPIO_VISACRO_LEVELS:
            raise ValueError(f"level must be one of {sorted(standards.ALIPIO_VISACRO_LEVELS)}")
        out["soil_frequency"] = standards.alipio_visacro(float(p["rho"]), float(p["f"]), level=lvl)
        out["soil_frequency"]["impulse_factor"] = dict(
            first=standards.tb781_impulse_reduction(float(p["rho"]), "first")["factor"],
            subsequent=standards.tb781_impulse_reduction(float(p["rho"]), "subsequent")["factor"])
    if all(p.get(k) not in (None, "") for k in ("rho", "I_E", "V_lim")):
        out["epr_contour"] = standards.epr_contour_distance(
            float(p["rho"]), float(p["I_E"]), float(p["V_lim"]))
    return out


def api_report(p):
    lang = _require_choice(p.get("lang", "en"), {"en", "fa"}, "Report language")
    html_doc = report.build(p.get("data", {}), lang)
    name = p.get("filename") or f"earthing_report_{lang}.html"
    name = os.path.basename(name)
    os.makedirs(OUTPUTS, exist_ok=True)
    path = os.path.join(OUTPUTS, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    return dict(html=html_doc, path=path, filename=name)


def api_drawings(p):
    """Construction drawing set (module 11) from the results of the other
    modules.  Returns SVG previews, a vector PDF and a ZIP with DXF/SVG/CSV."""
    results = p.get("results") or {}
    if not isinstance(results, dict):
        raise ValueError("results must be the module results object.")
    usable = [k for k in ("grid", "bem", "building", "earthpit", "lightning", "airterm", "sysgnd")
              if results.get(k)]
    if not usable:
        raise ValueError("Run at least one design module (substation grid, numerical solver, "
                         "building, earth pit, lightning or air termination) before drawing.")
    opt = dict(p.get("options") or {})
    for key, label in (("conductor_mm2", "Conductor size (mm²)"), ("rod_section_m", "Rod section length (m)"),
                       ("fence_offset", "Fence offset (m)"), ("fence_bond_m", "Fence bonding interval (m)")):
        if opt.get(key) not in (None, "", 0, "0"):
            _require_positive(opt, {key: label})
        else:
            opt.pop(key, None)
    for key, label, lo, hi in (("wastage_pct", "Allowance (%)", 0, 100), ("met_ways", "MET ways", 4, 40),
                               ("test_pits", "Test pits", 0, 200)):
        if opt.get(key) not in (None, ""):
            v = float(opt[key])
            if not lo <= v <= hi:
                raise ValueError(f"{label} must be between {lo} and {hi}.")
        else:
            opt.pop(key, None)
    res = drawings.build(dict(results=results, options=opt, meta=p.get("meta") or {},
                              version=APP_VERSION))
    pre = os.path.basename(res["filename"] or "drawings")
    if p.get("save") is False:
        res["saved_to"] = None
        return res
    try:
        import base64
        out = os.path.join(OUTPUTS, "drawings")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, pre + "_drawings.pdf"), "wb") as fh:
            fh.write(base64.b64decode(res["pdf_b64"]))
        with open(os.path.join(out, pre + "_drawing_set.zip"), "wb") as fh:
            fh.write(base64.b64decode(res["zip_b64"]))
        res["saved_to"] = out
    except OSError:
        res["saved_to"] = None
    return res


def api_project_save(p):
    os.makedirs(PROJECTS, exist_ok=True)
    name = os.path.basename(p.get("name") or "project")
    if not name.endswith(".json"):
        name += ".json"
    path = os.path.join(PROJECTS, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(p.get("data", {}), fh, indent=2, ensure_ascii=False)
    return dict(saved=True, path=path, name=name)


def api_project_list(_):
    os.makedirs(PROJECTS, exist_ok=True)
    items = []
    for f in sorted(os.listdir(PROJECTS)):
        if f.endswith(".json"):
            fp = os.path.join(PROJECTS, f)
            items.append(dict(name=f, size=os.path.getsize(fp),
                              modified=os.path.getmtime(fp)))
    return dict(projects=items)


def api_project_load(p):
    name = os.path.basename(p.get("name", ""))
    path = os.path.join(PROJECTS, name)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Project '{name}' not found.")
    with open(path, encoding="utf-8") as fh:
        return dict(name=name, data=json.load(fh))


ROUTES = {
    "/api/meta": api_meta,
    "/api/soil/reduce": api_soil_reduce,
    "/api/soil/invert": api_soil_invert,
    "/api/soil/equivalent": api_soil_equivalent,
    "/api/fault": api_fault,
    "/api/conductor": api_conductor,
    "/api/ieee80/design": api_ieee80,
    "/api/ieee80/optimise": api_ieee80_optimise,
    "/api/bem": api_bem,
    "/api/transfer": api_transfer,
    "/api/bem/convergence": api_bem_convergence,
    "/api/bem/seasonal": api_bem_seasonal,
    "/api/bem/montecarlo": api_bem_montecarlo,
    "/api/bem/powerfreq": api_bem_powerfreq,
    "/api/bem/optimise": api_bem_optimise,
    "/api/bem/governing": api_bem_governing,
    "/api/dxf/inspect": api_dxf_inspect,
    "/api/cable/sheath": api_cable_sheath,
    "/api/dxf/import": api_dxf_import,
    "/api/earthtest": api_earthtest,
    "/api/fault/sweep": api_fault_sweep,
    "/api/risk": api_risk,
    "/api/fuse": api_fuse,
    "/api/spd": api_spd,
    "/api/hf": api_hf,
    "/api/building": api_building,
    "/api/electrode": api_electrode,
    "/api/rods-required": api_rods_required,
    "/api/earthpit": api_earthpit,
    "/api/lightning": api_lightning,
    "/api/airterm": api_airterm,
    "/api/system-grounding": api_sysgnd,
    "/api/standards": api_standards,
    "/api/report": api_report,
    "/api/drawings": api_drawings,
    "/api/project/save": api_project_save,
    "/api/project/list": api_project_list,
    "/api/project/load": api_project_load,
}


def dispatch(path: str, payload: dict) -> dict:
    """Call an endpoint by its route path. Raises KeyError for unknown paths."""
    fn = ROUTES[path]
    return clean(fn(payload or {}))
