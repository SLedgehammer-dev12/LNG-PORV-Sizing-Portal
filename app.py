"""
LNG PORV Emniyet Vanası Boyutlandırma ve Termodinamik Analiz Yazılımı (Streamlit Dashboard)
Çoklu EOS Destekli (Peng-Robinson, SRK, GERG-2008), Dinamik T/P Bağlı k_mix(T,P) Hesabı,
Rachford-Rice VLE Flaş BOG Motoru, Dinamik Gaz Kompozisyonu Düzenleyicisi ve API 520 / NFPA 59A Standart Uyumlu.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import logging

from lng_thermo import calculate_costald_density, calculate_vapor_density, COMPONENT_DATA
from vle_thermo import calculate_two_phase_vle_flash, calculate_eos_mixture_properties, calculate_isenthalpic_flash, EOS_COMPONENT_DATA
from psv_sizing import calculate_relieving_loads, calculate_nfpa59a_air_equivalent, calculate_api520_subcritical_orifice_area, evaluate_valve_matrix, calculate_valve_capacity, calculate_bor_tank_bog, calculate_fire_scenario_load
from psv_database import search_matching_valves
from report_generator import generate_html_report

from unit_converter import (
    convert_pressure_to_mbar,
    convert_volumetric_flow_to_m3_h,
    convert_mass_flow_to_kg_h,
    convert_volume_to_m3,
    convert_temperature_to_kelvin,
    convert_density_to_kg_m3,
    convert_area_from_mm2,
    PRESSURE_UNITS_ABS,
    PRESSURE_UNITS_GAUGE,
    VOLUMETRIC_FLOW_UNITS,
    MASS_FLOW_UNITS,
    VOLUME_UNITS,
    DENSITY_UNITS,
    AREA_UNITS
)

logger = logging.getLogger(__name__)

# Page Config
st.set_page_config(
    page_title="LNG PORV Emniyet Vanası Boyutlandırma Portalı",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with High Contrast WCAG AA Compliance
st.markdown("""
<style>
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .main-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .main-title {
        color: #38bdf8;
        font-size: 24px;
        font-weight: 700;
        margin: 0;
    }
    .sub-title {
        color: #94a3b8;
        font-size: 14px;
        margin-top: 5px;
    }
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .metric-value {
        color: #38bdf8;
        font-size: 19px;
        font-weight: 700;
    }
    .metric-label {
        color: #cbd5e1;
        font-size: 12px;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Header Section
st.markdown("""
<div class="main-header">
    <div class="main-title">⚓ LNG PORV Emniyet Vanası Boyutlandırma Portalı</div>
    <div class="sub-title">Çoklu EOS (PR / SRK / GERG-2008), Dinamik k(T,P), VLE Flaş Motoru, COSTALD Kriyojenik Termodinamik ve API 520 Analiz Portalı</div>
</div>
""", unsafe_allow_html=True)

# Sidebar Input Controls with Dynamic Unit Selectors & EOS Selector
st.sidebar.header("⚙️ Girdi, EOS ve Birim Ayarları")

eos_choice = st.sidebar.selectbox(
    "📊 Termodinamik Durum Denklemi (EOS)",
    [
        "Peng-Robinson (PR 1976)",
        "Soave-Redlich-Kwong (SRK)",
        "HEOS (GERG-2008 Helmholtz Energy EOS)",
        "İdeal Gaz (Ideal Gas)"
    ],
    index=0,
    help="VLE Flaş dengesi, Z sıkıştırılabilirlik faktörü ve dinamik Cp/Cv k_mix(T,P) hesabı için EOS modeli."
)

eos_code = 'PR'
if 'SRK' in eos_choice:
    eos_code = 'SRK'
elif 'HEOS' in eos_choice or 'GERG' in eos_choice:
    eos_code = 'HEOS'
elif 'İdeal' in eos_choice:
    eos_code = 'IDEAL'

input_tab1, input_tab2, input_tab3 = st.sidebar.tabs(["Saha & Operasyon", "LNG Kompozisyon Kataloğu", "Flaş BOG Modu"])

with input_tab1:
    st.subheader("1. Tank & Saha Şartları")
    
    col_v, col_vu = st.columns([3, 2])
    with col_v:
        V_n_input = st.number_input("Tank Net Hacmi (V_n)", value=160000.0, step=5000.0, min_value=1.0)
    with col_vu:
        V_n_unit = st.selectbox("Hacim Birimi", list(VOLUME_UNITS.keys()), index=0)
    V_n = convert_volume_to_m3(V_n_input, V_n_unit)
    
    col_q, col_qu = st.columns([3, 2])
    with col_q:
        Q_fill_input = st.number_input("Max. LNG Dolum Debisi (Q_fill)", value=10000.0, step=500.0, min_value=1.0)
    with col_qu:
        Q_fill_unit = st.selectbox("Dolum Debi Birimi", list(VOLUMETRIC_FLOW_UNITS.keys()), index=0)
    Q_fill = convert_volumetric_flow_to_m3_h(Q_fill_input, Q_fill_unit)
    
    col_pmin, col_pmin_u = st.columns([3, 2])
    with col_pmin:
        P_atm_min_input = st.number_input("Min. Atmosferik Basınç (P_atm,min)", value=906.03, format="%.2f", min_value=100.0)
    with col_pmin_u:
        P_atm_min_unit = st.selectbox("Min Patm Birimi", list(PRESSURE_UNITS_ABS.keys()), index=0)
    P_atm_min = convert_pressure_to_mbar(P_atm_min_input, P_atm_min_unit, is_gauge=False)
    
    col_pmax, col_pmax_u = st.columns([3, 2])
    with col_pmax:
        P_atm_max_input = st.number_input("Max. Atmosferik Basınç (P_atm,max)", value=1014.602, format="%.3f", min_value=100.0)
    with col_pmax_u:
        P_atm_max_unit = st.selectbox("Max Patm Birimi", list(PRESSURE_UNITS_ABS.keys()), index=0)
    P_atm_max = convert_pressure_to_mbar(P_atm_max_input, P_atm_max_unit, is_gauge=False)
    
    st.subheader("2. PORV Emniyet Vanası Ayarları")
    col_pset, col_pset_u = st.columns([3, 2])
    with col_pset:
        P_set_input = st.number_input("PORV Set Basıncı (P_set)", value=240.0, step=10.0, min_value=1.0)
    with col_pset_u:
        P_set_unit = st.selectbox("Set Basınç Birimi", list(PRESSURE_UNITS_GAUGE.keys()), index=0)
    P_set = convert_pressure_to_mbar(P_set_input, P_set_unit, is_gauge=True)
    
    Overpressure_pct = st.number_input("İzin Verilen Overpressure (%)", value=10.0, step=1.0, min_value=0.0)
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        N_working = st.number_input("Çalışan Vana (N)", value=3, min_value=1, max_value=10)
    with col_v2:
        N_spare = st.number_input("Yedek Vana (+1)", value=1, min_value=0, max_value=5)

    st.subheader("3. Yangın Senaryosu (Fire Case) Şartları")
    wetted_area_m2 = st.number_input("Islatılmış Tank Yüzey Alanı (A_wetted, m²)", value=1200.0, step=100.0, min_value=1.0)
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        insulation_factor_F = st.number_input("Yalıtım Faktörü (F)", value=0.15, min_value=0.01, max_value=1.0, step=0.05, help="0.15 yalıtımlı tank, 1.0 yalıtımsız tank")
    with col_f2:
        latent_heat_kJ_kg = st.number_input("Gizli Isı (L, kJ/kg)", value=510.0, step=10.0, min_value=10.0)
    col_tfire, col_tfire_u = st.columns([3, 2])
    with col_tfire:
        T_fire_input = st.number_input("Yangın Tahliye Sıcaklığı (T_fire)", value=-100.0, step=5.0, help="Yangın senaryosunda tahliye edilen gazın beklenen sıcaklığı")
    with col_tfire_u:
        T_fire_unit = st.selectbox("Yangın T Birimi", ['°C', 'K', '°F', '°R'], index=0)
    T_fire_K = convert_temperature_to_kelvin(T_fire_input, T_fire_unit)

# Session State for Dynamic Gas Composition Editor
DEFAULT_ACTIVE_COMPS = ['CH4', 'C2H6', 'C3H8', 'iC4H10', 'nC4H10', 'N2']
DEFAULT_VALS = {'CH4': 90.50, 'C2H6': 5.50, 'C3H8': 2.50, 'iC4H10': 0.50, 'nC4H10': 0.50, 'N2': 0.50}

if 'active_components' not in st.session_state:
    st.session_state['active_components'] = DEFAULT_ACTIVE_COMPS.copy()

for c_key, val in DEFAULT_VALS.items():
    if f"comp_{c_key}" not in st.session_state:
        st.session_state[f"comp_{c_key}"] = val

with input_tab2:
    st.subheader("3. Dinamik LNG Kompozisyon Düzenleyicisi")
    st.caption("18 Gazlı Katalogdan bileşen seçip ekleyebilir ve mol yüzdelerini düzenleyebilirsiniz:")
    
    # Multiselect component picker
    available_comps = list(EOS_COMPONENT_DATA.keys())
    selected_comps = st.multiselect(
        "Katalogdan Eklenmek İstenen Gazlar:",
        options=available_comps,
        default=st.session_state['active_components'],
        format_func=lambda key: EOS_COMPONENT_DATA[key]['name']
    )
    if not selected_comps:
        st.error("❌ **Hata**: Kompozisyon hesabı için en az 1 adet gaz bileşeni seçilmelidir!")
        st.stop()
        
    st.session_state['active_components'] = selected_comps
    
    # Auto-normalize button
    if st.button("⚡ Kompozisyonu Otomatik %100'e Eşitle (Normalize)"):
        curr_sum = sum(st.session_state.get(f"comp_{k}", 0.0) for k in selected_comps)
        if curr_sum > 0:
            for k in selected_comps:
                st.session_state[f"comp_{k}"] = round((st.session_state.get(f"comp_{k}", 0.0) / curr_sum) * 100.0, 3)
            st.rerun()

    # Dynamic inputs for selected active components
    comp_dict = {}
    st.markdown("**Aktif Gaz Mol Yüzdeleri (%):**")
    for k in selected_comps:
        val = st.number_input(
            f"{EOS_COMPONENT_DATA[k]['name']} %",
            min_value=0.0,
            max_value=100.0,
            key=f"comp_{k}",
            step=0.1,
            format="%.2f"
        )
        comp_dict[k] = val
        
    st.subheader("4. Kriyojenik Sıcaklık Girdileri")
    col_tlng, col_tlng_u = st.columns([3, 2])
    with col_tlng:
        T_lng_input = st.number_input("Sıvı LNG Sıcaklığı (T_LNG)", value=-160.0, step=1.0)
    with col_tlng_u:
        T_lng_unit = st.selectbox("Sıvı T Birimi", ['°C', 'K', '°F', '°R'], index=0)
    T_lng_K = convert_temperature_to_kelvin(T_lng_input, T_lng_unit)
    
    col_trel, col_trel_u = st.columns([3, 2])
    with col_trel:
        T_relief_input = st.number_input("Tahliye Buhar Sıcaklığı (T_relief)", value=-155.0, step=1.0)
    with col_trel_u:
        T_relief_unit = st.selectbox("Buhar T Birimi", ['°C', 'K', '°F', '°R'], index=0)
    T_relief_K = convert_temperature_to_kelvin(T_relief_input, T_relief_unit)
    
    total_composition_pct = sum(comp_dict.values())
    if abs(total_composition_pct - 100.0) < 0.01:
        st.success(f"✅ Mol Toplamı: **%{total_composition_pct:.2f}** (Kusursuz)")
    elif total_composition_pct < 100.0:
        st.warning(f"⚠️ Mol Toplamı: **%{total_composition_pct:.2f}** (Eksik: %{100.0 - total_composition_pct:.2f})")
    else:
        st.error(f"❌ Mol Toplamı: **%{total_composition_pct:.2f}** (Fazla: %{total_composition_pct - 100.0:.2f})")
        
    costald_res = calculate_costald_density(comp_dict, temperature_k=T_lng_K)
    rho_lng_calculated = costald_res['density_kg_m3']
    M_mix_calculated = costald_res['molar_mass_g_mol']
    
    st.info(f"**COSTALD Sıvı Yoğunluğu ({T_lng_input:.1f} {T_lng_unit})**: {rho_lng_calculated:.2f} kg/m³")
    st.info(f"**Mol Kütlesi (M)**: {M_mix_calculated:.2f} g/mol")
    
    override_rho = st.checkbox("Sıvı Yoğunluğunu Manuel Değiştir", value=False)
    if override_rho:
        col_rho, col_rhou = st.columns([3, 2])
        with col_rho:
            rho_input = st.number_input("Manuel LNG Yoğunluğu", value=471.0)
        with col_rhou:
            rho_unit = st.selectbox("Yoğunluk Birimi", list(DENSITY_UNITS.keys()), index=0)
        rho_lng = convert_density_to_kg_m3(rho_input, rho_unit)
    else:
        rho_lng = rho_lng_calculated

with input_tab3:
    st.subheader("5. Gemi Transfer Basıncı (İzentalpik Flaş İçin)")
    col_pship, col_pship_u = st.columns([3, 2])
    with col_pship:
        P_ship_input = st.number_input("Gemi Transfer Basıncı (P_ship)", value=5.0, step=0.5, min_value=0.1, help="LNG gemisinin tanka transfer basıncı (tipik 4-8 bar_g)")
    with col_pship_u:
        P_ship_unit = st.selectbox("P_ship Birimi", list(PRESSURE_UNITS_GAUGE.keys()), index=0, key="pship_unit")
    P_ship_mbar_g = convert_pressure_to_mbar(P_ship_input, P_ship_unit, is_gauge=True)

    st.subheader("6. Flaş BOG Debisi Giriş Modu")
    flash_mode = st.radio(
        "Flaş BOG Hesap Modu:",
        ["İzentalpik Flaş (PH-Flash, EOS)", "EOS VLE Flaş Oranı (%V/F)", "Sabit Flaş Oranı (%)", "Manuel Debi Girişi"],
        index=0,
        help="PH-Flash: İzentalpik genleşme ile gemi basıncından tank basıncına flaş hesabı. VLE Flash: Tank tahliye koşullarında PT-flaş."
    )
    
    if flash_mode == "Manuel Debi Girişi":
        flash_manual_mode = True
        col_wf, col_wfu = st.columns([3, 2])
        with col_wf:
            w_flash_input = st.number_input("Manuel Flaş BOG Debisi", value=94200.0, step=1000.0)
        with col_wfu:
            w_flash_unit = st.selectbox("Flaş Debi Birimi", list(MASS_FLOW_UNITS.keys()), index=0)
        w_flash_manual_kg_h = convert_mass_flow_to_kg_h(w_flash_input, w_flash_unit)
        manual_flash_pct = 2.0
        is_isenthalpic_mode = False
    elif flash_mode == "Sabit Flaş Oranı (%)":
        flash_manual_mode = False
        w_flash_manual_kg_h = 94200.0
        manual_flash_pct = st.number_input("Manuel Sabit Flaş Oranı (%)", value=2.0, step=0.1)
        is_isenthalpic_mode = False
    elif flash_mode == "İzentalpik Flaş (PH-Flash, EOS)":
        flash_manual_mode = False
        w_flash_manual_kg_h = 94200.0
        manual_flash_pct = None
        is_isenthalpic_mode = True
    else: # EOS VLE Flaş Oranı (%V/F)
        flash_manual_mode = False
        w_flash_manual_kg_h = 94200.0
        manual_flash_pct = None
        is_isenthalpic_mode = False

    st.subheader("7. Tank Isı Girişi BOG Giriş Modu")
    bog_mode = st.radio(
        "Tank BOG Hesaplama Yöntemi:",
        ["Otomatik (BOR %/gün Tank Hacminden)", "Manuel BOG Debisi Girişi"],
        index=0,
        help="Tank net hacmi (V_n) ve günlük kaynama oranı (% BOR/gün) ile otomatik hesaplama veya manuel BOG debisi."
    )
    
    if bog_mode == "Otomatik (BOR %/gün Tank Hacminden)":
        bog_auto_mode = True
        bor_pct_per_day = st.number_input("Günlük Kaynama Oranı (BOR %/gün)", value=0.10, step=0.01, min_value=0.01, format="%.2f", help="Tipik LNG tam dolum tank BOR değeri: %0.05 - %0.15 /gün aralığındadır.")
        bor_calc = calculate_bor_tank_bog(tank_volume_m3=V_n, lng_density_kg_m3=rho_lng, bor_pct_per_day=bor_pct_per_day)
        w_bog_kg_h = bor_calc['w_bog_kg_h']
        st.info(f"💡 Otomatik Hesaplanan Tank BOG: **{w_bog_kg_h:,.1f} kg/h** (BOR: %{bor_pct_per_day:.2f}/gün)")
    else:
        bog_auto_mode = False
        bor_pct_per_day = 0.10
        col_wbog, col_wbogu = st.columns([3, 2])
        with col_wbog:
            w_bog_input = st.number_input("Isı Girişi Tank BOG Debisi", value=1570.0, step=100.0)
        with col_wbogu:
            w_bog_unit = st.selectbox("BOG Debi Birimi", list(MASS_FLOW_UNITS.keys()), index=0)
        w_bog_kg_h = convert_mass_flow_to_kg_h(w_bog_input, w_bog_unit)

# --- CORE THERMODYNAMIC & RELIEF CALCULATIONS ---

def _compute_all_results(
    p_set_mbar, overpressure_pct, p_atm_min_mbar, p_atm_max_mbar,
    q_fill_m3h, rho_lng_val, comp_dict_frozen, t_relief_K, t_lng_K,
    t_fire_K, eos_code_val, n_working, flash_manual_mode_val,
    w_flash_manual_kg_h_val, flash_pct_val, w_bog_kg_h_val,
    bog_auto_mode_val, bor_pct_per_day_val,
    wetted_area_m2_val, insulation_factor_F_val, latent_heat_kJ_kg_val,
    is_isenthalpic_mode_val=False, p_ship_mbar_g_val=5000.0
):
    """Cached computation pipeline for all thermodynamic and sizing results."""
    comp_dict = dict(comp_dict_frozen)

    P1_mbar_a = p_set_mbar + (p_set_mbar * (overpressure_pct / 100.0)) + p_atm_min_mbar
    P1_kPa_a = P1_mbar_a / 10.0
    P2_kPa_a = p_atm_min_mbar / 10.0

    # Operational VLE Flash
    vle_res = calculate_two_phase_vle_flash(comp_dict, temperature_k=t_relief_K, pressure_kPa_a=P1_kPa_a, eos=eos_code_val)
    Z_factor = vle_res['Z_gas']
    k_factor = vle_res['k_mix']
    rho_v = vle_res['rho_v_kg_m3']
    M_vapor = vle_res['M_vapor_g_mol']

    # Isenthalpic (PH) Flash or fallback to PT-flash / manual
    isenthalpic_res = None
    if is_isenthalpic_mode_val:
        P_ship_kPa_a = (p_ship_mbar_g_val + p_atm_min_mbar) / 10.0
        P_tank_kPa_a = (p_set_mbar + p_atm_min_mbar) / 10.0
        isenthalpic_res = calculate_isenthalpic_flash(
            comp_dict,
            t_feed_k=t_lng_K,
            p_feed_kPa_a=P_ship_kPa_a,
            p_flash_kPa_a=P_tank_kPa_a,
            eos=eos_code_val
        )
        effective_flash_pct = isenthalpic_res['flash_pct']
    else:
        effective_flash_pct = vle_res['flash_pct'] if flash_pct_val is None else flash_pct_val

    loads = calculate_relieving_loads(
        q_fill_m3_h=q_fill_m3h, rho_lng_kg_m3=rho_lng_val, rho_v_kg_m3=rho_v,
        flash_pct=effective_flash_pct, w_bog_kg_h=w_bog_kg_h_val,
        flash_manual_mode=flash_manual_mode_val,
        w_flash_manual_kg_h=w_flash_manual_kg_h_val
    )

    q_a_total = calculate_nfpa59a_air_equivalent(loads['w_total_kg_s'], temperature_k=t_relief_K, Z=Z_factor, M_g_mol=M_vapor)
    q_a_per_valve = q_a_total / n_working

    subcrit = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=loads['w_total_kg_h'] / n_working,
        P1_kPa_a=P1_kPa_a, P2_kPa_a=P2_kPa_a,
        temperature_k=t_relief_K, M_g_mol=M_vapor, Z=Z_factor, k=k_factor, K_d=0.85
    )

    matrix = evaluate_valve_matrix(
        q_a_per_valve_m3_h=q_a_per_valve, P1_kPa_a=P1_kPa_a, P2_kPa_a=P2_kPa_a,
        temperature_k=t_relief_K, M_g_mol=M_vapor, Z=Z_factor, k=k_factor, K_d=0.85
    )

    # Fire Scenario
    fire_res = calculate_fire_scenario_load(
        wetted_area_m2=wetted_area_m2_val, insulation_factor_F=insulation_factor_F_val,
        latent_heat_kJ_kg=latent_heat_kJ_kg_val
    )

    fire_vle_res = calculate_two_phase_vle_flash(comp_dict, temperature_k=t_fire_K, pressure_kPa_a=P1_kPa_a, eos=eos_code_val)
    fire_Z = fire_vle_res['Z_gas']
    fire_k = fire_vle_res['k_mix']
    fire_M_vapor = fire_vle_res['M_vapor_g_mol']

    fire_q_a_total = calculate_nfpa59a_air_equivalent(fire_res['w_fire_kg_s'], temperature_k=t_fire_K, Z=fire_Z, M_g_mol=fire_M_vapor)
    fire_q_a_per_valve = fire_q_a_total / n_working

    fire_subcrit = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=fire_res['w_fire_kg_h'] / n_working,
        P1_kPa_a=P1_kPa_a, P2_kPa_a=P2_kPa_a,
        temperature_k=t_fire_K, M_g_mol=fire_M_vapor, Z=fire_Z, k=fire_k, K_d=1.0
    )

    fire_matrix = evaluate_valve_matrix(
        q_a_per_valve_m3_h=fire_q_a_per_valve, P1_kPa_a=P1_kPa_a, P2_kPa_a=P2_kPa_a,
        temperature_k=t_fire_K, M_g_mol=fire_M_vapor, Z=fire_Z, k=fire_k, K_d=1.0
    )

    # Governing Scenario by orifice area
    if fire_subcrit['A_o_mm2'] > subcrit['A_o_mm2']:
        governing_scenario = "🔥 Yangin Senaryosu (Fire Case)"
        governing_w_total_kg_h = fire_res['w_fire_kg_h']
        governing_q_a_total = fire_q_a_total
        governing_A_o_mm2 = fire_subcrit['A_o_mm2']
        governing_matrix = fire_matrix
        governing_is_fire = True
    else:
        governing_scenario = "⚙️ Operasyonel Senaryo (Dolum + Flas + BOG)"
        governing_w_total_kg_h = loads['w_total_kg_h']
        governing_q_a_total = q_a_total
        governing_A_o_mm2 = subcrit['A_o_mm2']
        governing_matrix = matrix
        governing_is_fire = False

    # Matched valves use governing A_o
    matched_valves = search_matching_valves(
        req_orifice_area_mm2=governing_A_o_mm2,
        required_air_capacity_m3_h=governing_q_a_total / n_working,
        P1_kPa_a=P1_kPa_a
    )

    return {
        'P1_kPa_a': P1_kPa_a, 'P2_kPa_a': P2_kPa_a, 'P1_mbar_a': P1_mbar_a,
        'vle_res': vle_res, 'Z_factor': Z_factor, 'k_factor': k_factor, 'rho_v': rho_v,
        'M_vapor': M_vapor, 'effective_flash_pct': effective_flash_pct, 'loads': loads,
        'q_a_total': q_a_total, 'q_a_per_valve': q_a_per_valve,
        'subcrit': subcrit, 'matrix': matrix,
        'fire_res': fire_res, 'fire_Z': fire_Z, 'fire_k': fire_k, 'fire_M_vapor': fire_M_vapor,
        'fire_q_a_total': fire_q_a_total, 'fire_q_a_per_valve': fire_q_a_per_valve,
        'fire_subcrit': fire_subcrit, 'fire_matrix': fire_matrix,
        'governing_scenario': governing_scenario, 'governing_w_total_kg_h': governing_w_total_kg_h,
        'governing_q_a_total': governing_q_a_total, 'governing_A_o_mm2': governing_A_o_mm2,
        'governing_matrix': governing_matrix, 'governing_is_fire': governing_is_fire,
        'matched_valves': matched_valves, 'eos_code': eos_code_val,
        'isenthalpic_res': isenthalpic_res
    }


