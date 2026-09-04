"""
Bilingual (English / Persian) design-report generator.

Produces a self-contained HTML document — printable to PDF from any browser —
containing the inputs, the intermediate quantities, every formula that was
applied with its standard reference, the compliance verdicts, and any charts
supplied by the user interface as PNG data URIs.
"""

from __future__ import annotations

import html
import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

T = {
    "en": {
        "dir": "ltr", "lang": "en",
        "title": "Earthing System Design Report",
        "project": "Project", "client": "Client", "engineer": "Engineer",
        "date": "Date", "reference": "Document reference", "revision": "Revision",
        "contents": "Contents",
        "soil": "Soil investigation and model",
        "fault": "Earth-fault current",
        "conductor": "Earthing conductor sizing",
        "grid": "Earth grid design (IEEE Std 80)",
        "numerical": "Numerical analysis (boundary-element solver)",
        "building": "LV installation earthing (IEC 60364)",
        "lightning": "Lightning protection earth termination (IEC 62305)",
        "sysgnd": "System neutral grounding (IEEE Std 142)",
        "checks": "Compliance summary",
        "figures": "Figures", "figure": "Figure",
        "parameter": "Parameter", "symbol": "Symbol", "value": "Value",
        "unit": "Unit", "source": "Basis / reference",
        "criterion": "Criterion", "limit": "Limit", "result": "Result",
        "pass": "PASS", "fail": "FAIL", "margin": "Margin",
        "notes": "Notes and assumptions",
        "disclaimer": "This report was produced by EarthSystem. All results "
                      "must be reviewed and approved by a competent engineer "
                      "before construction. Field verification of the soil "
                      "model and of the installed earthing resistance is "
                      "required.",
        "generated": "Generated",
        "summary": "Executive summary",
        "no_data": "Not evaluated in this run.",
        "assessment": "Assessment",
        "why_pass": "Why it passes", "why_fail": "Why it fails",
        "driver": "What drives the number",
        "means": "What the criterion means",
        "margin_txt": "Margin", "howfix": "How to fix it",
        "complies": "COMPLIES", "notcomplies": "DOES NOT COMPLY",
        "crosscheck": "Independent cross-check",
    },
    "fa": {
        "dir": "rtl", "lang": "fa",
        "title": "گزارش طراحی سیستم زمین (ارت)",
        "project": "پروژه", "client": "کارفرما", "engineer": "مهندس طراح",
        "date": "تاریخ", "reference": "شماره مدرک", "revision": "بازنگری",
        "contents": "فهرست مطالب",
        "soil": "مطالعات و مدل مقاومت ویژه خاک",
        "fault": "جریان خطای اتصال به زمین",
        "conductor": "انتخاب سطح مقطع هادی زمین",
        "grid": "طراحی شبکه زمین پست (استاندارد IEEE 80)",
        "numerical": "تحلیل عددی (روش المان مرزی)",
        "building": "زمین کردن تأسیسات فشار ضعیف (IEC 60364)",
        "lightning": "سیستم زمین صاعقه‌گیر (IEC 62305)",
        "sysgnd": "زمین کردن نقطه خنثی سیستم (IEEE 142)",
        "checks": "جمع‌بندی انطباق با استاندارد",
        "figures": "نمودارها", "figure": "نمودار",
        "parameter": "پارامتر", "symbol": "نماد", "value": "مقدار",
        "unit": "واحد", "source": "مبنا / مرجع",
        "criterion": "معیار", "limit": "حد مجاز", "result": "نتیجه",
        "pass": "قبول", "fail": "مردود", "margin": "حاشیه اطمینان",
        "notes": "یادداشت‌ها و مفروضات",
        "disclaimer": "این گزارش توسط نرم‌افزار EarthSystem تولید شده است. "
                      "کلیه نتایج باید پیش از اجرا توسط مهندس ذی‌صلاح بررسی و "
                      "تأیید شود. صحت‌سنجی میدانی مدل خاک و اندازه‌گیری مقاومت "
                      "زمین اجرا شده الزامی است.",
        "generated": "تاریخ تولید",
        "summary": "خلاصه مدیریتی",
        "no_data": "در این اجرا محاسبه نشده است.",
        "assessment": "ارزیابی و دلیل نتیجه",
        "why_pass": "دلیل قبول شدن", "why_fail": "دلیل مردود شدن",
        "driver": "عامل تعیین‌کننده مقدار",
        "means": "مفهوم فیزیکی معیار",
        "margin_txt": "حاشیه اطمینان", "howfix": "راه‌های اصلاح",
        "complies": "منطبق با استاندارد", "notcomplies": "عدم انطباق",
        "crosscheck": "صحت‌سنجی مستقل",
    },
}

