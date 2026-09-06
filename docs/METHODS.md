# EarthSystem — methods and equations

Every equation the software applies, with its source clause. Symbols follow the
originating standard.

---

## 1. Soil

**Field reduction** (IEEE Std 81-2012 §8)

    Wenner (b ≪ a)          ρₐ = 2πaR
    Wenner (exact)          ρₐ = 4πaR / [1 + 2a/√(a²+4b²) − 2a/√(4a²+4b²)]
    Schlumberger            ρₐ = πR(s² − (d/2)²)/d
    Driven rod (3-point)    ρ  = 2πLR / [ln(8L/d) − 1]

**Two-layer forward model** — image series with K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁)

    Wenner          ρₐ(a) = ρ₁ [ 1 + 4 Σₙ Kⁿ ( 1/√(1+(2nh/a)²) − 1/√(4+(2nh/a)²) ) ]
    Schlumberger    ρₐ(s) = ρ₁ [ 1 + 2 Σₙ Kⁿ / (1 + (2nh/s)²)^{3/2} ]

**Inversion** — (ρ₁, ρ₂, h) are optimised in log space with a dependency-free
Nelder–Mead simplex, minimising Σ((ρ_model − ρ_meas)/ρ_meas)². Nine starting points
are tried to avoid local minima. The reported RMS error is that residual in percent.

**Equivalent uniform resistivity** (IEEE Std 80-2013 §13.4) — depth-weighted average
over the electrode penetration when the electrodes cross the interface, otherwise ρ₁.

---

## 2. Fault current

**IEC 60909-0:2016**

    Three-phase             Iₖ″   = c·Uₙ / (√3·Z₁)                    Eq. (29)
    Peak                    iₚ    = κ·√2·Iₖ″,  κ = 1.02 + 0.98·e^(−3R/X)
    Line-to-earth           Iₖ₁″  = √3·c·Uₙ / |Z₁ + Z₂ + Z₀ + 3Z_f|    Eq. (52)
    Double line-to-earth    Iₖ₂E  = √3·c·Uₙ·|Z₂| / |Z₁Z₂ + Z₁Z₀ + Z₂Z₀|
    Thermal equivalent      I_th  = Iₖ″·√(m + n)                       Eq. (66)
    Network impedance       Z_Q   = c·Uₙ² / Sₖ″
    Transformer             Z_T   = u_k·Uₙ² / (100·S_r)

**IEEE Std 80-2013 clause 15**

    Decrement factor        D_f = √[ 1 + (T_a/t_f)(1 − e^(−2t_f/T_a)) ],  T_a = X/(2πfR)   Eq. (79)
    Split factor            S_f = |Z_r| / |Z_r + R_g|                                      Annex C
    Grid current            I_g = S_f·C_p·3I₀ ;   I_G = D_f·I_g                            Eq. (77)–(78)

---

## 3. Conductor sizing

**IEEE Std 80-2013 Eq. (37)**

    A[mm²] = I[kA] / √( (TCAP·10⁻⁴)/(t_c·α_r·ρ_r) · ln[(K₀ + T_m)/(K₀ + T_a)] )

with the full Table 1 material set (15 materials). T_m is limited by the joint type when
one is selected: exothermic weld 1083 °C, brazed 450 °C, bolted/pressure 250 °C.

**IEC 60364-5-54 clause 543.1.2**

    S = √(I²t) / k

k from Tables A.54.2 (separate PE), A.54.3 (PE as a cable core) and 54.6 (buried).

**Simplified PE selection** (Table 54.2): S ≤ 16 → S_PE = S; 16 < S ≤ 35 → 16 mm²;
S > 35 → S/2, scaled by k₁/k₂ for a different material.

**Minimum buried earthing conductor** (Table 54.1): 25 mm² Cu / 50 mm² steel when not
protected against corrosion; 16 mm² when corrosion-protected but not mechanically
protected; 2.5 mm² Cu / 10 mm² steel when fully protected.

**Bonding** (§544): main protective bonding ≥ half the earthing conductor, minimum 6 mm²,
need not exceed 25 mm² copper.

