"""
Unit Verification Test Suite for LNG PSV Relief Valve Sizing Application
Tests COSTALD method, relief load decomposition, API 520 subcritical sizing,
API 520 physical valve capacity model, report generation, and PSV manufacturer search.
"""

import math
import os

import pytest

from lng_thermo import calculate_costald_density
from psv_database import load_psv_database, search_matching_valves, validate_psv_database
from psv_sizing import (
    AIR_STD_RHO_KG_M3,
    calculate_api520_subcritical_orifice_area,
    calculate_fire_scenario_load,
    calculate_nfpa59a_air_equivalent,
    calculate_relieving_loads,
    calculate_valve_air_capacity_m3_h,
    calculate_valve_capacity,
    evaluate_valve_matrix,
)

DEFAULT_COMP = {'CH4': 90.5, 'C2H6': 5.5, 'C3H8': 2.5, 'iC4H10': 0.5, 'nC4H10': 0.5, 'N2': 0.5}
P1_DEFAULT = 117.003   # kPa_a (P_set 240 mbar_g + 10% OP + P_atm_min 906.03 mbar_a)
P2_DEFAULT = 90.603    # kPa_a (P_atm_min)


def _default_scenario():
    """Default 2% flash scenario used across sizing tests."""
    from vle_thermo import calculate_two_phase_vle_flash
    vle = calculate_two_phase_vle_flash(DEFAULT_COMP, temperature_k=118.15, pressure_kPa_a=114.6, eos='PR')
    loads = calculate_relieving_loads(10000.0, 471.0, vle['rho_v_kg_m3'], 2.0, 1570.0)
    return loads, vle['Z_gas'], vle['k_mix'], vle['M_vapor_g_mol']


def test_costald_density():
    res = calculate_costald_density(DEFAULT_COMP, temperature_k=118.15)

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
    # 32.01944 kg/s -> ~79,700 m3/h of air at 15 degC (API 520 equivalent orifice method)
    q_a = calculate_nfpa59a_air_equivalent(
        32.01944, temperature_k=118.15, Z=0.98, M_g_mol=16.043,
        k=1.31, K_d=0.85, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT
    )
    assert q_a > 70000.0 and q_a < 90000.0, f"Q_a out of range: {q_a}"


def test_nfpa59a_air_equivalent_matches_required_area_capacity():
    """Q_a must equal the API 520 air capacity of the required gas orifice area."""
    loads, Z, k, M = _default_scenario()
    q_a = calculate_nfpa59a_air_equivalent(
        loads['w_total_kg_s'], temperature_k=118.15, Z=Z, M_g_mol=M,
        k=k, K_d=0.85, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT
    )
    req = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=loads['w_total_kg_h'], P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT,
        temperature_k=118.15, M_g_mol=M, Z=Z, k=k, K_d=0.85
    )
    cap = calculate_valve_air_capacity_m3_h(req['A_o_mm2'], P1_DEFAULT, P2_DEFAULT, K_d=0.85)
    assert cap == pytest.approx(q_a, rel=1e-6)


def test_api520_subcritical_orifice_area():
    res = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=115270.0 / 3,
        P1_kPa_a=P1_DEFAULT,
        P2_kPa_a=P2_DEFAULT,
        temperature_k=118.15,
        M_g_mol=16.043,
        Z=0.98,
        k=1.31
    )
    assert res['is_subcritical']
    # Area per valve around ~45,000 mm2 for the 2% flash default scenario
    assert res['A_o_mm2'] > 40000.0 and res['A_o_mm2'] < 55000.0


def test_valve_capacity_is_api520_physical():
    """A valve's air capacity must scale linearly with area and follow API 520 (no calibration)."""
    cap = calculate_valve_capacity(148500.0, P1_DEFAULT, P2_DEFAULT, K_d=0.85)
    assert 80000.0 < cap < 100000.0, f"16x18 physical air capacity should be ~88,000 m3/h, got {cap}"
    # Linear in area
    assert calculate_valve_capacity(297000.0, P1_DEFAULT, P2_DEFAULT, K_d=0.85) == pytest.approx(2.0 * cap, rel=1e-9)
    # Linear in Kd
    assert calculate_valve_capacity(148500.0, P1_DEFAULT, P2_DEFAULT, K_d=0.85 * 2) == pytest.approx(2.0 * cap, rel=1e-9)
    # Higher P1 -> higher capacity
    assert calculate_valve_capacity(148500.0, P1_DEFAULT * 1.2, P2_DEFAULT, K_d=0.85) > cap


