"""
LNG PORV Emniyet Vanası Ön Boyutlandırma ve Termodinamik Analiz Yazılımı (Streamlit Dashboard)
Çoklu EOS Destekli (Peng-Robinson, SRK, GERG-2008), Dinamik T/P Bağlı k_mix(T,P) Hesabı,
Rachford-Rice VLE Flaş BOG Motoru, Dinamik Gaz Kompozisyonu Düzenleyicisi.

Kapsam: API 520 Part I / API 521 / NFPA 59A denklem tabanlı PORV ön boyutlandırma.
Kapsam dışı: API 520 Part II tesisat analizi, API 625 / API 620 App. Q tank tasarımı,
tank basınç-vakum koruması ve sertifikalı vana kapasitesi teyidi.
"""

import json
import logging
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lng_thermo import calculate_costald_density
from psv_database import search_matching_valves
from psv_sizing import (
    SCOPE_STATEMENT,
    STANDARD_EDITIONS,
    calculate_api520_subcritical_orifice_area,
    calculate_bor_tank_bog,
    calculate_fire_scenario_load,
    calculate_nfpa59a_air_equivalent,
    calculate_relieving_loads,
    calculate_valve_capacity,
    compute_governing_decision,
    evaluate_valve_matrix,
)
from report_generator import generate_html_report
from unit_converter import (
    DENSITY_UNITS,
    MASS_FLOW_UNITS,
    PRESSURE_UNITS_ABS,
    PRESSURE_UNITS_GAUGE,
    VOLUME_UNITS,
    VOLUMETRIC_FLOW_UNITS,
    convert_density_to_kg_m3,
    convert_mass_flow_to_kg_h,
    convert_pressure_to_mbar,
    convert_temperature_to_kelvin,
    convert_volume_to_m3,
    convert_volumetric_flow_to_m3_h,
)
from version_checker import CURRENT_VERSION, check_for_updates, get_version_info
from vle_thermo import (
    EOS_COMPONENT_DATA,
    calculate_bubble_point_temperature,
    calculate_eos_mixture_properties,
    calculate_isenthalpic_flash,
    calculate_two_phase_vle_flash,
)

logger = logging.getLogger(__name__)

# Widget keys are intentionally pre-populated in st.session_state (save/load support),
# which makes Streamlit log an informational policy warning for every widget. Silence it.
logging.getLogger("streamlit.elements.lib.policies").setLevel(logging.ERROR)

