"""
Air-termination design and lightning protection zones to IEC 62305-3:2010.

The earth termination is handled in :mod:`earthsys.iec62305`; this module
covers what happens above ground — where the flash is intercepted and which
volume that interception actually protects.

Three methods are provided, as in clause 5.2.2 of the standard:

* the **rolling sphere method** (Annex A.2), valid for every case,
* the **protective angle method** (Annex A.1), valid only for simple shapes
  and only up to the height of the rolling sphere radius,
* the **mesh method** (Annex A.3), for the protection of flat surfaces.

Rolling sphere geometry
-----------------------
The standard construction is a sphere of radius R that is rolled over the
structure.  Every point the sphere can touch is exposed; every point it
cannot reach is protected.  All of the familiar closed-form results follow
from that single statement, and this module derives them rather than
tabulating them.

For a vertical air termination of height ``h`` standing on flat ground, a
sphere resting on the ground has its centre at height ``R``.  It touches the
tip when the horizontal distance from the mast is

    a(h) = sqrt(2·R·h − h²)                                        (h ≤ 2R)

so the protected radius measured at a reference plane of height ``h_x`` is

    r_p = a(h) − a(h_x)                                            (h < R)

and, once the mast is at least as tall as the sphere, the mast body itself
keeps the sphere at arm's length and the radius saturates at

    r_p = R − a(h_x)                                               (h ≥ R)

Between two terminations the sphere sags between the tips.  Resting on both,
its centre sits a height sqrt(R² − (d/2)²) above the line joining them, so the
lowest protected point on the span is depressed by

    p = R − sqrt(R² − (d/2)²)                                      (the sag)

For anything more complicated than that — several masts of different heights,
a mast standing on a roof, a catenary wire, a building whose own edges
intercept the flash — the module rolls the sphere numerically.  Every solid
surface is sampled into capture points and a ball of radius R is marched over
them; the sequence of arcs it rests on is the boundary of the protected
volume.  The closed-form results above fall out of the same march, which is
used as a cross-check.
"""

from __future__ import annotations

import math

# --------------------------------------------------------------------------
# class parameters
# --------------------------------------------------------------------------

#: Rolling sphere radius, IEC 62305-3 Table 2.
ROLLING_SPHERE_R = {"I": 20.0, "II": 30.0, "III": 45.0, "IV": 60.0}

#: Mesh size for the mesh method, IEC 62305-3 Table 2.
MESH_SIZE = {"I": 5.0, "II": 10.0, "III": 15.0, "IV": 20.0}

#: Typical distance between down-conductors, IEC 62305-3 Table 4.
DOWN_SPACING = {"I": 10.0, "II": 10.0, "III": 15.0, "IV": 20.0}

# The protective angle of IEC 62305-3 Figure 1 is published as a graph, not as
# a table of numbers, so the curves below are a digitisation of that figure.
# They are held here as data, and deliberately kept separate from the rolling
# sphere, which is derived exactly.  Verify these against your own copy of the
# standard before using the protective angle method for a submitted design;
# the rolling sphere result is the one this program treats as authoritative.
PROTECTIVE_ANGLE = {
    "I":   [(0, 80), (2, 71), (5, 68), (10, 61), (15, 48), (20, 25)],
    "II":  [(0, 80), (2, 74), (5, 72), (10, 65), (15, 58), (20, 50),
            (25, 40), (30, 25)],
    "III": [(0, 80), (2, 77), (5, 76), (10, 72), (15, 66), (20, 60),
            (30, 48), (40, 34), (45, 25)],
    "IV":  [(0, 80), (2, 79), (5, 78), (10, 74), (15, 70), (20, 66),
            (30, 57), (40, 47), (50, 36), (60, 25)],
}

PROTECTIVE_ANGLE_SOURCE = (
    "Digitised from IEC 62305-3:2010 Figure 1. The figure is published as a "
    "graph; these are read-off values and should be confirmed against the "
    "standard. The rolling sphere result is derived exactly and governs."
)


def _cls(lps_class: str) -> str:
    c = str(lps_class or "III").strip().upper()
    return c if c in ROLLING_SPHERE_R else "III"


