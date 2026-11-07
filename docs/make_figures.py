#!/usr/bin/env python3
"""
Generate the figures for the Earthing System theory document (docs/THEORY.md).

Every plot that can be computed is computed with the earthsys engine itself, so
the figures in the documentation and the numbers in the software cannot drift apart.

    python docs/make_figures.py            # writes docs/figures/*.png
"""

from __future__ import annotations

import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle, Circle, FancyBboxPatch

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
OUT = os.path.join(BASE, "docs", "figures")
os.makedirs(OUT, exist_ok=True)

from earthsys import bem, conductor, faultcurrent, iec60364, iec62305, ieee80, soil  # noqa

# ---------------------------------------------------------------- style ----
ACC, RED, GRN, ORG, PUR = "#0f6b8a", "#c0322b", "#0b7a45", "#a8630a", "#6d4aa8"
SOIL, METAL = "#e8dcc8", "#8a949c"
INK, INK2, INK3, LINE = "#1a2027", "#4a5661", "#6b7884", "#d8e0e7"
# Okabe-Ito based series colours, the same as the application's charts, so a
# curve keeps its colour from the screen to the printed document and survives colour blindness
SERIES = ["#0072b2", "#d55e00", "#009e73", "#b4579a", "#9a6700", "#7a5cc4"]
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": INK3, "axes.labelcolor": INK, "axes.linewidth": 0.8,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": "#0f2f4f",
    "axes.titlelocation": "left", "axes.titlepad": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.prop_cycle": matplotlib.cycler(color=SERIES),
    "axes.grid": True, "grid.color": LINE, "grid.linewidth": 0.55,
    "axes.axisbelow": True,
    "xtick.color": INK3, "ytick.color": INK3, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.major.size": 3.2, "ytick.major.size": 3.2,
    "lines.solid_capstyle": "round",
    "legend.frameon": True, "legend.framealpha": .94, "legend.edgecolor": LINE,
    "legend.fancybox": True, "legend.borderpad": 0.5,
    "figure.dpi": 200, "savefig.dpi": 220, "savefig.bbox": "tight", "savefig.pad_inches": 0.08,
    "savefig.facecolor": "white",
})


def save(fig, name):
    p = os.path.join(OUT, name + ".png")
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    print("  ", name + ".png")


# ============================================================ 1. half space
def fig_halfspace():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.4))
    rho, I, a0 = 100.0, 1000.0, 0.5
    r = np.linspace(a0, 20, 500)
    V = rho * I / (2 * np.pi * r)
    a1.plot(r, V, color=ACC, lw=2.2)
    a1.fill_between(r[r <= 1], V[r <= 1], color=ACC, alpha=.28,
                    label="0.5–1 m: 50 % of the total R")
    a1.fill_between(r[(r > 1) & (r <= 10)], V[(r > 1) & (r <= 10)],
                    color=ACC, alpha=.13, label="1–10 m: 45 %")
    a1.fill_between(r[r > 10], V[r > 10], color=ACC, alpha=.05, label="10 m–∞: 5 %")
    a1.set_xlabel("Distance from the electrode, r (m)")
    a1.set_ylabel("Potential V (V)")
    a1.set_title("(a) Potential of a hemispherical electrode")
    a1.legend(fontsize=7.5, loc="upper right")
    a1.set_xlim(0, 20)

    Rcum = rho / (2 * np.pi) * (1 / a0 - 1 / r)
    Rtot = rho / (2 * np.pi * a0)
    a2.plot(r, 100 * Rcum / Rtot, color=RED, lw=2.2)
    a2.axhline(50, color="#5a6773", ls=":", lw=1)
    a2.axvline(1.0, color="#5a6773", ls=":", lw=1)
    a2.annotate("half the resistance\nlies within 1 m", xy=(1.0, 50),
                xytext=(5.5, 38), fontsize=8,
                arrowprops=dict(arrowstyle="->", color="#5a6773", lw=1))
    a2.set_xlabel("Distance from the electrode, r (m)")
    a2.set_ylabel("Cumulative resistance (% of total)")
    a2.set_title("(b) Where the earth resistance actually is")
    a2.set_xlim(0, 20); a2.set_ylim(0, 100)
    fig.tight_layout()
    save(fig, "fig01_halfspace")