# Page Config
st.set_page_config(
    page_title="LNG PORV Emniyet Vanası Ön Boyutlandırma Portalı",
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
st.markdown(f"""
<div class="main-header">
    <div class="main-title">⚓ LNG PORV Emniyet Vanası Ön Boyutlandırma Portalı <span style="font-size: 15px; color: #38bdf8; font-weight: 500;">v{CURRENT_VERSION}</span></div>
    <div class="sub-title">Çoklu EOS (PR / SRK / GERG-2008), İzentalpik PH-Flaş (h₁=h₂), Dinamik k(T,P), COSTALD Termodinamik ve API 520 Part I / API 521 Ön Boyutlandırma</div>
    <div class="sub-title" style="color:#fbbf24;">ℹ️ Kapsam: PORV ön boyutlandırma. API 520 Part II tesisat analizi, API 625 / API 620 App. Q tank tasarımı ve sertifikalı kapasite teyidi kapsam dışıdır.</div>
</div>
""", unsafe_allow_html=True)

# --- SIDEBAR INPUT DEFAULTS (tek kaynak: kaydet/yükle ve doğrulama için) ---
INPUT_DEFAULTS = {
    'in_V_n': 160000.0, 'in_V_n_unit': 'm³',
    'in_Q_fill': 10000.0, 'in_Q_fill_unit': 'm³/h',
    'in_P_atm_min': 906.03, 'in_P_atm_min_unit': 'mbar_a',
    'in_P_atm_max': 1014.602, 'in_P_atm_max_unit': 'mbar_a',
    'in_P_set': 240.0, 'in_P_set_unit': 'mbar_g',
    'in_Overpressure_pct': 10.0,
    'in_N_working': 3, 'in_N_spare': 1,
    'in_wetted_area_m2': 1200.0, 'in_insulation_factor_F': 0.15,
    'in_latent_heat_kJ_kg': 510.0,
    'in_T_fire': -100.0, 'in_T_fire_unit': '°C',
    'in_fire_overpressure_pct': 21.0,
    'in_fire_q_constant': '70.9 (34.500 Btu/h·ft² - drenaj/söndürme yok)',
    'in_flash_basis': "Molar (mol/mol) - fiziksel V/F",
    'in_T_tank': -160.0, 'in_T_tank_unit': '°C',
    'in_T_relief': -155.0, 'in_T_relief_unit': '°C',
    'in_auto_sat_temp': True,
    'in_override_rho': False, 'in_rho_manual': 471.0, 'in_rho_unit': 'kg/m³',
    'in_cargo_diff': False,
    'in_P_ship': 5.0, 'in_P_ship_unit': 'bar_g',
    'in_tcargo_mode': "Otomatik (Azot İçeriği & Doygunluk Esaslı)",
    'in_p_voyage_mbar_g': 100.0, 'in_delta_t_transfer': 0.50,
    'in_T_cargo': -161.0, 'in_T_cargo_unit': '°C',
    'in_flash_mode': "İzentalpik Flaş (PH-Flash, EOS)",
    'in_w_flash_manual': 94200.0, 'in_w_flash_unit': 'kg/h',
    'in_manual_flash_pct': 2.0,
    'in_bog_mode': "Otomatik (BOR %/gün Tank Hacminden)",
    'in_bor_pct_per_day': 0.10,
    'in_w_bog_manual': 1570.0, 'in_w_bog_unit': 'kg/h',
    'in_eos_choice': "Peng-Robinson (PR 1976)",
    'in_valve_type_filter': "Yalnızca Pilot Kumandalı",
    'in_filter_mode': "Tüm Uygun Vanaları Göster (%90 - %200 Kapasite)",
    'in_show_all_valves': True,
    'in_report_language': "Türkçe (TR)",
    'in_project_name': "LNG Depolama Tesisi - PORV Boyutlandırma",
    'in_project_revision': "Rev. 0",
    'in_project_prepared_by': "",
    'in_project_checked_by': "",
}
for _k, _v in INPUT_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Sidebar Input Controls with Dynamic Unit Selectors & EOS Selector
st.sidebar.header("⚙️ Girdi, EOS ve Birim Ayarları")

with st.sidebar.expander("🔄 Güncelleme Yönetimi & Versiyon", expanded=False):
    ver_info = get_version_info()
    st.markdown(f"**Mevcut Sürüm:** `v{ver_info['current_version']}`")
    st.caption(f"**Yayın Kanalı:** {ver_info['release_channel']}")
    st.caption(f"**Derleme Tarihi:** {ver_info['build_date']}")

    if st.button("🔔 Güncellemeleri Denetle", key="btn_check_updates"):
        with st.spinner("Sürüm durumu denetleniyor..."):
            upd_res = check_for_updates()
            if upd_res["update_available"]:
                st.warning(f"**Yeni Sürüm Mevcut:** {upd_res['latest_version']}\n\n[İndirme Sayfasına Git]({upd_res['release_url']})")
            else:
                st.success(f"{upd_res['status_message']}")


eos_choice = st.sidebar.selectbox(
    "📊 Termodinamik Durum Denklemi (EOS)",
    [
        "Peng-Robinson (PR 1976)",
        "Soave-Redlich-Kwong (SRK)",
        "HEOS (GERG-2008 Helmholtz Energy EOS)",
        "İdeal Gaz (Ideal Gas)"
    ],
    index=0,
    key='in_eos_choice',
    help="VLE Flaş dengesi, Z sıkıştırılabilirlik faktörü ve dinamik Cp/Cv k_mix(T,P) hesabı için EOS modeli. "
         "Not: İzentalpik flaş entalpi tutarlılığı için PR referansı kullanır; HEOS/İdeal seçimi Z, k, ρ_v ve M üzerinde etkilidir."
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
        V_n_input = st.number_input("Tank Net Hacmi (V_n)", value=160000.0, step=5000.0, min_value=1.0, key='in_V_n')
    with col_vu:
        V_n_unit = st.selectbox("Hacim Birimi", list(VOLUME_UNITS.keys()), index=0, key='in_V_n_unit')
    V_n = convert_volume_to_m3(V_n_input, V_n_unit)

    col_q, col_qu = st.columns([3, 2])
    with col_q:
        Q_fill_input = st.number_input("Max. LNG Dolum Debisi (Q_fill)", value=10000.0, step=500.0, min_value=1.0, key='in_Q_fill')
    with col_qu:
        Q_fill_unit = st.selectbox("Dolum Debi Birimi", list(VOLUMETRIC_FLOW_UNITS.keys()), index=0, key='in_Q_fill_unit')
    Q_fill = convert_volumetric_flow_to_m3_h(Q_fill_input, Q_fill_unit)

    col_pmin, col_pmin_u = st.columns([3, 2])
    with col_pmin:
        P_atm_min_input = st.number_input("Min. Atmosferik Basınç (P_atm,min)", value=906.03, format="%.2f", min_value=100.0, key='in_P_atm_min')
    with col_pmin_u:
        P_atm_min_unit = st.selectbox("Min Patm Birimi", list(PRESSURE_UNITS_ABS.keys()), index=0, key='in_P_atm_min_unit')
    P_atm_min = convert_pressure_to_mbar(P_atm_min_input, P_atm_min_unit, is_gauge=False)

    col_pmax, col_pmax_u = st.columns([3, 2])
    with col_pmax:
        P_atm_max_input = st.number_input("Max. Atmosferik Basınç (P_atm,max)", value=1014.602, format="%.3f", min_value=100.0, key='in_P_atm_max')
    with col_pmax_u:
        P_atm_max_unit = st.selectbox("Max Patm Birimi", list(PRESSURE_UNITS_ABS.keys()), index=0, key='in_P_atm_max_unit')
    P_atm_max = convert_pressure_to_mbar(P_atm_max_input, P_atm_max_unit, is_gauge=False)

    st.subheader("2. PORV Emniyet Vanası Ayarları")
    col_pset, col_pset_u = st.columns([3, 2])
    with col_pset:
        P_set_input = st.number_input("PORV Set Basıncı (P_set)", value=240.0, step=10.0, min_value=1.0, key='in_P_set')
    with col_pset_u:
        P_set_unit = st.selectbox("Set Basınç Birimi", list(PRESSURE_UNITS_GAUGE.keys()), index=0, key='in_P_set_unit')
    P_set = convert_pressure_to_mbar(P_set_input, P_set_unit, is_gauge=True)

    Overpressure_pct = st.number_input("İzin Verilen Overpressure (%)", value=10.0, step=1.0, min_value=0.0, max_value=50.0, key='in_Overpressure_pct')

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        N_working = st.number_input("Çalışan Vana (N)", value=3, min_value=1, max_value=10, key='in_N_working')
    with col_v2:
        N_spare = st.number_input("Yedek Vana (+1)", value=1, min_value=0, max_value=5, key='in_N_spare')

    valve_type_choice = st.radio(
        "Vana Tipi Filtresi (Aday Havuzu):",
        ["Tümü (Pilot + Yaylı)", "Yalnızca Pilot Kumandalı", "Yalnızca Yaylı"],
        index=1, key='in_valve_type_filter',
        help="Pilot kumandalı ve yaylı vanalar farklı kapasite/Kd ve karşı basınç davranışına sahiptir. "
             "PORV uygulaması için 'Yalnızca Pilot Kumandalı' seçilmesi önerilir; tip karışımı seçim sonuçlarını etkiler."
    )
    valve_type_code = ('pilot' if valve_type_choice.startswith("Yalnızca Pilot")
                       else 'spring' if valve_type_choice.startswith("Yalnızca Yaylı") else 'all')

    st.subheader("3. Yangın Senaryosu (Fire Case) Şartları")
    wetted_area_m2 = st.number_input("Islatılmış Tank Yüzey Alanı (A_wetted, m²)", value=1200.0, step=100.0, min_value=1.0, key='in_wetted_area_m2')
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        insulation_factor_F = st.number_input("Yalıtım Faktörü (F)", value=0.15, min_value=0.01, max_value=1.0, step=0.05, key='in_insulation_factor_F', help="0.15 yalıtımlı tank, 1.0 yalıtımsız tank")
    with col_f2:
        latent_heat_kJ_kg = st.number_input("Gizli Isı (L, kJ/kg)", value=510.0, step=10.0, min_value=10.0, key='in_latent_heat_kJ_kg')
    col_tfire, col_tfire_u = st.columns([3, 2])
    with col_tfire:
        T_fire_input = st.number_input("Yangın Tahliye Sıcaklığı (T_fire)", value=-100.0, step=5.0, key='in_T_fire', help="Yangın senaryosunda tahliye edilen gazın beklenen sıcaklığı")
    with col_tfire_u:
        T_fire_unit = st.selectbox("Yangın T Birimi", ['°C', 'K', '°F', '°R'], index=0, key='in_T_fire_unit')
    T_fire_K = convert_temperature_to_kelvin(T_fire_input, T_fire_unit)

    col_fop, col_fqc = st.columns([2, 3])
    with col_fop:
        fire_overpressure_pct = st.number_input("Yangın Overpressure (%)", value=21.0, step=1.0, min_value=0.0, max_value=50.0, key='in_fire_overpressure_pct',
                                                help="API 520/NFPA 59A yangın senaryosunda izin verilen maksimum aşırı basınç %21'dir.")
    with col_fqc:
        fire_q_constant_choice = st.selectbox(
            "Yangın Isı Girişi Korelasyon Katsayısı C (API 521, SI seti)",
            [
                "70.9 (34.500 Btu/h·ft² - drenaj/söndürme yok)",
                "43.2 (21.000 Btu/h·ft² - drenaj + söndürme mevcut)"
            ],
            index=0, key='in_fire_q_constant'
        )
    fire_coefficient_c_si = 70.9 if fire_q_constant_choice.startswith('70.9') else 43.2
    st.caption(
        "ℹ️ C, ısı akısı değil; `Q_fire = C × F × A^0.82` korelasyon katsayısıdır (birim kW/m^1,64). "
        "Yangın vana kapasitesi her modelin **katalog Kd değeri** ile hesaplanır; gerekli alan referans olarak Kd=0.85 ile gösterilir. "
        "Kd=1.0 yalnızca ilgili model için üretici tarafından sertifikalandırılmışsa geçerlidir."
    )

# Session State for Dynamic Gas Composition Editor
DEFAULT_ACTIVE_COMPS = ['CH4', 'C2H6', 'C3H8', 'iC4H10', 'nC4H10', 'N2']
DEFAULT_VALS = {'CH4': 90.50, 'C2H6': 5.50, 'C3H8': 2.50, 'iC4H10': 0.50, 'nC4H10': 0.50, 'N2': 0.50}

# Initialize all composition session state keys early (for save/load)
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

    # Tank basıncındaki doygunluk sıcaklığı (sıcaklık varsayılanları ve tutarlılık kontrolü için)
    P_tank_est_kPa = (P_set + P_atm_min) / 10.0
    try:
        t_bp_est = calculate_bubble_point_temperature(comp_dict, pressure_kPa_a=P_tank_est_kPa, eos=eos_code)
    except Exception as _bp_err:
        logger.warning(f"Tank doygunluk sıcaklığı hesaplanamadı: {_bp_err}")
        t_bp_est = 112.45

    st.subheader("4. Kriyojenik Sıcaklık Girdileri")
    auto_sat_temp = st.checkbox(
        "Tank doygunluk sıcaklığına otomatik eşitle (T_tank = T_relief = T_doygun)",
        value=st.session_state.get('in_auto_sat_temp', True), key='in_auto_sat_temp',
        help="İşaretliyken sıvı ve buhar sıcaklıkları tank basıncındaki gerçek doygunluk sıcaklığına eşitlenir "
             "(termodinamik olarak tutarlı konservatif varsayılan). Kapatarak manuel değer girebilirsiniz."
    )
    if auto_sat_temp:
        st.session_state['in_T_tank_unit'] = 'K'
        st.session_state['in_T_tank'] = round(t_bp_est, 2)
        st.session_state['in_T_relief_unit'] = 'K'
        st.session_state['in_T_relief'] = round(t_bp_est, 2)
        st.info(
            f"🌡️ Tank doygunluk sıcaklığı (P_tank = {P_tank_est_kPa:.1f} kPa_a): "
            f"**{t_bp_est:.2f} K ({t_bp_est - 273.15:.2f} °C)** → T_tank ve T_relief bu değere eşitlendi."
        )
    else:
        st.caption(f"💡 *Tank Basıncındaki Doygunluk (Kaynama) Sıcaklığı:* **{t_bp_est:.2f} K ({t_bp_est - 273.15:.2f} °C)**")

    col_ttank, col_ttank_u = st.columns([3, 2])
    with col_ttank:
        T_tank_input = st.number_input("Tank LNG Sıcaklığı (T_tank)", value=-160.0, step=1.0, key='in_T_tank',
                                       disabled=auto_sat_temp,
                                       help="Tankta bulunan LNG'nin sıcaklığı. COSTALD sıvı yoğunluğu bu sıcaklıkta hesaplanır.")
    with col_ttank_u:
        T_tank_unit = st.selectbox("Tank T Birimi", ['°C', 'K', '°F', '°R'], index=0, key="in_T_tank_unit", disabled=auto_sat_temp)
    T_tank_K = convert_temperature_to_kelvin(T_tank_input, T_tank_unit)

    col_trel, col_trel_u = st.columns([3, 2])
    with col_trel:
        T_relief_input = st.number_input("Tahliye Buhar Sıcaklığı (T_relief)", value=-155.0, step=1.0, key='in_T_relief',
                                         disabled=auto_sat_temp,
                                         help="Tahliye edilen buharın sıcaklığı; Z, k, ρ_v ve M_vapor bu sıcaklıkta hesaplanır.")
    with col_trel_u:
        T_relief_unit = st.selectbox("Buhar T Birimi", ['°C', 'K', '°F', '°R'], index=0, key="in_T_relief_unit", disabled=auto_sat_temp)
    T_relief_K = convert_temperature_to_kelvin(T_relief_input, T_relief_unit)

    if not auto_sat_temp and abs(T_relief_K - t_bp_est) > 2.0:
        _sign = "sıcak" if T_relief_K > t_bp_est else "soğuk"
        st.warning(
            f"⚠️ **Tahliye Buhar Sıcaklığı Tutarsızlığı:** Seçilen T_relief ({T_relief_K:.2f} K) tank doygunluğundan "
            f"({t_bp_est:.2f} K) **{abs(T_relief_K - t_bp_est):.2f} K {_sign}**. Buhar özellikleri (ρ_v, Z, M_vapor) bu "
            f"sıcaklıkta hesaplandığından dolum/taşma yükü ve gerekli orifis alanı değişir. "
            f"Doygunluk sıcaklığını kullanmak için otomatik eşitlemeyi açın."
        )

    total_composition_pct = sum(comp_dict.values())
    if abs(total_composition_pct - 100.0) < 0.01:
        st.success(f"✅ Mol Toplamı: **%{total_composition_pct:.2f}** (Kusursuz)")
    elif total_composition_pct < 100.0:
        st.warning(f"⚠️ Mol Toplamı: **%{total_composition_pct:.2f}** (Eksik: %{100.0 - total_composition_pct:.2f})")
    else:
        st.error(f"❌ Mol Toplamı: **%{total_composition_pct:.2f}** (Fazla: %{total_composition_pct - 100.0:.2f})")

    costald_res = calculate_costald_density(comp_dict, temperature_k=T_tank_K)
    rho_lng_calculated = costald_res['density_kg_m3']
    M_mix_calculated = costald_res['molar_mass_g_mol']

    st.info(f"**COSTALD Sıvı Yoğunluğu ({T_tank_input:.1f} {T_tank_unit})**: {rho_lng_calculated:.2f} kg/m³")
    st.info(f"**Sıvı Faz Mol Kütlesi (M_liquid)**: {M_mix_calculated:.2f} g/mol")

    override_rho = st.checkbox("Sıvı Yoğunluğunu Manuel Değiştir", value=False, key='in_override_rho')
    if override_rho:
        col_rho, col_rhou = st.columns([3, 2])
        with col_rho:
            rho_input = st.number_input("Manuel LNG Yoğunluğu", value=471.0, key='in_rho_manual')
        with col_rhou:
            rho_unit = st.selectbox("Yoğunluk Birimi", list(DENSITY_UNITS.keys()), index=0, key='in_rho_unit')
        rho_lng = convert_density_to_kg_m3(rho_input, rho_unit)
    else:
        rho_lng = rho_lng_calculated

    # Kargo LNG Kompozisyonu (Tanktan Farklı)
    st.subheader("4b. Kargo LNG Kompozisyonu (İzentalpik Flaş İçin)")
    cargo_diff = st.checkbox("Kargo LNG Kompozisyonu Tanktakinden Farklı", value=False, key='in_cargo_diff',
                             help="İşaretlenirse gemi kargosunun kompozisyonu tanktan ayrı girilir. Karışım flaş hesabında kargo kompozisyonu kullanılır.")
    cargo_comp_dict = None
    if cargo_diff:
        st.caption("Gemi Kargosu LNG Bileşenleri (mol %):")
        cargo_selected = st.multiselect(
            "Kargo Gazlar:",
            options=available_comps,
            default=st.session_state['active_components'],
            format_func=lambda key: EOS_COMPONENT_DATA[key]['name'],
            key="cargo_comps"
        )
        if not cargo_selected:
            st.error("❌ En az 1 gaz bileşeni seçilmelidir!")
            st.stop()
        cargo_comp_dict = {}
        for k in cargo_selected:
            default_cargo_val = st.session_state.get(f"cargo_{k}", 90.0 if k == 'CH4' else 2.0)
            val = st.number_input(
                f"Kargo {EOS_COMPONENT_DATA[k]['name']} %",
                min_value=0.0, max_value=100.0,
                value=default_cargo_val,
                key=f"cargo_{k}",
                step=0.1, format="%.2f"
            )
            cargo_comp_dict[k] = val
        cargo_total = sum(cargo_comp_dict.values())
        if abs(cargo_total - 100.0) < 0.01:
            st.success(f"✅ Kargo Mol Toplamı: **%{cargo_total:.2f}**")
        elif cargo_total < 100.0:
            st.warning(f"⚠️ Kargo Mol Toplamı: **%{cargo_total:.2f}** (Eksik: %{100.0 - cargo_total:.2f})")
        else:
            st.error(f"❌ Kargo Mol Toplamı: **%{cargo_total:.2f}** (Fazla: %{cargo_total - 100.0:.2f})")
        if st.button("⚡ Kargo Kompozisyonunu %100'e Eşitle", key="norm_cargo"):
            if cargo_total > 0:
                for k in cargo_selected:
                    st.session_state[f"cargo_{k}"] = round((st.session_state.get(f"cargo_{k}", 0.0) / cargo_total) * 100.0, 3)
                st.rerun()
        st.caption("💡 *Kargo LNG sıcaklığı ve transfer koşulları **Tab 3 (Flaş BOG Modu)** sekmesinden azot içeriğine ve gemi seyrine göre otomatik veya manuel olarak yönetilmektedir.*")
    else:
        cargo_comp_dict = None

with input_tab3:
    st.subheader("5. Gemi Kargo ve Transfer Koşulları (İzentalpik Flaş İçin)")
    col_pship, col_pship_u = st.columns([3, 2])
    with col_pship:
        P_ship_input = st.number_input("Gemi Pompa Çıkış Basıncı (P_ship)", value=5.0, step=0.5, min_value=0.1, key='in_P_ship',
                                       help="Gemi pompa çıkış basıncı (tipik 4-8 bar_g). Boru hattı kayıpları + tank girişine kadar olan toplam basınç düşüşü izentalpik kabul edilir (konservatif). Gerçek flaş tank girişinde P_tank'a genleşmeyle oluşur.")
    with col_pship_u:
        P_ship_unit = st.selectbox("P_ship Birimi", list(PRESSURE_UNITS_GAUGE.keys()), index=0, key="in_P_ship_unit")
    P_ship_mbar_g = convert_pressure_to_mbar(P_ship_input, P_ship_unit, is_gauge=True)

    # Cargo LNG Temperature & Nitrogen-aware auto calculation
    st.markdown("##### 🌡️ Gemi / Kargo LNG Sıcaklığı ($T_{\\text{cargo}}$)")
    tcargo_mode = st.radio(
        "Kargo LNG Sıcaklığı Belirleme Yöntemi:",
        ["Otomatik (Azot İçeriği & Doygunluk Esaslı)", "Manuel Sıcaklık Girişi"],
        index=0, key='in_tcargo_mode',
        help="Otomatik: Gemi seyir basıncında kargo kompozisyonunun doygunluk sıcaklığını hesaplar. Azot varlığı kaynama noktasını düşürür ve flaşı artırır. Manuel: Saha ölçüm verisi (TT) girilir."
    )

    active_flash_comp = cargo_comp_dict if (cargo_diff and cargo_comp_dict) else comp_dict
    n2_mol_pct = active_flash_comp.get('N2', 0.0)
    P_tank_est_kPa = (P_set + P_atm_min) / 10.0

    if tcargo_mode == "Otomatik (Azot İçeriği & Doygunluk Esaslı)":
        with st.expander("⚙️ Otomatik Hesap Parametreleri (Gemi Seyir Basıncı & Hat Isısı)", expanded=False):
            col_pvoyage, col_dth = st.columns(2)
            with col_pvoyage:
                p_voyage_mbar_g = st.number_input("Gemi Seyir Tank Basıncı (mbar_g)", value=100.0, step=10.0, min_value=0.0, key='in_p_voyage_mbar_g',
                                                  help="Gemi tanklarında seyir esnasında tutulan pozitif basınç (tipik 50-200 mbar_g).")
            with col_dth:
                delta_t_transfer = st.number_input("Pompa & Hat Isı Girdisi (ΔT, °C)", value=0.50, step=0.1, min_value=0.0, key='in_delta_t_transfer',
                                                   help="Kargo pompalarının hidrolik ısınması ve transfer hattından gelen ısı transferi (tipik +0.3 ile +0.8 °C).")

        P_voyage_kPa_a = (p_voyage_mbar_g + P_atm_min) / 10.0
        try:
            t_sat_ship = calculate_bubble_point_temperature(active_flash_comp, pressure_kPa_a=P_voyage_kPa_a, eos=eos_code)
        except Exception:
            t_sat_ship = 111.66

        T_cargo_K = t_sat_ship + delta_t_transfer
        T_cargo_C = T_cargo_K - 273.15
        T_cargo_input = round(T_cargo_C, 2)

        if n2_mol_pct > 0.05:
            st.success(
                f"🔵 **Azot (%{n2_mol_pct:.2f} mol) Tespit Edildi:** Azotun çok düşük kaynama noktası (-195.8 °C) nedeniyle "
                f"gemi doygunluk sıcaklığı **{t_sat_ship:.2f} K ({t_sat_ship - 273.15:.2f} °C)** değerine inmiştir. "
                f"Hat ısınması (+{delta_t_transfer:.2f} K) ile tank giriş sıcaklığı: **{T_cargo_K:.2f} K ({T_cargo_C:.2f} °C)**."
            )
        else:
            st.info(
                f"⚪ **Azot İçermeyen Kompozisyon:** Saf hidrokarbonlar için {p_voyage_mbar_g:.0f} mbar_g gemi basıncında doygunluk "
                f"sıcaklığı **{t_sat_ship:.2f} K ({t_sat_ship - 273.15:.2f} °C)**. "
                f"Hat ısınması (+{delta_t_transfer:.2f} K) ile tank giriş sıcaklığı: **{T_cargo_K:.2f} K ({T_cargo_C:.2f} °C)**."
            )

        # Subcooling / VF netliği: kargo tank basıncında doygunluğun altındaysa dolum flaşı oluşmaz
        try:
            t_bp_tank_cargo = calculate_bubble_point_temperature(active_flash_comp, pressure_kPa_a=P_tank_est_kPa, eos=eos_code)
        except Exception:
            t_bp_tank_cargo = t_bp_est
        if T_cargo_K < t_bp_tank_cargo:
            _dT_gerekli = max(0.0, t_bp_tank_cargo - t_sat_ship)
            st.warning(
                f"⚠️ **Subcooled Kargo → Dolum Flaşı Yok (VF = %0):** T_cargo ({T_cargo_K:.2f} K) tank doygunluk sıcaklığının "
                f"({t_bp_tank_cargo:.2f} K) **{t_bp_tank_cargo - T_cargo_K:.2f} K altında**. Tank basıncı seyir basıncından yüksek "
                f"olduğundan kargo tankta aşırı soğumuş durumdadır ve izentalpik genleşmede buharlaşma olmaz. "
                f"Flaş oluşması için hat ısı girdisi **ΔT ≥ {_dT_gerekli:.2f} K** olmalı ya da manuel modda "
                f"T_cargo ≥ **{t_bp_tank_cargo - 273.15:.2f} °C** girilmelidir."
            )
        else:
            st.success(
                f"🟢 **Doymuş/Kızgın Kargo:** T_cargo ({T_cargo_K:.2f} K) ≥ tank doygunluğu ({t_bp_tank_cargo:.2f} K) → "
                f"izentalpik genleşmede dolum flaşı oluşur."
            )
    else:
        col_tcargo, col_tcargo_u = st.columns([3, 2])
        with col_tcargo:
            T_cargo_input = st.number_input("Kargo LNG Giriş Sıcaklığı (T_cargo)", value=-161.0, step=0.5, key='in_T_cargo',
                                            help="Gemi manifoldundan veya tank girişinde ölçülen gerçek LNG sıcaklığı.")
        with col_tcargo_u:
            T_cargo_unit = st.selectbox("Kargo T Birimi", ['°C', 'K', '°F', '°R'], index=0, key="in_T_cargo_unit")
        T_cargo_K = convert_temperature_to_kelvin(T_cargo_input, T_cargo_unit)
        T_cargo_C = T_cargo_K - 273.15

        try:
            t_tank_bp = calculate_bubble_point_temperature(active_flash_comp, pressure_kPa_a=P_tank_est_kPa, eos=eos_code)
            if T_cargo_K < (t_tank_bp - 0.2):
                st.info(
                    f"ℹ️ **Aşırı Soğutulmuş Kargo (Subcooled):** T_cargo ({T_cargo_C:.2f} °C) < Tank Doygunluk ({t_tank_bp - 273.15:.2f} °C). "
                    f"Tank basıncında sıvı subcooled olduğundan saf hidrokarbon flaşı %0 olabilir (azot çözünmüşse azot flaşı oluşur)."
                )
            else:
                st.warning(
                    f"⚠️ **Doymuş/Kızgın Sıvı:** T_cargo ({T_cargo_C:.2f} °C) ≥ Tank Doygunluk ({t_tank_bp - 273.15:.2f} °C). "
                    f"Tank girişinde genleşmeyle doğrudan termodinamik flaş gazlaşması gerçekleşecektir."
                )
        except Exception as _bp_err:
            logger.warning(f"Kargo doygunluk sıcaklığı hesaplanamadı: {_bp_err}")

    st.subheader("6. Flaş BOG Debisi Giriş Modu")
    flash_mode = st.radio(
        "Flaş BOG Hesap Modu:",
        ["İzentalpik Flaş (PH-Flash, EOS)", "Sabit Flaş Oranı (%)", "Manuel Debi Girişi"],
        index=0, key='in_flash_mode',
        help="İzentalpik flaş: Gemi LNG'sinin tank basıncına genleşmesiyle flaş oranı (NFPA 59A / API 625 uyumlu). "
             "Sabit oran/debi: kullanıcı tanımlı manuel girdi."
    )
    st.caption(
        "ℹ️ *Flaş, tahliye (set) basıncında değerlendirilir: P_flash = P_set + P_atm_min. Set basıncı flaş için en düşük "
        "(en az konservatif) varsayımdır; tank işletme basıncı set altında ise flaş oranı daha yüksek olur.*"
    )

    if flash_mode == "Manuel Debi Girişi":
        flash_manual_mode = True
        col_wf, col_wfu = st.columns([3, 2])
        with col_wf:
            w_flash_input = st.number_input("Manuel Flaş BOG Debisi", value=94200.0, step=1000.0, key='in_w_flash_manual')
        with col_wfu:
            w_flash_unit = st.selectbox("Flaş Debi Birimi", list(MASS_FLOW_UNITS.keys()), index=0, key='in_w_flash_unit')
        w_flash_manual_kg_h = convert_mass_flow_to_kg_h(w_flash_input, w_flash_unit)
        manual_flash_pct = 2.0
        is_isenthalpic_mode = False
        flash_basis = 'mass'
    elif flash_mode == "Sabit Flaş Oranı (%)":
        flash_manual_mode = False
        w_flash_manual_kg_h = 94200.0
        manual_flash_pct = st.number_input("Manuel Sabit Flaş Oranı (%)", value=2.0, step=0.1, min_value=0.0, max_value=100.0, key='in_manual_flash_pct')
        flash_basis_choice = st.radio(
            "Flaş Oranı Bazı:",
            ["Molar (mol/mol) - fiziksel V/F", "Kütlesel (kg/kg) - doğrudan kütle oranı"],
            index=0, key='in_flash_basis', horizontal=True,
            help="PH-Flaş/VLE sonuçları mol bazlıdır. Molar seçilirse W_flash, M_vapor/M_feed kütle dönüşümüyle hesaplanır. "
                 "Kütlesel seçimi yalnızca girdi gerçekten kütle% ise kullanılmalıdır."
        )
        flash_basis = 'molar' if flash_basis_choice.startswith('Molar') else 'mass'
        is_isenthalpic_mode = False
    else:  # İzentalpik Flaş (PH-Flash, EOS)
        flash_manual_mode = False
        w_flash_manual_kg_h = 94200.0
        manual_flash_pct = None
        is_isenthalpic_mode = True
        flash_basis = 'molar'

    st.subheader("7. Tank Isı Girişi BOG Giriş Modu")
    bog_mode = st.radio(
        "Tank BOG Hesaplama Yöntemi:",
        ["Otomatik (BOR %/gün Tank Hacminden)", "Manuel BOG Debisi Girişi"],
        index=0, key='in_bog_mode',
        help="Tank net hacmi (V_n) ve günlük kaynama oranı (% BOR/gün) ile otomatik hesaplama veya manuel BOG debisi."
    )

    if bog_mode == "Otomatik (BOR %/gün Tank Hacminden)":
        bog_auto_mode = True
        bor_pct_per_day = st.number_input("Günlük Kaynama Oranı (BOR %/gün)", value=0.10, step=0.01, min_value=0.01, format="%.2f", key='in_bor_pct_per_day', help="Tipik LNG tam dolum tank BOR değeri: %0.05 - %0.15 /gün aralığındadır.")
        bor_calc = calculate_bor_tank_bog(tank_volume_m3=V_n, lng_density_kg_m3=rho_lng, bor_pct_per_day=bor_pct_per_day)
        w_bog_kg_h = bor_calc['w_bog_kg_h']
        st.info(f"💡 Otomatik Hesaplanan Tank BOG: **{w_bog_kg_h:,.1f} kg/h** (BOR: %{bor_pct_per_day:.2f}/gün)")
    else:
        bog_auto_mode = False
        bor_pct_per_day = 0.10
        col_wbog, col_wbogu = st.columns([3, 2])
        with col_wbog:
            w_bog_input = st.number_input("Isı Girişi Tank BOG Debisi", value=1570.0, step=100.0, key='in_w_bog_manual')
        with col_wbogu:
            w_bog_unit = st.selectbox("BOG Debi Birimi", list(MASS_FLOW_UNITS.keys()), index=0, key='in_w_bog_unit')
        w_bog_kg_h = convert_mass_flow_to_kg_h(w_bog_input, w_bog_unit)

# --- INPUT VALIDATION (hard errors stop the calculation, warnings continue) ---
_validation_errors = []
if P_atm_min > P_atm_max:
    _validation_errors.append(f"Min. atmosferik basınç ({P_atm_min:.2f} mbar_a), maksimumdan ({P_atm_max:.2f} mbar_a) büyük olamaz.")
if total_composition_pct <= 0.0:
    _validation_errors.append("LNG kompozisyonu toplamı sıfır olamaz; en az bir bileşen giriniz.")
for _tname, _tval in (("Tank LNG", T_tank_K), ("Tahliye buharı", T_relief_K), ("Kargo LNG", T_cargo_K), ("Yangın", T_fire_K)):
    if not (60.0 <= _tval <= 400.0):
        _validation_errors.append(f"{_tname} sıcaklığı ({_tval:.2f} K) fiziksel aralık (60-400 K) dışında.")
if cargo_comp_dict is not None and sum(cargo_comp_dict.values()) <= 0.0:
    _validation_errors.append("Kargo LNG kompozisyonu toplamı sıfır olamaz.")
# Finite / physical-range checks for scalar inputs (guards loaded JSON configs)
for _nname, _nval, _nmin in (
    ("Tank hacmi V_n", V_n, 1.0), ("Dolum debisi Q_fill", Q_fill, 1.0),
    ("P_atm_min", P_atm_min, 100.0), ("P_atm_max", P_atm_max, 100.0),
    ("P_set", P_set, 1.0), ("P_ship", P_ship_mbar_g, 0.0),
    ("Sıvı yoğunluğu ρ_LNG", rho_lng, 1.0), ("Tank BOG debisi", w_bog_kg_h, 0.0),
    ("Islatılmış alan", wetted_area_m2, 1.0), ("Gizli ısı L", latent_heat_kJ_kg, 1.0),
):
    if not math.isfinite(_nval):
        _validation_errors.append(f"{_nname} sonlu (finite) bir sayı olmalıdır.")
    elif _nval < _nmin:
        _validation_errors.append(f"{_nname} fiziksel alt sınırın altında ({_nval:g} < {_nmin:g}).")
if not (0.0 <= P_set_input <= 50000.0):
    _validation_errors.append("P_set 0-50000 mbar_g aralığı dışında.")
if _validation_errors:
    for _err in _validation_errors:
        st.error(f"❌ **Girdi Doğrulama Hatası:** {_err}")
    st.stop()

# Save/Load Configuration (all input widgets + compositions)
with st.sidebar.expander("💾 Konfigürasyon Kaydet/Yükle"):
    col_save, col_load = st.columns(2)
    with col_save:
        _cfg = {'config_version': 2}
        for _k in INPUT_DEFAULTS:
            _cfg[_k] = st.session_state.get(_k, INPUT_DEFAULTS[_k])
        _cfg['active_components'] = list(st.session_state.get('active_components', DEFAULT_ACTIVE_COMPS))
        _cfg['composition'] = {
            c: st.session_state.get(f"comp_{c}", DEFAULT_VALS.get(c, 0.0))
            for c in EOS_COMPONENT_DATA.keys()
        }
        if cargo_comp_dict is not None:
            _cfg['cargo_active_components'] = list(st.session_state.get('cargo_comps', []))
            _cfg['cargo_composition'] = {k: st.session_state.get(f"cargo_{k}", v) for k, v in cargo_comp_dict.items()}
        st.download_button("📥 Kaydet", data=json.dumps(_cfg, indent=2, ensure_ascii=False), file_name="LNG_config.json", mime="application/json")
    with col_load:
        loaded_file = st.file_uploader("📂 Yükle", type="json", label_visibility="collapsed")
        if loaded_file:
            try:
                loaded = json.loads(loaded_file.read().decode())
                if not isinstance(loaded, dict):
                    raise ValueError("Konfigürasyon kök elemanı bir JSON nesnesi olmalıdır.")
                _cfg_ver = loaded.get('config_version')
                if _cfg_ver is not None and not isinstance(_cfg_ver, int):
                    raise ValueError("config_version tamsayı olmalıdır.")
                if isinstance(_cfg_ver, int) and _cfg_ver > 2:
                    st.warning(f"⚠️ Konfigürasyon sürümü ({_cfg_ver}) bu uygulamadan yeni; bilinmeyen alanlar yok sayılacak.")
                for _k, _default in INPUT_DEFAULTS.items():
                    if _k in loaded:
                        _val = loaded[_k]
                        if _default is not None and not isinstance(_val, type(_default)):
                            if not (isinstance(_default, float) and isinstance(_val, (int, float)) and not isinstance(_val, bool)):
                                raise ValueError(f"'{_k}' alanı tipi uyumsuz ({type(_val).__name__}).")
                        if isinstance(_val, float) and not math.isfinite(_val):
                            raise ValueError(f"'{_k}' alanı sonlu (finite) bir sayı değil.")
                        st.session_state[_k] = _val
                # Backward compatibility: old "EOS VLE Flaş Oranı" mode maps to isenthalpic PH flash
                if st.session_state.get('in_flash_mode') == "EOS VLE Flaş Oranı (%V/F)":
                    st.session_state['in_flash_mode'] = "İzentalpik Flaş (PH-Flash, EOS)"
                if loaded.get('active_components'):
                    st.session_state['active_components'] = list(loaded['active_components'])
                for k, v in loaded.get('composition', {}).items():
                    st.session_state[f"comp_{k}"] = v
                if loaded.get('cargo_active_components'):
                    st.session_state['cargo_comps'] = list(loaded['cargo_active_components'])
                for k, v in loaded.get('cargo_composition', {}).items():
                    st.session_state[f"cargo_{k}"] = v
                st.success("✅ Yüklendi.")
                st.rerun()
            except Exception as ex:
                st.error(f"Hata: {ex}")

# --- CORE THERMODYNAMIC & RELIEF CALCULATIONS ---

def _mixture_molar_mass(composition_mol: dict) -> float:
    """Molar mass (g/mol) of a normalized or raw composition dict."""
    total = sum(composition_mol.values())
    if total <= 0.0:
        return 0.0
    return sum(v * EOS_COMPONENT_DATA[c]['M'] for c, v in composition_mol.items() if c in EOS_COMPONENT_DATA) / total


def _blend_relieving_vapor(y_tank, t_tank_k, w_tank_kg_h, y_flash, t_flash_k, w_flash_kg_h):
    """
    Molar-flow blend of the displacement/BOG vapor (tank) and flash vapor streams.

    Returns (T_mix_K, z_mix, n_tank_mol_h, n_flash_mol_h). The mixed composition is
    used to evaluate Z, k and M at the relieving state instead of arithmetically
    averaging non-linear properties.
    """
    n_tank = max(0.0, w_tank_kg_h) / max(1e-9, _mixture_molar_mass(y_tank))
    n_flash = max(0.0, w_flash_kg_h) / max(1e-9, _mixture_molar_mass(y_flash))
    n_total = n_tank + n_flash
    if n_total <= 0.0:
        return t_tank_k, dict(y_tank), 0.0, 0.0
    z_mix = {}
    for c in set(y_tank) | set(y_flash):
        value = (n_tank * y_tank.get(c, 0.0) + n_flash * y_flash.get(c, 0.0)) / n_total
        if value > 0.0:
            z_mix[c] = value
    t_mix = (n_tank * t_tank_k + n_flash * t_flash_k) / n_total
    return t_mix, z_mix, n_tank, n_flash


def _solve_max_fill_m3_h(valve, *, n_working, p1_kpa, p2_kpa, t_mix_k, z_sizing, m_sizing, k_sizing,
                         rho_feed, rho_v_disp, w_bog_kg_h, flash_mass_pct, q_hi_hint):
    """
    Bisection solve for the maximum LNG fill rate for which the valve's air capacity
    (at operational relieving conditions) exactly covers the operational relief load.

    Uses the operational mass balance (including the fixed heat-ingress BOG), so it
    remains valid when the governing scenario is fire. Gas properties (Z, k, M, t_mix)
    are held at the evaluated operating state while the Q-proportional terms
    (displacement and flash flows) scale with the fill rate. Returns None if the valve
    cannot cover the load at any upper bound.
    """
    capacity_air_m3_h = valve['air_capacity_m3_h']

    def required_air_m3_h(q_fill):
        ld = calculate_relieving_loads(
            q_fill_m3_h=q_fill, rho_lng_kg_m3=rho_feed, rho_v_kg_m3=rho_v_disp,
            flash_pct=flash_mass_pct, w_bog_kg_h=w_bog_kg_h, flash_basis='mass'
        )
        return calculate_nfpa59a_air_equivalent(
            ld['w_total_kg_s'], temperature_k=t_mix_k, Z=z_sizing, M_g_mol=m_sizing,
            k=k_sizing, K_d=0.85, P1_kPa_a=p1_kpa, P2_kPa_a=p2_kpa
        ) / n_working

    lo = 1.0
    hi = max(10.0, float(q_hi_hint))
    for _ in range(60):
        if required_air_m3_h(hi) >= capacity_air_m3_h:
            break
        hi *= 2.0
    else:
        return None
    if required_air_m3_h(lo) > capacity_air_m3_h:
        return 0.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if required_air_m3_h(mid) < capacity_air_m3_h:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _compute_all_results(
    p_set_mbar, overpressure_pct, p_atm_min_mbar, p_atm_max_mbar,
    q_fill_m3h, rho_lng_val, comp_dict_frozen, t_relief_K, t_cargo_K,
    t_fire_K, eos_code_val, n_working, flash_manual_mode_val,
    w_flash_manual_kg_h_val, flash_pct_val, w_bog_kg_h_val,
    bog_auto_mode_val, bor_pct_per_day_val,
    wetted_area_m2_val, insulation_factor_F_val, latent_heat_kJ_kg_val,
    fire_overpressure_pct=21.0, fire_q_constant_val=70.9, fire_K_d_val=0.85,
    is_isenthalpic_mode_val=False, p_ship_mbar_g_val=5000.0,
    cargo_comp_frozen=None, flash_basis_val='molar', valve_type_filter_val='all'
):
    """Cached computation pipeline for all thermodynamic and sizing results.

    State policy (v2.0):
    - Displacement/BOG vapor uses the tank composition and the P1 relieving density.
    - The PH flash supplies its own T_flash and vapor composition; the molar flash
      fraction is converted to a mass flow with M_vapor/M_feed.
    - Tank and flash vapor streams are blended on a molar basis; sizing properties
      (Z, k, M) are evaluated from that mixture at (T_mix, P1) with the selected EOS.
    - Required orifice areas use a common reference Kd = 0.85 for operational and
      fire scenarios (unbiased governing comparison). Valve capacities always use
      each valve's catalog Kd. ``fire_K_d_val`` is accepted for backward
      compatibility only and no longer overrides catalog coefficients.
    """
    if str(flash_basis_val).lower() not in ('molar', 'mass'):
        raise ValueError(f"Geçersiz flaş bazı: {flash_basis_val}")
    comp_dict = dict(comp_dict_frozen)
    flash_comp = dict(cargo_comp_frozen) if cargo_comp_frozen else comp_dict

    P1_mbar_a = p_set_mbar + (p_set_mbar * (overpressure_pct / 100.0)) + p_atm_min_mbar
    P1_kPa_a = P1_mbar_a / 10.0
    P2_kPa_a = p_atm_min_mbar / 10.0
    P_tank_kPa_a = (p_set_mbar + p_atm_min_mbar) / 10.0
    P1_fire_kPa_a = (p_set_mbar + (p_set_mbar * (fire_overpressure_pct / 100.0)) + p_atm_min_mbar) / 10.0
    P_ship_kPa_a = (p_ship_mbar_g_val + p_atm_min_mbar) / 10.0

    # 1) Tank vapor state (equilibrium at tank/set pressure) - composition source
    vle_res = calculate_two_phase_vle_flash(comp_dict, temperature_k=t_relief_K, pressure_kPa_a=P_tank_kPa_a, eos=eos_code_val)
    y_tank = vle_res['y_vapor']
    Z_factor = vle_res['Z_gas']
    k_factor = vle_res['k_mix']
    rho_v = vle_res['rho_v_kg_m3']
    M_vapor = vle_res['M_vapor_g_mol']

    # 2) Isenthalpic (PH) flash of the cargo feed: own T_flash and vapor composition
    isenthalpic_res = None
    if is_isenthalpic_mode_val or flash_pct_val is None:
        isenthalpic_res = calculate_isenthalpic_flash(
            flash_comp,
            t_feed_k=t_cargo_K,
            p_feed_kPa_a=P_ship_kPa_a,
            p_flash_kPa_a=P_tank_kPa_a,
            eos=eos_code_val
        )
        effective_flash_pct = isenthalpic_res['flash_pct']
        y_flash = isenthalpic_res['y_vapor']
        t_flash_K = isenthalpic_res['T_flash_K']
    else:
        effective_flash_pct = flash_pct_val
        y_flash = y_tank
        t_flash_K = t_relief_K

    # 3) Feed (liquid) properties from the flash composition at cargo conditions
    feed_costald = calculate_costald_density(flash_comp, temperature_k=t_cargo_K)
    M_feed = feed_costald['molar_mass_g_mol']
    rho_feed = feed_costald['density_kg_m3']

    # 4) Vapor molar masses needed for the molar -> mass flash conversion
    M_vapor_flash = _mixture_molar_mass(y_flash)

    # 5) Displaced tank vapor density at the relieving pressure P1
    tank_vapor_at_p1 = calculate_eos_mixture_properties(y_tank, t_relief_K, P1_kPa_a, eos=eos_code_val)
    rho_v_disp = tank_vapor_at_p1['rho_v_kg_m3']

    # 6) Relieving loads (molar-consistent flash mass flow)
    loads = calculate_relieving_loads(
        q_fill_m3_h=q_fill_m3h, rho_lng_kg_m3=rho_feed, rho_v_kg_m3=rho_v_disp,
        flash_pct=effective_flash_pct, w_bog_kg_h=w_bog_kg_h_val,
        flash_manual_mode=flash_manual_mode_val,
        w_flash_manual_kg_h=w_flash_manual_kg_h_val,
        flash_basis=flash_basis_val,
        m_vapor_g_mol=M_vapor_flash if is_isenthalpic_mode_val or flash_pct_val is None else M_vapor,
        m_feed_g_mol=M_feed
    )

    # 7) Molar blend of the two vapor streams -> sizing properties at (T_mix, P1)
    t_mix_K, z_mix, n_tank_stream, n_flash_stream = _blend_relieving_vapor(
        y_tank, t_relief_K, loads['w_disp_kg_h'] + loads['w_bog_kg_h'],
        y_flash, t_flash_K, loads['w_flash_kg_h']
    )
    sizing_props = calculate_eos_mixture_properties(z_mix, t_mix_K, P1_kPa_a, eos=eos_code_val)
    Z_sizing = sizing_props['Z_gas']
    k_sizing = sizing_props['k_mix']
    M_sizing = sizing_props['M_mix']
    cargo_vapor_blend_used = bool(cargo_comp_frozen and n_flash_stream > 0.0)

    q_a_total = calculate_nfpa59a_air_equivalent(
        loads['w_total_kg_s'], temperature_k=t_mix_K, Z=Z_sizing, M_g_mol=M_sizing,
        k=k_sizing, K_d=0.85, P1_kPa_a=P1_kPa_a, P2_kPa_a=P2_kPa_a
    )
    q_a_per_valve = q_a_total / n_working

    subcrit = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=loads['w_total_kg_h'] / n_working,
        P1_kPa_a=P1_kPa_a, P2_kPa_a=P2_kPa_a,
        temperature_k=t_mix_K, M_g_mol=M_sizing, Z=Z_sizing, k=k_sizing, K_d=0.85
    )

    matrix = evaluate_valve_matrix(
        q_a_per_valve_m3_h=q_a_per_valve, P1_kPa_a=P1_kPa_a, P2_kPa_a=P2_kPa_a, K_d=None,
        valve_type=valve_type_filter_val
    )

    # Fire Scenario: separate fire overpressure; catalog Kd for every valve in the
    # matrix, reference Kd = 0.85 for the required area (same basis as operational).
    fire_res = calculate_fire_scenario_load(
        wetted_area_m2=wetted_area_m2_val, insulation_factor_F=insulation_factor_F_val,
        latent_heat_kJ_kg=latent_heat_kJ_kg_val, fire_coefficient_c_si=fire_q_constant_val
    )

    fire_vle_res = calculate_two_phase_vle_flash(comp_dict, temperature_k=t_fire_K, pressure_kPa_a=P1_fire_kPa_a, eos=eos_code_val)
    fire_Z = fire_vle_res['Z_gas']
    fire_k = fire_vle_res['k_mix']
    fire_M_vapor = fire_vle_res['M_vapor_g_mol']

    fire_q_a_total = calculate_nfpa59a_air_equivalent(
        fire_res['w_fire_kg_s'], temperature_k=t_fire_K, Z=fire_Z, M_g_mol=fire_M_vapor,
        k=fire_k, K_d=0.85, P1_kPa_a=P1_fire_kPa_a, P2_kPa_a=P2_kPa_a
    )
    fire_q_a_per_valve = fire_q_a_total / n_working

    fire_subcrit = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=fire_res['w_fire_kg_h'] / n_working,
        P1_kPa_a=P1_fire_kPa_a, P2_kPa_a=P2_kPa_a,
        temperature_k=t_fire_K, M_g_mol=fire_M_vapor, Z=fire_Z, k=fire_k, K_d=0.85
    )

    fire_matrix = evaluate_valve_matrix(
        q_a_per_valve_m3_h=fire_q_a_per_valve, P1_kPa_a=P1_fire_kPa_a, P2_kPa_a=P2_kPa_a, K_d=None,
        valve_type=valve_type_filter_val
    )

    # Governing Scenario by orifice area (both required areas use the same reference Kd).
    # Q_a is NOT comparable across scenarios because each scenario's air capacity is
    # evaluated at its own relieving pressure (fire 21% vs operational 10% overpressure).
    gov_decision = compute_governing_decision(subcrit['A_o_mm2'], fire_subcrit['A_o_mm2'])
    governing_is_fire = gov_decision['governing'] == 'fire'
    if governing_is_fire:
        governing_scenario = "🔥 Yangin Senaryosu (Fire Case)"
        governing_w_total_kg_h = fire_res['w_fire_kg_h']
        governing_q_a_total = fire_q_a_total
        governing_A_o_mm2 = fire_subcrit['A_o_mm2']
        governing_matrix = fire_matrix
    else:
        governing_scenario = "⚙️ Operasyonel Senaryo (Dolum + Flas + BOG)"
        governing_w_total_kg_h = loads['w_total_kg_h']
        governing_q_a_total = q_a_total
        governing_A_o_mm2 = subcrit['A_o_mm2']
        governing_matrix = matrix

    # Matched valves use governing air capacity (retrieve all evaluated down to >= 90% coverage)
    matched_valves = search_matching_valves(
        required_air_capacity_m3_h=governing_q_a_total / n_working,
        P1_kPa_a=P1_fire_kPa_a if governing_is_fire else P1_kPa_a,
        P2_kPa_a=P2_kPa_a,
        show_all_above_90=True,
        valve_type=valve_type_filter_val
    )

    return {
        'P1_kPa_a': P1_kPa_a, 'P2_kPa_a': P2_kPa_a, 'P1_mbar_a': P1_mbar_a,
        'P1_fire_kPa_a': P1_fire_kPa_a, 'fire_overpressure_pct': fire_overpressure_pct,
        'fire_coefficient_c_si': fire_res['fire_coefficient_c_si'],
        'fire_K_d_reference': 0.85,
        'vle_res': vle_res, 'Z_factor': Z_factor, 'k_factor': k_factor, 'rho_v': rho_v,
        'M_vapor': M_vapor, 'effective_flash_pct': effective_flash_pct, 'loads': loads,
        'Z_sizing': Z_sizing, 'k_sizing': k_sizing, 'M_sizing': M_sizing,
        't_mix_K': t_mix_K, 'z_mix': z_mix,
        'sizing_eos_name': sizing_props.get('eos_name', eos_code_val),
        'sizing_fallback_used': bool(sizing_props.get('fallback_used', False)),
        'rho_v_disp': rho_v_disp, 'rho_v_sizing': sizing_props['rho_v_kg_m3'],
        'M_feed': M_feed, 'rho_feed': rho_feed, 'flash_basis': loads['flash_basis'],
        'M_vapor_flash': M_vapor_flash,
        'cargo_vapor_blend_used': cargo_vapor_blend_used,
        'q_a_total': q_a_total, 'q_a_per_valve': q_a_per_valve,
        'subcrit': subcrit, 'matrix': matrix,
        'fire_res': fire_res, 'fire_Z': fire_Z, 'fire_k': fire_k, 'fire_M_vapor': fire_M_vapor,
        'fire_q_a_total': fire_q_a_total, 'fire_q_a_per_valve': fire_q_a_per_valve,
        'fire_subcrit': fire_subcrit, 'fire_matrix': fire_matrix,
        'governing_scenario': governing_scenario, 'governing_w_total_kg_h': governing_w_total_kg_h,
        'governing_q_a_total': governing_q_a_total, 'governing_A_o_mm2': governing_A_o_mm2,
        'governing_matrix': governing_matrix, 'governing_is_fire': governing_is_fire,
        'governing_margin_pct': gov_decision['margin_pct'],
        'governing_borderline': gov_decision['borderline'],
        'matched_valves': matched_valves, 'eos_code': eos_code_val,
        'isenthalpic_res': isenthalpic_res,
        'valve_type_filter': valve_type_filter_val
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
        t_relief_K=T_relief_K, t_cargo_K=T_cargo_K, t_fire_K=T_fire_K,
        eos_code_val=eos_code, n_working=N_working,
        flash_manual_mode_val=flash_manual_mode,
        w_flash_manual_kg_h_val=w_flash_manual_kg_h, flash_pct_val=manual_flash_pct,
        w_bog_kg_h_val=w_bog_kg_h, bog_auto_mode_val=bog_auto_mode,
        bor_pct_per_day_val=bor_pct_per_day,
        wetted_area_m2_val=wetted_area_m2, insulation_factor_F_val=insulation_factor_F,
        latent_heat_kJ_kg_val=latent_heat_kJ_kg,
        fire_overpressure_pct=fire_overpressure_pct, fire_q_constant_val=fire_coefficient_c_si,
        is_isenthalpic_mode_val=is_isenthalpic_mode,
        p_ship_mbar_g_val=P_ship_mbar_g,
        cargo_comp_frozen=tuple(sorted(cargo_comp_dict.items())) if cargo_comp_dict else None,
        flash_basis_val=flash_basis,
        valve_type_filter_val=valve_type_code
    )

    # Unpack results
    P1_kPa_a = results['P1_kPa_a']
    P2_kPa_a = results['P2_kPa_a']
    P1_mbar_a = results['P1_mbar_a']
    P1_fire_kPa_a = results['P1_fire_kPa_a']
    vle_res = results['vle_res']
    Z_factor = results['Z_factor']
    k_factor = results['k_factor']
    rho_v = results['rho_v']
    M_vapor = results['M_vapor']
    Z_sizing = results.get('Z_sizing', Z_factor)
    k_sizing = results.get('k_sizing', k_factor)
    M_sizing = results.get('M_sizing', M_vapor)
    cargo_vapor_blend_used = results.get('cargo_vapor_blend_used', False)
    effective_flash_pct = results['effective_flash_pct']
    loads = results['loads']
    q_a_total = results['q_a_total']
    q_a_per_valve = results['q_a_per_valve']
    subcrit = results['subcrit']
    matrix = results['matrix']
    fire_res = results['fire_res']
    fire_Z = results['fire_Z']
    fire_k = results['fire_k']
    fire_M_vapor = results['fire_M_vapor']
    fire_q_a_total = results['fire_q_a_total']
    fire_q_a_per_valve = results['fire_q_a_per_valve']
    fire_subcrit = results['fire_subcrit']
    fire_matrix = results['fire_matrix']
    governing_scenario = results['governing_scenario']
    governing_w_total_kg_h = results['governing_w_total_kg_h']
    governing_q_a_total = results['governing_q_a_total']
    governing_A_o_mm2 = results['governing_A_o_mm2']
    governing_matrix = results['governing_matrix']
    governing_is_fire = results['governing_is_fire']
    governing_margin_pct = results.get('governing_margin_pct')
    governing_borderline = results.get('governing_borderline', False)
    matched_valves = results['matched_valves']
    isenthalpic_res = results.get('isenthalpic_res', None)
    t_mix_K = results.get('t_mix_K', T_relief_K)
    rho_v_disp = results.get('rho_v_disp', rho_v)
    rho_v_sizing = results.get('rho_v_sizing', rho_v)
    M_feed = results.get('M_feed', M_mix_calculated)
    rho_feed = results.get('rho_feed', rho_lng)
    flash_basis = results.get('flash_basis', 'molar')
    z_mix = results.get('z_mix', vle_res['y_vapor'])
    M_vapor_flash = _mixture_molar_mass(isenthalpic_res['y_vapor']) if isenthalpic_res else M_vapor
    enthalpy_model = (isenthalpic_res or {}).get('enthalpy_model', results.get('eos_code', 'PR'))
    sizing_eos_name = results.get('sizing_eos_name', vle_res['eos_used'])

    # Normalized composition actually used by the calculations
    _mol_total = sum(comp_dict.values()) or 100.0
    normalized_composition = {c: v / _mol_total * 100.0 for c, v in comp_dict.items()}
    cargo_normalized_composition = None
    if cargo_comp_dict:
        _cargo_total = sum(cargo_comp_dict.values()) or 100.0
        cargo_normalized_composition = {c: v / _cargo_total * 100.0 for c, v in cargo_comp_dict.items()}

    # Report Data Dictionary Compilation (single source of truth for the HTML report)
    report_inputs = {
        'project_name': st.session_state.get('in_project_name', ''),
        'project_revision': st.session_state.get('in_project_revision', ''),
        'project_prepared_by': st.session_state.get('in_project_prepared_by', ''),
        'project_checked_by': st.session_state.get('in_project_checked_by', ''),
        'eos_choice': eos_choice,
        'V_n': V_n, 'Q_fill': Q_fill, 'P_atm_min': P_atm_min, 'P_atm_max': P_atm_max,
        'P_set': P_set, 'Overpressure_pct': Overpressure_pct,
        'fire_overpressure_pct': fire_overpressure_pct,
        'fire_coefficient_c_si': fire_coefficient_c_si, 'fire_K_d_reference': 0.85,
        'N_working': N_working, 'N_spare': N_spare,
        'T_tank_K': T_tank_K, 'T_relief_K': T_relief_K, 'T_cargo_K': T_cargo_K,
        'T_fire_K': T_fire_K, 'P_ship_kPa_a': (P_ship_mbar_g + P_atm_min) / 10.0,
        'flash_pct': effective_flash_pct, 'flash_manual_mode': flash_manual_mode,
        'flash_basis': flash_basis,
        'bog_auto_mode': bog_auto_mode, 'bor_pct_per_day': bor_pct_per_day,
        'wetted_area_m2': wetted_area_m2, 'insulation_factor_F': insulation_factor_F,
        'latent_heat_kJ_kg': latent_heat_kJ_kg, 'K_d': 0.85, 'P1_kPa_a': P1_kPa_a,
        'P1_fire_kPa_a': P1_fire_kPa_a,
        'normalized_composition': normalized_composition,
        'raw_composition': dict(comp_dict),
        'cargo_normalized_composition': cargo_normalized_composition,
        'standard_editions': STANDARD_EDITIONS,
        'scope_statement': SCOPE_STATEMENT,
        'valve_type_filter': valve_type_code,
        'valve_type_filter_label': valve_type_choice,
        'max_fill_m3_h': None,  # filled after the recommendation block below
    }

    report_thermo = {
        'density_kg_m3': rho_lng, 'molar_mass_g_mol': M_mix_calculated,
        'vapor_density': rho_v, 'Z_factor': Z_factor,
        'k_factor': k_factor, 'M_vapor': M_vapor,
        'Z_sizing': Z_sizing, 'k_sizing': k_sizing, 'M_sizing': M_sizing,
        't_mix_K': t_mix_K, 'rho_v_disp': rho_v_disp, 'rho_v_sizing': rho_v_sizing,
        'M_feed': M_feed, 'rho_feed': rho_feed,
        'cargo_vapor_blend_used': cargo_vapor_blend_used,
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
        'fire_Z': fire_Z, 'fire_k': fire_k, 'T_fire_K': T_fire_K,
        'isenthalpic_res': isenthalpic_res,
        'operational_matrix': matrix,
        'flash_basis': loads.get('flash_basis', flash_basis),
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
    st.success("✅ **LNG Kompozisyon Doğrulaması**: Girilen gaz bileşenlerinin mol toplamı tam olarak **%100.00**'dir.")

# Metrics Row (6 key thermodynamic metrics including Z_gas and dynamic k_mix(T,P))
m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)

