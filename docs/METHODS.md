# Earthing System — methods and equations

Every equation the software applies, with its source clause. Symbols follow the
originating standard. IEEE 80 equation, figure and table numbers are those of
IEEE Std 80-2013 as republished with Corrigendum 1-2015 (since version 1.3.2; earlier
versions quoted some IEEE 80-2000 numbers).

---

## 1. Soil

**Field reduction** (IEEE Std 81-2012 §8)

    Wenner (b ≪ a)          ρₐ = 2πaR
    Wenner (exact)          ρₐ = 4πaR / [1 + 2a/√(a²+4b²) − 2a/√(4a²+4b²)]
    Schlumberger            ρₐ = πR(s² − (d/2)²)/d
    Driven rod (3-point)    ρ  = 2πLR / [ln(8L/d) − 1]

**Two-layer forward model** — image series with K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁)

    Wenner          ρₐ(a) = ρ₁ [ 1 + 4 Σₙ Kⁿ ( 1/√(1+(2nh/a)²) − 1/√(4+(2nh/a)²) ) ]
    Schlumberger    ρₐ(s) = ρ₁ [ 1 + 2 Σₙ Kⁿ / (1 + (2nh/s)²)^{3/2} ]   (MN → 0)
                    ρₐ(s,d) = ρ₁ [ 1 + (s² − d²/4)/d · 2 Σₙ Kⁿ ( 1/R(s − d/2) − 1/R(s + d/2) ) ],
                    R(x) = √(x² + (2nh)²), used with the MN of each reading (1.3.2)

**Inversion** — (ρ₁, ρ₂, h) are optimised in log space with a dependency-free
Nelder–Mead simplex, minimising Σ((ρ_model − ρ_meas)/ρ_meas)². Twenty-seven starting
points are tried to avoid local minima. The reported RMS error is that residual in percent;
a fit is graded good (RMS ≤ 3 %), acceptable (≤ 5 %) or poor, and a non-monotonic curve
(H- or K-type) is flagged as three-layer.

**Three and four layers** (1.4.0, 1.5.0; `earthsys/layered.py`) — kernel recurrence from the
deepest interface, K_{i,i+1} = (ρ_{i+1} − ρ_i)/(ρ_{i+1} + ρ_i):

    R_{N−1} = K_{N−1,N},   R_i(λ) = (K_{i,i+1} + R_{i+1}e^{−2λh_{i+1}})/(1 + K_{i,i+1}R_{i+1}e^{−2λh_{i+1}})
    θ(λ) = R₁e^{−2λh₁}/(1 − R₁e^{−2λh₁}),   ψ(r) = ∫₀^∞ θ(λ)J₀(λr)dλ
    Wenner          ρₐ = ρ₁[1 + 4a(ψ(a) − ψ(2a))]
    Schlumberger    ρₐ = ρ₁[1 + 2(s² − d²/4)/d · (ψ(s − d/2) − ψ(s + d/2))]

The top interface's images are summed exactly and the rest of the kernel integrated by
Gauss–Legendre quadrature (two layers to 10⁻⁶, the three-layer image series to 10⁻⁸).

**Inversion with three or four layers** — Levenberg–Marquardt in log parameters from 64
shape-based starts plus starts built from the fit with one layer fewer; thinnest layers
h₁ ≥ 0.05 a_min, h₂, h₃ ≥ 0.1 a_min. A further layer is kept only if

    F = [(Φ_n − Φ_{n+1})/2] / [Φ_{n+1}/(N − k)],   p = ((N − k)/(N − k + 2F))^{(N−k)/2} < 0.05
    (k = 5 for the third layer, 7 for the fourth) and the RMS falls by at least a fifth.

*Automatic* tries three layers when there are six or more readings and the two-layer fit
misses by more than 3 % RMS or the curve is non-monotonic; it tries four when three layers are
kept, there are nine or more readings and the three-layer RMS still exceeds 3 %. **Equivalence**: from the 5 × 5 (or 7 × 7)
covariance, the best-determined combination of a middle layer is h ρ^β with
β = −C_ρh/C_ρρ, σ = √(C_hh(1 − r²)); β ≈ −1 names the conductance S = h/ρ, β ≈ +1 the
transverse resistance T = ρh. A parameter whose own spread exceeds ×20 is reported as not
resolved.

**Forced models and what the readings reach** (1.6.1) — *Three layers* or *Four layers*
shows the requested model even when the test above rejects it, but the result then carries a
warning naming the supported model and its values. A fourth layer is tested against three;
when three were not supported, against two directly (k = 3 → 7, four extra parameters, upper
tail of F for an even numerator in closed form). Each layer is flagged *not resolved* when its
ρ or the depth of its top has a spread above ×20 or reached the search bound, and *below the
reach of the traverse* when its top lies deeper than twice the median depth of investigation
of the longest spread (Edwards, 1977):

    z_median = 0.52 a_max (Wenner),   0.38 s_max = 0.19 AB (Schlumberger)

The section draws flagged layers veiled and marks z_median; *Pull inputs* and *Use the fitted
soil model* ask for confirmation before using a warned model, and the report prints the
warning. A spurious conductive layer lowers the computed resistance and GPR, which is unsafe.

**Equivalent uniform resistivity** — for a grid, the disc rule
ρ_eq = ρ₁(F/4r + 1/L_T)/(1/4r + 1/L_T), r = √(A/π), with F the disc factor of the layered
earth, since 1.4.0 written for any number of layers as one integral of the surface kernel
B(μ):

    F = 1 + (4/πr) ∫₀^∞ B(μ)(1 − cos 2μr)/(2μ²) dμ        (equal to the two-layer series to 10⁻¹³)

