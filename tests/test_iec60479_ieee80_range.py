"""BS EN 50522:2022 prospective limit, Formula (A.3) with Tables B.1 and B.4
(1.3.5; 1.3.4 used the 2010 method, I_B = U_Tp/Z_T), and the IEEE 80-2013
16.7 validity warnings (1.3.4)."""
from earthsys import standards, ieee80


def test_body_impedance_table_points_and_interpolation():
    assert standards.en50522_body_impedance(200) == 1275
    assert abs(standards.en50522_body_impedance(220) - 1235) < 1e-9
    assert standards.en50522_body_impedance(10) == 3250
    assert standards.en50522_body_impedance(900) == 775


def test_uvtp_worked_values():
    f = standards.en50522_prospective_touch_limit
    assert round(f(0.5, 2500)["U_vTp"]) == 1175     # 225 + 0.200 x 4750
    assert round(f(0.5, 100)["U_vTp"]) == 455       # 225 + 0.200 x 1150
    assert round(f(0.5, 3000)["U_vTp"]) == 1325
    assert round(f(0.05, 100)["U_vTp"]) == 1760     # 725 + 0.900 x 1150
    assert round(f(0.1, 0, R_F1=0)["U_vTp"]) == 655


def test_cross_check_reports_uvtp_not_mesh_over_utp():
    g = ieee80.GridGeometry(Lx=70, Ly=70, D=7, h=0.5)
    r = ieee80.design(400, g, 1.908, rho_s=2500, hs=0.102, ts=0.5)
    xc = r["en50522"]
    assert "mesh_vs_UTp" not in xc
    assert round(xc["U_vTp"]) == 1175 and "U_vTp" in xc["note"]


def test_ieee80_16_7_range_warnings():
    ok = ieee80.design(400, ieee80.GridGeometry(Lx=70, Ly=70, D=7), 1.908)
    assert not ok["warnings"]
    big = ieee80.design(100, ieee80.GridGeometry(Lx=150, Ly=100, D=10), 5.0)
    assert any("10 000" in w for w in big["warnings"])
    wide = ieee80.design(100, ieee80.GridGeometry(Lx=50, Ly=50, D=25), 5.0)
    assert any("2.5–22.5" in w for w in wide["warnings"])
    irr = ieee80.design(100, ieee80.GridGeometry(Lx=50, Ly=50, D=5, shape="irregular"), 5.0)
    assert any("irregular" in w for w in irr["warnings"])
