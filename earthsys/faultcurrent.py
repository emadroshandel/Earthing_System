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
Earth-fault current determination.

* IEC 60909-0:2016 -- short-circuit currents (three-phase, line-to-earth,
  peak value, thermal equivalent)
* IEEE Std 80-2013 clause 15 -- decrement factor D_f, split factor S_f,
  future-growth factor C_p and the maximum grid current I_G
"""

from __future__ import annotations

import cmath
import math

SQRT3 = math.sqrt(3.0)

# IEC 60909 voltage factor c (Table 1)
C_FACTORS = {
    "lv_max": 1.05, "lv_min": 0.95,
    "lv_400_max": 1.10,
    "mv_hv_max": 1.10, "mv_hv_min": 1.00,
}


# ---------------------------------------------------------------------------
# Source impedances
# ---------------------------------------------------------------------------

def grid_source_impedance(Un_kV: float, Sk_MVA: float, xr_ratio: float = 10.0,
                          c: float = 1.1) -> complex:
    """Network (grid) equivalent positive-sequence impedance, IEC 60909 §6.

    Z_Q = c * Un^2 / S_k"        (ohm, referenced to Un)
    """
    Z = c * (Un_kV * 1e3) ** 2 / (Sk_MVA * 1e6)
    if xr_ratio is None or xr_ratio <= 0:
        return complex(Z, 0.0)                  # purely resistive source
    if math.isinf(xr_ratio):
        return complex(0.0, Z)                  # purely reactive source
    X = Z * xr_ratio / math.sqrt(1.0 + xr_ratio ** 2)
    R = X / xr_ratio
    return complex(R, X)


def transformer_impedance(Sr_MVA: float, Un_kV: float, ukr_pct: float,
                          urr_pct: float | None = None,
                          pk_kW: float | None = None) -> complex:
    """Transformer positive-sequence impedance referred to the Un side."""
    Zt = ukr_pct / 100.0 * (Un_kV * 1e3) ** 2 / (Sr_MVA * 1e6)
    if urr_pct is not None:
        Rt = urr_pct / 100.0 * (Un_kV * 1e3) ** 2 / (Sr_MVA * 1e6)
    elif pk_kW is not None:
        Ir = Sr_MVA * 1e6 / (SQRT3 * Un_kV * 1e3)
        Rt = pk_kW * 1e3 / (3.0 * Ir ** 2)
    else:
        Rt = 0.10 * Zt          # typical when only u_k is known
    Xt = math.sqrt(max(Zt ** 2 - Rt ** 2, 0.0))
    return complex(Rt, Xt)


def line_impedance(length_km: float, r1: float, x1: float,
                   r0: float | None = None, x0: float | None = None):
    """Line/cable impedances (ohm/km inputs) -> (Z1, Z0)."""
    Z1 = complex(r1 * length_km, x1 * length_km)
    if r0 is None:
        r0 = 3.0 * r1
    if x0 is None:
        x0 = 3.0 * x1
    Z0 = complex(r0 * length_km, x0 * length_km)
    return Z1, Z0


# ---------------------------------------------------------------------------
# Fault currents
# ---------------------------------------------------------------------------

def three_phase_fault(Un_kV: float, Z1: complex, c: float = 1.1) -> dict:
    Ik = c * Un_kV * 1e3 / (SQRT3 * abs(Z1))
    xr = abs(Z1.imag / Z1.real) if Z1.real else float("inf")
    if xr == float("inf"):
        kappa = 2.0
    elif xr <= 0:
        kappa = 1.02                     # purely resistive: exp(-3R/X) -> 0
    else:
        kappa = 1.02 + 0.98 * math.exp(-3.0 / xr)
    return dict(Ik_kA=Ik / 1000.0, ip_kA=kappa * math.sqrt(2.0) * Ik / 1000.0,
                kappa=kappa, xr_ratio=xr, Z1=_c(Z1),
                formula="IEC 60909-0 Eq. (29): Iₖ\" = c·Un/(√3·Z₁)")


def line_to_earth_fault(Un_kV: float, Z1: complex, Z2: complex, Z0: complex,
                        Zf: complex = 0j, c: float = 1.1) -> dict:
    """Single line-to-earth fault, IEC 60909-0 Eq. (52).

        I_k1" = sqrt(3) * c * Un / |Z1 + Z2 + Z0 + 3*Zf|
    """
    Zt = Z1 + Z2 + Z0 + 3.0 * Zf
    Ik1 = SQRT3 * c * Un_kV * 1e3 / abs(Zt)
    I0 = Ik1 / 3.0
    xr = abs(Zt.imag / Zt.real) if Zt.real else float("inf")
    return dict(Ik1_kA=Ik1 / 1000.0, I0_kA=I0 / 1000.0,
                three_I0_kA=Ik1 / 1000.0,
                Zsum=_c(Zt), xr_ratio=xr, Z1=_c(Z1), Z2=_c(Z2), Z0=_c(Z0),
                formula="IEC 60909-0 Eq. (52): Iₖ₁\" = √3·c·Un/|Z₁+Z₂+Z₀+3Z_f|")


def double_line_to_earth(Un_kV: float, Z1: complex, Z2: complex, Z0: complex,
                         c: float = 1.1) -> dict:
    """Line-to-line-to-earth fault, IEC 60909-0 Eq. (45)-(47).

    Two quantities come out of this fault and they are different things:

        I"k2E   the current in one of the two faulted phases   Eq. (45)/(46)
        I"kE2E  the current returning through earth, = 3 I0    Eq. (47)

    The phase current needs the 120 degree rotation between the two faulted
    phases — the `a` operator — so |Z0 - a Z2| is not |Z0 - Z2|.  Dropping the
    rotation makes the earth current vanish whenever Z0 = Z2, which is the
    commonest assumption there is, and an earthing system sized on a zero
    earth current is sized on nothing.
    """
    a = cmath.exp(2j * math.pi / 3.0)
    den = abs(Z1 * Z2 + Z1 * Z0 + Z2 * Z0)
    if den == 0:
        raise ValueError("The sequence impedances give a zero denominator: "
                         "check Z1, Z2 and Z0.")
    U = c * Un_kV * 1e3
    Ik2E = U * abs(Z0 - a * Z2) / den                 # phase current, Eq. (46)
    Ie = SQRT3 * U * abs(Z2) / den                    # 3.I0 through earth (47)
    return dict(Ik2E_kA=Ik2E / 1000.0, IkE2E_kA=Ie / 1000.0,
                I3I0_kA=Ie / 1000.0,
                formula="IEC 60909-0 Eq. (46) phase, Eq. (47) earth (3·I0)")


def _c(z: complex) -> dict:
    return dict(r=z.real, x=z.imag, mag=abs(z),
                angle_deg=math.degrees(cmath.phase(z)) if z != 0 else 0.0)


# ---------------------------------------------------------------------------
# IEEE 80 grid current
# ---------------------------------------------------------------------------

def decrement_factor(tf: float, xr_ratio: float, f: float = 50.0) -> dict:
    """IEEE Std 80-2013 Eq. (84):

        D_f = sqrt( 1 + (T_a/t_f)(1 - e^(-2 t_f / T_a)) ),  T_a = X/(2*pi*f*R)
    """
    Ta = xr_ratio / (2.0 * math.pi * f)
    # Limits of Eq. (84): a purely resistive loop (X/R = 0, T_a = 0) has no
    # d.c. offset, D_f = 1; a purely reactive one (X/R = inf, the offset never
    # decays) gives (T_a/t_f)(1 - e^(-2t_f/T_a)) -> 2, D_f = sqrt(3).  Both used
    # to raise ZeroDivisionError / return NaN (e.g. Z1 = j2, Z0 = j6 ohm).
    if Ta <= 0:
        Df = 1.0
    elif math.isinf(Ta):
        Df = math.sqrt(3.0)
    else:
        Df = math.sqrt(1.0 + (Ta / tf) * (1.0 - math.exp(-2.0 * tf / Ta)))
    return dict(Df=Df, Ta=Ta, tf=tf, xr_ratio=xr_ratio, f=f,
                formula="IEEE Std 80-2013 Eq. (84)")


def split_factor_simple(Rg: float, Z_return: complex | float) -> dict:
    """Current-division factor by the simple parallel-path model.

        S_f = |Z_return| / |Z_return + R_g|

    Z_return is the equivalent impedance of all metallic return paths
    (overhead earth wires, cable sheaths, neutral conductors) seen from the
    substation.  S_f = 1 when there is no metallic return path.
    """
    if Z_return in (None, 0, 0j):
        return dict(Sf=1.0, note="No metallic return path — all fault current "
                                 "returns through the earth grid.")
    Z = complex(Z_return)
    Sf = abs(Z) / abs(Z + Rg)
    return dict(Sf=Sf, Z_return=_c(Z), Rg=Rg,
                formula="Current divider S_f = |Z_r| / |Z_r + R_g| "
                        "(IEEE Std 80-2013 Annex C)")


def split_factor_cable_s34(l_km: float, z_c: complex, r_c: float,
                           R_A: float, R_B: float,
                           remote_source: bool = False) -> dict:
    """Fraction of the earth-fault current that enters the soil at the faulted
    substation B, fed by an unarmoured three-core cable earthed at both ends
    (ENA EREC S34:2018 Appendix D.2):

        local source at A (D.2.1):          S_f = |l·r_c|       / |l·z_c + R_A + R_B|
        source beyond A, e.g. behind an
        overhead line (D.2.3):               S_f = |l·r_c + R_A| / |l·z_c + R_A + R_B|

    z_c is the sheath self impedance with earth return (Ω/km, complex), r_c
    the sheath resistance (Ω/km), R_A and R_B the terminal earth
    resistances (Ω).  For N identical cables use z_c/N and r_c/N.  As l grows
    S_f tends to the reduction factor r_c/|z_c|.  Armoured and single-core
    cables need S34 D.2 (armoured form), D.3 or D.4.
    """
    if l_km <= 0:
        raise ValueError("cable length must be positive")
    zc = complex(z_c)
    num = l_km * r_c + (R_A if remote_source else 0.0)
    den = abs(l_km * zc + R_A + R_B)
    Sf = abs(num) / den
    case = "D.2.3" if remote_source else "D.2.1"
    return dict(Sf=Sf, reduction_factor=r_c / abs(zc), case=case,
                formula=("S_f = |l·r_c%s| / |l·z_c + R_A + R_B|  "
                         "(ENA EREC S34:2018 App. %s)")
                        % (" + R_A" if remote_source else "", case))


# Indicative values only.  They are NOT taken from IEEE Std 80 (which gives
# Table C.1 and the curves of Figures C.1-C.22 instead); they are a coarse
# summary of what that table gives for a grid of about 1 ohm.  Use
# split_factor_table_c1 for an estimate tied to the standard.
SPLIT_FACTOR_GUIDE = [
    dict(case="Distribution substation, no transmission line, no neutral", Sf=1.00),
    dict(case="Distribution substation, 1 transmission line, 1 distribution neutral", Sf=0.60),
    dict(case="Distribution substation, 2 transmission lines, 4 neutrals", Sf=0.28),
    dict(case="Transmission substation, 4 lines with shield wires", Sf=0.20),
    dict(case="Transmission substation, 8+ lines with shield wires", Sf=0.12),
    dict(case="Generating station, extensive metallic network", Sf=0.05),
]

# IEEE Std 80-2013 Table C.1: approximate equivalent impedance (ohm) of the
# transmission-line shield wires and distribution-feeder neutrals, for 100 %
# remote contribution.  Key (transmission lines, distribution neutrals);
# value (Z for Rtg = 15, Rdg = 25 ohm;  Z for Rtg = 100, Rdg = 200 ohm).
SPLIT_FACTOR_TABLE_C1 = {
    (1, 1): (0.91 + 0.485j, 3.27 + 0.652j), (1, 2): (0.54 + 0.33j, 2.18 + 0.412j),
    (1, 4): (0.295 + 0.20j, 1.32 + 0.244j), (1, 8): (0.15 + 0.11j, 0.732 + 0.133j),
    (1, 12): (0.10 + 0.076j, 0.507 + 0.091j), (1, 16): (0.079 + 0.057j, 0.387 + 0.069j),
    (2, 1): (0.685 + 0.302j, 2.18 + 0.442j), (2, 2): (0.455 + 0.241j, 1.63 + 0.324j),
    (2, 4): (0.27 + 0.165j, 1.09 + 0.208j), (2, 8): (0.15 + 0.10j, 0.685 + 0.122j),
    (2, 12): (0.10 + 0.07j, 0.47 + 0.087j), (2, 16): (0.08 + 0.055j, 0.366 + 0.067j),
    (4, 1): (0.45 + 0.16j, 1.30 + 0.273j), (4, 2): (0.34 + 0.15j, 1.09 + 0.22j),
    (4, 4): (0.23 + 0.12j, 0.817 + 0.16j), (4, 8): (0.134 + 0.083j, 0.546 + 0.103j),
    (4, 12): (0.095 + 0.061j, 0.41 + 0.077j), (4, 16): (0.073 + 0.05j, 0.329 + 0.06j),
    (8, 1): (0.27 + 0.08j, 0.72 + 0.152j), (8, 2): (0.23 + 0.08j, 0.65 + 0.134j),
    (8, 4): (0.17 + 0.076j, 0.543 + 0.11j), (8, 8): (0.114 + 0.061j, 0.408 + 0.079j),
    (8, 12): (0.085 + 0.049j, 0.327 + 0.064j), (8, 16): (0.067 + 0.041j, 0.273 + 0.052j),
    (12, 1): (0.191 + 0.054j, 0.498 + 0.106j),
}


def split_factor_table_c1(Rg: float, n_lines: int, n_neutrals: int,
                          high_resistance: bool = False) -> dict:
    """Split factor from IEEE Std 80-2013 Table C.1.

    S_f = |Z_eq| / |Z_eq + R_g|, the current divider of Eq. (C.4), with
    Z_eq the tabulated equivalent impedance of the shield wires and feeder
    neutrals (Rtg = 15 / Rdg = 25 ohm, or 100 / 200 ohm when
    high_resistance).  Valid for 100 % remote contribution only.
    """
    key = (int(n_lines), int(n_neutrals))
    if key not in SPLIT_FACTOR_TABLE_C1:
        raise ValueError(f"IEEE 80 Table C.1 has no row for {key[0]} lines and "
                         f"{key[1]} neutrals")
    Z = SPLIT_FACTOR_TABLE_C1[key][1 if high_resistance else 0]
    out = split_factor_simple(Rg, Z)
    out.update(n_lines=key[0], n_neutrals=key[1],
               Rtg_Rdg="100/200 Ω" if high_resistance else "15/25 Ω",
               formula="S_f = |Z_eq| / |Z_eq + R_g|, Z_eq from IEEE Std 80-2013 "
                       "Table C.1 (100 % remote contribution)")
    return out


def grid_current(three_I0_kA: float, Sf: float, Df: float,
                 Cp: float = 1.0) -> dict:
    """Maximum grid current, IEEE Std 80-2013 Eq. (78) and (69).

        I_g = S_f * 3I_0 * C_p       (symmetrical grid current)
        I_G = D_f * I_g              (maximum grid current)
    """
    Ig = Sf * three_I0_kA * Cp
    IG = Df * Ig
    return dict(Ig_kA=Ig, IG_kA=IG, Sf=Sf, Df=Df, Cp=Cp,
                three_I0_kA=three_I0_kA,
                formula="IEEE Std 80-2013 Eq. (78), (69); C_p: growth margin (cf. 15.11)")


def thermal_equivalent(Ik_kA: float, tk: float, xr_ratio: float,
                       f: float = 50.0) -> dict:
    """Thermal equivalent short-circuit current, IEC 60909-0 clause 4.8."""
    if xr_ratio is None or xr_ratio <= 0:
        kappa = 1.02                     # X/R -> 0 limit of the kappa formula
    elif math.isinf(xr_ratio):
        kappa = 2.0
    else:
        kappa = 1.02 + 0.98 * math.exp(-3.0 / xr_ratio)
    fk = f * tk
    if fk <= 0:
        m = 0.0
    elif kappa >= 2.0 - 1e-12:
        # ln(kappa - 1) -> 0: the limit of the factor m (IEC 60909-0 4.8) is 2
        # (a d.c. component that never decays); the closed form divides by 0.
        m = 2.0
    else:
        m = (math.exp(4.0 * fk * math.log(kappa - 1.0)) - 1.0) / (2.0 * fk * math.log(kappa - 1.0)) \
            if kappa > 1.0000001 else 0.0
    m = max(m, 0.0)
    n = 1.0                      # far-from-generator fault
    Ith = Ik_kA * math.sqrt(m + n)
    return dict(Ith_kA=Ith, m=m, n=n, kappa=kappa,
                formula="IEC 60909-0 Eq. (66): I_th = Iₖ\"·√(m+n)")


# ---------------------------------------------------------------------------
# Split factor from the shield-wire ladder, and the fault-location sweep
# (1.8.0)
# ---------------------------------------------------------------------------
#
# IEEE Std 80-2013 clause 15.9 and Annex C: the current that returns to its
# source through the soil — and so raises the grid — is the fault current
# less what the overhead earth (shield) wires and distribution neutrals
# carry back.  Those wires form a ladder: a span impedance Z_s between
# towers, and a tower-footing resistance R_t from every tower to earth
# (Endrenyi 1963; Sebo 1969; Garrett and Patel 1995).  The phase current
# also induces a voltage in the shield wire (mutual impedance Z_m), which
# drives a further part of the return current along it.  Table C.1 is a
# set of pre-computed answers for typical lines; here the ladder itself is
# solved, and the fault is moved along the line, because the largest grid
# current is often for a fault at the first towers outside the station
# rather than inside it (IEEE Std 80 clause 15.9.1).

_MU0 = 4e-7 * math.pi


def carson_self(r_ohm_km: float, gmr_m: float, rho: float, f: float = 50.0) -> complex:
    """Self impedance of an overhead wire with earth return, Ω/km:
    r + π²·10⁻⁴·f + j·4π·10⁻⁴·f·ln(D_e/GMR),  D_e = 658.5·√(ρ/f)."""
    De = 658.5 * math.sqrt(rho / f)
    return complex(r_ohm_km + math.pi ** 2 * 1e-4 * f,
                   4 * math.pi * 1e-4 * f * math.log(De / gmr_m))


def carson_mutual(d_m: float, rho: float, f: float = 50.0) -> complex:
    """Mutual impedance between two parallel wires d apart, earth return, Ω/km."""
    De = 658.5 * math.sqrt(rho / f)
    return complex(math.pi ** 2 * 1e-4 * f, 4 * math.pi * 1e-4 * f * math.log(De / d_m))


def bundle_self(r_ohm_km: float, gmr_m: float, n_wires: int, d_sw: float,
                rho: float, f: float = 50.0) -> complex:
    """Series impedance per km of n identical shield wires bonded together at
    every tower (1.9.2), Ω/km.  The wires carry the same voltage drop, so the
    bundle's impedance is 1/(1ᵀZ⁻¹1) of their impedance matrix: for two wires
    d_sw apart (z_s + z_m(d_sw))/2, not z_s/2 — the mutual impedance between
    them is nearly as large as the self impedance."""
    n = int(n_wires)
    zs = carson_self(r_ohm_km, gmr_m, rho, f)
    if n <= 1:
        return zs
    if n != 2:
        raise ValueError("A line has one or two shield wires.")
    if not d_sw or d_sw <= 0:
        raise ValueError("Give the spacing between the two shield wires (m).")
    return (zs + carson_mutual(float(d_sw), rho, f)) / 2


def ladder_input(Zspan: complex, Rt: float, n_spans: int,
                 R_remote: float | None = None) -> complex:
    """Input impedance, from the station, of a shield wire of n_spans spans
    with a tower of footing resistance Rt at every intermediate tower and,
    if R_remote is given, bonded to the remote station's earth."""
    n_t = max(int(n_spans) - 1, 0)
    if R_remote is not None and R_remote > 0:
        Z = complex(R_remote)
        k = n_t
    elif n_t > 0:
        Z = complex(Rt)
        k = n_t - 1
    else:
        return complex(1e12)
    for _ in range(k):
        Z = Zspan + Z
        Z = Rt * Z / (Rt + Z)
    return Zspan + Z


