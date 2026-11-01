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
Governing values of the numerical solution (1.8.2).

The studies of page 5 — the convergence check, seasonal soil, soil
uncertainty and the non-equipotential solution — each answer the question
"how large can this touch or step voltage really be?" for one reason the
plain solution leaves out.  Up to 1.8.1 they were reported beside the plain
solution but the verdict, the design report's compliance table and the
drawing stamp still used the plain solution alone.  This module combines
them: for every quantity it takes the largest value any applicable study
produced, names the study it came from, and re-states the checks with it.

Which value each study contributes:

* plain solution       the numerical solution itself
* convergence check    the largest of the coarse, fine and Richardson values
                       (touch, step); the Richardson estimate (R_g, GPR)
* seasonal soil        the worst case (dry / frozen top layer) for each quantity
* soil uncertainty     the 95th percentile of the soil models drawn from the
                       fit (each quantity separately)
* non-equipotential    touch and step with the conductors' own impedance, and
                       the GPR at the feed point

The maxima are taken separately, not multiplied together: each study is a
different correction to the same answer, and stacking them would claim a
dry, uncertain, coarse and non-equipotential worst case all at once.

A study counts only if it was run on the model that the plain solution
solved: same electrodes, soil and current (`model_key`).  A study left over
from an earlier geometry is listed as out of date and ignored.

