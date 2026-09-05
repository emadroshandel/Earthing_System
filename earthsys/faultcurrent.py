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
    """Line-to-line-to-earth fault earth current, IEC 60909-0 Eq. (46)."""
    num = SQRT3 * c * Un_kV * 1e3 * abs(Z2)
    den = abs(Z1 * Z2 + Z1 * Z0 + Z2 * Z0)
    Ik2E = num / den
    Ie = SQRT3 * c * Un_kV * 1e3 * abs(Z2 - Z0) / den   # earth return component
    return dict(Ik2E_kA=Ik2E / 1000.0, IkE2E_kA=Ie / 1000.0,
                formula="IEC 60909-0 Eq. (46)/(47)")


def _c(z: complex) -> dict:
    return dict(r=z.real, x=z.imag, mag=abs(z),
                angle_deg=math.degrees(cmath.phase(z)) if z != 0 else 0.0)


# ---------------------------------------------------------------------------
# IEEE 80 grid current
# ---------------------------------------------------------------------------

def decrement_factor(tf: float, xr_ratio: float, f: float = 50.0) -> dict:
    """IEEE Std 80-2013 Eq. (79):

        D_f = sqrt( 1 + (T_a/t_f)(1 - e^(-2 t_f / T_a)) ),  T_a = X/(2*pi*f*R)
    """
    Ta = xr_ratio / (2.0 * math.pi * f)
    Df = math.sqrt(1.0 + (Ta / tf) * (1.0 - math.exp(-2.0 * tf / Ta)))
    return dict(Df=Df, Ta=Ta, tf=tf, xr_ratio=xr_ratio, f=f,
                formula="IEEE Std 80-2013 Eq. (79)")


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


SPLIT_FACTOR_GUIDE = [
    dict(case="Distribution substation, no transmission line, no neutral", Sf=1.00),
    dict(case="Distribution substation, 1 transmission line, 1 distribution neutral", Sf=0.60),
    dict(case="Distribution substation, 2 transmission lines, 4 neutrals", Sf=0.28),
    dict(case="Transmission substation, 4 lines with shield wires", Sf=0.20),
    dict(case="Transmission substation, 8+ lines with shield wires", Sf=0.12),
    dict(case="Generating station, extensive metallic network", Sf=0.05),
]


def grid_current(three_I0_kA: float, Sf: float, Df: float,
                 Cp: float = 1.0) -> dict:
    """Maximum grid current, IEEE Std 80-2013 Eq. (77)/(78).

        I_g = S_f * 3I_0 * C_p       (symmetrical grid current)
        I_G = D_f * I_g              (maximum grid current)
    """
    Ig = Sf * three_I0_kA * Cp
    IG = Df * Ig
    return dict(Ig_kA=Ig, IG_kA=IG, Sf=Sf, Df=Df, Cp=Cp,
                three_I0_kA=three_I0_kA,
                formula="IEEE Std 80-2013 Eq. (77)–(78): I_G = D_f·S_f·C_p·3I₀")


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