def ladder_infinite(Zspan: complex, Rt: float) -> complex:
    """Driving-point impedance of an infinitely long ladder (Endrenyi):
    Z∞ = Z_s/2 + √(Z_s·R_t + Z_s²/4)."""
    return Zspan / 2 + cmath.sqrt(Zspan * Rt + Zspan * Zspan / 4)


def _tri_solve(lo, d, up, r):
    n = len(d)
    c = [0j] * n
    y = [0j] * n
    dd = d[0]
    c[0] = up[0] / dd if n > 1 else 0j
    y[0] = r[0] / dd
    for i in range(1, n):
        dd = d[i] - lo[i - 1] * c[i - 1]
        if i < n - 1:
            c[i] = up[i] / dd
        y[i] = (r[i] - lo[i - 1] * y[i - 1]) / dd
    for i in range(n - 2, -1, -1):
        y[i] -= c[i] * y[i + 1]
    return y


def ladder_nodes(Zspan, Ynode, Espan, inj):
    """Node potentials of a ladder (1.8.5).

    Zspan  series impedance of each span k (node k to k+1), n values
    Ynode  shunt admittance of each node to remote earth, n+1 values
    Espan  series EMF in each span, driving current from node k to k+1
    inj    current injected into each node from outside, n+1 values
    Returns the n+1 node potentials and the n span currents (k → k+1).
    """
    n = len(Zspan)
    N = n + 1
    ys = [1.0 / complex(z) for z in Zspan]
    d = [complex(y) for y in Ynode]
    lo = [0j] * (N - 1)
    up = [0j] * (N - 1)
    r = [complex(i) for i in inj]
    for k in range(n):
        d[k] += ys[k]
        d[k + 1] += ys[k]
        lo[k] = -ys[k]
        up[k] = -ys[k]
        # Norton equivalent of the EMF: E·y drawn from node k, pushed into k+1
        r[k] -= Espan[k] * ys[k]
        r[k + 1] += Espan[k] * ys[k]
    V = _tri_solve(lo, d, up, r)
    I = [(V[k] - V[k + 1] + Espan[k]) * ys[k] for k in range(n)]
    return V, I


