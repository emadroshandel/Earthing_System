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
        "impulse": "Behaviour under the lightning impulse",
        "airterm": "Air termination and protection zone (IEC 62305-3)",
        "sysgnd": "System neutral grounding (IEEE Std 142)",
        "earthpit": "Earth pits (backfilled electrodes)",
        "checks": "Compliance summary",
        "figures": "Figures", "figure": "Figure",
        "parameter": "Parameter", "symbol": "Symbol", "value": "Value",
        "unit": "Unit", "source": "Basis / reference",
        "criterion": "Criterion", "limit": "Limit", "result": "Result",
        "pass": "PASS", "fail": "FAIL", "margin": "Margin",
        "notes": "Notes and assumptions",
        "disclaimer": "This report was produced by Earthing System. All results "
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
        "standards": "Standards and codes of practice",
        "standards_intro": ("Standards applied or cross-checked in this report "
                            "(role: implemented, cross-check or reference). "
                            "Editions are those the calculations follow."),
        "role": "Role", "std": "Standard", "std_title": "Title", "area": "Area",
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
        "impulse": "رفتار سیستم زمین در برابر ضربه صاعقه",
        "airterm": "صاعقه‌گیر و محدوده حفاظت‌شده (IEC 62305-3)",
        "sysgnd": "زمین کردن نقطه خنثی سیستم (IEEE 142)",
        "earthpit": "چاه ارت (الکترود در مواد کاهنده مقاومت)",
        "checks": "جمع‌بندی انطباق با استاندارد",
        "figures": "نمودارها", "figure": "نمودار",
        "parameter": "پارامتر", "symbol": "نماد", "value": "مقدار",
        "unit": "واحد", "source": "مبنا / مرجع",
        "criterion": "معیار", "limit": "حد مجاز", "result": "نتیجه",
        "pass": "قبول", "fail": "مردود", "margin": "حاشیه اطمینان",
        "notes": "یادداشت‌ها و مفروضات",
        "disclaimer": "این گزارش توسط نرم‌افزار Earthing System تولید شده است. "
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
        "standards": "استانداردها و آیین‌نامه‌ها",
        "standards_intro": ("استانداردهایی که در این گزارش به کار رفته یا برای "
                            "صحت‌سنجی استفاده شده‌اند."),
        "role": "نقش", "std": "استاندارد", "std_title": "عنوان", "area": "حوزه",
    },
}

