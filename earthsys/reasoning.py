"""
Explanation of every compliance verdict.

The calculation modules decide whether a criterion passes.  This module says
*why*: what the criterion physically protects against, which quantity drove
the result, by how much it passed or failed, and — when it failed — exactly
which design lever restores compliance and what value that lever needs.

Nothing here changes a result. It only interprets one, so the same numbers can
be taught, defended in a design review, and printed in the report.

Each explanation is a dict:

    meaning   what the criterion means in physical terms
    verdict   the quantified outcome, in one sentence
    driver    the quantity that dominates the result
    remedy    list of concrete actions with their computed effect (failures)
    headroom  how much margin remains (passes)
"""

from __future__ import annotations

import math

from . import ieee80


def _pct(value, limit):
    if not limit:
        return 0.0
    return (value - limit) / limit * 100.0


def _fmt(v, nd=1):
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "—"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 100:
        return f"{v:.{max(nd - 1, 0)}f}"
    return f"{v:.{nd}f}"


# ---------------------------------------------------------------------------
# Shared physical explanations
# ---------------------------------------------------------------------------

MEANING = {
    "gpr": (
        "The ground potential rise is how far the whole earthing system is "
        "lifted above remote earth during the fault: GPR = I_G · R_g. If the "
        "GPR itself is below the tolerable touch voltage, then no point in the "
        "installation can expose a person to more than that value, whatever "
        "the shape of the potential profile. It is a sufficient — not a "
        "necessary — condition, so failing it does not condemn the design; it "
        "only means the mesh and step voltages have to be checked properly "
        "(IEEE Std 80-2013 §16.4)."),
    "touch": (
        "Touch voltage is the potential difference between an earthed metal "
        "part a person is holding and the soil under their feet, one metre "
        "away. The tolerable value is the voltage that drives no more than the "
        "fibrillation current through the body for the duration of the fault. "
        "The mesh voltage E_m is the worst touch voltage inside the grid — it "
        "occurs at the centre of a corner mesh, where the buried conductors "
        "are furthest away and the soil potential sags lowest."),
    "step": (
        "Step voltage is the potential difference between a person's two feet, "
        "one metre apart, standing on the soil. The body path foot-to-foot has "
        "roughly four times the resistance of the hand-to-feet path, which is "
        "why the tolerable step voltage is about four times the tolerable "
        "touch voltage — and why step voltage is almost never the binding "
        "criterion in a well-built grid."),
    "zs": (
        "In a TN system the earth fault returns through metal, so the fault "
        "current is set by the loop impedance Z_s. Automatic disconnection "
        "requires that this current is large enough to operate the protective "
        "device within the time of IEC 60364-4-41 Table 41.1: Z_s · I_a ≤ "
        "C_min · U₀. Failing means the device will not trip fast enough, and "
        "the exposed metal stays live at a dangerous voltage."),
    "tt": (
        "In a TT system the fault current returns through the earth itself, so "
        "it is limited by the installation electrode R_A in series with the "
        "supply electrode. That current is far too small to operate an "
        "overcurrent device, so the criterion is on voltage instead: the "
        "exposed metal must not sit above 50 V a.c., i.e. R_A · I_a ≤ U_L. In "
        "practice this makes an RCD mandatory."),
    "rcd": (
        "The residual-current device trips on the difference between line and "
        "neutral current, so it does not care how small the earth-fault "
        "current is. The largest residual current it may be rated for follows "
        "from R_A · IΔn ≤ 50 V."),
    "rs_field": (
        "The rolling sphere is the physical statement of the whole method: a "
        "sphere whose radius is the striking distance of the smallest stroke "
        "the class must intercept is rolled over the structure. Wherever it "
        "touches, the leader can reach — that point is a strike point. "
        "Wherever it cannot reach, the flash is intercepted by something else "
        "first, and that volume is protected. The radius comes from the "
        "class, because a smaller minimum current means a shorter striking "
        "distance and a smaller sphere that reaches into more places."),
    "rs_edge": (
        "The edges and corners of a flat roof are the most exposed points on "
        "any building. A sphere resting on the ground beside the wall touches "
        "the roof edge while it is still far from the middle of the roof, so "
        "an air termination in the centre of the roof does not protect the "
        "perimeter. IEC 62305-3 therefore asks for terminations on the "
        "corners and along the exposed edges, normally a perimeter conductor "
        "with short rods at the corners."),
    "rs_span": (
        "Between two terminations the sphere sags into the gap. Resting on "
        "both tips its centre sits sqrt(R² − (d/2)²) above the line joining "
        "them, so the lowest protected point is depressed by "
        "p = R − sqrt(R² − (d/2)²). Once that sag exceeds the height of the "
        "terminations above the surface, the sphere reaches the surface and "
        "the gap is unprotected."),
    "rs_plan": (
        "In plan each vertical termination protects a circle of radius "
        "r_p = sqrt(2Rh − h²) − sqrt(2Rh_x − h_x²) on the reference plane. "
        "The circles are a quick check on coverage; the elevation, where the "
        "sphere is actually rolled, is what decides compliance."),
    "rs_mesh": (
        "The mesh method protects a flat surface by covering it with a "
        "conductor mesh fine enough that no point of the surface is further "
        "from a conductor than the mesh size for the class. It replaces the "
        "rolling sphere on flat roofs, where rolling a sphere would otherwise "
        "demand an impractical number of rods."),
    "lps_r": (
        "IEC 62305-3 recommends an earth-termination resistance below 10 Ω. "
        "This is informative, not mandatory: for lightning the geometry of the "
        "electrode matters more than its 50 Hz resistance, because the "
        "impulse behaviour is governed by the inductance of the conductor and "
        "by soil ionisation. A low resistance is still the practical way to "
        "keep the potential rise and the sparking risk down."),
    "lps_geom": (
        "The minimum electrode length l₁ exists so that the lightning current "
        "is dispersed over enough soil volume, rather than concentrated at one "
        "point. It grows with soil resistivity and with the protection level, "
        "because a higher level implies a larger design current."),
    "lps_down": (
        "At least two down-conductors are required so the current divides, "
        "which halves the voltage drop along each one and therefore halves the "
        "separation distance needed to prevent a dangerous side flash."),
    "bem_touch": (
        "The numerical solver reports the largest touch voltage anywhere the "
        "person can both stand on the soil and reach earthed metal — the "
        "electrode footprint plus one metre of arm reach. Unlike the "
        "closed-form mesh voltage it is not tied to a rectangular grid, so it "
        "also catches hot spots at re-entrant corners and around isolated "
        "electrodes."),
    "bem_step": (
        "The numerical step voltage is the largest potential difference over "
        "the chosen step distance anywhere on the scanned surface, taken from "
        "the gradient of the computed surface potential."),
}


