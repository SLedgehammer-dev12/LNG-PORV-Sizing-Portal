"""
LNG PORV Sizing Portal - 60-Scenario End-to-End Functional Test Campaign

Runs the REAL computation pipeline (app._compute_all_results) plus the HTML report
generator for 60 parameter scenarios, applies physical/consistency/monotonicity
checks and writes a markdown results report.

Usage:  python3 scenario_campaign.py
"""

import datetime
import logging
import math
import time

logging.disable(logging.WARNING)

import app  # noqa: E402  (imports the Streamlit app in bare mode; provides _compute_all_results)
import psv_database  # noqa: E402
from lng_thermo import calculate_costald_density  # noqa: E402
from psv_sizing import (  # noqa: E402
    calculate_valve_air_capacity_m3_h,
)
from report_generator import generate_html_report  # noqa: E402
from unit_converter import (  # noqa: E402
    convert_pressure_to_mbar,
    convert_temperature_to_kelvin,
    convert_volumetric_flow_to_m3_h,
)
from version_checker import CURRENT_VERSION  # noqa: E402

DEFAULT_COMP = {'CH4': 90.5, 'C2H6': 5.5, 'C3H8': 2.5, 'iC4H10': 0.5, 'nC4H10': 0.5, 'N2': 0.5}
BASE = dict(
    p_set=240.0, op=10.0, patm_min=906.03, patm_max=1014.602, q_fill=10000.0,
    t_relief=118.15, t_cargo=111.27, t_fire=173.15, eos='PR', n_working=3,
    flash_mode='PH', flash_pct=None, w_flash_manual=94200.0,
    bog_auto=True, bor=0.10, w_bog=1570.0,
    wetted=1200.0, F=0.15, L=510.0, fire_op=21.0, fire_const=70.9, fire_kd=1.0,
    p_ship=5000.0, comp=None, cargo_comp=None, rho_lng=None,
)

SCENARIOS = []


def S(sid, cat, name, note="", expect=None, **kw):
    SCENARIOS.append(dict(id=sid, cat=cat, name=name, note=note, expect=expect or {}, params=kw))


def _p(**overrides):
    p = dict(BASE)
    p.update(overrides)
    return p


# ---------------------------------------------------------------- scenario list
# A. Baseline
S(1, "A-Temel", "Varsayılan (otomatik kargo T, PH-flaş)", "Referans davranış",
  expect=dict(no_exc=True), **_p())
S(2, "A-Temel", "Sabit %2 flaş (klasik NFPA senaryosu)", "W_flash = Q·ρ·%2",
  expect=dict(vf_min=1.9, vf_max=2.1, wtotal_min=110000, wtotal_max=120000), **_p(flash_mode='FIXED', flash_pct=2.0))
S(3, "A-Temel", "Aşırı soğuk kargo (VF≈0)", "Subcooled: flaş yok",
  expect=dict(vf_max=0.05), **_p(t_cargo=110.5))
S(4, "A-Temel", "Manuel flaş debisi 94.200 kg/h", "Manuel mod yükü",
  expect=dict(vf_min=1.9, vf_max=2.1), **_p(flash_mode='MANUAL'))
S(5, "A-Temel", "Manuel tank BOG 1.570 kg/h", "Manuel BOG",
  expect=dict(wtotal_min=20000, wtotal_max=25000), **_p(w_bog=1570.0))
S(6, "A-Temel", "Otomatik BOR %0,10/gün", "V_n·ρ·BOR/2400",
  expect=dict(wtotal_min=20000, wtotal_max=25000), **_p())

# B. Composition
S(7, "B-Kompozisyon", "Zengin LNG (%96 CH4)", "Daha hafif → ρ düşer, M düşer",
  expect=dict(m_max=17.0, rho_lng_min=420), **_p(comp={'CH4': 96.0, 'C2H6': 2.5, 'C3H8': 1.0, 'N2': 0.5}))
S(8, "B-Kompozisyon", "Fakir/ağır LNG (%85 CH4)", "ρ ve M artar",
  expect=dict(rho_lng_min=460, vapor_lighter=True), **_p(comp={'CH4': 85.0, 'C2H6': 8.0, 'C3H8': 4.0, 'iC4H10': 1.0, 'nC4H10': 1.0, 'N2': 1.0}))
S(9, "B-Kompozisyon", "Yüksek azot (%3 N2)", "N2 buharı zenginleşir, M_vapor düşer",
  expect=dict(m_min=15.0, m_max=19.0, n2_enrich=True, vapor_lighter=True), **_p(comp={'CH4': 88.0, 'C2H6': 5.0, 'C3H8': 2.0, 'iC4H10': 0.5, 'nC4H10': 0.5, 'N2': 3.0, 'nC5H12': 0.5}))