# Persian labels for the quantity names used in the tables
LABELS_FA = {
    "Air-termination mesh size": "ابعاد شبکه صاعقه‌گیر روی بام",
    "Ambient temperature": "دمای محیط",
    "Burial depth": "عمق دفن",
    "Conductor diameter": "قطر هادی",
    "Conductor spacing": "فاصله هادی‌های شبکه",
    "Continuous / short-time rating": "توان نامی پیوسته / کوتاه‌مدت",
    "Decrement factor": "ضریب کاهش (مؤلفه DC)",
    "Design current": "جریان طراحی",
    "Discretised segments": "تعداد المان‌های گسسته‌سازی",
    "Down-conductor spacing": "فاصله هادی‌های نزولی",
    "Duration": "مدت زمان خطا",
    "Earth resistance": "مقاومت زمین",
    "Earth-fault current": "جریان خطای زمین",
    "Earth-fault loop impedance": "امپدانس حلقه خطای زمین",
    "Earth-termination arrangement": "آرایش سیستم زمین صاعقه",
    "Earthing resistance": "مقاومت سیستم زمین",
    "Effective mesh length": "طول مؤثر برای ولتاژ تماس",
    "Effective step length": "طول مؤثر برای ولتاژ گام",
    "Electrode resistance": "مقاومت الکترود زمین",
    "Equivalent diameter": "قطر معادل",
    "Equivalent uniform resistivity": "مقاومت ویژه یکنواخت معادل",
    "Fault duration (shock)": "مدت خطا (معیار شوک)",
    "Fault duration (thermal)": "مدت خطا (معیار حرارتی)",
    "Future-growth factor": "ضریب توسعه آتی",
    "Geometric factor": "ضریب هندسی",
    "Grid area": "مساحت شبکه زمین",
    "Grid dimensions": "ابعاد شبکه زمین",
    "Grid resistance": "مقاومت شبکه زمین",
    "Ground potential rise": "افزایش پتانسیل زمین (GPR)",
    "Horizontal conductor length": "طول هادی افقی",
    "Injected current": "جریان تزریقی",
    "Irregularity factor": "ضریب نامنظمی",
    "LPS class": "سطح حفاظت صاعقه",
    "Line-to-earth fault current": "جریان خطای فاز به زمین",
    "Lower-layer resistivity": "مقاومت ویژه لایه پایین",
    "Material": "جنس هادی",
    "Maximum disconnection time": "حداکثر زمان قطع مجاز",
    "Maximum grid current": "حداکثر جریان شبکه زمین",
    "Maximum step voltage": "حداکثر ولتاژ گام",
    "Maximum temperature": "حداکثر دمای مجاز",
    "Maximum touch voltage": "حداکثر ولتاژ تماس",
    "Mesh (touch) voltage": "ولتاژ چشمه (تماس)",
    "Mesh factor": "ضریب چشمه",
    "Minimum cross-section": "حداقل سطح مقطع",
    "Minimum electrode length": "حداقل طول الکترود",
    "Neutral resistor": "مقاومت نقطه خنثی",
    "Nominal system voltage": "ولتاژ نامی شبکه",
    "Nominal voltage to earth": "ولتاژ نامی نسبت به زمین",
    "Number of down-conductors": "تعداد هادی‌های نزولی",
    "Number of rods": "تعداد میله‌های زمین",
    "Operating current of the device": "جریان عملکرد وسیله حفاظتی",
    "RMS fit error": "خطای برازش (RMS)",
    "Recommended method": "روش پیشنهادی",
    "Reflection factor": "ضریب بازتاب",
    "Rod length": "طول میله زمین",
    "Rolling-sphere radius": "شعاع کره غلتان",
    "Selected RCD rating": "جریان نامی کلید جریان باقیمانده",
    "Selected standard size": "سطح مقطع استاندارد انتخابی",
    "Separation distance": "فاصله جدایش",
    "Soil model": "مدل خاک",
    "Soil resistivity": "مقاومت ویژه خاک",
    "Split factor": "ضریب تقسیم جریان",
    "Step factor": "ضریب گام",
    "Step voltage": "ولتاژ گام",
    "Surface derating factor": "ضریب کاهش لایه سطحی",
    "Symmetrical grid current": "جریان متقارن شبکه زمین",
    "System charging current": "جریان خازنی شبکه",
    "System earthing arrangement": "نوع سیستم زمین",
    "Test array": "آرایش اندازه‌گیری",
    "Tolerable step voltage": "ولتاژ گام مجاز",
    "Tolerable touch voltage": "ولتاژ تماس مجاز",
    "Total buried length": "طول کل هادی دفن‌شده",
    "Total electrode length": "طول کل الکترود",
    "Upper-layer resistivity": "مقاومت ویژه لایه بالا",
    "Upper-layer thickness": "ضخامت لایه بالا",
    # compliance criteria
    "GPR vs tolerable touch voltage": "مقایسه GPR با ولتاژ تماس مجاز",
    "Mesh (touch) voltage E_m": "ولتاژ چشمه (تماس) E_m",
    "Step voltage E_s": "ولتاژ گام E_s",
    "Maximum touch voltage": "حداکثر ولتاژ تماس",
    "Maximum step voltage": "حداکثر ولتاژ گام",
    "Earth-fault loop impedance Z_s": "امپدانس حلقه خطا Z_s",
    "TT electrode: R_A × I_a \u2264 50 V": "الکترود TT: R_A × I_a ≤ 50 V",
    "RCD selection": "انتخاب کلید جریان باقیمانده",
    "Earth-termination geometry": "هندسه سیستم زمین صاعقه",
    "Number of down-conductors": "تعداد هادی‌های نزولی",
    "Earthing resistance \u2264 10 \u03a9 (recommended)":
        "مقاومت زمین ≤ ۱۰ اهم (توصیه‌شده)",
}
T["fa"]["L"] = LABELS_FA
T["en"]["L"] = {}