# Persian labels for the quantity names used in the tables
LABELS_FA = {
    "Additional studies": "مطالعات تکمیلی",
    "Governing values": "مقادیر حاکم (مبنای حکم انطباق)",
    "Fence touch voltage": "ولتاژ تماس حصار",
    "Maximum touch voltage (governing)": "حداکثر ولتاژ تماس (مقدار حاکم)",
    "Maximum step voltage (governing)": "حداکثر ولتاژ گام (مقدار حاکم)",
    "Earth resistance / impedance": "مقاومت / امپدانس زمین",
    "plain solution": "حل پایه",
    "Soil readings set aside (robust fit)": "قرائت‌های کنار گذاشته شده (برازش مقاوم)",
    "Traverses fitted separately": "برازش جداگانه هر مسیر اندازه‌گیری",
    "Shield wires and fault location": "سیم محافظ و محل خطا",
    "Convergence check": "بررسی همگرایی",
    "Seasonal soil": "تغییرات فصلی خاک",
    "Soil uncertainty": "عدم قطعیت مدل خاک",
    "Non-equipotential solution": "حل بدون فرض هم‌پتانسیلی",
    "Two-scale solution": "حل دومقیاسی",
    "Plate area": "مساحت صفحه",
    "Lightning model segments": "تعداد قطعات مدل صاعقه",
    "Circuit-field check: largest touch voltage": "بررسی مدل مدار-میدان: بیشترین ولتاژ تماس",
    "Parallel lines in the corridor": "خطوط موازی در مسیر مشترک",
    "Shield wires on the line": "سیم‌های محافظ خط",
    "Grid optimisation": "بهینه‌سازی شبکه زمین",
    "Fall-of-potential test": "آزمون افت پتانسیل",
    "Risk assessment (IEC 62305-2)": "ارزیابی ریسک (IEC 62305-2)",
    "Surge protection (IEC 62305-4)": "حفاظت در برابر اضافه‌ولتاژ (IEC 62305-4)",
    "Reading set aside": "قرائت کنار گذاشته شده",
    "Largest grid current": "بیشترین جریان شبکه زمین",
    "Design grid current": "جریان طراحی شبکه زمین",
    "Fault in the station: grid current": "خطا در پست: جریان شبکه زمین",
    "Probability of meeting both limits": "احتمال رعایت هر دو حد مجاز",
    "Earth impedance at the feed": "امپدانس زمین در محل تزریق",
    "Earth resistance, equipotential": "مقاومت زمین با فرض هم‌پتانسیلی",
    "Recommended current-electrode distance": "فاصله پیشنهادی الکترود جریان",
    "Resistance implied by the readings": "مقاومت حاصل از قرائت‌ها",
    "Risk R1, unprotected": "ریسک R1 بدون حفاظت",
    "Strike-point density": "چگالی نقاط برخورد",
    "Flashes to the structure": "تعداد صاعقه به سازه",
    "Protection found": "حفاظت یافت‌شده",
    "Closest protection": "نزدیک‌ترین حفاظت",
    "Fuse operating time at the fault current": "زمان عملکرد فیوز در جریان خطا",
    "Other lines at the station": "خطوط دیگر متصل به پست",
    "Measured footing resistances": "مقاومت‌های پای دکل اندازه‌گیری‌شده",
    "Cable sheaths — earth-fault return": "غلاف کابل‌ها — مسیر برگشت جریان خطای زمین",
    "Highest link-box voltage": "بیشترین ولتاژ جعبه اتصال",
    "Split factor": "ضریب تقسیم جریان",
    "Current into the station earth": "جریان ورودی به زمین پست",
    "Current returning in the sheaths": "جریان برگشتی از غلاف‌ها",
    "Earth potential rise at the far end": "افزایش پتانسیل زمین در انتهای دور",
    "Risk management (IEC 62305-2:2024)": "مدیریت ریسک (IEC 62305-2:2024)",
    "Protection found": "حفاظت لازم",
    "Conductors": "هادی‌ها",
    "Rods": "میله‌ها",
    "Air-termination mesh size": "ابعاد شبکه صاعقه‌گیر روی بام",
    "Impulse front time": "زمان جبهه موج ضربه",
    "Injection point": "محل تزریق جریان صاعقه",
    "Effective length of a horizontal electrode": "طول مؤثر الکترود افقی",
    "Extent of the earthing system": "گستره سیستم زمین",
    "Length beyond the reach of the front": "طول خارج از دسترس جبهه موج",
    "Equivalent radius of the earthing system": "شعاع معادل سیستم زمین",
    "Effective radius adopted": "شعاع مؤثر انتخابی",
    "Impulse coefficient": "ضریب ضربه",
    "Impedance during the front": "امپدانس در زمان جبهه موج",
    "Peak potential rise from I·R": "افزایش پتانسیل بر مبنای I·R",
    "Peak potential rise under the impulse": "افزایش پتانسیل در شرایط ضربه",
    "Ambient temperature": "دمای محیط",
    "Burial depth": "عمق دفن",
    "Conductor diameter": "قطر هادی",
    "Conductor spacing": "فاصله هادی‌های شبکه",
    "Continuous / short-time rating": "توان نامی پیوسته / کوتاه‌مدت",
    "Decrement factor": "ضریب کاهش (مؤلفه DC)",
    "Design current": "جریان طراحی",
    "Discretised segments": "تعداد المان‌های گسسته‌سازی",
    "Solution method": "روش حل دستگاه معادلات",
    "Automatic refinement": "ریزسازی خودکار المان‌ها",
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
    "Permissible touch voltage (cross-check)": "ولتاژ تماس مجاز (صحت‌سنجی EN 50522)",
    "Permissible prospective touch voltage (cross-check)": "ولتاژ تماس پیش‌بینی‌شده مجاز (صحت‌سنجی EN 50522)",
    "Prospective touch voltage, finite surface layer": "ولتاژ تماس پیش‌بینی‌شده مجاز با لایهٔ سطحی با ضخامت محدود",
    "IEEE 80 touch limit, body resistance only": "حد ولتاژ تماس IEEE 80 بدون لایه سطحی",
    "Soil resistivity at 1/(4T)": "مقاومت ویژه خاک در فرکانس 1/(4T)",
    "Tolerable touch voltage": "ولتاژ تماس مجاز",
    "Total buried length": "طول کل هادی دفن‌شده",
    "Total electrode length": "طول کل الکترود",
    "Upper-layer resistivity": "مقاومت ویژه لایه بالا",
    "Upper-layer thickness": "ضخامت لایه بالا",
    "Layer 1 resistivity": "مقاومت ویژه لایه اول",
    "Layer 2 resistivity": "مقاومت ویژه لایه دوم",
    "Layer 3 resistivity": "مقاومت ویژه لایه سوم",
    "Layer 1 thickness": "ضخامت لایه اول",
    "Layer 2 thickness": "ضخامت لایه دوم",
    "Layer 3 thickness": "ضخامت لایه سوم",
    "Layer 4 resistivity": "مقاومت ویژه لایه چهارم",
    "RMS fit error, two-layer model": "خطای برازش (RMS) مدل دولایه",
    "Best-determined combination": "ترکیب با بهترین تعیین",
    "Fence potential": "پتانسیل حصار",
    "Low-frequency resistance (lightning model)": "مقاومت فرکانس پایین (مدل صاعقه)",
    "Impulse impedance, first stroke": "امپدانس ضربه، ضربه اول",
    "Impulse impedance, subsequent stroke": "امپدانس ضربه، ضربه بعدی",
    "Impulse coefficient, first stroke": "ضریب ضربه، ضربه اول",
    "Impulse coefficient, subsequent stroke": "ضریب ضربه، ضربه بعدی",
    "Peak potential rise, first stroke": "حداکثر افزایش پتانسیل، ضربه اول",
    "Peak potential rise, subsequent stroke": "حداکثر افزایش پتانسیل، ضربه بعدی",
    "Impulse impedance with ionisation, first stroke": "امپدانس ضربه با یونیزاسیون خاک، ضربه اول",
    "Impulse impedance with ionisation, subsequent stroke": "امپدانس ضربه با یونیزاسیون خاک، ضربه بعدی",
    "Peak potential rise with ionisation, first stroke": "حداکثر افزایش پتانسیل با یونیزاسیون خاک، ضربه اول",
    "Peak potential rise with ionisation, subsequent stroke": "حداکثر افزایش پتانسیل با یونیزاسیون خاک، ضربه بعدی",
    "Fence touch voltage, inside": "ولتاژ تماس حصار، داخل",
    "Fence touch voltage, outside": "ولتاژ تماس حصار، بیرون",
    "Grid-to-fence transfer voltage": "ولتاژ انتقالی شبکه به حصار",
    "Largest touch voltage along the route": "بیشترین ولتاژ تماس در طول مسیر",
    "Fence own resistance": "مقاومت زمین حصار",
    "Transferred potential at the far end": "پتانسیل انتقالی در انتهای دور",
    "Far-end metal potential": "پتانسیل فلز در انتهای دور",
    "GPR with the conductor": "افزایش پتانسیل زمین با هادی",
    "Attenuation length": "طول میرایی",
    "Current drawn away from the grid": "جریان منحرف‌شده از شبکه",
    # compliance criteria
    "GPR vs tolerable touch voltage": "مقایسه GPR با ولتاژ تماس مجاز",
    "Mesh (touch) voltage E_m": "ولتاژ چشمه (تماس) E_m",
    "Step voltage E_s": "ولتاژ گام E_s",
    "Maximum touch voltage": "حداکثر ولتاژ تماس",
    "Maximum step voltage": "حداکثر ولتاژ گام",
    "Fence touch voltage (fence)": "ولتاژ تماس حصار",
    "Earth-fault loop impedance Z_s": "امپدانس حلقه خطا Z_s",
    "TT electrode: R_A × I_a \u2264 50 V": "الکترود TT: R_A × I_a ≤ 50 V",
    "TT loop impedance: Z_s × I_a \u2264 U₀": "امپدانس حلقه TT: Z_s × I_a ≤ U₀",
    "Automatic disconnection (U₀ \u2264 50 V)": "قطع خودکار (U₀ ≤ ۵۰ ولت)",
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
        ok = all(c.get("passed", True) for c in (checks or []) if not c.get("advisory"))
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

def _lflag(d, i):
    """Caution for a layer the readings do not fix (soil page layer_status)."""
    st = d.get("layer_status") or []
    if len(st) < i:
        return ""
    x = st[i - 1]
    return ("below the reach of the traverse, not measured" if x.get("below_reach")
            else "" if x.get("resolved", True) else
            "resistivity not resolved by the readings"
            if x.get("top_resolved", True) and not x.get("rho_resolved", True) else
            "depth of its top not resolved by the readings"
            if x.get("rho_resolved", True) else "not resolved by the readings")


def _sec_soil(t, d):
    if not d:
        return ""
    rows = []
    if d.get("rho1") is not None and (d.get("n_layers") or 2) >= 3:
        four = d.get("n_layers") == 4
        rows += [
            _row(t, "Layer 1 resistivity", "ρ₁", d.get("rho1"), "Ω·m",
                 ("Four" if four else "Three") + "-layer inversion of the field traverse"),
            _row(t, "Layer 2 resistivity", "ρ₂", d.get("rho2"), "Ω·m", _lflag(d, 2)),
            _row(t, "Layer 3 resistivity", "ρ₃", d.get("rho3"), "Ω·m", _lflag(d, 3)),
        ] + ([_row(t, "Layer 4 resistivity", "ρ₄", d.get("rho4"), "Ω·m", _lflag(d, 4))] if four else []) + [
            _row(t, "Layer 1 thickness", "h₁", d.get("h"), "m", ""),
            _row(t, "Layer 2 thickness", "h₂", d.get("h2"), "m", ""),
        ] + ([_row(t, "Layer 3 thickness", "h₃", d.get("h3"), "m", "")] if four else []) + [
            _row(t, "RMS fit error", "ε", d.get("rms_pct"), "%", ""),
        ]
        ms = d.get("model_selection") or {}
        if ms.get("rms_two") is not None:
            rows.append(_row(t, "RMS fit error, two-layer model", "ε₂",
                             ms.get("rms_two"), "%",
                             f"F test p = {_fmt(ms.get('p_value'))}"))
        eq = ((d.get("uncertainty") or {}).get("equivalence") or {})
        if eq.get("beta") is not None and eq.get("determined") not in (None, "both"):
            rows.append(_row(t, "Best-determined combination", "h₂·ρ₂^β",
                             eq.get("combination"), "",
                             f"β = {_fmt(eq.get('beta'))}, within "
                             f"×{_fmt(eq.get('combination_factor'))}"))
    elif d.get("rho1") is not None:
        rows += [
            _row(t, "Upper-layer resistivity", "ρ₁", d.get("rho1"), "Ω·m",
                 "Two-layer inversion of the field traverse"),
            _row(t, "Lower-layer resistivity", "ρ₂", d.get("rho2"), "Ω·m", _lflag(d, 2)),
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
                         "IEEE Std 81-2025 §7.3"))
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
    if d.get("model_warning"):
        body = (f"<div class='note'><bdi>{html.escape(str(d['model_warning']))}"
                f"</bdi></div>") + body
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
             "IEEE Std 80-2013 Eq. (84)"),
        _row(t, "Future-growth factor", "C_p", d.get("Cp"), "-", ""),
        _row(t, "Symmetrical grid current", "I_g", d.get("Ig_kA"), "kA", ""),
        _row(t, "Maximum grid current", "I_G", d.get("IG_kA"), "kA",
             "IEEE Std 80-2013 Eq. (69)"),
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
             "IEEE Std 80-2013 Eq. (45)"),
        # The size the conductor page selects is the largest of the IEEE 80
        # area, the IEC adiabatic area and the Table 54.1 minimum
        # (api.api_conductor -> selected_mm2).  The report used to print the
        # IEEE 80 figure alone, e.g. 6 mm² where the page selected 25 mm².
        (_row(t, "Selected standard size", "A_std", None, "mm²",
              f"no single conductor covers the duty ({_fmt(d.get('required_mm2'))} mm² required)")
         if d.get("off_scale") else
         _row(t, "Selected standard size", "A_std",
              d.get("selected_mm2", d.get("standard_mm2")), "mm²",
              ({"ieee80": "IEEE 80 design basis, not below the Table 54.1 minimum",
                "iec": "IEC 60364-5-54 design basis, not below the Table 54.1 minimum"}
               .get(d.get("basis"), "larger of IEEE 80 and IEC 60364-5-54 adiabatic, "
                                    "not below the Table 54.1 minimum")
               + (f"; governed by {d['governs']}" if d.get("governs") else ""))
              if d.get("selected_mm2") is not None else "")),
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
        _row(t, "Geometric factor", "n", m.get("n"), "-", "Eq. (89)–(93)"),
        _row(t, "Mesh factor", "K_m", m.get("Km"), "-", "Eq. (86)"),
        _row(t, "Irregularity factor", "K_i", m.get("Ki"), "-", "Eq. (94)"),
        _row(t, "Step factor", "K_s", m.get("Ks"), "-", "Eq. (99)"),
        _row(t, "Effective mesh length", "L_M", m.get("LM"), "m", "Eq. (95)/(96)"),
        _row(t, "Effective step length", "L_S", m.get("LS"), "m", "Eq. (98)"),
        _row(t, "Mesh (touch) voltage", "E_m", m.get("Em"), "V", "Eq. (85)"),
        _row(t, "Step voltage", "E_s", m.get("Es"), "V", "Eq. (97)"),
        _row(t, "Surface derating factor", "C_s", tol.get("Cs"), "-", "Eq. (27)"),
        _row(t, "Tolerable touch voltage", "E_touch", tol.get("E_touch"), "V",
             f"{tol.get('body_weight', 70)} kg body, Eq. (32)/(33)"),
        _row(t, "Tolerable step voltage", "E_step", tol.get("E_step"), "V",
             "Eq. (29)/(30)"),
    ]
    xc = d.get("en50522") or {}
    if xc:
        rows += [
            _row(t, "Permissible touch voltage (cross-check)", "U_Tp", xc.get("U_Tp"), "V",
                 "BS EN 50522:2022 Table B.4 / IEC 60479-1"),
            _row(t, "IEEE 80 touch limit, body resistance only", "E_touch,0",
                 xc.get("E_bare_ieee80"), "V", "1000·k/√t_s"),
        ]
        if xc.get("U_vTp") is not None:
            rows.append(_row(t, "Permissible prospective touch voltage (cross-check)",
                             "U_vTp", xc.get("U_vTp"), "V",
                             "BS EN 50522:2022 Formula (A.3), 1000 Ω footwear"))
        if xc.get("U_vTp_thin") is not None:
            rows.append(_row(t, "Prospective touch voltage, finite surface layer",
                             "U_vTp", xc.get("U_vTp_thin"), "V",
                             f"R_F2 = 1.5·C_s·ρ_s (C_s = {xc.get('Cs', 0):.3f}); conservative"))
    # Print the resistance formula that produced R_g (1.3.3 always printed
    # Sverak, even when Schwarz or the automatic combination was used).
    sverak = "R_g = ρ [ 1/L_T + 1/√(20A) ( 1 + 1/(1 + h√(20/A)) ) ]  — Eq. (57)"
    schwarz = ("R_g = (R₁R₂ − R_m²)/(R₁ + R₂ − 2R_m)  — Schwarz, Eq. (58)–(61)")
    chosen = str((d.get("resistance") or {}).get("chosen", "Sverak"))
    if chosen.startswith("Sverak ×"):
        rf = (f"{sverak} (grid conductors only)<br>R_g = R_g,Sverak × R_g,Schwarz/R₁"
              f" — automatic: Sverak × Schwarz rod factor")
    elif chosen.startswith("Schwarz"):
        rf = schwarz
    else:
        rf = sverak
    f = (f"<div class='formula'>{rf}"
         "<br>E_m = ρ·K_m·K_i·I_G / L_M &nbsp;&nbsp; E_s = ρ·K_s·K_i·I_G / L_S</div>")
    warn = "".join(f"<div class='note'><bdi>{html.escape(str(w))}</bdi></div>"
                   for w in (d.get("warnings") or []))
    return (f"<h2>{t['grid']}</h2>{_table(t, rows)}{f}{warn}"
            f"{_checks_table(t, d.get('checks', []), d.get('narrative'), d.get('cross_check'))}")