with m_col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{rho_lng:.1f} kg/m³</div>
        <div class="metric-label">Sıvı LNG Yoğunluğu (ρ_LNG @ {T_tank_input:.1f} {T_tank_unit})</div>
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
        fp = isenthalpic_res['flash_pct']
        if fp < 0.01:
            flash_value = f"%{fp:.4f}"
        elif fp < 1.0:
            flash_value = f"%{fp:.3f}"
        else:
            flash_value = f"%{fp:.2f}"
        if isenthalpic_res['converged']:
            flash_tooltip = f"T_flash={isenthalpic_res['T_flash_K']:.2f}K"
            if fp <= 0.001:
                flash_tooltip += " • Subcooled (flaş yok)"
        else:
            flash_tooltip = "⚠️ Yakınsama uyarısı"
    else:
        flash_value = f"%{vle_res['flash_pct']:.2f}"
        flash_tooltip = ""
    flash_label = "Dolum Flaş Oranı (VF)"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{flash_value}</div>
        <div class="metric-label">{flash_label}</div>
        <div class="metric-value" style="font-size:10px;color:#94a3b8">{flash_tooltip}</div>
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
_valve_type_label = {'pilot': "Yalnızca Pilot Kumandalı", 'spring': "Yalnızca Yaylı", 'all': "Tümü (Pilot + Yaylı)"}[valve_type_code]
st.caption(f"Min. Sahadaki Atmosferik Basınç ({P_atm_min:.2f} mbar_a), Relieving Pressure ({P1_mbar_a:.2f} mbar_a) ve Vana Tipi Filtresi: **{_valve_type_label}**")

