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

from . import (airterm, bem, conductor, faultcurrent, iec60364, iec62305, ieee80,
               ieee142, materials, reasoning, report, soil, standards)

APP_VERSION = "1.3.5"

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
    if rows:
        red = soil.reduce_survey(rows, array)
        sp = [r["spacing"] for r in red]
        rh = [r["rho"] for r in red]
        if array == "schlumberger":
            mn = [r.get("d") for r in red]
    else:
        sp = p["spacings"]
        rh = p["rho"]
        if array == "schlumberger" and p.get("mn"):
            mn = p["mn"]
    res = soil.invert_two_layer(sp, rh, array, mn)
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
    # conductor, which contradicted the table and the book (Sec. 5.5).
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
    # Design basis (book Sec. 5.3).  'both' (default) selects the larger of
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
    res["layout"] = dict(conductors=g.conductor_paths(), rods=g.rod_positions())
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
                              rods=gg.rod_positions())
        reasoning.explain_ieee80(best)
    return res


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

    if not bem.HAVE_NUMPY:
        raise RuntimeError("The numerical solver needs numpy. "
                           "Install it with:  pip install numpy")
    net = bem.build_network(p)
    seg = net.discretise(float(p.get("segment_length", 2.5)),
                         int(p.get("max_segments", 2500)))
    sol = net.solve()

    xs = [c for it in net.raw for c in (it[0][0], it[1][0])]
    ys = [c for it in net.raw for c in (it[0][1], it[1][1])]
    pad = float(p.get("margin", 10.0))
    xlim = p.get("xlim") or [min(xs) - pad, max(xs) + pad]
    ylim = p.get("ylim") or [min(ys) - pad, max(ys) + pad]
    nx = int(p.get("nx", 61))
    ny = int(p.get("ny", 61))

    ws = net.worst_touch_step(xlim, ylim, nx, ny,
                              float(p.get("step_distance", 1.0)),
                              p.get("touch_box"),
                              float(p.get("touch_margin", 1.0)))
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
    out.update(segments=seg, surface=ws["surface"], probes=probes,
               touch_box=ws.get("touch_box"),
               touch_max=ws["touch_max"], touch_at=ws["touch_at"],
               step_max=ws["step_max"], step_at=ws["step_at"],
               profile=prof, geometry=net.geometry_json(),
               current=net.current_distribution(), xlim=xlim, ylim=ylim)

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
    return reasoning.explain_bem(out)


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
                        {"mcb", "breaker", "mccb", "fuse", "gg", "fuse_gg", "rcd", "rcbo"},
                        "Protective device")
        _require_positive(dev, {"rating_A": "Device rating (A, or A for IΔn)"})
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
    "/api/building": api_building,
    "/api/electrode": api_electrode,
    "/api/rods-required": api_rods_required,
    "/api/lightning": api_lightning,
    "/api/airterm": api_airterm,
    "/api/system-grounding": api_sysgnd,
    "/api/standards": api_standards,
    "/api/report": api_report,
    "/api/project/save": api_project_save,
    "/api/project/list": api_project_list,
    "/api/project/load": api_project_load,
}


def dispatch(path: str, payload: dict) -> dict:
    """Call an endpoint by its route path. Raises KeyError for unknown paths."""
    fn = ROUTES[path]
    return clean(fn(payload or {}))
