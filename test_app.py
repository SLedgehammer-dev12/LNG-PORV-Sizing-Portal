"""
Unit Verification Test Suite for LNG PSV Relief Valve Sizing Application
Tests COSTALD method, relief load decomposition, API 520 subcritical sizing, and PSV manufacturer search.
"""

import os
import pytest
from lng_thermo import calculate_costald_density, calculate_vapor_density
from psv_sizing import calculate_relieving_loads, calculate_nfpa59a_air_equivalent, calculate_api520_subcritical_orifice_area, evaluate_valve_matrix
from psv_database import search_matching_valves

def test_costald_density():
    comp = {'CH4': 90.5, 'C2H6': 5.5, 'C3H8': 2.5, 'iC4H10': 0.5, 'nC4H10': 0.5, 'N2': 0.5}
    res = calculate_costald_density(comp, temperature_k=118.15)
    
    assert res['density_kg_m3'] > 440.0 and res['density_kg_m3'] < 500.0, "LNG density should be in physical cryogenic range ~470 kg/m3"
    assert res['molar_mass_g_mol'] > 16.0 and res['molar_mass_g_mol'] < 20.0, "Molar mass should be ~17.5 g/mol"

def test_relieving_loads():
    loads = calculate_relieving_loads(
        q_fill_m3_h=10000.0,
        rho_lng_kg_m3=471.0,
        rho_v_kg_m3=1.95,
        flash_pct=2.0,
        w_bog_kg_h=1570.0
    )
    
    assert loads['w_disp_kg_h'] == 19500.0
    assert loads['w_flash_kg_h'] == 94200.0
    assert loads['w_bog_kg_h'] == 1570.0
    assert loads['w_total_kg_h'] == 115270.0
    assert abs(loads['w_total_kg_s'] - 32.01944) < 0.1

def test_nfpa59a_air_equivalent():
    # 32.01944 kg/s -> ~79,258 m3/h of air
    q_a = calculate_nfpa59a_air_equivalent(32.01944, temperature_k=118.15, Z=0.98, M_g_mol=16.043)
    assert q_a > 75000.0 and q_a < 83000.0

def test_api520_subcritical_orifice_area():
    # Min Patm = 906.03 mbar_a -> P1 = 117.003 kPa_a
    res = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=115270.0 / 3,
        P1_kPa_a=117.003,
        P2_kPa_a=90.603,
        temperature_k=118.15,
        M_g_mol=16.043,
        Z=0.98,
        k=1.31
    )
    assert res['is_subcritical'] == True
    # Area around 154,500 mm2 per valve
    assert res['A_o_mm2'] > 140000.0 and res['A_o_mm2'] < 170000.0

def test_psv_database_matching():
    matched = search_matching_valves(req_orifice_area_mm2=154500.0, required_air_capacity_m3_h=26419.5, P1_kPa_a=117.003)
    assert len(matched) > 0
    # Anderson Greenwood 18"x20" should be recommended
    top_matches = [m for m in matched if "18\" x 20\"" in m['dn_size']]
    assert len(top_matches) > 0
    assert top_matches[0]['coverage_pct'] > 120.0

def test_run_app_path_resolution(tmp_path, monkeypatch):
    """ Test run_app resolve_path in both standard and PyInstaller sys._MEIPASS frozen modes. """
    import sys
    from run_app import resolve_path
    
    # 1. Standard mode
    standard_path = resolve_path("app.py")
    assert standard_path.endswith("app.py")
    
    # 2. Simulated PyInstaller frozen mode
    fake_meipass = str(tmp_path / "fake_meipass")
    monkeypatch.setattr(sys, "_MEIPASS", fake_meipass, raising=False)
    
    frozen_path = resolve_path("app.py")
    assert frozen_path == os.path.join(fake_meipass, "app.py")

def test_psv_database_frozen_path(tmp_path, monkeypatch):
    """ Test psv_database JSON loading under simulated PyInstaller sys._MEIPASS frozen environment. """
    import sys
    import json
    import psv_database
    
    # Create fake psv_database.json inside temporary meipass directory
    fake_meipass = tmp_path / "meipass_test"
    fake_meipass.mkdir()
    fake_db_file = fake_meipass / "psv_database.json"
    dummy_data = [{"id": "TEST_VALVE", "manufacturer": "TestCorp", "series": "Series 100", "type": "PORV", "dn_size": "10x12", "orifice_area_mm2": 50000.0, "discharge_coeff_kd": 0.85, "cryogenic_certified": True}]
    fake_db_file.write_text(json.dumps(dummy_data), encoding="utf-8")
    
    # Simulate PyInstaller frozen environment
    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)
    
    db_items = psv_database.load_psv_database()
    assert len(db_items) == 1
    assert db_items[0]["manufacturer"] == "TestCorp"

def test_module_imports_for_executability():
    """ Verify all application modules import cleanly for PyInstaller packaging. """
    import run_app
    import app
    import lng_thermo
    import psv_sizing
    import psv_database
    import report_generator
    import unit_converter
    
    assert hasattr(run_app, 'resolve_path')
    assert hasattr(app, 'st')
    assert hasattr(lng_thermo, 'calculate_costald_density')
    assert hasattr(psv_sizing, 'calculate_api520_subcritical_orifice_area')
    assert hasattr(psv_database, 'search_matching_valves')
    assert hasattr(report_generator, 'generate_html_report')
    assert hasattr(unit_converter, 'convert_pressure_to_mbar')

if __name__ == '__main__':
    pytest.main(['-v', 'test_app.py'])

