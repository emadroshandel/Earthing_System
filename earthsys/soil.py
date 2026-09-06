"""
Soil resistivity: field-data reduction and two-layer model inversion.

Implements
----------
* Wenner (4-pin, equal spacing) and Schlumberger apparent-resistivity reduction
* Driven-rod (three-point / fall-of-potential) reduction
* Two-layer forward models (Wenner and Schlumberger) using the classical
  image series with reflection factor K = (rho2 - rho1)/(rho2 + rho1)
* Least-squares inversion for (rho1, rho2, h) with a dependency-free
  Nelder-Mead optimiser
* Equivalent uniform resistivity for use with the IEEE 80 closed-form
  equations (IEEE Std 80-2013, 13.4.2)

References: IEEE Std 81-2012 clause 8; IEEE Std 80-2013 clause 13;
Sunde, "Earth Conduction Effects in Transmission Systems", 1949.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence

MAX_IMAGES = 400          # image-series truncation
SERIES_TOL = 1e-9


# ---------------------------------------------------------------------------
# Field data reduction
# ---------------------------------------------------------------------------

def wenner_rho(R: float, a: float, b: float | None = None) -> float:
    """Apparent resistivity from a Wenner array.

    R : measured resistance V/I (ohm)
    a : electrode spacing (m)
    b : electrode burial depth (m). If None or b << a the simple
        rho = 2*pi*a*R is returned; otherwise the exact expression is used.
    """
    if b is None or b <= 0 or a / max(b, 1e-9) > 20.0:
        return 2.0 * math.pi * a * R
    num = 4.0 * math.pi * a * R
    den = (1.0 + 2.0 * a / math.sqrt(a * a + 4.0 * b * b)
           - 2.0 * a / math.sqrt(4.0 * a * a + 4.0 * b * b))
    return num / den


def schlumberger_rho(R: float, s: float, d: float) -> float:
    """Apparent resistivity from a Schlumberger array.

    R : measured resistance (ohm)
    s : half distance between the outer (current) electrodes, AB/2 (m)
    d : distance between the inner (potential) electrodes, MN (m)
    """
    return math.pi * R * (s * s - (d / 2.0) ** 2) / d


def driven_rod_rho(R: float, L: float, d: float) -> float:
    """Apparent resistivity back-calculated from a driven-rod (3-point) test.

    Inverts the Dwight formula  R = rho/(2*pi*L) * (ln(8L/d) - 1).
    L : rod length in contact with soil (m); d : rod diameter (m)
    """
    return R * 2.0 * math.pi * L / (math.log(8.0 * L / d) - 1.0)


# ---------------------------------------------------------------------------
# Two-layer forward models
# ---------------------------------------------------------------------------

def wenner_two_layer(a: float, rho1: float, rho2: float, h: float) -> float:
    """Apparent resistivity seen by a Wenner array over a two-layer earth."""
    if rho1 <= 0 or rho2 <= 0 or h <= 0:
        return float("nan")
    K = (rho2 - rho1) / (rho2 + rho1)
    s = 0.0
    Kn = 1.0
    for n in range(1, MAX_IMAGES + 1):
        Kn *= K
        if abs(Kn) < SERIES_TOL:
            break
        u = 2.0 * n * h / a
        term = 1.0 / math.sqrt(1.0 + u * u) - 1.0 / math.sqrt(4.0 + u * u)
        s += Kn * term
    return rho1 * (1.0 + 4.0 * s)


def schlumberger_two_layer(s_half: float, rho1: float, rho2: float, h: float) -> float:
    """Apparent resistivity seen by a Schlumberger array (AB/2 = s_half)."""
    if rho1 <= 0 or rho2 <= 0 or h <= 0:
        return float("nan")
    K = (rho2 - rho1) / (rho2 + rho1)
    acc = 0.0
    Kn = 1.0
    for n in range(1, MAX_IMAGES + 1):
        Kn *= K
        if abs(Kn) < SERIES_TOL:
            break
        u = 2.0 * n * h / s_half
        acc += Kn / (1.0 + u * u) ** 1.5
    return rho1 * (1.0 + 2.0 * acc)


FORWARD = {"wenner": wenner_two_layer, "schlumberger": schlumberger_two_layer}


# ---------------------------------------------------------------------------
# Nelder-Mead (dependency free)
# ---------------------------------------------------------------------------

def _nelder_mead(f, x0: Sequence[float], step: Sequence[float],
                 max_iter: int = 3000, tol: float = 1e-10):
    n = len(x0)
    simplex = [list(x0)]
    for i in range(n):
        p = list(x0)
        p[i] += step[i]
        simplex.append(p)
    fv = [f(p) for p in simplex]

    alpha, gamma, rho_c, sigma = 1.0, 2.0, 0.5, 0.5
    for _ in range(max_iter):
        order = sorted(range(n + 1), key=lambda i: fv[i])
        simplex = [simplex[i] for i in order]
        fv = [fv[i] for i in order]
        if abs(fv[-1] - fv[0]) <= tol * (abs(fv[0]) + abs(fv[-1]) + 1e-30):
            break
        centroid = [sum(p[i] for p in simplex[:-1]) / n for i in range(n)]
        xr = [centroid[i] + alpha * (centroid[i] - simplex[-1][i]) for i in range(n)]
        fr = f(xr)
        if fv[0] <= fr < fv[-2]:
            simplex[-1], fv[-1] = xr, fr
            continue
        if fr < fv[0]:
            xe = [centroid[i] + gamma * (xr[i] - centroid[i]) for i in range(n)]
            fe = f(xe)
            simplex[-1], fv[-1] = (xe, fe) if fe < fr else (xr, fr)
            continue
        xc = [centroid[i] + rho_c * (simplex[-1][i] - centroid[i]) for i in range(n)]
        fc = f(xc)
        if fc < fv[-1]:
            simplex[-1], fv[-1] = xc, fc
            continue
        for i in range(1, n + 1):
            simplex[i] = [simplex[0][j] + sigma * (simplex[i][j] - simplex[0][j])
                          for j in range(n)]
            fv[i] = f(simplex[i])
    best = min(range(n + 1), key=lambda i: fv[i])
    return simplex[best], fv[best]


# ---------------------------------------------------------------------------
# Inversion
# ---------------------------------------------------------------------------

def invert_two_layer(spacings: Sequence[float], rho_app: Sequence[float],
                     array: str = "wenner") -> dict:
    """Least-squares fit of a two-layer earth to measured apparent resistivity.

    Parameters are optimised in log space so that rho1, rho2 and h stay
    positive without needing a constrained optimiser.  Several starting
    points are tried to reduce the chance of a local minimum.

    Returns a dict with rho1, rho2, h, K, rms_pct, fitted curve and residuals.
    """
    fwd = FORWARD.get(array, wenner_two_layer)
    xs = [float(s) for s in spacings]
    ys = [float(r) for r in rho_app]
    if len(xs) < 3:
        raise ValueError("At least three measurement points are required.")

    def objective(p):
        r1, r2, hh = math.exp(p[0]), math.exp(p[1]), math.exp(p[2])
        acc = 0.0
        for a, y in zip(xs, ys):
            m = fwd(a, r1, r2, hh)
            if not math.isfinite(m) or m <= 0:
                return 1e30
            acc += ((m - y) / y) ** 2
        return acc

    y_min, y_max = min(ys), max(ys)
    a_min, a_max = min(xs), max(xs)
    starts = []
    for r1 in (ys[0], y_min, 0.5 * (y_min + y_max)):
        for r2 in (ys[-1], y_max, y_min):
            for hh in (0.3 * a_max, 0.8 * a_min + 0.2 * a_max, 1.5 * a_min):
                if r1 > 0 and r2 > 0 and hh > 0:
                    starts.append([math.log(r1), math.log(r2), math.log(hh)])

    best_p, best_f = None, float("inf")
    for s0 in starts:
        p, fval = _nelder_mead(objective, s0, [0.35, 0.35, 0.35])
        if fval < best_f:
            best_p, best_f = p, fval

    rho1, rho2, h = (math.exp(v) for v in best_p)
    fitted = [fwd(a, rho1, rho2, h) for a in xs]
    resid = [(m - y) / y * 100.0 for m, y in zip(fitted, ys)]
    rms = math.sqrt(best_f / len(xs)) * 100.0
    K = (rho2 - rho1) / (rho2 + rho1)

    # smooth curve for plotting
    curve_x, curve_y = [], []
    lo, hi = math.log10(a_min * 0.7), math.log10(a_max * 1.4)
    for i in range(120):
        a = 10 ** (lo + (hi - lo) * i / 119.0)
        curve_x.append(a)
        curve_y.append(fwd(a, rho1, rho2, h))

    return dict(rho1=rho1, rho2=rho2, h=h, K=K, rms_pct=rms,
                fitted=fitted, residual_pct=resid, array=array,
                curve_x=curve_x, curve_y=curve_y,
                spacings=xs, measured=ys)


# ---------------------------------------------------------------------------
# Equivalent uniform soil
# ---------------------------------------------------------------------------

def equivalent_uniform(rho1: float, rho2: float, h: float,
                       grid_depth: float = 0.5, rod_length: float = 0.0,
                       method: str = "auto") -> dict:
    """Equivalent uniform resistivity for the closed-form IEEE 80 equations.

    method
      'top'      : rho1 — note this is NOT the conservative choice when
                   rho2 > rho1: a grid whose plan size greatly exceeds h
                   drives current into the lower layer, so taking rho1
                   under-states Rg, the GPR and the mesh voltage.
      'weighted' : depth-weighted average over the electrode penetration
      'auto'     : weighted when electrodes cross the interface, else rho1

    Any other value is rejected.  A mis-spelt method used to fall through to
    rho1 with the note "electrodes stay in the upper layer" attached, which is
    a wrong number carrying a false explanation.
    """
    if method not in ("top", "weighted", "auto"):
        raise ValueError(
            f"Unknown equivalent-resistivity method {method!r}: "
            f"use 'top', 'weighted' or 'auto'.")
    depth = max(grid_depth + rod_length, grid_depth)
    if method == "top":
        rho_e, note = rho1, "Top-layer resistivity used."
    elif method == "weighted" or (method == "auto" and depth > h):
        d1 = min(h, depth)
        d2 = max(0.0, depth - h)
        rho_e = (rho1 * d1 + rho2 * d2) / max(depth, 1e-9)
        note = ("Depth-weighted average over the electrode penetration "
                f"({d1:.2f} m in layer 1, {d2:.2f} m in layer 2). This is a "
                f"first approximation only — where the two layers differ by "
                f"more than about a factor of three, run the numerical "
                f"solver, which takes the layered soil directly and does not "
                f"need an equivalent value at all.")
    else:
        rho_e, note = rho1, "Electrodes stay in the upper layer; rho1 used."
    return dict(rho_equivalent=rho_e, penetration=depth, note=note)


def reduce_survey(rows: Iterable[dict], array: str = "wenner") -> List[dict]:
    """Convert raw traverse rows into apparent resistivity.

    Each row may supply either 'rho' directly, or 'R', or 'V' and 'I'.
    Wenner rows use key 'a' (spacing); Schlumberger rows use 's' and 'd'.
    """
    out = []
    for r in rows:
        R = r.get("R")
        if R is None and r.get("V") is not None and r.get("I"):
            R = float(r["V"]) / float(r["I"])
        if array == "wenner":
            a = float(r.get("a", r.get("spacing", 0)))
            rho = float(r["rho"]) if r.get("rho") is not None else wenner_rho(
                float(R), a, r.get("b"))
            out.append(dict(spacing=a, R=R, rho=rho))
        else:
            s = float(r.get("s", r.get("spacing", 0)))
            d = float(r.get("d", 1.0))
            rho = float(r["rho"]) if r.get("rho") is not None else schlumberger_rho(
                float(R), s, d)
            out.append(dict(spacing=s, R=R, rho=rho, d=d))
    return out
