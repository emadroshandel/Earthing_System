"""
Independent audit of the EarthSystem engine.

Every expected value below is written out from the published formula rather
than taken from the module under test, so this checks the code against the
standard and not against itself.
"""
import math
import sys

sys.path.insert(0, '.')
from earthsys import (conductor, faultcurrent, iec60364, iec62305, ieee80,
                      ieee142, soil, materials, airterm)

FAILS = []
NOTES = []


def chk(name, got, want, tol=1e-3, unit=''):
    if want == 0:
        ok = abs(got) < tol
        rel = abs(got)
    else:
        rel = abs(got - want) / abs(want)
        ok = rel <= tol
    print(f"  [{'ok ' if ok else 'FAIL'}] {name:<58} got {got:>12.5g} "
          f"want {want:>12.5g} {unit}  ({rel*100:.3f} %)")
    if not ok:
        FAILS.append((name, got, want))


def note(s):
    NOTES.append(s)
    print(f"  [note] {s}")


print("\n=== 1. Soil — array reduction ==========================================")
# Wenner, rho = 2*pi*a*R
chk("Wenner rho from R (a=3 m, R=10 ohm)",
    soil.wenner_rho(10.0, 3.0), 2 * math.pi * 3.0 * 10.0)
# Schlumberger, rho = pi*R*(s^2 - (d/2)^2)/d
chk("Schlumberger rho (s=10, MN=1, R=2)",
    soil.schlumberger_rho(2.0, 10.0, 1.0),
    math.pi * 2.0 * (100.0 - 0.25) / 1.0)
# a uniform earth must invert back to itself
sp = [1, 2, 4, 8, 16]
d = soil.invert_two_layer(sp, [250.0] * len(sp), "wenner")
chk("uniform traverse inverts to rho1", d["rho1"], 250.0, 0.03)
chk("uniform traverse inverts to rho2", d["rho2"], 250.0, 0.08)
# the forward two-layer model must reproduce a known limit: at a << h the
# array sees only the upper layer, at a >> h only the lower
r1, r2, h = 300.0, 60.0, 2.0
chk("two-layer forward, a << h -> rho1", soil.wenner_two_layer(0.05, r1, r2, h), r1, 0.02)
chk("two-layer forward, a >> h -> rho2", soil.wenner_two_layer(400.0, r1, r2, h), r2, 0.05)

print("\n=== 2. Fault current ===================================================")
# IEC 60909 single line-to-earth:  Ik1 = c*sqrt(3)*Un / |Z1+Z2+Z0|
Z1 = complex(0.5, 5.0)
Z0 = complex(1.5, 15.0)
Un, c = 20.0, 1.1
want = c * math.sqrt(3) * Un * 1000.0 / abs(Z1 + Z1 + Z0) / 1000.0     # kA
f = faultcurrent.line_to_earth_fault(Un, Z1, Z1, Z0, 0j, c)
key = 'Ik1_kA' if 'Ik1_kA' in f else [k for k in f if k.endswith('_kA')][0]
chk("IEC 60909 Ik1'' from sequence impedances", f[key], want, 1e-6, 'kA')
# decrement factor, IEEE 80 Eq (79): Df = sqrt(1 + Ta/tf (1 - e^(-2tf/Ta)))
for tf, xr in ((0.5, 10.0), (0.1, 20.0), (1.0, 5.0)):
    Ta = xr / (2 * math.pi * 50.0)
    w = math.sqrt(1 + Ta / tf * (1 - math.exp(-2 * tf / Ta)))
    chk(f"decrement factor Df (tf={tf}s, X/R={xr})",
        faultcurrent.decrement_factor(tf, xr, 50.0)["Df"], w, 1e-9)

print("\n=== 3. Conductor sizing ================================================")
# IEEE 80 Eq (37) written out independently
m_ = materials.IEEE80_MATERIALS["cu_hard"]
I, tc, Ta, Tm = 6.8, 0.5, 40.0, m_["Tm"]
ar, K0, TCAP, rr = m_["alpha_r"], m_["K0"], m_["TCAP"], m_["rho_r"]
want = I / math.sqrt((TCAP * 1e-4) / (tc * ar * rr)
                     * math.log((K0 + Tm) / (K0 + Ta)))   # I in kA -> mm^2