---

## 4. Substation grid — IEEE Std 80-2013

**Safety criteria**

    C_s      = 1 − 0.09(1 − ρ/ρ_s)/(2h_s + 0.09)                Eq. (27)
    E_step   = (1000 + 6C_sρ_s)·k/√t_s
    E_touch  = (1000 + 1.5C_sρ_s)·k/√t_s
    k = 0.116 (50 kg) or 0.157 (70 kg)                          Eq. (29)–(33)

**Resistance**

    Sverak   R_g = ρ[ 1/L_T + 1/√(20A)·(1 + 1/(1 + h√(20/A))) ]  Eq. (52)

    Schwarz  R₁ = ρ/(πL_C)·[ ln(2L_C/h′) + k₁L_C/√A − k₂ ]
             R₂ = ρ/(2πn_R L_R)·[ ln(8L_R/d_R) − 1 + 2k₁L_R(√n_R − 1)²/√A ]
             R_m = ρ/(πL_C)·[ ln(2L_C/L_R) + k₁L_C/√A − k₂ + 1 ]
             R_g = (R₁R₂ − R_m²)/(R₁ + R₂ − 2R_m)                Eq. (56)–(60)

with h′ = √(d·h) and k₁, k₂ from the Figure 25 fits, bilinearly interpolated in h/√A:

| depth | k₁ | k₂ |
|---|---|---|
| 0 | −0.04(L_x/L_y) + 1.41 | −0.15(L_x/L_y) + 5.50 |
| √A/10 | −0.05(L_x/L_y) + 1.20 | +0.10(L_x/L_y) + 4.68 |
| √A/6 | −0.05(L_x/L_y) + 1.13 | −0.05(L_x/L_y) + 4.40 |

**Geometry factor**

    n = n_a·n_b·n_c·n_d
    n_a = 2L_C/L_p
    n_b = 1 (square)          else √(L_p/(4√A))
    n_c = 1 (square/rect.)    else [L_xL_y/A]^(0.7A/(L_xL_y))
    n_d = 1 (square/rect./L)  else D_m/√(L_x² + L_y²)             Eq. (84)–(88)

**Mesh and step voltages**

    K_h  = √(1 + h/h₀),  h₀ = 1 m                                Eq. (83)
    K_ii = 1 with rods on the perimeter, else 1/(2n)^(2/n)       Eq. (82)
    K_m  = (1/2π)·{ ln[ D²/(16hd) + (D+2h)²/(8Dd) − h/(4d) ]
                    + (K_ii/K_h)·ln[8/(π(2n−1))] }               Eq. (81)
    K_i  = 0.644 + 0.148n                                        Eq. (89)
    K_s  = (1/π)·[ 1/(2h) + 1/(D+h) + (1/D)(1 − 0.5^(n−2)) ]     Eq. (94)

    L_M  = L_C + L_R                                  (no perimeter rods)   Eq. (90)
    L_M  = L_C + [1.55 + 1.22(L_r/√(L_x²+L_y²))]·L_R  (perimeter rods)      Eq. (91)
    L_S  = 0.75L_C + 0.85L_R                                                Eq. (93)

    E_m  = ρ·K_m·K_i·I_G / L_M                                   Eq. (85)
    E_s  = ρ·K_s·K_i·I_G / L_S                                   Eq. (92)

**Acceptance** — the design passes if GPR ≤ E_touch (no further analysis needed, §16.4),
or if both E_m ≤ E_touch and E_s ≤ E_step. Auto-refine first reduces D in 0.5 m steps down
to 1.5 m, then adds perimeter rods in groups of four.

---

## 5. Numerical solver

The buried metal is discretised into cylindrical segments. With uniform leakage current
density on each segment and a single electrode potential V, the system solved is

    ⎡ P   −1 ⎤ ⎡ I ⎤   ⎡ 0  ⎤
    ⎣ 1ᵀ   0 ⎦ ⎣ V ⎦ = ⎣ I_G ⎦        R_g = V / I_G

