"""
JSON API layer.

Every endpoint is a plain function taking a dict of parameters and returning a
dict of results.  The layer is deliberately transport-agnostic: `server.py`
exposes it over HTTP for the desktop application, and `web/pyodide-boot.js`
calls exactly the same functions inside the browser when EarthSystem runs from
GitHub Pages with no server at all.
"""

from __future__ import annotations

import json
import math
import os

from . import (bem, conductor, faultcurrent, iec60364, iec62305, ieee80,
               ieee142, materials, reasoning, report, soil)

APP_VERSION = "1.1.0"

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.path.join(BASE, "projects")
OUTPUTS = os.path.join(BASE, "outputs")


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
        c_factors=faultcurrent.C_FACTORS,
        system_types=iec60364.SYSTEM_TYPES,
        disconnection_times=iec60364.DISCONNECTION_TIMES,
        fuse_gg={str(k): v for k, v in iec60364.FUSE_GG.items()},
        mcb_multipliers=iec60364.MCB_MULTIPLIERS,
        lps_classes=iec62305.LPS_CLASS,
        lps_l1={"rho": materials.LPS_L1_RHO, "l1": materials.LPS_L1},
        lps_electrodes=materials.LPS_ELECTRODE_MIN,
        grounding_methods=ieee142.GROUNDING_METHODS,
        have_numpy=bem.HAVE_NUMPY,
    )


def api_soil_reduce(p):
    rows = soil.reduce_survey(p.get("rows", []), p.get("array", "wenner"))
    return dict(rows=rows)


def api_soil_invert(p):
    rows = p.get("rows")
    array = p.get("array", "wenner")
    if rows:
        red = soil.reduce_survey(rows, array)
        sp = [r["spacing"] for r in red]
        rh = [r["rho"] for r in red]
    else:
        sp = p["spacings"]
        rh = p["rho"]
    res = soil.invert_two_layer(sp, rh, array)
    res["uniform_average"] = sum(rh) / len(rh)
    res["equivalent"] = soil.equivalent_uniform(
        res["rho1"], res["rho2"], res["h"],
        float(p.get("grid_depth", 0.5)), float(p.get("rod_length", 0.0)),
        p.get("equivalent_method", "auto"))
    return res


def api_fault(p):
    Un = float(p.get("Un_kV", 20.0))
    c = float(p.get("c", 1.1))
    mode = p.get("mode", "impedance")

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
    xr = float(p.get("xr_ratio") or lg["xr_ratio"] or 10.0)
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
    out = {}
    if p.get("standard", "ieee80") == "ieee80":
        Tm = p.get("Tm")
        if p.get("joint") and p["joint"] in materials.JOINT_TM_LIMITS:
            Tm = materials.JOINT_TM_LIMITS[p["joint"]]
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
    out["min_buried"] = conductor.min_buried_earthing_conductor(
        bool(p.get("corrosion_protected", True)),
        bool(p.get("mechanically_protected", False)))
    if p.get("S_line_mm2"):
        out["pe"] = conductor.pe_from_line_conductor(float(p["S_line_mm2"]))
        out["bonding"] = conductor.bonding_conductors(out["pe"]["area_mm2"])
    chosen = out.get("ieee80", out["iec"])
    out["selected_mm2"] = max(
        chosen.get("standard_mm2") or 0,
        out["iec"].get("standard_mm2") or 0,
        out["min_buried"]["copper_mm2"] if p.get("iec_material", "copper") == "copper"
        else out["min_buried"]["steel_mm2"])
    out["diameter_m"] = materials.diameter_from_area(out["selected_mm2"]) / 1000.0
    return out


def _geometry(p) -> ieee80.GridGeometry:
    return ieee80.GridGeometry(
        Lx=float(p.get("Lx", 70)), Ly=float(p.get("Ly", 70)),
        D=float(p.get("D", 7)), h=float(p.get("h", 0.5)),
        d=float(p.get("d", 0.01)), n_rods=int(p.get("n_rods", 0)),
        Lr=float(p.get("Lr", 0.0)), d_rod=float(p.get("d_rod", 0.016)),
        rods_on_perimeter=bool(p.get("rods_on_perimeter", True)),
        shape=p.get("shape", "rectangular"), Dm=float(p.get("Dm", 0.0)))