# ====================================================== 2. body circuit ----
def fig_body():
    """Pictorial above, equivalent circuit below — the point of the figure is
    that only the foot network differs between the two cases."""
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.6))

    def resistor(ax, x, y, w, h, label, color):
        # drawn over the wire, so the wire stops at the body of the resistor
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                    boxstyle="round,pad=0,rounding_size=0.08",
                                    fc="white", ec=color, lw=1.6, zorder=3))
        ax.text(x, y, label, ha="center", va="center", fontsize=8, color=color, zorder=4)

    for ax, kind in zip(axes, ("touch", "step")):
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
        # ---------- pictorial ----------
        ax.add_patch(Rectangle((0, 5.4), 10, 1.5, fc=SOIL, ec="none"))
        ax.plot([0, 10], [6.9, 6.9], color="#a08a6a", lw=1.4)

        if kind == "touch":
            ax.add_patch(Rectangle((6.9, 6.9), .75, 2.7, fc=METAL, ec="#5a6773"))
            ax.text(7.28, 9.85, "earthed metal", ha="center", fontsize=8)
            hx = 4.6
            ax.add_patch(Circle((hx, 9.35), .28, fc="none", ec="#1a2027", lw=1.4))
            ax.plot([hx, hx], [9.07, 7.95], color="#1a2027", lw=1.4)
            ax.plot([hx, hx - .42], [7.95, 6.95], color="#1a2027", lw=1.4)
            ax.plot([hx, hx + .42], [7.95, 6.95], color="#1a2027", lw=1.4)
            ax.plot([hx, 6.85], [8.85, 8.85], color="#1a2027", lw=1.4)
            ax.annotate("", xy=(6.7, 8.6), xytext=(5.0, 8.6),
                        arrowprops=dict(arrowstyle="<-", color=RED, lw=1.6))
            ax.text(5.85, 8.25, "$I_B$", fontsize=9, color=RED, ha="center")
            ax.text(0.35, 9.5, "TOUCH", fontsize=11.5, fontweight="bold",
                    color="#0f2f4f")
            ax.text(0.35, 8.9, "hand → both feet", fontsize=8.6, color="#5a6773")
            ax.text(0.35, 6.0, "both feet on the\nsame potential", fontsize=8,
                    color="#8a7b5c")
        else:
            hx = 4.9
            ax.add_patch(Circle((hx, 9.35), .28, fc="none", ec="#1a2027", lw=1.4))
            ax.plot([hx, hx], [9.07, 7.95], color="#1a2027", lw=1.4)
            ax.plot([hx, hx - 1.0], [7.95, 6.95], color="#1a2027", lw=1.4)
            ax.plot([hx, hx + 1.0], [7.95, 6.95], color="#1a2027", lw=1.4)
            ax.annotate("", xy=(hx + 1.0, 6.55), xytext=(hx - 1.0, 6.55),
                        arrowprops=dict(arrowstyle="<->", color=ORG, lw=1.4))
            ax.text(hx, 6.15, "1 m", ha="center", fontsize=8.4, color=ORG)
            ax.text(0.35, 9.5, "STEP", fontsize=11.5, fontweight="bold",
                    color="#0f2f4f")
            ax.text(0.35, 8.9, "foot → foot", fontsize=8.6, color="#5a6773")
            ax.text(0.35, 6.0, "the two feet sit on\ndifferent potentials",
                    fontsize=8, color="#8a7b5c")

        # ---------- equivalent circuit ----------
        # One series loop: the touch (or step) voltage drives the body current
        # through the body and then through the foot network back to the soil.
        L, Rr, T, B = 1.3, 8.6, 4.45, 1.55
        wire = dict(color=INK, lw=1.25, solid_capstyle="round", zorder=2)
        ax.plot([L, L], [T, 3.33], **wire); ax.plot([L, L], [2.67, B], **wire)
        ax.add_patch(Circle((L, 3.0), .33, fc="white", ec=INK, lw=1.25, zorder=3))
        ax.text(L, 3.14, "+", ha="center", va="center", fontsize=8, color=INK, zorder=4)
        ax.text(L, 2.83, "−", ha="center", va="center", fontsize=8, color=INK, zorder=4)
        ax.text(L - .48, 3.0, "$U_T$" if kind == "touch" else "$U_S$", ha="right", va="center",
                fontsize=10, color="#0f2f4f")
        ax.plot([L, Rr], [T, T], **wire)
        ax.plot([L, Rr], [B, B], **wire)
        resistor(ax, 3.55, T, 2.6, .74, "$R_B$ = 1000 Ω  (body)", RED)
        ax.annotate("", xy=(5.6, T + .3), xytext=(5.0, T + .3),
                    arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.2, mutation_scale=9))
        ax.text(5.3, T + .46, "$I_B$", ha="center", fontsize=8.6, color=RED)

        if kind == "touch":
            # the two feet side by side: in parallel
            for x in (6.75, Rr):
                ax.plot([x, x], [T, B], **wire)
                resistor(ax, x, 3.0, .9, 1.1, "$3\\rho_s$", ACC)
            for x, y in ((6.75, T), (6.75, B)):
                ax.add_patch(Circle((x, y), .075, fc=INK, ec="none", zorder=4))
            ax.text(5.95, 3.0, "feet in parallel\n= $1.5\\rho_s$", ha="right", va="center",
                    fontsize=8.2, color=ACC, linespacing=1.4)
            ax.text(5.0, .62, "$U_T = I_B\\,(R_B + 1.5\\,C_s\\rho_s)$",
                    ha="center", fontsize=10.5, color="#0f2f4f")
        else:
            # one foot after the other: in series
            ax.plot([Rr, Rr], [T, B], **wire)
            resistor(ax, Rr, 3.57, .9, .86, "$3\\rho_s$", ACC)
            resistor(ax, Rr, 2.43, .9, .86, "$3\\rho_s$", ACC)
            ax.text(Rr - .75, 3.0, "feet in series\n= $6\\rho_s$", ha="right", va="center",
                    fontsize=8.2, color=ACC, linespacing=1.4)
            ax.text(5.0, .62, "$U_S = I_B\\,(R_B + 6\\,C_s\\rho_s)$",
                    ha="center", fontsize=10.5, color="#0f2f4f")

    fig.suptitle("The body as a circuit — only the foot network changes, and that "
                 "is the whole difference between 1.5 and 6",
                 fontsize=9.6, color="#0f2f4f", y=1.0)
    fig.tight_layout()
    save(fig, "fig02_body_circuit")