def class_data(lps_class: str) -> dict:
    c = _cls(lps_class)
    return dict(lps_class=c, R=ROLLING_SPHERE_R[c], mesh=MESH_SIZE[c],
                down_spacing=DOWN_SPACING[c])


def protective_angle(lps_class: str, h: float) -> dict:
    """Protective angle alpha for a termination of height ``h`` above the
    plane it is protecting.  ``None`` above the rolling sphere radius, where
    the method is not permitted (IEC 62305-3 Table 2, note)."""
    c = _cls(lps_class)
    R = ROLLING_SPHERE_R[c]
    tab = PROTECTIVE_ANGLE[c]
    if h > R:
        return dict(applicable=False, alpha=None, h=h, R=R, lps_class=c,
                    reason="The protective angle method is not applicable "
                           "above h = R; use the rolling sphere.")
    a = tab[-1][1]
    for i in range(len(tab) - 1):
        x0, y0 = tab[i]
        x1, y1 = tab[i + 1]
        if x0 <= h <= x1:
            f = 0.0 if x1 == x0 else (h - x0) / (x1 - x0)
            a = y0 + f * (y1 - y0)
            break
    return dict(applicable=True, alpha=a, h=h, R=R, lps_class=c,
                radius=h * math.tan(math.radians(a)),
                source=PROTECTIVE_ANGLE_SOURCE)


# --------------------------------------------------------------------------
# closed-form rolling sphere results
# --------------------------------------------------------------------------

def _a(R: float, z: float) -> float:
    """Horizontal half-chord of a ground-resting sphere at height ``z``."""
    if z <= 0.0:
        return 0.0
    if z >= 2.0 * R:
        return 0.0
    return math.sqrt(2.0 * R * z - z * z)


def protection_radius(R: float, h: float, hx: float = 0.0) -> float:
    """Radius protected by one vertical termination of height ``h``, measured
    on a reference plane at height ``hx``.  Both heights are above the plane
    the sphere rolls on."""
    if h <= hx:
        return 0.0
    reach = R if h >= R else _a(R, h)
    return max(0.0, reach - _a(R, hx))


def sphere_sag(R: float, d: float) -> float:
    """Penetration of the sphere between two equal terminations ``d`` apart."""
    if d <= 0:
        return 0.0
    if d >= 2.0 * R:
        return R          # the sphere reaches the plane between them
    return R - math.sqrt(R * R - (d / 2.0) ** 2)


def max_span(R: float, h: float, hx: float = 0.0) -> float:
    """Largest spacing between two terminations of height ``h`` for which the
    sphere still does not reach the plane at ``hx``."""
    p = h - hx
    if p <= 0:
        return 0.0
    if p >= R:
        return 2.0 * R
    return 2.0 * math.sqrt(max(0.0, R * R - (R - p) ** 2))


# --------------------------------------------------------------------------
# numerical rolling sphere — marching a ball over the capture points
# --------------------------------------------------------------------------

def _upper_centre(a, b, R):
    """Centre of the circle of radius ``R`` through ``a`` and ``b``, taking
    the solution on the upper side."""
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    d = math.hypot(dx, dz)
    if d < 1e-9 or d > 2.0 * R:
        return None
    mx, mz = (ax + bx) / 2.0, (az + bz) / 2.0
    q = math.sqrt(max(0.0, R * R - (d / 2.0) ** 2))
    nx, nz = -dz / d, dx / d
    c1 = (mx + nx * q, mz + nz * q)
    c2 = (mx - nx * q, mz - nz * q)
    return c1 if c1[1] >= c2[1] else c2


_TWO_PI = 2.0 * math.pi


def _cw(from_ang: float, to_ang: float) -> float:
    """Clockwise rotation from one angle to another, in [0, 2*pi)."""
    d = (from_ang - to_ang) % _TWO_PI
    return d