got = conductor.ieee80_conductor_area(I, tc, "cu_hard", Ta)
key = 'A_mm2' if 'A_mm2' in got else [k for k in got if 'mm2' in k][0]
chk("IEEE 80 Eq (37) area, hard-drawn copper", got[key], want, 1e-4, 'mm2')
# IEC 60364-5-54 adiabatic  S = I*sqrt(t)/k
ad = conductor.adiabatic_area(6800.0, 0.5, "copper", "pvc70", "separate")
kk = ad.get("k")
akey = [x for x in ad if 'mm2' in x][0]
chk("IEC adiabatic S = I.sqrt(t)/k", ad[akey], 6800.0 * math.sqrt(0.5) / kk, 1e-9, 'mm2')
# the area must scale as sqrt(t) and linearly with I
a1 = conductor.ieee80_conductor_area(10.0, 1.0, "cu_hard", 40.0)[key]
a2 = conductor.ieee80_conductor_area(10.0, 4.0, "cu_hard", 40.0)[key]
chk("area doubles when the duration quadruples", a2 / a1, 2.0, 1e-6)
a3 = conductor.ieee80_conductor_area(20.0, 1.0, "cu_hard", 40.0)[key]
chk("area doubles when the current doubles", a3 / a1, 2.0, 1e-9)

print("\n=== 4. Electrodes (IEC 60364-5-54 / BS 7430) ===========================")
rho = 100.0
# Dwight rod:  R = rho/(2*pi*L) * [ln(8L/d) - 1]
L, dm = 3.0, 0.016
want = rho / (2 * math.pi * L) * (math.log(8 * L / dm) - 1.0)
chk("driven rod, Dwight", iec60364.rod(rho, L, dm)["R"], want, 1e-9, 'ohm')
# a rod twice as long is less than half the resistance? no - slightly more than half
r3 = iec60364.rod(rho, 3.0, dm)["R"]
r6 = iec60364.rod(rho, 6.0, dm)["R"]
print(f"  [info] rod 3 m {r3:.2f} ohm, 6 m {r6:.2f} ohm, ratio {r6/r3:.3f} "
      f"(expected a little above 0.5)")
if not (0.45 < r6 / r3 < 0.60):
    FAILS.append(("rod length scaling", r6 / r3, 0.52))
# plate, ring, foundation must all fall with 1/rho and be positive
for nm, fn in (("rod", lambda: iec60364.rod(rho, 3, .016)),
               ("strip", lambda: iec60364.horizontal_strip(rho, 20, .03, .6)),
               ("ring", lambda: iec60364.ring(rho, 6, .01, .7)),
               ("plate", lambda: iec60364.plate(rho, 1.0, 1.0)),
               ("foundation", lambda: iec60364.foundation(rho, 400.0)),
               ("mesh", lambda: iec60364.mesh(rho, 200, 120, .7))):
    R = fn()["R"]
    print(f"  [info] {nm:<11} R = {R:8.3f} ohm at rho = {rho:g}")
    if not (R > 0 and math.isfinite(R)):
        FAILS.append((nm + " resistance", R, "positive finite"))
# resistance must be exactly proportional to resistivity
R100 = iec60364.rod(100.0, 3, .016)["R"]
R400 = iec60364.rod(400.0, 3, .016)["R"]
chk("rod resistance is proportional to rho", R400 / R100, 4.0, 1e-9)
# rods in parallel: worse than R/n, better than R
one = iec60364.rod(rho, 3, .016)["R"]
grp = iec60364.rods_parallel(rho, 3, .016, 4, 6.0)["R"]
print(f"  [info] one rod {one:.2f} ohm, four at 6 m spacing {grp:.2f} ohm "
      f"(ideal parallel would be {one/4:.2f})")
if not (one / 4 < grp < one):
    FAILS.append(("parallel rods bracket", grp, f"{one/4:.2f}..{one:.2f}"))

print("\n=== 5. IEEE 80 — Annex B worked example ================================")
GEO = lambda **kw: ieee80.GridGeometry(**{**dict(Lx=70.0, Ly=70.0, D=7.0, h=0.5,
                                              d=0.01), **kw})
