"""
Engineering Calculation Report Generator Module
Generates comprehensive printable HTML/PDF engineering reports for LNG PORV sizing.

All values are taken from the computation pipeline; no project-specific or
hard-coded valve recommendations are embedded. Turkish (tr) and English (en)
report languages are supported.
"""

import datetime

DEFAULT_PROJECT_NAME = {
    'tr': "LNG Depolama Tesisi - PORV Boyutlandırma",
    'en': "LNG Storage Facility - PORV Sizing",
}

TEXTS = {
    'tr': {
        'report_title': "PORV Emniyet Vanası Boyutlandırma ve Termodinamik Analiz Raporu",
        'revision': "Revizyon",
        'prepared_by': "Hazırlayan",
        'checked_by': "Kontrol Eden",
        'date': "Tarih",
        'sec1': "1. Tasarım ve Saha Parametreleri (Girdiler)",
        'param': "Parametre Adı", 'symbol': "Sembol", 'value': "Değer", 'unit': "Birim", 'desc': "Açıklama",
        'tank_volume': "Net Tank Kapasitesi", 'tank_volume_d': "LNG Depolama Net Hacmi",
        'fill_rate': "Maksimum Dolum Debisi", 'fill_rate_d': "Gemi LNG Yanaşma & Dolum Hızı",
        'patm_min': "Saha Min. Atmosferik Basınç", 'patm_min_d': "Kritik Boyutlandırma Bazı",
        'patm_max': "Saha Maks. Atmosferik Basınç", 'patm_max_d': "Tasarım Sınırı",
        'pset': "PORV Set Basıncı", 'pset_d': "Vana Açma Set Basıncı",
        'overpressure': "Aşırı Basınç Marjı (Overpressure)", 'overpressure_d': "API 520 / NFPA 59A İzin Verilen Marj",
        'p1': "Mutlak Tahliye Giriş Basıncı", 'p1_d': "P1 = P_set + Overpressure + P_atm_min",
        'config': "Vana Konfigürasyonu", 'config_d': "PORV Düzeni",
        'ttank': "Tank LNG Sıcaklığı", 'trelief': "Tahliye Buhar Sıcaklığı",
        'tcargo': "Kargo LNG Giriş Sıcaklığı", 'pship': "Gemi Pompa Çıkış Basıncı",
        'sec2': "2. Termodinamik ve Akışkan Hesaplama Sonuçları",
        'method': "Yöntem / Standart",
        'rho_lng': "COSTALD Sıvı LNG Yoğunluğu (ρ_LNG)", 'rho_lng_m': "Hankinson-Brobst-Thomson (COSTALD 1979)",
        'm_mix': "Sıvı Faz Mol Kütlesi (M_liquid)", 'm_mix_m': "Karışım Kompozisyon Hesabı (sıvı)",
        'm_vapor': "Buhar Faz Mol Kütlesi (M_vapor)", 'm_vapor_m': "VLE denge buharı (metanca zengin)",
        'rho_v': "Doygun Buhar Yoğunluğu (ρ_v)", 'rho_v_m': "Reel Gaz (EOS)",
        'z_factor': "Gaz Sıkıştırılabilirlik Faktörü (Z)", 'z_factor_m': "EOS VLE Flaş",
        'k_factor': "Dinamik İzantropik Üs (k = Cp/Cv)", 'k_factor_m': "EOS türevi + ideal Cp",
        'w_flash': "Flaş BOG Debisi (W_flash)", 'w_flash_m': "İzentalpik PH-Flaş / Manuel",
        'w_disp': "Yer Değiştirme Debisi (W_disp)", 'w_disp_m': "Q_fill × ρ_v",
        'w_bog': "Isı Girişi Tank BOG (W_bog)", 'w_bog_m': "BOR %/gün veya manuel",
        'w_total': "Toplam Operasyonel Tahliye Debisi (W_operasyonel)",
        'qa': "NFPA 59A Eşdeğer Hava Debisi (Q_a)", 'qa_m': "NFPA 59A Madde 8.4.10.7.4.2 (API 520 eşdeğer orifis)",
        'qa_valve': "Vana Başına Düşen Hava Debisi",
        'ao': "API 520 Gerekli Efektif Orifis Alanı (A_o)", 'ao_m': "API 520 Part I",
        'sec2b': "2.1. Mühendislik Formülleri ve Sayısal Değişken Detayları",
        'calc_step': "Hesaplama Adımı & Standart", 'formula': "Kullanılan Formül", 'formula_vars': "Formüldeki Sayısal Değişken Değerleri",
        'sec3': "3. Hüküm Süren (Governing) Vana Matrisi",
        'valve_size': "Vana Anma Ölçüsü & Markası", 'ao_area': "Efektif Orifis Alanı (mm²)",
        'air_cap': "Hava Kapasitesi (m³/h)", 'coverage': "Kapasite Oranı", 'assessment': "Teknik Değerlendirme",
        'sec4': "4. Uygun Üretici Vana Marka & Model Kataloğu",
        'manufacturer': "Üretici Marka", 'series': "Model Serisi", 'valve_type': "Vana Tipi",
        'dn_size': "Anma Çapı", 'orifice': "Orifis Alanı", 'status': "Öneri Durumu",
        'sec5': "5. Mühendislik Sonuç ve Tavsiye Raporu",
        'governing': "Hüküm Süren Senaryo",
        'rec_a': "Seçenek A (Tavsiye Edilen)", 'rec_b': "Seçenek B (Alternatif)", 'rec_c': "Seçenek C (Dolum Debisi Limiti)",
        'smallest': "En küçük uygun vana", 'capacity_use': "Kapasite kullanımı",
        'alt_valve': "Bir üst boy alternatif vana", 'safety_margin': "İlave emniyet marjı sağlar.",
        'max_fill': "Seçilen vana düzeni korunursa maksimum dolum debisi",
        'oversized_note': "Uyarı: Bu vana %200 üzeri kapasiteye sahiptir (aşırı boyutlandırma / chattering riski). Çalışan vana adedinin artırılması veya ara çap model değerlendirilmelidir.",
        'no_valve': "Kapasite ≥ %100 şartını sağlayan vana bulunamadı; vana adedi veya sistem koşulları revize edilmelidir.",
        'footer': "NFPA 59A, API 520 Part I/II, API 625, API 620 App. Q ve ASME Sec. VIII Div. 1 referans alınarak hesaplanmıştır.",
        'disclaimer': "Bu rapor, girilen veriler ve seçilen modeller esas alınarak otomatik üretilmiştir. Nihai tasarım, yetkili mühendis onayı gerektirir.",
        'air_std': "Hava standart şartları: 15 °C, 1.01325 bar_a",
        'fire_sec': "Yangın Senaryosu (Fire Case)",
        'fire_q': "Yangın Durumu Isı Girişi (Q_fire)",
        'fire_w': "Yangın Senaryosu Tahliye Debisi (W_fire)",
        'fire_ao': "Yangın Senaryosu Gerekli A_o (Kd = 1.0)",
        'fire_p1': "Yangın Relieving Basıncı (P1_fire)",
        'ph_flash': "İzentalpik Flaş (PH-Flash) Sonuçları",
        'ph_tflash': "Genleşme Flaş Sıcaklığı (T_flash)",
        'ph_vf': "Buhar Oranı (VF)",
        'ph_hfeed': "Besleme Entalpisi (h_feed)",
        'yes': "Evet", 'no': "Hayır",
        'converged': "Yakınsadı",
    },
    'en': {
        'report_title': "PORV Relief Valve Sizing and Thermodynamic Analysis Report",
        'revision': "Revision",
        'prepared_by': "Prepared by",
        'checked_by': "Checked by",
        'date': "Date",
        'sec1': "1. Design and Site Parameters (Inputs)",
        'param': "Parameter", 'symbol': "Symbol", 'value': "Value", 'unit': "Unit", 'desc': "Description",
        'tank_volume': "Net Tank Capacity", 'tank_volume_d': "LNG Net Storage Volume",
        'fill_rate': "Maximum Filling Rate", 'fill_rate_d': "Ship LNG Loading Rate",
        'patm_min': "Site Min. Atmospheric Pressure", 'patm_min_d': "Critical Sizing Basis",
        'patm_max': "Site Max. Atmospheric Pressure", 'patm_max_d': "Design Limit",
        'pset': "PORV Set Pressure", 'pset_d': "Valve Opening Set Pressure",
        'overpressure': "Allowed Overpressure", 'overpressure_d': "API 520 / NFPA 59A Allowed Margin",
        'p1': "Absolute Relieving Inlet Pressure", 'p1_d': "P1 = P_set + Overpressure + P_atm_min",
        'config': "Valve Configuration", 'config_d': "PORV Arrangement",
        'ttank': "Tank LNG Temperature", 'trelief': "Relieving Vapor Temperature",
        'tcargo': "Cargo LNG Inlet Temperature", 'pship': "Ship Pump Discharge Pressure",
        'sec2': "2. Thermodynamic and Fluid Calculation Results",
        'method': "Method / Standard",
        'rho_lng': "COSTALD Liquid LNG Density (ρ_LNG)", 'rho_lng_m': "Hankinson-Brobst-Thomson (COSTALD 1979)",
        'm_mix': "Liquid-Phase Molar Mass (M_liquid)", 'm_mix_m': "Mixture Composition Calculation (liquid)",
        'm_vapor': "Vapor-Phase Molar Mass (M_vapor)", 'm_vapor_m': "VLE equilibrium vapor (methane-enriched)",
        'rho_v': "Saturated Vapor Density (ρ_v)", 'rho_v_m': "Real Gas (EOS)",
        'z_factor': "Compressibility Factor (Z)", 'z_factor_m': "EOS VLE Flash",
        'k_factor': "Dynamic Isentropic Exponent (k = Cp/Cv)", 'k_factor_m': "EOS derivative + ideal Cp",
        'w_flash': "Flash BOG Rate (W_flash)", 'w_flash_m': "Isenthalpic PH-Flash / Manual",
        'w_disp': "Displacement Rate (W_disp)", 'w_disp_m': "Q_fill × ρ_v",
        'w_bog': "Heat Ingress Tank BOG (W_bog)", 'w_bog_m': "BOR %/day or manual",
        'w_total': "Total Operational Relief Rate (W_operational)",
        'qa': "NFPA 59A Equivalent Air Flow (Q_a)", 'qa_m': "NFPA 59A 8.4.10.7.4.2 (API 520 equivalent orifice)",
        'qa_valve': "Air Flow per Valve",
        'ao': "API 520 Required Effective Orifice Area (A_o)", 'ao_m': "API 520 Part I",
        'sec2b': "2.1. Engineering Formulas and Numerical Variable Details",
        'calc_step': "Calculation Step & Standard", 'formula': "Formula Used", 'formula_vars': "Numerical Variable Values",
        'sec3': "3. Governing Valve Matrix",
        'valve_size': "Valve Size & Manufacturer", 'ao_area': "Effective Orifice Area (mm²)",
        'air_cap': "Air Capacity (m³/h)", 'coverage': "Capacity Ratio", 'assessment': "Assessment",
        'sec4': "4. Suitable Manufacturer Valve Catalog",
        'manufacturer': "Manufacturer", 'series': "Model Series", 'valve_type': "Valve Type",
        'dn_size': "Nominal Size", 'orifice': "Orifice Area", 'status': "Recommendation Status",
        'sec5': "5. Engineering Conclusion and Recommendation",
        'governing': "Governing Scenario",
        'rec_a': "Option A (Recommended)", 'rec_b': "Option B (Alternative)", 'rec_c': "Option C (Filling Rate Limit)",
        'smallest': "Smallest adequate valve", 'capacity_use': "Capacity utilization",
        'alt_valve': "Next-size alternative valve", 'safety_margin': "Provides additional safety margin.",
        'max_fill': "If the selected valve arrangement is kept, maximum filling rate",
        'oversized_note': "Warning: This valve exceeds 200% capacity (oversizing / chattering risk). Consider increasing the number of working valves or evaluating an intermediate size.",
        'no_valve': "No valve with capacity ≥ 100% was found; valve count or system conditions must be revised.",
        'footer': "Calculated with reference to NFPA 59A, API 520 Part I/II, API 625, API 620 App. Q and ASME Sec. VIII Div. 1.",
        'disclaimer': "This report was generated automatically from the entered data and selected models. Final design requires approval by a qualified engineer.",
        'air_std': "Air standard conditions: 15 °C, 1.01325 bar_a",
        'fire_sec': "Fire Case",
        'fire_q': "Fire Heat Input (Q_fire)",
        'fire_w': "Fire Case Relief Rate (W_fire)",
        'fire_ao': "Fire Case Required A_o (Kd = 1.0)",
        'fire_p1': "Fire Relieving Pressure (P1_fire)",
        'ph_flash': "Isenthalpic Flash (PH-Flash) Results",
        'ph_tflash': "Expansion Flash Temperature (T_flash)",
        'ph_vf': "Vapor Fraction (VF)",
        'ph_hfeed': "Feed Enthalpy (h_feed)",
        'yes': "Yes", 'no': "No",
        'converged': "Converged",
    },
}

