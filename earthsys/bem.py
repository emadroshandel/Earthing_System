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
                 tol: float = 1e-6):
        self.rho1 = float(rho1)
        self.rho2 = float(rho2) if rho2 else None
        self.h = float(h) if h else None
        self.uniform = self.rho2 is None or self.h is None or \
            abs(self.rho2 - self.rho1) < 1e-9
        self.K = 0.0 if self.uniform else \
            (self.rho2 - self.rho1) / (self.rho2 + self.rho1)
        if self.uniform:
            self.N = 0
        else:
            n = 1
            while abs(self.K) ** n > tol and n < max_images:
                n += 1
            self.N = n

    def describe(self):
        if self.uniform:
            return f"Uniform soil, ρ = {self.rho1:g} Ω·m"
        return (f"Two-layer soil: ρ₁ = {self.rho1:g} Ω·m, "
                f"ρ₂ = {self.rho2:g} Ω·m, h = {self.h:g} m, K = {self.K:+.3f}, "
                f"{self.N} image terms")


class Segment:
    __slots__ = ("p1", "p2", "radius", "mid", "length", "tag", "layer")

    def __init__(self, p1, p2, radius, tag="", layer=1):
        self.p1 = np.asarray(p1, dtype=float)
        self.p2 = np.asarray(p2, dtype=float)
        self.radius = float(radius)
        self.mid = 0.5 * (self.p1 + self.p2)
        self.length = float(np.linalg.norm(self.p2 - self.p1))
        self.tag = tag
        self.layer = layer          # 1 = upper layer, 2 = lower layer


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


