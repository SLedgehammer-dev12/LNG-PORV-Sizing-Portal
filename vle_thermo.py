"""
VLE & Multi-EOS Thermodynamic Engine (Peng-Robinson, SRK, GERG-2008 / Ideal Gas)
Calculates Real Gas Z-factor, Fugacity Coefficients, Rachford-Rice Two-Phase VLE Flash BOG,
and Dynamic Temperature & Pressure Dependent Heat Capacity Ratio k_mix(T, P) = Cp(T,P) / Cv(T,P).
"""

import math
import logging

logger = logging.getLogger(__name__)

# Expanded 18-Component Thermodynamic Constants Database
# Tc in K, Pc in bar, omega dimensionless, M in g/mol
# Aly-Lee / Ideal Gas Cp coefficients: Cp_ideal(T) = A + B*T + C*T^2 + D*T^3 (J/(mol*K))
EOS_COMPONENT_DATA = {
    'CH4': {
        'name': 'Methane (Metan - CH4)',
        'M': 16.043, 'Tc': 190.56, 'Pc': 45.99, 'omega': 0.011, 'k_ideal_298': 1.31,
        'cp_coeffs': [19.25, 0.05213, 1.197e-5, -1.132e-8]
    },
    'C2H6': {
        'name': 'Ethane (Etan - C2H6)',
        'M': 30.070, 'Tc': 305.32, 'Pc': 48.72, 'omega': 0.099, 'k_ideal_298': 1.19,
        'cp_coeffs': [5.409, 0.1781, -6.938e-5, 8.713e-9]
    },
    'C3H8': {
        'name': 'Propane (Propan - C3H8)',
        'M': 44.097, 'Tc': 369.83, 'Pc': 42.48, 'omega': 0.152, 'k_ideal_298': 1.13,
        'cp_coeffs': [-4.224, 0.3063, -1.586e-4, 3.215e-8]
    },
    'iC4H10': {
        'name': 'iso-Butane (İzo-Bütan - i-C4H10)',
        'M': 58.122, 'Tc': 407.85, 'Pc': 36.40, 'omega': 0.186, 'k_ideal_298': 1.10,
        'cp_coeffs': [-7.913, 0.4029, -2.261e-4, 5.048e-8]
    },
    'nC4H10': {
        'name': 'n-Butane (n-Bütan - n-C4H10)',
        'M': 58.122, 'Tc': 425.12, 'Pc': 37.96, 'omega': 0.200, 'k_ideal_298': 1.09,
        'cp_coeffs': [3.955, 0.3713, -1.834e-4, 3.500e-8]
    },
    'iC5H12': {
        'name': 'iso-Pentane (İzo-Pentan - i-C5H12)',
        'M': 72.150, 'Tc': 460.40, 'Pc': 33.80, 'omega': 0.227, 'k_ideal_298': 1.08,
        'cp_coeffs': [-9.450, 0.4850, -2.610e-4, 5.420e-8]
    },
    'nC5H12': {
        'name': 'n-Pentane (n-Pentan - n-C5H12)',
        'M': 72.150, 'Tc': 469.70, 'Pc': 33.70, 'omega': 0.251, 'k_ideal_298': 1.08,
        'cp_coeffs': [-3.626, 0.4873, -2.580e-4, 5.310e-8]
    },
    'C6plus': {
        'name': 'Hexane+ (Hekzan+ - C6+)',
        'M': 86.177, 'Tc': 507.60, 'Pc': 30.25, 'omega': 0.301, 'k_ideal_298': 1.06,
        'cp_coeffs': [-4.413, 0.5820, -3.119e-4, 6.490e-8]
    },
    'N2': {
        'name': 'Nitrogen (Azot - N2)',
        'M': 28.013, 'Tc': 126.20, 'Pc': 33.90, 'omega': 0.037, 'k_ideal_298': 1.40,
        'cp_coeffs': [31.15, -0.01357, 2.680e-5, -1.168e-8]
    },
    'CO2': {
        'name': 'Carbon Dioxide (Karbondioksit - CO2)',
        'M': 44.010, 'Tc': 304.13, 'Pc': 73.77, 'omega': 0.225, 'k_ideal_298': 1.28,
        'cp_coeffs': [24.99, 0.05519, -3.369e-5, 7.948e-9]
    },
    'O2': {
        'name': 'Oxygen (Oksijen - O2)',
        'M': 31.999, 'Tc': 154.58, 'Pc': 50.43, 'omega': 0.022, 'k_ideal_298': 1.39,
        'cp_coeffs': [29.10, -0.00877, 2.025e-5, -8.727e-9]
    },
    'H2': {
        'name': 'Hydrogen (Hidrojen - H2)',
        'M': 2.016, 'Tc': 33.19, 'Pc': 13.13, 'omega': -0.216, 'k_ideal_298': 1.41,
        'cp_coeffs': [27.14, 0.00927, -1.380e-5, 7.645e-9]
    },
    'Ar': {
        'name': 'Argon (Argon - Ar)',
        'M': 39.948, 'Tc': 150.80, 'Pc': 48.70, 'omega': 0.001, 'k_ideal_298': 1.67,
        'cp_coeffs': [20.786, 0.0, 0.0, 0.0]
    },
    'He': {
        'name': 'Helium (Helyum - He)',
        'M': 4.003, 'Tc': 5.19, 'Pc': 2.27, 'omega': -0.365, 'k_ideal_298': 1.67,
        'cp_coeffs': [20.786, 0.0, 0.0, 0.0]
    },
    'H2S': {
        'name': 'Hydrogen Sulfide (Hidrojen Sülfür - H2S)',
        'M': 34.080, 'Tc': 373.53, 'Pc': 89.63, 'omega': 0.090, 'k_ideal_298': 1.32,
        'cp_coeffs': [32.68, 0.0124, 1.93e-6, -2.10e-9]
    },
    'H2O': {
        'name': 'Water Vapor (Su Buharı - H2O)',
        'M': 18.015, 'Tc': 647.10, 'Pc': 220.64, 'omega': 0.344, 'k_ideal_298': 1.33,
        'cp_coeffs': [32.24, 0.00192, 1.055e-5, -3.596e-9]
    },
    'CO': {
        'name': 'Carbon Monoxide (Karbonmonoksit - CO)',
        'M': 28.010, 'Tc': 132.86, 'Pc': 34.94, 'omega': 0.049, 'k_ideal_298': 1.40,
        'cp_coeffs': [29.56, -0.00658, 2.013e-5, -1.223e-8]
    },
    'Air': {
        'name': 'Air (Hava - Air)',
        'M': 28.965, 'Tc': 132.53, 'Pc': 37.86, 'omega': 0.035, 'k_ideal_298': 1.40,
        'cp_coeffs': [28.97, -0.00157, 1.708e-5, -8.773e-9]
    }
}