A three- or four-layer model can also be collapsed to an **equivalent two-layer** model for
one grid: the top layer is kept and the layers below are replaced by the half-space that gives
the same F at r = √(A/π). Without the grid area: depth-weighted average over the electrode
penetration when the electrodes cross the interface, otherwise ρ₁.

---

## 2. Fault current

**IEC 60909-0:2016**

    Three-phase             Iₖ″   = c·Uₙ / (√3·Z₁)                    Eq. (29)
    Peak                    iₚ    = κ·√2·Iₖ″,  κ = 1.02 + 0.98·e^(−3R/X)
    Line-to-earth           Iₖ₁″  = √3·c·Uₙ / |Z₁ + Z₂ + Z₀ + 3Z_f|    Eq. (52)
    Double line-to-earth    I″kE2E = √3·c·Uₙ·|Z₂| / |Z₁Z₂ + Z₁Z₀ + Z₂Z₀|   (earth current 3I₀, Eq. (47))
                            I″k2E  = c·Uₙ·|Z₀ − aZ₂| / |Z₁Z₂ + Z₁Z₀ + Z₂Z₀|  (phase current, Eq. (46))
    Thermal equivalent      I_th  = Iₖ″·√(m + n)                       Eq. (66)
    Network impedance       Z_Q   = c·Uₙ² / Sₖ″
    Transformer             Z_T   = u_k·Uₙ² / (100·S_r)

**IEEE Std 80-2013 clause 15**

    Decrement factor        D_f = √[ 1 + (T_a/t_f)(1 − e^(−2t_f/T_a)) ],  T_a = X/(2πfR)   Eq. (84)
                            (limits: D_f = 1 for X/R = 0, √3 for X/R → ∞)
    Split factor            S_f = |Z_r| / |Z_r + R_g|                                      Annex C
    Grid current            I_g = S_f·C_p·3I₀ ;   I_G = D_f·I_g                            Eq. (78), (69)

---

## 3. Conductor sizing

**IEEE Std 80-2013 Eq. (37)**

    A[mm²] = I[kA] / √( (TCAP·10⁻⁴)/(t_c·α_r·ρ_r) · ln[(K₀ + T_m)/(K₀ + T_a)] )

with the full Table 1 material set (15 materials). T_m is limited by the joint type when
one is selected: exothermic weld 1083 °C, brazed 450 °C, bolted/pressure 250 °C — but never
above the material's own T_m (T_m = min(joint, material), 1.3.4).

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

    Sverak   R_g = ρ[ 1/L_T + 1/√(20A)·(1 + 1/(1 + h√(20/A))) ]  Eq. (57)

    Schwarz  R₁ = ρ/(πL_C)·[ ln(2L_C/h′) + k₁L_C/√A − k₂ ]
             R₂ = ρ/(2πn_R L_R)·[ ln(8L_R/d_R) − 1 + 2k₁L_R(√n_R − 1)²/√A ]
             R_m = ρ/(πL_C)·[ ln(2L_C/L_R) + k₁L_C/√A − k₂ + 1 ]
             R_g = (R₁R₂ − R_m²)/(R₁ + R₂ − 2R_m)                Eq. (58)–(61)

*Automatic* uses Sverak for a grid without rods and, with rods, Sverak's grid-only value
multiplied by the Schwarz rod factor R_g/R₁ — so adding rods can never appear to raise
R_g, as it did in version 1.1 (2.776 → 2.867 Ω for Annex B with 20 rods).

with h′ = √(d·h), L_x/L_y the length-to-width ratio (≥ 1), and k₁, k₂ from the Figure 24 fits,
linearly interpolated in h between the three curves (the slope of k₂ for h = 0 was
printed with the wrong sign before version 1.3.2):

| depth | k₁ | k₂ |
|---|---|---|
| 0 | −0.04(L_x/L_y) + 1.41 | +0.15(L_x/L_y) + 5.50 |
| √A/10 | −0.05(L_x/L_y) + 1.20 | +0.10(L_x/L_y) + 4.68 |
| √A/6 | −0.05(L_x/L_y) + 1.13 | −0.05(L_x/L_y) + 4.40 ¹ |

¹ As printed in the standard. The plotted curve C of Figure 24(b) rises from about 4.45 to 4.6 between
x = 1 and 4, i.e. +0.05x + 4.40; the printed fit is kept because it is the lower-k₂, conservative reading.
Curves B and C are drawn only up to x = 4.

**Geometry factor**

    n = n_a·n_b·n_c·n_d
    n_a = 2L_C/L_p
    n_b = 1 (square)          else √(L_p/(4√A))
    n_c = 1 (square/rect.)    else [L_xL_y/A]^(0.7A/(L_xL_y))
    n_d = 1 (square/rect./L)  else D_m/√(L_x² + L_y²)             Eq. (89)–(93)

**Mesh and step voltages**

    K_h  = √(1 + h/h₀),  h₀ = 1 m                                Eq. (88)
    K_ii = 1 with rods on the perimeter, else 1/(2n)^(2/n)       Eq. (87)
    K_m  = (1/2π)·{ ln[ D²/(16hd) + (D+2h)²/(8Dd) − h/(4d) ]
                    + (K_ii/K_h)·ln[8/(π(2n−1))] }               Eq. (86)
    K_i  = 0.644 + 0.148n                                        Eq. (94)
    K_s  = (1/π)·[ 1/(2h) + 1/(D+h) + (1/D)(1 − 0.5^(n−2)) ]     Eq. (99)

    L_M  = L_C + L_R                                  (no perimeter rods)   Eq. (95)
    L_M  = L_C + [1.55 + 1.22(L_r/√(L_x²+L_y²))]·L_R  (perimeter rods)      Eq. (96)
    L_S  = 0.75L_C + 0.85L_R                                                Eq. (98)

    E_m  = ρ·K_m·K_i·I_G / L_M                                   Eq. (85)
    E_s  = ρ·K_s·K_i·I_G / L_S                                   Eq. (97)

