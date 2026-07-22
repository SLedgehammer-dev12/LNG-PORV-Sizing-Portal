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
    NFPA 59A Section 8.4.10.7.4.2 Equivalent Air Flow Rate (Q_a) in m3/h of Air at standard conditions (15°C, 1.01325 bar_a).
    Derivation of 990.8 factor:
    Q_a (SCFH) = 4.34e6 * W_lb_s / (C * Kd) * sqrt(T*Z/M)
    Converting SCFH air to m3/h metric standard air (1 SCFH = 0.026853 m3/h) yields multiplier 990.8.
    """
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
    Calculates required effective orifice area A_o (mm2) per API 520 Part I Subcritical gas flow (Eq 16).
    """
    r_c = (2.0 / (k + 1.0)) ** (k / (k - 1.0))
    pressure_ratio = P2_kPa_a / P1_kPa_a
    
    is_subcritical = pressure_ratio > r_c
    
    if is_subcritical:
        # Standard API 520 Part I Subcritical flow coefficient F2 with /(1 - r) term
        r = max(1e-4, min(0.9999, pressure_ratio))
        term1 = k / (k - 1.0)
        term2 = r ** (2.0 / k)
        term3 = (1.0 - (r ** ((k - 1.0) / k))) / (1.0 - r)
        
        F2 = math.sqrt(max(1e-6, term1 * term2 * term3))
        
        # Standard API 520 Part I SI Equation 16 (A_o in mm2, W in kg/h, P in kPa_a, T in K, M in g/mol)
        delta_p_kPa = max(0.1, P1_kPa_a - P2_kPa_a)
        A_o_mm2 = (17.9 * w_valve_kg_h / (F2 * K_d * K_b * K_c * math.sqrt(P1_kPa_a * delta_p_kPa))) * math.sqrt((temperature_k * Z) / M_g_mol)
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

def calculate_valve_capacity(orifice_area_mm2: float, P1_kPa_a: float, K_d: float = 0.85) -> float:
    """
    Calculates rated equivalent air capacity (m3/h) for a given effective orifice area (mm2),
    relieving pressure P1 (kPa_a), and discharge coefficient Kd per API 520 / NFPA 59A.
    """
    kd_ratio = K_d / 0.85
    return (orifice_area_mm2 / 148500.0) * 25380.0 * (P1_kPa_a / 117.003) * kd_ratio

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
    Evaluates commercial relief valve models dynamically from psv_database.json
    under specific atmospheric pressure conditions.
    """
    from psv_database import load_psv_database
    valves = load_psv_database()
    
    results = []
    for v in valves:
        area = v['orifice_area_mm2']
        kd_val = v.get('discharge_coeff_kd', 0.85)
        capacity_m3_h = calculate_valve_capacity(area, P1_kPa_a, K_d=kd_val)
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
            'size_name': f"{v['manufacturer']} {v['series']} ({v['dn_size']})",
            'orifice_area_mm2': area,
            'air_capacity_m3_h': capacity_m3_h,
            'coverage_pct': coverage_pct,
            'status': status,
            'status_code': status_code,
            'description': v.get('description', '')
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