def _spans(line_km, span_km, spans_km):
    if spans_km:
        sp = [float(x) for x in spans_km]
        if any(x <= 0 for x in sp):
            raise ValueError("Every span length must be positive.")
        return sp
    if line_km <= 0 or span_km <= 0:
        raise ValueError("The line length and span length must be positive.")
    n = max(1, int(round(line_km / span_km)))
    return [line_km / n] * n


def _ladder_input_list(Zsp, Rts, R_remote):
    """Input impedance of a ladder with its own span impedances and footing
    resistances, ending on the remote station's earth."""
    Z = complex(R_remote)
    for k in range(len(Zsp) - 1, 0, -1):
        Z = Zsp[k] + Z
        Z = Rts[k - 1] * Z / (Rts[k - 1] + Z)
    return Zsp[0] + Z


def ladder_line_impedance(line_km: float, span_km: float, Rt: float, R_remote: float,
                          rho: float = 100.0, f: float = 50.0, sw_r_km: float = 0.33,
                          sw_gmr: float = 0.004, n_wires: int = 1,
                          d_sw: float = 10.0) -> complex:
    """Input impedance of the shield wire(s) of an unfaulted outgoing line,
    seen from the station (1.8.5): the ladder of ladder_input with Carson's
    self impedance.  Two shield wires d_sw apart are one bundle with their
    mutual impedance (bundle_self, 1.9.2); up to 1.9.1 they were taken as
    z_s/2, which put the ladder's impedance 14–19 % low (and the grid
    current low with it)."""
    zs = bundle_self(sw_r_km, sw_gmr, n_wires, d_sw, rho, f)
    sp = _spans(line_km, span_km, None)
    return _ladder_input_list([zs * x for x in sp], [Rt] * (len(sp) - 1), R_remote)