CSS = """
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; color: #1e293b; background-color: #f8fafc; font-size: 13px; }
        .header { border-bottom: 3px solid #0284c7; padding-bottom: 12px; margin-bottom: 20px; }
        .header h1 { color: #0f172a; font-size: 20px; margin: 0 0 5px 0; }
        .header p { color: #64748b; margin: 0; font-size: 12px; }
        .meta { color: #475569; font-size: 12px; margin-top: 6px; }
        .card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); page-break-inside: avoid; }
        h2 { color: #0369a1; font-size: 15px; border-bottom: 1px solid #cbd5e1; padding-bottom: 5px; margin-top: 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
        th { background-color: #f1f5f9; color: #334155; font-weight: 600; }
        tr:nth-child(even) { background-color: #f8fafc; }
        .badge-success { background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 4px; font-weight: bold; }
        .badge-warning { background-color: #fef9c3; color: #854d0e; padding: 3px 8px; border-radius: 4px; font-weight: bold; }
        .badge-danger { background-color: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 4px; font-weight: bold; }
        .footer { text-align: center; font-size: 11px; color: #94a3b8; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; }
        @media print {
            body { background: #ffffff; margin: 10mm; font-size: 11px; }
            .card { box-shadow: none; page-break-inside: avoid; }
            h2 { page-break-after: avoid; }
            .no-print { display: none; }
        }
"""