g = ieee80.design(400.0, GEO(), 1.908, rho_s=2500.0, hs=0.102, ts=0.5, body_weight=70)
chk("Cs surface derating", g["tolerable"]["Cs"], 0.74, 0.02)
chk("E_touch tolerable (70 kg)", g["tolerable"]["E_touch"], 838.2, 0.01, 'V')
chk("E_step tolerable (70 kg)", g["tolerable"]["E_step"], 2686.6, 0.01, 'V')
chk("grid resistance Rg", g["Rg"], 2.78, 0.02, 'ohm')
chk("ground potential rise", g["GPR"], 5304.0, 0.01, 'V')
chk("GPR = IG x Rg is self-consistent", g["GPR"], 1.908e3 * g["Rg"], 1e-6, 'V')
chk("mesh voltage Em", g["mesh"]["Em"], 1002.1, 0.05, 'V')
# the 50 kg criterion must be the more onerous one
g50 = ieee80.design(400.0, GEO(), 1.908, rho_s=2500.0, hs=0.102, ts=0.5, body_weight=50)
if not g50["tolerable"]["E_touch"] < g["tolerable"]["E_touch"]:
    FAILS.append(("50 kg is more conservative", g50["tolerable"]["E_touch"],
                  "< 70 kg value"))
print(f"  [info] tolerable touch: 70 kg {g['tolerable']['E_touch']:.0f} V, "
      f"50 kg {g50['tolerable']['E_touch']:.0f} V")
# closing the conductor spacing must lower the mesh voltage
gD = ieee80.design(400.0, GEO(D=3.5), 1.908, rho_s=2500.0, hs=0.102, ts=0.5, body_weight=70)
print(f"  [info] Em at D=7 m {g['mesh']['Em']:.0f} V, at D=3.5 m {gD['mesh']['Em']:.0f} V")
if not gD["mesh"]["Em"] < g["mesh"]["Em"]:
    FAILS.append(("finer mesh lowers Em", gD["mesh"]["Em"], "< coarse"))

print("\n=== 6. LV installations (IEC 60364) ====================================")
t = iec60364.max_disconnection_time("TN", 230.0, "final")
chk("TN final circuit at 230 V", t["t"], 0.4, 1e-9, 's')
chk("TT final circuit at 230 V",
    iec60364.max_disconnection_time("TT", 230.0, "final")["t"], 0.2, 1e-9, 's')
chk("TN distribution circuit",
    iec60364.max_disconnection_time("TN", 230.0, "distribution")["t"], 5.0, 1e-9, 's')
# a B32 MCB trips instantaneously at 5 x In
chk("MCB curve B multiplier",
    iec60364.device_Ia("mcb", 32.0, 0.4, "B")["Ia"], 5 * 32.0, 1e-9, 'A')
chk("MCB curve C multiplier",
    iec60364.device_Ia("mcb", 32.0, 0.4, "C")["Ia"], 10 * 32.0, 1e-9, 'A')
# TT:  R_A * I_a <= 50 V
c = iec60364.tt_electrode_check(20.0, 0.5, 50.0)
chk("TT check R_A x Ia", c["touch_voltage"], 10.0, 1e-9, 'V')
if not c["passed"]:
    FAILS.append(("TT 20 ohm with 500 mA RCD should pass", c["value"], "<= 50"))
# the largest RCD allowed on a 100 ohm electrode is 500 mA (100 x 0.5 = 50 V)
sel = iec60364.rcd_selection(100.0, 50.0)
print(f"  [info] on a 100 ohm electrode the largest RCD is "
      f"{sel['selected_IdN']*1000 if sel['selected_IdN'] else None} mA")
if sel["selected_IdN"] and sel["selected_IdN"] * 100.0 > 50.0 + 1e-9:
    FAILS.append(("RCD selection exceeds 50 V", sel["selected_IdN"] * 100.0, "<= 50"))

print("\n=== 7. Lightning earth termination (IEC 62305-3) =======================")
for cls, expect in (("I", 20), ("II", 30), ("III", 45), ("IV", 60)):
    chk(f"class {cls} rolling sphere in iec62305 matches airterm",
        iec62305.LPS_CLASS[cls]["rolling_sphere"], expect, 1e-9, 'm')
    chk(f"class {cls} rolling sphere agrees between the two modules",
        airterm.ROLLING_SPHERE_R[cls], iec62305.LPS_CLASS[cls]["rolling_sphere"], 1e-9)