# ---------------------------------------------------------------------------
# IEEE 80 grid
# ---------------------------------------------------------------------------

def _invert_hs(rho, rho_s, ts, k, target_E, hs_max=0.6):
    """Surface-layer thickness that would raise E_touch to target_E."""
    def E(hs):
        Cs = 1.0 - 0.09 * (1.0 - rho / rho_s) / (2.0 * hs + 0.09)
        return (1000.0 + 1.5 * Cs * rho_s) * k / math.sqrt(ts)
    if E(hs_max) < target_E:
        return None
    lo, hi = 0.0, hs_max
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if E(mid) < target_E:
            lo = mid
        else:
            hi = mid
    return hi


def explain_ieee80(result: dict) -> dict:
    """Attach an explanation to every check of an ieee80.design() result."""
    tol, mesh, g = result["tolerable"], result["mesh"], result["geometry"]
    Em, Es = mesh["Em"], mesh["Es"]
    Et, Estep = tol["E_touch"], tol["E_step"]
    GPR, Rg = result["GPR"], result["Rg"]
    rho, rho_s, hs, ts, k = tol["rho"], tol["rho_s"], tol["hs"], tol["ts"], tol["k"]

    for c in result["checks"]:
        name = c["name"]

        # ---- GPR ------------------------------------------------------
        if name.startswith("GPR"):
            c["meaning"] = MEANING["gpr"]
            if c["passed"]:
                c["verdict"] = (
                    f"GPR = {_fmt(GPR)} V is below the tolerable touch voltage "
                    f"of {_fmt(Et)} V, so the design is safe by inspection and "
                    f"the mesh and step checks are formally unnecessary.")
                c["headroom"] = f"{_fmt(-_pct(GPR, Et))} % below the limit."
            else:
                c["verdict"] = (
                    f"GPR = I_G · R_g = {_fmt(result['IG_kA'] * 1000)} A × "
                    f"{_fmt(Rg, 3)} Ω = {_fmt(GPR)} V, which is "
                    f"{_fmt(_pct(GPR, Et))} % above the tolerable touch "
                    f"voltage of {_fmt(Et)} V. This is expected for almost any "
                    f"real substation and is not a failure of the design — it "
                    f"simply means the mesh and step voltages below decide the "
                    f"outcome.")
                c["driver"] = (
                    f"R_g = {_fmt(Rg, 3)} Ω, dominated by the grid area "
                    f"({_fmt(g['A'])} m²) and the soil resistivity "
                    f"({_fmt(rho)} Ω·m).")
            continue

        # ---- mesh (touch) voltage --------------------------------------
        if name.startswith("Mesh"):
            c["meaning"] = MEANING["touch"]
            c["driver"] = (
                f"E_m = ρ·K_m·K_i·I_G / L_M = {_fmt(rho)} × {_fmt(mesh['Km'], 3)} "
                f"× {_fmt(mesh['Ki'], 3)} × {_fmt(result['IG_kA'] * 1000)} / "
                f"{_fmt(mesh['LM'])} = {_fmt(Em)} V. The geometric factor "
                f"n = {_fmt(mesh['n'], 2)} sets K_i, and the conductor spacing "
                f"D = {_fmt(g['D'], 1)} m sets K_m.")
            if c["passed"]:
                c["verdict"] = (
                    f"E_m = {_fmt(Em)} V is {_fmt(-_pct(Em, Et))} % below the "
                    f"tolerable touch voltage of {_fmt(Et)} V, so a person "
                    f"touching earthed metal at the worst point in the grid "
                    f"would pass less than the fibrillation current for "
                    f"{_fmt(ts, 2)} s.")
                c["headroom"] = (
                    f"The design would still comply with the grid current up "
                    f"to {_fmt(result['IG_kA'] * Et / Em, 2)} kA, or with the "
                    f"soil resistivity up to {_fmt(rho * Et / Em)} Ω·m.")
            else:
                need = Em / Et
                remedies = []
                # 1. clearing time
                ts_need = ts * (Et / Em) ** 2
                remedies.append(
                    f"Reduce the fault clearing time from {_fmt(ts, 2)} s to "
                    f"{_fmt(ts_need, 2)} s or less — the tolerable voltage "
                    f"scales as 1/√t_s, so this alone closes the gap.")
                # 2. surface layer
                hs_need = _invert_hs(rho, rho_s, ts, k, Em)
                if hs_need and hs_need > hs:
                    remedies.append(
                        f"Increase the surface-layer thickness from "
                        f"{_fmt(hs, 3)} m to about {_fmt(hs_need, 3)} m, which "
                        f"raises C_s and with it the tolerable touch voltage.")
                else:
                    remedies.append(
                        "A thicker surface layer will not be enough on its "
                        "own — C_s saturates, so the tolerable voltage cannot "
                        "rise much further by that route alone.")
                # 3. more buried metal
                remedies.append(
                    f"Increase the effective mesh length L_M by a factor of at "
                    f"least {_fmt(need, 2)} (from {_fmt(mesh['LM'])} m to about "
                    f"{_fmt(mesh['LM'] * need)} m) by reducing the conductor "
                    f"spacing or adding perimeter rods. Reducing D also lowers "
                    f"K_m, so the real requirement is a little less than this.")
                # 4. current
                remedies.append(
                    f"Reduce the grid current: E_m is proportional to I_G, so "
                    f"I_G would have to fall from "
                    f"{_fmt(result['IG_kA'], 3)} kA to "
                    f"{_fmt(result['IG_kA'] / need, 3)} kA — usually achieved "
                    f"by a lower split factor S_f, i.e. more overhead earth "
                    f"wires or cable sheaths sharing the return current.")
                c["remedy"] = remedies
                c["verdict"] = (
                    f"E_m = {_fmt(Em)} V exceeds the tolerable touch voltage "
                    f"of {_fmt(Et)} V by {_fmt(_pct(Em, Et))} %. A person "
                    f"touching an earthed structure at the centre of a corner "
                    f"mesh during the fault could pass more than the "
                    f"fibrillation current, so the design must be changed.")
            continue

        # ---- step voltage ----------------------------------------------
        if name.startswith("Step"):
            c["meaning"] = MEANING["step"]
            c["driver"] = (
                f"E_s = ρ·K_s·K_i·I_G / L_S = {_fmt(rho)} × {_fmt(mesh['Ks'], 3)} "
                f"× {_fmt(mesh['Ki'], 3)} × {_fmt(result['IG_kA'] * 1000)} / "
                f"{_fmt(mesh['LS'])} = {_fmt(Es)} V. K_s is dominated by the "
                f"burial depth h = {_fmt(g['h'], 2)} m, because the steepest "
                f"surface gradient sits directly over the outermost conductor.")
            if c["passed"]:
                c["verdict"] = (
                    f"E_s = {_fmt(Es)} V is {_fmt(-_pct(Es, Estep))} % below "
                    f"the tolerable step voltage of {_fmt(Estep)} V. This is "
                    f"the usual outcome: the foot-to-foot body path has about "
                    f"four times the resistance of the hand-to-feet path, so "
                    f"the step limit is roughly four times the touch limit "
                    f"while the two computed voltages are of the same order.")
                c["headroom"] = f"{_fmt(-_pct(Es, Estep))} % margin."
            else:
                c["verdict"] = (
                    f"E_s = {_fmt(Es)} V exceeds the tolerable step voltage of "
                    f"{_fmt(Estep)} V by {_fmt(_pct(Es, Estep))} %. This is "
                    f"unusual and normally points to a very shallow grid, a "
                    f"very high soil resistivity, or too little buried metal.")
                c["remedy"] = [
                    f"Bury the grid deeper: K_s falls as 1/(2h), so increasing "
                    f"h from {_fmt(g['h'], 2)} m materially reduces E_s.",
                    f"Add a perimeter conductor or rods to raise L_S from "
                    f"{_fmt(mesh['LS'])} m.",
                    "Extend the surface layer at least 1 m beyond the fence "
                    "line, where the step gradient is steepest.",
                ]
            continue

    result["narrative"] = _narrative_ieee80(result)
    return result


