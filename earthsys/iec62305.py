"""
Lightning protection earth-termination design to IEC 62305-3:2010.

Covers
------
* LPS class parameters (rolling sphere, mesh size, down-conductor spacing)
* Minimum electrode length l1 vs soil resistivity (Figure 3)
* Type A (radial / vertical electrodes) and Type B (ring / foundation)
  earth-termination sizing
* Separation distance s = k_i · k_c · l / k_m (clause 6.3)
* Equipotential bonding and SPD placement guidance (IEC 62305-4 LPZ concept)
"""

from __future__ import annotations

import math

from .materials import LPS_L1, LPS_L1_RHO, LPS_ELECTRODE_MIN
from . import iec60364 as lv

LPS_CLASS = {
    "I":   dict(rolling_sphere=20, mesh="5 × 5 m",  down_spacing=10,
                ki=0.08, interception_prob=0.99, I_max_kA=200, I_min_kA=3),
    "II":  dict(rolling_sphere=30, mesh="10 × 10 m", down_spacing=10,
                ki=0.06, interception_prob=0.97, I_max_kA=150, I_min_kA=5),
    "III": dict(rolling_sphere=45, mesh="15 × 15 m", down_spacing=15,
                ki=0.04, interception_prob=0.91, I_max_kA=100, I_min_kA=10),
    "IV":  dict(rolling_sphere=60, mesh="20 × 20 m", down_spacing=20,
                ki=0.04, interception_prob=0.84, I_max_kA=100, I_min_kA=16),
}

KM_MATERIAL = {"air": 1.0, "concrete": 0.5, "brick": 0.5, "wood": 0.5}


def min_electrode_length(lps_class: str, rho: float) -> dict:
    """l1 from IEC 62305-3 Figure 3, linearly interpolated in rho."""
    cls = lps_class.upper()
    table = LPS_L1.get(cls, LPS_L1["III"])
    xs, ys = LPS_L1_RHO, table
    if rho <= xs[0]:
        l1 = ys[0]
    elif rho >= xs[-1]:
        # beyond 3000 ohm.m keep the class-I/II slope
        slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
        l1 = ys[-1] + slope * (rho - xs[-1])
    else:
        l1 = ys[-1]
        for i in range(len(xs) - 1):
            if xs[i] <= rho <= xs[i + 1]:
                f = (rho - xs[i]) / (xs[i + 1] - xs[i])
                l1 = ys[i] + f * (ys[i + 1] - ys[i])
                break
    return dict(l1=l1, l1_vertical=l1 / 2.0, lps_class=cls, rho=rho,
                reference="IEC 62305-3:2010 Figure 3")


def type_a(lps_class: str, rho: float, n_down: int,
           electrode: str = "vertical", L_each: float | None = None,
           d: float = 0.016, h: float = 0.5, w: float = 0.03) -> dict:
    """Type A arrangement: one radial/vertical electrode per down-conductor."""
    ml = min_electrode_length(lps_class, rho)
    L_req = ml["l1_vertical"] if electrode == "vertical" else ml["l1"]
    L = L_each if L_each else L_req
    n = max(2, int(n_down))

    if electrode == "vertical":
        each = lv.rod(rho, L, d)
        combined = lv.rods_parallel(rho, L, d, n, max(2.0 * L, 5.0))
    else:
        each = lv.horizontal_strip(rho, L, w, h)
        combined = dict(R=each["R"] / n * 1.4, note="1.4 mutual-coupling allowance")

    return dict(arrangement="Type A", lps_class=lps_class.upper(),
                electrode=electrode, n_electrodes=n,
                L_required=L_req, L_used=L, length_ok=L >= L_req - 1e-9,
                each=each, R_total=combined["R"], combined=combined,
                min_count_ok=n >= 2, l1=ml,
                note="At least two electrodes are required; the length of each "
                     "must be not less than l1 (horizontal) or 0.5·l1 (vertical).")