# l1 grows with resistivity and with the protection level
l_low = iec62305.min_electrode_length("I", 500.0)["l1"]
l_high = iec62305.min_electrode_length("I", 3000.0)["l1"]
print(f"  [info] class I l1: {l_low:.0f} m at 500 ohm.m, {l_high:.0f} m at 3000 ohm.m")
if not l_high > l_low:
    FAILS.append(("l1 grows with rho", l_high, "> " + str(l_low)))
if not iec62305.min_electrode_length("I", 2000.0)["l1"] >= \
       iec62305.min_electrode_length("III", 2000.0)["l1"]:
    FAILS.append(("l1 is larger for class I than class III", None, None))
# separation distance s = ki*kc*l/km, and concrete needs twice the air distance
a = iec62305.separation_distance("III", 10.0, 4, "air")
b = iec62305.separation_distance("III", 10.0, 4, "concrete")
chk("separation s = ki*kc*l/km (air)", a["s"], 0.04 * 0.44 * 10.0 / 1.0, 1e-9, 'm')
chk("concrete doubles the separation distance", b["s"] / a["s"], 2.0, 1e-9)

print("\n=== 8. System neutral grounding (IEEE 142) =============================")
# charging current 3*I_C0 = 3 * 2*pi*f*C0*V_ln
V, km, C0, f_ = 6.6, 8.0, 0.25, 50.0
Vln = V * 1000.0 / math.sqrt(3)
want = 3 * 2 * math.pi * f_ * (C0 * 1e-6 * km) * Vln
cc = ieee142.charging_current(V, km, C0, 0.0, 0.0, f_, 0.0)
chk("cable charging current 3.Ic0", cc["three_IC0"], want, 0.02, 'A')
# effectively grounded needs X0/X1 <= 3 and R0/X1 <= 1
e1 = ieee142.effectively_grounded(25.0, 10.0, 5.0)     # X0/X1 = 2.5
e2 = ieee142.effectively_grounded(40.0, 10.0, 5.0)     # X0/X1 = 4.0
print(f"  [info] X0/X1 = 2.5 -> effectively grounded: {e1['effectively_grounded']}; "
      f"X0/X1 = 4.0 -> {e2['effectively_grounded']}")
if not (e1["effectively_grounded"] and not e2["effectively_grounded"]):
    FAILS.append(("effectively-grounded test", (e1, e2), "True then False"))

print("\n=== 9. Air termination (IEC 62305-3 Annex A) ===========================")
R = 45.0
chk("r_p of a 10 m mast, class III", airterm.protection_radius(R, 10.0, 0.0),
    math.sqrt(2 * R * 10 - 100), 1e-12, 'm')
chk("sag between masts 30 m apart", airterm.sphere_sag(R, 30.0),
    R - math.sqrt(R * R - 225.0), 1e-12, 'm')
# the numerical roll must agree with both
pts, _ = airterm.build_geometry({"width": 0, "height": 0},
                                [{"x": -15, "height": 10, "base": 0},
                                 {"x": 15, "height": 10, "base": 0}], R=R)
prof = airterm.roll_sphere(pts, R, -90, 90, samples=4001)
chk("numerical roll reproduces the sag", airterm._profile_height(prof, 0.0),
    10.0 - airterm.sphere_sag(R, 30.0), 2e-3, 'm')

print("\n=== 9b. Impulse behaviour (effective length and effective area) ========")
# L_eff recomputed from the closed form, in both feed conditions
for _rho, _tau, _feed, _k in ((100.0, 1.0, "end", 1.40),
                              (400.0, 0.25, "centre", 1.55),
                              (1000.0, 10.0, "end", 1.40)):
    chk(f"L_eff at {_rho:.0f} ohm.m, {_tau} us, {_feed}-fed",
        iec62305.effective_length(_rho, _tau, _feed)["L_eff"],
        _k * math.sqrt(_rho * _tau), 1e-12, 'm')

