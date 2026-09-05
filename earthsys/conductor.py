"""
Earthing-conductor thermal sizing.

* IEEE Std 80-2013, clause 11.3, Eq. (37) / (42)  -- symmetrical and
  asymmetrical current, full material table
* IEC 60364-5-54 clause 543.1.2 -- adiabatic equation S = sqrt(I^2 t)/k
* IEC 60364-5-54 Table 54.2 -- simplified PE selection from the line conductor
"""

from __future__ import annotations

import math

from .materials import (IEEE80_MATERIALS, K_FACTORS_BURIED, K_FACTORS_IN_CABLE,
                        K_FACTORS_SEPARATE, MIN_EARTHING_CONDUCTOR,
                        diameter_from_area, next_standard_area)


# ---------------------------------------------------------------------------
# IEEE 80
# ---------------------------------------------------------------------------

def ieee80_conductor_area(I_kA: float, tc: float, material: str = "cu_hard",
                          Ta: float = 40.0, Tm: float | None = None) -> dict:
    """Minimum conductor area per IEEE Std 80-2013 Eq. (37).

    I_kA : rms current through the conductor (kA)
    tc   : duration of current flow (s)
    Ta   : ambient temperature (degC)
    Tm   : maximum allowable temperature (degC); defaults to the material
           fusing temperature, but should be reduced for bolted/brazed joints.

        A_mm2 = I / sqrt( (TCAP*1e-4)/(tc*alpha_r*rho_r)
                          * ln( (K0 + Tm)/(K0 + Ta) ) )
    """
    m = IEEE80_MATERIALS[material]
    Tm = m["Tm"] if Tm is None else float(Tm)
    K0, alpha_r, rho_r, TCAP = m["K0"], m["alpha_r"], m["rho_r"], m["TCAP"]

    inner = (TCAP * 1.0e-4) / (tc * alpha_r * rho_r) * math.log((K0 + Tm) / (K0 + Ta))
    if inner <= 0:
        raise ValueError("Invalid temperature limits for this material.")
    A = I_kA / math.sqrt(inner)

    return dict(
        area_mm2=A,
        diameter_mm=diameter_from_area(A),
        area_kcmil=A * 1.9735,
        standard_mm2=next_standard_area(A),
        material=m["name"], material_key=material,
        Tm=Tm, Ta=Ta, tc=tc, I_kA=I_kA,
        formula="IEEE Std 80-2013 Eq. (37)",
        current_density_A_per_mm2=(I_kA * 1000.0 / A) if A else 0.0,
    )


def ieee80_asymmetric_area(I_kA: float, tc: float, Df: float,
                           material: str = "cu_hard", Ta: float = 40.0,
                           Tm: float | None = None) -> dict:
    """Sizing for the asymmetrical (dc-offset) case: I_F = Df * I_f."""
    r = ieee80_conductor_area(I_kA * Df, tc, material, Ta, Tm)
    r["Df"] = Df
    r["I_symmetrical_kA"] = I_kA
    r["I_asymmetrical_kA"] = I_kA * Df
    r["formula"] = "IEEE Std 80-2013 Eq. (37) with decrement factor D_f"
    return r


def ieee80_fusing_time(A_mm2: float, I_kA: float, material: str = "cu_hard",
                       Ta: float = 40.0, Tm: float | None = None) -> float:
    """Time (s) for the given conductor to reach Tm at current I_kA."""
    m = IEEE80_MATERIALS[material]
    Tm = m["Tm"] if Tm is None else float(Tm)
    K0, alpha_r, rho_r, TCAP = m["K0"], m["alpha_r"], m["rho_r"], m["TCAP"]
    return ((TCAP * 1.0e-4) / (alpha_r * rho_r)
            * math.log((K0 + Tm) / (K0 + Ta)) * (A_mm2 / I_kA) ** 2)


# ---------------------------------------------------------------------------
# IEC 60364-5-54
# ---------------------------------------------------------------------------