P_ij is the average potential on segment i per ampere leaked from segment j:

    P_ij = (1/L_iL_j) ∫_i ∫_j G(r) ds ds′

**Green's function** (z is depth, positive downwards; surface at z = 0)

    uniform     G = ρ/(4π)·[ 1/√(r_h² + (z−z′)²) + 1/√(r_h² + (z+z′)²) ]

    two-layer   G = ρ₁/(4π) Σ_{n=−N}^{N} K^{|n|}
                    [ 1/√(r_h² + (z − z′ − 2nh)²) + 1/√(r_h² + (z + z′ − 2nh)²) ]

    N is truncated where |K|^N < 10⁻⁶.

**Self term** (exact average potential on a thin cylinder of length L, radius a)

    P_ii,direct = ρ/(2πL)·[ ln(2L/a) − 1 ]

plus the image contributions by Gauss quadrature. Near pairs — including a segment and its
own air-surface image — use a Galerkin double quadrature; far pairs use mid-point
collocation with adaptive source quadrature. This matters: pure collocation
under-estimates the average potential of a close source and biases R_g low by 5–15 %.

**Verification.** With one segment the solver reproduces Dwight's rod formula
R = ρ/(2πL)[ln(4L/a) − 1] analytically, because

    direct + image = ρ/(2πL)[ln(2L/a) − 1] + ρ·ln2/(2πL) = ρ/(2πL)[ln(4L/a) − 1]

**Post-processing.** Surface potential on a rectangular grid; touch voltage = GPR − V,
reported only inside the electrode footprint plus 1 m of arm reach; step voltage from the
surface-potential gradient over the chosen step distance; leakage current per segment and
its density; profiles along an arbitrary traverse.

---

## 6. Buildings and homes

**Electrode resistances** (Dwight, as tabulated in IEEE Std 142 Table 4.2)

    Vertical rod          R = ρ/(2πL)·[ln(8L/d) − 1]
    n rods in parallel    R_n = (R₁/n)(1 + λα),  α = ρ/(2πR₁s)
    Horizontal conductor  R = ρ/(4πℓ)·[ln(4ℓ/a) + ln(4ℓ/s) − 2 + s/(2ℓ)
                                        − s²/(16ℓ²) + s⁴/(512ℓ⁴)],  ℓ = L/2, s = 2h
    Ring (diameter D)     R = ρ/(2π²D)·[ln(8D/a) + ln(4D/s)]
    Buried plate          R = ρ/(8a) + ρ/(4πs)·[1 − 7a²/12s² + 33a⁴/40s⁴]
    Foundation            R ≈ 0.2ρ/∛V
    Mesh                  Sverak, as above

For a flat tape the equivalent radius is a = w/4.

**Automatic disconnection** (IEC 60364-4-41)

    TN            Z_s · I_a ≤ C_min · U₀                       §411.4.4
    TT            R_A · I_a ≤ U_L (50 V a.c.)                  §411.5.3
    RCD           R_A · IΔn ≤ U_L
    Touch voltage U_t = U₀·Z_PE/Z_s

Maximum disconnection times, Table 41.1 (final circuits ≤ 63 A):

| U₀ | TN | TT |
|---|---|---|
| 50 < U₀ ≤ 120 | 0.8 s | 0.3 s |
| 120 < U₀ ≤ 230 | 0.4 s | 0.2 s |
| 230 < U₀ ≤ 400 | 0.2 s | 0.07 s |
| > 400 | 0.1 s | 0.04 s |

Distribution circuits: 5 s (TN), 1 s (TT).

I_a comes from the tripping multiplier of the device: type B 5·I_n, type C 10·I_n,
type D 20·I_n, or the tabulated gG fuse currents for 0.4 s and 5 s.

---

## 7. Lightning earth termination — IEC 62305-3

| Class | Rolling sphere | Mesh | Down-conductor spacing | k_i |
|---|---|---|---|---|
| I | 20 m | 5 × 5 m | 10 m | 0.08 |
| II | 30 m | 10 × 10 m | 10 m | 0.06 |
| III | 45 m | 15 × 15 m | 15 m | 0.04 |
| IV | 60 m | 20 × 20 m | 20 m | 0.04 |