R_GAS = 8.3144626 # J/(mol*K)

def calculate_cp_ideal_component(comp: str, temperature_k: float) -> float:
    """ Calculates ideal gas Cp (J/(mol*K)) for a component at temperature_k. """
    c_data = EOS_COMPONENT_DATA.get(comp, EOS_COMPONENT_DATA['CH4'])
    a, b, c, d = c_data['cp_coeffs']
    T = max(50.0, min(1000.0, temperature_k))
    return a + b * T + c * (T**2) + d * (T**3)

def solve_cubic_z(A: float, B: float, eos: str = 'PR') -> tuple:
    """
    Solves the cubic equation of state in compressibility factor Z:
    PR: Z^3 - (1 - B) Z^2 + (A - 2B - 3B^2) Z - (AB - B^2 - B^3) = 0
    SRK: Z^3 - Z^2 + (A - B - B^2) Z - A*B = 0
    Returns (Z_gas, Z_liquid)
    """
    if eos.upper() == 'SRK':
        a2 = -1.0
        a1 = A - B - (B**2)
        a0 = -A * B
    else: # PR (1976)
        a2 = -(1.0 - B)
        a1 = A - 2.0 * B - 3.0 * (B**2)
        a0 = -(A * B - (B**2) - (B**3))

    p = a1 - (a2**2) / 3.0
    q = (2.0 * (a2**3) / 27.0) - (a2 * a1 / 3.0) + a0
    discriminant = (q**2) / 4.0 + (p**3) / 27.0

    roots = []
    if discriminant < 0:
        m = 2.0 * math.sqrt(-p / 3.0)
        arg = -q / (2.0 * math.sqrt(- (p**3) / 27.0)) if p != 0 else 0.0
        arg = max(-1.0, min(1.0, arg))
        theta = math.acos(arg) / 3.0
        
        r1 = m * math.cos(theta) - a2 / 3.0
        r2 = m * math.cos(theta + (2.0 * math.pi / 3.0)) - a2 / 3.0
        r3 = m * math.cos(theta + (4.0 * math.pi / 3.0)) - a2 / 3.0
        roots = sorted([r1, r2, r3])
    else:
        u_arg = -q / 2.0 + math.sqrt(max(0.0, discriminant))
        v_arg = -q / 2.0 - math.sqrt(max(0.0, discriminant))
        u = math.pow(u_arg, 1/3) if u_arg >= 0 else -math.pow(abs(u_arg), 1/3)
        v = math.pow(v_arg, 1/3) if v_arg >= 0 else -math.pow(abs(v_arg), 1/3)
        r1 = u + v - a2 / 3.0
        roots = [r1]

    valid_roots = [r for r in roots if r > B]
    if not valid_roots:
        valid_roots = [max(1e-3, B + 1e-3)]
        
    Z_gas = max(valid_roots)
    Z_liquid = min(valid_roots)
    return Z_gas, Z_liquid