def _badge_class_matrix(status_code: str) -> str:
    if status_code == 'FAIL':
        return "badge-danger"
    if 'WARNING' in status_code or status_code == 'OVERSIZED':
        return "badge-warning"
    return "badge-success"


def _badge_class_valve(status: str) -> str:
    if "TAM UYGUN" in status or "FULLY" in status.upper():
        return "badge-success"
    if "UGUN" in status or "YAKIN" in status or "SUITABLE" in status.upper() or "BORDERLINE" in status.upper():
        return "badge-warning"
    return "badge-danger"


def _select_recommendation(matrix_results: list) -> dict:
    """Selects the smallest adequate valve and the next-size alternative from the matrix."""
    if not matrix_results:
        return {'adequate': False, 'best': None, 'second': None}
    ordered = sorted(matrix_results, key=lambda m: m['orifice_area_mm2'])
    in_window = [m for m in ordered if 100.0 <= m['coverage_pct'] <= 200.0]
    if in_window:
        return {'adequate': True, 'best': in_window[0], 'second': in_window[1] if len(in_window) > 1 else None}
    adequate = [m for m in ordered if m['coverage_pct'] >= 100.0]
    if adequate:
        return {'adequate': True, 'best': adequate[0], 'second': None}
    return {'adequate': False, 'best': max(ordered, key=lambda m: m['coverage_pct']), 'second': None}