CSS = """
@page { size: A4; margin: 18mm 15mm; }
* { box-sizing: border-box; }
body { font-family: %(font)s; font-size: 10.5pt; line-height: 1.55;
       color: #1a1d21; margin: 0; padding: 24px; background: #fff; }
h1 { font-size: 20pt; margin: 0 0 4px; color: #0f2f4f; }
h2 { font-size: 13.5pt; margin: 26px 0 8px; padding-bottom: 5px;
     border-bottom: 2px solid #0f6b8a; color: #0f2f4f; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 16px 0 6px; color: #14526b; }
.sub { color: #5b6570; font-size: 9.5pt; margin-bottom: 18px; }
table { width: 100%%; border-collapse: collapse; margin: 8px 0 14px;
        font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #ccd4da; padding: 5px 8px; text-align: %(align)s;
         vertical-align: top; }
th { background: #eef4f7; font-weight: 600; color: #0f2f4f; }
tr:nth-child(even) td { background: #fafcfd; }
td.num { text-align: %(numalign)s; font-variant-numeric: tabular-nums;
         direction: ltr; unicode-bidi: isolate; }
.meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px 18px;
        background: #f5f8fa; border: 1px solid #dde5ea; padding: 12px;
        border-radius: 6px; margin-bottom: 18px; font-size: 9.5pt; }
.meta b { color: #0f2f4f; }
bdi { unicode-bidi: isolate; }
td bdi { display: inline-block; }

.pass { color: #0b6b3a; font-weight: 700; }
.fail { color: #b3261e; font-weight: 700; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 10px;
         font-size: 9pt; font-weight: 700; }
.badge.pass { background: #e2f5ea; color: #0b6b3a; }
.badge.fail { background: #fdeceb; color: #b3261e; }
.formula { font-family: "Cambria Math", "Latin Modern Math", Georgia, serif;
           background: #f7f9fb; border-inline-start: 3px solid #0f6b8a;
           padding: 6px 10px; margin: 6px 0 12px; font-size: 10pt;
           direction: ltr; text-align: left; }
.verdict { border-radius: 6px; padding: 9px 12px; margin: 10px 0;
            border: 1px solid; font-size: 9.5pt; page-break-inside: avoid; }
.verdict.vok  { background: #eef8f2; border-color: #b6dfc8; }
.verdict.vbad { background: #fdf0ee; border-color: #f0c3bd; }
.verdict p { margin: 6px 0 0; line-height: 1.6; }
table.checks tr.whyrow td { background: #fbfcfd; border-top: none; }
.why { font-size: 9pt; line-height: 1.6; color: #3d4650; padding: 2px 4px; }
.why p { margin: 5px 0; }
.why .mean { border-inline-start: 2px solid #ccd4da; padding-inline-start: 8px; }
.why ol { margin: 4px 0 0; padding-inline-start: 18px; }
.why li { margin: 3px 0; }
.note { background: #fffaf0; border: 1px solid #f0e0bd; padding: 9px 12px;
        border-radius: 5px; font-size: 9.5pt; margin: 10px 0; }
.fig { margin: 14px 0; page-break-inside: avoid; text-align: center; }
.fig img { max-width: 100%%; border: 1px solid #dde5ea; border-radius: 4px; }
.fig .cap { font-size: 9pt; color: #5b6570; margin-top: 5px; }
footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid #dde5ea;
         font-size: 8.5pt; color: #6b7580; }
ol.toc { font-size: 10pt; }
.kpi { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
       margin: 10px 0 18px; }
.kpi div { border: 1px solid #dde5ea; border-radius: 6px; padding: 10px;
           background: #f9fbfc; }
.kpi .v { font-size: 15pt; font-weight: 700; color: #0f2f4f;
          direction: ltr; unicode-bidi: isolate; text-align: %(align)s; }
.kpi .l { font-size: 8.5pt; color: #5b6570; }
@media print { body { padding: 0; } .fig { page-break-inside: avoid; } }
"""


