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
Power-frequency analysis without the equipotential assumption (1.8.0).

The boundary-element solver of bem.py holds all buried metal at one
potential.  That is exact for a perfect conductor and close for a compact
copper grid, but a large grid — a power-plant or a long counterpoise — has
series impedance: the fault current enters at one point and loses voltage
along the conductors, so the far corner sits below the GPR at the feed,
the earth impedance is higher than the equipotential R_g, and the touch
voltage concentrates near the injection.

Here the same electrodes are solved as a network of conductors with
internal impedance (skin effect; steel μr = 200) and self and mutual
inductance with earth return, coupled through the soil — the circuit-field
model of hf.py evaluated at 50 or 60 Hz.  The fault current may enter at
several points (transformer neutrals, each with its share).  The leakage
currents found are then used with the static Green's function of bem.py,
in real and imaginary parts, to give the surface potential; the touch
voltage at a point is the magnitude of the difference between the
potential of the nearest earthed metal and the surface potential there.

On a 300 m × 300 m copper grid (D = 20 m) in 30 Ω·m soil fed at one corner
the far corner sits at 70 % of the feed-point potential and |Z| is 22 %
above the equipotential R_g; with steel conductors 24 % and +180 %.  On
a 100 m copper grid in 100 Ω·m soil the difference is below 1 %.

The circuit-field model holds up to 3000 segments (MAX_SEGMENTS; 1500 up
to 1.8.6): the segment currents are eliminated first and only the node
admittance matrix is factorised (hf.Model.solve).  A larger model is
solved in two scales (1.8.9): the circuit-field model with segments long
enough to stay within the limit gives the metal potentials, which vary
slowly along the conductors; these are interpolated along each conductor
to the segments of the length asked for, and the leakage currents there
follow from the static boundary-element matrix (P I = V, dense or
compressed, up to bem.MAX_SEGMENTS).  The surface potentials, touch and
step voltages are those of the fine currents; the earth impedance and the
metal potentials are those of the coarse model.  On a 300 m grid fed at a
corner, coarse 10 m and 20 m models with 5 m leakage reproduce the touch
and step voltages of the full 5 m model within 0.4 % (copper and steel,
uniform and two-layer soil), where the 20 m model alone was 6–20 % out.

Soil is uniform or horizontally layered; a vertical soil boundary is
solved by the equipotential solver only.
"""

from __future__ import annotations

import cmath
import types
import math

from . import bem, hf

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None

# Segment cap of the non-equipotential solution: 1500 up to 1.8.6, 3000 since
# the currents are eliminated before the solution (hf.Model.solve, 1.8.7).
MAX_SEGMENTS = 3000


def _soil_lists(p):
    rho = [float(p["rho1"])]
    h = []
    for rk, hk in (("rho2", "h_layer"), ("rho3", "h_layer2"), ("rho4", "h_layer3")):
        if p.get(rk) not in (None, "") and p.get(hk) not in (None, ""):
            rho.append(float(p[rk]))
            h.append(float(p[hk]))
        else:
            break
    return rho, h


def metal_on_segments(wires, Vn, net):
    """Potential of the metal at the mid-point of every segment of the
    bem network `net`, interpolated along each conductor from the node
    potentials Vn of the circuit-field model `wires` (both built from the
    same conductor list, in the same order)."""
    mids = np.array([sg.mid for sg in net.segments])
    return metal_at_points(wires, Vn, net, mids, np.asarray(net.seg_raw, int))


def metal_at_points(wires, Vn, net, pts, raws):
    """Metal potential at points `pts` lying on the conductors `raws`
    (indices into net.raw), interpolated linearly along each conductor
    between the circuit-field model's node potentials."""
    if len(wires.raw) != len(net.raw):
        raise ValueError("The two discretisations do not share their conductors.")
    pts = np.asarray(pts, float)
    out = np.zeros(len(pts), complex)
    seg_raw = np.asarray(raws, int)
    for r, (a, b, *_rest) in enumerate(net.raw):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        d = b - a
        L2 = float(d @ d) or 1.0
        ks = np.nonzero(wires.raw_idx == r)[0]
        fs = np.nonzero(seg_raw == r)[0]
        if not fs.size:
            continue
        if not ks.size:
            raise ValueError("A conductor is missing from the circuit-field model.")
        P = np.vstack([wires.p1[ks], wires.p2[ks]])
        V = np.concatenate([Vn[wires.na[ks]], Vn[wires.nb[ks]]])
        t = ((P - a) @ d) / L2
        o = np.argsort(t, kind="stable")
        t, V = t[o], V[o]
        keep = np.concatenate([[True], np.diff(t) > 1e-12])
        t, V = t[keep], V[keep]
        tm = ((pts[fs] - a) @ d) / L2
        out[fs] = np.interp(tm, t, V.real) + 1j * np.interp(tm, t, V.imag)
    return out