def bem_refine_text(r):
    from . import bem
    return bem.describe_refinement(r) or "-"


def _solver_text(info):
    from . import bem
    return bem.describe_solver(info) or "-"


def _sec_bem(t, d):
    if not d:
        return ""
    rows = [
        _row(t, "Soil model", "-", d.get("soil"), "", "Boundary-element solver"),
        _row(t, "Discretised segments", "N", d.get("segments"), "-", ""),
        _row(t, "Solution method", "-", _solver_text(d.get("solver")), "", ""),
        *([_row(t, "Automatic refinement", "-", bem_refine_text(d.get("refinement")), "",
                "segments halved at the worst touch and step points")]
          if d.get("refinement") else []),
        _row(t, "Total electrode length", "L", d.get("total_length"), "m", ""),
        *([_row(t, "Plate area", "A_p", d.get("plate_area"), "m²",
                f"{d.get('plates')} plate(s), both faces in contact with the soil")]
          if d.get("plate_area") else []),
        _row(t, "Injected current", "I_G", d.get("IG"), "A", ""),
        _row(t, "Earth resistance", "R_g", d.get("Rg"), "Ω",
             "R_g = GPR / I_G from the method-of-moments solution"),
        _row(t, "Ground potential rise", "GPR", d.get("GPR"), "V", ""),
        _row(t, "Maximum touch voltage", "U_T,max", d.get("touch_max"), "V",
             "GPR − V_surface over the scanned area"),
        _row(t, "Maximum step voltage", "U_S,max", d.get("step_max"), "V",
             "1 m potential difference at the soil surface"),
    ]
    nets = {n.get("index"): n for n in (d.get("networks") or [])}
    for f in d.get("fences") or []:
        nm = f.get("name", "fence")
        how = "bonded to the grid" if f.get("bonded") else "isolated"
        rows += [
            _row(t, "Fence potential", "V_F", f.get("V_fence"), "V",
                 f"{nm}, {how}: {_fmt(f.get('V_pct_GPR'))} % of GPR"),
            _row(t, "Fence touch voltage, inside", "U_T,in",
                 abs((f.get("touch_inside") or {}).get("touch_max", 0)), "V",
                 "V_F − V_surface within 1 m inside the fence"),
            _row(t, "Fence touch voltage, outside", "U_T,out",
                 abs((f.get("touch_outside") or {}).get("touch_max", 0)), "V",
                 "V_F − V_surface within 1 m outside the fence"),
        ]
        if not f.get("bonded"):
            n = nets.get(f.get("net")) or {}
            rows += [
                _row(t, "Grid-to-fence transfer voltage", "ΔV", f.get("transfer_from_main"),
                     "V", "GPR − V_F"),
                _row(t, "Fence own resistance", "R_F", n.get("R_self"), "Ω",
                     "fence energised alone, grid present and floating"),
            ]
    tr = d.get("transfer")
    if tr:
        rows += [
            _row(t, "GPR with the conductor", "GPR", tr.get("GPR"), "V",
                 f"{tr.get('kind')} conductor, {_fmt(tr.get('length'))} m, {tr.get('near')} at the station"),
            _row(t, "Current drawn away from the grid", "I", tr.get("I_diverted"), "A", ""),
            _row(t, "Attenuation length", "1/α", tr.get("attenuation_length"), "m", "lossy-line model"),
            _row(t, "Far-end metal potential", "V_far", tr.get("V_far"), "V",
                 f"{_fmt(tr.get('V_far_pct'))} % of GPR"),
            _row(t, "Transferred potential at the far end", "U_T", tr.get("transfer_far"), "V",
                 "metal − local soil (IEEE Std 80 §17.3)"),
            _row(t, "Largest touch voltage along the route", "U_T", tr.get("touch_max"), "V",
                 f"at {_fmt(tr.get('touch_max_at'))} m; "
                 + ("solved with the station" if tr.get("model") == "coupled"
                    else "one-way lossy-line model")),
        ]
        cf = tr.get("circuit_field") or {}
        if cf and not cf.get("skipped"):
            rows.append(_row(t, "Circuit-field check: largest touch voltage", "U_T,cf",
                             cf.get("touch_max"), "V",
                             f"station and route with conductor impedance and mutual inductance, "
                             f"{cf.get('segments')} segments; design value "
                             f"{_fmt(tr.get('touch_max_design'))} V (the larger of the two)"))
    h = d.get("hf")
    if h:
        rows.append(_row(t, "Low-frequency resistance (lightning model)", "R_LF", h.get("R"), "Ω",
                         h.get("soil", "")))
        g = h.get("grading")
        rows.append(_row(t, "Lightning model segments", "N", h.get("segments"), "",
                         (f"graded mesh: {_fmt(g.get('s0'))} m at the injection, growing "
                          f"{_fmt(100 * g.get('alpha', 0))} % of the distance, up to "
                          f"{_fmt(g.get('s_max'))} m") if g else
                         f"{_fmt(h.get('seg_len'))} m segments"))
        for key, lab in (("first_tb781", "first"), ("subsequent_tb781", "subsequent"),
                         ("first_heidler", "first"), ("subsequent_heidler", "subsequent")):
            x = (h.get("responses") or {}).get(key)
            if not x:
                continue
            rows += [
                _row(t, f"Impulse impedance, {lab} stroke", "Z_p", x.get("Z_impulse"), "Ω",
                     f"{_fmt(x.get('I_peak_kA'))} kA, {x.get('label', '')}"),
                _row(t, f"Impulse coefficient, {lab} stroke", "IC", x.get("IC"), "–",
                     "Z_p / R_LF"),
                _row(t, f"Peak potential rise, {lab} stroke", "V_p", x.get("V_peak_kV"), "kV", ""),
            ]
            if x.get("Z_impulse_ion") is not None:
                ion = h.get("ionisation") or {}
                rows += [
                    _row(t, f"Impulse impedance with ionisation, {lab} stroke", "Z_p,i",
                         x.get("Z_impulse_ion"), "Ω",
                         f"E0 = {_fmt(ion.get('E0'))} kV/m, I_g = {_fmt(ion.get('Ig_kA'))} kA"),
                    _row(t, f"Peak potential rise with ionisation, {lab} stroke", "V_p,i",
                         x.get("V_peak_ion_kV"), "kV", "Grcev (2009) Eq. 20"),
                ]
    return (f"<h2>{t['numerical']}</h2>{_table(t, rows)}"
            f"{_checks_table(t, d.get('checks', []), d.get('narrative'), d.get('cross_check'))}"
            f"{_sec_governing(t, d.get('governing'))}")