try:
    # Apply Streamlit caching when running inside Streamlit, otherwise call directly
    try:
        compute_all_results = st.cache_data(show_spinner="Hesaplanıyor...")(_compute_all_results)
    except Exception:
        compute_all_results = _compute_all_results

    results = compute_all_results(
        p_set_mbar=P_set, overpressure_pct=Overpressure_pct,
        p_atm_min_mbar=P_atm_min, p_atm_max_mbar=P_atm_max,
        q_fill_m3h=Q_fill, rho_lng_val=rho_lng,
        comp_dict_frozen=tuple(sorted(comp_dict.items())),
        t_relief_K=T_relief_K, t_lng_K=T_lng_K, t_fire_K=T_fire_K,
        eos_code_val=eos_code, n_working=N_working,
        flash_manual_mode_val=flash_manual_mode,
        w_flash_manual_kg_h_val=w_flash_manual_kg_h, flash_pct_val=manual_flash_pct,
        w_bog_kg_h_val=w_bog_kg_h, bog_auto_mode_val=bog_auto_mode,
        bor_pct_per_day_val=bor_pct_per_day,
        wetted_area_m2_val=wetted_area_m2, insulation_factor_F_val=insulation_factor_F,
        latent_heat_kJ_kg_val=latent_heat_kJ_kg,
        is_isenthalpic_mode_val=is_isenthalpic_mode,
        p_ship_mbar_g_val=P_ship_mbar_g
    )

    # Unpack results
    P1_kPa_a = results['P1_kPa_a']; P2_kPa_a = results['P2_kPa_a']; P1_mbar_a = results['P1_mbar_a']
    vle_res = results['vle_res']; Z_factor = results['Z_factor']; k_factor = results['k_factor']
    rho_v = results['rho_v']; M_vapor = results['M_vapor']
    effective_flash_pct = results['effective_flash_pct']; loads = results['loads']
    q_a_total = results['q_a_total']; q_a_per_valve = results['q_a_per_valve']
    subcrit = results['subcrit']; matrix = results['matrix']
    fire_res = results['fire_res']; fire_Z = results['fire_Z']; fire_k = results['fire_k']
    fire_M_vapor = results['fire_M_vapor']; fire_q_a_total = results['fire_q_a_total']
    fire_q_a_per_valve = results['fire_q_a_per_valve']; fire_subcrit = results['fire_subcrit']
    fire_matrix = results['fire_matrix']; governing_scenario = results['governing_scenario']
    governing_w_total_kg_h = results['governing_w_total_kg_h']
    governing_q_a_total = results['governing_q_a_total']
    governing_A_o_mm2 = results['governing_A_o_mm2']
    governing_matrix = results['governing_matrix']; governing_is_fire = results['governing_is_fire']
    matched_valves = results['matched_valves']
    isenthalpic_res = results.get('isenthalpic_res', None)

    # Report Data Dictionary Compilation
    report_inputs = {
        'Q_fill': Q_fill, 'P_atm_min': P_atm_min, 'P_set': P_set,
        'Overpressure_pct': Overpressure_pct, 'T_relief_K': T_relief_K,
        'flash_pct': effective_flash_pct, 'flash_manual_mode': flash_manual_mode,
        'bog_auto_mode': bog_auto_mode, 'bor_pct_per_day': bor_pct_per_day,
        'wetted_area_m2': wetted_area_m2, 'insulation_factor_F': insulation_factor_F,
        'latent_heat_kJ_kg': latent_heat_kJ_kg, 'K_d': 0.85, 'P1_kPa_a': P1_kPa_a,
        'T_fire_K': T_fire_K, 'N_working': N_working, 'N_spare': N_spare, 'V_n': V_n,
        'P_atm_max': P_atm_max
    }
    
    report_thermo = {
        'density_kg_m3': rho_lng, 'molar_mass_g_mol': M_vapor,
        'vapor_density': rho_v, 'Z_factor': Z_factor,
        'k_factor': k_factor, 'M_vapor': M_vapor,
        'fire_Z': fire_Z, 'fire_k': fire_k, 'fire_M_vapor': fire_M_vapor
    }
    
    report_sizing = {
        'w_flash_kg_h': loads['w_flash_kg_h'], 'w_disp_kg_h': loads['w_disp_kg_h'],
        'w_bog_kg_h': loads['w_bog_kg_h'], 'w_total_kg_h': loads['w_total_kg_h'],
        'w_total_kg_s': loads['w_total_kg_s'], 'w_total_g_s': loads['w_total_kg_h'] * 1000.0 / 3600.0,
        'q_a_total_m3_h': q_a_total, 'q_a_per_valve_m3_h': q_a_per_valve,
        'A_o_mm2': subcrit['A_o_mm2'], 'A_o_in2': subcrit['A_o_in2'],
        'w_valve_kg_h': loads['w_total_kg_h'] / N_working,
        'api_details': subcrit, 'fire_details': fire_res, 'fire_q_a_total': fire_q_a_total,
        'fire_q_a_per_valve': fire_q_a_per_valve, 'fire_subcrit': fire_subcrit,
        'fire_matrix': fire_matrix, 'governing_scenario': governing_scenario,
        'governing_w_total_kg_h': governing_w_total_kg_h,
        'governing_A_o_mm2': governing_A_o_mm2, 'governing_matrix': governing_matrix,
        'fire_Z': fire_Z, 'fire_k': fire_k, 'T_fire_K': T_fire_K
    }