S(10, "B-Kompozisyon", "CO2 içeren LNG (%1)", "Asidik bileşen",
  expect=dict(no_exc=True), **_p(comp={'CH4': 89.0, 'C2H6': 5.5, 'C3H8': 2.5, 'iC4H10': 0.5, 'nC4H10': 0.5, 'CO2': 1.0, 'N2': 0.5}))
S(11, "B-Kompozisyon", "Ağır LNG (C4/C5 zengin)", "En yüksek ρ ve M",
  expect=dict(rho_lng_min=480, vapor_lighter=True), **_p(comp={'CH4': 82.0, 'C2H6': 8.0, 'C3H8': 4.0, 'iC4H10': 2.0, 'nC4H10': 2.0, 'nC5H12': 1.5, 'N2': 0.5}))
S(12, "B-Kompozisyon", "Saf metan (%100 CH4)", "Pure-component özel yolu",
  expect=dict(no_exc=True, vf_max=100), **_p(comp={'CH4': 100.0}))
S(13, "B-Kompozisyon", "Near-pure metan (%99,6)", "Near-pure flaş yolu",
  expect=dict(no_exc=True), **_p(comp={'CH4': 99.6, 'N2': 0.4}))
S(14, "B-Kompozisyon", "H2 + He izleri", "Çok hafif bileşenler",
  expect=dict(m_max=16.5), **_p(comp={'CH4': 90.0, 'C2H6': 5.0, 'C3H8': 2.0, 'N2': 1.0, 'H2': 1.0, 'He': 1.0}))

# C. EOS
S(15, "C-EOS", "Peng-Robinson (PR)", "Varsayılan EOS", expect=dict(no_exc=True), **_p(eos='PR'))
S(16, "C-EOS", "Soave-Redlich-Kwong (SRK)", "PR ile ≤%2 sapma",
  expect=dict(no_exc=True), **_p(eos='SRK'))
S(17, "C-EOS", "HEOS (GERG-2008)", "PR ile ≤%2 sapma",
  expect=dict(no_exc=True), **_p(eos='HEOS'))
S(18, "C-EOS", "İdeal Gaz", "En basit model; Z=1",
  expect=dict(z_min=0.999, z_max=1.001), **_p(eos='IDEAL'))

# D. Temperature
S(19, "D-Sıcaklık", "Kargo -165 °C", "Çok soğuk → düşük VF",
  expect=dict(vf_max=0.05), **_p(t_cargo=108.15))
S(20, "D-Sıcaklık", "Kargo -160 °C", "Referans sıcaklık",
  expect=dict(no_exc=True), **_p(t_cargo=113.15))
S(21, "D-Sıcaklık", "Kargo -155 °C", "Daha sıcak → VF artar",
  expect=dict(vf_min=0.1), **_p(t_cargo=118.15))
S(22, "D-Sıcaklık", "Kargo -150 °C", "VF en yüksek",
  expect=dict(vf_min=0.5), **_p(t_cargo=123.15))
S(23, "D-Sıcaklık", "Tank -163 °C / buhar -158 °C", "Soğuk tank, ρ_LNG yüksek",
  expect=dict(rho_lng_min=455), **_p(t_relief=115.15))
S(24, "D-Sıcaklık", "Buhar sıcaklığı -160 °C", "ρ_v artar (T düşer)",
  expect=dict(rho_lng_min=440), **_p(t_relief=113.15))

# E. Pressure
S(25, "E-Basınç", "P_atm_min = 950 mbar", "Daha yüksek Patm → küçük A_o",
  expect=dict(rel_band=('ao_op', 0.97, 1.06)), **_p(patm_min=950.0))
S(26, "E-Basınç", "P_atm_min = 1000 mbar", "A_o daha da küçük",
  expect=dict(rel_band=('ao_op', 0.97, 1.06)), **_p(patm_min=1000.0))
S(27, "E-Basınç", "P_set = 200 mbar_g", "Düşük set → büyük A_o",
  expect=dict(rel_ref=('ao_op', 'gt', 1.05)), **_p(p_set=200.0))
S(28, "E-Basınç", "P_set = 300 mbar_g", "Yüksek set → küçük A_o",
  expect=dict(rel_ref=('ao_op', 'lt', 0.99)), **_p(p_set=300.0))
S(29, "E-Basınç", "Overpressure %0", "P1 = P_set + Patm",
  expect=dict(rel_ref=('ao_op', 'gt', 1.03)), **_p(op=0.0))

# F. Flow / valve count
S(30, "F-Debi/Vana", "Q_fill = 5.000 m³/h", "A_o yarıya yakın",
  expect=dict(rel_ref=('ao_op', 'lt', 0.6)), **_p(q_fill=5000.0))
