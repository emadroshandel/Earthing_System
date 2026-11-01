"""Transferred potential along long metallic paths at power frequency.

A pipe, rail, cable screen or bare earth wire that leaves an earthing
system carries part of its potential rise elsewhere (IEEE Std 80 clause
17.3).  It is not equipotential: it has a series impedance with earth
return and leaks current into the soil along its length, so its potential
falls with distance.  The conductor is modelled as a lossy transmission
line in the ladder form

        node k --- z dx --- node k+1
          |
        g dx  (to the soil potential V_s(x) at that node)

driven by

  * the bond at the station end (directly to the GPR, through a bonding
    resistance, or not at all for an insulated joint), and
  * the potential the station imposes on the soil along the route,
    V_s(x) = GPR * f(x), which a bare or poorly coated conductor picks up
    by conduction even when it is insulated from the grid.

Everything is linear in the GPR, so the current a bonded conductor draws
away from the grid follows in closed form and the GPR is corrected for it.
The coupling is one way: the conductor's own leakage does not change the
soil potential around the station.  For a bare conductor bonded to the
grid that is the dominant approximation, and the result is conservative
for the transferred voltage at the far end.

Since 1.8.8 bare and coated conductors are solved together with the station
(coupled_transferred_potential): the route's segments leak into the soil
through the same potential-coefficient matrix as the grid's.  Against the
full circuit-field solution of hf.py for a 2 km bare copper wire bonded to
IEEE 80 Annex H Grid 3 the coupled solution gives the GPR within 1.2 %, the
current drawn within 1.4 % and the touch voltage along the route within 3 %;
the one-way model was 10 % high on the GPR and 2–2.5 times high on the touch
voltage, because it leaves out the wire's own leakage, which lifts the soil
beside it.  For a coated pipe the two agree beyond the station's edge.

Units: SI, impedances per metre, conductances per metre.
"""
from __future__ import annotations

import cmath
import math

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:          # pragma: no cover
    np = None
    HAVE_NUMPY = False

MU0 = 4e-7 * math.pi
EULER_GAMMA = 0.5772156649

# Typical values, quoted in the help text and used as defaults.
METALS = {
    # resistivity (ohm.m), relative permeability
    "copper": (1.72e-8, 1.0),
    "aluminium": (2.83e-8, 1.0),
    "lead": (2.2e-7, 1.0),
    "steel": (1.8e-7, 300.0),
}

KINDS = ("bare", "coated", "insulated", "rail", "custom")


def carson_external(rho_soil: float, f: float, radius: float) -> complex:
    """Self impedance of a conductor with earth return (Carson), ohm/m,
    excluding the conductor's own internal impedance.

    R = pi^2 f 1e-7  (the earth-return resistance, independent of rho)
    X = omega mu0 / (2 pi) ln(De / r),  De = 658.5 sqrt(rho / f)
    For a buried conductor the depth makes no practical difference at
    50/60 Hz because De is hundreds of metres.
    """
    w = 2 * math.pi * f
    De = 658.5 * math.sqrt(rho_soil / f)
    return complex(math.pi ** 2 * f * 1e-7,
                   w * MU0 / (2 * math.pi) * math.log(De / max(radius, 1e-6)))


def internal_impedance(radius: float, f: float, metal: str = "copper",
                       wall: float | None = None,
                       r_dc_per_km: float | None = None) -> complex:
    """Internal impedance of a round conductor or tube, ohm/m.

    A given d.c. resistance takes precedence (non-magnetic conductors).
    Otherwise the skin depth decides: a wall (or radius) thicker than about
    two skin depths uses the surface-impedance form (1+j) rho / (2 pi r delta),
    which is what makes a steel pipe several times more resistive at 50 Hz
    than at d.c.; a thinner one uses the d.c. value.
    """
    rho_m, mu_r = METALS.get(metal, METALS["copper"])
    w = 2 * math.pi * f
    t = wall if wall not in (None, "", 0) else radius
    t = min(float(t), radius)
    area = math.pi * (radius ** 2 - (radius - t) ** 2)
    rdc = (float(r_dc_per_km) / 1000.0 if r_dc_per_km not in (None, "")
           else rho_m / area)
    delta = math.sqrt(2 * rho_m / (w * MU0 * mu_r))
    if t > 2 * delta:
        zs = (1 + 1j) * rho_m / (2 * math.pi * radius * delta)
        return complex(max(zs.real, rdc), zs.imag)
    # thin wall: d.c. resistance plus the internal inductance of a solid
    # conductor, mu/(8 pi) per metre, which is an upper bound for a tube
    return complex(rdc, w * MU0 * mu_r / (8 * math.pi) * (t / radius))


def soil_leakage(rho_soil: float, radius: float, depth: float,
                 length: float) -> float:
    """Leakage conductance per metre of a long bare conductor, S/m.

    From the resistance of a horizontal wire of length l at depth d
    (Sunde / Dwight):  R = rho / (pi l) [ln(2 l / sqrt(2 a d)) - 1],
    so g = 1 / (R l).  `length` is the length over which the conductor is
    effectively at one potential -- the smaller of its actual length and
    its attenuation length -- and enters only through the logarithm.
    """
    d = max(depth, radius)
    L = max(length, 10 * d)
    return math.pi / (rho_soil * (math.log(2 * L / math.sqrt(2 * radius * d)) - 1.0))


