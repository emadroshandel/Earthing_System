"""
System neutral grounding for industrial and commercial power systems.

IEEE Std 142 (Green Book) and IEEE Std 32 / C62.92:

* selection between solid, low-resistance, high-resistance, reactance
  grounded and ungrounded systems
* neutral earthing resistor (NER / NGR) sizing and rating
* system charging current estimation for high-resistance grounding
* effectively-grounded test (X0/X1, R0/X1) and coefficient of grounding
  for surge-arrester selection
"""

from __future__ import annotations

import math

SQRT3 = math.sqrt(3.0)

GROUNDING_METHODS = {
    "solid": dict(
        name="Solidly grounded",
        fault_current="Comparable to the three-phase fault current",
        pros="Simple; effective overvoltage control; straightforward "
             "ground-fault protection.",
        cons="Large arc-flash energy and equipment damage at the fault; "
             "immediate trip on the first earth fault.",
        typical="LV systems (400/230 V), and HV transmission."),
    "low_resistance": dict(
        name="Low-resistance grounded",
        fault_current="100 A – 1000 A (typically 200–400 A)",
        pros="Limits damage while keeping enough current for selective "
             "relaying; controls transient overvoltage.",
        cons="Still trips on the first fault; resistor is a maintained item.",
        typical="MV industrial systems, 2.4–15 kV."),
    "high_resistance": dict(
        name="High-resistance grounded",
        fault_current="≤ 10 A, and always ≥ 3·I_C0",
        pros="Continuity of service on the first earth fault; no arc-flash "
             "from a single ground fault; transient overvoltage limited.",
        cons="Requires fault-locating scheme; unsuitable when line-to-neutral "
             "loads are connected.",
        typical="Continuous-process plants, generator neutrals, 480 V–15 kV."),
    "reactance": dict(
        name="Reactance grounded",
        fault_current="Set so that X0 ≤ 10·X1 (typically 25–60 % of 3-ph)",
        pros="Limits fault current without the resistor losses.",
        cons="Narrow window before ferroresonant / transient overvoltage.",
        typical="Generator neutrals, some MV systems."),
    "ungrounded": dict(
        name="Ungrounded",
        fault_current="Capacitive charging current only (typically < 10 A)",
        pros="Service continuity on the first fault.",
        cons="Severe transient overvoltage from restriking arcing faults; "
             "no longer recommended for new installations.",
        typical="Legacy systems; being replaced by high-resistance grounding."),
}


def charging_current(V_ll_kV: float, cable_km: float = 0.0,
                     C0_uF_per_km: float = 0.25,
                     motors_kVA: float = 0.0, transformers_kVA: float = 0.0,
                     f: float = 50.0, overhead_km: float = 0.0,
                     C0_oh_uF_per_km: float = 0.006) -> dict:
    """Estimate the system zero-sequence charging current 3·I_C0 (A).

        I_C0 = 2*pi*f*C0*V_LN   per phase;   3*I_C0 is the total earth-fault
        capacitive current of an ungrounded system.
    """
    V_ln = V_ll_kV * 1000.0 / SQRT3
    C_total = cable_km * C0_uF_per_km + overhead_km * C0_oh_uF_per_km
    Ic_cable = 3.0 * 2.0 * math.pi * f * (C_total * 1e-6) * V_ln
    # rule-of-thumb allowances (IEEE 142 Table 1)
    Ic_motor = motors_kVA * 0.0002 / 1.0
    Ic_tx = transformers_kVA * 0.00005
    total = Ic_cable + Ic_motor + Ic_tx
    return dict(three_IC0=total, cable_component=Ic_cable,
                motor_component=Ic_motor, transformer_component=Ic_tx,
                C_total_uF=C_total, V_ln=V_ln, f=f,
                formula="3·I_C0 = 3·2πf·C₀·V_LN  plus machine allowances")


def hrg_resistor(V_ll_kV: float, three_IC0: float,
                 margin: float = 1.0) -> dict:
    """High-resistance grounding: the resistor must pass I_R ≥ 3·I_C0.

        R_N = V_LN / I_R
    """
    V_ln = V_ll_kV * 1000.0 / SQRT3
    I_R = max(three_IC0 * margin, three_IC0)
    R = V_ln / I_R if I_R else float("inf")
    P_cont = V_ln ** 2 / R if R else 0.0
    return dict(V_ln=V_ln, I_R=I_R, R_ohm=R, three_IC0=three_IC0,
                total_fault_current=math.hypot(I_R, three_IC0),
                continuous_power_W=P_cont,
                rating_note="Rate the resistor for continuous duty when the "
                            "system is designed to run with a standing earth "
                            "fault (IEEE Std 32 continuous rating).",
                criterion_met=I_R >= three_IC0,
                formula="R_N = V_LN / I_R,  I_R ≥ 3·I_C0  (IEEE Std 142 §1.4)")