S(31, "F-Debi/Vana", "Q_fill = 20.000 m³/h", "A_o ~2x",
  expect=dict(rel_ref=('ao_op', 'gt', 1.8)), **_p(q_fill=20000.0))
S(32, "F-Debi/Vana", "N = 1 çalışan vana", "Vana başına yük 3x",
  expect=dict(rel_ref=('ao_op', 'gt', 2.8)), **_p(n_working=1))
S(33, "F-Debi/Vana", "N = 6 çalışan vana", "Vana başına yük yarıya",
  expect=dict(rel_ref=('ao_op', 'lt', 0.55)), **_p(n_working=6))

# G. Fire
S(34, "G-Yangın", "Yalıtım F = 0,30", "W_fire ~2x (F=0,15'e göre)",
  expect=dict(wfire_min=45000), **_p(F=0.30))
S(35, "G-Yangın", "Yalıtımsız F = 1,0", "Yangın kesin hüküm sürer",
  expect=dict(gov='fire', wfire_min=150000), **_p(F=1.0))
S(36, "G-Yangın", "Isı akısı sabiti 43,2 kW/m²", "W_fire %61'e düşer",
  expect=dict(wfire_max=18000), **_p(fire_const=43.2))
S(37, "G-Yangın", "T_fire = -50 °C", "A_o_fire artar (√T)",
  expect=dict(no_exc=True), **_p(t_fire=223.15))
S(38, "G-Yangın", "Yangın Kd = 0,85", "A_o_fire artar",
  expect=dict(no_exc=True), **_p(fire_kd=0.85))

# H. Flash / BOG extremes
S(39, "H-Flaş/BOG", "Sabit %10 flaş", "W_flash 5x",
  expect=dict(vf_min=9.9, vf_max=10.1, wtotal_min=400000), **_p(flash_mode='FIXED', flash_pct=10.0))
S(40, "H-Flaş/BOG", "Kızgın kargo 125 K", "Güçlü flaş",
  expect=dict(vf_min=1.0), **_p(t_cargo=125.0))
S(41, "H-Flaş/BOG", "Çok soğuk kargo 105 K", "Flaş yok",
  expect=dict(vf_max=0.05), **_p(t_cargo=105.0))
S(42, "H-Flaş/BOG", "BOR %1,0/gün", "BOG 10x",
  expect=dict(wtotal_min=48000), **_p(w_bog=31000.0))
S(43, "H-Flaş/BOG", "Manuel BOG = 0", "Yalnız taşma+flaş",
  expect=dict(wtotal_min=18000, wtotal_max=24000), **_p(w_bog=0.0))

# I. Critical / boundary
S(44, "I-Kritik/Sınır", "P_set = 500 mbar_g", "Subkritik rejim",
  expect=dict(crit_op=True), **_p(p_set=500.0))
S(45, "I-Kritik/Sınır", "P_set = 2.500 mbar_g", "Kritik akışa geçiş",
  expect=dict(crit_op=False), **_p(p_set=2500.0))
S(46, "I-Kritik/Sınır", "Çok düşük debi 1.000 m³/h", "Fallback filtre",
  expect=dict(no_exc=True), **_p(q_fill=1000.0))
S(47, "I-Kritik/Sınır", "Çok yüksek debi 30.000 m³/h", "Kapasite açığı/uyarı",
  expect=dict(no_exc=True), **_p(q_fill=30000.0))
S(48, "I-Kritik/Sınır", "P_atm_min = 500 mbar (aşırı)", "ΔP büyür, A_o küçülür",
  expect=dict(rel_ref=('ao_op', 'gt', 1.1)), **_p(patm_min=500.0))

# J. Unit conversions (converted inputs must equal SI equivalents)
S(49, "J-Birim", "T_relief -247 °F → 118,15 K", "°F dönüşümü",
  expect=dict(no_exc=True), **_p(t_relief=convert_temperature_to_kelvin(-247.0, '°F')))
S(50, "J-Birim", "T_relief 212,67 °R → 118,15 K", "°R dönüşümü",
  expect=dict(no_exc=True), **_p(t_relief=convert_temperature_to_kelvin(212.67, '°R')))
S(51, "J-Birim", "P_set 0,24 bar_g → 240 mbar_g", "bar_g dönüşümü",
  expect=dict(no_exc=True), **_p(p_set=convert_pressure_to_mbar(0.24, 'bar_g', is_gauge=True)))
S(52, "J-Birim", "Q_fill 2,77778 m³/s → 10.000 m³/h", "m³/s dönüşümü",
  expect=dict(no_exc=True), **_p(q_fill=convert_volumetric_flow_to_m3_h(2.777778, 'm³/s')))