def generate_html_report(
    inputs: dict,
    thermo_results: dict,
    sizing_results: dict,
    matrix_results: list,
    matched_valves: list,
    language: str = 'tr',
    app_version: str = "1.4.1"
) -> str:
    """Generates a clean, professional HTML engineering calculation report."""
    lang = 'en' if str(language).lower().startswith('en') else 'tr'
    T = TEXTS[lang]
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    project_name = inputs.get('project_name') or DEFAULT_PROJECT_NAME[lang]
    revision = inputs.get('project_revision') or "-"
    prepared_by = inputs.get('project_prepared_by') or "-"
    checked_by = inputs.get('project_checked_by') or "-"

    n_work = int(inputs.get('N_working', 3))
    n_spare = int(inputs.get('N_spare', 1))
    api_details = sizing_results.get('api_details', {}) or {}
    fire_details = sizing_results.get('fire_details', {}) or {}
    fire_subcrit = sizing_results.get('fire_subcrit', {}) or {}
    governing_scenario = sizing_results.get('governing_scenario', '-')
    ph_flash = sizing_results.get('isenthalpic_res') or {}

    rec = _select_recommendation(matrix_results)

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <title>{T['report_title']}</title>
    <style>{CSS}</style>
</head>
<body>

<div class="header">
    <h1>{project_name}</h1>
    <p>{T['report_title']}</p>
    <div class="meta">
        {T['date']}: {now_str} | {T['revision']}: {revision} | {T['prepared_by']}: {prepared_by} | {T['checked_by']}: {checked_by} | EOS: {inputs.get('eos_choice', '-')}
    </div>
