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
Studies built on the boundary-element solver (version 1.8.0).

* convergence     the same model solved with the segments halved, and a
                  Richardson estimate of the converged touch and step
                  voltages, so the discretisation error is stated rather
                  than assumed away
* seasonal        the same electrodes under a dry or a frozen top layer
* monte_carlo     the soil model's fitted uncertainty carried through to
                  R_g, GPR, touch and step voltage, and a probability of
                  meeting the limits
* optimise_grid   the cheapest grid (conductor and rod length) that meets
                  the touch and step limits, searched with the numerical
                  solver over conductor count, unequal (graded) spacing and
                  perimeter rods

Requires numpy.
"""

from __future__ import annotations

import math

from . import bem, parallel

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None


SOIL_KEYS = ("rho1", "rho2", "h_layer", "rho3", "h_layer2", "rho4", "h_layer3",
             "rho_v", "x_v", "y_v", "angle_v")


def soil_spec(p: dict) -> dict:
    return {k: p.get(k) for k in SOIL_KEYS if p.get(k) not in (None, "")}


def run_case(p: dict, target: float | None = None, nx: int | None = None,
             grade: bool | None = None, refine: bool = True) -> dict:
    """Build, discretise and solve one model and scan it for the worst touch
    and step voltages.  `p` is the payload of /api/bem."""
    net = bem.build_network(p)
    seg = float(target if target is not None else p.get("segment_length", 2.5))
    g = bool(p.get("grade_ends", True)) if grade is None else bool(grade)
    net.discretise(seg, int(p.get("max_segments", bem.MAX_SEGMENTS)), grade_ends=g)
    sol = net.solve()
    xs = [c for it in net.raw for c in (it[0][0], it[1][0])]
    ys = [c for it in net.raw for c in (it[0][1], it[1][1])]
    pad = float(p.get("margin", 10.0))
    xlim = p.get("xlim") or [min(xs) - pad, max(xs) + pad]
    ylim = p.get("ylim") or [min(ys) - pad, max(ys) + pad]
    n = int(nx or p.get("nx", 41))
    ws = net.worst_touch_step(xlim, ylim, n, n, float(p.get("step_distance", 1.0)),
                              p.get("touch_box"), float(p.get("touch_margin", 1.0)),
                              zones=p.get("zones") or None, refine=refine)
    return dict(net=net, sol=sol, ws=ws, Rg=float(sol["Rg"]), GPR=float(sol["GPR"]),
                touch=float(ws["touch_max"]), step=float(ws["step_max"]),
                segments=len(net.segments), xlim=xlim, ylim=ylim)


def _summary(args) -> dict:
    """run_case for a worker process: the numbers, without the network."""
    q, target, nx, grade = args
    r = run_case(q, target, nx=nx, grade=grade)
    ws = r["ws"]
    return dict(Rg=r["Rg"], GPR=r["GPR"], touch=r["touch"], step=r["step"],
                segments=r["segments"],
                ws=dict(touch_at=ws["touch_at"], step_at=ws["step_at"],
                        step_direction_deg=ws.get("step_direction_deg", 0.0)))


# Summaries of solved cases, so that the studies reuse each other's work
# (1.8.7): the "as measured" case of the seasonal study is the coarse case
# of the convergence study, and either is reused when the study is run
# again with nothing changed.  Keyed by everything the case depends on.
_RUN_KEYS = SOIL_KEYS + ("IG", "conductor_radius", "items", "max_segments", "margin",
                         "xlim", "ylim", "step_distance", "touch_box", "touch_margin", "zones")
_SUMMARIES = {}
_SUMMARY_ORDER = []
_SUMMARY_SIZE = 48


def _summary_key(args) -> str:
    import hashlib
    import json
    q, target, nx, grade = args
    t = float(target if target is not None else q.get("segment_length", 2.5))
    # only what build_network and run_case read: the study's own settings
    # (the seasonal factors, say) do not change the case
    blob = json.dumps(dict(q={k: q.get(k) for k in _RUN_KEYS}, t=t, nx=int(nx or q.get("nx", 41)),
                           g=bool(q.get("grade_ends", True)) if grade is None else bool(grade)),
                      sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def summaries(arg_list) -> list:
    """_summary for each argument tuple, from the store where the same case
    has been solved before, the rest on the worker processes."""
    keys = [_summary_key(a) for a in arg_list]
    todo = [i for i, k in enumerate(keys) if k not in _SUMMARIES]
    # the same case twice in one call is solved once
    first = {}
    for i in todo:
        first.setdefault(keys[i], i)
    uniq = sorted(first.values())
    for i, r in zip(uniq, parallel.pmap(_summary, [arg_list[i] for i in uniq])):
        _SUMMARIES[keys[i]] = r
        _SUMMARY_ORDER.append(keys[i])
    while len(_SUMMARY_ORDER) > _SUMMARY_SIZE:
        _SUMMARIES.pop(_SUMMARY_ORDER.pop(0), None)
    return [dict(_SUMMARIES[k], reused=(i not in uniq)) for i, k in enumerate(keys)]


def clear_summaries():
    _SUMMARIES.clear()
    _SUMMARY_ORDER.clear()


# ---------------------------------------------------------------------------
# Discretisation error
# ---------------------------------------------------------------------------

def convergence(p: dict, base: dict | None = None) -> dict:
    """Solve with segments of h and h/2 and estimate the converged values.

    For a first-order method the error falls in proportion to h, so the
    converged value is about f(h/2) + [f(h/2) − f(h)] (Richardson).  The
    observed order on the IEEE 80 Annex B grid is between 0.5 and 1, so
    assuming 1 gives a correction that is, if anything, too small; the
    verdict therefore takes the largest of f(h), f(h/2) and the estimate.
    """
    h = float(p.get("segment_length", 2.5))
    nx = int(p.get("nx", 41))
    if base:
        a, b = base, summaries([(p, h / 2.0, nx, None)])[0]
    else:
        a, b = summaries([(p, h, nx, None), (p, h / 2.0, nx, None)])
    out = dict(h=h, h_half=h / 2.0, segments=[a["segments"], b["segments"]],
               reused=[bool(a.get("reused", base is not None)), bool(b.get("reused"))])
    worst = 0.0
    for k in ("Rg", "GPR", "touch", "step"):
        f1, f2 = a[k], b[k]
        est = f2 + (f2 - f1)
        ch = (f2 - f1) / f2 * 100.0 if f2 else 0.0
        out[k] = dict(coarse=f1, fine=f2, extrapolated=est, change_pct=ch,
                      design=max(f1, f2, est) if k in ("touch", "step") else est)
        if k in ("touch", "step"):
            worst = max(worst, abs(ch))
    out["max_change_pct"] = worst
    out["converged"] = worst <= 2.0
    out["note"] = (
        f"Halving the segments from {h:g} m to {h / 2:g} m changed the touch voltage by "
        f"{out['touch']['change_pct']:+.1f} % and the step voltage by "
        f"{out['step']['change_pct']:+.1f} %. "
        + ("The solution is converged to within 2 %." if out["converged"] else
           "That is more than 2 %: the checks use the largest of the two solutions and "
           "the Richardson estimate, and a shorter segment length is advisable."))
    return out


# ---------------------------------------------------------------------------
# Seasonal variation
# ---------------------------------------------------------------------------

def _layers_of(p: dict):
    """(rho list, thickness list) of the payload's soil."""
    rho = [float(p["rho1"])]
    h = []
    for rk, hk in (("rho2", "h_layer"), ("rho3", "h_layer2"), ("rho4", "h_layer3")):
        if p.get(rk) not in (None, "") and p.get(hk) not in (None, ""):
            rho.append(float(p[rk]))
            h.append(float(p[hk]))
        else:
            break
    return rho, h


