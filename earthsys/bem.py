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
Numerical earthing analysis by the boundary-element (method-of-moments)
technique.

The buried metal is discretised into short cylindrical segments.  Each
segment is assumed to leak a uniform current density into the soil and all
segments share one potential (the earth is bonded together), which gives

    [ P    -1 ] [ I ]   [ 0  ]
    [ 1ᵀ    0 ] [ V ] = [ I_G ]

where P_ij is the average potential appearing on segment i per ampere leaked
from segment j.  Solving this system yields the leakage-current distribution,
the ground potential rise, and hence the earth resistance R_g = V / I_G.

Soil models
-----------
* uniform         G = ρ/(4πr) with the air-surface image
* two-layer       G from the complete image series with reflection factor
                  K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁).  All four Green's functions are
                  used — source and field point each in the upper or the
                  lower layer — and every conductor that crosses the layer
                  interface is split there, so rods driven into the lower
                  layer see the lower-layer resistivity.  (Version 1.1 used
                  the upper-layer function for every segment, which put R_g
                  about 2 % low for rods reaching a more conductive layer.)
* three-layer     G from the exact image expansion of earthsys.layered: the
                  images near the electrodes one by one, the deep ones from
                  the spectral solution as Taylor tables in r (version 1.4).
                  Every conductor is split at both interfaces and each
                  segment sees the resistivity of its own layer.

Coordinates: x, y horizontal (m); z is DEPTH, positive downwards, the soil
surface being z = 0.

