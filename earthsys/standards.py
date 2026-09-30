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
The wider standards landscape (new in 1.3.0).

Earthing System designs to IEEE 80, IEC 60364, IEC 62305 and IEEE 142. This module
adds two things around those four:

1. ``REGISTRY`` — every standard, guide and technical brochure the software and
   its tutorial refer to, with edition, status and the design area it serves.
   The report prints the entries relevant to the modules that were run.

2. Small, well-defined calculations from the other codes, used as
   *cross-checks* and teaching aids. None of them changes a pass/fail verdict:

   * ``en50522_touch_limit``      permissible touch voltage U_Tp(t_F),
                                  BS EN 50522 / IEC 61936-1 (from IEC 60479-1)
   * ``ieee80_bare_touch``        IEEE 80 touch limit with no surface layer,
                                  for a like-for-like comparison with U_Tp
   * ``eg0_coincidence``          coincidence probability, ENA EG-0 / AS 2067
   * ``eg0_risk_band``            negligible / ALARP / intolerable
   * ``alipio_visacro``           frequency-dependent soil, CIGRE TB 781
   * ``far_field_potential`` and
     ``epr_contour_distance``     transferred-EPR zone around an electrode
                                  (AS/NZS 3835.1, ENA EREC S34, AS/NZS 4853)
   * ``carson_depth`` and
     ``mutual_impedance_per_km``  inductive coupling to pipelines and
                                  telecom lines (CIGRE TB 95, AS/NZS 4853)
   * ``hvdc_temperature_rise``    steady-state thermal limit of an HVDC
                                  electrode (EPRI EL-2020)
   * ``faraday_mass_loss``        anodic dissolution of an electrode (EPRI EL-2020)
   * ``srg_max_aperture``         aperture of a signal-reference / mesh bonding
                                  network (IEEE 1100, BS EN 50310)