def type_b(lps_class: str, rho: float, area: float | None = None,
           perimeter: float | None = None, d: float = 0.01, h: float = 0.5,
           foundation_volume: float | None = None) -> dict:
    """Type B arrangement: ring electrode (or foundation electrode).

    Requirement: mean radius r_e of the area enclosed by the ring >= l1.
    """
    ml = min_electrode_length(lps_class, rho)
    l1 = ml["l1"]

    if area is None and perimeter:
        area = (perimeter / (2.0 * math.pi)) ** 2 * math.pi
    if area is None:
        raise ValueError("Provide the enclosed area or the ring perimeter.")
    re = math.sqrt(area / math.pi)
    ok = re >= l1

    supplement = None
    if not ok:
        supplement = dict(horizontal_each=l1 - re,
                          vertical_each=(l1 - re) / 2.0,
                          note="Add supplementary electrodes at each "
                               "down-conductor: l_r = l1 − r_e (horizontal) "
                               "or l_v = (l1 − r_e)/2 (vertical).")

    if foundation_volume:
        R = lv.foundation(rho, foundation_volume)
    else:
        R = lv.ring(rho, re, d, h)

    return dict(arrangement="Type B", lps_class=lps_class.upper(),
                area=area, mean_radius=re, l1=l1, radius_ok=ok,
                supplementary=supplement, resistance=R, R_total=R["R"],
                ring_length=2.0 * math.pi * re, l1_data=ml,
                recommended_R=10.0,
                R_recommendation_met=R["R"] <= 10.0,
                note="IEC 62305-3 recommends an earthing resistance below "
                     "10 Ω (informative) for the lightning protection system.")


def separation_distance(lps_class: str, length_m: float, n_down: int,
                        material: str = "air",
                        kc: float | None = None) -> dict:
    """s = k_i · k_c · l / k_m  (IEC 62305-3 clause 6.3)."""
    cls = LPS_CLASS[lps_class.upper()]
    ki = cls["ki"]
    km = KM_MATERIAL.get(material, 1.0)
    if kc is None:
        if n_down <= 1:
            kc = 1.0
        elif n_down == 2:
            kc = 0.66
        elif n_down == 3:
            kc = 0.55
        else:
            kc = 0.44
    s = ki * kc * length_m / km
    return dict(s=s, ki=ki, kc=kc, km=km, length=length_m,
                n_down=n_down, material=material,
                formula="s = k_i·k_c·l/k_m  (IEC 62305-3 §6.3)")


def down_conductors(lps_class: str, perimeter_m: float) -> dict:
    cls = LPS_CLASS[lps_class.upper()]
    spacing = cls["down_spacing"]
    n = max(2, int(math.ceil(perimeter_m / spacing)))
    return dict(n_down=n, typical_spacing=spacing,
                actual_spacing=perimeter_m / n, perimeter=perimeter_m,
                mesh_size=cls["mesh"], rolling_sphere=cls["rolling_sphere"],
                reference="IEC 62305-3 Table 4 / Table 2")


# ---------------------------------------------------------------------------
# Behaviour under the impulse — effective length and effective area
# ---------------------------------------------------------------------------
#
# Everything above this line is a power-frequency or d.c. calculation: the
# whole electrode is assumed to be at one potential, so making it longer
# always lowers the resistance.  A lightning current does not behave that
# way.  The front is over in a microsecond or two, and in that time the
# travelling wave has only reached a limited distance along the buried
# conductor; the series inductance of the conductor holds the far end back
# while the leakage conductance to soil is already bleeding the current away
# near the injection point.  Beyond that distance the electrode carries
# almost no current and contributes almost nothing.  That distance is the
# *effective length*, and it is why a 200 m radial electrode is no better
# under lightning than a 30 m one.
#
# Two consequences matter to a designer:
#
#   1. Extra electrode length beyond L_eff is money spent for nothing.
#   2. The earth potential rise under a stroke is larger — often much
#      larger — than I·R would suggest from the resistance measured with a
#      d.c. or 50 Hz tester, because only the effective part is working.

IMPULSE_K = {"centre": 1.55, "end": 1.40}


def _is_centre(injection) -> bool:
    """Centre-fed, or fed from an edge or a corner.  Spelt out because
    "centre" and "corner" share their first letter and a prefix test on
    them is a bug waiting to happen."""
    return str(injection).strip().lower() in ("centre", "center", "middle")

# Gupta & Thapar fitted K = a - b·s to model tests, with s the conductor
# spacing of the mesh in metres.  The fit was made over roughly 3 m to 15 m
# spacing; outside that band the linear fit is extrapolated and flagged.
GT_SPACING_RANGE = (3.0, 15.0)

# IEC 62305-1 Table 3 front times T1, in microseconds.
IMPULSE_FRONTS = {
    "first_negative": 1.0,
    "first_positive": 10.0,
    "subsequent": 0.25,
}