def _narrative_ieee80(r: dict) -> str:
    tol, mesh = r["tolerable"], r["mesh"]
    if r["passed"]:
        if r["GPR"] <= tol["E_touch"]:
            return (
                f"The design complies. The ground potential rise "
                f"({_fmt(r['GPR'])} V) never reaches the tolerable touch "
                f"voltage ({_fmt(tol['E_touch'])} V), so no person can be "
                f"exposed to a dangerous potential anywhere on the site, "
                f"whatever the shape of the potential profile.")
        return (
            f"The design complies. The ground potential rise is "
            f"{_fmt(r['GPR'])} V, well above the tolerable touch voltage, but "
            f"the earth grid distributes that rise so evenly that the worst "
            f"touch voltage inside the grid is only {_fmt(mesh['Em'])} V "
            f"against a limit of {_fmt(tol['E_touch'])} V, and the worst step "
            f"voltage is {_fmt(mesh['Es'])} V against {_fmt(tol['E_step'])} V. "
            f"That evenness is what the {_fmt(r['geometry']['LT'])} m of buried "
            f"conductor buys.")
    failing = [c["name"] for c in r["checks"][1:] if not c["passed"]]
    return (
        f"The design does not comply: {', '.join(failing)} exceeds the "
        f"tolerable value. The grid resistance itself ({_fmt(r['Rg'], 3)} Ω) is "
        f"not the problem — what matters is how unevenly the potential is "
        f"distributed inside the grid. Each remedy listed against the failing "
        f"criterion is quantified; the Auto-refine button searches the "
        f"conductor spacing and then perimeter rods automatically.")