The numbers here are the published constants or textbook physics; the
standards themselves remain the authority.
"""

from __future__ import annotations

import math

MU0 = 4e-7 * math.pi
EPS0 = 8.8541878128e-12
FARADAY = 96485.33212          # C/mol
SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0

# ---------------------------------------------------------------------------
# 1. Registry
# ---------------------------------------------------------------------------
# role: "implemented" — the software computes to it;
#       "cross-check" — a calculation from it is reported beside the main one;
#       "reference"   — cited for scope, practice or further reading.

REGISTRY = [
    # Substation earthing ----------------------------------------------------
    dict(id="IEEE Std 80-2013", area="substation", role="implemented",
         title="IEEE Guide for Safety in AC Substation Grounding",
         note="Modules 3-4. A revision (P80) is in preparation."),
    dict(id="AS 2067:2016", area="substation", role="reference",
         title="Substations and high voltage installations exceeding 1 kV a.c.",
         note="Australian; risk-based touch/step assessment via ENA EG-0."),
    dict(id="BS EN 50522:2022", area="substation", role="cross-check",
         title="Earthing of power installations exceeding 1 kV a.c.",
         note="Checked against the 2022 text (A1:2024 not checked). U_Tp from Table B.4 and U_vTp from Formula (A.3) reported beside IEEE 80."),
    dict(id="ENA DOC 045-2022 (EG-1)", area="substation", role="reference",
         title="Substation Earthing Guide", note="Energy Networks Australia."),
    dict(id="IEC 61936-1:2021", area="substation", role="reference",
         title="Power installations exceeding 1 kV AC and 1.5 kV DC — Part 1: AC",
         note="Same U_Tp curve as EN 50522."),
    # Testing ----------------------------------------------------------------
    dict(id="IEEE Std 81-2025", area="testing", role="implemented",
         title="IEEE Guide for Measuring Earth Resistivity, Ground Impedance, "
               "and Earth Surface Potentials of a Grounding System",
         note="Module 1. Revision of IEEE Std 81-2012; formulas unchanged."),
    dict(id="ENA TS 41-24:2018", area="testing", role="reference",
         title="Guidelines for the design, installation, testing and maintenance "
               "of main earthing systems in substations",
         note="Energy Networks Association (UK), Issue 2."),
    # Touch and step ---------------------------------------------------------
    dict(id="IEC TS 60479-1:2005+AMD1:2016", area="touch-step", role="cross-check",
         title="Effects of current on human beings and livestock — Part 1: General aspects",
         note="Body impedance (Table 1) and curves c1-c3. Basis of U_Tp, U_vTp and of EG-0 fibrillation probability."),
    dict(id="IEC 60479-2:2019", area="touch-step", role="reference",
         title="Effects of current on human beings and livestock — Part 2: Special aspects",
         note=""),
    dict(id="ENA DOC 025-2022 (EG-0)", area="touch-step", role="cross-check",
         title="Power System Earthing Guide — Part 1: Management Principles",
         note="Energy Networks Australia. Coincidence probability and risk bands."),
    # Renewables -------------------------------------------------------------
    dict(id="IEC 62305-3:2010", area="renewables", role="implemented",
         title="Protection against lightning — Part 3: Physical damage to structures and life hazard",
         note="Modules 7-8. Edition 3 (2024) published."),
    dict(id="IEC 61400-24:2019", area="renewables", role="reference",
         title="Wind energy generation systems — Part 24: Lightning protection",
         note="+AMD1:2024. Wind-turbine earthing builds on IEC 62305-3."),
    dict(id="IEEE Std 2760-2020", area="renewables", role="reference",
         title="IEEE Guide for Wind Power Plant Grounding System Design for Personnel Safety",
         note="Sometimes miscited as IEEE 2870."),
    dict(id="IEEE Std 2778-2020", area="renewables", role="reference",
         title="IEEE Guide for Solar Power Plant Grounding for Personnel Protection",
         note=""),
    # Pipelines --------------------------------------------------------------
    dict(id="AS/NZS 4853:2012", area="pipelines", role="cross-check",
         title="Electrical hazards on metallic pipelines",
         note="Conductive (EPR) and inductive (LFI) coupling."),
    dict(id="CIGRE TB 95", area="pipelines", role="reference",
         title="Guide on the influence of high voltage AC power systems on metallic pipelines",
         note="1995."),
    # Industrial and commercial ---------------------------------------------
    dict(id="IEEE Std 142-2007", area="industrial", role="implemented",
         title="IEEE Recommended Practice for Grounding of Industrial and Commercial Power Systems",
         note="Module 9 (Green Book)."),
    dict(id="IEC 60364-4-41:2005+A1:2017", area="industrial", role="implemented",
         title="Low-voltage electrical installations — Protection against electric shock",
         note="Module 6."),
    dict(id="IEC 60364-5-54:2011+A1:2021", area="industrial", role="implemented",
         title="Low-voltage electrical installations — Earthing arrangements and protective conductors",
         note="Module 6."),
    dict(id="AS/NZS 3000:2018", area="industrial", role="reference",
         title="Electrical installations (Australian/New Zealand Wiring Rules)",
         note="+Amdts 1-3."),
    dict(id="BS 7671:2018", area="industrial", role="reference",
         title="Requirements for Electrical Installations (IET Wiring Regulations, 18th Edition)",
         note="Current consolidated version +A4:2026."),
    dict(id="BS 7430:2011+A1:2015", area="industrial", role="implemented",
         title="Code of practice for protective earthing of electrical installations",
         note="Module 6 λ tables. Replaced by BS 7430:2026."),
    # Overhead lines ---------------------------------------------------------
    dict(id="AS/NZS 7000:2016", area="overhead-lines", role="reference",
         title="Overhead line design", note="Structure earthing and EPR."),
    dict(id="CIGRE TB 781", area="overhead-lines", role="cross-check",
         title="Impact of soil-parameter frequency dependence on the response of grounding "
               "electrodes and on the lightning performance of electrical systems",
         note="2019. Alipio-Visacro soil model."),
    dict(id="CIGRE TB 839", area="overhead-lines", role="reference",
         title="Procedures for estimating the lightning performance of transmission lines — new aspects",
         note="2021."),
    dict(id="IEEE Std 1243-1997", area="overhead-lines", role="reference",
         title="IEEE Guide for Improving the Lightning Performance of Transmission Lines",
         note=""),
    # HVDC -------------------------------------------------------------------
    dict(id="EPRI EL-2020", area="hvdc", role="cross-check",
         title="HVDC Ground Electrode Design", note="EPRI final report, 1981."),
    # Data centres -----------------------------------------------------------
    dict(id="IEC 60364-5-548:1996", area="data-centres", role="reference",
         title="Earthing arrangements and equipotential bonding for information technology installations",
         note="Withdrawn 2002; content moved into IEC 60364-5-54 and IEC 60364-4-44."),
    dict(id="IEEE Std 1100-2005", area="data-centres", role="cross-check",
         title="IEEE Recommended Practice for Powering and Grounding Electronic Equipment",
         note="Emerald Book; inactive-reserved since 2021."),
    # Telecom ----------------------------------------------------------------
    dict(id="AS/NZS 3835.1:2006", area="telecom", role="cross-check",
         title="Earth potential rise — Protection of telecommunications network users, "
               "personnel and plant — Code of practice",
         note=""),
    dict(id="BS EN 50310:2016+A1:2020", area="telecom", role="reference",
         title="Telecommunications bonding networks for buildings and other structures",
         note=""),
    # Fault-current distribution --------------------------------------------
    dict(id="ENA EREC S34:2018", area="fault-distribution", role="cross-check",
         title="A guide for assessing the rise of earth potential at electrical installations",
         note="Issue 2. Ground-return fraction, cable sheaths, hot zones."),
    dict(id="CIGRE TB 347", area="fault-distribution", role="reference",
         title="Earth potential rises in specially bonded screen systems", note="2008."),
    dict(id="IEC 60909-0:2016", area="fault-distribution", role="implemented",
         title="Short-circuit currents in three-phase a.c. systems — Calculation of currents",
         note="Module 2."),
]

AREAS = {
    "substation": "Substation earthing",
    "testing": "Testing and measurement",
    "touch-step": "Touch and step voltage criteria",
    "renewables": "Renewable generation",
    "pipelines": "Metallic pipelines",
    "industrial": "Industrial and commercial installations",
    "overhead-lines": "Overhead lines",
    "hvdc": "HVDC earth electrodes",
    "data-centres": "Data centres",
    "telecom": "Telecommunications",
    "fault-distribution": "Fault-current distribution",
}

# Which areas each report section draws on.
MODULE_AREAS = {
    "soil": ["testing"],
    "fault": ["fault-distribution"],
    "conductor": ["substation"],
    "grid": ["substation", "touch-step", "fault-distribution"],
    "bem": ["substation", "touch-step"],
    "building": ["industrial", "data-centres", "telecom"],
    "lightning": ["renewables", "overhead-lines"],
    "airterm": ["renewables"],
    "sysgnd": ["industrial"],
}


def by_area(area: str) -> list:
    return [s for s in REGISTRY if s["area"] == area]


def for_modules(modules) -> list:
    """Registry entries relevant to the given report sections, in registry order."""
    areas = {a for m in modules for a in MODULE_AREAS.get(m, [])}
    return [s for s in REGISTRY if s["area"] in areas]


# ---------------------------------------------------------------------------
# 2. Touch-voltage criteria
# ---------------------------------------------------------------------------

# BS EN 50522:2022 Table B.4 / Figure 8: permissible touch voltage U_Tp against
# fault duration t_F (rounded to 5 V). Weighted over four touching conditions,
# no additional resistance; IEC 60479-1:2018 body impedance (50 % of the
# population) and curve c2.  Up to 1.3.4 the software used the 2010 edition's
# Table B.3 (716, 654, 537, 220, 117, 96, 86, 85 V), kept below for reference.
EN50522_UTP = [
    (0.05, 725.0), (0.10, 655.0), (0.20, 525.0), (0.50, 225.0),
    (1.00, 115.0), (2.00, 95.0), (5.00, 85.0), (10.0, 85.0),
]
EN50522_UTP_2010 = [
    (0.05, 716.0), (0.10, 654.0), (0.20, 537.0), (0.50, 220.0),
    (1.00, 117.0), (2.00, 96.0), (5.00, 86.0), (10.0, 85.0),
]
# BS EN 50522:2022 Table B.1: permissible body current I_B (curve c2 of
# IEC 60479-1:2018, left hand to both feet) against fault duration.
# (The 2010 edition printed 750 mA at 0.10 s.)
EN50522_IB = [
    (0.05, 0.900), (0.10, 0.800), (0.20, 0.600), (0.50, 0.200),
    (1.00, 0.080), (2.00, 0.060), (5.00, 0.051), (10.0, 0.050),
]


def _loglog(pts, x):
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            w = math.log(x / x0) / math.log(x1 / x0)
            return math.exp(math.log(y0) + w * math.log(y1 / y0))
    raise AssertionError("unreachable")


def en50522_body_current(t_F: float) -> float:
    """Permissible body current I_B (A) of BS EN 50522:2022 Table B.1,
    interpolated log-log and clamped at the ends of the table."""
    if t_F <= 0:
        raise ValueError("fault duration must be positive")
    return _loglog(EN50522_IB, t_F)


def en50522_touch_limit(t_F: float) -> float:
    """Permissible touch voltage U_Tp (V) for fault duration t_F (s),
    BS EN 50522:2022 Table B.4 / Figure 8.

    Log-log interpolation of the tabulated points; clamped at the ends of the
    table (725 V below 0.05 s, 85 V above 10 s; the standard allows 80 V for
    durations much longer than 10 s)."""
    if t_F <= 0:
        raise ValueError("fault duration must be positive")
    return _loglog(EN50522_UTP, t_F)


# BS EN 50522 Table B.2 = IEC TS 60479-1:2005+AMD1:2016 Table 1, 50 % column:
# total body impedance Z_T (Ω), hand to hand, large dry contact areas, against
# touch voltage U_T (V).  Values correspond to about 0.1 s of current flow.
EN50522_ZT = [
    (25.0, 3250.0), (50.0, 2500.0), (75.0, 2000.0), (100.0, 1725.0),
    (125.0, 1550.0), (150.0, 1400.0), (175.0, 1325.0), (200.0, 1275.0),
    (225.0, 1225.0), (400.0, 950.0), (500.0, 850.0), (700.0, 775.0),
    (1000.0, 775.0),
]


def en50522_body_impedance(U_T: float) -> float:
    """Total body impedance Z_T(U_T) of BS EN 50522 Table B.2 (IEC 60479-1
    Table 1, 50 % of the population, hand to hand), interpolated linearly and
    clamped at 3250 Ω below 25 V and 775 Ω above 700 V."""
    if U_T <= 0:
        raise ValueError("touch voltage must be positive")
    pts = EN50522_ZT
    if U_T <= pts[0][0]:
        return pts[0][1]
    if U_T >= pts[-1][0]:
        return pts[-1][1]
    for (u0, z0), (u1, z1) in zip(pts, pts[1:]):
        if u0 <= U_T <= u1:
            return z0 + (z1 - z0) * (U_T - u0) / (u1 - u0)
    raise AssertionError("unreachable")


def en50522_prospective_touch_limit(t_F: float, rho_s: float,
                                    R_F1: float = 1000.0,
                                    Cs: float = 1.0) -> dict:
    """Permissible prospective touch voltage U_vTp of BS EN 50522:2022,
    Formula (A.3) with the circuit of Figure B.2 (heart current factor 1):

        U_vTp = U_Tp(t_F) + I_B(t_F)·(R_H + R_F),  R_F = R_F1 + R_F2,
        R_F2 = 1.5 m⁻¹·C_s·ρ_s

    with U_Tp from Table B.4 and I_B from Table B.1.  R_F1 is the footwear
    resistance (1000 Ω in Figure B.3), R_F2 the resistance to earth of the
    standing point; the standard writes R_F2 = 1.5·ρ_S (C_s = 1, an
    infinitely thick layer), so pass the IEEE 80 C_s for a thin layer.
    U_vTp is compared with a prospective touch voltage such as E_m.

    Up to 1.3.4 this followed the 2010 edition, I_B = U_Tp/Z_T(U_Tp) with the
    hand-to-hand Z_T of Table B.2, which gives a smaller I_B (178 mA against
    200 mA at 0.5 s) and so a U_vTp about 10 % lower."""
    if rho_s < 0 or R_F1 < 0:
        raise ValueError("rho_s and R_F1 must not be negative")
    U = en50522_touch_limit(t_F)
    IB = en50522_body_current(t_F)
    Z = en50522_body_impedance(U)
    RF = R_F1 + 1.5 * Cs * rho_s
    return dict(U_Tp=U, Z_T=Z, I_B=IB, R_F=RF, U_vTp=U + IB * RF,
                formula="U_vTp = U_Tp + I_B·(R_F1 + 1.5·ρ_s)  "
                        "(BS EN 50522:2022 Formula (A.3), Tables B.1 and B.4)")


def ieee80_bare_touch(t_s: float, body_weight: int = 70) -> float:
    """IEEE 80 tolerable touch voltage across the body resistance alone,
    R_B = 1000 Ω, with no foot, footwear or surface-layer resistance (the
    like-for-like comparison with U_Tp): E = 1000·k/√t_s."""
    k = 0.157 if body_weight == 70 else 0.116
    return 1000.0 * k / math.sqrt(t_s)


def touch_cross_check(t_s: float, E_touch: float, E_mesh: float,
                      body_weight: int = 70, rho_s: float | None = None,
                      R_F1: float = 1000.0, Cs: float | None = None) -> dict:
    """Report the EN 50522 permissible touch voltage beside IEEE 80's.

    U_Tp is the voltage across the body alone, with no foot, footwear or
    surface-layer resistance, so the fair comparison is IEEE 80's R_B·I_B; the
    ratio E_touch/E_body shows how much of the IEEE 80 allowance comes from the
    resistance under the feet (native soil and surface layer).

    With rho_s (the resistivity under the feet) it also gives the Annex B
    prospective limit U_vTp, with footwear R_F1, which is the like-for-like
    comparison for the prospective mesh voltage E_m.  (Up to 1.3.4 the result
    carried E_m/U_Tp, which compares a prospective voltage with a body
    voltage.)

    With Cs (the IEEE 80 surface-layer derating of a finite layer) it also
    gives U_vTp with R_F2 = 1.5·C_s·ρ_s.  BS EN 50522:2010 Table B.4 writes
    R_F2 = 1.5·ρ_S with no allowance for the layer thickness, i.e. an
    infinitely thick layer; for a 100 mm layer that overstates the standing
    resistance, and the book (Sec. 3.6) recommends the C_s value as the
    conservative one where the edition and national annex are silent (1.3.5)."""
    U = en50522_touch_limit(t_s)
    Eb = ieee80_bare_touch(t_s, body_weight)
    out = dict(standard="BS EN 50522", t_F=t_s, U_Tp=U, E_bare_ieee80=Eb,
               surface_layer_gain=E_touch / Eb if Eb else None)
    tail = ""
    if rho_s is not None and rho_s > 0:
        pv = en50522_prospective_touch_limit(t_s, rho_s, R_F1)
        out.update(U_vTp=pv["U_vTp"], Z_T=pv["Z_T"], R_F=pv["R_F"],
                   rho_s=rho_s, R_F1=R_F1,
                   mesh_vs_UvTp=E_mesh / pv["U_vTp"] if pv["U_vTp"] else None)
        tail = (f" With {R_F1:.0f} Ω footwear and 1.5·ρ_s = {1.5 * rho_s:.0f} Ω "
                f"under the feet, the prospective limit of Formula (A.3) is U_vTp = "
                f"{pv['U_vTp']:.0f} V, the value to compare with E_m = "
                f"{E_mesh:.0f} V.")
        if Cs is not None and 0 < Cs < 1:
            pc = en50522_prospective_touch_limit(t_s, rho_s, R_F1, Cs)
            out.update(U_vTp_thin=pc["U_vTp"], R_F_thin=pc["R_F"], Cs=Cs,
                       mesh_vs_UvTp_thin=E_mesh / pc["U_vTp"] if pc["U_vTp"] else None)
            verdict = "above" if E_mesh > pc["U_vTp"] else "below"
            tail += (f" The standard takes the layer as infinitely thick (R_F2 = 1.5·ρ_S); allowing "
                     f"for its finite thickness (1.5·C_s·ρ_s = "
                     f"{1.5 * Cs * rho_s:.0f} Ω, C_s = {Cs:.3f}) gives "
                     f"U_vTp = {pc['U_vTp']:.0f} V, and E_m is {verdict} it.")
    out["note"] = (f"EN 50522 permits U_Tp = {U:.0f} V at t_F = {t_s:g} s across "
                   f"the body; IEEE 80 ({body_weight} kg) permits {Eb:.0f} V "
                   f"across the body alone (R_B = 1000 Ω, no foot resistance) "
                   f"and {E_touch:.0f} V with the foot and surface-layer "
                   f"resistance.{tail} Informational: the verdict remains the "
                   "IEEE 80 one.")
    return out


# ENA EG-0 / AS 2067 probabilistic assessment ------------------------------

def eg0_coincidence(f_n: float, p_n: float, f_d: float, t_d: float,
                    T_years: float = 1.0) -> float:
    """Coincidence probability (small-probability form used by EG-0):

        P_coinc = f_n · p_n · (f_d + t_d) · T / (365·24·3600)

    f_n  earth faults per year that raise the EPR at the location
    p_n  contacts (exposures) per year
    f_d  fault duration (s);  t_d  contact duration (s);  T  period (years)."""
    for v, n in ((f_n, "f_n"), (p_n, "p_n"), (f_d, "f_d"), (t_d, "t_d"), (T_years, "T")):
        if v < 0:
            raise ValueError(f"{n} must not be negative")
    return f_n * p_n * (f_d + t_d) * T_years / SECONDS_PER_YEAR


def eg0_risk_band(p_fatality_per_year: float) -> str:
    """Individual risk bands: < 1e-6 negligible, > 1e-4 intolerable, between: ALARP."""
    if p_fatality_per_year < 1e-6:
        return "negligible"
    if p_fatality_per_year > 1e-4:
        return "intolerable"
    return "ALARP"


# ---------------------------------------------------------------------------
# 3. Frequency-dependent soil — CIGRE TB 781 (Alipio–Visacro model)
# ---------------------------------------------------------------------------

# CIGRE TB 781 Table 3.2: parameter sets of the Alipio-Visacro causal model.
ALIPIO_VISACRO_LEVELS = {
    "mean":                    dict(h0=1.26, gamma=0.54, eps_inf_r=12.0),
    "relatively_conservative": dict(h0=0.95, gamma=0.58, eps_inf_r=8.0),
    "conservative":            dict(h0=0.70, gamma=0.62, eps_inf_r=4.0),
}


def alipio_visacro(rho0: float, f: float, gamma: float | None = None,
                   eps_inf_r: float | None = None, level: str = "mean") -> dict:
    """Resistivity and relative permittivity of soil at frequency f (Hz).

    CIGRE TB 781, Eq. 3.10-3.11 with the parameters of its Table 3.2:
    σ(f)  = σ0 + σ0·h(σ0)·(f/1 MHz)^γ                     (σ in mS/m)
    ε_r(f) = ε∞r + tan(πγ/2)·1e-3 /(2π ε0 (1 MHz)^γ) · σ0·h(σ0)·f^(γ-1)
    h(σ0) = h0·σ0^-0.73.  level = "mean" (h0 1.26, γ 0.54, ε∞r 12; the set
    TB 781 recommends for regular engineering, its Eq. 5.3-5.4),
    "relatively_conservative" (0.95, 0.58, 8) or "conservative" (0.70, 0.62, 4).
    rho0 is the low-frequency (≈100 Hz) resistivity in Ω·m.  Valid about
    100 Hz – 4 MHz."""
    if rho0 <= 0 or f <= 0:
        raise ValueError("rho0 and f must be positive")
    par = ALIPIO_VISACRO_LEVELS[level]
    g = par["gamma"] if gamma is None else gamma
    einf = par["eps_inf_r"] if eps_inf_r is None else eps_inf_r
    s0 = 1000.0 / rho0                       # mS/m
    h = par["h0"] * s0 ** -0.73
    s = s0 + s0 * h * (f / 1e6) ** g         # mS/m
    eps_r = einf + (math.tan(math.pi * g / 2) * 1e-3
                    / (2 * math.pi * EPS0 * (1e6) ** g)) * s0 * h * f ** (g - 1)
    return dict(rho=1000.0 / s, eps_r=eps_r, ratio=(1000.0 / s) / rho0,
                level=level, standard="CIGRE TB 781")


# CIGRE TB 781 Table 4.1: reduction of the impulse coefficient Z_p/R_LF by the
# frequency dependence of the soil, for electrodes shorter than L_eff
# (simulated for horizontal electrodes; TB 781 4.2.3 finds the same ratio for
# grids and counterpoises).
TB781_IC_RHO = [100.0, 300.0, 600.0, 1000.0, 2000.0, 4000.0]
TB781_IC_FIRST = [0.98, 0.95, 0.92, 0.89, 0.82, 0.72]
TB781_IC_SUBSEQUENT = [0.91, 0.84, 0.77, 0.70, 0.60, 0.50]


def tb781_impulse_reduction(rho0: float, stroke: str = "first") -> dict:
    """Factor by which frequency-dependent soil lowers the impulse impedance
    of an electrode shorter than its effective length (CIGRE TB 781 Table 4.1,
    log-linear interpolation in ρ0, held constant outside 100–4000 Ω·m).

    Note the factor is much closer to 1 than ρ(f)/ρ0 at the representative
    frequency: the impulse impedance does not scale with the resistivity."""
    ys = TB781_IC_FIRST if stroke == "first" else TB781_IC_SUBSEQUENT
    x = min(max(rho0, TB781_IC_RHO[0]), TB781_IC_RHO[-1])
    lx = math.log(x)
    for i in range(len(TB781_IC_RHO) - 1):
        a, b = math.log(TB781_IC_RHO[i]), math.log(TB781_IC_RHO[i + 1])
        if lx <= b:
            fac = ys[i] + (ys[i + 1] - ys[i]) * (lx - a) / (b - a)
            break
    if rho0 < 300:
        relevance = "not relevant (ρ0 < 300 Ω·m): ignore"
    elif rho0 <= 700:
        relevance = "relevant (300–700 Ω·m): recommended"
    else:
        relevance = "very relevant (> 700 Ω·m): mandatory for the lightning response"
    return dict(factor=fac, stroke=stroke, relevance=relevance,
                standard="CIGRE TB 781 Table 4.1 and Table 5.1")


def tb781_counterpoise_zp1st(rho0: float, L: float) -> dict:
    """First-stroke impulse impedance of tower-footing counterpoises with
    frequency-dependent soil, CIGRE TB 781 Eq. 4.1-4.2 (from its ref. [A51]):
        Z_P1st = 0.16·ρ0·L^-0.687          (100 ≤ ρ0 ≤ 600 Ω·m)
        Z_P1st = 0.4·ρ0^0.89·L^-0.75       (600 < ρ0 ≤ 4000 Ω·m)
    L in m as defined in the brochure's Figure 4.9 (length of each wire)."""
    if not (100.0 <= rho0 <= 4000.0) or L <= 0:
        raise ValueError("TB 781 Eq. 4.1-4.2 cover 100 ≤ ρ0 ≤ 4000 Ω·m and L > 0")
    Z = 0.16 * rho0 * L ** -0.687 if rho0 <= 600.0 else 0.4 * rho0 ** 0.89 * L ** -0.75
    return dict(Z_P1st=Z, rho0=rho0, L=L, standard="CIGRE TB 781 Eq. 4.1–4.2")