def line_parameters(kind: str, rho_soil: float, length: float, radius: float,
                    depth: float = 1.0, f: float = 50.0, metal: str = "steel",
                    wall: float | None = None, r_dc_per_km=None,
                    coating_res: float | None = None,
                    leak_ohm_km: float | None = None,
                    z_per_km: complex | None = None) -> dict:
    """Series impedance z (ohm/m) and leakage conductance g (S/m).

    kind = 'bare'      metal in contact with the soil (earth wire, bare pipe)
           'coated'    pipe with a coating of specific resistance
                       `coating_res` (ohm.m^2, 1e4 poor ... 1e6 good)
           'insulated' cable screen or sheathed conductor: no leakage except
                       where it is earthed at the ends
           'rail'      leakage given directly as rail-to-earth resistance
                       `leak_ohm_km` (ohm.km); typical 2 ... 20
           'custom'    z_per_km and leak_ohm_km both given
    """
    if kind not in KINDS:
        raise ValueError(f"Unknown conductor kind '{kind}'. Use one of {KINDS}.")
    if rho_soil <= 0 or length <= 0 or radius <= 0:
        raise ValueError("Soil resistivity, length and radius must be positive.")
    if z_per_km not in (None, ""):
        z = complex(z_per_km) / 1000.0
    else:
        z = carson_external(rho_soil, f, radius) + internal_impedance(
            radius, f, metal, wall, r_dc_per_km)
    note = ""
    if kind == "insulated":
        g = 0.0
    elif kind in ("rail", "custom"):
        if leak_ohm_km in (None, "") or float(leak_ohm_km) <= 0:
            raise ValueError("Give the conductor-to-earth leakage resistance "
                             "in ohm.km.")
        g = 1.0 / (float(leak_ohm_km) * 1000.0)
    else:
        # the attenuation length enters the soil term logarithmically; two
        # passes are plenty
        Le = length
        for _ in range(3):
            gs = soil_leakage(rho_soil, radius, depth, Le)
            g = gs
            if kind == "coated":
                if coating_res in (None, "") or float(coating_res) <= 0:
                    raise ValueError("Give the coating specific resistance "
                                     "(ohm.m²).")
                gc = 2 * math.pi * radius / float(coating_res)
                g = 1.0 / (1.0 / gs + 1.0 / gc)
            gam = cmath.sqrt(z * g)
            Le = min(length, 1.0 / max(gam.real, 1e-12))
        note = f"leakage from a {Le:.0f} m effective length"
    gam = cmath.sqrt(z * g) if g > 0 else 0j
    return dict(z=z, g=g, gamma=gam,
                Z0=(cmath.sqrt(z / g) if g > 0 else None),
                attenuation_length=(1.0 / gam.real if g > 0 and gam.real > 0
                                    else None),
                note=note)


def solve_ladder(L: float, z: complex, g: float, Vs, *, n: int | None = None,
                 near: str = "bonded", R_bond: float = 0.0, V_near: complex = 1.0,
                 far: str = "open", R_far: float | None = None,
                 V_far_soil: complex | None = None, x_nodes=None, emf=None):
    """Node potentials of the lossy line.

    L, z, g     length (m), series impedance (ohm/m), leakage (S/m)
    Vs          callable x -> soil potential (V) at the conductor, or an
                array of n+1 values at the nodes
    near        'bonded' (to V_near through R_bond) or 'insulated'
    far         'open', 'earthed' (through R_far to the local soil) or
                'remote' (through R_far to remote earth, 0 V)
    emf         optional callable x -> series EMF per metre (V/m, complex)
                induced along the conductor, positive driving current
                away from the station (inductive coupling, 1.8.0)
    Returns x, V_metal, V_soil, I_series (A, node k to k+1), I_near
    (current drawn from the station end).
    """
    if not HAVE_NUMPY:
        raise RuntimeError("The transferred-potential solver needs numpy.")
    if x_nodes is not None:
        x = np.unique(np.clip(np.asarray(x_nodes, float), 0.0, L))
        if x[0] > 0:
            x = np.concatenate([[0.0], x])
        if x[-1] < L:
            x = np.concatenate([x, [L]])
    else:
        if n is None:
            # Uniform spacing that resolves the attenuation length by 20
            # nodes, plus geometric refinement near the station, where the
            # soil potential the line picks up changes within metres.
            gam = abs(cmath.sqrt(z * g)) if g > 0 else 0.0
            n = int(min(2000, max(200, 20 * L * gam)))
        x = np.unique(np.concatenate([
            np.linspace(0.0, L, n + 1),
            np.geomspace(min(0.1, L / 10), L, 160),
            np.linspace(0.0, min(L, 20.0), 81)]))
    # merge nodes that coincide to rounding (1.8.8): the three node sets
    # above can give two nodes 1e-16 m apart, whose span then has a series
    # admittance of 1e19 S and wrecks the elimination (seen as a GPR of a
    # few volts for an 800 m bare wire); an array of soil potentials given
    # per node keeps its nodes
    if callable(Vs) and len(x) > 2:
        x = x[np.concatenate([[True], np.diff(x) > 1e-9 * max(L, 1.0)])]
        x[-1] = L                       # the far end stays where it is
    N = len(x)
    n = N - 1
    dx = np.diff(x)
    Vs_n = (np.asarray([Vs(t) for t in x], complex) if callable(Vs)
            else np.asarray(Vs, complex))
    if len(Vs_n) != N:
        raise ValueError("The soil potential array must have one value per node.")
    ys = 1.0 / (z * dx)                      # series admittance of each span
    gl = np.zeros(N)
    gl[:-1] += 0.5 * g * dx
    gl[1:] += 0.5 * g * dx
    # tridiagonal system: diagonal d, off-diagonals -ys
    d = gl.astype(complex)
    d[:-1] += ys
    d[1:] += ys
    lo = -ys.astype(complex)                 # Y[k+1, k]
    up = -ys.astype(complex)                 # Y[k, k+1]
    rhs = (gl * Vs_n).astype(complex)
    Ek = np.zeros(n, complex)
    if emf is not None:
        # series source in each span: I_k = (V_k − V_k+1 + E_k)·y_k
        xm = 0.5 * (x[:-1] + x[1:])
        Ek = np.array([complex(emf(t)) for t in xm]) * dx
        rhs[:-1] -= Ek * ys
        rhs[1:] += Ek * ys
    # station end
    if near == "bonded":
        if R_bond and R_bond > 0:
            d[0] += 1.0 / R_bond
            rhs[0] += V_near / R_bond
        else:
            d[0] = 1.0
            up[0] = 0.0
            rhs[0] = V_near
    elif near != "insulated":
        raise ValueError("near must be 'bonded' or 'insulated'")
    # far end
    if far in ("earthed", "remote"):
        if R_far is None or R_far <= 0:
            raise ValueError("Give the far-end earthing resistance (ohm).")
        Vref = (Vs_n[-1] if far == "earthed" else 0.0)
        if V_far_soil is not None:
            Vref = V_far_soil
        d[-1] += 1.0 / R_far
        rhs[-1] += Vref / R_far
    elif far != "open":
        raise ValueError("far must be 'open', 'earthed' or 'remote'")
    if g == 0 and near == "insulated" and far == "open":
        raise ValueError("An insulated conductor with an insulating joint at "
                         "the station and an open far end is not connected "
                         "to anything: its potential is undefined.")
    V = _thomas(lo, d, up, rhs)
    Iser = (V[:-1] - V[1:] + Ek) * ys
    if near == "bonded":
        I_near = (Iser[0] + gl[0] * (V[0] - Vs_n[0]))
    else:
        I_near = 0j
    return dict(x=x, V=V, Vs=Vs_n, I_series=Iser, I_near=complex(I_near), n=n)


