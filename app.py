"""
LNG PORV Emniyet Vanası Boyutlandırma ve Termodinamik Analiz Yazılımı (Streamlit Dashboard)
İki Yönlü Birim Çevrim, Genişletilmiş Gaz Komponent Kataloğu, %100 Mol Kontrolü, Ayrıştırılmış Sıvı LNG ve Tahliye Sıcaklıkları.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from lng_thermo import calculate_costald_density, calculate_vapor_density, COMPONENT_DATA
from psv_sizing import calculate_relieving_loads, calculate_nfpa59a_air_equivalent, calculate_api520_subcritical_orifice_area, evaluate_valve_matrix
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

# Page Config
st.set_page_config(
    page_title="LNG PORV Emniyet Vanası Boyutlandırma Portalı",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Modern Engineering Aesthetics
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
        padding: 16px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .metric-value {
        color: #38bdf8;
        font-size: 20px;
        font-weight: 700;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 12px;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Header Section
st.markdown("""
<div class="main-header">
    <div class="main-title">⚓ LNG PORV Emniyet Vanası Boyutlandırma Portalı</div>
    <div class="sub-title">Pilot Uyarılı Emniyet Vanası Boyutlandırma, COSTALD Kriyojenik Termodinamik ve Akışkan Analiz Portalı</div>