def tb781_tower_ic1st(rho0: float) -> dict:
    """First-stroke impulse coefficient of a tower footing from its measured
    low-frequency resistance, CIGRE TB 781 Eq. 4.3-4.4:
        IC_1st = 0.89 - 5e-5·ρ0,   Z_P1st = IC_1st·R_LF."""
    return dict(IC_1st=0.89 - 5e-5 * rho0, standard="CIGRE TB 781 Eq. 4.3–4.4")


# ---------------------------------------------------------------------------
# 4. Transferred EPR and coupling
# ---------------------------------------------------------------------------

def far_field_potential(rho: float, I_E: float, x: float) -> float:
    """Soil surface potential at distance x (m) from an electrode carrying I_E
    (A) in uniform soil, far enough away that it looks like a hemisphere:
    V = ρ·I_E/(2πx)."""
    if x <= 0:
        raise ValueError("distance must be positive")
    return rho * I_E / (2 * math.pi * x)


def epr_contour_distance(rho: float, I_E: float, V_lim: float) -> float:
    """Distance at which the surface potential falls to V_lim (the edge of a
    hazard / hot zone, e.g. the ITU 430 V / 650 V HOT-site limits of ENA TS
    41-24 §4.3.7, or AS/NZS 3835.1), far-field hemisphere form:
    x = ρI_E/(2πV_lim), measured from the electrode's centre.  Close to the
    grid use epr_contour_distance_s34()."""
    if V_lim <= 0:
        raise ValueError("V_lim must be positive")
    return rho * I_E / (2 * math.pi * V_lim)