except Exception as e:
    st.error(f"❌ **Termodinamik veya Hidrolik Hesaplama Hatası**: {str(e)}")
    logger.exception("Error in core calculation pipeline")
    st.stop()

if Overpressure_pct == 0.0:
    st.info("ℹ️ **Aşırı Basınç Bilgisi**: Overpressure **%0.0** seçilmiştir. Emniyet vanası set basıncında (Relieving Pressure = Set Pressure + Patm) tam açılma kapasitesiyle değerlendirilmektedir.")

# P_atm_max design pressure check
P1_max_kPa_a = (P_set + P_set * (Overpressure_pct / 100.0) + P_atm_max) / 10.0
P_design_mbar_g = P_set + P_atm_max - 1013.25
col_dp1, col_dp2 = st.columns(2)
with col_dp1:
    st.info(f"""
    ℹ️ **Max. Atmosferik Basınç Tasarım Kontrolü**:
    - Max. Relieving Pressure (P1_max): **{P1_max_kPa_a:.2f} kPa_a**
    - Tank Tasarım Basıncı (P_set + P_atm_max): **{P_design_mbar_g:.1f} mbar_g** (P_atm_max = {P_atm_max:.2f} mbar_a bazında)
    """)
with col_dp2:
    st.info(f"""
    ℹ️ **Boyutlandırma Bazı (Minimum Atmosferik)**:
    - P1 (Kritik Boyutlandırma): **{P1_kPa_a:.2f} kPa_a** (P_atm_min = {P_atm_min:.2f} mbar_a)
    - En düşük gaz yoğunluğu → en büyük orifis alanı ihtiyacı (konservatif yaklaşım)
    """)