def roll_sphere(points, R, x_lo, x_hi, ground=0.0, samples=720):
    """March a ball of radius ``R`` from left to right over ``points``.

    ``points`` is the sampled solid geometry: air-termination tips, roof and
    wall surfaces, catenary wires — everything the flash could attach to.

    Returns the boundary of the protected volume as a height profile
    ``z(x)`` on a uniform grid, together with the contact points the ball
    actually rested on and a few ball positions worth drawing.
    """
    pts = [(float(x), float(z)) for x, z in points if z is not None]
    pts = [p for p in pts if p[1] > ground + 1e-9]
    if not pts:
        return dict(x=[], z=[], supports=[], spheres=[], arcs=[])
    pts.sort()

    arcs = []       # (cx, cz, x_from, x_to)  boundary arcs of radius R
    supports = []   # contact points the ball rested on
    spheres = []    # ball positions worth drawing

    eps = 1e-9
    start = min(p[0] for p in pts) - 2.2 * R
    stop = max(p[0] for p in pts) + 2.2 * R
    cx = start
    guard = 0
    state = "ground"
    pivot = None
    ang = 0.0

    while guard < 20000:
        guard += 1
        if state == "ground":
            # slide right along the ground until the ball first touches a point
            best = None
            for p in pts:
                if p[1] >= 2.0 * R:
                    continue
                xc = p[0] - _a(R, p[1])
                if xc > cx + 1e-7 and (best is None or xc < best[0]):
                    best = (xc, p)
            if best is None:
                break
            xc, p = best
            # the arc rising from the ground contact to that point
            arcs.append((xc, ground + R, xc, p[0]))
            spheres.append(dict(cx=xc, cz=ground + R, contacts=[[p[0], p[1]]],
                                ground=True))
            supports.append(dict(x=p[0], z=p[1]))
            pivot = p
            ang = math.atan2((ground + R) - p[1], xc - p[0])
            cx = xc
            state = "pivot"
            continue

        # pivot phase: rotate the ball clockwise about the current support
        A = pivot
        # (a) rotation at which the ball meets the ground again
        v = (ground + R - A[1]) / R
        d_ground = None
        if -1.0 <= v <= 1.0:
            phi_g = math.asin(v)                # right-hand descent branch
            d_ground = _cw(ang, phi_g)
            if d_ground < 1e-9:
                d_ground += _TWO_PI
        # (b) rotation at which it meets another capture point
        d_best, B, C_best = None, None, None
        for p in pts:
            if abs(p[0] - A[0]) < 1e-12 and abs(p[1] - A[1]) < 1e-12:
                continue
            if math.hypot(p[0] - A[0], p[1] - A[1]) > 2.0 * R:
                continue
            C = _upper_centre(A, p, R)
            if C is None:
                continue
            phi = math.atan2(C[1] - A[1], C[0] - A[0])
            d = _cw(ang, phi)
            if d < 1e-9:
                d += _TWO_PI
            if d > math.pi + 1e-9:      # behind the direction of travel
                continue
            if d_best is None or d < d_best:
                d_best, B, C_best = d, p, C

        if d_best is not None and (d_ground is None or d_best <= d_ground):
            arcs.append((C_best[0], C_best[1], min(A[0], B[0]), max(A[0], B[0])))
            if abs(B[0] - A[0]) > 0.35 * R:
                spheres.append(dict(cx=C_best[0], cz=C_best[1],
                                    contacts=[[A[0], A[1]], [B[0], B[1]]],
                                    ground=False))
            supports.append(dict(x=B[0], z=B[1]))
            pivot = B
            ang = math.atan2(C_best[1] - B[1], C_best[0] - B[0])
            continue

        # the ball rolls off onto the ground
        if d_ground is None:
            break
        phi = ang - d_ground
        Cx = A[0] + R * math.cos(phi)
        arcs.append((Cx, ground + R, A[0], Cx))
        spheres.append(dict(cx=Cx, cz=ground + R, contacts=[[A[0], A[1]]],
                            ground=True))
        cx = Cx
        state = "ground"
        if cx > stop:
            break

    # ------------------------------------------------- sample the boundary
    n = max(120, int(samples))
    xs = [x_lo + (x_hi - x_lo) * i / (n - 1) for i in range(n)]
    zs = [ground] * n
    for (ccx, ccz, xa, xb) in arcs:
        if xb < x_lo or xa > x_hi:
            continue
        for i, x in enumerate(xs):
            if x < xa - 1e-9 or x > xb + 1e-9:
                continue
            dx = x - ccx
            if abs(dx) > R:
                continue
            z = ccz - math.sqrt(max(0.0, R * R - dx * dx))
            if z > zs[i]:
                zs[i] = z
    # the boundary can never dip below the plane
    zs = [max(ground, z) for z in zs]

    # keep the supports tidy: one entry per distinct contact
    tidy, seen = [], set()
    for s in supports:
        key = (round(s["x"], 3), round(s["z"], 3))
        if key in seen:
            continue
        seen.add(key)
        tidy.append(s)

    # thin the drawn ball positions so the elevation stays readable
    spheres.sort(key=lambda s: s["cx"])
    drawn, last = [], None
    for s in spheres:
        if last is None or abs(s["cx"] - last) > 0.5 * R:
            drawn.append(s)
            last = s["cx"]

    return dict(x=xs, z=zs, supports=tidy, spheres=drawn[:8],
                arcs=[dict(cx=a[0], cz=a[1], x0=a[2], x1=a[3]) for a in arcs])


