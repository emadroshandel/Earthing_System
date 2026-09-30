# Earthing System

**Earthing (grounding) system design for homes, buildings, substations and power plants.**

Implements IEEE Std 80-2013, IEC 60364-4-41 / -5-54, IEC 62305-3, IEC 60909-0 and
IEEE Std 142, adds a boundary-element numerical solver for arbitrary electrode geometry in
uniform or two-layer soil, explains *why* every compliance criterion passed or failed, and
produces a printable design report in English or Persian. Version 1.3 places the design in
the wider standards landscape: BS EN 50522, ENA EG-0/EG-1 and AS 2067 touch-voltage criteria,
CIGRE TB 781 frequency-dependent soil, and the codes for renewables, pipelines, HVDC
electrodes, data centres, telecommunications and fault-current distribution
(`earthsys/standards.py`, §17).

Runs three ways from the same code: a local desktop window, a local browser application, or
entirely inside your browser with no installation at all.

**▶ Live demo — no installation:** https://emadroshandel.github.io/Earthing_System/

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/validation-112%20checks-brightgreen.svg)](tests/test_validation.py)

---

## Contents

1. [Why this exists](#1-why-this-exists)
2. [Install](#2-install)
3. [Quick start](#3-quick-start)
4. [The interface](#4-the-interface)
5. [The ten modules](#5-the-ten-modules)
6. [Why it passed or failed](#6-why-it-passed-or-failed)
7. [The numerical solver](#7-the-numerical-solver)
8. [Reports](#8-reports)
9. [Python API](#9-python-api)
10. [What it writes](#10-what-it-writes)
11. [Theory and teaching material](#11-theory-and-teaching-material)
12. [Validation and tests](#12-validation-and-tests)
13. [Running it online](#13-running-it-online)
14. [Limitations](#14-limitations)
15. [Troubleshooting](#15-troubleshooting)
16. [Contributing](#16-contributing)
17. [Licence and references](#17-licence-and-references)

---

## 1. Why this exists

Earthing design is spread across a shelf of standards that do not talk to each other. The
soil survey is IEEE 81, the fault current is IEC 60909, the conductor is IEEE 80 *or*
IEC 60364 depending on who you ask, the substation grid is IEEE 80, the house is
IEC 60364, the lightning termination is IEC 62305, and the neutral is IEEE 142. Each has
its own symbols and its own worked examples, and the numbers have to be carried by hand
from one to the next.

The commercial tools that join them up are expensive and closed — you cannot see what they
compute, and you certainly cannot teach from them.

Earthing System joins them up in one place, shows every intermediate quantity with the clause
it came from, explains each verdict in words a student or a reviewer can follow, and is
small enough to read end to end. The calculation engine is about 3000 lines of dependency-
light Python.

## 2. Install

**Requirements:** Python 3.9 or newer. `numpy` is needed only for the numerical solver.
`pywebview` is optional and gives a native desktop window. Everything else — the HTTP
server, the whole engine, the report generator — is Python standard library. Plotly is
bundled, so the application works offline.

```bash
git clone https://github.com/emadroshandel/Earthing_System.git
cd Earthing_System
pip install -r requirements.txt        # numpy; pywebview optional
```

On Windows there is nothing to install by hand — the launchers find Python and fetch
`numpy` themselves on first run.

## 3. Quick start

**Windows**

> Double-click **`Run EarthSystem (browser).bat`** — or **`Run EarthSystem (desktop).bat`**
> for a native window.

**Any platform**

```bash
python server.py                     # opens your browser automatically
python server.py --port 8800 --no-browser
python desktop.py                    # native window via pywebview
python START_EarthSystem.py          # fallback if batch files are blocked
```

**No installation at all** — open the [live demo](https://emadroshandel.github.io/Earthing_System/).
The same Python engine runs in your browser through Pyodide; nothing is uploaded anywhere.

Then load one of the example projects with the **Import** button:

| File | What it is |
|---|---|
| `examples/ieee80_annexB.json` | The worked example from IEEE Std 80-2013 Annex B |
| `examples/villa_TT.json` | A domestic TT installation with a foundation electrode |

## 4. The interface

Ten pages down the left, in the order a real design goes:

```
Inputs           1  Soil model          field data → two-layer earth
                 2  Fault current       IEC 60909 → I_G
                 3  Conductor sizing    thermal sizing, PE and bonding

Design modules   4  Substation grid     the full IEEE 80 procedure
                 5  Numerical solver    boundary-element method
                 6  Buildings & homes   IEC 60364, TN / TT / IT
                 7  Lightning earth     IEC 62305-3, earth termination
                 8  Air termination     IEC 62305-3, rolling sphere zone
                 9  System grounding    IEEE 142, neutral earthing

Output          10  Design report       English or Persian, printable
                 i  Theory & reference  the physics behind every page
```

Every input carries a small **?** beside its label. Hover it — or the label — and a
short explanation appears saying what the quantity is, what it is measured between, and
where a typical value comes from, so `D` reads as "centre-to-centre distance between
adjacent parallel grid conductors" rather than just `D`. Click the **?** to keep the
explanation open while you read it. The geometry tables name and dimension every
parameter the same way. **Explain all** in the top bar drops every explanation inline at
once, which is what you want when teaching from the form or printing it.

Every design page also carries a **scale section drawing** of what it just computed — the
fitted soil strata with the electrode depths on them, the grid with its surface layer and
what touch and step voltage actually mean on site, the electrode type you selected drawn to
its own dimensions, and the rolling sphere rolled over the structure in elevation and plan.
The drawings are built from the same numbers as the results table, so a reader can check the
model against the site before trusting the answer, and they are embedded in the report.

The modules feed each other. **Pull inputs** on the grid page takes ρ from the soil model,
`I_G` from the fault module and the conductor diameter from the sizing module. **Build from
the IEEE 80 grid** on the numerical page rebuilds the same geometry for the solver, so the
closed-form and numerical answers can be compared directly.

A green or red dot on each nav item shows whether that module has been run and whether it
complied.

## 5. The ten modules

| # | Module | Standard | What it computes |
|---|---|---|---|
| 1 | Soil model | IEEE Std 81-2025 §7.3, §7.6 | Wenner / Schlumberger reduction, two-layer inversion (ρ₁, ρ₂, h, K) by Nelder–Mead, equivalent uniform ρ |
| 2 | Fault current | IEC 60909-0, IEEE 80 §15 | Iₖ₁″, Iₖ″, iₚ, I_th, decrement factor D_f, split factor S_f, maximum grid current I_G |
| 3 | Conductor sizing | IEEE 80 Eq. (37), IEC 60364-5-54 | Minimum area by both methods, joint temperature limits, PE and bonding sizes, minimum buried sizes |
| 4 | Substation grid | IEEE Std 80-2013 | Tolerable touch/step voltages, R_g by Sverak **and** Schwarz, GPR, E_m, E_s, and an auto-refinement search |
| 5 | Numerical solver | Boundary-element method | Arbitrary geometry, uniform or two-layer soil, surface potential field, touch/step maps, per-segment leakage current |
| 6 | Buildings & homes | IEC 60364-4-41 / -5-54 | Electrode resistances, R_A, Z_s, disconnection time, RCD selection, TN / TT / IT |
| 7 | Lightning earth | IEC 62305-3 | LPS class data, l₁, Type A / Type B termination, down-conductors, separation distance s, and the behaviour under the impulse: effective length L_eff = k(ρT)^0.5, effective area of a meshed system by three published expressions, centre versus corner injection, and the impulse coefficient A = Z/R that says by how much a measured resistance understates the potential rise |
| 8 | Air termination | IEC 62305-3 Annex A | Rolling sphere rolled numerically over the structure, protected radius r_p, sphere penetration between terminations, maximum span, roof-field and roof-edge checks, plan coverage, protective angle and mesh methods |
| 9 | System grounding | IEEE 142, IEEE C62.92 | Method selection, NER sizing, charging current, effectively-grounded test |
| 10 | Design report | — | One printable HTML document, English or Persian (RTL), drawings and charts embedded |

## 6. Why it passed or failed

Every compliance row expands. Under it you get four things, computed from your own numbers:

- **What the criterion means** — the physics it protects against.
- **What drives the number** — the formula with your values substituted.
- **Why it passed or failed** — the quantified comparison.
- **How to fix it** — each remedy with its own computed magnitude.

For example, when the IEEE 80 mesh voltage fails, the software does not say "reduce the
spacing". It says:

> E_m = 1002 V exceeds the tolerable touch voltage of 841 V by 19.2 %. A person touching an
> earthed structure at the centre of a corner mesh during the fault could pass more than the
> fibrillation current.
>
> 1. Reduce the fault clearing time from 0.50 s to **0.35 s** or less — the tolerable
>    voltage scales as 1/√t_s, so this alone closes the gap.
> 2. Increase the surface-layer thickness from 0.102 m to about **0.548 m**.
> 3. Increase the effective mesh length L_M by a factor of at least **1.19** (from 1540 m to
>    about 1835 m).
> 4. Reduce I_G from 1.908 kA to **1.601 kA** — usually by a lower split factor S_f.

The same blocks appear in the generated report, so a design review can be held on the
document alone.

## 7. The numerical solver

The buried metal is discretised into cylindrical segments held at one potential; solving
for the leakage-current distribution gives the true earth resistance and the whole surface
potential field. It removes three restrictions of the closed-form equations at once:
arbitrary shape, layered soil, and non-uniform current leakage.

Two implementation details make it trustworthy:

- **The self term is exact.** `P_ii = ρ/(2πL)[ln(2L/a) − 1]`, derived analytically. With a
  single segment the solver reproduces Dwight's rod formula to better than 0.2 %.
- **Near pairs use Galerkin double quadrature, not collocation.** Mid-point collocation
  under-estimates the potential of a close source by about 21 %, which biases the computed
  earth resistance 5–15 % *low* — an error in the unsafe direction. This is the single
  most important line of code in `bem.py`.

Outputs: 2-D and 3-D surface potential, touch and step voltage maps, an arbitrary traverse
profile, per-segment leakage current, and a 3-D view of the electrode geometry.

## 8. Reports

One HTML document, printable to PDF from any browser, containing the inputs, every
intermediate quantity with its clause reference, the compliance verdicts with their full
reasoning, the scale section drawings and the charts captured from each module.

Available in **English** and **Persian (RTL)** — the Persian version has translated
headings, quantity names and verdict badges, with numbers and formulas correctly isolated
for right-to-left layout.

## 9. Python API

The engine is importable and has no framework dependencies.

```python
from earthsys import ieee80, soil, reasoning

# fit a two-layer soil model to a Wenner traverse
m = soil.invert_two_layer([1, 2, 4, 6, 10, 16],
                          [320, 245, 182, 162, 168, 182], "wenner")
print(m["rho1"], m["rho2"], m["h"], m["rms_pct"])

# design a grid and ask why it failed
g = ieee80.GridGeometry(Lx=70, Ly=70, D=7, h=0.5, d=0.01)
r = reasoning.explain_ieee80(
        ieee80.design(rho=400, g=g, IG_kA=1.908,
                      rho_s=2500, hs=0.102, ts=0.5))
print(r["narrative"])
for c in r["checks"]:
    print(c["name"], c["passed"], c.get("verdict"))

# search for a compliant design
opt = ieee80.optimise(400, g, 1.908, 2500, 0.102, 0.5)
print(opt["best"]["strategy"], opt["best"]["D"])
```

Every JSON endpoint is also a plain function:

```python
from earthsys.api import dispatch
dispatch("/api/ieee80/design", {"rho": 400, "Lx": 70, "Ly": 70, "D": 7,
                                "IG_kA": 1.908, "rho_s": 2500, "hs": 0.102})
```

## 10. What it writes

```
projects/   *.json   saved projects (also Export/Import from the toolbar)
outputs/    *.html   generated reports
```

Both are git-ignored. Projects are plain JSON: inputs, tables and results, so they diff
cleanly and can be generated by script.

## 11. Theory and teaching material

| Document | For |
|---|---|
 the plots in the tutorial and the numbers in the software cannot drift apart. Rebuild the whole set — the
figures, the Word document and its table of contents — with:


`THEORY.md` is also rendered inside the application, on the **Theory & reference** page,
with a contents sidebar — so the software teaches while it is being used. It derives the
tolerable-voltage formulas from the foot-resistance model, the decrement factor from the
rms of the DC offset, the adiabatic conductor equation from the heat balance, and the
boundary-element self term from first principles, then checks each against the standard's
own published form.

## 12. Validation and tests

```bash
python -m unittest discover -s tests -v      # 183 checks
```

Against the worked example of **IEEE Std 80-2013 Annex B** (70 × 70 m grid, ρ = 400 Ω·m,
ρ_s = 2500 Ω·m, h_s = 0.102 m, t_s = 0.5 s, I_G = 1908 A):

| Quantity | Published | Earthing System |
|---|---|---|
| C_s | 0.74 | 0.743 |
| E_touch (70 kg) | 838.2 V | 840.5 V |
| E_step (70 kg) | 2686.6 V | 2696.1 V |
| R_g | 2.78 Ω | 2.776 Ω |
| GPR | 5304 V | 5296 V |
| n | 11 | 11.000 |
| K_m | 0.89 | 0.890 |
| K_i | 2.272 | 2.272 |
| E_m | 1002.1 V | 1001.6 V |

The boundary-element solver is checked against Dwight's closed forms for a vertical rod, a
horizontal conductor and a ring, and against Sverak for the grid. It settles a few percent
lower than the closed forms — the physically correct direction, because they assume uniform
leakage current while the solver enforces a single electrode potential. For the Annex B
grid the numerical corner-mesh touch voltage is **931 V** against the closed-form
**1002 V**, a 7 % difference between two methods that share no equations.

> During validation this cross-check caught a real error in a widely republished formula.
> Several references quote Dwight's horizontal-conductor resistance with the total length
> where the half-length belongs, which inflates the result by about 12 % for a 30 m tape.
> `docs/THEORY.md` §9.4 has the details.

### Changes in 1.2.0

Six defects found while writing the second edition of the tutorial
(*Earthing System Design — Theory and Practice*, Appendix D) are fixed; each has a
regression test in `tests/test_v12_fixes.py` that fails on 1.1.

1. **Equivalent resistivity for grids.** The automatic rule weighted the layers by burial
   depth and ignored the grid size (Annex B grid in 2 m of 400 Ω·m: −66 % over 1600 Ω·m).
   It now treats the grid as a disc on the two-layer earth; **Pull inputs** recomputes it
   for the grid entered. Conservative in all 48 cases checked against the numerical solver.
2. **Two-layer boundary elements.** Rod segments below the interface used the upper-layer
   Green's function (−2 % on R_g). All four two-layer functions are now used and conductors
   are split at the interface.
3. **Automatic resistance formula.** The switch from Sverak to Schwarz made rods appear to
   raise R_g. Automatic now applies Schwarz's rod factor to Sverak's grid value.
4. **Hollow-square rod factor.** λ now follows BS 7430 (4.51 for eight rods, not 3.45) and
   is computed from the layout for other counts and for the filled square.
5. **Bonded electrodes.** Module 6 now includes the mutual resistance between electrodes
   (optional separation field) instead of adding them like resistors in parallel.
6. **Soil fit quality.** Fits are graded, three-layer (H/K-type) curves are flagged, a poor
   fit asks for confirmation before it is pulled into the grid design, and the built-in
   example traverse is now a genuine two-layer site.

### Changes in 1.3.5

IEC 60364-5-54:2011+A1:2021 and BS EN 50522:2022; each has a regression test in
`tests/test_v135_book_consistency.py`.

1. **Buried-conductor minimum.** A bare conductor buried in soil is now treated as *not*
   protected against corrosion. Its floor is the larger of BS 7671 Table 54.1 (25 mm²
   copper, 50 mm² steel) and IEC 60364-5-54:2011 542.3.1 / Table 54.1 (25 mm² copper,
   50 mm² with a lightning protection system connected; hot-dip galvanized steel round
   wire 10 mm, 78.5 mm²). The default had been "corrosion protected" (16 mm²), and the
   sheath/no-sheath table had been attributed to IEC 60364-5-54, whose 2011 Table 54.1 is
   the earth-electrode table. Claiming a sheath for a bare conductor raises a warning.
2. **Design basis on the conductor page.** Choose *both standards* (the larger area, the
   default), *IEEE 80 only* (HV grid: the welded-joint saving is realised) or *IEC
   60364-5-54 only* (LV). The page and the report say which criterion governs.
3. **BS EN 50522:2022.** U_Tp now follows Table B.4 of the 2022 edition (725, 655, 525,
   225, 115, 95, 85, 85 V; the 2010 values were 716 … 85 V), and U_vTp follows Formula
   (A.3), U_vTp = U_Tp + I_B·R_F with I_B from Table B.1 (the 2010 method used
   I_B = U_Tp/Z_T). Annex B grid: U_Tp 225 V, U_vTp 1175 V.
4. **Thin surface layer.** The cross-check also gives U_vTp with R_F2 = 1.5·C_s·ρ_s, the
   conservative treatment of a finite layer (982 V for Annex B, which E_m = 1002 V
   exceeds).
5. **Labels.** The simplified PE rule is labelled IEC 60364-5-54 Table 54.2
   (BS 7671 Table 54.7); buried k factors cite Table A.54.6.
6. **Benchmarks.** The numerical solver is tested against IEEE 80-2013/Cor 1-2015
   Annex H Grids 1, 2, 3 and 6 (within 0.5 % of CDEGS for R_g and the corner-mesh touch
   voltage of Grids 1–3). The Annex B.5 two-layer example (IEEE 80: 1.353 Ω) is reproduced
   only with the rods stopped at the interface (1.355 Ω); with the full 9.144 m rods the
   solver gives 1.137 Ω, like the independent solver of the tutorial.

### Changes in 1.3.4

A regression test in `tests/test_v134_fixes.py`.

- **gG fuse operating currents checked against BS 7671:2018.** The 0.4 s currents for BS 88-2 fuses of 2-32 A and the 5 s currents for 20-100 A are now derived from BS 7671 Tables 41.2 and 41.4 (through the maximum measured Z_s of the IET On-Site Guide 2018, Table B3, times its divisor 1.25): I_a = 0.95 x 230 V / Z_s,max. Several old, indicative values were low (20 A at 0.4 s: 120 A instead of 134 A; 25 A: 155 instead of 175 A), which let a longer loop pass. Other ratings remain indicative and the result says so.
- **gG fuses for times shorter than 0.4 s** (e.g. 0.2 s in TT final circuits): the 0.4 s current was used unchanged, which is non-conservative. I_a is now scaled by √(0.4/t) (constant I²t), with a note to check the fuse's time–current curve.
- **Lightning earth termination verdict:** the recommended 10 Ω row decided the overall IEC 62305-3 verdict; it is now marked as a recommendation (5.4.1) and the verdict follows the l1 geometry and the down-conductor count.
- **EN 50522 cross-check label:** the IEEE 80 value 1000·k/√t_s is the body resistance alone; it was labelled "no surface layer"/"bare".
- **Neutral earthing recommendation:** high-resistance grounding was recommended whenever 3·I_C0 ≤ 10 A; IEEE 142 §1.4.3.1 limits the total earth-fault current, √(I_R² + 3I_C0²), so HRG is now recommended only up to about 7 A of charging current, with a caution when it is selected above the limit. The report printed the resistor current as the earth-fault current; it now prints both.
- **Foundation electrode volume:** the code called V the "enclosed earth volume" and the input help text the "concrete volume". R ≈ 0.2·ρ/∛V is the equal-volume hemisphere, so V is the volume inside the foundation's soil-contact faces (a solid pad's concrete volume, or plan area × depth below ground for a basement); the docstring, formula label and both help texts now say so, and DIN 18014 is no longer cited for the resistance.
- **IEEE 81 edition:** the soil page, report and standards list cite IEEE Std 81-2025 §7.3/§7.6 instead of IEEE Std 81-2012 clause 8. Formulas unchanged.
- **ENA EREC S34:** new engine functions `faultcurrent.split_factor_cable_s34` (cable split factor, S34 App. D.2) and `standards.epr_contour_distance_s34` (Formula P7); the plate formula label now names S34 Formula R2. Tests in `tests/test_refs_s34.py` reproduce S34's worked examples.
- **EN 50522 prospective touch voltage:** the grid result carried E_m/U_Tp, which divides a prospective voltage by a body voltage. It now gives U_vTp of BS EN 50522 Annex B (body impedance from IEC TS 60479-1 Table 1, 1000 Ω footwear, R_F2 = 1.5·ρ_s) and E_m/U_vTp, shown on the grid page and in the report (`standards.en50522_prospective_touch_limit`). Informational; the verdict stays IEEE 80.
- **IEEE 80 validity range:** besides the burial depth, the grid page now warns when the area is outside 6.25–10 000 m², the spacing outside 2.5–22.5 m, there are more than 40 meshes along a side, or the outline is irregular (IEEE Std 80-2013 §16.7). Tests in `tests/test_iec60479_ieee80_range.py`.
- **gG fuse data from BS 7671:2018+A2:2022:** I_a = 0.95·230/Z_s from Table 41.2(a) (0.4 s, 2–63 A) and Table 41.4(a) (5 s, 2–200 A). The previous On-Site Guide 2018 values differed by up to 3 %, and the indicative 40–63 A values at 0.4 s were up to 12 % low.
- **Signal reference grid:** `standards.srg_max_aperture` uses λ/20 (IEEE Std 1100-2005 §4.6.4) instead of λ/10.
- **TT labels:** the 30 mA row now reads "30 mA RCD satisfies R_A·IΔn ≤ 50 V" (§411.5.3); the 200 Ω advisory cites BS 7671 Table 41.5 Note 2.
- **Non-rectangular grids:** an L- or T-shaped grid was computed as its bounding rectangle (IEEE 80 Example B.4: E_m 24 % low). The true area, perimeter and conductor length are now entered (grid page, "Non-rectangular grid") and required; B.4 is reproduced within 0.5 %.
- **Perimeter rods** are placed at the four corners first, then shared among the sides.
- **Verdict banner:** advisory rows (GPR screening, lightning 10 Ω) show CHECK and no longer turn the banner red above a compliant result.
- **Pull inputs:** values are written as plain numbers; locale formatting (thousands separators, Persian digits) used to blank the field and fall back to 100 Ω·m and 1 kA. Blank required grid fields are now an error.
- **Validation:** every endpoint rejects zero/negative values and unknown choices with a plain message; the optimiser refuses a zero step; server file paths are no longer sent to the browser.
- **Fault page:** a true "enter 3I₀ directly" mode with its own X/R field.
- **Labels:** IEEE 80 Eq. (45)/(48) for conductor sizing; C_p marked as a growth margin not in IEEE 80-2013. Tests in `tests/test_v135_audit.py`.
- **TT electrode above 200 ohm:** an advisory row (it never fails the design) repeats the BS 7671 guidance that such a resistance may not be stable through dry and frozen seasons.

- **Two-layer numerical solver, deep images.** The image series stopped at 60 terms whatever K was.
  The deeper images are now added as a tabulated function of horizontal distance. R_g for a
  20 × 20 m grid on 100 Ω·m over 20 000 Ω·m (h = 1 m) moves from 41.5 Ω to 48.7 Ω (+17 %); for
  ρ₂/ρ₁ = 40 by +0.8 %; negligible below ρ₂/ρ₁ ≈ 10.
- **Joint temperature.** A joint type now only lowers T_m: min(joint, material). An exothermic weld
  used to put 1083 °C on aluminium and zinc-coated steel (areas 13 % and 27 % too small).
- **Purely reactive or resistive fault loops.** D_f (√3 and 1), κ and the thermal factor m use their
  limits instead of failing with a division by zero; a computed X/R of 0 is no longer replaced by 10.
- **Grid without a surface layer.** A failing design with ρ_s = 0 crashed while composing the remedies.
- **Auto-refine with rods.** The layout drawing and the form now show the added rods on the perimeter,
  where the optimiser placed them.
- **Report.** The conductor section prints the size the page selected (largest of IEEE 80, IEC
  adiabatic and Table 54.1), not the IEEE 80 area alone; system grounding prints the method name.
  The step-voltage explanation no longer attributes the 4:1 ratio to the body path.
- **TT with an MCB or fuse** now uses IEC 60364-4-41 §411.5.4, Z_s · I_a ≤ U₀ with
  Z_s = Z_e + Z_line + R_A; §411.5.3 (R_A · IΔn ≤ 50 V) is kept for RCDs. The old rule
  R_A · I_a ≤ 50 V was applied to every device.
- **U₀ ≤ 50 V**: no disconnection time is required (Table 41.1 starts at 50 V); the old code
  demanded 0.1 s (TN) / 0.04 s (TT).
- **Validation**: the numerical solver rejects ρ₁ ≤ 0, ρ₂ ≤ 0 or a zero layer thickness; strip and
  ring electrodes reject h = 0 with an explanation instead of a division-by-zero message.
- **IEEE 80 applicability**: warning when h is outside 0.25–2.5 m; the report's formula block
  shows the resistance formula actually used.
- **Numerical page, "Build from the IEEE 80 grid"**: rods spread over the area when the grid page
  says so, instead of always on the perimeter.

### Changes in 1.3.3

Checked against the full texts of **IEEE Std 80-2013 (+ Cor 1-2015)**, **BS 7430:2011+A1:2015**,
**EN 50522:2010**, **IEC 62305-1:2010** and **CIGRE TB 781**. Tests in `tests/test_v133_references.py`.

- **IEEE 80 material constants (Table 1)** were the 2000-edition values. Now the 2013 table:
  copper TCAP 3.4 (was 3.42; areas +0.3 %), and in particular **1020 steel** α_r 0.00377,
  K₀ 245, TCAP 3.8 — the old constants gave a steel conductor **13 % too small** at its fusing temperature
  (2 % at a 250 °C joint).
  Stainless-clad, zinc-coated and 304 stainless steel are updated the same way; the 17 %
  copper-clad rod is added; the aluminium grades (not in the 2013 table) are labelled as such.
- **Surface materials (Table 7)** rebuilt from the 2013 table, with its dry/wet values.
- **Equation numbers.** Formula strings, reports and METHODS cited the IEEE 80-2000 numbers.
  They now cite 2013 + Cor 1-2015: Sverak (57), Schwarz (58)–(61), Figure 24, D_f (84),
  I_G (69), K_m (86), K_i (94), K_s (99), E_s (97), L_M (95)/(96), L_S (98).
- **Split factor.** New `faultcurrent.split_factor_table_c1` — S_f from IEEE 80 Table C.1
  (reproduces the Annex C examples: 0.349, 0.247, 182 A) with a calculator in module 2.
  The quick-pick chips are now labelled as indicative values; they are not from IEEE 80.
- **BS 7430 group factor λ.** Rods in a line now use the formula of 9.5.4,
  λ = 2(1/2 + … + 1/n) (e.g. 2.167 for four rods, not 2.15); hollow square from Table 2,
  corrected (12 rods 5.46, 16 rods 6.14) and extended to 76 rods.

- **CIGRE TB 781 (frequency-dependent soil).** The Alipio–Visacro model was confirmed against the
  brochure (Eq. 3.10–3.11, 5.3–5.4). Added its conservative parameter sets, the impulse-impedance
  reduction of Table 4.1 and the relevance classes of Table 5.1 (module 7 now reports them), and
  the tower-footing expressions Eq. 4.1–4.4 (`earthsys.standards`). The note in module 7 no longer
  implies that the resistivity at 1/(4T) can stand in for ρ: at 1000 Ω·m it is 63 % of ρ, while the
  first-stroke impulse impedance falls only to 89 %.

Confirmed without change: EN 50522 Table B.3 (and R_F1 = 1000 Ω, R_F2 = 1.5ρ_s), IEC 62305-1
lightning-current parameters, IEEE 80 Annex B results.

### Changes in 1.3.2

Three corrections; each has a
regression test in `tests/test_v132_fixes.py`.

- **Schwarz coefficient k₂.** Curve A of IEEE 80 Figure 25 (grid at the surface) is
  k₂ = +0.15x + 5.50; earlier versions had −0.15x. For the Annex B grid with twenty rods the
  Schwarz resistance moves from 2.867 Ω to 2.844 Ω (R₁ from 2.908 to 2.884 Ω). The automatic
  formula (Sverak × Schwarz rod factor) changes by less than 0.1 %.
- **Finite MN in the Schlumberger inversion.** The forward model now uses the exact
  expression for the potential electrodes actually used, instead of the ideal gradient
  array. The ideal form is wrong by up to 3 % for MN = AB/10 and 11 % for MN = AB/5.
- **IEC k factors for buried conductors.** The initial and final temperatures shown beside
  the "buried" k factors (20 → 500 °C) did not belong to the values (they are the "normal
  conditions" 30 → 200 °C values of Table A.54.5); the k values, and so every area, are unchanged.
  Steel with PVC covering is now 52 (was 51), as tabulated.

Four corrections in the lightning modules against the text of **IEC 62305-3:2010**
(Edition 2.0):

- **l₁ (Figure 3), class II**: the line is l₁ = max(5, 0.02ρ − 11) m — 49 m at 3000 Ω·m, not 45 m.
  Class I (max(5, 0.03ρ − 10)) was already right. Both are now taken from the vector drawing.
- **Protective angle (Figure 1)**: the hand-digitised angles were up to 16° too generous (class I at
  10 m: 61° instead of 45°) and rose to 80° below 2 m. They are now read from the vector drawing
  (±0.3°) and held constant below 2 m. The rolling sphere, which governs, is unchanged.
- **k_c (Table 12)**: 0.44 for three or more down-conductors (was 0.55 for three).
- **Earth-electrode minimum dimensions (Table 7)**: updated to the 2010 edition.

One addition: module 1 now reports the **uncertainty of the fitted soil model** — one-standard-
deviation ranges of ρ₁, ρ₂ and h and the correlation of ρ₁ with h, from the linearised covariance
s²(JᵀJ)⁻¹ of the least-squares fit (tutorial §2.6). The help text for the external loop
impedance Z_e now says what to enter for a TT supply.

### Changes in 1.3.1

The software's name is written correctly everywhere a user sees it — the window title, the
application header, the loading screen, the design report, the server banner and the
documentation — as **Earthing System** (two words), matching the repository name. File
names, the `earthsys` package and the `"app": "EarthSystem"` tag inside saved project files
are unchanged, so existing projects and shortcuts keep working.

### Changes in 1.3.0

1. **New module `earthsys/standards.py`.** A registry of 34 standards, guides and CIGRE
   brochures (edition, status, area, and whether Earthing System *implements*, *cross-checks* or
   only *references* each), plus small calculations taken from them:
   BS EN 50522 permissible touch voltage U_Tp(t_F); the ENA EG-0 coincidence probability
   and risk bands; the CIGRE TB 781 (Alipio–Visacro) frequency-dependent soil; the far-field
   EPR contour used for telecom and pipeline hazard zones (AS/NZS 3835.1, EREC S34,
   AS/NZS 4853); Carson's mutual impedance for inductive coupling (CIGRE TB 95); the
   thermal limit and anodic mass loss of an HVDC electrode (EPRI EL-2020); and the
   aperture of a mesh bonding network (IEEE 1100, BS EN 50310).
2. **Module 4** reports the BS EN 50522 U_Tp beside the IEEE 80 limits, and the IEEE 80
   bare-soil value that is its like-for-like comparison.
3. **Module 7** reports the soil resistivity at the representative frequency of the
   lightning front (CIGRE TB 781).
4. **Report** gains a *Standards and codes of practice* table listing the standards relevant
   to the modules that were run (English and Persian).
5. **API** gains `/api/standards`; `/api/meta` returns the registry.
6. Tests: `tests/test_v13_standards.py` (18 tests).

## 13. Running it online

The same interface runs with no server. `web/boot.js` probes for `/api/health`; if there is
no server it loads Pyodide, fetches the `earthsys` package sources, and patches `fetch` so
that every `/api/...` call goes to the identical Python code inside the browser. `app.js`
never learns which mode it is in, and the numbers are bit-for-bit the same.

To publish your own copy, follow [`PUBLISH.md`](PUBLISH.md) — it has the exact commands.
In short: push the repository, and the workflow in `.github/workflows/pages.yml` deploys it
on every push to `main` (Settings → Pages → Source: **GitHub Actions**). The root
`index.html` forwards to `web/`.

> With *Source: GitHub Actions* selected, GitHub deploys nothing until a workflow exists —
> that file is what does it. *Deploy from a branch* → `main` → `/ (root)` also works;
> `.nojekyll` is included for that case.

First load fetches about 20 MB (Pyodide plus numpy) and is then cached. Save/Open to disk
are hidden in browser mode; Export/Import JSON still work.

## 14. Limitations

- The closed-form IEEE 80 equations assume uniform soil, a rectangular grid and uniform
  current leakage. The shape selector is recorded with the design but does not change the
  arithmetic: an L or T grid is computed as the rectangle that bounds it, which is the
  conservative direction for Rg and the optimistic one for the mesh voltage. For a
  genuinely irregular outline, use the numerical solver, which takes the real geometry.
- The numerical solver assumes a horizontally layered earth, power-frequency behaviour and
  perfectly bonded metal. It does **not** model soil ionisation or solve the electrode as a
  transmission line. The effective length and effective area of module 7 do address the
  impulse behaviour, but by published closed-form estimates, not by a transient solution.
- Two-layer soil only. Three-layer sites are fitted as two layers; the fit-quality grade
  and the residual column tell you when that is not good enough.
- Transferred potentials, fence bonding and cable-sheath currents are not modelled — they
  are handled by the standards' rules rather than by a formula.
- Fuse operating currents are indicative values; use the manufacturer's curves for a real
  design.
- See [`DISCLAIMER.md`](DISCLAIMER.md).

## 15. Troubleshooting

**A launcher window flashes and disappears.** Run `Diagnose.bat` — it prints and saves
`diagnostic.txt` listing every Python it can find. The launchers also write
`startup_log.txt` on every run.

**"Python was not found".** Install Python 3.9+ from python.org and tick *Add python.exe to
PATH*. The launchers also search the usual Anaconda, Miniconda and per-user install
locations.

**Security software blocks the .bat files.** Use `python START_EarthSystem.py` instead.

**"numpy missing — numerical solver off".** `pip install numpy`. Everything except module 5
works without it.

**The numerical solver is slow.** Cost grows as N². Increase the segment length or reduce
the surface-grid resolution; 3 m segments and 61 × 61 points solve a 70 × 70 m grid in
under a second.

**The soil fit has a large RMS error.** The site is probably not two layers, or there is
buried metal crossing the traverse. Run a perpendicular traverse and compare.

## 16. Contributing

Issues and pull requests are welcome. Useful directions:

- three-layer soil inversion
- transferred potential and fence-bonding checks
- frequency-domain electrode response for lightning
- more languages for the report generator
- worked examples from other standards for the validation suite

Keep the engine dependency-light — numpy is the only hard requirement, and it should stay
that way.

## 17. Licence and references

GNU General Public License, version 3 or later — see [`LICENSE`](LICENSE).

    Earthing System — earthing system design to IEEE 80, IEC 60364, IEC 62305 and IEEE 142.
    Copyright (C) 2026 Emad Roshandel

    This program is free software: you can redistribute it and/or modify it under the
    terms of the GNU General Public License as published by the Free Software
    Foundation, either version 3 of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful, but WITHOUT ANY
    WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
    PARTICULAR PURPOSE. See the GNU General Public License for more details.

In practice this means you may use, study, modify and redistribute the program freely,
including commercially, but anything you distribute that is derived from it must also be
released under the GPL with its source. Running it in-house — including for paid
consultancy work — carries no obligation to publish anything.

Third-party components in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md); the bundled
Plotly.js remains under its own MIT licence, which is compatible with the GPL.

This software implements methods published in the standards below and reproduces the
numerical constants they require, each cited to its clause. It does not reproduce their
text, figures or commentary, and it is not a substitute for them. No endorsement by any
standards body is claimed.

**Standards implemented** (the calculations follow these editions)

1. IEEE Std 80-2013, *IEEE Guide for Safety in AC Substation Grounding* (incl. Cor 1-2015)
2. IEEE Std 81-2025, *IEEE Guide for Measuring Earth Resistivity, Ground Impedance, and Earth Surface Potentials of a Grounding System* (revision of IEEE Std 81-2012)
3. IEEE Std 142-2007, *IEEE Recommended Practice for Grounding of Industrial and Commercial Power Systems* (Green Book)
4. IEEE Std C62.92 series, *IEEE Guide for the Application of Neutral Grounding in Electrical Utility Systems*
5. IEC 60364-4-41:2005+A1:2017, *Low-voltage electrical installations — Protection against electric shock*
6. IEC 60364-5-54:2011+A1:2021, *Earthing arrangements and protective conductors*
7. IEC 60909-0:2016, *Short-circuit currents in three-phase a.c. systems — Calculation of currents*
8. IEC 62305-1 and IEC 62305-3:2010, *Protection against lightning* (edition 3 of Part 3 published 2024)
9. BS 7430:2011+A1:2015, *Code of practice for protective earthing of electrical installations* (λ tables; replaced by BS 7430:2026)

**Standards cross-checked or referenced** (`earthsys/standards.py`)

*Substation earthing*

10. AS 2067:2016, *Substations and high voltage installations exceeding 1 kV a.c.*
11. BS EN 50522:2022+A1:2024, *Earthing of power installations exceeding 1 kV a.c.*
12. IEC 61936-1:2021, *Power installations exceeding 1 kV AC and 1.5 kV DC — Part 1: AC*
13. ENA DOC 045-2022, *Substation Earthing Guide* (EG-1), Energy Networks Australia

*Testing*

14. ENA TS 41-24 Issue 2 (2018), *Guidelines for the design, installation, testing and maintenance of main earthing systems in substations*, Energy Networks Association (UK)

*Touch and step voltage*

15. IEC 60479-1:2018, *Effects of current on human beings and livestock — Part 1: General aspects* (replaces IEC TS 60479-1:2005+A1:2016); IEC 60479-2:2019, *Part 2: Special aspects*
16. ENA DOC 025-2022, *Power System Earthing Guide — Part 1: Management Principles* (EG-0), Energy Networks Australia

*Renewable generation*

17. IEC 61400-24:2019+AMD1:2024, *Wind energy generation systems — Part 24: Lightning protection* (turbine earthing, built on IEC 62305-3)
18. IEEE Std 2760-2020, *IEEE Guide for Wind Power Plant Grounding System Design for Personnel Safety*
19. IEEE Std 2778-2020, *IEEE Guide for Solar Power Plant Grounding for Personnel Protection*

*Metallic pipelines*

20. AS/NZS 4853:2012, *Electrical hazards on metallic pipelines*
21. CIGRE TB 95 (1995), *Guide on the influence of high voltage AC power systems on metallic pipelines*

*Industrial and commercial installations*

22. AS/NZS 3000:2018, *Electrical installations* (Wiring Rules), with Amendments 1–3
23. BS 7671:2018+A4:2026, *Requirements for Electrical Installations* (IET Wiring Regulations, 18th Edition)

*Overhead lines*

24. AS/NZS 7000:2016, *Overhead line design*
25. CIGRE TB 781 (2019), *Impact of soil-parameter frequency dependence on the response of grounding electrodes and on the lightning performance of electrical systems*
26. CIGRE TB 839 (2021), *Procedures for estimating the lightning performance of transmission lines — new aspects*
27. IEEE Std 1243-1997, *IEEE Guide for Improving the Lightning Performance of Transmission Lines*

*HVDC*

28. EPRI EL-2020 (1981), *HVDC Ground Electrode Design*, Electric Power Research Institute

*Data centres*

29. IEC 60364-5-548:1996, *Earthing arrangements and equipotential bonding for information technology installations* (withdrawn 2002; content now in IEC 60364-5-54 and IEC 60364-4-44)
30. IEEE Std 1100-2005, *IEEE Recommended Practice for Powering and Grounding Electronic Equipment* (Emerald Book; inactive-reserved since 2021)

*Telecommunications*

31. AS/NZS 3835.1:2006, *Earth potential rise — Protection of telecommunications network users, personnel and plant — Code of practice*
32. BS EN 50310:2016+A1:2020, *Telecommunications bonding networks for buildings and other structures*

*Fault-current distribution*

33. ENA EREC S34 Issue 2 (2018), *A guide for assessing the rise of earth potential at electrical installations*, Energy Networks Association (UK)
34. CIGRE TB 347 (2008), *Earth potential rises in specially bonded screen systems*

**Papers and books**

35. H. B. Dwight, "Calculation of resistances to ground", *Trans. AIEE*, 55, 1936
36. E. D. Sunde, *Earth Conduction Effects in Transmission Systems*, Van Nostrand, 1949
37. J. R. Carson, "Wave propagation in overhead wires with ground return", *Bell Syst. Tech. J.*, 5, 1926
38. S. J. Schwarz, "Analytical expressions for resistance of grounding systems", *Trans. AIEE*, 73, 1954
39. C. F. Dalziel, "Threshold 60-cycle fibrillating currents", *Trans. AIEE*, 79, 1960
40. F. Dawalibi and D. Mukhedkar, "Optimum design of substation grounding in two-layer earth", *IEEE Trans. PAS*, 94, 1975
41. J. G. Sverak, "Sizing of ground conductors against fusing", *IEEE Trans. PAS*, 100, 1981
42. R. Alipio and S. Visacro, "Modeling the frequency dependence of electrical parameters of soil", *IEEE Trans. Electromagnetic Compatibility*, 56(5), 2014