filter_mode = st.radio(
    "Vana Görünüm Filtresi:",
    ["Tüm Uygun Vanaları Göster (%90 - %200 Kapasite)", "Yalnızca Uyumlu Vanaları Göster (%100 - %200 Kapasite)"],
    index=0,
    horizontal=True, key='in_filter_mode',
    help="Kriyojenik emniyet prensipleri ve API 520 Part II uyarınca, %90 altı yetersiz, %200 üzeri ise aşırı boyutlandırılmış (chattering / flutter riski) vanalar filtrelenir."
)

if not vle_res.get('converged', True):
    st.warning(f"⚠️ **VLE Flaş Yakınsama Uyarısı**: Faz dengesi {vle_res.get('iterations', '?')} iterasyonda tam yakınsamadı; Z/k/ρ_v sonuçları yaklaşık değerdir.")
if vle_res.get('phase_split_model') == 'wilson_initial' and eos_code in ('HEOS', 'IDEAL'):
    st.info(
        f"ℹ️ **Faz Ayrımı Modeli:** {vle_res.get('eos_used', eos_code)} seçili; ancak iki fazlı faz ayrımı "
        f"şu an Wilson K-değerleriyle başlatılmakta, özellikler (Z, k, ρ_v, M) seçilen EOS ile hesaplanmaktadır. "
        f"Rapor bu durumu 'phase_split_model' alanında kaydeder."
    )

