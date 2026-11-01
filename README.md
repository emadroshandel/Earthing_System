# Earthing System

**Earthing (grounding) system design for homes, buildings, substations and power plants.**

Implements IEEE Std 80-2013, IEC 60364-4-41 / -5-54, IEC 62305-2/-3/-4:2024, IEC 60909-0 and
IEEE Std 142, adds a boundary-element numerical solver for arbitrary electrode geometry in
uniform or layered soil (up to four layers) or two soils across a vertical boundary — sized
for power-plant grids of tens of thousands of segments — with fences and other separate metal,
concrete foundations, transferred potential along pipes, rails and cable screens, and the
frequency-domain lightning response of any electrode — explains *why* every compliance
criterion passed or failed, and produces a printable design report in English or Persian.
Version 1.8 states how accurate the numerical answer is (refinement at conductor ends and a
convergence check), drops the equipotential assumption for large grids, carries the soil
model's uncertainty and its seasonal changes through to the touch and step voltages,
optimises the grid, plans and interprets the fall-of-potential test, solves the shield-wire
ladder for the split factor along the line, and adds the IEC 62305-2:2024 risk management
(risk R and frequency of damage F, zone by zone) and IEC 62305-4:2024 surge protection. Version 1.3 places the design in
the wider standards landscape: BS EN 50522, ENA EG-0/EG-1 and AS 2067 touch-voltage criteria,
CIGRE TB 781 frequency-dependent soil, and the codes for renewables, pipelines, HVDC
electrodes, data centres, telecommunications and fault-current distribution
(`earthsys/standards.py`, §17).

Runs three ways from the same code: a local desktop window, a local browser application, or
entirely inside your browser with no installation at all.

