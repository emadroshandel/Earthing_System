"""
Substation / power-plant earth grid design to IEEE Std 80-2013.

Implements the complete design procedure of Figure 33 (design flow chart):

  1. field data and soil model                       -> soil.py
  2. conductor size                                  -> conductor.py
  3. tolerable touch and step criteria               -> tolerable_voltages()
  4. initial grid layout                             -> GridGeometry
  5. grid resistance (Sverak and Schwarz)            -> grid_resistance()
  6. grid current and GPR                            -> faultcurrent.py
  7. mesh and step voltages                          -> mesh_step_voltages()
  8. comparison, refinement, detail design           -> design() / optimise()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

from .materials import diameter_from_area


# ---------------------------------------------------------------------------
# 3. Tolerable body-current voltages
# ---------------------------------------------------------------------------

def surface_derating(rho: float, rho_s: float, hs: float) -> dict:
    """Surface-layer derating factor C_s, IEEE Std 80-2013 Eq. (27).

        C_s = 1 - 0.09 (1 - rho/rho_s) / (2 h_s + 0.09)
    """
    if rho_s <= 0 or hs <= 0:
        return dict(Cs=1.0, note="No surface layer.")
    Cs = 1.0 - 0.09 * (1.0 - rho / rho_s) / (2.0 * hs + 0.09)
    return dict(Cs=Cs, rho=rho, rho_s=rho_s, hs=hs,
                formula="IEEE Std 80-2013 Eq. (27)")


def tolerable_voltages(rho: float, rho_s: float, hs: float, ts: float,
                       body_weight: int = 70) -> dict:
    """Tolerable step and touch voltages, IEEE Std 80-2013 Eq. (29)–(33).

        E_step  = (1000 + 6 C_s rho_s) * k / sqrt(t_s)
        E_touch = (1000 + 1.5 C_s rho_s) * k / sqrt(t_s)
        k = 0.116 (50 kg body)   or   0.157 (70 kg body)
    """
    cs = surface_derating(rho, rho_s, hs)
    Cs = cs["Cs"]
    k = 0.157 if int(body_weight) == 70 else 0.116
    rs = rho_s if rho_s > 0 else rho
    E_step = (1000.0 + 6.0 * Cs * rs) * k / math.sqrt(ts)
    E_touch = (1000.0 + 1.5 * Cs * rs) * k / math.sqrt(ts)
    return dict(E_step=E_step, E_touch=E_touch, Cs=Cs, k=k,
                body_weight=body_weight, ts=ts, rho=rho, rho_s=rho_s, hs=hs,
                RB=1000.0,
                Ib=k / math.sqrt(ts),
                formula=("IEEE Std 80-2013 Eq. (30)/(32) for 50 kg, "
                         "Eq. (29)/(31) for 70 kg"))


# ---------------------------------------------------------------------------
# 4. Grid geometry
# ---------------------------------------------------------------------------

@dataclass
class GridGeometry:
    Lx: float = 70.0            # grid dimension in x (m)
    Ly: float = 70.0            # grid dimension in y (m)
    D: float = 7.0              # conductor spacing (m)
    h: float = 0.5              # burial depth (m)
    d: float = 0.01             # conductor diameter (m)
    n_rods: int = 0             # number of ground rods
    Lr: float = 0.0             # length of each rod (m)
    d_rod: float = 0.016        # rod diameter (m)
    rods_on_perimeter: bool = True
    shape: str = "rectangular"  # rectangular | L | T | irregular
    Dm: float = 0.0             # max distance between any two grid points (m)

    # ---- derived ---------------------------------------------------------
    @property
    def A(self) -> float:
        return self.Lx * self.Ly

    @property
    def Lp(self) -> float:
        return 2.0 * (self.Lx + self.Ly)

    @property
    def Nx(self) -> int:
        """Conductors running in the x direction (parallel to x)."""
        return max(2, int(round(self.Ly / self.D)) + 1)

    @property
    def Ny(self) -> int:
        return max(2, int(round(self.Lx / self.D)) + 1)

    @property
    def Lc(self) -> float:
        """Total length of buried horizontal conductor (m)."""
        return self.Nx * self.Lx + self.Ny * self.Ly

    @property
    def LR(self) -> float:
        return self.n_rods * self.Lr

    @property
    def LT(self) -> float:
        return self.Lc + self.LR

    @property
    def Dmax(self) -> float:
        return self.Dm if self.Dm > 0 else math.hypot(self.Lx, self.Ly)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(A=self.A, Lp=self.Lp, Nx=self.Nx, Ny=self.Ny,
                 Lc=self.Lc, LR=self.LR, LT=self.LT, Dmax=self.Dmax)
        return d

    def conductor_paths(self):
        """Return the grid conductor segments as ((x1,y1),(x2,y2)) pairs."""
        segs = []
        ny = self.Ny
        nx = self.Nx
        for j in range(ny):
            x = self.Lx * j / (ny - 1) if ny > 1 else 0.0
            segs.append(((x, 0.0), (x, self.Ly)))
        for i in range(nx):
            y = self.Ly * i / (nx - 1) if nx > 1 else 0.0
            segs.append(((0.0, y), (self.Lx, y)))
        return segs

    def rod_positions(self):
        """Ground-rod (x, y) positions: corners first, then around perimeter."""
        n = self.n_rods
        if n <= 0:
            return []
        if not self.rods_on_perimeter:
            # distribute over the whole area
            pts, k = [], max(1, int(math.ceil(math.sqrt(n))))
            for i in range(k):
                for j in range(k):
                    if len(pts) < n:
                        pts.append((self.Lx * (i + 0.5) / k,
                                    self.Ly * (j + 0.5) / k))
            return pts
        per = self.Lp
        pts = []
        for i in range(n):
            s = per * i / n
            if s < self.Lx:
                pts.append((s, 0.0))
            elif s < self.Lx + self.Ly:
                pts.append((self.Lx, s - self.Lx))
            elif s < 2 * self.Lx + self.Ly:
                pts.append((2 * self.Lx + self.Ly - s, self.Ly))
            else:
                pts.append((0.0, per - s))
        return pts


# ---------------------------------------------------------------------------
# 5. Grid resistance
# ---------------------------------------------------------------------------

def sverak_resistance(rho: float, A: float, LT: float, h: float) -> dict:
    """IEEE Std 80-2013 Eq. (52) -- Sverak.

        R_g = rho [ 1/L_T + 1/sqrt(20A) ( 1 + 1/(1 + h sqrt(20/A)) ) ]
    """
    Rg = rho * (1.0 / LT + 1.0 / math.sqrt(20.0 * A)
                * (1.0 + 1.0 / (1.0 + h * math.sqrt(20.0 / A))))
    return dict(Rg=Rg, method="Sverak", formula="IEEE Std 80-2013 Eq. (52)")


def _schwarz_k(Lx: float, Ly: float, h: float, A: float):
    """k1, k2 from IEEE Std 80-2013 Figure 25, linear fits, bilinear in depth."""
    ratio = max(Lx, Ly) / max(min(Lx, Ly), 1e-9)
    sqrtA = math.sqrt(A)
    tables = [
        (0.0,          (-0.04 * ratio + 1.41, -0.15 * ratio + 5.50)),
        (sqrtA / 10.0, (-0.05 * ratio + 1.20,  0.10 * ratio + 4.68)),
        (sqrtA / 6.0,  (-0.05 * ratio + 1.13, -0.05 * ratio + 4.40)),
    ]
    if h <= tables[0][0]:
        return tables[0][1]
    if h >= tables[-1][0]:
        return tables[-1][1]
    for (d0, v0), (d1, v1) in zip(tables[:-1], tables[1:]):
        if d0 <= h <= d1:
            f = (h - d0) / max(d1 - d0, 1e-12)
            return (v0[0] + f * (v1[0] - v0[0]), v0[1] + f * (v1[1] - v0[1]))
    return tables[-1][1]


def schwarz_resistance(rho: float, g: GridGeometry) -> dict:
    """IEEE Std 80-2013 Eq. (56)–(60) -- Schwarz combined grid + rod bed."""
    A, Lc, Lx, Ly, h = g.A, g.Lc, g.Lx, g.Ly, g.h
    k1, k2 = _schwarz_k(Lx, Ly, h, A)
    sqrtA = math.sqrt(A)
    hp = math.sqrt(g.d * h) if h > 0 else 0.5 * g.d          # h'
    R1 = rho / (math.pi * Lc) * (math.log(2.0 * Lc / hp)
                                 + k1 * Lc / sqrtA - k2)

    if g.n_rods > 0 and g.Lr > 0:
        nR, Lr, dR = g.n_rods, g.Lr, g.d_rod
        R2 = rho / (2.0 * math.pi * nR * Lr) * (
            math.log(8.0 * Lr / dR) - 1.0
            + 2.0 * k1 * Lr * (math.sqrt(nR) - 1.0) ** 2 / sqrtA)
        Rm = rho / (math.pi * Lc) * (math.log(2.0 * Lc / Lr)
                                     + k1 * Lc / sqrtA - k2 + 1.0)
        den = R1 + R2 - 2.0 * Rm
        Rg = (R1 * R2 - Rm ** 2) / den if abs(den) > 1e-12 else R1
    else:
        R2 = Rm = float("nan")
        Rg = R1

    return dict(Rg=Rg, R1=R1, R2=R2, Rm=Rm, k1=k1, k2=k2, h_prime=hp,
                method="Schwarz", formula="IEEE Std 80-2013 Eq. (56)–(60)")


def grid_resistance(rho: float, g: GridGeometry, method: str = "auto") -> dict:
    sv = sverak_resistance(rho, g.A, g.LT, g.h)
    try:
        sc = schwarz_resistance(rho, g)
    except (ValueError, ZeroDivisionError):
        sc = dict(Rg=float("nan"), method="Schwarz", formula="not evaluated")
    if method == "sverak":
        chosen = sv
    elif method == "schwarz":
        chosen = sc
    else:
        chosen = sc if (g.n_rods > 0 and math.isfinite(sc["Rg"])) else sv
    return dict(Rg=chosen["Rg"], chosen=chosen["method"],
                sverak=sv, schwarz=sc)


# ---------------------------------------------------------------------------
# 7. Mesh and step voltages
# ---------------------------------------------------------------------------

def geometric_factors(g: GridGeometry) -> dict:
    """n = n_a n_b n_c n_d and the K factors, IEEE Std 80-2013 Eq. (84)–(94)."""
    A, Lc, Lp, Lx, Ly, h, d = g.A, g.Lc, g.Lp, g.Lx, g.Ly, g.h, g.d

    # IEEE Std 80-2013 Eq. (85)-(88):
    #   n_b = 1 for square grids
    #   n_c = 1 for square and rectangular grids
    #   n_d = 1 for square, rectangular and L-shaped grids
    shape = (g.shape or "rectangular").lower()
    is_square = abs(Lx - Ly) < 1e-6 and shape in ("square", "rectangular")

    n_a = 2.0 * Lc / Lp
    n_b = 1.0 if is_square else math.sqrt(Lp / (4.0 * math.sqrt(A)))
    n_c = 1.0 if shape in ("square", "rectangular") else (
        (Lx * Ly / A) ** (0.7 * A / (Lx * Ly)) if Lx * Ly > 0 else 1.0)
    n_d = 1.0 if shape in ("square", "rectangular", "l") else (
        g.Dmax / math.sqrt(Lx ** 2 + Ly ** 2))
    n = n_a * n_b * n_c * n_d

    has_rods = g.n_rods > 0 and g.rods_on_perimeter
    Kh = math.sqrt(1.0 + h / 1.0)                    # h0 = 1 m
    Kii = 1.0 if has_rods else 1.0 / (2.0 * n) ** (2.0 / n)

    D = g.D
    Km = (1.0 / (2.0 * math.pi)) * (
        math.log(D ** 2 / (16.0 * h * d)
                 + (D + 2.0 * h) ** 2 / (8.0 * D * d)
                 - h / (4.0 * d))
        + (Kii / Kh) * math.log(8.0 / (math.pi * (2.0 * n - 1.0))))
    Ki = 0.644 + 0.148 * n
    Ks = (1.0 / math.pi) * (1.0 / (2.0 * h) + 1.0 / (D + h)
                            + (1.0 / D) * (1.0 - 0.5 ** (n - 2.0)))

    return dict(n=n, n_a=n_a, n_b=n_b, n_c=n_c, n_d=n_d,
                Km=Km, Ki=Ki, Ks=Ks, Kii=Kii, Kh=Kh, D=D,
                has_perimeter_rods=has_rods,
                formula="IEEE Std 80-2013 Eq. (84)–(94)")


def effective_lengths(g: GridGeometry) -> dict:
    """L_M (mesh) and L_S (step), IEEE Std 80-2013 Eq. (89)–(93)."""
    Lc, LR, Lr = g.Lc, g.LR, g.Lr
    if g.n_rods > 0 and g.rods_on_perimeter:
        factor = 1.55 + 1.22 * (Lr / math.sqrt(g.Lx ** 2 + g.Ly ** 2))
        LM = Lc + factor * LR
        note = "Rods in the corners and along the perimeter — Eq. (91)."
    else:
        factor = 1.0
        LM = Lc + LR
        note = "No rods, or rods not on the perimeter — Eq. (90)."
    LS = 0.75 * Lc + 0.85 * LR
    return dict(LM=LM, LS=LS, rod_factor=factor, note=note)


def mesh_step_voltages(rho: float, g: GridGeometry, IG_A: float) -> dict:
    gf = geometric_factors(g)
    el = effective_lengths(g)
    Em = rho * gf["Km"] * gf["Ki"] * IG_A / el["LM"]
    Es = rho * gf["Ks"] * gf["Ki"] * IG_A / el["LS"]
    out = dict(Em=Em, Es=Es, IG_A=IG_A, rho=rho)
    out.update(gf)
    out.update(el)
    out["formula"] = "IEEE Std 80-2013 Eq. (85) E_m = ρ·K_m·K_i·I_G/L_M ; Eq. (92) E_s"
    return out


# ---------------------------------------------------------------------------
# Complete design
# ---------------------------------------------------------------------------

def design(rho: float, g: GridGeometry, IG_kA: float,
           rho_s: float = 3000.0, hs: float = 0.1, ts: float = 0.5,
           body_weight: int = 70, r_method: str = "auto") -> dict:
    tol = tolerable_voltages(rho, rho_s, hs, ts, body_weight)
    res = grid_resistance(rho, g, r_method)
    Rg = res["Rg"]
    IG_A = IG_kA * 1000.0
    GPR = IG_A * Rg
    ms = mesh_step_voltages(rho, g, IG_A)

    gpr_ok = GPR <= tol["E_touch"]
    touch_ok = ms["Em"] <= tol["E_touch"]
    step_ok = ms["Es"] <= tol["E_step"]
    passed = gpr_ok or (touch_ok and step_ok)

    checks = [
        dict(name="GPR vs tolerable touch voltage",
             value=GPR, limit=tol["E_touch"], unit="V", passed=gpr_ok,
             note=("GPR is below the tolerable touch voltage — no further "
                   "analysis is required (IEEE 80 §16.4)." if gpr_ok else
                   "GPR exceeds the tolerable touch voltage — mesh and step "
                   "voltages must be checked.")),
        dict(name="Mesh (touch) voltage E_m",
             value=ms["Em"], limit=tol["E_touch"], unit="V", passed=touch_ok,
             margin_pct=(tol["E_touch"] - ms["Em"]) / tol["E_touch"] * 100.0),
        dict(name="Step voltage E_s",
             value=ms["Es"], limit=tol["E_step"], unit="V", passed=step_ok,
             margin_pct=(tol["E_step"] - ms["Es"]) / tol["E_step"] * 100.0),
    ]

    return dict(
        geometry=g.to_dict(), tolerable=tol, resistance=res, Rg=Rg,
        GPR=GPR, IG_kA=IG_kA, mesh=ms, checks=checks, passed=passed,
        summary=dict(Rg=Rg, GPR=GPR, Em=ms["Em"], Es=ms["Es"],
                     E_touch=tol["E_touch"], E_step=tol["E_step"],
                     spacing=g.D, n_rods=g.n_rods, LT=g.LT, area=g.A),
    )


def optimise(rho: float, g: GridGeometry, IG_kA: float,
             rho_s: float = 3000.0, hs: float = 0.1, ts: float = 0.5,
             body_weight: int = 70, D_min: float = 1.5, D_step: float = 0.5,
             allow_rods: bool = True, max_rods: int = 200,
             r_method: str = "auto") -> dict:
    """Reduce conductor spacing (and optionally add rods) until compliant.

    Returns the compliant design plus the full sweep used for plotting.
    """
    from copy import deepcopy

    sweep = []
    best = None
    trial = deepcopy(g)
    D = trial.D
    while D >= D_min - 1e-9:
        trial.D = D
        r = design(rho, trial, IG_kA, rho_s, hs, ts, body_weight, r_method)
        sweep.append(dict(D=D, Em=r["mesh"]["Em"], Es=r["mesh"]["Es"],
                          Rg=r["Rg"], GPR=r["GPR"], LT=trial.LT,
                          passed=r["passed"],
                          E_touch=r["tolerable"]["E_touch"],
                          E_step=r["tolerable"]["E_step"]))
        if r["passed"] and best is None:
            best = dict(result=r, D=D, strategy="spacing reduction")
        D = round(D - D_step, 6)

    rod_sweep = []
    if best is None and allow_rods:
        trial = deepcopy(g)
        if trial.Lr <= 0:
            trial.Lr = 3.0
        trial.rods_on_perimeter = True
        n = max(4, trial.n_rods)
        while n <= max_rods:
            trial.n_rods = n
            r = design(rho, trial, IG_kA, rho_s, hs, ts, body_weight, r_method)
            rod_sweep.append(dict(n_rods=n, Em=r["mesh"]["Em"], Es=r["mesh"]["Es"],
                                  Rg=r["Rg"], GPR=r["GPR"], passed=r["passed"]))
            if r["passed"]:
                best = dict(result=r, D=trial.D, n_rods=n,
                            strategy="ground rods added on the perimeter")
                break
            n += 4

    return dict(found=best is not None, best=best, sweep=sweep,
                rod_sweep=rod_sweep,
                note=("No compliant design was found within the search bounds. "
                      "Consider a larger area, a deeper/thicker surface layer, "
                      "faster clearing time, or soil treatment."
                      if best is None else ""))


def conductor_diameter_from_area(area_mm2: float) -> float:
    """Convenience: conductor diameter in metres from area in mm²."""
    return diameter_from_area(area_mm2) / 1000.0