def fault_location_sweep(Un_kV: float, Rg: float, *, line_km: float, span_km: float = 0.3,
                         Rt: float = 15.0, R_remote: float = 0.5,
                         Z1_line: complex = complex(0.06, 0.4),
                         Z0_line: complex = complex(0.25, 1.2),
                         Z1_local: complex = complex(0.5, 5.0), Z0_local: complex = complex(0.3, 3.0),
                         Z1_remote: complex = complex(0.5, 5.0), Z0_remote: complex = complex(0.5, 5.0),
                         zs_km: complex | None = None, zm_km: complex | None = None,
                         sw_r_km: float = 0.33, sw_gmr: float = 0.004, d_phase_sw: float = 8.0,
                         rho: float = 100.0, f: float = 50.0, c: float = 1.1,
                         Z_other: complex | None = None, spans_km=None, Rt_list=None,
                         other_lines=None, n_wires: int = 1, d_sw: float = 10.0,
                         parallel_lines=None) -> dict:
    """Grid current for a single-line-to-earth fault at the station and at
    every tower of one outgoing line with a shield wire.

    The line runs from this station (node 0, earth resistance Rg) over
    n = line_km/span_km spans to a remote station (node n, R_remote), with a
    tower of footing resistance Rt at every intermediate node.  The fault
    current follows from the sequence networks of the two sources and the
    line (I_f = 3cU_n/√3 / |2Z₁ + Z₀|, the zero-sequence share of each end by
    current division); the shield wire carries a series EMF −Z_m·I_phase in
    every span the phase current flows through; and the ladder is solved for
    its node potentials.  The grid current is V₀/R_g.  `Z_other` is the
    combined input impedance of every other shield wire and neutral bonded
    to the grid (in parallel with R_g).

    Since 1.8.5 the spans may differ (`spans_km`, one length per span), each
    tower may have its own footing resistance (`Rt_list`, one per
    intermediate tower, e.g. measured values), and the other outgoing lines
    can be given as `other_lines` (dicts of line_km, span_km, Rt, R_remote and
    optionally sw_r_km, sw_gmr, n_wires, d_sw) whose shield-wire ladders are
    solved and put in parallel with the grid.

    Since 1.9.2 the faulted line may have two shield wires (`n_wires`,
    `d_sw` apart, each `d_phase_sw` from the faulted phase), taken as one
    bundle with their mutual impedance, and `parallel_lines` are lines that
    share the corridor over the whole route — the same tower positions and
    the same remote station — each a dict of separation (m, between the line
    centres), Rt, and optionally n_wires, d_sw, sw_r_km, sw_gmr and d_phase
    (from the faulted phase to its shield wires; default the separation).
    Their shield wires are coupled to the faulted phase and to every other
    shield wire through Carson's mutual impedances (shield wires taken at one
    height), and the whole corridor is solved as one network of nodes per
    line and tower (corridor_nodes).
    """
    if Rg <= 0:
        raise ValueError("The grid resistance must be positive.")
    sps = _spans(line_km, span_km, spans_km)
    n = len(sps)
    line_km = sum(sps)
    sp = line_km / n
    if Rt_list is not None:
        Rts = [float(r) for r in Rt_list]
        if len(Rts) != n - 1:
            raise ValueError(f"Give one footing resistance per intermediate tower: {n - 1} "
                             f"values for {n} spans.")
        if any(r <= 0 for r in Rts):
            raise ValueError("Every footing resistance must be positive.")
    else:
        Rts = [float(Rt)] * (n - 1)
    Yother = (1.0 / complex(Z_other)) if Z_other else 0j
    others = []
    for k, ol in enumerate(other_lines or [], 1):
        Zo = ladder_line_impedance(float(ol["line_km"]), float(ol.get("span_km", 0.3)),
                                   float(ol.get("Rt", 15.0)), float(ol.get("R_remote", 0.5)),
                                   rho, f, float(ol.get("sw_r_km", sw_r_km)),
                                   float(ol.get("sw_gmr", sw_gmr)), int(ol.get("n_wires", 1)),
                                   float(ol.get("d_sw", 10.0) or 10.0))
        Yother += 1.0 / Zo
        others.append(dict(name=ol.get("name", f"line {k}"), Z=abs(Zo)))
    zs = complex(zs_km) if zs_km is not None else bundle_self(sw_r_km, sw_gmr, n_wires,
                                                              d_sw, rho, f)
    zm = complex(zm_km) if zm_km is not None else carson_mutual(d_phase_sw, rho, f)
    if parallel_lines:
        if zs_km is not None or zm_km is not None:
            raise ValueError("Parallel lines are computed from the corridor geometry; "
                             "leave the shield-wire impedances to be calculated.")
        corridor = _corridor(n_wires, d_sw, d_phase_sw, sw_r_km, sw_gmr, Rts,
                             parallel_lines, rho, f)
    Zsp = [zs * s_ for s_ in sps]
    Zmp = [zm * s_ for s_ in sps]
    E = c * Un_kV * 1e3 / math.sqrt(3.0)
    xs = [0.0]
    for s_ in sps:
        xs.append(xs[-1] + s_)
    rows = []
    for j in range(0, n):                       # node j: 0 = in the station
        x = xs[j]
        Z1a = Z1_local + Z1_line * x
        Z1b = Z1_remote + Z1_line * (line_km - x)
        Z0a = Z0_local + Z0_line * x
        Z0b = Z0_remote + Z0_line * (line_km - x)
        Z1 = Z1a * Z1b / (Z1a + Z1b)
        Z0 = Z0a * Z0b / (Z0a + Z0b)
        I0 = E / (2 * Z1 + Z0)
        If = 3 * I0
        Ia = If * Z0b / (Z0a + Z0b)             # 3I0 from this station's side
        Ib = If - Ia                            # from the remote side
        # nodal equations, node k = 0 … n; EMF in span k: −Zm·I_phase(k→k+1)
        Iph = [(Ia if k < j else -Ib) for k in range(n)]
        if parallel_lines:
            V = corridor_nodes(corridor, sps, Rg, Yother, R_remote, Iph, j, If, Ia, Ib)
        else:
            Y = [1.0 / Rg + Yother] + [1.0 / r_ for r_ in Rts] + [1.0 / R_remote]
            Es = [-Zmp[k] * Iph[k] for k in range(n)]
            inj = [0j] * (n + 1)
            inj[j] += If
            inj[0] -= Ia
            inj[n] -= Ib
            V, _ = ladder_nodes(Zsp, Y, Es, inj)
        Ig = V[0] / Rg
        rows.append(dict(node=j, x_km=x, If_kA=abs(If) / 1e3, I_local_kA=abs(Ia) / 1e3,
                         I_remote_kA=abs(Ib) / 1e3, Ig_kA=abs(Ig) / 1e3,
                         GPR_V=abs(V[0]), Sf=abs(Ig) / abs(If) if abs(If) else 0.0,
                         V_tower_V=abs(V[j]) if j > 0 else None))
    worst = max(rows, key=lambda q: q["Ig_kA"])
    inside = rows[0]
    out = dict(rows=rows, n_spans=n, span_km=sp,
               zs_km=dict(re=zs.real, im=zs.imag), zm_km=dict(re=zm.real, im=zm.imag),
               coupling_k=abs(zm / zs),
               Z_ladder=abs(_ladder_input_list(Zsp, Rts, R_remote)),
               Z_infinite=abs(ladder_infinite(zs * sp, sum(Rts) / len(Rts) if Rts else Rt)),
               spans_km=sps, Rt_list=Rts, other_lines=others, n_wires=int(n_wires),
               parallel_lines=(corridor["summary"] if parallel_lines else []),
               Z_other_total=(abs(1.0 / Yother) if Yother else None),
               station=inside, worst=worst,
               Sf_station=inside["Sf"],
               governs="fault inside the station" if worst["node"] == 0 else
               f"fault at tower {worst['node']} ({worst['x_km']:.2f} km out)")
    out["note"] = (
        f"Fault inside the station: I_f = {inside['If_kA']:.2f} kA, of which "
        f"{inside['Ig_kA']:.2f} kA flows into the grid (S_f = {inside['Sf']:.3f}). "
        + (f"The largest grid current, {worst['Ig_kA']:.2f} kA, is for a fault at tower "
           f"{worst['node']}, {worst['x_km']:.2f} km out: the station's own source then "
           f"returns its current through the soil. Design with it."
           if worst["node"] != 0 else
           "No fault along the line gives a larger grid current."))
    return out