**Acceptance** — the design passes if GPR ≤ E_touch (no further analysis needed, §16.4),
or if both E_m ≤ E_touch and E_s ≤ E_step. A warning (not a failure) is given when the burial
depth is outside 0.25 m ≤ h ≤ 2.5 m, the range of Eq. (99) (1.3.4). The report prints the
resistance formula actually used (Sverak, Schwarz, or Sverak × Schwarz rod factor). Auto-refine first reduces D in 0.5 m steps down
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

    Images are summed explicitly up to n = 60; the deeper ones, up to |K|ⁿ < 10⁻⁶ (and the
    remainder in closed form), are added as a tabulated function of r_h alone, their depth
    (≥ 2·61·h) being large against z and z′ (1.3.4; before, the series simply stopped at 60,
    −15 % on R_g for ρ₂/ρ₁ = 200).

**Two regions with a vertical boundary** (1.8.7) — uniform ρ₁ on one side of a vertical plane,
ρ′ on the other, K = (ρ′ − ρ₁)/(ρ′ + ρ₁), K_s = K for a source on the ρ₁ side and −K on the
ρ′ side; r′ is the distance to the source mirrored in the plane, the suffix a the air image:

    same side       G = ρ_s/(4π)·[ 1/r + 1/r_a + K_s (1/r′ + 1/r′_a) ]
    across          G = ρ_s(1 + K_s)/(4π)·[ 1/r + 1/r_a ]

Exact (the two mirrors are perpendicular, so the images close after four terms); continuous
in potential and normal current density across the plane, and reciprocal. Conductors are
split at the plane. A segment parallel to the plane at distance d takes its mirror term in
closed form, K_s ρ_s/(4π)·(2/L²)[L asinh(L/D) − √(L² + D²) + D], D = 2d; a segment in the
plane (2d < a) takes K_s times its direct self term, i.e. ρ₁(1 + K) = 2ρ₁ρ′/(ρ₁ + ρ′).
Exact checks: an electrode in the plane, and any electrode symmetric about it, behave as in
uniform soil of that harmonic mean (10⁻¹² and 3 × 10⁻⁶ in the tests).

**Self term** (exact average potential on a thin cylinder of length L, radius a)

    P_ii,direct = ρ/(2πL)·[ ln(2L/a) − 1 ]

plus the image contributions by Gauss quadrature. Near pairs — including a segment and its
own air-surface image — use a Galerkin double quadrature; far pairs use mid-point
collocation with adaptive source quadrature. This matters: pure collocation
under-estimates the average potential of a close source and biases R_g low by 5–15 %.

**Verification.** With one segment the solver reproduces Dwight's rod formula
R = ρ/(2πL)[ln(4L/a) − 1] analytically, because

    direct + image = ρ/(2πL)[ln(2L/a) − 1] + ρ·ln2/(2πL) = ρ/(2πL)[ln(4L/a) − 1]

Input validation: ρ₁ > 0, and every further layer's ρ > 0 with the thickness of the layer
above it > 0; a third layer needs the second, a fourth the third. "Build from the IEEE 80 grid" places the rods as the grid page does — on the perimeter,
or spread over the area (1.3.4).

**Three and four layers** (1.4.0, 1.5.0) — images by wave tracing: a wave in layer L meeting
the plane to layer M is reflected with R = (ρ_M − ρ_L)/(ρ_M + ρ_L) (source mirrored in the
plane) and transmitted with 1 + R (source unmoved); the surface reflects with +1:

    G_ij = ρ_i/(4π) Σ_k a_k / √(r_h² + (z − s_k z′ − D_k)²)

Images within 3Z of the electrode region (Z the deepest conductor) are kept one by one, those
within 8Z merged in 5 % bins, all others taken from the spectral solution tabulated in r_h
with Taylor coefficients in z − s z′ to the seventh order. Every conductor is split at every
interface; each segment uses its own layer's ρ in the self term.

**Separate networks** (1.5.0) — fences and other floating metal. With E the segment–network
incidence matrix and J the injected currents (I_G for the grid, 0 for a floating network):

    ⎡ P   −E ⎤ ⎡ I ⎤   ⎡ 0 ⎤
    ⎣ Eᵀ   0 ⎦ ⎣ V ⎦ = ⎣ J ⎦        V = Z J,  Z the mutual-resistance matrix

Fence element: posts at the given spacing and at every vertex, an optional buried wire at an
offset, bonded (part of network 1) or isolated. Fence touch voltage = V_fence − V_surface
within 1 m of the fence line on either side; step across the fence line; grid-to-fence
transfer voltage. Scan points within 0.25 m of metal that reaches the surface are excluded
from the step scan.