def _sec_governing(t, g):
    """Governing values of the numerical page (1.8.2): the verdict that counts."""
    if not g:
        return ""
    L = t.get("L", {})
    Q = g.get("quantities") or {}
    rows = []
    for k, lab, sym, unit in (("touch", "Maximum touch voltage", "U_T", "V"),
                              ("step", "Maximum step voltage", "U_S", "V"),
                              ("Rg", "Earth resistance / impedance", "R_g", "Ω"),
                              ("GPR", "Ground potential rise", "GPR", "V")):
        q = Q.get(k)
        if not q:
            continue
        src = str(q.get("label", ""))
        if q.get("detail"):
            src += f" ({q['detail']})"
        if q.get("source") != "base" and q.get("base"):
            src += f"; {L.get('plain solution', 'plain solution')} {_fmt(q['base'])} {unit}"
        rows.append(_row(t, lab, sym, q.get("value"), unit, html.escape(src)))
    title = L.get("Governing values", "Governing values")
    return (f"<h3>{html.escape(title)}</h3>{_table(t, rows)}"
            f"{_checks_table(t, g.get('checks', []), g.get('note'))}")


def _sec_studies(t, data):
    """Section for the 1.8.0 studies: robust and multi-traverse soil fits,
    the shield-wire ladder, accuracy and soil studies of the numerical
    solver, the non-equipotential solution, optimisation, the
    fall-of-potential plan, IEC 62305-2 risk and IEC 62305-4 SPDs."""
    st = data.get("studies") or {}
    soil = data.get("soil") or {}
    rob = soil.get("robust") or {}
    trv = soil.get("traverses") or {}
    if not st and not rob.get("excluded") and not trv:
        return ""
    L = t.get("L", {})
    out = [f"<h2>{html.escape(L.get('Additional studies', 'Additional studies'))}</h2>"]

    def sub(title, rows, note=""):
        if not rows and not note:
            return
        out.append(f"<h3>{html.escape(L.get(title, title))}</h3>")
        if rows:
            out.append(_table(t, rows))
        if note:
            out.append(f"<div class='note'><bdi>{html.escape(str(note))}</bdi></div>")

    if rob.get("excluded"):
        sub("Soil readings set aside (robust fit)",
            [_row(t, "Reading set aside", "a", e.get("spacing"), "m",
                  f"measured {_fmt(e.get('measured'))} Ω·m, model {_fmt(e.get('model'))} Ω·m")
             for e in rob["excluded"]], rob.get("note", ""))
    if trv.get("fits"):
        sub("Traverses fitted separately",
            [_row(t, f"Traverse {f.get('name')}", "ρ₁ / ρ₂ / h",
                  f"{_fmt(f.get('rho1'))} / {_fmt(f.get('rho2'))} / {_fmt(f.get('h'))}",
                  "Ω·m / Ω·m / m", f"RMS {_fmt(f.get('rms_pct'))} %")
             for f in trv["fits"] if f.get("fitted")], trv.get("note", ""))
    fs = st.get("faultsweep")
    if fs:
        s0, w = fs.get("station") or {}, fs.get("worst") or {}
        sub("Shield wires and fault location", [
            _row(t, "Fault in the station: grid current", "I_g", s0.get("Ig_kA"), "kA",
                 f"S_f = {_fmt(s0.get('Sf'))}"),
            _row(t, "Largest grid current", "I_g,max", w.get("Ig_kA"), "kA", fs.get("governs", "")),
            _row(t, "Design grid current", "I_G", fs.get("IG_design_kA"), "kA", "D_f · I_g,max"),
        ] + ([_row(t, "Other lines at the station", "Z_other", fs.get("Z_other_total"), "Ω",
                   ", ".join(str(o.get("name")) for o in fs.get("other_lines") or []))]
             if fs.get("other_lines") else [])
          + ([_row(t, "Parallel lines in the corridor", "n", len(fs.get("parallel_lines")), "",
                   html.escape("; ".join(f"{q.get('name')}: {_fmt(q.get('separation'))} m"
                                         for q in fs.get("parallel_lines"))
                               + "; solved as one coupled network"))]
             if fs.get("parallel_lines") else [])
          + ([_row(t, "Shield wires on the line", "n", fs.get("n_wires"), "",
                   "one bundle with their mutual impedance")]
             if (fs.get("n_wires") or 1) > 1 else [])
          + ([_row(t, "Measured footing resistances", "R_t", f"{len(fs.get('Rt_list'))} towers", "",
                   f"{_fmt(min(fs['Rt_list']))} … {_fmt(max(fs['Rt_list']))} Ω")]
             if fs.get("Rt_list") else []), fs.get("note", ""))
    cs = st.get("cablesheath")
    if cs:
        sub("Cable sheaths — earth-fault return", [
            _row(t, "Split factor", "S_f", cs.get("Sf"), "", cs.get("bonding", "")),
            _row(t, "Current into the station earth", "I_g", cs.get("Ig_kA"), "kA", ""),
            _row(t, "Current returning in the sheaths", "I_sheath", cs.get("I_sheath_kA"), "kA", ""),
            _row(t, "Earth potential rise at the far end", "GPR_B", cs.get("GPR_B"), "V", ""),
        ] + ([_row(t, "Highest link-box voltage", "V_lb",
                   max(l["V_max"] for l in cs["link_boxes"]), "V",
                   f"{_fmt(max(l['V_across_max'] for l in cs['link_boxes']))} V across a "
                   f"sectionalising joint")] if cs.get("link_boxes") else []), cs.get("note", ""))
    cv = st.get("convergence")
    if cv:
        sub("Convergence check", [
            _row(t, "Touch voltage, estimated converged", "U_T", (cv.get("touch") or {}).get("extrapolated"), "V",
                 f"change on halving the segments {_fmt((cv.get('touch') or {}).get('change_pct'))} %"),
            _row(t, "Step voltage, estimated converged", "U_S", (cv.get("step") or {}).get("extrapolated"), "V",
                 f"change {_fmt((cv.get('step') or {}).get('change_pct'))} %"),
        ], cv.get("note", ""))
    se = st.get("seasonal")
    if se:
        sub("Seasonal soil", [
            _row(t, c.get("name"), "R_g / U_T / U_S",
                 f"{_fmt(c.get('Rg'))} / {_fmt(c.get('touch'))} / {_fmt(c.get('step'))}", "Ω / V / V", "")
            for c in se.get("cases") or []], se.get("note", ""))
    mc = st.get("montecarlo")
    if mc:
        S_ = mc.get("stats") or {}
        rows = [_row(t, f"{lab}, 5 % / median / 95 %", sym,
                     f"{_fmt((S_.get(k) or {}).get('p05'))} / {_fmt((S_.get(k) or {}).get('p50'))} / {_fmt((S_.get(k) or {}).get('p95'))}",
                     u, "") for lab, sym, k, u in (("Earth resistance", "R_g", "Rg", "Ω"),
                                                   ("Touch voltage", "U_T", "touch", "V"),
                                                   ("Step voltage", "U_S", "step", "V"))]
        if mc.get("p_pass") is not None:
            ci = (mc.get("ci95") or {}).get("p_pass")
            rows.append(_row(t, "Probability of meeting both limits", "P", 100.0 * mc["p_pass"], "%",
                             f"{mc.get('n')} soil models"
                             + (f", 95 % CI {_fmt(100 * ci[0], 0)}–{_fmt(100 * ci[1], 0)} %" if ci else "")
                             + (", Latin hypercube" if mc.get("method") == "lhs" else "")))
        sub("Soil uncertainty", rows, mc.get("note", ""))
    pf = st.get("powerfreq")
    if pf:
        sub("Non-equipotential solution", [
            _row(t, "Earth impedance at the feed", "|Z|", (pf.get("Z") or {}).get("abs"), "Ω",
                 f"{pf.get('metal')}, {_fmt(pf.get('f'))} Hz"),
            _row(t, "Earth resistance, equipotential", "R_g", pf.get("Rg_equipotential"), "Ω", ""),
            _row(t, "Lowest metal potential / feed", "V_min/V_feed", pf.get("V_min_over_feed"), "–", ""),
            _row(t, "Maximum touch voltage", "U_T", pf.get("touch_max"), "V",
                 f"equipotential {_fmt((pf.get('equipotential') or {}).get('touch_max'))} V"),
            _row(t, "Maximum step voltage", "U_S", pf.get("step_max"), "V",
                 f"equipotential {_fmt((pf.get('equipotential') or {}).get('step_max'))} V"),
        ] + ([_row(t, "Two-scale solution", "N / N_f",
                   f"{(pf.get('two_scale') or {}).get('coarse_segments')} / "
                   f"{(pf.get('two_scale') or {}).get('fine_segments')}", "",
                   f"metal potentials at {_fmt((pf.get('two_scale') or {}).get('coarse_length'))} m, "
                   f"leakage and surface at {_fmt((pf.get('two_scale') or {}).get('fine_length'))} m")]
             if pf.get("two_scale") else []) + [_row(t, "Fence touch voltage", "U_T,F", f.get("touch_max"), "V",
                  html.escape(f"{f.get('name')} ({'bonded' if f.get('bonded') else 'isolated'}), "
                              f"{f.get('side')}; equipotential {_fmt(f.get('equipotential_touch'))} V"))
             for f in pf.get("fences") or []], pf.get("note", ""))
    op = st.get("optimise")
    if op and op.get("best"):
        b = op["best"]
        sub("Grid optimisation", [
            _row(t, "Conductors", "n_x × n_y", f"{b.get('n_x')} × {b.get('n_y')}", "", f"grading {_fmt(b.get('grading'))}"),
            _row(t, "Rods", "n", b.get("rods"), "", ""),
            _row(t, "Maximum touch voltage", "U_T", b.get("touch"), "V", ""),
            _row(t, "Maximum step voltage", "U_S", b.get("step"), "V", ""),
        ], op.get("note", ""))
    ft = st.get("earthtest")
    if ft:
        rec = ft.get("recommended") or {}
        rows = [_row(t, "Recommended current-electrode distance", "d_C", rec.get("dC"), "m",
                     f"61.8 % error {_fmt(rec.get('error_618_pct'))} %")] if rec else []
        it = ft.get("interpretation")
        if it:
            rows.append(_row(t, "Resistance implied by the readings", "R", it.get("R_true_estimate"), "Ω",
                             f"scale {_fmt(it.get('scale'))}, shape RMS {_fmt(it.get('rms_shape_pct'))} %"))
        sub("Fall-of-potential test", rows, ft.get("note", ""))
    rk = st.get("risk")
    if rk:
        u = rk.get("unprotected") or {}
        c = rk.get("choice") or rk.get("best") or {}
        pr = rk.get("protected") or {}
        rows = [_row(t, "Strike-point density", "N_SG", u.get("NSG"), "1/km²/yr", f"k = {_fmt(u.get('k'))}"),
                _row(t, "Flashes to the structure", "N_D", u.get("ND"), "1/yr", "")]
        for z in u.get("zones") or []:
            rows.append(_row(t, f"Risk R, zone {z.get('name')}", "R", z.get("R"), "1/yr",
                             "R_T = 10⁻⁵" + (f"; F = {_fmt(z.get('F'))} /yr against F_T = {_fmt(z.get('FT'))}"
                                             if z.get("FT") and z.get("systems") else "")
                             + (f"; of which surroundings (Annex E) {_fmt(z.get('RE'))}"
                                if z.get("surroundings") else "")))
        if c:
            rows.append(_row(t, "Protection found" if rk.get("choice") else "Closest protection",
                             "LPS / bonding / SPD", f"{c.get('lps')} / {c.get('eb')} / {c.get('spd')}", "",
                             f"largest zone R = {_fmt(pr.get('R', c.get('R')))}"))
        sub("Risk management (IEC 62305-2:2024)", rows, rk.get("note", ""))
    sp = st.get("spd")
    if sp:
        out.append(f"<h3>{html.escape(L.get('Surge protection (IEC 62305-4)', 'Surge protection (IEC 62305-4)'))}</h3>")
        out.append(_checks_table(t, sp.get("checks") or [], sp.get("note", "")))
    return "".join(out)


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
        _row(t, "Maximum disconnection time", "t",
             ((d.get("disconnection") or {}).get("t")
              if (d.get("disconnection") or {}).get("required", True)
              else ("not required" if t["lang"] == "en" else "الزامی نیست")),
             "s", (d.get("disconnection") or {}).get("rule", "IEC 60364-4-41 Table 41.1")),
        _row(t, "Operating current of the device", "I_a",
             (d.get("device") or {}).get("Ia"), "A",
             (d.get("device") or {}).get("basis", "")),
    ]
    dv = d.get("device") or {}
    if dv.get("If_min"):
        rows.append(_row(t, "Fuse operating time at the fault current", "t_op",
                         dv.get("t_operate") if dv.get("t_operate") is not None else "—", "s",
                         f"I_f = C_min·U₀/Z_s = {_fmt(dv.get('If_min'))} A"))
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