def epr_contour_distance_s34(area: float, U_E: float, V_x: float) -> float:
    """ENA EREC S34:2018 Formula P7 (B.3.8): distance (m) from the edge of a
    compact electrode of plan area `area` (m²) and EPR U_E (V) to the contour
    V_x (V):  x = √(A/π)·[1/sin(πV_x/(2U_E)) − 1].  Returns 0 if V_x >= U_E."""
    if area <= 0 or U_E <= 0 or V_x <= 0:
        raise ValueError("area, U_E and V_x must be positive")
    if V_x >= U_E:
        return 0.0
    return math.sqrt(area / math.pi) * (1.0 / math.sin(math.pi * V_x / (2.0 * U_E)) - 1.0)


def carson_depth(rho: float, f: float = 50.0) -> float:
    """Equivalent depth of the earth return path (m): D_e = 658.5·√(ρ/f)."""
    return 658.5 * math.sqrt(rho / f)


def mutual_impedance_per_km(rho: float, d: float, f: float = 50.0) -> complex:
    """Carson mutual impedance between two earth-return circuits a distance d
    (m) apart, Ω/km:  Z_m = π²f·1e-4 + j·4πf·1e-4·ln(D_e/d)."""
    if d <= 0:
        raise ValueError("separation must be positive")
    De = carson_depth(rho, f)
    return complex(math.pi ** 2 * f * 1e-4, 4 * math.pi * f * 1e-4 * math.log(De / d))