# ========================================================== 3. Wenner -----
def fig_wenner():
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    ax.set_xlim(-1, 11); ax.set_ylim(-4.2, 2.4); ax.axis("off")
    ax.add_patch(Rectangle((-1, -4.2), 12, 4.2, fc=SOIL, ec="none"))
    ax.plot([-1, 11], [0, 0], color="#a08a6a", lw=1.6)
    xs = [1.5, 4.0, 6.5, 9.0]
    lab = ["C1", "P1", "P2", "C2"]
    col = [RED, ACC, ACC, RED]
    for x, l, c in zip(xs, lab, col):
        ax.plot([x, x], [0, -0.55], color=c, lw=3.2, solid_capstyle="butt")
        ax.plot(x, 0.12, marker="v", color=c, ms=7)
        ax.text(x, 0.55, l, ha="center", fontsize=9.5, fontweight="bold", color=c)
    for x0, x1 in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(x1, 1.55), xytext=(x0, 1.55),
                    arrowprops=dict(arrowstyle="<->", color="#5a6773", lw=1))
        ax.text((x0 + x1) / 2, 1.75, "a", ha="center", fontsize=9, style="italic")
    # current flow lines
    th = np.linspace(0, np.pi, 200)
    for k, rr in enumerate([1.3, 2.2, 3.1, 4.0]):
        cx = (xs[0] + xs[3]) / 2
        ax.plot(cx + rr * 1.55 * np.cos(th), -rr * 0.85 * np.sin(th),
                color=RED, lw=.9, alpha=.42)
    ax.text(5.25, -3.6, "current flow lines", ha="center", fontsize=8, color=RED,
            alpha=.85)
    ax.text(5.25, 2.12, "$\\rho_a = 2\\pi a R$,   $R = \\Delta V / I$",
            ha="center", fontsize=11, color="#0f2f4f")
    ax.text(-0.6, -1.1, "soil", fontsize=9, color="#8a7b5c")
    ax.set_title("The Wenner four-pin array", pad=13)
    fig.tight_layout()
    save(fig, "fig03_wenner")


# ==================================================== 4. two-layer curves --
def fig_twolayer():
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    a = np.logspace(-0.6, 1.8, 200)
    rho1, h = 200.0, 2.0
    for K, ls in [(-0.8, "-"), (-0.5, "-"), (-0.2, "-"),
                  (0.2, "--"), (0.5, "--"), (0.8, "--")]:
        rho2 = rho1 * (1 + K) / (1 - K)
        y = [soil.wenner_two_layer(x, rho1, rho2, h) for x in a]
        ax.plot(a, y, ls, lw=1.9,
                label=f"K = {K:+.1f}  (ρ₂ = {rho2:.0f} Ω·m)")
    ax.axhline(rho1, color="#5a6773", lw=1, ls=":")
    ax.text(0.3, rho1 * 1.04, "ρ₁ = 200 Ω·m", fontsize=8, color="#5a6773")
    ax.axvline(h, color=ORG, lw=1, ls=":")
    ax.text(h * 1.08, 30, "h = 2 m", fontsize=8, color=ORG, rotation=90)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Wenner spacing a (m)")
    ax.set_ylabel("Apparent resistivity ρₐ (Ω·m)")
    ax.set_title("Two-layer earth: the reflection factor sets the shape of the curve")
    ax.legend(fontsize=7.6, ncol=2)
    fig.tight_layout()
    save(fig, "fig04_two_layer")


# =========================================================== 5. inversion --
def fig_inversion():
    a = [1, 2, 4, 6, 10, 16]
    y = [320, 245, 182, 162, 168, 182]
    r = soil.invert_two_layer(a, y, "wenner")
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 5.0), sharex=True,
                                 gridspec_kw=dict(height_ratios=[3, 1.15]))
    a1.plot(r["curve_x"], r["curve_y"], color=ACC, lw=2.2,
            label=f"two-layer fit: ρ₁={r['rho1']:.0f}, ρ₂={r['rho2']:.0f} Ω·m, "
                  f"h={r['h']:.2f} m")
    a1.plot(a, y, "o", color=RED, ms=8, label="measured", zorder=5)
    a1.set_ylabel("Apparent resistivity ρₐ (Ω·m)")
    a1.set_xscale("log")
    a1.set_title("Fitting a two-layer model to a field traverse")
    a1.legend(fontsize=8)
    a2.bar([str(x) for x in a], r["residual_pct"], color=ORG, width=.55)
    a2.axhline(0, color="#5a6773", lw=.9)
    a2.set_ylabel("residual (%)")
    a2.set_xlabel("Wenner spacing a (m)")
    a2.grid(axis="x", alpha=0)
    a1.text(0.02, 0.06, f"RMS error {r['rms_pct']:.1f} % — the rise beyond 6 m is a "
            f"third layer\nthe two-layer model cannot represent",
            transform=a1.transAxes, fontsize=7.8, color="#5a6773")
    fig.tight_layout()
    save(fig, "fig05_inversion")


# ==================================================== 6. decrement factor --
def fig_decrement():
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    t = np.logspace(-2, 0.7, 300)
    for xr, c in [(5, GRN), (10, ACC), (20, ORG), (40, RED)]:
        Df = [faultcurrent.decrement_factor(x, xr, 50.0)["Df"] for x in t]
        ax.plot(t, Df, color=c, lw=2, label=f"X/R = {xr}")
    ax.axhline(math.sqrt(2), color="#5a6773", ls=":", lw=1)
    ax.text(0.011, 1.425, "√2 — fully offset limit", fontsize=8, color="#5a6773")
    ax.axvline(0.5, color="#8a949c", ls="--", lw=1)
    ax.text(0.53, 1.05, "typical clearing\ntime 0.5 s", fontsize=8, color="#5a6773")
    ax.set_xscale("log")
    ax.set_xlabel("Fault duration $t_f$ (s)")
    ax.set_ylabel("Decrement factor $D_f$")
    ax.set_title("The DC offset matters only for fast-clearing faults")
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, "fig06_decrement")