def test_valve_capacity_zero_p2_is_critical():
    cap_crit = calculate_valve_air_capacity_m3_h(50000.0, 117.003, 0.0, K_d=0.85)
    cap_sub = calculate_valve_air_capacity_m3_h(50000.0, 117.003, 90.603, K_d=0.85)
    assert cap_crit > cap_sub > 0.0


def test_psv_database_matching_physical_model():
    """With the physical API 520 model, 16x18 is oversized and 10x12 is the smallest adequate valve."""
    loads, Z, k, M = _default_scenario()
    q_a_per_valve = calculate_nfpa59a_air_equivalent(
        loads['w_total_kg_s'], temperature_k=118.15, Z=Z, M_g_mol=M,
        k=k, K_d=0.85, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT
    ) / 3.0
    matched = search_matching_valves(
        required_air_capacity_m3_h=q_a_per_valve,
        P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT, show_all_above_90=True
    )
    assert len(matched) > 0
    # 16"x18" (148,500 mm2) is ~338% of required -> must be filtered out (>200%)
    assert not any('16" x 18"' in m['dn_size'] for m in matched), "16x18 should be oversized/filtered"
    # 10"x12" must be the smallest adequate model (~130%)
    ten_twelve = [m for m in matched if '10" x 12"' in m['dn_size'] and m['coverage_pct'] >= 100.0]
    assert len(ten_twelve) > 0
    assert 100.0 <= min(m['coverage_pct'] for m in ten_twelve) <= 200.0


def test_matrix_marks_16x18_oversized():
    loads, Z, k, M = _default_scenario()
    q_a_per_valve = calculate_nfpa59a_air_equivalent(
        loads['w_total_kg_s'], temperature_k=118.15, Z=Z, M_g_mol=M,
        k=k, K_d=0.85, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT
    ) / 3.0
    matrix = evaluate_valve_matrix(q_a_per_valve_m3_h=q_a_per_valve, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT)
    oversized = [m for m in matrix if '16" x 18"' in m['size_name']]
    assert len(oversized) > 0
    assert all(m['status_code'] == 'OVERSIZED' for m in oversized), "16x18 must be tagged OVERSIZED"
    assert all(m['coverage_pct'] > 200.0 for m in oversized)


def test_matrix_kd_override_applied():
    """Fire scenario passes K_d=1.0; it must actually change the computed capacities."""
    loads, Z, k, M = _default_scenario()
    q_a_per_valve = calculate_nfpa59a_air_equivalent(
        loads['w_total_kg_s'], temperature_k=118.15, Z=Z, M_g_mol=M,
        k=k, K_d=0.85, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT
    ) / 3.0
    m_kd = evaluate_valve_matrix(q_a_per_valve_m3_h=q_a_per_valve, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT, K_d=1.0)
    m_catalog = evaluate_valve_matrix(q_a_per_valve_m3_h=q_a_per_valve, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT, K_d=None)
    cap_kd = next(m['air_capacity_m3_h'] for m in m_kd if '10" x 12"' in m['size_name'])
    cap_cat = next(m['air_capacity_m3_h'] for m in m_catalog if '10" x 12"' in m['size_name'])
    assert cap_kd > cap_cat, "K_d=1.0 must yield higher capacity than catalog Kd"


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


def test_run_app_find_free_port():
    from run_app import find_free_port
    port = find_free_port(8501, max_tries=20)
    assert isinstance(port, int) and 8501 <= port <= 8520


def test_psv_database_frozen_path(tmp_path, monkeypatch):
    """ Test psv_database JSON loading under simulated PyInstaller sys._MEIPASS frozen environment. """
    import json
    import sys

    import psv_database

    # Create fake psv_database.json inside temporary meipass directory
    fake_meipass = tmp_path / "meipass_test"
    fake_meipass.mkdir()
    fake_db_file = fake_meipass / "psv_database.json"
    dummy_data = [{
        "id": "TEST_VALVE", "manufacturer": "TestCorp", "series": "Series 100", "type": "PORV",
        "dn_size": "10x12", "orifice_area_mm2": 50000.0, "discharge_coeff_kd": 0.85, "cryogenic_certified": True
    }]
    fake_db_file.write_text(json.dumps(dummy_data), encoding="utf-8")

    # Simulate PyInstaller frozen environment
    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

    db_items = psv_database.load_psv_database()
    assert len(db_items) == 1
    assert db_items[0]["manufacturer"] == "TestCorp"