def induced_emf(I_fault: float, Z_m_per_km: complex, L_km: float,
                screening: float = 1.0) -> float:
    """Longitudinal EMF (V) induced along a parallel length L_km:
    |E| = k·|Z_m|·L·I, k the screening factor (1 = unscreened)."""
    return screening * abs(Z_m_per_km) * L_km * I_fault


# ---------------------------------------------------------------------------
# 5. HVDC earth electrodes — EPRI EL-2020
# ---------------------------------------------------------------------------

def hvdc_temperature_rise(V_electrode: float, rho: float, lam: float) -> float:
    """Steady-state maximum temperature rise (K) of an electrode whose potential
    rise is V (V), in soil of resistivity ρ (Ω·m) and thermal conductivity
    λ (W/m·K):  Δθ_max = V²/(2ρλ)  (independent of electrode shape)."""
    return V_electrode ** 2 / (2 * rho * lam)


def hvdc_max_potential(dtheta: float, rho: float, lam: float) -> float:
    """Inverse of hvdc_temperature_rise: the largest electrode potential that
    keeps the steady temperature rise below dtheta."""
    return math.sqrt(2 * rho * lam * dtheta)


_METALS = {  # molar mass g/mol, valence
    "iron": (55.845, 2), "copper": (63.546, 2), "zinc": (65.38, 2),
    "aluminium": (26.982, 3),
}


