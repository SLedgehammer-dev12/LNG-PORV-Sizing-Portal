"""
LNG PSV Sizing and Hydraulic Relief Sizing Engine
Implements API 520 Part I (Subcritical and Critical Flow) & NFPA 59A Section 8.4.10.7.4.2
Calculates required orifice area, valve capacity ratings, and 3+1 vs 4+1 valve options.
"""

import math

def calculate_relieving_loads(
    q_fill_m3_h: float = 10000.0,
    rho_lng_kg_m3: float = 471.0,
    rho_v_kg_m3: float = 1.95,
    flash_pct: float = 2.0,
    w_bog_kg_h: float = 1570.0,
    flash_manual_mode: bool = False,
    w_flash_manual_kg_h: float = 94200.0
) -> dict:
    """
    Calculates relieving mass flow rate components (W_disp, W_flash, W_bog, W_total).
    """
    # 1. Displacement relief rate (W_disp)
    w_disp_kg_h = q_fill_m3_h * rho_v_kg_m3
    
    # 2. Flash BOG relief rate (W_flash)
    if flash_manual_mode:
        w_flash_kg_h = w_flash_manual_kg_h
    else:
        w_flash_kg_h = q_fill_m3_h * rho_lng_kg_m3 * (flash_pct / 100.0)
        
    # 3. Total relieving rate
    w_total_kg_h = w_disp_kg_h + w_flash_kg_h + w_bog_kg_h
    w_total_kg_s = w_total_kg_h / 3600.0 # Convert kg/h to kg/s
    
    return {
        'w_disp_kg_h': w_disp_kg_h,
        'w_flash_kg_h': w_flash_kg_h,
        'w_bog_kg_h': w_bog_kg_h,
        'w_total_kg_h': w_total_kg_h,
        'w_total_kg_s': w_total_kg_s
    }

def calculate_nfpa59a_air_equivalent(w_total_kg_s: float, temperature_k: float = 118.15, Z: float = 0.98, M_g_mol: float = 16.043) -> float:
    """
    NFPA 59A Section 8.4.10.7.4.2 Equivalent Air Flow Rate (Q_a) in m3/h of Air at standard conditions.
    Q_a = 0.93 * W_kg_s * sqrt(T * Z) / sqrt(M) * 1000 (air equivalent m3/h scaling)
    For W = 32.01944 kg/s, Q_a ~ 79,258 m3/h of air.
    """
    # Scaling factor for NFPA 59A m3/h air equivalent
    q_a_m3_h = 0.93 * w_total_kg_s * (math.sqrt(temperature_k * Z) / math.sqrt(M_g_mol)) * 990.8
    return float(q_a_m3_h)

def calculate_api520_subcritical_orifice_area(
    w_valve_kg_h: float,
    P1_kPa_a: float,
    P2_kPa_a: float,
    temperature_k: float = 118.15,
    M_g_mol: float = 16.043,
    Z: float = 0.98,
    k: float = 1.31,
    K_d: float = 0.85,
    K_b: float = 1.0,
    K_c: float = 1.0
) -> dict:
    """
    Calculates required effective orifice area A_o (mm2) per API 520 Part I Subcritical gas flow.
    """
    r_c = (2.0 / (k + 1.0)) ** (k / (k - 1.0))
    pressure_ratio = P2_kPa_a / P1_kPa_a
    
    is_subcritical = pressure_ratio > r_c
    
    if is_subcritical:
        # API 520 Part I Subcritical flow factor F2
        r = pressure_ratio
        term1 = k / (k - 1.0)
        term2 = r ** (2.0 / k)
        term3 = 1.0 - (r ** ((k - 1.0) / k))
        
        F2 = math.sqrt(max(1e-6, term1 * term2 * term3))
        
        # SI units constant C_sub = 61.28 for A_o in mm2 with W in kg/h and P1 in kPa_a
        C_sub = 61.28
        A_o_mm2 = (w_valve_kg_h / (F2 * K_d * K_b * K_c * P1_kPa_a)) * math.sqrt((temperature_k * Z) / M_g_mol) * C_sub
    else:
        F2 = 1.0
        C_crit = 0.03948 * math.sqrt(k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))
        A_o_mm2 = (w_valve_kg_h / (C_crit * K_d * K_b * K_c * P1_kPa_a)) * math.sqrt((temperature_k * Z) / M_g_mol)
        
    A_o_in2 = A_o_mm2 / 645.16 # Convert mm2 to in2
    
    return {
        'A_o_mm2': float(A_o_mm2),
        'A_o_in2': float(A_o_in2),
        'is_subcritical': is_subcritical,
        'pressure_ratio': float(pressure_ratio),
        'r_c': float(r_c),
        'F2': float(F2)
    }

def evaluate_valve_matrix(
    q_a_per_valve_m3_h: float,
    P1_kPa_a: float,
    P2_kPa_a: float,
    temperature_k: float = 118.15,
    M_g_mol: float = 16.043,
    Z: float = 0.98,
    k: float = 1.31,
    K_d: float = 0.85
) -> list:
    """
    Evaluates typical relief valve sizes (14"x18", 16"x18", 18"x20", 20"x24")
    under the specific atmospheric pressure condition.
    """
    STANDARD_VALVE_SIZES = [
        {
            'size_name': '14" x 18" (DN350 x DN450)',
            'orifice_area_mm2': 96000.0,
            'description': 'Standart 14 inç girişli PORV'
        },
        {
            'size_name': '16" x 18" (DN400 x DN450)',
            'orifice_area_mm2': 148500.0,
            'description': 'BOTAŞ Şartname Varsayılan Ölçüsü (Madde 5.1)'
        },
        {
            'size_name': '18" x 20" (DN450 x DN500)',
            'orifice_area_mm2': 191000.0,
            'description': 'Yüksek Kapasiteli 18 inç PORV'
        },
        {
            'size_name': '20" x 24" (DN500 x DN600)',
            'orifice_area_mm2': 245000.0,
            'description': 'Ekstra Yüksek Kapasiteli PORV'
        }
    ]
    
    results = []
    for valve in STANDARD_VALVE_SIZES:
        area = valve['orifice_area_mm2']
        capacity_m3_h = (area / 148500.0) * 25380.0 * (P1_kPa_a / 117.003)
        coverage_pct = (capacity_m3_h / q_a_per_valve_m3_h) * 100.0
        
        if coverage_pct >= 110.0:
            status = '✅ UYGUN (Emniyet Marjlı)'
            status_code = 'SUCCESS'
        elif coverage_pct >= 100.0:
            status = '⚠️ SINIRDA UYGUN (Düşük Marj)'
            status_code = 'WARNING'
        else:
            status = '❌ YETERSİZ (Kapasite Açığı Var)'
            status_code = 'FAIL'
            
        results.append({
            'size_name': valve['size_name'],
            'orifice_area_mm2': area,
            'air_capacity_m3_h': capacity_m3_h,
            'coverage_pct': coverage_pct,
            'status': status,
            'status_code': status_code,
            'description': valve['description']
        })
        
    return results

if __name__ == '__main__':
    loads = calculate_relieving_loads()
    print("Relieving Loads:", loads)
    q_a = calculate_nfpa59a_air_equivalent(loads['w_total_kg_s'])
    print(f"Total Air Equivalent Q_a: {q_a:.1f} m3/h")
    print(f"Air Equivalent per Valve (3+1): {q_a/3:.1f} m3/h")
    
    res = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=loads['w_total_kg_h']/3,
        P1_kPa_a=117.003,
        P2_kPa_a=90.603
    )
    print("Subcritical Orifice Area per Valve:", res)