def test_psv_database_schema_validation():
    """Corrupted entries must be rejected without crashing the loader."""
    raw = [
        {"id": "OK", "manufacturer": "M", "series": "S", "type": "T", "dn_size": "2x3",
         "orifice_area_mm2": 1000.0, "discharge_coeff_kd": 0.85, "cryogenic_certified": True},
        {"id": "NEG_AREA", "manufacturer": "M", "series": "S", "type": "T", "dn_size": "2x3",
         "orifice_area_mm2": -5.0, "discharge_coeff_kd": 0.85, "cryogenic_certified": True},
        {"id": "MISSING_FIELD", "manufacturer": "M"},
        {"id": "BAD_KD", "manufacturer": "M", "series": "S", "type": "T", "dn_size": "2x3",
         "orifice_area_mm2": 1000.0, "discharge_coeff_kd": 1.5, "cryogenic_certified": True},
        {"id": "OK", "manufacturer": "M", "series": "S", "type": "T", "dn_size": "2x3",
         "orifice_area_mm2": 1000.0, "discharge_coeff_kd": 0.85, "cryogenic_certified": True},
    ]
    valid, errors = validate_psv_database(raw)
    assert len(valid) == 1
    assert valid[0]['id'] == 'OK'
    assert len(errors) == 4


def test_psv_database_missing_file_returns_empty(tmp_path, monkeypatch):
    import sys

    import psv_database
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "nonexistent"), raising=False)
    assert psv_database.load_psv_database() == []