def faraday_mass_loss(I: float, years: float, metal: str = "iron") -> float:
    """Mass (kg) dissolved from an anode carrying I (A) for `years`:
    m = M·I·t/(z·F). Iron: 9.13 kg per ampere-year."""
    M, z = _METALS[metal]
    return M * I * years * SECONDS_PER_YEAR / (z * FARADAY) / 1000.0


# ---------------------------------------------------------------------------
# 6. Bonding networks for electronic equipment — IEEE 1100, BS EN 50310
# ---------------------------------------------------------------------------

def srg_max_aperture(f_max: float, fraction: float = 0.05) -> float:
    """Largest mesh opening (m) of a signal reference grid that still behaves
    as an equipotential plane up to f_max (Hz): λ/20 by default, the limit
    IEEE Std 1100-2005 §4.6.4 adopts for digital equipment (λ/10 is only the
    −3 dB point).  0.6 m gives about 25 MHz (IEEE 1100 §4.8.5.3.5).  Up to
    1.3.4 the default was λ/10."""
    return fraction * 299_792_458.0 / f_max


def strap_impedance(length_m: float, f: float, L_per_m: float = 1e-6) -> float:
    """Inductive impedance (Ω) of a bonding strap, ≈1 µH/m: |Z| = 2πf·L·ℓ."""
    return 2 * math.pi * f * L_per_m * length_m