**▶ Live demo — no installation:** https://emadroshandel.github.io/Earthing_System/

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/validation-546%20tests-brightgreen.svg)](#11-validation-and-tests)

---

## Contents

1. [Why this exists](#1-why-this-exists)
2. [Install](#2-install)
3. [Quick start](#3-quick-start)
4. [The interface](#4-the-interface)
5. [The eleven modules](#5-the-eleven-modules)
6. [Why it passed or failed](#6-why-it-passed-or-failed)
7. [The numerical solver](#7-the-numerical-solver)
8. [Reports](#8-reports)
9. [Python API](#9-python-api)
10. [Theory and teaching material](#10-theory-and-teaching-material)
11. [Validation and tests](#11-validation-and-tests)
12. [Running it online](#12-running-it-online)
13. [Limitations](#13-limitations)
14. [Troubleshooting](#14-troubleshooting)
15. [Contributing](#15-contributing)
16. [Licence and references](#16-licence-and-references)

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
small enough to read. The calculation engine is about 13 000 lines of dependency-light
Python, every module documented with the equations it implements.

## 2. Install

**Requirements:** Python 3.9 or newer. `numpy` is needed only for the numerical solver
(module 5, including the transferred potential and the lightning response), the three- and
four-layer soil fits and the earth-pit card.
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
Inputs           1  Soil model          field data → two-, three- or four-layer earth
                 2  Fault current       IEC 60909 → I_G
                 3  Conductor sizing    thermal sizing, PE and bonding

Design modules   4  Substation grid     the full IEEE 80 procedure
                 5  Numerical solver    boundary-element method, fences, transferred
                                        potential, lightning response
                 6  Buildings & homes   IEC 60364, TN / TT / IT
                 7  Lightning earth     IEC 62305-3, earth termination
                 8  Air termination     IEC 62305-3, rolling sphere zone
                 9  System grounding    IEEE 142, neutral earthing

Output          10  Design report       English or Persian, printable
                11  Construction        drawing set: PDF, DXF, SVG,
                    drawings            bill of materials
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

A green tick or a red exclamation mark on each nav item shows whether that module has been run and whether it
complied.

The **Geometry** tab of the numerical solver shows the solved electrodes in 3-D (three.js,
bundled for offline use): every segment coloured by its leakage current density, the
earth-surface potential as a translucent sheet above them, and markers at the worst touch
and step locations. Depth is drawn exaggerated (adjustable) because a grid is tens of
metres wide and half a metre deep. Hover a conductor or the surface to read its values;
**Plan** and **Elevation** snap the camera. Without WebGL the tab falls back to the
Plotly wireframe.

### Accessibility

The interface is built to WCAG 2.2 AA and checked with an automated Playwright audit over
every page at desktop and phone widths, in both themes:

- everything works from the keyboard — a skip link, real buttons for the menu, tabs and
  chips, arrow keys inside tab strips, a focus ring on every control, and dialogs that
  keep focus inside and return it on Escape;
- every input is announced with its label, unit and **?** explanation;
- text meets 4.5:1 contrast in the light and the dark theme, and status is never shown
  by colour alone;
- each chart carries a text summary for screen readers and a **Data table** you can open
  beneath it, and the series colours (Okabe–Ito) stay distinct with colour blindness;
- below 820 px the menu folds into a drawer and nothing scrolls sideways;
- animations stop when the system asks for reduced motion.

## 5. The eleven modules

| # | Module | Standard | What it computes |
|---|---|---|---|
| 1 | Soil model | IEEE Std 81-2025 §7.3, §7.6 | Wenner / Schlumberger reduction, two-layer inversion (ρ₁, ρ₂, h, K) by Nelder–Mead, three- and four-layer inversion by Levenberg–Marquardt with an F test of each added layer and the middle layers' equivalence, a robust refit that sets aside readings inconsistent with the rest, a separate fit of each traverse with a lateral-variation check, equivalent uniform ρ and equivalent two-layer model for any number of layers |
| 2 | Fault current | IEC 60909-0, IEEE 80 §15, Annex C | Iₖ₁″, Iₖ″, iₚ, I_th, decrement factor D_f, split factor S_f (Table C.1, or the shield-wire and tower-footing ladder solved with the phase-to-shield-wire coupling — unequal spans, measured footing resistances and the other outgoing lines' ladders in parallel), the grid current for a fault anywhere along an outgoing line, the earth-fault current returning in cable sheaths (bonded at both ends, at joints or at one end), maximum grid current I_G |
| 3 | Conductor sizing | IEEE 80 Eq. (37), IEC 60364-5-54 | Minimum area by both methods, joint temperature limits, PE and bonding sizes, minimum buried sizes |
| 4 | Substation grid | IEEE Std 80-2013 | Tolerable touch/step voltages, R_g by Sverak **and** Schwarz, GPR, E_m, E_s, and an auto-refinement search |
| 5 | Numerical solver | Boundary-element method; IEEE 80 §17.3; IEEE 81 §8; electromagnetic model | Arbitrary geometry — wires, rods, rings, plates — in uniform or layered soil (up to four layers), typed in or imported from a DXF site drawing; surface potential field, touch/step maps (touch zones where equipment stands), per-segment leakage current; refinement at conductor ends, automatic refinement at the worst points and a convergence check; governing values that take the worst of the solution and every study as the verdict; a non-equipotential solution with the conductors' own impedance, fences included, solved in two scales for large plants; seasonal and Monte Carlo (Latin hypercube) soil studies with confidence intervals; grid optimisation with unequal spacing; fall-of-potential test planning and interpretation; fences and other separate metal (bonded or floating) with their own touch voltages; concrete piers and strip footings; transferred potential along straight or bent routes (bare and coated conductors solved with the station), with induction from a faulted line on any route (parallel, oblique or crossing); harmonic impedance and lightning potential rise, with layered soil, soil ionisation and frequency-dependent soil |
| 6 | Buildings & homes | IEC 60364-4-41 / -5-54, BS 7430, IEC 60269 | Electrode resistances, R_A, Z_s, disconnection time, RCD selection, TN / TT / IT; fuses from BS 7671's tables, the IEC 60269 gates (gG, gM, aM, the fuse systems of Parts 2 and 3) or the manufacturer's time–current curve, with the operating time at the fault current; earth pits (backfilled electrodes, solved numerically) |
| 7 | Lightning earth | IEC 62305-2, -3, -4 (2024) | Risk R = R_L1 + R_L2 and frequency of damage F of internal systems, zone by zone, with incoming lines in sections; the least LPS class, entrance bonding SPDs and coordinated SPDs that meet R_T and F_T; SPD current share, lead drop 0.1·I_SPD per metre, the protection rules of IEC 62305-4:2024 Annex C and the simplified I_imp per protection mode; LPS class data, l₁, Type A / Type B termination, down-conductors, separation distance s, and the behaviour under the impulse: effective length L_eff = k(ρT)^0.5, effective area of a meshed system by three published expressions, centre versus corner injection, and the impulse coefficient A = Z/R that says by how much a measured resistance understates the potential rise |
| 8 | Air termination | IEC 62305-3 Annex A | Rolling sphere rolled numerically over the structure, protected radius r_p, sphere penetration between terminations, maximum span, roof-field and roof-edge checks, plan coverage, protective angle and mesh methods |
| 9 | System grounding | IEEE 142, IEEE C62.92 | Method selection, NER sizing, charging current, effectively-grounded test |
| 10 | Design report | — | One printable HTML document, English or Persian (RTL), drawings and charts embedded |
| 11 | Construction drawings | IEC 61082-1, IEC 60617, ISO 5457, ISO 7200, ISO 129-1, ISO 5455; IEEE 80, IEEE 837, BS EN 50522, IEC 60364-5-54, IEC 62305-3, IEC 62561-1/-2/-5/-7, BS 7430, BS 7671 | Drawing register and general notes, earth-grid layout plan with rod schedule, typical sections, earth pit and test link, main earthing terminal, connection details, equipment bonding details, conductor selection chart, lightning earth termination, earthing schematics and bill of materials; a design-rule verification of every installation rule shown; vector PDF, one DXF (R12) per sheet and SVG |

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

How the answer is made reliable (1.8):

- **The worst touch and step voltage are searched for, not sampled.** Both are located on the
  plot grid and along a ring just outside the electrodes, then refined in position — and the
  step in direction — to 0.02 m and 1°, so the result does not change with the plot
  resolution. The touch voltage counts only where a person can reach earthed metal (within
  1 m of buried metal or inside a mesh), or only in the *touch zones* you give.
- **Refinement at conductor ends.** The leakage current crowds towards the free end of every
  conductor; halving the end segments three times gives, with 3 m segments, the corner touch
  voltage of a uniform 0.5 m mesh at a quarter of the unknowns.
- **A convergence check** solves again with the segments halved and estimates the converged
  value; the verdict uses the larger.
- **Automatic refinement (1.8.8)** halves the segments round the worst touch and step points
  until both change by less than a stated tolerance, and reports each level.
- **Governing values.** The verdict of the page, the report's compliance table and the drawing
  stamp use, for each quantity, the largest value from the solution and from every study run
  on the same electrodes, soil and current — convergence, seasonal soil, the 95th percentile
  of the soil uncertainty and the non-equipotential solution — and name the study it came
  from. A study left over from an earlier model is listed as out of date and ignored.

What else the numerical page does:

- **Non-equipotential solution.** The conductors' own impedance at 50 or 60 Hz, with one or
  more injection points: a 300 m copper grid in 30 Ω·m soil has |Z| 33 % above the
  equipotential R_g, and its far corner sits at 70 % of the feed-point potential.
- **Soil uncertainty and seasons.** Soil models drawn from the fit's covariance by Latin
  hypercube sampling give the spread of R_g, touch and step voltage and the probability of
  meeting the limits, with its 95 % confidence interval and the number of samples that would
  narrow it to ±5 %; dry and frozen top layers give the seasonal worst case.
- **Grid optimisation.** The cheapest grid that meets the limits, searched with the solver
  over the number of conductors, unequal spacing drawn towards the edges, and perimeter rods.
- **Fall-of-potential test.** The test curve for the real electrode and soil: how far out the
  current electrode must go, where the probe must stand, and — with the readings — the
  resistance they imply and whether the soil model's shape agrees.

- **Large grids (1.8.7).** Mirror and rotation symmetries are found and the system reduced
  by them exactly (a square grid with perimeter rods: an eighth of the unknowns); above
  4000 unknowns the matrix is stored compressed (an H-matrix built by adaptive cross
  approximation) and solved by preconditioned GMRES, so the segment limit is 20 000. On the
  Annex B grid at 0.125 m segments (13 520 unknowns) R_g agrees with the dense solution to
  4 × 10⁻¹¹ and the touch voltage to 5 × 10⁻⁹. Solutions are kept and reused: the same model
  with another current, and in uniform soil with another resistivity, costs nothing, and the
  studies share their cases.
- **Two soils side by side (1.8.7).** ρ₁ on one side of a vertical boundary — a fault, a rock
  face, the edge of a lake or a backfilled area — and ρ′ on the other, solved exactly with
  images in the boundary. An electrode in the boundary sees the harmonic mean
  2ρ₁ρ′/(ρ₁ + ρ′), which the solver reproduces to 10⁻¹².
- **Layered soil, up to four layers.** The Green's function is built by tracing reflections
  between the planes, with the far images taken from the spectral solution; every conductor
  is split at every interface. Checked against an independent spectral computation
  (3.5 × 10⁻¹⁰) and an axisymmetric finite-volume solution for rods crossing both
  interfaces (0.13 %).
- **Separate metal.** A fence, bonded or isolated, or any other floating metal is held at its
  own potential; the solver returns the mutual-resistance matrix, the fence potential, its
  touch voltages inside and outside, and the grid-to-fence transfer voltage. IEEE 80 Annex H
  Grids 4 and 5 are reproduced within 1.5 % and 2.5 % of the reference programs.
- **Concrete foundations.** *Pier / pile* and *Strip footing* elements: the bar cage in a
  concrete shell of the given resistivity (Fagan and Lee's table within 3 %).
- **Plates.** Horizontal or vertical rectangular plates — earth plates, or a raft's
  reinforcement as one sheet — cut into edge-graded strips; within 0.3 % of an exact plate
  solution, always slightly high (1.9.0).
- **Transferred potential.** A bare or coated pipe or wire leaving the station is solved
  together with the grid (1.8.8): its segments leak into the same soil, so the current it
  draws, the GPR and the soil beside the route all include its own leakage — within 1–3 % of
  the full circuit-field solution. An insulated cable screen or a rail is solved as a lossy
  line driven by the station's soil potential. The route may bend, and a faulted line on any
  route induces its voltage along it.
- **Lightning response.** The same electrodes solved as thin wires in the frequency domain:
  harmonic impedance, potential rise under first and subsequent strokes (CIGRE TB 781 or
  Heidler currents), impulse impedance and coefficient; constant or frequency-dependent soil,
  uniform or layered (exact Sommerfeld solution), with optional soil ionisation.

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

# fit three layers and test whether the third is supported
from earthsys import layered
a = [1, 3, 6, 8, 10, 15, 20, 40, 60]
r = [138, 79, 71, 67, 80, 88, 99, 151, 170]
sel = layered.select_three(a, r, soil.invert_two_layer(a, r, "wenner"))
print(sel["chosen"], sel["three"]["rho"], sel["three"]["h"], sel["p_value"])

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

```python
# lightning response of a 10 m rod in two-layer soil, with ionisation
from earthsys import hf
d = hf.analyse([{"kind": "rod", "x": 0, "y": 0, "top_depth": 0, "length": 10, "radius": 0.008}],
               rho0=300, layers={"rho": [60], "h": [2.0]}, E0=400,
               waveforms=("first_heidler", "subsequent_heidler"))
print(d["R"], d["responses"]["first_heidler"]["Z_impulse_ion"])
```

Every JSON endpoint is also a plain function:

```python
from earthsys.api import dispatch
dispatch("/api/ieee80/design", {"rho": 400, "Lx": 70, "Ly": 70, "D": 7,
                                "IG_kA": 1.908, "rho_s": 2500, "hs": 0.102})
```

## 10. Theory and teaching material

| Document | For |
|---|---|
| [`docs/THEORY.md`](docs/THEORY.md) | The physics and mathematics behind every page — derivations, worked examples, 21 figures, and a suggested teaching sequence |
| [`docs/METHODS.md`](docs/METHODS.md) | The condensed equation reference, every formula with its clause number or source |

Every figure in `docs/figures` is generated from the engine itself by `docs/make_figures.py`, so
the plots in the theory and the numbers in the software cannot drift apart. Rebuild the whole
set — the figures, the Word document and its table of contents — with:

```bash
bash docs/build_docx.sh
```

`THEORY.md` is also rendered inside the application, on the **Theory & reference** page,
with a contents sidebar — so the software teaches while it is being used. It derives the
tolerable-voltage formulas from the foot-resistance model, the decrement factor from the
rms of the DC offset, the adiabatic conductor equation from the heat balance, and the
boundary-element self term from first principles, then checks each against the standard's
own published form; since 1.6.0 it also covers three- and four-layer soil, fences,
transferred potential, earth pits, concrete foundations and the computed lightning response;
since 1.8.0, robust soil fitting, the shield-wire ladder, the search for the worst touch and
step voltage, the discretisation error, the non-equipotential solution, soil uncertainty,
grid optimisation, the fall-of-potential test, induction, and IEC 62305-2 and -4.

## 11. Validation and tests

```bash
python -m unittest discover -s tests -v      # 546 tests
python -m pytest tests                       # the same suite; pytest lists 553 items
python audit.py                              # 54 independent re-derivations of the formulas
```

The suite reproduces published results wherever they exist. Besides IEEE 80 Annex B below:
IEEE 80 Annex H Grids 1–6 (against CDEGS, ETAP and WinIGS), BS 7430 and EREC S34 worked
examples, IEC 62305-3 figures read from the vector drawings, three- and four-layer soil
traverses of Gonos and Stathopulos, Zhang et al. and Slaoui and Erchiqui, CIGRE TB 781 (a
measured rod and Table 4.1), Grcev (2009) with and without ionisation, Alipio and Visacro
(2014), the exact two-layer results of Arnautovski-Toseva et al. (2007), and Fagan and Lee's
concrete-encased rods (1970).

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

### Changes in 1.10.0

1. **Accessibility pass to WCAG 2.2 AA** (`web/a11y.js`, `web/styles.css`, `web/index.html`). Landmarks
   and a skip link; the side menu, tabs, chips and the verdict-row toggles are real buttons with
   their ARIA states; every one of the ~400 form fields is tied to its label, unit and explanation;
   muted text darkened to 4.5:1 and the dark theme's text on the accent colour fixed (it was 2.3:1);
   visible focus rings; error toasts are announced; dialogs trap and return focus; reduced motion
   is respected. A measured Playwright audit went from 87 contrast failures, 407 unlabelled inputs
   and 165 keyboard-unreachable controls to none (disabled buttons excepted, as WCAG allows).
2. **Phone layout.** Below 820 px the menu becomes a drawer and the forms reflow; no page scrolls
   sideways at 390 px (all twelve did).
3. **Charts.** Okabe–Ito series colours that survive colour blindness and clear 3:1 on both
   themes; every Plotly chart gets a screen-reader summary of each series and an openable data table.
4. **3-D electrode view** (`web/grid3d.js`, three.js 0.182.0 vendored). The numerical solver's
   Geometry tab draws the segments as one instanced mesh coloured by leakage current density
   under the surface-potential sheet, with the worst touch and step points marked, hover read-outs
   and keyboard orbiting. Renders on demand and frees its GPU buffers on every re-solve.
5. **Server.** `.js` is served as `text/javascript` whatever the Windows registry says, which ES
   modules require.

### Changes in 1.9.5

1. **Binary DXF** (`dxfimport`, the DXF card of the numerical page). A drawing saved as binary
   DXF is now read as well as an ASCII one, any release from R12 (one-byte group codes) to the
   current one (two-byte codes); strings are decoded as UTF-8 from AutoCAD 2007 on and in the
   drawing's code page (`$DWGCODEPAGE`) before, and names written as `\U+XXXX` escapes are shown
   as their characters. The page sends a binary file as base64; a DWG is recognised and refused
   with a message. Checks: drawings written by another program (ezdxf) in R12, R2000 and R2018,
   each both ways, give the same entities, layers and electrode items from the binary file as
   from the ASCII one, and coordinates are read bit for bit.
2. **Damage to the surroundings, IEC 62305-2:2024 Annex E** (`risk.surroundings_losses`, the
   risk page). A zone where a strike can harm people or property outside the structure
   (explosion, thermal flux, toxic fumes, soil or water pollution, radioactive material) gets
   the components R_B1E … R_Z2E of Table E.1, with the losses of Tables E.3 (inside the site
   fence or spreading beyond it) and E.4 and the presence of people t_zE/8760 of Table E.2 (1
   when not known). They are added to R_L1 and R_L2 of the zone and shown separately; F is
   unchanged. The surge components (C, M, W, Z) count only when a failure of internal systems
   can cause the damage, as the annex asks. Checks: with the surroundings' losses and presence
   set to the zone's own, all twelve components equal their Table 3 counterparts (which
   reproduce Annex F); with fire and explosion only, the result equals adding L_E to L_F1 and
   L_F2 by (C.1) and (C.2); and the components against a hand calculation. The annex has no
   worked example of its own.

### Changes in 1.9.4

1. **Cross-bonded cable sheaths** (`faultcurrent.cable_sheath_crossbonded`, bonding
   "cross_bonded" on the cable-sheath page). The minor sections are entered one by one, three
   to a major section. Each sheath of each minor section is its own conductor, coupled to the
   other sheaths and to the faulted core by Carson's formulas; at every link box the sheath of
   position p continues as the sheath of the next position, and the sheaths are earthed at A,
   at B and at the major joints. The link boxes are open (their voltage limiters not
   conducting) and the cores are not transposed. Besides the split factor the page gives the
   largest current in one sheath and, at every link box, the sheath voltage to remote earth and
   across the sectionalising joint, which the voltage limiters must withstand. Checks: with
   equal minor sections the result equals the both-ends model with earths at the major joints
   to 10⁻¹² (every sheath path then visits each position once); against an independent
   solution written path by path, with unequal sections, flat and trefoil, one and two circuits,
   to 10⁻¹⁰. 3 km, six 0.5 km minor sections, I_f = 10 kA, R_A = 0.5 Ω, R_B = 1 Ω, joints 5 Ω,
   r_s = 0.2 Ω/km, ρ = 100 Ω·m:

| Formation | Minor sections (km) | Faulted phase | I_g at B | Largest link-box voltage / across a joint |
|---|---|---|---|---|
| trefoil, 0.09 m | 6 × 0.5 | any | 0.758 kA | 650 V / 345 V |
| trefoil, 0.09 m | 0.4, 0.55, 0.55, 0.5, 0.45, 0.55 | any | 0.758 kA | 640 V / 380 V |
| flat, 0.2 m | 6 × 0.5 | outer | 0.787 kA | 825 V / 814 V |
| flat, 0.2 m | 6 × 0.5 | middle | 0.793 kA | 734 V / 527 V |
| flat, 0.2 m | 0.4, 0.55, 0.55, 0.5, 0.45, 0.55 | outer | 0.787 kA | 824 V / 857 V |

   In trefoil the split does not depend on the minor lengths (the sheaths are equally far
   apart, so only the total induced voltage counts), but the link-box voltages do. Entering
   the link boxes as earthed joints, the only way before, gave 0.680 kA (trefoil) and 0.708 kA
   (flat), 10 % low.

### Changes in 1.9.3

1. **Lightning model for large electrodes** (`hf.harmonic_impedance`, graded mesh). Above the
   segment limit (800) the model used to lengthen every segment alike, so a large grid was
   meshed at 5–20 m everywhere, the injection included, where the current changes within the
   soil's skin depth at the highest frequency. The mesh is now graded: the segment length at
   the injection (a fifth of the skin depth at f_max, at most 1 m) grows in proportion to the
   distance from it, s₀ + α·d, with α the smallest that keeps the model within the limit. Far
   out the current has either decayed (high frequencies) or varies slowly (low ones). Where a
   grid's crossings alone need more segments than the limit allows, the limit gives way so that
   half of it is left for the fine mesh at the injection. Largest error of |Z(jω)|, 100 Hz–10
   MHz:

| Grid (corner feed unless noted) | Soil | Reference | Graded | Old uniform mesh |
|---|---|---|---|---|
| 40 m × 40 m, D 10 m | 100 Ω·m | uniform 0.21 m, 1920 seg. | 250 seg.: 0.07 % | 280 seg. (1.4 m): 0.7 % |
| 200 m × 200 m, D 20 m | 100 Ω·m | graded, 2400 seg. | 800 seg.: 0.09 % | 880 seg. (5 m): 3.5 % |
| same, fed at the centre | 100 Ω·m | graded, 2400 seg. | 800 seg.: 0.10 % | 880 seg.: 7.9 % |
| 200 m × 200 m, D 20 m | 30 Ω·m | graded, 2400 seg. | 800 seg.: 0.07 % | 880 seg.: 14.7 % |
| 400 m × 400 m, D 20 m | 100 Ω·m | graded, 2400 seg. | 1240 seg.: 0.10 % | 840 seg. (20 m): 68 % |

   The 40 m case is against a uniform mesh at the full fine length;
   the larger cases against a graded mesh three times finer, which agrees with it as closely.
   R_LF is within 0.1 % in every case. The impulse impedance of the TB 781 strokes moved little
   with the old mesh (up to 3 % high, for the 400 m grid) because their energy lies below
   1 MHz; |Z| at a few MHz, and so steep fronts, was what suffered. Results within the limit
   are unchanged.
2. Tests: `tests/test_v193_lightning_graded.py`.

### Changes in 1.9.2

1. **Shield wires coupled to each other** (fault-current page, shield-wire card;
   `faultcurrent.bundle_self`, `_corridor`, `corridor_nodes`).
   - **Two shield wires on a line** are one bundle bonded at every tower, with their mutual
     impedance: (z_s + z_m)/2 per km. Up to 1.9.1 the two wires of an *other* line were taken
     as z_s/2, which put that ladder's impedance 14–19 % low — more current taken away from
     the grid than it really takes, so the grid current low (not conservative). The faulted
     line may now have two shield wires as well.
   - **Parallel lines in the same corridor** (same towers' positions, same remote station) are
     solved as one network of nodes per line and tower, with every shield wire coupled to the
     faulted phase and to every other shield wire (Carson). On a 132 kV, 20 km line a parallel
     line 30 m away takes the station-fault grid current from 1.30 kA to 0.91 kA and the worst
     (fault 4 km out) from 6.29 to 4.70 kA; entered as an independent other line it gave 1.10
     and 5.33 kA, so the uncoupled model was conservative here.
   - Checked against an independent solution with every wire of every span its own branch
     (10⁻¹⁰), against the bundle identity, and against the classical coupling far from the
     ends (the wires carry −Z⁻¹z_p·I_phase, 10⁻⁶). A line on a different route stays an
     independent ladder.
2. **Circuit-field check of the transferred potential** (`transfer.circuit_field_check`). A
   bare or coated route bonded to the station is also solved by the circuit-field model:
   station and route as one network of conductors with their internal impedance (the route's
   own metal, e.g. a hollow steel pipe, beside a copper grid) and self and mutual inductance
   — so the magnetic coupling between the route and the grid conductors, which the coupled
   solution leaves out, and the drop along the grid are included. The check runs where the
   model takes up to 2000 segments; each access point shows both touch voltages and the
   larger is the design value. Against the coupled solution: a 400 m copper wire on a 30 m grid
   within 1 %; a 1 km bare steel pipe and a 600 m pipe running 100 m beside the grid edge,
   touch within 4 % (far end 3 % higher in the check), current drawn within 1 %; a coated pipe
   within 0.1 %. Not run (and said so) when the route is not bonded directly, ends on an earth,
   carries induction from a faulted line, or the model has fences or plates.
3. **Fence sections and gates.** Up to now the README said they were not modelled; they are,
   as several fence outlines that are not closed (*+ Fence (outline)*, closed = 0): each is
   its own network, bonded or isolated, the gap between two is the gate or the insulated
   section, and the results give each section's potential and touch voltage and the voltage
   between sections. The help text now says how.
4. Tests: `tests/test_v192_corridor.py`.

### Changes in 1.9.1

1. **Shortest segment** (`bem.MIN_SEG_RADII`). The thin-wire kernel places a conductor's
   current on its axis and evaluates the potential on its surface; with segments shorter than
   about four radii its matrix stops being positive definite and some leakage currents turn
   negative (a 6 m rod of 50 mm radius: below four radii R jumps about erratically, by up to 9 %), and where
   conductors cross the trouble starts near six radii. Ordinary grids never get there, and the
   end grading and the automatic refinement already stopped at ten radii, but a short segment
   length typed for a thick conductor did not. Now no bare conductor is cut finer than ten
   radii, in the numerical page, the non-equipotential solution and the lightning model; the
   results say which conductors were kept there and at what length. Plates keep their own
   strips (1.9.0), whose length was validated against an exact solution; concrete-encased
   conductors keep their 1.5 concrete radii.
2. Tests: `tests/test_v191_thin_wire_guard.py`.

### Changes in 1.9.0

1. **Plates** (numerical page, *+ Plate (horizontal)* and *+ Plate (vertical)*; item
   `kind: "plate"`). A thin solid metal rectangle in contact with the soil — an earth plate, or
   a raft's reinforcement taken as one sheet — horizontal at a depth or vertical below a top
   edge, at any angle in plan. It is cut along its long side into 16 strips (up to 64 for a wide
   plate near the surface), narrow at the edges where a plate's charge density rises as
   d^(−1/2) (cosine spacing); each strip is a conductor of radius w/2π, the radius at which an
   array of wires carries charge exactly as the plane it fills. Checked against an independent
   panel solution (exact potential of uniform rectangles, extrapolated) and the capacitance of
   the unit square (Read 2004):

   | Plate | Reference R | Solver, 16 strips |
   |---|---|---|
   | 10 m square, 1000 m deep (full space + image) | 2.1736 Ω | +0.22 % |
   | 1 m square, 0.5 m deep, 100 Ω·m | 28.419 Ω | +0.20 % |
   | 10 m × 1 m, 0.5 m deep | 8.3286 Ω | +0.08 % |
   | 1 m square vertical, top 0.5 m | 25.747 Ω | +0.18 % |
   | 1 m square, 0.5 m deep, 100 over 400 Ω·m, h = 2 m | 35.795 Ω | +0.16 % |

   The error falls as 1/n² with the number of strips and is always on the high side; the
   surface potential over a 6 m plate 0.5 m deep is within 0.8 % of the GPR of the panel
   solution. A raft's reinforcement as a plate: against the bars entered as a grid (6–18 m
   rafts, bars 12–20 mm at 0.2–0.25 m) R is 0.0–0.7 % low; on a 12 m raft the touch voltage
   is 1.2 % low and the step voltage 2.6 % high. The concrete is taken as soil. Plates keep
   their own segments (the convergence check and the automatic refinement leave them alone);
   the non-equipotential and lightning models take wire electrodes and refuse a plate.
2. **The browser build solves in the background** (`web/engine.js`). The calculation engine
   runs in a Web Worker, so the page keeps responding — it scrolls, switches pages and shows
   progress — while a large model is solved: during a 6 s solution the page drew 374 frames
   where it drew 1 before. The results are identical. A browser that refuses the worker runs
   the engine on the page's own thread as before.
3. Tests: `tests/test_v190_plates.py`.

### Changes in 1.8.9

1. **Two-scale non-equipotential solution** (`powerfreq.two_scale_leakage`,
   `bem.Network.leakage_for_potentials`). A model larger than the circuit-field model takes
   (3000 segments) is no longer coarsened throughout. The circuit-field model is solved with
   segments long enough to stay within the limit and gives the metal potentials, which vary
   slowly along the conductors; these are interpolated along each conductor to segments of
   the length asked for, and the leakage currents there follow from the static
   boundary-element matrix (dense, or compressed with GMRES, up to 20 000 segments). The
   surface potential, touch and step voltages are those of the fine currents; the earth
   impedance and the metal potentials are those of the coarse model. The fine currents sum to
   I_G within a fraction of a percent before they are scaled to it, and the ratio is reported.
   Checked on a 300 m × 300 m grid (D = 20 m) fed at a corner against the full model at 5 m:

   | Case | Full model, 5 m: touch / step | Two-scale 20 m / 5 m | 20 m alone |
   |---|---|---|---|
   | Copper, 30 Ω·m | 201.6 V / 73.6 V | +0.4 % / −0.1 % | +6.5 % / −12.4 % |
   | Steel, 30 Ω·m | 694.1 V / 243.3 V | +0.2 % / 0.0 % | +16.5 % / −16.1 % |
   | Steel, 30/200 Ω·m, h = 3 m | 594.5 V / 219.6 V | +0.4 % / 0.0 % | +15.2 % / −19.9 % |

   A 360 m × 200 m plant grid with 26 rods in two-layer soil (200/50 Ω·m) at 2 m segments is
   now solved with 2768 coarse and 7448 fine segments in about three minutes; the coarse model
   alone read the touch voltage 4 % and the step voltage 5 % high. `two_scale: false` keeps
   the coarsened solution of earlier versions.
2. **Memory of the circuit-field model.** In layered soil the near-image blocks kept between
   frequencies — about a hundred N × N arrays — are now kept only within 1 GB, the layered
   corrections are added in place, and the matrices are freed before the boundary-element
   half. The plant grid above passed 6 GB and stopped in 1.8.8; its circuit-field model now
   peaks at about 2.8 GB. The results are unchanged (10⁻¹³).
3. **Correction.** The 3000-segment limit was applied to the total length divided by the
   segment length, but the conductors are also cut where they meet and at the layer
   boundaries, so grids with many rods ran up to 40 % over it. The count after cutting is now
   kept within the limit; a layout with more crossings than the limit is refused with a
   message.
4. Tests: `tests/test_v189_two_scale.py`.

### Changes in 1.8.8

1. **Transferred potential solved with the station** (`transfer.coupled_transferred_potential`;
   *Solve with the station*, on by default). A bare or coated conductor is cut into segments
   that leak into the soil with the grid's (one potential-coefficient matrix), with its series
   impedance between them. The current it draws, the GPR and the soil beside the route then
   include its own leakage. Checked: with the series impedance set to zero it reproduces the
   main solver with the wire as part of the grid, or floating, to 10⁻⁶; against the full
   circuit-field model at 50 Hz, a 2 km bare copper wire bonded to Annex H Grid 3 gives the
   GPR within 1.2 %, the current drawn within 1.4 % and the touch voltage along the route
   within 3 %. The one-way line model of earlier versions read that GPR 10 % high and the touch
   voltage beside the wire two to three times high (293 V against 118 V); for a coated pipe the
   two agree beyond the station edge. The one-way figures are still reported for comparison.
2. **Automatic refinement** (numerical page, *Automatic refinement*, a tolerance in %). After the
   solution the segments within 3 m of the worst touch and step points — and of their
   symmetry images — are halved and the model solved again until both change by less than the
   tolerance. With the default 3 m graded segments on Annex B the first refinement moves them
   by 0.04 % and 0.15 %; from 8 m segments it reaches a 0.25 m mesh's values within about 0.5 %.
3. **Corrections.**
   - The one-way line model could place two nodes 10⁻¹⁶ m apart, whose span then dominated
     the elimination: for an 800 m bare copper wire on a 30 m grid it gave a GPR of 3 V instead
     of about 410 V. Coincident nodes are now merged; the input admittance of a uniform line
     matches tanh(γL)/Z₀. Routes whose node set had no such pair (the book's 2 km cases among
     them) are unchanged.
   - The Sommerfeld tables of the lightning and non-equipotential models were built from one
     J₀(rλ) array, which for uniform soil and a layout several hundred metres across ran to
     gigabytes and stopped the run; they are now summed in blocks, with the same result.
4. **Automatic tests on GitHub** (`.github/workflows/tests.yml`): the formula audit and the
   test suite run on every push, on Python 3.10 and 3.12.
5. Tests: `tests/test_v188_accuracy_transfer.py`.

### Changes in 1.8.7

1. **Solver size** (`earthsys/hmatrix.py`, `earthsys/bem.py`). Large power-plant grids are
   solved at the segment length asked for instead of being coarsened:
   - **Symmetry.** Mirrors in x, y and the diagonals and rotations by 90° and 180° that map
     every segment and the soil onto themselves are detected, and the system is reduced to
     one segment per orbit — exact, with an eighth of the columns and of the unknowns for a
     square grid. The Annex H grids agree with the full solution to 10⁻¹².
   - **Compressed matrix and iterative solution.** Above 4000 unknowns (after the reduction)
     the matrix is an H-matrix: blocks between distant clusters of segments are replaced by
     adaptive cross approximations to 10⁻⁸, near blocks keep the exact near-field quadrature,
     and GMRES with a block-Jacobi preconditioner solves it in 10–20 iterations. Against the
     dense solution: 10⁻⁸ in R_g and 10⁻⁷ in touch and step on Annex B with rods and Annex H
     Grids 2 and 3; 13 520 segments in about 25 s in uniform soil.
   - **Two-layer series tabulated** for points at one depth (cubic Hermite in asinh(r), 10⁻¹⁰):
     two-layer solutions twice as fast, answers unchanged to 10⁻¹¹.
   - **Reuse.** Solutions are kept by geometry and soil and serve another current, and in
     uniform soil another resistivity; the studies share their cases (the measured case of the
     seasonal study is the coarse case of the convergence check), and a study run again with
     nothing changed is not recomputed.
   - The segment limit of the numerical page is 20 000 (was 4000); surface maps of large
     models are summed through the same cluster trees.
   - **Non-equipotential solution:** the segment currents are eliminated before the
     solution, leaving the node admittance matrix — a third of the memory, about a ninth of
     the arithmetic — and the limit is 3000 segments (was 1500).
2. **Two soils side by side** (`/api/bem` fields `rho_v`, `x_v`, `y_v`, `angle_v`; numerical
   page *Second region ρ′*). Uniform ρ₁ on one side of a vertical boundary and ρ′ on the
   other, with the exact four-term image solution; conductors are split at the boundary; a
   conductor parallel to it takes its mirror image in closed form. Checked against the exact
   result for an electrode in the boundary (harmonic mean, 10⁻¹²) and for one symmetric about
   it (the Annex B grid halved by the boundary, 3 × 10⁻⁶), the first-order image
   estimate for a rod near it (0.05 %), reciprocity and continuity across it. Used by the
   main solution, the convergence check, the transferred potential, the optimisation and the
   fall-of-potential test; the seasonal and soil-uncertainty studies, the non-equipotential
   solution and the lightning response remain for horizontally layered soil.
3. Tests: `tests/test_v187_solver_vertical.py`.

### Changes in 1.8.6

1. **Fuse time–current characteristics** (`earthsys/fuses.py`, `/api/fuse`). Automatic
   disconnection with a fuse no longer depends only on BS 7671's tables for BS 88-2 fuses:
   - **IEC 60269 gates** for a fuse of any make: the gG and gM gates of IEC 60269-1 Table 3
     (16–1250 A), the pre-arcing I²t at 0.01 s (Table 7) and the conventional currents
     (Table 2), with the small ratings of IEC 60269-2 fuse system A (NH) and IEC 60269-3 systems
     A (D-type), B (NF cylindrical), C (BS 88-3) and F (BS 1362 plug-top); aM fuses from Table 4.
     The upper limit of the band, joined on log–log axes, operates every compliant fuse-link
     within the time — safe for a fuse of unknown make.
   - **The manufacturer's curve**, pasted as current–time points (CSV), followed on log–log
     axes, with a current tolerance that moves a mean curve to the safe side.
   - The page plots the band or curve with I_a at the required time and the prospective fault
     current, and reports the time within which the fuse operates at C_min·U₀/Z_s.
2. **BS 88-2 ratings that BS 7671 does not tabulate** (80–200 A at 0.4 s, and 250–1250 A) now
   take the upper limit of the IEC 60269 gates instead of indicative values or a multiplier. At
   125 A and 0.4 s that is 1348 A instead of 1050 A. Every value BS 7671 does tabulate was
   checked to lie inside the gates.
3. Tests: `tests/test_v186_fuses.py`.

### Changes in 1.8.5

1. **Lightning risk to IEC 62305-2:2024** (`earthsys/risk.py`, rewritten). Edition 3 replaces
   the four risks of 2010 with one risk R = R_L1 + R_L2 (injury to living beings and physical
   damage) against R_T = 10⁻⁵, and turns the loss of service into the frequency of damage
   F = F_C + F_M + F_W + F_Z of internal systems against a tolerable F_T (0.1 /yr critical,
   1 /yr non-critical). The new module has the strike-point density N_SG = k·N_G, the
   Uw-dependent collection areas (r_M = 350/U_w, r_I = 2000/U_w^1.8), lines in sections
   (an HV section with C_T = 0.2), the new component R_AD for people exposed on a roof,
   P_P = t_z/8760 and P_e = t_e/8760, P_TWS for a thunderstorm warning system, P_S = 1 once an
   LPS is installed, several internal systems per zone (P_C, P_M combined) and any number of
   risk zones. It searches LPS class × entrance bonding SPDs × coordinated SPDs for the
   cheapest set that meets R_T in every zone and F_T wherever it is set. It reproduces the
   three worked examples of Annex F — house, office building and hospital — to the figures
   printed in the standard (tests). The page has a risk-zone table and loads the office
   building as an example; the version 1.8.0–1.8.4 single-zone inputs still work.
2. **The 2024 editions of Parts 1, 3 and 4.** Part 3: class data, Figure 1 and Figure 5 are
   unchanged; k_m = 0.7 for an FRP, PE or PVC stand-off at least 0.5 m long, 0.5 m more on
   vertical electrodes in drying or freezing topsoil, and the Type A lengths waived below
   10 Ω. Part 4: the SPD lead drop is ΔU = 0.1·I_SPD kV per metre (C.4), the long-circuit rule
   is U_p/f ≤ (U_w − U_i)/k with the reflection factor k (2 when unknown), U_p ≤ 0.5·U_w for
   critical systems, and the simplified I_imp and I_n per protection mode of Tables C.3 and
   C.4 are given. Part 1: the conventional surge currents of Tables E.1 and E.2.
3. **Several lines in the shield-wire ladder.** Unequal spans (`spans_km`), a measured
   footing resistance for each tower (`Rt_list`), and the other outgoing lines entered as
   their own ladders (length, span, footing, remote earth, number of shield wires) and put in
   parallel with the grid. With uniform inputs the result is the 1.8.4 one to 1e-14.
4. **Induction from a faulted line of any route.** Give the faulted line as x, y points: the
   EMF per metre is computed point by point along the route from the nearest point of the
   line, z_m(d)·I·cos θ, so oblique approaches and crossings count only their real exposure
   (a perpendicular crossing induces nothing). The parallel-line input still works.
5. **Earth-fault current returning in cable sheaths** (`/api/cable/sheath`, a card on the
   fault page). The sheaths are solved as a ladder with the core-to-sheath coupling (Carson):
   trefoil, flat or three-core, armour in parallel, several circuits, earthed joints or link
   boxes, bonding at both ends or at one end, the source at A or beyond it. It gives the split
   factor, the current into each earth, the sheath current and the joint voltages, and equals
   EREC S34 D.2.1 and D.2.3 for a three-core cable. *Use S_f* sends it to the fault page.
6. Report sections for the cable sheaths, the extended ladder and the zone-by-zone risk.
   Tests: `tests/test_v185_risk_coupling.py`.

### Changes in 1.8.4

1. **Faster solutions, same answers.** The surface potential now sums the near-field
   corrections for all point–segment pairs at once instead of one call per segment; far
   segments use a 2-point Gauss rule (exact for a cubic, about 1e-5 at five segment lengths);
   the matrix assembly uses its 4-point rule for every pair it is responsible for and its full
   6 × 10 double quadrature only within 2.5 segment lengths, with a 3 × 4 rule out to eight.
   Touch, step and R_g change by less than 1e-6 against 1.8.3 (tests compare the field with a
   12-point reference and the matrix with the full rule). Annex B grid with rods, 3 m
   segments: 3.1 s → 1.8 s in uniform soil, 30.8 s → 13.4 s in two-layer and 23.2 s → 10.6 s
   in three-layer soil.
2. **Studies on several cores** (`earthsys/parallel.py`). The seasonal cases, the
   soil-uncertainty samples, the two solutions of the convergence check and the candidates of
   each optimisation round are solved on a pool of worker processes (cores − 1, at most 8;
   `ES_WORKERS` overrides; one thread per worker). The optimiser now advances all its
   combinations together, one candidate each per round. On the 70 m Annex B case it finds the
   same design as before in 115 s on one core and 84 s on two, against 295 s in 1.8.3; more
   cores shorten it further. The in-browser build runs the same code serially.
3. **DXF import** (`earthsys/dxfimport.py`, `/api/dxf/inspect`, `/api/dxf/import`). An ASCII
   DXF site plan (binary DXF too from 1.9.5) is read with the standard library: each layer is shown with what it holds and
   a suggested use (conductor, rod, fence or ignore); lines and polylines become conductors
   (bulges and arcs as chords of at most 15°), circles on a conductor layer rings, points,
   small circles and blocks rods, and each polyline on a fence layer a fence. The unit comes
   from `$INSUNITS` unless a scale is given, and the layout can be moved to the origin.
4. **Fence outlines in the table.** *+ Fence (outline)* adds a fence along any outline, edited
   as `x,y; x,y; …`; fence names can be edited.
5. Tests: `tests/test_v184_speed_dxf.py`.

### Changes in 1.8.3

1. **Soil-uncertainty sampling.** The soil models are now drawn by Latin hypercube sampling
   (McKay, Beckman and Conover, 1979): every parameter's distribution is split into as many
   equally likely bands as there are samples, with one sample in each, so 20 samples cover the
   tails evenly. With 10 samples the scatter of the sampled mean ρ₁ falls to less than half
   that of random sampling (a test checks it). Random sampling stays available.
2. **Confidence intervals.** Each probability of compliance is reported with its 95 %
   confidence interval (Wilson score interval), the number of samples that would narrow it to
   ±5 %, and the confidence that the largest sample lies above the true 95th percentile
   (1 − 0.95ⁿ; 59 samples give 95 %). The design report prints the interval.
3. **Fences in the non-equipotential solution.** Up to 1.8.2 fences were left out. Their
   posts and buried wire are now solved as leaking conductors; the fabric above ground joins
   them into one node per fence, and a bonded fence is joined to the grid at the grid node
   nearest to it. The solution reports each fence's potential and touch voltage (sampled
   0.5 m and 1 m inside and outside, as the main solver does) beside the equipotential value,
   adds a check for each fence, and the governing values use the fence touch voltage where it
   is larger. For a compact copper grid the fence potential agrees with the main solver within
   0.2 % and the touch voltage within 0.5 %.
4. Tests: `tests/test_v183_sampling_fences.py`.

### Changes in 1.8.2

1. **Governing values** (`earthsys/governing.py`, `/api/bem/governing`). Up to 1.8.1 the
   studies of the numerical page were reported beside the solution, but the verdict, the design
   report's compliance table and the drawing stamp used the plain solution alone, so a design
   could show *complies* at the equipotential touch voltage while the non-equipotential study
   on the same page exceeded the limit. Now, for touch, step, R_g and GPR, the largest value of
   the solution and of every study run on the same model governs:

   | Study | Value it contributes |
   |---|---|
   | Convergence check | largest of the coarse, fine and Richardson values (touch, step) |
   | Seasonal soil | the worst case for each quantity |
   | Soil uncertainty | the 95th percentile of each quantity |
   | Non-equipotential solution | touch and step with the conductor impedance; GPR at the feed |

   The maxima are taken separately, not multiplied. Every result of the solver and of the
   studies carries a `model_key` (electrodes, soil and current), and a study from an earlier
   model is ignored and listed as out of date. Touch-zone and fence checks are scaled by the
   governing-to-plain touch ratio. A new card on page 5 shows the governing checks with the
   study behind each and the remedy that fits it; the navigation dot, the report (English and
   Persian) and the drawings' design-rule verification (*Numerical analysis, governing values*)
   follow it.
2. Tests: `tests/test_v182_governing.py`.

### Changes in 1.8.1

1. **Faster grid optimisation.** The search now climbs from the sparsest grid and never solves a
   candidate that already costs more than the best design found so far; the graded, rodded
   combinations are tried first so that the bound prunes early. On a 70 m square in 400 Ω·m
   (IEEE 80 Annex B limits) it returns the same design (15 lines, grading 0.6, perimeter rods,
   29 % cheaper than the best uniform grid) in 40 % less time. A test checks the result against
   solving every candidate.
2. **Transferred potential** uses the same discretisation as the main solver: refinement at
   conductor ends and the 4000-segment limit.
3. **Tests** that use `pytest.mark.parametrize` now expand their cases under `unittest` whether
   or not pytest is installed (two such tests errored under `unittest` when it was).
4. Documentation: contents links in this README fixed; the Word build of `THEORY.md` is now
   `docs/THEORY.docx`, built locally and not kept in the repository.

### Changes in 1.8.0

Accuracy first: the numerical solver's answers no longer depend on how they are looked at,
say how far they are from converged, and no longer assume what the design has to prove.
New modules `earthsys/studies.py`, `earthsys/powerfreq.py`, `earthsys/earthtest.py`,
`earthsys/risk.py` and `earthsys/spd.py`; tests in `tests/test_v180_studies.py`; theory in
`docs/THEORY.md` §2.9, §3.7, §8.10–8.16, §10.8–10.9 and `docs/METHODS.md` §11.

1. **Step voltage in the worst direction, independent of the plot.** 1.7.0 differenced the
   surface potential in +x and +y and combined the two with hypot(): on the IEEE 80 Annex B
   grid with its 20 rods it read 480 V at 61 points and 603 V at 181, against 488 V from a
   brute-force search. The maximum is now located on the plot grid and along a ring outside
   the electrodes and refined in position and direction (0.02 m, 1°): 487 V at every
   resolution. The touch voltage is refined the same way.
2. **Where a person can touch.** The touch voltage counts within 1 m of buried metal or inside
   a mesh — the bounding rectangle used before put the empty notch of an L-shaped grid into
   the check — or, when given, only in **touch zones** (equipment rectangles, each with an
   optional limit of its own).
3. **Refinement at conductor ends** (on by default) and a **convergence check** that halves
   the segments and gives the Richardson estimate; the verdict uses the larger. A model too
   large for the segment limit now says that its segments were lengthened (the limit is
   4000 by default). Corner touch on Annex B with rods: 1173 V with uniform 3 m segments,
   1201 V graded (840 unknowns), 1216 V uniform 0.5 m (3380 unknowns).
4. **Non-equipotential solution** (`/api/bem/powerfreq`): the electrodes with the
   conductors' internal impedance and inductance at 50/60 Hz, fed at one or more points.
   300 m × 300 m copper grid, 30 Ω·m: |Z| = 1.33 R_g, far corner at 70 % of the feed point,
   touch 190 V against 104 V held equipotential; steel: |Z| = 3.1 R_g.
5. **Robust soil fit and several traverses.** A reading more than 3 robust standard
   deviations (at least 5 %) from the curve is set aside, one at a time, and listed; each
   traverse is also fitted alone and lateral variation over a factor 1.5 is flagged.
6. **Soil uncertainty** (`/api/bem/montecarlo`): soil models from the fit's covariance,
   percentiles of R_g, GPR, touch and step, probability of compliance; and **seasonal soil**
   (`/api/bem/seasonal`): dry and frozen top layers.
7. **Grid optimisation** (`/api/bem/optimise`): the cheapest grid meeting both limits, over
   the conductor count, unequal spacing x = L(u − g·sin 2πu/2π) and perimeter rods; the
   result loads into the electrode table. Grids accept `grading`, `n_x` and `n_y`.
8. **Fall-of-potential test** (`/api/earthtest`): the test curve for the actual electrode and
   soil, the current-electrode distance needed for a given accuracy, where the probe must
   stand, and the interpretation of measured readings. Annex B grid, 100 Ω·m over 1000 Ω·m at
   5 m: the 61.8 % reading is 27 % low with the current electrode at 1 × D and 0.9 % at 5 × D
   (in uniform soil 5 % and 0 %).
9. **Shield-wire ladder and fault location** (`/api/fault/sweep`): the tower-footing ladder
   with Carson's self and mutual impedances, solved for a fault in the station and at every
   tower; the largest grid current is often for a fault outside the station.
10. **Transferred potential** along bent routes, with the voltage induced by a parallel
    faulted line.
11. **IEC 62305-2 risk assessment** (`/api/risk`): R1 for a single-zone structure and the
    least LPS class and SPD level that meet R_T = 10⁻⁵; the class can be sent to the
    earth-termination design. **IEC 62305-4 SPD coordination** (`/api/spd`).
12. All new results go into the design report (English and Persian).
13. Housekeeping: every test file runs under plain `unittest` as well as `pytest`.

### Changes in 1.7.0

1. **Construction drawings (module 11).** The design now ends in a drawing set that a
   contractor can build from and a manufacturer can quote from, generated from the results of
   the other modules with no further calculation:
   000 register, general notes, legend and design-rule verification; 101 earth-grid layout
   plan (axes, dimension chains, rod schedule, test pits, fence, flag notes); 102 typical
   sections (trench, driven rod, equipment riser, fence); 201 earth pit, test link and warning
   label; 202 main earthing terminal; 301 connection details; 302 equipment bonding details;
   303 conductor selection chart with the IEEE 80 / IEC adiabatic sizing and the BS EN 50522
   Table C.1 / IEC 60364-5-54 Table 54.1 and 54.2 and IEC 62305-3 Table 8/9 minima; 401 lightning earth termination
   plan and down-conductor elevation; 501 TN/TT/IT and neutral-earthing schematics; 901 bill of
   materials with joints counted from the plan (cross, tee, corner, rod).
2. **Drafting rules.** ISO 5457 sheets (A3, A2, A1) with centring marks and a reference grid of
   50 mm fields from the centring marks, rows lettered from the top without I and O
   (IEC 61082-1, 5.7.3.4); a title block with every mandatory field of IEC 61082-1 Table B.1 /
   ISO 7200; line widths 0.25 / 0.5 / 1.0 mm in the 2:1 ratio of IEC 61082-1, 5.10; lettering
   only in the heights 1.8, 2.5, 3.5, 5 and 7 mm of IEC 61082-1, 5.11; IEC 60617 symbols
   (S00200 earth, S00202 protective earthing, S00204 bonding on the plans; S00020, S00044,
   S00059, S00064, S00555, S00809 and S00850 on the schematics, with dash-dot boundary frames
   to IEC 61082-1, 7.1.5); indices such as R_A and 3I_C0 set as subscripts; ISO 129-1
   dimensions, with oblique strokes for short spaces in a chain; ISO 5455 preferred scales
   chosen automatically for every view.
   Every rod is in the plan's schedule (up to three columns) and in rod_schedule.csv.
3. **L- and T-shaped grids are drawn to their true outline.** The grid module now places the
   notch on the conductor lines so that the outline reproduces the entered area and conductor
   length — IEEE 80 Example B.4 (70 m × 105 m, A = 4900 m², L_C = 1575 m) comes out exactly as
   the published 35 m × 70 m notch — clips the conductors to it and puts the rods on its
   perimeter. The grid page, the numerical solver's *Build from the IEEE 80 grid* and the layout
   plan all use it.
4. **Design-rule verification of the drawings.** The buried bare copper electrode is sized for
   its duty (BS EN 50522:2022 Table C.1 and IEC 60364-5-54 Table 54.1): 50 mm² where it also
   serves lightning protection (with IEC 62305-3 Table 7), 25 mm² for protection against
   electric shock only, 16 mm² where the risk of corrosion and mechanical damage is extremely
   low; automatic when a lightning protection system is designed or surge arresters are
   bonded. Then the thermal size, rod diameter and coating, burial
   depth, mesh ratio, surface layer, touch and step voltages, rod spacing, fence position,
   down-conductor spacing and test joints, ring-earth radius and position, MET disconnection,
   bonding sizes, joint qualification and the verdict of every calculation module used —
   each with its clause. Only when a rule or a module fails is every sheet stamped
   *NOT FOR CONSTRUCTION*.
5. **Outputs.** One vector PDF of the whole set (base-14 fonts, nothing to embed), one AutoCAD
   R12 DXF per sheet with named ISO layers, SVG previews, and CSV register and bill of
   materials — all in one ZIP, written by `earthsys/cad.py` with the standard library only, so
   the module also runs in the browser build.
6. Module results now keep their inputs (`_in`), so the drawings know the rod length, pit
   diameter, conductor material and LPS geometry that produced them.
7. Example names only: the report's engineer field and the examples no longer carry a real
   name.
8. `tests/test_v170_drawings.py`: the IEEE 80 Example B.4 outline, the electrode duty, every
   project type (substation, numerical layout, L-shaped grid, building only, lightning only),
   all sheet sizes, the joint count, a failing rod, the IEC 61082-1 lettering and line widths,
   DXF/PDF structure, and that no lettering leaves a sheet or runs into the title panel.

### Changes in 1.6.1

1. **Forced models are warned.** *Three layers* or *Four layers* still shows the requested
   model, but when the F test rejects the extra layers a warning heads the results and names
   the supported model with its values. Before, the verdict was a note below the residual
   table, and it said "the simpler model is kept" while the page showed the other one. Forced
   onto the built-in example traverse (longest spacing 40 m), three layers put 2 Ω·m below
   141 m; both that layer and four layers' 66 Ω·m below 70 m are rejected at p ≈ 0.8.
2. **Four layers reported the wrong count.** A requested four-layer model set the
   "supported" count to four, so no caution appeared at all. The count is now the one the
   tests support; a fourth layer is tested against two layers directly when the third fails.
3. **Unresolved and unreachable layers are flagged** in the table, the KPIs and the report,
   and drawn veiled in the section: a layer whose ρ or top has a one-standard-deviation factor
   above 20 (or sits on the search bound), or whose top lies below twice the median depth of
   investigation of the longest spread.
4. **Depth of investigation.** The section's dotted line was drawn at a_max; it is now the
   median depth of investigation, 0.52 a (Wenner) or 0.38 s (Schlumberger), after Edwards
   (1977).
5. **Hidden equivalence note.** For four layers the statement that h₂ is not resolved was
   filtered out; it is shown now.
6. **Confirmation before use.** *Pull inputs* (grid page) and *Use the fitted soil model*
   (numerical page) ask once before using a warned model, as they already did for a poor
   fit; a spurious conductive layer makes the computed resistance and GPR too low.
7. **Drawing.** The scale bar's last block overlapped its label, and the captions of two
   thin top layers overlapped; both are fixed.

### Changes in 1.6.0

**Layered soil, soil ionisation and concrete foundations in the lightning model** (module
`earthsys/hf.py`, foundation elements in `earthsys/bem.py`; tests in
`tests/test_v160_layers_ion_concrete.py`).

1. **Layered soil under lightning.** The lightning response now takes the soil card's
   two to four layers, each constant or frequency dependent. The Green's functions are the
   exact (Sommerfeld) solution for the stratified half-space — the transmission-line Green's
   functions of the mixed-potential formulation C — split into the direct term and the images
   near the electrode, integrated exactly, and a smooth correction tabulated per frequency.
   Against the exact model of Arnautovski-Toseva, Grcev and El Khamlichi Drissi (2007) for
   10 m and 50 m wires in four two-layer soils: the 10 m wire within 1 % up to 100 kHz and
   3.5 % at 1 MHz, the 50 m wire within 4.5 % up to 1 MHz; at 10 MHz the layered result
   follows the uniform one (which is 6.6 % above theirs) within 2 %. At low frequency it agrees with the boundary-element solver within 0.2 %, for
   rods that cross interfaces and for three layers.
2. **Soil ionisation.** Optional, with the critical field E0 (400 kV/m CIGRE, 300 kV/m
   IEEE): the resistive part of the response follows R/√(1 + i/I_g), I_g = E0ρ/(2πR²), and
   the reactive part is kept (Grcev 2009, Eq. 20). Reproduces Grcev's Table I (10 m rod,
   100 Ω·m): 8.3 Ω for the first stroke, 13.9 Ω against 13.4 Ω for the subsequent one.
3. **Concrete foundations.** New *Pier / pile* and *Strip footing* elements on the numerical
   page: the bar cage becomes one bar of the cage's geometric-mean radius inside a concrete
   cylinder whose resistivity (and, in the lightning model, permittivity) is in series with
   the soil. Fagan and Lee's (1970) Table VII is reproduced within 3 %, Wiener's (1970)
   measured footings fall in the measured range. Both the power-frequency solver and the
   lightning model take them.

### Changes in 1.5.0

**Four-layer soil, fences and transferred potential** (new module `earthsys/transfer.py`,
endpoint `/api/transfer`; tests in `tests/test_v150_fence_transfer.py`).

1. **Four layers.** *Number of layers* gains *Four layers*; *Automatic* tries a fourth when
   three layers still miss the readings by more than 3 % RMS with nine or more readings, and keeps it on the F test with
   N − 7 degrees of freedom. On the Zhang et al. traverse it finds the fourth layer
   (RMS 11.7 % → 3.8 %, p = 0.001) and fixes the thin layer's conductance within ×1.18; on
   Slaoui and Erchiqui's sounding it keeps three. The solver, grid rule and soil pull take
   four layers.
2. **Separate metal networks.** The solver holds each piece of metal at its own potential and
   returns the mutual-resistance matrix. A new **Fence** element places posts (and an optional
   buried wire) along a rectangle, bonded to the grid or isolated. Results add each network's
   potential and own resistance, the grid-to-fence transfer voltage and the fence touch
   voltage inside and outside. IEEE 80 Annex H Grid 4 (isolated fence) is reproduced within
   1.5 % of CDEGS or WinIGS for every quantity but one step voltage (4 %), and Grid 5 (bonded
   fence, L-shape) within 2.5 %.
3. **Transferred potential.** A pipe, rail, cable screen or bare wire leaving the station is
   solved as a lossy line (Carson series impedance, steel skin effect, coating or soil
   leakage) driven by the bond and by the solver's soil potential along the route, with the
   GPR corrected for the current it draws away. The numerical page has a new card; the report
   prints the result.
4. **Lightning response** (new module `earthsys/hf.py`, endpoint `/api/hf`, tests in
   `tests/test_v150_lightning.py`). The electrodes of the numerical
   page are solved as thin wires in a lossy half-space, in the frequency domain, with the
   Sommerfeld corrections for horizontal currents and charges; soil constant or
   frequency-dependent (Alipio–Visacro, CIGRE TB 781). Harmonic impedance, potential rise under
   the TB 781 and Heidler first and subsequent strokes, impulse impedance and coefficient.
   Reproduces Grcev's (2009) Sommerfeld results within about 5 % from 100 Ω·m up, the HEM
   results of TB 781 for a 3 m rod within 4 % and the rod's measured potential rise within 9 %,
   and TB 781 Table 4.1 within 0.02.
5. **Faster surface maps.** Surface potentials are evaluated for all segments at once, with
   the ±z images merged on the surface; points on top of fence posts are excluded from the
   step scan.
6. **Robustness.** Angles are reduced before numpy's cos and sin in the Bessel functions;
   on some machines the vectorised large-argument path raised a hardware floating-point
   exception that killed the process during an inversion.

### Changes in 1.4.0

**Three-layer soil**, from the field traverse to the numerical solver (new module
`earthsys/layered.py`, numpy only; tests in `tests/test_v140_three_layer.py`).

1. **Forward model.** Wenner and Schlumberger (finite MN) apparent resistivity of an N-layer
   earth from the recurrent kernel and its Hankel transform; the top interface is summed as
   images, the rest by Gauss–Legendre quadrature. Matches the two-layer formulas to 1e-6
   and the complete three-layer image series to 1e-8, in under a millisecond per traverse.
2. **Inversion.** Five parameters by Levenberg–Marquardt in log space from 64 starts plus
   seeds from the two-layer fit (global minimum in 30 of 30 random test earths). The soil
   page's *Number of layers* (Automatic / Two / Three) keeps the third layer only when an F
   test gives p < 0.05 and the RMS falls by a fifth (no false positives in 15 noisy
   two-layer sites, 14 of 15 three-layer sites found). Reports the linearised ranges and the
   combination h₂·ρ₂^β of the middle layer that the readings fix (S- or T-equivalence).
   On the published traverses of Gonos & Stathopulos (2005) it matches or beats the
   published GA, DE and SA fits.
3. **Grid rule.** The disc factor F is now one kernel integral, valid for any number of
   layers (equal to the old two-layer series to 1e-13). **Pull inputs** takes three-layer
   models and also reports the equivalent two-layer model for the grid. Conservative in all
   24 three-layer test cases against the three-layer solver.
4. **Solver.** Three-layer Green's function by tracing reflected and transmitted waves (exact
   image series, checked against an independent spectral integration to 3.5e-10), with the
   deep images taken from the spectral solution as Taylor tables. Conductors are split at
   both interfaces. Agrees with an independent finite-volume solution within 0.13 % for
   rods crossing both interfaces. The numerical page has ρ₃, the second-layer thickness and
   **Use the fitted soil model**.
5. **Report** prints the three-layer model, the two-layer RMS and the F test.

### Changes in 1.3.6

**Earth pits.** Module 6 has a new card for an electrode in a hole of low-resistivity
backfill (`earthsys/earthpit.py`, endpoint `/api/earthpit`, tests in
`tests/test_v136_earthpit.py`).

1. **Numerical solution.** The rod or plate and its backfill cylinder are solved by an
   axisymmetric finite-volume model of Laplace's equation. It uses numpy only, so it also
   runs in the browser. Checked against Dwight's rod (−1.1 %; the BEM value 33.15 Ω is
   matched to 0.1 %), the buried-plate formula (−0.7 %) and BS 7430 9.5.7 (within 2.5 %,
   BS on the conservative side).
2. **Backfill library.** Bentonite 2.5 Ω·m (IEEE 80 14.5) and 8.7 Ω·m (CBIP Publication 302),
   enhancement compounds at their declared value (IEC 62561-7), concrete, or a measured mix.
   Partial columns are allowed: a plate at the bottom of a dug well, or a hole whose top is
   refilled with excavated soil.
3. **Groups and targets.** n pits in a line with the BS 7430 9.5.4 group factor; the number
   of pits for a target resistance in the dry season.
4. **Checks.** BS 7430 9.8 current density at the metal and at the backfill boundary;
   electrode sizes against IEC 62561-2 Table 3 and the Iranian earthing regulation
   (Art. 15, 24); IEC 62561-5:2023 housing class; re-service limit of 1.5 × the
   commissioning value (CBIP 302, 8.4.5).
5. **Report and registry.** A report section (English and Persian) and a new
   "Earth electrodes and earth pits" area in the standards registry.

### Changes in 1.3.5

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
   solver gives 1.137 Ω, like an independent axisymmetric solution.

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

Four corrections in the lightning modules against the **IEC 62305-3:2010** :

- **l₁ (Figure 3), class II**: the line is l₁ = max(5, 0.02ρ − 11) m — 49 m at 3000 Ω·m, not 45 m.
  Class I (max(5, 0.03ρ − 10)) was already right. Both are now taken from the vector drawing.
- **Protective angle (Figure 1)**: the hand-digitised angles were up to 16° too generous (class I at
  10 m: 61° instead of 45°) and rose to 80° below 2 m. They are now read from the vector drawing
  (±0.3°) and held constant below 2 m. The rolling sphere, which governs, is unchanged.
- **k_c (Table 12)**: 0.44 for three or more down-conductors (was 0.55 for three).
- **Earth-electrode minimum dimensions (Table 7)**: updated to the 2010 edition.

One addition: module 1 now reports the **uncertainty of the fitted soil model** — one-standard-
deviation ranges of ρ₁, ρ₂ and h and the correlation of ρ₁ with h, from the linearised covariance
s²(JᵀJ)⁻¹ of the least-squares fit (`docs/THEORY.md` §2.5). The help text for the external loop
impedance Z_e now says what to enter for a TT supply.

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

## 12. Running it online

The same interface runs with no server. `web/boot.js` probes for `/api/health`; if there is
no server it starts `web/engine.js` in a Web Worker, which loads Pyodide and the `earthsys`
package sources, and patches `fetch` so that every `/api/...` call goes to the identical
Python code in that background thread (on the page's own thread if the browser refuses the
worker). `app.js` never learns which mode it is in, the page stays responsive while a model
is solved, and the numbers are bit-for-bit the same.

## 13. Limitations

- The closed-form IEEE 80 equations assume uniform soil and uniform current leakage. For an
  L-, T- or irregular grid they take the true area, perimeter and conductor length (the
  shape factors n_c and n_d of Eq. (91)–(93)), but they remain approximations; for a
  genuinely irregular outline use the numerical solver, which takes the real geometry.
- At most four soil layers. A fifth is left to the residuals, and the middle layers' ρ and h
  are often fixed only in combination (the result says which); layered solver runs take up
  to twice as long as uniform ones.
- The main power-frequency solver holds the metal of each network at one potential; the
  non-equipotential solution removes that, fences included, but treats each fence's fabric as
  a perfect connection above ground and joins a bonded fence to the grid at one point (the
  grid node nearest to it). Fences follow any outline (typed as x,y corners or imported from a
  DXF). Insulated sections and gates are entered as several open fence outlines, each its
  own network (a gate leaf is taken with the section it hangs on).
- DXF import reads ASCII and binary DXF (not DWG) and takes plan geometry: lines,
  polylines (arcs as 15° chords), circles, points and block insertions. Depth, rod length and
  radii are set on import, not read from the drawing.
- Soil is horizontally layered, or two uniform soils side by side across one vertical plane;
  the two are not combined (layers on either side of a boundary, or several boundaries), and
  the seasonal and soil-uncertainty studies, the non-equipotential solution and the
  lightning response take horizontal layers only. Buried rock of limited size, tanks or
  backfilled trenches would need a volume method.
- Segments: no bare conductor is cut finer than ten of its radii (1.9.1); a thick conductor
  asked for shorter segments is solved at that length and the results say so.
- Large models: the compressed solution (above 4000 unknowns after the symmetry reduction)
  is accurate to about 10⁻⁷ against the dense one; the numerical page takes up to 20 000
  segments, and the non-equipotential solution 3000 in the circuit-field model, with the
  leakage and the surface at up to 20 000 (the two-scale solution); the earth impedance and
  metal potentials of a larger model come from the coarser circuit-field model. In the
  in-browser build memory and a single thread (in the background since 1.9.0) make a few
  thousand segments the practical size.
- Transferred potential: in the station's soil model. A bare or coated conductor is solved
  with the station (static leakage field, series impedance per metre) and, where the model
  takes up to 2000 segments, checked by the circuit-field model, which adds the inductive
  coupling between route and grid and the drop along the grid (the larger touch voltage is
  the design value); a rail or an insulated screen
  uses the one-way line model, in which its own leakage does not change the station's soil
  potential. Induction from the faulted line is computed point by
  point along the route from the nearest point of the line (one earth-return current, no
  shield-wire screening of its own, no current change along the line) and combined with the
  conductive part assuming the GPR is in phase with the fault current.
- The shield-wire ladder couples the faulted line's shield wires (one or two) and those of
  lines sharing its corridor over the whole route (same tower positions and remote station)
  to the faulted phase and to each other; a line on another route, or sharing only part of
  the route, is an independent ladder in parallel with the grid. Shield wires are taken at
  one height and Carson's approximation needs spacings well below the earth-return depth
  (the page refuses beyond a fifth of it). A counterpoise or a cable sheath on the same
  route is entered as another line.
- The seasonal and soil-uncertainty studies cannot take a vertical soil boundary: their soil
  cases are horizontal layers, and layers on either side of a boundary are not solved.
- The cable-sheath model is one route, bonded at both ends, at earthed joints or at one end
  (all sheaths in parallel: trefoil, flat or three-core), or cross-bonded (1.9.4, minor
  sections and transpositions modelled; trefoil or flat). In the cross-bonded model the link
  boxes are open, as with their voltage limiters not conducting, the cores are not transposed,
  and parallel circuits lie side by side.
- The risk assessment follows IEC 62305-2:2024 with the typical values of its annexes;
  P_SPD values better than LPL I (S2, S4) are entered as a number, and the losses to the
  surroundings (Annex E, from 1.9.5) use the annex's typical values for one scenario per
  structure; footnote g of Table E.3 (a reduction with a thunderstorm warning system inside the
  site fence) is not applied, which errs on the safe side. The SPD energy-coordination distances are the usual
  guidance values; the manufacturer's data take precedence.
- Plates (1.9.0) are thin rectangles solved by the main numerical solver and its studies, with
  the soil on both faces; a raft's concrete is taken as soil, and its reinforcement as a solid
  sheet (within about 1 % of the bars entered one by one). Plates of other shapes are entered
  as several rectangles.
- Lightning response: thin wires; foundations are concrete cylinders (plates, rafts and blocks
  are not modelled, nor is breakdown of the concrete); an electrode larger than the segment
  limit (800) is meshed fine at the injection and coarser away from it (1.9.3, within 0.1 % of
  a finer mesh on grids up to 400 m); all layers share one frequency dependence and
  permittivity; ionisation follows the CIGRE/IEEE formula, recommended for electrodes up to
  about 30 m, with an uncertain critical field E₀; in 10 Ω·m soil between 1 and 5 MHz the
  impedance is 5–16 % above Grcev's (conservative).
- Fuses: the IEC 60269 gates give a current that operates every compliant fuse-link, which is
  safe but on the high side; enter the manufacturer's time–current curve for a tight answer.
  The gates of IEC 60269-3 system D (Italian cylindrical) and of the gD, gN and gK classes of
  Part 2 are not included.
- See [`DISCLAIMER.md`](DISCLAIMER.md).

## 14. Troubleshooting

**A launcher window flashes and disappears.** Run `Diagnose.bat` — it prints and saves
`diagnostic.txt` listing every Python it can find. The launchers also write
`startup_log.txt` on every run.

**"Python was not found".** Install Python 3.9+ from python.org and tick *Add python.exe to
PATH*. The launchers also search the usual Anaconda, Miniconda and per-user install
locations.

**Security software blocks the .bat files.** Use `python START_EarthSystem.py` instead.

**"numpy missing — numerical solver off".** `pip install numpy`. Everything except module 5,
the three- and four-layer soil fits and the earth-pit card works without it.

**The numerical solver is slow.** Up to 4000 unknowns the cost grows as N² (assembly) and
N³ (solution); above that the compressed solver grows about as N log N. A symmetric layout is
reduced automatically, so keep a symmetric grid symmetric where the design allows. Increase
the segment length or reduce the surface-grid resolution; 3 m segments and 61 × 61 points
solve a 70 × 70 m grid with 20 rods in uniform soil in about three seconds, layered soil in
five to fifteen, most of it the search for the worst touch and step voltage; a 360 × 200 m
two-layer plant grid of 7400 segments takes about a minute to solve and as long again to scan
for the worst touch and step voltage. The studies (seasonal soil,
soil uncertainty, optimisation, convergence) spread their solutions over the processor's
cores on the desktop and in the local browser application; set the environment variable
`ES_WORKERS` to the number of worker processes you want (1 turns this off). The in-browser
build has one thread and runs them one after another. The lightning response solves the electrodes at 40 frequencies: a 30 m wire
takes seconds, a grid of several hundred segments a minute or two, and layered soil up to
twice that. Lower the highest frequency or the number of segments to speed it up.

**The soil fit has a large RMS error.** The site is probably not two layers: with six or
more readings, *Automatic* also tries three, and with nine or more four; *Three layers* and
*Four layers* force them. If even four layers fit badly, look for buried metal crossing the
traverse and run a perpendicular one.

## 15. Contributing

Issues and pull requests are welcome. Useful directions:

- measured field data: soil traverses, fall-of-potential tests and impulse tests of real sites
- measured fall-of-potential curves with the electrode geometry, to test the interpretation
- foundation rafts and pad footings in the lightning model; breakdown of concrete
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
2. IEEE Std 81-2025, *IEEE Guide for Measuring Earth Resistivity, Ground Impedance, and Earth Surface Potentials of a Grounding System* (revision of IEEE Std 81-2012)
3. IEEE Std 142-2007, *IEEE Recommended Practice for Grounding of Industrial and Commercial Power Systems* (Green Book)
4. IEEE Std C62.92 series, *IEEE Guide for the Application of Neutral Grounding in Electrical Utility Systems*
5. IEC 60364-4-41:2005+A1:2017, *Low-voltage electrical installations — Protection against electric shock*
6. IEC 60364-5-54:2011+A1:2021, *Earthing arrangements and protective conductors*
7. IEC 60909-0:2016, *Short-circuit currents in three-phase a.c. systems — Calculation of currents*
8. IEC 62305-1, -2, -3 and -4:2024, *Protection against lightning* (edition 3; Part 3's class data, Figure 1 and Figure 5 are those of 2010)
9. BS 7430:2011+A1:2015, *Code of practice for protective earthing of electrical installations* (λ tables; replaced by BS 7430:2026)
10. IEC 60269-1:2006+A1:2009+A2:2014, IEC 60269-2:2013+A1:2016 and IEC 60269-3:2010+A1:2013, *Low-voltage fuses* (gates, conventional currents, pre-arcing I²t)

**Standards cross-checked or referenced** (`earthsys/standards.py`)

*Substation earthing*

11. AS 2067:2016, *Substations and high voltage installations exceeding 1 kV a.c.*
12. BS EN 50522:2022+A1:2024, *Earthing of power installations exceeding 1 kV a.c.*
13. IEC 61936-1:2021, *Power installations exceeding 1 kV AC and 1.5 kV DC — Part 1: AC*
14. ENA DOC 045-2022, *Substation Earthing Guide* (EG-1), Energy Networks Australia

*Testing*

15. ENA TS 41-24 Issue 2 (2018), *Guidelines for the design, installation, testing and maintenance of main earthing systems in substations*, Energy Networks Association (UK)

*Touch and step voltage*

16. IEC 60479-1:2018, *Effects of current on human beings and livestock — Part 1: General aspects* (replaces IEC TS 60479-1:2005+A1:2016); IEC 60479-2:2019, *Part 2: Special aspects*
17. ENA DOC 025-2022, *Power System Earthing Guide — Part 1: Management Principles* (EG-0), Energy Networks Australia

*Renewable generation*

18. IEC 61400-24:2019+AMD1:2024, *Wind energy generation systems — Part 24: Lightning protection* (turbine earthing, built on IEC 62305-3)
19. IEEE Std 2760-2020, *IEEE Guide for Wind Power Plant Grounding System Design for Personnel Safety*
20. IEEE Std 2778-2020, *IEEE Guide for Solar Power Plant Grounding for Personnel Protection*

*Metallic pipelines*

21. AS/NZS 4853:2012, *Electrical hazards on metallic pipelines*
22. CIGRE TB 95 (1995), *Guide on the influence of high voltage AC power systems on metallic pipelines*

*Industrial and commercial installations*

23. AS/NZS 3000:2018, *Electrical installations* (Wiring Rules), with Amendments 1–3
24. BS 7671:2018+A4:2026, *Requirements for Electrical Installations* (IET Wiring Regulations, 18th Edition)

*Overhead lines*

25. AS/NZS 7000:2016, *Overhead line design*
26. CIGRE TB 781 (2019), *Impact of soil-parameter frequency dependence on the response of grounding electrodes and on the lightning performance of electrical systems*
27. CIGRE TB 839 (2021), *Procedures for estimating the lightning performance of transmission lines — new aspects*
28. IEEE Std 1243-1997, *IEEE Guide for Improving the Lightning Performance of Transmission Lines*

*HVDC*

29. EPRI EL-2020 (1981), *HVDC Ground Electrode Design*, Electric Power Research Institute

*Data centres*

30. IEC 60364-5-548:1996, *Earthing arrangements and equipotential bonding for information technology installations* (withdrawn 2002; content now in IEC 60364-5-54 and IEC 60364-4-44)
31. IEEE Std 1100-2005, *IEEE Recommended Practice for Powering and Grounding Electronic Equipment* (Emerald Book; inactive-reserved since 2021)

*Telecommunications*

32. AS/NZS 3835.1:2006, *Earth potential rise — Protection of telecommunications network users, personnel and plant — Code of practice*
33. BS EN 50310:2016+A1:2020, *Telecommunications bonding networks for buildings and other structures*

*Fault-current distribution*

34. ENA EREC S34 Issue 2 (2018), *A guide for assessing the rise of earth potential at electrical installations*, Energy Networks Association (UK)
35. CIGRE TB 347 (2008), *Earth potential rises in specially bonded screen systems*

**Papers and books**

36. H. B. Dwight, "Calculation of resistances to ground", *Trans. AIEE*, 55, 1936
37. E. D. Sunde, *Earth Conduction Effects in Transmission Systems*, Van Nostrand, 1949
38. J. R. Carson, "Wave propagation in overhead wires with ground return", *Bell Syst. Tech. J.*, 5, 1926
39. S. J. Schwarz, "Analytical expressions for resistance of grounding systems", *Trans. AIEE*, 73, 1954
40. C. F. Dalziel, "Threshold 60-cycle fibrillating currents", *Trans. AIEE*, 79, 1960
41. F. Dawalibi and D. Mukhedkar, "Optimum design of substation grounding in two-layer earth", *IEEE Trans. PAS*, 94, 1975
42. J. G. Sverak, "Sizing of ground conductors against fusing", *IEEE Trans. PAS*, 100, 1981
43. R. Alipio and S. Visacro, "Modeling the frequency dependence of electrical parameters of soil", *IEEE Trans. Electromagnetic Compatibility*, 56(5), 2014
44. M. Bebendorf, "Approximation of boundary element matrices", *Numerische Mathematik*, 86(4), 2000 — adaptive cross approximation (compressed solver, 1.8.7)
45. Y. Saad and M. H. Schultz, "GMRES: a generalized minimal residual algorithm for solving nonsymmetric linear systems", *SIAM J. Sci. Stat. Comput.*, 7(3), 1986
46. F. H. Read, "Capacitances and singularities of the unit triangle, square, tetrahedron and cube", *COMPEL*, 23(2), 2004 — the reference value for plates (1.9.0)