def _corridor(n_wires, d_sw, d_phase_sw, sw_r_km, sw_gmr, Rts, parallel_lines, rho, f):
    """Per-km line-level admittance matrix of a corridor of parallel lines
    (1.9.2).  Line 0 is the faulted line.  Every shield wire is a conductor
    of the wire-level impedance matrix Z (Carson, Ω/km); the wires of one
    line are bonded at its towers, so with B mapping wires to lines the
    lines' span admittance per km is BᵀZ⁻¹B and the current driven by the
    faulted phase is BᵀZ⁻¹z_p·I_phase, z_p being the mutual impedances
    from the phase to the wires."""
    import numpy as np
    wires = []                                  # (x, r, gmr, line, d_phase)

    def add(line, centre, n, d, r, g, dph):
        n = int(n)
        if n not in (1, 2):
            raise ValueError("A line has one or two shield wires.")
        if n == 2 and (not d or d <= 0):
            raise ValueError("Give the spacing between the two shield wires (m).")
        for x in ([centre] if n == 1 else [centre - d / 2, centre + d / 2]):
            wires.append((x, float(r), float(g), line, dph))

    add(0, 0.0, n_wires, d_sw, sw_r_km, sw_gmr, float(d_phase_sw))
    rts, summ = [list(Rts)], []
    n_t = len(Rts)
    for k, pl in enumerate(parallel_lines, 1):
        sep = float(pl["separation"])
        if sep <= 0:
            raise ValueError(f"Parallel line {k}: the separation must be positive.")
        dph = float(pl.get("d_phase") or sep)
        add(k, sep, pl.get("n_wires", 1), float(pl.get("d_sw", 10.0) or 10.0),
            pl.get("sw_r_km", sw_r_km), pl.get("sw_gmr", sw_gmr), dph)
        if pl.get("Rt_list"):
            rt = [float(v) for v in pl["Rt_list"]]
            if len(rt) != n_t:
                raise ValueError(f"Parallel line {k}: give one footing resistance per tower "
                                 f"({n_t}).")
        else:
            rt = [float(pl.get("Rt", 15.0))] * n_t
        if any(v <= 0 for v in rt):
            raise ValueError(f"Parallel line {k}: every footing resistance must be positive.")
        rts.append(rt)
        summ.append(dict(name=pl.get("name", f"parallel line {k}"), separation=sep,
                         n_wires=int(pl.get("n_wires", 1)), d_phase=dph))
    De = 658.5 * math.sqrt(rho / f)
    m = len(wires)
    Z = np.zeros((m, m), complex)
    zp = np.zeros(m, complex)
    for a in range(m):
        Z[a, a] = carson_self(wires[a][1], wires[a][2], rho, f)
        own = wires[a][3] == 0
        dp = float(d_phase_sw) if own else wires[a][4]
        if dp >= 0.2 * De:
            raise ValueError(f"A distance of {dp:g} m is too large for Carson's "
                             f"approximation here (equivalent earth-return depth {De:.0f} m).")
        zp[a] = carson_mutual(dp, rho, f)
        for b in range(a + 1, m):
            d = abs(wires[a][0] - wires[b][0])
            if d <= 0:
                raise ValueError("Two shield wires are at the same position.")
            if d >= 0.2 * De:
                raise ValueError(f"A spacing of {d:g} m is too large for Carson's "
                                 f"approximation here (equivalent earth-return depth {De:.0f} m).")
            Z[a, b] = Z[b, a] = carson_mutual(d, rho, f)
    L = len(rts)
    B = np.zeros((m, L))
    for a, w in enumerate(wires):
        B[a, w[3]] = 1.0
    Zi = np.linalg.inv(Z)
    Ykm = B.T @ Zi @ B                      # line-level admittance × km
    Jkm = -(B.T @ Zi @ zp)                  # line currents per A of phase current
    return dict(Ykm=Ykm, Jkm=Jkm, rts=rts, L=L, summary=summ, Z=Z, zp=zp, B=B)