**Solution of large models** (1.8.7; `earthsys/hmatrix.py`)

    Symmetry      mirrors in x, y and the diagonals, rotations by 90° and 180° about the
                  centre of the layout that map every segment (radius, soil zone, network,
                  shell) and the soil onto themselves; orbits O_a with representatives r_a:
                  P_red[a,b] = (|O_b|/|O_a|)·Σ_{i∈O_a} P[i, r_b],
                  ⎡ P_red    −E_red ⎤ ⎡ I_red ⎤   ⎡ 0 ⎤
                  ⎣ (|O|E_red)ᵀ   0 ⎦ ⎣   V   ⎦ = ⎣ J ⎦,   I = I_red[orbit]   (exact)
    Dense         n_eff ≤ 4000 unknowns (after the reduction): LU of the augmented system
    H-matrix      above that: binary cluster tree (≤ 64 segments per leaf); a block is
                  compressed when its horizontal gap g ≥ 8 L_max and min(diam) ≤ 1.5 g, by
                  adaptive cross approximation with partial pivoting to 10⁻⁸ of the block's
                  Frobenius norm (Bebendorf 2000); other blocks dense, with the near-field
                  quadrature written in; X = P⁻¹E by restarted GMRES(60) (Saad and Schultz
                  1986) to a relative residual of 10⁻⁹, block-Jacobi preconditioner (diagonal
                  blocks of ≤ 256 segments); Z = (EᵀX)⁻¹, I-shapes X·Z
    Two layers    for field and source points at one depth the image series is tabulated
                  in u = asinh(r_h/Δ_min) with its derivative (step 0.01, cubic Hermite,
                  relative error < 10⁻¹⁰); the term at Δ = 0 is added exactly
    Reuse         solutions kept by a hash of the segments, soil and solver (12 most recent);
                  for uniform soil without concrete Z/ρ is kept, so one solution serves any ρ
                  and any I_G; study cases kept by everything they depend on (48 most recent)
    Maps          point tree × segment tree; near and small blocks summed directly, large far
                  blocks through ACA (10⁻⁷) applied to the currents
    Limit         20 000 segments (was 4000)

Checks (`tests/test_v187_solver_vertical.py`): symmetric against full dense 10⁻¹² on the Annex H
grids; H-matrix against dense 10⁻⁸ in R_g and 10⁻⁷ in touch and step on Annex B with rods and
Annex H Grids 2 and 3; 13 520 segments (Annex B at 0.125 m) against the symmetric dense
solution 4 × 10⁻¹¹ in R_g and 5 × 10⁻⁹ in touch.

**Concrete-encased conductors** (1.6.0) — *Pier / pile* and *Strip footing* elements. The cage
of n bars of radius a on a circle of radius b becomes one bar of radius
a_eq = (n a b^{n−1})^{1/n} (b = r_c − cover − a); the section a cylinder of radius r_c
(D/2 for a pier, (w + h)/4 + 0.09 min(w, h) for a w × h section). Each segment's self
coefficient gains the shell ρ_c ln(r_c/a_eq)/(2πL); the soil sees radius r_c; near pairs use
the kernel with r_h floored at r_c; segments are at least 1.5 r_c long (Fagan and Lee 1970).

**Transferred potential** (1.5.0; `earthsys/transfer.py`) — a straight conductor leaving the
station as a lossy line in soil at the solver's potential V_s(x):

    dV/dx = −z I,   dI/dx = −g (V − V_s(x))
    z = z_int + π² f 10⁻⁷ + j(ωμ₀/2π) ln(D_e/a),   D_e = 658.5 √(ρ/f)        (Carson)
    g_bare = π / (ρ[ln(2ℓ/√(2ad)) − 1]),   1/g_coated = 1/g_bare + r_c/(2πa),   g_screen = 0
    GPR = R_g I_G / (1 + R_g (a − c))        (reciprocity correction)

Steel: z_int is the surface impedance (1 + j)ρ_m/(2πaδ) when the wall exceeds 2δ (μ_r = 300).
Solved as a ladder (Thomas algorithm) on a mesh refined near the station; ends bonded or
insulated at the station, open, locally earthed or remotely earthed at the far end.

**Transferred potential solved with the station** (1.8.8) — bare and coated routes: segments
from max(min(mean grid segment, 3 m), 12a) at the station growing by 1.15 to min(50 m, L/20);
coating r_c/(2πa) added to the segment's own coefficient; all leakage in one static P:

    I = P⁻¹ [E, B] [V_s; U]          B: ½ to each end node of a route segment
    Eᵀ I = J − δ I_bond,   I_bond = J₀ + leak₀,   J_{j−1} = J_j + leak_j,   J_{m−1} = leak_m + I_far
    J_j = (U_j − U_{j+1} + e_j Δs_j)/(z Δs_j),   bond: U₀ = V₀ (− R_bond I_bond)
    touch(s) = |U(s) − V_surface(1 m beside the route, lower side)|

Far end earthed locally: to the soil 2 m beside the route end. z from (Carson + internal) as
before; the EMF of a faulted line is a second right-hand side. Checked against hf.py at 50 Hz
(2 km bare wire on Annex H Grid 3: GPR +1.2 %, current −1.4 %, touch ≤ 3 %).

**Automatic refinement** (1.8.8) — halve the segments within r = max(3 m, 2s + 1 m) of the
worst touch point and both feet of the worst step (and their symmetry images), never below 10
radii (1.5 shell radii); re-solve and re-search until |Δtouch|, |Δstep| < tol; geometric
extrapolation of the last three levels when they contract.

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
    Foundation            R ≈ 0.2ρ/∛V                       (compact foundations)
    Mesh                  Sverak, as above

**Earth pits** (1.3.6; `earthsys/earthpit.py`) — axisymmetric finite-volume solution of
∇·(σ∇V) = 0 for a rod (or a plate as a disc) in a column of backfill, checked against

    BS 7430 9.5.7   R = ρ/(2πL)[ln(8L/D) − 1] + ρ_c/(2πL) ln(D/d)     (full-length column)
    group           R_n = (R₁ + λρ/(2πs))/n                            (BS 7430 9.5.4)
    current density J_max = 10³ √(57.7/(ρ t)) A/m² (short time), 40 A/m² (continuous)   (BS 7430 9.8)

**Piles, piers, strip footings** (1.6.0, numerical page) — rod in a concrete shell
(Fagan and Lee 1970):

    R = ρ_c/(2πL) ln(r_c/a) + ρ/(2πL)(ln(4L/r_c) − 1) = R_bare + (ρ_c − ρ) ln(r_c/a)/(2πL)

so encasement lowers R exactly when ρ_c < ρ. Default ρ_c = 50 Ω·m (buried concrete 30–100 Ω·m).