def two_scale_leakage(spec, bsoil, wires, Vn, IG, seg_fine, max_fine, grade=True):
    """The fine half of the two-scale solution (1.8.9).

    The circuit-field model gives the node potentials Vn of the metal on a
    coarse discretisation.  The metal potential varies over the attenuation
    length of the grid (hundreds of metres at 50 Hz), so it is interpolated
    along each conductor onto segments of the length asked for; the leakage
    currents there follow from the static potential coefficients of the
    boundary-element solver, P I = V (P real, the real and imaginary parts
    solved separately; compressed above DENSE_LIMIT segments).  The total is
    scaled to I_G (the ratio is reported: it measures how far the two
    discretisations disagree).  The surface potential, touch and step
    voltages are then those of the fine leakage currents."""
    net_f = bem.build_network(spec)
    net_f.soil = bsoil
    net_f.discretise(seg_fine, max_fine, grade_ends=grade)
    Vseg = metal_on_segments(wires, Vn, net_f)
    I_f = net_f.leakage_for_potentials(Vseg)
    tot = complex(I_f.sum())
    fac = IG / tot if abs(tot) > 0 else 1.0
    I_f = I_f * fac
    return net_f, I_f, dict(fine_segments=len(net_f.segments), fine_length=float(seg_fine),
                            current_balance=float(abs(fac)),
                            current_balance_deg=float(math.degrees(cmath.phase(fac))))


class _ComplexField:
    """Surface potential of complex leakage currents, through bem.Network."""

    def __init__(self, net, IT):
        self.net = net
        self.Ir = np.real(IT).astype(float)
        self.Ii = np.imag(IT).astype(float)

    def at(self, px, py):
        px = np.asarray(px, float)
        pts = np.column_stack([px.ravel(), np.asarray(py, float).ravel(), np.zeros(px.size)])
        self.net.I = self.Ir
        vr = self.net.potential_at(pts)
        self.net.I = self.Ii
        vi = self.net.potential_at(pts)
        return (vr + 1j * vi).reshape(px.shape)