def corridor_nodes(cor, sps, Rg, Yother, R_remote, Iph, j, If, Ia, Ib, full=False):
    """Node potentials of the corridor for a fault at tower j of line 0
    (1.9.2): node 0 is the station (every line bonded to the grid), node 1
    the remote station, then one node per line and intermediate tower.
    Span k between towers k and k+1 carries the line currents
    Y_k (V_k − V_{k+1}) + J·I_phase(k), Y_k = Y_km/length."""
    import numpy as np
    L, n = cor["L"], len(sps)
    N = 2 + L * (n - 1)

    def node(line, k):
        if k == 0:
            return 0
        if k == n:
            return 1
        return 2 + line * (n - 1) + (k - 1)
    G = np.zeros((N, N), complex)
    rhs = np.zeros(N, complex)
    G[0, 0] += 1.0 / Rg + Yother
    G[1, 1] += 1.0 / R_remote
    for line in range(L):
        for k in range(1, n):
            G[node(line, k), node(line, k)] += 1.0 / cor["rts"][line][k - 1]
    for k in range(n):
        Y = cor["Ykm"] / sps[k]
        J = cor["Jkm"] * Iph[k]
        a = [node(line, k) for line in range(L)]
        b = [node(line, k + 1) for line in range(L)]
        for p in range(L):
            for q in range(L):
                G[a[p], a[q]] += Y[p, q]
                G[a[p], b[q]] -= Y[p, q]
                G[b[p], a[q]] -= Y[p, q]
                G[b[p], b[q]] += Y[p, q]
            rhs[a[p]] -= J[p]
            rhs[b[p]] += J[p]
    rhs[node(0, j)] += If
    rhs[0] -= Ia
    rhs[1] -= Ib
    V = np.linalg.solve(G, rhs)
    if full:
        # potentials of every line at every tower, and the span currents
        P = np.array([[V[node(line, k)] for k in range(n + 1)] for line in range(L)])
        Isp = np.array([cor["Ykm"] / sps[k] @ (P[:, k] - P[:, k + 1]) + cor["Jkm"] * Iph[k]
                        for k in range(n)])
        return P, Isp
    return [complex(V[0])] + [complex(V[node(0, k)]) for k in range(1, n + 1)]


# ---------------------------------------------------------------------------
# Earth-fault current returning in cable sheaths (1.8.5)
# ---------------------------------------------------------------------------
#
# A substation B fed from A by cable: for an earth fault at B the fault
# current flows out along the faulted core and back partly in the sheaths
# (and armour) of the cable, partly through the soil between the two
# earthing systems.  Only the soil part raises B's earth.  ENA EREC S34
# Appendix D gives closed forms for a single section with the sheath bonded
# at both ends; here the sheath is a ladder like the shield wire: its
# sections run between the end earths and any intermediate joint or
# link-box earths, the faulted core induces −z_m·I_f in every section, and
# the node potentials give the earth current at each end, the sheath
# current and the voltage of every joint.

def _sheath_geometry(formation: str, s: float, r_m: float, faulted: int = 0):
    """Self GMR of the sheaths in parallel and their GMD to the faulted core."""
    if formation == "three_core":
        return r_m, r_m, 1
    if formation == "trefoil":
        pos = [(0.0, 0.0), (s, 0.0), (s / 2.0, s * math.sqrt(3.0) / 2.0)]
    elif formation == "flat":
        pos = [(-s, 0.0), (0.0, 0.0), (s, 0.0)]
    else:
        raise ValueError("Formation must be trefoil, flat or three_core.")
    d = lambda a, b: r_m if a == b else math.dist(pos[a], pos[b])
    gmr = (math.prod(d(a, b) for a in range(3) for b in range(3))) ** (1.0 / 9.0)
    gmd = (math.prod(d(faulted, b) for b in range(3))) ** (1.0 / 3.0)
    return gmr, gmd, 3


