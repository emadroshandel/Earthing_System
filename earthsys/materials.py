"""
Material, soil and standard-size reference data for EarthSystem.

Sources
-------
* IEEE Std 80-2013, Table 1  -- conductor material constants
* IEEE Std 80-2013, Table 7  -- typical soil resistivities
* IEC 60364-5-54:2011, Tables A.54.1 .. A.54.6 -- k factors (adiabatic)
* IEC 60364-5-54:2011, Table 54.1 -- minimum earthing-conductor sizes
* IEC 62305-3:2010, Table 7 / Figure 3 -- lightning earth-termination data

All tables are plain Python data so they can be edited by the user without
touching the calculation code.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# IEEE Std 80-2013 Table 1 -- Material constants
# ---------------------------------------------------------------------------
# key: (description, conductivity %, alpha_r 1/degC @20C, K0 degC,
#       Tm degC (fusing / max allowable), rho_r uohm-cm @20C,
#       TCAP J/(cm^3 . degC))

IEEE80_MATERIALS = {
    "cu_annealed": dict(
        name="Copper, annealed soft-drawn",
        conductivity=100.0, alpha_r=0.00393, K0=234.0, Tm=1083.0,
        rho_r=1.72, TCAP=3.42),
    "cu_hard": dict(
        name="Copper, commercial hard-drawn",
        conductivity=97.0, alpha_r=0.00381, K0=242.0, Tm=1084.0,
        rho_r=1.78, TCAP=3.42),
    "cu_hard_brazed": dict(
        name="Copper, commercial hard-drawn (brazed joints)",
        conductivity=97.0, alpha_r=0.00381, K0=242.0, Tm=250.0,
        rho_r=1.78, TCAP=3.42),
    "cu_hard_bolted": dict(
        name="Copper, commercial hard-drawn (bolted / pressure joints)",
        conductivity=97.0, alpha_r=0.00381, K0=242.0, Tm=250.0,
        rho_r=1.78, TCAP=3.42),
    "ccs_40": dict(
        name="Copper-clad steel wire (40 %)",
        conductivity=40.0, alpha_r=0.00378, K0=245.0, Tm=1084.0,
        rho_r=4.40, TCAP=3.85),
    "ccs_30": dict(
        name="Copper-clad steel wire (30 %)",
        conductivity=30.0, alpha_r=0.00378, K0=245.0, Tm=1084.0,
        rho_r=5.86, TCAP=3.85),
    "ccs_rod_20": dict(
        name="Copper-clad steel rod (20 %)",
        conductivity=20.0, alpha_r=0.00378, K0=245.0, Tm=1084.0,
        rho_r=8.62, TCAP=3.85),
    "al_ec": dict(
        name="Aluminium, EC grade",
        conductivity=61.0, alpha_r=0.00403, K0=228.0, Tm=657.0,
        rho_r=2.86, TCAP=2.56),
    "al_5005": dict(
        name="Aluminium, 5005 alloy",
        conductivity=53.5, alpha_r=0.00353, K0=263.0, Tm=652.0,
        rho_r=3.22, TCAP=2.60),
    "al_6201": dict(
        name="Aluminium, 6201 alloy",
        conductivity=52.5, alpha_r=0.00347, K0=268.0, Tm=654.0,
        rho_r=3.28, TCAP=2.60),
    "acs_wire": dict(
        name="Aluminium-clad steel wire",
        conductivity=20.3, alpha_r=0.00360, K0=258.0, Tm=657.0,
        rho_r=8.48, TCAP=3.58),
    "steel_1020": dict(
        name="Steel, 1020",
        conductivity=10.8, alpha_r=0.00160, K0=605.0, Tm=1510.0,
        rho_r=15.90, TCAP=3.28),
    "ss_clad_rod": dict(
        name="Stainless-clad steel rod",
        conductivity=9.8, alpha_r=0.00160, K0=605.0, Tm=1400.0,
        rho_r=17.50, TCAP=4.44),
    "zn_steel_rod": dict(
        name="Zinc-coated steel rod",
        conductivity=8.6, alpha_r=0.00320, K0=293.0, Tm=419.0,
        rho_r=20.10, TCAP=3.93),
    "ss_304": dict(
        name="Stainless steel 304",
        conductivity=2.4, alpha_r=0.00130, K0=749.0, Tm=1400.0,
        rho_r=72.00, TCAP=4.03),
}

# Recommended maximum temperature when joints limit the design
JOINT_TM_LIMITS = {
    "welded_exothermic": 1083.0,
    "brazed": 450.0,
    "pressure_bolted": 250.0,
}

# ---------------------------------------------------------------------------
# IEEE Std 80-2013 Table 7 -- typical soil resistivity ranges (ohm.m)
# ---------------------------------------------------------------------------
SOIL_TYPES = [
    dict(key="wet_organic", name="Wet organic soil", low=10.0, high=100.0, typical=10.0),
    dict(key="moist", name="Moist soil", low=100.0, high=1000.0, typical=100.0),
    dict(key="dry", name="Dry soil", low=1000.0, high=10000.0, typical=1000.0),
    dict(key="bedrock", name="Bedrock", low=10000.0, high=1e6, typical=10000.0),
    dict(key="clay", name="Clay / loam", low=5.0, high=200.0, typical=40.0),
    dict(key="sand_gravel", name="Sand and gravel", low=50.0, high=1000.0, typical=500.0),
    dict(key="limestone", name="Limestone", low=100.0, high=10000.0, typical=2000.0),
    dict(key="granite", name="Granite", low=1000.0, high=50000.0, typical=25000.0),
]

# Surface (finishing) layer materials -- IEEE Std 80-2013 Table 7
SURFACE_MATERIALS = [
    dict(key="crushed_rock_dry", name="Crushed rock, 19 mm (dry)", rho_dry=2.0e6, rho_wet=10000.0),
    dict(key="crushed_rock_wash", name="Washed granite, 19 mm", rho_dry=4.0e6, rho_wet=1300.0),
    dict(key="limestone_gravel", name="Limestone gravel, 25 mm", rho_dry=7.0e6, rho_wet=2000.0),
    dict(key="asphalt", name="Asphalt", rho_dry=2.0e6, rho_wet=10000.0),
    dict(key="concrete", name="Concrete", rho_dry=1.0e6, rho_wet=100.0),
    dict(key="none", name="No surface layer (native soil)", rho_dry=0.0, rho_wet=0.0),
]

# ---------------------------------------------------------------------------
# IEC 60364-5-54 / BS 7671 -- adiabatic k factors
# ---------------------------------------------------------------------------
# k = sqrt( Qc(B+20)/rho20 * ln(1 + (Tf-Ti)/(B+Ti)) )
# Values below are the tabulated results for the usual combinations.

K_FACTORS_SEPARATE = {  # PE not incorporated in a cable, initial temp 30 degC
    ("copper", "pvc70"):   dict(k=143, Ti=30, Tf=160, label="Cu, PVC 70 °C, S ≤ 300 mm²"),
    ("copper", "pvc90"):   dict(k=143, Ti=30, Tf=160, label="Cu, PVC 90 °C"),
    ("copper", "xlpe"):    dict(k=176, Ti=30, Tf=250, label="Cu, XLPE / EPR 90 °C"),
    ("copper", "rubber"):  dict(k=159, Ti=30, Tf=200, label="Cu, 60 °C rubber"),
    ("copper", "bare"):    dict(k=228, Ti=30, Tf=500, label="Cu, bare (no fire risk)"),
    ("aluminium", "pvc70"): dict(k=95, Ti=30, Tf=160, label="Al, PVC 70 °C"),
    ("aluminium", "xlpe"):  dict(k=116, Ti=30, Tf=250, label="Al, XLPE / EPR"),
    ("aluminium", "bare"):  dict(k=148, Ti=30, Tf=300, label="Al, bare"),
    ("steel", "pvc70"):    dict(k=52, Ti=30, Tf=160, label="Steel, PVC 70 °C"),
    ("steel", "xlpe"):     dict(k=64, Ti=30, Tf=250, label="Steel, XLPE / EPR"),
    ("steel", "bare"):     dict(k=82, Ti=30, Tf=500, label="Steel, bare"),
}

K_FACTORS_IN_CABLE = {  # PE as a core of a cable or bundled with cables
    ("copper", "pvc70"):   dict(k=115, Ti=70, Tf=160, label="Cu core, PVC 70 °C"),
    ("copper", "pvc90"):   dict(k=100, Ti=90, Tf=160, label="Cu core, PVC 90 °C"),
    ("copper", "xlpe"):    dict(k=143, Ti=90, Tf=250, label="Cu core, XLPE / EPR"),
    ("copper", "rubber"):  dict(k=141, Ti=60, Tf=200, label="Cu core, 60 °C rubber"),
    ("aluminium", "pvc70"): dict(k=76, Ti=70, Tf=160, label="Al core, PVC 70 °C"),
    ("aluminium", "xlpe"):  dict(k=94, Ti=90, Tf=250, label="Al core, XLPE / EPR"),
}

K_FACTORS_BURIED = {  # earthing conductor buried in soil, initial temp 20 degC
    ("copper", "bare"):     dict(k=159, Ti=20, Tf=500, label="Cu, bare, buried"),
    ("copper", "pvc"):      dict(k=143, Ti=20, Tf=160, label="Cu, PVC covered, buried"),
    ("aluminium", "bare"):  dict(k=105, Ti=20, Tf=300, label="Al, bare, buried"),
    ("steel", "bare"):      dict(k=58,  Ti=20, Tf=500, label="Galvanised steel, bare, buried"),
    ("steel", "pvc"):       dict(k=51,  Ti=20, Tf=160, label="Steel, PVC covered, buried"),
}

# IEC 60364-5-54 Table 54.1 -- minimum cross-section of buried earthing conductor
MIN_EARTHING_CONDUCTOR = {
    ("protected_corrosion", "protected_mech"): dict(copper=2.5, steel=10.0),
    ("protected_corrosion", "unprotected_mech"): dict(copper=16.0, steel=16.0),
    ("unprotected_corrosion", "any"): dict(copper=25.0, steel=50.0),
}

# IEC 62305-3 Table 7 -- minimum dimensions of earth electrodes
LPS_ELECTRODE_MIN = [
    dict(material="Copper", form="Solid round rod", dim="15 mm diameter"),
    dict(material="Copper", form="Stranded conductor", dim="50 mm²"),
    dict(material="Copper", form="Solid tape", dim="50 mm², 2 mm thick"),
    dict(material="Hot-dip galvanised steel", form="Solid round rod", dim="16 mm diameter"),
    dict(material="Hot-dip galvanised steel", form="Solid tape", dim="90 mm², 3 mm thick"),
    dict(material="Hot-dip galvanised steel", form="Pipe", dim="25 mm dia., 2 mm wall"),
    dict(material="Stainless steel", form="Solid round rod", dim="15 mm diameter"),
    dict(material="Stainless steel", form="Solid tape", dim="100 mm², 2 mm thick"),
]

# IEC 62305-3 Figure 3 -- minimum length l1 (m) of the earth electrode
# rows = LPS class, columns = soil resistivity break-points (ohm.m)
LPS_L1_RHO = [500.0, 1000.0, 2000.0, 3000.0]
LPS_L1 = {
    "I":   [5.0, 20.0, 50.0, 80.0],
    "II":  [5.0, 10.0, 30.0, 45.0],
    "III": [5.0, 5.0, 5.0, 5.0],
    "IV":  [5.0, 5.0, 5.0, 5.0],
}

# ---------------------------------------------------------------------------
# Standard conductor / electrode sizes
# ---------------------------------------------------------------------------
STD_AREAS_MM2 = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185,
                 240, 300, 400, 500, 630, 800, 1000]

STD_AWG = [
    dict(awg="8", mm2=8.37), dict(awg="6", mm2=13.30), dict(awg="4", mm2=21.15),
    dict(awg="2", mm2=33.62), dict(awg="1/0", mm2=53.49), dict(awg="2/0", mm2=67.43),
    dict(awg="3/0", mm2=85.01), dict(awg="4/0", mm2=107.2),
    dict(awg="250 kcmil", mm2=126.7), dict(awg="350 kcmil", mm2=177.3),
    dict(awg="500 kcmil", mm2=253.4), dict(awg="750 kcmil", mm2=380.0),
]

STD_TAPES = [  # width x thickness (mm)
    dict(label="20 × 3", w=20, t=3, area=60), dict(label="25 × 3", w=25, t=3, area=75),
    dict(label="25 × 4", w=25, t=4, area=100), dict(label="30 × 3", w=30, t=3, area=90),
    dict(label="40 × 4", w=40, t=4, area=160), dict(label="50 × 6", w=50, t=6, area=300),
]

STD_RODS = [  # nominal rod diameters (mm)
    dict(label="12.7 mm (1/2\")", d=12.7), dict(label="14.2 mm", d=14.2),
    dict(label="16 mm (5/8\")", d=16.0), dict(label="17.2 mm", d=17.2),
    dict(label="19.0 mm (3/4\")", d=19.0), dict(label="20 mm", d=20.0),
    dict(label="25.4 mm (1\")", d=25.4),
]


def material_list():
    """Return the material table as a list of dicts for the UI."""
    out = []
    for key, m in IEEE80_MATERIALS.items():
        d = dict(m)
        d["key"] = key
        out.append(d)
    return out


def area_from_diameter(d_mm: float) -> float:
    """Cross-sectional area (mm²) of a round conductor of diameter d (mm)."""
    from math import pi
    return pi * d_mm ** 2 / 4.0


def diameter_from_area(a_mm2: float) -> float:
    """Diameter (mm) of a round conductor of area a (mm²)."""
    from math import pi, sqrt
    return 2.0 * sqrt(a_mm2 / pi)


def next_standard_area(a_mm2: float):
    """Smallest standard metric area not less than a_mm2 (None if off-scale)."""
    for a in STD_AREAS_MM2:
        if a >= a_mm2:
            return a
    return None