def effective_length(rho: float, tau: float, feed: str = "end") -> dict:
    """Effective length of a horizontal electrode under an impulse.

        L_eff = k · (ρ · τ)^0.5        ρ in Ω·m, τ in µs, L_eff in m

    k = 1.40 for an electrode fed at one end and 1.55 for one fed at its
    centre, the centre-fed case being longer only because the current has
    two directions to travel in.  The square-root form follows from the
    lossy transmission line: the distance the front reaches in a time τ
    scales with the square root of the product of the soil resistivity
    (which sets the leakage) and the time available.
    """
    if rho <= 0 or tau <= 0:
        raise ValueError("Soil resistivity and front time must both be "
                         "greater than zero.")
    k = IMPULSE_K.get(feed, IMPULSE_K["end"])
    return dict(L_eff=k * math.sqrt(rho * tau), k=k, feed=feed,
                rho=rho, tau=tau,
                formula="L_eff = k·(ρ·τ)^0.5  [k = 1.40 end-fed, "
                        "1.55 centre-fed; ρ in Ω·m, τ in µs]")


def _gupta_thapar(rho: float, T: float, spacing: float,
                  injection: str) -> dict:
    """r_e = K(ρT)^0.5 with K a linear function of the mesh spacing."""
    s = float(spacing)
    if injection == "centre":
        K, expr = 1.45 - 0.05 * s, "K = 1.45 − 0.05·s"
    else:
        K, expr = 0.60 - 0.025 * s, "K = 0.60 − 0.025·s"
    lo, hi = GT_SPACING_RANGE
    out_of_range = not (lo <= s <= hi)
    K = max(K, 0.05)
    return dict(name="Gupta & Thapar", r=K * math.sqrt(rho * T), K=K,
                expression=expr, out_of_range=out_of_range,
                note=("Conductor spacing %.1f m is outside the %.0f–%.0f m "
                      "band the fit was made over, so K is extrapolated."
                      % (s, lo, hi)) if out_of_range else None)


def _grcev(rho: float, T: float, injection: str) -> dict:
    """a_eff = K·exp[0.84 (ρT)^0.22], from the transmission-line study of
    the effective area of large grounding grids."""
    K = 1.0 if injection == "centre" else 0.5
    return dict(name="Grcev", r=K * math.exp(0.84 * (rho * T) ** 0.22), K=K,
                expression="a_eff = K·exp[0.84·(ρT)^0.22]",
                out_of_range=False, note=None)


def _conductor_reach(rho: float, T: float, injection: str) -> dict:
    """The horizontal-electrode effective length applied radially: how far
    along a conductor the front actually gets."""
    feed = "centre" if injection == "centre" else "end"
    L = effective_length(rho, T, feed)
    return dict(name="Conductor reach", r=L["L_eff"], K=L["k"],
                expression="L_eff = k·(ρT)^0.5", out_of_range=False,
                note="The horizontal-electrode formula read as a radius; it "
                     "is the distance the front travels along a conductor, "
                     "not a fitted grid result.")


def effective_area(rho: float, T: float, area: float,
                   spacing: float = 7.0, injection: str = "centre") -> dict:
    """Effective radius and participating area of a meshed earthing system.

    Three published estimates are returned side by side rather than one
    number, because they do not agree: at ρT = 1000 Ω·m·µs they span a
    factor of three or so.  The spread is the honest answer — treat the
    smallest as the design case if the consequence of getting it wrong is
    an equipment failure, and the largest if it is only cost.
    """
    if rho <= 0 or T <= 0:
        raise ValueError("Soil resistivity and front time must both be "
                         "greater than zero.")
    if area <= 0:
        raise ValueError("The area covered by the earthing system must be "
                         "greater than zero.")
    inj = "centre" if _is_centre(injection) else "corner"
    r_geom = math.sqrt(area / math.pi)

    models = [_gupta_thapar(rho, T, spacing, inj),
              _conductor_reach(rho, T, inj),
              _grcev(rho, T, inj)]
    for m in models:
        m["r"] = min(m["r"], r_geom)          # cannot exceed the electrode
        m["area"] = math.pi * m["r"] ** 2
        m["fraction"] = min(1.0, m["area"] / area)
        m["fully_used"] = m["r"] >= r_geom - 1e-9

    rs = [m["r"] for m in models]
    governing = min(models, key=lambda m: m["r"])

    return dict(rho=rho, T=T, spacing=spacing, injection=inj,
                area=area, geometric_radius=r_geom,
                models=models, governing=governing["name"],
                r_min=min(rs), r_max=max(rs), r_mean=sum(rs) / len(rs),
                spread=max(rs) / min(rs) if min(rs) > 0 else None,
                fraction_min=min(m["fraction"] for m in models),
                fraction_max=max(m["fraction"] for m in models),
                fully_used=all(m["fully_used"] for m in models),
                reference="Gupta & Thapar; Grcev — effective area of "
                          "earthing grids under impulse")