def cable_sheath_return(If_kA: float, *, length_km: float, R_A: float, R_B: float,
                        r_sheath_km: float, r_mean: float, formation: str = "trefoil",
                        spacing: float = 0.1, n_circuits: int = 1, joints=None,
                        R_joint: float | None = None, bonding: str = "both_ends",
                        rho: float = 100.0, f: float = 50.0, fault_at: str = "B",
                        faulted_phase: int = 0, r_armour_km: float | None = None,
                        source_beyond: bool = False, z_sheath_km=None, z_mutual_km=None,
                        minor_km=None, circuit_sep: float = 0.5) -> dict:
    """Earth-fault current at B (or A) returning in the cable sheaths.

    If_kA        earth-fault current (kA), from the fault module
    length_km    route length; r_sheath_km the resistance of one sheath (Ω/km),
                 r_mean its mean radius (m); r_armour_km an armour in parallel
    formation    'trefoil', 'flat' (spacing = centre distance, m) or
                 'three_core' (one common sheath)
    n_circuits   identical cables in parallel
    joints       distances (km from A) of joints or link boxes earthed through
                 R_joint (Ω); none = one section
    bonding      'both_ends' (sheaths earthed at A and B and at the joints),
                 'single_point_A' / 'single_point_B' (earthed at one end only:
                 no sheath return; the whole current goes through the soil) or
                 'cross_bonded' (1.9.4: `minor_km` minor sections, three to a
                 major section; see cable_sheath_crossbonded)
    source_beyond the source is beyond A (an overhead line into A): the current
                 then also returns through A's earth (S34 D.2.3)
    """
    if If_kA <= 0 or length_km <= 0 or R_A <= 0 or R_B <= 0:
        raise ValueError("Fault current, cable length and both earth resistances must be positive.")
    if r_sheath_km <= 0 or r_mean <= 0:
        raise ValueError("Sheath resistance and mean radius must be positive.")
    If = If_kA * 1e3
    gmr, gmd, n_sh = _sheath_geometry(formation, spacing, r_mean, int(faulted_phase))
    r_one = r_sheath_km if not r_armour_km else (r_sheath_km * r_armour_km / (r_sheath_km + r_armour_km))
    n_par = n_sh * max(int(n_circuits), 1)
    De = 658.5 * math.sqrt(rho / f)
    w = 2 * math.pi * f
    k_e = math.pi ** 2 * 1e-4 * f                       # earth-return resistance, Ω/km
    if z_sheath_km is not None:
        zs = complex(z_sheath_km)
    else:
        # all sheaths in parallel, Carson: r/n + π²10⁻⁴f + jω(μ0/2π)ln(De/GMR)
        zs = complex(r_one / n_par + k_e, w * 2e-4 * math.log(De / gmr))
    if z_mutual_km is not None:
        zm = complex(z_mutual_km)
    else:
        zm = complex(k_e, w * 2e-4 * math.log(De / gmd))
    pts = sorted(set(float(x) for x in (joints or []) if 0 < float(x) < length_km))
    if pts and (R_joint is None or R_joint <= 0):
        raise ValueError("Give the earth resistance of the joints or link boxes.")
    xs = [0.0] + pts + [float(length_km)]
    sec = [b - a for a, b in zip(xs[:-1], xs[1:])]
    if bonding == "cross_bonded":
        return cable_sheath_crossbonded(
            If_kA, minor_km=minor_km, R_A=R_A, R_B=R_B, r_sheath_km=r_sheath_km,
            r_mean=r_mean, formation=formation, spacing=spacing, n_circuits=n_circuits,
            circuit_sep=circuit_sep, R_major=R_joint, rho=rho, f=f, fault_at=fault_at,
            faulted_phase=faulted_phase, r_armour_km=r_armour_km, source_beyond=source_beyond)
    single = bonding in ("single_point_A", "single_point_B")
    if single:
        # no sheath circuit: the current returns entirely through the soil
        IgB = If if fault_at == "B" else 0.0
        IgA = If if fault_at == "A" else 0.0
        return dict(If_kA=If_kA, Sf=1.0, Ig_kA=If_kA, IgA_kA=IgA / 1e3, IgB_kA=IgB / 1e3,
                    I_sheath_kA=0.0, GPR_A=IgA * R_A, GPR_B=IgB * R_B, joints=[],
                    zs_km=[zs.real, zs.imag], zm_km=[zm.real, zm.imag],
                    reduction_factor=1.0, bonding=bonding,
                    note=("The sheaths are earthed at one end only, so they carry no "
                          "earth-fault return current: the whole fault current flows "
                          "through the soil to the faulted end's earth. An earth "
                          "continuity conductor laid with the cable restores a return path."))
    Zsp = [zs * L for L in sec]
    Y = [1.0 / R_A] + ([1.0 / R_joint] * len(pts) if pts else []) + [1.0 / R_B]
    n = len(sec)
    inj = [0j] * (n + 1)
    if fault_at == "B":
        # core current from A to B in every section
        Es = [-zm * L * If for L in sec]
        inj[n] += If
        if not source_beyond:
            inj[0] -= If                       # the source neutral is A's earth
    else:
        Es = [zm * L * If for L in sec]        # core current from B to A
        inj[0] += If
        inj[n] -= If
    V, I = ladder_nodes(Zsp, Y, Es, inj)
    IgB = V[n] / R_B
    IgA = V[0] / R_A
    Ig = IgB if fault_at == "B" else IgA
    Ish = I[0] if fault_at == "B" else I[-1]
    rf = abs(1.0 - zm / zs)
    jrows = [dict(x_km=x, V=abs(V[k + 1]), I_earth_A=abs(V[k + 1] / R_joint))
             for k, x in enumerate(pts)]
    out = dict(If_kA=If_kA, fault_at=fault_at, bonding=bonding, formation=formation,
               Ig_kA=abs(Ig) / 1e3, Sf=abs(Ig) / If, IgA_kA=abs(IgA) / 1e3, IgB_kA=abs(IgB) / 1e3,
               I_sheath_kA=abs(Ish) / 1e3, GPR_A=abs(V[0]), GPR_B=abs(V[n]),
               joints=jrows, sections=sec, zs_km=[zs.real, zs.imag], zm_km=[zm.real, zm.imag],
               gmr=gmr, gmd=gmd, reduction_factor=rf,
               formula="sheath ladder with core-to-sheath mutual coupling (Carson); "
                       "cf. ENA EREC S34:2018 App. D")
    end = "B" if fault_at == "B" else "A"
    out["note"] = (
        f"For an earth fault at {end}, {abs(Ish) / 1e3:.2f} kA of the {If_kA:.2f} kA returns "
        f"in the sheaths and {abs(Ig) / 1e3:.2f} kA enters the soil at {end} "
        f"(S_f = {abs(Ig) / If:.3f}), raising its earth to {abs(V[n] if end == 'B' else V[0]):.0f} V. "
        f"The sheaths' reduction factor |1 − z_m/z_s| is {rf:.3f}."
        + (f" The highest joint voltage is {max(j['V'] for j in jrows):.0f} V." if jrows else ""))
    return out



# ---------------------------------------------------------------------------
# Cross-bonded sheaths (1.9.4)
# ---------------------------------------------------------------------------
#
# Single-core cables with cross-bonded sheaths: the route is cut into major
# sections of three minor sections.  At the two cross-bonding joints inside
# a major section the sheaths are transposed (the sheath at position p
# continues at position p+1) through unearthed link boxes; at the ends of a
# major section all sheaths are bonded together and earthed.  Every sheath
# and the faulted core are conductors of a Carson impedance matrix; the
# sheath network is solved node by node with the transpositions in its
# connectivity, so unequal minor sections, the voltages at the link boxes and
# across the sectionalising insulation all come out.  With equal minor
# sections every sheath path visits each position once, and the result
# equals the both-ends model with earths at the major joints exactly.