</div>
""", unsafe_allow_html=True)

# Sidebar Input Controls with Dynamic Unit Selectors
st.sidebar.header("⚙️ Girdi ve Birim Ayarları")

input_tab1, input_tab2, input_tab3 = st.sidebar.tabs(["Saha & Operasyon", "LNG Kompozisyonu", "Flaş BOG Modu"])

with input_tab1:
    st.subheader("1. Tank & Saha Şartları")
    
    col_v, col_vu = st.columns([3, 2])
    with col_v:
        V_n_input = st.number_input("Tank Net Hacmi (V_n)", value=160000.0, step=5000.0)
    with col_vu:
        V_n_unit = st.selectbox("Hacim Birimi", list(VOLUME_UNITS.keys()), index=0)
    V_n = convert_volume_to_m3(V_n_input, V_n_unit)
    
    col_q, col_qu = st.columns([3, 2])
    with col_q:
        Q_fill_input = st.number_input("Max. LNG Dolum Debisi (Q_fill)", value=10000.0, step=500.0)
    with col_qu:
        Q_fill_unit = st.selectbox("Dolum Debi Birimi", list(VOLUMETRIC_FLOW_UNITS.keys()), index=0)
    Q_fill = convert_volumetric_flow_to_m3_h(Q_fill_input, Q_fill_unit)
    
    col_pmin, col_pmin_u = st.columns([3, 2])
    with col_pmin:
        P_atm_min_input = st.number_input("Min. Atmosferik Basınç (P_atm,min)", value=906.03, format="%.2f")
    with col_pmin_u:
        P_atm_min_unit = st.selectbox("Min Patm Birimi", list(PRESSURE_UNITS_ABS.keys()), index=0)
    P_atm_min = convert_pressure_to_mbar(P_atm_min_input, P_atm_min_unit, is_gauge=False)
    
    col_pmax, col_pmax_u = st.columns([3, 2])
    with col_pmax:
        P_atm_max_input = st.number_input("Max. Atmosferik Basınç (P_atm,max)", value=1014.602, format="%.3f")
    with col_pmax_u:
        P_atm_max_unit = st.selectbox("Max Patm Birimi", list(PRESSURE_UNITS_ABS.keys()), index=0)
    P_atm_max = convert_pressure_to_mbar(P_atm_max_input, P_atm_max_unit, is_gauge=False)
    
    st.subheader("2. PORV Emniyet Vanası Ayarları")
    col_pset, col_pset_u = st.columns([3, 2])
    with col_pset:
        P_set_input = st.number_input("PORV Set Basıncı (P_set)", value=240.0, step=10.0)
    with col_pset_u:
        P_set_unit = st.selectbox("Set Basınç Birimi", list(PRESSURE_UNITS_GAUGE.keys()), index=0)
    P_set = convert_pressure_to_mbar(P_set_input, P_set_unit, is_gauge=True)
    
    Overpressure_pct = st.number_input("İzin Verilen Overpressure (%)", value=10.0, step=1.0)
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        N_working = st.number_input("Çalışan Vana (N)", value=3, min_value=1, max_value=10)
    with col_v2:
        N_spare = st.number_input("Yedek Vana (+1)", value=1, min_value=0, max_value=5)

# Session State Initialization for Expanded LNG Composition
DEFAULT_COMPOSITION = {
    'CH4': 90.50,
    'C2H6': 5.50,
    'C3H8': 2.50,
    'iC4H10': 0.50,
    'nC4H10': 0.50,
    'iC5H12': 0.00,
    'nC5H12': 0.00,
    'C6plus': 0.00,
    'N2': 0.50,
    'CO2': 0.00,
    'O2': 0.00,
    'H2': 0.00,
    'Ar': 0.00,
    'He': 0.00
}

for c_key in DEFAULT_COMPOSITION:
    if f"comp_{c_key}" not in st.session_state:
        st.session_state[f"comp_{c_key}"] = DEFAULT_COMPOSITION[c_key]

with input_tab2:
    st.subheader("3. Genişletilmiş LNG Kompozisyonu")
    st.caption("LNG sıvı ve buharını oluşturan 14 bileşenin mol yüzdeleri (%):")
    
    # Auto-normalize action button
    if st.button("⚡ Kompozisyonu Otomatik %100'e Eşitle"):
        current_sum = sum(st.session_state[f"comp_{k}"] for k in DEFAULT_COMPOSITION)
        if current_sum > 0:
            for k in DEFAULT_COMPOSITION:
                st.session_state[f"comp_{k}"] = round((st.session_state[f"comp_{k}"] / current_sum) * 100.0, 3)
            st.rerun()
            
    # Hydrocarbons Section
    st.markdown("**Hidrokarbon Bileşenler:**")
    c_ch4 = st.number_input("Metan (CH4) %", min_value=0.0, max_value=100.0, key="comp_CH4", step=0.1, format="%.2f")
    c_c2h6 = st.number_input("Etan (C2H6) %", min_value=0.0, max_value=100.0, key="comp_C2H6", step=0.1, format="%.2f")
    c_c3h8 = st.number_input("Propan (C3H8) %", min_value=0.0, max_value=100.0, key="comp_C3H8", step=0.1, format="%.2f")
    c_ic4 = st.number_input("iso-Bütan (i-C4H10) %", min_value=0.0, max_value=100.0, key="comp_iC4H10", step=0.05, format="%.2f")
    c_nc4 = st.number_input("n-Bütan (n-C4H10) %", min_value=0.0, max_value=100.0, key="comp_nC4H10", step=0.05, format="%.2f")
    c_ic5 = st.number_input("iso-Pentan (i-C5H12) %", min_value=0.0, max_value=100.0, key="comp_iC5H12", step=0.05, format="%.2f")
    c_nc5 = st.number_input("n-Pentan (n-C5H12) %", min_value=0.0, max_value=100.0, key="comp_nC5H12", step=0.05, format="%.2f")
    c_c6p = st.number_input("Heksan+ (C6+) %", min_value=0.0, max_value=100.0, key="comp_C6plus", step=0.05, format="%.2f")
    
    # Inerts & Impurities Section
    st.markdown("**İnert ve İz Gazlar:**")
    c_n2 = st.number_input("Azot (N2) %", min_value=0.0, max_value=100.0, key="comp_N2", step=0.1, format="%.2f")
    c_co2 = st.number_input("Karbondioksit (CO2) %", min_value=0.0, max_value=100.0, key="comp_CO2", step=0.05, format="%.2f")
    c_o2 = st.number_input("Oksijen (O2) %", min_value=0.0, max_value=100.0, key="comp_O2", step=0.05, format="%.2f")
    c_h2 = st.number_input("Hidrojen (H2) %", min_value=0.0, max_value=100.0, key="comp_H2", step=0.05, format="%.2f")
    c_ar = st.number_input("Argon (Ar) %", min_value=0.0, max_value=100.0, key="comp_Ar", step=0.05, format="%.2f")
    c_he = st.number_input("Helyum (He) %", min_value=0.0, max_value=100.0, key="comp_He", step=0.05, format="%.2f")
    
    st.subheader("4. Kriyojenik Sıcaklık Girdileri")
    
    col_tlng, col_tlng_u = st.columns([3, 2])
    with col_tlng:
        T_lng_input = st.number_input("Sıvı LNG Sıcaklığı (T_LNG)", value=-160.0, step=1.0, help="COSTALD sıvı yoğunluk hesabı için depolama sıcaklığı.")
    with col_tlng_u:
        T_lng_unit = st.selectbox("Sıvı T Birimi", ['°C', 'K', '°F', '°R'], index=0)
    T_lng_K = convert_temperature_to_kelvin(T_lng_input, T_lng_unit)
    
    col_trel, col_trel_u = st.columns([3, 2])
    with col_trel:
        T_relief_input = st.number_input("Tahliye Buhar Sıcaklığı (T_relief)", value=-155.0, step=1.0, help="Emniyet vanası gaz tahliye debisi hesabı için sıcaklık.")
    with col_trel_u:
        T_relief_unit = st.selectbox("Buhar T Birimi", ['°C', 'K', '°F', '°R'], index=0)
    T_relief_K = convert_temperature_to_kelvin(T_relief_input, T_relief_unit)
    
    comp_dict = {
        'CH4': c_ch4,
        'C2H6': c_c2h6,
        'C3H8': c_c3h8,
        'iC4H10': c_ic4,
        'nC4H10': c_nc4,
        'iC5H12': c_ic5,
        'nC5H12': c_nc5,
        'C6plus': c_c6p,
        'N2': c_n2,
        'CO2': c_co2,
        'O2': c_o2,
        'H2': c_h2,
        'Ar': c_ar,
        'He': c_he
    }
    
    total_composition_pct = sum(comp_dict.values())
    
    # Live %100 Total Control Banner in Sidebar
    if abs(total_composition_pct - 100.0) < 0.01:
        st.success(f"✅ Mol Toplamı: **%{total_composition_pct:.2f}** (Kusursuz)")
    elif total_composition_pct < 100.0:
        st.warning(f"⚠️ Mol Toplamı: **%{total_composition_pct:.2f}** (Eksik: %{100.0 - total_composition_pct:.2f})")
    else:
        st.error(f"❌ Mol Toplamı: **%{total_composition_pct:.2f}** (Fazla: %{total_composition_pct - 100.0:.2f})")
        
    # Calculate COSTALD liquid density dynamically at T_lng_K
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
    st.subheader("5. Flaş BOG Debisi Giriş Modu")
    flash_mode = st.radio(
        "Flaş BOG Hesap Modu:",
        ["Otomatik (%2.0 Flaş Oranı)", "Manuel Debi Girişi"],
        index=0
    )
    
    if flash_mode == "Manuel Debi Girişi":
        flash_manual_mode = True
        col_wf, col_wfu = st.columns([3, 2])
        with col_wf:
            w_flash_input = st.number_input("Manuel Flaş BOG Debisi", value=94200.0, step=1000.0)
        with col_wfu:
            w_flash_unit = st.selectbox("Flaş Debi Birimi", list(MASS_FLOW_UNITS.keys()), index=0)
        w_flash_manual_kg_h = convert_mass_flow_to_kg_h(w_flash_input, w_flash_unit)
    else:
        flash_manual_mode = False
        w_flash_manual_kg_h = 94200.0
        
    flash_pct = st.number_input("Otomatik Mod Flaş Oranı (%)", value=2.0, step=0.1)
    
    col_wbog, col_wbogu = st.columns([3, 2])
    with col_wbog:
        w_bog_input = st.number_input("Isı Girişi Tank BOG Debisi", value=1570.0, step=100.0)
    with col_wbogu:
        w_bog_unit = st.selectbox("BOG Debi Birimi", list(MASS_FLOW_UNITS.keys()), index=0)
    w_bog_kg_h = convert_mass_flow_to_kg_h(w_bog_input, w_bog_unit)

# --- CORE CALCULATIONS ---
# Absolute relieving pressure P1 in kPa_a
P1_mbar_a = P_set + (P_set * (Overpressure_pct / 100.0)) + P_atm_min
P1_kPa_a = P1_mbar_a / 10.0 # mbar_a to kPa_a
P2_kPa_a = P_atm_min / 10.0 # Backpressure / atmospheric in kPa_a

# Vapor density at relieving temperature and relieving pressure
Z_factor = 0.98
k_factor = 1.31
rho_v = calculate_vapor_density(P1_kPa_a, temperature_k=T_relief_K, M_g_mol=M_mix_calculated, Z=Z_factor)

# Relieving mass flow rates
loads = calculate_relieving_loads(
    q_fill_m3_h=Q_fill,
    rho_lng_kg_m3=rho_lng,
    rho_v_kg_m3=rho_v,
    flash_pct=flash_pct,
    w_bog_kg_h=w_bog_kg_h,
    flash_manual_mode=flash_manual_mode,
    w_flash_manual_kg_h=w_flash_manual_kg_h
)

# NFPA 59A Equivalent Air Rate
q_a_total = calculate_nfpa59a_air_equivalent(loads['w_total_kg_s'], temperature_k=T_relief_K, Z=Z_factor, M_g_mol=M_mix_calculated)
q_a_per_valve = q_a_total / N_working

# API 520 Subcritical Orifice Area per valve
subcrit = calculate_api520_subcritical_orifice_area(
    w_valve_kg_h=loads['w_total_kg_h'] / N_working,
    P1_kPa_a=P1_kPa_a,
    P2_kPa_a=P2_kPa_a,
    temperature_k=T_relief_K,
    M_g_mol=M_mix_calculated,
    Z=Z_factor,
    k=k_factor,
    K_d=0.85
)

# Matrix evaluation
matrix = evaluate_valve_matrix(
    q_a_per_valve_m3_h=q_a_per_valve,
    P1_kPa_a=P1_kPa_a,
    P2_kPa_a=P2_kPa_a,
    temperature_k=T_relief_K,
    M_g_mol=M_mix_calculated,
    Z=Z_factor,
    k=k_factor,
    K_d=0.85
)

# Manufacturer Database Search
matched_valves = search_matching_valves(
    req_orifice_area_mm2=subcrit['A_o_mm2'],
    required_air_capacity_m3_h=q_a_per_valve,
    P1_kPa_a=P1_kPa_a
)

# --- MAIN DASHBOARD DISPLAY ---

# Prominent Total Composition Validation Alert Box in Main View
if abs(total_composition_pct - 100.0) >= 0.01:
    diff_pct = 100.0 - total_composition_pct
    st.warning(f"""
    ⚠️ **LNG Kompozisyon Uyarısı**: Girilen gaz bileşenlerinin mol toplamı **%{total_composition_pct:.2f}** seviyesindedir (Fark: **%{diff_pct:+.2f}**).
    Hesaplamalar otomatik %100'e normalize edilen kesirlerle yürütülmüştür. İsterseniz sol paneldeki **"⚡ Kompozisyonu Otomatik %100'e Eşitle"** butonuna basarak değerleri net güncelleyebilirsiniz.
    """)
else:
    st.success(f"✅ **LNG Kompozisyon Doğrulaması**: Girilen 14 gaz bileşeninin mol toplamı tam olarak **%100.00**'dir.")

# Metrics Row (Including Liquid Density at T_lng & Relieving Vapor Density at T_relief)
m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

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
        <div class="metric-value" style="color:#a855f7;">{rho_v:.3f} kg/m³</div>
        <div class="metric-label">Buhar Yoğunluğu (ρ_v @ {T_relief_input:.1f} {T_relief_unit})</div>
    </div>
    """, unsafe_allow_html=True)

