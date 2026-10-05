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
Earth pits: an electrode in a hole filled with low-resistivity backfill.

An earth pit is a rod, pipe or plate set in a bored or dug hole that is filled,
wholly or in part, with a material of lower resistivity than the soil
(bentonite, coke breeze, an earthing enhancing compound, or a salt-charcoal-clay
mix), usually with an inspection housing at the top.  Physically the backfill
replaces the innermost shells of soil, where most of the resistance lies
(tutorial §1.4, §11.7).

Methods
-------
* ``solve_pit`` — an axisymmetric finite-volume solution of Laplace's equation
  div(sigma grad V) = 0 in (r, z) for a vertical rod (or a horizontal disc of
  the plate's area) inside a cylinder of backfill, in uniform soil, with no
  current through the surface.  It needs no closed form and is checked against
  Dwight's rod (0.1 % from the boundary-element value), the buried-plate
  formula (1.5 %) and BS 7430 9.5.7 (2.5 %).
* ``bs7430_backfilled`` — BS 7430:2011+A1:2015, 9.5.7: rod of length L and
  diameter d in a column of backfill of diameter D over its whole length,
      R = [ (rho - rho_c)(ln(8L/D) - 1) + rho_c (ln(8L/d) - 1) ] / (2 pi L).
  This is exactly two shells in series: the backfill annulus from d to D, and
  the soil outside a rod of diameter D.
* ``pit_group`` — n equal pits in a line at spacing s, by superposition (§1.6)
  with the BS 7430 9.5.4 group factor:  R_n = (R_1 + lambda rho/(2 pi s)) / n.
* ``current_density_check`` — BS 7430 9.8: J_max = 1e3 sqrt(57.7/(rho t)) A/m²
  for a short-time overload, 40 A/m² for continuous loading, at the metal
  surface (in the backfill) and at the backfill boundary (in the soil).

Material data are those stated in the sources: bentonite 2.5 ohm.m at 300 %
moisture (IEEE 80 14.5), 8.7 ohm.m at a water-to-bentonite ratio of 4:1
(CBIP Publication 302, 6.3.1.1), enhancement materials below 0.12 ohm.m
(IEEE 80 14.5), concrete 30–200 ohm.m (IEEE 80 14.6).  The resistivity of a
mix is the manufacturer's declared value (IEC 62561-7, 4.4, 5.4); for a
site mix it must be measured.
"""

from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------------------
# Backfill materials (resistivity in ohm.m, with source)
# ---------------------------------------------------------------------------

BACKFILLS = {
    "bentonite_300": dict(rho=2.5, label="Bentonite, 300 % moisture",
                          source="IEEE Std 80-2013, 14.5 b)"),
    "bentonite_4to1": dict(rho=8.7, label="Bentonite slurry, water:bentonite 4:1 at 20 °C",
                           source="CBIP Publication 302 (2007), 6.3.1.1"),
    "gem": dict(rho=0.12, label="Ground enhancement material (≤ 0.12 Ω·m)",
                source="IEEE Std 80-2013, 14.5 d); declared value per IEC 62561-7"),
    "concrete": dict(rho=50.0, label="Concrete in moist soil (30–200 Ω·m)",
                     source="IEEE Std 80-2013, 14.6; 30–90 Ω·m in the Iranian earthing regulation, Art. 54"),
    "custom": dict(rho=None, label="Measured / declared value",
                   source="manufacturer's declared resistivity (IEC 62561-7, 5.4) or a soil-box test"),
}

# IEC 62561-5:2023, 4.1 and 6.4.2: inspection-housing classes and test loads
HOUSING_CLASSES = {
    "L": dict(use="light duty: walkways", load_kN=4.0, plate_mm=62),
    "M": dict(use="medium duty: slow-moving cars", load_kN=15.0, plate_mm=130),
    "H": dict(use="heavy duty: slow-moving multi-axle vehicles", load_kN=30.0, plate_mm=170),
}

# Minimum earth-rod sizes: IEC 62561-2:2012 Table 3 and the Iranian earthing
# safety regulation (2007), Art. 24.  Diameters in mm.
ROD_MIN_D_MM = {
    "copper": dict(iec=15.0, iran=12.0),
    "copper_bonded_steel": dict(iec=14.0, iran=16.0),
    "galvanized_steel": dict(iec=14.0, iran=16.0),
    "stainless_steel": dict(iec=15.0, iran=None),
}
# Plates: IEC 62561-2 Table 3 (500 x 500 mm; Cu 1.5 mm, galvanized steel 3 mm);
# Iranian regulation Art. 15 (1.0 x 0.5 m; Cu 2 mm, galvanized steel 3 mm).
PLATE_MIN = {
    "copper": dict(iec=(0.25, 1.5), iran=(0.5, 2.0)),
    "galvanized_steel": dict(iec=(0.25, 3.0), iran=(0.5, 3.0)),
}


# ---------------------------------------------------------------------------
# Closed forms
# ---------------------------------------------------------------------------

def rod_dwight(rho: float, L: float, d: float) -> float:
    return rho / (2.0 * math.pi * L) * (math.log(8.0 * L / d) - 1.0)


def bs7430_backfilled(rho: float, rho_c: float, L: float, d: float, D: float) -> dict:
    """BS 7430:2011+A1:2015 9.5.7: rod in a full-length column of backfill."""
    if D <= d:
        raise ValueError("The backfill diameter D must exceed the rod diameter d.")
    R = ((rho - rho_c) * (math.log(8.0 * L / D) - 1.0)
         + rho_c * (math.log(8.0 * L / d) - 1.0)) / (2.0 * math.pi * L)
    R_annulus = rho_c / (2.0 * math.pi * L) * math.log(D / d)
    return dict(R=R, R_backfill=R_annulus, R_soil=R - R_annulus,
                formula="R = [(ρ − ρc)(ln 8L/D − 1) + ρc(ln 8L/d − 1)]/(2πL)  (BS 7430 9.5.7)")


# ---------------------------------------------------------------------------
# Axisymmetric finite-volume solver
# ---------------------------------------------------------------------------

def _graded(points, end, h0, growth):
    """Sorted node coordinates in [0, end], fine (h0) at each of `points`."""
    pts = {0.0, end}
    for f in points:
        pts.add(f)
        for sgn in (1.0, -1.0):
            x, h = f, h0
            while 0.0 < x < end:
                pts.add(x)
                x += sgn * h
                h *= growth
    return np.array(sorted(p for p in pts if 0.0 <= p <= end))


def _merge(x, tol, keep):
    x = np.sort(np.asarray(x, float))
    out = [x[0]]
    for v in x[1:]:
        if v - out[-1] > tol:
            out.append(v)
        elif any(abs(v - k) < 1e-12 for k in keep):
            out[-1] = v
    return np.array(out)


def _solve_blocks(g_r, g_z, elec, farb):
    """Solve the five-point network for V (1 on `elec`, 0 on `farb`).

    Direct block-tridiagonal elimination (block Thomas) using numpy only, so
    that the same code runs in the browser (Pyodide ships numpy, not scipy).
    The blocks run along the longer grid axis; each block is one line of
    nodes along the shorter axis.
    """
    if elec.shape[1] > elec.shape[0]:
        # make axis 0 the longer one
        V = _solve_blocks(g_z.T, g_r.T, elec.T, farb.T)
        return V.T
    n0, m = elec.shape
    fixed = elec | farb
    Vfix = np.where(elec, 1.0, 0.0)
    # remove links touching a fixed node from the unknown system; their
    # conductance stays on the diagonal and their current goes to the rhs
    diag = np.zeros((n0, m))
    diag[:-1, :] += g_r; diag[1:, :] += g_r
    diag[:, :-1] += g_z; diag[:, 1:] += g_z
    rhs = np.zeros((n0, m))
    rhs[:-1, :] += g_r * Vfix[1:, :] * fixed[1:, :]
    rhs[1:, :] += g_r * Vfix[:-1, :] * fixed[:-1, :]
    rhs[:, :-1] += g_z * Vfix[:, 1:] * fixed[:, 1:]
    rhs[:, 1:] += g_z * Vfix[:, :-1] * fixed[:, :-1]
    off0 = np.where(fixed[:-1, :] | fixed[1:, :], 0.0, g_r)      # between blocks
    off1 = np.where(fixed[:, :-1] | fixed[:, 1:], 0.0, g_z)      # within a block
    diag = np.where(fixed, 1.0, diag)
    rhs = np.where(fixed, Vfix, rhs)
    idx = np.arange(m - 1)
    Sinv = []
    y = []
    prev_inv = None
    for i in range(n0):
        S = np.diag(diag[i])
        S[idx, idx + 1] = -off1[i]
        S[idx + 1, idx] = -off1[i]
        b = rhs[i].copy()
        if i > 0:
            c = off0[i - 1]
            S -= c[:, None] * prev_inv * c[None, :]
            b += c * (prev_inv @ y[-1])
        prev_inv = np.linalg.inv(S)
        Sinv.append(prev_inv)
        y.append(b)
    V = np.zeros((n0, m))
    V[-1] = Sinv[-1] @ y[-1]
    for i in range(n0 - 2, -1, -1):
        V[i] = Sinv[i] @ (y[i] + off0[i] * V[i + 1])
    return V


def solve_pit(rho: float, rho_c: float, electrode: str = "rod", L: float = 3.0,
              d: float = 0.016, area: float = 0.5, top: float = 0.0,
              D: float = 0.3, fill_top: float = 0.0, fill_bottom: float | None = None,
              far: float = 3000.0, growth: float = 1.10, field: bool = False) -> dict:
    """Resistance of an electrode in a cylinder of backfill, by finite volumes.

    field=True also returns the node coordinates r, z (m) and the potential
    V (per unit of electrode potential) for plotting.

    electrode  'rod'   — vertical solid cylinder, diameter d, from depth `top`
                         to `top + L`;
               'plate' — a plate of one-face area `area`, modelled as a
                         horizontal disc of the same area at depth `top`
                         (deep in the soil the orientation of a thin plate
                         changes its resistance little).
    backfill   cylinder of diameter D from depth fill_top to fill_bottom
               (default: to the bottom of the electrode), resistivity rho_c.
    """
    if electrode == "plate":
        a = math.sqrt(area / math.pi)
        L = 0.0
    else:
        a = d / 2.0
    b = D / 2.0
    if fill_bottom is None:
        fill_bottom = top + L
    bottom = top + L
    h0r = max(min(a, b) * 0.02, 0.0015)
    h0z = 0.02 if L > 0 else min(0.02, h0r)
    r = _graded([a, b], far, h0r, growth)
    r = np.concatenate([r, np.linspace(0.0, a, 5)])
    zpts = [bottom, fill_bottom, fill_top, top]
    z = _graded([p for p in zpts if p > 0] or [max(L, 0.5)], far, h0z, growth)
    if L > 0:
        z = np.concatenate([z, np.linspace(top, bottom, max(int(L / 0.05), 1) + 1)])
    r = _merge(r, 1e-5, (a, b))
    z = _merge(z, 1e-4, tuple(zpts))
    nr, nz = len(r), len(z)

    # dual-cell faces
    rl = np.r_[0.0, 0.5 * (r[1:] + r[:-1])]
    rh = np.r_[0.5 * (r[1:] + r[:-1]), r[-1]]
    zl = np.r_[0.0, 0.5 * (z[1:] + z[:-1])]
    zh = np.r_[0.5 * (z[1:] + z[:-1]), z[-1]]

    def sig(rm, zm):
        inside = (rm < b) & (zm >= fill_top) & (zm < fill_bottom)
        return np.where(inside, 1.0 / rho_c, 1.0 / rho)

    # radial links (i, j)-(i+1, j): the face is split at z_j into two
    # half-heights, which may lie in different materials
    rm = np.outer(0.5 * (r[:-1] + r[1:]), np.ones(nz))
    dr = (r[1:] - r[:-1])[:, None]
    g_r = np.zeros((nr - 1, nz))
    for z0, z1 in ((zl, z), (z, zh)):
        zm = np.outer(np.ones(nr - 1), 0.5 * (z0 + z1))
        g_r += sig(rm, zm) * 2.0 * np.pi * rm * (z1 - z0)[None, :] / dr
    # axial links (i, j)-(i, j+1): the face is split at r_i into two annuli
    zm = np.outer(np.ones(nr), 0.5 * (z[:-1] + z[1:]))
    dz = (z[1:] - z[:-1])[None, :]
    g_z = np.zeros((nr, nz - 1))
    for r0, r1 in ((rl, r), (r, rh)):
        rmid = np.outer(0.5 * (r0 + r1), np.ones(nz - 1))
        g_z += sig(rmid, zm) * (np.pi * (r1 ** 2 - r0 ** 2))[:, None] / dz

    Rg, Zg = np.meshgrid(r, z, indexing="ij")
    elec = (Rg <= a + 1e-12) & (Zg >= top - 1e-9) & (Zg <= bottom + 1e-9)
    farb = (Rg >= r[-1] - 1e-9) | (Zg >= z[-1] - 1e-9)
    V = _solve_blocks(g_r, g_z, elec, farb)
    # current leaving the electrode nodes through links to non-electrode nodes
    Iinj = float((g_r * (elec[:-1, :] & ~elec[1:, :]) * (1.0 - V[1:, :])).sum()
                 + (g_z * (elec[:, :-1] & ~elec[:, 1:]) * (1.0 - V[:, 1:])).sum()
                 + (g_z * (elec[:, 1:] & ~elec[:, :-1]) * (1.0 - V[:, :-1])).sum())
    R = 1.0 / Iinj + rho / (2.0 * math.pi * far)
    n = nr * nz
    out = dict(R=R, nodes=n, method="axisymmetric finite volume (Laplace, insulating surface)")
    if field:
        out.update(r=r, z=z, V=V)
    return out


# ---------------------------------------------------------------------------
# Groups, loading, sizing
# ---------------------------------------------------------------------------

def lambda_line(n: int) -> float:
    return 2.0 * sum(1.0 / k for k in range(2, n + 1)) if n > 1 else 0.0


def pit_group(R1: float, rho: float, n: int, s: float) -> dict:
    """n equal pits in a line at spacing s (superposition; BS 7430 9.5.4 lambda)."""
    lam = lambda_line(n)
    Rn = (R1 + lam * rho / (2.0 * math.pi * s)) / n
    return dict(R=Rn, n=n, s=s, lam=lam, ideal=R1 / n,
                formula="R_n = [R₁ + λρ/(2πs)]/n,  λ = 2(1/2 + … + 1/n)")


def pits_required(R1: float, rho: float, target: float, s: float, max_n: int = 60) -> dict:
    for n in range(1, max_n + 1):
        g = pit_group(R1, rho, n, s)
        if g["R"] <= target:
            return dict(n=n, R=g["R"], s=s, reachable=True)
    g = pit_group(R1, rho, max_n, s)
    floor = rho / (2.0 * math.pi * s) * 2.0 * math.log(1.781 * max_n / 2.718) / max_n
    return dict(n=None, R=g["R"], s=s, reachable=False,
                note=f"{max_n} pits in a line give {g['R']:.2f} Ω; the mutual term "
                     f"alone is {floor:.2f} Ω. Use a grid or longer electrodes.")


def jmax_bs7430(rho: float, t: float) -> float:
    """BS 7430 9.8: maximum short-time current density at an electrode surface (A/m²)."""
    return 1e3 * math.sqrt(57.7 / (rho * t))


def current_density_check(I_fault: float, t: float, rho: float, rho_c: float,
                          electrode: str, L: float, d: float, area: float,
                          D: float, fill_len: float) -> dict:
    if electrode == "plate":
        A_metal = 2.0 * area
    else:
        A_metal = math.pi * d * L
    J_metal = I_fault / A_metal
    out = dict(J_metal=J_metal, Jmax_metal=jmax_bs7430(rho_c, t), A_metal=A_metal)
    out["metal_ok"] = J_metal <= out["Jmax_metal"]
    if fill_len > 0 and D > 0:
        A_b = math.pi * D * fill_len + (math.pi * D ** 2 / 4.0)
        out.update(J_boundary=I_fault / A_b, Jmax_boundary=jmax_bs7430(rho, t), A_boundary=A_b)
        out["boundary_ok"] = out["J_boundary"] <= out["Jmax_boundary"]
    out["continuous_limit"] = 40.0
    return out


def size_checks(electrode: str, material: str, d: float = 0.0, area: float = 0.0,
                thickness_mm: float = 0.0) -> list:
    notes = []
    if electrode == "rod":
        m = ROD_MIN_D_MM.get(material)
        if m:
            dm = d * 1e3
            for key, name in (("iec", "IEC 62561-2:2012 Table 3"), ("iran", "Iranian earthing regulation, Art. 24")):
                if m[key] is not None:
                    ok = dm + 1e-9 >= m[key]
                    notes.append(dict(rule=name, required=f"≥ {m[key]:g} mm", actual=f"{dm:g} mm", ok=ok))
    elif electrode == "plate":
        m = PLATE_MIN.get(material)
        if m:
            for key, name in (("iec", "IEC 62561-2:2012 Table 3"), ("iran", "Iranian earthing regulation, Art. 15")):
                A_req, t_req = m[key]
                ok = area + 1e-9 >= A_req and thickness_mm + 1e-9 >= t_req
                notes.append(dict(rule=name, required=f"≥ {A_req:g} m², ≥ {t_req:g} mm",
                                  actual=f"{area:g} m², {thickness_mm:g} mm", ok=ok))
    return notes


def design(p: dict) -> dict:
    """Full earth-pit calculation for the API (see api.api_earthpit)."""
    rho = float(p.get("rho", 100.0))
    season = float(p.get("season_factor", 1.0))
    electrode = str(p.get("electrode", "rod"))
    L = float(p.get("L", 3.0)); d = float(p.get("d", 0.016))
    area = float(p.get("area", 0.5)); top = float(p.get("top", 0.0))
    D = float(p.get("D", 0.3))
    key = str(p.get("backfill", "bentonite_4to1"))
    mat = BACKFILLS.get(key, BACKFILLS["custom"])
    rho_c = float(p["rho_c"]) if p.get("rho_c") not in (None, "") else mat["rho"]
    if rho_c is None:
        raise ValueError("Enter the backfill resistivity for a custom material.")
    fill_top = float(p.get("fill_top", 0.0))
    bottom = top + (0.0 if electrode == "plate" else L)
    fill_bottom = float(p.get("fill_bottom", bottom + (0.2 if electrode == "plate" else 0.0)))
    n = int(p.get("n", 1)); s = float(p.get("s", max(2.0 * (bottom or 1.0), 3.0)))

    common = dict(electrode=electrode, L=L, d=d, area=area, top=top, D=D)
    bare = solve_pit(rho, rho, **common, fill_top=fill_top, fill_bottom=fill_bottom)["R"]
    pit = solve_pit(rho, rho_c, **common, fill_top=fill_top, fill_bottom=fill_bottom)
    dry = solve_pit(rho * season, rho_c, **common, fill_top=fill_top, fill_bottom=fill_bottom)["R"] \
        if season != 1.0 else pit["R"]
    res = dict(rho=rho, rho_c=rho_c, backfill=mat["label"], backfill_source=mat["source"],
               R_bare=bare, R_pit=pit["R"], reduction=1.0 - pit["R"] / bare,
               R_dry=dry, season_factor=season, method=pit["method"], nodes=pit["nodes"])
    if electrode == "rod" and abs(fill_top - top) < 1e-9 and abs(fill_bottom - bottom) < 1e-9 and top == 0.0:
        res["bs7430"] = bs7430_backfilled(rho, rho_c, L, d, D)
        res["R_dwight_bare"] = rod_dwight(rho, L, d)
    fill_len = max(fill_bottom - fill_top, 0.0)
    res["backfill_volume_m3"] = math.pi * D ** 2 / 4.0 * fill_len - (
        math.pi * d ** 2 / 4.0 * min(L, fill_len) if electrode == "rod" else 0.0)
    res["group"] = pit_group(res["R_pit"], rho, n, s)
    res["group_dry"] = pit_group(dry, rho * season, n, s)
    if p.get("target") not in (None, ""):
        res["required"] = pits_required(dry, rho * season, float(p["target"]), s)
    if p.get("I_fault") not in (None, "") and p.get("t_fault") not in (None, ""):
        I_pit = float(p["I_fault"]) / max(n, 1)
        res["loading"] = current_density_check(I_pit, float(p["t_fault"]), rho * season, rho_c,
                                               electrode, L, d, area, D, fill_len)
        res["loading"]["I_per_pit"] = I_pit
    res["size_checks"] = size_checks(electrode, str(p.get("material", "copper_bonded_steel")),
                                     d=d, area=area, thickness_mm=float(p.get("thickness_mm", 0) or 0))
    hc = str(p.get("housing_class", "L")).upper()
    if hc in HOUSING_CLASSES:
        res["housing"] = dict(cls=hc, **HOUSING_CLASSES[hc],
                              rule="IEC 62561-5:2023, 4.1 and 6.4.2 (load for 120 s, ≤ 3 mm set)")
    res["maintenance"] = dict(
        retest_limit=1.5 * res["R_pit"],
        note="Re-test in the dry season and after watering; service the pit when its "
             "resistance exceeds 1.5 times the commissioning value (CBIP Publication 302, 8.4.5).")
    return res
