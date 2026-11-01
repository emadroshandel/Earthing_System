# Earthing System — the physics and mathematics behind every page

A teaching companion. `METHODS.md` lists *what* each equation is and where it comes from;
this document explains *why* it has that form, derives it where the derivation is short
enough to be worth seeing, and works through the numbers.

It is written to be taught from. Each chapter follows the same shape: the physical
question, the derivation, a worked example with real numbers, and a note on what makes
the result pass or fail.

---

## Contents

1. [The physics of earthing](#1-the-physics-of-earthing)
2. [Soil — module 1](#2-soil--module-1)
3. [Fault current — module 2](#3-fault-current--module-2)
4. [Conductor sizing — module 3](#4-conductor-sizing--module-3)
5. [Safety criteria — the heart of module 4](#5-safety-criteria--the-heart-of-module-4)
6. [Grid resistance — module 4](#6-grid-resistance--module-4)
7. [Mesh and step voltage — module 4](#7-mesh-and-step-voltage--module-4)
8. [The numerical solver — module 5](#8-the-numerical-solver--module-5)
9. [Buildings and homes — module 6](#9-buildings-and-homes--module-6)
10. [Lightning — module 7](#10-lightning--module-7)
11. [Air termination and protection zones — module 8](#11-air-termination-and-protection-zones--module-8)
12. [System neutral grounding — module 9](#12-system-neutral-grounding--module-9)
13. [Reading a verdict](#13-reading-a-verdict)
14. [A suggested teaching sequence](#14-a-suggested-teaching-sequence)
15. [Symbols](#15-symbols)
16. [The wider standards landscape](#16-the-wider-standards-landscape)

---

## 1. The physics of earthing

### 1.1 What problem are we actually solving

Earthing is not about "getting rid of" current. It is about **controlling the potential
of the soil surface** while a fault current flows through it, so that no person standing
on that surface can have a dangerous current pass through their body.

Everything else — resistance, conductor size, mesh spacing — is downstream of that one
requirement.

### 1.2 Current in a conducting half-space

Take a small hemispherical electrode of radius `a` at the surface of soil of resistivity
ρ, injecting a current `I`. By symmetry the current spreads radially. At radius `r` it
crosses a hemisphere of area 2πr², so the current density is

```
J(r) = I / (2πr²)
```

Ohm's law in local form gives the electric field `E = ρJ`, and the potential at radius
`r` relative to infinity is the integral of that field:

```
V(r) = ∫r^∞ ρ I /(2πr'²) dr' = ρI / (2πr)          … (1.1)
```

This single expression is the seed of almost everything in the software. Two consequences
matter enormously:

**Consequence 1 — the resistance lives next to the electrode.**
The resistance between radius `r₁` and `r₂` is `ρ/(2π)·(1/r₁ − 1/r₂)`. Put in numbers for
a 0.5 m hemisphere in 100 Ω·m soil: from 0.5 m to 1 m you accumulate 15.9 Ω; from 1 m to
10 m, 14.3 Ω; from 10 m to infinity, only 1.6 Ω. **Half the total resistance is inside the
first metre.** That is why the *shape and size* of the electrode dominates, why driving a
rod deeper helps more than driving many short ones, and why the soil far away is almost
irrelevant.

**Consequence 2 — the potential gradient at the surface is steepest near the electrode.**
`dV/dr = −ρI/(2πr²)`. That gradient is exactly the step voltage a person walking there
would experience. It is why step voltage is worst at the edge of the grid, not in the
middle.

![Figure 1 — Potential around a hemispherical electrode in 100 Ω·m soil, and the cumulative resistance. Half of the total earth resistance is accumulated within the first metre — which is why electrode geometry matters far more than distant soil.](figures/fig01_halfspace.png)

*Figure 1 — Potential around a hemispherical electrode in 100 Ω·m soil, and the cumulative resistance. Half of the total earth resistance is accumulated within the first metre — which is why electrode geometry matters far more than distant soil.*

### 1.3 Ground potential rise, touch and step voltage

When the fault current `I_G` flows into an earthing system of resistance `R_g`, the whole
metal structure rises to

```
GPR = I_G · R_g          … (1.2)
```

above true remote earth. That is not in itself dangerous — a bird on a wire is at 20 kV
and perfectly well. Danger comes from **differences**:

- **Touch voltage** `U_T` — between earthed metal a person is holding (at GPR) and the
  soil under their feet, one metre away (at some lower potential `V_s`):
  `U_T = GPR − V_s`.
- **Step voltage** `U_S` — between the soil under one foot and the soil under the other,
  one metre apart: `U_S = V(x) − V(x+1)`.
- **Transferred potential** — when a conductor carries GPR *outside* the grid, so that
  someone standing on remote soil touches metal at full GPR. This is the most dangerous
  case of all, because the full GPR appears across the person; it is handled by isolation
  and bonding rules rather than by a formula.

The whole design problem is: **make the soil surface follow the metal as closely as
possible**, so those differences stay small.

> One metre is not arbitrary. It is the conventional reach of an arm and the conventional
> length of a stride, and it is baked into every tolerable-voltage formula in IEEE 80.

### 1.4 The human body as a circuit element

To turn "dangerous" into a number we need a circuit. IEEE 80 uses:

- **Body resistance** `R_B = 1000 Ω` — hand-to-both-feet or foot-to-foot, a deliberately
  conservative single value that ignores skin resistance.
- **Foot resistance.** A foot is modelled as a metallic disc of radius `b = 0.08 m`
  resting on the soil. The resistance of a disc electrode on a half-space is a classical
  result:

```
R_f = ρ / (4b) = ρ / (4 × 0.08) = 3.125 ρ ≈ 3ρ          … (1.3)
```

Now build the two circuits:

| Case | Feet | Foot network | Total series resistance |
|---|---|---|---|
| Touch (hand → both feet) | parallel | `3ρ/2 = 1.5ρ` | `R_B + 1.5ρ` |
| Step (foot → foot) | series | `2 × 3ρ = 6ρ` | `R_B + 6ρ` |

**Those two numbers, 1.5 and 6, are the entire reason the touch and step formulas look
different.** Nothing else changes between them.

![Figure 2 — The body as a circuit. The body resistance and the foot resistance are the same in both cases; only the way the two feet are connected changes — parallel for touch, series for step.](figures/fig02_body_circuit.png)

*Figure 2 — The body as a circuit. The body resistance and the foot resistance are the same in both cases; only the way the two feet are connected changes — parallel for touch, series for step.*

### 1.5 How much current is too much — Dalziel

Ventricular fibrillation is an energy phenomenon, not a pure current one. Dalziel's
experimental work gives a constant-energy law:

```
I_B² · t = S_B     ⟹     I_B = k / √t          … (1.4)
```

with `S_B = 0.0135` for a 50 kg body (`k = √0.0135 = 0.116`) and `S_B = 0.0246` for
70 kg (`k = 0.157`). Valid for shock durations from about 0.03 s to 3 s.

The `1/√t` is why **clearing time is such a powerful design lever**: halving the fault
duration raises every tolerable voltage by √2 ≈ 41 %.

### 1.6 Putting it together

Tolerable voltage = (tolerable current) × (circuit resistance):

```
E_touch = I_B (R_B + 1.5 C_s ρ_s) = (1000 + 1.5 C_s ρ_s) · k/√t_s     … (1.5)
E_step  = I_B (R_B + 6.0 C_s ρ_s) = (1000 + 6.0 C_s ρ_s) · k/√t_s     … (1.6)
```

You have now derived IEEE 80 Equations (29) to (33) from first principles. `C_s` and `ρ_s`
are explained in §5.

---

## 2. Soil — module 1
### 2.1 What resistivity is, and what moves it

Soil conducts through **electrolyte in its pores**, not through the mineral grains. So
resistivity is governed by moisture content, dissolved salts and temperature — not by what
the rock is made of. Practical consequences:

- Resistivity can change by a factor of 10 between wet and dry season. An electrode
  measured in spring can be twice as bad in August.
- Below 0 °C resistivity rises steeply as pore water freezes: near −5 °C it can be 3–5×
  the value at +10 °C. Electrodes are therefore driven below the frost line.
- Resistivity falls with depth in most sites, because deeper soil stays moist. This is
  precisely why a two-layer model with `ρ₂ < ρ₁` is so common, and why a long rod that
  reaches the lower layer is worth many short ones.

### 2.2 The Wenner array — deriving ρₐ = 2πaR

Four electrodes in a line, equally spaced by `a`. Current `I` enters at C1 and leaves at
C2; the voltage between the inner pair P1, P2 is measured.

Using (1.1) and superposing the source and the sink:

```
V(P1) = ρI/(2π) · [ 1/a − 1/(2a) ] =  ρI/(4πa)
V(P2) = ρI/(2π) · [ 1/(2a) − 1/a ] = −ρI/(4πa)

ΔV = V(P1) − V(P2) = ρI/(2πa)
```

so, with `R = ΔV/I`,

```
ρₐ = 2π a R          … (2.1)
```

![Figure 3 — The Wenner four-pin array. Current is injected at C1 and collected at C2; the potential difference between P1 and P2 gives the apparent resistivity directly.](figures/fig03_wenner.png)

*Figure 3 — The Wenner four-pin array. Current is injected at C1 and collected at C2; the potential difference between P1 and P2 gives the apparent resistivity directly.*

**What `a` means physically.** There is a persistent teaching shortcut that "the Wenner
array reads the resistivity down to a depth of `a`". It is a shortcut, not a theorem: the
measurement is a weighted average over a volume whose *median* depth of investigation is
about `0.52a` (Edwards, 1977; `0.38s` for Schlumberger), with contributions from much deeper
but fading. That is exactly why we do not use the raw numbers as a layer model — we
**invert** them — and why a layer the fit places far below the longest spacing is an
extrapolation, not a measurement. The soil page marks the median depth on its section and,
since 1.6.1, veils any layer that starts deeper than twice it.

Practical rules for the traverse: use spacings in a roughly logarithmic ladder
(0.5, 1, 2, 3, 5, 8, 12, 20, 30 m), extend the largest spacing to at least the diagonal of
the planned grid, and run at least two traverses at right angles.

### 2.3 The Schlumberger array

Outer (current) electrodes at ±s, inner (potential) electrodes separated by `d ≪ 2s`:

```
ρₐ = π R (s² − (d/2)²) / d          … (2.2)
```

Its advantage is that you move only the outer pair between readings, so the small,
noise-sensitive potential electrodes stay put. Its limitation is that as `s/d` grows the
measured voltage shrinks, so eventually you must widen `d`.

### 2.4 The two-layer earth and the image series

Now put a horizontal interface at depth `h` between resistivity `ρ₁` above and `ρ₂` below.
This is the classical method-of-images problem, exactly analogous to optics: the interface
partially "reflects" the current source, with a reflection coefficient

```
K = (ρ₂ − ρ₁) / (ρ₂ + ρ₁),     −1 ≤ K ≤ +1          … (2.3)
```

`K > 0` means the lower layer is more resistive (current is pushed back up), `K < 0` means
it is more conductive (current is drawn down). `K = 0` is uniform soil.

Each reflection produces an image source at `2nh`, weighted by `Kⁿ`. Summing over all
reflections and then over the four Wenner electrodes gives

```
ρₐ(a) = ρ₁ [ 1 + 4 Σ(n=1..∞) Kⁿ ( 1/√(1+(2nh/a)²) − 1/√(4+(2nh/a)²) ) ]   … (2.4)
```

and for Schlumberger

```
ρₐ(s) = ρ₁ [ 1 + 2 Σ(n=1..∞) Kⁿ / (1 + (2nh/s)^2)^(3/2) ]                … (2.5)
```

**Sanity checks a student should do themselves:**
- Set `K = 0`: every term vanishes and `ρₐ = ρ₁`. Correct — uniform soil.
- Let `a → 0`: `2nh/a → ∞`, all terms vanish, `ρₐ → ρ₁`. Correct — a very short array only
  sees the top layer.
- Let `a → ∞`: the series converges to a value that can be shown to give `ρₐ → ρ₂`.
  Correct — a very wide array only sees the bottom layer.

Because `|K| < 1` the series converges geometrically. Earthing System truncates it when
`|K|ⁿ < 10⁻⁶`, which for `K = 0.8` needs 62 terms and for `K = 0.3` only 12.

![Figure 4 — Apparent resistivity over a two-layer earth for a range of reflection factors, with ρ₁ = 200 Ω·m and h = 2 m. Short spacings always read ρ₁; long spacings tend to ρ₂. The transition happens around a ≈ h.](figures/fig04_two_layer.png)

*Figure 4 — Apparent resistivity over a two-layer earth for a range of reflection factors, with ρ₁ = 200 Ω·m and h = 2 m. Short spacings always read ρ₁; long spacings tend to ρ₂. The transition happens around a ≈ h.*

### 2.5 Inversion — fitting the model to the field data

We measure `ρₐ` at several spacings and want `(ρ₁, ρ₂, h)`. This is a three-parameter
non-linear least-squares problem. Earthing System minimises the **relative** residual

```
Φ(ρ₁, ρ₂, h) = Σᵢ [ (ρₐ,model(aᵢ) − ρₐ,meas(aᵢ)) / ρₐ,meas(aᵢ) ]²        … (2.6)
```

Two deliberate choices are worth teaching:

1. **Relative, not absolute, residuals.** Apparent resistivity often spans a decade across
   the traverse. An absolute-error fit would be dominated by the largest values and would
   fit the deep soil while ignoring the shallow soil — which is where the electrodes are.
2. **Optimise in log space.** The search variables are `ln ρ₁, ln ρ₂, ln h`. This keeps
   every parameter positive automatically with no constraints, and makes the search scale-
   free: a factor-of-two error costs the same whether the value is 10 or 10 000.

The optimiser is a Nelder–Mead simplex written out in `soil.py`, so the software has no
SciPy dependency. It is started from twenty-seven initial guesses and the best result is
kept, because the objective can have local minima when the data are noisy.

**Reading the RMS error.** Below about 5 % the two-layer model is a good description.
Between 5 % and 15 % it is usable but the site probably has three layers or lateral
variation. Above 15 % do not trust a layered model at all — go back to the field, run
perpendicular traverses, and look for buried metal (a pipe or an old cable crossing the
traverse is the classic cause of an unfittable curve).

### 2.6 Worked example

Field data (Wenner):

| a (m) | 1 | 2 | 4 | 6 | 10 | 16 |
|---|---|---|---|---|---|---|
| ρₐ (Ω·m) | 320 | 245 | 182 | 162 | 168 | 182 |

The curve falls then rises — the signature of a conductive middle layer, i.e. the true
site has three layers. Fitting two layers gives roughly `ρ₁ ≈ 378 Ω·m`, `ρ₂ ≈ 166 Ω·m`,
`h ≈ 0.96 m`, RMS ≈ 4.5 %. The fit follows the falling branch well and misses the rise at
large spacing, which is exactly what you should expect and exactly what the residual
column shows you. For a grid buried at 0.5 m this is a perfectly serviceable model,
because the electrode never sees the third layer.
Since version 1.4 *Automatic* also tries three layers here. They fit at 1.05 % RMS, but
with only six readings the F test of §2.8 gives `p = 0.23`, so the two-layer model stands.

![Figure 5 — Two-layer inversion of the example traverse, with the residuals below. The fit follows the falling branch and misses the rise beyond 6 m — the signature of a third layer that a two-layer model cannot represent.](figures/fig05_inversion.png)

*Figure 5 — Two-layer inversion of the example traverse, with the residuals below. The fit follows the falling branch and misses the rise beyond 6 m — the signature of a third layer that a two-layer model cannot represent.*

### 2.7 Equivalent uniform resistivity

The closed-form IEEE 80 equations assume one resistivity, so the two fitted layers have
to be collapsed into one number. The question is *how deep the electrode's current goes*
— and for a grid the answer is about one grid radius, however shallow the grid is buried.
A 70 m grid at 0.5 m in 2 m of topsoil drives most of its current into the lower layer.

Version 1.2 therefore treats the grid as a disc of the same area, radius `r = √(A/π)`, on
the two-layer earth. The disc on a two-layer earth has an exact image-series solution
(the same one used for the foot and the surface layer in §5):

```
R_disc = ρ₁ F / (4r)
F(K, h/r) = 1 + (4/πr) Σₙ Kⁿ [ r·atan(r/nh) − (nh/2)·ln(1 + r²/n²h²) ]   … (2.8)
```

The conductor near field (Sverak's `ρ/L_T` term) lies in the upper layer and keeps `ρ₁`,
so the equivalent resistivity is

```
ρ_eq = ρ₁ · (F/4r + 1/L_T) / (1/4r + 1/L_T)                              … (2.9)
```

which returns `ρ₁` exactly in uniform soil. **Pull inputs** on the grid page evaluates
(2.9) for the grid actually entered there. Checked against the two-layer numerical solver
for 48 grids (10–70 m, h = 1–30 m, ρ₂/ρ₁ = 0.1–25), the closed form with (2.9) is
conservative in every case, typically by 3–20 %.

**Any number of layers (version 1.4).** Over the images of the surface kernel the disc
factor is a sum, and since `∫₀^∞ e^(−λq)(1 − cos λr)/λ² dλ = r·atan(r/q) − (q/2)ln(1 + r²/q²)`
the whole sum is one smooth integral of the kernel `B(μ)` of (2.10):

```
F = 1 + (4/πr) ∫₀^∞ B(μ) (1 − cos 2μr)/(2μ²) dμ                         … (2.9a)
```

It equals the two-layer series (2.8) to 10⁻¹³ and needs no image series for three or four
layers. Tested against the three-layer numerical solver on 24 cases, the closed form with
(2.9) stays conservative in every one (+3 to +43 %). For the grid page a three- or
four-layer model can also be collapsed to an **equivalent two-layer** one for the grid in
hand: the top layer is kept and the layers below are replaced by the half-space that gives
the same disc factor at `r = √(A/π)` (within −2.1 to +3.3 % of the three-layer solver).

> **What version 1.1 did.** It weighted the layers by the *burial depth* of the
> electrodes. For the IEEE 80 Annex B grid in 2 m of 400 Ω·m that gave `ρ_eq = 400` whatever
> the lower layer — a closed-form `R_g` of +191 % over 100 Ω·m and **−66 % over 1600 Ω·m**,
> the unsafe direction. The depth-weighted rule is still offered, but only for small
> electrodes (a rod or two) whose size is comparable with their depth.

The numerical solver needs none of this: it uses the layered model directly.

**Check the fit first.** A two-layer curve is monotonic. If the measured curve falls and
then rises (or the reverse) the site has at least three layers, the fitted `ρ₁` and `h` are
not physical, and module 1 now says so and asks for confirmation before a poor fit is
pulled into the grid design.

### 2.8 Three and four layers

Some curves cannot be followed by two layers at all: they fall and then rise (H-type, a
conductive layer sandwiched between resistive ones) or rise and then fall (K-type). Since
version 1.4 module 1 fits three layers, and since 1.5 four.

**The forward model.** For more than two layers only the kernel of the Hankel integral
changes. Seen from above, each interface reflects like a single one, except that the stack
below gives it a reflection coefficient that depends on the spatial frequency `λ`.
Climbing from the deepest interface,

```
R_{N−1} = K_{N−1,N}
R_i(λ)  = [K_{i,i+1} + R_{i+1} x_{i+1}] / [1 + K_{i,i+1} R_{i+1} x_{i+1}],
          x_{i+1} = e^(−2λh_{i+1})
θ(λ)    = R₁ e^(−2λh₁) / (1 − R₁ e^(−2λh₁))                             … (2.10)

ψ(r) = ∫₀^∞ θ(λ) J₀(λr) dλ
ρₐ,Wenner(a) = ρ₁ [ 1 + 4a(ψ(a) − ψ(2a)) ]                         … (2.11)
```

with `K_{i,i+1} = (ρ_{i+1} − ρ_i)/(ρ_{i+1} + ρ_i)` and `h_i` the thickness of layer `i`. For two
layers `R₁ = K` and (2.11) is the image series (2.4). For three or more layers the image
series is double and, with a conductive layer between resistive ones, converges very slowly
(tens of thousands of terms), so the software sums the top interface's images exactly and
integrates the rest of the kernel by Gauss–Legendre quadrature. This reproduces (2.4) to
10⁻⁶ and the complete three-layer image series to 10⁻⁸, in under a millisecond per traverse.

**The fit** of `ρ₁, ρ₂, ρ₃, h₁, h₂` minimises the same relative misfit (2.6) in log space, by
Levenberg–Marquardt from 64 shape-based starts plus four built from the two-layer fit. It
found the global minimum in 30 of 30 random test earths.

**Is the extra layer real?** Two more parameters always lower the misfit. With `Φ₂`, `Φ₃` the
minimised misfits and `N` readings, the F test

```
F = [(Φ₂ − Φ₃)/2] / [Φ₃/(N − 5)]
p = ((N − 5)/(N − 5 + 2F))^((N − 5)/2)                           … (2.12)
```

keeps the third layer only when `p < 0.05` and the RMS falls by at least a fifth. For a
fourth layer the same test uses `Φ₃`, `Φ₄` and `N − 7`, so it needs at least nine readings.
On noisy synthetic traverses the rule added no false layer to 15 two-layer sites and found
the third layer in 14 of 15 three-layer sites. The example of §2.6 is the cautionary case:
three layers fit it at 1.05 % RMS against 4.5 %, but with six readings `p = 0.23`. Six
readings cannot establish a fifth parameter; *Automatic* keeps two layers and says why.
Choosing *Three layers* or *Four layers* forces the model onto the page but not past the
test: since 1.6.1 a warning above the results gives the supported model, and layers that
are not resolved, or that start deeper than twice the median depth of investigation (§2.2),
are flagged and drawn veiled. Forced onto the built-in example traverse (longest spacing
40 m), three layers put 2 Ω·m below 141 m and four put 66 Ω·m below 70 m: two different
guesses at ground the traverse never reached, both rejected at `p ≈ 0.8`.

**Equivalence.** A thin middle layer is seen only through its effect on the current that
crosses it. The covariance of the fit says which combination `h₂ρ₂^β` the readings fix:
`β ≈ −1` for a thin conductive layer (its conductance `S = h/ρ` is fixed) and `β ≈ +1` for a
thin resistive one (its transverse resistance `T = ρh`). The software prints `β`, names `S`
or `T` when it applies, and reports a parameter as not resolved when its own spread exceeds a
factor of 20.

**Checks.** On the two field traverses of Gonos and Stathopulos the three-layer fits match or
improve on the published genetic-algorithm, differential-evolution and simulated-annealing
fits (case B coincides with Li and Rao's within 1.5 % in every parameter). On the
thirteen-reading traverse of Zhang et al. a fourth layer is accepted (RMS 11.7 % → 3.8 %,
`p = 0.001`) and its thin layer's conductance agrees with both published fits within a factor
of 1.18; on Slaoui and Erchiqui's sounding a fourth layer is refused (`p = 1`).

**Why it matters.** On case B of Gonos and Stathopulos the two-layer fit is a 0.19 m skin of
20 523 Ω·m over 77.5 Ω·m. Put the 70 × 70 m Annex B grid on it and the numerical solver gives
`R_g` = 0.519 Ω; on the three-layer model the same grid has 0.959 Ω. The two-layer fit
understates the GPR by 46 % — the unsafe direction.


---

### 2.9 One bad reading, and more than one traverse (version 1.8)

**Robust fitting.** Least squares weighs every reading by the square of its misfit, so one
reading that is simply wrong — a pin in a stone, a buried pipe under the traverse, a
misread range — pulls the whole curve towards itself. The soil page now fits all the
readings, scales the residuals rᵢ (in %) by their median absolute deviation,

    σ̂ = 1.4826 · median|rᵢ − median r|,

and sets aside the worst reading if it lies more than max(3σ̂, 5 %) from the median, then
refits. One reading goes at a time — a large outlier distorts the residuals of its
neighbours, and removing several at once would discard good readings with it — and never
more than a fifth of them, nor so many that the model loses its spare degrees of freedom.
The page lists what it set aside and the refitted value at that spacing, so the reading can
be checked on the field sheet or measured again. A reading is never discarded silently.

On the example traverse with the 6 m reading changed from 156 to 260 Ω·m, the plain fit
has an RMS error of 10.6 % and puts the interface at 3.2 m; the robust fit sets that one
reading aside and returns ρ₁ = 297 Ω·m, ρ₂ = 108 Ω·m, h = 2.51 m — the clean values.

**Several traverses.** Every inversion on this page assumes horizontal layers. IEEE Std 81
asks for traverses in more than one direction precisely because that assumption can fail.
Give each reading its traverse name and the page fits all of them together *and* each
traverse with three or more readings on its own. When the separate fits disagree by more
than a factor of 1.5 — in ρ₁, in ρ₂ or in the readings at the spacings they share — the
soil varies across the site, which no layered model represents. Design with the worst
traverse where the electrode is, or model the zones separately.

## 3. Fault current — module 2
### 3.1 Why symmetrical components

A single line-to-earth fault is an unbalanced condition, so the three phases cannot be
analysed independently. Fortescue's transformation splits any unbalanced set into three
balanced sets — positive, negative and zero sequence — each of which can be analysed with
an ordinary single-phase circuit.

The **zero-sequence** network is the one that matters here, because zero-sequence current
is by definition the current that is identical in all three phases and therefore must
return through earth and through any neutral or shield conductors. Earthing is, in a
precise sense, the study of the zero-sequence return path.

### 3.2 Line-to-earth fault current

Connecting the three sequence networks in series (the standard result for a single
line-to-earth fault) gives

```
I_k1" = √3 · c · Uₙ / |Z₁ + Z₂ + Z₀ + 3Z_f|          … (3.1)
```

Points to draw students' attention to:

- `3Z_f`, not `Z_f` — fault impedance appears three times because the full fault current
  `3I₀` passes through it while each sequence network carries only `I₀`.
- The **voltage factor `c`** (1.1 for MV/HV maximum) accounts for tap settings, load, and
  the tolerance on the nominal voltage. It is a deliberate conservatism, not physics.
- `Z₀` is usually very different from `Z₁`: for a line with earth return it may be 3× as
  large; for a delta-star transformer it depends entirely on the winding connection. Get
  `Z₀` wrong and the entire earthing design is wrong. This is the number most worth
  checking against the utility's own study.

Special case worth showing: if `Z₀ = Z₁ = Z₂`, then (3.1) reduces to `c·Uₙ/(√3·Z₁)`,
which is the three-phase fault current. The software's test suite checks exactly this.

### 3.3 The DC offset and the decrement factor

A short circuit does not start as a clean sinusoid. Because the circuit is inductive, the
current cannot jump, so a decaying DC component appears:

```
i(t) = √2 I [ cos(ωt + θ) − e^(−t/T_a) cos θ ],     T_a = X/(ωR) = (X/R)/(2πf)
```

The earthing system does not care about the peak; it cares about **heating and about the
rms value over the fault duration**, because both the tolerable body current and the
conductor heating are rms/energy quantities. So compute the rms of the whole waveform over
`0 … t_f`:

```
(1/t_f) ∫₀^{t_f} (√2 I e^{−t/T_a})² dt = 2I² · (T_a/2)(1 − e^{−2t_f/T_a}) / t_f
```

Adding the ac part (`I²`) and taking the ratio to the symmetrical rms gives

```
D_f = √[ 1 + (T_a/t_f)(1 − e^{−2 t_f / T_a}) ]          … (3.2)
```

**Behaviour to point out:**
- `t_f ≫ T_a` (a slow-clearing fault): `D_f → 1`. The DC offset has died long before the
  fault clears, so it contributes nothing.
- `t_f ≪ T_a` (a fast-clearing fault on a stiff, inductive system): expand the exponential
  to get `D_f → √2`. The current is essentially fully offset for the whole fault.
- Therefore **fast clearing makes `D_f` worse while making the tolerable voltage better**,
  and the tolerable voltage wins, because it goes as `1/√t` while `D_f` is capped at √2.
  This is worth showing students explicitly, because the two effects look like they might
  cancel and they do not.

![Figure 6 — The decrement factor against fault duration for several X/R ratios. At the usual 0.5 s clearing time the DC offset contributes only a few percent; below about 0.1 s it becomes significant.](figures/fig06_decrement.png)

*Figure 6 — The decrement factor against fault duration for several X/R ratios. At the usual 0.5 s clearing time the DC offset contributes only a few percent; below about 0.1 s it becomes significant.*

### 3.4 The split factor `S_f`

Not all of the fault current returns through the earth grid. Any overhead earth wire,
cable sheath or distribution neutral bonded to the grid offers a metallic path in parallel
with it. The split factor is the fraction that actually goes into the soil:

```
S_f = |Z_r| / |Z_r + R_g|          … (3.3)
```

a plain current divider between the metallic return impedance `Z_r` and the grid
resistance `R_g`.

`S_f` is one of the most influential and most-often-fudged numbers in the whole design.
With no metallic return, `S_f = 1`. A transmission substation with eight shielded lines
may see `S_f ≈ 0.12` — meaning **88 % of the fault current never enters the soil**, and
the grid can be eight times smaller than a naive design would suggest. Earthing System offers
the IEEE 80 Annex C guide values as one-click chips, but a real project should use the
utility's own study.

### 3.5 Assembling the grid current

```
I_g = S_f · C_p · 3I₀        I_G = D_f · I_g          … (3.4)
```

`C_p` is the future-growth factor: fault levels rise as networks are reinforced, and an
earth grid is buried in concrete for forty years. `C_p = 1.0` means today's fault level,
`C_p = 1.25` designs for a 25 % increase.

### 3.6 Worked example

20 kV system, `S_k" = 500 MVA`, `X/R = 10`, `X₀/X₁ = 3`, `t_f = 0.5 s`, 50 Hz,
`S_f = 0.6`, `C_p = 1.0`:

```
Z₁      ≈ 0.0796 + j0.796 Ω        (from Z = c·Uₙ²/S_k")
Z₀      ≈ 0.0796 + j2.388 Ω
I_k1"   = √3 · 1.1 · 20000 / |Z₁+Z₂+Z₀| ≈ 8.69 kA
T_a     = 10/(2π·50) = 0.0318 s
D_f     = √[1 + (0.0318/0.5)(1 − e^(−31.4))] = 1.031
I_g     = 0.6 × 8.69 = 5.21 kA
I_G     = 1.031 × 5.21 = 5.37 kA
```

Note how little `D_f` contributes at 0.5 s and how much `S_f` does. Students consistently
over-focus on the first and under-focus on the second.

---

### 3.7 The split factor from the shield wire, and where the fault is (version 1.8)

Table C.1 of IEEE Std 80 is a set of answers for typical lines. Behind it is a ladder: the
shield wire of each span has a series impedance Z_s = z_s·ℓ (Carson, with earth return),

    z_s = r + π²·10⁻⁴·f + j·4π·10⁻⁴·f·ln(D_e/GMR)   Ω/km,   D_e = 658.5·√(ρ/f),

every tower ties it to earth through its footing resistance R_t, and the far end is bonded
to the remote station. An infinite ladder has the driving-point impedance (Endrenyi)

    Z∞ = Z_s/2 + √(Z_s·R_t + Z_s²/4).

The phase current also induces a voltage in the shield wire through the mutual impedance
z_m (the same formula with the phase-to-shield distance in place of the GMR), which drives a
share k = |z_m/z_s| of the return current along the wire without its ever entering the
soil.

The fault-current page now solves that ladder node by node — the towers, the station grid
R_g, the remote station — with the fault current injected where the fault is, each
source's zero-sequence current returning to its own neutral, and an EMF −z_m·I_phase in
every span the phase current flows through. The grid current is V₀/R_g. Moving the fault
from the station out along the line answers the question clause 15.9 raises: for a fault
inside the station only the *remote* contribution returns through the soil, but for a fault
at a tower a few kilometres out the station's *own* source returns its current through the
soil to its neutral, and that can be several times larger. On a 132 kV, 20 km line with
R_t = 15 Ω and R_g = 0.5 Ω the station fault puts 1.3 kA into the grid and a fault 4 km out
puts 6.3 kA. The design current is the largest of the sweep.

**Real lines (version 1.8.5).** Nothing in the nodal solution needs equal spans or equal
footings: the span impedances Z_k = z_s·ℓ_k and the EMFs −z_m·ℓ_k·I enter span by span, and
each tower's own R_t,k enters its node. Measured footing resistances matter most near the
station — a poor tower in the first kilometre shifts more of a station fault back into the
grid. The other outgoing lines are ladders too. Each is solved on its own for its input
impedance seen from the station,

    Z_in,j = 1/Y_0  of the ladder (Z_s,j, R_t,j, …, R_remote,j)  with no source in it,

and the admittances Σ 1/Z_in,j are added to the station node in parallel with 1/R_g. The
mutual coupling between the shield wires of different lines is neglected for lines on
different routes; it is small when the lines leave in different directions. With equal spans
and footings the result is the uniform one exactly.

**Coupled shield wires (version 1.9.2).** Two shield wires bonded at every tower carry the same
voltage drop, so with their impedance matrix Z the bundle's current is 1ᵀZ⁻¹1 times that drop:

    z_bundle = (z_s + z_m(d_sw))/2       for two wires d_sw apart,

not z_s/2 — the mutual impedance of two wires ten metres apart is a third of the self
impedance or more, and z_s/2 put the ladder impedance of a two-wire line 14–19 % low. Lines that
share the corridor over the whole route are solved together. Every shield wire w is a
conductor of the wire-level matrix Z (Carson self and mutual impedances, Ω/km) and couples to
the faulted phase through z_p,w; the wires of a line meet at its towers, so with B mapping
wires to lines the lines' span admittance is Y = BᵀZ⁻¹B/ℓ and the phase current drives
J = −BᵀZ⁻¹z_p·I_phase in each span:

    I_lines = Y (V_k − V_{k+1}) + J,

one node per line and tower, the station and the remote station shared. Far from both ends
the drop along every wire vanishes and the wires carry −Z⁻¹z_p·I_phase, the classical
coupling; the solution reproduces that to 10⁻⁶ and an independent solution with every wire of
every span its own branch to 10⁻¹⁰. On a 132 kV, 20 km line (R_t = 15 Ω, R_g = 0.5 Ω) a
parallel line 30 m away lowers the station-fault grid current from 1.30 to 0.91 kA and the worst
from 6.29 to 4.70 kA; as an uncoupled ladder it gave 1.10 and 5.33 kA.

### 3.8 Earth-fault current returning in cable sheaths (version 1.8.5)

When the station is fed by cable the sheaths take the place of the shield wire. For a fault
at the far end B fed from A, the core carries I_f from A to B and induces −z_m·ℓ·I_f in the
sheath circuit of every section, where

    z_s = r_s/n + π²·10⁻⁴·f + j·4π·10⁻⁴·f·ln(D_e/GMR_sheaths)     Ω/km
    z_m =         π²·10⁻⁴·f + j·4π·10⁻⁴·f·ln(D_e/GMD_core,sheaths)

with all n sheaths in parallel (their geometric mean radius together: r_m for a three-core
cable, (r_m·s²)^{1/3} for trefoil, and so on). The sheaths are earthed at A (R_A), at B (R_B)
and at each joint or link box (R_j), which makes the same ladder as §3.7, and its node
potentials give the current into each earth. For a single section and a three-core cable
the result is exactly the EREC S34 Appendix D form

    S_f = |ℓ·r_c| / |ℓ·z_c + R_A + R_B|        (source at A, D.2.1)
    S_f = |ℓ·r_c + R_A| / |ℓ·z_c + R_A + R_B|  (source beyond A, D.2.3)

with z_c and r_c those of the sheath. A cable bonded at one end only has no sheath circuit
for this current, so S_f = 1: the whole fault current goes through the soil, which is why
single-point bonded cables are laid with an earth-continuity conductor. As the cable gets
longer S_f falls towards the reduction factor |1 − z_m/z_s|.

**Cross-bonded sheaths (version 1.9.4).** A cross-bonded cable is split into minor sections,
three to a major section; at the link boxes between them each sheath is connected to the
sheath of the next cable position, and the sheaths are earthed together at the major joints.
The model keeps every sheath of every minor section k as a branch of length ℓ_k, with the
branch impedance matrix ℓ_k·Z, where Z_ii = r_s + π²·10⁻⁴·f + j·4π·10⁻⁴·f·ln(D_e/r_m) and
Z_ij the same without r_s at the distance between sheaths i and j, and the source
−ℓ_k·z_ci·I_f from the faulted core (z_ci at the distance from the core to sheath i, r_m for
its own sheath). The nodes are A, B, the major joints, and at each link box one node per
cable position and circuit, where position p of section k continues as position p + 1 of
section k + 1. The nodal equations (A_b·Y_b·A_bᵀ + earths)·V = injections − A_b·Y_b·E, with
Y_b the inverse of the branch matrices, give the earth currents, the sheath currents and the
link-box voltages. The link boxes are open, as with the sheath voltage limiters not
conducting, and the cores are not transposed. With equal minor sections every sheath path
visits each position once, its impedance is the mean of the matrix rows, and the result is
that of the both-ends model with earths at the major joints, which the program reproduces to
10⁻¹². In trefoil the paths' impedance matrix is αI + β11ᵀ whatever the minor lengths, so
the split is independent of them while the link-box voltages are not.

## 4. Conductor sizing — module 3
### 4.1 The adiabatic assumption

A fault lasts a fraction of a second. In that time essentially no heat escapes the
conductor into the soil, so all the `I²R` energy goes into raising the conductor's own
temperature. That is the **adiabatic assumption**, and it is what makes the problem
solvable in closed form.

Take a conductor of area `A`, length `L`, density `δ`, specific heat `c`, resistivity
`ρ_e(T) = ρ₂₀[1 + α(T − 20)]`. In time `dt`:

```
energy in  = I² · (ρ_e L / A) · dt
energy stored = (δ A L) · c · dT
```

Equating and separating variables:

```
I² dt / A² = (δ c / ρ₂₀) · dT / [1 + α(T − 20)]
```

Integrating from `T_a` to `T_m`, and defining `K₀ = 1/α − 20` so that
`1 + α(T − 20) = α(T + K₀)`:

```
I² t / A² = (δ c) / (ρ₂₀ α) · ln[ (K₀ + T_m) / (K₀ + T_a) ]
```

Writing `TCAP = δ·c` (the volumetric heat capacity) and rearranging:

```
A = I / √( (TCAP·10⁻⁴)/(t_c · α_r · ρ_r) · ln[(K₀+T_m)/(K₀+T_a)] )       … (4.1)
```

which is IEEE Std 80-2013 Equation (37). The `10⁻⁴` is a unit conversion only
(`TCAP` in J/(cm³·°C), `ρ_r` in µΩ·cm, `A` in mm², `I` in kA).

**Everything in that formula is now meaningful rather than magic**: `TCAP` is how much
heat the metal can absorb per degree, `ρ_r` is how much heat it generates, `α_r` describes
how the generation worsens as it heats up, and the logarithm is the accumulated effect of
that feedback between ambient and the limit temperature.

### 4.2 The IEC form is the same physics

IEC 60364-5-54 writes it as

```
S = √(I² t) / k
k = √( Q_c(B + 20)/ρ₂₀ · ln[1 + (T_f − T_i)/(B + T_i)] )               … (4.2)
```

with `B = 1/α₀`. Compare term by term with (4.1): `Q_c` is `TCAP`, `B + 20` plays the role
of `K₀ + 20`, and the logarithm is identical after algebra. The IEC simply pre-computes
the whole square root into a single tabulated `k`, because in an LV installation the
material and insulation combinations are few and standard.

Consequences for teaching: the two standards **will not** give the same answer, and it is
not a mistake. IEEE 80 lets you choose `T_m` freely and use the true material constants;
IEC fixes `T_f` at the insulation limit. For a bare buried copper conductor IEEE 80 with
`T_m = 1084 °C` allows a much smaller conductor than IEC with `T_f = 500 °C`. Earthing System
computes both and selects the larger, which is the defensible engineering position.

### 4.3 What actually limits `T_m` in practice

Rarely the metal. Usually:

| Limit | `T_m` | Why |
|---|---|---|
| Exothermic weld | 1083 °C | The joint is as good as the parent metal |
| Brazed joint | 450 °C | Filler alloy softens |
| Bolted / pressure joint | 250 °C | Contact pressure relaxes, resistance runs away |

A grid welded exothermically can use half the copper of the same grid bolted together.
This one dropdown on the conductor page changes the material cost of a substation more
than any other single input.

![Figure 7 — Conductor sizing. (a) The required area against fault duration for three materials. (b) The same 10 kA, 0.5 s duty sized for three joint types — the joint, not the metal, usually sets the size.](figures/fig08_conductor.png)

*Figure 7 — Conductor sizing. (a) The required area against fault duration for three materials. (b) The same 10 kA, 0.5 s duty sized for three joint types — the joint, not the metal, usually sets the size.*

### 4.4 The other three constraints

Thermal sizing is necessary but not sufficient. Earthing System also applies:

- **Mechanical and corrosion minima** (IEC 60364-5-54 Table 54.1). A buried conductor not
  protected against corrosion must be at least 25 mm² copper regardless of what the
  thermal calculation says — because it has to still be there in thirty years.
- **The simplified PE rule** (Table 54.2): `S ≤ 16 → S_PE = S`; `16 < S ≤ 35 → 16`;
  `S > 35 → S/2`. This is a shortcut that is always at least as conservative as the
  adiabatic calculation for the standard material pairings.
- **Bonding conductor rules** (§544): main protective bonding at least half the earthing
  conductor, minimum 6 mm², need not exceed 25 mm² copper.

The software reports all of them and selects the largest. When teaching, make students
predict which one will bind before they press the button — for domestic work it is almost
always the mechanical minimum, and for substations almost always the thermal one.

---

## 5. Safety criteria — the heart of module 4

### 5.1 The surface layer, and why it works

Spread 100 mm of crushed rock (`ρ_s` ≈ 2500 Ω·m dry) over the soil (`ρ` ≈ 100 Ω·m) and the
foot resistance rises enormously — the tolerable touch voltage in (1.5) is dominated by
`1.5 ρ_s` as soon as `ρ_s` is large. This is by far the cheapest safety measure available:
a lorry of gravel against tonnes of copper.

But the layer is thin, so the foot does not see pure `ρ_s`. Some current leaks through into
the soil beneath. The **derating factor** `C_s` accounts for this. IEEE 80 gives an
empirical fit to the exact series solution:

```
C_s = 1 − 0.09 (1 − ρ/ρ_s) / (2 h_s + 0.09)          … (5.1)
```

Read it as a *fraction of the ideal benefit that the layer actually delivers*:

- `h_s → ∞`: `C_s → 1`. A thick layer gives the full benefit.
- `h_s → 0`: `C_s → 1 − (1 − ρ/ρ_s) = ρ/ρ_s`, so `C_s ρ_s → ρ`. Correct — no layer means
  the foot sees native soil.
- `ρ_s = ρ`: `C_s = 1` and the layer does nothing, as it should.
- The 0.09 is `2b/... ` in disguise — it comes from the 0.08 m foot radius.

**The saturation is the teaching point.** Going from 50 mm to 100 mm buys a lot; going
from 200 mm to 300 mm buys almost nothing. Earthing System's remedy text computes the exact
thickness needed and will tell you when no achievable thickness can close the gap.

**A trap worth teaching:** `ρ_s` for crushed rock collapses when it is wet or contaminated
with fines. Washed granite is ~4 MΩ·m dry but ~1300 Ω·m wet. Always design with the wet
value unless the yard is roofed.

![Figure 8 — (a) The surface-layer derating factor against thickness. The benefit saturates: beyond about 150 mm a thicker layer buys very little. (b) Tolerable touch and step voltages against clearing time, showing the 1/√t behaviour and the difference between the 50 kg and 70 kg criteria.](figures/fig07_tolerable.png)

*Figure 8 — (a) The surface-layer derating factor against thickness. The benefit saturates: beyond about 150 mm a thicker layer buys very little. (b) Tolerable touch and step voltages against clearing time, showing the 1/√t behaviour and the difference between the 50 kg and 70 kg criteria.*

### 5.2 The two body weights

`k = 0.116` (50 kg) or `0.157` (70 kg). The 50 kg criterion gives tolerable voltages about
26 % lower and is the conservative choice where the public may be present, or where the
workforce may include lighter individuals. This is a **policy decision, not a calculation**
— make students state and justify their choice rather than accepting the default.

### 5.3 Worked example (IEEE Std 80-2013 Annex B)

`ρ = 400 Ω·m`, `ρ_s = 2500 Ω·m`, `h_s = 0.102 m`, `t_s = 0.5 s`, 70 kg:

```
C_s      = 1 − 0.09(1 − 400/2500)/(2×0.102 + 0.09) = 0.743
E_touch  = (1000 + 1.5 × 0.743 × 2500) × 0.157/√0.5 = 840 V
E_step   = (1000 + 6.0 × 0.743 × 2500) × 0.157/√0.5 = 2696 V
```

The ratio `E_step/E_touch = 3.2`. Ask students why it is not exactly 4 — the answer is the
fixed 1000 Ω body resistance, which is a larger fraction of the touch circuit than of the
step circuit.

---

## 6. Grid resistance — module 4
### 6.1 From a hemisphere to a grid

For a hemisphere of radius `r`, (1.1) gives `R = ρ/(2πr)`. A real grid is a flat mesh, not
a hemisphere, but the same idea holds: at large distance the grid looks like a single
electrode of some equivalent size, and close in the resistance depends on how much metal
there is. Sverak's expression captures both limits:

```
R_g = ρ [ 1/L_T + (1/√(20A)) ( 1 + 1/(1 + h√(20/A)) ) ]          … (6.1)
```

- The `1/L_T` term is the **local** contribution: more buried metal, less resistance. It
  dominates for a small grid with a lot of conductor.
- The `1/√(20A)` term is the **far-field** contribution: it depends only on the area, not
  on how much copper you put in it. It dominates for a large grid.
- The bracket with `h` is the burial-depth correction, tending to 2 at the surface and to
  1 as the grid goes deep.

**The most important design consequence in the whole subject** falls straight out of this:
once the grid is large, `R_g` is set by the *area* and adding more conductor inside that
area barely changes it. Doubling the copper in a 70 × 70 m grid changes `R_g` by a few
percent. So — **you do not add copper to reduce resistance; you add copper to even out the
potential.** Students who understand this stop trying to fix touch-voltage failures by
"adding more earth".

![Figure 9 — The IEEE 80 Annex B grid, without and with perimeter rods. Adding twenty 7.5 m rods changes the resistance by only about 5 %, but it changes the mesh voltage far more — because the rods raise the effective mesh length and set K_ii to 1.](figures/fig09_layout.png)

*Figure 9 — The IEEE 80 Annex B grid, without and with perimeter rods. Adding twenty 7.5 m rods changes the resistance by only about 5 %, but it changes the mesh voltage far more — because the rods raise the effective mesh length and set K_ii to 1.*

### 6.2 Schwarz — when rods are present

Sverak treats all buried metal alike. Schwarz splits it into the horizontal grid (`R₁`),
the rod bed (`R₂`) and their mutual resistance (`R_m`), then combines them as two coupled
electrodes:

```
R_g = (R₁R₂ − R_m²) / (R₁ + R₂ − 2R_m)          … (6.2)
```

This is the standard formula for two coupled conductors — not a parallel combination,
because the grid and the rods occupy overlapping volumes of soil and therefore "compete"
for the same current paths. `R_m` quantifies that competition; if you (wrongly) set
`R_m = 0`, (6.2) collapses to the parallel formula and gives an optimistic answer.

### 6.3 Why rods earn their keep in layered soil

In uniform soil, rods add little that the same length of horizontal conductor would not.
Their value appears when `ρ₂ < ρ₁`: a 6 m rod through a 2 m resistive top layer reaches
soil that may be five times more conductive, and its resistance drops accordingly. Because
the closed-form equations use a single equivalent resistivity, **they systematically
understate this benefit** — which is exactly the case where the numerical solver, with the
true two-layer Green's function, earns its place.

---

## 7. Mesh and step voltage — module 4
This is the part of IEEE 80 that looks most like arbitrary curve-fitting. It is not — every
factor has a job. Here is what each one does.

### 7.1 The physical picture

Inside the grid the soil potential is not flat. Directly above a buried conductor it is
close to GPR; midway between two conductors it sags. The sag is the touch voltage. It is
largest **at the centre of a corner mesh**, because that point has the fewest conductors
near it — the corner has metal on only two sides instead of four.

So the design quantity `E_m` is defined as *the touch voltage at the centre of the corner
mesh*. It is not an average; it is the worst case.

![Figure 10 — Earth-surface potential computed by the boundary-element solver for the Annex B grid. The potential is nearly flat inside the grid and falls steeply outside it; the small dips are the mesh centres.](figures/fig10_surface_potential.png)

*Figure 10 — Earth-surface potential computed by the boundary-element solver for the Annex B grid. The potential is nearly flat inside the grid and falls steeply outside it; the small dips are the mesh centres.*

### 7.2 The mesh factor `K_m`

```
K_m = (1/2π) { ln[ D²/(16hd) + (D+2h)²/(8Dd) − h/(4d) ]
               + (K_ii/K_h) ln[8/(π(2n−1))] }                       … (7.1)
```

Term by term:

- `D²/(16hd)` — the direct contribution of the two conductors bounding the mesh, from the
  potential of a buried line source and its image. The `D²` says the sag grows with the
  square of the spacing: **halving `D` is worth far more than adding conductor anywhere
  else.**
- `(D+2h)²/(8Dd)` — the image of those conductors in the earth's surface.
- `−h/(4d)` — a correction for the finite burial depth.
- `ln[8/(π(2n−1))]` — the contribution of all the *other* conductors in the grid, which
  raise the potential at the corner mesh and therefore reduce the sag. It gets more
  negative as `n` grows, i.e. a bigger grid helps its own corner.
- `K_ii` — a correction for grids **without** rods on the perimeter. With perimeter rods
  `K_ii = 1`; without, `K_ii = 1/(2n)^(2/n) < 1`, which reduces the correcting term. This
  is the mathematical statement of the rule "always put rods in the corners".
- `K_h = √(1 + h/h₀)`, `h₀ = 1 m` — depth weighting.

### 7.3 The geometric factor `n` and the irregularity factor `K_i`

```
n = n_a · n_b · n_c · n_d,     n_a = 2L_C/L_p          … (7.2)
K_i = 0.644 + 0.148 n                                   … (7.3)
```

`n_a` is an "effective number of parallel conductors": total conductor length divided by
half the perimeter. For a square grid with 11 conductors each way, `n_a = 2×1540/280 = 11`
— it recovers the actual conductor count exactly, which is a good sanity check to show
students. `n_b`, `n_c`, `n_d` are shape corrections and equal 1 for a square grid; they
depart from 1 for rectangles, L-shapes and irregular outlines.

`K_i` is an empirical correction for the fact that current does **not** leave the grid
uniformly. It concentrates at the edges and especially at the corners — the same
edge-singularity behaviour you meet in electrostatics. `K_i` grows linearly with `n`
because a larger grid has proportionally more of its current forced out at the perimeter.

![Figure 11 — The same solution as a surface. The 'table top' shape is the whole objective of an earth grid: a flat interior means small touch voltages, and the steep edges are where step voltage is worst.](figures/fig11_potential_3d.png)

*Figure 11 — The same solution as a surface. The 'table top' shape is the whole objective of an earth grid: a flat interior means small touch voltages, and the steep edges are where step voltage is worst.*

### 7.4 The step factor `K_s`

```
K_s = (1/π) [ 1/(2h) + 1/(D+h) + (1/D)(1 − 0.5^(n−2)) ]          … (7.4)
```

The `1/(2h)` term dominates and it is the whole story: the steepest surface gradient sits
directly above the outermost conductor, and it is inversely proportional to burial depth.
**Depth is the step-voltage lever; spacing is the touch-voltage lever.**

### 7.5 The effective lengths

```
E_m = ρ K_m K_i I_G / L_M          E_s = ρ K_s K_i I_G / L_S
```

`L_M` and `L_S` are *not* the physical conductor lengths — they are the lengths weighted
by how much each element contributes to the quantity in question:

```
L_M = L_C + L_R                                       (no perimeter rods)
L_M = L_C + [1.55 + 1.22 (L_r/√(L_x²+L_y²))] L_R      (rods on the perimeter)
L_S = 0.75 L_C + 0.85 L_R
```

The `1.55 + 1.22(...)` weighting says a perimeter rod is worth about **1.6 to 1.8 times
its own length** of horizontal conductor for controlling touch voltage — because it is at
the corner, where the current concentrates, and because it reaches deeper soil. In `L_S`
the weights are *less* than one (0.75 and 0.85), because for step voltage the far parts of
the grid help less than the local conductor does.

### 7.6 How to read a failure

When `E_m` exceeds `E_touch`, Earthing System tells you which lever to pull and by how much.
The physics behind each:

| Lever | Effect | Why |
|---|---|---|
| Reduce `D` | Strong | `K_m` falls roughly as `ln D²`, and `L_M` rises |
| Add perimeter rods | Strong | `K_ii → 1` and `L_M` gains 1.6× the rod length |
| Thicker surface layer | Moderate, saturating | Raises `C_s` and so `E_touch` |
| Faster clearing | Strong | `E_touch ∝ 1/√t_s` |
| Lower `S_f` | Strong | `E_m ∝ I_G` |
| Bigger area | Weak for touch | Lowers `R_g` and GPR but barely changes the local sag |

The last row is the one students get wrong most often.

![Figure 12 — The principal design lever. Mesh and step voltage against conductor spacing for the Annex B case, with the tolerable limits. The design becomes compliant when the mesh-voltage curve crosses below its limit.](figures/fig14_sweep.png)

*Figure 12 — The principal design lever. Mesh and step voltage against conductor spacing for the Annex B case, with the tolerable limits. The design becomes compliant when the mesh-voltage curve crosses below its limit.*

---

## 8. The numerical solver — module 5
### 8.1 What the closed forms cannot do

IEEE 80's equations assume a rectangular (or L/T-shaped) grid, uniform soil and — crucially
— **uniform current leakage from every part of the electrode**. Real problems break all
three: sites are irregular, soil is layered, and current leaves the perimeter far more
readily than the middle.

### 8.2 The method of moments

Discretise the buried metal into `N` short cylindrical segments. Assume each segment `j`
leaks a uniform current `I_j` into the soil. Because the metal is bonded, every segment
must sit at the **same** potential `V`. That gives `N` equations

```
Σ_j P_ij I_j = V     for every i          … (8.1)
```

plus one more, current conservation, `Σ_j I_j = I_G`. Together:

```
⎡ P   −1 ⎤ ⎡ I ⎤   ⎡ 0  ⎤
⎣ 1ᵀ   0 ⎦ ⎣ V ⎦ = ⎣ I_G ⎦          R_g = V / I_G          … (8.2)
```

`P_ij` is the average potential appearing on segment `i` per ampere leaked from segment
`j`. This is a **potential-coefficient matrix**, exactly analogous to the capacitance
coefficient matrix in electrostatics — and indeed the two problems are mathematically
identical, because both solve Laplace's equation with the same boundary conditions.

![Figure 13 — The boundary-element formulation. (a) The electrode is divided into segments, each leaking a uniform current, all held at one potential. (b) The insulating soil surface is enforced by an image source of the same sign at the mirrored depth.](figures/fig15_bem_method.png)

*Figure 13 — The boundary-element formulation. (a) The electrode is divided into segments, each leaking a uniform current, all held at one potential. (b) The insulating soil surface is enforced by an image source of the same sign at the mirrored depth.*

### 8.3 The Green's function and the image

The kernel is the potential of a point current source in a half-space. The soil surface is
a boundary with no current crossing it (air does not conduct), which is enforced by placing
an **image source of the same sign** at the mirrored depth — the opposite sign convention
to the grounded-plane problem in electrostatics, and a good exam question:

```
G(field, source) = ρ/(4π) [ 1/√(r_h² + (z−z')²) + 1/√(r_h² + (z+z')²) ]   … (8.3)
```

with `z` measured downwards from the surface. Note `ρ/4π`, not `ρ/2π` — the factor of two
that turns it into (1.1) comes from the image term when both points are on the surface.

**Two-layer soil.** With a lower layer of resistivity `ρ₂` below depth `h`, and
`K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁)`, the image series depends on which layer the source and the field
point are in (image depth written as `±z' + shift`):

```
both in layer 1   ρ₁/4π  Σ Kⁿ [ images at ±z' ± 2nh ]            (n = 0 is (8.3))
field in layer 2  ρ₁(1+K)/4π  Σ Kⁿ [ z' − 2nh,  −z' − 2nh ]
source in layer 2 ρ₁(1+K)/4π  Σ Kⁿ [ z' + 2nh,  −z' − 2nh ]
both in layer 2   ρ₂/4π [ z',  −K at 2h − z',  (1−K²) Σ Kⁿ at −z' − 2nh ]
```

Every conductor that crosses the interface is split there, and each segment uses the
function of its own layer, including `ρ₂` in its self term. (Version 1.1 applied the
first line to every segment, so rods below the interface saw `ρ₁`: for the Annex B grid
with twenty 7.5 m rods over 100 Ω·m, `R_g` came out 2.0 % low.) The potential is
continuous across the interface to six digits, which is a useful test of the four
functions.

### 8.4 The self term — a derivation worth doing

For `i = j` the integral is singular and must be done analytically. For a segment of length
`L` and radius `a` with uniform current, the average potential on it is

```
V = ρI/(4πL²) ∫₀^L ∫₀^L ds ds' / √((s−s')² + a²)
  = ρI/(4πL²) · 2[ L·asinh(L/a) − (√(L²+a²) − a) ]
  ≈ ρ/(2πL) [ ln(2L/a) − 1 ] · I     for a ≪ L          … (8.4)
```

**Check it against Dwight.** Take a vertical rod of length `L` from the surface. Its image
is a collinear rod of the same length just above. The image contribution is

```
ρI/(4πL²) ∫₀^L ∫₀^L ds ds'/(s+s') = ρI/(4πL²) · 2L ln2 = ρ I ln2/(2πL)
```

so the total is

```
R = ρ/(2πL)[ln(2L/a) − 1 + ln 2] = ρ/(2πL)[ln(4L/a) − 1]
```

which is exactly Dwight's rod formula, and identical to IEEE 80's `ρ/(2πL)[ln(8L/d) − 1]`
since `d = 2a`. The software reproduces this to better than 0.2 % with a single segment —
a test worth running in front of a class.

### 8.5 Collocation versus Galerkin — a real trap

The cheap way to fill `P` is **collocation**: evaluate the potential at the *midpoint* of
segment `i`. For distant sources that is fine. For close sources it is badly wrong, because
the potential varies strongly across the segment and the midpoint value is not the average.

Concretely: for a segment and its own surface image at depth 0.8 m, midpoint collocation
underestimates the image contribution by about 21 %. Accumulated over a whole grid this
biased the computed earth resistance **5 to 15 % low** — an error in the unsafe direction.

Earthing System therefore uses **Galerkin double quadrature** (averaging over the field segment
as well as the source segment) for all near pairs, including the self-image pair, and keeps
cheap collocation only for far pairs. This is the single most important implementation
detail in `bem.py`, and it is the sort of thing that separates a solver you can trust from
one that merely runs.

### 8.6 Layered soil

The same image series as §2.4, now in three dimensions:

```
G = ρ₁/(4π) Σ(n=−N..N) K^|n| [ 1/√(r_h² + (z − z' − 2nh)²)
                             + 1/√(r_h² + (z + z' − 2nh)²) ]          … (8.5)
```

At `n = 0` this reduces to (8.3). At `K = 0` all other terms vanish. Both are checked in
the test suite, and both are good student exercises.

**Three and four layers (versions 1.4–1.5).** The two-layer formulas are one rule applied to
every reflection, and the rule builds the Green's function of any number of layers. Treat
the field of the source as waves, each the potential `a/R` of a point source, travelling up
or down. A wave in layer `L` meeting the plane to layer `M` splits into a reflected wave,
`R = (ρ_M − ρ_L)/(ρ_M + ρ_L)` times as strong with its source mirrored in the plane, and a
transmitted one, `1 + R` times as strong with its source unmoved; the surface reflects with
`R = +1`. The field in layer `j` of a unit source in layer `i` is then

```
G_ij = ρ_i/(4π) Σ_k a_k / √(r_h² + (z − s_k z' − D_k)²)                  … (8.6)
```

with a sign `s_k = ±1` and a shift `D_k` (a sum of `±2d` over the interface depths) for each
image. The software traces the waves plane by plane and merges those that coincide. With a
conductive layer between resistive ones the series is long (123 000 images above 10⁻¹⁰ for
300/30/3000 Ω·m), so images near the electrode are kept one by one, those further away are
merged in bins, and all the rest are taken from the spectral (Hankel-transform) solution,
tabulated once per soil model. Checks: against an independent spectral computation to
3.5 × 10⁻¹⁰; a three-layer model with two equal layers reproduces the two-layer solver to
4 × 10⁻⁵; rods crossing both interfaces agree with an axisymmetric finite-volume solution
within 0.13 %. Every conductor is split at every interface, and each segment uses the
resistivity of its own layer in its self term.

### 8.7 What to compare, and why it matters

After solving, evaluate the touch voltage at the centre of the corner mesh and compare it
with the closed-form `E_m`. For the Annex B grid: **931 V numerical against 1002 V
closed-form, a 7 % difference.** The two methods share no equations, so agreement at this
level is strong evidence that both are right.

Expect the numerical value to be slightly *lower*, and understand why: the closed forms
assume uniform leakage current, whereas the real (and computed) distribution concentrates
at the edges, which flattens the potential in the interior. A disagreement much larger than
about 15 % means the grid is violating an assumption of the closed forms — usually shape
irregularity or strong soil layering — and the numerical answer is the one to believe.

![Figure 14 — Touch voltage over the reachable area, with the tolerable contour drawn in green. Everything outside that contour fails. This is what the closed-form equations cannot show you: exactly where the problem is.](figures/fig12_touch_map.png)

*Figure 14 — Touch voltage over the reachable area, with the tolerable contour drawn in green. Everything outside that contour fails. This is what the closed-form equations cannot show you: exactly where the problem is.*

![Figure 15 — A traverse across the middle of the grid. Touch voltage is largest at the grid edge; step voltage peaks just outside the perimeter conductor, where the surface gradient is steepest.](figures/fig13_profile.png)

*Figure 15 — A traverse across the middle of the grid. Touch voltage is largest at the grid edge; step voltage peaks just outside the perimeter conductor, where the surface gradient is steepest.*

### 8.8 Separate pieces of metal: fences (version 1.5)

A fence that is not bonded to the grid, a pipe crossing the yard or a neighbour's earth is
neither at the GPR nor at remote earth: it **floats** at whatever potential the soil imposes.
Number the separate networks `k = 1 … m` (network 1 is the grid) and let `E` be the incidence
matrix, `E_ik = 1` when segment `i` belongs to network `k`. In place of (8.2),

```
⎡ P   −E ⎤ ⎡ I ⎤   ⎡ 0 ⎤
⎣ Eᵀ   0 ⎦ ⎣ V ⎦ = ⎣ J ⎦,        V = Z J,   Z_jk = Z_kj                  … (8.7)
```

where `J_k` is the current driven into network `k` (`I_G` for the grid, zero for a floating
fence). Solving once per unit injection gives the mutual-resistance matrix `Z`; a floating
fence then sits at `Z_F1 I_G`, the fraction `Z_F1/Z_11` of the GPR. A floating fence has **two**
touch voltages, of opposite sign: outside, where the soil has fallen below the fence, and
inside, where the grid has lifted the soil above it. The module reports both, and the step
across the fence line.

IEEE 80 Annex H Grid 4 (an isolated fence around Grid 3) is reproduced within 1.5 % of CDEGS
or WinIGS for every quantity except one step voltage (4 %); the fence floats at 57 % of the
GPR and the grid-to-fence transfer voltage is 309 V against 309.2 V (CDEGS) and 312.4 V
(WinIGS). Grid 5 (an L-shaped grid with a bonded fence) is reproduced within 2.5 %.

### 8.9 Transferred potential along long conductors (version 1.5)

A pipe, rail, cable screen or bare wire that leaves the site carries the station's potential
with it. Over kilometres it is a lossy transmission line: series impedance `z` per metre with
earth return, leakage `g` per metre into soil that the station holds at `V_s(x)`:

```
dV/dx = −z I,        dI/dx = −g (V − V_s(x))                             … (8.8)

z = z_int + π² f 10⁻⁷ + j(ωμ₀/2π) ln(D_e/a),     D_e = 658.5 √(ρ/f) m    … (8.9)
```

(Carson's earth return; for steel, `z_int` is the skin-effect surface impedance, more than
three times the d.c. resistance at 50 Hz). A bare conductor leaks as a horizontal wire,
`g = π/(ρ[ln(2ℓ/√(2ad)) − 1])`; a coating adds `r_c/(2πa)` in series; a cable screen has
`g = 0`. The software takes `V_s(x)` from the solver along the route, solves (8.8) as a ladder,
and corrects the GPR for the current the conductor draws away, by reciprocity:

```
GPR = R_g I_G / (1 + R_g (a − c))                                       … (8.10)
```

`a` is the admittance the conductor presents at the station and `c` the share of its leakage
that returns to lift the grid. Checks: the line solution against `cosh γ(L−x)/cosh γL` to
4 × 10⁻⁹; a 150 m bare wire bonded to a 40 m grid gives the GPR within 1 % of the full solver
(6 % low without the correction `c`).

**Solved with the station (version 1.8.8).** (8.10) is a one-way coupling: the soil along the
route is the station's alone, so the conductor's own leakage — which lifts the soil beside
it — is left out, and the GPR correction is a first-order estimate. A bare or coated
conductor is now solved together with the grid. The route is cut into segments (short at the
station, growing to 50 m) that leak into the soil through the same potential-coefficient
matrix as the grid's segments; a coating adds `r_c/(2πa)` to each segment's own coefficient.
Between its nodes the route has the series impedance `z Δs`. With `I` all the leakage
currents, `V_s` the station potentials and `U` the route's node potentials:

```
P I = E V_s + B U          soil (a route segment is at the mean of its two node potentials)
Eᵀ I = J − I_bond          station networks
J_{j−1} = J_j + leak_j     route nodes,   J_j = (U_j − U_{j+1} + e_j Δs_j)/(z Δs_j)
```

`P` is the static matrix of the main solver (the leakage field is quasi-static at 50 Hz, as
before); `I = P⁻¹[E, B][V_s; U]` is eliminated and the small complex system in `V_s`, `U`
and the bond current is solved. The touch voltage along the route is now the metal
potential minus the surface potential one metre to the side, which includes the conductor's
own leakage. Checks: with `z → 0` it reproduces the main solver with the wire as part of the
grid (bonded) or as a separate network (floating) to 10⁻⁶; against the full circuit-field
model of §10.7 at 50 Hz, for a 2 km bare copper wire bonded to Grid 3, the GPR is within
1.2 %, the current drawn within 1.4 % and the touch voltage along the route within 3 %. The
one-way model read the GPR 10 % high and the touch voltage two to three times high; for a
coated pipe the two agree beyond the station edge. Rails (whose leakage is given, not
computed) and insulated screens keep the line model.

**Circuit-field check (version 1.9.2).** The coupled solution still holds the station at one
potential and couples the route to it through the soil only. Where the model is small enough
(2000 segments), station and route are also solved by the circuit-field model at 50 Hz: one
network of conductors with internal impedance — the grid's metal for the grid, the route's own
(a hollow steel pipe, say) for the route — and self and mutual inductance with earth return,
so the magnetic coupling between route and grid conductors and the drop along the grid are in
it; a coating is a resistive shell of r_c/(2πa) per metre. The route is bonded at its start to
the nearest grid node and the fault current enters at the grid node nearest to the centroid.
Its touch voltages are computed the same way, metal minus the surface one metre to the side,
and the larger of the two models is the design value. The two agree within 1 % for a 400 m
wire on a 30 m grid and a coated pipe, and within 4 % for steel pipes of 600 m to 1 km on a
100 m grid, one of them running beside the grid edge, the check slightly higher at the far
end.

**Teaching point.** Put four 2 km conductors on Grid 3 (GPR 720 V). An insulated screen earthed
remotely through 10 Ω keeps 89 % of the GPR at its far end. A coated pipe keeps 97 %. A bare
copper wire leaks, falls to 30 % and more than halves the GPR (334 V, drawing 460 A) — it is
a counterpoise, and the soil it lifts beside itself keeps its touch voltage near 120 V. An
insulating joint at the fence leaves the pipe floating at 3.5 %, but a person at the joint
touches 564 V, because the surface there is still at four fifths of the GPR. Put the joint
where the soil potential has fallen.

---

### 8.10 Finding the worst touch and step voltage (version 1.8)

The surface potential is smooth, but its maxima of interest sit on the edge of where they
are allowed to be — the touch voltage at one metre from the last conductor, the step voltage
across the edge of the grid — and a plot grid only samples them. Version 1.7 differenced
the potential over one step in +x and in +y and combined the two as √(ΔV_x² + ΔV_y²). That
is the gradient for a field that is linear over a metre, which the field at a grid corner is
not: on the IEEE 80 Annex B grid with its 20 rods it read 480 V with a 61-point scan and
603 V with a 181-point scan, against 488 V from a brute-force search over position and
direction. The scan also never stepped in −x or −y, so on two sides of the grid it missed the
step that ends on the conductor.

Now both maxima are first located coarsely — the step screened in four directions and both
senses on the plot grid (interpolated) and along a ring one step outside the electrodes
(exact) — and the best candidates are refined by a compass search in position and, for the
step, in direction, to 0.02 m and 1°. The answer is 487 V at every resolution.

The touch voltage is counted only where a person can stand on the soil and reach earthed
metal: within one metre of buried metal seen in plan, or inside a mesh (enclosed by
conductors on all four sides). The empty notch of an L- or T-shaped grid no longer counts.
Where the equipment that can actually be touched is known, *touch zones* restrict the check
to those rectangles, each with its own limit if it has one. Because the reach region is
bounded by arcs round the conductor ends, its boundary is sampled directly — a compass search
cannot slide along a curve.

### 8.11 Refinement at the ends, and the discretisation error (version 1.8)

The leakage current density rises steeply towards the free end of a conductor — the grid
corner, the rod tip — and the touch and step voltages there follow it. A uniform mesh of
3 m segments smears that peak:

| Segments | Unknowns | Touch 1 m from the corner |
|---|---|---|
| uniform 3 m | 588 | 1173 V |
| uniform 0.5 m | 3380 | 1216 V |
| 3 m, ends halved three times | 840 | 1201 V |

Halving the end segment of every conductor three times buys most of the refinement at a
quarter of the unknowns, and is on by default. The solver now also says how far it is from
the converged answer: the *convergence check* solves again with the segments halved and
estimates the limit by Richardson extrapolation, f∞ ≈ f(h/2) + [f(h/2) − f(h)] for a
first-order method. The observed order is between 0.5 and 1, so this correction is if anything
too small; the verdict therefore uses the largest of the two solutions and the estimate.
When a model has more conductor than the segment limit allows, the segments are lengthened —
and the page now says so.

**Automatic refinement at the worst points (version 1.8.8).** The touch and step voltages that
decide the verdict depend most on the segments within a few metres of where they occur.
With *automatic refinement* on, the solver halves the segments within 3 m of the worst touch
point and of both feet of the worst step (and of their images under the layout's symmetries,
so the reduction of §8.19 is kept), solves again, searches again, and repeats until both
change by less than the tolerance from one level to the next. On Annex B with twenty rods,
3 m graded segments move by 0.04 % (touch) and 0.15 % (step) on the first refinement; 8 m
segments converge in two levels to about 0.5 % (touch, high) and 0.3 % (step) of a mesh of
0.25 m. What it cannot remove is the global part of the error — the GPR, set by every
segment — which is what the convergence check measures, so the two are complementary.

### 8.12 When the grid is not at one potential (version 1.8)

The method of moments of §8.2 holds every piece of buried metal at the same potential. The
conductors have impedance: internal (skin effect, and steel's permeability), and self and
mutual inductance with earth return. For a compact copper grid the voltage drop along the
conductors is negligible against the GPR; for a power-plant grid of several hundred metres,
for steel, or in low-resistivity soil, it is not. The fault current enters at the
transformer neutral and loses voltage on its way to the far corners.

The non-equipotential solution solves the same electrodes as a network of conductors coupled
through the soil — the circuit–field model of the lightning page (§10.7) evaluated at 50 or
60 Hz — with the fault current entering at one or more points. The leakage currents it finds
are then put into the static Green's function of §8.3, real and imaginary parts separately,
for the surface potential; the touch voltage at a point is the magnitude of the difference
between the potential of the nearest grid node and the surface potential there.

| Grid, fed at one corner | Soil | |Z| / R_g | Far corner / feed point |
|---|---|---|---|
| 100 m × 100 m copper | 100 Ω·m | 1.005 | 0.99 |
| 300 m × 300 m copper | 30 Ω·m | 1.33 | 0.70 |
| 300 m × 300 m steel | 30 Ω·m | 3.1 | 0.24 |

For the 300 m copper grid the touch voltage near the feed point is 190 V against 104 V for the
equipotential solution. The page says whether the assumption is adequate (|Z| within 5 % of
R_g and no metal below 90 % of the feed-point potential).

Fences are part of the same network (version 1.8.3). Their posts and any buried fence wire
leak current like any other conductor; the fabric above ground does not, so it is represented
by joining the post tops and the wire into one node — a connection without leakage. An
isolated fence then floats at whatever potential the soil around it imposes; a bonded fence is
joined to the grid at the grid node nearest to it. One bond is deliberate: a perfect fence
bonded at several points would short-circuit the grid's own impedance, which is the very
effect this solution is there to show. The fence touch voltage is the magnitude of the fence
potential minus the surface potential, 0.5 m and 1 m inside and outside the fence line.

### 8.13 The soil is uncertain, and it changes with the season (version 1.8)

The soil model is the least certain input of the whole design. §2.5 gives its covariance
C = s²(JᵀJ)⁻¹ in logarithmic parameters; the *uncertainty study* draws soil models from it
(log-normal, correlations kept, a parameter the readings do not resolve capped at a factor of
three), solves the electrodes in each, and reports the 5 %, 50 % and 95 % values of R_g, GPR,
touch and step voltage, and the fraction of models that meet the limits. To keep it
affordable, each sample is solved in full but searched for its maxima only around the points
found for the fitted model.

With 20 samples, plain random sampling leaves whole parts of a distribution empty. The study
therefore uses Latin hypercube sampling (version 1.8.3): the standard normal range of each
parameter is split into n bands of equal probability 1/n, one value is drawn in each band, the
bands are paired at random between the parameters, and the correlations of the fit are then
imposed through the square root of the covariance matrix. Each parameter is covered evenly
from tail to tail; the scatter of the estimated mean falls by more than half for ten samples.
A fraction k/n of models that pass is an estimate, so its 95 % confidence interval is given
by the Wilson score interval

    (p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n),   z = 1.96,

and about 1.96²·p(1−p)/0.05² samples narrow it to ±5 %. The 95th percentile of the samples is
the design value; the largest of n samples lies above the true 95th percentile with
confidence 1 − 0.95ⁿ, which reaches 95 % at n = 59.

The survey is also one moment in the year. The *seasonal study* multiplies the resistivity of
the top metre (or any depth) by a dry-season factor, and optionally replaces the top by a
frozen layer, collapsing the result back to at most four layers, and solves each case. A dry
top layer raises R_g and the GPR; whether it raises the touch voltage depends on how much of
the potential the surface soil carries — which is why it is computed rather than assumed.

### 8.14 Optimising the grid (version 1.8)

A uniform grid has its highest mesh voltages in the corner meshes and its lowest in the
middle; drawing the conductors towards the edges evens them out. A line at fraction u of the
width is placed at

    x = L·(u − g·sin(2πu)/2π),

so the edge meshes are (1 − g) and the centre meshes (1 + g) times the mean spacing. The
optimiser searches, with the numerical solver itself, the number of conductors (upwards from
the sparsest grid, then by bisection — fewer conductors give higher voltages), the grading
g ∈ {0, 0.35, 0.6} and rods round the perimeter or none, and returns the cheapest design that
meets both limits, with the cost of a metre of conductor and of rod as relative weights. A
candidate that already costs more than the best design found so far is never solved, so the
dense, slow grids are rarely reached: on a 70 m square the search takes 40 % less time than
solving the densest grid of every combination first (version 1.8.1).

### 8.15 Planning and reading a fall-of-potential test (version 1.8)

IEEE Std 81 measures an electrode's resistance by passing a current to a remote current
electrode C and reading the voltage to a probe P moved out along the traverse. The reading
equals the true resistance only where P sits at the potential of remote earth as seen from
the electrode — 61.8 % of the distance for a hemisphere in uniform soil. In layered soil,
with the probe line at an angle, or with distances taped from the edge of a large grid, that
point moves.

The test page solves the electrode and a driven current electrode together — two networks,
+I and −I — so the whole curve R(x) = (V_E − V_P(x))/I is computed for the real geometry and
soil. For the 70 m Annex B grid (largest dimension D = 99 m), distances measured from its
centre as IEEE Std 81 does:

| Current electrode at | Uniform 400 Ω·m | 100 Ω·m over 1000 Ω·m at 5 m |
|---|---|---|
| 1 × D | −5.0 % (true value at 64 %) | −27 % (at 71 %) |
| 2 × D | −0.5 % (62 %) | −7.2 % (66 %) |
| 5 × D | 0.0 % (62 %) | −0.9 % (63 %) |

(error of the reading taken at 61.8 %, and the probe position that gives the true value). In
uniform soil the rule holds for a grid much as for a hemisphere, as superposition leads one
to expect; over a resistive substratum the current electrode must be far further out. Taped from
the grid's edge instead of its centre, the true-value position for C at 1 × D moves to about
50 % of the distance and the 61.8 % reading is 19 % high. The plan recommends the shortest
distance whose 61.8 % reading is within the accuracy asked for, and where the probe must stand.
Given the readings, the computed curve is scaled to them by least squares: the factor is the
ratio of site to model resistance, and the residual of the shape says whether the soil model —
not only its level — is right.

### 8.16 Induction along a parallel route (version 1.8; any route, 1.8.5)

A pipeline or cable that runs beside a faulted line also has a voltage induced along it by
the earth-return current I in the line, z_m·I per metre (Carson's mutual impedance at the
separation d, §3.7). The transferred-potential solver adds it as a series source in every
section of the parallel stretch; with the GPR and the fault current in phase it is combined
with the conductive part as a phasor. An insulated conductor bonded at the station and open
at the far end carries the whole EMF, z_m·I·ℓ, to its far end. Routes need no longer be
straight: a polyline is followed through the station's soil potential.

Since 1.8.5 the faulted line can be given as its own route. At each point s of the
conductor the nearest point of the line is found, at distance d(s), with u the line's
direction there and t the conductor's, and

    e(s) = z_m(d(s))·I·(t·u)     V/m,

zero where the nearest point is beyond the line's ends or d exceeds the Carson depth D_e.
This is the K.26 sectioning of an oblique exposure taken to the limit of short sections: an
approach at angle θ counts cos θ of its length, and a crossing at right angles induces
nothing. The EMF profile then enters the same lossy-line solution as before.

### 8.17 Which value decides: the governing values (version 1.8.2)

Each study of §8.11–8.13 corrects the plain solution for one thing it leaves out: the
convergence check for the length of the segments, the seasonal study for a dry or frozen
surface, the uncertainty study for what the soil readings cannot pin down, and the
non-equipotential solution for the impedance of the conductors. A verdict that ignores them
answers a question nobody asked. The page therefore takes, for each of the touch voltage, the
step voltage, R_g and the GPR,

    X_gov = max( X_plain, X_convergence, X_seasonal,worst, X_uncertainty,95 %, X_non-equipotential ),

over the studies that were actually run, and names the one that gave the maximum. The maxima
are taken one at a time and not multiplied: a dry season, an unlucky soil draw, a coarse mesh
and the conductor impedance acting together at their worst is not a design case, and stacking
them would penalise every design that is studied carefully.

Two rules keep the comparison honest. A study counts only if it solved the same electrodes,
soil and current as the plain solution — each result carries a fingerprint of that model, and
a study left from before an edit is listed as out of date and ignored. And the touch checks
of touch zones and fences, which only the plain solution evaluates, are multiplied by
X_gov / X_plain for the touch voltage: exact when the study scales the whole field (a uniform
change of resistivity), conservative otherwise. The design report and the drawing stamp use
the same governing values, so the verdict cannot differ between the page, the report and the
drawings.

### 8.18 Keeping the work down (version 1.8.4)

Almost all the time of a solution goes into evaluating the image sum of §8.3 between pairs of
points, and how many quadrature points each pair needs depends only on how far apart they are
compared with the segment length L. A Gauss rule with m points integrates a polynomial of
degree 2m − 1 exactly; along a segment seen from a distance d the integrand 1/r is smooth on
the scale of d, so the error of an m-point rule falls roughly as (L/2d)^(2m). The solver
therefore spends its effort where the integrand is sharp:

| Where | Rule | Error |
|---|---|---|
| matrix, pairs closer than 2.5 L | 6 × 10 double (Galerkin) quadrature | the reference |
| matrix, 2.5 L to 8 L | 3 × 4 double quadrature | about 1e-8 relative |
| matrix, beyond 8 L | 4-point collocation | about 1e-9 |
| field, within 5 L of a segment | 12 points | the reference |
| field, beyond 5 L | 2 points | about 1e-5 at 5 L, falling as (L/d)⁴ |

Against the uniform rules of earlier versions the touch and step voltages and R_g move by less
than one part in a million. Independent solutions — seasonal cases, soil samples, the two
halves of the convergence check, the candidates of one optimisation round — are spread over
the processor's cores; each worker does its linear algebra on one thread so that the cores are
not oversubscribed.

### 8.19 Large grids: symmetry, compression and reuse (version 1.8.7)

The matrix P of §8.2 is dense — every segment raises the potential of every other — so stored
as it is it needs n² numbers and its solution n³/3 operations. At 4000 segments that is
128 MB and a few seconds; a power-plant grid of 300 × 300 m with 10 m meshes has 18 km of
conductor, 7000 segments at 2.5 m, and 400 MB and a minute; at 1 m segments it does not fit at
all. Version 1.8.7 removes the limit in three ways, each checked against the dense solution.

**Symmetry.** A square grid with rods on its perimeter looks the same after a mirror in x, in
y or in a diagonal, or a quarter turn: eight transformations. If a transformation g maps
every segment onto a segment (same radius, same layer, same network) and the soil onto
itself, then P[gi, gj] = P[i, j], the injections are unchanged, and so is the solution: the
current is the same on every segment of an orbit {g i}. Writing I_b for the common current of
orbit O_b and taking one equation per orbit, at its representative r_a,

    Σ_b I_b Σ_{j∈O_b} P[r_a, j] = V ,     Σ_{j∈O_b} P[r_a, j] = (|O_b|/|O_a|) Σ_{i∈O_a} P[i, r_b]

and the right-hand form needs only the columns of the representatives. The square grid is
solved with an eighth of the columns and an eighth of the unknowns — 1/512 of the
elimination — and the answer is the same to the last digits (10⁻¹² in the tests). A
rectangle has four symmetries, an L-shaped grid none; the solver finds them itself.

**Compression.** Two groups of segments far apart compared with their size see each other
through a smooth function: the block of P between them is, to any stated accuracy, a sum of
a few products of a column and a row. The segments are sorted into a tree of clusters (each
split in two along its longest side, down to 64), and a pair of clusters whose horizontal
gap exceeds 1/1.5 of the smaller diameter, and the 8 L reach of the near-field quadrature of
§8.18, is replaced by such a sum, found by adaptive cross approximation: take a row of the
block, its largest entry picks a column, subtract the product, and repeat until the next
product is below 10⁻⁸ of what has been gathered. Only k(m + n) of the m n entries are ever
computed. Horizontal gaps are used because every image of §8.3 and §8.6 sits at the
horizontal position of its source (or, in §8.20, further away on the same side). The
system is then solved by GMRES, which needs only products of the compressed matrix with
vectors, preconditioned with the exact inverse of the diagonal blocks of 256 segments; it
converges in 10 to 20 iterations. On the Annex B grid at 0.125 m segments (13 520 unknowns)
R_g agrees with the dense solution to 4 × 10⁻¹¹ and the touch voltage to 5 × 10⁻⁹. Above
4000 unknowns (after the symmetry reduction) the compressed solution is used.

In two-layer soil most of the time went into the image series, up to 4N + 4 = 244 terms per
pair. For a grid at one depth the series between two of its points depends only on their
horizontal distance, so it is tabulated once — in u = asinh(r/Δ_min), Δ_min the smallest
vertical offset of an image, with the derivative for cubic Hermite interpolation, to 10⁻¹⁰ —
and the single term at zero offset is added exactly. The Annex H Grid 3 solution is twice as
fast and the answers move by 10⁻¹¹.

**Reuse.** The currents depend on the geometry and the soil, not on I_G, so a solution is
kept and serves the same model with another current; in uniform soil they do not depend on ρ
either (R_g is proportional to it), so one solution serves every resistivity. The studies
keep their cases too: the "as measured" case of the seasonal study is the coarse case of the
convergence check, and running a study again with nothing changed costs nothing.

The non-equipotential solution of §8.12 had its own limit, 1500 segments, from its
(N_n + 2N)² complex system. Eliminating the segment currents first — I_T = Z_T⁻¹ M V and
I_L = Z_L⁻¹ D V, with M the average and D the difference of the end potentials — leaves the
node admittance matrix Y = Dᵀ Z_L⁻¹ D + Mᵀ Z_T⁻¹ M: a third of the memory and a ninth of the
arithmetic, and the limit is now 3000 segments.

**Two scales (version 1.8.9).** A model beyond that limit is solved in two scales. The metal
potential varies slowly along a conductor — it changes over the distance on which the series
impedance acts, tens of metres — while the leakage current and the surface potential change
over a segment length near a crossing or an end. The circuit-field model is therefore solved
with segments long enough to stay within the limit, giving the node potentials V_n. On each
conductor V is interpolated linearly between the nodes to the mid-points of segments of the
length asked for, and the leakage currents there follow from the static potential
coefficients of §8.3:

    P I_f = V(x_f),   real and imaginary parts separately (P is real),

dense, or with the compressed matrix and GMRES described above beyond 4000 segments. The sum of I_f
differs from I_G by the difference between the two models' leakage, a fraction of a percent;
I_f is scaled to I_G and the ratio reported. The surface potential, touch and step voltages
are those of I_f, with the metal potential interpolated at the ends of the fine segments; the
earth impedance and the metal potentials are those of the coarse model. On the 300 m grid of
§8.12, fed at a corner, coarse 20 m and fine 5 m segments reproduce the touch and
step voltages of the full 5 m model within 0.4 % — copper and steel, uniform and two-layer
soil — where the 20 m model alone is 6–20 % out (the step voltage low, the touch voltage
high). The count against the limit is taken after the conductors are cut at their crossings
and at the layer boundaries.

### 8.20 Two soils side by side (version 1.8.7)

Soil is not always layered horizontally. A geological fault, a rock face, the edge of a lake or
of a backfilled area divides the site into two soils side by side. For two uniform soils
separated by a vertical plane the image method of §2.4 is exact — and simpler than for
layers, because the plane is crossed only once.

A unit source in soil 1 (ρ₁) near the plane to soil 2 (ρ₂) produces in soil 1 the field of
the source and of a mirror image in the plane, of strength K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁); in soil 2,
the field of the source alone, of strength 1 − K, in soil 2's resistivity:

    V₁ = ρ₁/(4π) [1/r + K/r′],     V₂ = ρ₂(1 − K)/(4π r) = ρ₁(1 + K)/(4π r)

Both conditions on the plane hold: there r = r′, so V₁ = ρ₁(1 + K)/(4πr) = V₂; and the normal
derivatives of 1/r and 1/r′ are opposite, so the normal current density is
(1 − K)/(4π)·∂(1/r)/∂n on both sides. The air surface is a second mirror, perpendicular to
the first, so its image of each term simply joins it (§8.3): four terms in all, no series.
A source in soil 2 is the same with K → −K.

Two limits check it. Far from the plane K/r′ vanishes and the soil is uniform. A source in
the plane sees ρ₁(1 + K) = 2ρ₁ρ₂/(ρ₁ + ρ₂) in every direction — so an electrode lying in the
plane behaves exactly as in uniform soil of the harmonic mean resistivity, which the solver
reproduces to 10⁻¹². More generally, for any electrode symmetric about the plane the uniform
solution in the harmonic mean has no current across the plane, so it meets both conditions
and is exact: the Annex B grid with the boundary through its centre agrees with it to
3 × 10⁻⁶. A rod 1 m from the plane agrees within 0.05 % with the first-order
estimate R ≈ R₁₁ + K R₁₂, R₁₂ the mutual resistance to its own mirror image.

Conductors that cross the plane are split there, as at a layer interface, and each piece
uses its own side's resistivity. A conductor parallel to the plane and close to it sees its
own mirror image as a parallel line 2d away, a nearly singular term that a Gauss rule would
resolve poorly; it is taken in closed form, the same average potential as the self term of
§8.4 with the radius replaced by 2d. Horizontal layers on either side are not combined with
the plane: images of perpendicular planes with different contrasts do not close.

### 8.21 Plates (version 1.9.0)

An earth plate, or the reinforcement of a raft taken as one sheet, is a thin conductor whose
charge spreads over an area and crowds towards its edges, where the surface density of a
thin plate rises as d^(−1/2) with the distance d from the edge. The solver's elements are
wires, so the plate is cut along its long side into n strips whose edges follow a cosine
(Chebyshev) spacing across the short side, t_k = ½ − ½ cos(πk/n), narrow at the edges where the
density changes fastest. Each strip becomes a conductor on its centre line with radius

    a_k = w_k / (2π).

The radius is not the w/4 of an isolated flat strip. An infinite array of wires of radius a
at spacing s, charge q per metre, has the two-dimensional potential
−(q/4πε) ln[2 cosh(2πz/s) − 2 cos(2πy/s)]. Away from the array this is the potential of the
plane with the same charge, σ = q/s; on the wires it exceeds the plane's by
(q/2πε) ln(s/2πa), which vanishes for a = s/2π. With that radius the array carries charge
exactly as the plane it fills. The strips are cut into segments of the short side divided by
n, without end grading, which keeps every segment about four radii long, inside the range of
the thin-wire kernel. They keep that length when the rest of the model is refined.

Checked against an independent panel solution — constant-charge rectangles with the exact
potential of a uniform rectangle, ∫∫dA/r = x ln(y + r) + y ln(x + r) − w atan(xy/wr), cosine
graded, with the image of the surface (and in two-layer soil the series of K^n images), and
Richardson extrapolation in 1/n² — which itself reproduces the capacitance of the unit square,
C = 0.3667896·4πε₀ a (Read 2004), to 1·10⁻⁵. With 16 strips the resistance is high by 0.08–0.22 %
for a 10 m square in a full space, 1 m squares horizontal and vertical near the surface,
10:1 strips and a plate in two-layer soil; the error falls as 50/n² % and is never below the
reference. The surface potential over a 6 m plate 0.5 m deep is within 0.8 % of the GPR. A
wide horizontal plate near the surface gets more strips, so that the widest is no wider than
about 1.2 times its depth (at most 64).

A raft's bars entered as a grid and the same raft as a plate differ by 0.0–0.7 % in R
(6–18 m, bars 12–20 mm at 0.2–0.25 m), the plate lower, since a mesh of bars leaks a little
less readily than the solid sheet; on a 12 m raft the touch voltage is 1.2 % lower and the
step voltage 2.6 % higher. The concrete is taken as soil.

### 8.22 The shortest segment (version 1.9.1)

The thin-wire kernel puts each segment's current on its axis and evaluates the potential on
the surface of the other segments, 1/√(r² + a²). That is accurate while a segment is long
against its radius. Below about four radii the potential-coefficient matrix stops being
positive definite and some leakage currents come out negative: for a 6 m rod of 50 mm radius
in 100 Ω·m, R is 13.05 Ω at ten radii, 12.92 Ω at four, then 13.06, 12.83 and 11.91 Ω at three,
2.5 and two radii, with negative currents on a third to a half of the segments. Where conductors cross,
negative currents appear near six radii. The end grading and the automatic refinement have
always stopped at ten radii; since 1.9.1 the segment length itself does, for every bare
conductor, in the numerical solver, the non-equipotential solution and the lightning model,
and the results name the conductors kept there. The strips of a plate (§8.21) are about four
of their radii long by design; they are parallel and do not cross, their matrix is positive
definite, and their resistance was checked against an exact plate solution.

## 9. Buildings and homes — module 6
### 9.1 The system types, and what actually differs

The letters are a code: the **first** letter is how the source is earthed, the **second**
is how the installation's exposed metal is earthed.

| System | Source | Exposed metal | Fault path | Consequence |
|---|---|---|---|---|
| **TN-S** | Earthed | To source via a separate PE | Metallic | Large fault current; overcurrent device trips |
| **TN-C** | Earthed | Combined PEN | Metallic | No RCD possible downstream of the PEN |
| **TN-C-S** | Earthed | PEN split into N and PE at the origin | Metallic | Common utility arrangement (PME) |
| **TT** | Earthed | Own local electrode | **Through the soil** | Small fault current; RCD effectively mandatory |
| **IT** | Isolated or high-impedance | Local electrode | First fault limited by capacitance | Continuity; needs insulation monitoring |

The single most important teaching point: **in TN the fault current is large and the
criterion is on time; in TT the fault current is small and the criterion is on voltage.**
Everything else follows.

![Figure 16 — The two fault paths. In TN the return is metallic and the fault current is large enough to operate an overcurrent device; in TT it returns through the soil and is far too small, so the criterion becomes a limit on touch voltage and an RCD is required.](figures/fig16_tn_tt.png)

*Figure 16 — The two fault paths. In TN the return is metallic and the fault current is large enough to operate an overcurrent device; in TT it returns through the soil and is far too small, so the criterion becomes a limit on touch voltage and an RCD is required.*

### 9.2 The TN criterion

```
Z_s · I_a ≤ C_min · U₀          … (9.1)
```

`I_a` is the current that operates the device within the time of Table 41.1 (0.4 s for a
230 V final circuit, 5 s for a distribution circuit). For a type B breaker `I_a = 5I_n`,
type C `10I_n`, type D `20I_n`. `C_min = 0.95` allows for a low supply voltage.

Why the times differ: 0.4 s is the exposure a person may credibly receive from a portable
appliance they are holding; 5 s applies to fixed distribution equipment they are unlikely
to be touching when the fault occurs. Both trace back to the same `I_B = k/√t` curve.

**Fuses (version 1.8.6).** A fuse has no multiplier: `I_a` is read from its time–current
characteristic at the required time. IEC 60269 does not fix that curve, only the **gates**
it must pass through. For gG (and gM) fuse-links of 16–1250 A, IEC 60269-1 Table 3 gives
`I_min(10 s)`, `I_max(5 s)`, `I_min(0.1 s)` and `I_max(0.1 s)`; Table 7 the pre-arcing `I²t`
at 0.01 s; Table 2 the conventional non-fusing and fusing currents `I_nf`, `I_f` (1.25 and
1.6·I_n) at the conventional time (1 to 4 h); Parts 2 and 3 add the small ratings of each fuse
system. Every compliant fuse-link of rating `I_n` operates within `t` at any current to the
right of the **upper limit** of the band, the polyline through

```
(I_f, t_conv), (I_max(5 s), 5 s), (I_max(0.1 s), 0.1 s), (√(I²t_max/0.01 s), 0.01 s)   … (9.1a)
```

on log–log axes, extended below 0.01 s at constant `I²t`. Real characteristics are concave
on those axes and lie inside the band, so the chord is safe: for a 32 A gG fuse it gives
259 A at 0.4 s, against the 221 A of BS 7671 Table 41.2 for BS 88-2 fuses (whose tabulated
values all lie inside the gates — a test checks every one). Where the make is known the
manufacturer's curve is better: it is entered as current–time points, followed on log–log
axes, and moved by its current tolerance (often ±10 % on a mean pre-arcing curve) to the
safe side. Above 0.1 s the arcing time is negligible, so pre-arcing time and operating time
coincide, which is how IEC 60364 uses the curve. The page also reports the time within which
the fuse certainly operates at the prospective fault current `C_min·U₀/Z_s` — the same
criterion as (9.1) read the other way.

### 9.3 The TT criterion

The fault current returns through the soil, through `R_A` in series with the source
electrode. That is typically a few tens of ohms, giving a few amperes — nowhere near enough
to trip a 32 A breaker. So the criterion becomes a voltage one:

```
R_A · I_a ≤ U_L = 50 V          … (9.2)
```

With an RCD, `I_a = IΔn`. For a 30 mA RCD, `R_A ≤ 50/0.03 = 1667 Ω` — essentially any
electrode qualifies. For a 300 mA RCD, `R_A ≤ 167 Ω`. **This is why RCDs are mandatory in
practice in TT systems**, and why the software's remedy text always offers "use a more
sensitive RCD" as the first option: it relaxes the electrode requirement in direct
proportion.

### 9.4 Electrode formulas

All of these come from the same half-space potential theory as §1.2, with the electrode
geometry changing the boundary condition.

**Vertical rod** (Dwight, derived in §8.4):

```
R = ρ/(2πL) [ ln(8L/d) − 1 ]          … (9.3)
```

The logarithm is the key: **doubling the length does much more than doubling the
diameter**. Going from 12 mm to 25 mm rod diameter changes `R` by about 12 %; going from
1.5 m to 3 m changes it by about 40 %.

**Horizontal conductor of total length `L` at depth `h`** (Dwight, IEEE 142 Table 4.2,
written with the half-length `ℓ = L/2` and `s = 2h`):

```
R = ρ/(4πℓ) [ ln(4ℓ/a) + ln(4ℓ/s) − 2 + s/(2ℓ) − s²/(16ℓ²) + … ]         … (9.4)
```

> **A published-formula trap.** Several references — including popular open-source code —
> quote this with `L` where Dwight's `2ℓ` belongs, which inflates the result by about 12 %
> for a 30 m tape. Earthing System was caught by this during validation: the boundary-element
> solver disagreed with the "textbook" formula by 11.6 %, and it turned out the solver was
> right. The two-method cross-check is what found it. Worth telling students as a lesson
> about trusting a single source.

**Plate, ring, foundation** follow the same pattern and are listed in `METHODS.md`. The
foundation electrode `R ≈ 0.2ρ/∛V` deserves a mention: concrete in contact with soil is a
surprisingly good conductor (its pore water is alkaline and ionic), and a building's own
foundation reinforcement is usually the cheapest low-resistance electrode available. It is
mandatory for new buildings in several countries for exactly this reason. Piles, piers and strip
footings, which are long and slender rather than compact, are treated in §9.8.

### 9.5 Electrodes in parallel — why you never get `R/n`

Two rods 1 m apart are almost the same electrode. Each one's current raises the potential
of the other's soil, so they interfere. The classical result:

```
R_n = (R₁/n)(1 + λα),     α = ρ/(2π R₁ s)          … (9.5)
```

where `s` is the spacing and `λ` the group factor. `λ` is not an empirical number: it is
the potential each rod receives from its neighbours, in units of `ρ/(2πs)`, averaged over
the group,

```
λ = (1/n) Σᵢ Σ_{j≠i} s / d_ij                                      … (9.6)
```

Earthing System uses the BS 7430 Table 5 values where they exist (rods in a line; hollow
square with 4, 8, 12, 16, 20 rods — 4.51 for eight) and evaluates (9.6) for the actual
layout otherwise, including the filled square. (Version 1.1 held line-like values for the
hollow square — 3.45 for eight rods — and line values for the filled square, both
optimistic.) The correction vanishes as `s → ∞` and grows as the rods crowd together.

**Dissimilar electrodes.** The same physics applies when a foundation electrode, a ring
and a rod group are bonded together. Module 6 represents each electrode by its
resistance `Rᵢ` and equivalent hemisphere radius `rᵢ = ρ/(2πRᵢ)`, takes the mutual
resistance of a pair as `min(ρ/(2π max(D, rᵢ + rⱼ)), Rᵢ, Rⱼ)` and solves `[R] I = V·1`,
so `R_A = 1/(1ᵀ[R]⁻¹1)`. Without a stated separation `D` the hemispheres are taken as
touching — the conservative case for one building plot. (Version 1.1 added them like
resistors in parallel.)

**Practical rule to teach:** space rods at least their own length apart, and preferably
twice. Four rods at 6 m spacing give about 3.1× the benefit of one; four rods at 1 m
spacing give barely 2×. The software computes the utilisation factor so students can see
this directly.

![Figure 17 — (a) Rod resistance against length for three soils — the logarithm means length always beats diameter. (b) Rods in parallel never reach the ideal R₁/n, and the shortfall grows as they are crowded together.](figures/fig17_electrodes.png)

*Figure 17 — (a) Rod resistance against length for three soils — the logarithm means length always beats diameter. (b) Rods in parallel never reach the ideal R₁/n, and the shortfall grows as they are crowded together.*

### 9.6 The seasonal factor nobody plans for

`R_A` is measured once, in whatever season the commissioning happened. Soil dries in
summer and freezes in winter, and a rod electrode can easily **double** its resistance
between seasons. The margin the software reports on the TT check is not an academic
number — it is the seasonal allowance. Teach students to look at it, not just at the
PASS badge.

### 9.7 Earth pits (version 1.3.6)

An earth pit sets the rod in a hole filled with backfill of resistivity `ρ_c` below the
soil's. §1.2 showed where the resistance of an electrode lives: in the innermost shells. For
a rod the cylinder of soil between its diameter `d` and a diameter `D` holds the fraction
`ln(D/d)/(ln(8L/d) − 1)` of the rod's whole resistance — 46 % for a 3 m × 16 mm rod in a
0.3 m hole. Filling that cylinder replaces `ρ` by `ρ_c` there and leaves the rest:

```
R = ρ/(2πL)[ln(8L/D) − 1] + ρ_c/(2πL) ln(D/d)          (BS 7430 9.5.7)   … (9.7)
```

Two shells in series: a rod of the hole's diameter in soil, plus the backfill annulus.
Two consequences run against intuition. No backfill can do better than the fat rod
(`ρ_c → 0` gives Dwight with `D` for `d`: 17.9 Ω against 33.1 Ω bare for the 3 m rod in
100 Ω·m), and backfill does not cure the seasons, because the soil term is still
proportional to `ρ`. The software's earth-pit card solves the pit numerically (axisymmetric
finite volumes), which handles partial columns and plates at the bottom of a well; (9.7) lies
within 2.5 % of that solution, on the conservative side. It also checks the current density
at the metal and at the backfill boundary against BS 7430 9.8,
`J_max = 10³ √(57.7/(ρ t))` A/m².

### 9.8 Piles, piers and strip footings: the concrete shell (version 1.6)

The hemisphere `R ≈ 0.2ρ/∛V` of §9.4 suits a compact foundation whose steel fills it. A pile,
pier, pole base or strip footing is long and slender, with its steel near the axis, and the
concrete is a coaxial shell in series with the soil — (9.7) again, with concrete for backfill
(Fagan and Lee 1970):

```
R = ρ_c/(2πL) ln(r_c/a) + ρ/(2πL)(ln(4L/r_c) − 1)
  = R_bare + (ρ_c − ρ)/(2πL) · ln(r_c/a)                                 … (9.8)
```

The second form gives the rule worth remembering: **concrete helps exactly when it is less
resistive than the soil**, whatever the dimensions. Buried concrete in moist ground is about
30–100 Ω·m (Fagan and Lee measured 30 Ω·m; IEEE 142 gives about 30; IEEE 80 21–100 wet); an
exposed slab is several hundred (EPRI measured 196 Ω·m wet and 264 Ω·m dry on a pad). The
software's default is 50 Ω·m.

A cage of `n` bars of radius `a` on a circle of radius `b` acts as one bar of its
geometric-mean radius, and a rectangular section `w × h` as a cylinder of equal capacitance:

```
a_eq = (n a b^(n−1))^(1/n),     r_c = (w + h)/4 + 0.09 min(w, h)     … (9.9)
```

(`w/4` for a flat strip and `0.59w` for a square, both exact). Six 16 mm bars on a 0.14 m
circle give `a_eq` = 0.10 m, half the radius of a 0.4 m pier: a reinforced pier is close to a
bare rod of its own diameter.

The numerical page has **Pier / pile** and **Strip footing** elements. The solver puts the
concrete shell `ρ_c ln(r_c/a_eq)/(2πL)` in series with each segment's leakage, uses the
kernel reduced to the concrete's radius for near pairs and keeps those segments at least
1.5 `r_c` long. Fagan and Lee's own table for a 10 ft, ¾ in rod in 16 in of concrete is
reproduced within 3 %, and Wiener's measured footings (6–13 Ω over 14 months) fall inside the
measured range. The lightning model takes the same elements (§10.7, Figure 21).

---

## 10. Lightning — module 7
### 10.1 Why power-frequency thinking fails

A lightning stroke has a rise time of about 1 µs, which corresponds to significant energy
up to a few megahertz. At those frequencies:

- The **inductance** of the down-conductor and the electrode dominates the impedance.
  A straight conductor has roughly 1 µH/m; at `di/dt = 100 kA/µs` that is 100 kV per metre.
  A 50 Hz resistance calculation is irrelevant to this.
- **Soil ionises** around the electrode when the local field exceeds roughly 300 kV/m,
  effectively enlarging the electrode and *reducing* its impulse impedance below its
  measured 50 Hz resistance.
- Only about the first 10–20 m of a long horizontal electrode carries useful current during
  the fast front — the rest is disconnected by its own inductance. This is why IEC 62305
  specifies **lengths and geometry**, not resistance.

That is the reason the 10 Ω figure in IEC 62305-3 is *informative* while the `l₁` geometry
requirement is *normative*. Earthing System's verdict text makes that distinction explicitly,
because students routinely invert it.

### 10.2 `l₁`, and Type A versus Type B

`l₁` (Figure 3) is the minimum electrode length, growing with soil resistivity and with
protection class. It is a proxy for "enough soil volume to disperse the charge".

- **Type A** — individual radial or vertical electrodes, at least two, each of length
  `≥ l₁` (horizontal) or `≥ 0.5 l₁` (vertical). Suitable for small structures.
- **Type B** — a ring electrode (or the foundation) with mean radius `r_e = √(A/π) ≥ l₁`.
  Preferred for larger structures and mandatory in practice where there is an electronic
  system to protect, because the ring also provides the equipotential reference.

If `r_e < l₁`, add `l_r = l₁ − r_e` horizontally or `l_v = (l₁ − r_e)/2` vertically at each
down-conductor. The software computes these directly.

![Figure 18 — The minimum electrode length of IEC 62305-3:2024 Figure 5 (Figure 3 in 2010, unchanged). For classes III and IV it is 5 m whatever the soil; for classes I and II it grows steeply in resistive ground.](figures/fig18_lps_l1.png)

*Figure 18 — The minimum electrode length of IEC 62305-3:2024 Figure 5 (Figure 3 in 2010, unchanged). For classes III and IV it is 5 m whatever the soil; for classes I and II it grows steeply in resistive ground.*

### 10.3 Separation distance — the derivation

A down-conductor carrying a fraction of the stroke current develops a voltage along its
length, mostly inductive: `U ≈ L' · l · di/dt`. If nearby metal is at earth potential and
closer than the distance that voltage can flash over, you get a **side flash** — often into
the building's electrical or data wiring, which is far more damaging than the original
strike.

```
s = k_i · k_c · l / k_m          … (10.1)
```

- `k_i` encodes `di/dt` for the protection class: 0.08 (class I), 0.06 (II), 0.04 (III/IV).
- `k_c` is the **current division** among down-conductors: 1 for a single conductor, 0.66
  for two, 0.44 for four or more. More down-conductors, less current each, less voltage.
- `k_m` is the dielectric strength of the intervening material: **1 for air, 0.5 for
  concrete, brick or wood.**

That last one is counter-intuitive and worth stopping on: because `k_m` is in the
denominator, `k_m = 0.5` **doubles** the required separation. Solid building materials are
*worse* insulators than air over these distances — they are porous, absorb moisture, and
puncture rather than flash over. Students almost always guess the other way.

### 10.4 Effective length and effective area — putting a number on §10.1

Section 10.1 asserted that only the first ten or twenty metres of a long horizontal
electrode does any work during the front. That is worth turning into an equation, because
it changes what you build.

**The mechanism.** A buried conductor is a lossy transmission line: series inductance
`L'` per metre, and shunt conductance `G'` per metre to the soil. A step of current
injected at one end does not appear at the far end instantly — it diffuses along the line,
and while it is diffusing the conductance near the injection point is already bleeding it
into the soil. By the time the front has peaked, at `t = T`, the current has only reached
a limited distance. Beyond that distance the conductor is carrying almost nothing. The
diffusion length of such a line scales as `√(T/(L'G'))`, and since `G' ∝ 1/ρ` while `L'`
is essentially fixed by the geometry, the distance scales as `√(ρT)`. Fitting the constant
to measurements gives

```
L_eff = k · (ρ · T)^0.5      ρ in Ω·m, T in µs, L_eff in m      … (10.2)
        k = 1.40  fed at one end
        k = 1.55  fed at its centre
```

The centre-fed constant is larger only because the current has two directions to travel
in rather than one, so each half of the electrode sees half the current and the front gets
a little further.

Put the numbers of §10.1 in: 100 Ω·m soil, a 1 µs first negative stroke, fed at one end,
gives `L_eff = 1.4 × √100 = 14 m`. That is where the "10–20 m" came from. In 1000 Ω·m soil
it is 44 m; under a 0.25 µs subsequent stroke in 100 Ω·m it is only 7 m.

**The design consequence.** Electrode beyond `L_eff` is not merely of diminishing value —
during the front it is doing nothing at all. It still helps at power frequency, so a long
radial electrode is not wasted money if the same system also has to carry earth-fault
current. But if the reason you are adding it is lightning, adding *length* is the wrong
move; adding *conductor within the effective radius*, or moving the injection point, is
the right one.

### 10.5 The effective area of a meshed system, and why three formulas disagree

For a grid rather than a single radial electrode the same argument gives an **effective
radius** `r_eff` around the injection point, and an effective area `π r_eff²`. Three
published expressions are in common use and Earthing System reports all three:

```
Gupta & Thapar   r_eff = K (ρT)^0.5      K = 1.45 − 0.05 s   (centre-fed)
                                          K = 0.60 − 0.025 s  (corner-fed)
Conductor reach  r_eff = k (ρT)^0.5      equation (10.2) read as a radius
Grcev            r_eff = K exp[0.84 (ρT)^0.22]   K = 1 centre, 0.5 corner
```

where `s` is the mesh conductor spacing in metres. Gupta & Thapar's fit was made over
roughly 3 m to 15 m spacing; outside that band the linear `K` is an extrapolation and the
program says so.

Work the program's default switchyard: a 70 × 70 m grid at 7 m spacing in 400 Ω·m soil,
struck by a 1 µs front.

| | centre-fed | corner-fed |
|---|---|---|
| Gupta & Thapar | 22.0 m | 8.5 m |
| Conductor reach | 31.0 m | 28.0 m |
| Grcev | 23.1 m | 11.5 m |

The grid's own equivalent radius is `√(4900/π) = 39.5 m`. So on the most pessimistic
estimate, a corner-fed stroke puts **5 % of a 4900 m² grid to work**; on the most
optimistic, 50 %. That is a factor of six between two published formulas applied to the
same site, and it is not a defect in this program — it is the state of the published work.
Design on the smallest if the consequence of being wrong is an equipment failure, and on
the largest if it is only the cost of copper.

Two things the table does say unambiguously:

1. **Front time matters more than anything you can build.** Take the same grid to an 8 µs
   front and the centre-fed effective radius is 62 m — larger than the grid, so the whole
   thing participates. The 1 µs case is severe because it is fast, not because the grid is
   small.
2. **Where the current enters is a free design variable.** Every formula makes the
   corner-fed case roughly half the centre-fed one, because the current has a quadrant to
   spread into instead of the whole plane. Choosing which down-conductor lands where costs
   nothing and buys a factor of two.

### 10.6 Why the measured resistance flatters the design

This is the part that matters for safety. An earth resistance measured with a d.c. or 50 Hz
tester describes the whole electrode sitting at one potential. Under the front only the
effective part is carrying current, so the impedance the stroke actually sees is higher.

To first order, take the disc-electrode result `R = ρ/(4r)`: if only a radius `r_eff`
participates instead of the geometric `r_geom`, the impedance rises in the ratio of the
radii. Define the **impulse coefficient**

```
A = Z_impulse / R_measured ≈ r_geom / r_eff      (A ≥ 1)      … (10.3)
```

For the corner-fed 1 µs case above, `A ≈ 39.5 / 8.5 = 4.6`. A grid measured at 4.5 Ω
behaves like about 21 Ω during the front, and the peak earth potential rise for the class
III current of 100 kA is around **2100 kV rather than the 450 kV that I·R would give**.

Equation (10.3) is an estimate, not a measurement — a defensible number needs an impulse
test or a full field model (§10.7), and it deliberately ignores soil ionisation, which
pushes the other way (§10.1) and can be significant at high current density. But it is the
right order and it points the right way, which is what a warning has to do. Size
equipotential bonding and SPD coordination on the impulse value; never quote the measured
resistance as if it described the lightning performance of an extended earthing system.

### 10.7 The lightning response computed: the electromagnetic model (versions 1.5–1.6)

§10.4–10.6 put numbers on the impulse behaviour with closed-form estimates. For an electrode
of any shape the numerical page computes the response itself, in the frequency domain, in the
manner of Grcev's electromagnetic model and the HEM of Visacro and Soares. The conductors are
cut into segments; segment `k` carries a longitudinal current `I_L` along it and leaks a
transverse current `I_T` into the soil, and at angular frequency `ω`

```
(V_a + V_b)/2 = Σ_j Z^T_kj I_T,j
V_a − V_b    = Σ_j Z^L_kj I_L,j + Z_i,k I_L,k                           … (10.4)
Kirchhoff's current law at every node
```

with the couplings

```
Z^T_kj = 1/(4πκ ℓ_k ℓ_j) ∫∫ [ e^(−γR)/R + K e^(−γR')/R' ] dl dl'
Z^L_kj = jωμ₀/(4π) ∫∫ [ t_k·t_j e^(−γR)/R + K t_k·t'_j e^(−γR')/R' ] dl dl'
                                                                   … (10.5)

κ = σ + jωε,   γ = √(jωμ₀κ),   K = (κ − jωε₀)/(κ + jωε₀)
```

where the image current `t'_j` keeps only the vertical part of the current, mirrored, and
Sommerfeld integrals add what the image leaves out at high frequency. As `ω → 0` it is the
solver of §8. The harmonic impedance `Z(jω)` gives the potential rise for a lightning current
`i(t)`:

```
v(t) = R i(t) + F⁻¹{ [Z(jω) − R] I(jω) }
Z_p = max v / max i,     IC = Z_p / R                              … (10.6)
```

Soil may be constant or frequency dependent (Alipio–Visacro, CIGRE TB 781). The model
reproduces Grcev's Sommerfeld results within about 5 % from 100 Ω·m up, the potential rise
measured on a 3 m rod (CIGRE TB 781) within 9 % with frequency-dependent soil, and the
impulse coefficients of Alipio and Visacro.

**Layered soil (1.6).** The exact Green's functions of a stratified half-space follow from
two transmission lines along `z`, TM and TE, with `u_i = √(λ² + γ_i²)`, `Z^e_i = u_i/κ_i` and
`Z^h_i = jωμ₀/u_i` in layer `i`. With `V^e`, `V^h` their voltages for a unit shunt current and
`I^e` the current for a unit series voltage,

```
G = ∫₀^∞ g̃ J₀(λρ) λ dλ,       g̃_φ   = 2κ'(V^e − V^h)/λ²
g̃_A,h = 2V^h/(jωμ₀),          g̃_A,v = 2I^e/κ'                     … (10.7)
```

for the scalar potential and the vector potential of horizontal and vertical currents
(Michalski and Zheng's formulation C; `κ'` of the source layer). For `λ ≫ |γ|` these become
the image series of §8.6 with complex reflection coefficients `(κ_L − κ_M)/(κ_L + κ_M)`. The
software integrates the direct term and the images within about a metre of the electrode
exactly and tabulates the smooth remainder per frequency. Against the exact two-layer model of
Arnautovski-Toseva, Grcev and El Khamlichi Drissi (2007) for 10 m and 50 m wires in four
two-layer soils it agrees within 1 % up to 100 kHz and 3.5 % at 1 MHz for the 10 m wire, and
within 4.5 % up to 1 MHz for the 50 m wire (Figure 19); its low-frequency limit matches the
solver of §8 within 0.2 %. Image models alone (quasi-static images, with or without
retardation) missed the same benchmark by up to 26 %.

![Figure 19 — Harmonic impedance of end-fed horizontal wires (5 mm radius, 0.75 m deep, ε_r = 10) in two-layer soil: Earthing System (lines) against the exact Sommerfeld model of Arnautovski-Toseva et al. 2007 (circles). (a) 10 m wire; (b) 50 m wire.](figures/fig19_layered_hf.png)

*Figure 19 — Harmonic impedance of end-fed horizontal wires (5 mm radius, 0.75 m deep, ε_r = 10) in two-layer soil: Earthing System (lines) against the exact Sommerfeld model of Arnautovski-Toseva et al. 2007 (circles). (a) 10 m wire; (b) 50 m wire.*

**Soil ionisation (1.6).** Grcev (2009) combined the CIGRE/IEEE resistance under ionisation
with the frequency response: ionisation acts on the resistive drop `R i(t)` of (10.6) and the
reactive part `x(t)` is kept,

```
v_i(t) = R(t) i(t) + x(t)
R(t) = R / √(1 + i(t)/I_g),      I_g = E₀ρ / (2πR²)               … (10.8)
```

with `E₀` the critical field of the soil (400 kV/m CIGRE, 300 kV/m IEEE; 300–1500 kV/m have
been published, and a higher value is the cautious choice). For a single electrode Grcev also
gave `A_i = 1/√(1 + I_m/I_g) + A − 1`. His 10 m rod in 100 Ω·m (`R` = 11 Ω, `E₀` = 300 kV/m)
gives 8.3 Ω for the 30 kA first stroke (published 8.3 Ω) and 13.9 Ω for the 12 kA subsequent
stroke (published 13.4 Ω). The lesson is in Figure 20: ionisation lowers the slow first stroke
by a quarter, but the subsequent stroke peaks during its inductive rise, before the soil has
broken down, and is lowered by only 6 %.

![Figure 20 — A 10 m rod in 100 Ω·m soil under the Heidler currents used by Grcev (2009), without ionisation and with it (E₀ = 300 kV/m). (a) First stroke, 30 kA; (b) subsequent stroke, 12 kA. R(t) is the ionised resistance of (10.8).](figures/fig20_ionisation.png)

*Figure 20 — A 10 m rod in 100 Ω·m soil under the Heidler currents used by Grcev (2009), without ionisation and with it (E₀ = 300 kV/m). (a) First stroke, 30 kA; (b) subsequent stroke, 12 kA. R(t) is the ionised resistance of (10.8).*

**Foundations (1.6).** A conductor cast in concrete leaks through the concrete first. In the
lightning model the shell of §9.8 becomes an admittance `2πκ_c/ln(r_c/a)` per metre in series
with the soil, `κ_c = 1/ρ_c + jωε_c`, and the soil sees a conductor of the concrete's radius
(Figure 21).

![Figure 21 — (a) A 3.05 m rod bare and cast in 0.41 m of concrete against soil resistivity: Earthing System (lines) and Fagan and Lee's Table VII (markers); the concrete helps once the soil is more resistive than the concrete. (b) Harmonic impedance of a 3 m concrete pier (0.4 m, six 16 mm bars, ρ_c = 50 Ω·m) and a bare 3 m rod in 100 and 1000 Ω·m soil.](figures/fig21_foundation.png)

*Figure 21 — (a) A 3.05 m rod bare and cast in 0.41 m of concrete against soil resistivity: Earthing System (lines) and Fagan and Lee's Table VII (markers); the concrete helps once the soil is more resistive than the concrete. (b) Harmonic impedance of a 3 m concrete pier (0.4 m, six 16 mm bars, ρ_c = 50 Ω·m) and a bare 3 m rod in 100 and 1000 Ω·m soil.*

**Large electrodes (version 1.9.3).** The segment length at the injection is a fifth of the
soil's skin depth at the highest frequency (at most 1 m): there the current changes within
that distance. The model is held to 800 segments, and up to 1.9.2 a larger electrode had every
segment lengthened alike — 5 m on a 200 m grid, 20 m on a 400 m one — the injection included.
Away from the injection the current has either decayed (high frequencies) or varies slowly
(low ones), so the mesh is now graded: s(d) = s₀ + α·d with d the distance from the
injection, each conductor piece marched with the local length, and α the smallest value that
keeps the model within the limit (found by bisection). A grid cut at its crossings has a
least number of segments however coarse the mesh; when that is near the limit, the limit
gives way so that half of it remains for the fine mesh at the injection. Largest error of
|Z(jω)| over 100 Hz–10 MHz:

| Grid (corner feed unless noted) | Soil | Reference | Graded | Old uniform mesh |
|---|---|---|---|---|
| 40 m × 40 m, D 10 m | 100 Ω·m | uniform 0.21 m, 1920 seg. | 250 seg.: 0.07 % | 280 seg. (1.4 m): 0.7 % |
| 200 m × 200 m, D 20 m | 100 Ω·m | graded, 2400 seg. | 800 seg.: 0.09 % | 880 seg. (5 m): 3.5 % |
| same, fed at the centre | 100 Ω·m | graded, 2400 seg. | 800 seg.: 0.10 % | 880 seg.: 7.9 % |
| 200 m × 200 m, D 20 m | 30 Ω·m | graded, 2400 seg. | 800 seg.: 0.07 % | 880 seg.: 14.7 % |
| 400 m × 400 m, D 20 m | 100 Ω·m | graded, 2400 seg. | 1240 seg.: 0.10 % | 840 seg. (20 m): 68 % |

The 40 m case is against a uniform mesh at the full fine length; the larger ones against a
graded mesh with three times the segments. R_LF is within 0.1 % everywhere; the impulse
impedance of the TB 781 strokes, whose energy lies below 1 MHz, moved by at most 3 % with the
old mesh, but |Z| at a few megahertz — the steep fronts — was badly wrong.

**Limits.** Conductors are thin wires. A foundation is a cylinder of concrete (rafts and
blocks are not modelled, nor is breakdown of the concrete, which Fagan and Lee observed under
impulse current). All layers share one frequency dependence and permittivity. The ionisation
formula is instantaneous and was recommended for electrodes up to about 30 m. 

---

### 10.8 Does the structure need protection? — IEC 62305-2:2024 (version 1.8.5)

The risk assessment decides whether a lightning protection system is needed at all and how
much. Edition 3 (2024) of IEC 62305-2 has one risk, the sum of the injury to living beings
(L1) and the physical damage (L2),

    R = R_L1 + R_L2,   tolerable R_T = 10⁻⁵ per year,

and judges the internal systems by their **frequency of damage**

    F = F_C + F_M + F_W + F_Z,   tolerable F_T = 0.1 /yr (critical) or 1 /yr (non-critical),

both in every risk zone — a part of the structure with its own floor, fire compartment,
loss class and equipment, and outside areas where people stand.

**Dangerous events.** Lightning location systems count flashes, but one flash often strikes
the ground at several points, so the 2024 edition works with the strike-point density
N_SG = k·N_G (k = 2 unless the data provider gives it). With A_D as before,

    N_D = N_SG·A_D·C_D·10⁻⁶,
    N_M = (N_SG/k)·A_M·10⁻⁶,       A_M = 2r_M(L + W) + πr_M²,   r_M = 350/U_w,
    N_L = N_SG·40L_L·C_I·C_E·C_T·10⁻⁶,
    N_I = (N_SG/k)·2r_I·L_L·C_I·C_E·C_T·10⁻⁶,   r_I = 2000/U_w^1.8,

summed over the sections of each line (an HV section beyond the transformer has C_T = 0.2,
a buried one C_I = 0.3). The equipment withstand U_w now sets how far away a flash still
matters: for 2.5 kV r_I = 384 m, for 1.5 kV 964 m.

**Components** (Table 3) are N × P × L with the presence of people P_P = t_z/8760 and the
exposure of equipment P_e = t_e/8760 written out:

    R_AT = N_D·P_AT·P_P·L_T,   R_AD = N_D·P_AD·P_P·L_D (people on a roof),
    R_B1 = N_D·P_B·P_P·L_F1,   R_B2 = N_D·P_B·L_F2,
    R_C1 = N_D·P_C·P_P·P_e·L_O1,  R_M1 = N_M·P_M·P_P·P_e·L_O1,
    R_U = (N_L + N_DJ)·P_U·P_P·L_T,  R_V1,2, R_W1,2 likewise,  R_Z1 = N_I·P_Z·P_P·P_e·L_O1,

with P_B = P_S·P_LPS·r_f·r_p (P_S = 1 once an LPS is installed), P_C = 1 − Π(1 − P_SPD·C_LD)
and P_M = 1 − Π(1 − P_SPD·(K_S1K_S2K_S3)²) over the internal systems in the zone, and the
thunderstorm-warning factor P_TWS in the touch and line probabilities. The fire reduction
factors r_f and r_p have moved from the loss to the probability, and the losses are the
typical values of Table C.2 by loss class (low, normal, high, very high).

The module reproduces the worked examples of Annex F: for the house R = 1.793·10⁻⁵ falling to
0.149·10⁻⁵ with LPL IV SPDs at the entrance; for the office building's archive R = 6.53·10⁻⁵
and F = 0.584 /yr, and with an LPS class II and SPDs to LPL II R = 0.59·10⁻⁵ and F = 0.014;
the hospital's intensive care unit R = 306.8·10⁻⁵. It then searches the LPS class, the SPD
level of the bonding at the line entrances (an LPS brings its own) and the coordinated SPD
level, one step each, for the cheapest set that meets R_T in every zone and F_T wherever it is
set; the class found can be sent to the earth-termination design.

**Damage to the surroundings (Annex E, version 1.9.5).** Where a strike on the structure can
harm people or property outside it — an explosion, a fire, a toxic or radioactive release,
pollution of soil or water — Annex E adds, for the zone where the damage starts, the
components of its Table E.1. They are those of Table 3 with the presence of people in the
surroundings P_PE = t_zE/8760 (Table E.2; 1 when it is not known) in place of P_P and the
losses of the surroundings in place of the zone's:

    R_B1E = N_D·P_B·P_PE·L_F1E,   R_B2E = N_D·P_B·L_F2E,
    R_C1E = N_D·P_C·P_PE·P_e·L_O1E,  R_C2E = N_D·P_C·P_e·L_O2E,

and likewise R_M, R_V, R_W and R_Z; R_AT, R_AD and R_U have no counterpart. L_F1E and L_O1E
come from Table E.3, separately for damage that stays inside the site fence and damage that
spreads beyond it (toxic fumes: 0.1 and 1.0 for L_F1E), and L_F2E, L_O2E from Table E.4. The
surge components count only where a failure of internal systems can itself cause the damage;
otherwise the annex asks for them to be taken as zero. The components are added to the
zone's R_L1 and R_L2. With t_zE = t_z and fire and explosion only, this is the simple method
of (C.1)–(C.2), L_BT = L_B + L_E, which the program reproduces.

### 10.9 Surge protective devices — IEC 62305-4:2024 (version 1.8; 2024 rules 1.8.5)

About half of a direct flash goes into the earth termination and half into the services; it
divides between the services and their conductors, so a Type 1 SPD on a four-conductor power
line, with two services, must take I_imp = 0.5·200/(2·4) = 12.5 kA for LPL I. Its effective
protection level includes its connecting leads, U_p/f = U_p + ΔU for a voltage-limiting SPD
and max(U_p, ΔU) for a switching one, with ΔU = 0.1·I_SPD kV per metre of lead (IEC 62305-4:2024
C.4: 1 kV per metre at 10 kA), and protects the equipment only if

    U_p/f ≤ U_w           at the equipment,
    U_p/f ≤ 0.8·U_w       for a circuit up to 10 m,
    U_p/f ≤ (U_w − U_i)/k for a longer circuit, k = 1…2 the reflection factor (2 when unknown:
                          oscillation can double the voltage),

and U_p ≤ 0.5·U_w where the failure of the internal systems is critical. For the simplified
selection at the origin of the installation, Table C.3 gives I_imp per protection mode —
25, 18.75 and 12.5 kA for LPL I, II and III–IV on L–PE and N–PE (CT1), with the N–PE gap of a
CT2 connection taking two or four times that —

with U_i the voltage induced in the circuit loop. Two stages share the energy only with enough
impedance between them — about 10 m of cable from a spark gap to a varistor, about 5 m between
two varistors, or a decoupling inductor — unless the manufacturer declares them coordinated.

## 11. Air termination and protection zones — module 8
### 11.1 What the rolling sphere actually is

Module 7 asks where the lightning current goes once it is in the building. This module asks
the earlier question: **where does the flash attach in the first place, and what does that
attachment point protect?**

A downward leader descends in steps of a few tens of metres, and at each step it has not yet
"chosen" where it will land. It commits only when some earthed object comes within the
**striking distance** — the separation at which the field between the leader tip and that
object is enough to launch the connecting upward leader. The striking distance is set by the
charge already in the channel, and therefore by the peak current the stroke will carry:

```
r_s ≈ 10 · I^0.65          (metres, I in kA)          … (11.1)
```

Now roll that idea around. Draw a sphere of radius `r_s` centred on the leader tip. The
first earthed object the sphere touches is the object that gets struck. Sweep the leader tip
over every possible approach and the sphere sweeps out a surface: **everything the sphere can
touch is a possible strike point, and everything it cannot reach is protected.** That single
sentence is the whole of the rolling sphere method, and every closed-form result below is
derived from it rather than tabulated.

The class fixes the radius, because the class fixes the *smallest* current the system must
catch. A smaller minimum current means a shorter striking distance, a smaller sphere, and a
sphere that can nestle into more places — so a higher protection level is a *smaller* sphere:

| Class | `I_min` | Rolling sphere `R` | Mesh size | Interception probability |
|-------|---------|--------------------|-----------|--------------------------|
| I     | 3 kA    | 20 m               | 5 × 5 m   | 0.99 |
| II    | 5 kA    | 30 m               | 10 × 10 m | 0.97 |
| III   | 10 kA   | 45 m               | 15 × 15 m | 0.91 |
| IV    | 16 kA   | 60 m               | 20 × 20 m | 0.84 |

Note the direction of the trade: class IV misses about one flash in six of those below its
design current — but those are the weak strokes, which do the least damage.

### 11.2 Deriving the protected radius

Take one vertical air termination of height `h` standing on flat ground. A sphere resting on
the ground has its centre at height `R`. It touches the tip when the horizontal distance from
the mast is

```
a(h) = √(2·R·h − h²)                              … (11.2)
```

which is just the circle equation `x² + (R − h)² = R²` rearranged. Anything on the ground
closer than `a(h)` is under the arc and cannot be reached, so `a(h)` is the protected radius
at ground level. If instead you are protecting a plane at height `h_x` — a roof, a tank top,
a switchyard platform — the same construction on that plane gives

```
r_p = a(h) − a(h_x)                               … (11.3)
```

This is the formula every handbook quotes, and (11.2) is where it comes from.

Two consequences are worth dwelling on, because both are counter-intuitive:

- `a(h)` is maximum at `h = R` and **decreases** beyond it. Geometrically the sphere starts
  to nestle in beside a very tall mast. Physically the mast has become tall enough to be
  struck on its *side*, so its tip no longer shields the ground beside it. Once `h ≥ R` the
  mast body itself holds the sphere off at exactly `R`, and the protected radius saturates:
  `r_p = R − a(h_x)`. A taller mast is not indefinitely better.
- The protective angle method (§11.5) is *not* valid above `h = R` for exactly this reason:
  a cone has no way to express a radius that stops growing.

### 11.3 The sag between two terminations

Put two terminations of equal height `h` a distance `d` apart. A sphere resting on both has
its centre `√(R² − (d/2)²)` above the line joining the tips, so the lowest point the sphere
reaches on that span is depressed below the tips by the **penetration**, or sag:

```
p = R − √(R² − (d/2)²)                            … (11.4)
```

The protected height at mid-span is therefore `h − p`. Set that equal to the plane you are
protecting and solve for `d` to get the largest spacing you may use:

```
d_max = 2·√(R² − (R − h)²) = 2·a(h)               … (11.5)
```

This is the single most useful number on the page. It is also the number that catches people
out: on a 10 m building under class III (`R = 45 m`), 1 m rods on the two roof edges 20 m
apart give `p = 1.13 m` against a rod height of 1 m — the sphere reaches the roof by 130 mm
and the design fails. The remedy is 1.2 m rods, or one more rod, not a bigger earth
electrode. Earthing System reports `p`, the protected height at mid-span, and the tip height that
would be required at the spacing you entered.

### 11.4 Why roof edges and corners are special

A sphere resting on the *ground* beside the wall reaches the roof edge while it is still far
from the middle of the roof. So an air termination in the centre of a flat roof can protect
the whole roof field and still leave every edge and corner exposed. That is not a quirk of
the arithmetic; it is why IEC 62305-3 clause 5.2.3 asks for terminations on the corners and
along the exposed edges — in practice a perimeter conductor with short rods at the corners —
rather than relying on a single central mast.

Earthing System tests the roof field and the roof edges as two separate criteria, because the
remedy for each is different, and reports them separately in the elevation and in the report.

### 11.5 The protective angle method, and its limits

The protective angle method replaces the arc with a straight cone: a termination of height
`h` protects a cone of half-angle `α`, so a circle of radius `h·tan α` on the reference
plane. `α` is read from IEC 62305-3 Figure 1 as a function of `h` and the class, and the
method is permitted **only for simple shapes and only while `h ≤ R`**.

Two cautions belong with it:

- Figure 1 is published as a *graph*, not as a table of numbers. The values in
  `earthsys/airterm.py` are a digitisation of that graph and should be checked against your
  own copy of the standard before they go into a submitted design. The rolling sphere, by
  contrast, is derived exactly from (11.2)–(11.4), which is why Earthing System treats it as the
  governing result and shows the angle only for comparison.
- The two methods do not always agree, and neither is uniformly conservative. The program
  reports both radii side by side and says which is the smaller, so the disagreement is
  visible rather than hidden.

### 11.6 The mesh method

On a large flat roof, rolling a sphere would demand an impractical forest of rods. The mesh
method instead covers the surface with a conductor grid fine enough that no point of the
surface is further from a conductor than the mesh size for the class (5, 10, 15 or 20 m). The
mesh must follow the roof edges, take the shortest possible route, and be bonded to
down-conductors at typically 10–20 m of perimeter per conductor (Table 4). It is the normal
solution for a warehouse or a plant building; the rolling sphere is the normal solution for
a mast, a tank farm or an irregular structure.

### 11.7 How the module computes it

For anything more complicated than one or two masts on flat ground — masts of different
heights, a rod standing on a roof, a catenary wire, a building whose own edges intercept the
flash — there is no closed form. Earthing System therefore rolls the sphere numerically:

1. Every solid surface is **sampled into capture points**: the tips and shafts of the
   terminations, the roof line, the wall tops, any catenary.
2. A ball of radius `R` is **marched** over that point set from left to right. It either
   slides along the ground until it first touches a capture point, or pivots about the point
   it is resting on until it meets the next point — or falls back to the ground.
3. Each resting position, touching two supports, contributes one **arc of radius `R`** to the
   boundary of the protected volume. The sequence of arcs is the envelope drawn on the
   elevation.
4. The envelope is sampled into a height profile `z(x)`; anything below it is protected and
   anything on or above it can be touched.

The march reproduces (11.2) and (11.4) to within the sampling resolution, and the test suite
asserts exactly that — the closed form and the numerical roll check each other. What the
march adds is every case the closed form cannot express.

A last word on what this module does *not* do. It decides where the flash attaches and what
that attachment protects. It says nothing about the current once it is in the conductor —
that is module 7, and the two must both pass. A perfect air termination discharging into an
inadequate earth termination simply moves the damage.

---

## 12. System neutral grounding — module 9
### 12.1 The problem with an ungrounded system

An "ungrounded" system is not isolated from earth; it is capacitively coupled to it through
the distributed cable capacitance `C₀`. A single earth fault therefore draws only the
charging current `3I_C0`, and the system keeps running — which is why ungrounded systems
were popular.

The failure mode is the **arcing (restriking) ground fault**. The arc extinguishes at a
current zero, leaving the healthy phases charged. Half a cycle later the recovery voltage
restrikes the arc, pumping more energy into the L-C circuit. Each restrike ratchets the
trapped charge up, and voltages of 5–6 per unit can develop — puncturing insulation
somewhere else entirely, often in a machine winding far from the original fault.

### 12.2 High-resistance grounding — why `I_R ≥ 3I_C0`

Insert a resistor in the neutral. Now the fault circuit is `R` in parallel with the
capacitive path. The resistor **drains the trapped charge** between half cycles, so the
ratchet cannot build. The criterion is that the resistive current must at least equal the
capacitive current:

```
I_R ≥ 3 I_C0,     R_N = V_LN / I_R          … (12.1)
```

Satisfying it limits transient overvoltage to about 2.5 per unit, which insulation can
withstand indefinitely.

The first job on this page is therefore to estimate `3I_C0 = 3 · 2πf C₀ V_LN`, plus
allowances for motors and transformers. Cable capacitance dominates: a plant with 8 km of
6.6 kV cable at 0.25 µF/km has `3I_C0 ≈ 7 A`, so a resistor passing ~7 A (about 530 Ω)
does the job and the system can run with a standing earth fault while it is located.

**The limit of the method:** if `3I_C0` exceeds about 10 A the arc will not self-extinguish
and high-resistance grounding is no longer appropriate — move to low-resistance grounding
and trip on the first fault.

### 12.3 "Effectively grounded" and arrester selection

```
X₀/X₁ ≤ 3   and   R₀/X₁ ≤ 1          … (12.2)
```

When both hold, the healthy-phase voltage rise during an earth fault stays below about
1.4 per unit, and **80 % rated surge arresters** may be used. When they do not, the healthy
phases can approach full line voltage (1.73 pu) and full-rated arresters are required. This
is the direct link between the earthing philosophy and the insulation coordination of the
whole installation — a good closing point for a course, because it shows that earthing is
not a bolt-on but a system-level decision.

---

## 13. Reading a verdict

Every compliance row in Earthing System can be expanded to show four things. Teach students to
read them in this order:

1. **What the criterion means** — the physics being protected against. If they cannot state
   this, the number is meaningless to them.
2. **What drives the number** — the formula with the actual values substituted, so they can
   see which factor is large.
3. **Why it passed or failed** — the quantified comparison, with the percentage.
4. **How to fix it** — each remedy with its computed magnitude ("reduce `t_s` from 0.50 s
   to 0.35 s"), so the choice between levers is an engineering judgement about cost and
   feasibility rather than guesswork.

The same four blocks appear in the generated report, so a design review can be held on the
document alone.

**A caution to teach alongside the badges.** A PASS is a statement about a model, not about
a site. It is conditional on the soil model being right (measured, in the correct season),
on the fault current being right (from the utility's study, not a guess), and on the
installation matching the drawing. The report's disclaimer says this, and it should be read
aloud in class at least once.

---

## 14. A suggested teaching sequence

Four sessions of about two hours, each ending with the students running the software
themselves.

**Session 1 — Physics and soil (chapters 1–2).**
Derive `V = ρI/2πr`, the foot resistance, and the tolerable-voltage formulas. Then have
students measure or be given a Wenner traverse and invert it. Exercise: take the example
traverse, delete the two largest spacings, re-fit, and explain why `ρ₂` and `h` move so much
— it teaches what the data actually constrain.

**Session 2 — Fault current and conductors (chapters 3–4).**
Derive the decrement factor and the adiabatic equation. Exercise: size the same conductor
for a bolted joint and for an exothermic weld and compare the copper cost. Then vary `S_f`
from 1.0 to 0.2 and watch the whole design change.

**Session 3 — The grid (chapters 5–7).**
Reproduce IEEE 80 Annex B step by step by hand, then in the software, and confirm every
intermediate value. Exercise: it fails on mesh voltage — have each student fix it by a
different lever and compare the resulting designs on cost and robustness.

**Session 4 — Numerical methods and the rest (chapters 8–12).**
Run the same grid through the boundary-element solver and compare. Exercise: make the grid
L-shaped and observe that the closed-form and numerical answers now diverge; discuss which
to believe. Then a domestic TT design and a lightning earth termination, ten minutes each.
Finish on the rolling sphere: put 1 m rods on the two edges of a 20 m roof under class III,
watch it fail by 130 mm, and have the students find the three different ways to fix it —
taller rods, a third rod, or a finer mesh. It is the clearest demonstration in the whole
course that geometry, not resistance, is what protects a structure from a direct strike.

**Optional session 5 — Layers, separate metal and lightning (§2.8, §8.6–8.9, §9.7–9.8, §10.7).**
Fit the H-type traverse of the soil page with two and three layers and read the F test; put
the Annex B grid on both models and compare `R_g`. Add an isolated fence and find the two
touch voltages; then bond it and compare. Run a 2 km pipe out of the station with and without
an insulating joint. Finish with the lightning card: a 3 m rod, then the same rod in a
concrete pier, then two-layer soil and ionisation, and explain each change in the impulse
coefficient.

**Assessment idea.** Give each student a different soil traverse and fault level and ask
for a complete design report, generated by the software but with a written justification of
every input choice — because the software will happily compute a beautiful answer from
wrong inputs, and knowing which inputs matter is the actual skill.

---

## 15. Symbols

| Symbol | Meaning | Unit |
|---|---|---|
| ρ, ρ₁, ρ₂ | Soil resistivity; upper and lower layer | Ω·m |
| ρ_s | Surface-layer resistivity | Ω·m |
| ρₐ | Apparent resistivity from a field measurement | Ω·m |
| K | Reflection coefficient `(ρ₂−ρ₁)/(ρ₂+ρ₁)` | – |
| h | Burial depth, or upper-layer thickness | m |
| h_s | Surface-layer thickness | m |
| C_s | Surface derating factor | – |
| A | Grid area, or conductor cross-section | m², mm² |
| D | Conductor spacing in the grid | m |
| d | Conductor diameter | m |
| L_C, L_R, L_T | Horizontal, rod and total buried length | m |
| L_M, L_S | Effective length for mesh and step voltage | m |
| n, K_m, K_i, K_s, K_ii, K_h | IEEE 80 geometric factors | – |
| R_g, R_A | Earth resistance of a grid / installation electrode | Ω |
| GPR | Ground potential rise | V |
| E_m, E_s | Computed mesh (touch) and step voltage | V |
| E_touch, E_step | Tolerable touch and step voltage | V |
| I_B | Tolerable body current | A |
| R_B, R_f | Body and foot resistance | Ω |
| I_G, I_g, 3I₀ | Maximum grid, symmetrical grid, and zero-sequence current | A |
| D_f, S_f, C_p | Decrement, split and growth factors | – |
| T_a | DC time constant `X/(ωR)` | s |
| t_s, t_c, t_f | Shock, conductor and fault duration | s |
| TCAP, α_r, ρ_r, K₀, T_m | IEEE 80 material constants | – |
| k | IEC 60364 adiabatic constant | A·s^½/mm² |
| Z_s, Z_e, I_a | Loop impedance, external loop, device operating current | Ω, A |
| IΔn | RCD rated residual current | A |
| l₁, s, k_i, k_c, k_m | IEC 62305 electrode length and separation factors | m, – |
| 3I_C0, R_N | System charging current, neutral resistor | A, Ω |
| ρ₃, ρ₄, h₁ … h₃ | Resistivities and thicknesses of further layers | Ω·m, m |
| S, T | Conductance `h/ρ` and transverse resistance `ρh` of a thin layer | S, Ω·m² |
| Z, E | Mutual-resistance matrix of separate networks; network incidence matrix | Ω, – |
| z, g, γ | Series impedance, leakage and propagation constant of a long conductor | Ω/m, S/m, 1/m |
| ρ_c, r_c, a_eq | Concrete resistivity, concrete radius, equivalent bar radius | Ω·m, m, m |
| κ, γ | Complex conductivity `σ + jωε`, propagation constant `√(jωμ₀κ)` | S/m, 1/m |
| Z(jω), Z_p, IC | Harmonic impedance, impulse impedance, impulse coefficient | Ω, Ω, – |
| E₀, I_g | Critical field of the soil, ionisation current | kV/m, kA |

---

## 16. The wider standards landscape

Earthing System computes to IEEE 80, IEC 60364, IEC 62305 and IEEE 142 (with IEC 60909 for the
fault current and BS 7430 for the rod factors). Version 1.3 places them among the other
standards a designer meets. `earthsys/standards.py` holds the registry (edition, status,
area, and whether the software *implements*, *cross-checks* or only *references* each) and
the small calculations below. None of them changes a verdict.

**Three families of touch-voltage criterion.**

- **IEEE 80.** Dalziel, `R_B = 1000 Ω`, and the surface layer through `C_s` (§5).
- **BS EN 50522:2022 and IEC 61936-1.** The permissible touch voltage `U_Tp(t_F)` comes
  from the IEC 60479-1:2018 body impedance and curve c2. The tabulated values are 716, 654,
  537, 220, 117, 96, 86 and 85 V at 0.05, 0.1, 0.2, 0.5, 1, 2, 5 and 10 s. Footwear and the
  surface layer enter as series resistances:
  `U_vTp = U_Tp + (R_F1 + 1.5·ρ_s)·U_Tp/Z_B(U_Tp)`. The like-for-like IEEE 80 value is the
  bare-soil limit `1000·k/√t`. At 0.5 s it is 222 V (70 kg), against `U_Tp = 220 V`.
- **AS 2067:2016 with ENA EG-0 and EG-1** (ENA DOC 025-2022 and 045-2022). The criterion is
  a risk. `P_coinc = f_n·p_n·(f_d + t_d)·T / (365·24·3600)` and
  `P_fatality = P_coinc·P_fib`. The risk is negligible below 10⁻⁶ per year, intolerable
  above 10⁻⁴, and ALARP between.

**Testing.** IEEE 81-2012 (now 81-2025) and, in the UK, ENA TS 41-24:2018. The latter adds
current-injection and slope methods for large grids, and maintenance testing.

**Fault-current distribution.** ENA EREC S34:2018 uses the reduction factor
`r = |1 − z_m/z_s|` of each return conductor. For a cable screen, `z_m = z_s − R_scr`, so
`r = R_scr/|z_s|`. A 0.2 Ω/km copper screen in 100 Ω·m soil gives `r = 0.29`: 71 % of the
fault current returns in the screen. CIGRE TB 347 covers the EPR transferred by specially
bonded screens.

**Wiring rules.** AS/NZS 3000:2018 (MEN), BS 7671:2018+A4:2026 (PME), and BS 7430 (the 2011
edition is implemented; the 2026 edition is published).

**Data centres and telecommunications.** IEC 60364-5-548 (withdrawn 2002), IEEE 1100-2005
and BS EN 50310 use a mesh bonding network with openings `a ≤ c/(10·f_max)`: 1 m at 30 MHz.
AS/NZS 3835.1 and EREC S34 bound the EPR zone at `x = ρ·I_E/(2π·V_lim)`. For 5.48 kA in
100 Ω·m, the 430 V boundary is at 203 m.

**Frequency-dependent soil (CIGRE TB 781).**
`σ(f) = σ0 + σ0·1.26·σ0^−0.73·(f/1 MHz)^0.54` (σ in mS/m), with the matching permittivity.
A 1000 Ω·m soil behaves as 627 Ω·m at 250 kHz. Using the low-frequency value is conservative
for the EPR. Module 7 reports the frequency-dependent value.

**Overhead lines and renewables.**

- AS/NZS 7000:2016 and CIGRE TB 839: the critical backflashover current is
  `I_c ≈ CFO/((1 − c)·R_i)`.
- IEC 61400-24 and IEEE 2760-2020 for wind. IEEE 2760 is sometimes miscited as 2870.
- IEEE 2778-2020 for solar.

**Pipelines and HVDC.**

- AS/NZS 4853:2012 and CIGRE TB 95: the Carson mutual impedance is
  `z_m = π²f·10⁻⁴ + j·4πf·10⁻⁴·ln(D_e/d)` Ω/km, with `D_e = 658.5·√(ρ/f)`, and the induced
  EMF is `E = k·|z_m|·L·I_f`.
- EPRI EL-2020: the electrode thermal limit `Δθ_max = V²/(2ρλ)` holds for any electrode
  shape, and Faraday's law `m = M·I·t/(z·F)` gives 9.13 kg of iron per ampere-year.

## References

**Standards implemented** (the calculations follow these editions)

1. IEEE Std 80-2013, *IEEE Guide for Safety in AC Substation Grounding* (incl. Cor 1-2015)
2. IEEE Std 81-2012, *IEEE Guide for Measuring Earth Resistivity, Ground Impedance, and Earth Surface Potentials of a Grounding System* (superseded by IEEE Std 81-2025)
3. IEEE Std 142-2007, *IEEE Recommended Practice for Grounding of Industrial and Commercial Power Systems* (Green Book)
4. IEEE Std C62.92 series, *IEEE Guide for the Application of Neutral Grounding in Electrical Utility Systems*
5. IEC 60364-4-41:2005+A1:2017, *Low-voltage electrical installations — Protection against electric shock*
6. IEC 60364-5-54:2011+A1:2021, *Earthing arrangements and protective conductors*
7. IEC 60909-0:2016, *Short-circuit currents in three-phase a.c. systems — Calculation of currents*
8. IEC 62305-1, -2, -3 and -4:2024, *Protection against lightning* (edition 3)
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
43. L. Grcev, "Modeling of grounding electrodes under lightning currents", *IEEE Trans. Electromagnetic Compatibility*, 51(3), 2009
44. K. A. Michalski and D. Zheng, "Electromagnetic scattering and radiation by surfaces of arbitrary shape in layered media, Part I: Theory", *IEEE Trans. Antennas and Propagation*, 38(3), 1990
45. V. Arnautovski-Toseva, L. Grcev and K. El Khamlichi Drissi, "High frequency electromagnetic analysis of horizontal grounding conductor and near-by passive parallel conductor within two-layer soil", *Proc. 15th Int. Conf. on Software, Telecommunications and Computer Networks (SoftCOM)*, IEEE, 2007
46. V. Arnautovski-Toseva and L. Grcev, "Image and exact models of a vertical wire penetrating a two-layered earth", *IEEE Trans. Electromagnetic Compatibility*, 53(4), 2011
47. V. Arnautovski-Toseva and L. Grcev, "On the image model of a buried horizontal wire", *IEEE Trans. Electromagnetic Compatibility*, 58(1), 2016
48. E. J. Fagan and R. H. Lee, "The use of concrete-enclosed reinforcing rods as grounding electrodes", *IEEE Trans. Industry and General Applications*, IGA-6(4), 1970
49. P. Wiener, "A comparison of concrete encased grounding electrodes to driven ground rods", *IEEE Trans. Industry and General Applications*, IGA-6(3), 1970
50. I. F. Gonos and I. A. Stathopulos, "Estimation of multilayer soil parameters using genetic algorithms", *IEEE Trans. Power Delivery*, 20(1), 2005
51. CIGRE TB 781 (2019) and S. Visacro and R. Alipio, "Frequency dependence of soil parameters", *IEEE Trans. Power Delivery*, 27(2), 2012 — frequency-dependent soil in the lightning model
52. IEEE Std 80-2013 Annex H — benchmark grids with fences (Grids 4 and 5)
53. Electric Power Research Institute, *Touch and Step Voltage Measurements on Field Installed Ground Grid and Concrete Pads*, Technical Update 1018976, 2009
54. L. S. Edwards, "A modified pseudosection for resistivity and IP", *Geophysics*, 42(5), 1977 — median depth of investigation of the Wenner and Schlumberger arrays
55. M. Bebendorf, "Approximation of boundary element matrices", *Numerische Mathematik*, 86(4), 2000 — adaptive cross approximation (compressed solver, 1.8.7)
56. Y. Saad and M. H. Schultz, "GMRES: a generalized minimal residual algorithm for solving nonsymmetric linear systems", *SIAM J. Sci. Stat. Comput.*, 7(3), 1986
57. F. H. Read, "Capacitances and singularities of the unit triangle, square, tetrahedron and cube", *COMPEL*, 23(2), 2004 — the reference value for plates (1.9.0)