def test_peng_robinson_and_srk_vle_flash():
    """ Test Peng-Robinson (PR) and SRK EOS Z-factor, dynamic k_mix(T,P), and Rachford-Rice VLE Flash calculations. """
    from vle_thermo import calculate_two_phase_vle_flash

    sample_comp = {'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 3.0, 'N2': 2.0}

    # 1. PR EOS Test
    pr_res = calculate_two_phase_vle_flash(sample_comp, temperature_k=118.15, pressure_kPa_a=117.0, eos='PR')
    assert 0.90 < pr_res['Z_gas'] < 1.0, f"PR Z_gas should be ~0.96, got {pr_res['Z_gas']}"
    assert 1.28 < pr_res['k_mix'] < 1.45, f"Real-gas k_mix at 118K should be ~1.36, got {pr_res['k_mix']}"
    assert pr_res['rho_v_kg_m3'] > 1.5, "Vapor density should be > 1.5 kg/m3"
    assert pr_res['converged'] is True

    # 2. SRK EOS Test
    srk_res = calculate_two_phase_vle_flash(sample_comp, temperature_k=118.15, pressure_kPa_a=117.0, eos='SRK')
    assert 0.90 < srk_res['Z_gas'] < 1.0, f"SRK Z_gas should be ~0.96, got {srk_res['Z_gas']}"
    assert 1.28 < srk_res['k_mix'] < 1.45, f"SRK dynamic k_mix should be ~1.36, got {srk_res['k_mix']}"

    # 3. HEOS (GERG-2008) Test
    heos_res = calculate_two_phase_vle_flash(sample_comp, temperature_k=118.15, pressure_kPa_a=117.0, eos='HEOS')
    assert 0.90 < heos_res['Z_gas'] < 1.0, f"HEOS Z_gas should be ~0.94, got {heos_res['Z_gas']}"
    assert 1.28 < heos_res['k_mix'] < 1.45, f"HEOS dynamic k_mix should be ~1.37, got {heos_res['k_mix']}"


def test_ideal_cp_cryogenic_methane():
    """Aly-Lee polynomial under-predicts methane Cp0 at 118 K; CoolProp ideal curve must be used."""
    from vle_thermo import calculate_cp_ideal_component
    cp = calculate_cp_ideal_component('CH4', 118.15)
    assert 31.0 < cp < 35.5, f"Methane Cp0 at 118 K should be ~33.3 J/mol/K, got {cp}"
    cp_n2 = calculate_cp_ideal_component('N2', 118.15)
    assert 28.0 < cp_n2 < 30.5, f"Nitrogen Cp0 at 118 K should be ~29.1 J/mol/K, got {cp_n2}"


def test_k_mix_pressure_dependence():
    """Cp/Cv must respond to pressure for a real gas (not a fixed ideal-gas value)."""
    from vle_thermo import calculate_eos_mixture_properties
    low = calculate_eos_mixture_properties({'CH4': 100.0}, 200.0, 100.0, eos='PR')
    high = calculate_eos_mixture_properties({'CH4': 100.0}, 200.0, 5000.0, eos='PR')
    assert low['k_mix'] < 1.45, f"Low-pressure k should be ~1.34, got {low['k_mix']}"
    assert high['k_mix'] > low['k_mix'] + 0.05, "High-pressure real-gas k must differ from ideal-gas k"
    assert high['Cp_real'] > low['Cp_real']


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
    """ Test API 521 fire scenario heat absorption and relieving load. """
    # Insulated tank (F=0.15), API 521 no-drainage constant 70.9 kW/m2
    res = calculate_fire_scenario_load(wetted_area_m2=1200.0, insulation_factor_F=0.15, latent_heat_kJ_kg=510.0)
    assert res['q_fire_kW'] > 3000.0 and res['q_fire_kW'] < 5000.0, f"Fire heat input should be ~3600 kW for F=0.15, got {res['q_fire_kW']}"
    assert res['w_fire_kg_h'] > 20000.0 and res['w_fire_kg_h'] < 35000.0, "Fire W should be ~25000 kg/h"
    assert abs(res['w_fire_kg_s'] - res['w_fire_kg_h'] / 3600.0) < 0.01
    # Uninsulated tank (F=1.0) — much higher heat input
    res_unins = calculate_fire_scenario_load(wetted_area_m2=1200.0, insulation_factor_F=1.0, latent_heat_kJ_kg=510.0)
    assert res_unins['q_fire_kW'] > 20000.0, "Uninsulated fire case should have much higher heat input"
    assert res_unins['w_fire_kg_h'] > res['w_fire_kg_h'] * 3.0, "Uninsulated W should be > 3x insulated"


def test_fire_constant_selection():
    """API 521 21,000 Btu/h/ft2 variant (43.2 kW/m2) must be ~61% of the 34,500 variant (70.9)."""
    res_345 = calculate_fire_scenario_load(q_constant_kW_per_m2=70.9)
    res_210 = calculate_fire_scenario_load(q_constant_kW_per_m2=43.2)
    assert res_210['q_fire_kW'] == pytest.approx(res_345['q_fire_kW'] * 43.2 / 70.9, rel=1e-9)
    assert res_210['q_fire_kW'] < res_345['q_fire_kW']


def test_fire_case_api520_orifice():
    """ Test API 520 orifice area calculation at fire case conditions. """
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
    import lng_thermo
    import psv_database
    import psv_sizing
    import report_generator
    import run_app
    import unit_converter
    import vle_thermo

    assert hasattr(run_app, 'resolve_path')
    assert hasattr(run_app, 'find_free_port')
    assert hasattr(lng_thermo, 'calculate_costald_density')
    assert hasattr(vle_thermo, 'calculate_two_phase_vle_flash')
    assert hasattr(psv_sizing, 'calculate_api520_subcritical_orifice_area')
    assert hasattr(psv_sizing, 'calculate_valve_air_capacity_m3_h')
    assert hasattr(psv_database, 'search_matching_valves')
    assert hasattr(report_generator, 'generate_html_report')
    assert hasattr(unit_converter, 'convert_pressure_to_mbar')

    # PyInstaller collects modules by static analysis of the entry script (run_app.py).
    # These names MUST stay bound in the run_app namespace or the packaged apps break
    # at runtime with ModuleNotFoundError (regression: v1.4.0 ruff --fix removed them).
    for mod in ('app', 'lng_thermo', 'vle_thermo', 'psv_sizing',
                'psv_database', 'report_generator', 'unit_converter'):
        assert hasattr(run_app, mod), \
            f"run_app must import '{mod}' so PyInstaller bundles it into the app"


def test_version_checker():
    """ Verify version checker metadata and update checker functions. """
    from version_checker import check_for_updates, get_version_info, parse_version_tuple
    info = get_version_info()
    assert info['current_version'] == '1.4.1'
    assert 'build_date' in info
    assert len(info['changelog']) > 0

    assert parse_version_tuple('1.2.0') == (1, 2, 0)
    assert parse_version_tuple('v2.0.5') == (2, 0, 5)

    upd = check_for_updates(timeout_sec=0.5)
    assert 'current_version' in upd
    assert 'status_message' in upd


def test_bubble_point_temperature_calculation():
    """ Verify calculation of mixture bubble point temperature and N2 depression effect. """
    from vle_thermo import calculate_bubble_point_temperature
    comp = {'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 3.0, 'N2': 2.0}
    t_bp = calculate_bubble_point_temperature(comp, pressure_kPa_a=117.0, eos='PR')
    assert 106.0 < t_bp < 112.0, f"Expected bubble point around 108 K, got {t_bp}"

    # Verify lean LNG without N2 (must not collapse to 180 K)
    comp_pure = {'CH4': 95.0, 'C2H6': 5.0}
    t_bp_pure = calculate_bubble_point_temperature(comp_pure, pressure_kPa_a=115.0, eos='PR')
    assert 112.0 < t_bp_pure < 116.0, f"Expected lean LNG bubble point ~113.8 K, got {t_bp_pure}"

    # Verify lean LNG with 1.0% N2: N2 must depress the bubble point by 2-5 K
    comp_n2 = {'CH4': 95.0, 'C2H6': 4.0, 'N2': 1.0}
    t_bp_n2 = calculate_bubble_point_temperature(comp_n2, pressure_kPa_a=115.0, eos='PR')
    assert 109.0 < t_bp_n2 < 112.5, f"Expected N2-depressed bubble point ~110.7 K, got {t_bp_n2}"
    assert t_bp_n2 < t_bp_pure, "N2 presence must lower bubble point temperature"


def test_valves_above_90_percent_mode():
    """ Verify show_all_above_90 includes borderline 90-100% valves when present."""
    # Required capacity ~23,800 m3/h: 8"x10" (36,800-39,000 mm2) lands in the 90-100% band
    all_valves = search_matching_valves(
        required_air_capacity_m3_h=23800.0,
        P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT,
        show_all_above_90=True
    )
    valves_90 = [v for v in all_valves if v['coverage_pct'] >= 90.0]
    assert len(valves_90) > 0
    has_8x10 = any('8" x 10"' in v['dn_size'] for v in valves_90)
    assert has_8x10, "8x10 inch valve should be included when show_all_above_90=True"
    assert all(v['coverage_pct'] >= 90.0 for v in valves_90)


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
    assert res['converged']
    assert 0.0 <= res['flash_pct'] <= 100.0
    assert 95.0 <= res['T_flash_K'] <= 130.0


def test_isenthalpic_flash_pure_methane():
    """Pure methane isenthalpic expansion must return a bounded VF and converge."""
    from vle_thermo import calculate_isenthalpic_flash
    res = calculate_isenthalpic_flash(
        {'CH4': 100.0}, t_feed_k=113.0, p_feed_kPa_a=600.0, p_flash_kPa_a=120.0, eos='PR'
    )
    assert res['converged']
    assert 0.0 <= res['flash_pct'] <= 100.0
    assert 90.0 <= res['T_flash_K'] <= 200.0


def test_valve_database_expanded_manufacturers():
    """ Verify database contains expanded manufacturer pool and wide range of sizes. """
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
    """ Verify that search_matching_valves strictly enforces max_coverage_pct=200.0. """
    matches = search_matching_valves(
        required_air_capacity_m3_h=12000.0,
        P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT,
        max_coverage_pct=200.0,
        show_all_above_90=True
    )
    assert len(matches) > 0
    for v in matches:
        assert v['coverage_pct'] <= 200.0, f"Valve {v['id']} has coverage {v['coverage_pct']:.1f}% > 200%"
        assert v['coverage_pct'] >= 90.0, f"Valve {v['id']} has coverage {v['coverage_pct']:.1f}% < 90%"


def test_small_flow_valve_selection_and_oversized_status():
    """ Verify small flow rates match compact valves and oversized status is properly tagged. """
    matches = search_matching_valves(
        required_air_capacity_m3_h=1500.0,
        P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT,
        max_coverage_pct=200.0,
        show_all_above_90=True
    )
    assert len(matches) > 0
    for v in matches:
        assert any(sz in v['dn_size'] for sz in ['2" x 3"', '3" x 4"', '4" x 6"']), f"Unexpected large size {v['dn_size']} for small flow"
        assert v['coverage_pct'] <= 200.0

    matrix = evaluate_valve_matrix(q_a_per_valve_m3_h=1500.0, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT)
    oversized = [m for m in matrix if m['coverage_pct'] > 200.0]
    assert len(oversized) > 0
    assert oversized[0]['status_code'] == 'OVERSIZED'
    assert "AŞIRI BÜYÜK" in oversized[0]['status']


def test_search_matching_valves_derives_capacity_from_area():
    """req_orifice_area_mm2 alone must be enough to run the search."""
    matches = search_matching_valves(
        req_orifice_area_mm2=50000.0, P1_kPa_a=P1_DEFAULT, P2_kPa_a=P2_DEFAULT,
        show_all_above_90=True
    )
    assert len(matches) > 0


def test_report_generator_uses_real_values_and_dynamic_recommendation():
    """The report must show computed Z/M values and the dynamic best valve (no hardcoded 18x20)."""
    from report_generator import generate_html_report
    loads, Z, k, M = _default_scenario()
    sub = calculate_api520_subcritical_orifice_area(
        loads['w_total_kg_h'] / 3, P1_DEFAULT, P2_DEFAULT, 118.15, M, Z, k, 0.85
    )
    q_a = calculate_nfpa59a_air_equivalent(
        loads['w_total_kg_s'], 118.15, Z, M, k, 0.85, P1_DEFAULT, P2_DEFAULT
    )
    matrix = evaluate_valve_matrix(q_a / 3, P1_DEFAULT, P2_DEFAULT)
    inputs = {
        'project_name': 'Test Facility', 'project_revision': 'Rev.1', 'eos_choice': 'PR',
        'V_n': 160000, 'Q_fill': 10000, 'P_atm_min': 906.03, 'P_atm_max': 1014.602,
        'P_set': 240, 'Overpressure_pct': 10, 'fire_overpressure_pct': 21,
        'N_working': 3, 'N_spare': 1, 'T_tank_K': 113.15, 'T_relief_K': 118.15,
        'T_cargo_K': 112.4, 'T_fire_K': 173.15, 'P_ship_kPa_a': 590.6,
        'flash_pct': 2.0, 'wetted_area_m2': 1200, 'insulation_factor_F': 0.15,
        'latent_heat_kJ_kg': 510, 'K_d': 0.85, 'P1_kPa_a': P1_DEFAULT,
        'P1_fire_kPa_a': 119.1,
    }
    thermo = {
        'density_kg_m3': 471.0, 'molar_mass_g_mol': 16.5, 'vapor_density': 1.945,
        'Z_factor': Z, 'k_factor': k, 'M_vapor': M,
        'fire_Z': 0.99, 'fire_k': 1.35, 'fire_M_vapor': 16.1,
    }
    sizing = {
        'w_flash_kg_h': loads['w_flash_kg_h'], 'w_disp_kg_h': loads['w_disp_kg_h'],
        'w_bog_kg_h': loads['w_bog_kg_h'], 'w_total_kg_h': loads['w_total_kg_h'],
        'w_total_kg_s': loads['w_total_kg_s'], 'w_total_g_s': loads['w_total_kg_h'] * 1000 / 3600,
        'q_a_total_m3_h': q_a, 'q_a_per_valve_m3_h': q_a / 3,
        'A_o_mm2': sub['A_o_mm2'], 'A_o_in2': sub['A_o_in2'], 'w_valve_kg_h': loads['w_total_kg_h'] / 3,
        'api_details': sub, 'fire_details': calculate_fire_scenario_load(),
        'fire_q_a_total': 10000, 'fire_q_a_per_valve': 3333, 'fire_subcrit': sub,
        'fire_matrix': matrix, 'governing_scenario': 'Operational',
        'governing_w_total_kg_h': loads['w_total_kg_h'], 'governing_A_o_mm2': sub['A_o_mm2'],
        'governing_matrix': matrix, 'fire_Z': 0.99, 'fire_k': 1.35, 'T_fire_K': 173.15,
        'isenthalpic_res': {'T_flash_K': 112.4, 'flash_pct': 2.0, 'h_feed_J_mol': -6800.0, 'converged': True},
    }
    html = generate_html_report(inputs, thermo, sizing, matrix, [], language='tr', app_version='1.4.1')
    assert f"{Z:.4f}" in html, "Report must show the computed Z factor"
    assert f"{M:.2f}" in html, "Report must show the computed vapor molar mass"
    assert '18" x 20" (DN450 x DN500)' not in html, "Report must not hardcode 18x20 recommendation"
    assert '10" x 12"' in html, "Report must show the dynamically selected smallest adequate valve"
    assert 'v1.4.1' in html
    # English variant
    html_en = generate_html_report(inputs, thermo, sizing, matrix, [], language='en', app_version='1.4.1')
    assert "PORV Relief Valve Sizing" in html_en
    assert "Option A (Recommended)" in html_en


def test_report_generator_empty_matrix_no_crash():
    from report_generator import generate_html_report
    html = generate_html_report(
        {'V_n': 1, 'Q_fill': 1, 'P_atm_min': 900, 'P_atm_max': 1010, 'P_set': 240,
         'Overpressure_pct': 10, 'N_working': 3, 'N_spare': 1},
        {}, {}, [], [], language='tr'
    )
    assert isinstance(html, str) and len(html) > 100


def test_costald_density_vs_coolprop_reference():
    """Golden validation: COSTALD mixture density must match CoolProp HEOS liquid density within 2%.

    Fixed (T, P) liquid states are used because CoolProp's mixture saturation (Q=0)
    and low-temperature phase detection for this 6-component mixture are not stable
    across CoolProp versions.
    """
    cp = pytest.importorskip("CoolProp.CoolProp")
    mix = ("HEOS::Methane[0.905]&Ethane[0.055]&Propane[0.025]"
           "&Isobutane[0.005]&n-Butane[0.005]&Nitrogen[0.005]")
    compared = 0
    for temp_k, pressure_pa in ((118.15, 500000.0), (120.0, 800000.0), (125.0, 1000000.0)):
        try:
            rho_cp = cp.PropsSI('D', 'T', temp_k, 'P', pressure_pa, mix)
        except Exception:
            continue
        if not math.isfinite(rho_cp) or rho_cp < 350.0:
            # CoolProp mixture phase detection returned a non-liquid state; skip this point
            continue
        rho_costald = calculate_costald_density(DEFAULT_COMP, temperature_k=temp_k)['density_kg_m3']
        assert rho_costald == pytest.approx(rho_cp, rel=0.02), \
            f"COSTALD {rho_costald:.1f} vs CoolProp {rho_cp:.1f} at {temp_k} K"
        compared += 1
    assert compared >= 1, "No valid CoolProp liquid reference state could be evaluated"


def test_pr_vs_heos_consistency():
    """Golden validation: PR and HEOS must agree on Z, k and vapor density within 2%."""
    from vle_thermo import calculate_two_phase_vle_flash
    pr = calculate_two_phase_vle_flash(DEFAULT_COMP, 118.15, 114.6, eos='PR')
    heos = calculate_two_phase_vle_flash(DEFAULT_COMP, 118.15, 114.6, eos='HEOS')
    assert pr['Z_gas'] == pytest.approx(heos['Z_gas'], rel=0.02)
    assert pr['k_mix'] == pytest.approx(heos['k_mix'], rel=0.02)
    assert pr['rho_v_kg_m3'] == pytest.approx(heos['rho_v_kg_m3'], rel=0.02)
    assert pr['M_vapor_g_mol'] == pytest.approx(heos['M_vapor_g_mol'], rel=0.01)


def test_app_smoke_no_exception():
    """End-to-end Streamlit AppTest smoke test: the full script must run without exceptions."""
    apptest = pytest.importorskip("streamlit.testing.v1")
    at = apptest.AppTest.from_file("app.py", default_timeout=180)
    at.run()
    assert not at.exception, f"App raised: {[str(e.value) for e in at.exception]}"
    assert len(at.dataframe) >= 1, "Valve matrix dataframe should be rendered"


if __name__ == '__main__':
    pytest.main(['-v', 'test_app.py'])