</div>

<div class="card">
    <h2>{T['sec1']}</h2>
    <table>
        <tr><th>{T['param']}</th><th>{T['symbol']}</th><th>{T['value']}</th><th>{T['unit']}</th><th>{T['desc']}</th></tr>
        <tr><td>{T['tank_volume']}</td><td>V_n</td><td>{inputs.get('V_n', 0):,.0f}</td><td>m³</td><td>{T['tank_volume_d']}</td></tr>
        <tr><td>{T['fill_rate']}</td><td>Q_fill</td><td>{inputs.get('Q_fill', 0):,.0f}</td><td>m³/h</td><td>{T['fill_rate_d']}</td></tr>
        <tr><td>{T['patm_min']}</td><td>P_atm_min</td><td>{inputs.get('P_atm_min', 0):.2f}</td><td>mbar_a</td><td>{T['patm_min_d']}</td></tr>
        <tr><td>{T['patm_max']}</td><td>P_atm_max</td><td>{inputs.get('P_atm_max', 0):.3f}</td><td>mbar_a</td><td>{T['patm_max_d']}</td></tr>
        <tr><td>{T['pset']}</td><td>P_set</td><td>{inputs.get('P_set', 0):.1f}</td><td>mbar_g</td><td>{T['pset_d']}</td></tr>
        <tr><td>{T['overpressure']}</td><td>-</td><td>%{inputs.get('Overpressure_pct', 0):.1f}</td><td>-</td><td>{T['overpressure_d']}</td></tr>
        <tr><td>{T['p1']}</td><td>P1</td><td>{sizing_results.get('P1_kPa_a', 0):.3f}</td><td>kPa_a</td><td>{T['p1_d']}</td></tr>
        <tr><td>{T['config']}</td><td>-</td><td>{n_work} + {n_spare}</td><td>-</td><td>{T['config_d']}</td></tr>
        <tr><td>{T['ttank']}</td><td>T_tank</td><td>{inputs.get('T_tank_K', 0):.2f}</td><td>K</td><td>COSTALD</td></tr>
        <tr><td>{T['trelief']}</td><td>T_relief</td><td>{inputs.get('T_relief_K', 0):.2f}</td><td>K</td><td>API 520</td></tr>
        <tr><td>{T['tcargo']}</td><td>T_cargo</td><td>{inputs.get('T_cargo_K', 0):.2f}</td><td>K</td><td>PH-Flash</td></tr>
        <tr><td>{T['pship']}</td><td>P_ship</td><td>{inputs.get('P_ship_kPa_a', 0):.2f}</td><td>kPa_a</td><td>PH-Flash</td></tr>
    </table>
</div>

