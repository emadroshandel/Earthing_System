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
Frequency response of earth electrodes: harmonic impedance and the
potential rise under a lightning current.

At power frequency an electrode is one equipotential, and the solver of
`bem` gives its resistance.  Under a lightning front it is not: the
current needs time to travel along the conductor, the conductor's
inductance and the soil's capacitance matter, and the soil's own
resistivity and permittivity fall with frequency.  This module solves the
electrode as a network of thin-wire segments in a lossy half-space, in the
frequency domain, in the way of the hybrid electromagnetic model (HEM) of
Visacro and Soares and of Grcev's electromagnetic model:

* each segment k carries a longitudinal current IL_k along it and leaks a
  transverse current IT_k, uniform along it, into the soil;
* the leakage sets up the scalar potential, with the complex conductivity
  κ = σ + jωε of the soil,

      φ = (1/4πκ) ∫ (IT/L) [e^{-γR}/R + K e^{-γR'}/R'] dl',
      K = (κ - jωε0)/(κ + jωε0),      γ = √(jωμκ);

* the longitudinal current sets up the vector potential, retarded in the
  same way, whose line integral is the inductive voltage drop;
* Kirchhoff's current law closes the system at every node.

The air–soil interface is represented by images ("modified images").  The
scalar potential of a charge has the image coefficient K above.  For the
vector potential the quasi-static limit of the Sommerfeld solution (the
mixed-potential formulation C of Michalski and Zheng) gives no image for
horizontal currents, because the soil and the air have the same
permeability, and the coefficient K on the mirrored current for vertical
ones.  The Sommerfeld correction terms that this leaves out vanish at low
frequency and stay small for buried electrodes below a few megahertz,
which covers the spectrum of lightning currents (Grcev 2009).

The unknowns per frequency are the node potentials, IL and IT:

    (V_a + V_b)/2 - Σ ZT_kj IT_j            = 0     (segment k)
    V_a - V_b - Σ ZL_kj IL_j - Zi_k IL_k    = 0     (segment k, a→b)
    Σ IL out - Σ IL in + Σ IT/2             = I_inj (node n)

At ω → 0 the inductive terms vanish, all node potentials become equal and
the leakage reproduces the solver of `bem`: the harmonic impedance tends
to the earth resistance.

Soil: uniform or horizontally layered (`LayeredSoil`), each layer with
constant ρ and ε_r or with the frequency dependence of Alipio and Visacro
(CIGRE TB 781).  In layered soil the Green's functions are the exact
Sommerfeld solution of the stratified half-space (see `_matrices_layered`).
Concrete-encased conductors (foundations) carry a coaxial concrete shell
in series with their leakage.  Soil ionisation enters the time response
(`time_response(ionisation=…)`).

Coordinates as in `bem`: x, y horizontal, z depth positive downwards.
"""

from __future__ import annotations

import cmath
import math

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:                                    # pragma: no cover
    np = None
    HAVE_NUMPY = False

MU0 = 4e-7 * math.pi
EPS0 = 8.854187817e-12

METAL_RHO = {"copper": 1.72e-8, "steel": 1.8e-7, "aluminium": 2.83e-8,
             "galvanised steel": 1.8e-7}


def _gauss(n: int):
    x, w = np.polynomial.legendre.leggauss(n)
    return 0.5 * (x + 1.0), 0.5 * w


# ---------------------------------------------------------------------------
# Soil
# ---------------------------------------------------------------------------

class Soil:
    """Uniform soil, constant or frequency-dependent.

    model = "constant"          ρ0 and ε_r at every frequency
            "alipio_visacro"    CIGRE TB 781 Eq. 3.10–3.11 (level "mean",
                                "relatively_conservative" or "conservative")
    """

    def __init__(self, rho0: float, eps_r: float = 10.0,
                 model: str = "constant", level: str = "mean"):
        if rho0 <= 0:
            raise ValueError("Soil resistivity must be positive.")
        self.rho0 = float(rho0)
        self.eps_r = float(eps_r)
        self.model = model
        self.level = level

    def params(self, f: float):
        """(σ, ε) at frequency f (S/m, F/m)."""
        if self.model == "constant" or f <= 0:
            return 1.0 / self.rho0, self.eps_r * EPS0
        from .standards import alipio_visacro
        av = alipio_visacro(self.rho0, max(f, 100.0), level=self.level)
        return 1.0 / av["rho"], av["eps_r"] * EPS0

    def kappa(self, f: float) -> complex:
        s, e = self.params(f)
        return complex(s, 2 * math.pi * f * e)

    def describe(self):
        if self.model == "constant":
            return (f"uniform soil, ρ = {self.rho0:g} Ω·m, ε_r = {self.eps_r:g}, "
                    f"constant with frequency")
        return (f"uniform soil, ρ0 = {self.rho0:g} Ω·m, frequency dependent "
                f"(Alipio–Visacro, {self.level.replace('_', ' ')})")

    # a uniform soil is the one-layer case of LayeredSoil
    N = 1
    depths: list = []

    def kappas(self, f: float):
        return np.array([self.kappa(f)])

    def layer_of(self, z: float) -> int:
        return 0

    def rho_near(self, zs=None) -> float:
        return self.rho0


class LayeredSoil:
    """Horizontally layered soil: ρ₁ … ρ_N (Ω·m), thicknesses h₁ … h_{N−1}
    (m), and for every layer a constant or Alipio–Visacro frequency
    dependence.  Each layer is a `Soil`."""

    def __init__(self, rho, h=(), eps_r=10.0, model: str = "constant",
                 level: str = "mean"):
        rho = [float(r) for r in rho]
        h = [float(t) for t in h]
        if len(h) != len(rho) - 1:
            raise ValueError("A soil with N layers needs N resistivities and "
                             "N − 1 thicknesses.")
        if h and min(h) <= 0:
            raise ValueError("Every layer thickness must be greater than zero.")
        eps = list(eps_r) if isinstance(eps_r, (list, tuple)) else [eps_r] * len(rho)
        self.layers = [Soil(r, e, model, level) for r, e in zip(rho, eps)]
        self.rho = rho
        self.h = h
        self.N = len(rho)
        self.depths = list(np.cumsum(h)) if h else []
        self.model = model
        self.level = level
        self.rho0 = rho[0]
        self.eps_r = eps[0]

    def kappas(self, f: float):
        return np.array([s.kappa(f) for s in self.layers])

    def kappa(self, f: float) -> complex:
        """The most conductive layer's κ (it sets the shortest wavelength,
        which is what the segment length must resolve)."""
        k = self.kappas(f)
        return complex(k[int(np.argmax(np.abs(k)))])

    def params(self, f: float):
        return self.layers[0].params(f)

    def layer_of(self, z: float) -> int:
        """0-based layer index of depth z (a point on an interface belongs
        to the layer above)."""
        return int(sum(1 for d in self.depths if z > d + 1e-9))

    def rho_near(self, zs) -> float:
        """Resistivity of the soil around an electrode: the layers weighted
        by the length of conductor in each."""
        zs = np.atleast_1d(np.asarray(zs, float))
        idx = [self.layer_of(z) for z in zs]
        return float(np.mean([self.rho[i] for i in idx]))

    def describe(self):
        parts = []
        for i, r in enumerate(self.rho):
            if i < len(self.h):
                parts.append(f"ρ{i + 1} = {r:g} Ω·m to {self.depths[i]:g} m")
            else:
                parts.append(f"ρ{i + 1} = {r:g} Ω·m below")
        dep = ("constant with frequency" if self.model == "constant" else
               f"frequency dependent (Alipio–Visacro, {self.level.replace('_', ' ')})")
        return f"{self.N}-layer soil: " + ", ".join(parts) + f"; ε_r = {self.eps_r:g}, " + dep


def make_soil(rho, h=(), eps_r=10.0, model="constant", level="mean"):
    """Soil for one or more layers (a single layer gives `Soil`)."""
    rho = list(rho) if isinstance(rho, (list, tuple)) else [rho]
    h = list(h or [])
    if len(rho) == 1:
        return Soil(rho[0], eps_r if not isinstance(eps_r, (list, tuple)) else eps_r[0],
                    model, level)
    return LayeredSoil(rho, h, eps_r, model, level)


def trace_images(depths, kap, K_surf, src: int, tol: float = 1e-7,
                 max_gen: int = 5000):
    """Quasi-static images of a point source in layer `src` (0-based) of a
    stratified medium with complex conductivities κ_i, at one frequency.

    The image theory of the dc earth (`layered.image_series`) carries over
    by replacing 1/ρ with κ = σ + jωε: a wave in layer L meeting the plane
    to layer M is reflected with R = (κ_L − κ_M)/(κ_L + κ_M) and
    transmitted with 1 + R; at the air surface R = K = (κ₁ − jωε₀)/(κ₁ + jωε₀).
    This is the low-frequency (image) limit of the Sommerfeld solution for
    layered media (Arnautovski-Toseva and Grcev 2004, 2011).

    Returns {field_layer: (s, shift, amp)}: the potential in that layer is
    (1/4πκ_src) Σ amp/√(r² + (z − s·z' − shift)²)."""
    N = len(kap)
    plane = np.array([0.0] + list(depths), float)
    R_up = np.zeros(N, complex)
    R_dn = np.zeros(N, complex)
    R_up[0] = K_surf
    for L in range(1, N):
        R_up[L] = (kap[L] - kap[L - 1]) / (kap[L] + kap[L - 1])
    for L in range(N - 1):
        R_dn[L] = (kap[L] - kap[L + 1]) / (kap[L] + kap[L + 1])
    Q = 1e7

    def code(Lr, dr, sr, shr):
        return ((np.round(shr * Q).astype(np.int64) * 8 + Lr) * 4 + dr) * 2 + (sr > 0)

    def merge(Lr, dr, sr, shr, ar):
        if ar.size == 0:
            return Lr, dr, sr, shr, ar
        u, idx, inv = np.unique(code(Lr, dr, sr, shr), return_index=True,
                                return_inverse=True)
        a = (np.bincount(inv, weights=ar.real, minlength=len(u))
             + 1j * np.bincount(inv, weights=ar.imag, minlength=len(u)))
        return Lr[idx], dr[idx], sr[idx], shr[idx], a

    coll = [(np.array([src]), np.array([2]), np.array([1]), np.array([0.0]),
             np.array([1.0 + 0j]))]
    L = np.array([src, src]); d = np.array([0, 1]); sg = np.array([1, 1])
    sh = np.zeros(2); a = np.ones(2, complex)
    gen = 0
    while a.size and gen < max_gen:
        gen += 1
        parts = []
        up = d == 0
        if up.any():
            Lu, su, hu, au = L[up], sg[up], sh[up], a[up]
            Ru = R_up[Lu]
            parts.append((Lu, np.ones_like(Lu), -su, 2.0 * plane[Lu] - hu, au * Ru))
            t = Lu > 0
            if t.any():
                parts.append((Lu[t] - 1, np.zeros(t.sum(), int), su[t], hu[t],
                              au[t] * (1.0 + Ru[t])))
        dn = (~up) & (L < N - 1)
        if dn.any():
            Ld, sd, hd, ad = L[dn], sg[dn], sh[dn], a[dn]
            Rd = R_dn[Ld]
            parts.append((Ld, np.zeros_like(Ld), -sd, 2.0 * plane[Ld + 1] - hd, ad * Rd))
            parts.append((Ld + 1, np.ones_like(Ld), sd, hd, ad * (1.0 + Rd)))
        if not parts:
            break
        L, d, sg, sh, a = (np.concatenate([p[i] for p in parts]) for i in range(5))
        L, d, sg, sh, a = merge(L, d, sg, sh, a)
        coll.append((L, d, sg, sh, a))
        keep = (np.abs(a) > tol) & ~((d == 1) & (L == N - 1))
        L, d, sg, sh, a = L[keep], d[keep], sg[keep], sh[keep], a[keep]
        if len(coll) > 48:
            coll = [merge(*[np.concatenate([c[i] for c in coll]) for i in range(5)])]
    CL, CD, CS, CH, CA = (np.concatenate([c[i] for c in coll]) for i in range(5))
    out = {}
    for Lf in range(N):
        m = CL == Lf
        s_, h_, a_ = CS[m].astype(int), CH[m], CA[m]
        if a_.size:
            u, idx, inv = np.unique(np.round(h_ * Q).astype(np.int64) * 2 + (s_ > 0),
                                    return_index=True, return_inverse=True)
            a_ = (np.bincount(inv, weights=a_.real, minlength=len(u))
                  + 1j * np.bincount(inv, weights=a_.imag, minlength=len(u)))
            s_, h_ = s_[idx], h_[idx]
            k = np.abs(a_) > 0
            s_, h_, a_ = s_[k], h_[k], a_[k]
        out[Lf] = (s_, h_, a_)
    return out


# ---------------------------------------------------------------------------
# Geometry: wires split at every junction, then into segments
# ---------------------------------------------------------------------------

def _closest_params(p1, p2, q1, q2):
    """Parameters (s, t) in [0,1] of the closest points of segments p and q,
    and their distance."""
    d1, d2, r = p2 - p1, q2 - q1, p1 - q1
    a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    c, b = d1 @ r, d1 @ d2
    den = a * e - b * b
    if den > 1e-14 * a * e:
        s = min(max((b * f - c * e) / den, 0.0), 1.0)
    else:
        s = 0.0
    t = (b * s + f) / e
    if t < 0:
        t, s = 0.0, min(max(-c / a, 0.0), 1.0)
    elif t > 1:
        t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    dist = float(np.linalg.norm(p1 + d1 * s - (q1 + d2 * t)))
    return s, t, dist


class Wires:
    """Thin wires with radius, split at junctions and discretised."""

    def __init__(self):
        self.raw = []           # (p1, p2, radius, tag)
        self.encase = {}        # raw index -> concrete shell (see `encased`)
        self.nodes = None
        self.segs = None

    @classmethod
    def from_items(cls, items, conductor_radius=0.005):
        """Build from the item list of the numerical page (grid, rod, ring,
        rectangle, conductor).  Fences are not part of a lightning electrode
        and are rejected."""
        from . import bem
        net = bem.Network(bem.SoilModel(100.0), 1.0)
        spec = dict(rho1=100.0, items=[], conductor_radius=conductor_radius)
        for it in items or []:
            if it.get("kind") == "fence":
                raise ValueError("Fences are not part of the lightning model; "
                                 "remove them for the frequency response.")
            spec["items"].append(it)
        net = bem.build_network(spec)
        w = cls()
        for i, (a, b, rad, tag, *_) in enumerate(net.raw):
            w.raw.append((np.array(a, float), np.array(b, float), float(rad), tag))
            if i in net.encase:
                w.encase[len(w.raw) - 1] = dict(net.encase[i])
        return w

    def add(self, p1, p2, radius, tag="", concrete=None):
        """Add a wire.  `concrete` = dict(radius=r_c, rho=ρ_c, eps_r=ε_c)
        encases it in a coaxial concrete shell (a foundation bar)."""
        self.raw.append((np.array(p1, float), np.array(p2, float), float(radius), tag))
        if concrete:
            self.encase[len(self.raw) - 1] = dict(concrete)
        return self

    def discretise(self, seg_len: float, tol: float = 1e-6, z_cuts=()):
        """Split every wire where another wire meets or crosses it, and where
        it crosses a soil interface (depths `z_cuts`), then into segments no
        longer than seg_len, and number the nodes."""
        raw = self.raw
        cuts = [[0.0, 1.0] for _ in raw]
        for i, (a1, a2, _, _) in enumerate(raw):
            for zc in z_cuts:
                if (a1[2] - zc) * (a2[2] - zc) < 0:
                    cuts[i].append((zc - a1[2]) / (a2[2] - a1[2]))
        for i, (a1, a2, r1, _) in enumerate(raw):
            for j, (b1, b2, r2, _) in enumerate(raw):
                if j <= i:
                    continue
                s, t, d = _closest_params(a1, a2, b1, b2)
                if d < max(tol, 1e-3 * min(r1, r2)):
                    cuts[i].append(s)
                    cuts[j].append(t)
        segs, keys, nodes = [], {}, []

        def node(p):
            k = tuple(np.round(p / tol).astype(np.int64))
            if k not in keys:
                keys[k] = len(nodes)
                nodes.append(p.copy())
            return keys[k]

        shell = []
        for i, (a, b, rad, tag) in enumerate(raw):
            enc = self.encase.get(i)
            cs = sorted(set(min(max(c, 0.0), 1.0) for c in cuts[i]))
            merged = [cs[0]]
            L = float(np.linalg.norm(b - a))
            for c in cs[1:]:
                if (c - merged[-1]) * L > 10 * tol:
                    merged.append(c)
            if merged[-1] < 1.0:
                merged[-1] = 1.0
            for t0, t1 in zip(merged[:-1], merged[1:]):
                q1, q2 = a + (b - a) * t0, a + (b - a) * t1
                Lq = float(np.linalg.norm(q2 - q1))
                sl = max(seg_len, 1.5 * float(enc["radius"])) if enc else seg_len
                n = max(1, int(math.ceil(Lq / sl - 1e-9)))
                prev = node(q1)
                for k in range(n):
                    pa = q1 + (q2 - q1) * k / n
                    pb = q1 + (q2 - q1) * (k + 1) / n
                    nb = node(pb)
                    if enc:
                        rc = max(float(enc["radius"]), rad * 1.0001)
                        segs.append((prev, nb, pa, pb, rc, tag))
                        shell.append((rad, math.log(rc / rad), float(enc["rho"]),
                                      float(enc.get("eps_r", 10.0))))
                    else:
                        segs.append((prev, nb, pa, pb, rad, tag))
                        shell.append((rad, 0.0, 1.0, 1.0))
                    prev = nb
        self.nodes = np.array(nodes)
        self.segs = segs
        self.na = np.array([s[0] for s in segs])
        self.nb = np.array([s[1] for s in segs])
        self.p1 = np.array([s[2] for s in segs])
        self.p2 = np.array([s[3] for s in segs])
        self.rad = np.array([s[4] for s in segs])          # radius seen by the soil
        sh = np.array(shell, float).reshape(-1, 4)
        self.rad_m = sh[:, 0]                              # metal radius
        self.sh_ln = sh[:, 1]                              # ln(r_c/a), 0 if bare
        self.sh_rho = sh[:, 2]
        self.sh_eps = sh[:, 3]
        self.L = np.linalg.norm(self.p2 - self.p1, axis=1)
        self.t = (self.p2 - self.p1) / self.L[:, None]
        self.mid = 0.5 * (self.p1 + self.p2)
        return len(segs)

    def nearest_node(self, p):
        p = np.asarray(p, float)
        return int(np.argmin(np.linalg.norm(self.nodes - p[None, :], axis=1)))

    @property
    def extent(self):
        pts = np.vstack([self.p1, self.p2])
        return float(np.linalg.norm(pts.max(0) - pts.min(0)))


# ---------------------------------------------------------------------------
# Integrals
# ---------------------------------------------------------------------------

def _line_integral(P, a, b, rmin):
    """∫ dl / |P - r(l)| over the straight segment a→b for points P (M,3),
    with the perpendicular distance floored at rmin (thin-wire kernel)."""
    d = b - a
    L = float(np.linalg.norm(d))
    u = d / L
    w = P - a[None, :]
    s = w @ u
    perp = np.sqrt(np.maximum(np.einsum("ij,ij->i", w, w) - s * s, 0.0))
    rho = np.maximum(perp, rmin)
    return np.arcsinh((L - s) / rho) + np.arcsinh(s / rho)


def _self_static(L, a):
    """∫∫ dl dl' / sqrt((l-l')² + a²) over one segment of length L."""
    return 2.0 * (L * math.asinh(L / a) - math.sqrt(L * L + a * a) + a)


class Model:
    """Thin-wire electrode in a lossy half-space."""

    def __init__(self, wires: Wires, soil: Soil, metal: str = "copper",
                 n_outer: int = 6, n_dyn: int = 4, air_image: bool = True,
                 a_image: str = "sommerfeld"):
        self.w = wires
        self.soil = soil
        self.metal = metal
        self.n_outer = n_outer
        self.n_dyn = n_dyn
        self.air_image = air_image
        # "sommerfeld" (default): images plus the Sommerfeld corrections of
        # horizontal currents and of charges; "quasistatic": images only;
        # "none"/"full": no image / the image K for the vector potential of
        # every current (kept for the comparisons of the tutorial)
        self.a_image = a_image
        self._static()

    # -- frequency-independent part ---------------------------------------
    def _static(self):
        w = self.w
        N = len(w.L)
        to, wo = _gauss(self.n_outer)
        Sd = np.zeros((N, N))
        Si = np.zeros((N, N))
        # field points on every segment (outer quadrature)
        F = (w.p1[:, None, :] + (w.p2 - w.p1)[:, None, :] * to[None, :, None])
        Fflat = F.reshape(-1, 3)
        mirror = np.array([1.0, 1.0, -1.0])
        for j in range(N):
            a, b, r = w.p1[j], w.p2[j], w.rad[j]
            val = _line_integral(Fflat, a, b, r).reshape(N, -1)
            Sd[:, j] = (val @ wo) * w.L
            vali = _line_integral(Fflat, a * mirror, b * mirror, r).reshape(N, -1)
            Si[:, j] = (vali @ wo) * w.L
            Sd[j, j] = _self_static(w.L[j], r)
        self.Sd = 0.5 * (Sd + Sd.T)          # symmetrise (Galerkin)
        self.Si = 0.5 * (Si + Si.T)
        # direction products: direct, mirrored image (horizontal, vertical)
        t = w.t
        self.Td = t @ t.T
        self.Th = t[:, :2] @ t[:, :2].T
        self.Tv = -np.outer(t[:, 2], t[:, 2])        # t_k · mirrored(t_j), z part
        # distances for the retarded (dynamic) part: segment mid-points for
        # far pairs, Gauss points for pairs closer than a few segment lengths
        mid = w.mid
        midi = mid * mirror
        LL = np.outer(w.L, w.L)
        dm = mid[:, None, :] - mid[None, :, :]
        self.Rm = np.sqrt(np.sum(dm * dm, axis=-1) + w.rad[None, :] ** 2)
        dmi = mid[:, None, :] - midi[None, :, :]
        self.Rmi = np.sqrt(np.sum(dmi * dmi, axis=-1) + w.rad[None, :] ** 2)
        self.LL = LL
        reach = 4.0 * np.maximum(w.L[:, None], w.L[None, :])
        near = (self.Rm < reach) | (self.Rmi < reach)
        I, J = np.nonzero(near)
        self.near = (I, J)
        tq, wq = _gauss(self.n_dyn)
        Q = (w.p1[:, None, :] + (w.p2 - w.p1)[:, None, :] * tq[None, :, None])
        Qi = Q * mirror
        self.Q = Q
        dd = Q[I][:, :, None, :] - Q[J][:, None, :, :]
        self.Rd = np.sqrt(np.sum(dd * dd, axis=-1) + (w.rad[J][:, None, None] ** 2))
        di = Q[I][:, :, None, :] - Qi[J][:, None, :, :]
        self.Ri = np.sqrt(np.sum(di * di, axis=-1) + (w.rad[J][:, None, None] ** 2))
        self.Wq = (wq[:, None] * wq[None, :])[None, :, :] * LL[I, J][:, None, None]
        # node incidence
        Nn = len(w.nodes)
        self.Nn = Nn
        self.N = N
        if getattr(self.soil, "N", 1) > 1:
            self._layered_setup()

    def _dyn(self, gamma):
        """∫∫ (e^{-γR} - 1)/R for direct and image pairs."""
        def f(R):
            x = gamma * R
            # (e^{-x} - 1)/R, stable for small x
            small = np.abs(x) < 1e-4
            out = np.where(small, -gamma * (1 - x / 2 + x * x / 6),
                           np.expm1(-x) / np.where(small, 1.0, R))
            return out
        I, J = self.near
        Dd = f(self.Rm) * self.LL
        Di = f(self.Rmi) * self.LL
        Dd[I, J] = np.sum(f(self.Rd) * self.Wq, axis=(1, 2))
        Di[I, J] = np.sum(f(self.Ri) * self.Wq, axis=(1, 2))
        return Dd, Di

    # -- Sommerfeld corrections ---------------------------------------------
    def _pair_geometry(self):
        """Horizontal distance and depth sum: (mid-points N×N, near pairs
        at the Gauss points)."""
        if getattr(self, "_geo", None) is None:
            w = self.w
            zfloor = 2 * w.rad.max()
            m = w.mid
            rho_m = np.hypot(m[:, None, 0] - m[None, :, 0], m[:, None, 1] - m[None, :, 1])
            Z_m = np.maximum(m[:, None, 2] + m[None, :, 2], zfloor)
            I, J = self.near
            Q = self.Q
            rho_q = np.hypot(Q[I][:, :, None, 0] - Q[J][:, None, :, 0],
                             Q[I][:, :, None, 1] - Q[J][:, None, :, 1])
            Z_q = np.maximum(Q[I][:, :, None, 2] + Q[J][:, None, :, 2], zfloor)
            self._geo = (rho_m, Z_m, rho_q, Z_q)
        return self._geo

    @staticmethod
    def _lambda_rule(k0, g1, rmax, zmin):
        """Quadrature nodes and weights in λ for the Sommerfeld integrals:
        [0, k0] with the square-root end point removed, then panels short
        enough for J0(λ ρ_max) and fine near |γ1|, up to where e^{-λ Z_min}
        has died away."""
        tg, wg = _gauss(16)
        lam, wl = [], []
        if k0 > 0:
            lam.append(k0 * (1 - tg * tg))
            wl.append(wg * 2 * k0 * tg)
        ag = abs(g1)
        lam_max = max(40.0 / zmin, 12.0 * ag)
        step = min(math.pi / max(rmax, 1e-6), lam_max / 40.0)
        edges = [k0]
        x = k0
        while x < lam_max:
            dx = step
            if x < 3 * ag + 1.0 / zmin:
                dx = min(dx, 0.2 * ag + 0.05 / zmin)
            dx = min(dx, lam_max - x)
            x += dx
            edges.append(x)
        e = np.array(edges)
        lo, hi = e[:-1], e[1:]
        lam.append((lo[:, None] + (hi - lo)[:, None] * tg[None, :]).ravel())
        wl.append(((hi - lo)[:, None] * wg[None, :]).ravel())
        return np.concatenate(lam), np.concatenate(wl)

    def _sommerfeld(self, f, k1, K):
        """Pair integrals of the two Sommerfeld corrections to the image
        model, both from the mixed-potential formulation C of Michalski and
        Zheng for a half-space (source and field in the soil):

        TE (vector potential of horizontal currents)
            S_A = ∫ Γ_h e^{-u1 Z} J0(λρ) λ/u1 dλ,  Γ_h = (u1 - u0)/(u1 + u0)
        scalar potential of charges, beyond the image K
            S_φ = ∫ (R_φ - K) e^{-u1 Z} J0(λρ) λ/u1 dλ,
            R_φ = (u1² Γ_e - γ1² Γ_h)/λ²,  Γ_e = (κ1 u0 - κ0 u1)/(κ1 u0 + κ0 u1)

        with u_i = √(λ² + γ_i²).  Both vanish at low frequency; together they
        are what the quasi-static images leave out."""
        rho_m, Z_m, rho_q, Z_q = self._pair_geometry()
        om = 2 * math.pi * f
        g1sq = 1j * om * MU0 * k1
        g1 = cmath.sqrt(g1sq)
        k0 = om * math.sqrt(MU0 * EPS0)
        kap0 = 1j * om * EPS0
        rmax = float(rho_m.max()) + 1e-9
        zmin = float(min(Z_m.min(), Z_q.min() if Z_q.size else Z_m.min()))
        zmax = float(max(Z_m.max(), Z_q.max() if Z_q.size else Z_m.max()))
        lam, wl = self._lambda_rule(k0, g1, rmax, zmin)
        u1 = np.sqrt(lam * lam + g1sq)
        d0 = lam * lam - k0 * k0
        u0 = np.where(d0 >= 0, np.sqrt(np.abs(d0)) + 0j, 1j * np.sqrt(np.abs(d0)))
        gh = (u1 - u0) / (u1 + u0)
        ge = (k1 * u0 - kap0 * u1) / (k1 * u0 + kap0 * u1)
        rphi = (u1 * u1 * ge - g1sq * gh) / (lam * lam) - K
        from .layered import j0
        rg = np.unique(np.concatenate([np.linspace(0, rmax, 300),
                                       np.geomspace(1e-3, rmax, 120)]))
        J0 = j0(np.outer(rg, lam))
        zs = np.unique(np.round(np.concatenate([Z_m.ravel(), Z_q.ravel()]), 5))
        if len(zs) > 40:
            zs = np.unique(np.concatenate([np.geomspace(zmin, zmax, 36), [zmin, zmax]]))
        wA = gh * lam / u1 * wl
        wP = rphi * lam / u1 * wl
        E = np.exp(-np.outer(zs, u1))
        TA = J0 @ (wA[None, :] * E).T
        TP = J0 @ (wP[None, :] * E).T
        I, J = self.near
        res = []
        for T in (TA, TP):
            M = self._interp2(rg, zs, T, rho_m, Z_m) * self.LL
            if len(I):
                M[I, J] = np.sum(self._interp2(rg, zs, T, rho_q, Z_q) * self.Wq, axis=(1, 2))
            res.append(M)
        hz = np.hypot(self.w.t[:, 0], self.w.t[:, 1]) > 1e-9
        res[0] = res[0] * np.outer(hz, hz)
        return res[0], res[1]

    @staticmethod
    def _interp2(rg, zs, T, rho, Z):
        """Bilinear interpolation of a table T(r, z) (complex)."""
        ir = np.clip(np.searchsorted(rg, rho) - 1, 0, len(rg) - 2)
        fr = (rho - rg[ir]) / (rg[ir + 1] - rg[ir])
        if len(zs) == 1:
            return T[ir, 0] * (1 - fr) + T[ir + 1, 0] * fr
        iz = np.clip(np.searchsorted(zs, Z) - 1, 0, len(zs) - 2)
        fz = np.clip((Z - zs[iz]) / (zs[iz + 1] - zs[iz]), 0.0, 1.0)
        return (T[ir, iz] * (1 - fr) * (1 - fz) + T[ir + 1, iz] * fr * (1 - fz)
                + T[ir, iz + 1] * (1 - fr) * fz + T[ir + 1, iz + 1] * fr * fz)

    def _zint(self, f):
        """Internal impedance per metre of a round solid conductor."""
        rho_m = METAL_RHO.get(self.metal, METAL_RHO["copper"])
        mu_r = 1.0 if self.metal in ("copper", "aluminium") else 200.0
        a = self.w.rad_m
        rdc = rho_m / (math.pi * a * a)
        if f <= 0:
            return rdc + 0j
        delta = math.sqrt(2 * rho_m / (2 * math.pi * f * MU0 * mu_r))
        zs = (1 + 1j) * rho_m / (2 * math.pi * a * delta)
        lin = rdc + 1j * 2 * math.pi * f * MU0 * mu_r / (8 * math.pi)
        return np.where(a > 2 * delta, np.maximum(zs.real, rdc) + 1j * zs.imag, lin)

    # -- one frequency -----------------------------------------------------
    # -- layered soil ----------------------------------------------------------
    # In a stratified soil the Green's functions are written as
    #
    #     G = direct term + images close to the electrode + correction.
    #
    # The direct term and the images near the electrode (the air image, the
    # first reflections in nearby interfaces) are integrated exactly, like the
    # direct term of the uniform model: the scalar potential of a charge has
    # the quasi-static image series of `trace_images`, each image retarded
    # with the propagation constant of the field layer; vertical currents
    # have the same images in the vector potential, horizontal ones none.
    # The correction is the exact (Sommerfeld) solution for the layered
    # half-space minus those near images.  It is smooth -- the far images
    # and the frequency dependence of the reflection coefficients -- so it
    # is tabulated per frequency on a grid in (ρ, z, z') and interpolated.
    #
    # The exact solution is that of the mixed-potential formulation C of
    # Michalski and Zheng (1990): with the transmission-line Green's
    # functions V^e, V^h (voltage, shunt current source) and I^e (current,
    # series voltage source) of the TM and TE lines of the stack (air, layer
    # 1 … N), in normalised form (spatial G = ∫ g̃ J0(λρ) λ dλ):
    #
    #     scalar potential   g̃_φ  = 2 κ' (V^e − V^h)/λ²
    #     A, horizontal      g̃_Ah = 2 V^h/(jωμ0)
    #     A, vertical        g̃_Av = 2 I^e/κ'
    #
    # (κ' of the source layer).  Each reduces to e^{-u|z−z'|}/u in a uniform
    # medium.  This is the model of Arnautovski-Toseva and Grcev (2004,
    # 2011) for wires in two-layer soil, for any number of layers.

    def _layered_setup(self):
        w = self.w
        soil = self.soil
        self.lay = np.array([soil.layer_of(z) for z in w.mid[:, 2]])
        self.layers_present = sorted(set(self.lay.tolist()))
        self.D_near = max(1.0, 3.0 * float(w.L.max()))
        self._nearblk = {}
        self.tz = w.t[:, 2]
        self.zr = {}
        for m in self.layers_present:
            idx = np.where(self.lay == m)[0]
            z = np.concatenate([w.p1[idx, 2], w.p2[idx, 2]])
            self.zr[m] = (idx, float(z.min()), float(z.max()))
        # depth nodes of the correction tables, per layer
        tq, _ = _gauss(self.n_dyn)
        Qz = (w.p1[:, None, 2] + (w.p2 - w.p1)[:, None, 2] * tq[None, :])
        self.znodes = {}
        for m in self.layers_present:
            idx = self.zr[m][0]
            zz = np.unique(np.round(np.concatenate([w.mid[idx, 2], Qz[idx].ravel()]), 4))
            if len(zz) > 16:
                n = int(min(40, max(12, math.ceil((zz[-1] - zz[0]) / 0.25) + 1)))
                zz = np.linspace(zz[0], zz[-1], n)
            self.znodes[m] = zz
        mid = w.mid
        self.rho_m = np.hypot(mid[:, None, 0] - mid[None, :, 0], mid[:, None, 1] - mid[None, :, 1])
        I, J = self.near
        Q = self.Q
        self.rho_q = np.hypot(Q[I][:, :, None, 0] - Q[J][:, None, :, 0],
                              Q[I][:, :, None, 1] - Q[J][:, None, :, 1])
        self.zq_f = np.broadcast_to(Q[I][:, :, None, 2], self.rho_q.shape)
        self.zq_s = np.broadcast_to(Q[J][:, None, :, 2], self.rho_q.shape)

    def _u_range(self, n, m, s):
        _, f0, f1 = self.zr[n]
        _, s0, s1 = self.zr[m]
        return (f0 - s1, f1 - s0) if s > 0 else (f0 + s0, f1 + s1)

    def _near_block(self, n, m, s, h):
        """Static Galerkin integral and dynamic geometry of one image."""
        key = (n, m, int(s), int(round(h * 1e6)))
        blk = self._nearblk.get(key)
        if blk is not None:
            return blk
        w = self.w
        rows = self.zr[n][0]
        cols = self.zr[m][0]
        to, wo = _gauss(self.n_outer)
        F = (w.p1[rows][:, None, :] + (w.p2 - w.p1)[rows][:, None, :] * to[None, :, None])
        Ff = F.reshape(-1, 3)
        S = np.zeros((len(rows), len(cols)))

        def tr(P):
            Q = np.array(P, float)
            Q[..., 2] = s * Q[..., 2] + h
            return Q
        for jj, j in enumerate(cols):
            a, b = tr(w.p1[j]), tr(w.p2[j])
            val = _line_integral(Ff, a, b, w.rad[j]).reshape(len(rows), -1)
            S[:, jj] = (val @ wo) * w.L[rows]
        mid_r = w.mid[rows]
        mid_c = tr(w.mid[cols])
        dm = mid_r[:, None, :] - mid_c[None, :, :]
        Rm = np.sqrt(np.sum(dm * dm, axis=-1) + w.rad[cols][None, :] ** 2)
        reach = 4.0 * np.maximum(w.L[rows][:, None], w.L[cols][None, :])
        I, J = np.nonzero(Rm < reach)
        tq, wq = _gauss(self.n_dyn)
        Q = w.p1[:, None, :] + (w.p2 - w.p1)[:, None, :] * tq[None, :, None]
        Qr, Qc = Q[rows], tr(Q[cols])
        dd = Qr[I][:, :, None, :] - Qc[J][:, None, :, :]
        Rd = np.sqrt(np.sum(dd * dd, axis=-1) + w.rad[cols][J][:, None, None] ** 2)
        LL = np.outer(w.L[rows], w.L[cols])
        Wq = (wq[:, None] * wq[None, :])[None, :, :] * LL[I, J][:, None, None]
        blk = dict(S=S, Rm=Rm, I=I, J=J, Rd=Rd, Wq=Wq, LL=LL)
        self._nearblk[key] = blk
        return blk

    @staticmethod
    def _dyn_of(blk, gamma):
        def fdyn(R):
            x = gamma * R
            small = np.abs(x) < 1e-4
            return np.where(small, -gamma * (1 - x / 2 + x * x / 6),
                            np.expm1(-x) / np.where(small, 1.0, R))
        D = fdyn(blk["Rm"]) * blk["LL"]
        if len(blk["I"]):
            D[blk["I"], blk["J"]] = np.sum(fdyn(blk["Rd"]) * blk["Wq"], axis=(1, 2))
        return D

    # transmission-line Green's functions of the stack, vectorised over λ
    def _tl_stack(self, lam, kap, f):
        soil = self.soil
        om = 2 * math.pi * f
        k0 = om * math.sqrt(MU0 * EPS0)
        kap0 = 1j * om * EPS0
        Nl = soil.N
        u = np.array([np.sqrt(lam * lam + 1j * om * MU0 * k) for k in kap])
        d0 = lam * lam - k0 * k0
        ua = np.where(d0 >= 0, np.sqrt(np.abs(d0)) + 0j, 1j * np.sqrt(np.abs(d0)))
        jwm = 1j * om * MU0
        Ze = u / kap[:, None]
        Zh = jwm / u
        Zea = ua / kap0
        Zha = jwm / ua
        d = list(soil.h) + [np.inf]
        tops = [0.0] + list(soil.depths)
        out = {}
        for key, Z, Za in (("e", Ze, Zea), ("h", Zh, Zha)):
            Gu = np.zeros_like(Z)
            Gd = np.zeros_like(Z)
            Gu[0] = (Za - Z[0]) / (Za + Z[0])
            for i in range(1, Nl):
                r = (Z[i - 1] - Z[i]) / (Z[i - 1] + Z[i])
                e = np.exp(-2 * u[i - 1] * d[i - 1])
                Gu[i] = (r + Gu[i - 1] * e) / (1 + r * Gu[i - 1] * e)
            for i in range(Nl - 2, -1, -1):
                r = (Z[i + 1] - Z[i]) / (Z[i + 1] + Z[i])
                e = np.exp(-2 * u[i + 1] * d[i + 1]) if np.isfinite(d[i + 1]) else 0.0
                Gd[i] = (r + Gd[i + 1] * e) / (1 + r * Gd[i + 1] * e)
            out[key] = (Z, Gu, Gd)
        return u, out, d, tops

    def _tl_kernel(self, u, Z, Gu, Gd, d, tops, n, m, z, zp, current=False,
                   direct=False):
        """V(z|z') (or I(z|z') when `current`) on the TL of the stack:
        source in layer m at depths zp, field in layer n at depths z.
        Returns (nλ, nz, nzp).  The direct term of n == m is included only
        when `direct`."""
        sg = -1.0 if current else 1.0
        um = u[m][:, None, None]
        dm = d[m]
        zt = tops[m]
        gu = sg * Gu[m][:, None, None]
        gd = sg * Gd[m][:, None, None]
        pref = (0.5 / Z[m] if current else 0.5 * Z[m])[:, None, None]

        def same(zf):
            zf = np.asarray(zf, float)[None, :, None]
            zs = np.asarray(zp, float)[None, None, :]
            acc = gu * np.exp(-um * (zf + zs - 2 * zt))
            if np.isfinite(dm):
                zb = zt + dm
                D = 1 - gu * gd * np.exp(-2 * um * dm)
                acc = acc + gd * np.exp(-um * (2 * zb - zf - zs))
                acc = acc + gu * gd * (np.exp(-um * (2 * dm + zf - zs))
                                       + np.exp(-um * (2 * dm - zf + zs)))
                acc = acc / D
            return acc
        if n == m:
            V = same(z)
            if direct:
                V = V + np.exp(-um * np.abs(np.asarray(z)[None, :, None]
                                            - np.asarray(zp)[None, None, :]))
            return pref * V
        if n > m:
            zb = tops[m] + dm
            Vb = pref * (same([zb]) + np.exp(-um * np.abs(zb - np.asarray(zp)[None, None, :])))
            for k in range(m + 1, n + 1):
                uk = u[k][:, None, None]
                g = sg * Gd[k][:, None, None]
                ztk = tops[k]
                if k == n:
                    zf = np.asarray(z, float)[None, :, None]
                    if np.isfinite(d[k]):
                        zbk = ztk + d[k]
                        return Vb * (np.exp(-uk * (zf - ztk))
                                     + g * np.exp(-uk * (2 * zbk - ztk - zf))) \
                            / (1 + g * np.exp(-2 * uk * d[k]))
                    return Vb * np.exp(-uk * (zf - ztk))
                Vb = Vb * (1 + g) * np.exp(-uk * d[k]) / (1 + g * np.exp(-2 * uk * d[k]))
        # n < m: field above the source
        Vt = pref * (same([zt]) + np.exp(-um * np.abs(np.asarray(zp)[None, None, :] - zt)))
        for k in range(m - 1, n - 1, -1):
            uk = u[k][:, None, None]
            g = sg * Gu[k][:, None, None]
            ztk = tops[k]
            zbk = ztk + d[k]
            if k == n:
                zf = np.asarray(z, float)[None, :, None]
                return Vt * (np.exp(-uk * (zbk - zf))
                             + g * np.exp(-uk * (zf + zbk - 2 * ztk))) \
                    / (1 + g * np.exp(-2 * uk * d[k]))
            Vt = Vt * (1 + g) * np.exp(-uk * d[k]) / (1 + g * np.exp(-2 * uk * d[k]))

    def _tl_kernels(self, u, tl, d, tops, n, m, z, zp):
        """V^e, V^h and I^e of `_tl_kernel` at once, sharing the
        exponentials (same-layer pairs, the bulk of the work)."""
        if n != m:
            return (self._tl_kernel(u, *tl["e"], d, tops, n, m, z, zp),
                    self._tl_kernel(u, *tl["h"], d, tops, n, m, z, zp),
                    self._tl_kernel(u, *tl["e"], d, tops, n, m, z, zp, current=True))
        um = u[m][:, None, None]
        dm = d[m]
        zt = tops[m]
        zf = np.asarray(z, float)[None, :, None]
        zs = np.asarray(zp, float)[None, None, :]
        e1 = np.exp(-um * (zf + zs - 2 * zt))
        if np.isfinite(dm):
            zb = zt + dm
            e2 = np.exp(-um * (2 * zb - zf - zs))
            e34 = np.exp(-um * (2 * dm + zf - zs)) + np.exp(-um * (2 * dm - zf + zs))
            e0 = np.exp(-2 * um * dm)
        out = []
        for key, cur in (("e", False), ("h", False), ("e", True)):
            Z, Gu, Gd = tl[key]
            sg = -1.0 if cur else 1.0
            gu = sg * Gu[m][:, None, None]
            acc = gu * e1
            if np.isfinite(dm):
                gd = sg * Gd[m][:, None, None]
                acc = (acc + gd * e2 + gu * gd * e34) / (1 - gu * gd * e0)
            pref = (0.5 / Z[m] if cur else 0.5 * Z[m])[:, None, None]
            out.append(pref * acc)
        return out

    @staticmethod
    def _interp3(rg, za, zb, T, rho, Z, Zp):
        """Trilinear interpolation of T(ρ, z, z') (complex)."""
        ir = np.clip(np.searchsorted(rg, rho) - 1, 0, len(rg) - 2)
        fr = np.clip((rho - rg[ir]) / (rg[ir + 1] - rg[ir]), 0.0, 1.0)

        def axis(g, x):
            if len(g) == 1:
                return np.zeros(np.shape(x), int), np.zeros(np.shape(x)), 0
            i = np.clip(np.searchsorted(g, x) - 1, 0, len(g) - 2)
            return i, np.clip((x - g[i]) / (g[i + 1] - g[i]), 0.0, 1.0), 1
        ia, fa, da = axis(za, Z)
        ib, fb, db = axis(zb, Zp)
        out = 0.0
        for dr, wr in ((0, 1 - fr), (1, fr)):
            for dA, wA in ((0, 1 - fa), (da, fa)):
                if da == 0 and dA == 0 and wA is fa:
                    continue
                for dB, wB in ((0, 1 - fb), (db, fb)):
                    if db == 0 and dB == 0 and wB is fb:
                        continue
                    wgt = wr * (wA if da else 1.0) * (wB if db else 1.0)
                    out = out + T[ir + dr, ia + dA, ib + dB] * wgt
        return out

    @staticmethod
    def _lambda_layered(k0, gmin, gmax, rmax, zmin):
        """λ nodes for the layered correction: [0, k0] with the branch point
        removed; geometric panels through the region λ ~ |γ_i| where the
        reflection coefficients change; then panels short enough for
        J0(λρ_max) up to where e^{−λ z_min} and the γ²/λ² tails have died."""
        tg, wg = _gauss(8)
        lam, wl = [], []
        if k0 > 0:
            t16, w16 = _gauss(16)
            lam.append(k0 * (1 - t16 * t16))
            wl.append(w16 * 2 * k0 * t16)
        lam_max = max(40.0 / zmin, 40.0 * gmax)
        a = max(k0, 1e-3 * gmin, 1e-9)
        b = max(40.0 * gmax, a * 1.01)
        e = [k0]
        if a > k0:
            e.append(a)
        nb = max(2, int(math.ceil(math.log(b / a) / math.log(1.35))))
        e.extend(np.geomspace(a, b, nb + 1)[1:].tolist())
        step = min(2 * math.pi / max(rmax, 1e-6), 0.5 / zmin + 0.0, lam_max / 40.0)
        x = e[-1]
        while x < lam_max:
            x = min(x + max(step, 0.1 * x if rmax < 1e-6 else step), lam_max)
            e.append(x)
        e = np.array(e)
        lo, hi = e[:-1], e[1:]
        keep = hi > lo
        lo, hi = lo[keep], hi[keep]
        lam.append((lo[:, None] + (hi - lo)[:, None] * tg[None, :]).ravel())
        wl.append(((hi - lo)[:, None] * wg[None, :]).ravel())
        return np.concatenate(lam), np.concatenate(wl)

    def _layered_correction(self, f, kap, K, near_imgs):
        """Tables of the three corrections (φ, A_h, A_v) per layer pair and
        their values at every segment pair (× L_k L_j)."""
        w = self.w
        om = 2 * math.pi * f
        k0 = om * math.sqrt(MU0 * EPS0)
        gmax = max(abs(cmath.sqrt(1j * om * MU0 * k)) for k in kap)
        rmax = float(self.rho_m.max()) + 1e-9
        zseg = w.mid[:, 2]
        zmin = max(0.05, min(2 * float(zseg.min()), self.D_near))
        gmin = min(abs(cmath.sqrt(1j * om * MU0 * k)) for k in kap)
        lam, wl = self._lambda_layered(k0, gmin, gmax, rmax, zmin)
        u, tl, d, tops = self._tl_stack(lam, kap, f)
        from .layered import j0
        rg = np.unique(np.concatenate([np.linspace(0, rmax, 160),
                                       np.geomspace(1e-3, rmax, 60)])) if rmax > 1e-6 \
            else np.array([0.0, 1e-3])
        J0 = j0(np.outer(rg, lam)) * (wl * lam)[None, :]
        N = self.N
        Cphi = np.zeros((N, N), complex)
        Cah = np.zeros((N, N), complex)
        Cav = np.zeros((N, N), complex)
        I, J = self.near
        jwm = 1j * om * MU0
        for m in self.layers_present:
            cols = self.zr[m][0]
            zp = self.znodes[m]
            for n in self.layers_present:
                rows = self.zr[n][0]
                z = self.znodes[n]
                Ve, Vh, Ie = self._tl_kernels(u, tl, d, tops, n, m, z, zp)
                lam3 = lam[:, None, None]
                gphi = 2 * kap[m] * (Ve - Vh) / lam3 ** 2
                gah = 2 * Vh / jwm
                gav = 2 * Ie / kap[m]
                un = u[n][:, None, None]
                Zf = z[None, :, None]
                Zs = zp[None, None, :]
                fa = kap[n] / kap[m]
                for s, h, a in near_imgs.get((n, m), []):
                    e = np.exp(-un * np.abs(Zf - s * Zs - h)) / un
                    gphi = gphi - a * e
                    gav = gav - a * s * fa * e
                if n != m:
                    gah = gah - np.exp(-un * np.abs(Zf - Zs)) / un
                nz, nzp = len(z), len(zp)
                tabs = []
                for g in (gphi, gah, gav):
                    tabs.append((J0 @ g.reshape(len(lam), -1)).reshape(len(rg), nz, nzp))
                blk = np.ix_(rows, cols)
                LL = np.outer(w.L[rows], w.L[cols])
                rr = self.rho_m[blk]
                Zr = np.broadcast_to(zseg[rows][:, None], rr.shape)
                Zc = np.broadcast_to(zseg[cols][None, :], rr.shape)
                inb = np.isin(I, rows) & np.isin(J, cols)
                for C, T in zip((Cphi, Cah, Cav), tabs):
                    C[blk] = self._interp3(rg, z, zp, T, rr, Zr, Zc) * LL
                    if inb.any():
                        C[I[inb], J[inb]] = np.sum(
                            self._interp3(rg, z, zp, T, self.rho_q[inb], self.zq_f[inb],
                                          self.zq_s[inb]) * self.Wq[inb], axis=(1, 2))
        return Cphi, Cah, Cav

    def _matrices_layered(self, f: float):
        w = self.w
        soil = self.soil
        if f <= 0:
            f = 1e-2            # the dc limit, through the same exact path
        om = 2 * math.pi * f
        kap = soil.kappas(f)
        k0 = 1j * om * EPS0
        K = (kap[0] - k0) / (kap[0] + k0) if self.air_image else 0.0
        gam = np.array([cmath.sqrt(1j * om * MU0 * k) for k in kap]) if f > 0 \
            else np.zeros(len(kap), complex)
        N = self.N
        G0 = np.array(self.Sd, complex)
        if f > 0:
            for n in self.layers_present:
                r = self.zr[n][0]
                G0[r, :] += self._dyn(gam[n])[0][r, :]
        Phi = np.zeros((N, N), complex)
        Av = np.zeros((N, N), complex)
        near_imgs = {}
        exact = self.a_image == "sommerfeld" and f > 0
        for m in self.layers_present:
            imgs = trace_images(soil.depths, kap, K, m, tol=1e-7)
            cols = self.zr[m][0]
            for n in self.layers_present:
                rows = self.zr[n][0]
                blk = np.ix_(rows, cols)
                sv, hv, av = imgs[n]
                fa = kap[n] / kap[m]
                d0 = (sv > 0) & (np.abs(hv) < 1e-9)
                a0 = complex(av[d0].sum()) if d0.any() else 0.0
                Phi[blk] += a0 * G0[blk]
                Av[blk] += a0 * fa * G0[blk]
                lst = []
                if n != m and a0 != 0:
                    lst.append((1, 0.0, a0))
                for sgn in (1, -1):
                    sel = (~d0) & (sv == sgn)
                    if not sel.any():
                        continue
                    hs, am = hv[sel], av[sel]
                    lo, hi = self._u_range(n, m, sgn)
                    dist = np.maximum(0.0, np.maximum(lo - hs, hs - hi))
                    near = dist < self.D_near if exact else np.ones(len(hs), bool)
                    for h, a in zip(hs[near], am[near]):
                        nb = self._near_block(n, m, sgn, float(h))
                        G = nb["S"] + (self._dyn_of(nb, gam[n]) if f > 0 else 0.0)
                        Phi[blk] += a * G
                        Av[blk] += a * sgn * fa * G
                        lst.append((sgn, float(h), a))
                near_imgs[(n, m)] = lst
        Ah = np.array(G0)
        if exact:
            Cphi, Cah, Cav = self._layered_correction(f, kap, K, near_imgs)
            Phi += Cphi
            Ah += Cah
            Av += Cav
        kap_src = kap[self.lay]
        ZT = Phi / (4 * math.pi * kap_src[None, :] * np.outer(w.L, w.L))
        ZT = 0.5 * (ZT + ZT.T)                    # Galerkin symmetry
        tz = self.tz
        ZL = (1j * om * MU0 / (4 * math.pi)) * (self.Th * Ah + np.outer(tz, tz) * Av)
        ZL[np.diag_indices_from(ZL)] += self._zint(f) * w.L
        return ZT, ZL

    def _shell(self, f):
        """Leakage impedance of the concrete shells, Ω (0 for bare wires):
        ln(r_c/a)/(2π κ_c L) with κ_c = 1/ρ_c + jωε_c."""
        w = self.w
        kc = 1.0 / w.sh_rho + 1j * 2 * math.pi * f * EPS0 * w.sh_eps
        return w.sh_ln / (2 * math.pi * kc * w.L)

    def matrices(self, f: float):
        if getattr(self.soil, "N", 1) > 1:
            ZT, ZL = self._matrices_layered(f)
        else:
            ZT, ZL = self._matrices_uniform(f)
        if np.any(self.w.sh_ln > 0):
            ZT[np.diag_indices_from(ZT)] += self._shell(f)
        return ZT, ZL

    def _matrices_uniform(self, f: float):
        w = self.w
        om = 2 * math.pi * f
        k1 = self.soil.kappa(f)
        k0 = 1j * om * EPS0
        K = (k1 - k0) / (k1 + k0) if self.air_image else 0.0
        gam = cmath.sqrt(1j * om * MU0 * k1) if f > 0 else 0.0
        if f > 0:
            Dd, Di = self._dyn(gam)
        else:
            Dd = Di = 0.0
        Gd = self.Sd + Dd
        Gi = self.Si + Di
        te = 0.0
        sp = 0.0
        if self.a_image == "sommerfeld" and f > 0:
            te, sp = self._sommerfeld(f, k1, K)
        ZT = (Gd + K * Gi + sp) / (4 * math.pi * k1 * np.outer(w.L, w.L))
        if self.a_image in ("none",):
            img = 0.0
        elif self.a_image == "full":
            img = K * (self.Th + self.Tv)
        else:                                   # quasi-static, formulation C
            img = K * self.Tv
        ZL = (1j * om * MU0 / (4 * math.pi)) * (self.Td * Gd + img * Gi + self.Th * te)
        ZL[np.diag_indices_from(ZL)] += self._zint(f) * w.L
        return ZT, ZL

    def solve(self, f: float, feed, I: complex = 1.0):
        """Solve at frequency f with current I injected at node `feed`.
        Returns (Z, V_nodes, IL, IT)."""
        w = self.w
        N, Nn = self.N, self.Nn
        ZT, ZL = self.matrices(f)
        n = Nn + 2 * N
        A = np.zeros((n, n), complex)
        b = np.zeros(n, complex)
        iV = np.arange(Nn)
        iL = Nn + np.arange(N)
        iT = Nn + N + np.arange(N)
        r1 = np.arange(N)
        # (1) average potential of segment = leakage potential
        A[r1, w.na] += 0.5
        A[r1, w.nb] += 0.5
        A[np.ix_(r1, iT)] -= ZT
        # (2) longitudinal drop
        r2 = N + np.arange(N)
        A[r2, w.na] += 1.0
        A[r2, w.nb] -= 1.0
        A[np.ix_(r2, iL)] -= ZL
        # (3) KCL at nodes
        r3 = 2 * N
        A[r3 + w.na, iL] += 1.0
        A[r3 + w.nb, iL] -= 1.0
        A[r3 + w.na, iT] += 0.5
        A[r3 + w.nb, iT] += 0.5
        b[r3 + feed] = I
        x = np.linalg.solve(A, b)
        V = x[:Nn]
        return V[feed] / I, V, x[iL], x[iT]


# ---------------------------------------------------------------------------
# Lightning current waveforms
# ---------------------------------------------------------------------------

# CIGRE TB 781 Figure 4.1: representative first- and subsequent-stroke
# currents (De Conti and Visacro, after the Mount San Salvatore medians).
# Sampled from the vector figure of the brochure, every 0.4 µs (first) and
# 0.1 µs (subsequent), in kA; extended beyond the plotted window by an
# exponential decay to the median time to half value.
def _tb781_samples():
    from . import tb781_waves
    return {"a": tb781_waves.FIRST, "b": tb781_waves.SUBSEQUENT}


def heidler(t, I0, eta, n, tau1, tau2):
    x = (np.maximum(t, 0.0) / tau1) ** n
    return I0 / eta * x / (1 + x) * np.exp(-np.maximum(t, 0.0) / tau2)


WAVEFORMS = {
    # Rachidi et al. (2001), used by Grcev (2009): Heidler functions,
    # times in µs.  The first stroke is scaled to Grcev's 30 kA peak.
    "first_heidler": dict(label="First stroke, Heidler (Grcev 2009): 30 kA, 8.4 µs to peak",
                          parts=[(28.0, 0.73, 2, 1.8, 95.0)], peak=30.0),
    "subsequent_heidler": dict(label="Subsequent stroke, Heidler (Grcev 2009): 12 kA, 0.8 µs to peak",
                               parts=[(10.7, 0.639, 2, 0.25, 2.5), (6.5, 0.867, 2, 2.1, 230.0)],
                               peak=None),
    "first_tb781": dict(label="First stroke, CIGRE TB 781 Fig. 4.1 (double peak, 31.1 kA)",
                        sampled="a", t50=75.0),
    "subsequent_tb781": dict(label="Subsequent stroke, CIGRE TB 781 Fig. 4.1 (11.8 kA)",
                             sampled="b", t50=32.0),
}


def waveform(name: str, t_us, peak_kA: float | None = None):
    """Current in kA at times t (µs)."""
    t = np.asarray(t_us, float)
    wf = WAVEFORMS[name]
    if "parts" in wf:
        i = sum(heidler(t, *p) for p in wf["parts"])
        if wf.get("peak"):
            tt = np.linspace(0, 100, 20001)
            pk = float(sum(heidler(tt, *p) for p in wf["parts"]).max())
            i = i * wf["peak"] / pk
    else:
        pts = np.array(_tb781_samples()[wf["sampled"]])
        ts, isamp = pts[:, 0], pts[:, 1]
        o = np.argsort(ts)
        ts, isamp = ts[o], isamp[o]
        ts[0] = 0.0
        i = np.interp(t, ts, isamp, left=0.0)
        # tail: exponential through the last sample, half the peak at t50
        tl, il = ts[-1], isamp[-1]
        ip = isamp.max()
        tau = (wf["t50"] - tl) / math.log(il / (0.5 * ip)) if il > 0.5 * ip else 50.0
        tail = t > tl
        i = np.where(tail, il * np.exp(-(t - tl) / tau), i)
    if peak_kA:
        i = i * peak_kA / float(np.max(i))
    return i


# ---------------------------------------------------------------------------
# Frequency sweep and time response
# ---------------------------------------------------------------------------

def default_seg_len(soil: Soil, f_max: float, extent: float):
    """Segment length: a fifth of the skin depth in the soil at f_max, and
    no more than 1 m, but not so short that the model has thousands of
    segments."""
    k = soil.kappa(f_max)
    gam = abs(cmath.sqrt(1j * 2 * math.pi * f_max * MU0 * k))
    return float(min(1.0, max(0.2 / gam, extent / 400.0, 0.05)))


def sweep(model: Model, feed: int, freqs):
    Z = np.array([model.solve(f, feed)[0] for f in freqs])
    return Z


def harmonic_impedance(items=None, wires: Wires | None = None, soil: Soil | None = None,
                       feed=None, f_min=100.0, f_max=10e6, n_f=41,
                       seg_len=None, metal="copper", **kw):
    """Harmonic impedance Z(jω) seen from the feed point."""
    if wires is None:
        wires = Wires.from_items(items)
    if seg_len is None:
        seg_len = default_seg_len(soil, f_max, _raw_extent(wires))
    total = sum(float(np.linalg.norm(b - a)) for a, b, *_ in wires.raw)
    seg_len = max(seg_len, total / float(kw.pop("max_segments", 800)))
    wires.discretise(seg_len, z_cuts=getattr(soil, "depths", []))
    model = Model(wires, soil, metal=metal, **kw)
    if feed is None:
        feed = 0
    elif not isinstance(feed, (int, np.integer)):
        feed = wires.nearest_node(feed)
    freqs = np.geomspace(f_min, f_max, n_f)
    R = model.solve(0.0, feed)[0].real
    Z = sweep(model, feed, freqs)
    return dict(f=freqs, Z=Z, R=R, segments=model.N, nodes=model.Nn,
                feed=feed, model=model)


def _raw_extent(w: Wires):
    pts = np.vstack([np.vstack([a, b]) for a, b, *_ in w.raw])
    return float(np.linalg.norm(pts.max(0) - pts.min(0)))


def ionisation_current(E0_kV_m: float, rho: float, R: float) -> float:
    """I_g (kA) of the CIGRE / IEEE nonlinear resistance, Grcev (2009) Eq. 18:
    the current at which the field at the electrode reaches the soil's
    critical field E0, I_g = E0 ρ/(2π R²)  (E0 in kV/m, ρ in Ω·m, R in Ω)."""
    return E0_kV_m * rho / (2 * math.pi * R * R)


def time_response(freqs, Z, R, current_name="subsequent_tb781", peak_kA=None,
                  t_max_us=None, dt_us=None, i_t=None, t_us=None,
                  ionisation=None):
    """Potential rise v(t) for a lightning current, by v = R i + F⁻¹[(Z - R) I].

    Z is interpolated from the sweep (in log frequency, real and imaginary
    parts of Z - R separately) and held at its last value above f_max,
    where the current has no energy to speak of.  Splitting off R i keeps
    the slow tail of the current, which the time window truncates, out of
    the transform."""
    if i_t is None:
        if t_max_us is None:
            t_max_us = 200.0 if "first" in current_name else 60.0
        if dt_us is None:
            dt_us = 0.01 if "first" in current_name else 0.002
        t_us = np.arange(0.0, t_max_us, dt_us)
        i_t = waveform(current_name, t_us, peak_kA)
    else:
        t_us = np.asarray(t_us, float)
        dt_us = float(t_us[1] - t_us[0])
        i_t = np.asarray(i_t, float)
    n = len(t_us)
    nfft = 1 << int(math.ceil(math.log2(4 * n)))
    dt = dt_us * 1e-6
    fgrid = np.fft.rfftfreq(nfft, dt)
    lf = np.log(np.asarray(freqs))
    D = np.asarray(Z) - R
    lg = np.log(np.maximum(fgrid, freqs[0]))
    Dr = np.interp(lg, lf, D.real)
    Di = np.interp(lg, lf, D.imag)
    # below f_min the excess impedance falls to zero like f (inductive) —
    # scale the first value down linearly
    lowf = fgrid < freqs[0]
    Dr[lowf] = D.real[0] * (fgrid[lowf] / freqs[0]) ** 2
    Di[lowf] = D.imag[0] * fgrid[lowf] / freqs[0]
    Dg = Dr + 1j * Di
    # taper i(t) to zero over the last 10 % of the window to limit leakage
    It = np.fft.rfft(i_t, nfft)
    x = np.fft.irfft(It * Dg, nfft)[:n]
    v = R * i_t + x
    k = int(np.argmax(v))
    j = int(np.argmax(i_t))
    out = dict(t_us=t_us, i_kA=i_t, v_kV=v, x_kV=x,
               V_peak=float(v[k]), t_V_peak=float(t_us[k]),
               I_peak=float(i_t[j]), t_I_peak=float(t_us[j]),
               Z_impulse=float(v[k] / i_t[j]),
               IC=float(v[k] / i_t[j] / R))
    if ionisation:
        # Soil ionisation (Grcev 2009, Eq. 18 and 20): the resistive part of
        # the response sees R(t) = R/√(1 + i(t)/I_g); the reactive part x(t),
        # set by the frequency response, is kept.  I_g = E0 ρ/(2πR²).
        Ig = ionisation_current(float(ionisation["E0"]), float(ionisation["rho"]), R)
        Rt = R / np.sqrt(1.0 + np.maximum(i_t, 0.0) / Ig)
        vi = Rt * i_t + x
        ki = int(np.argmax(vi))
        out.update(v_ion_kV=vi, R_t=Rt, Ig_kA=Ig,
                   V_peak_ion=float(vi[ki]), t_V_peak_ion=float(t_us[ki]),
                   Z_impulse_ion=float(vi[ki] / i_t[j]),
                   IC_ion=float(vi[ki] / i_t[j] / R),
                   R_min=float(Rt.min()))
    return out


def impulse_coefficient_formula(rho, length, T1_us, Im_kA, R, E0_kV_m=400.0):
    """Grcev (2009) Eq. 22–25: the impulse coefficient of a vertical or
    horizontal electrode with and without ionisation, from ρ, ℓ, the
    zero-to-peak time T1 and the peak current."""
    x = rho * T1_us
    al = 0.025 + math.exp(-0.82 * x ** 0.257)
    be = 0.17 + math.exp(-0.22 * x ** 0.555)
    leff = (1 - be) / al
    A = 1.0 if length <= leff else al * length + be
    Ig = ionisation_current(E0_kV_m, rho, R)
    Ai = 1.0 / math.sqrt(1.0 + Im_kA / Ig) + A - 1.0
    return dict(A=A, A_ion=Ai, L_eff=leff, alpha=al, beta=be, Ig_kA=Ig)


# ---------------------------------------------------------------------------
# Reference formulas
# ---------------------------------------------------------------------------

def tl_impedance(f, rho, eps_r, length, radius, depth=None, vertical=True):
    """Transmission-line model of Grcev (2009) Eq. (10)–(11), open line:
    Z = Z0 coth(γ l), with R', G', C', L' from Dwight / Sunde."""
    f = np.asarray(f, float)
    om = 2 * np.pi * f
    if vertical:
        R = rho / (2 * np.pi * length) * (np.log(4 * length / radius) - 1)
    else:
        R = rho / (np.pi * length) * (np.log(2 * length / np.sqrt(2 * radius * depth)) - 1)
    G = 1 / (R * length)
    C = rho * eps_r * EPS0 / R / length
    L = MU0 / (2 * np.pi) * (np.log(2 * length / radius) - 1)     # per metre
    Zs = 1j * om * L
    Ys = G + 1j * om * C
    Z0 = np.sqrt(Zs / Ys)
    g = np.sqrt(Zs * Ys)
    return Z0 / np.tanh(g * length), R


def grcev_fc(rho, length):
    """Grcev's characteristic (switch) frequency, MHz, Eq. (21) of 2009."""
    return rho * (0.6 / length) ** 2.3


def alipio_ic(rho0, length, stroke="first"):
    """Impulse coefficient of a horizontal electrode, Alipio & Visacro
    (2014) Eq. (3)–(7), frequency-dependent soil."""
    if stroke == "first":
        ic0 = -0.00086 * rho0 ** 0.686 + 0.992
        al = 2e-3 + math.exp(-1.55 * rho0 ** 0.162)
        be = -0.5 + math.exp(-0.00046 * rho0 ** 0.83)
    else:
        ic0 = -0.0945 * rho0 ** 0.25 + 1.235
        al = 7.32e-4 + math.exp(-0.97 * rho0 ** 0.2)
        be = -0.7 + math.exp(-0.0037 * rho0 ** 0.51)
    leff = (ic0 - be) / al
    ic = ic0 if length <= leff else al * length + be
    return dict(IC=ic, IC0=ic0, L_eff=leff, alpha=al, beta=be)


# ---------------------------------------------------------------------------
# One call for the application
# ---------------------------------------------------------------------------

def analyse(items, rho0, eps_r=10.0, soil_model="constant", level="mean",
            feed=None, f_max=10e6, n_f=40, peaks=None, max_segments=800,
            metal="copper", waveforms=("first_tb781", "subsequent_tb781"),
            layers=None, E0=None):
    """Harmonic impedance and lightning response of an electrode.

    layers = dict(rho=[ρ2, ρ3, …], h=[h1, h2, …]) adds layers below the
             top layer of resistivity rho0 (thicknesses h of the layers
             above each);
    E0     = critical field of the soil (kV/m) to include ionisation.

    Returns plain lists, ready for the interface."""
    if layers and layers.get("rho"):
        soil = LayeredSoil([rho0] + [float(r) for r in layers["rho"]],
                           [float(h) for h in layers["h"]], eps_r, soil_model, level)
    else:
        soil = Soil(rho0, eps_r, soil_model, level)
    wires = Wires.from_items(items)
    if not wires.raw:
        raise ValueError("Add at least one electrode element.")
    if feed is None:
        a = wires.raw[0][0]
        feed = [float(a[0]), float(a[1]), float(a[2])]
    r = harmonic_impedance(wires=wires, soil=soil, feed=feed, f_min=100.0,
                           f_max=f_max, n_f=n_f, metal=metal,
                           max_segments=max_segments)
    Z = r["Z"]
    R = r["R"]
    peaks = peaks or {}
    default_peak = {"first_tb781": 31.1, "subsequent_tb781": 11.8,
                    "first_heidler": 30.0, "subsequent_heidler": 12.0}
    responses = {}
    ion = None
    w = r["model"].w
    rho_ion = soil.rho_near(w.mid[:, 2]) if hasattr(soil, "rho_near") else rho0
    if E0:
        ion = dict(E0=float(E0), rho=rho_ion)
    for wfn in waveforms:
        tr = time_response(r["f"], Z, R, wfn, peaks.get(wfn, default_peak.get(wfn)),
                           ionisation=ion)
        step = max(1, len(tr["t_us"]) // 1500)
        tmax = 20.0 if "first" in wfn else 6.0
        k = tr["t_us"] <= tmax
        extra = {}
        if ion:
            extra = dict(v_ion_kV=tr["v_ion_kV"][k][::step].tolist(),
                         R_t=tr["R_t"][k][::step].tolist(),
                         V_peak_ion_kV=tr["V_peak_ion"], t_V_peak_ion=tr["t_V_peak_ion"],
                         Z_impulse_ion=tr["Z_impulse_ion"], IC_ion=tr["IC_ion"],
                         R_min=tr["R_min"], Ig_kA=tr["Ig_kA"])
        responses[wfn] = dict(**extra,
            label=WAVEFORMS[wfn]["label"],
            t_us=tr["t_us"][k][::step].tolist(),
            i_kA=tr["i_kA"][k][::step].tolist(),
            v_kV=tr["v_kV"][k][::step].tolist(),
            V_peak_kV=tr["V_peak"], t_V_peak=tr["t_V_peak"],
            I_peak_kA=tr["I_peak"], t_I_peak=tr["t_I_peak"],
            Z_impulse=tr["Z_impulse"], IC=tr["IC"],
            V_lf_kV=R * tr["I_peak"])
    feed_node = wires.nodes[r["feed"]].tolist()
    # switch frequency: where |Z| first departs from R by 10 %
    absZ = np.abs(Z)
    dev = np.where(np.abs(absZ / R - 1) > 0.10)[0]
    f_switch = float(r["f"][dev[0]]) if len(dev) else None
    inductive = bool(absZ[-1] > R)
    out = dict(f=r["f"].tolist(), absZ=absZ.tolist(),
               phase=np.degrees(np.angle(Z)).tolist(),
               Zr=Z.real.tolist(), Zi=Z.imag.tolist(),
               R=R, segments=r["segments"], nodes=r["nodes"],
               feed=feed_node, soil=soil.describe(), f_switch=f_switch,
               high_frequency=("inductive" if inductive else "capacitive"),
               responses=responses, layers=getattr(soil, "N", 1),
               encased=int(np.count_nonzero(w.sh_ln > 0)))
    if ion:
        ext = _raw_extent(wires)
        out["ionisation"] = dict(E0=float(E0), rho=rho_ion, extent=ext,
                                 Ig_kA=ionisation_current(float(E0), rho_ion, R),
                                 outside_range=bool(ext > 30.0))
    # reference formulas for a single straight horizontal electrode
    if len(wires.raw) == 1:
        a, b, rad, _ = wires.raw[0]
        L = float(np.linalg.norm(b - a))
        horizontal = abs(b[2] - a[2]) < 1e-9
        out["single"] = dict(length=L, horizontal=horizontal,
                             grcev_fc_MHz=grcev_fc(rho0, L))
        if horizontal and soil_model == "alipio_visacro":
            out["single"]["alipio"] = {s: alipio_ic(rho0, L, s)
                                       for s in ("first", "subsequent")}
    return out