def _sec_earthpit(t, d):
    if not d:
        return ""
    g, gd = d.get("group") or {}, d.get("group_dry") or {}
    rows = [
        _row(t, "Soil resistivity", "ρ", d.get("rho"), "Ω·m", ""),
        _row(t, "Backfill resistivity", "ρ_c", d.get("rho_c"), "Ω·m",
             f"{d.get('backfill', '')} — {d.get('backfill_source', '')}"),
        _row(t, "Electrode without backfill", "R₀", d.get("R_bare"), "Ω", d.get("method", "")),
        _row(t, "Electrode in its pit", "R₁", d.get("R_pit"), "Ω", d.get("method", "")),
    ]
    bs = d.get("bs7430")
    if bs:
        rows.append(_row(t, "BS 7430 9.5.7 cross-check", "R₁", bs.get("R"), "Ω", bs.get("formula", "")))
    if d.get("season_factor", 1) != 1:
        rows.append(_row(t, "One pit, dry season", "R₁,dry", d.get("R_dry"), "Ω",
                         f"soil ρ × {_fmt(d.get('season_factor'))}"))
    if g.get("n", 1) > 1:
        rows += [_row(t, "Pits in a line", "n", g.get("n"), "", f"spacing {_fmt(g.get('s'))} m"),
                 _row(t, "Group resistance", "R_n", g.get("R"), "Ω", g.get("formula", "")),
                 _row(t, "Group resistance, dry season", "R_n,dry", gd.get("R"), "Ω", "")]
    req = d.get("required")
    if req:
        rows.append(_row(t, "Pits needed for the target (dry season)", "n",
                         req.get("n") if req.get("reachable") else "—", "", req.get("note", "")))
    ld = d.get("loading")
    if ld:
        rows.append(_row(t, "Current density at the metal", "J", ld.get("J_metal"), "A/m²",
                         f"BS 7430 9.8 limit {_fmt(ld.get('Jmax_metal'))} A/m²"))
        if ld.get("J_boundary") is not None:
            rows.append(_row(t, "Current density at the backfill boundary", "J", ld.get("J_boundary"),
                             "A/m²", f"BS 7430 9.8 limit {_fmt(ld.get('Jmax_boundary'))} A/m²"))
    hs = d.get("housing")
    if hs:
        rows.append(_row(t, "Inspection housing", "-", f"Class {hs.get('cls')} ({_fmt(hs.get('load_kN'))} kN)",
                         "", hs.get("rule", "")))
    mt = d.get("maintenance") or {}
    rows.append(_row(t, "Re-service the pit above", "R", mt.get("retest_limit"), "Ω", mt.get("note", "")))
    for c in d.get("size_checks", []):
        rows.append(_row(t, "Electrode size", "-", f"{c.get('actual')} ({'OK' if c.get('ok') else 'below'})",
                         "", f"{c.get('rule')}: {c.get('required')}"))
    return f"<h2>{t['earthpit']}</h2>{_table(t, rows)}"


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
    sf = d.get("soil_frequency") or {}
    if sf:
        rows.append(_row(t, "Soil resistivity at 1/(4T)", "ρ(f)", sf.get("rho_f"), "Ω·m",
                         "CIGRE TB 781 (Alipio–Visacro), informational"))
        if sf.get("Zp_factor_first") is not None:
            rows.append(_row(t, "Impulse-impedance factor, first / subsequent stroke", "–",
                             f"{sf['Zp_factor_first']:.2f} / {sf['Zp_factor_subsequent']:.2f}", "",
                             "CIGRE TB 781 Table 4.1, informational"))
    out = (f"<h2>{t['lightning']}</h2>{_table(t, rows)}"
           f"{_checks_table(t, d.get('checks', []), d.get('narrative'))}")

    imp = d.get("impulse")
    if imp:
        lin = imp.get("linear") or {}
        ar = imp.get("area") or {}
        irows = [
            _row(t, "Impulse front time", "T", imp.get("T"), "µs",
                 "IEC 62305-1 Table 3"),
            _row(t, "Injection point", "-", imp.get("injection"), "", ""),
            _row(t, "Effective length of a horizontal electrode", "L_eff",
                 lin.get("L_eff"), "m", "L_eff = k·(ρT)^0.5"),
            _row(t, "Extent of the earthing system", "-",
                 imp.get("electrode_extent"), "m",
                 "ring mean radius, or the length of each radial electrode"),
            _row(t, "Length beyond the reach of the front", "-",
                 imp.get("wasted_length"), "m",
                 "no contribution to the impulse duty"),
            _row(t, "Equivalent radius of the earthing system", "r_geom",
                 imp.get("r_geometric"), "m", "√(A/π)"),
            _row(t, "Effective radius adopted", "r_eff",
                 imp.get("r_effective"), "m",
                 ("governed by " + ar["governing"]) if ar.get("governing") else ""),
            _row(t, "Impulse coefficient", "A = Z/R",
                 imp.get("impulse_coefficient"), "-", "first order, R = ρ/(4r)"),
            _row(t, "Impedance during the front", "Z", imp.get("Z_impulse"),
                 "Ω", "estimate"),
            _row(t, "Peak potential rise from I·R", "-",
                 None if imp.get("EPR_lf") is None else imp["EPR_lf"] / 1000.0,
                 "kV", f"{imp.get('I_kA')} kA"),
            _row(t, "Peak potential rise under the impulse", "-",
                 None if imp.get("EPR_impulse") is None
                 else imp["EPR_impulse"] / 1000.0, "kV",
                 "design bonding and SPDs on this value"),
        ]
        for mo in (ar.get("models") or []):
            irows.append(_row(t, f"Effective radius — {mo['name']}", "r_eff",
                              mo.get("r"), "m", mo.get("expression", "")))
        out += f"<h3>{t.get('impulse', 'Behaviour under the lightning impulse')}</h3>"
        out += _table(t, irows)
        if imp.get("verdict"):
            out += f"<div class='note'>{html.escape(imp['verdict'])}</div>"
        out += f"<div class='note'>{html.escape(imp.get('warning', ''))}</div>"
    return out