# =================================================== 7. tolerable voltages -
def fig_tolerable():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.6))
    hs = np.linspace(0.0, 0.40, 200)
    for rs, c in [(1000, GRN), (2500, ACC), (5000, ORG)]:
        Cs = [ieee80.surface_derating(100.0, rs, max(h, 1e-6))["Cs"] for h in hs]
        a1.plot(hs * 1000, Cs, color=c, lw=2, label=f"ρ_s = {rs} Ω·m")
    a1.axvline(102, color=RED, ls=":", lw=1.2)
    a1.text(108, .55, "100 mm\ntypical", fontsize=8, color=RED)
    a1.set_xlabel("Surface-layer thickness $h_s$ (mm)")
    a1.set_ylabel("Derating factor $C_s$")
    a1.set_title("(a) $C_s$ saturates — thicker stops helping")
    a1.legend(fontsize=8); a1.set_ylim(0, 1.02)

    ts = np.linspace(0.05, 3.0, 300)
    Et = [ieee80.tolerable_voltages(400, 2500, .102, t, 70)["E_touch"] for t in ts]
    Es = [ieee80.tolerable_voltages(400, 2500, .102, t, 70)["E_step"] for t in ts]
    Et5 = [ieee80.tolerable_voltages(400, 2500, .102, t, 50)["E_touch"] for t in ts]
    a2.plot(ts, Es, color=GRN, lw=2, label="$E_{step}$ (70 kg)")
    a2.plot(ts, Et, color=ACC, lw=2, label="$E_{touch}$ (70 kg)")
    a2.plot(ts, Et5, color=RED, lw=1.6, ls="--", label="$E_{touch}$ (50 kg)")
    a2.axvline(.5, color="#8a949c", ls=":", lw=1)
    a2.set_yscale("log")
    a2.set_xlabel("Shock duration $t_s$ (s)")
    a2.set_ylabel("Tolerable voltage (V)")
    a2.set_title("(b) Everything scales as $1/\\sqrt{t_s}$")
    a2.legend(fontsize=8)
    fig.tight_layout()
    save(fig, "fig07_tolerable")


# =================================================== 8. conductor sizing ---
def fig_conductor():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.6))
    t = np.logspace(-1.3, 0.8, 200)
    for mat, lbl, c in [("cu_hard", "Copper, hard-drawn", ACC),
                        ("al_ec", "Aluminium, EC grade", GRN),
                        ("steel_1020", "Steel 1020", ORG)]:
        A = [conductor.ieee80_conductor_area(10.0, x, mat, 40.0)["area_mm2"] for x in t]
        a1.plot(t, A, color=c, lw=2, label=lbl)
    a1.set_xscale("log"); a1.set_yscale("log")
    a1.set_xlabel("Fault duration $t_c$ (s)")
    a1.set_ylabel("Minimum area (mm²)")
    a1.set_title("(a) Material, for $I$ = 10 kA")
    a1.legend(fontsize=7.8)

    joints = [("Exothermic weld\n1083 °C", 1083.0, GRN),
              ("Brazed\n450 °C", 450.0, ORG),
              ("Bolted\n250 °C", 250.0, RED)]
    names = [j[0] for j in joints]
    vals = [conductor.ieee80_conductor_area(10.0, .5, "cu_hard", 40.0, j[1])["area_mm2"]
            for j in joints]
    bars = a2.bar(names, vals, color=[j[2] for j in joints], width=.55)
    for b, v in zip(bars, vals):
        a2.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f} mm²",
                ha="center", fontsize=9, fontweight="bold")
    a2.set_ylabel("Minimum area (mm²)")
    a2.set_title("(b) The joint decides the copper bill")
    a2.grid(axis="x", alpha=0)
    a2.set_ylim(0, max(vals) * 1.22)
    fig.tight_layout()
    save(fig, "fig08_conductor")


# ==================================================== 9. grid layout ------
def fig_layout():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 4.3))
    for ax, nr, ttl in ((a1, 0, "(a) 70 × 70 m grid, D = 7 m, no rods"),
                        (a2, 20, "(b) the same grid with 20 perimeter rods")):
        g = ieee80.GridGeometry(Lx=70, Ly=70, D=7, h=0.5, d=0.01,
                                n_rods=nr, Lr=7.5 if nr else 0)
        for (p, q) in g.conductor_paths():
            ax.plot([p[0], q[0]], [p[1], q[1]], color=ACC, lw=1.4)
        rods = g.rod_positions()
        if rods:
            ax.plot([r[0] for r in rods], [r[1] for r in rods], "o",
                    color=RED, ms=7, label=f"{len(rods)} ground rods")
            ax.legend(fontsize=8, loc="upper right")
        d = ieee80.design(400, g, 1.908, 2500, .102, .5, 70)
        ax.set_title(ttl)
        ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
        ax.set_aspect("equal"); ax.set_xlim(-8, 78); ax.set_ylim(-8, 78)
        ax.text(35, -6.2, f"$R_g$ = {d['Rg']:.2f} Ω   $E_m$ = {d['mesh']['Em']:.0f} V"
                          f"   ($E_{{touch}}$ = {d['tolerable']['E_touch']:.0f} V)",
                ha="center", fontsize=8.6,
                color=GRN if d["passed"] else RED)
    fig.tight_layout()
    save(fig, "fig09_layout")