def _with_layers(p: dict, rho, h) -> dict:
    q = {k: v for k, v in p.items() if k not in SOIL_KEYS}
    keys = (("rho2", "h_layer"), ("rho3", "h_layer2"), ("rho4", "h_layer3"))
    q["rho1"] = rho[0]
    for i, (rk, hk) in enumerate(keys):
        if i + 1 < len(rho):
            q[rk] = rho[i + 1]
            q[hk] = h[i]
    return q


def seasonal_soils(p: dict, dry_factor: float = 2.0, dry_depth: float = 1.0,
                   frozen_rho: float | None = None, frozen_depth: float = 0.0):
    """The soil as measured, plus a dry-season and an optional frozen case.

    The dry case multiplies the resistivity of the soil above `dry_depth`
    by `dry_factor` (IEEE Std 80-2013 §13.4 and IEEE Std 81 §7.3: moisture
    near the surface varies with the season; the survey is a snapshot).  The
    frozen case puts a layer of `frozen_rho` over the top `frozen_depth`.
    Each modified profile is collapsed back to at most four layers."""
    rho, h = _layers_of(p)
    depths = list(np.cumsum(h)) if h else []

    def overlay(top_rho_fn, d):
        if d <= 0:
            return None
        bounds = [0.0] + depths + [math.inf]
        iv = []                                   # (top, bottom, rho)
        for i, r in enumerate(rho):
            t, bt = bounds[i], bounds[i + 1]
            if t < d < bt:
                iv.append((t, d, top_rho_fn(r)))
                iv.append((d, bt, r))
            elif bt <= d:
                iv.append((t, bt, top_rho_fn(r)))
            else:
                iv.append((t, bt, r))
        merged = [list(iv[0])]
        for t, bt, r in iv[1:]:
            if abs(r - merged[-1][2]) <= 1e-9 * r:
                merged[-1][1] = bt
            else:
                merged.append([t, bt, r])
        # at most four layers: merge the pair below the top with the least contrast
        while len(merged) > 4:
            k = min(range(1, len(merged) - 1),
                    key=lambda i: abs(math.log(merged[i][2] / merged[i + 1][2])))
            a_, b_ = merged[k], merged[k + 1]
            if b_[1] == math.inf:
                a_[2] = b_[2]
            else:
                ta, tb = a_[1] - a_[0], b_[1] - b_[0]
                a_[2] = math.exp((ta * math.log(a_[2]) + tb * math.log(b_[2])) / (ta + tb))
            a_[1] = b_[1]
            merged.pop(k + 1)
        return [float(m[2]) for m in merged], [float(m[1] - m[0]) for m in merged[:-1]]

    cases = [dict(name="As measured", rho=rho, h=h)]
    dry = overlay(lambda r: r * float(dry_factor), float(dry_depth))
    if dry and float(dry_factor) != 1.0:
        cases.append(dict(name=f"Dry season (top {dry_depth:g} m × {dry_factor:g})",
                          rho=dry[0], h=dry[1]))
    if frozen_rho and frozen_depth and float(frozen_depth) > 0:
        fr = overlay(lambda r: float(frozen_rho), float(frozen_depth))
        if fr:
            cases.append(dict(name=f"Frozen top {frozen_depth:g} m at {float(frozen_rho):g} Ω·m",
                              rho=fr[0], h=fr[1]))
    return cases


