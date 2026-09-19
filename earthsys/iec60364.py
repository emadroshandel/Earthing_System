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
Earthing for homes, buildings and LV installations.

Standards implemented
---------------------
* IEC 60364-5-54:2011  -- earthing arrangements, protective conductors,
  protective bonding conductors, earth electrodes
* IEC 60364-4-41:2017  -- protection against electric shock, automatic
  disconnection of supply, maximum disconnection times (Table 41.1)
* BS 7671 (18th Ed.) -- the same requirements with UK-specific maximum
  earth-fault loop impedances

Electrode resistance formulas follow Dwight (1936) and IEEE Std 142 /
IEC 60364-5-54 Annex; the foundation-electrode approximation follows the
customary R ~= 0.2 rho / V^(1/3) relationship used in DIN 18014 practice.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Earth electrode resistance
# ---------------------------------------------------------------------------

def rod(rho: float, L: float, d: float) -> dict:
    """Single vertical rod, Dwight:  R = rho/(2 pi L) (ln(8L/d) - 1)."""
    R = rho / (2.0 * math.pi * L) * (math.log(8.0 * L / d) - 1.0)
    return dict(R=R, type="Vertical rod", L=L, d=d, rho=rho,
                formula="R = ρ/(2πL)·[ln(8L/d) − 1]")


# BS 7430:2011 Table 5 (identical in ENA EREC S34).  Hollow square: rods
# spaced s round the perimeter of a square, m per side, n = 4(m - 1).
BS7430_LAMBDA_LINE = {1: 0.0, 2: 1.00, 3: 1.66, 4: 2.15, 5: 2.54, 6: 2.87,
                      7: 3.15, 8: 3.39, 9: 3.61, 10: 3.81}
BS7430_LAMBDA_HOLLOW = {4: 2.71, 8: 4.51, 12: 5.48, 16: 6.13, 20: 6.63}