# ============================================ 10-12. BEM field solutions --
def fig_bem():
    net = bem.Network(bem.SoilModel(400.0), 1908.0)
    net.add_grid(70, 70, 7, 0.5, 0.005)
    net.discretise(3.0)
    net.solve()
    ws = net.worst_touch_step((-8, 78), (-8, 78), 81, 81)
    sp = ws["surface"]
    X, Y = np.meshgrid(sp["x"], sp["y"])
    V = np.array(sp["V"])
    T = np.array(sp["touch"])

    # --- surface potential ---
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    cf = ax.contourf(X, Y, V, levels=26, cmap="viridis")
    ax.contour(X, Y, V, levels=13, colors="white", linewidths=.4, alpha=.5)
    g = ieee80.GridGeometry(Lx=70, Ly=70, D=7)
    for (p, q) in g.conductor_paths():
        ax.plot([p[0], q[0]], [p[1], q[1]], color="white", lw=.7, alpha=.55)
    fig.colorbar(cf, ax=ax, label="Surface potential (V)", shrink=.88)
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_aspect("equal")
    ax.set_title(f"Earth-surface potential — GPR = {net.V:.0f} V, "
                 f"$R_g$ = {net.V/1908:.2f} Ω")
    ax.grid(alpha=0)
    fig.tight_layout()
    save(fig, "fig10_surface_potential")

    # --- 3D ---
    fig = plt.figure(figsize=(7.4, 5.0))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, V, cmap="viridis", linewidth=0, antialiased=True,
                    rstride=2, cstride=2)
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    ax.set_zlabel("Potential (V)")
    ax.set_title("The potential 'table top': flat inside the grid, "
                 "steep at the edges", pad=1)
    ax.view_init(elev=32, azim=-127)
    ax.grid(alpha=.2)
    fig.tight_layout()
    save(fig, "fig11_potential_3d")

    # --- touch map with the tolerable contour ---
    Et = ieee80.tolerable_voltages(400, 2500, .102, .5, 70)["E_touch"]
    # touch voltage only means something where a person can stand on the soil AND
    # reach earthed metal: the grid footprint plus one metre of arm reach
    reach = (X >= -1) & (X <= 71) & (Y >= -1) & (Y <= 71)
    Tm = np.where(reach, T, np.nan)
    fig, ax = plt.subplots(figsize=(6.8, 5.2))
    ax.add_patch(Rectangle((-8, -8), 86, 86, fc="#eef2f5", ec="none", zorder=0))
    cf = ax.contourf(X, Y, Tm, levels=24, cmap="magma_r", zorder=1)
    cl = ax.contour(X, Y, Tm, levels=[Et], colors=[GRN], linewidths=2.4, zorder=3)
    ax.clabel(cl, fmt={Et: f"tolerable {Et:.0f} V"}, fontsize=8)
    ax.add_patch(Rectangle((-1, -1), 72, 72, fc="none", ec="#5a6773", lw=1.1,
                           ls="--", zorder=4))
    ax.text(35, 74.5, "dashed line = grid footprint + 1 m arm reach",
            ha="center", fontsize=7.8, color="#5a6773")
    for (p, q) in g.conductor_paths():
        ax.plot([p[0], q[0]], [p[1], q[1]], color="white", lw=.6, alpha=.45)
    fig.colorbar(cf, ax=ax, label="Touch voltage GPR − V (V)", shrink=.88)
    ax.plot(*ws["touch_at"], marker="*", color=GRN, ms=18, mec="black", mew=.6,
            zorder=5)
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_aspect("equal")
    ax.set_xlim(-8, 78); ax.set_ylim(-8, 78)
    ax.set_title(f"Touch voltage inside the reachable area — worst point "
                 f"{ws['touch_max']:.0f} V at the corner")
    ax.grid(alpha=0)
    fig.tight_layout()
    save(fig, "fig12_touch_map")

    # --- profile ---
    pr = net.profile([-8, 35], [78, 35], 260)
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    ax.plot(pr["s"], pr["V"], color=ACC, lw=2, label="surface potential")
    ax.plot(pr["s"], pr["touch"], color=RED, lw=2, label="touch voltage")
    ax.plot(pr["s"], pr["step"], color=GRN, lw=2, label="step voltage (1 m)")
    ax.axhline(Et, color=RED, ls=":", lw=1.2, label=f"tolerable touch {Et:.0f} V")
    ax.axvspan(8, 78, color=ACC, alpha=.06)
    ax.text(43, ax.get_ylim()[1] * .93, "inside the grid", ha="center",
            fontsize=8, color="#5a6773")
    ax.set_xlabel("Distance along the traverse (m)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Profile across the grid: touch worst at the edge, "
                 "step worst just outside")
    ax.legend(fontsize=7.8, loc="center right")
    fig.tight_layout()
    save(fig, "fig13_profile")


# ================================================== 13. design levers -----
def fig_sweep():
    g = ieee80.GridGeometry(Lx=70, Ly=70, D=7, h=.5, d=.01)
    opt = ieee80.optimise(400, g, 1.908, 2500, .102, .5, 70, D_min=1.5, D_step=.25)
    sw = opt["sweep"]
    D = [s["D"] for s in sw]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.plot(D, [s["Em"] for s in sw], color=RED, lw=2.2, label="mesh voltage $E_m$")
    ax.plot(D, [s["E_touch"] for s in sw], color=RED, ls=":", lw=1.5,
            label="tolerable touch")
    ax.plot(D, [s["Es"] for s in sw], color=GRN, lw=2.2, label="step voltage $E_s$")
    ax.plot(D, [s["E_step"] for s in sw], color=GRN, ls=":", lw=1.5,
            label="tolerable step")
    if opt["found"]:
        Db = opt["best"]["D"]
        ax.axvline(Db, color=ACC, lw=1.6)
        ax.annotate(f"compliant at\nD = {Db:g} m", xy=(Db, 1600),
                    xytext=(Db + 1.4, 2100), fontsize=8.5, color=ACC,
                    arrowprops=dict(arrowstyle="->", color=ACC))
        ax.axvspan(min(D), Db, color=GRN, alpha=.07)
    ax.set_xlabel("Conductor spacing D (m)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("The main design lever: mesh voltage against conductor spacing")
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, "fig14_sweep")