def impulse_response(rho: float, T: float, R_lf: float,
                     area: float | None = None,
                     extent: float | None = None,
                     spacing: float = 7.0, injection: str = "centre",
                     I_kA: float = 100.0) -> dict:
    """Put the effective length and the effective area together into the two
    numbers a designer acts on: how much of the electrode is working, and
    how far the earth potential rise exceeds I·R_lf because of it.

    The impulse coefficient A = Z_imp / R_lf is estimated to first order
    from the resistance of a disc electrode, R = ρ/(4r): if only a radius
    r_eff participates instead of the full r_geom, the impedance rises in
    the ratio of the radii.  It is an estimate, not a measurement — a real
    number needs an impulse test or a full transmission-line model — but it
    is the right order and it points the right way, which is what a warning
    has to do.
    """
    feed = "centre" if _is_centre(injection) else "end"
    lin = effective_length(rho, T, feed)

    area_res = None
    if area and area > 0:
        area_res = effective_area(rho, T, area, spacing, injection)

    if area_res:
        r_eff = area_res["r_min"]
        r_geom = area_res["geometric_radius"]
    else:
        r_eff = lin["L_eff"]
        r_geom = extent if extent else r_eff

    A = max(1.0, r_geom / r_eff) if r_eff > 0 else None
    Z = R_lf * A if (R_lf is not None and A is not None) else None
    epr_lf = R_lf * I_kA * 1000.0 if R_lf is not None else None
    epr_imp = Z * I_kA * 1000.0 if Z is not None else None

    over = None
    if extent and extent > lin["L_eff"] + 1e-9:
        over = extent - lin["L_eff"]

    return dict(rho=rho, T=T, injection=injection, I_kA=I_kA,
                linear=lin, area=area_res,
                electrode_extent=extent, wasted_length=over,
                r_effective=r_eff, r_geometric=r_geom,
                impulse_coefficient=A, R_lf=R_lf, Z_impulse=Z,
                EPR_lf=epr_lf, EPR_impulse=epr_imp,
                warning="An earth resistance measured with a d.c. or 50 Hz "
                        "tester describes the whole electrode at one "
                        "potential. Under a lightning front only the "
                        "effective part is carrying current, so the real "
                        "potential rise is higher than I·R suggests. Size "
                        "bonding and SPD coordination on the impulse value, "
                        "not on the measured resistance.",
                reference="Effective length and effective area under impulse "
                          "conditions")

def design(lps_class: str, rho: float, area: float, perimeter: float,
           arrangement: str = "B", d: float = 0.01, h: float = 0.5,
           rod_d: float = 0.016, foundation_volume: float | None = None,
           separation_length: float = 10.0,
           separation_material: str = "air",
           front_time: float = 1.0, injection: str = "centre",
           mesh_spacing: float | None = None) -> dict:
    """Complete earth-termination design for a structure."""
    dc = down_conductors(lps_class, perimeter)
    if arrangement.upper() == "A":
        earth = type_a(lps_class, rho, dc["n_down"], "vertical", None, rod_d, h)
    else:
        earth = type_b(lps_class, rho, area, perimeter, d, h, foundation_volume)
    sep = separation_distance(lps_class, separation_length, dc["n_down"],
                              separation_material)
    cls = LPS_CLASS[lps_class.upper()]

    checks = [
        dict(name="Earth-termination geometry",
             passed=earth.get("length_ok", earth.get("radius_ok", True)),
             note=("Electrode length ≥ l1" if arrangement.upper() == "A"
                   else "Ring mean radius r_e ≥ l1")),
        dict(name="Earthing resistance ≤ 10 Ω (recommended)",
             passed=earth["R_total"] <= 10.0,
             value=earth["R_total"], limit=10.0, unit="Ω"),
        dict(name="Number of down-conductors",
             passed=dc["n_down"] >= 2, value=dc["n_down"], limit=2, unit="-"),
    ]

    # How the same electrode behaves when the current is a lightning
    # front rather than a power-frequency fault.
    if arrangement.upper() == "A":
        extent = earth.get("L_used")
        meshed = None
    else:
        extent = earth.get("mean_radius")
        meshed = area if mesh_spacing else None
    imp = impulse_response(rho, float(front_time), earth["R_total"],
                           area=meshed, extent=extent,
                           spacing=float(mesh_spacing or 7.0),
                           injection=injection,
                           I_kA=float(cls["I_max_kA"]))

    return dict(lps_class=lps_class.upper(), class_data=cls, rho=rho,
                down_conductors=dc, earth=earth, separation=sep,
                impulse=imp,
                electrode_min_sizes=LPS_ELECTRODE_MIN, checks=checks,
                passed=all(c["passed"] for c in checks),
                bonding_note="Bond all incoming metallic services and, where "
                             "direct bonding is not possible, use SPDs at the "
                             "LPZ 0/1 boundary (IEC 62305-3 §6.2, 62305-4).")