def _fmt(v, nd=3):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "✔" if v else "✘"
    if isinstance(v, (int,)):
        return f"{v:,}"
    if isinstance(v, float):
        if not math.isfinite(v):
            return "—"
        if v == 0:
            return "0"
        a = abs(v)
        if a >= 1e5 or a < 1e-3:
            return f"{v:.3e}"
        if a >= 100:
            return f"{v:,.1f}"
        if a >= 10:
            return f"{v:,.2f}"
        return f"{v:,.{nd}f}"
    return html.escape(str(v))


def _row(t, label, symbol, value, unit="", source=""):
    lab = t.get("L", {}).get(label, label)
    return (f"<tr><td>{html.escape(str(lab))}</td>"
            f"<td>{symbol}</td>"
            f"<td class='num'>{_fmt(value)}</td>"
            f"<td><bdi>{html.escape(str(unit))}</bdi></td>"
            f"<td><bdi>{source}</bdi></td></tr>")


def _table(t, rows):
    if not rows:
        return ""
    head = (f"<tr><th>{t['parameter']}</th><th>{t['symbol']}</th>"
            f"<th>{t['value']}</th><th>{t['unit']}</th><th>{t['source']}</th></tr>")
    return f"<table>{head}{''.join(rows)}</table>"


def _checks_table(t, checks, narrative="", cross_check=""):
    out = []
    if narrative:
        ok = all(c.get("passed", True) for c in (checks or []))
        out.append(
            f"<div class='verdict {'vok' if ok else 'vbad'}'>"
            f"<b>{t['complies'] if ok else t['notcomplies']}</b>"
            f"<p><bdi>{html.escape(str(narrative))}</bdi></p></div>")
    if not checks:
        return "".join(out)

    rows = [f"<tr><th>{t['criterion']}</th><th>{t['value']}</th>"
            f"<th>{t['limit']}</th><th>{t['result']}</th></tr>"]
    for c in checks:
        ok = c.get("passed", True)
        badge = (f"<span class='badge {'pass' if ok else 'fail'}'>"
                 f"{t['pass'] if ok else t['fail']}</span>")
        unit = c.get("unit", "")
        cname = t.get("L", {}).get(c.get("name", ""), c.get("name", ""))
        rows.append(
            f"<tr><td>{html.escape(str(cname))}</td>"
            f"<td class='num'>{_fmt(c.get('value'))} {html.escape(unit)}</td>"
            f"<td class='num'>{_fmt(c.get('limit'))} {html.escape(unit)}</td>"
            f"<td>{badge}</td></tr>")
        why = _why_block(t, c, ok)
        if why:
            rows.append(f"<tr class='whyrow'><td colspan='4'>{why}</td></tr>")
    out.append(f"<table class='checks'>{''.join(rows)}</table>")
    if cross_check:
        out.append(f"<div class='note'><b>{t['crosscheck']}.</b> "
                   f"<bdi>{html.escape(str(cross_check))}</bdi></div>")
    return "".join(out)


