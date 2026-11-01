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
Surge protective device (SPD) selection and coordination, IEC 62305-4:2024
Annex C, IEC 62305-1:2024 Annex E and IEC 61643-12 (1.8.0; brought to the
2024 editions in 1.8.5).

* Lightning current share — for a direct flash to the structure, about
  half the current goes into the earth termination and half into the
  services; it divides equally between the services and between their
  conductors (IEC 62305-1 Annex E):  I_imp = 0.5·I / (n_s·m).
* Effective protection level (IEC 62305-4:2024 C.2.3.3) — the SPD's U_p
  plus the inductive drop of its connecting leads, U_p/f = U_p + ΔU for a
  voltage-limiting SPD and max(U_p, ΔU) for a voltage-switching one, with
  ΔU = 0.1·I_SPD kV per metre of lead (C.4) — 1 kV/m at 10 kA.  I_SPD is
  the current expected through the SPD: the share 0.5·I/(n_s·m) at a
  Type 1, 10 kA at the later stages unless given.
* Protection condition (C.2.3.1, C.2.3.2):
      U_p/f ≤ U_w                when the SPD is at the equipment,
      U_p/f ≤ 0.8·U_w            when the circuit to the equipment is ≤ 10 m,
      U_p/f ≤ (U_w − U_i)/k      when it is longer (Rule 2, C.1), k the
                                 reflection factor, 1…2, 2 when unknown,
  with U_i the voltage induced in the circuit loop by nearby flashes;
  U_p ≤ 0.5·U_w where the failure of internal systems is critical.
* Simplified selection at the origin of the installation (Tables C.3,
  C.4): I_imp per protection mode for CT1 and CT2 connections, and the
  conventional surge currents of IEC 62305-1:2024 Tables E.1 and E.2 by
  source of damage.