class Network:
    """Buried electrode network: conductors, rods, rings, arbitrary paths."""

    def __init__(self, soil: SoilModel, IG: float = 1.0):
        if not HAVE_NUMPY:
            raise RuntimeError("The numerical solver requires numpy "
                               "(pip install numpy).")
        self.soil = soil
        self.IG = float(IG)
        self.raw = []          # (p1, p2, radius, tag)
        self.segments: list[Segment] = []
        self.I = None
        self.V = None

    # -- geometry building -------------------------------------------------
    def add_conductor(self, p1, p2, radius, tag=""):
        self.raw.append((tuple(map(float, p1)), tuple(map(float, p2)),
                         float(radius), tag))
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

    # -- discretisation ----------------------------------------------------
    def discretise(self, target: float = 2.0, max_segments: int = 3000):
        total = sum(np.linalg.norm(np.array(b) - np.array(a))
                    for a, b, _, _ in self.raw)
        if total / max(target, 1e-6) > max_segments:
            target = total / max_segments
        self.segments = []
        for a, b, rad, tag in self.raw:
            a = np.array(a, float)
            b = np.array(b, float)
            L = float(np.linalg.norm(b - a))
            # split at the layer interface so that every segment lies in
            # one layer and sees that layer's Green's function
            cuts = [0.0, 1.0]
            s = self.soil
            if not s.uniform and (a[2] - s.h) * (b[2] - s.h) < 0:
                cuts.insert(1, (s.h - a[2]) / (b[2] - a[2]))
            for t0, t1 in zip(cuts[:-1], cuts[1:]):
                q1 = a + (b - a) * t0
                q2 = a + (b - a) * t1
                Lq = float(np.linalg.norm(q2 - q1))
                n = max(1, int(math.ceil(Lq / target - 1e-9)))
                for k in range(n):
                    p1 = q1 + (q2 - q1) * k / n
                    p2 = q1 + (q2 - q1) * (k + 1) / n
                    zm = 0.5 * (p1[2] + p2[2])
                    lay = 2 if (not s.uniform and zm > s.h) else 1
                    self.segments.append(Segment(p1, p2, rad, tag, lay))
        return len(self.segments)

    # -- Green's function --------------------------------------------------
    def _green_terms(self, field, src_pts, skip_direct=False, src_layer=1):
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
        zf = field[:, 2]
        zs = src_pts[None, :, 2]
        out = np.zeros_like(rh2)
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
            for coef, sgn, shift in image_terms(s, src_layer, fl):
                if skip_direct and sgn == 1 and shift == 0.0 and fl == src_layer:
                    continue
                zi = sgn * zs + shift
                acc += coef / np.sqrt(np.maximum(r2 + (zfm - zi) ** 2, 1e-24))
            out[m] = acc
        return out

    def _coeff_column(self, field, seg: Segment, nq: int, skip_direct=False):
        t, w = _gauss(nq)
        pts = seg.p1[None, :] + (seg.p2 - seg.p1)[None, :] * t[:, None]
        G = self._green_terms(field, pts, skip_direct, seg.layer)
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
            col = self._coeff_column(pts, sj, nq_near, skip_direct=skip)
            col = col.reshape(len(idx), nf) @ wf
            P[idx, j] = col

        # ---- exact self terms -------------------------------------------
        for j, sj in enumerate(segs):
            L, a = sj.length, sj.radius
            rho_j = self.soil.rho2 if sj.layer == 2 else rho1
            self_direct = rho_j / (2.0 * math.pi * L) * (math.log(2.0 * L / a) - 1.0)
            tfp = sj.p1[None, :] + (sj.p2 - sj.p1)[None, :] * tf[:, None]
            img = self._coeff_column(tfp, sj, 16, skip_direct=True) @ wf
            P[j, j] = self_direct + float(img)
        return P

    def solve(self, target: float = 2.0):
        if not self.segments:
            self.discretise(target)
        n = len(self.segments)
        P = self.build_matrix()
        A = np.zeros((n + 1, n + 1))
        A[:n, :n] = P
        A[:n, n] = -1.0
        A[n, :n] = 1.0
        b = np.zeros(n + 1)
        b[n] = self.IG
        sol = np.linalg.solve(A, b)
        self.I = sol[:n]
        self.V = float(sol[n])
        return dict(segments=n, GPR=self.V, Rg=self.V / self.IG, IG=self.IG,
                    I_min=float(self.I.min()), I_max=float(self.I.max()),
                    soil=self.soil.describe(),
                    total_length=float(sum(s.length for s in self.segments)))

    # -- post-processing ---------------------------------------------------
    def potential_at(self, points):
        """Earth-surface / soil potential (V) at arbitrary points (N, 3)."""
        pts = np.atleast_2d(np.asarray(points, float))
        out = np.zeros(len(pts))
        for j, sj in enumerate(self.segments):
            d = np.linalg.norm(pts - sj.mid, axis=1)
            nq = 4 if np.all(d > 5 * sj.length) else 12
            out += self.I[j] * self._coeff_column(pts, sj, nq)
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

    def touch_bbox(self, margin: float = 1.0):
        """Bounding box of the buried metal, expanded by `margin` (arm reach)."""
        xs = [c for it in self.raw for c in (it[0][0], it[1][0])]
        ys = [c for it in self.raw for c in (it[0][1], it[1][1])]
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

        def _stepfield(px, py, V0):
            """|dV| over one step in the worst direction, differenced at the
            step distance itself.  For a locally linear field this is
            |grad V| * step, which is what the step voltage is."""
            return np.hypot(np.abs(_V(px + st, py) - V0),
                            np.abs(_V(px, py + st) - V0))

        Xq, Yq = np.meshgrid(np.asarray(sp["x"], dtype=float),
                             np.asarray(sp["y"], dtype=float))
        grad = _stepfield(Xq, Yq, V)

        # The worst step is almost always just outside the electrode, and a
        # coarse plot grid can miss it entirely — the value used to swing by
        # 2.6x with nx alone.  Sample the perimeter densely as well, so the
        # answer does not depend on the resolution the user chose for the
        # picture.
        b = self.touch_bbox(0.0)
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
            touch_box=list(box), GPR=self.V, surface=sp)

    def current_distribution(self):
        return [dict(x=float(s.mid[0]), y=float(s.mid[1]), z=float(s.mid[2]),
                     I=float(i), density=float(i / (2 * math.pi * s.radius * s.length)),
                     tag=s.tag, length=s.length)
                for s, i in zip(self.segments, self.I)]

    def geometry_json(self):
        return [dict(p1=list(map(float, s.p1)), p2=list(map(float, s.p2)),
                     r=s.radius, tag=s.tag) for s in self.segments]


# ---------------------------------------------------------------------------
# Convenience: build a network from a description dict
# ---------------------------------------------------------------------------

def build_network(spec: dict) -> Network:
    soil = SoilModel(spec.get("rho1", 100.0), spec.get("rho2"),
                     spec.get("h_layer"))
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
    return net