# ---------------------------------------------------------------------------
# IEC 60364 installation
# ---------------------------------------------------------------------------

def explain_building(result: dict, rho: float | None = None) -> dict:
    U0 = result.get("U0", 230.0)
    RA = result.get("RA")
    dev = result.get("device", {})
    Ia = dev.get("Ia")
    t = (result.get("disconnection") or {}).get("t")

    for c in result.get("checks", []):
        name = c.get("name", "")

        if name.startswith("Earth-fault loop"):
            c["meaning"] = MEANING["zs"]
            Zs, Zmax = c.get("Zs"), c.get("Zs_max")
            If = c.get("If")
            c["driver"] = (
                f"Z_s = {_fmt(Zs, 3)} Ω gives a prospective fault current of "
                f"{_fmt(If)} A; the device needs {_fmt(Ia)} A to operate "
                f"within {_fmt(t, 2)} s ({dev.get('basis', '')}).")
            if c.get("passed"):
                c["verdict"] = (
                    f"Z_s = {_fmt(Zs, 3)} Ω is below the maximum permitted "
                    f"{_fmt(Zmax, 3)} Ω, so the fault current of {_fmt(If)} A "
                    f"comfortably exceeds the {_fmt(Ia)} A the device needs and "
                    f"disconnection happens within {_fmt(t, 2)} s.")
                c["headroom"] = (
                    f"The loop impedance could rise to {_fmt(Zmax, 3)} Ω — a "
                    f"{_fmt((Zmax - Zs) / max(Zs, 1e-9) * 100)} % increase — "
                    f"before the criterion is lost. That is the allowance for "
                    f"conductor heating and for future circuit extensions.")
            else:
                c["verdict"] = (
                    f"Z_s = {_fmt(Zs, 3)} Ω exceeds the maximum of "
                    f"{_fmt(Zmax, 3)} Ω. The fault current would be only "
                    f"{_fmt(If)} A against the {_fmt(Ia)} A needed, so the "
                    f"device would not trip within {_fmt(t, 2)} s and the "
                    f"exposed metal would stay live.")
                c["remedy"] = [
                    f"Reduce Z_s to {_fmt(Zmax, 3)} Ω or less — increase the "
                    f"protective conductor cross-section, or shorten the "
                    f"circuit; Z_s falls roughly in proportion to the run "
                    f"length.",
                    f"Use a device with a lower operating current: a type B "
                    f"breaker trips at 5·I_n against 10·I_n for type C, which "
                    f"halves the required fault current.",
                    "Add a residual-current device: an RCD makes the "
                    "disconnection independent of the loop impedance, and is "
                    "the standard remedy when Z_s cannot be reduced.",
                ]
            continue

        if name.startswith("TT electrode"):
            c["meaning"] = MEANING["tt"]
            RAmax = c.get("RA_max")
            Ut = c.get("touch_voltage")
            c["driver"] = (
                f"R_A = {_fmt(RA, 2)} Ω and I_a = {_fmt(Ia)} A give a "
                f"prospective touch voltage of {_fmt(Ut)} V.")
            if c.get("passed"):
                c["verdict"] = (
                    f"R_A · I_a = {_fmt(Ut)} V stays below the {_fmt(c.get('UL', 50))} V "
                    f"limit, so exposed metal cannot reach a dangerous "
                    f"potential during an earth fault. The electrode could be "
                    f"as poor as {_fmt(RAmax, 1)} Ω and still satisfy this.")
                c["headroom"] = (
                    f"Electrode resistance may rise to {_fmt(RAmax, 1)} Ω — "
                    f"important, because soil dries out in summer and a rod "
                    f"electrode can easily double its resistance between "
                    f"seasons.")
            else:
                c["verdict"] = (
                    f"R_A · I_a = {_fmt(Ut)} V exceeds the "
                    f"{_fmt(c.get('UL', 50))} V limit. The electrode "
                    f"resistance must not exceed {_fmt(RAmax, 2)} Ω but is "
                    f"{_fmt(RA, 2)} Ω.")
                rem = [
                    f"Lower R_A to {_fmt(RAmax, 2)} Ω — a factor of "
                    f"{_fmt(RA / max(RAmax, 1e-9), 2)} — by adding electrodes "
                    f"in parallel, using longer rods, or bonding to the "
                    f"foundation reinforcement.",
                    "Use a more sensitive RCD: the permitted electrode "
                    "resistance is inversely proportional to IΔn, so going "
                    "from 300 mA to 30 mA relaxes R_A by a factor of ten.",
                ]
                c["remedy"] = rem
            continue

        if name.startswith("RCD"):
            c["meaning"] = MEANING["rcd"]
            det = c.get("detail", {})
            sel = det.get("selected_mA")
            c["verdict"] = (
                f"With R_A = {_fmt(RA, 2)} Ω the largest residual current that "
                f"keeps the touch voltage under 50 V is "
                f"{_fmt(det.get('max_IdN', 0) * 1000)} mA, so the largest "
                f"standard rating that qualifies is {_fmt(sel)} mA."
                if sel else
                f"With R_A = {_fmt(RA, 2)} Ω no standard RCD rating satisfies "
                f"R_A · IΔn ≤ 50 V; the electrode must be improved first.")
            if det.get("additional_protection_30mA"):
                c["headroom"] = (
                    "A 30 mA RCD is also acceptable here, which is what "
                    "IEC 60364-4-41 §415.1 requires for socket outlets and "
                    "for additional protection against direct contact.")
            continue

    result["narrative"] = _narrative_building(result)
    return result