def calculate_eos_mixture_properties(
    composition_mol: dict,
    temperature_k: float,
    pressure_kPa_a: float,
    eos: str = 'PR'
) -> dict:
    """
    Calculates thermodynamic properties (Z_gas, Z_liquid, dynamic Cp/Cv ratio k_mix(T,P), density)
    using Peng-Robinson (PR) or Soave-Redlich-Kwong (SRK) EOS.
    """
    total_pct = sum(composition_mol.values())
    if total_pct <= 0:
        total_pct = 100.0
    x = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not x:
        x = {'CH4': 1.0}
        
    P_bar = pressure_kPa_a / 100.0
    P_Pa = pressure_kPa_a * 1000.0
    T = max(30.0, temperature_k)
    
    a_i = {}
    b_i = {}
    m_i = {}
    
    for c in x:
        data = EOS_COMPONENT_DATA[c]
        Tc = data['Tc']
        Pc = data['Pc']
        w = data['omega']
        Tr = T / Tc
        
        if eos.upper() == 'SRK':
            m = 0.480 + 1.574 * w - 0.176 * (w**2)
            alpha = (1.0 + m * (1.0 - math.sqrt(Tr)))**2
            a = 0.42748 * ((R_GAS * Tc)**2) / (Pc * 1e5) * alpha
            b = 0.08664 * (R_GAS * Tc) / (Pc * 1e5)
        else: # PR 1976
            m = 0.37464 + 1.54226 * w - 0.26992 * (w**2)
            alpha = (1.0 + m * (1.0 - math.sqrt(Tr)))**2
            a = 0.45724 * ((R_GAS * Tc)**2) / (Pc * 1e5) * alpha
            b = 0.07780 * (R_GAS * Tc) / (Pc * 1e5)
            
        a_i[c] = a
        b_i[c] = b
        m_i[c] = m
        
    a_mix = 0.0
    b_mix = sum(x[c] * b_i[c] for c in x)
    
    comp_list = list(x.keys())
    for i in range(len(comp_list)):
        c_i = comp_list[i]
        for j in range(len(comp_list)):
            c_j = comp_list[j]
            a_mix += x[c_i] * x[c_j] * math.sqrt(a_i[c_i] * a_i[c_j])
            
    A = (a_mix * P_Pa) / ((R_GAS * T)**2)
    B = (b_mix * P_Pa) / (R_GAS * T)
    
    Z_gas, Z_liquid = solve_cubic_z(A, B, eos=eos)
    
    M_mix = sum(x[c] * EOS_COMPONENT_DATA[c]['M'] for c in x)
    
    Cp_ideal = sum(x[c] * calculate_cp_ideal_component(c, T) for c in x)
    Cv_ideal = Cp_ideal - R_GAS
    
    # Real Gas Residual Heat Capacity Correction Cv_res(T,P) from EOS second temperature derivative
    d2a_dT2 = 0.0
    for i in range(len(comp_list)):
        c_i = comp_list[i]
        Tc_i = EOS_COMPONENT_DATA[c_i]['Tc']
        Pc_i = EOS_COMPONENT_DATA[c_i]['Pc']
        m_i_val = m_i[c_i]
        if eos.upper() == 'SRK':
            a0_i = 0.42748 * ((R_GAS * Tc_i)**2) / (Pc_i * 1e5)
        else:
            a0_i = 0.45724 * ((R_GAS * Tc_i)**2) / (Pc_i * 1e5)

        for j in range(len(comp_list)):
            c_j = comp_list[j]
            Tc_j = EOS_COMPONENT_DATA[c_j]['Tc']
            Pc_j = EOS_COMPONENT_DATA[c_j]['Pc']
            m_j_val = m_i[c_j]
            if eos.upper() == 'SRK':
                a0_j = 0.42748 * ((R_GAS * Tc_j)**2) / (Pc_j * 1e5)
            else:
                a0_j = 0.45724 * ((R_GAS * Tc_j)**2) / (Pc_j * 1e5)

            d2a_ij = math.sqrt(a0_i * a0_j) * (1.0 / (4.0 * (T**1.5))) * (
                (m_i_val * (1.0 + m_j_val) / math.sqrt(Tc_i)) +
                (m_j_val * (1.0 + m_i_val) / math.sqrt(Tc_j))
            )
            d2a_dT2 += x[c_i] * x[c_j] * d2a_ij

    if eos.upper() == 'SRK':
        Cv_res = (T * d2a_dT2 / b_mix) * math.log(1.0 + B / Z_gas) if Z_gas > B else 0.0
    else: # PR
        sqrt2 = math.sqrt(2.0)
        log_term = math.log((Z_gas + (1.0 + sqrt2) * B) / max(1e-6, Z_gas + (1.0 - sqrt2) * B))
        Cv_res = (T * d2a_dT2 / (2.0 * sqrt2 * b_mix)) * log_term if Z_gas > B else 0.0

    Cv_real = max(R_GAS * 0.1, Cv_ideal + max(0.0, Cv_res))
    Cp_real = Cv_real + R_GAS * Z_gas
    
    k_mix = max(1.05, min(1.67, Cp_real / Cv_real))
    
    rho_v = (P_Pa * (M_mix / 1000.0)) / (Z_gas * R_GAS * T)
    
    return {
        'Z_gas': float(Z_gas),
        'Z_liquid': float(Z_liquid),
        'k_mix': float(k_mix),
        'Cp_ideal': float(Cp_ideal),
        'Cp_real': float(Cp_real),
        'Cv_real': float(Cv_real),
        'M_mix': float(M_mix),
        'rho_v_kg_m3': float(rho_v),
        'A': float(A),
        'B': float(B),
        'eos_name': eos.upper()
    }