with m_col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{loads['w_total_kg_h']:,.0f} kg/h</div>
        <div class="metric-label">Toplam Kütlesel Tahliye Debisi (W)</div>
    </div>
    """, unsafe_allow_html=True)

with m_col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{q_a_total:,.0f} m³/h</div>
        <div class="metric-label">NFPA 59A Hava Eşdeğeri (Q_a)</div>
    </div>
    """, unsafe_allow_html=True)

with m_col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color:#f43f5e;">{subcrit['A_o_mm2']:,.0f} mm²</div>
        <div class="metric-label">Gerekli Orifis Alanı (A_o / Vana)</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Main Section 1: Standard Valve Size Evaluation Matrix
st.header("1. Standart Vana Anma Ölçüsü Karşılaştırma Matrisi")
st.caption(f"Set: {P_set:.0f} mbar_g, Overpressure: %{Overpressure_pct:.0f}, P_atm_min: {P_atm_min:.2f} mbar_a (P1 = {P1_mbar_a:.2f} mbar_a) | Sıvı LNG Sıcaklığı: {T_lng_input:.1f} {T_lng_unit} | Tahliye Buhar Sıcaklığı: {T_relief_input:.1f} {T_relief_unit}")

matrix_df = pd.DataFrame(matrix)
matrix_df_display = matrix_df[['size_name', 'orifice_area_mm2', 'air_capacity_m3_h', 'coverage_pct', 'status']].copy()
matrix_df_display.columns = ['Vana Anma Ölçüsü (Giriş x Çıkış)', 'Efektif Orifis Alanı (mm²)', 'Hava Tahliye Kapasitesi (m³/h)', 'Kapasite Oranı (%)', 'Teknik Değerlendirme']