def _narrative_building(r: dict) -> str:
    sysname = r.get("system", "")
    if r.get("passed"):
        return (
            f"The {sysname} installation complies. Every earth fault on the "
            f"circuit is cleared within the time required by IEC 60364-4-41 "
            f"Table 41.1, and the voltage appearing on exposed metal while the "
            f"fault lasts stays inside the safe limit. The electrode "
            f"resistance is {_fmt(r.get('RA'), 2)} Ω and the loop impedance "
            f"{_fmt(r.get('Zs'), 3)} Ω.")
    bad = [c.get("name") for c in r.get("checks", []) if not c.get("passed", True)]
    return (
        f"The {sysname} installation does not comply: {', '.join(bad)}. Until "
        f"this is corrected, an earth fault would leave exposed metal at a "
        f"dangerous potential for longer than the standard permits. The "
        f"quantified remedies are listed against each failing criterion.")


# ---------------------------------------------------------------------------
# IEC 62305 lightning
# ---------------------------------------------------------------------------

def explain_lightning(result: dict) -> dict:
    e = result.get("earth", {})
    R = e.get("R_total")
    for c in result.get("checks", []):
        name = c.get("name", "")
        if name.startswith("Earth-termination geometry"):
            c["meaning"] = MEANING["lps_geom"]
            l1 = e.get("l1") if isinstance(e.get("l1"), (int, float)) else \
                (e.get("l1") or {}).get("l1")
            if result.get("earth", {}).get("arrangement") == "Type B":
                re_ = e.get("mean_radius")
                if c.get("passed"):
                    c["verdict"] = (
                        f"The ring encloses an area whose mean radius is "
                        f"{_fmt(re_, 2)} m, which meets the minimum electrode "
                        f"length l₁ = {_fmt(l1, 1)} m for class "
                        f"{result.get('lps_class')} in {_fmt(result.get('rho'))} Ω·m "
                        f"soil.")
                else:
                    sup = e.get("supplementary") or {}
                    c["verdict"] = (
                        f"The ring mean radius is only {_fmt(re_, 2)} m "
                        f"against the required l₁ = {_fmt(l1, 1)} m, so the "
                        f"lightning current would be forced into too small a "
                        f"soil volume.")
                    c["remedy"] = [
                        f"Add a horizontal electrode of "
                        f"{_fmt(sup.get('horizontal_each'), 1)} m, or a "
                        f"vertical one of {_fmt(sup.get('vertical_each'), 1)} m, "
                        f"at each down-conductor (IEC 62305-3 §5.4.2.2).",
                        "Or enlarge the ring so that √(A/π) ≥ l₁.",
                    ]
            else:
                c["verdict"] = (
                    f"Each electrode is {_fmt(e.get('L_used'), 1)} m against a "
                    f"required {_fmt(e.get('L_required'), 1)} m, and there are "
                    f"{e.get('n_electrodes')} of them (minimum two).")
            continue

        if name.startswith("Earthing resistance"):
            c["meaning"] = MEANING["lps_r"]
            if c.get("passed"):
                c["verdict"] = (
                    f"R_E = {_fmt(R, 2)} Ω is below the 10 Ω recommended by "
                    f"IEC 62305-3, so the potential rise during a stroke and "
                    f"the risk of side flashing to nearby services are both "
                    f"kept low.")
            else:
                c["verdict"] = (
                    f"R_E = {_fmt(R, 2)} Ω exceeds the 10 Ω that IEC 62305-3 "
                    f"recommends. This is informative rather than mandatory — "
                    f"the geometric requirement above is the binding one — but "
                    f"a high resistance raises the potential rise and makes "
                    f"equipotential bonding of incoming services more "
                    f"important.")
                c["remedy"] = [
                    f"Add electrodes in parallel or extend the ring: R_E would "
                    f"have to fall by a factor of {_fmt(R / 10.0, 2)}.",
                    "Bond to the foundation reinforcement — a foundation earth "
                    "electrode is usually the cheapest way to reach a low "
                    "resistance, because it uses concrete already in the "
                    "ground.",
                    "Where the soil is genuinely poor, accept the resistance "
                    "and concentrate on bonding and SPD coordination at the "
                    "LPZ 0/1 boundary.",
                ]
            continue

        if name.startswith("Number of down"):
            c["meaning"] = MEANING["lps_down"]
            dc = result.get("down_conductors", {})
            c["verdict"] = (
                f"{dc.get('n_down')} down-conductors at {_fmt(dc.get('actual_spacing'), 1)} m "
                f"spacing, against the {dc.get('typical_spacing')} m typical "
                f"spacing for class {result.get('lps_class')}. More "
                f"down-conductors divide the current further and reduce the "
                f"separation distance s, which is {_fmt((result.get('separation') or {}).get('s'), 2)} m here.")
            continue

    result["narrative"] = _narrative_lightning(result)
    return result