def seasonal(p: dict, base: dict | None = None) -> dict:
    s = p.get("seasonal") or {}
    cases = seasonal_soils(p, float(s.get("dry_factor", 2.0)), float(s.get("dry_depth", 1.0)),
                           s.get("frozen_rho"), float(s.get("frozen_depth", 0.0) or 0.0))
    out = []
    todo = [i for i in range(len(cases)) if not (i == 0 and base)]
    # the measured case is solved with the payload itself, so that it is the
    # same case (and the same stored solution) as the convergence study's
    solved = dict(zip(todo, summaries(
        [((p if i == 0 else _with_layers(p, cases[i]["rho"], cases[i]["h"])), None,
          int(p.get("nx", 41)), None) for i in todo])))
    for i, c in enumerate(cases):
        r = base if (i == 0 and base) else solved[i]
        out.append(dict(name=c["name"], rho=c["rho"], h=c["h"], Rg=r["Rg"], GPR=r["GPR"],
                        touch=r["touch"], step=r["step"],
                        touch_at=r["ws"]["touch_at"], step_at=r["ws"]["step_at"]))
    worst = dict(touch=max(out, key=lambda c: c["touch"])["name"],
                 step=max(out, key=lambda c: c["step"])["name"],
                 Rg=max(out, key=lambda c: c["Rg"])["name"])
    return dict(cases=out, worst=worst,
                note=("The survey is one moment of the year. A dry top layer raises R_g and the "
                      "GPR; whether it raises the touch voltage depends on how much of the "
                      "potential is carried by the surface soil — which is why the case is "
                      "computed rather than assumed. Use the worst case for the design."))