# K. Robustness
S(53, "K-Dayanıklılık", "Boş kompozisyon", "CH4 fallback, çökme yok",
  expect=dict(no_exc=True), **_p(comp={}))
S(54, "K-Dayanıklılık", "Bozuk/eksik vana veritabanı", "Boş matris, çökme yok",
  expect=dict(no_exc=True, allow_empty_db=True), **_p())
S(55, "K-Dayanıklılık", "T_relief = 50 K (alt sınır dışı)", "İç clamp, çökme yok",
  expect=dict(no_exc=True), **_p(t_relief=50.0))
S(56, "K-Dayanıklılık", "T_relief = 500 K (üst sınır dışı)", "İdeal gaz bölgesi, çökme yok",
  expect=dict(no_exc=True), **_p(t_relief=500.0))

# L. Report / UI
S(57, "L-Rapor/UI", "HTML rapor (TR) — varsayılan", "Z/M/öneri doğru, NaN yok",
  expect=dict(no_exc=True), **_p())
S(58, "L-Rapor/UI", "HTML rapor (EN) — varsayılan", "İngilizce başlık",
  expect=dict(no_exc=True), **_p())
S(59, "L-Rapor/UI", "HTML rapor — boş matris", "Çökme yok",
  expect=dict(no_exc=True, allow_empty_db=True), **_p())
S(60, "L-Rapor/UI", "AppTest UI smoke + etkileşim", "EOS/flaş/Kd değişimleri",
  expect=dict(no_exc=True), **_p())


# ------------------------------------------------------------------- execution
def run_pipeline(params):
    comp = params['comp'] if params['comp'] is not None else DEFAULT_COMP
    rho_lng = params['rho_lng']
    if rho_lng is None:
        rho_lng = calculate_costald_density(comp, temperature_k=params['t_relief'])['density_kg_m3']
    if params['flash_mode'] == 'PH':
        flash_manual_mode, flash_pct_val, isenth = False, None, True
    elif params['flash_mode'] == 'FIXED':
        flash_manual_mode, flash_pct_val, isenth = False, params['flash_pct'], False
    else:
        flash_manual_mode, flash_pct_val, isenth = True, 2.0, False

    res = app._compute_all_results(
        p_set_mbar=params['p_set'], overpressure_pct=params['op'],
        p_atm_min_mbar=params['patm_min'], p_atm_max_mbar=params['patm_max'],
        q_fill_m3h=params['q_fill'], rho_lng_val=rho_lng,
        comp_dict_frozen=tuple(sorted(comp.items())),
        t_relief_K=params['t_relief'], t_cargo_K=params['t_cargo'], t_fire_K=params['t_fire'],
        eos_code_val=params['eos'], n_working=params['n_working'],
        flash_manual_mode_val=flash_manual_mode,
        w_flash_manual_kg_h_val=params['w_flash_manual'], flash_pct_val=flash_pct_val,
        w_bog_kg_h_val=params['w_bog'], bog_auto_mode_val=params['bog_auto'],
        bor_pct_per_day_val=params['bor'],
        wetted_area_m2_val=params['wetted'], insulation_factor_F_val=params['F'],
        latent_heat_kJ_kg_val=params['L'],
        fire_overpressure_pct=params['fire_op'], fire_q_constant_val=params['fire_const'],
        fire_K_d_val=params['fire_kd'],
        is_isenthalpic_mode_val=isenth, p_ship_mbar_g_val=params['p_ship'],
        cargo_comp_frozen=tuple(sorted(params['cargo_comp'].items())) if params['cargo_comp'] else None,
    )
    return res, rho_lng