def lrg_resistor(V_ll_kV: float, I_target_A: float, t_rating_s: float = 10.0,
                 X0_source: float = 0.0) -> dict:
    """Low-resistance (limited) grounding resistor sizing."""
    V_ln = V_ll_kV * 1000.0 / SQRT3
    R = V_ln / I_target_A
    return dict(V_ln=V_ln, I_target=I_target_A, R_ohm=R,
                energy_kJ=I_target_A ** 2 * R * t_rating_s / 1000.0,
                power_W=I_target_A ** 2 * R,
                time_rating_s=t_rating_s,
                formula="R_N = V_LN / I_f  (IEEE Std 32 short-time rating)")


def reactor_grounding(V_ll_kV: float, I_target_A: float,
                      X1: float | None = None) -> dict:
    V_ln = V_ll_kV * 1000.0 / SQRT3
    X = V_ln / I_target_A
    out = dict(V_ln=V_ln, X_ohm=X, I_target=I_target_A,
               formula="X_N = V_LN / I_f")
    if X1:
        X0 = 3.0 * X + X1
        out.update(X0=X0, X0_over_X1=X0 / X1,
                   acceptable=X0 / X1 <= 10.0,
                   note="X₀/X₁ should stay ≤ 10 to avoid ferroresonance and "
                        "excessive transient overvoltage.")
    return out


def effectively_grounded(X0: float, X1: float, R0: float = 0.0) -> dict:
    """IEEE C62.92 effectively-grounded test: X0/X1 ≤ 3 and R0/X1 ≤ 1."""
    a = X0 / X1 if X1 else float("inf")
    b = R0 / X1 if X1 else float("inf")
    eff = a <= 3.0 and b <= 1.0
    # coefficient of grounding (approximate closed form)
    k = math.sqrt(3.0) * math.sqrt(a ** 2 + a + 1.0) / (a + 2.0) if a > -2 else 1.0
    cog = min(max(k / math.sqrt(3.0), 0.0), 1.0)
    return dict(X0_over_X1=a, R0_over_X1=b, effectively_grounded=eff,
                coefficient_of_grounding=cog,
                arrester_duty_pu=cog * math.sqrt(3.0),
                note=("Effectively grounded — 80 % rated arresters are "
                      "normally acceptable." if eff else
                      "Not effectively grounded — use 100 % (full-rated) "
                      "arresters and check the temporary overvoltage duty."),
                formula="IEEE Std C62.92: X₀/X₁ ≤ 3 and R₀/X₁ ≤ 1")


def recommend(V_ll_kV: float, continuity_critical: bool,
              ln_loads: bool, three_IC0: float,
              arc_flash_concern: bool = True) -> dict:
    """Suggest a grounding method for the given system requirements."""
    reasons = []
    if ln_loads and V_ll_kV <= 1.0:
        choice = "solid"
        reasons.append("Line-to-neutral loads are supplied, so the neutral "
                       "must be solidly earthed.")
    elif continuity_critical and three_IC0 <= 10.0:
        choice = "high_resistance"
        reasons.append("Continuity of service is critical and the system "
                       f"charging current (3·I_C0 = {three_IC0:.1f} A) is low "
                       "enough for high-resistance grounding.")
    elif V_ll_kV > 1.0:
        choice = "low_resistance"
        reasons.append("Medium-voltage system without line-to-neutral loads: "
                       "low-resistance grounding limits damage while keeping "
                       "selective earth-fault relaying practical.")
    else:
        choice = "solid"
        reasons.append("Default LV practice.")
    if arc_flash_concern and choice == "solid" and V_ll_kV > 0.6:
        reasons.append("Consider resistance grounding to reduce arc-flash "
                       "incident energy from earth faults.")
    return dict(method=choice, data=GROUNDING_METHODS[choice], reasons=reasons,
                alternatives={k: v for k, v in GROUNDING_METHODS.items()
                              if k != choice})


def equipment_grounding_conductor(I_fault_A: float, t_s: float,
                                  material: str = "copper") -> dict:
    """Equipment grounding conductor sizing (IEEE 142 §2.4, adiabatic)."""
    from .conductor import adiabatic_area
    return adiabatic_area(I_fault_A, t_s, material, "bare", "separate")