Requires numpy.
"""

from __future__ import annotations

import math

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:                                    # pragma: no cover
    np = None
    HAVE_NUMPY = False


# Gauss-Legendre nodes/weights on [0, 1]
_GL = {}


def _gauss(n: int):
    if n not in _GL:
        x, w = np.polynomial.legendre.leggauss(n)
        _GL[n] = (0.5 * (x + 1.0), 0.5 * w)
    return _GL[n]


class SoilModel:
    """Uniform or two-layer horizontally stratified soil."""

    def __init__(self, rho1: float, rho2: float | None = None,
                 h: float | None = None, max_images: int = 60,
                 tol: float = 1e-6, rho3: float | None = None,
                 h2: float | None = None, rho4: float | None = None,
                 h3: float | None = None):
        self.rho1 = float(rho1)
        self.rho2 = float(rho2) if rho2 else None
        self.h = float(h) if h else None
        self.rho3 = float(rho3) if rho3 else None
        self.h2 = float(h2) if h2 else None
        self.three = (self.rho2 is not None and self.h is not None and
                      self.rho3 is not None and self.h2 is not None)
        self.green = None
        if self.three:
            from . import layered
            rhos = [self.rho1, self.rho2, self.rho3]
            hs = [self.h, self.h2]
            if rho4 and h3:
                rhos.append(float(rho4))
                hs.append(float(h3))
            self.earth = layered.LayeredEarth(rhos, hs)
            self.rhos = rhos
            self.interfaces = list(self.earth.depths)
            self.uniform = False
            self.K = (self.rho2 - self.rho1) / (self.rho2 + self.rho1)
            self.N = self.N_tail = 0
            return
        self.uniform = self.rho2 is None or self.h is None or \
            abs(self.rho2 - self.rho1) < 1e-9
        self.rhos = [self.rho1] if self.uniform else [self.rho1, self.rho2]
        self.interfaces = [] if self.uniform else [self.h]
        self.K = 0.0 if self.uniform else \
            (self.rho2 - self.rho1) / (self.rho2 + self.rho1)
        self.N_tail = 0
        self._tail = None
        if self.uniform:
            self.N = 0
        else:
            # Images are summed explicitly up to max_images; beyond that the
            # remaining images (up to |K|^n < tol) are all deep, at about 2nh,
            # and are added as a tabulated function of the horizontal
            # distance only (tail(), below).  Version 1.3.3 and earlier simply
            # stopped at 60 images, which for K > 0.8 dropped a real part of
            # the series: -0.8 % on R_g for rho2/rho1 = 40 and -15 % for
            # rho2/rho1 = 200 (thin soil over rock) — on the unsafe side.
            aK = abs(self.K)
            n_tol = int(math.ceil(math.log(tol) / math.log(aK))) if aK > 0 else 1
            self.N = max(1, min(n_tol, max_images))
            self.N_tail = max(self.N, min(n_tol, 20000))

    def tail(self, rh):
        """Sum_{n = N+1}^{N_tail} K^n / sqrt(rh^2 + (2nh)^2), plus the
        remainder beyond N_tail in closed form, for an array of horizontal
        distances rh (m).  Zero when the explicit series is already complete.

        The depth of source and field point is neglected against 2nh (the
        first omitted image is at least 2(N+1)h deep); the function of rh is
        tabulated once and interpolated."""
        rh = np.asarray(rh, float)
        if self.N_tail <= self.N:
            return np.zeros_like(rh)
        need = float(rh.max()) if rh.size else 0.0
        if self._tail is None or self._tail[0][-1] < need:
            h, K = self.h, self.K
            step = 2.0 * (self.N + 1) * h / 50.0
            top = max(need * 1.5, 50.0 * step)
            grid = np.linspace(0.0, top, int(math.ceil(top / step)) + 2)
            n = np.arange(self.N + 1, self.N_tail + 1, dtype=float)
            Kn = np.sign(K) ** n * np.exp(n * math.log(abs(K)))
            vals = np.zeros_like(grid)
            for a in range(0, len(n), 512):
                nn, kk = n[a:a + 512], Kn[a:a + 512]
                vals += (kk[None, :] / np.sqrt(grid[:, None] ** 2
                                               + (2.0 * nn[None, :] * h) ** 2)).sum(axis=1)
            # remainder beyond N_tail: sum K^n/(2nh) = (-ln(1-K) - partial)/(2h)
            m = np.arange(1, self.N_tail + 1, dtype=float)
            partial = float((np.sign(K) ** m * np.exp(m * math.log(abs(K))) / m).sum())
            vals += (-math.log(1.0 - K) - partial) / (2.0 * h)
            self._tail = (grid, vals)
        grid, vals = self._tail
        return np.interp(rh, grid, vals)

    def tail_amplitude(self, src_layer: int, fld_layer: int) -> float:
        """Coefficient multiplying K^n per image order n in image_terms."""
        if self.uniform:
            return 0.0
        if src_layer == 1 and fld_layer == 1:
            return 4.0 * self.rho1 / (4.0 * math.pi)
        if src_layer != fld_layer:
            return 2.0 * self.rho1 * (1.0 + self.K) / (4.0 * math.pi)
        return self.rho2 * (1.0 - self.K ** 2) / (4.0 * math.pi)

    def layer_of(self, z: float) -> int:
        """1-based layer index of depth z (a point on an interface belongs
        to the layer above)."""
        return 1 + sum(1 for d in self.interfaces if z > d)

    def prepare(self, Z: float, r_max: float):
        """Three-layer soil: build (or extend) the Green's function tables
        for points no deeper than Z and no further apart than r_max."""
        if not self.three:
            return
        from . import layered
        if self.green is None:
            self.green = layered.LayeredGreen(self.earth, Z, r_max)
        else:
            self.green.ensure(Z, r_max)

    def describe(self):
        if self.three:
            n = len(self.rhos)
            names = {3: "Three", 4: "Four"}.get(n, str(n))
            parts = [f"ρ{'₁₂₃₄₅'[i]} = {r:g} Ω·m to {d:g} m"
                     for i, (r, d) in enumerate(zip(self.rhos, self.interfaces))]
            parts.append(f"ρ{'₁₂₃₄₅'[n - 1]} = {self.rhos[-1]:g} Ω·m below")
            return (f"{names}-layer soil: " + ", ".join(parts) +
                    " (exact image expansion with spectral deep-image tables)")
        if self.uniform:
            return f"Uniform soil, ρ = {self.rho1:g} Ω·m"
        extra = (f" (+ {self.N_tail - self.N} deep images tabulated)"
                 if self.N_tail > self.N else "")
        return (f"Two-layer soil: ρ₁ = {self.rho1:g} Ω·m, "
                f"ρ₂ = {self.rho2:g} Ω·m, h = {self.h:g} m, K = {self.K:+.3f}, "
                f"{self.N} image terms{extra}")


class Segment:
    __slots__ = ("p1", "p2", "radius", "mid", "length", "tag", "layer", "net",
                 "shell")

    def __init__(self, p1, p2, radius, tag="", layer=1, net=0, shell=0.0):
        self.p1 = np.asarray(p1, dtype=float)
        self.p2 = np.asarray(p2, dtype=float)
        self.radius = float(radius)
        self.mid = 0.5 * (self.p1 + self.p2)
        self.length = float(np.linalg.norm(self.p2 - self.p1))
        self.tag = tag
        self.layer = layer          # 1-based soil layer of the segment
        self.net = int(net)         # electrically connected network index
        # concrete encasement: ρ_c ln(r_c/a)/2π (Ω·m); the leakage of the
        # segment crosses this before it reaches the soil at r_c = radius
        self.shell = float(shell)


def image_terms(soil, src_layer: int, fld_layer: int):
    """Image series of the two-layer Green's function.

    Returns a list of (coefficient, sign, shift): the image of a unit source
    at depth z' sits at depth  sign·z' + shift  and contributes
    coefficient / distance.  The four cases are the complete solution of
    Laplace's equation in two horizontal layers (tutorial §8.6):

      G11  source and field in layer 1  ρ₁/4π Σ Kⁿ (four images per n)
      G21  field in layer 2             ρ₁(1+K)/4π Σ Kⁿ
      G12  source in layer 2            ρ₁(1+K)/4π Σ Kⁿ   (reciprocal)
      G22  both in layer 2              ρ₂/4π [1/r − K/r(2h−z') ...]
    """
    if soil.uniform:
        c = soil.rho1 / (4.0 * math.pi)
        return [(c, 1, 0.0), (c, -1, 0.0)]
    K, h, N = soil.K, soil.h, soil.N
    T = []
    if src_layer == 1 and fld_layer == 1:
        c = soil.rho1 / (4.0 * math.pi)
        T += [(c, 1, 0.0), (c, -1, 0.0)]
        for n in range(1, N + 1):
            k = c * K ** n
            T += [(k, 1, -2 * n * h), (k, 1, 2 * n * h),
                  (k, -1, -2 * n * h), (k, -1, 2 * n * h)]
    elif src_layer == 1 and fld_layer == 2:
        c = soil.rho1 * (1.0 + K) / (4.0 * math.pi)
        for n in range(0, N + 1):
            T += [(c * K ** n, 1, -2 * n * h), (c * K ** n, -1, -2 * n * h)]
    elif src_layer == 2 and fld_layer == 1:
        c = soil.rho1 * (1.0 + K) / (4.0 * math.pi)
        for n in range(0, N + 1):
            T += [(c * K ** n, 1, 2 * n * h), (c * K ** n, -1, -2 * n * h)]
    else:
        c = soil.rho2 / (4.0 * math.pi)
        T += [(c, 1, 0.0), (-c * K, -1, 2 * h)]
        for n in range(0, N + 1):
            T.append((c * (1.0 - K * K) * K ** n, -1, -2 * n * h))
    return T


def _offset_path(pts, d, closed=True):
    """Offset a polyline by `d` (positive = outwards for a closed path,
    to the right of the direction of travel for an open one), with mitred
    corners."""
    P = [np.array(q, float) for q in pts]
    if closed and np.allclose(P[0], P[-1]):
        P = P[:-1]
    n = len(P)
    if closed:
        area = 0.5 * sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1]
                         for i in range(n))
        sgn = 1.0 if area > 0 else -1.0    # CCW: outward normal is right
    else:
        sgn = 1.0

    def normal(a, b):
        t = (b - a) / max(np.linalg.norm(b - a), 1e-12)
        return np.array([t[1], -t[0]]) * sgn

    out = []
    for i in range(n):
        if not closed and i in (0, n - 1):
            a, b = (P[0], P[1]) if i == 0 else (P[-2], P[-1])
            out.append(P[i] + d * normal(a, b))
            continue
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        n1, n2 = normal(a, b), normal(b, c)
        bis = n1 + n2
        nb = np.linalg.norm(bis)
        if nb < 1e-9:
            out.append(b + d * n1)
            continue
        bis /= nb
        out.append(b + d * bis / max(float(bis @ n1), 0.2))
    if closed:
        out.append(out[0])
    return [tuple(map(float, q)) for q in out]


class Network:
    """Buried electrode network: conductors, rods, rings, arbitrary paths."""

    def __init__(self, soil: SoilModel, IG: float = 1.0):
        if not HAVE_NUMPY:
            raise RuntimeError("The numerical solver requires numpy "
                               "(pip install numpy).")
        self.soil = soil
        self.IG = float(IG)
        self.raw = []          # (p1, p2, radius, tag, net)
        self.encase = {}       # raw index -> dict(radius, rho, eps_r): concrete shell
        self.segments: list[Segment] = []
        self.I = None
        self.V = None
        # Electrically separate metal networks.  Network 0 is the energised
        # main grid, which takes the fault current IG.  Others (an isolated
        # fence, a remote structure) take their own injected current --
        # zero for a floating network, which then settles at whatever
        # potential the soil around it imposes.
        self.nets = [dict(name="main", injection=None, kind="main")]
        self.fences = []       # dict(net, path, reach) for fence touch checks
        self.Vnet = None
        self.Z = None          # mutual-resistance matrix between networks
        self._net = 0          # network that add_* methods attach to

    def add_network(self, name="floating", injection=0.0, kind="floating"):
        """Declare a separate metal network and return its index.

        `injection` is the current (A) driven into it from outside; zero
        means it floats.  Conductors added while it is the current network
        (see `use_network`) belong to it."""
        self.nets.append(dict(name=name, injection=float(injection), kind=kind))
        return len(self.nets) - 1

    def use_network(self, k: int):
        self._net = int(k)
        return self

    # -- geometry building -------------------------------------------------
    def add_conductor(self, p1, p2, radius, tag="", net=None, concrete=None):
        """A straight conductor.  `concrete` = dict(radius=r_c, rho=ρ_c[,
        eps_r]) encases it in a coaxial concrete cylinder of radius r_c."""
        self.raw.append((tuple(map(float, p1)), tuple(map(float, p2)),
                         float(radius), tag,
                         self._net if net is None else int(net)))
        if concrete:
            rc = float(concrete["radius"])
            if rc <= radius:
                raise ValueError("The concrete radius must exceed the radius "
                                 "of the steel it encases.")
            if float(concrete["rho"]) <= 0:
                raise ValueError("Concrete resistivity must be positive.")
            self.encase[len(self.raw) - 1] = dict(concrete)
        return self

    def add_grid(self, Lx, Ly, D, depth, radius, x0=0.0, y0=0.0, tag="grid"):
        nx = max(2, int(round(Lx / D)) + 1)      # lines parallel to y
        ny = max(2, int(round(Ly / D)) + 1)      # lines parallel to x
        for j in range(nx):
            x = x0 + Lx * j / (nx - 1)
            self.add_conductor((x, y0, depth), (x, y0 + Ly, depth), radius, tag)
        for i in range(ny):
            y = y0 + Ly * i / (ny - 1)
            self.add_conductor((x0, y, depth), (x0 + Lx, y, depth), radius, tag)
        return self

    def add_rod(self, x, y, top_depth, length, radius, tag="rod"):
        self.add_conductor((x, y, top_depth), (x, y, top_depth + length),
                           radius, tag)
        return self

    def add_ring(self, cx, cy, r, depth, radius, n_sides=32, tag="ring"):
        for i in range(n_sides):
            a1 = 2 * math.pi * i / n_sides
            a2 = 2 * math.pi * (i + 1) / n_sides
            self.add_conductor((cx + r * math.cos(a1), cy + r * math.sin(a1), depth),
                               (cx + r * math.cos(a2), cy + r * math.sin(a2), depth),
                               radius, tag)
        return self

    def add_rectangle(self, x0, y0, Lx, Ly, depth, radius, tag="ring"):
        pts = [(x0, y0), (x0 + Lx, y0), (x0 + Lx, y0 + Ly), (x0, y0 + Ly), (x0, y0)]
        for a, b in zip(pts[:-1], pts[1:]):
            self.add_conductor((a[0], a[1], depth), (b[0], b[1], depth), radius, tag)
        return self

    def add_fence(self, path, post_spacing=3.0, post_depth=0.762,
                  post_radius=0.0255, wire_offset=None, wire_depth=0.5,
                  wire_radius=0.005, bonded=False, closed=True,
                  name="fence", reach=1.0):
        """A metal fence: posts driven into the soil along `path`, with an
        optional buried wire run parallel to it.

        path         : list of (x, y) vertices of the fence line
        post_spacing : maximum distance between posts (m); posts are also
                       placed at every vertex
        wire_offset  : horizontal offset (m) of a buried fence wire from the
                       fence line, positive outwards (None = no wire).  It
                       is bonded to the posts through the fence fabric.
        bonded       : True connects the fence to the main grid (network 0);
                       False makes it a separate, floating network.
        Returns the index of the network the fence belongs to.
        """
        pts = [tuple(map(float, q[:2])) for q in path]
        if closed and pts[0] != pts[-1]:
            pts.append(pts[0])
        if len(pts) < 2:
            raise ValueError("A fence needs at least two vertices.")
        k = 0 if bonded else self.add_network(name, 0.0, kind="fence")
        prev = self._net
        self._net = k
        posts = []
        for a, b in zip(pts[:-1], pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-9:
                continue
            nseg = max(1, int(math.ceil(L / float(post_spacing) - 1e-9)))
            for j in range(nseg):
                t = j / nseg
                posts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        if not closed:
            posts.append(pts[-1])
        for x, y in posts:
            self.add_conductor((x, y, 0.0), (x, y, float(post_depth)),
                               post_radius, "fence_post")
        if wire_offset is not None:
            wp = _offset_path(pts, float(wire_offset), closed)
            for a, b in zip(wp[:-1], wp[1:]):
                self.add_conductor((a[0], a[1], wire_depth),
                                   (b[0], b[1], wire_depth),
                                   wire_radius, "fence_wire")
        self._net = prev
        self.fences.append(dict(net=k, path=pts, closed=closed,
                                reach=float(reach), name=name,
                                bonded=bool(bonded), posts=len(posts)))
        return k

    # -- discretisation ----------------------------------------------------
    def discretise(self, target: float = 2.0, max_segments: int = 3000):
        total = sum(np.linalg.norm(np.array(b) - np.array(a))
                    for a, b, *_ in self.raw)
        if total / max(target, 1e-6) > max_segments:
            target = total / max_segments
        self.segments = []
        for ir, (a, b, rad, tag, nk) in enumerate(self.raw):
            enc = self.encase.get(ir)
            shell = 0.0
            if enc:
                rc = float(enc["radius"])
                shell = float(enc["rho"]) * math.log(rc / rad) / (2 * math.pi)
                rad = rc
            a = np.array(a, float)
            b = np.array(b, float)
            L = float(np.linalg.norm(b - a))
            # split at the layer interface so that every segment lies in
            # one layer and sees that layer's Green's function
            cuts = [0.0, 1.0]
            s = self.soil
            for zi in s.interfaces:
                if (a[2] - zi) * (b[2] - zi) < 0:
                    cuts.append((zi - a[2]) / (b[2] - a[2]))
            cuts = sorted(cuts)
            for t0, t1 in zip(cuts[:-1], cuts[1:]):
                q1 = a + (b - a) * t0
                q2 = a + (b - a) * t1
                Lq = float(np.linalg.norm(q2 - q1))
                # a thick (concrete-encased) conductor keeps its segments
                # longer than its radius, as the thin-wire kernel requires
                tg = max(target, 1.5 * rad) if shell > 0 else target
                n = max(1, int(math.ceil(Lq / tg - 1e-9)))
                for k in range(n):
                    p1 = q1 + (q2 - q1) * k / n
                    p2 = q1 + (q2 - q1) * (k + 1) / n
                    zm = 0.5 * (p1[2] + p2[2])
                    lay = s.layer_of(zm)
                    self.segments.append(Segment(p1, p2, rad, tag, lay, nk, shell))
        return len(self.segments)

    # -- Green's function --------------------------------------------------
    def _green_terms(self, field, src_pts, skip_direct=False, src_layer=1,
                     min_rh2=0.0):
        """Sum of image contributions between field points and source points.

        field     : (M, 3) array of field points (either layer)
        src_pts   : (Q, 3) array of source quadrature points, all in
                    `src_layer`
        returns   : (M, Q) array of potential coefficients (V per A per unit
                    current density weight -- caller applies quadrature weights)
        skip_direct drops the singular 1/r term of a same-layer pair (the
        caller supplies it analytically for the self term).
        """
        s = self.soil
        dx = field[:, None, 0] - src_pts[None, :, 0]
        dy = field[:, None, 1] - src_pts[None, :, 1]
        rh2 = dx * dx + dy * dy
        if min_rh2:
            rh2 = np.maximum(rh2, min_rh2)
        zf = field[:, 2]
        zs = src_pts[None, :, 2]
        out = np.zeros_like(rh2)
        if s.three:
            s.prepare(max(float(zf.max()), float(zs.max())),
                      float(np.sqrt(rh2.max())) if rh2.size else 1.0)
            lay = np.array([s.layer_of(z) for z in zf])
            c = s.rhos[src_layer - 1] / (4.0 * math.pi)
            for fl in range(1, len(s.rhos) + 1):
                m = lay == fl
                if m.any():
                    out[m] = c * s.green.sum_terms(src_layer, fl, rh2[m],
                                                   zf[m][:, None], zs, skip_direct)
            return out
        if s.uniform:
            masks = [(1, np.ones(len(field), bool))]
        else:
            in2 = zf > s.h
            masks = [(1, ~in2), (2, in2)]
        for fl, m in masks:
            if not m.any():
                continue
            zfm = zf[m][:, None]
            r2 = rh2[m]
            acc = np.zeros_like(r2)
            terms = image_terms(s, src_layer, fl)
            if not skip_direct and not np.any(zfm):
                # Field points on the surface: an image at z and one at -z
                # are the same distance away, so (sgn, shift) and
                # (-sgn, -shift) merge -- this halves the work for the
                # surface-potential maps, which dominate post-processing.
                merged = {}
                for coef, sgn, shift in terms:
                    key = (sgn, shift) if sgn > 0 else (-sgn, -shift)
                    merged[key] = merged.get(key, 0.0) + coef
                terms = [(c, k[0], k[1]) for k, c in merged.items()]
            for coef, sgn, shift in terms:
                if skip_direct and sgn == 1 and shift == 0.0 and fl == src_layer:
                    continue
                zi = sgn * zs + shift
                acc += coef / np.sqrt(np.maximum(r2 + (zfm - zi) ** 2, 1e-24))
            if s.N_tail > s.N:
                acc += s.tail_amplitude(src_layer, fl) * s.tail(np.sqrt(r2))
            out[m] = acc
        return out

    def _coeff_column(self, field, seg: Segment, nq: int, skip_direct=False,
                      reduced=False):
        t, w = _gauss(nq)
        pts = seg.p1[None, :] + (seg.p2 - seg.p1)[None, :] * t[:, None]
        # `reduced`: the field point sits on the surface of a thick
        # conductor (a concrete-encased bar, whose radius is that of the
        # concrete), so the horizontal distance is floored at that radius
        G = self._green_terms(field, pts, skip_direct, seg.layer,
                              seg.radius ** 2 if reduced else 0.0)
        return G @ w                                  # average over the segment

    # -- assembly and solution --------------------------------------------
    def build_matrix(self, near_factor: float = 8.0, nf: int = 6, nq_near: int = 10):
        """Assemble the potential-coefficient matrix.

        Far pairs use mid-point collocation (fast).  Near pairs -- including
        the pair formed by a segment and its own air-surface image -- are
        re-evaluated with a double (Galerkin) Gauss quadrature, because
        collocation under-estimates the average potential when the source is
        close, which would otherwise bias the earth resistance low.
        """
        segs = self.segments
        n = len(segs)
        mids = np.array([s.mid for s in segs])
        lens = np.array([s.length for s in segs])
        P = np.zeros((n, n))
        if self.soil.three:
            ends = np.array([q for s in segs for q in (s.p1, s.p2)])
            ext = float(np.hypot(np.ptp(ends[:, 0]), np.ptp(ends[:, 1])))
            # the surface map extends a margin beyond the electrodes
            self.soil.prepare(float(ends[:, 2].max()), ext + 60.0)
        rho1 = self.soil.rho1

        # ---- pass 1: mid-point collocation ------------------------------
        for j, sj in enumerate(segs):
            d = np.linalg.norm(mids - sj.mid, axis=1)
            nq = 4 if np.all(d > 5 * sj.length) else 12
            P[:, j] = self._coeff_column(mids, sj, nq)

        # ---- pass 2: near pairs by double quadrature --------------------
        tf, wf = _gauss(nf)
        for j, sj in enumerate(segs):
            reach = near_factor * max(sj.length, float(lens.mean()))
            dx = mids[:, 0] - sj.mid[0]
            dy = mids[:, 1] - sj.mid[1]
            rh = np.hypot(dx, dy)
            d_direct = np.sqrt(rh ** 2 + (mids[:, 2] - sj.mid[2]) ** 2)
            d_image = np.sqrt(rh ** 2 + (mids[:, 2] + sj.mid[2]) ** 2)
            idx = np.where((d_direct < reach) | (d_image < reach))[0]
            if idx.size == 0:
                continue
            # field quadrature points for every near segment i
            pts = []
            for i in idx:
                si = segs[i]
                pts.append(si.p1[None, :] + (si.p2 - si.p1)[None, :] * tf[:, None])
            pts = np.concatenate(pts, axis=0)
            skip = False
            col = self._coeff_column(pts, sj, nq_near, skip_direct=skip,
                                     reduced=sj.shell > 0)
            col = col.reshape(len(idx), nf) @ wf
            P[idx, j] = col

        # ---- exact self terms -------------------------------------------
        for j, sj in enumerate(segs):
            L, a = sj.length, sj.radius
            rho_j = self.soil.rhos[sj.layer - 1]
            if sj.shell > 0:
                # exact average over a tube (thick encasement, L ~ r_c)
                self_direct = rho_j / (4.0 * math.pi * L * L) * 2.0 * (
                    L * math.asinh(L / a) - math.sqrt(L * L + a * a) + a)
            else:
                self_direct = rho_j / (2.0 * math.pi * L) * (math.log(2.0 * L / a) - 1.0)
            tfp = sj.p1[None, :] + (sj.p2 - sj.p1)[None, :] * tf[:, None]
            img = self._coeff_column(tfp, sj, 16, skip_direct=True) @ wf
            P[j, j] = self_direct + float(img) + sj.shell / L
        return P

    def solve(self, target: float = 2.0):
        if not self.segments:
            self.discretise(target)
        n = len(self.segments)
        m = len(self.nets)
        P = self.build_matrix()
        # Incidence of segments on networks.  Every segment of network k is
        # at the same potential V_k, and the currents leaving network k add
        # up to the current injected into it:
        #     P I - E V = 0 ,   E^T I = J
        E = np.zeros((n, m))
        for i, sg in enumerate(self.segments):
            E[i, sg.net] = 1.0
        empty = [self.nets[k]["name"] for k in range(m) if E[:, k].sum() == 0]
        if empty:
            raise ValueError("Network(s) without any conductor: "
                             + ", ".join(empty))
        A = np.zeros((n + m, n + m))
        A[:n, :n] = P
        A[:n, n:] = -E
        A[n:, :n] = E.T
        # one solve per unit injection gives the mutual-resistance matrix
        # Z (V_j for 1 A into network k) and the matching current shapes,
        # so a fence's own resistance and its coupling to the grid come out
        # of the same factorisation.
        B = np.zeros((n + m, m))
        B[n:, :] = np.eye(m)
        sol = np.linalg.solve(A, B)
        self.Ibasis = sol[:n, :]
        self.Z = sol[n:, :]
        J = np.array([self.IG] + [nt["injection"] for nt in self.nets[1:]])
        self.I = self.Ibasis @ J
        self.Vnet = self.Z @ J
        self.V = float(self.Vnet[0])
        out = dict(segments=n, GPR=self.V, Rg=float(self.Z[0, 0]), IG=self.IG,
                   I_min=float(self.I.min()), I_max=float(self.I.max()),
                   soil=self.soil.describe(),
                   total_length=float(sum(s.length for s in self.segments)))
        if m == 1:
            out["Rg"] = self.V / self.IG if self.IG else float(self.Z[0, 0])
        else:
            out["networks"] = self.network_summary()
        return out

    def network_summary(self):
        """Potential, current and resistances of every network."""
        out = []
        for k, nt in enumerate(self.nets):
            segs = [s for s in self.segments if s.net == k]
            I_k = float(sum(self.I[i] for i, s in enumerate(self.segments)
                            if s.net == k))
            # resistance of network k alone in the soil, the others removed
            # is not what Z[k,k] is: Z[k,k] keeps the others present but
            # floating, which is the physical situation on site.
            out.append(dict(
                index=k, name=nt["name"], kind=nt["kind"],
                V=float(self.Vnet[k]),
                V_pct_GPR=(100.0 * float(self.Vnet[k]) / self.V
                           if self.V else None),
                current=I_k, R_self=float(self.Z[k, k]),
                R_mutual_main=float(self.Z[k, 0]),
                transfer_from_main=float(self.V - self.Vnet[k]),
                segments=len(segs),
                length=float(sum(s.length for s in segs))))
        return out

    # -- post-processing ---------------------------------------------------
    def potential_at(self, points, chunk: int = 400):
        """Earth-surface / soil potential (V) at arbitrary points (N, 3).

        All segments are summed at once with a 4-point Gauss rule (one
        vectorised Green's-function call per soil layer and chunk of field
        points); field points closer than five segment lengths to a segment
        are then corrected to a 12-point rule, which is what the
        per-segment loop used to do, at a fraction of the cost.
        """
        pts = np.atleast_2d(np.asarray(points, float))
        out = np.zeros(len(pts))
        if not len(pts):
            return out
        segs = self.segments
        t4, w4 = _gauss(4)
        t12, w12 = _gauss(12)
        by_layer = {}
        for j, sj in enumerate(segs):
            by_layer.setdefault(sj.layer, []).append(j)
        for lay, idx in by_layer.items():
            idx = np.array(idx)
            p1 = np.array([segs[j].p1 for j in idx])
            p2 = np.array([segs[j].p2 for j in idx])
            q = (p1[:, None, :] + (p2 - p1)[:, None, :] * t4[None, :, None]).reshape(-1, 3)
            wq = (self.I[idx][:, None] * w4[None, :]).ravel()
            for a in range(0, len(pts), chunk):
                f = pts[a:a + chunk]
                out[a:a + chunk] += self._green_terms(f, q, False, lay) @ wq
        # near-field correction
        for j, sj in enumerate(segs):
            d = np.linalg.norm(pts - sj.mid, axis=1)
            near = np.where(d <= 5 * sj.length)[0]
            if near.size == 0:
                continue
            f = pts[near]
            q12 = sj.p1[None, :] + (sj.p2 - sj.p1)[None, :] * t12[:, None]
            q4 = sj.p1[None, :] + (sj.p2 - sj.p1)[None, :] * t4[:, None]
            # a field point closer to the axis than the conductor radius is
            # on the metal (the top of a fence post, say): take the potential
            # at the conductor surface rather than the line-source singularity
            g = (self._green_terms(f, q12, False, sj.layer, sj.radius ** 2) @ w12
                 - self._green_terms(f, q4, False, sj.layer) @ w4)
            out[near] += self.I[j] * g
        return out

    def surface_potential(self, xlim, ylim, nx=61, ny=61, z=0.0):
        xs = np.linspace(xlim[0], xlim[1], nx)
        ys = np.linspace(ylim[0], ylim[1], ny)
        X, Y = np.meshgrid(xs, ys)
        pts = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, z)])
        V = self.potential_at(pts).reshape(X.shape)
        return dict(x=xs.tolist(), y=ys.tolist(), V=V.tolist(),
                    GPR=self.V,
                    touch=(self.V - V).tolist(),
                    V_max=float(V.max()), V_min=float(V.min()),
                    touch_max=float((self.V - V).max()))

    def profile(self, p_start, p_end, n=200, z=0.0, step=1.0):
        """Potential, touch and step voltage along a straight line."""
        p1 = np.array([p_start[0], p_start[1], z], float)
        p2 = np.array([p_end[0], p_end[1], z], float)
        t = np.linspace(0.0, 1.0, n)
        pts = p1[None, :] + (p2 - p1)[None, :] * t[:, None]
        V = self.potential_at(pts)
        L = float(np.linalg.norm(p2 - p1))
        s = t * L
        touch = self.V - V
        # step voltage over the given step distance along the same line
        d = (p2 - p1) / max(L, 1e-9)
        pts2 = pts + d[None, :] * step
        V2 = self.potential_at(pts2)
        step_v = np.abs(V - V2)
        return dict(s=s.tolist(), V=V.tolist(), touch=touch.tolist(),
                    step=step_v.tolist(), GPR=self.V,
                    touch_max=float(touch.max()), step_max=float(step_v.max()),
                    step_distance=step)

    def touch_bbox(self, margin: float = 1.0, net=0):
        """Bounding box of the buried metal, expanded by `margin` (arm reach).

        By default only the main (energised) network counts, because the
        touch voltage is GPR minus the surface potential; an isolated fence
        has its own touch check (`fence_touch`).  net=None takes all metal.
        """
        raw = [it for it in self.raw if net is None or it[4] == net] or self.raw
        xs = [c for it in raw for c in (it[0][0], it[1][0])]
        ys = [c for it in raw for c in (it[0][1], it[1][1])]
        return (min(xs) - margin, max(xs) + margin,
                min(ys) - margin, max(ys) + margin)

    def worst_touch_step(self, xlim, ylim, nx=41, ny=41, step=1.0,
                         touch_box=None, touch_margin=1.0):
        """Scan a rectangle for the worst touch and step voltages.

        Touch voltage is only meaningful where a person standing on the soil
        can also touch earthed metal, so it is evaluated inside the electrode
        footprint expanded by `touch_margin` (default 1 m of arm reach).
        Step voltage is evaluated over the whole scanned area.
        """
        sp = self.surface_potential(xlim, ylim, nx, ny)
        V = np.array(sp["V"])
        touch = self.V - V
        box = touch_box or self.touch_bbox(touch_margin)
        X, Y = np.meshgrid(np.array(sp["x"]), np.array(sp["y"]))
        inside = ((X >= box[0]) & (X <= box[1]) &
                  (Y >= box[2]) & (Y <= box[3]))
        masked = np.where(inside, touch, -np.inf)
        if not np.isfinite(masked).any():
            masked = touch
        i, j = np.unravel_index(np.argmax(masked), masked.shape)
        touch = masked if False else touch
        # Step voltage is the potential difference between two feet `step`
        # apart, so it has to be differenced at that distance.  Taking
        # np.gradient over the plot grid instead differences over 2*dx, which
        # makes the answer a function of the plot resolution rather than of
        # the physics: on the IEEE 80 Annex B grid it read 218 V at nx = 31
        # and 562 V at nx = 181 for the same model, and the default nx = 61
        # under-read the converged value by about 30 % — in the unsafe
        # direction, feeding a pass/fail check.  Evaluate the field at
        # +/- step/2 about each point instead; the cost is four field
        # evaluations, and the answer no longer moves with nx.
        st = float(step)

        def _V(px, py):
            pts = np.column_stack([np.asarray(px, dtype=float).ravel(),
                                   np.asarray(py, dtype=float).ravel(),
                                   np.zeros(np.size(px))])
            return np.asarray(self.potential_at(pts)).reshape(np.shape(px))

        # Metal that reaches the surface (fence posts) pins the soil next to
        # it at its own potential, so a foot placed on top of a post would
        # read a meaningless step.  Like the commercial codes, the scan
        # leaves out points within 0.25 m of such a conductor.
        tops = np.array([[sg.p1[0], sg.p1[1]] for sg in self.segments
                         if min(sg.p1[2], sg.p2[2]) < 0.05
                         and abs(sg.p2[0] - sg.p1[0]) + abs(sg.p2[1] - sg.p1[1]) < 1e-9])

        def _off_metal(px, py):
            if not len(tops):
                return np.ones(np.shape(px), bool)
            px = np.asarray(px, float)
            py = np.asarray(py, float)
            d2 = np.full(px.shape, np.inf)
            for tx, ty in tops:
                d2 = np.minimum(d2, (px - tx) ** 2 + (py - ty) ** 2)
            return d2 > 0.25 ** 2

        def _stepfield(px, py, V0):
            """|dV| over one step in the worst direction, differenced at the
            step distance itself.  For a locally linear field this is
            |grad V| * step, which is what the step voltage is."""
            ok = _off_metal(px, py) & _off_metal(px + st, py) & _off_metal(px, py + st)
            return np.where(ok, np.hypot(np.abs(_V(px + st, py) - V0),
                                         np.abs(_V(px, py + st) - V0)), 0.0)

        Xq, Yq = np.meshgrid(np.asarray(sp["x"], dtype=float),
                             np.asarray(sp["y"], dtype=float))
        grad = _stepfield(Xq, Yq, V)

        # The worst step is almost always just outside the electrode, and a
        # coarse plot grid can miss it entirely — the value used to swing by
        # 2.6x with nx alone.  Sample the perimeter densely as well, so the
        # answer does not depend on the resolution the user chose for the
        # picture.
        b = self.touch_bbox(0.0, net=None)
        peri_max, peri_at = 0.0, None
        if all(np.isfinite(b)):
            n_per = 240
            xs = np.linspace(b[0] - st, b[1] + st, n_per)
            ys = np.linspace(b[2] - st, b[3] + st, n_per)
            rx = np.concatenate([xs, xs,
                                 np.full(n_per, b[0] - st),
                                 np.full(n_per, b[1] + st)])
            ry = np.concatenate([np.full(n_per, b[2] - st),
                                 np.full(n_per, b[3] + st), ys, ys])
            rV = _V(rx, ry)
            rS = _stepfield(rx, ry, rV)
            k = int(np.argmax(rS))
            peri_max, peri_at = float(rS[k]), [float(rx[k]), float(ry[k])]
        si, sj = np.unravel_index(np.argmax(grad), grad.shape)
        s_grid = float(grad[si, sj])
        s_at = [float(sp["x"][sj]), float(sp["y"][si])]
        if peri_max > s_grid:
            s_grid, s_at = peri_max, peri_at
        return dict(
            touch_max=float(touch[i, j]),
            touch_at=[float(sp["x"][j]), float(sp["y"][i])],
            step_max=s_grid, step_at=s_at,
            step_note=("differenced over the %.2f m step itself and sampled "
                       "along the electrode perimeter, so it does not depend "
                       "on the plot resolution" % st),
            touch_box=list(box), GPR=self.V, surface=sp,
            fences=[self.fence_touch(f) for f in self.fences])

    def fence_touch(self, fence, spacing=0.5, step=1.0):
        """Touch voltage on a fence: the fence's own potential minus the
        surface potential where a person can stand and reach it, within
        `reach` (1 m) on either side of the fence line, plus the step
        voltage across the fence line.

        For a fence bonded to the grid the fence potential is the GPR; an
        isolated fence floats at its own potential, which is what makes the
        outside touch voltage smaller -- and the inside one, where the
        surface is lifted by the grid, sometimes larger.
        """
        if isinstance(fence, int):
            fence = self.fences[fence]
        Vf = float(self.Vnet[fence["net"]]) if self.Vnet is not None else self.V
        pts = [np.array(q, float) for q in fence["path"]]
        reach = fence.get("reach", 1.0)
        if fence.get("closed", True):
            P = pts[:-1] if np.allclose(pts[0], pts[-1]) else pts
            area = 0.5 * sum(P[i][0] * P[(i + 1) % len(P)][1]
                             - P[(i + 1) % len(P)][0] * P[i][1]
                             for i in range(len(P)))
            sgn = 1.0 if area > 0 else -1.0
        else:
            sgn = 1.0
        samples, tang, norm = [], [], []
        for a, b in zip(pts[:-1], pts[1:]):
            L = float(np.linalg.norm(b - a))
            if L < 1e-9:
                continue
            t = (b - a) / L
            nrm = np.array([t[1], -t[0]]) * sgn     # outward
            k = max(2, int(math.ceil(L / spacing)) + 1)
            for u in np.linspace(0.0, 1.0, k)[:-1]:
                samples.append(a + (b - a) * u)
                norm.append(nrm)
        samples = np.array(samples)
        norm = np.array(norm)
        offs = np.linspace(-reach, reach, 5)          # -1, -0.5, 0, .5, 1
        offs = offs[np.abs(offs) > 1e-9]
        res = {}
        for side, sel in (("inside", offs < 0), ("outside", offs > 0)):
            o = offs[sel]
            q = (samples[:, None, :] + norm[:, None, :] * o[None, :, None]).reshape(-1, 2)
            V = self.potential_at(np.column_stack([q, np.zeros(len(q))]))
            T = Vf - V
            j = int(np.argmax(np.abs(T)))
            res[side] = dict(touch_max=float(T[j]), at=[float(q[j, 0]), float(q[j, 1])],
                             touch_min=float(T.min()))
        # step across the fence line
        q1 = samples + norm * (step / 2)
        q2 = samples - norm * (step / 2)
        V1 = self.potential_at(np.column_stack([q1, np.zeros(len(q1))]))
        V2 = self.potential_at(np.column_stack([q2, np.zeros(len(q2))]))
        js = int(np.argmax(np.abs(V1 - V2)))
        worst = max(res["inside"]["touch_max"], res["outside"]["touch_max"],
                    key=abs)
        return dict(name=fence.get("name", "fence"), net=fence["net"],
                    bonded=fence.get("bonded", False), V_fence=Vf,
                    V_pct_GPR=100.0 * Vf / self.V if self.V else None,
                    transfer_from_main=float(self.V - Vf),
                    touch_inside=res["inside"], touch_outside=res["outside"],
                    touch_max=float(worst),
                    step_across=float(abs(V1[js] - V2[js])),
                    step_at=[float(samples[js, 0]), float(samples[js, 1])],
                    posts=fence.get("posts"))

    def current_distribution(self):
        return [dict(x=float(s.mid[0]), y=float(s.mid[1]), z=float(s.mid[2]),
                     I=float(i), density=float(i / (2 * math.pi * s.radius * s.length)),
                     tag=s.tag, length=s.length)
                for s, i in zip(self.segments, self.I)]

    def geometry_json(self):
        return [dict(p1=list(map(float, s.p1)), p2=list(map(float, s.p2)),
                     r=s.radius, tag=s.tag, net=s.net) for s in self.segments]


# ---------------------------------------------------------------------------
# Convenience: build a network from a description dict
# ---------------------------------------------------------------------------

def foundation_geometry(item: dict) -> dict:
    """Equivalent wire of a reinforced-concrete foundation element.

    shape "pier"  : vertical cylinder (pile, pier, pole base) of `diameter`,
                    from `top_depth` down `length`;
    shape "strip" : horizontal beam (strip footing, grade beam) from (x0, y0)
                    to (x1, y1) at `depth`, cross-section `width` × `height`.
    The cage of `bars` bars of `bar_diameter` at `cover` inside the concrete
    becomes one bar of the cage's geometric-mean radius
        a_eq = (n a b^{n−1})^{1/n}   (b = radius of the circle of bars),
    and the section one concrete cylinder of radius r_c (the circle for a
    pier; (w + h)/4 + 0.09·min(w, h) for a rectangle, which gives w/4 for a
    flat strip and 0.59 w for a square, the radii of equal capacitance).
    The leakage then crosses ρ_c ln(r_c/a_eq)/2π per metre of concrete
    before it reaches the soil (Fagan and Lee 1970)."""
    shape = item.get("shape", "pier")
    n = int(item.get("bars", 4))
    if n < 1:
        raise ValueError("A foundation needs at least one reinforcing bar.")
    a = 0.5 * float(item.get("bar_diameter", 0.016))
    cover = float(item.get("cover", 0.05))
    if shape == "pier":
        rc = 0.5 * float(item["diameter"])
    else:
        wd, ht = float(item["width"]), float(item["height"])
        rc = 0.25 * (wd + ht) + 0.09 * min(wd, ht)
    if n == 1:
        a_eq = a
    else:
        b = max(rc - cover - a, 2 * a)
        a_eq = (n * a * b ** (n - 1)) ** (1.0 / n)
    if a_eq >= 0.95 * rc:
        raise ValueError("The concrete cover is too thin for the bar cage "
                         "given; check the diameter and the cover.")
    rho_c = float(item.get("rho_c", 50.0))
    if rho_c <= 0:
        raise ValueError("Concrete resistivity must be positive.")
    return dict(a_eq=a_eq, rc=rc, rho_c=rho_c, eps_r=float(item.get("eps_c", 10.0)),
                shell_ohm_m=rho_c * math.log(rc / a_eq) / (2 * math.pi))


def add_foundation(net: "Network", item: dict):
    g = foundation_geometry(item)
    conc = dict(radius=g["rc"], rho=g["rho_c"], eps_r=g["eps_r"])
    if item.get("shape", "pier") == "pier":
        top = float(item.get("top_depth", 0.0))
        net.add_conductor((item["x"], item["y"], top),
                          (item["x"], item["y"], top + float(item["length"])),
                          g["a_eq"], "foundation", concrete=conc)
    else:
        d = float(item.get("depth", 0.5))
        net.add_conductor((item["x0"], item["y0"], d), (item["x1"], item["y1"], d),
                          g["a_eq"], "foundation", concrete=conc)
    return g


def build_network(spec: dict) -> Network:
    soil = SoilModel(spec.get("rho1", 100.0), spec.get("rho2"),
                     spec.get("h_layer"), rho3=spec.get("rho3"),
                     h2=spec.get("h_layer2"), rho4=spec.get("rho4"),
                     h3=spec.get("h_layer3"))
    net = Network(soil, spec.get("IG", 1000.0))
    r_cond = spec.get("conductor_radius", 0.005)

    for item in spec.get("items", []):
        kind = item.get("kind")
        if kind == "grid":
            net.add_grid(item["Lx"], item["Ly"], item["D"],
                         item.get("depth", 0.5), item.get("radius", r_cond),
                         item.get("x0", 0.0), item.get("y0", 0.0))
        elif kind == "rod":
            net.add_rod(item["x"], item["y"], item.get("top_depth", 0.5),
                        item["length"], item.get("radius", 0.008))
        elif kind == "ring":
            net.add_ring(item["cx"], item["cy"], item["r"],
                         item.get("depth", 0.5), item.get("radius", r_cond),
                         item.get("n_sides", 32))
        elif kind == "rectangle":
            net.add_rectangle(item["x0"], item["y0"], item["Lx"], item["Ly"],
                              item.get("depth", 0.5), item.get("radius", r_cond))
        elif kind == "conductor":
            net.add_conductor(item["p1"], item["p2"], item.get("radius", r_cond))
        elif kind == "foundation":
            add_foundation(net, item)
        elif kind == "fence":
            if "path" in item:
                path = item["path"]
            else:
                x0, y0 = item.get("x0", 0.0), item.get("y0", 0.0)
                Lx, Ly = item["Lx"], item["Ly"]
                path = [(x0, y0), (x0 + Lx, y0), (x0 + Lx, y0 + Ly), (x0, y0 + Ly)]
            wo = item.get("wire_offset")
            if item.get("wire", wo is not None) is False:
                wo = None
            net.add_fence(path, item.get("post_spacing", 3.0),
                          item.get("post_depth", 0.762),
                          item.get("post_radius", 0.0255),
                          wire_offset=wo,
                          wire_depth=item.get("wire_depth", 0.5),
                          wire_radius=item.get("wire_radius", r_cond),
                          bonded=bool(item.get("bonded", False)),
                          closed=item.get("closed", True),
                          name=item.get("name", "fence"))
    return net