<div class="card">
    <h2>{T['sec2']}</h2>
    <table>
        <tr><th>{T['param']}</th><th>{T['value']}</th><th>{T['unit']}</th><th>{T['method']}</th></tr>
        <tr><td>{T['rho_lng']}</td><td><strong>{thermo_results.get('density_kg_m3', 0):.2f}</strong></td><td>kg/m³</td><td>{T['rho_lng_m']}</td></tr>
        <tr><td>{T['m_mix']}</td><td>{thermo_results.get('molar_mass_g_mol', 0):.2f}</td><td>g/mol</td><td>{T['m_mix_m']}</td></tr>
        <tr><td>{T['m_vapor']}</td><td>{thermo_results.get('M_vapor', 0):.2f}</td><td>g/mol</td><td>{T['m_vapor_m']}</td></tr>
        <tr><td>{T['rho_v']}</td><td>{thermo_results.get('vapor_density', 0):.3f}</td><td>kg/m³</td><td>{T['rho_v_m']}</td></tr>
        <tr><td>{T['z_factor']}</td><td>{thermo_results.get('Z_factor', 0):.4f}</td><td>-</td><td>{T['z_factor_m']}</td></tr>
        <tr><td>{T['k_factor']}</td><td>{thermo_results.get('k_factor', 0):.4f}</td><td>-</td><td>{T['k_factor_m']}</td></tr>
        <tr><td>{T['w_flash']}</td><td>{sizing_results.get('w_flash_kg_h', 0):,.1f}</td><td>kg/h</td><td>{T['w_flash_m']}</td></tr>
        <tr><td>{T['w_disp']}</td><td>{sizing_results.get('w_disp_kg_h', 0):,.1f}</td><td>kg/h</td><td>{T['w_disp_m']}</td></tr>
        <tr><td>{T['w_bog']}</td><td>{sizing_results.get('w_bog_kg_h', 0):,.1f}</td><td>kg/h</td><td>{T['w_bog_m']}</td></tr>
        <tr><td><strong>{T['w_total']}</strong></td><td><strong>{sizing_results.get('w_total_kg_h', 0):,.1f}</strong></td><td><strong>kg/h</strong></td><td>{sizing_results.get('w_total_g_s', 0):.3f} g/s</td></tr>
        <tr><td><strong>{T['qa']}</strong></td><td><strong>{sizing_results.get('q_a_total_m3_h', 0):,.1f}</strong></td><td><strong>m³/h air</strong></td><td>{T['qa_m']} ({T['air_std']})</td></tr>
        <tr><td>{T['qa_valve']} ({n_work})</td><td>{sizing_results.get('q_a_per_valve_m3_h', 0):,.1f}</td><td>m³/h air</td><td>Q_a / {n_work}</td></tr>
        <tr><td><strong>{T['ao']}</strong></td><td><strong>{sizing_results.get('A_o_mm2', 0):,.1f} mm² ({sizing_results.get('A_o_in2', 0):.1f} in²)</strong></td><td><strong>mm²/valve</strong></td><td>{T['ao_m']}</td></tr>
        <tr><td>{T['fire_p1']}</td><td>{inputs.get('P1_fire_kPa_a', sizing_results.get('P1_kPa_a', 0)):.2f}</td><td>kPa_a</td><td>%{inputs.get('fire_overpressure_pct', 21.0):.0f} OP</td></tr>
        <tr><td>{T['fire_q']}</td><td>{fire_details.get('q_fire_kW', 0):,.1f}</td><td>kW</td><td>{fire_details.get('q_constant_kW_per_m2', 70.9):.1f} kW/m² × F={inputs.get('insulation_factor_F', 0.15):.2f}</td></tr>
        <tr><td>{T['fire_w']}</td><td>{fire_details.get('w_fire_kg_h', 0):,.1f}</td><td>kg/h</td><td>{sizing_results.get('fire_q_a_total', 0):,.1f} m³/h air</td></tr>
        <tr><td><strong>{T['fire_ao']}</strong></td><td><strong>{fire_subcrit.get('A_o_mm2', 0):,.1f}</strong></td><td><strong>mm²/valve</strong></td><td>Kd={inputs.get('fire_K_d', 1.0):.2f} | F2={fire_subcrit.get('F2', 0):.4f}</td></tr>
        <tr><td><strong>{T['governing']}</strong></td><td colspan="3"><strong>{governing_scenario}</strong> (A_o = {sizing_results.get('governing_A_o_mm2', 0):,.1f} mm²)</td></tr>
    </table>
