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


def schlumberger_two_layer(s_half: float, rho1: float, rho2: float, h: float,
                           mn: float | None = None) -> float:
    """Apparent resistivity seen by a Schlumberger array (AB/2 = s_half).

    With ``mn`` (the potential-electrode separation MN) the exact finite-MN
    expression is used (tutorial Eq. 2.9):

        rho_a = rho1 [1 + (s^2 - d^2/4)/d * 2 sum K^n (1/R(s - d/2) - 1/R(s + d/2))],
        R(x) = sqrt(x^2 + (2 n h)^2),  d = MN.

    Without it (or MN -> 0) the ideal gradient array is used,

        rho_a = rho1 [1 + 2 sum K^n / (1 + (2nh/s)^2)^1.5].

    Version 1.3.1 always used the ideal form even though MN is an input of
    the data reduction; the ideal form is then wrong by up to about 3 % for
    MN = AB/10, 11 % for MN = AB/5 and 28 % for MN = AB/3 (the Wenner
    geometry), always in the transition between the layers.
    """
    if rho1 <= 0 or rho2 <= 0 or h <= 0:
        return float("nan")
    K = (rho2 - rho1) / (rho2 + rho1)
    d = float(mn) if mn else 0.0
    exact = 0.0 < d < 2.0 * s_half and d > 1e-6 * s_half
    acc = 0.0
    Kn = 1.0
    if exact:
        xm, xp = s_half - d / 2.0, s_half + d / 2.0
        geom = (s_half * s_half - d * d / 4.0) / d
    for n in range(1, MAX_IMAGES + 1):
        Kn *= K
        if abs(Kn) < SERIES_TOL:
            break
        z = 2.0 * n * h
        if exact:
            acc += Kn * (1.0 / math.hypot(xm, z) - 1.0 / math.hypot(xp, z))
        else:
            u = z / s_half
            acc += Kn / (1.0 + u * u) ** 1.5
    return rho1 * (1.0 + 2.0 * (geom if exact else 1.0) * acc)


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
                     array: str = "wenner",
                     mn: Sequence[float] | None = None) -> dict:
    """Least-squares fit of a two-layer earth to measured apparent resistivity.

    Parameters are optimised in log space so that rho1, rho2 and h stay
    positive without needing a constrained optimiser.  Several starting
    points are tried to reduce the chance of a local minimum.

    Returns a dict with rho1, rho2, h, K, rms_pct, fitted curve and residuals.
    """
    base = FORWARD.get(array, wenner_two_layer)
    xs = [float(s) for s in spacings]
    mns = None
    if array == "schlumberger" and mn is not None:
        mns = [float(m) if m else 0.0 for m in mn]
        if len(mns) != len(xs):
            raise ValueError("One MN value is needed per Schlumberger reading.")
    # MN for the smooth plotting curve: the ratio MN/(AB/2) of the nearest reading
    ratios = [(x, m / x if x else 0.0) for x, m in zip(xs, mns)] if mns else []

    def fwd(a, r1, r2, hh, d=None):
        if not mns:
            return base(a, r1, r2, hh)
        if d is None:
            near = min(ratios, key=lambda t: abs(math.log(t[0] / a)))
            d = near[1] * a
        return base(a, r1, r2, hh, d)

    per_mn = mns if mns else [None] * len(xs)
    ys = [float(r) for r in rho_app]
    if len(xs) < 3:
        raise ValueError("At least three measurement points are required.")

    def objective(p):
        r1, r2, hh = math.exp(p[0]), math.exp(p[1]), math.exp(p[2])
        acc = 0.0
        for a, y, d in zip(xs, ys, per_mn):
            m = fwd(a, r1, r2, hh, d)
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
    fitted = [fwd(a, rho1, rho2, h, d) for a, d in zip(xs, per_mn)]
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

    fq = fit_quality(xs, ys, resid, rms)
    unc = _linearised_uncertainty(fwd, xs, per_mn, best_p, best_f)
    return dict(rho1=rho1, rho2=rho2, h=h, K=K, rms_pct=rms,
                uncertainty=unc,
                fitted=fitted, residual_pct=resid, array=array,
                finite_mn=bool(mns),
                curve_x=curve_x, curve_y=curve_y,
                spacings=xs, measured=ys, **fq)