λ: rods in a line, BS 7430:2011 9.5.4, λ = 2(1/2 + … + 1/n), which is exactly the
neighbour sum below; hollow square, BS 7430:2011 Table 2 (4–76 rods); otherwise
λ = (1/n) Σᵢ Σ_{j≠i} s/d_ij for the actual layout. (Up to 1.3.2 the line values were
rounded ones from an older edition, e.g. 2.15 for four rods instead of 2.167.)

**Combining bonded electrodes** — mutual resistance R_ij = min(ρ/(2π max(D, rᵢ+rⱼ)), Rᵢ, Rⱼ)
with rᵢ = ρ/(2πRᵢ); R_A = 1/(1ᵀ[R]⁻¹1). D is the stated separation; without one the
equivalent hemispheres are taken as touching.

For a flat tape the equivalent radius is a = w/4.

**Automatic disconnection** (IEC 60364-4-41)

    TN            Z_s · I_a ≤ C_min · U₀                       §411.4.4
    TT, RCD       R_A · IΔn ≤ U_L (50 V a.c.)                  §411.5.3
    TT, MCB/fuse  Z_s · I_a ≤ C_min · U₀,  Z_s = Z_e + Z_line + R_A   §411.5.4
                  (Z_e includes the source electrode R_B; before 1.3.4 the RCD rule
                  R_A · I_a ≤ 50 V was applied to overcurrent devices too)
    Touch voltage U_t = U₀·Z_PE/Z_s

Maximum disconnection times, Table 41.1 (final circuits ≤ 63 A):

| U₀ | TN | TT |
|---|---|---|
| 50 < U₀ ≤ 120 | 0.8 s | 0.3 s |
| 120 < U₀ ≤ 230 | 0.4 s | 0.2 s |
| 230 < U₀ ≤ 400 | 0.2 s | 0.07 s |
| > 400 | 0.1 s | 0.04 s |

Distribution circuits: 5 s (TN), 1 s (TT). For U₀ ≤ 50 V Table 41.1 imposes no
disconnection time (it starts at 50 V < U₀); the assessment reports "not required" (1.3.4).

Electrode inputs are validated: the strip and ring formulas contain ln(·/2h) and are
rejected at h = 0; the plate (shallow ENA form) and the mesh accept h = 0.

I_a comes from the tripping multiplier of the device: type B 5·I_n, type C 10·I_n,
type D 20·I_n, or, for a fuse (1.8.6):

| Fuse | I_a | Source |
|---|---|---|
| gG, BS 88-2 | 0.95·230/Z_s,max of the tables (0.4 s, 2–63 A; 5 s, 2–200 A); other ratings as gG, IEC 60269 | BS 7671:2018+A2:2022 Tables 41.2, 41.4 |
| gG / gM, any make | upper limit of the gates: (I_f, t_conv), (I_max 5 s), (I_max 0.1 s), (√(I²t_max/0.01), 0.01 s), log–log, constant I²t below 0.01 s; gM at its characteristic current | IEC 60269-1 Tables 2, 3, 7; IEC 60269-2 Table 102; IEC 60269-3 Tables 103, 203, 406, 602 |
| aM | (6.3·I_n, 60 s), (12.5·I_n, 0.5 s), (19·I_n, 0.1 s) | IEC 60269-1 Table 4 |
| Manufacturer's curve | current–time points, log–log, current × (1 + tolerance) | data sheet |

The operating time at the prospective fault current C_min·U₀/Z_s is read from the same
curve.

---

## 7. Lightning earth termination — IEC 62305-3

| Class | Rolling sphere | Mesh | Down-conductor spacing | k_i |
|---|---|---|---|---|
| I | 20 m | 5 × 5 m | 10 m | 0.08 |
| II | 30 m | 10 × 10 m | 10 m | 0.06 |
| III | 45 m | 15 × 15 m | 15 m | 0.04 |
| IV | 60 m | 20 × 20 m | 20 m | 0.04 |

**Minimum electrode length l₁** (Figure 3, read from the vector drawing of the 2010 edition):

    class I      l₁ = max(5, 0.03ρ − 10)  m      (5 m to 500 Ω·m, 80 m at 3000 Ω·m)
    class II     l₁ = max(5, 0.02ρ − 11)  m      (5 m to 800 Ω·m, 49 m at 3000 Ω·m)
    class III/IV l₁ = 5 m

Beyond 3000 Ω·m the last slope is kept; the standard recommends a type B arrangement there.

Vertical electrodes need 0.5·l₁.

**Type A** — at least two electrodes, each of length ≥ l₁ (horizontal) or 0.5·l₁ (vertical).

**Type B** — ring or foundation electrode with mean radius r_e = √(A/π) ≥ l₁. If r_e < l₁,
add at each down-conductor a horizontal electrode of l_r = l₁ − r_e, or a vertical one of
l_v = (l₁ − r_e)/2.

**Separation distance** — s = k_i·k_c·l/k_m, with k_c from Table 12: 1 (one down-conductor,
isolated LPS), 0.66 (two), 0.44 (three or more); k_m = 1 (air) or 0.5 (concrete, brick, wood).

An earthing resistance below 10 Ω is recommended (informative).

### 7.1 Behaviour under the impulse

**Effective length of a horizontal electrode** — how far the front travels along a buried
conductor before it peaks:

    L_eff = k (ρ T)^0.5        ρ in Ω·m, T in µs, L_eff in m
    k = 1.40  fed at one end        k = 1.55  fed at its centre

Electrode beyond L_eff carries almost nothing during the front. Front times from
IEC 62305-1 Table 3: 10 µs first positive, 1 µs first negative, 0.25 µs subsequent.