def _sec_airterm(t, d):
    if not d:
        return ""
    ms = d.get("mesh") or {}
    pl = d.get("plan") or {}
    terms = d.get("terminals") or []
    rows = [
        _row(t, "LPS class", "-", d.get("lps_class"), "", "IEC 62305-3 Table 2"),
        _row(t, "Rolling sphere radius", "R", d.get("R"), "m",
             "IEC 62305-3 Table 2"),
        _row(t, "Protected reference plane", "-", d.get("reference_plane"), "m", ""),
        _row(t, "Air terminations", "n", len(terms), "-", ""),
        _row(t, "Plan coverage of the protected plane", "-",
             (100.0 * pl["covered_fraction"]) if pl.get("covered_fraction") is not None
             else None, "%", "union of the protected circles"),
        _row(t, "Points left exposed", "-", d.get("exposed_count"), "-",
             "numerical rolling sphere"),
    ]
    for i, tm in enumerate(terms, 1):
        rows.append(_row(t, f"Termination {i}: tip height", "z", tm.get("tip"), "m", ""))
        rows.append(_row(t, f"Termination {i}: above the protected plane", "h",
                         tm.get("above_reference"), "m", ""))
        rows.append(_row(t, f"Termination {i}: protected radius", "r_p",
                         tm.get("r_protected"), "m",
                         "r_p = \u221a(2Rh \u2212 h\u00b2)"))
        pa = tm.get("protective_angle") or {}
        if pa.get("applicable"):
            rows.append(_row(t, f"Termination {i}: protective angle", "\u03b1",
                             pa.get("alpha"), "\u00b0", "IEC 62305-3 Figure 1"))
    for i, sp in enumerate(d.get("spans") or [], 1):
        rows.append(_row(t, f"Span {i}: spacing", "d", sp.get("d"), "m", ""))
        if sp.get("sag") is not None:
            rows.append(_row(t, f"Span {i}: sphere penetration", "p", sp.get("sag"), "m",
                             "p = R \u2212 \u221a(R\u00b2 \u2212 (d/2)\u00b2)"))
        rows.append(_row(t, f"Span {i}: protected height at mid-span", "-",
                         sp.get("protected_height"), "m", ""))
    if ms:
        rows.append(_row(t, "Mesh size for the class", "-", ms.get("mesh_required"),
                         "m", "IEC 62305-3 Table 2"))
        rows.append(_row(t, "Mesh conductor length", "L", ms.get("total_length"), "m", ""))
        rows.append(_row(t, "Down-conductors", "n", ms.get("n_down"), "-",
                         "IEC 62305-3 Table 4"))
        rows.append(_row(t, "Down-conductor spacing", "-",
                         ms.get("actual_down_spacing"), "m", ""))
    return (f"<h2>{t['airterm']}</h2>{_table(t, rows)}"
            f"{_checks_table(t, d.get('checks', []), d.get('narrative'), d.get('method_note', ''))}")


