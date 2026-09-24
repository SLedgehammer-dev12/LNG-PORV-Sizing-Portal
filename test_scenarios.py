"""
Permanent regression scenario tests for the LNG PORV Sizing Portal.

These tests exercise the REAL end-to-end computation pipeline
(app._compute_all_results) with the physical API 520 valve capacity model.
They complement test_app.py (unit/UI tests) and encode the critical findings
of the 60-scenario functional campaign (scenario_campaign.py).
"""

import logging
import math

import pytest

logging.disable(logging.WARNING)

import app  # noqa: E402
import psv_database  # noqa: E402
from lng_thermo import calculate_costald_density  # noqa: E402
from psv_sizing import calculate_valve_air_capacity_m3_h  # noqa: E402

DEFAULT_COMP = {'CH4': 90.5, 'C2H6': 5.5, 'C3H8': 2.5, 'iC4H10': 0.5, 'nC4H10': 0.5, 'N2': 0.5}
BASE = dict(
    p_set=240.0, op=10.0, patm_min=906.03, patm_max=1014.602, q_fill=10000.0,
    t_relief=118.15, t_cargo=111.27, t_fire=173.15, eos='PR', n_working=3,
    flash_mode='PH', flash_pct=2.0, w_flash_manual=94200.0,
    bog_auto=True, bor=0.10, w_bog=1570.0,
    wetted=1200.0, F=0.15, L=510.0, fire_op=21.0, fire_const=70.9, fire_kd=1.0,
    p_ship=5000.0, comp=None, rho_lng=None,
)


def run_pipeline(**overrides):
    """Runs the real end-to-end pipeline and returns (result, rho_lng)."""
    p = dict(BASE)
    p.update(overrides)
    comp = p['comp'] if p['comp'] is not None else DEFAULT_COMP
    rho_lng = p['rho_lng'] or calculate_costald_density(comp, temperature_k=p['t_relief'])['density_kg_m3']
    if p['flash_mode'] == 'PH':
        manual, fval, isenth = False, None, True
    elif p['flash_mode'] == 'FIXED':
        manual, fval, isenth = False, p['flash_pct'], False
    else:
        manual, fval, isenth = True, 2.0, False
    res = app._compute_all_results(
        p_set_mbar=p['p_set'], overpressure_pct=p['op'],
        p_atm_min_mbar=p['patm_min'], p_atm_max_mbar=p['patm_max'],
        q_fill_m3h=p['q_fill'], rho_lng_val=rho_lng,
        comp_dict_frozen=tuple(sorted(comp.items())),
        t_relief_K=p['t_relief'], t_cargo_K=p['t_cargo'], t_fire_K=p['t_fire'],
        eos_code_val=p['eos'], n_working=p['n_working'],
        flash_manual_mode_val=manual, w_flash_manual_kg_h_val=p['w_flash_manual'],
        flash_pct_val=fval, w_bog_kg_h_val=p['w_bog'], bog_auto_mode_val=p['bog_auto'],
        bor_pct_per_day_val=p['bor'], wetted_area_m2_val=p['wetted'],
        insulation_factor_F_val=p['F'], latent_heat_kJ_kg_val=p['L'],
        fire_overpressure_pct=p['fire_op'], fire_q_constant_val=p['fire_const'],
        fire_K_d_val=p['fire_kd'], is_isenthalpic_mode_val=isenth,
        p_ship_mbar_g_val=p['p_ship'],
        cargo_comp_frozen=None,
    )
    return res, rho_lng