def _profile_height(prof, x):
    """Boundary height of a rolled profile at an arbitrary x."""
    xs, zs = prof["x"], prof["z"]
    if not xs or x < xs[0] or x > xs[-1]:
        return 0.0
    n = len(xs)
    f = (x - xs[0]) / (xs[-1] - xs[0]) * (n - 1)
    i = min(n - 2, max(0, int(f)))
    t = f - i
    return zs[i] + t * (zs[i + 1] - zs[i])


# --------------------------------------------------------------------------
# geometry assembly
# --------------------------------------------------------------------------

def _sample_segment(p0, p1, step):
    x0, z0 = p0
    x1, z1 = p1
    d = math.hypot(x1 - x0, z1 - z0)
    n = max(1, int(math.ceil(d / step)))
    return [(x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * i / n) for i in range(n + 1)]


def build_geometry(structure, terminals, catenaries=None, step=None, R=45.0):
    """Sample every solid surface into capture points for the ball march.

    ``structure``  dict(width, height) — a rectangle in elevation, centred on
                   x = 0, standing on the reference plane.  ``height`` may be
                   zero for open ground.
    ``terminals``  list of dict(x, height, base) — vertical rods.  ``base``
                   defaults to the roof when the rod stands within the
                   structure footprint, otherwise to the ground.
    ``catenaries`` list of dict(x0, z0, x1, z1) — horizontal or sloping wires.
    """
    step = step or max(0.25, R / 90.0)
    pts = []
    parts = dict(roof=[], walls=[], terminals=[], catenaries=[])

    w = float(structure.get("width", 0.0) or 0.0)
    hgt = float(structure.get("height", 0.0) or 0.0)
    x0, x1 = -w / 2.0, w / 2.0
    if w > 0 and hgt > 0:
        roof = _sample_segment((x0, hgt), (x1, hgt), step)
        # the walls only matter near the top, but sampling them all is cheap
        wl = _sample_segment((x0, 0.0), (x0, hgt), step)
        wr = _sample_segment((x1, 0.0), (x1, hgt), step)
        pts += roof + wl + wr
        parts["roof"] = [x0, x1, hgt]
        parts["walls"] = [[x0, hgt], [x1, hgt]]

    for t in terminals or []:
        tx = float(t.get("x", 0.0))
        th = float(t.get("height", 0.0) or 0.0)
        base = t.get("base")
        if base is None:
            base = hgt if (w > 0 and hgt > 0 and x0 - 1e-9 <= tx <= x1 + 1e-9) else 0.0
        base = float(base)
        tip = base + th
        pts += _sample_segment((tx, base), (tx, tip), step)
        parts["terminals"].append(dict(x=tx, base=base, height=th, tip=tip))

    for c in catenaries or []:
        a = (float(c.get("x0", 0)), float(c.get("z0", 0)))
        b = (float(c.get("x1", 0)), float(c.get("z1", 0)))
        pts += _sample_segment(a, b, step)
        parts["catenaries"].append(dict(x0=a[0], z0=a[1], x1=b[0], z1=b[1]))

    return pts, parts


# --------------------------------------------------------------------------
# plan-view coverage
# --------------------------------------------------------------------------