# --- MAIN DASHBOARD DISPLAY ---

# Prominent Total Composition Validation Alert Box
if abs(total_composition_pct - 100.0) >= 0.01:
    diff_pct = 100.0 - total_composition_pct
    st.warning(f"""
    ⚠️ **LNG Kompozisyon Uyarısı**: Girilen gaz bileşenlerinin mol toplamı **%{total_composition_pct:.2f}** seviyesindedir (Fark: **%{diff_pct:+.2f}**).
    Hesaplamalar otomatik %100'e normalize edilen kesirlerle yürütülmüştür. İsterseniz sol paneldeki **"⚡ Kompozisyonu Otomatik %100'e Eşitle"** butonuna basabilirsiniz.
    """)
else:
    st.success(f"✅ **LNG Kompozisyon Doğrulaması**: Girilen gaz bileşenlerinin mol toplamı tam olarak **%100.00**'dir.")

# Metrics Row (6 key thermodynamic metrics including Z_gas and dynamic k_mix(T,P))
m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)

with m_col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{rho_lng:.1f} kg/m³</div>
        <div class="metric-label">Sıvı LNG Yoğunluğu (ρ_LNG @ {T_lng_input:.1f} {T_lng_unit})</div>
    </div>
    """, unsafe_allow_html=True)

with m_col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{M_vapor:.2f} g/mol</div>
        <div class="metric-label">Buhar Faz Mol Kütlesi (M_vapor)</div>
    </div>
    """, unsafe_allow_html=True)