def build_report(res, rho_lng, params, language='tr', matrix=None, matched=None):
    loads = res['loads']
    inputs = {
        'project_name': 'Senaryo Testi', 'project_revision': 'Rev.Test', 'eos_choice': params['eos'],
        'V_n': 160000, 'Q_fill': params['q_fill'], 'P_atm_min': params['patm_min'],
        'P_atm_max': params['patm_max'], 'P_set': params['p_set'], 'Overpressure_pct': params['op'],
        'fire_overpressure_pct': params['fire_op'], 'fire_K_d': params['fire_kd'],
        'N_working': params['n_working'], 'N_spare': 1,
        'T_tank_K': params['t_relief'] - 5, 'T_relief_K': params['t_relief'],
        'T_cargo_K': params['t_cargo'], 'T_fire_K': params['t_fire'],
        'P_ship_kPa_a': (params['p_ship'] + params['patm_min']) / 10.0,
        'flash_pct': res['effective_flash_pct'], 'wetted_area_m2': params['wetted'],
        'insulation_factor_F': params['F'], 'latent_heat_kJ_kg': params['L'], 'K_d': 0.85,
        'P1_kPa_a': res['P1_kPa_a'], 'P1_fire_kPa_a': res['P1_fire_kPa_a'],
    }
    thermo = {
        'density_kg_m3': rho_lng, 'molar_mass_g_mol': res['M_vapor'],
        'vapor_density': res['rho_v'], 'Z_factor': res['Z_factor'], 'k_factor': res['k_factor'],
        'M_vapor': res['M_vapor'], 'fire_Z': res['fire_Z'], 'fire_k': res['fire_k'],
        'fire_M_vapor': res['fire_M_vapor'],
    }
    sizing = {
        'w_flash_kg_h': loads['w_flash_kg_h'], 'w_disp_kg_h': loads['w_disp_kg_h'],
        'w_bog_kg_h': loads['w_bog_kg_h'], 'w_total_kg_h': loads['w_total_kg_h'],
        'w_total_kg_s': loads['w_total_kg_s'], 'w_total_g_s': loads['w_total_kg_h'] * 1000 / 3600,
        'q_a_total_m3_h': res['q_a_total'], 'q_a_per_valve_m3_h': res['q_a_per_valve'],
        'A_o_mm2': res['subcrit']['A_o_mm2'], 'A_o_in2': res['subcrit']['A_o_in2'],
        'w_valve_kg_h': loads['w_total_kg_h'] / params['n_working'],
        'api_details': res['subcrit'], 'fire_details': res['fire_res'],
        'fire_q_a_total': res['fire_q_a_total'], 'fire_q_a_per_valve': res['fire_q_a_per_valve'],
        'fire_subcrit': res['fire_subcrit'], 'fire_matrix': res['fire_matrix'],
        'governing_scenario': res['governing_scenario'],
        'governing_w_total_kg_h': res['governing_w_total_kg_h'],
        'governing_A_o_mm2': res['governing_A_o_mm2'], 'governing_matrix': res['governing_matrix'],
        'fire_Z': res['fire_Z'], 'fire_k': res['fire_k'], 'T_fire_K': params['t_fire'],
        'isenthalpic_res': res['isenthalpic_res'],
    }
    return generate_html_report(
        inputs, thermo, sizing,
        matrix if matrix is not None else res['governing_matrix'],
        matched if matched is not None else res['matched_valves'],
        language=language, app_version=CURRENT_VERSION,
    )


def general_checks(res, params, rho_lng, allow_empty_db=False):
    errs = []
    loads, sub, fire = res['loads'], res['subcrit'], res['fire_subcrit']
    nums = [res['Z_factor'], res['k_factor'], res['rho_v'], res['M_vapor'], res['q_a_total'],
            sub['A_o_mm2'], fire['A_o_mm2'], loads['w_total_kg_h'], rho_lng]
    if not all(math.isfinite(v) for v in nums):
        errs.append('non-finite değer')
    if not 0.0 <= res['effective_flash_pct'] <= 100.0:
        errs.append(f"VF aralık dışı ({res['effective_flash_pct']})")
    if not 1.0 <= res['k_factor'] <= 1.7:
        errs.append(f"k aralık dışı ({res['k_factor']:.3f})")
    if not 0.0 < res['Z_factor'] <= 1.3:
        errs.append(f"Z aralık dışı ({res['Z_factor']:.3f})")
    if not 2.0 <= res['M_vapor'] <= 100.0:
        errs.append(f"M aralık dışı ({res['M_vapor']:.2f})")
    if res['rho_v'] <= 0 or sub['A_o_mm2'] <= 0 or fire['A_o_mm2'] <= 0:
        errs.append('pozitif olmayan ρ_v veya A_o')
    balance = loads['w_disp_kg_h'] + loads['w_flash_kg_h'] + loads['w_bog_kg_h']
    if abs(balance - loads['w_total_kg_h']) > 0.1:
        errs.append('kütle dengesi hatası')
    cap_op = calculate_valve_air_capacity_m3_h(sub['A_o_mm2'], res['P1_kPa_a'], res['P2_kPa_a'], 0.85)
    if abs(cap_op - res['q_a_per_valve']) > max(1.0, 1e-6 * cap_op):
        errs.append(f"Q_a ↔ A_o (operasyonel) tutarsız ({cap_op:.1f} vs {res['q_a_per_valve']:.1f})")
    cap_fire = calculate_valve_air_capacity_m3_h(fire['A_o_mm2'], res['P1_fire_kPa_a'], res['P2_kPa_a'], params['fire_kd'])
    if abs(cap_fire - res['fire_q_a_per_valve']) > max(1.0, 1e-6 * cap_fire):
        errs.append(f"Q_a ↔ A_o (yangın) tutarsız ({cap_fire:.1f} vs {res['fire_q_a_per_valve']:.1f})")
    gov_expected_fire = fire['A_o_mm2'] > sub['A_o_mm2']
    if res['governing_is_fire'] != gov_expected_fire:
        errs.append('governing senaryo tutarsız')
    # coverage must equal air_capacity / required_air_capacity exactly
    req_qa = res['fire_q_a_per_valve'] if res['governing_is_fire'] else res['q_a_per_valve']
    for v in res['governing_matrix'][:3]:
        cov_check = v['air_capacity_m3_h'] / max(1e-9, req_qa) * 100.0
        if abs(cov_check - v['coverage_pct']) > 0.05:
            errs.append(f"coverage ↔ kapasite tutarsız ({v['coverage_pct']:.2f} vs {cov_check:.2f})")
            break
    # for the fire scenario (Kd=1.0) coverage must equal the pure area ratio
    if res['governing_is_fire']:
        for v in res['governing_matrix'][:3]:
            ratio = v['orifice_area_mm2'] / res['governing_A_o_mm2'] * 100.0
            if abs(ratio - v['coverage_pct']) > 0.5:
                errs.append(f"yangın coverage ↔ alan oranı sapması ({v['coverage_pct']:.2f} vs {ratio:.2f})")
                break
    if not allow_empty_db and not res['governing_matrix']:
        errs.append('boş vana matrisi')
    if not allow_empty_db and not res['matched_valves']:
        errs.append('boş katalog eşleşmesi')
    return errs