def _narrative_lightning(r: dict) -> str:
    if r.get("passed"):
        return (
            f"The earth termination satisfies IEC 62305-3 for class "
            f"{r.get('lps_class')}: the electrode geometry disperses the "
            f"lightning current over enough soil, there are enough "
            f"down-conductors to divide it, and the earthing resistance is "
            f"within the recommended value.")
    bad = [c.get("name") for c in r.get("checks", []) if not c.get("passed", True)]
    return (
        f"The earth termination does not yet satisfy IEC 62305-3 class "
        f"{r.get('lps_class')}: {', '.join(bad)}. Note that the geometric "
        f"requirement is mandatory while the 10 Ω resistance is a "
        f"recommendation, so treat them differently when deciding what to "
        f"change.")


# ---------------------------------------------------------------------------
# Numerical solver
# ---------------------------------------------------------------------------

def explain_bem(result: dict) -> dict:
    for c in result.get("checks", []):
        name = c.get("name", "")
        v, lim = c.get("value"), c.get("limit")
        if name.startswith("Maximum touch"):
            c["meaning"] = MEANING["bem_touch"]
            at = result.get("touch_at") or [0, 0]
            if c.get("passed"):
                c["verdict"] = (
                    f"The worst touch voltage found anywhere in the reachable "
                    f"area is {_fmt(v)} V at x = {_fmt(at[0], 1)} m, "
                    f"y = {_fmt(at[1], 1)} m, which is {_fmt(-_pct(v, lim))} % "
                    f"below the tolerable {_fmt(lim)} V.")
            else:
                c["verdict"] = (
                    f"The worst touch voltage is {_fmt(v)} V at "
                    f"x = {_fmt(at[0], 1)} m, y = {_fmt(at[1], 1)} m — "
                    f"{_fmt(_pct(v, lim))} % above the tolerable {_fmt(lim)} V. "
                    f"Look at the touch-voltage map: the hot spot is where the "
                    f"buried metal is furthest from the surface point a person "
                    f"can stand on while touching earthed steel.")
                c["remedy"] = [
                    "Add conductor or rods local to the hot spot — the "
                    "numerical solver lets you fix the specific location "
                    "rather than tightening the whole grid.",
                    "Extend the surface layer over the hot spot, which raises "
                    "the tolerable value rather than lowering the computed one.",
                    "Where the hot spot lies just outside a corner, a buried "
                    "perimeter conductor one metre out is the classic remedy.",
                ]
            continue
        if name.startswith("Maximum step"):
            c["meaning"] = MEANING["bem_step"]
            at = result.get("step_at") or [0, 0]
            c["verdict"] = (
                f"The steepest surface gradient over "
                f"{_fmt(result.get('profile', {}).get('step_distance', 1), 1)} m "
                f"is {_fmt(v)} V at x = {_fmt(at[0], 1)} m, y = {_fmt(at[1], 1)} m"
                + (f", {_fmt(-_pct(v, lim))} % below the tolerable {_fmt(lim)} V."
                   if c.get("passed") else
                   f", {_fmt(_pct(v, lim))} % above the tolerable {_fmt(lim)} V."))
            continue

    probes = result.get("probes") or []
    corner = next((p for p in probes if "orner mesh" in str(p.get("label"))), None)
    if corner:
        result["cross_check"] = (
            f"The touch voltage computed numerically at the centre of the "
            f"corner mesh is {_fmt(corner.get('touch'))} V. Comparing this with "
            f"the closed-form IEEE 80 mesh voltage for the same grid is the "
            f"single most useful validation you can do: the two methods share "
            f"no equations, so agreement within 5–15 % means both are right, "
            f"and a large disagreement means the grid violates an assumption "
            f"of the closed-form equations (usually shape irregularity or a "
            f"strongly layered soil).")
    result["narrative"] = _narrative_bem(result)
    return result