def cable_sheath_crossbonded(If_kA: float, *, minor_km, R_A: float, R_B: float,
                             r_sheath_km: float, r_mean: float, formation: str = "trefoil",
                             spacing: float = 0.1, n_circuits: int = 1,
                             circuit_sep: float = 0.5, R_major: float | None = None,
                             rho: float = 100.0, f: float = 50.0, fault_at: str = "B",
                             faulted_phase: int = 0, r_armour_km: float | None = None,
                             source_beyond: bool = False) -> dict:
    """Earth-fault current at B (or A) returning in cross-bonded sheaths.

    minor_km     minor section lengths from A, three per major section
    R_major      earth resistance at the intermediate major-section joints
    circuit_sep  centre distance between parallel circuits (m), side by side;
                 each circuit is cross-bonded on its own, all are bonded
                 together at the major joints
    The cores are not transposed; the link boxes are taken as open (their
    sheath voltage limiters not conducting)."""
    import numpy as np
    if formation not in ("trefoil", "flat"):
        raise ValueError("Cross-bonding is for single-core cables, in trefoil or flat formation.")
    sec = [float(x) for x in (minor_km or [])]
    if not sec or len(sec) % 3 or any(x <= 0 for x in sec):
        raise ValueError("Give the minor section lengths, three for every major section.")
    if If_kA <= 0 or R_A <= 0 or R_B <= 0 or r_sheath_km <= 0 or r_mean <= 0:
        raise ValueError("Fault current, earth resistances and sheath data must be positive.")
    n_major = len(sec) // 3
    if n_major > 1 and (R_major is None or R_major <= 0):
        raise ValueError("Give the earth resistance at the major-section joints.")
    nc = max(int(n_circuits), 1)
    if nc > 1 and (not circuit_sep or circuit_sep <= 0):
        raise ValueError("Give the distance between the circuits.")
    If = If_kA * 1e3
    if formation == "trefoil":
        pos = [(0.0, 0.0), (spacing, 0.0), (spacing / 2.0, spacing * math.sqrt(3.0) / 2.0)]
    else:
        pos = [(-spacing, 0.0), (0.0, 0.0), (spacing, 0.0)]
    wires = [(c, p, (x + c * circuit_sep, y)) for c in range(nc) for p, (x, y) in enumerate(pos)]
    m = len(wires)
    r_one = r_sheath_km if not r_armour_km else (r_sheath_km * r_armour_km
                                                  / (r_sheath_km + r_armour_km))
    De = 658.5 * math.sqrt(rho / f)
    w = 2 * math.pi * f
    k_e = math.pi ** 2 * 1e-4 * f
    zlog = lambda d: complex(k_e, w * 2e-4 * math.log(De / d))
    Z = np.zeros((m, m), complex)
    for a in range(m):
        for b in range(m):
            d = r_mean if a == b else math.dist(wires[a][2], wires[b][2])
            Z[a, b] = zlog(d) + (r_one if a == b else 0.0)
    core = pos[int(faulted_phase)]
    zc = np.array([zlog(r_mean if (wi[0] == 0 and wi[1] == int(faulted_phase))
                        else math.dist(core, wi[2])) for wi in wires])
    Zi = np.linalg.inv(Z)
    # nodes: 0 = A, 1 = B, 2.. = intermediate major joints, then per
    # cross-bonding joint one node per (circuit, position) at its end
    nmaj = n_major - 1
    nodes = 2 + nmaj
    xb = {}                                    # (joint j, circuit, position) -> node
    for j in range(len(sec) - 1):
        if (j + 1) % 3:
            for c in range(nc):
                for p in range(3):
                    xb[(j, c, p)] = nodes
                    nodes += 1

    def end_node(k, c, p):
        """Node at the end of minor section k of the sheath at (c, p)."""
        if k == len(sec) - 1:
            return 1
        if (k + 1) % 3 == 0:
            return 2 + (k + 1) // 3 - 1
        return xb[(k, c, p)]

    def start_node(k, c, p):
        if k == 0:
            return 0
        if k % 3 == 0:
            return 2 + k // 3 - 1
        # transposition: position p of section k continues position p-1 of k-1
        return xb[(k - 1, c, (p - 1) % 3)]
    G = np.zeros((nodes, nodes), complex)
    rhs = np.zeros(nodes, complex)
    G[0, 0] += 1.0 / R_A
    G[1, 1] += 1.0 / R_B
    for q in range(nmaj):
        G[2 + q, 2 + q] += 1.0 / R_major
    Icore = If if fault_at == "B" else -If     # core current A → B
    for k, L in enumerate(sec):
        Y = Zi / L
        J = Zi @ (-zc * Icore)                # EMF −z_c·L·I, admittance Z⁻¹/L
        a = [start_node(k, c, p) for c, p, _ in wires]
        b = [end_node(k, c, p) for c, p, _ in wires]
        for u in range(m):
            for v in range(m):
                G[a[u], a[v]] += Y[u, v]
                G[a[u], b[v]] -= Y[u, v]
                G[b[u], a[v]] -= Y[u, v]
                G[b[u], b[v]] += Y[u, v]
            rhs[a[u]] -= J[u]
            rhs[b[u]] += J[u]
    if fault_at == "B":
        rhs[1] += If
        if not source_beyond:
            rhs[0] -= If
    else:
        rhs[0] += If
        rhs[1] -= If
    V = np.linalg.solve(G, rhs)
    # sheath currents of every minor section, and the joints
    Isec = []
    for k, L in enumerate(sec):
        a = np.array([V[start_node(k, c, p)] for c, p, _ in wires])
        b = np.array([V[end_node(k, c, p)] for c, p, _ in wires])
        Isec.append(Zi @ (a - b) / L + Zi @ (-zc * Icore))
    IgA, IgB = V[0] / R_A, V[1] / R_B
    Ig = IgB if fault_at == "B" else IgA
    Ish = Isec[0].sum() if fault_at == "B" else Isec[-1].sum()
    xs = np.concatenate([[0.0], np.cumsum(sec)])
    links = []
    for j in range(len(sec) - 1):
        if (j + 1) % 3:
            Vend = [V[xb[(j, c, p)]] for c in range(nc) for p in range(3)]
            # across the sectionalising insulation at position p: the sheath
            # ending there and the one starting there
            across = [abs(V[xb[(j, c, p)]] - V[xb[(j, c, (p - 1) % 3)]])
                      for c in range(nc) for p in range(3)]
            links.append(dict(x_km=float(xs[j + 1]), V_max=float(max(abs(v) for v in Vend)),
                              V_across_max=float(max(across))))
    majors = [dict(x_km=float(xs[3 * (q + 1)]), V=float(abs(V[2 + q])),
                   I_earth_A=float(abs(V[2 + q]) / R_major)) for q in range(nmaj)]
    out = dict(If_kA=If_kA, fault_at=fault_at, bonding="cross_bonded", formation=formation,
               Ig_kA=abs(Ig) / 1e3, Sf=abs(Ig) / If, IgA_kA=abs(IgA) / 1e3,
               IgB_kA=abs(IgB) / 1e3, I_sheath_kA=abs(Ish) / 1e3,
               I_sheath_max_kA=float(max(np.abs(x).max() for x in Isec)) / 1e3,
               GPR_A=float(abs(V[0])), GPR_B=float(abs(V[1])),
               minor_km=sec, n_major=n_major, link_boxes=links, joints=majors,
               circuits=nc, length_km=float(xs[-1]),
               formula="cross-bonded sheaths solved node by node with the transpositions "
                       "(Carson matrix of sheaths and faulted core)")
    end = "B" if fault_at == "B" else "A"
    out["note"] = (
        f"For an earth fault at {end}, {abs(Ish) / 1e3:.2f} kA of the {If_kA:.2f} kA returns in "
        f"the cross-bonded sheaths and {abs(Ig) / 1e3:.2f} kA enters the soil at {end} "
        f"(S_f = {abs(Ig) / If:.3f}). "
        + (f"The highest sheath voltage at a link box is {max(l['V_max'] for l in links):.0f} V "
           f"to remote earth and {max(l['V_across_max'] for l in links):.0f} V across a "
           f"sectionalising joint; the sheath voltage limiters must withstand it."
           if links else ""))
    return out
