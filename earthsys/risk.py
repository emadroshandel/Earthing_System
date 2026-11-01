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
Lightning risk management, IEC 62305-2:2024 (Ed. 3) — the risk R and the
frequency of damage F, for a structure divided into risk zones (1.8.5).

Edition 3 replaces the four risks R1…R4 of the 2010 edition with one risk

    R = R_L1 + R_L2,   tolerable R_T = 10⁻⁵ per year            (6), (7.3)

where L1 is injury to living beings and L2 physical damage (loss of the
structure's value, its contents and services).  The loss of service to
the public of 2010 becomes the frequency of damage of internal systems,

    F = F_C + F_M + F_W + F_Z,   tolerable F_T = 0.1 /yr for critical
                                  systems, 1 /yr for non-critical       (12)

Both are judged zone by zone (8.3, 9.4).

Annual numbers of dangerous events (Annex A)
    N_SG = k·N_G   (k from the lightning location data; 2 when unknown)
    N_D  = N_SG·A_D·C_D·10⁻⁶,    A_D = L·W + 2·3H·(L+W) + π(3H)²
    N_M  = N_SG/k·A_M·10⁻⁶,      A_M = 2·r_M·(L+W) + π·r_M²,  r_M = 350/U_w
    N_L  = N_SG·A_L·C_I·C_E·C_T·10⁻⁶,  A_L = 40·L_L   (0.6·√ρ·L_L buried, ρ > 400 Ω·m)
    N_I  = N_SG/k·A_I·C_I·C_E·C_T·10⁻⁶, A_I = 2·r_I·L_L,  r_I = 2000/U_w^1.8
    N_DJ = N_SG·A_DJ·C_DJ·C_T·10⁻⁶
  summed over the sections of each line (8.4).

Risk components (Table 3), with P_P = t_z/8760 and P_e = t_e/8760
    R_AT = N_D·P_AT·P_P·L_T           R_AD = N_D·P_AD·P_P·L_D
    R_B1 = N_D·P_B·P_P·L_F1           R_B2 = N_D·P_B·L_F2
    R_C1 = N_D·P_C·P_P·P_e·L_O1       R_C2 = N_D·P_C·P_e·L_O2
    R_M1 = N_M·P_M·P_P·P_e·L_O1       R_M2 = N_M·P_M·P_e·L_O2
    R_U  = (N_L+N_DJ)·P_U·P_P·L_T
    R_V1 = (N_L+N_DJ)·P_V·P_P·L_F1    R_V2 = (N_L+N_DJ)·P_V·L_F2
    R_W1 = (N_L+N_DJ)·P_W·P_P·P_e·L_O1  R_W2 = (N_L+N_DJ)·P_W·P_e·L_O2
    R_Z1 = N_I·P_Z·P_P·P_e·L_O1       R_Z2 = N_I·P_Z·P_e·L_O2
Probabilities (Annex B)
    P_AT = P_LPS·P_am·r_t·P_TWS        P_AD = P_TWS·P_am·P_O·P_LPS
    P_B  = P_S·P_LPS·r_f·r_p           (P_S = 1 once an LPS is installed)
    P_C  = 1 − Π(1 − P_SPD·C_LD)       P_M = 1 − Π(1 − P_SPD·P_MS),
                                       P_MS = (K_S1·K_S2·K_S3)²
    P_U  = P_am·P_EB·P_LD·P_TWS·C_LD·r_t
    P_V  = P_EB·P_LD·P_TWS·C_LD·r_f·r_p
    P_W  = P_SPD·P_TWS·P_LD·C_LD        P_Z = P_SPD·P_TWS·C_LI
Damage to the surroundings (Annex E, 1.9.5): a zone that can harm them gets
the components of Table E.1, those of Table 3 with P_P → P_PE = t_zE/8760
and the losses L_F1E, L_O1E (Table E.3), L_F2E, L_O2E (Table E.4):
    R_B1E = N_D·P_B·P_PE·L_F1E          R_B2E = N_D·P_B·L_F2E
    R_C1E = N_D·P_C·P_PE·P_e·L_O1E      R_C2E = N_D·P_C·P_e·L_O2E
    R_M1E = N_M·P_M·P_PE·P_e·L_O1E      R_M2E = N_M·P_M·P_e·L_O2E
    R_V1E = (N_L+N_DJ)·P_V·P_PE·L_F1E   R_V2E = (N_L+N_DJ)·P_V·L_F2E
    R_W1E = (N_L+N_DJ)·P_W·P_PE·P_e·L_O1E  R_W2E = (N_L+N_DJ)·P_W·P_e·L_O2E
    R_Z1E = N_I·P_Z·P_PE·P_e·L_O1E      R_Z2E = N_I·P_Z·P_e·L_O2E
  added to R_L1 and R_L2 of the zone (R_AT, R_AD and R_U have no counterpart).
Frequency of damage (Table 4)
    F_C = N_D·P_C·P_e   F_M = N_M·P_M·P_e   F_W = (N_L+N_DJ)·P_W·P_e   F_Z = N_I·P_Z·P_e

The module reproduces the three worked examples of Annex F (house, office
building, hospital) to the figures printed in the standard; the tests
check them.
"""

from __future__ import annotations

import itertools
import math

STANDARD = "IEC 62305-2:2024"
RT = 1e-5

# ---------------------------------------------------------------- Annex A
CD = {"surrounded_higher": 0.25, "surrounded_same": 0.5, "isolated": 1.0, "hilltop": 2.0}
CI = {"aerial": 1.0, "buried": 0.3, "buried_meshed": 0.01}                     # Table A.2
CT = {"lv": 1.0, "hv_auto": 1.0, "telecom": 1.0, "hv": 0.2}                    # Table A.3
CE = {"rural": 1.0, "suburban": 0.5, "urban": 0.1, "urban_tall": 0.01}         # Table A.4

# ---------------------------------------------------------------- Annex B
PAM = {"none": 1.0, "notices": 0.1, "insulation": 0.01, "equipotential": 0.01,  # Table B.1
       "natural_lps": 1e-3, "restriction": 0.0}
RT_SURF = {"agricultural": 1e-2, "concrete": 1e-2, "marble": 1e-3, "ceramic": 1e-3,   # Table B.2
           "gravel": 1e-4, "moquette": 1e-4, "carpet": 1e-4,
           "asphalt": 1e-5, "linoleum": 1e-5, "wood": 1e-5, "insulating_layer": 0.0}
PLPS = {"none": 1.0, "IV": 0.2, "III": 0.1, "II": 0.05, "I": 0.02,              # Table B.3
        "I_natural": 0.01, "I_metal_roof": 0.001}
PS = {"masonry": 1.0, "wood": 1.0, "reinforced": 0.5, "metal_frame": 0.5}       # Table B.4
RP = {"none": 1.0, "manual": 0.5, "automatic": 0.2}                            # Table B.5
RF = {"explosion_0_20_50": 1.0, "explosion_1_21": 0.1, "explosion_2_22": 1e-3,  # Table B.6
      "high": 0.1, "ordinary": 0.01, "low": 1e-3, "none": 0.0}
PSPD = {"none": 1.0, "III-IV": 0.05, "II": 0.02, "I": 0.01}                    # Tables B.7, B.8
PEB = {"none": 1.0, "III-IV": 0.05, "II": 0.02, "I": 0.01}                     # Table B.13
CLD_CLI = {                                                                     # Table B.9
    "aerial_unshielded": (1.0, 1.0), "buried_unshielded": (1.0, 1.0),
    "multigrounded_neutral": (1.0, 0.2),
    "shield_buried_not_bonded": (1.0, 0.3), "shield_aerial_not_bonded": (1.0, 0.1),
    "shield_buried_bonded": (1.0, 0.0), "shield_aerial_bonded": (1.0, 0.0),
    "protective_cable": (0.0, 0.0), "no_line": (0.0, 0.0), "isolating": (0.0, 0.0),
    # names used by version 1.8.0–1.8.4
    "hv_multigrounded": (1.0, 0.2), "shield_bonded": (1.0, 0.0), "protected_duct": (0.0, 0.0),
}
KS3 = {"different_routing": 1.0, "same_conduit_025": 0.5, "same_conduit_01": 0.2,  # Table B.10
       "same_cable": 0.01, "shielded": 1e-4,
       "unshielded_no_precaution": 1.0, "unshielded_avoid_large_loops": 0.2,
       "unshielded_avoid_loops": 0.01}
# P_LD, Tables B.11 and B.12, by the shield resistance R_S of the line and U_w
UW_LIST = (0.35, 0.5, 1.0, 1.5, 2.5, 4.0, 6.0, 12.0, 16.0, 20.0, 40.0, 60.0, 75.0, 95.0)
PLD = {
    "unshielded": (1,) * 14,
    "rs_5_20": (1, 1, 1, 1, 0.95, 0.9, 0.8, 0.4, 0.3, 0.15, 0.03, 0.01, 0.007, 0.005),
    "rs_1_5": (1, 1, 0.9, 0.8, 0.6, 0.3, 0.1, 0.02, 0.01, 0.007, 0.0015, 0.001, 4e-4, 2e-4),
    "rs_le_1": (1, 0.85, 0.6, 0.4, 0.2, 0.04, 0.02, 0.005, 0.002, 0.0015, 4e-4, 1.5e-4, 1e-4, 0.7e-4),
}

# ---------------------------------------------------------------- Annex C
LT, LD = 1e-2, 1e-1
LOSS = {   # Table C.2, the upper value of each range (the recommended default)
    "very_high": dict(LF=0.2, LO=1e-2),
    "high": dict(LF=0.1, LO=1e-3),
    "normal": dict(LF=5e-2, LO=5e-4),
    "low": dict(LF=2e-2, LO=1e-4),
}
USE_TO_LOSS = {"hospital": "high", "museum": "high", "explosion": "very_high",
               "school": "normal", "hotel": "normal", "civic": "normal", "church": "normal",
               "entertainment": "normal", "commercial": "normal", "industrial": "normal",
               "office": "normal", "house": "low", "other": "low"}

# ---------------------------------------------------------------- Annex E
# Damage to the surroundings (1.9.5).  Table E.2: t_zE/8760, the presence of
# people in the surroundings; 1 when it is not known.
PPE = {"unknown": 1.0, "working_site": 0.25, "working_site_shifts": 1.0, "public": 0.5,
       "activity_zones": 0.75, "residences": 1.0, "roads": 1.0, "railways": 0.25,
       "inland_waterways": 0.1, "pedestrian_ways": 0.75, "open_grounds": 0.25,
       "infrequent": 0.25, "frequent": 0.5, "special": 0.1}
# Table E.3 (L1): (L_F1E, L_O1E) remaining inside the site fence, spreading
# outside it; Table E.4 (L2): (L_F2E, L_O2E)
LE1 = {"explosion": ((0.25, 0.025), (0.5, 0.05)), "thermal": ((0.05, 0.005), (0.1, 0.01)),
       "toxic": ((0.1, 0.01), (1.0, 0.1)), "soil": ((0.1, 0.01), (0.5, 0.05)),
       "water": ((0.25, 0.025), (2.5, 0.25)), "radioactive": ((0.5, 0.05), (5.0, 0.5))}
LE2 = {"explosion": (0.5, 0.05), "thermal": (0.1, 0.01), "toxic": (0.5, 0.05),
       "soil": (0.2, 0.02), "water": (0.5, 0.05), "radioactive": (1.0, 0.1)}


def surroundings_losses(sur: dict | None) -> dict | None:
    """The losses of Annex E for one zone's damage to the surroundings, or
    None when the zone cannot harm them.  `sur`: scenario (Tables E.3/E.4),
    spreading (beyond the site fence or not), area (Table E.2) or PPE,
    internal (whether a failure of internal systems can cause it; else only
    fire and explosion, R_B and R_V, count), and any of LF1E, LO1E, LF2E,
    LO2E to replace the table values."""
    if not sur:
        return None
    scen = sur.get("scenario")
    if scen not in (None, "", "custom") and scen not in LE1:
        raise ValueError(f"Unknown surroundings scenario '{scen}'. Use one of: "
                         f"{', '.join(sorted(LE1))}, or custom.")
    if scen in LE1:
        lf1, lo1 = LE1[scen][1 if sur.get("spreading", True) else 0]
        lf2, lo2 = LE2[scen]
    else:
        lf1 = lo1 = lf2 = lo2 = 0.0
    out = dict(LF1E=float(sur.get("LF1E", lf1)), LO1E=float(sur.get("LO1E", lo1)),
               LF2E=float(sur.get("LF2E", lf2)), LO2E=float(sur.get("LO2E", lo2)))
    if not sur.get("internal", False):
        out["LO1E"] = out["LO2E"] = 0.0
    ppe = sur.get("PPE")
    out["PPE"] = float(ppe) if ppe not in (None, "") else _key(PPE, sur.get("area", "unknown"),
                                                               "surroundings")
    if not 0.0 <= out["PPE"] <= 1.0:
        raise ValueError("t_zE/8760 lies between 0 and 1.")
    if any(v < 0 for v in out.values()):
        raise ValueError("The losses to the surroundings cannot be negative.")
    out.update(scenario=scen or "custom", spreading=bool(sur.get("spreading", True)),
               internal=bool(sur.get("internal", False)))
    return out


LPS_ORDER = ["none", "IV", "III", "II", "I"]
SPD_ORDER = ["none", "III-IV", "II", "I"]
_LPS_TO_LPL = {"none": "none", "IV": "III-IV", "III": "III-IV", "II": "II", "I": "I",
               "I_natural": "I", "I_metal_roof": "I"}


def _key(table, value, what):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if value not in table:
        raise ValueError(f"Unknown {what} '{value}'. Use one of: {', '.join(sorted(table))}.")
    return table[value]


def _better(a, b):
    """The more effective of two SPD levels."""
    return a if SPD_ORDER.index(a) >= SPD_ORDER.index(b) else b


def r_I(Uw):
    """Lateral distance for flashes near a line, r_I = 2000/U_w^1.8 m (A.12)."""
    return 2000.0 / float(Uw) ** 1.8


def r_M(Uw):
    """Lateral distance for flashes near the structure, r_M = 350/U_w m (A.8)."""
    return 350.0 / float(Uw)


def collection_areas(L, W, H, LL_lines, Uw=2.5):
    """A_D, A_M and, per line length, A_L and A_I (Annex A)."""
    H3 = 3.0 * H
    AD = L * W + 2 * H3 * (L + W) + math.pi * H3 ** 2
    rm = r_M(Uw)
    AM = 2 * rm * (L + W) + math.pi * rm ** 2
    return AD, AM, [40.0 * l for l in LL_lines], [2.0 * r_I(Uw) * l for l in LL_lines]


def p_ld(rs, Uw):
    """P_LD from Tables B.11/B.12: the tabulated U_w at or below the given one
    (the safe side).  rs is a class name or the shield resistance in Ω/km."""
    if isinstance(rs, (int, float)) and not isinstance(rs, bool):
        rs = "rs_le_1" if rs <= 1 else "rs_1_5" if rs <= 5 else "rs_5_20" if rs <= 20 else "unshielded"
    rs = rs or "unshielded"
    if rs not in PLD:
        raise ValueError(f"Unknown shield class '{rs}'.")
    i = max([j for j, u in enumerate(UW_LIST) if u <= float(Uw) + 1e-9] or [0])
    return float(PLD[rs][i])


def _sections(line):
    secs = line.get("sections")
    if not secs:
        secs = [dict(length=line.get("length", 1000.0), install=line.get("install", "buried"),
                     type=line.get("type", "lv"), environment=line.get("environment"),
                     rho=line.get("rho"))]
    return secs


def _line_events(line, NSG, k, env_default):
    """N_L, N_I, N_DJ of one line, summed over its sections."""
    if line.get("fibre") or line.get("optical"):
        return dict(NL=0.0, NI=0.0, NDJ=0.0, sections=[])
    Uw = float(line.get("Uw", 2.5))
    rows, NL, NI = [], 0.0, 0.0
    ct_last = 1.0
    for s in _sections(line):
        LL = float(s.get("length", 1000.0))
        if LL < 0:
            raise ValueError("A line section length cannot be negative.")
        inst = s.get("install", "buried")
        ci = _key(CI, inst, "installation factor")
        ce = _key(CE, s.get("environment") or env_default, "environment")
        ct = _key(CT, s.get("type", "lv"), "line type")
        ct_last = ct
        rho = s.get("rho")
        if inst == "buried" and rho and float(rho) > 400.0:
            al_ci = 0.6 * math.sqrt(float(rho)) * LL           # A.2 Note 3
        else:
            al_ci = 40.0 * LL * ci
        nl = NSG * al_ci * ce * ct * 1e-6
        ai = 2.0 * r_I(Uw) * LL
        ni = NSG / k * ai * ci * ce * ct * 1e-6
        NL += nl
        NI += ni
        rows.append(dict(length=LL, CI=ci, CE=ce, CT=ct, AL=al_ci / ci if ci else 0.0,
                         AI=ai, NL=nl, NI=ni))
    NDJ = 0.0
    a = line.get("adjacent")
    if a:
        ADJ = collection_areas(float(a["L"]), float(a["W"]), float(a["H"]), [])[0]
        NDJ = NSG * ADJ * CD[a.get("location", "isolated")] * ct_last * 1e-6
    return dict(NL=NL, NI=NI, NDJ=NDJ, sections=rows, rI=r_I(Uw), Uw=Uw)


def _default_zone(p):
    """One zone built from the single-zone inputs of version 1.8.0–1.8.4."""
    use = p.get("use", "other")
    fire = p.get("fire_risk", "ordinary")
    loss = p.get("loss") or USE_TO_LOSS.get(use, "low")
    lines = p.get("lines") or []
    return dict(name="Structure", tz=float(p.get("hours", 8760.0)),
                surface=p.get("surface_inside", "concrete"),
                touch=p.get("touch_measures", "none"),
                fire_risk=fire, fire_provisions=p.get("fire_provisions", "none"),
                loss=loss, life_systems=(use == "hospital" or str(fire).startswith("explosion")),
                systems=[dict(line=i, ks3=l.get("wiring", "different_routing"),
                              Uw=l.get("Uw", 2.5)) for i, l in enumerate(lines)],
                FT=p.get("FT"))


def _default_lines(p):
    if p.get("lines"):
        return p["lines"]
    return [dict(name="LV power", kind="power", install="buried", type="lv", length=1000.0,
                 shielding="buried_unshielded", Uw=2.5)]


def assess(p: dict, lps: str | None = None, spd: str | None = None, eb: str | None = None) -> dict:
    """Risk R and frequency of damage F, zone by zone, for one set of
    protection measures: LPS class, coordinated SPD level and the SPD level
    of the lightning equipotential bonding at the line entrances."""
    if "NSG" in p and p["NSG"] not in (None, ""):
        k = float(p.get("k", 2.0))
        NSG = float(p["NSG"])
    else:
        NG = float(p.get("NG", 4.0))
        k = float(p.get("k", 2.0))
        NSG = k * NG
    if NSG <= 0 or k <= 0:
        raise ValueError("The strike-point density N_SG (or N_G and k) must be positive.")
    L, W, H = float(p.get("L", 30)), float(p.get("W", 20)), float(p.get("H", 10))
    if min(L, W, H) <= 0:
        raise ValueError("The structure's length, width and height must be positive.")
    lps = lps or p.get("lps", "none")
    spd = spd or p.get("spd", "none")
    eb = eb or p.get("eb", "none")
    if lps not in PLPS:
        raise ValueError(f"Unknown LPS class '{lps}'.")
    if spd not in PSPD or eb not in PEB:
        raise ValueError("SPD levels are none, III-IV, II or I.")
    eb_eff = _better(eb, _LPS_TO_LPL[lps])          # an LPS brings its bonding SPDs
    ptws = float(p.get("ptws", 1.0))
    rt_tol = float(p.get("RT", RT))

    AD = float(p["AD"]) if p.get("AD") else collection_areas(L, W, H, [])[0]
    cd = CD[p.get("location", "isolated")]
    ND = NSG * AD * cd * 1e-6
    env = p.get("environment", "rural")
    p_lps = PLPS[lps]
    ps = 1.0 if lps != "none" else _key(PS, p.get("material", "masonry"), "construction")
    wm1 = p.get("mesh_width")
    ks1 = min(0.12 * float(wm1), 1.0) if wm1 else float(p.get("KS1", 1.0))

    lines = _default_lines(p)
    names = [l.get("name", f"line {i + 1}") for i, l in enumerate(lines)]
    ev = [_line_events(l, NSG, k, env) for l in lines]
    zones_in = p.get("zones") or [_default_zone(dict(p, lines=lines))]

    zones = []
    for zi, z in enumerate(zones_in):
        name = z.get("name", f"Z{zi + 1}")
        tz = float(z.get("tz", 8760.0))
        te = float(z.get("te", 8760.0))
        if not (0 <= tz <= 8760 and 0 <= te <= 8760):
            raise ValueError(f"Zone {name}: hours of presence must lie between 0 and 8760.")
        Pp, Pe = tz / 8760.0, te / 8760.0
        rt = _key(RT_SURF, z.get("surface", "concrete"), "floor surface")
        touch = z.get("touch", "none")
        pam = 1.0
        for t in (touch if isinstance(touch, (list, tuple)) else [touch]):
            pam *= _key(PAM, t, "touch protection")
        rf = _key(RF, z.get("fire_risk", "ordinary"), "fire risk")
        rp = _key(RP, z.get("fire_provisions", "none"), "fire provisions")
        explosive = str(z.get("fire_risk", "")).startswith("explosion")
        lc = LOSS[z.get("loss", "low")]
        # R_C1, R_M1, R_W1, R_Z1 count only where a failure of internal systems
        # endangers life (Table 3 note a): very-high-loss zones and explosion
        # risk by default; a hospital ward or the like is flagged by the user
        life = z.get("life_systems", z.get("loss", "low") == "very_high" or explosive)
        lt = float(z.get("LT", LT))
        ld = float(z.get("LD", LD)) if z.get("exposed") else 0.0
        lf1 = float(z.get("LF1", lc["LF"]))
        lf2 = float(z.get("LF2", lc["LF"]))
        lo1 = float(z.get("LO1", lc["LO"] if life else 0.0))
        lo2 = float(z.get("LO2", lc["LO"] if explosive else 0.0))
        wm2 = z.get("mesh_width")
        ks2 = min(0.12 * float(wm2), 1.0) if wm2 else float(z.get("KS2", 1.0))
        z_spd = z.get("spd", spd)
        if z_spd not in PSPD:
            raise ValueError(f"Zone {name}: unknown SPD level '{z_spd}'.")
        pspd = float(z.get("pspd", PSPD[z_spd]))

        PAT = p_lps * pam * rt * ptws
        PAD = ptws * pam * (1.0 if z.get("exposed") else 0.0) * p_lps
        PB = ps * p_lps * rf * rp
        c = dict(RAT=ND * PAT * Pp * lt, RAD=ND * PAD * Pp * ld,
                 RB1=ND * PB * Pp * lf1, RB2=ND * PB * lf2)
        pc_not, pm_not, uw_min = 1.0, 1.0, None
        used = {}
        sys_rows = []
        for s in z.get("systems") or []:
            li = s.get("line")
            if isinstance(li, str):
                if li not in names:
                    raise ValueError(f"Zone {name}: no incoming line named '{li}'.")
                li = names.index(li)
            line = lines[li] if li is not None else None
            cld, cli = CLD_CLI[line.get("shielding", "buried_unshielded")] if line else \
                (float(s.get("CLD", 0.0)), 0.0)
            if line is not None and (line.get("fibre") or line.get("optical")):
                cld, cli = 0.0, 0.0
            uw = float(s.get("Uw", line.get("Uw", 2.5) if line else 2.5))
            uw_min = uw if uw_min is None else min(uw_min, uw)
            ks3 = _key(KS3, s.get("ks3", "different_routing"), "internal wiring")
            pms = (ks1 * ks2 * ks3) ** 2
            s_pspd = float(s.get("pspd", PSPD[s.get("spd", z_spd)] if "spd" in s else pspd))
            pc_not *= 1.0 - min(s_pspd * cld, 1.0)
            pm_not *= 1.0 - min(s_pspd * pms, 1.0)
            if li is not None:
                used[li] = dict(cld=cld, cli=cli, pspd=s_pspd)
            sys_rows.append(dict(line=names[li] if li is not None else "—", CLD=cld, CLI=cli,
                                 KS3=ks3, PMS=pms, Uw=uw, PSPD=s_pspd))
        PC, PM = 1.0 - pc_not, 1.0 - pm_not
        NM = 0.0
        AM = 0.0
        if uw_min is not None:
            rm = r_M(uw_min)
            AM = 2 * rm * (L + W) + math.pi * rm ** 2
            NM = NSG / k * AM * 1e-6
        sur = surroundings_losses(z.get("surroundings"))
        if sur:
            ppe, lf1e, lo1e = sur["PPE"], sur["LF1E"], sur["LO1E"]
            lf2e, lo2e = sur["LF2E"], sur["LO2E"]
            c.update(RB1E=ND * PB * ppe * lf1e, RB2E=ND * PB * lf2e)
        c.update(RC1=ND * PC * Pp * Pe * lo1, RC2=ND * PC * Pe * lo2,
                 RM1=NM * PM * Pp * Pe * lo1, RM2=NM * PM * Pe * lo2,
                 RU=0.0, RV1=0.0, RV2=0.0, RW1=0.0, RW2=0.0, RZ1=0.0, RZ2=0.0)
        if sur:
            c.update(RC1E=ND * PC * ppe * Pe * lo1e, RC2E=ND * PC * Pe * lo2e,
                     RM1E=NM * PM * ppe * Pe * lo1e, RM2E=NM * PM * Pe * lo2e,
                     RV1E=0.0, RV2E=0.0, RW1E=0.0, RW2E=0.0, RZ1E=0.0, RZ2E=0.0)
        Fc = dict(FC=ND * PC * Pe, FM=NM * PM * Pe, FW=0.0, FZ=0.0)
        per_line = []
        for li, u in used.items():
            line, e = lines[li], ev[li]
            pld = p_ld(line.get("rs", "unshielded"), line.get("Uw", 2.5))
            peb = PEB[_better(line.get("eb", eb_eff), eb_eff)]
            PU = pam * peb * pld * ptws * u["cld"] * rt
            PV = peb * pld * ptws * u["cld"] * rf * rp
            PW = u["pspd"] * ptws * pld * u["cld"]
            PZ = u["pspd"] * ptws * u["cli"]
            n3 = e["NL"] + e["NDJ"]
            c["RU"] += n3 * PU * Pp * lt
            c["RV1"] += n3 * PV * Pp * lf1
            c["RV2"] += n3 * PV * lf2
            c["RW1"] += n3 * PW * Pp * Pe * lo1
            c["RW2"] += n3 * PW * Pe * lo2
            c["RZ1"] += e["NI"] * PZ * Pp * Pe * lo1
            c["RZ2"] += e["NI"] * PZ * Pe * lo2
            if sur:                            # Table E.1
                c["RV1E"] += n3 * PV * ppe * lf1e
                c["RV2E"] += n3 * PV * lf2e
                c["RW1E"] += n3 * PW * ppe * Pe * lo1e
                c["RW2E"] += n3 * PW * Pe * lo2e
                c["RZ1E"] += e["NI"] * PZ * ppe * Pe * lo1e
                c["RZ2E"] += e["NI"] * PZ * Pe * lo2e
            Fc["FW"] += n3 * PW * Pe
            Fc["FZ"] += e["NI"] * PZ * Pe
            per_line.append(dict(line=names[li], PLD=pld, PEB=peb, PU=PU, PV=PV, PW=PW, PZ=PZ))
        RL1 = sum(v for kk, v in c.items() if kk in ("RAT", "RAD", "RU") or kk.endswith(("1", "1E")))
        RL2 = sum(v for kk, v in c.items() if kk.endswith(("2", "2E")))
        RE = sum(v for kk, v in c.items() if kk.endswith("E"))
        R = RL1 + RL2
        F = sum(Fc.values())
        FT = z.get("FT")
        FT = float(FT) if FT not in (None, "") else None
        has_sys = bool(z.get("systems"))
        zones.append(dict(
            name=name, tz=tz, te=te, Pp=Pp, Pe=Pe, components=c, RL1=RL1, RL2=RL2, R=R,
            RE=RE, surroundings=sur,
            ok_R=R <= rt_tol, F=F, F_components=Fc, FT=FT,
            ok_F=(F <= FT) if (FT is not None and has_sys) else None,
            NM=NM, AM=AM, PAT=PAT, PAD=PAD, PB=PB, PC=PC, PM=PM, systems=sys_rows, lines=per_line,
            losses=dict(LT=lt, LD=ld, LF1=lf1, LF2=lf2, LO1=lo1, LO2=lo2),
            factors=dict(rt=rt, Pam=pam, rf=rf, rp=rp, KS1=ks1, KS2=ks2, PSPD=pspd)))
    Rmax = max(z["R"] for z in zones)
    ok_R = all(z["ok_R"] for z in zones)
    ok_F = all(z["ok_F"] is not False for z in zones)
    line_rows = [dict(name=n, **{kk: v for kk, v in e.items() if kk != "sections"},
                      sections=e["sections"]) for n, e in zip(names, ev)]
    comp_tot = {}
    for z in zones:
        for kk, v in z["components"].items():
            comp_tot[kk] = max(comp_tot.get(kk, 0.0), v)
    return dict(standard=STANDARD, NSG=NSG, k=k, AD=AD, ND=ND, CD=cd, lines=line_rows,
                zones=zones, R=Rmax, R1=Rmax, RT=rt_tol, ok_R=ok_R, ok_F=ok_F, ok=ok_R and ok_F,
                lps=lps, spd=spd, eb=eb, eb_effective=eb_eff, PLPS=p_lps, PS=ps, KS1=ks1,
                PTWS=ptws, components=comp_tot,
                F=max((z["F"] for z in zones if z["systems"]), default=0.0))


def _score(r):
    """How far a design is from meeting both criteria (≤ 1 meets them)."""
    s = r["R"] / r["RT"]
    for z in r["zones"]:
        if z["FT"] and z["systems"]:
            s = max(s, z["F"] / z["FT"])
    return s


def select(p: dict) -> dict:
    """Assess the structure as it is, then find the least protection that
    brings R to R_T in every zone and F to F_T wherever F_T is given: LPS
    class, coordinated SPDs, and bonding SPDs at the line entrances (an LPS
    brings bonding SPDs of its own level).  Cheapest first: one step for
    each class or level, ties broken by the lower remaining risk."""
    base = assess(p, "none", "none", "none")
    combos, seen = [], set()
    for lps, eb, spd in itertools.product(LPS_ORDER, SPD_ORDER, SPD_ORDER):
        eff = _better(eb, _LPS_TO_LPL[lps])
        if (lps, eff, spd) in seen:
            continue
        seen.add((lps, eff, spd))
        r = assess(p, lps, spd, eff)
        implied = SPD_ORDER.index(_LPS_TO_LPL[lps])
        rank = LPS_ORDER.index(lps) + max(SPD_ORDER.index(eff) - implied, 0) + SPD_ORDER.index(spd)
        combos.append(dict(lps=lps, eb=eff, spd=spd, R=r["R"], R1=r["R"], F=r["F"],
                           ok=r["ok"], ok_R=r["ok_R"], ok_F=r["ok_F"], rank=rank,
                           score=_score(r)))
    ok = sorted((c for c in combos if c["ok"]), key=lambda c: (c["rank"], c["R"]))
    choice = ok[0] if ok else None
    needed = not base["ok"]
    out = dict(standard=STANDARD, unprotected=base, combinations=combos, choice=choice,
               needed=needed, needed_R=not base["ok_R"], needed_F=not base["ok_F"])
    if choice:
        out["protected"] = assess(p, choice["lps"], choice["spd"], choice["eb"])
    else:
        best = min(combos, key=lambda c: (c["score"], c["rank"]))
        out["best"] = best
        out["protected"] = assess(p, best["lps"], best["spd"], best["eb"])
    worst = max(base["zones"], key=lambda z: z["R"])
    dom = max(worst["components"].items(), key=lambda kv: kv[1])

    def _desc(c):
        return (f"LPS {'class ' + c['lps'] if c['lps'] != 'none' else 'none'}, bonding SPDs at the line "
                f"entrances {'LPL ' + c['eb'] if c['eb'] != 'none' else 'none'}, coordinated SPDs "
                f"{'LPL ' + c['spd'] if c['spd'] != 'none' else 'none'}")

    if not needed:
        out["note"] = (f"Unprotected, the largest zone risk is R = {base['R']:.2e} per year against "
                       f"R_T = {base['RT']:.0e}" + (" and the frequency of damage is within F_T in every "
                       "zone where it is set" if any(z['FT'] for z in base['zones']) else "") +
                       f": {STANDARD} does not call for protection.")
    else:
        bits = []
        if not base["ok_R"]:
            bits.append(f"R = {base['R']:.2e} per year in zone {worst['name']} against R_T = "
                        f"{base['RT']:.0e} (largest component {dom[0]}, {dom[1]:.2e})")
        if not base["ok_F"]:
            fz = [z for z in base["zones"] if z["ok_F"] is False]
            bits.append("F above F_T in " + ", ".join(f"{z['name']} ({z['F']:.3g} > {z['FT']:g})" for z in fz))
        out["note"] = ("Unprotected: " + "; ".join(bits) + ". Protection is needed. " +
                       (f"The least protection that meets both criteria is {_desc(choice)}, "
                        f"giving R = {choice['R']:.2e}." if choice else
                        f"No combination of LPS and SPD levels in the tables meets both criteria on its "
                        f"own; the closest is {_desc(out['best'])}. The rest has to come from other "
                        "measures: shielded incoming lines with the shield bonded at entry (C_LD, C_LI, "
                        "Table B.9), spatial shielding (K_S1, K_S2), careful internal wiring (K_S3), "
                        "fire provisions (r_p), touch-voltage measures (P_am) or a thunderstorm warning "
                        "system (P_TWS)."))
    return out