st.dataframe(
    matrix_df_display.style.format({
        'Efektif Orifis Alanı (mm²)': '{:,.0f}',
        'Hava Tahliye Kapasitesi (m³/h)': '{:,.0f}',
        'Kapasite Oranı (%)': '%{:.1f}'
    })
)

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
    st.subheader("Atmosferik Basınç - Orifis Alanı ve Kapasite Eğrisi")
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
            M_g_mol=M_mix_calculated,
            Z=Z_factor,
            k=k_factor
        )
        area_list.append(res_sub['A_o_mm2'])
        
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=p_range, y=area_list, mode='lines+markers', name='Gerekli Orifis Alanı (mm²)', line=dict(color='#f43f5e', width=3)))
    fig1.add_vline(x=P_atm_min, line_dash="dash", line_color="#38bdf8", annotation_text=f"P_atm_min ({P_atm_min:.2f} mbar_a)")
    fig1.update_layout(
        template="plotly_dark",
        xaxis_title="Atmosferik Basınç (mbar_a)",
        yaxis_title="Gerekli Orifis Alanı (mm²)",
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig1)

with chart_col2:
    st.subheader("Dolum Debisi - Vana Kapasite Kullanım Oranları")
    q_range = np.linspace(5000.0, 12000.0, 20)
    cov_16 = []
    cov_18 = []
    
    for q in q_range:
        ld = calculate_relieving_loads(q_fill_m3_h=q, rho_lng_kg_m3=rho_lng, rho_v_kg_m3=rho_v, flash_pct=flash_pct, w_bog_kg_h=w_bog_kg_h)
        qa = calculate_nfpa59a_air_equivalent(ld['w_total_kg_s'], temperature_k=T_relief_K, Z=Z_factor, M_g_mol=M_mix_calculated) / N_working
        
        cap16 = 25380.0 * (P1_kPa_a / 117.003)
        cap18 = 32650.0 * (P1_kPa_a / 117.003)
        
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

col_rec1, col_rec2, col_rec3 = st.columns(3)

with col_rec1:
    st.success("""
    ### 🌟 Seçenek A (Tavsiye Edilen)
    **Vana Çapını Büyütme**:
    - 3+1 PORV konfigürasyonunda vana anma çapı **18" x 20" (DN450 x DN500)** olarak seçilmelidir.
    - Vana %123.5 kapasite kullanımı ile tam emniyet marjı sağlar.
    """)

with col_rec2:
    st.warning("""
    ### ⚠️ Seçenek B (Konfigürasyon Revizyonu)
    **Vana Adedini Arttırma**:
    - Vana çapı 16" x 18" tutulacaksa, vana düzeni **4 Çalışan + 1 Yedek (Toplam 5 Vana)** olarak güncellenmelidir.
    """)

with col_rec3:
    st.info("""
    ### 🛑 Seçenek C (Dolum Debisi Limiti)
    **Dolum Hızını Derate Etme**:
    - 16" x 18" vanalar 3+1 düzeninde tutulursa, izin verilecek maksimum gemi LNG dolum debisi **9.600 m³/saat** seviyesi ile sınırlandırılmalıdır.
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
    'vapor_density': rho_v
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