* Energy coordination between stages — a voltage-switching Type 1 SPD
  (spark gap) ahead of a voltage-limiting Type 2 (MOV) needs about 10 m of
  cable or a decoupling inductor between them; two MOV stages about 5 m
  (IEC 61643-12 and manufacturers' data) unless the manufacturer declares
  them coordinated.
"""

from __future__ import annotations

import math

I_PEAK = {"I": 200.0, "II": 150.0, "III": 100.0, "IV": 100.0, "III-IV": 100.0}
UW_CATEGORY = {"I": 1.5, "II": 2.5, "III": 4.0, "IV": 6.0}     # 230/400 V, IEC 60664-1

# IEC 62305-4:2024 Table C.3: I_imp (kA, 10/350) per mode at the origin of the
# installation of a building protected against direct strikes (S1)
_IIMP_MODE = {"I": 25.0, "II": 18.75, "III-IV": 12.5}
# Table C.4: I_n (kA, 8/20) when no Type 1 test is needed
_IN_MODE = 5.0
# IEC 62305-1:2024 Tables E.1 (low voltage) and E.2 (telecommunication):
# conventional surge currents by source of damage and LPL, kA
SURGE_LV = {"III-IV": dict(S3=5.0, S4=0.3, S2=0.1, S1_inductive=5.0, S1_resistive=12.5),
            "II": dict(S3=7.5, S4=0.45, S2=0.15, S1_inductive=7.5, S1_resistive=18.75),
            "I": dict(S3=10.0, S4=0.6, S2=0.2, S1_inductive=10.0, S1_resistive=25.0)}
SURGE_TLC = {"III-IV": dict(S3=1.0, S4=0.3, S2=0.1, S1_inductive=5.0, S1_resistive=1.25),
             "II": dict(S3=1.5, S4=0.45, S2=0.15, S1_inductive=7.5, S1_resistive=1.875),
             "I": dict(S3=2.0, S4=0.6, S2=0.2, S1_inductive=10.0, S1_resistive=2.5)}


def simplified_selection(lpl: str, phases: int = 3, connection: str = "CT1") -> dict:
    """Minimum I_imp (Table C.3) and I_n (Table C.4) per protection mode."""
    lpl = "III-IV" if lpl in ("III", "IV") else lpl
    if lpl not in _IIMP_MODE:
        raise ValueError("LPL must be I, II or III-IV.")
    i = _IIMP_MODE[lpl]
    mult = 2 if int(phases) == 1 else 4
    if connection.upper() == "CT2":
        imp = {"L-N": i, "N-PE": i * mult}
        inn = {"L-N": _IN_MODE, "N-PE": _IN_MODE * mult}
    else:
        imp = {"L-PE": i, "N-PE": i}
        inn = {"L-PE": _IN_MODE, "N-PE": _IN_MODE}
    return dict(lpl=lpl, phases=int(phases), connection=connection.upper(), Iimp_kA=imp, In_kA=inn)


def induced_voltage(loop_area_m2: float, distance_m: float, I_kA: float = 100.0,
                    di_dt_kA_us: float | None = None) -> float:
    """Voltage induced in a loop by a nearby flash, kV (rough, unshielded):
    U_i = μ0·A·(di/dt)/(2π·s).  The default di/dt is that of the subsequent
    stroke of the LPL I parameters (IEC 62305-1 Table 3: 200 kA/µs at 50 kA;
    scaled here with the peak)."""
    if loop_area_m2 <= 0 or distance_m <= 0:
        return 0.0
    didt = (di_dt_kA_us if di_dt_kA_us else 200.0 * I_kA / 200.0) * 1e9   # A/s
    return 4e-7 * math.pi * loop_area_m2 * didt / (2 * math.pi * distance_m) / 1e3


def coordinate(p: dict) -> dict:
    lpl = str(p.get("lpl", "III-IV"))
    if lpl not in I_PEAK:
        raise ValueError("LPL must be I, II, III-IV.")
    n_s = max(int(p.get("n_services", 2)), 1)
    m = max(int(p.get("conductors", 4)), 1)
    I = I_PEAK[lpl]
    iimp = 0.5 * I / (n_s * m)
    stages = p.get("stages") or [
        dict(name="Main board — Type 1", type="1", technology="switching", Up=2.5, lead=0.5,
             Iimp=12.5, In=None, distance_to_next=10.0),
        dict(name="Sub-board — Type 2", type="2", technology="limiting", Up=1.3, lead=0.5,
             Iimp=None, In=20.0, distance_to_next=None)]
    Uw = float(p.get("Uw", 2.5))
    k_refl = min(max(float(p.get("k_reflection", 2.0)), 1.0), 2.0)
    critical = bool(p.get("critical"))
    l_eq = float(p.get("circuit_length", 5.0))
    Ui = float(p.get("Ui", 0.0) or 0.0)
    if p.get("loop_area") and p.get("flash_distance"):
        Ui = induced_voltage(float(p["loop_area"]), float(p["flash_distance"]), I)
    rows = []
    checks = []
    for i, s in enumerate(stages):
        Up = float(s["Up"])
        # the current that actually flows through the SPD: the expected share
        # of the lightning current at a Type 1, 10 kA (1 kV/m) elsewhere
        i_spd = s.get("I_spd") or (iimp if str(s.get("type")) == "1" else 10.0)
        i_spd = float(i_spd)
        dU = 0.1 * i_spd * float(s.get("lead", 0.5))            # IEC 62305-4:2024 (C.4)
        upf = max(Up, dU) if s.get("technology") == "switching" else Up + dU
        rows.append(dict(name=s.get("name", f"stage {i + 1}"), Up=Up, dU=dU, Upf=upf, I_spd=i_spd))
        if str(s.get("type")) == "1":
            ok = float(s.get("Iimp") or 0) >= iimp
            checks.append(dict(name=f"{s.get('name')}: impulse current I_imp", value=float(s.get("Iimp") or 0),
                               limit=iimp, unit="kA", passed=ok, sense=">=",
                               note=f"0.5·{I:g} kA / ({n_s} services × {m} conductors)"))
        if str(s.get("type")) == "2" and s.get("In") is not None:
            ok = float(s["In"]) >= 5.0
            checks.append(dict(name=f"{s.get('name')}: nominal discharge current I_n",
                               value=float(s["In"]), limit=5.0, unit="kA", passed=ok, sense=">=",
                               note="IEC 60364-5-534: at least 5 kA 8/20 per mode"))
        if i + 1 < len(stages):
            nxt = stages[i + 1]
            need = 10.0 if (s.get("technology") == "switching" and nxt.get("technology") == "limiting") else 5.0
            dist = s.get("distance_to_next")
            if s.get("coordinated_by_manufacturer"):
                checks.append(dict(name=f"Energy coordination {s.get('name')} → {nxt.get('name')}",
                                   value=None, limit=None, unit="m", passed=True,
                                   note="declared coordinated by the manufacturer"))
            else:
                ok = dist is not None and float(dist) >= need
                checks.append(dict(name=f"Energy coordination {s.get('name')} → {nxt.get('name')}",
                                   value=None if dist is None else float(dist), limit=need, unit="m",
                                   passed=bool(ok), sense=">=",
                                   note="decoupling cable length (or a decoupling inductor)"))
    last = rows[-1]
    if l_eq <= 0.0:
        lim, rule = Uw, "SPD at the equipment terminals: U_p/f ≤ U_w"
    elif l_eq <= 10.0:
        lim, rule = 0.8 * Uw, "circuit to the equipment ≤ 10 m: U_p/f ≤ 0.8·U_w"
    else:
        lim, rule = (Uw - Ui) / k_refl, f"circuit longer than 10 m: U_p/f ≤ (U_w − U_i)/k, k = {k_refl:g} (C.1)"
    checks.append(dict(name="Protection level at the equipment", value=last["Upf"], limit=lim,
                       unit="kV", passed=last["Upf"] <= lim, sense="<=", note=rule))
    if critical:
        checks.append(dict(name="Critical internal systems: U_p ≤ 0.5·U_w", value=last["Up"],
                           limit=0.5 * Uw, unit="kV", passed=last["Up"] <= 0.5 * Uw, sense="<=",
                           note="IEC 62305-4:2024 C.2.3.1.1, voltage doubling by oscillation"))
    ok = all(c["passed"] for c in checks)
    lk = "III-IV" if lpl in ("III", "IV", "III-IV") else lpl
    simp = simplified_selection(lk, int(p.get("phases", 3)), str(p.get("connection", "CT1")))
    return dict(lpl=lpl, I_peak_kA=I, Iimp_per_conductor_kA=iimp, Uw=Uw, Ui=Ui,
                simplified=simp, surge_lv=SURGE_LV[lk], surge_telecom=SURGE_TLC[lk],
                k_reflection=k_refl,
                circuit_length=l_eq, stages=rows, checks=checks, passed=ok,
                note=("Every stage, its coordination and the protection level at the equipment "
                      "meet IEC 62305-4." if ok else
                      "At least one condition fails: see the rows marked. A lower U_p, shorter "
                      "connecting leads, an SPD closer to the equipment or more decoupling length "
                      "are the usual remedies."))
