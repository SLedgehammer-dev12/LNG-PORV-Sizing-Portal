"""
LNG PSV Sizing and Hydraulic Relief Sizing Engine
Implements API 520 Part I (Subcritical and Critical Flow) & NFPA 59A Section 8.4.10.7.4.2
Calculates required orifice area and valve capacity ratings for the configured N+spare arrangement.

Valve capacities are computed from first principles with the API 520 Part I isentropic
gas flow equations (air at standard conditions), NOT from a calibrated reference point.
"""

import logging
import math

logger = logging.getLogger(__name__)

# Universal gas constant (J/mol/K)
R_GAS = 8.3144626

# Standard editions this tool is validated against. Keep in sync with the
# report footer and README; change only with engineering approval.
STANDARD_EDITIONS = {
    'NFPA 59A': '2023',
    'API 520 Part I': '10th Ed. (2020) + Errata 1 (2023)',
    'API 520 Part II': '7th Ed. (2020)',
    'API 521': '7th Ed. (2020)',
    'ASME BPVC Section VIII Div. 1': 'UG-131 capacity certification',
}

# Scope statement: this tool performs preliminary PORV load/capacity sizing.
SCOPE_STATEMENT = (
    "PORV ön boyutlandırma ve kapasite taraması. Kapsam dışı: API 520 Part II tesisat analizi, "
    "API 625 / API 620 App. Q full-containment tank tasarımı, tank basınç-vakum koruması."
)

# Air standard reference state used for all "equivalent air flow" / valve rating values.
# 15 degC, 1.01325 bar_a (metric standard air).
AIR_STD_T_K = 288.15
AIR_STD_P_KPA = 101.325
AIR_M_G_MOL = 28.97
AIR_Z = 1.0
AIR_K = 1.4
AIR_STD_RHO_KG_M3 = (AIR_STD_P_KPA * AIR_M_G_MOL) / (AIR_Z * R_GAS * AIR_STD_T_K)

# Critical pressure ratio helper values
_R_C_AIR = (2.0 / (AIR_K + 1.0)) ** (AIR_K / (AIR_K - 1.0))
_C_CRIT_AIR = 0.03948 * math.sqrt(AIR_K * (2.0 / (AIR_K + 1.0)) ** ((AIR_K + 1.0) / (AIR_K - 1.0)))
_SQRT_TZ_M_AIR = math.sqrt(AIR_STD_T_K * AIR_Z / AIR_M_G_MOL)


def calculate_relieving_loads(
    q_fill_m3_h: float = 10000.0,
    rho_lng_kg_m3: float = 471.0,
    rho_v_kg_m3: float = 1.95,
    flash_pct: float = 2.0,
    w_bog_kg_h: float = 1570.0,
    flash_manual_mode: bool = False,
    w_flash_manual_kg_h: float = 94200.0,
    flash_basis: str = 'molar',
    m_vapor_g_mol: float = None,
    m_feed_g_mol: float = None
) -> dict:
    """
    Calculates relieving mass flow rate components (W_disp, W_flash, W_bog, W_total).

    W_disp = Q_fill * rho_v, where rho_v is the displaced tank vapor density at the
    selected relieving state (the caller passes the P1-based density).

    W_flash uses the molar flash fraction beta from the isenthalpic (PH) flash and
    converts it to a mass flow with the phase molar masses:

        flash_basis='molar':  W_flash = Q_fill * rho_feed * beta * (M_vapor / M_feed)
        flash_basis='mass':   W_flash = Q_fill * rho_feed * (flash_pct / 100)

    'molar' is the physically consistent basis for PH-flash / VLE results and
    requires both molar masses. 'mass' is intended only for user-declared mass-%.
    """
    if q_fill_m3_h < 0.0:
        raise ValueError("Q_fill negatif olamaz.")
    if rho_lng_kg_m3 <= 0.0:
        raise ValueError("Besleme sıvı yoğunluğu pozitif olmalıdır.")
    if rho_v_kg_m3 <= 0.0:
        raise ValueError("Buhar yoğunluğu pozitif olmalıdır.")

    # 1. Displacement relief rate (W_disp)
    w_disp_kg_h = q_fill_m3_h * rho_v_kg_m3

    # 2. Flash BOG relief rate (W_flash)
    if flash_manual_mode:
        w_flash_kg_h = float(w_flash_manual_kg_h)
    elif str(flash_basis).lower() == 'mass':
        w_flash_kg_h = q_fill_m3_h * rho_lng_kg_m3 * (flash_pct / 100.0)
    else:
        if m_vapor_g_mol is None or m_feed_g_mol is None or m_feed_g_mol <= 0.0:
            raise ValueError(
                "Molar flaş bazı için m_vapor_g_mol ve m_feed_g_mol zorunludur "
                "(flash_basis='mass' kullanın veya molar kütleleri sağlayın)."
            )
        molar_fraction = flash_pct / 100.0
        mass_fraction = molar_fraction * (m_vapor_g_mol / m_feed_g_mol)
        w_flash_kg_h = q_fill_m3_h * rho_lng_kg_m3 * mass_fraction

    # 3. Total relieving rate
    w_total_kg_h = w_disp_kg_h + w_flash_kg_h + w_bog_kg_h
    w_total_kg_s = w_total_kg_h / 3600.0  # Convert kg/h to kg/s

    return {
        'w_flash_kg_h': w_flash_kg_h,
        'w_disp_kg_h': w_disp_kg_h,
        'w_bog_kg_h': w_bog_kg_h,
        'w_total_kg_h': w_total_kg_h,
        'w_total_kg_s': w_total_kg_s,
        'flash_basis': 'mass' if (flash_manual_mode or str(flash_basis).lower() == 'mass') else 'molar',
        'm_vapor_g_mol': m_vapor_g_mol,
        'm_feed_g_mol': m_feed_g_mol
    }