**Effective radius of a meshed system** — three published expressions, reported side by
side because they disagree; `s` is the mesh conductor spacing in metres:

| Expression | Centre-fed | Edge or corner-fed |
|---|---|---|
| Gupta & Thapar, r = K(ρT)^0.5 | K = 1.45 − 0.05 s | K = 0.60 − 0.025 s |
| Conductor reach, r = k(ρT)^0.5 | k = 1.55 | k = 1.40 |
| Grcev, r = K·exp[0.84 (ρT)^0.22] | K = 1 | K = 0.5 |

The Gupta & Thapar fit was made over roughly 3–15 m spacing; outside that band K is
extrapolated and the program flags it. Every r is capped at the electrode's own equivalent
radius r_geom = √(A/π), and the participating fraction is π r²/A.

**Impulse coefficient** — first order from the disc electrode R = ρ/(4r):

    A = Z_impulse / R_measured ≈ r_geom / r_eff        (A ≥ 1)
    EPR_impulse ≈ A · R_measured · I_peak

An estimate, not a measurement, and it ignores soil ionisation (which reduces the impulse
impedance). A resistance measured at d.c. or 50 Hz understates the potential rise of an
extended earthing system under a stroke; bonding and SPD coordination are sized on the
impulse value.

### 7.2 Computed lightning response (numerical page)

`earthsys/hf.py` (1.5.0; layered soil, ionisation and concrete in 1.6.0). Thin-wire segments
with longitudinal current I_L and leakage I_T; at each frequency

    (V_a + V_b)/2 = Σ Z^T_kj I_T,j,     V_a − V_b = Σ Z^L_kj I_L,j + Z_i,k I_L,k,     KCL at nodes
    Z^T_kj = 1/(4πκ ℓ_kℓ_j) ∫∫[e^{−γR}/R + K e^{−γR′}/R′],   Z^L_kj = jωμ₀/4π ∫∫[t_k·t_j e^{−γR}/R + K t_k·t′_j e^{−γR′}/R′]
    κ = σ + jωε,  γ = √(jωμ₀κ),  K = (κ − jωε₀)/(κ + jωε₀);  t′ keeps the mirrored vertical part

plus the Sommerfeld corrections S_A (horizontal currents, TE) and S_φ (charges) of the
half-space (Michalski and Zheng, formulation C). Soil: constant ρ₀, ε_r or Alipio–Visacro
(CIGRE TB 781, mean / relatively conservative / conservative).

**Layered soil** — the exact transmission-line Green's functions of the stack (air, layers
1 … N): u_i = √(λ² + γ_i²), Z^e_i = u_i/κ_i, Z^h_i = jωμ₀/u_i,

    G = ∫₀^∞ g̃ J₀(λρ) λ dλ,   g̃_φ = 2κ′(V^e − V^h)/λ²,   g̃_A,h = 2V^h/(jωμ₀),   g̃_A,v = 2I^e/κ′

The direct term and the images (complex reflection coefficients (κ_L − κ_M)/(κ_L + κ_M),
surface K) within D = max(1 m, 3 × segment length) of the electrode are integrated exactly
(Galerkin); the remainder of g̃ is tabulated per frequency in (ρ, z, z′) and interpolated.

**Concrete** — the shell adds ln(r_c/a_eq)/(2πκ_c ℓ_k), κ_c = 1/ρ_c + jωε_c, to Z^T_kk.

**Time response and ionisation**

    v(t) = R i(t) + F⁻¹{[Z(jω) − R] I(jω)},    Z_p = max v / max i,    IC = Z_p / R
    v_i(t) = R(t) i(t) + x(t),   R(t) = R/√(1 + i(t)/I_g),   I_g = E₀ρ/(2πR²)        (Grcev 2009)
    A_i = 1/√(1 + I_m/I_g) + A − 1                                                   (Grcev 2009 Eq. 25)

E₀ default 400 kV/m (CIGRE); ρ in I_g is the length-weighted resistivity of the layers holding
the electrode; a note is given beyond 30 m. Currents: CIGRE TB 781 Fig. 4.1 first and
subsequent strokes, or the Heidler functions of Rachidi et al. used by Grcev.

**Checks** — Grcev 2009 Sommerfeld curves within about 5 % from 100 Ω·m up; TB 781 rod: HEM
within 4 %, measurement within 9 %; Arnautovski-Toseva et al. 2007 two-layer wires within
3.5 % to 1 MHz (10 m) and 4.5 % (50 m); Grcev Table I with ionisation 8.3 Ω (8.3) and 13.9 Ω
(13.4); Fagan and Lee Table VII within 3 %; low-frequency limit equal to the solver of §5
within 0.2 %.

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
of `h` and the class. Valid only for simple shapes and only while `h <= R`; constant below
h = 2 m. Figure 1 is published as a graph; since 1.3.2 the values in `earthsys/airterm.py` are
read from its vector drawing (±0.3°). The rolling sphere governs.

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

## 10. Cross-checks against other standards — `earthsys/standards.py` (1.3)

These are reported for information only. No verdict depends on them.

**Permissible touch voltage** (BS EN 50522:2022 Table B.3, the same as IEC 61936-1).
`U_Tp(t_F)` is interpolated linearly in log–log coordinates between 0.05 s (716 V) and 10 s
(85 V), and clamped outside that range. Module 4 reports it beside the IEEE 80 bare-soil
limit `1000·k/√t_s`.

**Coincidence probability** (ENA EG-0, AS 2067).
`P_coinc = f_n·p_n·(f_d + t_d)·T / 31 536 000`. The risk bands are: below 10⁻⁶ negligible,
above 10⁻⁴ intolerable, and ALARP between.