# ================================================== 14. BEM illustration --
def fig_bem_method():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.7))
    # (a) discretisation
    a1.set_xlim(-1, 11); a1.set_ylim(-4, 3); a1.axis("off")
    a1.add_patch(Rectangle((-1, -4), 12, 4, fc=SOIL, ec="none"))
    a1.plot([-1, 11], [0, 0], color="#a08a6a", lw=1.6)
    xs = np.linspace(1, 9, 9)
    for i, x in enumerate(xs[:-1]):
        a1.plot([x, xs[i + 1]], [-1.2, -1.2], color=ACC, lw=5,
                solid_capstyle="butt")
        a1.plot([xs[i + 1], xs[i + 1]], [-1.35, -1.05], color="white", lw=1.6)
        a1.annotate("", xy=(x + .5, -2.3), xytext=(x + .5, -1.35),
                    arrowprops=dict(arrowstyle="->", color=RED, lw=1.1))
    a1.text(5, -3.0, "each segment leaks $I_j$", ha="center", fontsize=8.5, color=RED)
    a1.text(5, -0.75, "all segments at one potential $V$", ha="center",
            fontsize=8.5, color=ACC)
    a1.text(5, 1.45, "$\\sum_j P_{ij} I_j = V$   and   $\\sum_j I_j = I_G$",
            ha="center", fontsize=10.5, color="#0f2f4f")
    a1.text(5, .35, "one equation per segment, plus current conservation",
            ha="center", fontsize=8, color="#5a6773")
    a1.set_title("(a) Method of moments", pad=0)

    # (b) image method
    a2.set_xlim(-1, 11); a2.set_ylim(-4, 4); a2.axis("off")
    a2.add_patch(Rectangle((-1, -4), 12, 4, fc=SOIL, ec="none"))
    a2.add_patch(Rectangle((-1, 0), 12, 4, fc="#eaf2f7", ec="none"))
    a2.plot([-1, 11], [0, 0], color="#a08a6a", lw=1.8)
    a2.text(10.5, .35, "air", fontsize=8, color="#5a6773", ha="right")
    a2.text(10.5, -.75, "soil", fontsize=8, color="#8a7b5c", ha="right")
    a2.plot(3.5, -1.5, "o", color=ACC, ms=11)
    a2.text(3.5, -2.35, "source\n$+I$ at depth $z'$", ha="center", fontsize=8.4,
            color=ACC)
    a2.plot(3.5, 1.5, "o", color=ACC, ms=11, alpha=.45)
    a2.text(3.5, 2.0, "image $+I$ at $-z'$", ha="center", fontsize=8.4,
            color=ACC, alpha=.8)
    a2.plot([3.5, 3.5], [-1.5, 1.5], color=ACC, ls=":", lw=1.1)
    a2.plot(8.0, -0.9, "^", color=RED, ms=9)
    a2.text(8.0, -1.75, "field point", ha="center", fontsize=8.4, color=RED)
    a2.annotate("", xy=(7.9, -1.0), xytext=(3.65, -1.45),
                arrowprops=dict(arrowstyle="->", color="#5a6773", lw=1))
    a2.annotate("", xy=(7.9, -0.8), xytext=(3.65, 1.45),
                arrowprops=dict(arrowstyle="->", color="#5a6773", lw=1, ls="--"))
    a2.text(5, 3.2, "$G = \\dfrac{\\rho}{4\\pi}\\left[\\dfrac{1}{r}+"
                    "\\dfrac{1}{r'}\\right]$",
            ha="center", fontsize=11, color="#0f2f4f")
    a2.set_title("(b) The image that makes the surface insulating", pad=0)
    fig.tight_layout()
    save(fig, "fig15_bem_method")


# ================================================== 15. TN vs TT ---------
def fig_systems():
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.9))
    for ax, kind in zip(axes, ("TN-S", "TT")):
        ax.set_xlim(0, 10); ax.set_ylim(0, 7); ax.axis("off")
        ax.add_patch(Rectangle((0, 0), 10, 1.5, fc=SOIL, ec="none"))
        ax.plot([0, 10], [1.5, 1.5], color="#a08a6a", lw=1.4)
        # source
        ax.add_patch(FancyBboxPatch((0.5, 4.2), 2.0, 1.7, boxstyle="round,pad=.08",
                                    fc="#eaf2f7", ec=ACC, lw=1.3))
        ax.text(1.5, 5.05, "source\ntransformer", ha="center", fontsize=8)
        # load
        ax.add_patch(FancyBboxPatch((7.0, 4.2), 2.2, 1.7, boxstyle="round,pad=.08",
                                    fc="#f7f2ea", ec=ORG, lw=1.3))
        ax.text(8.1, 5.05, "equipment\n(exposed metal)", ha="center", fontsize=8)
        ax.plot([2.5, 7.0], [5.5, 5.5], color="#1a2027", lw=1.5)
        ax.text(4.7, 5.7, "line", fontsize=8)
        # source earth
        ax.plot([1.5, 1.5], [4.2, 1.5], color=ACC, lw=1.5)
        ax.plot([1.5, 1.5], [1.5, .8], color=ACC, lw=3)
        ax.text(1.5, .45, "source earth", ha="center", fontsize=7.6, color=ACC)
        if kind == "TN-S":
            ax.plot([7.0, 2.5], [4.5, 4.5], color=GRN, lw=2.4)
            ax.text(4.75, 4.72, "PE — metallic return", fontsize=8.4, color=GRN,
                    ha="center")
            ax.annotate("", xy=(3.1, 4.05), xytext=(6.4, 4.05),
                        arrowprops=dict(arrowstyle="->", color=RED, lw=2))
            ax.text(6.6, 4.05, "$I_f$", fontsize=9, color=RED, va="center")
            ax.text(4.9, 2.6, "large fault current\n→ overcurrent device trips\n"
                              "criterion: $Z_s I_a \\leq C_{min}U_0$  (TIME)",
                    ha="center", fontsize=8.6, color=RED)
        else:
            ax.plot([8.1, 8.1], [4.2, 1.5], color=GRN, lw=1.5)
            ax.plot([8.1, 8.1], [1.5, .8], color=GRN, lw=3)
            ax.text(8.1, .45, "$R_A$", ha="center", fontsize=8.6, color=GRN)
            th = np.linspace(0, np.pi, 60)
            ax.plot(4.8 + 3.3 * np.cos(th), 0.95 - 0.42 * np.sin(th),
                    color=RED, lw=1.8, ls="--")
            ax.text(4.9, 2.6, "small fault current through soil\n"
                              "→ RCD needed\n"
                              "criterion: $R_A I_a \\leq 50$ V  (VOLTAGE)",
                    ha="center", fontsize=8.6, color=RED)
        ax.set_title(kind, color="#0f2f4f")
    fig.suptitle("In TN the criterion is on time; in TT it is on voltage",
                 fontsize=9.5, color="#0f2f4f", y=1.03)
    fig.tight_layout()
    save(fig, "fig16_tn_tt")