with m_col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{Z_factor:.4f}</div>
        <div class="metric-label">Gaz Z Faktörü ({vle_res['eos_used']})</div>
    </div>
    """, unsafe_allow_html=True)

with m_col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{k_factor:.3f}</div>
        <div class="metric-label">Dinamik k = Cp/Cv ({T_relief_input:.1f} {T_relief_unit})</div>
    </div>
    """, unsafe_allow_html=True)

with m_col5:
    if isenthalpic_res is not None:
        flash_label = f"İzentalpik Flaş Oranı (VF)"
        flash_value = f"%{isenthalpic_res['flash_pct']:.2f}"
        if isenthalpic_res['converged']:
            flash_tooltip = f"T_flash={isenthalpic_res['T_flash_K']:.2f}K"
        else:
            flash_tooltip = "Yakınsama uyarısı"
    else:
        flash_label = "VLE Flaş Buhar Oranı (V/F)"
        flash_value = f"%{vle_res['flash_pct']:.2f}"
        flash_tooltip = ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{flash_value}</div>
        <div class="metric-label">{flash_label}</div>
    </div>
    """, unsafe_allow_html=True)

with m_col6:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{loads['w_total_kg_h']:,.0f} kg/h</div>
        <div class="metric-label">Toplam Tahliye Debisi (W_total)</div>
    </div>
    """, unsafe_allow_html=True)