</div>

<div class="card">
    <h2>{T['sec2b']}</h2>
    <table>
        <thead><tr><th>{T['calc_step']}</th><th>{T['formula']}</th><th>{T['formula_vars']}</th></tr></thead>
        <tbody>
            <tr>
                <td><strong>{T['qa']}</strong></td>
                <td><code>Q_a = air capacity of A_o,gas at (P1, P2)</code></td>
                <td>W = {sizing_results.get('w_total_kg_s', 0):.3f} kg/s | T = {inputs.get('T_relief_K', 0):.2f} K | Z = {thermo_results.get('Z_sizing', thermo_results.get('Z_factor', 0)):.4f} | M = {thermo_results.get('M_sizing', thermo_results.get('M_vapor', 0)):.2f} g/mol</td>
            </tr>
            <tr>
                <td><strong>{T['ao']}</strong></td>
                <td><code>A = (17.9 × W) / (F2 × Kd × Kb × Kc × √(P1 × ΔP)) × √(T × Z / M)</code></td>
                <td>W = {sizing_results.get('w_valve_kg_h', 0):,.1f} kg/h | P1 = {api_details.get('P1_kPa_a', 0):.2f} kPa_a | P2 = {api_details.get('P2_kPa_a', 0):.2f} kPa_a | ΔP = {api_details.get('delta_p_kPa', 0):.2f} kPa | r = {api_details.get('pressure_ratio', 0):.4f} | F2 = {api_details.get('F2', 0):.4f} | Kd = {inputs.get('K_d', 0.85):.2f}</td>
            </tr>
            <tr>
                <td><strong>{T['fire_sec']}</strong></td>
                <td><code>Q_fire = C_q × F × A_wetted^0.82 (kW)<br>W_fire = Q_fire × 3600 / L (kg/h)</code></td>
                <td>A_wetted = {inputs.get('wetted_area_m2', 0):,.0f} m² | F = {inputs.get('insulation_factor_F', 0):.2f} | L = {inputs.get('latent_heat_kJ_kg', 0):,.0f} kJ/kg | T_fire = {inputs.get('T_fire_K', 0):.1f} K | Kd = {inputs.get('fire_K_d', 1.0):.2f}</td>
            </tr>
        </tbody>
    </table>
</div>
"""

    if ph_flash:
        html += f"""
<div class="card">
    <h2>{T['ph_flash']}</h2>
    <table>
        <tr><th>{T['param']}</th><th>{T['value']}</th><th>{T['unit']}</th></tr>
        <tr><td>{T['ph_tflash']}</td><td>{ph_flash.get('T_flash_K', 0):.2f}</td><td>K</td></tr>
        <tr><td>{T['ph_vf']}</td><td>%{ph_flash.get('flash_pct', 0):.3f}</td><td>mol/mol</td></tr>
        <tr><td>{T['ph_hfeed']}</td><td>{ph_flash.get('h_feed_J_mol', 0):.1f}</td><td>J/mol</td></tr>
        <tr><td>{T['converged']}</td><td>{T['yes'] if ph_flash.get('converged') else T['no']}</td><td>-</td></tr>
    </table>
</div>
"""

    html += f"""
<div class="card">
    <h2>{T['sec3']} — {governing_scenario}</h2>
    <table>
        <thead>
            <tr><th>{T['valve_size']}</th><th>{T['ao_area']}</th><th>{T['air_cap']}</th><th>{T['coverage']}</th><th>{T['assessment']}</th></tr>
        </thead>
        <tbody>
