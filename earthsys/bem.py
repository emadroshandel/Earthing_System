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
    """Uniform soil, two to four horizontal layers, or two uniform regions
    side by side with a vertical boundary (1.8.7)."""

    def __init__(self, rho1: float, rho2: float | None = None,
                 h: float | None = None, max_images: int = 60,
                 tol: float = 1e-6, rho3: float | None = None,
                 h2: float | None = None, rho4: float | None = None,
                 h3: float | None = None, vertical: dict | None = None):
        self.rho1 = float(rho1)
        self.rho2 = float(rho2) if rho2 else None
        self.h = float(h) if h else None
        self.rho3 = float(rho3) if rho3 else None
        self.h2 = float(h2) if h2 else None
        self.three = (self.rho2 is not None and self.h is not None and
                      self.rho3 is not None and self.h2 is not None)
        self.green = None
        self.vertical = None
        if vertical and vertical.get("rho") not in (None, ""):
            if self.rho2 is not None and self.h is not None:
                raise ValueError("A vertical soil boundary is solved with uniform soil on "
                                 "each side: remove the horizontal layers, or the boundary.")
            rb = float(vertical["rho"])
            if rb <= 0 or self.rho1 <= 0:
                raise ValueError("Both resistivities of a two-region soil must be positive.")
            phi = math.radians(float(vertical.get("angle", 0.0) or 0.0))
            nrm = (math.cos(phi), math.sin(phi))
            x0, y0 = float(vertical.get("x", 0.0) or 0.0), float(vertical.get("y", 0.0) or 0.0)
            if abs(rb - self.rho1) > 1e-9 * self.rho1:
                # region 1: n·p <= c (with ρ₁); region 2: n·p > c (with ρ')
                self.vertical = dict(rho=rb, x=x0, y=y0, angle=math.degrees(phi),
                                     n=nrm, c=nrm[0] * x0 + nrm[1] * y0)
                self.uniform = False
                self.rhos = [self.rho1, rb]
                self.interfaces = []
                self.K = (rb - self.rho1) / (rb + self.rho1)
                self.N = self.N_tail = 0
                self._tail = None
                return
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

    def zone_of(self, p) -> int:
        """1-based soil zone of point p: its layer, or for a two-region soil
        its region (a point on the vertical boundary belongs to region 1)."""
        if self.vertical:
            v = self.vertical
            return 2 if v["n"][0] * p[0] + v["n"][1] * p[1] > v["c"] + 1e-12 else 1
        return self.layer_of(p[2])

    def zones_of(self, pts):
        """zone_of for an (M, 3) array of points."""
        pts = np.asarray(pts, float)
        if self.vertical:
            v = self.vertical
            return np.where(pts[:, 0] * v["n"][0] + pts[:, 1] * v["n"][1] > v["c"] + 1e-12, 2, 1)
        z = pts[:, 2]
        out = np.ones(len(z), int)
        for d in self.interfaces:
            out += (z > d)
        return out

    def plane_cuts(self, a, b):
        """Fractions (0, 1) along the straight conductor a→b at which it
        crosses a soil interface (horizontal layer or vertical boundary)."""
        cuts = []
        for zi in self.interfaces:
            if (a[2] - zi) * (b[2] - zi) < 0:
                cuts.append((zi - a[2]) / (b[2] - a[2]))
        if self.vertical:
            v = self.vertical
            fa = v["n"][0] * a[0] + v["n"][1] * a[1] - v["c"]
            fb = v["n"][0] * b[0] + v["n"][1] * b[1] - v["c"]
            if fa * fb < 0 and abs(fa) > 1e-9 and abs(fb) > 1e-9:
                cuts.append(fa / (fa - fb))
        return cuts

    def preserved_by(self, op) -> bool:
        """True when the plan transformation `op` ((M, 3) -> (M, 3)) maps the
        soil onto itself: always for horizontal layers; for a vertical
        boundary only when it keeps every point on its own side and at its
        own distance from the boundary."""
        if not self.vertical:
            return True
        v = self.vertical
        t = v["n"][1], -v["n"][0]                     # along the boundary
        q = np.array([[v["x"], v["y"], 0.0],
                      [v["x"] + 7.3 * v["n"][0] + 3.1 * t[0], v["y"] + 7.3 * v["n"][1] + 3.1 * t[1], 1.0],
                      [v["x"] - 2.9 * v["n"][0] - 5.7 * t[0], v["y"] - 2.9 * v["n"][1] - 5.7 * t[1], 2.0]])
        f = lambda P: P[:, 0] * v["n"][0] + P[:, 1] * v["n"][1]
        return bool(np.allclose(f(op(q)), f(q), atol=1e-9, rtol=0))

    def signature(self, scale_free: bool = False):
        """Hashable description of the soil for the solution cache.  With
        scale_free (uniform soil) the resistivity is left out: the currents do
        not depend on it and the resistances are proportional to it."""
        if self.uniform:
            return ("uniform",) if scale_free else ("uniform", self.rho1)
        if self.vertical:
            v = self.vertical
            return ("vertical", self.rho1, v["rho"], v["n"], v["c"])
        return ("layers", tuple(self.rhos), tuple(self.interfaces),
                getattr(self, "N", 0), getattr(self, "N_tail", 0))

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
        if self.vertical:
            v = self.vertical
            return (f"Two-region soil: ρ = {self.rho1:g} Ω·m and ρ' = {v['rho']:g} Ω·m beyond "
                    f"the vertical boundary through ({v['x']:g}, {v['y']:g}) m, normal at "
                    f"{v['angle']:g}°, K = {self.K:+.3f} (exact images)")
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


def graded_fraction(u: float, g: float) -> float:
    """Position (fraction of the side) of a graded grid line; see add_grid."""
    return u - g * math.sin(2.0 * math.pi * u) / (2.0 * math.pi)


# Shortest segment of a bare conductor, in conductor radii (1.9.1).  The
# thin-wire kernel puts the current on the axis and the field point on the
# surface; below about four radii its matrix loses positive definiteness and
# leakage currents turn negative (a 6 m rod of 50 mm radius: below four radii
# R jumps about erratically, by up to 9 %), and where conductors cross the
# trouble starts near six.  Ten radii, the limit the end grading and the
# automatic refinement already keep, leaves every case clean.
MIN_SEG_RADII = 10.0