# ================================================== 16. electrodes -------
def fig_electrodes():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.6))
    L = np.linspace(0.5, 12, 200)
    for rho, c in [(50, GRN), (150, ACC), (500, ORG)]:
        R = [iec60364.rod(rho, x, 0.016)["R"] for x in L]
        a1.plot(L, R, color=c, lw=2, label=f"ρ = {rho} Ω·m")
    a1.set_xlabel("Rod length L (m)")
    a1.set_ylabel("Rod resistance (Ω)")
    a1.set_title("(a) Length beats diameter, every time")
    a1.legend(fontsize=8)

    n = np.arange(1, 11)
    for s, c in [(3.0, RED), (6.0, ACC), (12.0, GRN)]:
        R = [iec60364.rods_parallel(150, 3.0, .016, int(k), s)["R"] for k in n]
        a2.plot(n, R, "o-", color=c, lw=1.9, ms=5, label=f"spacing {s:g} m")
    R1 = iec60364.rod(150, 3.0, .016)["R"]
    a2.plot(n, R1 / n, "k--", lw=1.4, label="ideal R₁/n (never achieved)")
    a2.set_xlabel("Number of rods in parallel")
    a2.set_ylabel("Combined resistance (Ω)")
    a2.set_title("(b) Rods interfere — spacing matters")
    a2.legend(fontsize=7.8)
    fig.tight_layout()
    save(fig, "fig17_electrodes")


# ================================================== 17. IEC 62305 l1 -----
def fig_lps():
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    rho = np.linspace(100, 3000, 200)
    for cls, c in [("I", RED), ("II", ORG), ("III", ACC), ("IV", GRN)]:
        l1 = [iec62305.min_electrode_length(cls, r)["l1"] for r in rho]
        ax.plot(rho, l1, color=c, lw=2.2, label=f"Class {cls}")
    ax.set_xlabel("Soil resistivity ρ (Ω·m)")
    ax.set_ylabel("Minimum electrode length $l_1$ (m)")
    ax.set_title("IEC 62305-3: the geometric requirement, not the resistance")
    ax.legend(fontsize=8.5)
    ax.annotate("classes III and IV: 5 m regardless of soil",
                xy=(2000, 5), xytext=(1100, 22), fontsize=8, color=GRN,
                arrowprops=dict(arrowstyle="->", color=GRN))
    fig.tight_layout()
    save(fig, "fig18_lps_l1")


# ======================================= 19–21. lightning model (1.5–1.6) ----
# The exact two-layer results of Arnautovski-Toseva, Grcev and El Khamlichi
# Drissi (2007), Tables 2-3: |Z| (ohm) of end-fed wires, r = 5 mm, 0.75 m deep.
AT07 = {10: ([1e4, 1e5, 1e6, 1e7],
             [[14.3, 14.6, 28.6, 59.6], [35.1, 34.2, 35.5, 58.1], [8.3, 8.9, 22.9, 57.1],
              [15.6, 16.1, 30.6, 63.8], [10.8, 10.9, 23.0, 55.0]]),
        50: ([1e3, 1e4, 1e5, 1e6],
             [[3.8, 4.4, 12.1, 29.6], [13.9, 14.1, 21.8, 40.2], [1.8, 2.6, 8.3, 22.9],
              [4.1, 4.6, 12.8, 31.9], [2.9, 3.6, 9.8, 23.1]])}
AT07_SOILS = [("uniform 100 Ω·m", [100], []), ("1a: 100 over 1000, d = 1 m", [100, 1000], [1.0]),
              ("1b: 100 over 10, d = 1 m", [100, 10], [1.0]),
              ("2a: 1000 over 100, d = 0.5 m", [1000, 100], [0.5]),
              ("2b: 10 over 100, d = 0.5 m", [10, 100], [0.5])]


def _logfmt(ax):
    from matplotlib.ticker import FuncFormatter, LogLocator
    ax.yaxis.set_major_locator(LogLocator(subs=(1, 2, 3, 5)))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, p: ""))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:g}"))


def fig_layered_hf():
    from earthsys import hf
    fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.9))
    cols = ["#8a949c", ACC, RED, GRN, PUR]
    for ax, L in zip(axs, (10, 50)):
        fr, ref = AT07[L]
        F = np.unique(np.concatenate([np.geomspace(1e3, fr[-1], 22), fr]))
        for k, (lab, rho, h) in enumerate(AT07_SOILS):
            soil_m = hf.make_soil(rho, h, 10.0)
            w = hf.Wires(); w.add((0, 0, 0.75), (L, 0, 0.75), 0.005)
            w.discretise(hf.default_seg_len(soil_m, fr[-1], L), z_cuts=soil_m.depths)
            m = hf.Model(w, soil_m)
            Z = np.abs([m.solve(f, 0)[0] for f in F])
            ax.plot(F, Z, color=cols[k], lw=1.4 if k == 0 else 2.0, ls="--" if k == 0 else "-", label=lab)
            ax.plot(fr, ref[k], "o", color=cols[k], ms=4.5, mfc="white", mew=1.3)
        ax.set_xscale("log"); ax.set_yscale("log"); _logfmt(ax)
        ax.set_xlabel("Frequency (Hz)"); ax.set_ylabel("|Z(jω)| (Ω)")
        ax.set_title(f"({'ab'[L == 50]}) {L} m wire in two-layer soil")
    axs[0].legend(fontsize=6.8, loc="upper left")
    axs[1].text(0.98, 0.03, "lines: Earthing System; circles: exact model (2007)", ha="right",
                transform=axs[1].transAxes, fontsize=7, color="#5a6773")
    fig.tight_layout()
    save(fig, "fig19_layered_hf")


