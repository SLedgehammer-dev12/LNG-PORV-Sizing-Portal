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
    # Area per valve around ~45,337 mm2 (total for 3 valves = ~136,000 mm2)
    assert res['A_o_mm2'] > 40000.0 and res['A_o_mm2'] < 55000.0

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

def test_peng_robinson_and_srk_vle_flash():
    """ Test Peng-Robinson (PR) and SRK EOS Z-factor, dynamic k_mix(T,P), and Rachford-Rice VLE Flash calculations. """
    from vle_thermo import calculate_two_phase_vle_flash, calculate_eos_mixture_properties
    
    sample_comp = {'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 3.0, 'N2': 2.0}
    
    # 1. PR EOS Test
    pr_res = calculate_two_phase_vle_flash(sample_comp, temperature_k=118.15, pressure_kPa_a=117.0, eos='PR')
    assert 0.90 < pr_res['Z_gas'] < 1.0, f"PR Z_gas should be ~0.96, got {pr_res['Z_gas']}"
    assert 1.25 < pr_res['k_mix'] < 1.55, f"Dynamic k_mix at 118K should be ~1.46, got {pr_res['k_mix']}"
    assert pr_res['rho_v_kg_m3'] > 1.5, "Vapor density should be > 1.5 kg/m3"
    
    # 2. SRK EOS Test
    srk_res = calculate_two_phase_vle_flash(sample_comp, temperature_k=118.15, pressure_kPa_a=117.0, eos='SRK')
    assert 0.90 < srk_res['Z_gas'] < 1.0, f"SRK Z_gas should be ~0.96, got {srk_res['Z_gas']}"
    assert 1.25 < srk_res['k_mix'] < 1.55, f"SRK dynamic k_mix should be ~1.46, got {srk_res['k_mix']}"

    # 3. HEOS (GERG-2008) Test
    heos_res = calculate_two_phase_vle_flash(sample_comp, temperature_k=118.15, pressure_kPa_a=117.0, eos='HEOS')
    assert 0.90 < heos_res['Z_gas'] < 1.0, f"HEOS Z_gas should be ~0.94, got {heos_res['Z_gas']}"
    assert 1.25 < heos_res['k_mix'] < 1.55, f"HEOS dynamic k_mix should be ~1.40, got {heos_res['k_mix']}"

def test_vle_flash_bisection_and_bubble_point():
    """ Test that V/F flash ratio does not lock at 50% and subcooled liquid (v_frac=0) computes bubble-point y_vap. """
    from vle_thermo import calculate_two_phase_vle_flash
    sample_comp = {'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 3.0, 'N2': 2.0}
    
    # Subcooled condition: Low temperature T=100K -> v_frac should be 0.0
    sub_res = calculate_two_phase_vle_flash(sample_comp, temperature_k=100.0, pressure_kPa_a=150.0, eos='PR')
    assert sub_res['v_frac_VF'] == 0.0, f"Expected v_frac=0 at 100K, got {sub_res['v_frac_VF']}"
    assert sub_res['y_vapor']['N2'] > sub_res['x_liquid']['N2'], "Bubble point vapor N2 fraction should be enriched vs liquid"
    assert sum(sub_res['y_vapor'].values()) == pytest.approx(1.0, abs=1e-4)

def test_fire_scenario_load():
    """ Test API 520 fire scenario heat absorption and relieving load. """
    from psv_sizing import calculate_fire_scenario_load
    # Insulated tank (F=0.15)
    res = calculate_fire_scenario_load(wetted_area_m2=1200.0, insulation_factor_F=0.15, latent_heat_kJ_kg=510.0)
    assert res['q_fire_kW'] > 3000.0 and res['q_fire_kW'] < 5000.0, f"Fire heat input should be ~3600 kW for F=0.15, got {res['q_fire_kW']}"
    assert res['w_fire_kg_h'] > 20000.0 and res['w_fire_kg_h'] < 35000.0, "Fire W should be ~25000 kg/h"
    assert abs(res['w_fire_kg_s'] - res['w_fire_kg_h'] / 3600.0) < 0.01
    # Uninsulated tank (F=1.0) — much higher heat input
    res_unins = calculate_fire_scenario_load(wetted_area_m2=1200.0, insulation_factor_F=1.0, latent_heat_kJ_kg=510.0)
    assert res_unins['q_fire_kW'] > 20000.0, "Uninsulated fire case should have much higher heat input"
    assert res_unins['w_fire_kg_h'] > res['w_fire_kg_h'] * 3.0, "Uninsulated W should be > 3x insulated"

def test_fire_case_api520_orifice():
    """ Test API 520 orifice area calculation at fire case conditions. """
    from psv_sizing import calculate_api520_subcritical_orifice_area
    # Fire case: higher temperature, K_d=1.0
    res = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=25000.0, P1_kPa_a=117.0, P2_kPa_a=90.6,
        temperature_k=173.15, M_g_mol=16.0, Z=1.0, k=1.31, K_d=1.0
    )
    assert res['A_o_mm2'] > 0, "Orifice area should be positive"
    # With K_d=1.0, area should be smaller than K_d=0.85 (higher discharge = smaller area needed)
    res_kd085 = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=25000.0, P1_kPa_a=117.0, P2_kPa_a=90.6,
        temperature_k=173.15, M_g_mol=16.0, Z=1.0, k=1.31, K_d=0.85
    )
    assert res['A_o_mm2'] < res_kd085['A_o_mm2'], f"K_d=1.0 area ({res['A_o_mm2']:.0f}) should be < K_d=0.85 area ({res_kd085['A_o_mm2']:.0f})"