**Minimum electrode length l₁** (Figure 3), linearly interpolated in ρ:

| ρ (Ω·m) | ≤ 500 | 1000 | 2000 | 3000 |
|---|---|---|---|---|
| Class I | 5 | 20 | 50 | 80 |
| Class II | 5 | 10 | 30 | 45 |
| Class III / IV | 5 | 5 | 5 | 5 |

Vertical electrodes need 0.5·l₁.

**Type A** — at least two electrodes, each of length ≥ l₁ (horizontal) or 0.5·l₁ (vertical).

**Type B** — ring or foundation electrode with mean radius r_e = √(A/π) ≥ l₁. If r_e < l₁,
add at each down-conductor a horizontal electrode of l_r = l₁ − r_e, or a vertical one of
l_v = (l₁ − r_e)/2.

**Separation distance** — s = k_i·k_c·l/k_m, with k_c = 1 (one down-conductor), 0.66 (two),
0.55 (three), 0.44 (four or more) and k_m = 1 (air) or 0.5 (concrete, brick).

An earthing resistance below 10 Ω is recommended (informative).

---

## 8. Air termination and protection zone — IEC 62305-3

Class parameters (Table 2 and Table 4):

| Class | Rolling sphere `R` | Mesh | Down-conductor spacing | `k_i` |
|-------|--------------------|------|------------------------|-------|
| I     | 20 m | 5 × 5 m   | 10 m | 0.08 |
| II    | 30 m | 10 × 10 m | 10 m | 0.06 |
| III   | 45 m | 15 × 15 m | 15 m | 0.04 |
| IV    | 60 m | 20 × 20 m | 20 m | 0.04 |

Rolling sphere, Annex A.2. Half-chord of a ground-resting sphere at height `z`:

```
a(z) = sqrt(2*R*z - z^2)                       (0 <= z <= 2R)
```

Radius protected by one vertical termination of height `h`, measured on a plane at `h_x`:

```
r_p = a(h)   - a(h_x)        for h <  R
r_p = R      - a(h_x)        for h >= R        (the mast body holds the sphere off)
```

Penetration of the sphere between two terminations of equal height, spacing `d`:

```
p     = R - sqrt(R^2 - (d/2)^2)
d_max = 2 * sqrt(R^2 - (R - h)^2) = 2*a(h)     (sphere just reaches the plane)
```

Protected height at mid-span = `h - p`; the arrangement complies when that is at or above
the plane being protected.

General geometry: solid surfaces are sampled into capture points and a ball of radius `R` is
marched over them; each resting position touching two supports contributes an arc of radius
`R` to the boundary of the protected volume. The march reproduces the closed forms above and
extends to arrangements they cannot express.

Protective angle, Annex A.1: `r = h * tan(alpha)`, with `alpha` from Figure 1 as a function
of `h` and the class. Valid only for simple shapes and only while `h <= R`. Figure 1 is
published as a graph; the values in `earthsys/airterm.py` are a digitisation of it and the
rolling sphere governs.

Mesh method, Annex A.3: conductor spacing not greater than the class mesh size in both
directions, following the roof edges, bonded to down-conductors at the Table 4 spacing.

---

## 9. System neutral grounding — IEEE Std 142

**Charging current** — 3I_C0 = 3·2πf·C₀·V_LN plus the machine allowances of Table 1.

**High resistance** — R_N = V_LN/I_R with I_R ≥ 3I_C0; the resistor is rated for
continuous duty when the system is designed to run with a standing earth fault (IEEE Std 32).

**Low resistance** — R_N = V_LN/I_f for the target fault current, with the short-time
energy I_f²·R_N·t.

**Reactance** — X_N = V_LN/I_f, checked against X₀/X₁ ≤ 10.

**Effectively grounded** (IEEE C62.92) — X₀/X₁ ≤ 3 and R₀/X₁ ≤ 1. When satisfied, 80 %
rated arresters are normally acceptable; otherwise use full-rated arresters and check the
temporary-overvoltage duty.