def plan_coverage(R, masts, roof, hx=0.0, grid=41):
    """Coverage of a rectangular plane by the protected circles of a set of
    vertical terminations, evaluated at the reference height ``hx``.

    ``masts`` list of dict(x, y, height) with the height measured above the
    plane being protected.  ``roof`` dict(width, depth).
    """
    W = float(roof.get("width", 0.0) or 0.0)
    D = float(roof.get("depth", 0.0) or 0.0)
    circles = []
    for mst in masts:
        h = float(mst.get("height", 0.0) or 0.0)
        r = protection_radius(R, h, hx)
        circles.append(dict(x=float(mst.get("x", 0.0)), y=float(mst.get("y", 0.0)),
                            r=r, height=h))
    if W <= 0 or D <= 0:
        return dict(circles=circles, covered_fraction=None, uncovered=[],
                    corners=[])

    n = max(11, int(grid))
    uncovered = []
    covered = 0
    total = 0
    for i in range(n):
        for j in range(n):
            x = -W / 2.0 + W * i / (n - 1)
            y = -D / 2.0 + D * j / (n - 1)
            total += 1
            if any((x - c["x"]) ** 2 + (y - c["y"]) ** 2 <= c["r"] ** 2 for c in circles):
                covered += 1
            else:
                uncovered.append([round(x, 3), round(y, 3)])
    corners = []
    for (x, y) in ((-W / 2, -D / 2), (W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2)):
        ok = any((x - c["x"]) ** 2 + (y - c["y"]) ** 2 <= c["r"] ** 2 for c in circles)
        corners.append(dict(x=x, y=y, protected=ok))
    return dict(circles=circles, covered_fraction=covered / total if total else None,
                uncovered=uncovered[:900], corners=corners,
                width=W, depth=D, n=n)


# --------------------------------------------------------------------------
# mesh method
# --------------------------------------------------------------------------

def mesh_method(lps_class, width, depth, mesh=None):
    """Mesh air-termination on a flat surface, IEC 62305-3 Annex A.3."""
    cd = class_data(lps_class)
    req = cd["mesh"]
    use = float(mesh) if mesh else req
    nx = max(2, int(math.ceil(width / use)) + 1) if width > 0 else 0
    ny = max(2, int(math.ceil(depth / use)) + 1) if depth > 0 else 0
    ax = width / (nx - 1) if nx > 1 else 0.0
    ay = depth / (ny - 1) if ny > 1 else 0.0
    length = nx * depth + ny * width
    per = 2.0 * (width + depth)
    n_down = max(2, int(math.ceil(per / cd["down_spacing"])))
    return dict(lps_class=cd["lps_class"], mesh_required=req, mesh_used=use,
                conductors_x=nx, conductors_y=ny,
                actual_spacing_x=ax, actual_spacing_y=ay,
                compliant=(ax <= req + 1e-9 and ay <= req + 1e-9),
                total_length=length, perimeter=per,
                n_down=n_down, down_spacing=cd["down_spacing"],
                actual_down_spacing=per / n_down if n_down else None,
                note="Mesh conductors must follow the roof edges and the "
                     "shortest possible route; no point of the protected "
                     "surface may be further from a conductor than the mesh "
                     "size (IEC 62305-3 Annex A.3).")


# --------------------------------------------------------------------------
# the complete assessment
# --------------------------------------------------------------------------