def _thomas(lo, d, up, r):
    """Solve a tridiagonal system (sub-diagonal lo, diagonal d,
    super-diagonal up) by forward elimination and back substitution."""
    n = len(d)
    c = np.zeros(n - 1, complex)
    y = np.zeros(n, complex)
    dd = d[0]
    c[0] = up[0] / dd if n > 1 else 0
    y[0] = r[0] / dd
    for i in range(1, n):
        dd = d[i] - lo[i - 1] * c[i - 1]
        if i < n - 1:
            c[i] = up[i] / dd
        y[i] = (r[i] - lo[i - 1] * y[i - 1]) / dd
    for i in range(n - 2, -1, -1):
        y[i] -= c[i] * y[i + 1]
    return y


def mutual_earth_return(rho_soil: float, f: float, d: float) -> complex:
    """Mutual impedance per metre between two parallel conductors d apart
    with earth return (Carson), ohm/m:
        z_m = μ0ω/8 + j μ0ω/(2π) · ln(D_e/d),   D_e = 658.5 √(ρ/f)."""
    De = 658.5 * math.sqrt(rho_soil / f)
    w = 2 * math.pi * f
    return complex(MU0 * w / 8.0, MU0 * w / (2 * math.pi) * math.log(De / max(d, 1e-3)))


def induced_emf_profile(route_at, length: float, line_path, I_A: float, rho_soil: float,
                        f: float = 50.0, d_min: float = 1.0, ds: float = 2.0):
    """EMF per metre induced along a route of any shape by a faulted line of
    any shape (1.8.5).

    At every point of the route the nearest point of the line is found; with
    d the distance to it and u the line's direction there (the direction of
    the earth-return current I_A, from the first vertex of `line_path`), the
    EMF per metre along the route tangent t is

        e(s) = z_m(d)·I_A·(t·u)

    — the parallel component of the route in the field of a locally straight
    line, which is the sectioning rule of ITU-T K.26 / the CCITT Directives
    taken to the limit of short sections.  Where the foot of the
    perpendicular falls beyond the ends of the line, or d exceeds the
    earth-return depth D_e, the coupling is taken as zero.
    Returns (e(s) callable, dict of samples for the report).
    """
    L = np.asarray(line_path, float)[:, :2]
    if len(L) < 2:
        raise ValueError("The faulted line needs at least two points.")
    De = 658.5 * math.sqrt(rho_soil / f)
    s = np.arange(0.0, length + ds, ds)
    s[-1] = min(s[-1], length)
    xy = route_at(s)
    tg = np.gradient(xy, s, axis=0)
    tg /= np.maximum(np.linalg.norm(tg, axis=1), 1e-12)[:, None]
    seg = np.diff(L, axis=0)
    sl = np.linalg.norm(seg, axis=1)
    u = seg / np.maximum(sl, 1e-12)[:, None]
    best_d = np.full(len(s), np.inf)
    best_c = np.zeros(len(s))
    inside = np.zeros(len(s), bool)
    for k in range(len(seg)):
        rel = xy - L[k]
        t = (rel @ seg[k]) / max(sl[k] ** 2, 1e-12)
        tc = np.clip(t, 0.0, 1.0)
        foot = L[k] + np.outer(tc, seg[k])
        d = np.linalg.norm(xy - foot, axis=1)
        ok = d < best_d
        best_d[ok] = d[ok]
        best_c[ok] = tg[ok] @ u[k]
        lo_ok = (t >= 0.0) | (k > 0)
        hi_ok = (t <= 1.0) | (k < len(seg) - 1)
        inside[ok] = (lo_ok & hi_ok)[ok]
    dd = np.maximum(best_d, d_min)
    w = 2 * math.pi * f
    zm = MU0 * w / 8.0 + 1j * MU0 * w / (2 * math.pi) * np.log(De / dd)
    e = np.where(inside & (best_d < De), zm * float(I_A) * best_c, 0j)

    def emf(t):
        return complex(np.interp(t, s, e.real), np.interp(t, s, e.imag))
    exposed = np.abs(e) > 0
    info = dict(s=s, e=e, d=best_d, cos=best_c,
                exposure_m=float(np.sum(np.diff(s)[exposed[:-1]])) if len(s) > 1 else 0.0,
                emf_total=float(abs(np.trapezoid(e, s)) if hasattr(np, "trapezoid") else abs(np.trapz(e, s))),
                emf_per_km_max=float(np.abs(e).max() * 1000.0),
                d_min=float(best_d.min()))
    return emf, info