def k_factor(material: str, insulation: str, installation: str = "separate") -> dict:
    table = {"separate": K_FACTORS_SEPARATE,
             "in_cable": K_FACTORS_IN_CABLE,
             "buried": K_FACTORS_BURIED}[installation]
    key = (material, insulation)
    if key not in table:
        raise ValueError(f"No k factor for {material}/{insulation} ({installation}).")
    return table[key]


def adiabatic_area(I_A: float, t_s: float, material: str = "copper",
                   insulation: str = "pvc70",
                   installation: str = "separate") -> dict:
    """S = sqrt(I^2 * t) / k  -- IEC 60364-5-54 Eq. (543.1)."""
    kf = k_factor(material, insulation, installation)
    S = math.sqrt(I_A * I_A * t_s) / kf["k"]
    return dict(area_mm2=S, standard_mm2=next_standard_area(S),
                k=kf["k"], k_label=kf["label"],
                initial_temp=kf["Ti"], final_temp=kf["Tf"],
                I_A=I_A, t_s=t_s,
                formula="IEC 60364-5-54 Eq. (543.1): S = √(I²t)/k")


def pe_from_line_conductor(S_line_mm2: float, same_material: bool = True,
                           k_line: float | None = None,
                           k_pe: float | None = None) -> dict:
    """Simplified PE selection -- IEC 60364-5-54 Table 54.2 / BS 7671 543.1.4.

        S <= 16          ->  S_pe = S
        16 < S <= 35     ->  S_pe = 16
        S  > 35          ->  S_pe = S/2

    When the PE is of a different material the result is scaled by k1/k2.
    """
    if S_line_mm2 <= 16.0:
        S_pe = S_line_mm2
        rule = "S ≤ 16 mm² → S_PE = S"
    elif S_line_mm2 <= 35.0:
        S_pe = 16.0
        rule = "16 < S ≤ 35 mm² → S_PE = 16 mm²"
    else:
        S_pe = S_line_mm2 / 2.0
        rule = "S > 35 mm² → S_PE = S/2"

    scaled = S_pe
    if not same_material and k_line and k_pe:
        scaled = S_pe * k_line / k_pe
        rule += f"  ×(k1/k2 = {k_line}/{k_pe})"

    return dict(area_mm2=scaled, standard_mm2=next_standard_area(scaled),
                base_area_mm2=S_pe, rule=rule,
                formula="IEC 60364-5-54 Table 54.2")


def min_buried_earthing_conductor(corrosion_protected: bool,
                                  mechanically_protected: bool) -> dict:
    """IEC 60364-5-54 Table 54.1 minimum sizes for a buried earthing conductor."""
    if not corrosion_protected:
        key = ("unprotected_corrosion", "any")
    else:
        key = ("protected_corrosion",
               "protected_mech" if mechanically_protected else "unprotected_mech")
    v = MIN_EARTHING_CONDUCTOR[key]
    return dict(copper_mm2=v["copper"], steel_mm2=v["steel"],
                condition=" / ".join(key),
                formula="IEC 60364-5-54 Table 54.1")


def bonding_conductors(S_pe_main_mm2: float, material: str = "copper") -> dict:
    """Main and supplementary protective bonding conductor sizing.

    Main protective bonding (IEC 60364-5-54 544.1): not less than half the
    cross-section of the main earthing conductor, minimum 6 mm² copper,
    need not exceed 25 mm² copper (or equivalent).
    Supplementary bonding (544.2): between two exposed-conductive-parts, not
    less than the smaller protective conductor; between an exposed and an
    extraneous part, not less than half the protective conductor.
    """
    main = max(6.0, min(25.0, S_pe_main_mm2 / 2.0))
    return dict(
        main_bonding_mm2=main,
        main_bonding_standard=next_standard_area(main),
        supplementary_exposed_exposed_mm2=max(2.5, S_pe_main_mm2),
        supplementary_exposed_extraneous_mm2=max(2.5, S_pe_main_mm2 / 2.0),
        min_mechanically_protected_mm2=2.5,
        min_unprotected_mm2=4.0,
        formula="IEC 60364-5-54 clauses 544.1 and 544.2",
    )