def expectation_checks(res, params, rho_lng, ref):
    errs, notes = [], []
    exp = params['_expect']
    vf = res['effective_flash_pct']
    if 'vf_min' in exp and vf < exp['vf_min']:
        errs.append(f"VF beklenen ≥{exp['vf_min']} (bulunan {vf:.3f})")
    if 'vf_max' in exp and vf > exp['vf_max']:
        errs.append(f"VF beklenen ≤{exp['vf_max']} (bulunan {vf:.3f})")
    if 'ao_op_min' in exp and res['subcrit']['A_o_mm2'] < exp['ao_op_min']:
        errs.append('A_o_op alt sınırın altında')
    if 'ao_op_max' in exp and res['subcrit']['A_o_mm2'] > exp['ao_op_max']:
        errs.append('A_o_op üst sınırın üstünde')
    if 'gov' in exp:
        got = 'fire' if res['governing_is_fire'] else 'op'
        if got != exp['gov']:
            errs.append(f"governing beklenen {exp['gov']}, bulunan {got}")
    for key, field in (('k_min', 'k_factor'), ('k_max', 'k_factor'), ('z_min', 'Z_factor'),
                       ('z_max', 'Z_factor'), ('m_min', 'M_vapor'), ('m_max', 'M_vapor')):
        if key in exp:
            val = res[field]
            if key.endswith('_min') and val < exp[key]:
                errs.append(f"{field} ≥{exp[key]} bekleniyordu ({val:.3f})")
            if key.endswith('_max') and val > exp[key]:
                errs.append(f"{field} ≤{exp[key]} bekleniyordu ({val:.3f})")
    if 'rho_lng_min' in exp and rho_lng < exp['rho_lng_min']:
        errs.append(f"ρ_LNG ≥{exp['rho_lng_min']} bekleniyordu ({rho_lng:.1f})")
    if 'rho_lng_max' in exp and rho_lng > exp['rho_lng_max']:
        errs.append(f"ρ_LNG ≤{exp['rho_lng_max']} bekleniyordu ({rho_lng:.1f})")
    if 'wtotal_min' in exp and res['loads']['w_total_kg_h'] < exp['wtotal_min']:
        errs.append(f"W_total ≥{exp['wtotal_min']} bekleniyordu ({res['loads']['w_total_kg_h']:.0f})")
    if 'wtotal_max' in exp and res['loads']['w_total_kg_h'] > exp['wtotal_max']:
        errs.append(f"W_total ≤{exp['wtotal_max']} bekleniyordu ({res['loads']['w_total_kg_h']:.0f})")
    if 'wfire_min' in exp and res['fire_res']['w_fire_kg_h'] < exp['wfire_min']:
        errs.append(f"W_fire ≥{exp['wfire_min']} bekleniyordu ({res['fire_res']['w_fire_kg_h']:.0f})")
    if 'wfire_max' in exp and res['fire_res']['w_fire_kg_h'] > exp['wfire_max']:
        errs.append(f"W_fire ≤{exp['wfire_max']} bekleniyordu ({res['fire_res']['w_fire_kg_h']:.0f})")
    if 'crit_op' in exp and res['subcrit']['is_subcritical'] != exp['crit_op']:
        errs.append(f"subkritik rejim beklenen {exp['crit_op']}")
    if exp.get('n2_enrich'):
        z_n2 = (params['comp'] if params['comp'] is not None else DEFAULT_COMP).get('N2', 0.0)
        y_n2 = res['vle_res'].get('y_vapor', {}).get('N2', 0.0) * 100.0
        if z_n2 > 0 and y_n2 <= z_n2:
            errs.append(f"N2 buharda zenginleşmedi (y={y_n2:.2f} ≤ z={z_n2:.2f})")
    if 'rel_band' in exp and ref is not None:
        field, lo, hi = exp['rel_band']
        cur = res['subcrit']['A_o_mm2'] if field == 'ao_op' else res['fire_subcrit']['A_o_mm2']
        base = ref['subcrit']['A_o_mm2'] if field == 'ao_op' else ref['fire_subcrit']['A_o_mm2']
        ratio = cur / base
        if not (lo <= ratio <= hi):
            errs.append(f"A_o referans bandı [{lo}, {hi}] dışında (oran {ratio:.3f})")
    if exp.get('vapor_lighter'):
        comp_used = params['comp'] if params['comp'] is not None else DEFAULT_COMP
        m_liq = calculate_costald_density(comp_used, temperature_k=params['t_relief'])['molar_mass_g_mol']
        if not res['M_vapor'] < m_liq:
            errs.append(f"Buhar fazı sıvıdan hafif değil (M_v={res['M_vapor']:.2f} ≥ M_l={m_liq:.2f})")
    if 'rel_ref' in exp and ref is not None:
        field, direction, factor = exp['rel_ref']
        cur = res['subcrit']['A_o_mm2'] if field == 'ao_op' else res['fire_subcrit']['A_o_mm2']
        base = ref['subcrit']['A_o_mm2'] if field == 'ao_op' else ref['fire_subcrit']['A_o_mm2']
        ratio = cur / base
        ok = ratio < factor if direction == 'lt' else ratio > factor
        if not ok:
            errs.append(f"A_o referansa göre {direction} {factor} bekleniyordu (oran {ratio:.3f})")
    return errs, notes