def rod_positions_unit(n: int, arrangement: str):
    """Rod positions for spacing s = 1 (used to compute lambda)."""
    if arrangement == "line":
        return [(float(i), 0.0) for i in range(n)]
    if arrangement == "hollow_square":
        # n rods at unit spacing round a square of perimeter n
        per = float(n)
        side = per / 4.0
        pts = []
        for i in range(n):
            t = float(i)
            if t < side:
                pts.append((t, 0.0))
            elif t < 2 * side:
                pts.append((side, t - side))
            elif t < 3 * side:
                pts.append((3 * side - t, side))
            else:
                pts.append((0.0, per - t))
        return pts
    # filled square: m x m lattice (row-major, truncated to n)
    m = max(1, int(math.ceil(math.sqrt(n))))
    return [(float(i % m), float(i // m)) for i in range(n)]


def rod_group_lambda(n: int, arrangement: str = "line"):
    """Group factor lambda of BS 7430 for n equal rods at spacing s.

    By definition lambda = (1/n) sum_i sum_{j != i} s / d_ij — each rod's
    potential raised by its neighbours, in units of rho/(2 pi s), averaged
    over the group (tutorial Eq. 9.7).  The published values of BS 7430
    Table 5 are used where they exist; otherwise the sum is evaluated for
    the actual layout.  (Version 1.1 used line-like values for the hollow
    square — 3.45 instead of 4.51 for eight rods — and the line values for
    a filled square, both on the optimistic side.)
    """
    if n <= 1:
        return 0.0, "single rod"
    if arrangement == "hollow_square" and n < 4:
        arrangement = "line"            # fewer than four rods cannot enclose
    if arrangement == "line" and n in BS7430_LAMBDA_LINE:
        return BS7430_LAMBDA_LINE[n], "BS 7430 Table 5"
    if arrangement == "hollow_square" and n in BS7430_LAMBDA_HOLLOW:
        return BS7430_LAMBDA_HOLLOW[n], "BS 7430 Table 5"
    pts = rod_positions_unit(n, arrangement)
    tot = 0.0
    for i, (xi, yi) in enumerate(pts):
        for j, (xj, yj) in enumerate(pts):
            if i != j:
                tot += 1.0 / max(math.hypot(xi - xj, yi - yj), 1e-9)
    return tot / n, "computed from the layout (Σ s/d over neighbours)"


def rods_parallel(rho: float, L: float, d: float, n: int, s: float,
                  arrangement: str = "line") -> dict:
    """n rods in parallel with mutual-resistance (utilisation) allowance.

    Uses the classical parallel-rod expression
        R_n = R_1/n * (1 + lambda * a),   a = rho/(2 pi R_1 s)
    with lambda from BS 7430 Table 5 (rods in a line, hollow square) and,
    for any other count or a filled square, from the geometry itself
    (rod_group_lambda).
    """
    R1 = rod(rho, L, d)["R"]
    alpha = rho / (2.0 * math.pi * R1 * s)
    lam, lam_src = rod_group_lambda(n, arrangement)
    Rn = R1 / n * (1.0 + lam * alpha)
    eta = R1 / (n * Rn) if Rn else 1.0
    return dict(R=Rn, R_single=R1, n=n, spacing=s, alpha=alpha, lam=lam,
                lam_source=lam_src,
                utilisation=eta, arrangement=arrangement,
                type=f"{n} × vertical rods ({arrangement})",
                formula="R_n = (R₁/n)(1 + λα),  α = ρ/(2πR₁s)")


def horizontal_strip(rho: float, L: float, w: float, h: float,
                     thickness: float = 0.003) -> dict:
    """Buried horizontal tape/strip of total length L, width w, at depth h.

    Dwight's horizontal-wire formula as tabulated in IEEE Std 142 Table 4.2,
    written for a conductor of TOTAL length L (Dwight's 2ℓ = L) buried at
    depth h (Dwight's s/2 = h):

        R = rho/(4 pi l) [ ln(4l/a) + ln(4l/s) - 2 + s/(2l)
                           - s^2/(16 l^2) + s^4/(512 l^4) ]
        l = L/2,  s = 2h,  a = equivalent radius (w/4 for a flat tape)
    """
    a = max(w / 4.0, thickness / 2.0)
    l = L / 2.0
    s = 2.0 * h
    R = rho / (4.0 * math.pi * l) * (
        math.log(4.0 * l / a) + math.log(4.0 * l / s) - 2.0
        + s / (2.0 * l) - s ** 2 / (16.0 * l ** 2) + s ** 4 / (512.0 * l ** 4))
    return dict(R=R, type="Horizontal buried tape", L=L, w=w, h=h, rho=rho,
                equivalent_radius=a,
                formula="Dwight horizontal conductor (IEEE Std 142 Table 4.2), "
                        "ℓ = L/2, s = 2h, a = w/4")


def horizontal_round(rho: float, L: float, d: float, h: float) -> dict:
    """Buried horizontal round conductor of diameter d at depth h."""
    return horizontal_strip(rho, L, 2.0 * d, h, thickness=d)


def plate(rho: float, area: float, h: float, both_faces: bool = True) -> dict:
    """Buried horizontal plate electrode of area `area` (m²) at depth h.

    Dwight (IEEE Std 142 Table 4.2), buried round plate of radius a at depth
    s/2:   R = rho/(8a) + rho/(4 pi s) [ 1 - 7a²/(12s²) + 33a⁴/(40s⁴) ]
    The ENA EREC S34 closed form is used when the plate is shallower than its
    own radius, where the series above is no longer valid.
    """
    r = math.sqrt(area / math.pi)
    s = 2.0 * h
    if not both_faces:
        return dict(R=rho / (4.0 * r), type="Plate electrode (one face)",
                    area=area, h=h, radius=r, rho=rho, formula="R = ρ/(4r)")
    if s >= 2.0 * r:
        R = rho / (8.0 * r) + rho / (4.0 * math.pi * s) * (
            1.0 - 7.0 * r ** 2 / (12.0 * s ** 2) + 33.0 * r ** 4 / (40.0 * s ** 4))
        f = "R = ρ/(8a) + ρ/(4πs)·[1 − 7a²/12s² + 33a⁴/40s⁴]  (Dwight, s = 2h)"
    else:
        R = rho / (8.0 * r) * (1.0 + r / (2.5 * h + r))
        f = "R = ρ/(8r)·[1 + r/(2.5h + r)]  (ENA EREC S34, shallow plate)"
    return dict(R=R, type="Plate electrode", area=area, h=h, radius=r,
                rho=rho, formula=f)


def ring(rho: float, radius: float, d: float, h: float) -> dict:
    """Buried ring electrode of mean radius `radius`, wire diameter d, depth h.

    Dwight (IEEE Std 142 Table 4.2), ring of DIAMETER D at depth s/2 made
    from wire of DIAMETER d:

        R = rho/(2 pi^2 D) [ ln(8D/d) + ln(4D/s) ]

    written here with D = 2·radius and s = 2h.  The second argument of the
    first logarithm is the wire diameter, not its radius; using the radius
    adds ln 2 to the bracket and over-states R by about 5 %, which the
    numerical solver in bem.py disagrees with.
    """
    D = 2.0 * radius
    s = 2.0 * h
    R = rho / (2.0 * math.pi ** 2 * D) * (
        math.log(8.0 * D / d) + math.log(4.0 * D / s))
    return dict(R=R, type="Ring electrode", radius=radius, d=d, h=h, rho=rho,
                circumference=2.0 * math.pi * radius,
                formula="R = ρ/(2π²D)·[ln(8D/d) + ln(4D/s)],  D = 2r, s = 2h")


def foundation(rho: float, volume_m3: float) -> dict:
    """Foundation (concrete-encased / Ufer) electrode.

        R ~= 0.2 * rho / V^(1/3)     (V = enclosed earth volume, m³)
    """
    R = 0.2 * rho / (volume_m3 ** (1.0 / 3.0))
    return dict(R=R, type="Foundation earth electrode", volume=volume_m3,
                rho=rho, formula="R ≈ 0.2·ρ/∛V  (DIN 18014 practice)")


def mesh(rho: float, area: float, total_length: float, h: float = 0.5) -> dict:
    """Buried mesh / grid electrode -- Sverak (IEEE Std 80 Eq. 52)."""
    R = rho * (1.0 / total_length + 1.0 / math.sqrt(20.0 * area)
               * (1.0 + 1.0 / (1.0 + h * math.sqrt(20.0 / area))))
    return dict(R=R, type="Mesh / grid electrode", area=area,
                total_length=total_length, h=h, rho=rho,
                formula="IEEE Std 80-2013 Eq. (52)")


ELECTRODE_FUNCS = {
    "rod": rod, "rods_parallel": rods_parallel, "strip": horizontal_strip,
    "round": horizontal_round, "plate": plate, "ring": ring,
    "foundation": foundation, "mesh": mesh,
}


def parallel_combination(resistances, coupling: float = 1.0,
                         rho: float | None = None,
                         separation: float | None = None) -> dict:
    """Combine electrodes that are bonded together, with mutual resistance.

    Electrodes in the same soil raise each other's potential, so they never
    add like resistors in parallel.  Each electrode i is represented by its
    self-resistance R_i and its equivalent hemisphere radius
    r_i = rho/(2 pi R_i); the mutual resistance of a pair a distance D apart
    is that of two point sources, rho/(2 pi D), never more than the smaller
    self-resistance:

        R_ij = min( rho/(2 pi max(D, r_i + r_j)),  R_i,  R_j ).

    With all electrodes at one potential V the currents follow from
    [R] I = V 1, so  R_A = 1 / (1ᵀ [R]⁻¹ 1).  When the separation is not
    given the hemispheres are taken as just touching (D = r_i + r_j) — the
    conservative assumption for electrodes on one building plot.  Version
    1.1 applied no mutual resistance (R_A = 1/Σ 1/R_i), which credited the
    villa example's two corner rods with −13 % where a numerical model of
    the foundation gives −6 %.

    `coupling` is an additional multiplier (default 1.0) kept for
    compatibility.
    """
    vals = [float(r) for r in resistances if r and r > 0 and math.isfinite(r)]
    if not vals:
        return dict(R=float("inf"), n=0)
    ideal = 1.0 / sum(1.0 / r for r in vals)
    n = len(vals)
    if n == 1 or not rho or rho <= 0:
        R = coupling * ideal
        return dict(R=R, n=n, ideal=ideal, coupling=coupling,
                    components=vals, mutual=False,
                    note=("Single electrode." if n == 1 else
                          "Combined without mutual resistance (ρ not given)."))
    radii = [rho / (2.0 * math.pi * r) for r in vals]
    M = [[0.0] * n for _ in range(n)]
    sep_used = []
    for i in range(n):
        M[i][i] = vals[i]
        for j in range(i + 1, n):
            touch = radii[i] + radii[j]
            D = max(float(separation), touch) if separation else touch
            Rm = min(rho / (2.0 * math.pi * D), vals[i], vals[j])
            M[i][j] = M[j][i] = Rm
            sep_used.append(D)
    # solve [M] x = 1 by Gaussian elimination (n is small; no numpy needed)
    A = [row[:] + [1.0] for row in M]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]
        piv = A[c][c]
        if abs(piv) < 1e-15:
            R = coupling * ideal
            return dict(R=R, n=n, ideal=ideal, coupling=coupling,
                        components=vals, mutual=False,
                        note="Mutual-resistance matrix singular; ideal parallel used.")
        for r in range(n):
            if r != c:
                f = A[r][c] / piv
                for k in range(c, n + 1):
                    A[r][k] -= f * A[c][k]
    x = [A[i][n] / A[i][i] for i in range(n)]
    Rmut = 1.0 / sum(x)
    Rmut = max(Rmut, ideal)
    R = coupling * Rmut
    how = (f"electrodes {separation:g} m apart" if separation else
           "equivalent hemispheres taken as touching (no separation given)")
    return dict(R=R, n=n, ideal=ideal, coupling=coupling, components=vals,
                mutual=True, R_mutual_model=Rmut,
                increase_pct=100.0 * (Rmut / ideal - 1.0),
                equivalent_radii=radii, separations=sep_used,
                note=(f"Mutual resistance included ({how}): "
                      f"{Rmut:.4g} Ω against {ideal:.4g} Ω for an ideal "
                      f"parallel combination (+{100.0 * (Rmut / ideal - 1.0):.1f} %)."))


def rods_required(rho: float, target_R: float, L: float, d: float,
                  s: float, max_n: int = 60) -> dict:
    """Number of parallel rods needed to reach a target electrode resistance."""
    R1 = rod(rho, L, d)["R"]
    if R1 <= target_R:
        return dict(n=1, R=R1, R_single=R1, achieved=True)
    for n in range(2, max_n + 1):
        r = rods_parallel(rho, L, d, n, s)
        if r["R"] <= target_R:
            return dict(n=n, R=r["R"], R_single=R1, achieved=True, detail=r)
    r = rods_parallel(rho, L, d, max_n, s)
    return dict(n=max_n, R=r["R"], R_single=R1, achieved=False, detail=r,
                note="Target not reached — increase rod length, spacing, "
                     "or use a different electrode type.")


# ---------------------------------------------------------------------------
# System earthing arrangements
# ---------------------------------------------------------------------------

SYSTEM_TYPES = {
    "TN-S": dict(
        name="TN-S",
        description="Source earthed at one point; separate neutral (N) and "
                    "protective (PE) conductors throughout the installation.",
        fault_path="Metallic — through the PE conductor back to the source.",
        protection="Overcurrent device or RCD; loop impedance dominated by "
                   "the line + PE conductor impedance.",
        rcd_required=False),
    "TN-C": dict(
        name="TN-C",
        description="Neutral and protective functions combined in a single "
                    "PEN conductor throughout.",
        fault_path="Metallic — through the PEN conductor.",
        protection="Overcurrent device only; RCDs cannot be used downstream "
                   "of a PEN conductor.",
        rcd_required=False),
    "TN-C-S": dict(
        name="TN-C-S (PME)",
        description="Combined PEN in the supply, separated into N and PE "
                    "within the installation.",
        fault_path="Metallic — through the PEN/PE conductor.",
        protection="Overcurrent device or RCD downstream of the split point.",
        rcd_required=False),
    "TT": dict(
        name="TT",
        description="Source earthed at the supply; installation has its own "
                    "independent earth electrode.",
        fault_path="Through the earth — R_A in series with the source earth.",
        protection="RCD is effectively mandatory: R_A × I_Δn ≤ 50 V.",
        rcd_required=True),
    "IT": dict(
        name="IT",
        description="Source isolated from earth (or earthed through a high "
                    "impedance); exposed-conductive-parts locally earthed.",
        fault_path="First fault current limited by the leakage capacitance / "
                   "earthing impedance.",
        protection="Insulation monitoring device; second fault handled like "
                   "TN or TT depending on the interconnection.",
        rcd_required=False),
}

# IEC 60364-4-41 Table 41.1 -- maximum disconnection times (s)
DISCONNECTION_TIMES = {
    "TN": [(50, 120, 0.8), (120, 230, 0.4), (230, 400, 0.2), (400, 1e9, 0.1)],
    "TT": [(50, 120, 0.3), (120, 230, 0.2), (230, 400, 0.07), (400, 1e9, 0.04)],
}
DISTRIBUTION_TIME = {"TN": 5.0, "TT": 1.0}


def max_disconnection_time(system: str, U0: float,
                           circuit: str = "final") -> dict:
    """Maximum disconnection time for a final circuit <= 63 A, or a
    distribution circuit (IEC 60364-4-41 clauses 411.3.2.2 / 411.3.2.3)."""
    fam = "TT" if system.upper().startswith("TT") else "TN"
    if circuit != "final":
        t = DISTRIBUTION_TIME[fam]
        return dict(t=t, family=fam, circuit=circuit,
                    rule="IEC 60364-4-41 clause 411.3.2.3")
    for lo, hi, t in DISCONNECTION_TIMES[fam]:
        if lo < U0 <= hi:
            return dict(t=t, family=fam, circuit=circuit, U0=U0,
                        rule="IEC 60364-4-41 Table 41.1")
    return dict(t=DISCONNECTION_TIMES[fam][-1][2], family=fam, U0=U0,
                rule="IEC 60364-4-41 Table 41.1 (extrapolated)")


# ---------------------------------------------------------------------------
# Protective devices
# ---------------------------------------------------------------------------

MCB_MULTIPLIERS = {"B": 5.0, "C": 10.0, "D": 20.0}

# Indicative gG fuse currents (A) for 0.4 s and 5 s -- IEC 60269 / BS 88-3.
FUSE_GG = {
    6: (28, 17), 10: (55, 32), 16: (90, 55), 20: (120, 75), 25: (155, 95),
    32: (210, 125), 40: (270, 165), 50: (350, 210), 63: (450, 270),
    80: (610, 380), 100: (800, 500), 125: (1050, 640), 160: (1300, 820),
    200: (1800, 1100),
}


def device_Ia(kind: str, rating_A: float, t_required: float = 0.4,
              curve: str = "B") -> dict:
    """Current I_a causing automatic operation within the required time."""
    kind = kind.lower()
    if kind in ("mcb", "breaker", "mccb"):
        m = MCB_MULTIPLIERS.get(curve.upper(), 5.0)
        return dict(Ia=m * rating_A, basis=f"Type {curve.upper()} MCB, "
                    f"instantaneous trip at {m:g}·In",
                    multiplier=m)
    if kind in ("fuse", "gg", "fuse_gg"):
        if rating_A in FUSE_GG:
            i04, i5 = FUSE_GG[rating_A]
            Ia = i04 if t_required <= 1.0 else i5
            return dict(Ia=float(Ia), basis=f"gG fuse {rating_A:g} A, "
                        f"{'0.4 s' if t_required <= 1.0 else '5 s'} value")
        return dict(Ia=rating_A * (7.0 if t_required <= 1.0 else 4.5),
                    basis="gG fuse, indicative multiplier (rating not tabulated)")
    if kind in ("rcd", "rcbo"):
        return dict(Ia=rating_A, basis=f"RCD rated residual current "
                    f"IΔn = {rating_A * 1000:g} mA")
    return dict(Ia=rating_A * 5.0, basis="Generic 5·In assumption")


def loop_impedance_check(U0: float, Zs: float, Ia: float,
                         Cmin: float = 0.95) -> dict:
    """TN systems: Zs × Ia ≤ Cmin × U0  (IEC 60364-4-41 Eq. 411.4.4)."""
    Zs_max = Cmin * U0 / Ia
    If = Cmin * U0 / Zs if Zs > 0 else float("inf")
    return dict(Zs=Zs, Zs_max=Zs_max, Ia=Ia, If=If, U0=U0, Cmin=Cmin,
                passed=Zs <= Zs_max,
                margin_pct=(Zs_max - Zs) / Zs_max * 100.0 if Zs_max else 0.0,
                formula="Z_s · I_a ≤ C_min · U₀  (IEC 60364-4-41 §411.4.4)")


def tt_electrode_check(RA: float, Ia: float, UL: float = 50.0) -> dict:
    """TT systems: R_A × I_a ≤ U_L (50 V a.c.)  (IEC 60364-4-41 §411.5.3)."""
    RA_max = UL / Ia if Ia else float("inf")
    return dict(RA=RA, RA_max=RA_max, Ia=Ia, UL=UL, passed=RA <= RA_max,
                touch_voltage=RA * Ia,
                formula="R_A · I_a ≤ U_L  (IEC 60364-4-41 §411.5.3)")


def rcd_selection(RA: float, UL: float = 50.0) -> dict:
    """Largest standard RCD residual current satisfying R_A × IΔn ≤ U_L."""
    standard = [0.010, 0.030, 0.100, 0.300, 0.500, 1.000]
    allowed = UL / RA if RA > 0 else float("inf")
    best = None
    for i in standard:
        if i <= allowed:
            best = i
    return dict(RA=RA, max_IdN=allowed, selected_IdN=best,
                selected_mA=(best * 1000.0 if best else None),
                options=[dict(IdN_mA=i * 1000, ok=i <= allowed) for i in standard],
                additional_protection_30mA=RA <= UL / 0.030,
                note=("No standard RCD satisfies the criterion — reduce R_A."
                      if best is None else ""),
                formula="R_A · IΔn ≤ 50 V")


def prospective_touch_voltage(U0: float, Z_line: float, Z_pe: float) -> dict:
    """Touch voltage appearing on exposed parts during a TN earth fault."""
    Zs = Z_line + Z_pe
    Ut = U0 * Z_pe / Zs if Zs else 0.0
    return dict(Ut=Ut, Zs=Zs, ratio=Z_pe / Zs if Zs else 0.0,
                formula="U_t = U₀·Z_PE/Z_s")


# ---------------------------------------------------------------------------
# Complete building assessment
# ---------------------------------------------------------------------------

def assess(system: str, U0: float, rho: float, electrodes: list,
           device: dict, circuit: str = "final",
           Z_line: float = 0.0, Z_pe: float = 0.0,
           Z_source: float = 0.0, UL: float = 50.0,
           coupling: float = 1.0, separation: float | None = None) -> dict:
    """Full LV earthing assessment for a home / building installation.

    electrodes : list of {"type": key, ...params}
    device     : {"kind": "mcb"/"fuse"/"rcd", "rating_A": .., "curve": "B"}
    """
    sysu = system.upper()
    results = []
    for e in electrodes:
        kind = e.get("type", "rod")
        fn = ELECTRODE_FUNCS.get(kind)
        if not fn:
            continue
        params = {k: v for k, v in e.items() if k != "type"}
        params.setdefault("rho", rho)
        try:
            results.append(fn(**params))
        except TypeError as exc:
            results.append(dict(R=float("nan"), type=kind, error=str(exc)))

    comb = parallel_combination([r.get("R") for r in results], coupling,
                                rho, separation)
    RA = comb["R"]

    t_max = max_disconnection_time(sysu, U0, circuit)
    dev = device_Ia(device.get("kind", "mcb"), device.get("rating_A", 32),
                    t_max["t"], device.get("curve", "B"))

    checks = []
    if sysu.startswith("TT"):
        c = tt_electrode_check(RA, dev["Ia"], UL)
        checks.append(dict(name="TT electrode: R_A × I_a ≤ 50 V", **c))
        rcd = rcd_selection(RA, UL)
        checks.append(dict(name="RCD selection", passed=rcd["selected_IdN"] is not None,
                           detail=rcd))
        Zs = Z_source + Z_line + RA
    else:
        Zs = Z_source + Z_line + Z_pe
        rcd = rcd_selection(RA, UL) if RA and math.isfinite(RA) else None
        c = loop_impedance_check(U0, Zs, dev["Ia"])
        checks.append(dict(name="Earth-fault loop impedance Z_s", **c))

    tv = prospective_touch_voltage(U0, Z_source + Z_line, Z_pe) \
        if not sysu.startswith("TT") else \
        dict(Ut=RA * (U0 / Zs if Zs else 0.0), Zs=Zs,
             formula="U_t = R_A · I_f")

    return dict(system=sysu, system_info=SYSTEM_TYPES.get(sysu, {}),
                electrodes=results, RA=RA, combination=comb,
                disconnection=t_max, device=dev, checks=checks,
                Zs=Zs, touch_voltage=tv, rcd=rcd, U0=U0, rho=rho,
                passed=all(c.get("passed", True) for c in checks))