def transferred_potential(*, GPR: float, Rg: float, IG: float,
                          soil_profile, length: float, kind: str = "bare",
                          rho_soil: float = 100.0, radius: float = 0.05,
                          depth: float = 1.0, f: float = 50.0,
                          metal: str = "steel", wall=None, r_dc_per_km=None,
                          coating_res=None, leak_ohm_km=None, z_per_km=None,
                          near: str = "bonded", R_bond: float = 0.0,
                          far: str = "open", R_far: float | None = None,
                          E_touch: float | None = None,
                          access_points=None, induced=None, route_at=None) -> dict:
    """Transferred potential of one conductor leaving the station.

    soil_profile : callable s -> V_soil(s)/GPR along the route (s from the
                   station end), normally from the numerical solver
    GPR, Rg, IG  : the station's own solution without this conductor
    access_points: distances (m) where the metal is accessible (valve pits,
                   level crossings, the far-end cabinet); the far end is
                   always added
    induced      : optional dict(I_A, d, s_from, s_to) — a faulted line carrying
                   I_A amperes (the earth-return current) runs parallel to the
                   route at d metres between s_from and s_to; its magnetic field
                   induces z_m·I volts per metre along that stretch (Carson), which
                   is added as a series source (1.8.0).  The GPR and the induced
                   voltage are combined as phasors with the fault current as the
                   reference (the GPR in phase with it, which holds for a
                   resistive grid).
                   Since 1.8.5 `induced` may instead give `line_path` (the
                   faulted line's route as x, y points, in the layout's frame)
                   with `route_at` the route's own geometry: the EMF then
                   follows the separation and angle at every point
                   (induced_emf_profile), for routes that are not parallel.
    """
    par = line_parameters(kind, rho_soil, length, radius, depth, f, metal,
                          wall, r_dc_per_km, coating_res, leak_ohm_km, z_per_km)
    z, g = par["z"], par["g"]
    # unit solution: everything scales with the GPR
    unit = solve_ladder(length, z, g, soil_profile, near=near, R_bond=R_bond,
                        V_near=1.0, far=far, R_far=R_far)
    a = unit["I_near"]                         # A drawn per volt of GPR
    # GPR corrected for the current the conductor draws away from the grid.
    # The current it then leaks back into the soil near the station lifts
    # the grid again: by reciprocity, a current i leaving the soil at a
    # point where the grid alone sets the potential f*GPR raises the grid
    # by i*Rg*f.  So  GPR = Rg (IG - a GPR + c GPR),  c = sum i_leak f.
    dxs = np.diff(unit["x"])
    gl = np.zeros(len(unit["x"]))
    gl[:-1] += 0.5 * g * dxs
    gl[1:] += 0.5 * g * dxs
    i_leak = gl * (unit["V"] - unit["Vs"])
    c = complex(np.sum(i_leak * unit["Vs"]))
    if near == "bonded":
        corr = 1.0 / (1.0 + Rg * (a - c))
    else:
        corr = 1.0
    GPRc = GPR * corr
    Vm = unit["V"] * GPRc
    Vs = unit["Vs"] * GPRc
    x = unit["x"]
    ind = None
    if induced and float(induced.get("I_A") or 0) > 0:
        Iind = float(induced["I_A"])
        geo = None
        if induced.get("line_path") and route_at is not None:
            e, geo = induced_emf_profile(route_at, length, induced["line_path"], Iind,
                                         rho_soil, f)
            zm = mutual_earth_return(rho_soil, f, max(geo["d_min"], 1.0))
            a0, a1 = 0.0, length
        else:
            zm = mutual_earth_return(rho_soil, f, float(induced.get("d", 50.0)))
            a0 = float(induced.get("s_from", 0.0) or 0.0)
            a1 = float(induced.get("s_to", length) or length)
            e = lambda t: (zm * Iind) if a0 <= t <= a1 else 0j
        sol_i = solve_ladder(length, z, g, np.zeros(len(x)), near=near, R_bond=R_bond,
                             V_near=0.0, far=far, R_far=R_far,
                             V_far_soil=(0.0 if far in ("earthed", "remote") else None),
                             x_nodes=x, emf=e)
        Vi = sol_i["V"]
        t_ind = np.abs(Vi)
        Vm = Vm + Vi
        ind = dict(zm_per_km=[float((zm * 1000).real), float((zm * 1000).imag)],
                   emf_per_km=float(abs(zm * Iind) * 1000.0),
                   emf_total=float(abs(zm * Iind) * max(a1 - a0, 0.0)),
                   touch_induced_max=float(t_ind.max()),
                   touch_induced_at=float(x[int(np.argmax(t_ind))]),
                   I_A=Iind, d=float(induced.get("d", 50.0)), s_from=a0, s_to=a1)
        if geo is not None:
            ind.update(mode="geometry", emf_per_km=geo["emf_per_km_max"],
                       emf_total=geo["emf_total"], exposure_m=geo["exposure_m"],
                       d=geo["d_min"], s_from=None, s_to=None,
                       emf_profile=dict(s=geo["s"].tolist(),
                                        e_per_km=(np.abs(geo["e"]) * 1000.0).tolist()))
        else:
            ind["mode"] = "parallel"
    touch = np.abs(Vm - Vs)
    pts = sorted(set([float(length)] + [float(p) for p in (access_points or [])
                                        if 0 <= float(p) <= length]))
    acc = []
    for s in pts:
        k = int(np.argmin(np.abs(x - s)))
        acc.append(dict(s=float(x[k]), V_metal=float(abs(Vm[k])),
                        V_soil=float(abs(Vs[k])), touch=float(touch[k]),
                        passed=(None if not E_touch else bool(touch[k] <= E_touch))))
    k_max = int(np.argmax(touch))
    far_k = len(x) - 1
    res = dict(
        kind=kind, length=length, near=near, far=far,
        z_per_km=[float((z * 1000).real), float((z * 1000).imag)],
        g_per_km=g * 1000.0,
        leak_ohm_km=(1.0 / (g * 1000.0) if g > 0 else None),
        attenuation_length=par["attenuation_length"],
        Z0=(abs(par["Z0"]) if par["Z0"] is not None else None),
        parameter_note=par["note"],
        GPR_without=GPR, GPR=float(abs(GPRc)),
        GPR_change_pct=float((abs(corr) - 1.0) * 100.0),
        I_diverted=float(abs(a * GPRc)),
        I_diverted_pct=float(abs(a * GPRc) / IG * 100.0) if IG else None,
        V_far=float(abs(Vm[far_k])), V_far_soil=float(abs(Vs[far_k])),
        V_far_pct=float(abs(Vm[far_k]) / abs(GPRc) * 100.0),
        transfer_far=float(touch[far_k]),
        touch_max=float(touch[k_max]), touch_max_at=float(x[k_max]),
        access=acc, E_touch=E_touch, induced=ind,
        profile=dict(s=x.tolist(), V_metal=np.abs(Vm).tolist(),
                     V_soil=np.abs(Vs).tolist(), touch=touch.tolist()),
    )
    if E_touch:
        res["passed"] = all(p["passed"] for p in acc)
    res["notes"] = _notes(res, kind, near, far)
    return res


def _notes(r, kind, near, far):
    out = []
    if kind == "insulated" and near == "bonded":
        out.append("An insulated conductor bonded at the station carries the "
                   "full station potential to its far end, where the soil is "
                   "near remote earth: the transferred voltage there is "
                   "almost the whole GPR (IEEE Std 80 clause 17.3).")
    if near == "insulated":
        out.append("With an insulating joint at the station the metal is "
                   "lifted only by the soil it passes through; the touch "
                   "voltage peaks where the conductor leaves the area of "
                   "high soil potential.")
    if r.get("attenuation_length") and r["attenuation_length"] < r["length"]:
        out.append(f"The potential of the metal decays with a characteristic "
                   f"length of about {r['attenuation_length']:.0f} m, shorter "
                   f"than the route, so the far end sits near remote earth.")
    if r.get("I_diverted_pct") and r["I_diverted_pct"] > 5:
        if r.get("model") == "coupled":
            out.append(f"The conductor draws {r['I_diverted_pct']:.0f} % of the "
                       f"fault current away from the grid, which lowers the GPR "
                       f"by {abs(r['GPR_change_pct']):.0f} %. The conductor was solved "
                       f"together with the station, so its own leakage is in the soil "
                       f"potential round the station and beside the route.")
        else:
            out.append(f"The conductor draws {r['I_diverted_pct']:.0f} % of the "
                       f"fault current away from the grid, which lowers the GPR "
                       f"by {abs(r['GPR_change_pct']):.0f} %. The soil potential "
                       f"around the station is not recomputed for that current.")
    return out