# Main Section 1: Dynamic Orifice Matrix
st.header("1. Standart Orifis Alanı Karşılaştırma Matrisi")
st.caption(f"Min. Sahadaki Atmosferik Basınç ({P_atm_min:.2f} mbar_a) ve Relieving Pressure ({P1_mbar_a:.2f} mbar_a) altında değerlendirme:")

filter_mode = st.radio(
    "Vana Görünüm Filtresi:",
    ["Tüm Vanaları Göster", "Yalnızca Uyumlu Vanaları Göster (Kapasite ≥ %100)"],
    index=0,
    horizontal=True
)

matrix_df = pd.DataFrame(matrix)
matrix_df = matrix_df.sort_values(by='coverage_pct', ascending=False)

if filter_mode == "Yalnızca Uyumlu Vanaları Göster (Kapasite ≥ %100)":
    matrix_df = matrix_df[matrix_df['coverage_pct'] >= 100.0]

matrix_df_display = matrix_df[['size_name', 'orifice_area_mm2', 'air_capacity_m3_h', 'coverage_pct', 'status']].copy()
matrix_df_display.columns = ['Vana Anma Ölçüsü & Markası', 'Efektif Orifis Alanı (mm²)', 'Hava Tahliye Kapasitesi (m³/h)', 'Kapasite Oranı (%)', 'Teknik Değerlendirme']

st.dataframe(
    matrix_df_display.style.format({
        'Efektif Orifis Alanı (mm²)': '{:,.0f}',
        'Hava Tahliye Kapasitesi (m³/h)': '{:,.0f}',
        'Kapasite Oranı (%)': '%{:.1f}'
    })
)

# Governing Scenario Valve Matrix (conditional fire display)
if governing_is_fire:
    st.subheader("🔥 Yangın Senaryosu — Hüküm Süren Vana Matrisi")
    st.caption(f"Yangın Tahliye Sıcaklığı: {T_fire_input:.1f} {T_fire_unit} | Q_fire = {fire_res['q_fire_kW']:,.1f} kW | W_fire = {fire_res['w_fire_kg_h']:,.1f} kg/h | K_d = 1.0")

    gov_df = pd.DataFrame(governing_matrix)
    gov_df = gov_df.sort_values(by='coverage_pct', ascending=False)
    gov_df_display = gov_df[['size_name', 'orifice_area_mm2', 'air_capacity_m3_h', 'coverage_pct', 'status']].copy()
    gov_df_display.columns = ['Vana Anma Ölçüsü & Markası', 'Efektif Orifis Alanı (mm²)', 'Hava Tahliye Kapasitesi (m³/h)', 'Kapasite Oranı (%)', 'Teknik Değerlendirme']

    st.dataframe(
        gov_df_display.style.format({
            'Efektif Orifis Alanı (mm²)': '{:,.0f}',
            'Hava Tahliye Kapasitesi (m³/h)': '{:,.0f}',
            'Kapasite Oranı (%)': '%{:.1f}'
        })
    )
else:
    st.caption("ℹ️ Operasyonel senaryo hüküm sürmektedir — yangın senaryosu ilave kapasite gerektirmemektedir.")

# Main Section 1.5: Detailed Engineering Formulas & Parameter Values
st.header("1.5. Detaylı Mühendislik Formülleri, Sayısal Parametre Değerleri ve Yangın Senaryosu")
st.caption("Aşağıdaki sekmelerde hesaplamalarda kullanılan matematiksel formüller ve sayısal parametre girdileri detaylandırılmıştır:")

exp1, exp2, exp3, exp4 = st.tabs([
    "📐 1. Toplam Tahliye Debisi & Alt Debiler",
    "💨 2. NFPA 59A Eşdeğer Hava Debisi (Q_a)",
    "🔥 3. API 520 Subcritical Orifis Alanı (A_o)",
    "🚒 4. Yangın Senaryosu (Fire Case) Analizi"
])

with exp1:
    st.markdown(f"""
    #### 📐 Toplam Tahliye Debisi Formülleri (W_total)
    - **Sıvı Yerdeğiştirme Debisi (W_disp)**:
      W_disp = Q_fill × ρ_v = {Q_fill:,.0f} m³/h × {rho_v:.3f} kg/m³ = **{loads['w_disp_kg_h']:,.1f} kg/h**
    - **Flaş BOG Debisi (W_flash)**:
      W_flash = Q_fill × ρ_LNG × (% Flaş) = {Q_fill:,.0f} × {rho_lng:.1f} × {effective_flash_pct / 100.0:.4f} = **{loads['w_flash_kg_h']:,.1f} kg/h**
    - **Isı Girişi Tank BOG Debisi (W_bog)**:
      {f"W_bog = V_n × ρ_LNG × (BOR / 2400) = {V_n:,.0f} × {rho_lng:.1f} × ({bor_pct_per_day:.2f} / 2400) = **{w_bog_kg_h:,.1f} kg/h**" if bog_auto_mode else f"W_bog = **{w_bog_kg_h:,.1f} kg/h** (Manuel Giriş)"}
    - **Toplam Kütlesel Operasyonel Tahliye Debisi (W_total)**:
      W_total = W_disp + W_flash + W_bog = **{loads['w_total_kg_h']:,.1f} kg/h** ({loads['w_total_kg_s'] * 1000.0:.2f} g/s)
    """)
    if isenthalpic_res is not None:
        st.info(f"""
        #### 🔬 İzentalpik Flaş (PH-Flash) Detayı ({isenthalpic_res['eos_used']})

        | Parametre | Değer | Birim |
        | :--- | :---: | :---: |
        | Besleme Entalpisi (h_feed) | **{isenthalpic_res['h_feed_J_mol']:.1f}** | J/mol |
        | Flaş Sıcaklığı (T_flash) | **{isenthalpic_res['T_flash_K']:.2f}** | K |
        | Buhar Oranı (VF) | **%{isenthalpic_res['flash_pct']:.3f}** | mol/mol |
        | Çözüm Yakınsadı | **{'Evet' if isenthalpic_res['converged'] else 'Hayır'}** | - |
        """)