**Frequency-dependent soil** (CIGRE TB 781, Alipio–Visacro median parameters).
`σ = σ0 + σ0·h(σ0)·(f/1 MHz)^0.54` with `h = 1.26·σ0^−0.73` (σ in mS/m) and
`ε_r∞ = 12` (TB 781 Table 3.2; also the "relatively conservative" set 0.95/0.58/8 and the
"conservative" set 0.70/0.62/4 via `level=`). In resistivity this is TB 781 Eq. 5.3–5.4,
`ρ = ρ0/(1 + 4.7e-6·ρ0^0.73·f^0.54)`, `ε_r = 9.5e4·ρ0^−0.27·f^−0.46 + 12` (agreement < 0.5 %).
Module 7 evaluates it at `f = 1/(4T)` and (since 1.3.3) reports the impulse-impedance factors of
TB 781 Table 4.1 for electrodes shorter than L_eff (first 0.98…0.72, subsequent 0.91…0.50 for
ρ0 = 100…4000 Ω·m, log-interpolated) and the relevance class of Table 5.1 (ignore < 300 Ω·m,
recommended 300–700, mandatory > 700). The impulse impedance falls much less than ρ(1/4T), and
TB 781 finds L_eff unchanged (subsequent) or longer (first stroke), so ρ(1/4T) is not substituted
into any design formula. Also available: `tb781_counterpoise_zp1st` (Eq. 4.1–4.2) and
`tb781_tower_ic1st` (Eq. 4.3–4.4).

**EPR contour** (AS/NZS 3835.1, EREC S34, AS/NZS 4853). For a far-field hemisphere,
`x = ρ·I_E/(2π·V_lim)`.

**Inductive coupling** (CIGRE TB 95, AS/NZS 4853). `D_e = 658.5·√(ρ/f)` and
`z_m = π²f·10⁻⁴ + j·4πf·10⁻⁴·ln(D_e/d)` Ω/km, valid for `d ≪ D_e`. The induced EMF is
`E = k·|z_m|·L·I`.

**HVDC electrode** (EPRI EL-2020). `Δθ_max = V²/(2ρλ)` and `m = M·I·t/(z·F)`.

**Bonding networks** (IEEE 1100, BS EN 50310). The mesh opening is `a ≤ c/(10·f_max)`, and a
bonding strap has `|Z| = 2πf·(1 µH/m)·ℓ`.


## 11. Studies added in 1.8.0