def _polyline(path, length):
    """Map distance along a polyline to (x, y); the last leg is extended
    when `length` exceeds the drawn route."""
    P = np.asarray(path, float)[:, :2]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])

    def at(s):
        s = np.asarray(s, float)
        k = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(seg) - 1)
        t = (s - cum[k]) / np.maximum(seg[k], 1e-12)
        return P[k] + (P[k + 1] - P[k]) * t[:, None]
    return at, float(cum[-1])


def soil_profile_from_network(net, start, direction, length, depth=1.0,
                              n=120, path=None):
    """Soil potential along a straight route, as a fraction of the GPR.

    Evaluated with the numerical solver at `n` points spaced
    geometrically (dense near the station, where it changes fastest),
    then interpolated; beyond the last point it falls as 1/r.
    """
    if not HAVE_NUMPY:
        raise RuntimeError("needs numpy")
    s = np.unique(np.concatenate([
        np.linspace(0.0, min(length, 50.0), 51),
        np.geomspace(1.0, max(length, 2.0), n)]))
    s = s[s <= length + 1e-9]
    if path is not None and len(path) >= 2:
        at, _ = _polyline(path, length)
        xy = at(s)
    else:
        d = np.asarray(direction[:2], float)
        d = d / max(np.linalg.norm(d), 1e-12)
        p0 = np.asarray(start[:2], float)
        xy = np.column_stack([p0[0] + d[0] * s, p0[1] + d[1] * s])
    pts = np.column_stack([xy[:, 0], xy[:, 1], np.full(len(s), float(depth))])
    v = np.asarray(net.potential_at(pts)) / net.V
    s_last, v_last = float(s[-1]), float(v[-1])

    def f(t):
        if t <= s_last:
            return float(np.interp(t, s, v))
        return v_last * s_last / t
    f.samples = (s, v)
    return f


# ---------------------------------------------------------------------------
# Coupled solution (1.8.8)
# ---------------------------------------------------------------------------

COUPLED_LIMIT = 6000          # station + route segments for the coupled solution


def route_nodes(length: float, ds0: float, ds_max: float, growth: float = 1.15,
                max_seg: int = 400):
    """Node positions along the route: ds0 at the station, growing
    geometrically to ds_max (the soil potential and the conductor's
    current change fastest near the station)."""
    s = [0.0]
    ds = float(ds0)
    while s[-1] < length - 1e-9:
        s.append(min(length, s[-1] + ds))
        ds = min(ds * growth, ds_max)
    s = np.array(s)
    if len(s) - 1 > max_seg:
        s = np.unique(np.concatenate([s[s < 50.0], np.linspace(min(50.0, length), length,
                                                                max_seg - int(np.sum(s < 50.0)))]))
    if length - s[-2] < 0.2 * (s[-2] - s[-3] if len(s) > 2 else length):
        s = np.delete(s, -2)             # no sliver at the far end
    return s