def api_ieee80(p):
    g = _geometry(p)
    res = ieee80.design(
        float(p.get("rho", 100.0)), g, float(p.get("IG_kA", 1.0)),
        float(p.get("rho_s", 3000.0)), float(p.get("hs", 0.1)),
        float(p.get("ts", 0.5)), int(p.get("body_weight", 70)),
        p.get("r_method", "auto"))
    res["layout"] = dict(conductors=g.conductor_paths(), rods=g.rod_positions())
    return reasoning.explain_ieee80(res)


def api_ieee80_optimise(p):
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
        gg = _geometry({**p, "D": res["best"]["D"],
                        "n_rods": res["best"].get("n_rods", g.n_rods),
                        "Lr": p.get("Lr", 3.0) if res["best"].get("n_rods") else p.get("Lr", 0)})
        best["layout"] = dict(conductors=gg.conductor_paths(),
                              rods=gg.rod_positions())
        reasoning.explain_ieee80(best)
    return res


def api_bem(p):
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


def api_building(p):
    return reasoning.explain_building(iec60364.assess(
        p.get("system", "TT"), float(p.get("U0", 230.0)),
        float(p.get("rho", 100.0)), p.get("electrodes", []),
        p.get("device", dict(kind="mcb", rating_A=32, curve="B")),
        p.get("circuit", "final"),
        float(p.get("Z_line", 0.0)), float(p.get("Z_pe", 0.0)),
        float(p.get("Z_source", 0.0)), float(p.get("UL", 50.0)),
        float(p.get("coupling", 1.0))), float(p.get("rho", 100.0)))


def api_electrode(p):
    kind = p.get("type", "rod")
    fn = iec60364.ELECTRODE_FUNCS.get(kind)
    if not fn:
        raise ValueError(f"Unknown electrode type '{kind}'.")
    params = {k: v for k, v in p.items() if k not in ("type",)}
    return fn(**params)


def api_rods_required(p):
    return iec60364.rods_required(
        float(p.get("rho", 100.0)), float(p.get("target_R", 10.0)),
        float(p.get("L", 3.0)), float(p.get("d", 0.016)),
        float(p.get("s", 6.0)), int(p.get("max_n", 60)))


def api_lightning(p):
    return reasoning.explain_lightning(iec62305.design(
        p.get("lps_class", "III"), float(p.get("rho", 100.0)),
        float(p.get("area", 200.0)), float(p.get("perimeter", 60.0)),
        p.get("arrangement", "B"), float(p.get("d", 0.01)),
        float(p.get("h", 0.5)), float(p.get("rod_d", 0.016)),
        p.get("foundation_volume"), float(p.get("separation_length", 10.0)),
        p.get("separation_material", "air")))


def api_sysgnd(p):
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
                                cc["three_IC0"])
        method = rec["method"]
        out["recommendation"] = rec
    out["method"] = method
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
    if p.get("X0") and p.get("X1"):
        out["effective"] = ieee142.effectively_grounded(
            float(p["X0"]), float(p["X1"]), float(p.get("R0", 0.0)))
    out["methods"] = ieee142.GROUNDING_METHODS
    return out


def api_report(p):
    lang = p.get("lang", "en")
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
    "/api/fault": api_fault,
    "/api/conductor": api_conductor,
    "/api/ieee80/design": api_ieee80,
    "/api/ieee80/optimise": api_ieee80_optimise,
    "/api/bem": api_bem,
    "/api/building": api_building,
    "/api/electrode": api_electrode,
    "/api/rods-required": api_rods_required,
    "/api/lightning": api_lightning,
    "/api/system-grounding": api_sysgnd,
    "/api/report": api_report,
    "/api/project/save": api_project_save,
    "/api/project/list": api_project_list,
    "/api/project/load": api_project_load,
}


def dispatch(path: str, payload: dict) -> dict:
    """Call an endpoint by its route path. Raises KeyError for unknown paths."""
    fn = ROUTES[path]
    return clean(fn(payload or {}))