Touch-zone and fence checks are evaluated by the plain solution; they are
scaled by the governing touch voltage divided by the plain one (never
below 1), which is exact when a study scales the whole field and
conservative otherwise.  Since 1.8.3 the non-equipotential solution also
solves each fence, and its fence touch voltage is used where it is larger.
"""

from __future__ import annotations

import hashlib
import json

STUDY_LABEL = {
    "base": "numerical solution",
    "convergence": "convergence check",
    "seasonal": "seasonal soil",
    "montecarlo": "soil uncertainty (95th percentile)",
    "powerfreq": "non-equipotential solution",
}

_SOIL_KEYS = ("rho1", "rho2", "h_layer", "rho3", "h_layer2", "rho4", "h_layer3",
              "rho_v", "x_v", "y_v", "angle_v")


def _canon(v):
    """Numbers rounded so that 7 and 7.0 and 7.0000000001 hash alike."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 9)
    if isinstance(v, str):
        try:
            return round(float(v), 9) if v.strip() else None
        except ValueError:
            return v
    if isinstance(v, dict):
        return {k: _canon(x) for k, x in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    return str(v)


def model_key(p: dict) -> str:
    """Fingerprint of what a numerical study solved: electrodes, soil, current."""
    m = dict(items=_canon(p.get("items") or []), IG=_canon(p.get("IG", 1000.0)),
             r=_canon(p.get("conductor_radius", 0.005)))
    for k in _SOIL_KEYS:
        v = p.get(k)
        if v not in (None, ""):
            m[k] = _canon(v)
    return hashlib.sha1(json.dumps(m, sort_keys=True).encode()).hexdigest()[:16]


def _candidates(bem: dict, studies: dict):
    """(quantity, value, source, detail) from the plain solution and each study."""
    out = []

    def add(q, v, src, detail=""):
        if isinstance(v, (int, float)) and v == v:
            out.append((q, float(v), src, detail))

    add("touch", bem.get("touch_max"), "base")
    add("step", bem.get("step_max"), "base")
    add("Rg", bem.get("Rg"), "base")
    add("GPR", bem.get("GPR"), "base")

    cv = studies.get("convergence")
    if cv:
        for q in ("touch", "step", "Rg", "GPR"):
            d = cv.get(q) or {}
            v = d.get("design") if q in ("touch", "step") else d.get("extrapolated")
            add(q, v, "convergence", f"segments {cv.get('h')} m and {cv.get('h_half')} m")

    se = studies.get("seasonal")
    if se:
        for c in se.get("cases") or []:
            for q in ("touch", "step", "Rg", "GPR"):
                add(q, c.get(q), "seasonal", str(c.get("name", "")))

    mc = studies.get("montecarlo")
    if mc:
        st = mc.get("stats") or {}
        for q in ("touch", "step", "Rg", "GPR"):
            add(q, (st.get(q) or {}).get("p95"), "montecarlo", f"{mc.get('n')} soil models")

    pf = studies.get("powerfreq")
    if pf:
        add("touch", pf.get("touch_max"), "powerfreq", f"{pf.get('metal')}, {pf.get('f')} Hz")
        add("step", pf.get("step_max"), "powerfreq", f"{pf.get('metal')}, {pf.get('f')} Hz")
        add("GPR", pf.get("GPR_feed"), "powerfreq", "at the feed point")
        z = pf.get("Z") or {}
        add("Rg", z.get("abs"), "powerfreq", "|Z| at the feed point")
    return out


def governing(bem: dict, studies: dict | None = None, limits: dict | None = None) -> dict:
    """Combine the plain numerical solution with the studies run on it.

    bem      result of /api/bem (with its model_key)
    studies  {'convergence': ..., 'seasonal': ..., 'montecarlo': ..., 'powerfreq': ...}
             — each the result of its endpoint (with its model_key)
    limits   {'E_touch': V, 'E_step': V}; taken from the bem checks if omitted
    """
    if not bem or bem.get("touch_max") is None:
        raise ValueError("Run the numerical solution first: the governing values "
                         "start from it.")
    studies = studies or {}
    key = bem.get("model_key")
    used, stale = {}, []
    for name in ("convergence", "seasonal", "montecarlo", "powerfreq"):
        s = studies.get(name)
        if not s:
            continue
        if key and s.get("model_key") and s.get("model_key") != key:
            stale.append(name)
            continue
        used[name] = s

    if limits is None:
        limits = {}
        for c in bem.get("checks") or []:
            if c.get("name") == "Maximum touch voltage":
                limits["E_touch"] = c.get("limit")
            elif c.get("name") == "Maximum step voltage":
                limits["E_step"] = c.get("limit")

    quantities = {}
    for q, v, src, det in _candidates(bem, used):
        e = quantities.setdefault(q, dict(value=None, source=None, detail="", base=None,
                                          candidates=[]))
        e["candidates"].append(dict(source=src, label=STUDY_LABEL[src], value=v, detail=det))
        if src == "base":
            e["base"] = v
        if e["value"] is None or v > e["value"] * (1 + 1e-12):
            e.update(value=v, source=src, detail=det)
    for e in quantities.values():
        e["label"] = STUDY_LABEL.get(e["source"], "")
        b = e.get("base")
        e["ratio"] = (e["value"] / b) if b else 1.0

    t = quantities.get("touch") or {}
    s = quantities.get("step") or {}
    factor = max(1.0, t.get("ratio") or 1.0)

    def why(e, unit):
        if e.get("source") == "base":
            return "the plain numerical solution (no study gives a larger value)"
        det = f", {e['detail']}" if e.get("detail") else ""
        return (f"the {e.get('label')}{det}: {e['value']:.4g} {unit} against "
                f"{e['base']:.4g} {unit} from the plain solution "
                f"(+{100 * (e['ratio'] - 1):.1f} %)")

    checks = []
    Et, Es = limits.get("E_touch"), limits.get("E_step")
    if Et or Es:
        if Et:
            checks.append(dict(name="Maximum touch voltage (governing)", value=t["value"],
                               limit=Et, unit="V", passed=t["value"] <= Et,
                               source=t["source"], basis=why(t, "V")))
        if Es:
            checks.append(dict(name="Maximum step voltage (governing)", value=s["value"],
                               limit=Es, unit="V", passed=s["value"] <= Es,
                               source=s["source"], basis=why(s, "V")))
        pf_fences = {f.get("name"): f for f in (used.get("powerfreq") or {}).get("fences") or []}
        for c in bem.get("checks") or []:
            n = c.get("name", "")
            if n.startswith("Touch voltage at ") or n.startswith("Fence touch voltage"):
                v = float(c.get("value") or 0.0) * factor
                src = t.get("source", "base") if factor > 1 else "base"
                basis = ("plain solution" if factor <= 1 else
                         f"plain solution × {factor:.3f}, the ratio of the governing to the "
                         f"plain touch voltage")
                # 1.8.3: the non-equipotential solution evaluates fences itself
                pf = pf_fences.get((c.get("fence") or {}).get("name"))
                if pf and float(pf.get("touch_max") or 0.0) > v:
                    v = float(pf["touch_max"])
                    src = "powerfreq"
                    basis = (f"the non-equipotential solution, which solves the fence itself: "
                             f"{v:.4g} V against {float(c.get('value') or 0):.4g} V from the "
                             f"plain solution")
                lim = c.get("limit")
                checks.append(dict(name=n + (" (governing)" if src != "base" else ""), value=v,
                                   limit=lim, unit="V",
                                   passed=(lim or 1e18) >= v, source=src, basis=basis))
    passed = all(c["passed"] for c in checks) if checks else None
    out = dict(model_key=key, quantities=quantities, checks=checks, passed=passed,
               studies_used=sorted(used), studies_stale=stale, touch_factor=factor,
               limits=dict(E_touch=Et, E_step=Es))

    # verdict text
    parts = []
    if used:
        parts.append("Studies taken into account: "
                     + ", ".join(STUDY_LABEL[k] for k in sorted(used)) + ".")
    else:
        parts.append("No study has been run on this model, so the governing values are "
                     "those of the plain solution. Run at least the convergence check; "
                     "the seasonal and soil-uncertainty studies where the soil is uncertain; "
                     "and the non-equipotential solution for a large grid or steel conductor.")
    if stale:
        parts.append("Out of date and ignored (run on different electrodes, soil or "
                     "current): " + ", ".join(STUDY_LABEL[k] for k in stale) + ".")
    if checks:
        base_ok = all(c.get("passed") for c in bem.get("checks") or [])
        if passed:
            parts.append("Every check passes with the governing values.")
        elif base_ok:
            failed = [c["name"].replace(" (governing)", "") for c in checks if not c["passed"]]
            parts.append("The plain solution passes, but with the governing values "
                         + ", ".join(f.lower() for f in failed)
                         + " exceeds the limit: the design does not comply.")
        else:
            parts.append("The design does not comply.")
    else:
        parts.append("No tolerable limits were supplied, so no verdict is given.")
    out["note"] = " ".join(parts)
    return out