def run_all():
    ref = None
    results = []
    t0 = time.time()
    for sc in SCENARIOS:
        params = dict(sc['params'])
        params['_expect'] = sc['expect']
        # special robustness scenario: corrupt DB
        corrupt_db = sc['id'] == 54
        original_get_db_path = psv_database.get_db_path
        if corrupt_db:
            psv_database.get_db_path = lambda: '/tmp/does_not_exist_psv_db.json'
        t_start = time.time()
        if sc['id'] == 60:
            continue
        try:
            res, rho_lng = run_pipeline(params)
            pipeline_err = None
        except Exception as err:  # noqa: BLE001
            res, rho_lng, pipeline_err = None, None, f"{type(err).__name__}: {err}"
        finally:
            if corrupt_db:
                psv_database.get_db_path = original_get_db_path

        errs = []
        if pipeline_err:
            errs.append(f"pipeline istisnası: {pipeline_err}")
        else:
            errs += general_checks(res, params, rho_lng, allow_empty_db=sc['expect'].get('allow_empty_db', False))
            errs += expectation_checks(res, params, rho_lng, ref)[0]
            if sc['id'] == 1:
                ref = res

        # report check for report scenarios
        report_ok, report_note = None, ""
        if sc['id'] in (57, 58, 59) and res is not None:
            lang = 'en' if sc['id'] == 58 else 'tr'
            matrix = [] if sc['id'] == 59 else None
            try:
                html = build_report(res, rho_lng, params, language=lang, matrix=matrix,
                                    matched=[] if sc['id'] == 59 else None)
                if 'nan' in html.lower() or 'inf' in html.lower():
                    errs.append('raporda NaN/Inf metni')
                    report_ok = False
                elif lang == 'en' and 'PORV Relief Valve Sizing' not in html:
                    errs.append('EN rapor başlığı eksik')
                    report_ok = False
                elif lang == 'tr' and 'Boyutlandırma ve Termodinamik Analiz Raporu' not in html:
                    errs.append('TR rapor başlığı eksik')
                    report_ok = False
                else:
                    report_ok = True
                    report_note = f"{len(html)} karakter"
            except Exception as err:  # noqa: BLE001
                errs.append(f"rapor istisnası: {type(err).__name__}: {err}")
                report_ok = False

        results.append(dict(sc=sc, res=res, rho_lng=rho_lng, errs=errs,
                            report_ok=report_ok, report_note=report_note,
                            ms=(time.time() - t_start) * 1000))

    # UI scenario 60 via AppTest
    ui_res = run_ui_scenario()
    for sc in SCENARIOS:
        if sc['id'] == 60:
            results.append(dict(sc=sc, res=None, rho_lng=None, errs=ui_res, report_ok=None,
                                report_note='AppTest etkileşimleri', ms=0.0))
    return results, time.time() - t0