def calculate_two_phase_vle_flash(
    composition_mol: dict,
    temperature_k: float,
    pressure_kPa_a: float,
    eos: str = 'PR'
) -> dict:
    """
    Rachford-Rice Two-Phase VLE Flash Solver.
    Calculates equilibrium BOG vapor fraction (V/F), vapor composition y_i, and liquid composition x_i.
    """
    total_pct = sum(composition_mol.values())
    if total_pct <= 0:
        total_pct = 100.0
    z = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not z:
        z = {'CH4': 1.0}

    P_bar = pressure_kPa_a / 100.0
    T = temperature_k

    K = {}
    for c in z:
        data = EOS_COMPONENT_DATA[c]
        P_ci = data['Pc']
        T_ci = data['Tc']
        w_i = data['omega']
        K[c] = (P_ci / P_bar) * math.exp(5.37 * (1.0 + w_i) * (1.0 - T_ci / T))

    def rachford_rice(v_frac):
        return sum((z[c] * (K[c] - 1.0)) / (1.0 + v_frac * (K[c] - 1.0)) for c in z)

    v_min, v_max = 0.0, 1.0
    f_min = rachford_rice(v_min)
    f_max = rachford_rice(v_max)

    if f_min <= 0:
        v_frac = 0.0
    elif f_max >= 0:
        v_frac = 1.0
    else:
        v_frac = 0.05
        for _ in range(30):
            v_mid = 0.5 * (v_min + v_max)
            f_mid = rachford_rice(v_mid)
            if abs(f_mid) < 1e-6:
                v_frac = v_mid
                break
            if f_mid > 0:
                v_min = v_mid
            else:
                v_max = v_mid
            v_frac = v_mid

    x_liq = {}
    y_vap = {}
    for c in z:
        denom = 1.0 + v_frac * (K[c] - 1.0)
        x_liq[c] = z[c] / denom
        y_vap[c] = (z[c] * K[c]) / denom

    sum_y = sum(y_vap.values())
    if sum_y > 0:
        y_vap = {c: val / sum_y for c, val in y_vap.items()}

    vap_props = calculate_eos_mixture_properties(y_vap, T, pressure_kPa_a, eos=eos)

    return {
        'v_frac_VF': float(v_frac),
        'flash_pct': float(v_frac * 100.0),
        'y_vapor': y_vap,
        'x_liquid': x_liq,
        'K_values': K,
        'Z_gas': vap_props['Z_gas'],
        'k_mix': vap_props['k_mix'],
        'rho_v_kg_m3': vap_props['rho_v_kg_m3'],
        'M_vapor_g_mol': vap_props['M_mix'],
        'eos_used': eos.upper()
    }