def _linearised_uncertainty(fwd, xs, mns, p, phi_min) -> dict | None:
    """Linearised (Gauss-Newton) covariance of the fitted parameters.

        C = s^2 (J^T J)^-1,   s^2 = Phi_min / (N - 3),
        J_ij = d ln rho_a(a_i) / d ln p_j,   p = (rho1, rho2, h)

    (tutorial Eq. 2.12).  Returns one-standard-deviation ranges, the relative
    standard deviations and the correlation of rho1 with h, which is the
    equivalence of the two-layer fit expressed as one number.  None when
    there are no spare degrees of freedom (three readings) or J is singular.
    """
    n = len(xs)
    if n <= 3:
        return None
    eps = 1e-5
    J = []
    try:
        for a, d in zip(xs, mns):
            row = []
            for j in range(3):
                up = list(p); dn = list(p)
                up[j] += eps; dn[j] -= eps
                fu = fwd(a, *(math.exp(v) for v in up), d)
                fd = fwd(a, *(math.exp(v) for v in dn), d)
                row.append((math.log(fu) - math.log(fd)) / (2 * eps))
            J.append(row)
    except (ValueError, ZeroDivisionError):
        return None
    JtJ = [[sum(J[i][r] * J[i][c] for i in range(n)) for c in range(3)] for r in range(3)]
    # 3 x 3 inverse by cofactors
    m = JtJ
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
           - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    if abs(det) < 1e-14:
        return None
    inv = [[0.0] * 3 for _ in range(3)]
    for r in range(3):
        for c in range(3):
            rows = [i for i in range(3) if i != c]
            cols = [k for k in range(3) if k != r]
            minor = (m[rows[0]][cols[0]] * m[rows[1]][cols[1]]
                     - m[rows[0]][cols[1]] * m[rows[1]][cols[0]])
            inv[r][c] = (-1) ** (r + c) * minor / det
    s2 = phi_min / (n - 3)
    C = [[s2 * inv[r][c] for c in range(3)] for r in range(3)]
    sd = [math.sqrt(max(C[i][i], 0.0)) for i in range(3)]
    names = ("rho1", "rho2", "h")
    out = dict(method="linearised covariance s²(JᵀJ)⁻¹, tutorial Eq. 2.12",
               dof=n - 3)
    for i, nm in enumerate(names):
        v = math.exp(p[i])
        out[nm] = dict(value=v, sd_pct=100.0 * sd[i],
                       low_68=v * math.exp(-sd[i]), high_68=v * math.exp(sd[i]))
    out["corr_rho1_h"] = C[0][2] / (sd[0] * sd[2]) if sd[0] > 0 and sd[2] > 0 else None
    return out