if not matrix:
    _filter_label = {'pilot': "Yalnızca Pilot Kumandalı", 'spring': "Yalnızca Yaylı", 'all': "Tümü"}[valve_type_code]
    st.error(
        f"❌ **Değerlendirilecek vana bulunamadı.** `psv_database.json` yüklenemedi/boş olabilir ya da "
        f"seçilen vana tipi filtresinde ({_filter_label}) uygun kayıt yoktur."
    )
    st.stop()

matrix_df = pd.DataFrame(matrix)
# Sort by orifice area ascending: smallest valve first
matrix_df = matrix_df.sort_values(by='orifice_area_mm2', ascending=True)

if filter_mode == "Yalnızca Uyumlu Vanaları Göster (%100 - %200 Kapasite)":
    filtered_matrix_df = matrix_df[(matrix_df['coverage_pct'] >= 100.0) & (matrix_df['coverage_pct'] <= 200.0)]
else:
    filtered_matrix_df = matrix_df[(matrix_df['coverage_pct'] >= 90.0) & (matrix_df['coverage_pct'] <= 200.0)]

# Fallback for extreme cases (very low or very high flow)
if filtered_matrix_df.empty and not matrix_df.empty:
    if matrix_df['coverage_pct'].min() > 200.0:
        st.info("ℹ️ Girilen tahliye debisi çok düşük olduğundan tüm vana modelleri %200 kapasite sınırının üzerindedir. En küçük mevcut modeller referans olarak listelenmiştir:")
        filtered_matrix_df = matrix_df.head(3)
    elif matrix_df['coverage_pct'].max() < 90.0:
        st.warning("⚠️ Girilen tahliye debisi çok yüksek olduğundan mevcut vanalar tek başına %90 kapasiteye ulaşamamaktadır. Lütfen vana adedini (N_working) artırınız:")
        filtered_matrix_df = matrix_df.tail(3)