def _narrative_bem(r: dict) -> str:
    base = (
        f"The boundary-element solution used {r.get('segments')} segments over "
        f"{_fmt(r.get('total_length'))} m of buried metal and gives an earth "
        f"resistance of {_fmt(r.get('Rg'), 3)} Ω, a ground potential rise of "
        f"{_fmt(r.get('GPR'))} V, a worst touch voltage of "
        f"{_fmt(r.get('touch_max'))} V and a worst step voltage of "
        f"{_fmt(r.get('step_max'))} V.")
    checks = r.get("checks")
    if not checks:
        return base + (
            " No tolerable limits were supplied, so no verdict is given — run "
            "the substation-grid module first and the limits from it will be "
            "applied here automatically.")
    if all(c.get("passed") for c in checks):
        return base + " Both are inside the tolerable limits, so the design complies."
    return base + (
        " At least one exceeds the tolerable limit; the map on the touch/step "
        "tab shows where, which is the practical advantage of the numerical "
        "method over the closed-form equations.")


def explain_airterm(result: dict) -> dict:
    """Say why an air-termination arrangement protects what it protects."""
    R = result.get("R")
    cls = result.get("lps_class")
    ref = result.get("reference_plane") or 0.0
    terms = result.get("terminals") or []
    st = result.get("structure") or {}
    tall = max(terms, key=lambda t: t.get("tip") or 0.0) if terms else {}
    n_exposed = result.get("exposed_count") or 0

    for c in result.get("checks", []):
        name = c.get("name", "")

        if name.startswith("Rolling sphere — roof surface") or \
           name.startswith("Rolling sphere — protected volume"):
            c["meaning"] = MEANING["rs_field"]
            c["driver"] = (
                f"The sphere radius R = {_fmt(R, 0)} m for class {cls}, and the "
                f"tallest termination reaches {_fmt(tall.get('tip'), 2)} m, "
                f"{_fmt(tall.get('above_reference'), 2)} m above the plane being "
                f"protected at {_fmt(ref, 2)} m.")
            if c.get("passed"):
                c["verdict"] = (
                    f"Rolling a sphere of radius {_fmt(R, 0)} m over the "
                    f"arrangement, no position of that sphere touches the "
                    f"protected surface, so every flash the class has to "
                    f"intercept is caught by the terminations first.")
                c["headroom"] = (
                    "The elevation shows the sphere in the positions that "
                    "generated the boundary; the protected volume is the "
                    "region under those arcs.")
            else:
                c["verdict"] = (
                    f"The sphere reaches the protected surface at "
                    f"{n_exposed} of the points scanned, so part of the "
                    f"structure can be struck directly.")
                c["remedy"] = [
                    "Add a termination in the gap, or raise the existing ones: "
                    "the protected height at mid-span is the tip height minus "
                    "the sag p = R − sqrt(R² − (d/2)²).",
                    "Or reduce the spacing below the largest permissible span "
                    "listed in the results table for this class.",
                    "Or move to a finer mesh air termination on the flat "
                    f"surface — {_fmt(result.get('mesh_size'), 0)} m for class {cls}.",
                ]
            continue

        if name.startswith("Rolling sphere — roof edges"):
            c["meaning"] = MEANING["rs_edge"]
            c["driver"] = (
                f"The wall is {_fmt(st.get('height'), 1)} m high and the sphere "
                f"radius is {_fmt(R, 0)} m, so a sphere resting on the ground "
                f"beside the building reaches the roof edge unless a "
                f"termination stands there.")
            if c.get("passed"):
                c["verdict"] = ("Terminations cover the edges and corners, "
                                "which are the first points a leader can reach.")
            else:
                c["verdict"] = ("Nothing intercepts the flash at the roof edge, "
                                "so the edge itself is the strike point.")
                c["remedy"] = [
                    "Run a perimeter air-termination conductor along the roof "
                    "edge and bond it to the down-conductors.",
                    "Put a short rod on each corner — the 'Corner rods' layout "
                    "on this page places them for you.",
                ]
            continue

        if name.startswith("Sphere penetration"):
            c["meaning"] = MEANING["rs_span"]
            if c.get("passed"):
                c["verdict"] = ("The sphere sags into the span but still "
                                "clears the protected plane.")
            else:
                c["verdict"] = ("The sphere reaches through the span and "
                                "touches the protected plane between the two "
                                "terminations.")
                c["remedy"] = [
                    "Close the spacing, or raise both terminations: the "
                    "protected height at mid-span is h − p.",
                    "Or add one termination in the middle of the span.",
                ]
            continue

        if name.startswith("Plan coverage") or name.startswith("Corners of the"):
            c["meaning"] = MEANING["rs_plan"]
            pl = result.get("plan") or {}
            if c.get("passed"):
                c["verdict"] = ("Every point of the protected plane falls "
                                "inside the protected circle of at least one "
                                "termination.")
            else:
                bad = [k for k in (pl.get("corners") or []) if not k.get("protected")]
                c["verdict"] = (
                    f"{_fmt(100.0 * (pl.get('covered_fraction') or 0.0), 1)} % of "
                    f"the plane is inside a protected circle"
                    + (f"; {len(bad)} corner(s) are outside every circle."
                       if bad else "."))
                c["remedy"] = [
                    "Add a termination over the uncovered area — the red points "
                    "on the plan mark it.",
                    "Or raise a termination: r_p grows as sqrt(2Rh − h²) with "
                    "height, up to h = R.",
                ]
            continue

        if name.startswith("Mesh size"):
            c["meaning"] = MEANING["rs_mesh"]
            c["verdict"] = (
                f"Class {cls} allows a mesh of "
                f"{_fmt(result.get('mesh_size'), 0)} m; the layout gives "
                f"{_fmt(c.get('value'), 2)} m.")
            if not c.get("passed"):
                c["remedy"] = ["Add a mesh conductor in each direction until "
                               "the spacing falls to the class value."]
            continue

        if name.startswith("Down-conductor"):
            c["meaning"] = MEANING["lps_down"]
            ms = result.get("mesh") or {}
            c["verdict"] = (
                f"{ms.get('n_down')} down-conductors round a perimeter of "
                f"{_fmt(ms.get('perimeter'), 1)} m give "
                f"{_fmt(ms.get('actual_down_spacing'), 1)} m between them "
                f"against the {_fmt(c.get('limit'), 0)} m typical for class {cls}.")
            continue

    ok = all(c.get("passed") for c in result.get("checks", []))
    n = len(terms)
    result["narrative"] = (
        f"A sphere of radius {_fmt(R, 0)} m — the striking distance for class "
        f"{cls} — was rolled over the structure and the {n} air termination"
        f"{'s' if n != 1 else ''} entered. "
        + ("Nothing it can touch lies on the protected surface, so the "
           "arrangement intercepts every flash the class has to catch."
           if ok else
           "It reaches the protected surface, so the arrangement leaves part "
           "of the structure open to a direct strike; the elevation marks "
           "where.")
        + " The protective angle and mesh results are shown alongside for "
          "comparison, but the rolling sphere is the method that governs.")
    return result