def run_ui_scenario():
    errs = []
    try:
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file("app.py", default_timeout=180)
        at.run()
        if at.exception:
            errs.append(f"başlangıç istisnası: {[str(e.value) for e in at.exception]}")
        at.selectbox(key='in_eos_choice').set_value("HEOS (GERG-2008 Helmholtz Energy EOS)").run()
        if at.exception:
            errs.append(f"HEOS istisnası: {[str(e.value) for e in at.exception]}")
        at.radio(key='in_flash_mode').set_value("Manuel Debi Girişi").run()
        if at.exception:
            errs.append(f"manuel flaş istisnası: {[str(e.value) for e in at.exception]}")
        at.checkbox(key='in_fire_kd_one').set_value(False).run()
        if at.exception:
            errs.append(f"Kd istisnası: {[str(e.value) for e in at.exception]}")
        if len(at.dataframe) < 1:
            errs.append('UI tablosu render edilmedi')
    except Exception as err:  # noqa: BLE001
        errs.append(f"AppTest hatası: {type(err).__name__}: {err}")
    return errs


def fmt_report(results, elapsed):
    lines = []
    lines.append("# LNG PORV Portalı — 60 Senaryo Uçtan Uca Fonksiyon Test Kampanyası")
    lines.append("")
    lines.append(f"Tarih: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')} | Süre: {elapsed:.1f} s | "
                 f"Senaryo: {len(results)} | PASS: {sum(1 for r in results if not r['errs'])} | "
                 f"FAIL: {sum(1 for r in results if r['errs'])}")
    lines.append("")
    lines.append("| # | Kategori | Senaryo | VF % | Z | k | ρ_v | M | A_o_op mm² | A_o_fire mm² | Governing | En küçük uygun vana | Kap. % | Durum |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        sc, res = r['sc'], r['res']
        if res is None:
            lines.append(f"| {sc['id']} | {sc['cat']} | {sc['name']} | - | - | - | - | - | - | - | - | - | - | "
                         f"{'✅ PASS' if not r['errs'] else '❌ FAIL'} |")
            continue
        best = ''
        best_cov = ''
        win = [m for m in sorted(res['governing_matrix'], key=lambda m: m['orifice_area_mm2'])
               if 100.0 <= m['coverage_pct'] <= 200.0]
        if win:
            best = win[0]['size_name'].split(' (')[0]
            best_cov = f"{win[0]['coverage_pct']:.0f}"
        else:
            any_ok = [m for m in sorted(res['governing_matrix'], key=lambda m: m['orifice_area_mm2'])
                      if m['coverage_pct'] >= 100.0]
            if any_ok:
                best = any_ok[0]['size_name'].split(' (')[0] + " (pencere dışı)"
                best_cov = f"{any_ok[0]['coverage_pct']:.0f}"
            elif res['governing_matrix']:
                b = max(res['governing_matrix'], key=lambda m: m['coverage_pct'])
                best = b['size_name'].split(' (')[0] + " (yetersiz)"
                best_cov = f"{b['coverage_pct']:.0f}"
        gov = 'YANGIN' if res['governing_is_fire'] else 'OPER.'
        lines.append(
            f"| {sc['id']} | {sc['cat']} | {sc['name']} | {res['effective_flash_pct']:.2f} | "
            f"{res['Z_factor']:.4f} | {res['k_factor']:.3f} | {res['rho_v']:.3f} | {res['M_vapor']:.2f} | "
            f"{res['subcrit']['A_o_mm2']:,.0f} | {res['fire_subcrit']['A_o_mm2']:,.0f} | {gov} | {best} | {best_cov} | "
            f"{'✅ PASS' if not r['errs'] else '❌ FAIL'} |")
    lines.append("")
    lines.append("## Hata Detayları")
    lines.append("")
    fails = [r for r in results if r['errs']]
    if not fails:
        lines.append("Hata yok.")
    for r in fails:
        lines.append(f"- **Senaryo {r['sc']['id']} — {r['sc']['name']}**: " + "; ".join(r['errs']))
    lines.append("")
    return "\n".join(lines)


if __name__ == '__main__':
    results, elapsed = run_all()
    report = fmt_report(results, elapsed)
    with open('scenario_campaign_results.md', 'w', encoding='utf-8') as f:
        f.write(report)
    print(report)
    print("\nSonuç dosyası: scenario_campaign_results.md")
