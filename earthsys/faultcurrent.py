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
    kappa = 1.02 + 0.98 * math.exp(-3.0 / xr) if xr != float("inf") else 2.0
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
                formula="IEEE Std 80-2013 Eq. (78), (69): I_G = D_f·S_f·C_p·3I₀")


def thermal_equivalent(Ik_kA: float, tk: float, xr_ratio: float,
                       f: float = 50.0) -> dict:
    """Thermal equivalent short-circuit current, IEC 60909-0 clause 4.8."""
    kappa = 1.02 + 0.98 * math.exp(-3.0 / xr_ratio)
    fk = f * tk
    if fk <= 0:
        m = 0.0
    else:
        m = (math.exp(4.0 * fk * math.log(kappa - 1.0)) - 1.0) / (2.0 * fk * math.log(kappa - 1.0)) \
            if kappa > 1.0000001 else 0.0
    m = max(m, 0.0)
    n = 1.0                      # far-from-generator fault
    Ith = Ik_kA * math.sqrt(m + n)
    return dict(Ith_kA=Ith, m=m, n=n, kappa=kappa,
                formula="IEC 60909-0 Eq. (66): I_th = Iₖ\"·√(m+n)")