def assert_invariants(res):
    loads, sub, fire = res['loads'], res['subcrit'], res['fire_subcrit']
    assert all(math.isfinite(v) for v in (res['Z_factor'], res['k_factor'], res['rho_v'],
                                          res['M_vapor'], res['q_a_total'], sub['A_o_mm2'], fire['A_o_mm2']))
    assert 0.0 <= res['effective_flash_pct'] <= 100.0
    assert 1.0 <= res['k_factor'] <= 1.7
    assert 0.0 < res['Z_factor'] <= 1.3
    assert 2.0 <= res['M_vapor'] <= 100.0
    assert sub['A_o_mm2'] > 0 and fire['A_o_mm2'] > 0
    balance = loads['w_disp_kg_h'] + loads['w_flash_kg_h'] + loads['w_bog_kg_h']
    assert balance == pytest.approx(loads['w_total_kg_h'], abs=0.1)
    # Q_a must equal the API 520 air capacity of the required orifice (per valve)
    cap_op = calculate_valve_air_capacity_m3_h(sub['A_o_mm2'], res['P1_kPa_a'], res['P2_kPa_a'], 0.85)
    assert cap_op == pytest.approx(res['q_a_per_valve'], rel=1e-6)
    cap_fire = calculate_valve_air_capacity_m3_h(fire['A_o_mm2'], res['P1_fire_kPa_a'], res['P2_kPa_a'], 1.0)
    assert cap_fire == pytest.approx(res['fire_q_a_per_valve'], rel=1e-6)
    # governing scenario must be the larger required area
    assert res['governing_is_fire'] == (fire['A_o_mm2'] > sub['A_o_mm2'])


# --------------------------------------------------------------- anchor tests
def test_scenario_default_anchor():
    """Default scenario regression anchor (v1.4.0 physical model)."""
    res, rho_lng = run_pipeline()
    assert_invariants(res)
    assert res['effective_flash_pct'] < 0.1
    assert res['subcrit']['A_o_mm2'] == pytest.approx(8143.0, rel=0.05)
    assert res['fire_subcrit']['A_o_mm2'] == pytest.approx(9364.0, rel=0.05)
    assert res['governing_is_fire'] is True
    assert 450.0 < rho_lng < 470.0
    assert res['Z_factor'] == pytest.approx(0.9676, abs=0.01)
    assert res['k_factor'] == pytest.approx(1.365, abs=0.02)


def test_scenario_fixed_2pct_flash_anchor():
    res, _ = run_pipeline(flash_mode='FIXED', flash_pct=2.0)
    assert_invariants(res)
    assert res['effective_flash_pct'] == pytest.approx(2.0, abs=0.01)
    assert res['loads']['w_total_kg_h'] == pytest.approx(112870.0, rel=0.03)
    assert res['subcrit']['A_o_mm2'] == pytest.approx(43190.0, rel=0.05)
    assert res['governing_is_fire'] is False


def test_scenario_manual_flash_uses_manual_flow():
    res, _ = run_pipeline(flash_mode='MANUAL')
    assert_invariants(res)
    assert res['loads']['w_flash_kg_h'] == pytest.approx(94200.0, abs=1.0)
    assert res['loads']['w_total_kg_h'] == pytest.approx(115170.0, rel=0.02)


# --------------------------------------------------------- composition effects
def test_scenario_high_nitrogen_enriches_vapor():
    res, _ = run_pipeline(comp={'CH4': 88.0, 'C2H6': 5.0, 'C3H8': 2.0, 'iC4H10': 0.5,
                                'nC4H10': 0.5, 'N2': 3.0, 'nC5H12': 0.5})
    assert_invariants(res)
    assert res['effective_flash_pct'] > 1.0, "N2 must increase the flash ratio"
    assert res['vle_res']['y_vapor']['N2'] > res['vle_res']['x_liquid']['N2']
    assert res['vle_res']['y_vapor']['N2'] * 100.0 > 3.0


def test_scenario_heavy_lng_density_and_vapor_enrichment():
    comp = {'CH4': 82.0, 'C2H6': 8.0, 'C3H8': 4.0, 'iC4H10': 2.0, 'nC4H10': 2.0,
            'nC5H12': 1.5, 'N2': 0.5}
    res, rho_lng = run_pipeline(comp=comp)
    assert_invariants(res)
    assert rho_lng > 480.0, "Heavy LNG must be denser"
    m_liq = calculate_costald_density(comp, temperature_k=118.15)['molar_mass_g_mol']
    assert res['M_vapor'] < m_liq, "Vapor phase must be lighter than the liquid"


def test_scenario_pure_and_near_pure_methane():
    for comp in ({'CH4': 100.0}, {'CH4': 99.6, 'N2': 0.4}):
        res, _ = run_pipeline(comp=comp)
        assert_invariants(res)
        assert res['M_vapor'] == pytest.approx(16.04, rel=0.03)