def design(lps_class="III", structure=None, terminals=None, catenaries=None,
           reference_plane=None, roof_depth=None, equipment=None,
           mesh=None, view=None):
    """Assess an air-termination arrangement by all three methods.

    Everything is expressed in an elevation through the structure: x across,
    z up from ground level.  The plan-view check treats the roof as a
    rectangle of ``structure.width`` by ``roof_depth``.
    """
    cd = class_data(lps_class)
    R = cd["R"]
    structure = dict(structure or {})
    terminals = list(terminals or [])
    W = float(structure.get("width", 0.0) or 0.0)
    H = float(structure.get("height", 0.0) or 0.0)
    D = float(roof_depth if roof_depth is not None else structure.get("depth", W) or 0.0)

    # the plane being protected: the roof if there is one, otherwise the ground
    ref = float(reference_plane) if reference_plane is not None else (H if H > 0 else 0.0)

    pts, parts = build_geometry(structure, terminals, catenaries, R=R)
    if not pts:
        raise ValueError("Define a structure or at least one air termination.")

    span = max(p[0] for p in pts) - min(p[0] for p in pts)
    pad = max(1.25 * R, 0.8 * span + 6.0)
    x_lo = min(p[0] for p in pts) - pad
    x_hi = max(p[0] for p in pts) + pad
    prof = roll_sphere(pts, R, x_lo, x_hi, ground=0.0)

    # ------------------------------------------------ per-terminal results
    term = []
    for t in parts["terminals"]:
        above_ref = t["tip"] - ref
        rp_ref = protection_radius(R, max(0.0, t["tip"] - ref), 0.0) if above_ref > 0 else 0.0
        pa = protective_angle(cd["lps_class"], max(0.0, above_ref))
        term.append(dict(
            x=t["x"], base=t["base"], height=t["height"], tip=t["tip"],
            above_reference=above_ref,
            r_protected=rp_ref,
            r_ground=protection_radius(R, t["tip"], 0.0),
            protective_angle=pa,
            angle_radius=(pa["radius"] if pa.get("applicable") else None),
            tall=t["tip"] >= R))

    # ------------------------------------------------------ spans and sag
    # The elevation is a section, so terminations that share an x collapse onto
    # one another; keep the tallest at each station before measuring the spans.
    by_x = {}
    for t in term:
        k = round(t["x"], 4)
        if k not in by_x or t["tip"] > by_x[k]["tip"]:
            by_x[k] = t
    spans = []
    xs_t = sorted(by_x.values(), key=lambda t: t["x"])
    for a, b in zip(xs_t, xs_t[1:]):
        d = b["x"] - a["x"]
        lower = min(a["tip"], b["tip"])
        sag = sphere_sag(R, d) if abs(a["tip"] - b["tip"]) < 1e-6 else None
        mid = (a["x"] + b["x"]) / 2.0
        ph = _profile_height(prof, mid)
        spans.append(dict(x0=a["x"], x1=b["x"], d=d,
                          sag=sag,
                          protected_height=ph,
                          clears_reference=ph >= ref - 1e-6,
                          required_tip=(ref + sag) if sag is not None else None,
                          max_span=max_span(R, lower - ref, 0.0) if lower > ref else 0.0))

    # ------------------------------------------------- what is left exposed
    #
    # The roof edges and corners are treated separately from the roof field.
    # A sphere resting on the ground beside the building touches the roof edge
    # long before it can reach the middle of the roof, which is exactly why
    # IEC 62305-3 asks for air terminations on the corners and along the
    # exposed edges and not only in the middle of the surface.
    exposed = []
    field_exposed = []
    edge_exposed = []
    band = min(1.0, 0.06 * W) if W > 0 else 0.0
    if W > 0 and H > 0:
        n = 81
        for i in range(n):
            x = -W / 2.0 + W * i / (n - 1)
            e = _profile_height(prof, x)
            if e >= H - 1e-6:
                continue
            is_edge = (abs(abs(x) - W / 2.0) <= band + 1e-9)
            rec = dict(x=round(x, 3), z=H, margin=round(e - H, 3),
                       what="roof edge" if is_edge else "roof surface")
            exposed.append(rec)
            (edge_exposed if is_edge else field_exposed).append(rec)
    field_protected = not field_exposed
    edges_protected = not edge_exposed

    for e in (equipment or []):
        ex, ez = float(e.get("x", 0.0)), float(e.get("z", 0.0))
        env = _profile_height(prof, ex)
        if env < ez - 1e-6:
            exposed.append(dict(x=ex, z=ez, what=e.get("name", "equipment"),
                                margin=round(env - ez, 3)))

    # --------------------------------------------------------- plan check
    masts_plan = []
    for src, res in zip(terminals, term):
        masts_plan.append(dict(x=res["x"], y=float(src.get("y", 0.0) or 0.0),
                               height=max(0.0, res["above_reference"])))
    plan = plan_coverage(R, masts_plan, dict(width=W, depth=D), hx=0.0)

    msh = mesh_method(cd["lps_class"], W, D, mesh)

    # -------------------------------------------------------------- checks
    checks = [
        dict(name="Air terminations provided",
             passed=len(term) >= 1, value=len(term), unit="-",
             note="At least one is required; the arrangement is judged by the "
                  "rolling sphere, not by the count."),
    ]
    if W > 0 and H > 0:
        checks.insert(0, dict(
            name="Rolling sphere — roof surface",
            passed=field_protected,
            value=len(field_exposed), limit=0, unit="points",
            note=(f"No part of the roof field can be touched by a sphere of "
                  f"radius {R:g} m."
                  if field_protected else
                  "The sphere reaches the roof between the air terminations. "
                  "Add a termination, raise the existing ones, or reduce the "
                  "spacing below the maximum span for this class.")))
        checks.insert(1, dict(
            name="Rolling sphere — roof edges and corners",
            passed=edges_protected,
            value=len(edge_exposed), limit=0, unit="points",
            note=("The edges are covered by the terminations shown."
                  if edges_protected else
                  "A sphere resting on the ground beside the building touches "
                  "the roof edge. The edges and corners are the most exposed "
                  "points of any flat roof: IEC 62305-3 clause 5.2.3 asks for "
                  "air terminations on the corners and along the exposed "
                  "edges, usually a perimeter conductor with short rods at "
                  "the corners.")))
    else:
        checks.insert(0, dict(
            name="Rolling sphere — protected volume",
            passed=not exposed, value=len(exposed), limit=0, unit="points",
            note=f"Evaluated against a sphere of radius {R:g} m."))
    if plan.get("covered_fraction") is not None:
        checks.append(dict(
            name="Plan coverage of the protected area",
            passed=plan["covered_fraction"] >= 0.999,
            value=100.0 * plan["covered_fraction"], limit=100.0, unit="%",
            note="Union of the protected circles of every vertical "
                 "termination, evaluated on the protected plane."))
        checks.append(dict(
            name="Corners of the protected area",
            passed=all(c["protected"] for c in plan["corners"]),
            value=sum(1 for c in plan["corners"] if c["protected"]),
            limit=4, unit="-",
            note="Corners are the most exposed points of any flat roof."))
    for s in spans:
        if s["sag"] is not None:
            checks.append(dict(
                name=(f"Sphere penetration over the span x = {s['x0']:.1f} m "
                      f"to {s['x1']:.1f} m ({s['d']:.1f} m apart)"),
                passed=s["clears_reference"],
                value=s["sag"], limit=None, unit="m",
                note=f"The sphere sags {s['sag']:.2f} m below the tips; the "
                     f"protected height at mid-span is "
                     f"{s['protected_height']:.2f} m against a plane at {ref:.2f} m."
                     + (f" Tips would have to reach {s['required_tip']:.2f} m "
                        f"at this spacing." if not s["clears_reference"] else "")))
    checks.append(dict(name="Mesh size for the class",
                       passed=msh["compliant"],
                       value=max(msh["actual_spacing_x"], msh["actual_spacing_y"]),
                       limit=msh["mesh_required"], unit="m",
                       note="Only relevant if the mesh method is used on the "
                            "flat surface."))
    checks.append(dict(name="Down-conductor spacing",
                       passed=(msh["actual_down_spacing"] or 0) <= cd["down_spacing"] + 1e-9,
                       value=msh["actual_down_spacing"], limit=cd["down_spacing"],
                       unit="m",
                       note="IEC 62305-3 Table 4 typical distance between "
                            "down-conductors."))

    return dict(
        lps_class=cd["lps_class"], R=R, mesh_size=cd["mesh"],
        reference_plane=ref,
        structure=dict(width=W, height=H, depth=D,
                       x0=-W / 2.0 if W else 0.0, x1=W / 2.0 if W else 0.0),
        terminals=term, geometry=parts,
        envelope=dict(x=[round(v, 3) for v in prof["x"]],
                      z=[round(v, 3) for v in prof["z"]]),
        spheres=prof["spheres"], supports=prof["supports"],
        spans=spans, exposed=exposed[:80], exposed_count=len(exposed),
        plan=plan, mesh=msh,
        view=dict(x_lo=x_lo, x_hi=x_hi),
        protective_angle_source=PROTECTIVE_ANGLE_SOURCE,
        checks=checks,
        passed=all(c["passed"] for c in checks),
        method_note=(
            "The rolling sphere is applied in the elevation shown. It is the "
            "only method valid for every case; the protective angle is given "
            "for comparison and is only permitted up to h = R, and the mesh "
            "method applies to flat surfaces."))