def coupled_transferred_potential(net, *, route_at, length: float, depth: float,
                                  radius: float, kind: str, z: complex,
                                  coating_res=None, near: str = "bonded",
                                  R_bond: float = 0.0, far: str = "open",
                                  R_far=None, emf=None, access_points=None,
                                  E_touch=None, reach: float = 1.0,
                                  ds0: float | None = None, ds_max: float | None = None):
    """Transferred potential with the conductor solved together with the
    station (1.8.8).

    The route is cut into segments that leak into the soil like the
    station's own (bare metal; a coated pipe through its coating, which
    enters as a series resistance coating_res/(2πa) per metre of the
    segment's leakage path).  All the leakage currents — station and route
    — share one potential-coefficient matrix P, so the route's own current
    changes the soil potential round the station and the station's changes
    the soil along the route.  The route also has series impedance z per
    metre (Carson earth return and internal impedance) between its nodes:

        P I = E_s V_s + B U                 soil, station networks at V_s,
                                            route segments at the mean of
                                            their two node potentials U
        E_kᵀ I = J_k − δ_k0 I_bond          station networks
        I_bond = J_0 + leak_0, J_{j−1} = J_j + leak_j, J_{m−1} = leak_m + I_far
        J_j = (U_j − U_{j+1} + e_j Δs_j)/(z Δs_j)

    with leak_j the leakage given to node j (half of each adjacent segment)
    and e the induced EMF per metre, if any.  P is real (the leakage field
    is quasi-static at power frequency, as in the one-way model); the
    unknowns are complex.  The touch voltage at a point of the route is the
    metal potential minus the surface potential `reach` metres to the side
    of the route (the lower of the two sides), which now includes the
    route's own leakage.  Returns arrays and the main figures; the caller
    builds the report."""
    from . import bem
    if kind not in ("bare", "coated"):
        raise ValueError("The coupled solution is for bare or coated conductors.")
    shell = 0.0
    if kind == "coated":
        shell = float(coating_res) / (2 * math.pi * radius)
    seg_g = list(net.segments)
    lmean = float(np.mean([sg.length for sg in seg_g])) if seg_g else 2.0
    ds0 = float(ds0 or max(min(lmean, 3.0), 12.0 * radius, 1.5 * radius))
    ds_max = float(ds_max or max(ds0, min(50.0, length / 20.0)))
    s = route_nodes(length, ds0, ds_max)
    # nodes where the route crosses a soil interface (two-region soil)
    soil = net.soil
    xy = route_at(s)
    pts = np.column_stack([xy, np.full(len(s), float(depth))])
    extra = []
    for k in range(len(s) - 1):
        for t in soil.plane_cuts(pts[k], pts[k + 1]):
            extra.append(s[k] + t * (s[k + 1] - s[k]))
    if extra:
        s = np.unique(np.concatenate([s, extra]))
        xy = route_at(s)
        pts = np.column_stack([xy, np.full(len(s), float(depth))])
    m = len(s) - 1
    ng = len(seg_g)
    if ng + m > COUPLED_LIMIT:
        raise ValueError(f"Station and route together have {ng + m} segments, more than "
                         f"the coupled solution takes ({COUPLED_LIMIT}).")
    comb = bem.Network(soil, net.IG)
    comb.nets = [dict(nt) for nt in net.nets] + [dict(name="route", injection=0.0, kind="route")]
    kr = len(comb.nets) - 1
    seg_r = [bem.Segment(pts[j], pts[j + 1], radius, "route",
                         soil.zone_of(0.5 * (pts[j] + pts[j + 1])), kr, shell)
             for j in range(m)]
    comb.segments = seg_g + seg_r
    N = ng + m
    ms = len(net.nets)
    P = comb.build_matrix()
    E = np.zeros((N, ms))
    for i, sg in enumerate(seg_g):
        E[i, sg.net] = 1.0
    B = np.zeros((N, m + 1))
    for j in range(m):
        B[ng + j, j] += 0.5
        B[ng + j, j + 1] += 0.5
    X = np.linalg.solve(P, np.hstack([E, B]))          # I = X [V_s; U]
    nw = ms + m + 1
    # rows of the leakage: station network totals and route node shares
    Ltot = E.T @ X                                      # (ms, nw)
    Lnode = B.T @ X                                     # (m+1, nw)
    ds = np.diff(s)
    yz = 1.0 / (z * ds)                                 # series admittance of each span
    e_ind = np.zeros(m, complex)
    if emf is not None:
        e_ind = np.array([complex(emf(0.5 * (s[j] + s[j + 1]))) for j in range(m)]) * ds
    e = np.zeros(m, complex)       # the EMF enters as a second right-hand side
    # unknowns: V_s (ms), U (m+1), I_bond
    nu = nw + 1
    iU = ms
    ib = nw
    A = np.zeros((ms + (m + 1) + 1, nu), complex)
    rhs = np.zeros(ms + (m + 1) + 1, complex)

    def J(j):
        """coefficients of J_j in the unknowns, and its constant part"""
        c = np.zeros(nu, complex)
        c[iU + j] += yz[j]
        c[iU + j + 1] -= yz[j]
        return c, e[j] * yz[j]
    # station networks: leakage = injection (− the bond current for net 0)
    inj = np.array([float(net.IG)] + [float(nt.get("injection") or 0.0) for nt in net.nets[1:]])
    for k in range(ms):
        A[k, :nw] = Ltot[k]
        if k == 0:
            A[k, ib] += 1.0
        rhs[k] = inj[k]
    # route nodes
    far_ref = None
    if far == "earthed":
        # the soil the far-end electrode sits in, from all the leakage, 2 m
        # to the side of the route end
        tg = xy[-1] - xy[-2]
        tg = tg / max(np.linalg.norm(tg), 1e-12)
        q = np.array([[xy[-1][0] - 2.0 * tg[1], xy[-1][1] + 2.0 * tg[0], float(depth)]])
        far_ref = comb._potential_row(q)[0] @ X          # (nw,)
    for jn in range(m + 1):
        r = ms + jn
        A[r, :nw] -= Lnode[jn]                           # − leakage at the node
        if jn > 0:
            c, k0 = J(jn - 1)
            A[r] += c
            rhs[r] -= k0
        if jn < m:
            c, k0 = J(jn)
            A[r] -= c
            rhs[r] += k0
        if jn == 0:
            A[r, ib] += 1.0
        if jn == m and far in ("earthed", "remote"):
            if R_far in (None, "") or float(R_far) <= 0:
                raise ValueError("Give the far-end earthing resistance (ohm).")
            A[r, iU + m] -= 1.0 / float(R_far)
            if far_ref is not None:
                A[r, :nw] += far_ref / float(R_far)
    # the bond
    rb = ms + m + 1
    if near == "bonded":
        A[rb, 0] = 1.0
        A[rb, iU] = -1.0
        if R_bond and float(R_bond) > 0:
            A[rb, ib] = -float(R_bond)
    elif near == "insulated":
        A[rb, ib] = 1.0
    else:
        raise ValueError("near must be 'bonded' or 'insulated'")
    # the induced EMF as a second right-hand side (the series sources of the
    # node equations), so its share is reported separately
    rhs_e = np.zeros_like(rhs)
    for jn in range(m + 1):
        r = ms + jn
        if jn > 0:
            rhs_e[r] -= e_ind[jn - 1] * yz[jn - 1]
        if jn < m:
            rhs_e[r] += e_ind[jn] * yz[jn]
    W = np.linalg.solve(A, np.column_stack([rhs, rhs_e]))
    tgn = np.gradient(xy, s, axis=0)
    tgn /= np.maximum(np.linalg.norm(tgn, axis=1), 1e-12)[:, None]
    nrm = np.column_stack([-tgn[:, 1], tgn[:, 0]])
    Q = [np.column_stack([xy + sg * reach * nrm, np.zeros(len(s))]) for sg in (1.0, -1.0)]

    def fields(w, ee):
        U = w[iU:iU + m + 1]
        I = X @ w[:nw]
        side = [comb.potential_at(q, currents=I.real) + 1j * comb.potential_at(q, currents=I.imag)
                for q in Q]
        return U, I, side
    U0, I0, S0 = fields(W[:, 0], e)
    if emf is not None:
        U1, I1, S1 = fields(W[:, 1], e_ind)
    else:
        U1, I1, S1 = np.zeros_like(U0), np.zeros_like(I0), [np.zeros_like(U0)] * 2
    w = W[:, 0] + W[:, 1]
    U, I = U0 + U1, I0 + I1
    side = [S0[0] + S1[0], S0[1] + S1[1]]
    t1, t2 = np.abs(U - side[0]), np.abs(U - side[1])
    Vsoil = np.where(t1 >= t2, side[0], side[1])
    touch = np.abs(U - Vsoil)
    ti = np.maximum(np.abs(U1 - S1[0]), np.abs(U1 - S1[1]))
    Jser = np.array([yz[j] * (U[j] - U[j + 1] + e_ind[j]) for j in range(m)])
    return dict(s=s, U=U, V_soil=Vsoil, touch=touch, V_station=w[:ms], GPR=complex(w[0]),
                I_bond=complex(w[ib]), I_series=Jser, I_leak=I, segments_route=m,
                segments_station=ng, net=comb, touch_induced=ti,
                GPR_fault=complex(W[0, 0]))