def test_bor_tank_bog_calculation():
    """ Test automatic BOG calculation from tank volume and BOR. """
    from psv_sizing import calculate_bor_tank_bog
    res = calculate_bor_tank_bog(tank_volume_m3=160000.0, lng_density_kg_m3=471.0, bor_pct_per_day=0.10)
    assert res['w_bog_kg_h'] > 3000.0 and res['w_bog_kg_h'] < 3200.0, f"Expected ~3140 kg/h, got {res['w_bog_kg_h']}"
    # Double BOR should double W_bog
    res2 = calculate_bor_tank_bog(tank_volume_m3=160000.0, lng_density_kg_m3=471.0, bor_pct_per_day=0.20)
    assert abs(res2['w_bog_kg_h'] - 2.0 * res['w_bog_kg_h']) < 0.01

def test_vle_flash_NR_no_50pct_lock():
    """ Test that NR solver does not lock at 50% V/F for realistic LNG conditions. """
    from vle_thermo import calculate_two_phase_vle_flash
    comp = {'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 3.0, 'N2': 2.0}
    # At 118K — should NOT lock at exactly 50% (the old NR fallback bug)
    res = calculate_two_phase_vle_flash(comp, temperature_k=118.15, pressure_kPa_a=117.0, eos='PR')
    assert res['v_frac_VF'] != pytest.approx(0.5, abs=0.01), f"V/F should NOT lock at 50%, got {res['v_frac_VF']:.4f}"
    assert 0.0 <= res['v_frac_VF'] <= 1.0, "V/F must be in [0, 1]"
    # At 250K — should be >50% vapor
    res_high = calculate_two_phase_vle_flash(comp, temperature_k=250.0, pressure_kPa_a=117.0, eos='PR')
    assert res_high['v_frac_VF'] > 0.5, f"V/F should be >50% at high temp, got {res_high['v_frac_VF']:.4f}"
    # Verify vapor composition is physically reasonable
    assert 'CH4' in res['y_vapor'], "Vapor phase must contain methane"
    assert sum(res['y_vapor'].values()) == pytest.approx(1.0, abs=1e-4), "Vapor fractions must sum to 1"

def test_module_imports_for_executability():
    """ Verify all application modules import cleanly for PyInstaller packaging. """
    import run_app
    import lng_thermo
    import vle_thermo
    import psv_sizing
    import psv_database
    import report_generator
    import unit_converter
    
    assert hasattr(run_app, 'resolve_path')
    assert hasattr(lng_thermo, 'calculate_costald_density')
    assert hasattr(vle_thermo, 'calculate_two_phase_vle_flash')
    assert hasattr(psv_sizing, 'calculate_api520_subcritical_orifice_area')
    assert hasattr(psv_database, 'search_matching_valves')
    assert hasattr(report_generator, 'generate_html_report')
    assert hasattr(unit_converter, 'convert_pressure_to_mbar')


def test_version_checker():
    """ Verify version checker metadata and update checker functions. """
    from version_checker import get_version_info, check_for_updates, parse_version_tuple
    info = get_version_info()
    assert info['current_version'] == '1.2.0'
    assert 'build_date' in info
    assert len(info['changelog']) > 0
    
    assert parse_version_tuple('1.2.0') == (1, 2, 0)
    assert parse_version_tuple('v2.0.5') == (2, 0, 5)
    
    upd = check_for_updates(timeout_sec=0.5)
    assert 'current_version' in upd
    assert 'status_message' in upd


def test_bubble_point_temperature_calculation():
    """ Verify calculation of mixture bubble point temperature. """
    from vle_thermo import calculate_bubble_point_temperature
    comp = {'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 3.0, 'N2': 2.0}
    t_bp = calculate_bubble_point_temperature(comp, pressure_kPa_a=117.0, eos='PR')
    assert 100.0 < t_bp < 120.0, f"Expected bubble point around 108 K, got {t_bp}"


def test_valves_above_90_percent_mode():
    """ Verify show_all_above_90 includes borderline 90-100% valves such as 16\"x18\". """
    from psv_database import search_matching_valves
    # With a required capacity of ~26,400 m3/h at 117 kPa_a, 16"x18" has ~96% coverage
    all_valves = search_matching_valves(
        req_orifice_area_mm2=154500.0,
        required_air_capacity_m3_h=26419.5,
        P1_kPa_a=117.003,
        show_all_above_90=True
    )
    valves_90 = [v for v in all_valves if v['coverage_pct'] >= 90.0]
    assert len(valves_90) > 0
    # 16"x18" valve should be present and marked as boundary / borderline
    has_16x18 = any("16\" x 18\"" in v['dn_size'] for v in valves_90)
    assert has_16x18, "16x18 inch valve should be included when show_all_above_90=True"


def test_isenthalpic_ph_flash():
    """ Verify isenthalpic PH-flash solver produces valid thermodynamic flash and temperature. """
    from vle_thermo import calculate_isenthalpic_flash
    comp = {'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 3.0, 'N2': 2.0}
    # Throttling from 600 kPa_a (5 bar_g) at 115 K to tank at 120 kPa_a
    res = calculate_isenthalpic_flash(
        comp,
        t_feed_k=115.0,
        p_feed_kPa_a=600.0,
        p_flash_kPa_a=120.0,
        eos='PR'
    )
    assert res['converged'] == True
    assert 0.0 <= res['flash_pct'] <= 100.0
    assert 95.0 <= res['T_flash_K'] <= 130.0


def test_valve_database_expanded_manufacturers():
    """ Verify database contains expanded manufacturer pool and wide range of sizes. """
    from psv_database import load_psv_database
    valves = load_psv_database()
    assert len(valves) >= 90, f"Expected at least 90 valves, got {len(valves)}"
    
    manufacturers = set(v['manufacturer'] for v in valves)
    expected_manufacturers = [
        "Fukui Seisakusho (Fukui Valve)",
        "Birkett (Emerson)",
        "Parker Bestobell",
        "Herose",
        "Leser",
        "Anderson Greenwood (Emerson)",
        "Baker Hughes (Consolidated)",
        "Curtiss-Wright (Farris)",
        "Crosby (Emerson)",
        "Mercer Valve",
        "Bopp & Reuther",
        "Weir (Sebim)"
    ]
    for m in expected_manufacturers:
        assert m in manufacturers, f"Expected manufacturer '{m}' in database"
        
    sizes = set(v['dn_size'] for v in valves)
    for expected_size in ['2" x 3"', '4" x 6"', '6" x 8"', '8" x 10"', '12" x 16"', '16" x 18"', '18" x 20"']:
        assert any(expected_size in s for s in sizes), f"Expected size {expected_size} in database"


def test_valve_coverage_cap_200_percent():
    """ Verify that search_matching_valves strictly enforces max_coverage_pct=200.0 to prevent 500-800% oversized valves. """
    from psv_database import search_matching_valves
    
    # Moderate flow rate: 5,000 m3/h
    matches = search_matching_valves(
        req_orifice_area_mm2=25000.0,
        required_air_capacity_m3_h=5000.0,
        P1_kPa_a=117.003,
        max_coverage_pct=200.0,
        show_all_above_90=True
    )
    assert len(matches) > 0
    # No valve should have coverage > 200%
    for v in matches:
        assert v['coverage_pct'] <= 200.0, f"Valve {v['id']} has coverage {v['coverage_pct']:.1f}% > 200%"
        assert v['coverage_pct'] >= 90.0, f"Valve {v['id']} has coverage {v['coverage_pct']:.1f}% < 90%"


def test_small_flow_valve_selection_and_oversized_status():
    """ Verify small flow rates match 2x3, 3x4, or 4x6 valves and oversized status is properly tagged in matrix. """
    from psv_sizing import evaluate_valve_matrix
    from psv_database import search_matching_valves
    
    # Small relief demand: 1,500 m3/h air
    matches = search_matching_valves(
        req_orifice_area_mm2=8000.0,
        required_air_capacity_m3_h=1500.0,
        P1_kPa_a=117.003,
        max_coverage_pct=200.0,
        show_all_above_90=True
    )
    assert len(matches) > 0
    # The selected valves should be compact (4"x6" or smaller)
    for v in matches:
        assert any(sz in v['dn_size'] for sz in ['2" x 3"', '3" x 4"', '4" x 6"']), f"Unexpected large size {v['dn_size']} for small flow"
        assert v['coverage_pct'] <= 200.0

    # Test matrix evaluation tags oversized models (>200%)
    matrix = evaluate_valve_matrix(q_a_per_valve_m3_h=1500.0, P1_kPa_a=117.003, P2_kPa_a=90.603)
    oversized = [m for m in matrix if m['coverage_pct'] > 200.0]
    assert len(oversized) > 0
    assert oversized[0]['status_code'] == 'OVERSIZED'
    assert "AŞIRI BÜYÜK" in oversized[0]['status']


if __name__ == '__main__':
    pytest.main(['-v', 'test_app.py'])