def fig_ionisation():
    from earthsys import hf
    w = hf.Wires(); w.add((0, 0, 0), (0, 0, 10), 0.0125)
    r = hf.harmonic_impedance(wires=w, soil=hf.Soil(100, 10), feed=(0, 0, 0),
                              f_min=100, f_max=1e7, n_f=50)
    fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.6))
    for ax, (wf, ttl, tmax) in zip(axs, (("first_heidler", "(a) First stroke, 30 kA", 15),
                                         ("subsequent_heidler", "(b) Subsequent stroke, 12 kA", 5))):
        tr = hf.time_response(r["f"], r["Z"], r["R"], wf, ionisation=dict(E0=300, rho=100))
        k = tr["t_us"] <= tmax
        t = tr["t_us"][k]
        ax.plot(t, tr["v_kV"][k], color=ACC, lw=2, label=f"no ionisation: Z_p = {tr['Z_impulse']:.1f} Ω")
        ax.plot(t, tr["v_ion_kV"][k], color=RED, lw=2, label=f"E₀ = 300 kV/m: Z_p = {tr['Z_impulse_ion']:.1f} Ω")
        b = ax.twinx(); b.grid(False)
        b.plot(t, tr["i_kA"][k], color=GRN, lw=1.1, ls=":", label="i(t) (kA)")
        b.plot(t, tr["R_t"][k], color="#8a949c", lw=1.1, ls="--", label="R(t) (Ω)")
        b.set_ylabel("Current (kA), R(t) (Ω)")
        ax.set_xlabel("Time (µs)"); ax.set_ylabel("Potential rise (kV)"); ax.set_title(ttl)
        h1, l1 = ax.get_legend_handles_labels(); h2, l2 = b.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, fontsize=6.8, loc="lower right")
    fig.tight_layout()
    save(fig, "fig20_ionisation")


def fig_foundation():
    from earthsys import hf
    from matplotlib.ticker import FuncFormatter
    L, r0, r1 = 3.048, 0.009525, 0.2032
    fagan = {30: {5: 5.46, 20: 7.89, 50: 12.75, 100: 20.85, 500: 85.7},
             50: {5: 8.56, 20: 11.0, 50: 15.85, 100: 23.95, 500: 88.75},
             80: {5: 13.21, 20: 15.64, 50: 20.50, 100: 28.6, 500: 93.4}}
    rs = np.geomspace(5, 500, 13)

    def R(items, rho):
        net = bem.build_network(dict(rho1=rho, IG=1.0, items=items)); net.discretise(0.5)
        return net.solve()["Rg"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.6, 3.9))
    rod = [dict(kind="rod", x=0, y=0, top_depth=0, length=L, radius=r0)]
    a.plot(rs, [R(rod, x) for x in rs], color="#5a6773", lw=1.6, ls="--", label="bare rod")
    for c, rc in zip((ACC, RED, GRN), (30, 50, 80)):
        it = [dict(kind="foundation", shape="pier", x=0, y=0, top_depth=0, length=L,
                   diameter=2 * r1, bars=1, bar_diameter=2 * r0, rho_c=rc)]
        a.plot(rs, [R(it, x) for x in rs], color=c, lw=2, label=f"in concrete, ρ_c = {rc} Ω·m")
        a.plot(list(fagan[rc]), list(fagan[rc].values()), "o", color=c, ms=4.5, mfc="white", mew=1.3)
    a.set_xscale("log"); a.set_yscale("log")
    for ax_ in (a.xaxis, a.yaxis):
        ax_.set_major_formatter(FuncFormatter(lambda v, p: f"{v:g}"))
    a.set_xlabel("Soil resistivity ρ (Ω·m)"); a.set_ylabel("Resistance (Ω)")
    a.set_title("(a) 3.05 m rod, bare and in 0.41 m of concrete")
    a.legend(fontsize=7, loc="upper left")
    a.text(0.98, 0.03, "markers: Fagan & Lee (1970) Table VII", ha="right", transform=a.transAxes,
           fontsize=7, color="#5a6773")
    pier = dict(kind="foundation", shape="pier", x=0, y=0, top_depth=0, length=3.0, diameter=0.4,
                bars=6, bar_diameter=0.016, cover=0.05, rho_c=50, eps_c=10)
    rod3 = dict(kind="rod", x=0, y=0, top_depth=0, length=3.0, radius=0.008)
    for c, rho in ((ACC, 100), (RED, 1000)):
        for it, ls, lab in ((pier, "-", "pier"), (rod3, "--", "bare rod")):
            r = hf.harmonic_impedance(items=[it], soil=hf.Soil(rho, 10), feed=(0, 0, 0),
                                      f_min=100, f_max=1e7, n_f=36)
            b.plot(r["f"], np.abs(r["Z"]), color=c, ls=ls, lw=2, label=f"{lab}, {rho} Ω·m")
    b.set_xscale("log"); b.set_yscale("log"); _logfmt(b)
    b.set_xlabel("Frequency (Hz)"); b.set_ylabel("|Z(jω)| (Ω)")
    b.set_title("(b) 3 m concrete pier and 3 m bare rod")
    b.legend(fontsize=7, loc="lower left", ncol=2)
    fig.tight_layout()
    save(fig, "fig21_foundation")


if __name__ == "__main__":
    print("Generating figures into", OUT)
    only = set(sys.argv[1:])
    for fn in (fig_halfspace, fig_body, fig_wenner, fig_twolayer, fig_inversion,
               fig_decrement, fig_tolerable, fig_conductor, fig_layout, fig_bem,
               fig_sweep, fig_bem_method, fig_systems, fig_electrodes, fig_lps,
               fig_layered_hf, fig_ionisation, fig_foundation):
        if not only or fn.__name__ in only:
            fn()
    print("done")