# Always highlight the smallest valve with coverage >= 100% (within <= 200% preferred)
_eligible = matrix_df[(matrix_df['coverage_pct'] >= 100.0) & (matrix_df['coverage_pct'] <= 200.0)].sort_values('orifice_area_mm2')
if not _eligible.empty:
    _best_size = _eligible.iloc[0]['size_name']
    _best_area = _eligible.iloc[0]['orifice_area_mm2']
    st.success(f"✅ En küçük uygun vana: **{_best_size}** ({_best_area:,.0f} mm², %{_eligible.iloc[0]['coverage_pct']:.1f} kapasite)")
else:
    _any_eligible = matrix_df[matrix_df['coverage_pct'] >= 100.0].sort_values('orifice_area_mm2')
    if not _any_eligible.empty:
        _best_size = _any_eligible.iloc[0]['size_name']
        _best_area = _any_eligible.iloc[0]['orifice_area_mm2']
        st.info(f"ℹ️ En küçük vana: **{_best_size}** ({_best_area:,.0f} mm², %{_any_eligible.iloc[0]['coverage_pct']:.1f} kapasite)")
    else:
        st.warning("⚠️ Kapasite ≥ %100 şartını sağlayan vana bulunamadı.")

matrix_df_display = filtered_matrix_df[['size_name', 'valve_category', 'orifice_area_mm2', 'discharge_coeff_kd', 'air_capacity_m3_h', 'coverage_pct', 'utilization_pct', 'status']].copy()
matrix_df_display['valve_category'] = matrix_df_display['valve_category'].map({'pilot': 'Pilot', 'spring': 'Yaylı'})
matrix_df_display.columns = ['Vana Anma Ölçüsü & Markası', 'Tip', 'Efektif Orifis Alanı (mm²)', 'Kd (katalog/sertifikalı)', 'Hava Tahliye Kapasitesi (m³/h)', 'Kapasite Karşılama Oranı (%)', 'Kapasite Kullanımı (%)', 'Teknik Değerlendirme']

st.dataframe(
    matrix_df_display.style.format({
        'Efektif Orifis Alanı (mm²)': '{:,.0f}',
        'Kd (katalog/sertifikalı)': '{:.3f}',
        'Hava Tahliye Kapasitesi (m³/h)': '{:,.0f}',
        'Kapasite Karşılama Oranı (%)': '%{:.1f}',
        'Kapasite Kullanımı (%)': '%{:.1f}'
    })
)