def _why_block(t, c, ok):
    """The reasoning that accompanies one verdict."""
    parts = []
    if c.get("verdict"):
        parts.append(f"<p><b>{t['why_pass'] if ok else t['why_fail']}:</b> "
                     f"<bdi>{html.escape(str(c['verdict']))}</bdi></p>")
    if c.get("driver"):
        parts.append(f"<p><b>{t['driver']}:</b> "
                     f"<bdi>{html.escape(str(c['driver']))}</bdi></p>")
    if c.get("meaning"):
        parts.append(f"<p class='mean'><b>{t['means']}:</b> "
                     f"<bdi>{html.escape(str(c['meaning']))}</bdi></p>")
    if c.get("headroom"):
        parts.append(f"<p><b>{t['margin_txt']}:</b> "
                     f"<bdi>{html.escape(str(c['headroom']))}</bdi></p>")
    if c.get("remedy"):
        items = "".join(f"<li><bdi>{html.escape(str(r))}</bdi></li>"
                        for r in c["remedy"])
        parts.append(f"<div><b>{t['howfix']}:</b><ol>{items}</ol></div>")
    return f"<div class='why'>{''.join(parts)}</div>" if parts else ""


def _figures(t, figures):
    if not figures:
        return ""
    out = [f"<h2>{t['figures']}</h2>"]
    for i, f in enumerate(figures, 1):
        src = f.get("data", "")
        cap = html.escape(str(f.get("caption", "")))
        out.append(f"<div class='fig'><img src='{src}' alt='figure {i}'>"
                   f"<div class='cap'><bdi>{t['figure']} {i} — {cap}</bdi></div></div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _sec_soil(t, d):
    if not d:
        return ""
    rows = []
    if d.get("rho1") is not None:
        rows += [
            _row(t, "Upper-layer resistivity", "ρ₁", d.get("rho1"), "Ω·m",
                 "Two-layer inversion of the field traverse"),
            _row(t, "Lower-layer resistivity", "ρ₂", d.get("rho2"), "Ω·m", ""),
            _row(t, "Upper-layer thickness", "h", d.get("h"), "m", ""),
            _row(t, "Reflection factor", "K", d.get("K"), "-",
                 "K = (ρ₂ − ρ₁)/(ρ₂ + ρ₁)"),
            _row(t, "RMS fit error", "ε", d.get("rms_pct"), "%", ""),
        ]
    if d.get("rho_equivalent") is not None:
        rows.append(_row(t, "Equivalent uniform resistivity", "ρ", d.get("rho_equivalent"),
                         "Ω·m", "IEEE Std 80-2013 §13.4"))
    if d.get("array"):
        rows.append(_row(t, "Test array", "-", d["array"].title(), "",
                         "IEEE Std 81-2012 §8"))
    body = _table(t, rows)
    if d.get("measured"):
        mrows = ["<tr><th>a (m)</th><th>ρₐ measured (Ω·m)</th>"
                 "<th>ρₐ fitted (Ω·m)</th><th>Δ (%)</th></tr>"]
        for i, a in enumerate(d.get("spacings", [])):
            mrows.append(f"<tr><td class='num'>{_fmt(a)}</td>"
                         f"<td class='num'>{_fmt(d['measured'][i])}</td>"
                         f"<td class='num'>{_fmt(d['fitted'][i])}</td>"
                         f"<td class='num'>{_fmt(d['residual_pct'][i])}</td></tr>")
        body += f"<table>{''.join(mrows)}</table>"
    return f"<h2>{t['soil']}</h2>{body}"


def _sec_fault(t, d):
    if not d:
        return ""
    rows = [
        _row(t, "Nominal system voltage", "Uₙ", d.get("Un_kV"), "kV", ""),
        _row(t, "Line-to-earth fault current", "3I₀", d.get("three_I0_kA"), "kA",
             "IEC 60909-0 Eq. (52)"),
        _row(t, "Split factor", "S_f", d.get("Sf"), "-",
             "IEEE Std 80-2013 Annex C"),
        _row(t, "Decrement factor", "D_f", d.get("Df"), "-",
             "IEEE Std 80-2013 Eq. (79)"),
        _row(t, "Future-growth factor", "C_p", d.get("Cp"), "-", ""),
        _row(t, "Symmetrical grid current", "I_g", d.get("Ig_kA"), "kA", ""),
        _row(t, "Maximum grid current", "I_G", d.get("IG_kA"), "kA",
             "IEEE Std 80-2013 Eq. (78)"),
        _row(t, "Fault duration (shock)", "t_s", d.get("ts"), "s", ""),
        _row(t, "Fault duration (thermal)", "t_c", d.get("tc"), "s", ""),
    ]
    return (f"<h2>{t['fault']}</h2>{_table(t, rows)}"
            "<div class='formula'>I_G = D_f · S_f · C_p · 3I₀</div>")


def _sec_conductor(t, d):
    if not d:
        return ""
    rows = [
        _row(t, "Material", "-", d.get("material"), "", "IEEE Std 80-2013 Table 1"),
        _row(t, "Design current", "I", d.get("I_kA"), "kA", ""),
        _row(t, "Duration", "t_c", d.get("tc"), "s", ""),
        _row(t, "Ambient temperature", "T_a", d.get("Ta"), "°C", ""),
        _row(t, "Maximum temperature", "T_m", d.get("Tm"), "°C", ""),
        _row(t, "Minimum cross-section", "A", d.get("area_mm2"), "mm²",
             "IEEE Std 80-2013 Eq. (37)"),
        _row(t, "Selected standard size", "A_std", d.get("standard_mm2"), "mm²", ""),
        _row(t, "Equivalent diameter", "d", d.get("diameter_mm"), "mm", ""),
    ]
    f = ("<div class='formula'>A = I / √( (TCAP·10⁻⁴)/(t_c·α_r·ρ_r) · "
         "ln[(K₀+T_m)/(K₀+T_a)] )</div>")
    return f"<h2>{t['conductor']}</h2>{_table(t, rows)}{f}"


def _sec_grid(t, d):
    if not d:
        return ""
    g, m, tol = d.get("geometry", {}), d.get("mesh", {}), d.get("tolerable", {})
    rows = [
        _row(t, "Grid dimensions", "L_x × L_y",
             f"{_fmt(g.get('Lx'))} × {_fmt(g.get('Ly'))}", "m", ""),
        _row(t, "Grid area", "A", g.get("A"), "m²", ""),
        _row(t, "Conductor spacing", "D", g.get("D"), "m", ""),
        _row(t, "Burial depth", "h", g.get("h"), "m", ""),
        _row(t, "Conductor diameter", "d", g.get("d"), "m", ""),
        _row(t, "Horizontal conductor length", "L_C", g.get("Lc"), "m", ""),
        _row(t, "Number of rods", "n_R", g.get("n_rods"), "-", ""),
        _row(t, "Rod length", "L_r", g.get("Lr"), "m", ""),
        _row(t, "Total buried length", "L_T", g.get("LT"), "m", ""),
        _row(t, "Grid resistance", "R_g", d.get("Rg"), "Ω",
             d.get("resistance", {}).get("chosen", "")),
        _row(t, "Ground potential rise", "GPR", d.get("GPR"), "V", "GPR = I_G · R_g"),
        _row(t, "Geometric factor", "n", m.get("n"), "-", "Eq. (85)–(88)"),
        _row(t, "Mesh factor", "K_m", m.get("Km"), "-", "Eq. (81)"),
        _row(t, "Irregularity factor", "K_i", m.get("Ki"), "-", "Eq. (89)"),
        _row(t, "Step factor", "K_s", m.get("Ks"), "-", "Eq. (94)"),
        _row(t, "Effective mesh length", "L_M", m.get("LM"), "m", "Eq. (90)/(91)"),
        _row(t, "Effective step length", "L_S", m.get("LS"), "m", "Eq. (93)"),
        _row(t, "Mesh (touch) voltage", "E_m", m.get("Em"), "V", "Eq. (85)"),
        _row(t, "Step voltage", "E_s", m.get("Es"), "V", "Eq. (92)"),
        _row(t, "Surface derating factor", "C_s", tol.get("Cs"), "-", "Eq. (27)"),
        _row(t, "Tolerable touch voltage", "E_touch", tol.get("E_touch"), "V",
             f"{tol.get('body_weight', 70)} kg body, Eq. (31)/(33)"),
        _row(t, "Tolerable step voltage", "E_step", tol.get("E_step"), "V",
             "Eq. (30)/(32)"),
    ]
    f = ("<div class='formula'>R_g = ρ [ 1/L_T + 1/√(20A) ( 1 + 1/(1 + h√(20/A)) ) ]"
         "<br>E_m = ρ·K_m·K_i·I_G / L_M &nbsp;&nbsp; E_s = ρ·K_s·K_i·I_G / L_S</div>")
    return (f"<h2>{t['grid']}</h2>{_table(t, rows)}{f}"
            f"{_checks_table(t, d.get('checks', []), d.get('narrative'))}")


def _sec_bem(t, d):
    if not d:
        return ""
    rows = [
        _row(t, "Soil model", "-", d.get("soil"), "", "Boundary-element solver"),
        _row(t, "Discretised segments", "N", d.get("segments"), "-", ""),
        _row(t, "Total electrode length", "L", d.get("total_length"), "m", ""),
        _row(t, "Injected current", "I_G", d.get("IG"), "A", ""),
        _row(t, "Earth resistance", "R_g", d.get("Rg"), "Ω",
             "R_g = GPR / I_G from the method-of-moments solution"),
        _row(t, "Ground potential rise", "GPR", d.get("GPR"), "V", ""),
        _row(t, "Maximum touch voltage", "U_T,max", d.get("touch_max"), "V",
             "GPR − V_surface over the scanned area"),
        _row(t, "Maximum step voltage", "U_S,max", d.get("step_max"), "V",
             "1 m potential difference at the soil surface"),
    ]
    return (f"<h2>{t['numerical']}</h2>{_table(t, rows)}"
            f"{_checks_table(t, d.get('checks', []), d.get('narrative'), d.get('cross_check'))}")


def _sec_building(t, d):
    if not d:
        return ""
    rows = [
        _row(t, "System earthing arrangement", "-", d.get("system"), "",
             "IEC 60364-1 §312.2"),
        _row(t, "Nominal voltage to earth", "U₀", d.get("U0"), "V", ""),
        _row(t, "Soil resistivity", "ρ", d.get("rho"), "Ω·m", ""),
        _row(t, "Electrode resistance", "R_A", d.get("RA"), "Ω", ""),
        _row(t, "Earth-fault loop impedance", "Z_s", d.get("Zs"), "Ω", ""),
        _row(t, "Maximum disconnection time", "t", (d.get("disconnection") or {}).get("t"),
             "s", "IEC 60364-4-41 Table 41.1"),
        _row(t, "Operating current of the device", "I_a",
             (d.get("device") or {}).get("Ia"), "A",
             (d.get("device") or {}).get("basis", "")),
    ]
    rcd = d.get("rcd") or {}
    if rcd.get("selected_mA"):
        rows.append(_row(t, "Selected RCD rating", "IΔn", rcd.get("selected_mA"),
                         "mA", "R_A · IΔn ≤ 50 V"))
    erows = ["<tr><th>Electrode</th><th>R (Ω)</th><th>Basis</th></tr>"]
    for e in d.get("electrodes", []):
        erows.append(f"<tr><td>{html.escape(str(e.get('type', '')))}</td>"
                     f"<td class='num'>{_fmt(e.get('R'))}</td>"
                     f"<td><bdi>{html.escape(str(e.get('formula', '')))}</bdi></td></tr>")
    etab = f"<table>{''.join(erows)}</table>" if len(erows) > 1 else ""
    return (f"<h2>{t['building']}</h2>{_table(t, rows)}{etab}"
            f"{_checks_table(t, d.get('checks', []), d.get('narrative'))}")


def _sec_lightning(t, d):
    if not d:
        return ""
    e = d.get("earth", {})
    dc = d.get("down_conductors", {})
    rows = [
        _row(t, "LPS class", "-", d.get("lps_class"), "", "IEC 62305-3 Table 1"),
        _row(t, "Soil resistivity", "ρ", d.get("rho"), "Ω·m", ""),
        _row(t, "Minimum electrode length", "l₁",
             (e.get("l1") if isinstance(e.get("l1"), (int, float))
              else (e.get("l1") or {}).get("l1")), "m", "IEC 62305-3 Figure 3"),
        _row(t, "Earth-termination arrangement", "-", e.get("arrangement"), "", ""),
        _row(t, "Earthing resistance", "R_E", e.get("R_total"), "Ω", ""),
        _row(t, "Number of down-conductors", "n", dc.get("n_down"), "-",
             "IEC 62305-3 Table 4"),
        _row(t, "Down-conductor spacing", "-", dc.get("actual_spacing"), "m", ""),
        _row(t, "Air-termination mesh size", "-", dc.get("mesh_size"), "", ""),
        _row(t, "Rolling-sphere radius", "r", dc.get("rolling_sphere"), "m", ""),
        _row(t, "Separation distance", "s", (d.get("separation") or {}).get("s"), "m",
             "s = k_i·k_c·l/k_m"),
    ]
    return (f"<h2>{t['lightning']}</h2>{_table(t, rows)}"
            f"{_checks_table(t, d.get('checks', []), d.get('narrative'))}")


def _sec_sysgnd(t, d):
    if not d:
        return ""
    rows = [
        _row(t, "Recommended method", "-",
             (d.get("data") or {}).get("name", d.get("method")), "",
             "IEEE Std 142"),
        _row(t, "System charging current", "3I_C0", d.get("three_IC0"), "A", ""),
        _row(t, "Neutral resistor", "R_N", d.get("R_ohm"), "Ω", ""),
        _row(t, "Earth-fault current", "I_f", d.get("I_R", d.get("I_target")), "A", ""),
        _row(t, "Continuous / short-time rating", "P", d.get("continuous_power_W",
             d.get("power_W")), "W", "IEEE Std 32"),
    ]
    return f"<h2>{t['sysgnd']}</h2>{_table(t, rows)}"


# ---------------------------------------------------------------------------

def build(data: dict, lang: str = "en") -> str:
    t = T.get(lang, T["en"])
    meta = data.get("meta", {})
    rtl = t["dir"] == "rtl"
    css = CSS % dict(
        font=("Vazirmatn, 'IRANSans', Tahoma, 'Segoe UI', sans-serif" if rtl
              else "'Segoe UI', 'Inter', Calibri, Arial, sans-serif"),
        align="right" if rtl else "left",
        numalign="left" if rtl else "right",
    )

    kpis = []
    for key, label, unit in (("Rg", "R<sub>g</sub>", "Ω"),
                             ("GPR", "GPR", "V"),
                             ("Em", "E<sub>m</sub>", "V"),
                             ("Es", "E<sub>s</sub>", "V")):
        v = (data.get("grid", {}) or {}).get("summary", {}).get(key)
        if v is None:
            v = (data.get("bem", {}) or {}).get(key)
        if v is not None:
            kpis.append(f"<div><div class='v'>{_fmt(v)} {unit}</div>"
                        f"<div class='l'>{label}</div></div>")
    kpi_html = f"<div class='kpi'>{''.join(kpis)}</div>" if kpis else ""

    sections = "".join([
        _sec_soil(t, data.get("soil")),
        _sec_fault(t, data.get("fault")),
        _sec_conductor(t, data.get("conductor")),
        _sec_grid(t, data.get("grid")),
        _sec_bem(t, data.get("bem")),
        _sec_building(t, data.get("building")),
        _sec_lightning(t, data.get("lightning")),
        _sec_sysgnd(t, data.get("sysgnd")),
        _figures(t, data.get("figures")),
    ])

    notes = data.get("notes") or ""
    notes_html = (f"<h2>{t['notes']}</h2><div class='note'>"
                  f"{html.escape(notes).replace(chr(10), '<br>')}</div>"
                  if notes else "")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="{t['lang']}" dir="{t['dir']}">
<head><meta charset="utf-8">
<title>{html.escape(meta.get('project', t['title']))} — {t['title']}</title>
<style>{css}</style></head>
<body>
<h1>{t['title']}</h1>
<div class="sub">{t['generated']}: {now} — EarthSystem</div>
<div class="meta">
  <div><b>{t['project']}:</b> <bdi>{html.escape(str(meta.get('project', '—')))}</bdi></div>
  <div><b>{t['client']}:</b> <bdi>{html.escape(str(meta.get('client', '—')))}</bdi></div>
  <div><b>{t['engineer']}:</b> <bdi>{html.escape(str(meta.get('engineer', '—')))}</bdi></div>
  <div><b>{t['reference']}:</b> <bdi>{html.escape(str(meta.get('reference', '—')))}</bdi></div>
  <div><b>{t['revision']}:</b> <bdi>{html.escape(str(meta.get('revision', '00')))}</bdi></div>
  <div><b>{t['date']}:</b> <bdi>{html.escape(str(meta.get('date', now[:10])))}</bdi></div>
</div>
{kpi_html}
{sections}
{notes_html}
<footer>{t['disclaimer']}</footer>
</body></html>"""