with exp2:
    st.markdown(f"""
    #### 💨 NFPA 59A Madde 8.4.10.7.4.2 Eşdeğer Hava Debisi Formülü (Q_a)
    `Q_a = 0.93 × W_total_kg_s × √(T × Z / M) × 990.8`

    | Parametre Tanımı | Sembol | Sayısal Değer | Birim |
    | :--- | :---: | :---: | :---: |
    | Toplam Kütlesel Tahliye Debisi | W_total | **{loads['w_total_kg_s']:.3f}** | kg/s |
    | Tahliye Sıcaklığı | T | **{T_relief_K:.2f}** | K |
    | Gaz Sıkıştırılabilirlik Faktörü ({vle_res['eos_used']}) | Z | **{Z_factor:.4f}** | - |
    | Buhar Faz Mol Kütlesi | M | **{M_vapor:.2f}** | g/mol |
    | **NFPA 59A Toplam Eşdeğer Hava Debisi** | **Q_a** | **{q_a_total:,.1f}** | **m³/h Hava** |
    | **Vana Başına Düşen Hava Debisi ({N_working} Çalışan)** | **Q_a,per_valve** | **{q_a_per_valve:,.1f}** | **m³/h Hava/Vana** |
    """)

with exp3:
    st.markdown(f"""
    #### 🔥 API 520 Part I Subcritical Orifis Alanı Formülü (A_o)
    `A_o = (17.9 × W_valve) / (F2 × Kd × Kb × Kc × √(P1 × ΔP)) × √(T × Z / M)`
    `F2 = √( [k/(k-1)] × r^(2/k) × [(1 - r^((k-1)/k)) / (1 - r)] ),  r = P2 / P1`

    | Parametre Tanımı | Sembol | Sayısal Değer | Birim / Not |
    | :--- | :---: | :---: | :--- |
    | Vana Başına Kütlesel Yük ({N_working} Vana) | W_valve | **{loads['w_total_kg_h']/N_working:,.1f}** | kg/h |
    | Relieving Absolüt Basınç (P1) | P1 | **{P1_kPa_a:.2f}** | kPa_a ({P1_mbar_a:.1f} mbar_a) |
    | Çıkış Sırt Basıncı (P2) | P2 | **{P2_kPa_a:.2f}** | kPa_a ({P_atm_min:.1f} mbar_a) |
    | Basınç Düşüşü (ΔP) | ΔP | **{P1_kPa_a - P2_kPa_a:.2f}** | kPa |
    | Basınç Oranı (r = P2/P1) | r | **{P2_kPa_a/P1_kPa_a:.4f}** | Subcritical Rejim (r > r_c = {subcrit['r_c']:.4f}) |
    | Subcritical Akış Katsayısı (F2) | F2 | **{subcrit['F2']:.4f}** | API 520 Subcritical Terimi |
    | Vana Tahliye Katsayısı | Kd | **0.85** | API 520 Standart Orifis |
    | **API 520 Gerekli Efektif Orifis Alanı** | **A_o** | **{subcrit['A_o_mm2']:,.1f}** | **mm² ({subcrit['A_o_in2']:.1f} in²)** |
    """)

with exp4:
    is_insulated = "Yalıtımlı Çift Cidarlı Tank" if insulation_factor_F <= 0.3 else "Yalıtımsız / Hasarlı Tank"
    fire_is_sub = "Subcritical" if fire_subcrit['is_subcritical'] else "Critical"
    st.markdown(f"""
    #### 🚒 Yangın Senaryosu (Fire Case) Tahliye Debisi & Hüküm Süren (Governing) Senaryo Analizi
    `Q_fire = 70.9 × F × (A_wetted ^ 0.82) (kW)`  
    `W_fire = (Q_fire × 3600) / L (kg/h)`

    | Parametre / Senaryo | Değer | Birim / Açıklama |
    | :--- | :---: | :--- |
    | Islatılmış Tank Yüzey Alanı (A_wetted) | **{wetted_area_m2:,.0f}** | m² |
    | Yalıtım / Çevre Faktörü (F) | **{insulation_factor_F:.2f}** | {is_insulated} |
    | LNG Buharlaşma Gizli Isısı (L) | **{latent_heat_kJ_kg:,.0f}** | kJ/kg |
    | Yangın Tahliye Sıcaklığı (T_fire) | **{T_fire_input:.1f} {T_fire_unit}** | Yangın senaryosu gaz sıcaklığı |
    | Yangın Gaz Z Faktörü ({eos_code}) | **{fire_Z:.4f}** | - |
    | Yangın Dinamik k = Cp/Cv | **{fire_k:.3f}** | - |
    | Yangın Vana Kd (API 520 Fire) | **1.00** | Yangın senaryosu tam açılma |
    | **Yangın Durumu Isı Girişi (Q_fire)** | **{fire_res['q_fire_kW']:,.1f}** | **kW** |
    | **Yangın Senaryosu Tahliye Debisi (W_fire)** | **{fire_res['w_fire_kg_h']:,.1f}** | **kg/h** ({fire_q_a_total:,.1f} m³/h Hava) |
    | **Yangın Senaryosu Gerekli A_o (API 520, Kd=1.0)** | **{fire_subcrit['A_o_mm2']:,.1f}** | **mm²** ({fire_is_sub}, F2={fire_subcrit['F2']:.4f}) |
    | **Operasyonel Tahliye Debisi (W_operasyonel)** | **{loads['w_total_kg_h']:,.1f}** | **kg/h** ({q_a_total:,.1f} m³/h Hava) |
    | **Operasyonel Gerekli A_o (API 520, Kd=0.85)** | **{subcrit['A_o_mm2']:,.1f}** | **mm²** |
    | **🏆 HÜKÜM SÜREN (GOVERNING) SENARYO** | **{governing_scenario}** | **A_o = {governing_A_o_mm2:,.1f} mm²** |
    """)

# Main Section 2: Commercial Manufacturer PSV Database Matching
st.header("2. Entegre PSV Üretici Vana Kataloğu Eşleştirmesi")
st.caption("Anderson Greenwood, Crosby, Consolidated, Leser, Farris ve Mercer marka katalog modellerinin sorgu sonuçları:")

matched_df = pd.DataFrame(matched_valves)
if not matched_df.empty:
    matched_df_display = matched_df[['manufacturer', 'series', 'type', 'dn_size', 'orifice_area_mm2', 'coverage_pct', 'status', 'standards']].copy()
    matched_df_display.columns = ['Üretici Marka', 'Model Serisi', 'Vana Tipi', 'Anma Çapı', 'Orifis Alanı (mm²)', 'Kapasite Oranı (%)', 'Öneri Durumu', 'Standartlar']
    
    st.dataframe(
        matched_df_display.style.format({
            'Orifis Alanı (mm²)': '{:,.0f}',
            'Kapasite Oranı (%)': '%{:.1f}'
        })
    )
else:
    st.warning("Gereksinimleri karşılayan vana bulunamadı.")