# ------------------------------------------------------------------ EOS cross
@pytest.mark.parametrize("eos", ["PR", "SRK", "HEOS"])
def test_scenario_eos_consistency(eos):
    res, _ = run_pipeline(eos=eos)
    assert_invariants(res)
    assert 0.90 < res['Z_factor'] < 1.0
    assert 1.30 < res['k_factor'] < 1.45


def test_scenario_pr_vs_heos_within_2pct():
    pr, _ = run_pipeline(eos='PR')
    heos, _ = run_pipeline(eos='HEOS')
    assert pr['Z_factor'] == pytest.approx(heos['Z_factor'], rel=0.02)
    assert pr['k_factor'] == pytest.approx(heos['k_factor'], rel=0.02)
    assert pr['rho_v'] == pytest.approx(heos['rho_v'], rel=0.02)
    assert pr['subcrit']['A_o_mm2'] == pytest.approx(heos['subcrit']['A_o_mm2'], rel=0.02)


def test_scenario_ideal_gas_z_is_one():
    res, _ = run_pipeline(eos='IDEAL')
    assert res['Z_factor'] == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------ temperature/load
def test_scenario_cargo_temperature_flash_trend():
    vfs = []
    for t_cargo in (111.27, 113.15, 118.15, 123.15):
        res, _ = run_pipeline(t_cargo=t_cargo)
        assert_invariants(res)
        vfs.append(res['effective_flash_pct'])
    assert vfs[0] < vfs[1] < vfs[2] < vfs[3], "Flash ratio must increase with cargo temperature"
    assert vfs[3] > 5.0


def test_scenario_cold_cargo_no_flash():
    res, _ = run_pipeline(t_cargo=105.0)
    assert_invariants(res)
    assert res['effective_flash_pct'] < 0.05


def test_scenario_fill_rate_scales_area():
    low, _ = run_pipeline(q_fill=5000.0)
    high, _ = run_pipeline(q_fill=20000.0)
    assert_invariants(low)
    assert_invariants(high)
    assert high['subcrit']['A_o_mm2'] > 3.0 * low['subcrit']['A_o_mm2']


def test_scenario_valve_count_scales_area():
    one, _ = run_pipeline(n_working=1)
    six, _ = run_pipeline(n_working=6)
    assert_invariants(one)
    assert_invariants(six)
    assert one['subcrit']['A_o_mm2'] == pytest.approx(6.0 * six['subcrit']['A_o_mm2'], rel=0.01)


# ----------------------------------------------------------------------- fire
def test_scenario_uninsulated_fire_governs():
    res, _ = run_pipeline(F=1.0)
    assert_invariants(res)
    assert res['governing_is_fire'] is True
    assert res['fire_res']['w_fire_kg_h'] > 150000.0


def test_scenario_low_fire_constant_switches_governing():
    res, _ = run_pipeline(fire_const=43.2)
    assert_invariants(res)
    assert res['governing_is_fire'] is False
    assert res['fire_res']['w_fire_kg_h'] < 18000.0


# --------------------------------------------------------- critical / boundary
def test_scenario_high_set_pressure_critical_flow():
    res, _ = run_pipeline(p_set=2500.0)
    assert_invariants(res)
    assert res['subcrit']['is_subcritical'] is False, "Very high set pressure must reach critical flow"


def test_scenario_moderate_set_pressure_subcritical():
    res, _ = run_pipeline(p_set=500.0)
    assert_invariants(res)
    assert res['subcrit']['is_subcritical'] is True


def test_scenario_extreme_low_atm_pressure_flashes_and_grows_area():
    res, _ = run_pipeline(patm_min=500.0)
    assert_invariants(res)
    assert res['effective_flash_pct'] > 1.0, "Very low tank pressure must increase flash"
    assert res['subcrit']['A_o_mm2'] > 50000.0


# --------------------------------------------------------------- robustness
def test_scenario_extreme_cold_temperature_no_crash():
    """Regression: Wilson K=0 caused a ZeroDivisionError at T=50 K."""
    res, _ = run_pipeline(t_relief=50.0)
    assert all(math.isfinite(v) for v in (res['Z_factor'], res['k_factor'], res['rho_v']))
    assert res['subcrit']['A_o_mm2'] > 0


def test_scenario_extreme_hot_temperature_no_crash():
    res, _ = run_pipeline(t_relief=500.0)
    assert_invariants(res)


