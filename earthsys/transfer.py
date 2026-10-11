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
                 V_far_soil: complex | None = None, x_nodes=None):
    """Node potentials of the lossy line.

    L, z, g     length (m), series impedance (ohm/m), leakage (S/m)
    Vs          callable x -> soil potential (V) at the conductor, or an
                array of n+1 values at the nodes
    near        'bonded' (to V_near through R_bond) or 'insulated'
    far         'open', 'earthed' (through R_far to the local soil) or
                'remote' (through R_far to remote earth, 0 V)
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
    rhs = gl * Vs_n
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
    Iser = (V[:-1] - V[1:]) * ys
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


def transferred_potential(*, GPR: float, Rg: float, IG: float,
                          soil_profile, length: float, kind: str = "bare",
                          rho_soil: float = 100.0, radius: float = 0.05,
                          depth: float = 1.0, f: float = 50.0,
                          metal: str = "steel", wall=None, r_dc_per_km=None,
                          coating_res=None, leak_ohm_km=None, z_per_km=None,
                          near: str = "bonded", R_bond: float = 0.0,
                          far: str = "open", R_far: float | None = None,
                          E_touch: float | None = None,
                          access_points=None) -> dict:
    """Transferred potential of one conductor leaving the station.

    soil_profile : callable s -> V_soil(s)/GPR along the route (s from the
                   station end), normally from the numerical solver
    GPR, Rg, IG  : the station's own solution without this conductor
    access_points: distances (m) where the metal is accessible (valve pits,
                   level crossings, the far-end cabinet); the far end is
                   always added
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
        access=acc, E_touch=E_touch,
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
        out.append(f"The conductor draws {r['I_diverted_pct']:.0f} % of the "
                   f"fault current away from the grid, which lowers the GPR "
                   f"by {abs(r['GPR_change_pct']):.0f} %. The soil potential "
                   f"around the station is not recomputed for that current.")
    return out


def soil_profile_from_network(net, start, direction, length, depth=1.0,
                              n=120):
    """Soil potential along a straight route, as a fraction of the GPR.

    Evaluated with the numerical solver at `n` points spaced
    geometrically (dense near the station, where it changes fastest),
    then interpolated; beyond the last point it falls as 1/r.
    """
    if not HAVE_NUMPY:
        raise RuntimeError("needs numpy")
    d = np.asarray(direction[:2], float)
    d = d / max(np.linalg.norm(d), 1e-12)
    p0 = np.asarray(start[:2], float)
    s = np.unique(np.concatenate([
        np.linspace(0.0, min(length, 50.0), 51),
        np.geomspace(1.0, max(length, 2.0), n)]))
    s = s[s <= length + 1e-9]
    pts = np.column_stack([p0[0] + d[0] * s, p0[1] + d[1] * s,
                           np.full(len(s), float(depth))])
    v = np.asarray(net.potential_at(pts)) / net.V
    s_last, v_last = float(s[-1]), float(v[-1])

    def f(t):
        if t <= s_last:
            return float(np.interp(t, s, v))
        return v_last * s_last / t
    f.samples = (s, v)
    return f