def _sec_sysgnd(t, d):
    if not d:
        return ""
    # api_sysgnd returns the method key ("high_resistance") and, in automatic
    # mode, the recommendation under d["recommendation"]; there is no
    # top-level "data", so the report used to print the raw key.
    from .ieee142 import GROUNDING_METHODS
    meth = d.get("method")
    name = ((d.get("data") or {}).get("name")
            or ((d.get("recommendation") or {}).get("data") or {}).get("name")
            or (GROUNDING_METHODS.get(meth) or {}).get("name") or meth)
    rows = [
        _row(t, "Recommended method" if d.get("recommendation") else "Method",
             "-", name, "", "IEEE Std 142"),
        _row(t, "System charging current", "3I_C0", d.get("three_IC0"), "A", ""),
        _row(t, "Neutral resistor", "R_N", d.get("R_ohm"), "Ω", ""),
        _row(t, "Resistor current" if d.get("I_R") else "Earth-fault current",
             "I_R" if d.get("I_R") else "I_f", d.get("I_R", d.get("I_target")), "A", ""),
    ]
    if d.get("total_fault_current"):
        # 1.3.3 printed the resistor current as the earth-fault current
        rows.append(_row(t, "Total earth-fault current", "I_f",
                         d.get("total_fault_current"), "A", "√(I_R² + (3I_C0)²)"))
    rows.append(_row(t, "Continuous / short-time rating", "P", d.get("continuous_power_W",
                     d.get("power_W")), "W", "IEEE Std 32"))
    warn = "".join(f"<div class='note'>{html.escape(w)}</div>"
                   for w in (d.get("warnings") or []))
    return f"<h2>{t['sysgnd']}</h2>{_table(t, rows)}{warn}"