def test_scenario_empty_composition_falls_back_to_methane():
    res, _ = run_pipeline(comp={})
    assert_invariants(res)
    assert res['M_vapor'] == pytest.approx(16.04, rel=0.03)


def test_scenario_corrupt_database_no_crash(monkeypatch):
    monkeypatch.setattr(psv_database, "get_db_path", lambda: "/tmp/nonexistent_psv_db.json")
    res, _ = run_pipeline()
    assert res['governing_matrix'] == []
    assert res['matched_valves'] == []
    assert res['subcrit']['A_o_mm2'] > 0


# ------------------------------------------------------------------- reports
def test_scenario_report_generation_tr_en():
    from report_generator import generate_html_report
    res, rho_lng = run_pipeline()
    loads = res['loads']
    inputs = {
        'project_name': 'Regression', 'project_revision': 'Rev.0', 'eos_choice': 'PR',
        'V_n': 160000, 'Q_fill': 10000, 'P_atm_min': 906.03, 'P_atm_max': 1014.602,
        'P_set': 240, 'Overpressure_pct': 10, 'fire_overpressure_pct': 21, 'fire_K_d': 1.0,
        'N_working': 3, 'N_spare': 1, 'T_tank_K': 113.15, 'T_relief_K': 118.15,
        'T_cargo_K': 111.27, 'T_fire_K': 173.15, 'P_ship_kPa_a': 590.6,
        'flash_pct': res['effective_flash_pct'], 'wetted_area_m2': 1200,
        'insulation_factor_F': 0.15, 'latent_heat_kJ_kg': 510, 'K_d': 0.85,
        'P1_kPa_a': res['P1_kPa_a'], 'P1_fire_kPa_a': res['P1_fire_kPa_a'],
    }
    thermo = {'density_kg_m3': rho_lng, 'molar_mass_g_mol': res['M_vapor'],
              'vapor_density': res['rho_v'], 'Z_factor': res['Z_factor'],
              'k_factor': res['k_factor'], 'M_vapor': res['M_vapor'],
              'fire_Z': res['fire_Z'], 'fire_k': res['fire_k'], 'fire_M_vapor': res['fire_M_vapor']}
    sizing = {
        'w_flash_kg_h': loads['w_flash_kg_h'], 'w_disp_kg_h': loads['w_disp_kg_h'],
        'w_bog_kg_h': loads['w_bog_kg_h'], 'w_total_kg_h': loads['w_total_kg_h'],
        'w_total_kg_s': loads['w_total_kg_s'], 'w_total_g_s': loads['w_total_kg_h'] * 1000 / 3600,
        'q_a_total_m3_h': res['q_a_total'], 'q_a_per_valve_m3_h': res['q_a_per_valve'],
        'A_o_mm2': res['subcrit']['A_o_mm2'], 'A_o_in2': res['subcrit']['A_o_in2'],
        'w_valve_kg_h': loads['w_total_kg_h'] / 3, 'api_details': res['subcrit'],
        'fire_details': res['fire_res'], 'fire_q_a_total': res['fire_q_a_total'],
        'fire_q_a_per_valve': res['fire_q_a_per_valve'], 'fire_subcrit': res['fire_subcrit'],
        'fire_matrix': res['fire_matrix'], 'governing_scenario': res['governing_scenario'],
        'governing_w_total_kg_h': res['governing_w_total_kg_h'],
        'governing_A_o_mm2': res['governing_A_o_mm2'], 'governing_matrix': res['governing_matrix'],
        'fire_Z': res['fire_Z'], 'fire_k': res['fire_k'], 'T_fire_K': 173.15,
        'isenthalpic_res': res['isenthalpic_res'],
    }
    html_tr = generate_html_report(inputs, thermo, sizing, res['governing_matrix'],
                                   res['matched_valves'], language='tr', app_version='1.4.0')
    assert 'Boyutlandırma ve Termodinamik Analiz Raporu' in html_tr
    assert 'nan' not in html_tr.lower()
    html_en = generate_html_report(inputs, thermo, sizing, res['governing_matrix'],
                                   res['matched_valves'], language='en', app_version='1.4.0')
    assert 'PORV Relief Valve Sizing' in html_en


if __name__ == '__main__':
    pytest.main(['-v', 'test_scenarios.py'])