# the effective radius of the program's default switchyard, both feed points
_A, _rho, _sp = 70.0 * 70.0, 400.0, 7.0
_ea_c = iec62305.effective_area(_rho, 1.0, _A, _sp, "centre")
_ea_k = iec62305.effective_area(_rho, 1.0, _A, _sp, "corner")
chk("Gupta & Thapar, centre-fed", _ea_c["models"][0]["r"],
    (1.45 - 0.05 * _sp) * math.sqrt(_rho), 1e-9, 'm')
chk("Gupta & Thapar, corner-fed", _ea_k["models"][0]["r"],
    (0.60 - 0.025 * _sp) * math.sqrt(_rho), 1e-9, 'm')
_gr = [m for m in _ea_c["models"] if m["name"] == "Grcev"][0]
chk("Grcev, centre-fed", _gr["r"], math.exp(0.84 * _rho ** 0.22), 1e-9, 'm')
print(f"  [info] 70x70 m grid at {_rho:.0f} ohm.m, 1 us front: centre-fed "
      f"{100 * _ea_c['fraction_min']:.0f}-{100 * _ea_c['fraction_max']:.0f} % of the "
      f"area works, corner-fed {100 * _ea_k['fraction_min']:.0f}-"
      f"{100 * _ea_k['fraction_max']:.0f} %")
if not _ea_k["r_min"] < _ea_c["r_min"]:
    FAILS.append(("a corner feed must use less area than a centre feed",
                  (_ea_k["r_min"], _ea_c["r_min"]), "corner < centre"))

# an 8 us front brings the whole grid into use
_ea_slow = iec62305.effective_area(_rho, 8.0, _A, _sp, "centre")
if not _ea_slow["fully_used"]:
    FAILS.append(("a slow front should use the whole grid",
                  _ea_slow["fraction_min"], "1.0"))
chk("effective radius is capped at the electrode", _ea_slow["r_max"],
    math.sqrt(_A / math.pi), 1e-9, 'm')

# the impulse coefficient and the potential rise it implies
_ir = iec62305.impulse_response(_rho, 1.0, 4.49, area=_A, spacing=_sp,
                                injection="corner", I_kA=100.0)
chk("impulse coefficient A = r_geom / r_eff", _ir["impulse_coefficient"],
    math.sqrt(_A / math.pi) / _ea_k["r_min"], 1e-9, '')
chk("EPR under the impulse = A.R.I", _ir["EPR_impulse"],
    _ir["impulse_coefficient"] * 4.49 * 100.0 * 1000.0, 1e-6, 'V')
if not _ir["EPR_impulse"] > _ir["EPR_lf"]:
    FAILS.append(("the impulse EPR must exceed I.R",
                  (_ir["EPR_impulse"], _ir["EPR_lf"]), "impulse > I.R"))
print(f"  [info] a 4.49 ohm grid struck at a corner behaves like "
      f"{_ir['Z_impulse']:.1f} ohm: {_ir['EPR_impulse'] / 1e3:.0f} kV instead of "
      f"{_ir['EPR_lf'] / 1e3:.0f} kV")

print("\n=== 10. Cross-module consistency =======================================")
# the fault module reports IG in kA and the grid module consumes kA
fr = faultcurrent.grid_current(6.8, 0.6, 1.0, 1.0)
print(f"  [info] 3I0 = 6.8 kA, Sf = 0.6 -> IG = {fr['IG_kA']:.4g} kA")
chk("IG = Df.Sf.Cp.3I0", fr["IG_kA"], 6.8 * 0.6, 1e-9, 'kA')
gg = ieee80.design(400.0, GEO(), fr["IG_kA"], rho_s=2500.0, hs=0.102, ts=0.5,
                   body_weight=70)
chk("GPR scales with the grid current handed over", gg["GPR"],
    fr["IG_kA"] * 1000.0 * gg["Rg"], 1e-6, 'V')

print("\n" + "=" * 72)
if FAILS:
    print(f"{len(FAILS)} CHECK(S) FAILED:")
    for n, got, want in FAILS:
        print(f"   - {n}: got {got!r}, wanted {want!r}")
    sys.exit(1)
print("all independent checks agree with the published formulas")