# ---------------------------------------------------------------------------

def _sec_standards(t, data):
    from . import standards as st
    mods = [m for m in ("soil", "fault", "conductor", "grid", "bem", "building",
                        "earthpit", "lightning", "airterm", "sysgnd") if data.get(m)]
    if not mods:
        return ""
    body = "".join(
        f"<tr><td><bdi>{html.escape(e['id'])}</bdi></td>"
        f"<td><bdi>{html.escape(e['title'])}</bdi></td>"
        f"<td>{html.escape(st.AREAS.get(e['area'], e['area']))}</td>"
        f"<td>{html.escape(e['role'])}</td></tr>"
        for e in st.for_modules(mods))
    return (f"<h2>{t['standards']}</h2><p class='note'>{t['standards_intro']}</p>"
            f"<table><thead><tr><th>{t['std']}</th><th>{t['std_title']}</th>"
            f"<th>{t['area']}</th><th>{t['role']}</th></tr></thead>"
            f"<tbody>{body}</tbody></table>")


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
        _sec_earthpit(t, data.get("earthpit")),
        _sec_lightning(t, data.get("lightning")),
        _sec_airterm(t, data.get("airterm")),
        _sec_sysgnd(t, data.get("sysgnd")),
        _sec_studies(t, data),
        _figures(t, data.get("figures")),
        _sec_standards(t, data),
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
<div class="sub">{t['generated']}: {now} — Earthing System</div>
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