def calculate_f2_subcritical(k: float, r: float) -> float:
    """API 520 Part I subcritical flow factor F2 for pressure ratio r = P2 / P1.

    Invalid inputs raise instead of being silently clamped so that a non-physical
    design state cannot be converted into a plausible-looking number.
    """
    if not math.isfinite(k) or k <= 1.0:
        raise ValueError(f"k = Cp/Cv 1'den büyük ve sonlu olmalıdır (girilen: {k}).")
    if not math.isfinite(r) or not (0.0 < r < 1.0):
        raise ValueError(f"Basınç oranı r = P2/P1 0 < r < 1 aralığında olmalıdır (girilen: {r}).")
    term1 = k / (k - 1.0)
    term2 = r ** (2.0 / k)
    term3 = (1.0 - (r ** ((k - 1.0) / k))) / (1.0 - r)
    return math.sqrt(max(1e-9, term1 * term2 * term3))


def calculate_critical_pressure_ratio(k: float) -> float:
    """Critical pressure ratio r_c = (2/(k+1))^(k/(k-1))."""
    if not math.isfinite(k) or k <= 1.0:
        raise ValueError(f"k = Cp/Cv 1'den büyük ve sonlu olmalıdır (girilen: {k}).")
    return (2.0 / (k + 1.0)) ** (k / (k - 1.0))


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
    Calculates required effective orifice area A_o (mm2) per API 520 Part I
    gas/vapor flow (critical Eq. 13/14, subcritical Eq. 16).

    Rejects non-physical states (P2 >= P1, non-positive properties) instead of
    clamping them.
    """
    if not all(math.isfinite(v) for v in (w_valve_kg_h, P1_kPa_a, P2_kPa_a, temperature_k, M_g_mol, Z, k, K_d)):
        raise ValueError("Gerekli orifis alanı girdileri sonlu (finite) olmalıdır.")
    if w_valve_kg_h <= 0.0:
        raise ValueError("Debi pozitif olmalıdır.")
    if P1_kPa_a <= 0.0 or P2_kPa_a <= 0.0 or P2_kPa_a >= P1_kPa_a:
        raise ValueError(f"Geçersiz basınç durumu: 0 < P2 < P1 olmalıdır (P1={P1_kPa_a}, P2={P2_kPa_a}).")
    if temperature_k <= 0.0 or M_g_mol <= 0.0 or Z <= 0.0 or K_d <= 0.0:
        raise ValueError("T, M, Z ve Kd pozitif olmalıdır.")

    r_c = calculate_critical_pressure_ratio(k)
    pressure_ratio = P2_kPa_a / P1_kPa_a

    is_subcritical = pressure_ratio > r_c
    delta_p_kPa = P1_kPa_a - P2_kPa_a

    C_crit = 0.03948 * math.sqrt(k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))
    if is_subcritical:
        F2 = calculate_f2_subcritical(k, pressure_ratio)
        # API 520 Part I SI subcritical equation
        A_o_mm2 = (17.9 * w_valve_kg_h / (F2 * K_d * K_b * K_c * math.sqrt(P1_kPa_a * delta_p_kPa))) * math.sqrt((temperature_k * Z) / M_g_mol)
    else:
        F2 = 1.0
        A_o_mm2 = (w_valve_kg_h / (C_crit * K_d * K_b * K_c * P1_kPa_a)) * math.sqrt((temperature_k * Z) / M_g_mol)

    A_o_in2 = A_o_mm2 / 645.16  # Convert mm2 to in2

    return {
        'A_o_mm2': float(A_o_mm2),
        'A_o_in2': float(A_o_in2),
        'is_subcritical': is_subcritical,
        'pressure_ratio': float(pressure_ratio),
        'r_c': float(r_c),
        'F2': float(F2),
        'C_crit': float(C_crit),
        'P1_kPa_a': float(P1_kPa_a),
        'P2_kPa_a': float(P2_kPa_a),
        'delta_p_kPa': float(delta_p_kPa),
        'temperature_k': float(temperature_k),
        'M_g_mol': float(M_g_mol),
        'Z': float(Z),
        'k': float(k),
        'K_d': float(K_d),
        'K_b': float(K_b),
        'K_c': float(K_c),
        'w_valve_kg_h': float(w_valve_kg_h)
    }


def compute_governing_decision(a_op_mm2: float, a_fire_mm2: float, margin_warn_pct: float = 5.0) -> dict:
    """
    Selects the governing relief scenario from the required orifice areas.

    A_o is the only valid common basis across scenarios: each scenario's
    required area uses its own relieving pressure and gas state, whereas the
    equivalent air flow Q_a embeds the scenario pressure scale and therefore
    must not be compared across scenarios.

    Returns the governing scenario ('fire' | 'operational'), the relative
    margin between the two required areas and a 'borderline' flag when the
    scenarios are within margin_warn_pct of each other.
    """
    if not all(math.isfinite(v) for v in (a_op_mm2, a_fire_mm2)):
        raise ValueError("Governing karşılaştırması için A_o değerleri sonlu olmalıdır.")
    if a_op_mm2 <= 0.0 or a_fire_mm2 <= 0.0:
        raise ValueError("Governing karşılaştırması için A_o değerleri pozitif olmalıdır.")
    a_max = max(a_op_mm2, a_fire_mm2)
    margin_pct = abs(a_op_mm2 - a_fire_mm2) / a_max * 100.0
    return {
        'governing': 'fire' if a_fire_mm2 > a_op_mm2 else 'operational',
        'margin_pct': float(margin_pct),
        'borderline': bool(margin_pct < margin_warn_pct),
        'a_op_mm2': float(a_op_mm2),
        'a_fire_mm2': float(a_fire_mm2),
    }


def calculate_valve_air_capacity_m3_h(
    orifice_area_mm2: float,
    P1_kPa_a: float,
    P2_kPa_a: float = 0.0,
    K_d: float = 0.85,
    T_air_K: float = AIR_STD_T_K,
    M_air_g_mol: float = AIR_M_G_MOL,
    Z_air: float = AIR_Z,
    k_air: float = AIR_K
) -> float:
    """
    Rated equivalent air capacity (m3/h at standard conditions) of an orifice area
    under relieving pressures (P1, P2) per API 520 Part I.

    Critical flow (r <= r_c):      W = A * C * Kd * P1 / sqrt(T*Z/M)
    Subcritical flow (r > r_c):    W = A * F2 * Kd * sqrt(P1*dP) / (17.9 * sqrt(T*Z/M))

    P2 = 0 is allowed and means sonic (critical) discharge to vacuum. Non-physical
    states (P2 >= P1) raise instead of being silently clamped.
    """
    if not all(math.isfinite(v) for v in (orifice_area_mm2, P1_kPa_a, P2_kPa_a, K_d, T_air_K, M_air_g_mol, Z_air, k_air)):
        raise ValueError("Kapasite girdileri sonlu (finite) olmalıdır.")
    if orifice_area_mm2 <= 0.0 or K_d <= 0.0:
        raise ValueError("Orifis alanı ve Kd pozitif olmalıdır.")
    if P1_kPa_a <= 0.0 or P2_kPa_a < 0.0 or P2_kPa_a >= P1_kPa_a:
        raise ValueError(f"Geçersiz basınç durumu: 0 <= P2 < P1 olmalıdır (P1={P1_kPa_a}, P2={P2_kPa_a}).")
    P1 = P1_kPa_a
    P2 = P2_kPa_a
    r = P2 / P1
    r_c = calculate_critical_pressure_ratio(k_air)
    sqrt_tzm = math.sqrt(T_air_K * Z_air / M_air_g_mol)

    if r > r_c:
        F2 = calculate_f2_subcritical(k_air, r)
        delta_p = max(0.1, P1 - P2)
        w_air_kg_h = (orifice_area_mm2 * F2 * K_d * math.sqrt(P1 * delta_p)) / (17.9 * sqrt_tzm)
    else:
        C_crit = 0.03948 * math.sqrt(k_air * (2.0 / (k_air + 1.0)) ** ((k_air + 1.0) / (k_air - 1.0)))
        w_air_kg_h = (orifice_area_mm2 * C_crit * K_d * P1) / sqrt_tzm

    return float(w_air_kg_h / AIR_STD_RHO_KG_M3)


def calculate_valve_capacity(
    orifice_area_mm2: float,
    P1_kPa_a: float,
    P2_kPa_a: float = 0.0,
    K_d: float = 0.85
) -> float:
    """
    Rated equivalent air capacity (m3/h) of a commercial valve model per API 520 Part I.
    Thin wrapper around calculate_valve_air_capacity_m3_h for valve catalog use.
    """
    return calculate_valve_air_capacity_m3_h(orifice_area_mm2, P1_kPa_a, P2_kPa_a, K_d=K_d)


def calculate_nfpa59a_air_equivalent(
    w_total_kg_s: float,
    temperature_k: float = 118.15,
    Z: float = 0.98,
    M_g_mol: float = 16.043,
    k: float = 1.31,
    K_d: float = 0.85,
    P1_kPa_a: float = 117.003,
    P2_kPa_a: float = 90.603
) -> float:
    """
    NFPA 59A Section 8.4.10.7.4.2 equivalent air flow Q_a (m3/h of air at standard
    conditions, 15 degC / 1.01325 bar_a).

    Physically exact equivalent-air-flow method: the process gas flow is first
    converted to the required effective orifice area with the API 520 Part I gas
    equation; Q_a is then the API 520 air capacity of that same orifice under the
    same relieving pressures. This keeps Q_a and valve air capacities on one basis.
    """
    w_kg_h = w_total_kg_s * 3600.0
    required = calculate_api520_subcritical_orifice_area(
        w_valve_kg_h=w_kg_h,
        P1_kPa_a=P1_kPa_a,
        P2_kPa_a=P2_kPa_a,
        temperature_k=temperature_k,
        M_g_mol=M_g_mol,
        Z=Z,
        k=k,
        K_d=K_d
    )
    return calculate_valve_air_capacity_m3_h(
        required['A_o_mm2'], P1_kPa_a, P2_kPa_a, K_d=K_d
    )


def calculate_bor_tank_bog(
    tank_volume_m3: float,
    lng_density_kg_m3: float = 471.0,
    bor_pct_per_day: float = 0.10
) -> dict:
    """
    Calculates automatic Tank Boil-Off Rate (BOG) mass flow rate (kg/h) based on tank volume (m3),
    LNG density (kg/m3), and specified daily boil-off rate percentage (BOR %/day).
    Formula: W_bog (kg/h) = Tank_Volume * LNG_Density * (BOR_pct / 100) / 24
    """
    m_lng_total_kg = tank_volume_m3 * lng_density_kg_m3
    w_bog_kg_h = m_lng_total_kg * (bor_pct_per_day / 100.0) / 24.0
    return {
        'm_lng_total_kg': float(m_lng_total_kg),
        'w_bog_kg_h': float(w_bog_kg_h),
        'bor_pct_per_day': float(bor_pct_per_day)
    }


def calculate_fire_scenario_load(
    wetted_area_m2: float = 1200.0,
    insulation_factor_F: float = 0.15,
    latent_heat_kJ_kg: float = 510.0,
    fire_coefficient_c_si: float = 70.9,
    q_constant_kW_per_m2: float = None
) -> dict:
    """
    Calculates Fire Scenario Heat Absorption & Relieving Load per API 521
    (wetted-area fire case, as adopted by API 520 Part I / NFPA 59A practice).

    SI-set correlation:  Q_fire (kW) = C * F * (A_wetted ** 0.82)
        C = 70.9  -> equivalent to 34,500 Btu/h/ft2 (no adequate drainage/firefighting)
        C = 43.2  -> equivalent to 21,000 Btu/h/ft2 (adequate drainage + firefighting)

    NOTE ON UNITS: C is NOT a heat flux. It is the dimensional correlation
    coefficient of the SI unit set and carries units of kW/m^1.64 because it is
    multiplied by A^0.82 (m^1.64). Do not label it "kW/m2".

    W_fire (kg/h) = Q_fire * 3600 / Latent_Heat_kJ_kg
    """
    if q_constant_kW_per_m2 is not None:  # deprecated legacy keyword
        logger.warning("q_constant_kW_per_m2 is deprecated; use fire_coefficient_c_si.")
        fire_coefficient_c_si = q_constant_kW_per_m2
    if wetted_area_m2 <= 0.0:
        raise ValueError("Islatılmış alan pozitif olmalıdır.")
    if not (0.0 < insulation_factor_F <= 1.0):
        raise ValueError("Yalıtım faktörü F 0 < F <= 1 aralığında olmalıdır.")
    if latent_heat_kJ_kg <= 0.0:
        raise ValueError("Gizli ısı pozitif olmalıdır.")

    c_fire = max(1.0, float(fire_coefficient_c_si))
    q_fire_kW = c_fire * insulation_factor_F * (wetted_area_m2 ** 0.82)
    w_fire_kg_h = (q_fire_kW * 3600.0) / latent_heat_kJ_kg
    w_fire_kg_s = w_fire_kg_h / 3600.0
    return {
        'q_fire_kW': float(q_fire_kW),
        'w_fire_kg_h': float(w_fire_kg_h),
        'w_fire_kg_s': float(w_fire_kg_s),
        'wetted_area_m2': float(wetted_area_m2),
        'insulation_factor_F': float(insulation_factor_F),
        'latent_heat_kJ_kg': float(latent_heat_kJ_kg),
        'fire_coefficient_c_si': float(c_fire),
        'q_constant_kW_per_m2': float(c_fire)  # deprecated alias, same value
    }


def evaluate_valve_matrix(
    q_a_per_valve_m3_h: float,
    P1_kPa_a: float,
    P2_kPa_a: float = 90.603,
    K_d: float = None,
    valve_type: str = 'all'
) -> list:
    """
    Evaluates commercial relief valve models dynamically from psv_database.json
    under specific atmospheric pressure conditions.

    Valve capacity is computed per API 520 Part I with air at standard conditions
    using each valve's own catalog discharge coefficient (``discharge_coeff_kd``).
    ``K_d`` is an explicit override for sensitivity studies only and must not be
    used for selection unless the value is certified for the specific model.
    ``valve_type`` filters the candidate pool to 'pilot', 'spring' or 'all'.
    """
    from psv_database import categorize_valve_type, load_psv_database
    valves = load_psv_database()

    results = []
    for v in valves:
        if valve_type in ('pilot', 'spring') and categorize_valve_type(v.get('type', '')) != valve_type:
            continue
        area = v['orifice_area_mm2']
        kd_val = K_d if K_d is not None else v.get('discharge_coeff_kd', 0.85)
        capacity_m3_h = calculate_valve_air_capacity_m3_h(area, P1_kPa_a, P2_kPa_a, K_d=kd_val)
        coverage_pct = (capacity_m3_h / max(1e-9, q_a_per_valve_m3_h)) * 100.0
        utilization_pct = (100.0 / coverage_pct * 100.0) if coverage_pct > 0.0 else float('inf')

        if coverage_pct > 200.0:
            status = '⚠️ AŞIRI BÜYÜK (>%200 Oversizing / Chattering Riski)'
            status_code = 'OVERSIZED'
        elif coverage_pct >= 110.0:
            status = '✅ UYGUN (Emniyet Marjlı)'
            status_code = 'SUCCESS'
        elif coverage_pct >= 100.0:
            status = '⚠️ SINIRDA UYGUN (Düşük Marj)'
            status_code = 'WARNING'
        elif coverage_pct >= 90.0:
            status = '⚠️ YAKIN KAPASİTE (%90-100 Sınırda)'
            status_code = 'WARNING_90'
        else:
            status = '❌ YETERSİZ (Kapasite Açığı Var)'
            status_code = 'FAIL'

        results.append({
            'size_name': f"{v['manufacturer']} {v['series']} ({v['dn_size']})",
            'orifice_area_mm2': area,
            'discharge_coeff_kd': kd_val,
            'air_capacity_m3_h': capacity_m3_h,
            'coverage_pct': coverage_pct,
            'utilization_pct': utilization_pct,
            'status': status,
            'status_code': status_code,
            'valve_category': categorize_valve_type(v.get('type', '')),
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