# ---------------------------------------------------------------------------
# Soil uncertainty → design uncertainty
# ---------------------------------------------------------------------------

def _norm_ppf(u):
    """Inverse of the standard normal distribution (Acklam's rational
    approximation, relative error < 1.2e-9), vectorised; no scipy needed."""
    u = np.clip(np.asarray(u, float), 1e-12, 1 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    lo, hi = 0.02425, 1 - 0.02425
    x = np.empty_like(u)
    m = u < lo
    q = np.sqrt(-2 * np.log(u[m]))
    x[m] = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
        ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    m2 = u > hi
    q = np.sqrt(-2 * np.log(1 - u[m2]))
    x[m2] = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
        ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    mc = ~(m | m2)
    q = u[mc] - 0.5
    r = q * q
    x[mc] = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    return x


def latin_hypercube_normal(n: int, dim: int, rng) -> "np.ndarray":
    """n × dim standard normal draws, one in each of n equal-probability
    strata of every dimension (Latin hypercube sampling, McKay et al. 1979)."""
    U = np.empty((n, dim))
    for j in range(dim):
        U[:, j] = (rng.permutation(n) + rng.random(n)) / n
    return _norm_ppf(U)


def wilson_interval(k: int, n: int, z: float = 1.959964) -> tuple:
    """95 % confidence interval of a proportion k/n (Wilson score interval)."""
    if n <= 0:
        return (0.0, 1.0)
    ph = k / n
    den = 1 + z * z / n
    cen = (ph + z * z / (2 * n)) / den
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (max(0.0, cen - half), min(1.0, cen + half))


def soil_samples(fit: dict, n: int, seed: int = 1, cap_sd: float = math.log(3.0),
                 method: str = "lhs"):
    """Draw soil models from the fitted model's linearised covariance.

    `fit` is the result of /api/soil/invert.  The parameters are sampled in
    logarithms (they are log-normal in the fit); a parameter the readings
    do not resolve has its standard deviation capped at a factor of three,
    and the sample is flagged.  `method` 'lhs' (default since 1.8.3) draws a
    Latin hypercube — every parameter covers its whole distribution evenly
    even with 20 samples — and 'random' plain random sampling."""
    rng = np.random.default_rng(seed)
    U = fit.get("uncertainty") or {}
    nl = int(fit.get("n_layers", 2))
    if nl >= 3:
        names = U.get("names")
        par = U.get("params") or {}
        corr = np.array(U.get("corr") or np.eye(len(names)))
        sd = np.array([min(float(par[nm]["sd_log"]), cap_sd) for nm in names])
        mu = np.log([float(par[nm]["value"]) for nm in names])
        capped = [nm for nm in names if float(par[nm]["sd_log"]) > cap_sd]
    else:
        names = ["rho1", "rho2", "h1"]
        keys = ["rho1", "rho2", "h"]
        if not U:
            raise ValueError("The soil fit carries no uncertainty (it needs at least "
                             "four readings for a two-layer model).")
        sdp = [float(U[k]["sd_pct"]) / 100.0 for k in keys]
        sd = np.array([min(s, cap_sd) for s in sdp])
        mu = np.log([float(U[k]["value"]) for k in keys])
        corr = np.eye(3)
        c = U.get("corr_rho1_h")
        if c is not None:
            corr[0, 2] = corr[2, 0] = float(c)
        if U.get("corr"):
            corr = np.array(U["corr"])
        capped = [k for k, s in zip(keys, sdp) if s > cap_sd]
    C = corr * np.outer(sd, sd)
    # nearest positive semi-definite
    w, V = np.linalg.eigh(0.5 * (C + C.T))
    C = (V * np.maximum(w, 0.0)) @ V.T
    if method == "lhs":
        w2, V2 = np.linalg.eigh(C)
        Lm = V2 * np.sqrt(np.maximum(w2, 0.0))
        X = mu[None, :] + latin_hypercube_normal(int(n), len(mu), rng) @ Lm.T
    elif method == "random":
        X = rng.multivariate_normal(mu, C, size=int(n))
    else:
        raise ValueError("Sampling method must be 'lhs' or 'random'.")
    m = (len(mu) + 1) // 2
    out = []
    for x in X:
        v = np.exp(x)
        out.append(dict(rho=[float(t) for t in v[:m]], h=[float(t) for t in v[m:]]))
    return out, capped


def _mc_sample(args) -> dict:
    """One soil sample of the uncertainty study (a worker-process task): the
    model solved in full, its maxima searched around the fitted model's."""
    p, s, ta, sa = args
    st = float(p.get("step_distance", 1.0))
    margin = float(p.get("touch_margin", 1.0))
    zones = p.get("zones") or None
    q = _with_layers(p, s["rho"], s["h"])
    net = bem.build_network(q)
    net.discretise(float(p.get("segment_length", 2.5)), int(p.get("max_segments", bem.MAX_SEGMENTS)),
                   grade_ends=bool(p.get("grade_ends", True)))
    sol = net.solve()
    tops = net._metal_tops()
    if zones:
        inside = lambda px, py: np.any([((px >= min(z["x0"], z["x1"])) & (px <= max(z["x0"], z["x1"]))
                                         & (py >= min(z["y0"], z["y1"])) & (py <= max(z["y0"], z["y1"])))
                                        for z in zones], axis=0)
    else:
        inside = lambda px, py: net.touch_region(px, py, margin)

    def ft(P):
        ok = inside(P[:, 0], P[:, 1])
        return np.where(ok, net.V - net._surf(P[:, 0], P[:, 1]), -1e30)

    def fs(P):
        return net._step(P[:, 0], P[:, 1], P[:, 2], st, tops)
    _, tv = bem.Network._climb(ft, ta, [0.5, 0.5], 2, [0.05, 0.05])
    _, sv = bem.Network._climb(fs, sa, [0.5, 0.5, math.pi / 16], 3,
                               [0.05, 0.05, math.radians(2.0)])
    return dict(Rg=float(sol["Rg"]), GPR=float(sol["GPR"]), touch=float(tv),
                step=float(sv), rho=s["rho"], h=s["h"])


def monte_carlo(p: dict, fit: dict, n: int = 24, seed: int = 1, method: str = "lhs") -> dict:
    """Carry the soil model's uncertainty through the numerical solution.

    Each sample is a complete soil model drawn from the fit's covariance;
    the electrodes are solved in it, and the spread of R_g, GPR and the
    touch and step voltages is reported with the probability that each
    stays within its limit.  In uniform soil every voltage is proportional
    to ρ, so the samples are scaled from one solution instead of re-solved.
    """
    lim = p.get("limits") or {}
    samples, capped = soil_samples(fit, n, seed, method=method)
    nx = int(p.get("mc_nx", 41))
    res = []
    if all(len(s["rho"]) == 1 for s in samples):
        base = run_case(_with_layers(p, [1.0], []), nx=nx)
        for s in samples:
            r = s["rho"][0]
            res.append(dict(Rg=base["Rg"] * r, GPR=base["GPR"] * r,
                            touch=base["touch"] * r, step=base["step"] * r))
    else:
        # The worst touch and step points move little between soil models
        # drawn from one fit, so each sample is solved in full but searched
        # only around the points found for the fitted model (a local compass
        # search from there), which costs a few dozen field evaluations
        # instead of a whole surface scan.
        base = run_case(p, nx=nx)
        ta = base["ws"]["touch_at"]
        sa = base["ws"]["step_at"] + [math.radians(base["ws"].get("step_direction_deg", 0.0))]
        res = parallel.pmap(_mc_sample, [(p, smp, ta, sa) for smp in samples])

    def stats(key):
        v = np.array([r[key] for r in res])
        return dict(mean=float(v.mean()), sd=float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                    p05=float(np.percentile(v, 5)), p50=float(np.percentile(v, 50)),
                    p95=float(np.percentile(v, 95)), min=float(v.min()), max=float(v.max()))

    out = dict(n=len(res), samples=res,
               stats={k: stats(k) for k in ("Rg", "GPR", "touch", "step")},
               capped=capped)
    pt = ps = None
    if lim.get("E_touch"):
        pt = float(np.mean([r["touch"] <= float(lim["E_touch"]) for r in res]))
    if lim.get("E_step"):
        ps = float(np.mean([r["step"] <= float(lim["E_step"]) for r in res]))
    both = None
    if lim.get("E_touch") and lim.get("E_step"):
        both = float(np.mean([r["touch"] <= float(lim["E_touch"]) and
                              r["step"] <= float(lim["E_step"]) for r in res]))
    out.update(p_touch=pt, p_step=ps, p_pass=both, method=method)
    nn = len(res)
    ci = {}
    for key, pv in (("p_touch", pt), ("p_step", ps), ("p_pass", both)):
        if pv is not None:
            lo, hi = wilson_interval(int(round(pv * nn)), nn)
            ci[key] = [lo, hi]
    out["ci95"] = ci
    # confidence that the largest sample lies above the true 95th percentile
    out["conf_max_above_p95"] = 1.0 - 0.95 ** nn
    hw = None
    if both is not None:
        lo, hi = ci["p_pass"]
        hw = 0.5 * (hi - lo)
        pp = min(max(both, 0.05), 0.95)
        out["samples_for_5pct"] = int(math.ceil(1.959964 ** 2 * pp * (1 - pp) / 0.05 ** 2))
    out["note"] = (
        f"{nn} soil models drawn from the fit's covariance (log-normal parameters, "
        + ("Latin hypercube" if method == "lhs" else "random") + " sampling). "
        + (f"The readings do not resolve {', '.join(capped)}; its spread was capped at a "
           "factor of three, so the true spread may be wider. " if capped else "")
        + (f"The probability of meeting both limits is {100 * both:.0f} % "
           f"(95 % confidence {100 * ci['p_pass'][0]:.0f}–{100 * ci['p_pass'][1]:.0f} %); "
           f"about {out['samples_for_5pct']} samples would narrow it to ±5 %. "
           if both is not None else "")
        + "The 95th percentiles are the design values; with "
        f"{nn} samples the largest one exceeds the true 95th percentile with "
        f"{100 * out['conf_max_above_p95']:.0f} % confidence (59 samples give 95 %).")
    return out


# ---------------------------------------------------------------------------
# Grid optimisation with the numerical solver
# ---------------------------------------------------------------------------

def _grid_items(Lx, Ly, n, g, depth, radius, rods, rod_length, rod_radius, x0=0.0, y0=0.0):
    """A graded grid with n lines along the longer side (count scaled on the
    shorter) and, optionally, rods round the perimeter at the line ends."""
    long_ = max(Lx, Ly)
    nx = n if Lx >= Ly else max(2, int(round((n - 1) * Lx / long_)) + 1)
    ny = n if Ly > Lx else max(2, int(round((n - 1) * Ly / long_)) + 1)
    items = [dict(kind="grid", Lx=Lx, Ly=Ly, D=long_ / (n - 1), depth=depth,
                  radius=radius, n_x=nx, n_y=ny, grading=g, x0=x0, y0=y0)]
    nrod = 0
    if rods:
        xs = [x0 + Lx * bem.graded_fraction(j / (nx - 1), g) for j in range(nx)]
        ys = [y0 + Ly * bem.graded_fraction(i / (ny - 1), g) for i in range(ny)]
        pts = set()
        step = max(1, int(rods))
        for j in range(0, nx, step):
            pts.add((round(xs[j], 6), y0)); pts.add((round(xs[j], 6), y0 + Ly))
        for i in range(0, ny, step):
            pts.add((x0, round(ys[i], 6))); pts.add((x0 + Lx, round(ys[i], 6)))
        for (x, y) in (( x0, y0), (x0 + Lx, y0), (x0, y0 + Ly), (x0 + Lx, y0 + Ly)):
            pts.add((x, y))
        for x, y in sorted(pts):
            items.append(dict(kind="rod", x=x, y=y, top_depth=depth, length=rod_length,
                              radius=rod_radius))
        nrod = len(pts)
    cond = nx * Ly + ny * Lx
    return items, dict(n_x=nx, n_y=ny, conductor_m=cond, rods=nrod,
                       rod_m=nrod * rod_length)


def optimise_grid(p: dict) -> dict:
    """Cheapest grid that meets the touch and step limits.

    Searched over: the number of conductors (upwards from the sparsest grid,
    then bisection — fewer conductors give higher mesh voltages; a grid that
    already costs more than the best design so far is not solved), the grading of their spacing (uniform, and
    two degrees of compression towards the edges) and rods at every second
    perimeter line end or none.  Cost is conductor metres × c_cond + rod
    metres × c_rod (relative costs, default 1 and 1.5 per metre).
    """
    lim = p.get("limits") or {}
    if not (lim.get("E_touch") and lim.get("E_step")):
        raise ValueError("The optimisation needs the tolerable touch and step voltages: "
                         "run the substation grid page first or enter them.")
    Et, Es = float(lim["E_touch"]), float(lim["E_step"])
    Lx, Ly = float(p["Lx"]), float(p["Ly"])
    depth = float(p.get("depth", 0.5))
    radius = float(p.get("conductor_radius", 0.005))
    rod_length = float(p.get("rod_length", 3.0))
    rod_radius = float(p.get("rod_radius", 0.008))
    c_cond = float(p.get("cost_conductor", 1.0))
    c_rod = float(p.get("cost_rod", 1.5))
    gradings = p.get("gradings") or [0.0, 0.35, 0.6]
    rod_opts = p.get("rod_options") or [0, 2]
    n_min = int(p.get("n_min", 3))
    n_max = int(p.get("n_max", max(4, int(math.ceil(max(Lx, Ly) / 2.0)) + 1)))
    soil = soil_spec(p)
    seg = float(p.get("segment_length", 2.5))
    tried = []

    nxp = int(p.get("nx", 31))

    def case(n, g, rods):
        items, info = _grid_items(Lx, Ly, n, g, depth, radius, rods, rod_length, rod_radius)
        q = dict(soil)
        q.update(IG=float(p.get("IG", 1000.0)), items=items, conductor_radius=radius,
                 segment_length=min(seg, 0.5 * max(Lx, Ly) / (n - 1)), grade_ends=True,
                 nx=nxp, touch_margin=float(p.get("touch_margin", 1.0)),
                 zones=p.get("zones"))
        return items, info, q

    def evaluate_batch(jobs):
        """Solve the candidates (n, g, rods) of one round, on worker
        processes where available (1.8.4), and record them."""
        built = [case(*j) for j in jobs]
        res = parallel.pmap(_summary, [(q, None, nxp, True) for _, _, q in built])
        rows = []
        for (n, g, rods), (items, info, _), r in zip(jobs, built, res):
            cost = info["conductor_m"] * c_cond + info["rod_m"] * c_rod
            row = dict(n=n, grading=g, rods_every=rods, **info, Rg=r["Rg"], GPR=r["GPR"],
                       touch=r["touch"], step=r["step"], cost=cost,
                       ok=r["touch"] <= Et and r["step"] <= Es, items=items)
            tried.append(row)
            rows.append(row)
        return rows

    def cost_of(n, g, rods):
        info = _grid_items(Lx, Ly, n, g, depth, radius, rods, rod_length, rod_radius)[1]
        return info["conductor_m"] * c_cond + info["rod_m"] * c_rod

    # Each combination of grading and rods is searched upwards from the
    # sparsest grid (x1.4 per step) and its last bracket bisected: the cheap,
    # coarse grids are the fast ones to solve, and no grid that already costs
    # more than the best passing design found so far is solved at all
    # (1.8.1; up to 1.8.0 the densest grid of every combination was solved
    # first).  Since 1.8.4 the combinations advance together, one candidate
    # each per round, and a round's candidates are solved in parallel.
    best = None
    pruned = 0
    combos = [dict(g=g, rods=rods, last_fail=n_min - 1, n=n_min, ok=None, phase="up")
              for g in sorted(gradings, reverse=True) for rods in sorted(rod_opts, reverse=True)]
    while True:
        jobs, owners = [], []
        for c in combos:
            if c["phase"] == "done":
                continue
            if c["phase"] == "up":
                n = c["n"]
                if n > n_max or (best is not None and cost_of(n, c["g"], c["rods"]) >= best["cost"]):
                    if best is not None and n <= n_max:
                        pruned += 1
                    c["phase"] = "done"
                    continue
            else:                                       # bisect
                if c["hi"] - c["lo"] <= 1:
                    c["phase"] = "done"
                    continue
                n = (c["lo"] + c["hi"]) // 2
            jobs.append((n, c["g"], c["rods"]))
            owners.append(c)
        if not jobs:
            break
        for c, row in zip(owners, evaluate_batch(jobs)):
            n = row["n"]
            if row["ok"] and (best is None or row["cost"] < best["cost"]):
                best = row
            if c["phase"] == "up":
                if row["ok"]:
                    c["ok"] = row
                    c.update(phase="bisect", lo=c["last_fail"], hi=n)
                else:
                    c["last_fail"] = n
                    c["n"] = n_max + 1 if n >= n_max else min(n_max, max(n + 1, int(math.ceil(n * 1.4))))
            else:
                if row["ok"]:
                    c["hi"], c["ok"] = n, row
                else:
                    c["lo"] = n
    table = sorted(({k: v for k, v in r.items() if k != "items"} for r in tried),
                   key=lambda r: (not r["ok"], r["cost"]))
    out = dict(limits=dict(E_touch=Et, E_step=Es), tried=table, evaluations=len(tried),
               pruned=pruned)
    if best is None:
        out["feasible"] = False
        out["note"] = ("No grid in the search range meets both limits. Raise the largest "
                       "number of conductors, add a surface layer (higher tolerable "
                       "voltages), lengthen the rods or enlarge the area.")
        return out
    uni = [r for r in tried if r["ok"] and r["grading"] == 0.0 and r["rods_every"] == best["rods_every"]]
    if not uni and best["grading"] > 0 and 0.0 in gradings:
        # the uniform grid was pruned; find its cheapest passing size so
        # that the saving of unequal spacing can still be stated
        last_fail, n, hit = best["n"] - 1, best["n"], None
        while n <= n_max:
            r = evaluate_batch([(n, 0.0, best["rods_every"])])[0]
            if r["ok"]:
                hit = r
                break
            last_fail = n
            if n == n_max:
                break
            n = min(n_max, max(n + 1, int(math.ceil(n * 1.4))))
        if hit is not None:
            lo, hi = last_fail, hit["n"]
            while hi - lo > 1:
                mid = (lo + hi) // 2
                r = evaluate_batch([(mid, 0.0, best["rods_every"])])[0]
                if r["ok"]:
                    hi, hit = mid, r
                else:
                    lo = mid
            uni = [hit]
        out["tried"] = sorted(({k: v for k, v in r.items() if k != "items"} for r in tried),
                              key=lambda r: (not r["ok"], r["cost"]))
        out["evaluations"] = len(tried)
    out.update(feasible=True, best={k: v for k, v in best.items() if k != "items"},
               items=best["items"])
    if uni and best["grading"] > 0:
        u = min(uni, key=lambda r: r["cost"])
        out["saving_vs_uniform_pct"] = 100.0 * (1.0 - best["cost"] / u["cost"])
    out["note"] = (f"Best of {len(tried)} numerical solutions: {best['n_x']} × {best['n_y']} "
                   f"conductors, grading {best['grading']:g}"
                   + (f", {best['rods']} rods of {rod_length:g} m" if best["rods"] else ", no rods")
                   + f"; touch {best['touch']:.0f} V of {Et:.0f} V, step {best['step']:.0f} V "
                     f"of {Es:.0f} V.")
    return out