"""

    filtered_matrix_results = [m for m in matrix_results if 90.0 <= m['coverage_pct'] <= 200.0]
    if not filtered_matrix_results and matrix_results:
        filtered_matrix_results = sorted(matrix_results, key=lambda m: abs(m['coverage_pct'] - 100.0))[:5]

    for m in sorted(filtered_matrix_results, key=lambda x: x['orifice_area_mm2']):
        badge_class = _badge_class_matrix(m.get('status_code', ''))
        html += f"""
            <tr>
                <td><strong>{m['size_name']}</strong></td>
                <td>{m['orifice_area_mm2']:,.0f} mm²</td>
                <td>{m['air_capacity_m3_h']:,.0f} m³/h</td>
                <td>%{m['coverage_pct']:.1f}</td>
                <td><span class="{badge_class}">{m['status']}</span></td>
            </tr>
        """

    html += f"""
        </tbody>
    </table>
</div>

<div class="card">
    <h2>{T['sec4']}</h2>
    <table>
        <thead>
            <tr><th>{T['manufacturer']}</th><th>{T['series']}</th><th>{T['valve_type']}</th><th>{T['dn_size']}</th><th>{T['orifice']}</th><th>{T['coverage']}</th><th>{T['status']}</th></tr>
        </thead>
        <tbody>
"""

    filtered_matched_valves = [v for v in matched_valves if 90.0 <= v['coverage_pct'] <= 200.0]
    if not filtered_matched_valves and matched_valves:
        filtered_matched_valves = sorted(matched_valves, key=lambda v: abs(v['coverage_pct'] - 100.0))[:5]

    for v in sorted(filtered_matched_valves, key=lambda x: x['orifice_area_mm2']):
        badge_class = _badge_class_valve(v.get('status', ''))
        html += f"""
            <tr>
                <td><strong>{v['manufacturer']}</strong></td>
                <td>{v['series']}</td>
                <td>{v['type']}</td>
                <td>{v['dn_size']}</td>
                <td>{v['orifice_area_mm2']:,.0f} mm²</td>
                <td>%{v['coverage_pct']:.1f}</td>
                <td><span class="{badge_class}">{v['status']}</span></td>
            </tr>
        """

    html += f"""
        </tbody>
    </table>
</div>

<div class="card">
    <h2>{T['sec5']}</h2>
    <p><strong>{T['governing']}:</strong> {governing_scenario} (A_o = {sizing_results.get('governing_A_o_mm2', 0):,.1f} mm²)</p>
"""

    if rec['adequate']:
        best = rec['best']
        max_fill = inputs.get('Q_fill', 0.0) * (best['coverage_pct'] / 100.0)
        html += f"""
    <p><strong>{T['rec_a']}:</strong> {T['smallest']} → <strong>{best['size_name']}</strong>
       (A_o = {best['orifice_area_mm2']:,.0f} mm², {T['capacity_use']} %{best['coverage_pct']:.1f}) — {n_work}+{n_spare}.</p>
"""
        if best['coverage_pct'] > 200.0:
            html += f"""
    <p class="badge-warning">{T['oversized_note']}</p>
"""
        if rec['second']:
            second = rec['second']
            html += f"""
    <p><strong>{T['rec_b']}:</strong> {T['alt_valve']} → <strong>{second['size_name']}</strong>
       (A_o = {second['orifice_area_mm2']:,.0f} mm², {T['capacity_use']} %{second['coverage_pct']:.1f}). {T['safety_margin']}</p>
"""
        html += f"""
    <p><strong>{T['rec_c']}:</strong> {T['max_fill']} <strong>{max_fill:,.0f} m³/h</strong>.</p>
"""
    else:
        best = rec['best']
        if best:
            html += f"""
    <p class="badge-danger">{T['no_valve']}</p>
    <p>{T['rec_a']}: {best['size_name']} (%{best['coverage_pct']:.1f})</p>
"""
        else:
            html += f"""
    <p class="badge-danger">{T['no_valve']}</p>
"""

    html += f"""
</div>

<div class="footer">
    <p>{T['footer']} | LNG PORV Sizing Portal v{app_version}</p>
    <p>{T['disclaimer']}</p>
</div>

</body>
</html>
"""
    return html