def analyse(p: dict) -> dict:
    """Non-equipotential power-frequency solution.

    p: the /api/bem payload (soil, items, IG in A) plus
       f              frequency, Hz (50)
       metal          'copper', 'steel', 'galvanised steel', 'aluminium'
       feeds          list of dict(x, y, share) — where the fault current
                      enters (default: the first conductor's start)
       segment_length, nx, step_distance, touch_margin, zones, limits
    """
    if np is None:
        raise RuntimeError("The non-equipotential solver needs numpy.")
    f = float(p.get("f", 50.0))
    IG = float(p.get("IG", 1000.0))
    metal = str(p.get("metal", "copper"))
    if metal not in hf.METAL_RHO:
        raise ValueError("Metal must be copper, steel, galvanised steel or aluminium.")
    rho, h = _soil_lists(p)
    items = [it for it in p.get("items", []) if it.get("kind") != "fence"]
    fence_items = [it for it in p.get("items", []) if it.get("kind") == "fence"]
    if not items:
        raise ValueError("Add at least one electrode element.")
    r_cond = float(p.get("conductor_radius", 0.005))
    wires = hf.Wires.from_items(items, conductor_radius=r_cond)
    n_main = len(wires.raw)
    # Fences (1.8.3): the posts and the buried fence wire are leaking
    # conductors; the fabric above ground joins them without leaking, so the
    # post tops and the wire are merged into one node per fence.  A bonded
    # fence is joined to the grid at the grid node nearest to it: one bond,
    # because a perfect fence bonded at several points would short-circuit
    # the grid's own impedance, the effect this solution exists to show.
    fence_raw, fence_meta = [], []
    for j, fi in enumerate(fence_items):
        fnet = bem.build_network(dict(rho1=100.0, items=[fi], conductor_radius=r_cond))
        idx = []
        for a, b, rad, tag, *_ in fnet.raw:
            wires.add(a, b, rad, tag)
            idx.append(len(wires.raw) - 1)
        fence_raw.append(idx)
        fence_meta.append(dict(fnet.fences[0]))
    soil = hf.make_soil(rho if len(rho) > 1 else rho[0], h, eps_r=10.0, model="constant")
    seg_user = seg = float(p.get("segment_length", 3.0))
    cap = int(p.get("max_segments", MAX_SEGMENTS))
    zc = getattr(soil, "depths", [])
    total = sum(float(np.linalg.norm(b - a)) for a, b, *_ in wires.raw)
    seg = max(seg, total / float(cap))
    # the conductors are also cut where they meet and at the layer
    # boundaries, so the count can exceed total/seg: lengthen the segments
    # until the model is within the limit (1.8.9; it was exceeded by up to
    # 40 % on grids with many rods)
    if wires.discretise(seg, z_cuts=zc) > cap:
        hi = 1.01 * max(float(np.linalg.norm(b - a)) for a, b, *_ in wires.raw)
        if wires.discretise(hi, z_cuts=zc) > cap:
            raise ValueError(
                f"The conductors meet or cross in more than {cap} places: the circuit-field "
                "model cannot take them. Simplify the layout, or use the equipotential solution.")
        lo = seg
        for _ in range(14):
            mid = math.sqrt(lo * hi)
            if wires.discretise(mid, z_cuts=zc) > cap:
                lo = mid
            else:
                hi = mid
        seg = hi
    # two-scale solution (1.8.9): when the model is too large for the segment
    # length asked for, the circuit-field model is solved with longer
    # segments for the metal potentials, which vary slowly along the
    # conductors, and the leakage currents and surface potentials are
    # computed at the length asked for (two_scale_leakage below)
    two_scale = seg > 1.0001 * seg_user and str(p.get("two_scale", True)).lower() not in (
        "0", "false", "no", "off")
    wires.discretise(seg, z_cuts=zc)
    fence_node = []
    if fence_items:
        groups = []
        main_seg = wires.raw_idx < n_main
        main_nodes = np.unique(np.concatenate([wires.na[main_seg], wires.nb[main_seg]]))
        for j, idx in enumerate(fence_raw):
            g = []
            for ri in idx:
                ks = np.where(wires.raw_idx == ri)[0]
                ends = np.unique(np.concatenate([wires.na[ks], wires.nb[ks]]))
                if wires.raw[ri][3] == "fence_post":
                    g.append(int(ends[np.argmin(wires.nodes[ends, 2])]))   # the post top
                else:
                    g.append(int(ends[0]))                                   # the wire
            if fence_meta[j].get("bonded"):
                tops = wires.nodes[g]
                d = np.linalg.norm(wires.nodes[main_nodes][:, None, :] - tops[None, :, :], axis=2)
                k = int(main_nodes[np.unravel_index(np.argmin(d), d.shape)[0]])
                fence_meta[j]["bond_at"] = [float(q) for q in wires.nodes[k]]
                g.append(k)
            groups.append(g)
        fence_node = wires.merge_nodes(groups)
    model = hf.Model(wires, soil, metal=metal)

    feeds = p.get("feeds") or []
    if not feeds:
        a0 = wires.raw[0][0]
        feeds = [dict(x=float(a0[0]), y=float(a0[1]), share=1.0)]
    shares = np.array([float(fd.get("share", 1.0)) for fd in feeds], float)
    if shares.sum() <= 0:
        raise ValueError("The shares of the injection points must add up to more than zero.")
    shares = shares / shares.sum()
    Vn = np.zeros(model.Nn, complex)
    IT = np.zeros(model.N, complex)
    feed_nodes = []
    for fd, s in zip(feeds, shares):
        z = fd.get("z")
        if z is None:
            # the nearest node in plan, at the shallowest depth there
            pxy = np.array([float(fd["x"]), float(fd["y"])])
            d = np.linalg.norm(wires.nodes[:, :2] - pxy[None, :], axis=1)
            near = np.where(d <= d.min() + 1e-6)[0]
            k = int(near[np.argmin(wires.nodes[near, 2])])
        else:
            k = wires.nearest_node([float(fd["x"]), float(fd["y"]), float(z)])
        _, V, _, I_T = model.solve(f, k, s * IG)
        Vn += V
        IT += I_T
        feed_nodes.append(k)
    # the circuit-field matrices are not needed again: free them before the
    # boundary-element half (a few GB for a layered model of 3000 segments)
    model = types.SimpleNamespace(N=int(model.N), Nn=int(model.Nn))

    # bem network over the same segments, for the equipotential comparison and
    # for the surface potential of the leakage currents
    bsoil = bem.SoilModel(rho[0], rho[1] if len(rho) > 1 else None,
                          h[0] if h else None,
                          rho3=rho[2] if len(rho) > 2 else None, h2=h[1] if len(h) > 1 else None,
                          rho4=rho[3] if len(rho) > 3 else None, h3=h[2] if len(h) > 2 else None)
    spec = dict(p)
    spec["items"] = items + fence_items
    net = bem.build_network(spec)
    net.soil = bsoil
    seg_net = np.zeros(model.N, int)
    for j, idx in enumerate(fence_raw):
        seg_net[np.isin(wires.raw_idx, idx)] = int(net.fences[j]["net"])
    segs = []
    for i in range(model.N):
        a, b = wires.p1[i], wires.p2[i]
        lay = bsoil.layer_of(0.5 * (a[2] + b[2]))
        shell = float(wires.sh_rho[i] * wires.sh_ln[i] / (2 * math.pi)) if wires.sh_ln[i] > 0 else 0.0
        segs.append(bem.Segment(a, b, float(wires.rad[i]), wires.segs[i][5], lay,
                                int(seg_net[i]), shell))
    net.segments = segs
    eq = net.solve()
    Rg_eq = float(eq["Rg"])
    I_eq = np.array(net.I, float).copy()

    Vabs = np.abs(Vn)
    vf = Vn[feed_nodes[int(np.argmax(shares))]]
    Zin = vf / IG
    two = None
    IT_field = IT
    if two_scale:
        net_f, IT_field, two = two_scale_leakage(
            spec, bsoil, wires, Vn, IG, seg_user,
            int(p.get("fine_max_segments", bem.MAX_SEGMENTS)),
            grade=str(p.get("grade_ends", True)).lower() not in ("0", "false", "no", "off"))
        two.update(coarse_segments=int(model.N), coarse_length=float(seg))
        net_f.solve()                           # held equipotential, at the fine length
        I_eq = np.array(net_f.I, float).copy()
        net = net_f
    field = _ComplexField(net, IT_field)

    # metal potential seen from the surface: nearest node of a horizontal
    # conductor in plan (equipment is bonded to the grid, not to the rod tips)
    hor = (np.abs(wires.p2[:, 2] - wires.p1[:, 2]) < 1e-6) & (wires.raw_idx < n_main)
    use = np.unique(np.concatenate([wires.na[hor], wires.nb[hor]])) if hor.any() \
        else np.arange(model.Nn)
    NP = wires.nodes[use]
    VP = Vn[use]
    if two_scale:
        # the metal potential at the ends of the fine horizontal segments of
        # the main metal, interpolated along each conductor, so the touch
        # voltage takes the metal at the fine spacing as the surface does
        fseg = [k for k, sg in enumerate(net.segments)
                if abs(sg.p2[2] - sg.p1[2]) < 1e-6 and net.seg_raw[k] < n_main]
        if fseg:
            ends = np.array([q for k in fseg for q in (net.segments[k].p1, net.segments[k].p2)])
            raws = np.repeat(np.asarray(net.seg_raw, int)[fseg], 2)
            ends, iu = np.unique(np.round(ends, 9), axis=0, return_index=True)
            NP = ends
            VP = metal_at_points(wires, Vn, net, ends, raws[iu])

    def metal_at(px, py):
        px = np.asarray(px, float)
        py = np.asarray(py, float)
        d = ((px.ravel()[:, None] - NP[None, :, 0]) ** 2 + (py.ravel()[:, None] - NP[None, :, 1]) ** 2)
        return VP[np.argmin(d, axis=1)].reshape(px.shape)

    xs = [c for it in net.raw for c in (it[0][0], it[1][0])]
    ys = [c for it in net.raw for c in (it[0][1], it[1][1])]
    pad = float(p.get("margin", 10.0))
    xlim = [min(xs) - pad, max(xs) + pad]
    ylim = [min(ys) - pad, max(ys) + pad]
    n = int(p.get("nx", 41))
    gx = np.linspace(xlim[0], xlim[1], n)
    gy = np.linspace(ylim[0], ylim[1], n)
    X, Y = np.meshgrid(gx, gy)
    Vs = field.at(X, Y)
    margin = float(p.get("touch_margin", 1.0))
    zones = p.get("zones") or None
    if zones:
        mask = np.zeros(X.shape, bool)
        for z in zones:
            mask |= ((X >= min(z["x0"], z["x1"])) & (X <= max(z["x0"], z["x1"]))
                     & (Y >= min(z["y0"], z["y1"])) & (Y <= max(z["y0"], z["y1"])))
        inside = lambda px, py: np.any([((px >= min(z["x0"], z["x1"])) & (px <= max(z["x0"], z["x1"]))
                                         & (py >= min(z["y0"], z["y1"])) & (py <= max(z["y0"], z["y1"])))
                                        for z in zones], axis=0)
    else:
        mask = net.touch_region(X, Y, margin)
        inside = lambda px, py: net.touch_region(px, py, margin)
    T = np.abs(metal_at(X, Y) - Vs)
    Tm = np.where(mask, T, -np.inf)
    dx = (gx[-1] - gx[0]) / max(n - 1, 1)

    def ftouch(P):
        ok = inside(P[:, 0], P[:, 1])
        v = np.abs(metal_at(P[:, 0], P[:, 1]) - field.at(P[:, 0], P[:, 1]))
        return np.where(ok, v, -1e30)

    order = np.argsort(Tm.ravel())[::-1][:30]
    pool = [(float(Tm.ravel()[k]), X.ravel()[k], Y.ravel()[k]) for k in order
            if np.isfinite(Tm.ravel()[k])]
    if not zones:
        # the arcs of the reach region round conductor ends and rods, where
        # the surface potential is lowest (as in bem.worst_touch_step)
        C = net._plan_conductors(0)
        E = [tuple(q) for c in C for q in c] + [tuple(q) for q in net._plan_points(0)]
        if E:
            E = np.unique(np.round(np.array(E, float), 6), axis=0)
            ang = np.linspace(0.0, 2 * math.pi, 49)[:-1]
            rr = margin * (1.0 - 1e-6)
            qx = (E[:, 0][:, None] + rr * np.cos(ang)[None, :]).ravel()
            qy = (E[:, 1][:, None] + rr * np.sin(ang)[None, :]).ravel()
            ok = inside(qx, qy)
            if ok.any():
                Tq = np.abs(metal_at(qx[ok], qy[ok]) - field.at(qx[ok], qy[ok]))
                for k in np.argsort(Tq)[::-1][:12]:
                    pool.append((float(Tq[k]), qx[ok][k], qy[ok][k]))
    pool.sort(key=lambda c: -c[0])
    cands = bem.Network._distinct([(c[1], c[2]) for c in pool], max(dx, 1.0))[:5]
    tbest = (-1.0, [0.0, 0.0])
    for c in cands:
        pt, v = bem.Network._climb(ftouch, list(c), [dx / 2, dx / 2], 2, [0.05, 0.05])
        if v > tbest[0]:
            tbest = (v, pt)

    st = float(p.get("step_distance", 1.0))

    def fstep(P):
        q1 = field.at(P[:, 0], P[:, 1])
        q2 = field.at(P[:, 0] + st * np.cos(P[:, 2]), P[:, 1] + st * np.sin(P[:, 2]))
        return np.abs(q1 - q2)

    sc = []
    for th in (0.0, 0.5 * math.pi, 0.25 * math.pi, -0.25 * math.pi):
        V2 = field.at(X + st * math.cos(th), Y + st * math.sin(th))
        S = np.abs(Vs - V2)
        for k in np.argsort(S.ravel())[::-1][:6]:
            sc.append((float(S.ravel()[k]), X.ravel()[k], Y.ravel()[k], th))
            sc.append((float(S.ravel()[k]), X.ravel()[k] + st * math.cos(th),
                       Y.ravel()[k] + st * math.sin(th), th + math.pi))
    sc.sort(key=lambda c: -c[0])
    sbest = (-1.0, [0.0, 0.0, 0.0])
    for s0, cx, cy, th in sc[:5]:
        pt, v = bem.Network._climb(fstep, [cx, cy, th], [dx / 2, dx / 2, math.pi / 8], 3,
                                   [0.05, 0.05, math.radians(2.0)])
        if v > sbest[0]:
            sbest = (v, pt)

    # the same model held equipotential, for comparison (bem's own scan)
    net.I = I_eq
    ws_eq = net.worst_touch_step(xlim, ylim, n, n, st, None, margin, zones=zones)

    # touch voltage on each fence: its own potential minus the soil within
    # reach on either side of the fence line (as bem.fence_touch)
    fences_out = []
    for j, fm in enumerate(fence_meta):
        Vf = Vn[fence_node[j]]
        reach = float(fm.get("reach", 1.0))
        res = {}
        # points on the perpendicular of each fence panel, as bem.fence_touch
        fp = [np.array(q, float) for q in fm["path"]]
        sgn = 1.0
        if fm.get("closed", True):
            Q = fp[:-1] if np.allclose(fp[0], fp[-1]) else fp
            area = 0.5 * sum(Q[i][0] * Q[(i + 1) % len(Q)][1] - Q[(i + 1) % len(Q)][0] * Q[i][1]
                             for i in range(len(Q)))
            sgn = 1.0 if area > 0 else -1.0
        smp, nrm = [], []
        for a, b in zip(fp[:-1], fp[1:]):
            L = float(np.linalg.norm(b - a))
            if L < 1e-9:
                continue
            tt = (b - a) / L
            k = max(2, int(math.ceil(L / 0.5)) + 1)
            for u in np.linspace(0.0, 1.0, k)[:-1]:
                smp.append(a + (b - a) * u)
                nrm.append(np.array([tt[1], -tt[0]]) * sgn)
        smp, nrm = np.array(smp), np.array(nrm)
        for side, offs in (("inside", (-reach, -0.5 * reach)), ("outside", (0.5 * reach, reach))):
            P = np.concatenate([smp + nrm * o for o in offs])
            Tf = np.abs(Vf - field.at(P[:, 0], P[:, 1]))
            i = int(np.argmax(Tf))
            res[side] = dict(touch_max=float(Tf[i]), at=[float(P[i, 0]), float(P[i, 1])])
        side = max(res, key=lambda q: res[q]["touch_max"])
        eqf = next((q for q in ws_eq.get("fences") or [] if q.get("name") == fm.get("name")), {})
        fences_out.append(dict(
            name=fm.get("name", f"fence {j + 1}"), bonded=bool(fm.get("bonded")),
            V_fence=float(abs(Vf)), V_pct_feed=float(abs(Vf) / abs(vf) * 100) if abs(vf) else None,
            touch_max=res[side]["touch_max"], touch_at=res[side]["at"], side=side,
            touch_inside=res["inside"], touch_outside=res["outside"],
            bond_at=fm.get("bond_at"),
            equipotential_touch=float(abs(eqf.get("touch_max", 0.0))) if eqf else None))

    node_pot = [dict(x=float(q[0]), y=float(q[1]), z=float(q[2]), V=float(abs(v)),
                     deg=float(math.degrees(cmath.phase(v))))
                for q, v in zip(wires.nodes, Vn)]
    out = dict(
        f=f, metal=metal, IG=IG, segments=int(model.N), nodes=int(model.Nn),
        Z=dict(re=float(Zin.real), im=float(Zin.imag), abs=float(abs(Zin)),
               deg=float(math.degrees(cmath.phase(Zin)))),
        Rg_equipotential=Rg_eq,
        impedance_ratio=float(abs(Zin) / Rg_eq) if Rg_eq else None,
        GPR_feed=float(abs(vf)), GPR_equipotential=float(Rg_eq * IG),
        V_node_max=float(Vabs.max()), V_node_min=float(Vabs.min()),
        V_min_over_feed=float(Vabs.min() / abs(vf)) if abs(vf) else None,
        touch_max=float(tbest[0]), touch_at=[float(tbest[1][0]), float(tbest[1][1])],
        step_max=float(sbest[0]), step_at=[float(sbest[1][0]), float(sbest[1][1])],
        step_direction_deg=float(math.degrees(sbest[1][2]) % 360.0),
        equipotential=dict(touch_max=float(ws_eq["touch_max"]), step_max=float(ws_eq["step_max"]),
                           touch_at=ws_eq["touch_at"], step_at=ws_eq["step_at"]),
        feeds=[dict(x=float(wires.nodes[k][0]), y=float(wires.nodes[k][1]),
                    z=float(wires.nodes[k][2]), share=float(s))
               for k, s in zip(feed_nodes, shares)],
        surface=dict(x=gx.tolist(), y=gy.tolist(), V=np.abs(Vs).tolist(),
                     touch=np.where(mask, T, np.nan).tolist()),
        node_potentials=node_pot, soil=soil.describe() if hasattr(soil, "describe") else "",
        fences=fences_out, two_scale=two)
    lim = p.get("limits") or {}
    if lim.get("E_touch") or lim.get("E_step"):
        out["checks"] = [
            dict(name="Maximum touch voltage (non-equipotential)", value=out["touch_max"],
                 limit=lim.get("E_touch"), unit="V",
                 passed=(lim.get("E_touch") or 1e18) >= out["touch_max"]),
            dict(name="Maximum step voltage (non-equipotential)", value=out["step_max"],
                 limit=lim.get("E_step"), unit="V",
                 passed=(lim.get("E_step") or 1e18) >= out["step_max"])]
        for fo in fences_out:
            out["checks"].append(dict(
                name=f"Fence touch voltage ({fo['name']}, non-equipotential)",
                value=fo["touch_max"], limit=lim.get("E_touch"), unit="V",
                passed=(lim.get("E_touch") or 1e18) >= fo["touch_max"]))
    ratio = out["impedance_ratio"] or 1.0
    vmin = out["V_min_over_feed"] or 1.0
    out["significant"] = bool(ratio > 1.05 or vmin < 0.9)
    out["note"] = (
        f"With the conductors' own impedance at {f:g} Hz the earth impedance is "
        f"|Z| = {abs(Zin):.4g} Ω against R_g = {Rg_eq:.4g} Ω held equipotential "
        f"({(ratio - 1) * 100:+.1f} %), and the metal furthest from the injection sits at "
        f"{vmin * 100:.0f} % of the feed-point potential. "
        + ("The equipotential assumption is not adequate for this grid: use these touch and "
           "step voltages, and check the GPR at the feed point." if out["significant"] else
           "The equipotential assumption is adequate here (within 5 % on the impedance and "
           "10 % on the metal potential)."))
    warn = [bem.thick_warning(t) for t in (getattr(wires, "thick", None),
                                            getattr(net, "thick", None)) if t]
    if warn:
        out["warnings"] = warn
    if two:
        out["note"] += (
            f" The model was too large for the circuit-field solution at "
            f"{seg_user:g} m: the metal potentials come from {two['coarse_segments']} segments "
            f"of {two['coarse_length']:.3g} m and the leakage currents, surface potentials, "
            f"touch and step voltages from {two['fine_segments']} segments of at most "
            f"{two['fine_length']:.3g} m (two-scale solution; the fine leakage sums to "
            f"{two['current_balance']:.3f} of I_G before scaling).")
    elif seg > 1.0001 * seg_user:
        out["note"] += (f" The segments were lengthened to {seg:.3g} m to keep the model "
                        f"within {int(p.get('max_segments', MAX_SEGMENTS))} segments.")
    return out