def fit_quality(xs, ys, resid, rms) -> dict:
    """Judge whether a two-layer model describes the traverse at all.

    A two-layer apparent-resistivity curve is monotonic in the spacing.  A
    curve that falls and then rises (H-type) or rises and then falls
    (K-type) has at least three layers, and the best two-layer fit then
    produces a thin fictitious top layer whose rho1 and h mean nothing
    (tutorial §2.7).  Version 1.1 reported such fits without comment — the
    built-in demo traverse was one, with RMS 12.8 % — and the equivalent
    resistivity derived from them could be passed straight into the grid
    design.
    """
    worst = max((abs(r) for r in resid), default=0.0)
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    yv = [ys[i] for i in order]
    i_min = min(range(len(yv)), key=lambda i: yv[i])
    i_max = max(range(len(yv)), key=lambda i: yv[i])
    three = False
    shape = ""
    excursion = 0.0
    if 0 < i_min < len(yv) - 1:
        rise = min(yv[0], yv[-1]) / yv[i_min] - 1.0
        if rise > 0.10:
            three, shape, excursion = True, "H-type (falls, then rises)", rise
    if 0 < i_max < len(yv) - 1:
        drop = 1.0 - max(yv[0], yv[-1]) / yv[i_max]
        if drop > 0.10 and drop > excursion:
            three, shape, excursion = True, "K-type (rises, then falls)", drop
    if rms <= 3.0 and worst <= 6.0:
        q = "good"
    elif rms <= 5.0 and worst <= 10.0:
        q = "acceptable"
    else:
        q = "poor"
    warn = note = ""
    if q == "poor" or (three and excursion > 0.25):
        warn = (f"The two-layer model does not describe this traverse well "
                f"(RMS {rms:.1f} %, largest residual {worst:.0f} %).")
        if three:
            warn += (f" The curve is {shape} by {100 * excursion:.0f} %, the "
                     f"signature of at least three layers; the fitted ρ₁ and h "
                     f"are then not physical.")
        warn += (" Before using the result, fit the part of the traverse that "
                 "matters for the electrode (spacings comparable with its "
                 "size), check the readings, or use the apparent resistivity "
                 "at a spacing about equal to the grid radius as a first "
                 "estimate.")
    elif three:
        note = (f"The curve is mildly {shape} ({100 * excursion:.0f} %), so a "
                f"third layer is present; the two-layer fit is {q} and usable, "
                f"but compare the residuals at the spacings that matter for "
                f"your electrode.")
    return dict(fit_quality=q, max_residual_pct=worst,
                three_layer_suspected=three, fit_warning=warn, fit_note=note)


# ---------------------------------------------------------------------------
# Equivalent uniform soil
# ---------------------------------------------------------------------------

def disc_factor(K: float, h_over_r: float) -> float:
    """F(K, h/r): resistance of a surface disc of radius r on two-layer soil,
    relative to the same disc on uniform soil of resistivity rho1.

        R_disc = rho1 F / (4 r)
        F = 1 + (4/(pi r)) sum_{n>=1} K^n [ r atan(r/(n h))
                                             - (n h/2) ln(1 + r^2/(n h)^2) ]

    (tutorial Eq. 6.5, the grid analogue of the foot-disc solution of §5.1).
    For n h >> r the bracket tends to r^2/(2 n h), so the tail of the series
    is summed in closed form with  sum K^n/n = -ln(1 - K).
    """
    K = max(-0.9999, min(0.9999, float(K)))
    if abs(K) < 1e-12:
        return 1.0
    q = max(float(h_over_r), 1e-6)          # h / r, with r = 1
    N = int(min(200000, max(400, 40.0 / q)))
    S = 0.0
    part = 0.0                               # sum K^n / n over n <= N
    Kn = 1.0
    for n in range(1, N + 1):
        Kn *= K
        nh = n * q
        S += Kn * (math.atan(1.0 / nh) - 0.5 * nh * math.log1p(1.0 / (nh * nh)))
        part += Kn / n
        if abs(Kn) < 1e-15:
            break
    # closed-form tail:  bracket ~ 1/(2 n q)  for n q >> 1
    tail = (1.0 / (2.0 * q)) * (-math.log(1.0 - K) - part)
    return 1.0 + 4.0 / math.pi * (S + tail)