def _grade_cuts(at1: bool, at2: bool, L: float, radius: float, levels: int):
    """Sub-intervals of [0, 1] for one segment: halved `levels` times towards
    a free conductor end (both ends when the segment is the whole
    conductor), never shorter than ten conductor radii, so the thin-wire
    kernel stays valid."""
    if not (at1 or at2):
        return [(0.0, 1.0)]
    lv = int(levels)
    while lv > 0 and L * 0.5 ** (lv + (1 if at1 and at2 else 0)) < MIN_SEG_RADII * radius:
        lv -= 1
    if lv <= 0:
        return [(0.0, 1.0)]
    fr = [0.5 ** k for k in range(lv, 0, -1)]            # 1/8, 1/4, 1/2
    if at1 and at2:
        cuts = sorted(set([0.0, 1.0, 0.5] + [f / 2 for f in fr]
                          + [1.0 - f / 2 for f in fr]))
    elif at1:
        cuts = [0.0] + fr + [1.0]
    else:
        cuts = [0.0] + [1.0 - f for f in reversed(fr)] + [1.0]
    return list(zip(cuts[:-1], cuts[1:]))


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
    Laplace's equation in two horizontal layers:

      G11  source and field in layer 1  ρ₁/4π Σ Kⁿ (four images per n)
      G21  field in layer 2             ρ₁(1+K)/4π Σ Kⁿ
      G12  source in layer 2            ρ₁(1+K)/4π Σ Kⁿ   (reciprocal)
      G22  both in layer 2              ρ₂/4π [1/r − K/r(2h−z') ...]
    """
    cache = soil.__dict__.setdefault("_terms", {})
    T = cache.get((src_layer, fld_layer))
    if T is None:
        T = cache[(src_layer, fld_layer)] = _image_terms(soil, src_layer, fld_layer)
    return T


def _image_terms(soil, src_layer, fld_layer):
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


# Dense solution up to this many unknowns (after the symmetry reduction);
# the compressed H-matrix solution above it (1.8.7).
DENSE_LIMIT = 4000
# Work (points x segments x image terms) above which a potential map is
# summed through the cluster trees (1.8.7).
TREE_WORK = 4e8
# Segment cap of the discretisation, raised in 1.8.7 from 4000 (the API
# default) now that large models are solved in compressed form.
MAX_SEGMENTS = 20000

_CACHE = {}
_CACHE_ORDER = []
_CACHE_SIZE = 12


def _CACHE_GET(key):
    if key is None or key not in _CACHE:
        return None
    _CACHE_ORDER.remove(key)
    _CACHE_ORDER.append(key)
    return _CACHE[key]


def _CACHE_PUT(key, val):
    if key in _CACHE:
        _CACHE_ORDER.remove(key)
    _CACHE[key] = val
    _CACHE_ORDER.append(key)
    while len(_CACHE_ORDER) > _CACHE_SIZE:
        _CACHE.pop(_CACHE_ORDER.pop(0), None)


def clear_cache():
    """Forget the stored solutions (Network.solve reuses them by default)."""
    _CACHE.clear()
    _CACHE_ORDER.clear()


def _full_cheaper(m, n, T, q=4):
    """True when evaluating an m × n block in full (m n q T kernel terms in
    one vectorised call) costs less than the about 30 row and column calls
    of an adaptive cross approximation, each with its Python overhead."""
    k = 1e-8                                   # s per kernel term, vectorised
    return m * n * q * T * k < 30.0 * (1e-4 + 0.5 * (m + n) * q * T * k)


class _CellIndex:
    """Points in square plan cells of side `size`: near(p) returns every
    point within `size` of p (and some a little further)."""

    def __init__(self, xy, size):
        self.xy = np.asarray(xy, float)
        self.size = float(size) if size > 0 else 1.0
        self.o = self.xy.min(axis=0) if len(self.xy) else np.zeros(2)
        ij = np.floor((self.xy - self.o) / self.size).astype(np.int64)
        self.cells = {}
        order = np.lexsort((ij[:, 1], ij[:, 0]))
        keys = ij[order]
        if len(order):
            brk = np.nonzero(np.any(np.diff(keys, axis=0) != 0, axis=1))[0] + 1
            for g in np.split(np.arange(len(order)), brk):
                self.cells[(int(keys[g[0], 0]), int(keys[g[0], 1]))] = np.sort(order[g])

    def near(self, p):
        i, j = np.floor((np.asarray(p, float) - self.o) / self.size).astype(np.int64)
        parts = [self.cells[(a, b)] for a in (i - 1, i, i + 1) for b in (j - 1, j, j + 1)
                 if (a, b) in self.cells]
        return np.sort(np.concatenate(parts)) if parts else np.zeros(0, int)


def _image_sum(r2, zf, zs, terms):
    """Sum of coef / sqrt(r2 + (zf − (sgn·zs + shift))²) over the image
    terms.  Small arrays are summed over all terms in one broadcast (the
    compressed solver evaluates the matrix a row or a column at a time,
    where a Python loop over 240 two-layer images would dominate); large
    ones term by term, to bound the memory."""
    T = len(terms)
    if T == 0:
        return np.zeros_like(r2)
    if r2.size * T <= 2_000_000 and T > 2:
        tc = np.array(terms, float)
        coef, sgn, shift = tc[:, 0], tc[:, 1], tc[:, 2]
        zi = zs[..., None] * sgn + shift
        dz = zf[..., None] - zi
        return (coef / np.sqrt(np.maximum(r2[..., None] + dz * dz, 1e-24))).sum(axis=-1)
    acc = np.zeros(np.broadcast_shapes(r2.shape, zs.shape))
    for coef, sgn, shift in terms:
        zi = sgn * zs + shift
        acc += coef / np.sqrt(np.maximum(r2 + (zf - zi) ** 2, 1e-24))
    return acc


def _layer_table(soil, src_layer, fl, a, b, rmax):
    """Two-layer soil: the image sum between a field depth a and a source
    depth b as a function of the horizontal distance only (1.8.7).

    The terms whose image lies at the field depth (the direct term of a
    same-depth pair) are left out and summed exactly by the caller; the
    rest is smooth on the scale of the smallest vertical offset Δ_min of an
    image, and is tabulated on u = asinh(r/Δ_min) with its derivative, for
    cubic Hermite interpolation (step 0.01 in u: relative error below 1e-10).
    A grid at one depth then costs the two-layer series once per table, not
    once per pair — the series has 4N + 4 terms, N up to 60."""
    tabs = soil.__dict__.setdefault("_tables", {})
    key = (src_layer, fl, round(float(a), 9), round(float(b), 9))
    tab = tabs.get(key)
    if tab is not None and tab["rmax"] >= rmax:
        return tab
    terms = image_terms(soil, src_layer, fl)
    c = np.array([t[0] for t in terms])
    dz = np.array([a - (t[1] * b + t[2]) for t in terms])
    exact = np.abs(dz) < 1e-9
    cs, ds = c[~exact], dz[~exact]
    dmin = max(float(np.abs(ds).min()) if ds.size else 1.0, 1e-3)
    top = max(1.3 * rmax, 20.0 * dmin, 1.0)
    du = 0.01
    umax = math.asinh(top / dmin)
    u = np.linspace(0.0, umax, int(math.ceil(umax / du)) + 2)
    du = float(u[1] - u[0])
    rh = dmin * np.sinh(u)
    R = np.zeros_like(u)
    dR = np.zeros_like(u)
    for k in range(0, len(cs), 64):
        cc, dd = cs[k:k + 64], ds[k:k + 64]
        D2 = rh[:, None] ** 2 + dd[None, :] ** 2
        inv = 1.0 / np.sqrt(D2)
        R += (cc * inv).sum(axis=1)
        dR += (-cc * rh[:, None] * inv ** 3).sum(axis=1)
    dR *= dmin * np.cosh(u)                   # d/du
    tab = dict(rmax=top, dmin=dmin, du=du, R=R, dR=dR, u_n=len(u),
               exact=[(float(ci), float(di)) for ci, di in zip(c[exact], dz[exact])])
    tabs[key] = tab
    return tab


def _table_eval(tab, rh):
    u = np.arcsinh(rh / tab["dmin"]) / tab["du"]
    k = np.clip(np.floor(u).astype(np.int64), 0, tab["u_n"] - 2)
    t = u - k
    t2, t3 = t * t, t * t * t
    R, dR, du = tab["R"], tab["dR"], tab["du"]
    return ((2 * t3 - 3 * t2 + 1) * R[k] + (t3 - 2 * t2 + t) * du * dR[k]
            + (-2 * t3 + 3 * t2) * R[k + 1] + (t3 - t2) * du * dR[k + 1])


def _image_sum_tabled(soil, src_layer, fl, r2, zf, zs, terms):
    """_image_sum for a two-layer soil, with the pairs whose field point is
    at the most common field depth and whose source is at the most common
    source depth taken from a _layer_table (a grid at one depth, or the
    surface seen from it); the rest (rods, say) summed term by term.  Works
    for a source row shared by every field point (zs (1, Q)) and for one row
    per field point (zs (M, Q))."""
    def mode(a):
        a = a.ravel()
        a = a[::max(1, a.size // 4000)]
        v, c = np.unique(a, return_counts=True)
        return v[np.argmax(c)]

    a_ = mode(zf)
    d_ = mode(zs)
    m = (zf == a_) & (zs == d_)                 # broadcast to r2's shape
    if not m.any():
        return _image_sum(r2, zf, zs, terms)
    out = np.empty_like(r2)
    rr = r2[m]
    tab = _layer_table(soil, src_layer, fl, a_, d_, float(np.sqrt(rr.max())))
    v = _table_eval(tab, np.sqrt(rr))
    for c, dz in tab["exact"]:
        v += c / np.sqrt(np.maximum(rr + dz * dz, 1e-24))
    out[m] = v
    if not m.all():
        k = ~m
        ZF = np.broadcast_to(zf, r2.shape)[k]
        ZS = np.broadcast_to(zs, r2.shape)[k]
        out[k] = _image_sum(r2[k], ZF, ZS, terms)
    return out


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
        self.raw_seg = {}      # raw index -> fixed segment length (plate strips, 1.9.0)
        self.plates = []       # dict(...) per plate, for the results
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

    def add_grid(self, Lx, Ly, D, depth, radius, x0=0.0, y0=0.0, tag="grid",
                 grading: float = 0.0, n_x: int | None = None, n_y: int | None = None):
        """A rectangular mesh.  `grading` g (0 ≤ g < 1) draws the conductors
        towards the edges: a line at fraction u of the width sits at
        L·(u − g·sin(2πu)/2π), so the edge meshes are (1 − g) times the mean
        spacing and the centre ones (1 + g) times it — the unequal spacing
        that evens out the mesh voltages, which are highest in the corner
        meshes of a uniform grid.  n_x, n_y override the counts from D."""
        nx = int(n_x) if n_x else max(2, int(round(Lx / D)) + 1)      # lines parallel to y
        ny = int(n_y) if n_y else max(2, int(round(Ly / D)) + 1)      # lines parallel to x
        g = float(grading or 0.0)
        if not 0.0 <= g < 1.0:
            raise ValueError("Grid grading must be at least 0 and below 1.")
        for j in range(nx):
            x = x0 + Lx * graded_fraction(j / (nx - 1), g)
            self.add_conductor((x, y0, depth), (x, y0 + Ly, depth), radius, tag)
        for i in range(ny):
            y = y0 + Ly * graded_fraction(i / (ny - 1), g)
            self.add_conductor((x0, y, depth), (x0 + Lx, y, depth), radius, tag)
        return self

    def add_rod(self, x, y, top_depth, length, radius, tag="rod"):
        self.add_conductor((x, y, top_depth), (x, y, top_depth + length),
                           radius, tag)
        return self

    def add_plate(self, corner, u, v, strips=None, tag="plate"):
        """A thin rectangular metal plate (1.9.0): the corner and the two edge
        vectors u, v (3-D, metres), |u| ≥ |v| after ordering.

        The plate is cut along its long side into `strips` parallel strips
        whose widths follow a cosine (Chebyshev) spacing across the short
        side, narrow at the edges where the charge density of a plate rises
        as d^(-1/2).  Each strip is a conductor on its centre line of radius
        w/(2π): an infinite array of wires of radius s/(2π) at spacing s
        carries charge exactly like the plane it fills (the 2-D field of the
        array, −ln[2 cosh(2πz/s) − 2 cos(2πy/s)], has no offset from that of
        a plane when r = s/2π).  The strips are cut into segments of the
        short side divided by `strips`, without end grading (a segment stays
        about four radii long, inside the thin-wire kernel's range).
        Against an independent panel solution (Read 2004 for the square,
        C = 0.3667896·4πε₀·a) the resistance is high by about 50/n² % —
        0.2–0.3 % at 16 strips — for squares and strips 1:1 to 10:1,
        horizontal or vertical, uniform or two-layer soil."""
        c = np.array(corner, float)
        u = np.array(u, float)
        v = np.array(v, float)
        if np.linalg.norm(v) > np.linalg.norm(u):
            u, v = v, u
        Lu, Lv = float(np.linalg.norm(u)), float(np.linalg.norm(v))
        if Lv <= 0 or Lu <= 0:
            raise ValueError("A plate needs a positive length and width.")
        if abs(float(u @ v)) > 1e-9 * Lu * Lv:
            raise ValueError("The edges of a plate must be at right angles.")
        n = int(strips or 16)
        if not 4 <= n <= 96:
            raise ValueError("A plate takes between 4 and 96 strips.")
        k = np.arange(n + 1)
        t = 0.5 - 0.5 * np.cos(np.pi * k / n)
        t[n - k[k < n / 2]] = 1.0 - t[k[k < n / 2]]       # exactly symmetric
        w = np.diff(t)
        w = 0.5 * (w + w[::-1])
        mid = t[:-1] + 0.5 * w
        seg = Lv / n
        for tm, tw in zip(mid, w):
            a = c + v * tm
            self.add_conductor(a, a + u, tw * Lv / (2.0 * math.pi), tag)
            self.raw_seg[len(self.raw) - 1] = seg
        self.plates.append(dict(corner=c.tolist(), u=u.tolist(), v=v.tolist(),
                                strips=n, length=Lu, width=Lv, net=self._net))
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
    def discretise(self, target: float = 2.0, max_segments: int = 3000,
                   grade_ends: bool = False, levels: int = 3):
        """Chop every conductor into segments of about `target` metres.

        grade_ends : split the segment at each free end of a conductor
                     geometrically (1/2, 1/4, ... of its length, `levels`
                     times).  The leakage-current density rises steeply
                     towards the end of a conductor, which is where the grid
                     corner and its touch and step voltages are; a uniform
                     mesh smears that peak and reads the corner touch voltage
                     low.  On the IEEE 80 Annex B grid with 20 rods the
                     1 m-outside-the-corner touch voltage reads 1173 V with
                     uniform 3 m segments, 1201 V graded (N = 840) and
                     1216 V uniform at 0.5 m (N = 3380): grading buys most of
                     the refinement at a quarter of the unknowns (1.8.0).
        """
        fixed = sum(math.ceil(np.linalg.norm(np.array(self.raw[i][1]) - np.array(self.raw[i][0]))
                              / L - 1e-9) for i, L in self.raw_seg.items())
        total = sum(np.linalg.norm(np.array(b) - np.array(a))
                    for i, (a, b, *_) in enumerate(self.raw) if i not in self.raw_seg)
        self.coarsened = None
        room = max_segments - fixed
        if self.raw_seg and room < (1 if total > 0 else 0):
            raise ValueError(f"The plates alone need {fixed} segments, more than the "
                             f"limit of {max_segments}: use fewer strips or raise the limit.")
        if total > 0 and total / max(target, 1e-6) > room:
            self.coarsened = dict(requested=float(target),
                                  used=float(total / room),
                                  max_segments=int(max_segments))
            target = total / room
        self.target = float(target)
        self.graded = bool(grade_ends)
        self.thick = None          # conductors kept at MIN_SEG_RADII (1.9.1)
        thick_n, thick_a, thick_l = 0, 0.0, 0.0
        self.segments = []
        self.seg_raw = []          # raw conductor of each segment (1.8.9)
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
            # split at the layer interfaces (and a vertical soil boundary)
            # so that every segment lies in one soil zone and sees that
            # zone's Green's function
            s = self.soil
            cuts = sorted([0.0, 1.0] + s.plane_cuts(a, b))
            for t0, t1 in zip(cuts[:-1], cuts[1:]):
                q1 = a + (b - a) * t0
                q2 = a + (b - a) * t1
                Lq = float(np.linalg.norm(q2 - q1))
                # a thick (concrete-encased) conductor keeps its segments
                # longer than its radius, as the thin-wire kernel requires
                tg = max(target, 1.5 * rad) if shell > 0 else target
                fx = self.raw_seg.get(ir)
                if fx:
                    tg = fx                       # a plate strip keeps its own length
                elif shell == 0 and tg < MIN_SEG_RADII * rad:
                    # a thick bare conductor: no segment shorter than ten
                    # radii (the thin-wire kernel's range, 1.9.1); a piece
                    # shorter than that stays one segment
                    if Lq > tg * (1 + 1e-9):      # it would have been cut finer
                        thick_n += 1
                        thick_a = max(thick_a, rad)
                        thick_l = max(thick_l, min(MIN_SEG_RADII * rad, Lq))
                    tg = MIN_SEG_RADII * rad
                n = max(1, int(math.ceil(Lq / tg - 1e-9)))
                for k in range(n):
                    p1 = q1 + (q2 - q1) * k / n
                    p2 = q1 + (q2 - q1) * (k + 1) / n
                    at1 = grade_ends and shell == 0 and not fx and t0 == 0.0 and k == 0
                    at2 = grade_ends and shell == 0 and not fx and t1 == 1.0 and k == n - 1
                    for c0, c1 in _grade_cuts(at1, at2, float(np.linalg.norm(p2 - p1)),
                                              rad, levels):
                        r1 = p1 + (p2 - p1) * c0
                        r2 = p1 + (p2 - p1) * c1
                        lay = s.zone_of(0.5 * (r1 + r2))
                        self.segments.append(Segment(r1, r2, rad, tag, lay, nk, shell))
                        self.seg_raw.append(ir)
        if thick_n:
            self.thick = dict(pieces=int(thick_n), radius=float(thick_a), length=float(thick_l),
                              requested=float(target))
        return len(self.segments)

    # -- Green's function --------------------------------------------------
    def _green_terms(self, field, src_pts, skip_direct=False, src_layer=1,
                     min_rh2=0.0):
        """Sum of image contributions between field points and source points.

        field     : (M, 3) array of field points (any layer or region)
        src_pts   : (Q, 3) array of source quadrature points, all in
                    `src_layer` (the soil zone: layer, or region of a
                    two-region soil)
        returns   : (M, Q) array of potential coefficients (V per A per unit
                    current density weight -- caller applies quadrature weights)
        skip_direct drops the singular 1/r term of a same-layer pair (the
        caller supplies it analytically for the self term).
        """
        return self._green(field, np.asarray(src_pts, float)[None, :, :], src_layer,
                           skip_direct, min_rh2 if min_rh2 else None)

    def _green_pairs(self, field, src, src_layer=1, min_rh2=None):
        """Image sum for P (field point, source points) pairs: field (P, 3),
        src (P, Q, 3), all sources in `src_layer`; returns (P, Q).  The
        pairwise twin of _green_terms (no self-term handling)."""
        if min_rh2 is not None:
            min_rh2 = np.asarray(min_rh2, float)[:, None]
        return self._green(field, src, src_layer, False, min_rh2)

    def _green(self, field, src, src_layer, skip_direct, min_rh2):
        """Common body of _green_terms (src (1, Q, 3), shared by every field
        point) and _green_pairs (src (M, Q, 3), one row per field point)."""
        s = self.soil
        field = np.asarray(field, float)
        dx = field[:, None, 0] - src[:, :, 0]
        dy = field[:, None, 1] - src[:, :, 1]
        rh2 = dx * dx + dy * dy
        if min_rh2 is not None:
            rh2 = np.maximum(rh2, min_rh2)
        zf = field[:, 2]
        zs = src[:, :, 2]
        shared = src.shape[0] == 1 and len(field) != 1

        def rows(a, m):
            return a if shared else a[m]

        out = np.zeros_like(rh2)
        if s.vertical:
            return self._green_vertical(field, src, src_layer, skip_direct, min_rh2, rh2)
        if s.three:
            s.prepare(max(float(zf.max()), float(zs.max())),
                      float(np.sqrt(rh2.max())) if rh2.size else 1.0)
            lay = s.zones_of(field)
            c = s.rhos[src_layer - 1] / (4.0 * math.pi)
            for fl in range(1, len(s.rhos) + 1):
                m = lay == fl
                if m.any():
                    out[m] = c * s.green.sum_terms(src_layer, fl, rh2[m],
                                                   zf[m][:, None], rows(zs, m), skip_direct)
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
            zsm = rows(zs, m)
            r2 = rh2[m]
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
            if skip_direct:
                terms = [t for t in terms if not (t[1] == 1 and t[2] == 0.0 and fl == src_layer)]
            if not skip_direct and s.N >= 3 and r2.size >= 256:
                acc = _image_sum_tabled(s, src_layer, fl, r2, zfm, zsm, terms)
            else:
                acc = _image_sum(r2, zfm, zsm, terms)
            if s.N_tail > s.N:
                acc += s.tail_amplitude(src_layer, fl) * s.tail(np.sqrt(r2))
            out[m] = acc
        return out

    def _green_vertical(self, field, src, src_layer, skip_direct, min_rh2, rh2):
        """Two uniform regions side by side, separated by a vertical plane
        (1.8.7).  With K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁) and K_s = K for a source in
        region 1, −K in region 2, the exact solution (images in the plane
        and in the air surface, which commute because they are
        perpendicular) is

          field in the source's region   ρ_s/4π [1/r + 1/r_a + K_s (1/r' + 1/r'_a)]
          field across the boundary      ρ_s(1 + K_s)/4π [1/r + 1/r_a]

        r, r' : distance to the source and to its mirror image in the
        boundary; the suffix a marks the air image (z → −z).  The two sides
        agree on the boundary (ρ₁(1 + K) = ρ₂(1 − K)) and so do the normal
        current densities, and the function is reciprocal."""
        s = self.soil
        v = s.vertical
        n0, n1 = v["n"]
        rho_s = s.rhos[src_layer - 1]
        Ks = s.K if src_layer == 1 else -s.K
        zf = field[:, 2][:, None]
        zs = src[:, :, 2]
        reg = s.zones_of(field)[:, None]
        same = reg == src_layer
        d_zm = (zf - zs) ** 2
        d_zp = (zf + zs) ** 2
        # skip_direct: True drops the direct term (the self term supplies
        # it); 2 drops the mirror image in the boundary as well
        # (_self_mirror supplies it)
        direct = 0.0 if skip_direct else 1.0
        g_dir = (direct / np.sqrt(np.maximum(rh2 + d_zm, 1e-24))
                 + 1.0 / np.sqrt(np.maximum(rh2 + d_zp, 1e-24)))
        # mirror image of the sources in the boundary plane
        off = src[:, :, 0] * n0 + src[:, :, 1] * n1 - v["c"]
        mx = src[:, :, 0] - 2.0 * off * n0
        my = src[:, :, 1] - 2.0 * off * n1
        ex = field[:, None, 0] - mx
        ey = field[:, None, 1] - my
        rm2 = ex * ex + ey * ey
        if min_rh2 is not None:
            rm2 = np.maximum(rm2, min_rh2)
        g_img = ((0.0 if skip_direct == 2 else 1.0) / np.sqrt(np.maximum(rm2 + d_zm, 1e-24))
                 + 1.0 / np.sqrt(np.maximum(rm2 + d_zp, 1e-24)))
        c = rho_s / (4.0 * math.pi)
        return np.where(same, c * (g_dir + Ks * g_img), c * (1.0 + Ks) * g_dir)

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
    def build_matrix(self, near_factor: float = 8.0, nf: int = 6, nq_near: int = 10,
                     mid_rule=(3, 4), cols=None):
        """Assemble the potential-coefficient matrix (or, with `cols`, only
        those of its columns: an (n, len(cols)) array).

        Far pairs use mid-point collocation (fast).  Near pairs -- including
        the pair formed by a segment and its own air-surface image -- are
        re-evaluated with a double (Galerkin) Gauss quadrature, because
        collocation under-estimates the average potential when the source is
        close, which would otherwise bias the earth resistance low.
        """
        segs = self.segments
        n = len(segs)
        cols = np.arange(n) if cols is None else np.asarray(cols, int)
        mids = np.array([s.mid for s in segs])
        P = np.zeros((n, len(cols)))
        self._prepare_soil()
        # ---- pass 1: mid-point collocation ------------------------------
        # Every pair closer than near_factor segment lengths (8 by default)
        # is recomputed by double quadrature in pass 2, so this pass only has
        # to be right for pairs at least that far apart, where a 4-point rule
        # is exact to about 1e-9 (1.8.4: it used 12 points for every field
        # point of a segment with any near neighbour, i.e. for nearly all).
        for c, j in enumerate(cols):
            P[:, c] = self._coeff_column(mids, segs[j], 4)
        # ---- pass 2 and the exact self terms ----------------------------
        for c, j, idx, vals in self._near_values(cols, near_factor, nf, nq_near, mid_rule):
            P[idx, c] = vals
        return P

    def _prepare_soil(self):
        if self.soil.three:
            ends = np.array([q for s in self.segments for q in (s.p1, s.p2)])
            ext = float(np.hypot(np.ptp(ends[:, 0]), np.ptp(ends[:, 1])))
            # the surface map extends a margin beyond the electrodes
            self.soil.prepare(float(ends[:, 2].max()), ext + 60.0)

    def _near_reach(self, near_factor=8.0):
        lens = np.array([s.length for s in self.segments])
        return near_factor * max(float(lens.max()), float(lens.mean()))

    def _near_values(self, cols, near_factor=8.0, nf=6, nq_near=10, mid_rule=(3, 4)):
        """Pass 2 of the assembly: for every column j in `cols`, the rows of
        the segments nearer than near_factor segment lengths (directly or
        through the air image), with their double-quadrature coefficients and
        the exact self term.  Yields (position in cols, j, rows, values)."""
        segs = self.segments
        mids = np.array([s.mid for s in segs])
        lens = np.array([s.length for s in segs])
        tf, wf = _gauss(nf)
        P1 = np.array([s.p1 for s in segs])
        P2 = np.array([s.p2 for s in segs])
        FQ = P1[:, None, :] + (P2 - P1)[:, None, :] * tf[None, :, None]   # (n, nf, 3)
        lmean = float(lens.mean())
        cells = _CellIndex(mids[:, :2], near_factor * max(float(lens.max()), lmean))
        for c, j in enumerate(cols):
            sj = segs[j]
            reach = near_factor * max(sj.length, lmean)
            cand = cells.near(sj.mid[:2])
            dx = mids[cand, 0] - sj.mid[0]
            dy = mids[cand, 1] - sj.mid[1]
            rh = np.hypot(dx, dy)
            d_direct = np.sqrt(rh ** 2 + (mids[cand, 2] - sj.mid[2]) ** 2)
            d_image = np.sqrt(rh ** 2 + (mids[cand, 2] + sj.mid[2]) ** 2)
            keep = (d_direct < reach) | (d_image < reach)
            idx = cand[keep]
            d_direct, d_image = d_direct[keep], d_image[keep]
            vals = np.zeros(idx.size)
            if idx.size:
                # 1.8.4: the full nf × nq_near rule only where the pair is within
                # 2.5 segment lengths (of either segment); beyond that a 3 × 4
                # Galerkin rule agrees with it to about 1e-6 at a fifth of the cost.
                lij = np.maximum(lens[idx], sj.length)
                dmin = np.minimum(d_direct, d_image)
                close = dmin < 2.5 * lij if mid_rule else np.ones(idx.size, bool)
                mf, mq = mid_rule or (nf, nq_near)
                for msk, nfx, nqx in ((close, nf, nq_near), (~close, mf, mq)):
                    sel = idx[msk]
                    if sel.size == 0:
                        continue
                    if nfx == nf:
                        pts, wq = FQ[sel].reshape(-1, 3), wf
                    else:
                        t3, wq = _gauss(nfx)
                        pts = (P1[sel][:, None, :] + (P2[sel] - P1[sel])[:, None, :]
                               * t3[None, :, None]).reshape(-1, 3)
                    col = self._coeff_column(pts, sj, nqx, skip_direct=False,
                                             reduced=sj.shell > 0)
                    vals[msk] = col.reshape(len(sel), nfx) @ wq
            # ---- exact self term ----------------------------------------
            L, a = sj.length, sj.radius
            rho_j = self.soil.rhos[sj.layer - 1]
            if sj.shell > 0:
                # exact average over a tube (thick encasement, L ~ r_c)
                self_direct = rho_j / (4.0 * math.pi * L * L) * 2.0 * (
                    L * math.asinh(L / a) - math.sqrt(L * L + a * a) + a)
            else:
                self_direct = rho_j / (2.0 * math.pi * L) * (math.log(2.0 * L / a) - 1.0)
            tfp = sj.p1[None, :] + (sj.p2 - sj.p1)[None, :] * tf[:, None]
            mirror = self._self_mirror(sj, self_direct)
            img = self._coeff_column(tfp, sj, 16,
                                     skip_direct=(2 if mirror is not None else True)) @ wf
            sv = self_direct + float(img) + sj.shell / L + (mirror or 0.0)
            at = np.nonzero(idx == j)[0]
            if at.size:
                vals[at[0]] = sv
            else:                                         # pragma: no cover
                idx = np.append(idx, j)
                vals = np.append(vals, sv)
            yield c, j, idx, vals

    def _self_mirror(self, sj, self_direct):
        """Two-region soil: the coefficient of a segment parallel to the
        vertical boundary on its own mirror image, in closed form (the image
        is a parallel line 2d away, d the distance to the boundary, which a
        Gauss rule would resolve badly when d is small against the length).
        A segment on the boundary (2d below its radius) coincides with its
        image: the coefficient is K times its own direct self term, so that
        it sees ρ(1 + K) = 2ρρ'/(ρ + ρ') on both sides — the exact result
        for an electrode in the plane.  None when it does not apply."""
        s = self.soil
        if not s.vertical:
            return None
        v = s.vertical
        nrm = np.array([v["n"][0], v["n"][1], 0.0])
        if abs(float(nrm @ (sj.p2 - sj.p1))) > 1e-9 * max(sj.length, 1e-9):
            return None
        d = abs(float(nrm @ sj.mid) - v["c"])
        Ks = s.K if sj.layer == 1 else -s.K
        L, a = sj.length, sj.radius
        D = 2.0 * d
        if D < a:
            return Ks * self_direct
        rho_s = s.rhos[sj.layer - 1]
        return Ks * rho_s / (4.0 * math.pi) * 2.0 / (L * L) * (
            L * math.asinh(L / D) - math.sqrt(L * L + D * D) + D)

    def _collocation(self, rows, cols):
        """Pass-1 (4-point collocation) coefficients for the rows x cols
        block, evaluated directly (the compressed solver's entry function)."""
        segs = self.segments
        rows = np.asarray(rows, int)
        cols = np.asarray(cols, int)
        out = np.zeros((rows.size, cols.size))
        if not rows.size or not cols.size:
            return out
        t, w = _gauss(4)
        f = self._mids[rows]
        for lay in np.unique(self._lay[cols]):
            k = np.nonzero(self._lay[cols] == lay)[0]
            cj = cols[k]
            q = (self._P1[cj][:, None, :] + (self._P2[cj] - self._P1[cj])[:, None, :]
                 * t[None, :, None]).reshape(-1, 3)
            G = self._green_terms(f, q, False, int(lay))
            out[:, k] = G.reshape(rows.size, cj.size, 4) @ w
        return out

    def _terms_estimate(self):
        """Image terms per Green's-function evaluation (for the cost model of
        the compressed solver)."""
        s = self.soil
        if s.vertical:
            return 4
        if s.three:
            return 60
        if s.uniform:
            return 2
        # two layers: a grid at one depth is summed from a table
        # (_layer_table), at the cost of about ten terms
        return 10 if s.N >= 3 else 4 * s.N + 4

    def _cache_arrays(self):
        segs = self.segments
        self._mids = np.array([s.mid for s in segs])
        self._P1 = np.array([s.p1 for s in segs])
        self._P2 = np.array([s.p2 for s in segs])
        self._lay = np.array([s.layer for s in segs])

    # -- symmetry ------------------------------------------------------------
    def symmetry(self, tol: float = 1e-6):
        """Mirror and rotation symmetries of the discretised model (1.8.7).

        A plan transformation (mirror in x, in y or in a diagonal, rotation
        by 90° or 180° about the centre of the layout) is a symmetry when it
        maps every segment onto a segment of the same radius, soil zone,
        network and concrete shell, and maps the soil onto itself.  Every
        network then maps onto itself, so with the injections unchanged the
        solution is the same on all the segments of an orbit.  Returns None,
        or dict(order, ops, orbit (n,), reps, sizes)."""
        segs = self.segments
        n = len(segs)
        self._sym_ops = {}
        if n < 8:
            return None
        P1 = np.array([s.p1 for s in segs])
        P2 = np.array([s.p2 for s in segs])
        allp = np.vstack([P1, P2])
        lo, hi = allp.min(axis=0), allp.max(axis=0)
        cx, cy = 0.5 * (lo[0] + hi[0]), 0.5 * (lo[1] + hi[1])
        ext = float(max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 1.0))
        q = tol * ext
        attr = [(round(s.radius, 12), s.layer, s.net, round(s.shell, 12)) for s in segs]

        def key_of(A, B):
            a = np.rint(A / q).astype(np.int64)
            b = np.rint(B / q).astype(np.int64)
            sw = (a[:, 0] > b[:, 0]) | ((a[:, 0] == b[:, 0]) & ((a[:, 1] > b[:, 1]) |
                                         ((a[:, 1] == b[:, 1]) & (a[:, 2] > b[:, 2]))))
            lo_ = np.where(sw[:, None], b, a)
            hi_ = np.where(sw[:, None], a, b)
            return [(tuple(l), tuple(h), at) for l, h, at in zip(lo_.tolist(), hi_.tolist(), attr)]

        base = {k: i for i, k in enumerate(key_of(P1, P2))}
        if len(base) != n:
            return None                       # coincident segments: do not reduce

        def op_mx(P):
            Q = P.copy(); Q[:, 0] = 2 * cx - P[:, 0]; return Q

        def op_my(P):
            Q = P.copy(); Q[:, 1] = 2 * cy - P[:, 1]; return Q

        def op_d1(P):
            Q = P.copy(); Q[:, 0] = cx + (P[:, 1] - cy); Q[:, 1] = cy + (P[:, 0] - cx); return Q

        def op_d2(P):
            Q = P.copy(); Q[:, 0] = cx - (P[:, 1] - cy); Q[:, 1] = cy - (P[:, 0] - cx); return Q

        def op_r90(P):
            Q = P.copy(); Q[:, 0] = cx - (P[:, 1] - cy); Q[:, 1] = cy + (P[:, 0] - cx); return Q

        def op_r180(P):
            Q = P.copy(); Q[:, 0] = 2 * cx - P[:, 0]; Q[:, 1] = 2 * cy - P[:, 1]; return Q

        found = []
        for name, op in (("mirror x", op_mx), ("mirror y", op_my), ("diagonal", op_d1),
                         ("anti-diagonal", op_d2), ("rotation 90°", op_r90),
                         ("rotation 180°", op_r180)):
            if not self.soil.preserved_by(op):
                continue
            perm = np.empty(n, int)
            ok = True
            for i, k in enumerate(key_of(op(P1), op(P2))):
                j = base.get(k)
                if j is None:
                    ok = False
                    break
                perm[i] = j
            if ok:
                found.append((name, perm))
                self._sym_ops = getattr(self, "_sym_ops", {})
                self._sym_ops[name] = op
        if not found:
            return None
        # the group generated by the symmetries found (at most 8 elements)
        group = [np.arange(n)]
        seen = {group[0].tobytes()}
        frontier = list(group)
        while frontier:
            nxt = []
            for g in frontier:
                for _, p in found:
                    h = p[g]
                    kb = h.tobytes()
                    if kb not in seen:
                        seen.add(kb)
                        group.append(h)
                        nxt.append(h)
            frontier = nxt
            if len(group) > 8:                 # pragma: no cover - cannot happen in plan
                return None
        G = np.array(group)                    # (|G|, n)
        orbit_min = G.min(axis=0)              # smallest index in each orbit
        reps, orbit = np.unique(orbit_min, return_inverse=True)
        sizes = np.bincount(orbit)
        return dict(order=len(group), ops=[nm for nm, _ in found], orbit=orbit,
                    reps=reps, sizes=sizes)

    # -- automatic local refinement ----------------------------------------------
    def refine_near(self, points, radius: float, levels: int = 1):
        """Halve every segment whose plan distance from one of `points`
        (x, y) is below `radius`, `levels` times; never below ten conductor
        radii (thin-wire kernel) or 1.5 shell radii (concrete).  Returns the
        number of segments split."""
        P = np.atleast_2d(np.asarray(points, float))[:, :2]
        split = 0
        for _ in range(int(levels)):
            out = []
            for sg in self.segments:
                a, b = sg.p1[:2], sg.p2[:2]
                d = b - a
                L2 = float(d @ d)
                if L2 > 0:
                    t = np.clip(((P - a) @ d) / L2, 0.0, 1.0)
                    near = np.hypot(*(P - (a + t[:, None] * d)).T).min()
                else:
                    near = np.hypot(*(P - a).T).min()
                lmin = 1.5 * sg.radius if sg.shell > 0 else MIN_SEG_RADII * sg.radius
                if near < radius and 0.5 * sg.length >= lmin:
                    m = 0.5 * (sg.p1 + sg.p2)
                    out.append(Segment(sg.p1, m, sg.radius, sg.tag, sg.layer, sg.net, sg.shell))
                    out.append(Segment(m, sg.p2, sg.radius, sg.tag, sg.layer, sg.net, sg.shell))
                    split += 1
                else:
                    out.append(sg)
            self.segments = out
        return split

    def auto_refine(self, ws_args: dict, tol: float = 0.01, max_levels: int = 4,
                    max_segments: int | None = None, radius: float | None = None):
        """Automatic accuracy control (1.8.8): solve, locate the worst touch
        and step voltages, halve the segments within `radius` of those points
        (and of their images under the model's symmetries, so the reduction
        is kept), and repeat until both change by less than `tol` (relative)
        from one level to the next, or `max_levels` refinements, or the
        segment limit.  Returns (solution, worst_touch_step result, history);
        history lists, per level, the segments, R_g, touch and step and the
        relative changes.  With three levels or more a geometric
        extrapolation of the last three values is reported as well."""
        cap = int(max_segments or MAX_SEGMENTS)
        sol = self.solve()
        ws = self.worst_touch_step(**ws_args)
        hist = [dict(level=0, segments=len(self.segments), Rg=float(sol["Rg"]),
                     touch=float(ws["touch_max"]), step=float(ws["step_max"]),
                     touch_at=list(ws["touch_at"]), step_at=list(ws["step_at"]))]
        st = float(ws_args.get("step", 1.0))
        if radius is None:
            # the conductors that set the potential within a step or an arm's
            # reach of the worst points: 3 m, or three local segment lengths
            radius = max(3.0, 2.0 * st + 1.0)
        converged = False
        for lev in range(1, int(max_levels) + 1):
            pts = [ws["touch_at"][:2], ws["step_at"][:2]]
            th = math.radians(float(ws.get("step_direction_deg", 0.0)))
            pts.append([ws["step_at"][0] + st * math.cos(th), ws["step_at"][1] + st * math.sin(th)])
            pts = self._with_images(np.array(pts, float))
            before = list(self.segments)
            if self.refine_near(pts, radius) == 0:
                break
            if len(self.segments) > cap:
                self.segments = before
                break
            sol = self.solve()
            ws = self.worst_touch_step(**ws_args)
            h = dict(level=lev, segments=len(self.segments), Rg=float(sol["Rg"]),
                     touch=float(ws["touch_max"]), step=float(ws["step_max"]),
                     touch_at=list(ws["touch_at"]), step_at=list(ws["step_at"]))
            p = hist[-1]
            h["touch_change"] = (h["touch"] - p["touch"]) / max(abs(h["touch"]), 1e-12)
            h["step_change"] = (h["step"] - p["step"]) / max(abs(h["step"]), 1e-12)
            hist.append(h)
            if abs(h["touch_change"]) < tol and abs(h["step_change"]) < tol:
                converged = True
                break
        out = dict(levels=hist, converged=converged, tol=float(tol), radius=float(radius))
        if len(hist) >= 3:
            for k in ("touch", "step", "Rg"):
                f0, f1, f2 = hist[-3][k], hist[-2][k], hist[-1][k]
                d1, d2 = f1 - f0, f2 - f1
                if d1 != 0 and 0 < d2 / d1 < 0.9:
                    q = d2 / d1
                    out[k + "_extrapolated"] = f2 + d2 * q / (1 - q)
        return sol, ws, out

    def _with_images(self, pts):
        """Points (x, y) together with their images under the symmetries
        the last symmetry() call found."""
        ops = list(getattr(self, "_sym_ops", {}).values())
        if not ops:
            return pts
        P = np.column_stack([pts, np.zeros(len(pts))])
        allp = [P]
        frontier = [P]
        for _ in range(3):                  # the group has at most 8 elements
            nxt = []
            for Q in frontier:
                for op in ops:
                    R = op(Q)
                    nxt.append(R)
            allp.extend(nxt)
            frontier = nxt
        A = np.vstack(allp)[:, :2]
        return np.unique(np.round(A, 9), axis=0)

    # -- solution --------------------------------------------------------------
    def solve(self, target: float = 2.0, method: str = "auto", symmetry: bool = True,
              dense_limit: int | None = None, tol: float = 1e-7, cache: bool = True):
        """Solve for the leakage currents and the network potentials.

        method       "auto" (default), "dense" or "hmatrix".  Auto uses the
                     dense solution when the number of unknowns — after the
                     symmetry reduction — is at most `dense_limit`
                     (DENSE_LIMIT, 4000), and the compressed H-matrix with
                     GMRES above it (1.8.7).
        symmetry     reduce the system by the mirror and rotation symmetries
                     of the model (exact; dense solution only)
        tol          accuracy of the compressed blocks and of GMRES
        cache        reuse a solution of the same discretised model and soil
                     (any current); for uniform soil the currents do not
                     depend on ρ at all, so one solution serves every ρ
        """
        if not self.segments:
            self.discretise(target)
        n = len(self.segments)
        m = len(self.nets)
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
        limit = int(dense_limit if dense_limit is not None else DENSE_LIMIT)
        sym = self.symmetry() if symmetry and method != "hmatrix" else None
        n_eff = len(sym["reps"]) if sym else n
        if method == "dense" or (method == "auto" and n_eff <= limit):
            how = "dense"
        elif method in ("auto", "hmatrix"):
            how = "hmatrix"
            sym = None
            n_eff = n
        else:
            raise ValueError("method must be 'auto', 'dense' or 'hmatrix'")
        scale_free = self.soil.uniform and all(sg.shell == 0 for sg in self.segments)
        key = self._solution_key(how, tol, scale_free) if cache else None
        hit = _CACHE_GET(key)
        info = dict(method=how, unknowns=n_eff, segments=n,
                    symmetry=(sym["order"] if sym else 1),
                    symmetry_ops=(sym["ops"] if sym else []), cached=bool(hit))
        if hit:
            Ibasis, Z, extra = hit
            Ibasis = Ibasis.copy()
            Z = Z * (self.soil.rho1 if scale_free else 1.0)
            info.update(extra)
        else:
            if how == "dense":
                Ibasis, Z = (self._solve_symmetric(sym, E) if sym else self._solve_dense(E))
                extra = {}
            else:
                Ibasis, Z, extra = self._solve_hmatrix(E, tol)
            info.update(extra)
            if key is not None:
                _CACHE_PUT(key, (Ibasis.copy(), Z / (self.soil.rho1 if scale_free else 1.0),
                                 extra))
        self.Ibasis = Ibasis
        self.Z = Z
        self.solver_info = info
        J = np.array([self.IG] + [nt["injection"] for nt in self.nets[1:]])
        self.I = self.Ibasis @ J
        self.Vnet = self.Z @ J
        self.V = float(self.Vnet[0])
        out = dict(segments=n, GPR=self.V, Rg=float(self.Z[0, 0]), IG=self.IG,
                   I_min=float(self.I.min()), I_max=float(self.I.max()),
                   soil=self.soil.describe(), solver=info,
                   total_length=float(sum(s.length for s in self.segments
                                          if s.tag != "plate")))
        if self.plates:
            # a plate is an area, not a length (1.9.0)
            out["plate_area"] = float(sum(pl["length"] * pl["width"] for pl in self.plates))
            out["plates"] = len(self.plates)
        if m == 1:
            out["Rg"] = self.V / self.IG if self.IG else float(self.Z[0, 0])
        else:
            out["networks"] = self.network_summary()
        return out

    def leakage_for_potentials(self, Vseg, tol: float = 1e-9):
        """Leakage currents I with P I = V for prescribed segment potentials
        V (complex allowed; P is real, so the real and imaginary parts are
        solved separately) — the fine half of the two-scale
        non-equipotential solution (1.8.9).  Dense up to DENSE_LIMIT
        segments, the compressed H-matrix with GMRES above."""
        Vseg = np.asarray(Vseg)
        n = len(self.segments)
        B = np.column_stack([np.real(Vseg), np.imag(Vseg)]).astype(float)
        if n <= DENSE_LIMIT:
            X = np.linalg.solve(self.build_matrix(), B)
        else:
            from . import hmatrix
            self._prepare_soil()
            self._cache_arrays()
            rr, cc, vv = [], [], []
            for _, j, idx, vals in self._near_values(np.arange(n)):
                rr.append(idx)
                cc.append(np.full(idx.size, j))
                vv.append(vals)
            lo = np.minimum(self._P1, self._P2)
            hi = np.maximum(self._P1, self._P2)
            T = self._terms_estimate()
            hm = hmatrix.HMatrix(self._collocation, self._mids, lo, hi,
                                 sparse=(np.concatenate(rr), np.concatenate(cc), np.concatenate(vv)),
                                 reach=self._near_reach(), tol=1e-8,
                                 full_eval=lambda a, b: _full_cheaper(a, b, T))
            pc = hmatrix.BlockJacobi(hm)
            X = np.zeros_like(B)
            for k in range(2):
                if not np.any(B[:, k]):
                    continue
                x, it, rel = hmatrix.gmres(hm.matvec, B[:, k], pc.apply, tol=tol)
                if rel > 1e-7:
                    raise RuntimeError(f"The iterative solver did not converge (residual {rel:.1e}).")
                X[:, k] = x
        return X[:, 0] + 1j * X[:, 1]

    def _solution_key(self, how, tol, scale_free):
        import hashlib
        segs = self.segments
        h = hashlib.sha1()
        arr = np.array([[*s.p1, *s.p2, s.radius, s.layer, s.net, s.shell] for s in segs])
        h.update(np.ascontiguousarray(arr).tobytes())
        h.update(repr((self.soil.signature(scale_free), how, float(tol) if how != "dense" else 0,
                       len(self.nets))).encode())
        return h.hexdigest()

    def _solve_dense(self, E):
        n, m = E.shape
        P = self.build_matrix()
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
        return sol[:n, :], sol[n:, :]

    def _solve_symmetric(self, sym, E):
        """The dense solution on one representative segment per orbit.

        By the symmetry, P[g i, g j] = P[i, j], so the equation of a
        representative row r_a with the orbit O_b's common current I_b is
            Σ_b I_b Σ_{j ∈ O_b} P[r_a, j] = V
        and Σ_{j ∈ O_b} P[r_a, j] = (|O_b|/|O_a|) Σ_{i ∈ O_a} P[i, r_b]:
        only the columns of the representatives are assembled (|G| times
        fewer) and the system is |G| times smaller (|G|³ times less work)."""
        n, m = E.shape
        orbit, reps, sizes = sym["orbit"], sym["reps"], sym["sizes"]
        k = len(reps)
        order = np.argsort(orbit, kind="stable")
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]])
        Pr = np.zeros((k, k))
        step = max(16, int(4_000_000 // max(n, 1)))
        for a in range(0, k, step):
            cols = reps[a:a + step]
            Pc = self.build_matrix(cols=cols)                     # (n, len(cols))
            Pr[:, a:a + step] = np.add.reduceat(Pc[order], starts, axis=0)
        Pr *= sizes[None, :] / sizes[:, None]
        Er = E[reps]                                               # (k, m)
        A = np.zeros((k + m, k + m))
        A[:k, :k] = Pr
        A[:k, k:] = -Er
        A[k:, :k] = (Er * sizes[:, None]).T
        B = np.zeros((k + m, m))
        B[k:, :] = np.eye(m)
        sol = np.linalg.solve(A, B)
        return sol[:k, :][orbit], sol[k:, :]

    def _solve_hmatrix(self, E, tol=1e-7):
        """Compressed solution for large models (1.8.7): H-matrix of the
        collocation coefficients with the near-field quadrature written into
        its dense blocks, and GMRES with a block-Jacobi preconditioner for
        X = P⁻¹E; then Z = (EᵀX)⁻¹ and the current shapes X Z."""
        from . import hmatrix
        n, m = E.shape
        self._prepare_soil()
        self._cache_arrays()
        rr, cc, vv = [], [], []
        for _, j, idx, vals in self._near_values(np.arange(n)):
            rr.append(idx)
            cc.append(np.full(idx.size, j))
            vv.append(vals)
        sparse = (np.concatenate(rr), np.concatenate(cc), np.concatenate(vv))
        lo = np.minimum(self._P1, self._P2)
        hi = np.maximum(self._P1, self._P2)
        T = self._terms_estimate()
        hm = hmatrix.HMatrix(self._collocation, self._mids, lo, hi, sparse=sparse,
                             reach=self._near_reach(), tol=tol * 0.1,
                             full_eval=lambda a, b: _full_cheaper(a, b, T))
        pc = hmatrix.BlockJacobi(hm)
        X = np.zeros((n, m))
        its, res = [], []
        for k in range(m):
            x, it, rel = hmatrix.gmres(hm.matvec, E[:, k], pc.apply, tol=tol * 1e-2)
            if rel > tol:
                raise RuntimeError(f"The iterative solver did not converge "
                                   f"(relative residual {rel:.1e} after {it} iterations).")
            X[:, k] = x
            its.append(it)
            res.append(rel)
        Z = np.linalg.inv(E.T @ X)
        extra = dict(iterations=its, residual=max(res),
                     compression=float(hm.stats["compression"]),
                     rank_max=int(hm.stats["rank_max"]),
                     far_blocks=int(hm.stats["far_blocks"]),
                     near_blocks=int(hm.stats["near_blocks"]))
        return X @ Z, Z, extra

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
    def potential_at(self, points, chunk: int = 400, currents=None):
        """Earth-surface / soil potential (V) at arbitrary points (N, 3).

        All segments are summed at once with a 2-point Gauss rule (one
        vectorised Green's-function call per soil layer and chunk of field
        points; exact for a cubic, so about 1e-5 at five segment lengths and
        better beyond — 4 points up to 1.8.3); field points closer than five
        segment lengths to a segment are then corrected to a 12-point rule.
        For a map of many points over a large model the far sum goes through
        the cluster trees of the compressed solver (1.8.7): blocks of points
        and segments far apart are summed through a cross approximation.
        `currents` replaces the solution's own segment currents.
        """
        pts = np.atleast_2d(np.asarray(points, float))
        out = np.zeros(len(pts))
        if not len(pts):
            return out
        I = self.I if currents is None else np.asarray(currents)
        A = self._arrays()
        n = len(A["lens"])
        t4, w4 = _gauss(2)             # far rule (named t4 for history)
        t12, w12 = _gauss(12)
        T = self._terms_estimate()
        if len(pts) >= 256 and n >= 1000 and len(pts) * n * T > TREE_WORK:
            out += self._far_tree(pts, I)
        else:
            for lay in np.unique(A["lay"]):
                idx = np.nonzero(A["lay"] == lay)[0]
                p1, p2 = A["P1"][idx], A["P2"][idx]
                q = (p1[:, None, :] + (p2 - p1)[:, None, :] * t4[None, :, None]).reshape(-1, 3)
                wq = (I[idx][:, None] * w4[None, :]).ravel()
                ck = max(1, min(chunk, int(4_000_000 // max(q.shape[0] * max(T // 2, 1), 1))))
                for a in range(0, len(pts), ck):
                    f = pts[a:a + ck]
                    out[a:a + ck] += self._green_terms(f, q, False, int(lay)) @ wq
        # near-field correction: find the (point, segment) pairs closer than
        # five segment lengths in one array operation, then loop only over
        # the segments that have any (the refinement searches call this with
        # a handful of points, where a loop over every segment dominated)
        mids = A["mids"]
        lens5 = 5.0 * A["lens"]
        ii_all, jj_all = [], []
        ck = max(1, min(256, int(3_000_000 // max(n, 1))))
        for a in range(0, len(pts), ck):
            f = pts[a:a + ck]
            dd = np.sqrt(((f[:, None, :] - mids[None, :, :]) ** 2).sum(axis=2))
            ii, jj = np.nonzero(dd <= lens5[None, :])
            ii_all.append(ii + a)
            jj_all.append(jj)
        ii = np.concatenate(ii_all)
        jj = np.concatenate(jj_all)
        if not ii.size:
            return out
        # 1.8.4: all (point, segment) pairs at once, grouped by the layer of
        # the segment, instead of one Green's-function call per segment —
        # the per-call overhead dominated the refinement searches.
        P1, P2, lay_s, rad2 = A["P1"], A["P2"], A["lay"], A["rad2"]
        for lay in np.unique(lay_s[jj]):
            sel = np.nonzero(lay_s[jj] == lay)[0]
            for b in range(0, sel.size, 20000):
                k = sel[b:b + 20000]
                i_, j_ = ii[k], jj[k]
                f = pts[i_]
                d = P2[j_] - P1[j_]
                q12 = P1[j_][:, None, :] + d[:, None, :] * t12[None, :, None]
                q4 = P1[j_][:, None, :] + d[:, None, :] * t4[None, :, None]
                # a field point closer to the axis than the conductor radius is
                # on the metal (the top of a fence post, say): take the potential
                # at the conductor surface rather than the line-source singularity
                g = (self._green_pairs(f, q12, int(lay), rad2[j_]) @ w12
                     - self._green_pairs(f, q4, int(lay)) @ w4)
                out += np.bincount(i_, weights=I[j_] * g, minlength=len(pts))
        return out

    def _potential_row(self, points):
        """Potential at `points` (M, 3) per ampere leaked by each segment:
        an (M, n) array, with a 12-point rule on every segment (for the few
        points of a boundary condition, 1.8.8)."""
        pts = np.atleast_2d(np.asarray(points, float))
        A = self._arrays()
        t12, w12 = _gauss(12)
        out = np.zeros((len(pts), len(A["lens"])))
        for lay in np.unique(A["lay"]):
            idx = np.nonzero(A["lay"] == lay)[0]
            p1, p2 = A["P1"][idx], A["P2"][idx]
            q = (p1[:, None, :] + (p2 - p1)[:, None, :] * t12[None, :, None]).reshape(-1, 3)
            G = self._green_terms(pts, q, False, int(lay))
            out[:, idx] = G.reshape(len(pts), len(idx), 12) @ w12
        return out

    def _arrays(self):
        """Segment arrays for post-processing, rebuilt when the segment list
        has been replaced or changed length."""
        segs = self.segments
        A = getattr(self, "_A", None)
        if A is None or A["id"] != id(segs) or len(A["lens"]) != len(segs):
            A = dict(id=id(segs),
                     P1=np.array([s.p1 for s in segs]), P2=np.array([s.p2 for s in segs]),
                     mids=np.array([s.mid for s in segs]),
                     lens=np.array([s.length for s in segs]),
                     lay=np.array([s.layer for s in segs]),
                     rad2=np.array([s.radius for s in segs]) ** 2, tree=None)
            self._A = A
        return A

    def _far_tree(self, pts, I):
        """2-point-rule potential of all the segments at many points, through
        a point tree and a segment tree: near blocks and small far blocks are
        summed directly, large far blocks through a cross approximation of
        the block (to 1e-7) applied to the currents."""
        from . import hmatrix
        A = self._arrays()
        t2, w2 = _gauss(2)
        T = self._terms_estimate()
        if A["tree"] is None:
            lo = np.minimum(A["P1"], A["P2"])
            hi = np.maximum(A["P1"], A["P2"])
            A["tree"] = hmatrix.cluster_tree(A["mids"], lo, hi, 64)
        sroot, sperm = A["tree"]
        proot, pperm = hmatrix.cluster_tree(pts, pts, pts, 64)
        far, near = hmatrix.block_partition(proot, sroot, 1.5, 0.0)

        def entries(rows, cols):
            out = np.zeros((rows.size, cols.size))
            f = pts[rows]
            for lay in np.unique(A["lay"][cols]):
                k = np.nonzero(A["lay"][cols] == lay)[0]
                cj = cols[k]
                q = (A["P1"][cj][:, None, :] + (A["P2"][cj] - A["P1"][cj])[:, None, :]
                     * t2[None, :, None]).reshape(-1, 3)
                out[:, k] = self._green_terms(f, q, False, int(lay)).reshape(
                    rows.size, cj.size, 2) @ w2
            return out

        res = np.zeros(len(pts))
        for a, b in near:
            R, C = pperm[a.start:a.stop], sperm[b.start:b.stop]
            res[R] += entries(R, C) @ I[C]
        for a, b in far:
            R, C = pperm[a.start:a.stop], sperm[b.start:b.stop]
            if _full_cheaper(len(R), len(C), T, 2):
                res[R] += entries(R, C) @ I[C]
                continue
            uv = hmatrix.aca(lambda i: entries(R[i:i + 1], C)[0],
                             lambda j: entries(R, C[j:j + 1])[:, 0], len(R), len(C), 1e-7)
            if uv is None:
                res[R] += entries(R, C) @ I[C]
            else:
                res[R] += uv[0] @ (uv[1].T @ I[C])
        return res

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

    # -- where a person can touch earthed metal -----------------------------
    def _plan_conductors(self, net=0):
        """Horizontal runs of network `net` in plan: (K, 2, 2) array."""
        segs = [(it[0], it[1]) for it in self.raw if (net is None or it[4] == net)]
        out = [((a[0], a[1]), (b[0], b[1])) for a, b in segs
               if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6]
        return np.array(out, float).reshape(-1, 2, 2)

    def _plan_points(self, net=0):
        """Plan positions of vertical members (rods, piers) of network `net`."""
        pts = [(it[0][0], it[0][1]) for it in self.raw
               if (net is None or it[4] == net)
               and math.hypot(it[1][0] - it[0][0], it[1][1] - it[0][1]) <= 1e-6]
        return np.array(pts, float).reshape(-1, 2)

    def touch_region(self, px, py, margin: float = 1.0, net=0):
        """True where a person standing on the soil can reach earthed metal.

        A point qualifies when it lies within `margin` (arm reach) of a
        conductor of the energised network seen in plan, or when it is
        enclosed by that network's horizontal conductors on all four sides
        (inside a mesh).  Before 1.8.0 the whole bounding rectangle of the
        electrodes counted, so the empty notch of an L- or T-shaped grid,
        where there is nothing to touch, could set the touch voltage.
        """
        px = np.asarray(px, float)
        py = np.asarray(py, float)
        shp = px.shape
        x = px.ravel()
        y = py.ravel()
        C = self._plan_conductors(net)
        R = self._plan_points(net)
        near = np.zeros(x.size, bool)
        if len(C):
            a = C[:, 0, :]
            d = C[:, 1, :] - a
            L2 = (d ** 2).sum(axis=1)
            for k in range(0, x.size, 2048):
                xx = x[k:k + 2048, None]
                yy = y[k:k + 2048, None]
                t = np.clip(((xx - a[None, :, 0]) * d[None, :, 0]
                             + (yy - a[None, :, 1]) * d[None, :, 1]) / L2[None, :], 0, 1)
                dx = xx - (a[None, :, 0] + t * d[None, :, 0])
                dy = yy - (a[None, :, 1] + t * d[None, :, 1])
                near[k:k + 2048] = (dx * dx + dy * dy).min(axis=1) <= margin ** 2 + 1e-12
        if len(R):
            for k in range(0, x.size, 2048):
                dd = ((x[k:k + 2048, None] - R[None, :, 0]) ** 2
                      + (y[k:k + 2048, None] - R[None, :, 1]) ** 2)
                near[k:k + 2048] |= dd.min(axis=1) <= margin ** 2 + 1e-12
        inside = np.zeros(x.size, bool)
        if len(C):
            x1, y1 = C[:, 0, 0], C[:, 0, 1]
            x2, y2 = C[:, 1, 0], C[:, 1, 1]
            for k in range(0, x.size, 2048):
                xx = x[k:k + 2048, None]
                yy = y[k:k + 2048, None]
                # crossings of the vertical line through the point
                spanx = (np.minimum(x1, x2)[None, :] <= xx) & (xx <= np.maximum(x1, x2)[None, :]) \
                    & (np.abs(x2 - x1)[None, :] > 1e-9)
                yc = y1[None, :] + (y2 - y1)[None, :] * (xx - x1[None, :]) / np.where(
                    np.abs(x2 - x1) > 1e-9, x2 - x1, 1.0)[None, :]
                up = (spanx & (yc >= yy)).any(axis=1)
                dn = (spanx & (yc <= yy)).any(axis=1)
                spany = (np.minimum(y1, y2)[None, :] <= yy) & (yy <= np.maximum(y1, y2)[None, :]) \
                    & (np.abs(y2 - y1)[None, :] > 1e-9)
                xc = x1[None, :] + (x2 - x1)[None, :] * (yy - y1[None, :]) / np.where(
                    np.abs(y2 - y1) > 1e-9, y2 - y1, 1.0)[None, :]
                rt = (spany & (xc >= xx)).any(axis=1)
                lt = (spany & (xc <= xx)).any(axis=1)
                inside[k:k + 2048] = up & dn & rt & lt
        return (near | inside).reshape(shp)

    def _surf(self, px, py):
        px = np.asarray(px, float)
        pts = np.column_stack([px.ravel(), np.asarray(py, float).ravel(),
                               np.zeros(px.size)])
        return np.asarray(self.potential_at(pts)).reshape(px.shape)

    def _metal_tops(self):
        return np.array([[sg.p1[0], sg.p1[1]] for sg in self.segments
                         if min(sg.p1[2], sg.p2[2]) < 0.05
                         and abs(sg.p2[0] - sg.p1[0]) + abs(sg.p2[1] - sg.p1[1]) < 1e-9]
                        ).reshape(-1, 2)

    def _off_metal(self, px, py, tops):
        """Metal that reaches the surface (fence posts) pins the soil next to
        it at its own potential, so a foot placed on a post would read a
        meaningless step; points within 0.25 m of one are left out, as the
        commercial codes do."""
        px = np.asarray(px, float)
        py = np.asarray(py, float)
        if not len(tops):
            return np.ones(px.shape, bool)
        d2 = np.full(px.shape, np.inf)
        for tx, ty in tops:
            d2 = np.minimum(d2, (px - tx) ** 2 + (py - ty) ** 2)
        return d2 > 0.25 ** 2

    def _step(self, px, py, theta, st, tops, V0=None):
        """|V(p) − V(p + s·u(θ))|, zero where either foot is on metal."""
        px = np.asarray(px, float)
        py = np.asarray(py, float)
        qx = px + st * np.cos(theta)
        qy = py + st * np.sin(theta)
        if V0 is None:
            V0 = self._surf(px, py)
        V1 = self._surf(qx, qy)
        ok = self._off_metal(px, py, tops) & self._off_metal(qx, qy, tops)
        return np.where(ok, np.abs(V0 - V1), 0.0)

    @staticmethod
    def _distinct(cands, sep):
        out = []
        for c in cands:
            if all(math.hypot(c[0] - o[0], c[1] - o[1]) > sep for o in out):
                out.append(c)
        return out

    @staticmethod
    def _climb(fb, x0, steps, n_dims, min_step):
        """Compass search maximising f; `fb` evaluates a batch of points
        (array (k, n_dims)) in one call.  Steps start at `steps` and are
        halved until they reach `min_step`."""
        x = np.array(x0, float)
        fx = float(fb(x[None, :])[0])
        st = np.array(steps, float)
        mn = np.array(min_step, float)
        it = 0
        while np.max(st / mn) > 1.0 and it < 300:
            it += 1
            trials = []
            for d in range(n_dims):
                for sg in (1.0, -1.0):
                    y = x.copy()
                    y[d] += sg * st[d]
                    trials.append(y)
            trials = np.array(trials)
            vals = np.asarray(fb(trials), float)
            k = int(np.argmax(vals))
            if vals[k] > fx + 1e-12:
                x, fx = trials[k], float(vals[k])
            else:
                st = st / 2.0
        return x.tolist(), fx

    def worst_touch_step(self, xlim, ylim, nx=41, ny=41, step=1.0,
                         touch_box=None, touch_margin=1.0, zones=None,
                         refine=True):
        """Worst touch and step voltages over a rectangle.

        Touch voltage is the GPR minus the surface potential, counted only
        where a person can reach earthed metal: inside `zones` when they are
        given (equipment positions, list of dict(name, x0, y0, x1, y1)),
        otherwise inside the region of `touch_region` (or `touch_box`, kept
        for callers that pass one).  Step voltage is the potential
        difference between two feet `step` apart, in the worst direction,
        anywhere in the scanned area.

        Both maxima are first located on the plot grid (step screened in
        four directions, both senses) and along a dense ring just outside
        the electrodes, then the best few candidates are refined by a
        compass search in position — and, for the step, in direction — to
        0.02 m and 1°, so the answer does not depend on the plot
        resolution.  Version 1.7.0 differenced only in +x and +y and
        combined them as hypot(), which over-read the step at a grid corner
        by up to √2 at fine resolution and under-read it on the right and
        top edges: 480 V at nx = 61 and 603 V at nx = 181 on the IEEE 80
        Annex B grid with rods, against 488 V from a brute-force search.
        """
        sp = self.surface_potential(xlim, ylim, nx, ny)
        V = np.array(sp["V"])
        xs = np.array(sp["x"], float)
        ys = np.array(sp["y"], float)
        X, Y = np.meshgrid(xs, ys)
        touch = self.V - V
        dx = (xs[-1] - xs[0]) / max(nx - 1, 1)
        dy = (ys[-1] - ys[0]) / max(ny - 1, 1)
        st = float(step)
        tops = self._metal_tops()

        # ---------------- touch -----------------------------------------
        def region_fn(box):
            if box is not None:
                return lambda px, py: ((np.asarray(px) >= box[0]) & (np.asarray(px) <= box[1])
                                       & (np.asarray(py) >= box[2]) & (np.asarray(py) <= box[3]))
            return lambda px, py: self.touch_region(px, py, touch_margin)

        def touch_search(inside_fn):
            mask = inside_fn(X, Y)
            if not mask.any():
                return None
            T = np.where(mask, touch, -np.inf)
            order = np.argsort(T.ravel())[::-1]
            cands = [(T.ravel()[k], X.ravel()[k], Y.ravel()[k]) for k in order[:60]
                     if np.isfinite(T.ravel()[k])]
            # the reach region is bounded by arcs round conductor ends and
            # rods, where the potential is lowest: sample those arcs too,
            # since a compass search cannot slide along a curved boundary
            ends = []
            if touch_box is None:
                C = self._plan_conductors(0)
                ends = [tuple(q) for c in C for q in c] + [tuple(q) for q in self._plan_points(0)]
            if ends:
                E = np.unique(np.round(np.array(ends, float), 6), axis=0)
                ang = np.linspace(0.0, 2 * math.pi, 73)[:-1]
                rr = touch_margin * (1.0 - 1e-6)
                qx = (E[:, 0][:, None] + rr * np.cos(ang)[None, :]).ravel()
                qy = (E[:, 1][:, None] + rr * np.sin(ang)[None, :]).ravel()
                ok = inside_fn(qx, qy)
                qx, qy = qx[ok], qy[ok]
                if qx.size:
                    Tq = self.V - self._surf(qx, qy)
                    for k in np.argsort(Tq)[::-1][:20]:
                        cands.append((float(Tq[k]), qx[k], qy[k]))
            cands.sort(key=lambda c: -c[0])
            cands = self._distinct([(c[1], c[2]) for c in cands], 0.5 * max(dx, dy, 0.5))[:5]
            best = None
            for cx, cy in cands:
                if refine:
                    def f(P):
                        ok = inside_fn(P[:, 0], P[:, 1])
                        return np.where(ok, self.V - self._surf(P[:, 0], P[:, 1]), -1e30)
                    p, val = self._climb(f, [cx, cy], [dx / 2, dy / 2], 2, [0.02, 0.02])
                else:
                    p = [cx, cy]
                    val = float(self.V - self._surf(np.array([cx]), np.array([cy]))[0])
                if best is None or val > best[0]:
                    best = (val, p)
            return dict(touch_max=float(best[0]),
                        touch_at=[float(best[1][0]), float(best[1][1])],
                        mask=mask)

        zone_res = []
        if zones:
            for z in zones:
                bx = (min(z["x0"], z["x1"]), max(z["x0"], z["x1"]),
                      min(z["y0"], z["y1"]), max(z["y0"], z["y1"]))
                # sample the zone itself as well as the plot grid, so a zone
                # smaller than the grid spacing is still evaluated
                gx = np.linspace(bx[0], bx[1], 9)
                gy = np.linspace(bx[2], bx[3], 9)
                ZX, ZY = np.meshgrid(gx, gy)
                Tz = self.V - self._surf(ZX, ZY)
                k = int(np.argmax(Tz))
                best = (float(Tz.ravel()[k]), [float(ZX.ravel()[k]), float(ZY.ravel()[k])])
                if refine:
                    fz = region_fn(bx)

                    def f(P, fz=fz):
                        ok = fz(P[:, 0], P[:, 1])
                        return np.where(ok, self.V - self._surf(P[:, 0], P[:, 1]), -1e30)
                    p, val = self._climb(f, best[1], [(bx[1] - bx[0]) / 16 + 1e-3,
                                                      (bx[3] - bx[2]) / 16 + 1e-3], 2, [0.02, 0.02])
                    if val > best[0]:
                        best = (val, p)
                zone_res.append(dict(name=z.get("name", "zone"), box=list(bx),
                                     touch_max=best[0], touch_at=[float(best[1][0]), float(best[1][1])],
                                     limit=z.get("limit")))
            wz = max(zone_res, key=lambda r: r["touch_max"])
            tres = dict(touch_max=wz["touch_max"], touch_at=wz["touch_at"],
                        mask=None)
            region = "zones"
        else:
            tres = touch_search(region_fn(touch_box))
            region = "box" if touch_box is not None else "reach"
            if tres is None:                          # nothing inside the scan
                k = int(np.argmax(touch))
                tres = dict(touch_max=float(touch.ravel()[k]),
                            touch_at=[float(X.ravel()[k]), float(Y.ravel()[k])], mask=None)
        mask = tres.pop("mask", None)

        # ---------------- step ------------------------------------------
        # Screening: the surface map is interpolated at the far foot (cheap),
        # in four directions and both senses; along a ring just outside the
        # electrodes, where the worst step usually is, the field is evaluated
        # exactly, stepping inwards and outwards.  The candidates are then
        # refined with exact evaluations.
        def interp(qx, qy):
            fx = np.clip((qx - xs[0]) / max(dx, 1e-12), 0, nx - 1 - 1e-9)
            fy = np.clip((qy - ys[0]) / max(dy, 1e-12), 0, ny - 1 - 1e-9)
            i0 = np.floor(fx).astype(int)
            j0 = np.floor(fy).astype(int)
            tx, ty = fx - i0, fy - j0
            return ((1 - tx) * (1 - ty) * V[j0, i0] + tx * (1 - ty) * V[j0, i0 + 1]
                    + (1 - tx) * ty * V[j0 + 1, i0] + tx * ty * V[j0 + 1, i0 + 1])

        okg = self._off_metal(X, Y, tops)
        cands = []
        for th in (0.0, 0.5 * math.pi, 0.25 * math.pi, -0.25 * math.pi):
            qx, qy = X + st * math.cos(th), Y + st * math.sin(th)
            inside_scan = (qx >= xs[0]) & (qx <= xs[-1]) & (qy >= ys[0]) & (qy <= ys[-1])
            S1 = np.where(okg & inside_scan, np.abs(V - interp(qx, qy)), 0.0)
            for k in np.argsort(S1.ravel())[::-1][:10]:
                cands.append((float(S1.ravel()[k]), X.ravel()[k], Y.ravel()[k], th))
                # the opposite sense: the far foot becomes the near one
                cands.append((float(S1.ravel()[k]), X.ravel()[k] + st * math.cos(th),
                              Y.ravel()[k] + st * math.sin(th), th + math.pi))
        b = self.touch_bbox(0.0, net=None)
        if all(np.isfinite(b)):
            n_per = 120
            xr = np.linspace(b[0] - st, b[1] + st, n_per)
            yr = np.linspace(b[2] - st, b[3] + st, n_per)
            sides = [(xr, np.full(n_per, b[2] - st), 0.5 * math.pi),     # bottom: step up
                     (xr, np.full(n_per, b[3] + st), -0.5 * math.pi),    # top: step down
                     (np.full(n_per, b[0] - st), yr, 0.0),               # left: step right
                     (np.full(n_per, b[1] + st), yr, math.pi)]           # right: step left
            for rx, ry, th in sides:
                rV = self._surf(rx, ry)
                for sense in (th, th + math.pi):
                    S1 = self._step(rx, ry, sense, st, tops, V0=rV)
                    for k in np.argsort(S1)[::-1][:4]:
                        cands.append((float(S1[k]), rx[k], ry[k], sense))
        cands.sort(key=lambda c: -c[0])
        pick = []
        for c in cands:
            if all(math.hypot(c[1] - o[1], c[2] - o[2]) > 0.5 * st
                   or abs(((c[3] - o[3] + math.pi) % (2 * math.pi)) - math.pi) > 0.6
                   for o in pick):
                pick.append(c)
            if len(pick) >= 6:
                break
        best = None
        for s0, cx, cy, th in pick:
            if refine:
                def f(P):
                    return self._step(P[:, 0], P[:, 1], P[:, 2], st, tops)
                p, val = self._climb(f, [cx, cy, th],
                                     [max(dx, 0.05) / 2, max(dy, 0.05) / 2, math.pi / 8],
                                     3, [0.02, 0.02, math.radians(1.0)])
            else:
                p, val = [cx, cy, th], s0
            if best is None or val > best[0]:
                best = (val, p)
        step_max, sp_at = best[0], best[1]

        out = dict(
            touch_max=float(tres["touch_max"]),
            touch_at=[float(v) for v in tres["touch_at"]],
            touch_region=region, touch_margin=float(touch_margin),
            step_max=float(step_max), step_at=[float(sp_at[0]), float(sp_at[1])],
            step_direction_deg=float(math.degrees(sp_at[2]) % 360.0),
            step_note=("worst direction, refined to 0.02 m and 1° from the plot-grid and "
                       "perimeter candidates, so it does not depend on the plot resolution"),
            touch_box=list(touch_box) if touch_box is not None else list(self.touch_bbox(touch_margin)),
            GPR=self.V, surface=sp,
            fences=[self.fence_touch(f) for f in self.fences])
        if mask is not None:
            out["surface"]["touch_mask"] = mask.astype(int).tolist()
        if zone_res:
            out["zones"] = zone_res
        return out

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


def plate_strips(item: dict) -> int:
    """Strips of a plate item: given, or 16, more for a wide horizontal
    plate near the surface so that the strips stay about as wide as the
    plate is deep (the surface potential over it then follows a plate's
    within about 1 % of the GPR), at most 64."""
    if item.get("strips") not in (None, "", 0):
        return int(item["strips"])
    n = 16
    if str(item.get("orientation", "horizontal")).startswith("h"):
        short = min(float(item["Lx"]), float(item["Ly"]))
        d = max(float(item.get("depth", 0.5)), 0.05)
        n = max(n, int(math.ceil(math.pi * short / (2.0 * 1.2 * d))))
    return min(n, 64)


def add_plate_item(net: "Network", item: dict):
    """Plate item of the numerical page (1.9.0).

    orientation "horizontal": corner (x0, y0), sides Lx, Ly at `depth`,
                              turned by `angle` degrees about the corner;
    orientation "vertical"  : top edge from (x0, y0) along `angle` degrees
                              for `length`, from `top_depth` down `height`."""
    o = str(item.get("orientation", "horizontal")).lower()
    a = math.radians(float(item.get("angle", 0.0) or 0.0))
    e1 = np.array([math.cos(a), math.sin(a), 0.0])
    e2 = np.array([-math.sin(a), math.cos(a), 0.0])
    x0, y0 = float(item.get("x0", 0.0)), float(item.get("y0", 0.0))
    if o.startswith("h"):
        Lx, Ly, d = float(item["Lx"]), float(item["Ly"]), float(item.get("depth", 0.5))
        if min(Lx, Ly) <= 0 or d < 0:
            raise ValueError("A horizontal plate needs positive Lx and Ly and a depth of 0 or more.")
        net.add_plate((x0, y0, d), Lx * e1, Ly * e2, plate_strips(item))
    elif o.startswith("v"):
        L, H, t = float(item["length"]), float(item["height"]), float(item.get("top_depth", 0.5))
        if min(L, H) <= 0 or t < 0:
            raise ValueError("A vertical plate needs a positive length and height and a top "
                             "depth of 0 or more.")
        net.add_plate((x0, y0, t), L * e1, np.array([0.0, 0.0, H]), plate_strips(item))
    else:
        raise ValueError("A plate is horizontal or vertical.")


def thick_warning(th) -> str:
    """Warning text for conductors kept at ten radii (1.9.1)."""
    if not th:
        return ""
    return (f"The segment length of {th['requested']:g} m is shorter than ten radii of the "
            f"thickest conductors (radius up to {th['radius']:g} m), where the thin-wire model "
            f"stops being valid: {th['pieces']} conductor piece(s) were cut into segments of "
            f"ten radii instead (up to {th['length']:.3g} m). The rest of the model uses the "
            f"length asked for.")


def describe_solver(info) -> str:
    """One line on how the system was solved (report and narrative, 1.8.7)."""
    if not info:
        return ""
    parts = []
    if info.get("method") == "hmatrix":
        its = info.get("iterations") or []
        parts.append(f"compressed H-matrix ({100.0 * float(info.get('compression', 1.0)):.0f} % of "
                     f"the dense storage), GMRES in {max(its) if its else '?'} iterations")
    else:
        parts.append("dense direct solution")
    if int(info.get("symmetry", 1)) > 1:
        parts.append(f"reduced by {int(info['symmetry'])}-fold symmetry to "
                     f"{int(info.get('unknowns', 0))} unknowns")
    if info.get("cached"):
        parts.append("reusing a stored solution of the same model")
    return ", ".join(parts)


def describe_refinement(r) -> str:
    """One line on the automatic refinement (report and narrative, 1.8.8)."""
    if not r or not r.get("levels"):
        return ""
    L = r["levels"]
    a, b = L[0], L[-1]
    txt = (f"{len(L) - 1} level(s), {a['segments']} → {b['segments']} segments; touch "
           f"{a['touch']:.1f} → {b['touch']:.1f} V, step {a['step']:.1f} → {b['step']:.1f} V")
    if r.get("converged"):
        txt += f"; last changes below {100 * r['tol']:.2g} %"
    else:
        txt += "; not converged within the levels or the segment limit"
    return txt


def vertical_spec(spec: dict):
    """The vertical soil boundary of a payload (1.8.7): ρ' beyond the line
    through (x_v, y_v) whose normal points at angle_v degrees from the x
    axis into the second region; None without rho_v."""
    if spec.get("rho_v") in (None, ""):
        return None
    return dict(rho=float(spec["rho_v"]), x=float(spec.get("x_v") or 0.0),
                y=float(spec.get("y_v") or 0.0), angle=float(spec.get("angle_v") or 0.0))


def build_network(spec: dict) -> Network:
    soil = SoilModel(spec.get("rho1", 100.0), spec.get("rho2"),
                     spec.get("h_layer"), rho3=spec.get("rho3"),
                     h2=spec.get("h_layer2"), rho4=spec.get("rho4"),
                     h3=spec.get("h_layer3"), vertical=vertical_spec(spec))
    net = Network(soil, spec.get("IG", 1000.0))
    r_cond = spec.get("conductor_radius", 0.005)

    for item in spec.get("items", []):
        kind = item.get("kind")
        if kind == "grid":
            net.add_grid(item["Lx"], item["Ly"], item.get("D", 0) or 1.0,
                         item.get("depth", 0.5), item.get("radius", r_cond),
                         item.get("x0", 0.0), item.get("y0", 0.0),
                         grading=float(item.get("grading", 0.0) or 0.0),
                         n_x=item.get("n_x"), n_y=item.get("n_y"))
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
        elif kind == "plate":
            add_plate_item(net, item)
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