def transferred_potential_coupled(net, *, route_at, soil_profile, length: float,
                                  kind: str, rho_soil: float, radius: float,
                                  depth: float = 1.0, f: float = 50.0, metal: str = "steel",
                                  wall=None, r_dc_per_km=None, coating_res=None,
                                  z_per_km=None, near: str = "bonded", R_bond: float = 0.0,
                                  far: str = "open", R_far=None, E_touch=None,
                                  access_points=None, induced=None) -> dict:
    """The report of transferred_potential, from the coupled solution
    (1.8.8), with the one-way figures kept under `one_way` for comparison.
    Bare and coated conductors only (their leakage is the soil's, which the
    coupled solution computes); for rails, custom leakage and insulated
    screens the one-way model is the model."""
    sol = dict(GPR=net.V, Rg=float(net.Z[0, 0]), IG=net.IG)
    one = transferred_potential(
        GPR=sol["GPR"], Rg=sol["Rg"], IG=sol["IG"], soil_profile=soil_profile,
        length=length, kind=kind, rho_soil=rho_soil, radius=radius, depth=depth, f=f,
        metal=metal, wall=wall, r_dc_per_km=r_dc_per_km, coating_res=coating_res,
        z_per_km=z_per_km, near=near, R_bond=R_bond, far=far, R_far=R_far,
        E_touch=E_touch, access_points=access_points, induced=induced, route_at=route_at)
    par = line_parameters(kind, rho_soil, length, radius, depth, f, metal, wall,
                          r_dc_per_km, coating_res, None, z_per_km)
    emf = None
    if induced and float(induced.get("I_A") or 0) > 0:
        Iind = float(induced["I_A"])
        if induced.get("line_path") and route_at is not None:
            emf, _ = induced_emf_profile(route_at, length, induced["line_path"], Iind,
                                         rho_soil, f)
        else:
            zm = mutual_earth_return(rho_soil, f, float(induced.get("d", 50.0)))
            a0 = float(induced.get("s_from", 0.0) or 0.0)
            a1 = float(induced.get("s_to", length) or length)
            emf = lambda t: (zm * Iind) if a0 <= t <= a1 else 0j
    c = coupled_transferred_potential(
        net, route_at=route_at, length=length, depth=depth, radius=radius, kind=kind,
        z=par["z"], coating_res=coating_res, near=near, R_bond=R_bond, far=far,
        R_far=R_far, emf=emf)
    x = c["s"]
    Vm, Vs, touch = c["U"], c["V_soil"], c["touch"]
    GPRc = abs(c["GPR"])
    pts = sorted(set([float(length)] + [float(p) for p in (access_points or [])
                                        if 0 <= float(p) <= length]))
    acc = []
    for sp in pts:
        V_m = complex(np.interp(sp, x, Vm.real) + 1j * np.interp(sp, x, Vm.imag))
        V_s = complex(np.interp(sp, x, Vs.real) + 1j * np.interp(sp, x, Vs.imag))
        t = float(np.interp(sp, x, touch))
        acc.append(dict(s=float(sp), V_metal=abs(V_m), V_soil=abs(V_s), touch=t,
                        passed=(None if not E_touch else bool(t <= E_touch))))
    k_max = int(np.argmax(touch))
    res = dict(one)
    res.update(
        model="coupled",
        GPR=float(GPRc),
        GPR_change_pct=float((abs(c["GPR_fault"]) / sol["GPR"] - 1.0) * 100.0),
        I_diverted=float(abs(c["I_bond"])),
        I_diverted_pct=float(abs(c["I_bond"]) / sol["IG"] * 100.0) if sol["IG"] else None,
        V_far=float(abs(Vm[-1])), V_far_soil=float(abs(Vs[-1])),
        V_far_pct=float(abs(Vm[-1]) / GPRc * 100.0) if GPRc else None,
        transfer_far=float(touch[-1]),
        touch_max=float(touch[k_max]), touch_max_at=float(x[k_max]),
        access=acc,
        profile=dict(s=x.tolist(), V_metal=np.abs(Vm).tolist(),
                     V_soil=np.abs(Vs).tolist(), touch=touch.tolist()),
        segments=dict(station=c["segments_station"], route=c["segments_route"]),
        one_way=dict(GPR=one["GPR"], I_diverted=one["I_diverted"], V_far_pct=one["V_far_pct"],
                     touch_max=one["touch_max"], touch_max_at=one["touch_max_at"],
                     transfer_far=one["transfer_far"]))
    if res.get("induced"):
        ti = c["touch_induced"]
        res["induced"] = dict(res["induced"], touch_induced_max=float(ti.max()),
                              touch_induced_at=float(x[int(np.argmax(ti))]))
    if E_touch:
        res["passed"] = all(p["passed"] for p in acc)
    res["notes"] = _notes(res, kind, near, far)
    return res


# ---------------------------------------------------------------------------
# Circuit-field check of the coupled solution (1.9.2)
# ---------------------------------------------------------------------------
#
# The coupled solution holds the station at one potential and couples the
# route to it through the soil only.  The circuit-field model of hf.py
# solves station and route as one network of conductors with internal
# impedance and self and mutual inductance with earth return, so it also
# contains the magnetic coupling between the route and the grid conductors
# and the drop along the grid itself.  It is run as a check where the model
# is small enough, and the larger touch voltage of the two is the design
# value.

CHECK_LIMIT = 2000            # circuit-field segments for the check