def equivalent_uniform(rho1: float, rho2: float, h: float,
                       grid_depth: float = 0.5, rod_length: float = 0.0,
                       method: str = "auto", area: float | None = None,
                       total_length: float | None = None) -> dict:
    """Equivalent uniform resistivity for the closed-form IEEE 80 equations.

    method
      'grid'     : rho1 F(K, h/r) with r = sqrt(A/pi) — the resistivity that
                   gives a disc of the grid's area the resistance it has on
                   the two-layer soil (tutorial §6.4).  This is the only rule
                   that looks as deep as the grid's current actually goes: a
                   70 m grid drives its current tens of metres down, however
                   shallow it is buried.  Needs the grid area.  When the
                   total buried length L_T is also given, the conductor
                   term rho1/L_T (the near field, which lies in the upper
                   layer) is kept at rho1:
                       rho = rho1 (F/4r + 1/L_T) / (1/4r + 1/L_T),
                   the ratio of Eq. 6.5 in layered and in uniform soil, so
                   that uniform soil returns rho1 exactly.
                   Without L_T it is the far-field value rho1 F.
      'top'      : rho1 — NOT the conservative choice when rho2 > rho1.
      'weighted' : depth-weighted average over the electrode penetration.
                   Suitable only for small electrodes (a rod or two) whose
                   size is comparable with their depth.
      'auto'     : 'grid' when the area is known, otherwise the old
                   penetration rule with a warning.

    Version 1.1 had no 'grid' rule: 'auto' weighted the layers by the burial
    depth only, which for the IEEE 80 Annex B grid in 2 m of 400 ohm-m put
    the closed-form R_g at +191 % (over 100 ohm-m) and -66 % (over
    1600 ohm-m, unsafe) of the two-layer numerical solution.

    Any other method name is rejected.
    """
    if method not in ("top", "weighted", "auto", "grid"):
        raise ValueError(
            f"Unknown equivalent-resistivity method {method!r}: "
            f"use 'grid', 'top', 'weighted' or 'auto'.")
    depth = max(grid_depth + rod_length, grid_depth)
    has_area = area is not None and float(area) > 0
    if method == "grid" and not has_area:
        raise ValueError("The grid-size rule needs the grid area (m²).")
    K = (rho2 - rho1) / (rho2 + rho1) if (rho1 + rho2) > 0 else 0.0
    out = dict(penetration=depth, method_used=None, K=K)
    if method == "top":
        rho_e, note = rho1, "Top-layer resistivity used."
        out["method_used"] = "top"
    elif method == "grid" or (method == "auto" and has_area):
        A = float(area)
        r = math.sqrt(A / math.pi)
        F = disc_factor(K, h / r)
        out.update(method_used="grid", area=A, r_equiv=r, F=F)
        if total_length and float(total_length) > 0:
            LT = float(total_length)
            ratio = (F / (4.0 * r) + 1.0 / LT) / (1.0 / (4.0 * r) + 1.0 / LT)
            rho_e = rho1 * ratio
            out.update(total_length=LT, ratio=ratio)
            how = (f"the conductor term ρ₁/L_T stays in layer 1, so "
                   f"ρ = ρ₁ (F/4r + 1/L_T)/(1/4r + 1/L_T) = ρ₁ × {ratio:.3f}")
        else:
            rho_e = rho1 * F
            how = "ρ = ρ₁F (far field only; the grid page refines it with L_T)"
        note = (f"Grid-size rule: the grid is treated as a disc of radius "
                f"r = √(A/π) = {r:.1f} m on the two-layer soil; h/r = "
                f"{h / r:.3f} and F(K, h/r) = {F:.3f}; {how}. Unlike a "
                f"depth average, this sees as deep as the grid's current "
                f"goes (about one radius). Checked against the two-layer "
                f"numerical solver for 48 grids (10–70 m, h = 1–30 m, "
                f"ρ₂/ρ₁ = 0.1–25): conservative in every case, typically by "
                f"3–20 %; rods reaching a more conductive layer are not "
                f"credited. Use the numerical solver for the final design.")
        if abs(rho2 / rho1 - 1.0) > 2.0 or abs(rho1 / rho2 - 1.0) > 2.0:
            note += (" The layers differ by more than a factor of three, so "
                     "the numerical solver is strongly recommended.")
    elif method == "weighted" or (method == "auto" and depth > h):
        d1 = min(h, depth)
        d2 = max(0.0, depth - h)
        rho_e = (rho1 * d1 + rho2 * d2) / max(depth, 1e-9)
        out["method_used"] = "weighted"
        note = ("Depth-weighted average over the electrode penetration "
                f"({d1:.2f} m in layer 1, {d2:.2f} m in layer 2). This suits "
                f"small electrodes only — for a grid, give its area so the "
                f"grid-size rule can be used, or run the numerical solver.")
    else:
        rho_e = rho1
        out["method_used"] = "top"
        note = ("Electrodes stay in the upper layer; ρ₁ used. For a grid "
                "this can be badly wrong — give the grid area so the "
                "grid-size rule can be used.")
    out.update(rho_equivalent=rho_e, note=note)
    return out


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
