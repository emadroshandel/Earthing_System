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
git clone https://github.com/emadroshandel/earthsystem.git
cd earthsystem
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
| 1 | Soil model | IEEE Std 81-2012 §8 | Wenner / Schlumberger reduction, two-layer inversion (ρ₁, ρ₂, h, K) by Nelder–Mead, equivalent uniform ρ |
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

`THEORY.md` is rendered inside the application, on the **Theory & reference** page,
with a contents sidebar — so the software teaches while it is being used. It derives the
tolerable-voltage formulas from the foot-resistance model, the decrement factor from the
rms of the DC offset, the adiabatic conductor equation from the heat balance, and the
boundary-element self term from first principles, then checks each against the standard's
own published form.

## 12. Validation and tests

```bash
python -m unittest discover -s tests -v      # 139 checks
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

### Changes in 1.3.0

The software and its tutorial now cite, and where it is meaningful cross-check against, the
wider set of earthing standards listed in §17. Nothing here changes a pass/fail verdict: the
verdicts remain those of IEEE 80, IEC 60364, IEC 62305 and IEEE 142.

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

## 13. Limitations

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

## 14. Troubleshooting

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

## 15. Contributing

Issues and pull requests are welcome. Useful directions:

- three-layer soil inversion
- transferred potential and fence-bonding checks
- frequency-domain electrode response for lightning
- more languages for the report generator
- worked examples from other standards for the validation suite

Keep the engine dependency-light — numpy is the only hard requirement, and it should stay
that way.

## 16. Licence and references

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
2. IEEE Std 81-2012, *IEEE Guide for Measuring Earth Resistivity, Ground Impedance, and Earth Surface Potentials of a Grounding System* (superseded by IEEE Std 81-2025)
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