# Interactive Plotly Charts
st.header("3. Termodinamik & Hidrolik Grafiksel Analiz")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Atmosferik Basınç - Gerekli Orifis Alanı Grafiği")
    p_range = np.linspace(900.0, 1020.0, 25)
    area_list = []
    
    for p in p_range:
        p1_kpa = (P_set + (P_set * Overpressure_pct / 100.0) + p) / 10.0
        p2_kpa = p / 10.0
        res_sub = calculate_api520_subcritical_orifice_area(
            w_valve_kg_h=loads['w_total_kg_h'] / N_working,
            P1_kPa_a=p1_kpa,
            P2_kPa_a=p2_kpa,
            temperature_k=T_relief_K,
            M_g_mol=M_vapor,
            Z=Z_factor,
            k=k_factor
        )
        area_list.append(res_sub['A_o_mm2'])
        
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=p_range, y=area_list, mode='lines+markers', name='Gerekli Orifis Alanı (mm²)', line=dict(color='#fb7185', width=3)))
    fig1.add_vline(x=P_atm_min, line_dash="dash", line_color="#38bdf8", annotation_text=f"Min Patm ({P_atm_min:.2f} mbar_a)")
    fig1.update_layout(
        template="plotly_dark",
        xaxis_title="Atmosferik Basınç (mbar_a)",
        yaxis_title="Gerekli Orifis Alanı (mm²)",
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig1)

with chart_col2:
    st.subheader("Dolum Debisi - Vana Kapasite Karşılama Oranı")
    q_range = np.linspace(5000.0, 12000.0, 20)
    cov_16 = []
    cov_18 = []
    
    # Dynamic rated capacity from database (16"x18" = 148,500 mm2, 18"x20" = 191,000 mm2)
    cap16 = calculate_valve_capacity(148500.0, P1_kPa_a)
    cap18 = calculate_valve_capacity(191000.0, P1_kPa_a)

    for q in q_range:
        ld = calculate_relieving_loads(q_fill_m3_h=q, rho_lng_kg_m3=rho_lng, rho_v_kg_m3=rho_v, flash_pct=effective_flash_pct, w_bog_kg_h=w_bog_kg_h)
        qa = calculate_nfpa59a_air_equivalent(ld['w_total_kg_s'], temperature_k=T_relief_K, Z=Z_factor, M_g_mol=M_vapor) / N_working
        
        cov_16.append((cap16 / qa) * 100.0)
        cov_18.append((cap18 / qa) * 100.0)
        
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=q_range, y=cov_16, mode='lines', name='16" x 18" Vana Kapasite Oranı (%)', line=dict(color='#fbbf24', width=2)))
    fig2.add_trace(go.Scatter(x=q_range, y=cov_18, mode='lines', name='18" x 20" Vana Kapasite Oranı (%)', line=dict(color='#4ade80', width=3)))
    fig2.add_hline(y=100.0, line_dash="dash", line_color="#ef4444", annotation_text="%100 Kapasite Sınırı")
    fig2.add_vline(x=Q_fill, line_dash="dot", line_color="#38bdf8", annotation_text=f"Mevcut Dolum ({Q_fill:,.0f} m³/h)")
    fig2.update_layout(
        template="plotly_dark",
        xaxis_title="LNG Dolum Debisi (m³/h)",
        yaxis_title="Kapasite Karşılama Oranı (%)",
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig2)

# Engineering Recommendation Panel
st.header("4. Mühendislik Çözüm Önerileri")

# Dynamically compute coverage and derated fill from matrix results
cov_16x18 = next((m['coverage_pct'] for m in matrix if '16' in m['size_name'] and '18' in m['size_name']), 95.0)
cov_18x20 = next((m['coverage_pct'] for m in matrix if '18' in m['size_name'] and '20' in m['size_name']), 123.5)
derated_q_fill = Q_fill * (100.0 / max(1.0, cov_16x18))

col_rec1, col_rec2, col_rec3 = st.columns(3)

with col_rec1:
    st.success(f"""
    ### 🌟 Seçenek A (Tavsiye Edilen)
    **Vana Çapını Büyütme**:
    - {N_working}+{N_spare} PORV konfigürasyonunda vana anma çapı **18" x 20" (DN450 x DN500)** olarak seçilmelidir.
    - Vana **%{cov_18x20:.1f}** kapasite kullanımı ile tam emniyet marjı sağlar.
    """)

with col_rec2:
    n_extra = N_working + 1
    st.warning(f"""
    ### ⚠️ Seçenek B (Konfigürasyon Revizyonu)
    **Vana Adedini Arttırma**:
    - Vana çapı 16" x 18" tutulacaksa, vana düzeni **{n_extra} Çalışan + {N_spare} Yedek (Toplam {n_extra + N_spare} Vana)** olarak güncellenmelidir.
    """)

with col_rec3:
    st.info(f"""
    ### 🛑 Seçenek C (Dolum Debisi Limiti)
    **Dolum Hızını Derate Etme**:
    - 16" x 18" vanalar {N_working}+{N_spare} düzeninde tutulursa, izin verilecek maksimum gemi LNG dolum debisi **{derated_q_fill:,.0f} m³/saat** seviyesi ile sınırlandırılmalıdır.
    """)

# Printable Report Export Button
st.markdown("<hr>", unsafe_allow_html=True)

report_inputs = {
    'V_n': V_n,
    'Q_fill': Q_fill,
    'P_atm_min': P_atm_min,
    'P_atm_max': P_atm_max,
    'P_set': P_set,
    'Overpressure_pct': Overpressure_pct,
    'N_working': N_working,
    'N_spare': N_spare,
    'flash_manual_mode': flash_manual_mode
}

report_sizing = {
    'P1_kPa_a': P1_kPa_a,
    'w_flash_kg_h': loads['w_flash_kg_h'],
    'w_disp_kg_h': loads['w_disp_kg_h'],
    'w_bog_kg_h': loads['w_bog_kg_h'],
    'w_total_kg_h': loads['w_total_kg_h'],
    'w_total_g_s': loads['w_total_kg_s'] * 1000.0,
    'q_a_total_m3_h': q_a_total,
    'q_a_per_valve_m3_h': q_a_per_valve,
    'A_o_mm2': subcrit['A_o_mm2'],
    'A_o_in2': subcrit['A_o_in2'],
    'matrix': matrix
}

report_thermo = {
    'density_kg_m3': rho_lng,
    'molar_mass_g_mol': M_mix_calculated,
    'vapor_density': rho_v,
    'Z_gas': Z_factor,
    'k_mix': k_factor,
    'eos_choice': eos_choice
}

html_report_content = generate_html_report(
    inputs=report_inputs,
    thermo_results=report_thermo,
    sizing_results=report_sizing,
    matrix_results=matrix,
    matched_valves=matched_valves
)

st.download_button(
    label="📄 Mühendislik Hesap Raporunu İndir (HTML / Yazdırılabilir)",
    data=html_report_content,
    file_name="LNG_PORV_Boyutlandirma_Raporu.html",
    mime="text/html"
)