| Quantity | Formula / method | Source |
|---|---|---|
| Robust soil fit | residuals scaled by σ̂ = 1.4826·MAD; worst reading beyond max(3σ̂, 5 %) set aside, one at a time, at most n/5 | robust statistics (Huber 1981) |
| Lateral variation | separate two-layer fit per traverse; flagged when ρ₁, ρ₂ or common-spacing readings differ by more than ×1.5 | IEEE Std 81-2025 §7 |
| Shield-wire self / mutual impedance | z_s = r + π²·10⁻⁴f + j4π·10⁻⁴f·ln(D_e/GMR); z_m with d for GMR; D_e = 658.5√(ρ/f) | Carson (1926) |
| Infinite ladder | Z∞ = Z_s/2 + √(Z_s·R_t + Z_s²/4) | Endrenyi (1963); IEEE 80 Annex C |
| Grid current, fault anywhere on the line | nodal solution of the ladder with series EMF −z_m·I_phase per span; I_g = V₀/R_g | IEEE Std 80-2013 §15.9 |
| Touch region | within 1 m of buried metal in plan, or enclosed by conductors on all four sides; or user touch zones | — |
| Step voltage | max over position and direction of \|V(p) − V(p + s·u(θ))\|, refined to 0.02 m and 1° | IEEE Std 80 §16 |
| End refinement | end segment halved three times towards each free conductor end (≥ 10 radii) | — |
| Discretisation error | f∞ ≈ f(h/2) + [f(h/2) − f(h)]; design value max(f(h), f(h/2), f∞) | Richardson extrapolation |
| Non-equipotential solution | thin-wire circuit–field model at 50/60 Hz (internal impedance, self and mutual inductance with earth return); surface potential from the static Green's function of the complex leakage currents | Grcev & Dawalibi (1990) |
| Non-equipotential, reduced (1.8.7) | currents eliminated: Y = Dᵀ Z_L⁻¹ D + Mᵀ Z_T⁻¹ M (N_n × N_n), I_L = Z_L⁻¹ D V, I_T = Z_T⁻¹ M V; up to 3000 segments (was 1500) | — |
| Non-equipotential, two scales (1.8.9) | above 3000 segments (counted after the cuts): coarse circuit-field model → V_n; V interpolated along each conductor to the fine mid-points; P I_f = V (real, imaginary), dense or H-matrix + GMRES; I_f scaled to I_G (ratio reported); surface, touch and step from I_f, metal at the fine segment ends; Z and V_n from the coarse model | 300 m grid: touch, step within 0.4 % of the full 5 m model (20 m alone: 6–20 %) |
| Plate (1.9.0) | n strips along the long side, edges t_k = ½ − ½cos(πk/n) across the short side; strip = wire of radius w_k/2π (array ≡ plane); segments short side/n, not graded; n = 16, ≥ π·W/(2.4 d) for a horizontal plate, ≤ 64 | Panel solution and Read (1997): +0.08 to +0.22 % at n = 16 |
| Shortest segment (1.9.1) | bare conductors: segment length ≥ 10 radii (bem, hf); plates exempt (validated strips); concrete-encased ≥ 1.5 r_c | below ~4 radii the matrix is indefinite (negative leakage) |
| Shield-wire bundle (1.9.2) | two wires bonded at every tower: z = 1/(1ᵀZ⁻¹1) = (z_s + z_m(d))/2 per km | identity to 10⁻¹² |
| Shield-wire corridor (1.9.2) | lines sharing the route: Y = BᵀZ⁻¹B/ℓ, J = −BᵀZ⁻¹z_p·I_ph per span; nodes per line and tower, shared station and remote nodes | wire-level branch solution 10⁻¹⁰; far-field −Z⁻¹z_p·I 10⁻⁶ |
| Transferred potential, circuit-field check (1.9.2) | station + route in the hf model at 50 Hz (route internal impedance per wire, coating as resistive shell), bonded at the nearest grid node, fed at the grid node nearest the centroid; design touch = max of the two models | coupled solution: 0.1–4 % |
| Lightning mesh, graded (1.9.3) | above 800 segments: s(d) = s₀ + α·d from the injection, s₀ = min(1 m, 0.2/|γ(f_max)|, extent/400); α by bisection to the limit; limit raised to n_min + 400 when the crossings alone need n_min | ≤ 0.1 % in |Z| (100 Hz–10 MHz) against meshes 3–8 times finer; old uniform mesh 0.7–68 % |
| Soil uncertainty | log-normal samples from C = s²(JᵀJ)⁻¹, Latin hypercube in the standard normal space (1.8.3); percentiles and probability of compliance | McKay, Beckman & Conover (1979) |
| Confidence of a probability | Wilson score interval, z = 1.96; samples for ±5 %: 1.96²p(1 − p)/0.05²; P(max > p95) = 1 − 0.95ⁿ | Wilson (1927) |
| Fences, non-equipotential (1.8.3) | posts and wire leak; post tops and wire merged into one node (fabric without leakage); bonded: joined to the nearest grid node | — |
| Seasonal soil | top layer × dry factor to a depth; optional frozen layer; at most four layers | IEEE Std 80 §13.4 |
| Graded grid | x = L(u − g·sin(2πu)/2π) | — |
| Fall-of-potential curve | R(x) = (V_E − V_P(x))/I with grid (+I) and current electrode (−I) solved together | IEEE Std 81-2025 §8 |
| Induced EMF on a parallel conductor | z_m·I per metre over the parallel stretch, series source in the lossy line | Carson (1926); IEEE 80 §17.3 |
| Induced EMF, any route (1.8.5) | e(s) = z_m(d(s))·I·(t·u), nearest point of the faulted line; 0 beyond its ends or d > D_e | Carson (1926); ITU-T K.26 sectioning |
| Shield-wire ladder, real lines (1.8.5) | span-by-span Z_k, EMF −z_m·ℓ_k·I, R_t,k per tower; other lines as ladder input admittances at the station node | Endrenyi (1967); EREC S34 |
| Cable-sheath return (1.8.5) | sheath ladder with core coupling, z_s, z_m by Carson; equals EREC S34 D.2.1/D.2.3 for one three-core section | EREC S34:2018 App. D |
| Cross-bonded sheaths (1.9.4) | every sheath of every minor section a branch (Carson matrix with the faulted core), transpositions at the link boxes, earths at A, B and the major joints; link boxes open | equals the both-ends model with earths at the major joints for equal sections (10⁻¹²); independent path-by-path solution (10⁻¹⁰) |
| Collection areas | A_D = LW + 6H(L + W) + 9πH²; A_M = 2r_M(L + W) + πr_M², r_M = 350/U_w; A_L = 40L_L (0.6√ρ·L_L buried, ρ > 400 Ω·m); A_I = 2r_I·L_L, r_I = 2000/U_w^1.8; N_SG = k·N_G | IEC 62305-2:2024 Annex A |
| Risk R, frequency F | R = R_L1 + R_L2 per zone (Table 3, with P_P = t_z/8760, P_e = t_e/8760); F = F_C + F_M + F_W + F_Z (Table 4); R_T = 10⁻⁵, F_T set by the owner | IEC 62305-2:2024 §6–9, Annexes A–C, F |
| Damage to the surroundings (1.9.5) | R_XE of Table E.1: Table 3 with P_P → t_zE/8760 (Table E.2) and L → L_F1E, L_O1E (Table E.3), L_F2E, L_O2E (Table E.4); added to R_L1, R_L2 of the zone | IEC 62305-2:2024 Annex E, (C.1)–(C.2) |
| SPD current share | I_imp = 0.5·I/(n_s·m); conventional surge currents by source | IEC 62305-1:2024 Annex E |
| SPD protection condition | U_p/f = U_p + ΔU, ΔU = 0.1·I_SPD kV/m; ≤ U_w, ≤ 0.8U_w (≤ 10 m), ≤ (U_w − U_i)/k (> 10 m, k = 1…2); U_p ≤ 0.5U_w critical; I_imp per mode Table C.3 | IEC 62305-4:2024 Annex C |
| Quadrature tiers (1.8.4) | matrix: 6 × 10 Galerkin within 2.5 L, 3 × 4 to 8 L, 4-point collocation beyond; field: 12 points within 5 L, 2 points beyond | Gauss–Legendre |
| DXF import (1.8.4) | ASCII DXF ENTITIES: LINE, LWPOLYLINE/POLYLINE (bulge = tan θ/4, chords ≤ 15°), ARC, CIRCLE, POINT, INSERT; unit from $INSUNITS | AutoCAD DXF reference |
| Binary DXF (1.9.5) | sentinel "AutoCAD Binary DXF"; group codes of 1 byte (255 + 2 bytes) to R12, 2 bytes after; values by code range (double, int16/32/64, bool, chunk, zero-terminated string); strings UTF-8 from AC1021, else $DWGCODEPAGE | AutoCAD DXF reference, binary DXF |
| Governing value (1.8.2) | X_gov = max(X_plain, X_conv, X_seasonal, X_MC,95 %, X_non-equipotential) over studies on the same model; zone and fence touch × X_gov/X_plain | — |