def circuit_field_check(p, *, route_at, length, depth, radius, kind, coating_res=None,
                        metal="steel", wall=None, r_dc_per_km=None, f=50.0,
                        access_points=None, reach=1.0, grid_metal="copper", ds0=None,
                        ds_max=None):
    """Station and route solved together by the circuit-field model at f.

    The route (bare, or coated: its coating enters as a resistive shell of
    coating_res/(2πa) per metre) is bonded at its start to the nearest
    grid node; the fault current IG enters the grid at the node nearest to
    the centroid of the grid conductors.  Returns the GPR there, the
    current the route draws, its far-end potential and the touch voltages
    at the access points (metal minus the surface potential `reach` metres
    to the side, the worse side), or dict(skipped=reason)."""
    from . import bem, hf
    items = [it for it in p.get("items") or [] if it.get("kind") not in ("fence",)]
    if any(it.get("kind") == "fence" for it in p.get("items") or []):
        return dict(skipped="fences are in the model (the check takes the electrode alone)")
    if any(it.get("kind") == "plate" for it in items):
        return dict(skipped="the circuit-field model takes wire electrodes, not plates")
    if p.get("rho_v") not in (None, ""):
        return dict(skipped="the circuit-field model takes horizontal layers only")
    rho = [float(p.get("rho1", 100.0))]
    h = []
    for kr, kh in (("rho2", "h_layer"), ("rho3", "h_layer2"), ("rho4", "h_layer3")):
        if p.get(kr) not in (None, "") and p.get(kh) not in (None, ""):
            rho.append(float(p[kr]))
            h.append(float(p[kh]))
        else:
            break
    soil = hf.make_soil(rho if len(rho) > 1 else rho[0], h, eps_r=10.0, model="constant")
    w = hf.Wires.from_items(items, conductor_radius=float(p.get("conductor_radius", 0.005)))
    n_grid = len(w.raw)
    if n_grid == 0:
        return dict(skipped="no electrode")
    # route pieces: the coupled solution's own nodes, one segment each
    seg_g = float(p.get("segment_length", 2.5))
    s = route_nodes(length, float(ds0 or max(min(seg_g, 3.0), 12.0 * radius)),
                    float(ds_max or max(ds0 or 3.0, min(50.0, length / 20.0))))
    xy = route_at(s)
    zi = internal_impedance(radius, f, metal, wall, r_dc_per_km)
    enc = None
    if kind == "coated":
        rc = radius * 1.001
        enc = dict(radius=rc, rho=float(coating_res) / (radius * math.log(rc / radius)),
                   eps_r=0.0)
    for k in range(len(s) - 1):
        w.add([xy[k, 0], xy[k, 1], depth], [xy[k + 1, 0], xy[k + 1, 1], depth], radius,
              "route", concrete=enc)
        w.seg_fix[len(w.raw) - 1] = float(s[k + 1] - s[k])
        w.zint[len(w.raw) - 1] = zi
    total = sum(float(np.linalg.norm(b - a)) for a, b, *_ in w.raw[:n_grid])
    seg = max(seg_g, total / max(1.0, CHECK_LIMIT - (len(s) - 1)))
    N = w.discretise(seg, z_cuts=getattr(soil, "depths", []))
    if N > CHECK_LIMIT:
        return dict(skipped=f"the model needs {N} segments, more than the check takes "
                            f"({CHECK_LIMIT})")
    grid_seg = w.raw_idx < n_grid
    gnodes = np.unique(np.concatenate([w.na[grid_seg], w.nb[grid_seg]]))
    start = np.array([xy[0, 0], xy[0, 1], depth])
    r0 = w.nearest_node(start)
    kb = gnodes[int(np.argmin(np.linalg.norm(w.nodes[gnodes] - start, axis=1)))]
    if r0 != kb:
        r0 = kb = w.merge_nodes([[int(kb), int(r0)]])[0]
        grid_seg = w.raw_idx < n_grid
        gnodes = np.unique(np.concatenate([w.na[grid_seg], w.nb[grid_seg]]))
    cen = w.mid[grid_seg].mean(axis=0)
    feed = int(gnodes[int(np.argmin(np.linalg.norm(w.nodes[gnodes, :2] - cen[:2], axis=1)))])
    model = hf.Model(w, soil, metal=grid_metal)
    model._nearblk_bytes = hf.NEARBLK_BYTES          # nothing to keep: one frequency
    IG = float(p.get("IG", 1000.0))
    _, V, IL, IT = model.solve(f, feed, IG)
    # route segments in order along the route (each piece runs outwards)
    rseg = np.where(w.raw_idx >= n_grid)[0]
    raw0 = np.array([w.raw[r][0] for r in w.raw_idx[rseg]])
    order = rseg[np.lexsort((np.linalg.norm(w.p1[rseg] - raw0, axis=1), w.raw_idx[rseg]))]
    s = np.concatenate([[0.0], np.cumsum(w.L[order])])
    Uk = np.array([V[w.na[order[0]]]] + [V[w.nb[i]] for i in order], complex)
    xy = route_at(np.minimum(s, length))
    I_route = IL[order[0]]
    # surface potential of the leakage currents, static kernel (as powerfreq)
    net = bem.Network(bem.SoilModel(rho[0], rho[1] if len(rho) > 1 else None,
                                    h[0] if h else None,
                                    rho3=rho[2] if len(rho) > 2 else None,
                                    h2=h[1] if len(h) > 1 else None,
                                    rho4=rho[3] if len(rho) > 3 else None,
                                    h3=h[2] if len(h) > 2 else None), IG)
    net.segments = [bem.Segment(w.p1[i], w.p2[i], float(w.rad[i]), w.segs[i][5],
                                net.soil.layer_of(0.5 * (w.p1[i][2] + w.p2[i][2])), 0, 0.0)
                    for i in range(model.N)]
    tg = np.gradient(xy, s, axis=0)
    tg /= np.maximum(np.linalg.norm(tg, axis=1), 1e-12)[:, None]
    nrm = np.column_stack([-tg[:, 1], tg[:, 0]])
    side = []
    for sg in (1.0, -1.0):
        q = np.column_stack([xy + sg * reach * nrm, np.zeros(len(s))])
        side.append(net.potential_at(q, currents=IT.real)
                    + 1j * net.potential_at(q, currents=IT.imag))
    touch = np.maximum(np.abs(Uk - side[0]), np.abs(Uk - side[1]))
    pts = sorted(set([float(length)] + [float(x) for x in (access_points or [])
                                        if 0 <= float(x) <= length]))
    acc = [dict(s=x, touch=float(np.interp(x, s, touch)),
                V_metal=float(abs(np.interp(x, s, Uk.real) + 1j * np.interp(x, s, Uk.imag))))
           for x in pts]
    GPR = abs(V[feed])
    return dict(GPR=float(GPR), V_bond=float(abs(V[kb])), I_diverted=float(abs(I_route)),
                V_far_pct=float(abs(Uk[-1]) / abs(V[kb]) * 100.0) if abs(V[kb]) else None,
                touch_max=float(touch.max()), touch_max_at=float(s[int(np.argmax(touch))]),
                access=acc, segments=int(model.N), grid_metal=grid_metal,
                feed=[float(c) for c in w.nodes[feed]])