# Governing Scenario Valve Matrix (conditional fire display)
if governing_is_fire:
    st.subheader("🔥 Yangın Senaryosu — Hüküm Süren Vana Matrisi")
    st.caption(f"Yangın Tahliye Sıcaklığı: {T_fire_input:.1f} {T_fire_unit} | Q_fire = {fire_res['q_fire_kW']:,.1f} kW | W_fire = {fire_res['w_fire_kg_h']:,.1f} kg/h | Gerekli alan referansı Kd = 0.85 | Vana kapasiteleri katalog Kd ile")

    gov_df = pd.DataFrame(governing_matrix)
    gov_df = gov_df.sort_values(by='orifice_area_mm2', ascending=True)

    if filter_mode == "Yalnızca Uyumlu Vanaları Göster (%100 - %200 Kapasite)":
        filtered_gov_df = gov_df[(gov_df['coverage_pct'] >= 100.0) & (gov_df['coverage_pct'] <= 200.0)]
    else:
        filtered_gov_df = gov_df[(gov_df['coverage_pct'] >= 90.0) & (gov_df['coverage_pct'] <= 200.0)]

    if filtered_gov_df.empty and not gov_df.empty:
        if gov_df['coverage_pct'].min() > 200.0:
            filtered_gov_df = gov_df.head(3)
        elif gov_df['coverage_pct'].max() < 90.0:
            filtered_gov_df = gov_df.tail(3)

    gov_df_display = filtered_gov_df[['size_name', 'valve_category', 'orifice_area_mm2', 'discharge_coeff_kd', 'air_capacity_m3_h', 'coverage_pct', 'utilization_pct', 'status']].copy()
    gov_df_display['valve_category'] = gov_df_display['valve_category'].map({'pilot': 'Pilot', 'spring': 'Yaylı'})
    gov_df_display.columns = ['Vana Anma Ölçüsü & Markası', 'Tip', 'Efektif Orifis Alanı (mm²)', 'Kd (katalog/sertifikalı)', 'Hava Tahliye Kapasitesi (m³/h)', 'Kapasite Karşılama Oranı (%)', 'Kapasite Kullanımı (%)', 'Teknik Değerlendirme']

    st.dataframe(
        gov_df_display.style.format({
            'Efektif Orifis Alanı (mm²)': '{:,.0f}',
            'Kd (katalog/sertifikalı)': '{:.3f}',
            'Hava Tahliye Kapasitesi (m³/h)': '{:,.0f}',
            'Kapasite Karşılama Oranı (%)': '%{:.1f}',
            'Kapasite Kullanımı (%)': '%{:.1f}'
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
    if loads.get('flash_basis') == 'molar':
        _wf_formula = (
            f"W_flash = Q_fill × ρ_feed × β_molar × (M_vapor/M_feed) = "
            f"{Q_fill:,.0f} × {rho_feed:.1f} × {effective_flash_pct / 100.0:.4f} × "
            f"({M_vapor_flash:.2f}/{M_feed:.2f}) = **{loads['w_flash_kg_h']:,.1f} kg/h**"
        )
        _wf_note = "Molar V/F, kütle dengesinden kütle debisine dönüştürülmüştür."
    else:
        _wf_formula = (
            f"W_flash = Q_fill × ρ_feed × (Kütle %) = {Q_fill:,.0f} × {rho_feed:.1f} × "
            f"{effective_flash_pct / 100.0:.4f} = **{loads['w_flash_kg_h']:,.1f} kg/h**"
        )
        _wf_note = "Kullanıcı tarafından kütlesel oran olarak girilmiştir."
    st.markdown(f"""
    #### 📐 Toplam Tahliye Debisi Formülleri (W_total)
    - **Sıvı Yerdeğiştirme Debisi (W_disp)**:
      W_disp = Q_fill × ρ_v(P1) = {Q_fill:,.0f} m³/h × {rho_v_disp:.3f} kg/m³ = **{loads['w_disp_kg_h']:,.1f} kg/h**
      *ρ_v tank buharı bileşimi ve P1 relieving basıncında hesaplanmıştır.*
    - **Flaş BOG Debisi (W_flash)** ({'Molar baz' if loads.get('flash_basis') == 'molar' else 'Kütlesel baz'}):
      {_wf_formula}
      *{_wf_note} Besleme yoğunluğu ρ_feed = {rho_feed:.1f} kg/m³ (T_cargo koşulu, {'kargo' if cargo_comp_dict else 'tank'} kompozisyonu).*
    - **Isı Girişi Tank BOG Debisi (W_bog)**:
      {f"W_bog = V_n × ρ_LNG × (BOR / 2400) = {V_n:,.0f} × {rho_lng:.1f} × ({bor_pct_per_day:.2f} / 2400) = **{w_bog_kg_h:,.1f} kg/h**" if bog_auto_mode else f"W_bog = **{w_bog_kg_h:,.1f} kg/h** (Manuel Giriş)"}
    - **Toplam Kütlesel Operasyonel Tahliye Debisi (W_total)**:
      W_total = W_disp + W_flash + W_bog = **{loads['w_total_kg_h']:,.1f} kg/h** ({loads['w_total_kg_s'] * 1000.0:.2f} g/s)
    """)
    if isenthalpic_res is not None:
        y_n2_val = isenthalpic_res.get('y_vapor', {}).get('N2', 0.0) * 100.0 if isinstance(isenthalpic_res.get('y_vapor'), dict) else 0.0
        z_n2_val = (cargo_comp_dict if (cargo_diff and cargo_comp_dict) else comp_dict).get('N2', 0.0)
        n2_row = f"\n        | Azot Zenginleşmesi (Buhar / Sıvı) | **{y_n2_val / max(0.001, z_n2_val):.1f}x** (%{z_n2_val:.2f} → %{y_n2_val:.2f}) | mol/mol |" if z_n2_val > 0.01 else ""
        _bound_note = "Evet (tek faz sınırı)" if isenthalpic_res.get('search_bound_hit') else "Hayır"
        st.info(f"""
        #### 🔬 İzentalpik Flaş (PH-Flash) Detayı

        | Parametre | Değer | Birim |
        | :--- | :---: | :---: |
        | Kargo Giriş Sıcaklığı (T_cargo) | **{T_cargo_K:.2f}** ({T_cargo_K - 273.15:.2f} °C) | K |
        | Genleşme Flaş Sıcaklığı (T_flash) | **{isenthalpic_res['T_flash_K']:.2f}** ({isenthalpic_res['T_flash_K'] - 273.15:.2f} °C) | K |
        | Besleme Entalpisi (h_feed) | **{isenthalpic_res['h_feed_J_mol']:.1f}** | J/mol |
        | Buhar Oranı (VF / Flaş %) | **%{isenthalpic_res['flash_pct']:.3f}** | mol/mol |
        | İstenen EOS | {isenthalpic_res['eos_used']} | - |
        | Entalpi Modeli (gerçek) | {enthalpy_model} | - |
        | Arama Sınırına Dayandı | {_bound_note} | - |
        | Çözüm Yakınsadı | **{'Evet' if isenthalpic_res['converged'] else 'Hayır'}** | - |{n2_row}
        """)

with exp2:
    st.markdown(f"""
    #### 💨 NFPA 59A Madde 8.4.10.7.4.2 Eşdeğer Hava Debisi (Q_a)
    Q_a, proses gazı debisinin API 520 Part I ile aynı şartlarda gerektirdiği efektif orifis alanının,
    standart şartlardaki (15 °C, 1.01325 bar_a) hava kapasitesidir:
    `A_o,gas = (17.9 × W) / (F2 × Kd × √(P1 × ΔP)) × √(T × Z / M)`
    `Q_a = API 520 hava kapasitesi(A_o,gas, P1, P2)`

    | Parametre Tanımı | Sembol | Sayısal Değer | Birim |
    | :--- | :---: | :---: | :---: |
    | Toplam Kütlesel Tahliye Debisi | W_total | **{loads['w_total_kg_s']:.3f}** | kg/s |
    | Boyutlandırma Karışım Sıcaklığı | T_mix | **{t_mix_K:.2f}** | K |
    | Gaz Sıkıştırılabilirlik Faktörü ({sizing_eos_name}) | Z | **{Z_sizing:.4f}** | - |
    | Buhar Faz Mol Kütlesi (karışım) | M | **{M_sizing:.2f}** | g/mol |
    | **NFPA 59A Toplam Eşdeğer Hava Debisi** | **Q_a** | **{q_a_total:,.1f}** | **m³/h Hava** |
    | **Vana Başına Düşen Hava Debisi ({N_working} Çalışan)** | **Q_a,per_valve** | **{q_a_per_valve:,.1f}** | **m³/h Hava/Vana** |
    """)
    if cargo_vapor_blend_used:
        st.info(
            f"🧪 **Karma Buhar Özellikleri:** Taşma+BOG buharı (tank, M={M_vapor:.2f}) ile flaş buharı "
            f"(kargo, M={M_vapor_flash:.2f}) mol akışına göre karıştırılmış; Z, k ve M bu karışım kompozisyonu ile "
            f"(T={t_mix_K:.2f} K, P1={P1_kPa_a:.2f} kPa_a) yeniden hesaplanmıştır: "
            f"**M={M_sizing:.2f} g/mol, Z={Z_sizing:.4f}, k={k_sizing:.4f}**."
        )

with exp3:
    _r = subcrit['pressure_ratio']
    _rc = subcrit['r_c']
    if subcrit['is_subcritical']:
        _regime = f"Subcritical Akış (r = {_r:.4f} > r_c = {_rc:.4f})"
        _ao_formula = "A_o = (17.9 × W_valve) / (F2 × Kd × Kb × Kc × √(P1 × ΔP)) × √(T × Z / M)"
        _flow_row = f"| Subcritical Akış Katsayısı (F2) | F2 | **{subcrit['F2']:.4f}** | API 520 Subcritical terimi (**kullanıldı**) |"
    else:
        _regime = f"Kritik Akış (r = {_r:.4f} ≤ r_c = {_rc:.4f})"
        _ao_formula = "A_o = (W_valve / (C_crit × Kd × Kb × Kc × P1)) × √(T × Z / M)"
        _flow_row = f"| Kritik Akış Katsayısı | C_crit | **{subcrit['C_crit']:.5f}** | API 520 Critical terimi (**kullanıldı**; F2 = 1.0) |"
    st.markdown(f"""
    #### 🔥 API 520 Part I Gerekli Orifis Alanı Formülü (A_o)
    `{_ao_formula}`
    `F2 = √( [k/(k-1)] × r^(2/k) × [(1 - r^((k-1)/k)) / (1 - r)] ),  r = P2 / P1`

    | Parametre Tanımı | Sembol | Sayısal Değer | Birim / Not |
    | :--- | :---: | :---: | :--- |
    | Vana Başına Kütlesel Yük ({N_working} Vana) | W_valve | **{loads['w_total_kg_h']/N_working:,.1f}** | kg/h |
    | Relieving Absolüt Basınç (P1) | P1 | **{P1_kPa_a:.2f}** | kPa_a ({P1_mbar_a:.1f} mbar_a) |
    | Çıkış Sırt Basıncı (P2) | P2 | **{P2_kPa_a:.2f}** | kPa_a ({P_atm_min:.1f} mbar_a) |
    | Basınç Düşüşü (ΔP) | ΔP | **{P1_kPa_a - P2_kPa_a:.2f}** | kPa |
    | Basınç Oranı (r = P2/P1) | r | **{_r:.4f}** | {_regime} |
    {_flow_row}
    | Vana Tahliye Katsayısı | Kd | **0.85** | Gerekli alan için referans değer; vana kapasitesi modelin katalog Kd'si ile |
    | Sırt Basıncı Düzeltmesi | Kb | **1.0** | Doğrudan atmosfere tahliye / built-up backpressure ihmalı (varsayım) |
    | Rupture Disc Faktörü | Kc | **1.0** | Kombinasyon yok varsayımı |
    | **API 520 Gerekli Efektif Orifis Alanı** | **A_o** | **{subcrit['A_o_mm2']:,.1f}** | **mm² ({subcrit['A_o_in2']:.1f} in²)** |
    """)

with exp4:
    is_insulated = "Yalıtımlı Çift Cidarlı Tank" if insulation_factor_F <= 0.3 else "Yalıtımsız / Hasarlı Tank"
    fire_is_sub = "Subcritical" if fire_subcrit['is_subcritical'] else "Critical"
    _fire_flow = (f"F2={fire_subcrit['F2']:.4f}" if fire_subcrit['is_subcritical']
                  else f"C_crit={fire_subcrit['C_crit']:.5f}, F2=1.0")
    _gov_margin_txt = f"%{governing_margin_pct:.2f}" if governing_margin_pct is not None else "N/A"
    _gov_op_mark = "🏆 **Governing**" if not governing_is_fire else "Operasyonel"
    _gov_fire_mark = "🏆 **Governing**" if governing_is_fire else "Yangın"
    st.markdown(f"""
    #### 🧭 Governing Kararının Gerekçesi (A_o bazlı)
    | Senaryo | W (kg/h) | Q_a (m³/h) | Q_a Basıncı P1 (kPa_a) | Gerekli A_o (mm²/valf) |
    | :--- | ---: | ---: | ---: | ---: |
    | {_gov_fire_mark} — Yangın | {fire_res['w_fire_kg_h']:,.1f} | {fire_q_a_total:,.1f} | {P1_fire_kPa_a:.3f} (%{fire_overpressure_pct:.0f} OP) | {fire_subcrit['A_o_mm2']:,.1f} |
    | {_gov_op_mark} — Operasyonel | {loads['w_total_kg_h']:,.1f} | {q_a_total:,.1f} | {P1_kPa_a:.3f} (%{Overpressure_pct:.0f} OP) | {subcrit['A_o_mm2']:,.1f} |
    | **Fark (marj)** | | | | **{_gov_margin_txt}** |

    ⚠️ **Not:** Q_a değerleri her senaryonun **kendi relieving basıncında** hesaplanır (yangın %{fire_overpressure_pct:.0f}, operasyonel %{Overpressure_pct:.0f} overpressure). Bu nedenle Q_a'lar senaryolar arası doğrudan karşılaştırılamaz; governing kararı **gerekli A_o** (ortak referans Kd = 0.85) baz alınarak verilir. Aynı 1 mm² orifis, yangın basıncında daha fazla hava geçirir; bu yüzden daha küçük A_o daha büyük Q_a üretebilir.
    """)
    if governing_borderline and governing_margin_pct is not None:
        st.warning(
            f"⚠️ **Governing Sınırda:** İki senaryonun gerekli alanları arasındaki fark yalnızca **{_gov_margin_txt}** (eşik %5). "
            f"Seçilen vana, A_o bazlı seçim gereği **her iki senaryoyu da** karşılar; ancak girdilerdeki küçük değişiklikler "
            f"governing senaryoyu değiştirebilir — her iki senaryoyu da raporlayın."
        )

    st.markdown(f"""
    #### 🚒 Yangın Senaryosu (Fire Case) Tahliye Debisi & Hüküm Süren (Governing) Senaryo Analizi
    `Q_fire = C × F × (A_wetted ^ 0.82) (kW)`
    `C = {fire_res['fire_coefficient_c_si']:.1f}` (API 521 SI korelasyon katsayısı, birim kW/m^1.64 — ısı akısı **değildir**)
    `W_fire = (Q_fire × 3600) / L (kg/h)`

    | Parametre / Senaryo | Değer | Birim / Açıklama |
    | :--- | :---: | :--- |
    | Islatılmış Tank Yüzey Alanı (A_wetted) | **{wetted_area_m2:,.0f}** | m² |
    | Yalıtım / Çevre Faktörü (F) | **{insulation_factor_F:.2f}** | {is_insulated} (kaynağı proje/API 521 kılavuzu ile doğrulanmalı) |
    | LNG Buharlaşma Gizli Isısı (L) | **{latent_heat_kJ_kg:,.0f}** | kJ/kg (relieving koşulunda doğrulanmalı) |
    | Yangın Tahliye Sıcaklığı (T_fire) | **{T_fire_input:.1f} {T_fire_unit}** | Yangın senaryosu gaz sıcaklığı |
    | Yangın Relieving Basıncı (P1_fire) | **{P1_fire_kPa_a:.2f}** | kPa_a (%{fire_overpressure_pct:.0f} overpressure) |
    | Yangın Gaz Z Faktörü ({eos_code}) | **{fire_Z:.4f}** | - |
    | Yangın Dinamik k = Cp/Cv | **{fire_k:.3f}** | - |
    | Akış Rejimi | **{fire_is_sub}** | {_fire_flow} |
    | Yangın Vana Kd Politikası | **Katalog Kd** | Her vana kendi sertifikalı/katalog Kd değeriyle; gerekli alan referans Kd=0.85 |
    | **Yangın Durumu Isı Girişi (Q_fire)** | **{fire_res['q_fire_kW']:,.1f}** | **kW** |
    | **Yangın Senaryosu Tahliye Debisi (W_fire)** | **{fire_res['w_fire_kg_h']:,.1f}** | **kg/h** ({fire_q_a_total:,.1f} m³/h Hava) |
    | **Yangın Senaryosu Gerekli A_o (referans Kd=0.85)** | **{fire_subcrit['A_o_mm2']:,.1f}** | **mm²** ({fire_is_sub}) |
    | **Operasyonel Tahliye Debisi (W_operasyonel)** | **{loads['w_total_kg_h']:,.1f}** | **kg/h** ({q_a_total:,.1f} m³/h Hava) |
    | **Operasyonel Gerekli A_o (referans Kd=0.85)** | **{subcrit['A_o_mm2']:,.1f}** | **mm²** |
    | **🏆 HÜKÜM SÜREN (GOVERNING) SENARYO** | **{governing_scenario}** | **A_o = {governing_A_o_mm2:,.1f} mm²** (aynı Kd bazı) |
    """)

# Main Section 2: Commercial Manufacturer PSV Database Matching
st.header("2. Entegre PSV Üretici Vana Kataloğu Eşleştirmesi")
st.caption("Anderson Greenwood, Crosby, Consolidated, Leser, Farris, Fukui Seisakusho, Birkett, Herose, Parker Bestobell, Bopp & Reuther, Weir Sebim ve Mercer marka katalog modellerinin sorgu sonuçları:")
st.caption("⚠️ *Katalog orifis alanları ve Kd değerleri **temsilidir (indicative)**; nihai seçim ve sipariş öncesi üretici sertifikalı kapasite tablosu doğrulanmalıdır.*")

col_v_toggle, col_v_info = st.columns([3, 2])
with col_v_toggle:
    show_all_valves = st.checkbox(
        "🔍 Tüm Uygun Vanaları Göster (%90 - %200 Kapasite)",
        value=True, key='in_show_all_valves',
        help="İşaretlendiğinde kapasite oranı %90.0 ile %200.0 arasındaki modeller listelenir (aşırı büyük modeller filtrelenir). İşaret kaldırıldığında sadece %100 - %200 arası modeller gösterilir."
    )
with col_v_info:
    st.info("💡 %90 - %100 aralığı sınırda modellerdir. %200'den büyük aşırı boyutlandırılmış modeller (oversized / chattering riski) filtrelenmiştir.")

if show_all_valves:
    filtered_valves = [v for v in matched_valves if 90.0 <= v['coverage_pct'] <= 200.0]
else:
    filtered_valves = [v for v in matched_valves if 100.0 <= v['coverage_pct'] <= 200.0]

if not filtered_valves and matched_valves:
    if all(v['coverage_pct'] > 200.0 for v in matched_valves):
        st.info("ℹ️ Girilen tahliye debisi çok düşük olduğundan tüm modeller %200 üzerindedir. En küçük modeller listelenmiştir:")
        filtered_valves = sorted(matched_valves, key=lambda x: x['coverage_pct'])[:3]
    elif all(v['coverage_pct'] < 90.0 for v in matched_valves):
        st.warning("⚠️ Yüksek debi nedeniyle hiçbir model %90 kapasiteye ulaşamamaktadır. Vana adedini (N) artırınız.")
        filtered_valves = sorted(matched_valves, key=lambda x: -x['coverage_pct'])[:3]

matched_df = pd.DataFrame(filtered_valves)
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
    st.warning("Seçilen filtre kriterlerini karşılayan vana bulunamadı.")


# Interactive Plotly Charts
st.header("3. Termodinamik & Hidrolik Grafiksel Analiz")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Atmosferik Basınç - Gerekli Orifis Alanı Grafiği")
    _p_lo = max(100.0, min(P_atm_min, P_atm_max) - 50.0)
    _p_hi = max(P_atm_min, P_atm_max) + 50.0
    p_range = np.linspace(_p_lo, _p_hi, 25)
    area_list = []

    for p in p_range:
        p1_kpa = (P_set + (P_set * Overpressure_pct / 100.0) + p) / 10.0
        p2_kpa = p / 10.0
        res_sub = calculate_api520_subcritical_orifice_area(
            w_valve_kg_h=loads['w_total_kg_h'] / N_working,
            P1_kPa_a=p1_kpa,
            P2_kPa_a=p2_kpa,
            temperature_k=t_mix_K,
            M_g_mol=M_sizing,
            Z=Z_sizing,
            k=k_sizing
        )
        area_list.append(res_sub['A_o_mm2'])

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=p_range, y=area_list, mode='lines+markers', name='Gerekli Orifis Alanı (mm²)', line=dict(color='#fb7185', width=3)))
    fig1.add_vline(x=P_atm_min, line_dash="dash", line_color="#38bdf8", annotation_text=f"Min Patm ({P_atm_min:.2f} mbar_a)")
    fig1.add_vline(x=P_atm_max, line_dash="dot", line_color="#94a3b8", annotation_text=f"Max Patm ({P_atm_max:.2f} mbar_a)")
    fig1.update_layout(
        template="plotly_dark",
        xaxis_title="Atmosferik Basınç (mbar_a)",
        yaxis_title="Gerekli Orifis Alanı (mm²)",
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig1)

with chart_col2:
    st.subheader("Dolum Debisi - Vana Kapasite Karşılama Oranı")
    _q_lo = max(1.0, Q_fill * 0.4)
    _q_hi = max(_q_lo * 1.1, Q_fill * 1.8)
    q_range = np.linspace(_q_lo, _q_hi, 25)

    # Pick up to 3 relevant valves from the governing matrix (closest to 100% coverage)
    _gov_sorted = sorted(governing_matrix, key=lambda m: abs(m['coverage_pct'] - 120.0))
    _chart_valves = _gov_sorted[:3]
    _chart_p1 = P1_fire_kPa_a if governing_is_fire else P1_kPa_a

    _chart_flash_mass_pct = (effective_flash_pct * (M_vapor_flash / M_feed)
                             if loads.get('flash_basis') == 'molar' else effective_flash_pct)

    _chart_traces = []
    for _v in _chart_valves:
        _cap = calculate_valve_capacity(_v['orifice_area_mm2'], _chart_p1, P2_kPa_a, K_d=_v.get('discharge_coeff_kd', 0.85))
        _covs = []
        for q in q_range:
            ld = calculate_relieving_loads(q_fill_m3_h=q, rho_lng_kg_m3=rho_feed, rho_v_kg_m3=rho_v_disp,
                                           flash_pct=_chart_flash_mass_pct, w_bog_kg_h=w_bog_kg_h, flash_basis='mass')
            qa = calculate_nfpa59a_air_equivalent(ld['w_total_kg_s'], temperature_k=t_mix_K, Z=Z_sizing, M_g_mol=M_sizing, k=k_sizing, K_d=0.85, P1_kPa_a=_chart_p1, P2_kPa_a=P2_kPa_a) / N_working
            _covs.append((_cap / max(1.0, qa)) * 100.0)
        _label = f"{_v['size_name'].split(' (')[0]} ({_v['orifice_area_mm2']:.0f}mm²)"
        _chart_traces.append(go.Scatter(x=q_range, y=_covs, mode='lines', name=_label, line=dict(width=2)))

    fig2 = go.Figure()
    for _t in _chart_traces:
        fig2.add_trace(_t)
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

# Find smallest adequate valve and next candidates from the GOVERNING scenario matrix
if not governing_matrix:
    st.error("❌ **Vana veritabanı yüklenemedi veya boş.** `psv_database.json` dosyasını kontrol edin.")
    st.stop()

_sorted_matrix = sorted(governing_matrix, key=lambda m: m['orifice_area_mm2'])
_best_valve = None
_second_valve = None
_adequate = False
# Prefer valves inside the recommended 100% - 200% capacity window
_in_window = [m for m in _sorted_matrix if 100.0 <= m['coverage_pct'] <= 200.0]
if _in_window:
    _best_valve = _in_window[0]
    _second_valve = _in_window[1] if len(_in_window) > 1 else None
    _adequate = True
else:
    _any_adequate = [m for m in _sorted_matrix if m['coverage_pct'] >= 100.0]
    if _any_adequate:
        _best_valve = _any_adequate[0]
        _adequate = True
    else:
        _best_valve = max(governing_matrix, key=lambda m: m['coverage_pct'])
        _adequate = False

_best_name = _best_valve['size_name']
_best_cov = _best_valve['coverage_pct']
_best_area = _best_valve['orifice_area_mm2']
_second_name = _second_valve['size_name'] if _second_valve else '-'
_second_cov = _second_valve['coverage_pct'] if _second_valve else 0.0

# Maximum allowable fill rate: solved from the OPERATIONAL mass balance with the
# smallest adequate operational valve. Never derived from a fire-governed matrix.
_op_sorted = sorted(matrix, key=lambda m: m['orifice_area_mm2'])
_op_window = [m for m in _op_sorted if 100.0 <= m['coverage_pct'] <= 200.0]
if _op_window:
    _op_best = _op_window[0]
elif [m for m in _op_sorted if m['coverage_pct'] >= 100.0]:
    _op_best = [m for m in _op_sorted if m['coverage_pct'] >= 100.0][0]
else:
    _op_best = max(matrix, key=lambda m: m['coverage_pct']) if matrix else None

_flash_mass_pct_for_solver = (effective_flash_pct * (M_vapor_flash / M_feed)
                              if loads.get('flash_basis') == 'molar' else effective_flash_pct)
_max_fill_q = None
if _op_best is not None:
    _max_fill_q = _solve_max_fill_m3_h(
        _op_best, n_working=N_working, p1_kpa=P1_kPa_a, p2_kpa=P2_kPa_a,
        t_mix_k=t_mix_K, z_sizing=Z_sizing, m_sizing=M_sizing, k_sizing=k_sizing,
        rho_feed=rho_feed, rho_v_disp=rho_v_disp, w_bog_kg_h=w_bog_kg_h,
        flash_mass_pct=_flash_mass_pct_for_solver, q_hi_hint=max(Q_fill, 1.0) * 8.0
    )
_best_util = (100.0 / _best_cov * 100.0) if _best_cov > 0.0 else float('inf')
_second_util = (100.0 / _second_cov * 100.0) if _second_cov > 0.0 else float('inf')

if _best_valve.get('valve_category') == 'spring' and valve_type_code == 'all':
    st.warning(
        "⚠️ **Tip Uyarısı:** Seçilen en küçük uygun vana **yaylı** tiptedir. Bu araç PORV (pilot kumandalı) "
        "odaklıdır; soldaki **Vana Tipi Filtresi → 'Yalnızca Pilot Kumandalı'** seçeneği ile aday havuzunu "
        "proje tip şartına göre daraltın. Tip ve geri basınç davranışı seçimi doğrudan etkiler."
    )
elif valve_type_code == 'pilot' and not _adequate:
    st.info(
        "ℹ️ Pilot-only filtrede %100-%200 penceresinde vana bulunamadı; adaylar mevcut en küçük pilot "
        "modellerden referans olarak gösterilmektedir. Vana adedini (N) veya katalog kapsamını gözden geçirin."
    )

col_rec1, col_rec2, col_rec3 = st.columns(3)

with col_rec1:
    if _adequate and _best_cov <= 200.0:
        st.success(f"""
        ### 🌟 Seçenek A (Tavsiye Edilen)
        **En Küçük Uygun Vana**:
        - **{_best_name}** (A_orifice = {_best_area:,.0f} mm²)
        - Kapasite Karşılama Oranı: **%{_best_cov:.1f}** (kapsama)
        - Gerçek Kapasite Kullanımı (talep/kapasite): **%{_best_util:.1f}**
        - {N_working}+{N_spare} konfigürasyonu için seçim; katalog verisi `indicative`, sertifikalı kapasite teyidi gerekir.
        """)
    elif _adequate:
        st.warning(f"""
        ### ⚠️ Seçenek A (Sınırlı Uygunluk)
        **%100-%200 Penceresinde Vana Yok**:
        - Mevcut katalogda %100-%200 aralığında vana bulunmamaktadır.
        - En yakın uygun vana: **{_best_name}** (A_orifice = {_best_area:,.0f} mm²)
        - Kapasite Karşılama Oranı: **%{_best_cov:.1f}** (kullanım **%{_best_util:.1f}**) → %200 üzeri (aşırı boyutlandırma riski).
        - Öneri: çalışan vana adedini (N) artırın veya ara çap modeli tedarikçiden talep edin.
        """)
    else:
        st.error(f"""
        ### ❌ Uygun Vana Bulunamadı
        - En yüksek kapasiteli vana: **{_best_name}** (%{_best_cov:.1f})
        - Vana konfigürasyonu veya dolum debisi gözden geçirilmelidir.
        """)

with col_rec2:
    if _adequate and _second_valve:
        n_extra = N_working + 1
        st.warning(f"""
        ### ⚠️ Seçenek B (Yedek Kapasite)
        **Daha Büyük Vana Alternatifi**:
        - **{_second_name}** (A_orifice = {_second_valve['orifice_area_mm2']:,.0f} mm²)
        - Kapasite Karşılama Oranı: **%{_second_cov:.1f}** (kullanım **%{_second_util:.1f}**)
        - Fazla emniyet marjı sağlar.
        """)
    elif _adequate:
        st.info("ℹ️ İkinci uygun vana alternatifi bulunmamaktadır.")
    else:
        st.warning(f"""
        ### ⚠️ Seçenek B (Konfigürasyon Revizyonu)
        **Vana Adedini Arttırma**:
        - Vana düzeni **{N_working + 1} Çalışan + {N_spare} Yedek** olarak güncellenmelidir.
        """)

with col_rec3:
    if _adequate and _max_fill_q is not None and _op_best is not None:
        _op_best_name = _op_best['size_name']
        _fire_note = (
            "\n        - ℹ️ *Hüküm süren senaryo yangın olduğundan bu limit **operasyonel kütle dengesinden** ayrıca çözülmüştür; "
            "yangın yükü dolum debisinden bağımsızdır.*" if governing_is_fire else ""
        )
        st.info(f"""
        ### 🛑 Seçenek C (Dolum Debisi Limiti)
        **Mevcut Vanayı Koruma**:
        - Operasyonel en küçük uygun vana: **{_op_best_name}**
        - Bu vana düzeni korunursa maksimum dolum debisi **{_max_fill_q:,.0f} m³/h** (P1'de hava kapasitesi kapsaması).{_fire_note}
        """)
    else:
        st.info("""
        ### 🛑 Seçenek C (Sistem Revizyonu)
        **Saha Koşullarını Değiştirme**:
        - Tank basıncı veya dolum debisi gözden geçirilmelidir.
        """)

# Printable Report Export Button
st.markdown("<hr>", unsafe_allow_html=True)

with st.expander("📝 Rapor Künyesi ve Dil Seçimi", expanded=False):
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.text_input("Proje / Tesis Adı", key='in_project_name')
        st.text_input("Revizyon No", key='in_project_revision')
    with col_p2:
        st.text_input("Hazırlayan", key='in_project_prepared_by')
        st.text_input("Kontrol Eden", key='in_project_checked_by')
    st.radio("Rapor Dili", ["Türkçe (TR)", "English (EN)"], horizontal=True, key='in_report_language')

report_inputs['project_name'] = st.session_state.get('in_project_name', '')
report_inputs['project_revision'] = st.session_state.get('in_project_revision', '')
report_inputs['project_prepared_by'] = st.session_state.get('in_project_prepared_by', '')
report_inputs['project_checked_by'] = st.session_state.get('in_project_checked_by', '')
report_inputs['max_fill_m3_h'] = _max_fill_q
report_inputs['best_compliance_pct'] = _best_cov
report_inputs['best_utilization_pct'] = _best_util
report_sizing['operational_best_valve'] = _op_best.get('size_name') if _op_best else None
_report_language = 'en' if st.session_state.get('in_report_language', 'Türkçe (TR)').startswith('English') else 'tr'

html_report_content = generate_html_report(
    inputs=report_inputs,
    thermo_results=report_thermo,
    sizing_results=report_sizing,
    matrix_results=governing_matrix,
    matched_valves=matched_valves,
    language=_report_language,
    app_version=CURRENT_VERSION
)

st.download_button(
    label="📄 Mühendislik Hesap Raporunu İndir (HTML / Yazdırılabilir)",
    data=html_report_content,
    file_name="LNG_PORV_Boyutlandirma_Raporu.html",
    mime="text/html"
)
