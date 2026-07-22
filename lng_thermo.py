"""
LNG Thermodynamic & Physical Properties Module
Calculates LNG Liquid Density using the COSTALD (Hankinson-Brobst-Thomson) Method,
as well as Saturated Methane/LNG Vapor Density and Real Gas Properties under relief conditions.
Supports expanded hydrocarbon (C1 to C6+) and non-hydrocarbon (N2, CO2, O2, H2, Ar, He) components.
"""

import math
import numpy as np

# Expanded Component physical constants for COSTALD Method
# T_c in Kelvin, P_c in bar, V_star in L/mol, M in g/mol, omega_srk dimensionless
COMPONENT_DATA = {
    'CH4': {'name': 'Methane (Metan - CH4)', 'M': 16.043, 'Tc': 190.56, 'Pc': 45.99, 'V_star': 0.0993, 'omega_srk': 0.011},
    'C2H6': {'name': 'Ethane (Etan - C2H6)', 'M': 30.070, 'Tc': 305.32, 'Pc': 48.72, 'V_star': 0.1455, 'omega_srk': 0.099},
    'C3H8': {'name': 'Propane (Propan - C3H8)', 'M': 44.097, 'Tc': 369.83, 'Pc': 42.48, 'V_star': 0.2001, 'omega_srk': 0.152},
    'iC4H10': {'name': 'iso-Butane (İzo-Bütan - i-C4H10)', 'M': 58.122, 'Tc': 407.85, 'Pc': 36.40, 'V_star': 0.2568, 'omega_srk': 0.186},
    'nC4H10': {'name': 'n-Butane (n-Bütan - n-C4H10)', 'M': 58.122, 'Tc': 425.12, 'Pc': 37.96, 'V_star': 0.2550, 'omega_srk': 0.200},
    'iC5H12': {'name': 'iso-Pentane (İzo-Pentan - i-C5H12)', 'M': 72.150, 'Tc': 460.40, 'Pc': 33.80, 'V_star': 0.3060, 'omega_srk': 0.227},
    'nC5H12': {'name': 'n-Pentane (n-Pentan - n-C5H12)', 'M': 72.150, 'Tc': 469.70, 'Pc': 33.70, 'V_star': 0.3040, 'omega_srk': 0.251},
    'C6plus': {'name': 'Hexane+ (Heksan+ - C6+)', 'M': 86.180, 'Tc': 507.60, 'Pc': 30.20, 'V_star': 0.3680, 'omega_srk': 0.301},
    'N2': {'name': 'Nitrogen (Azot - N2)', 'M': 28.013, 'Tc': 126.20, 'Pc': 34.00, 'V_star': 0.0901, 'omega_srk': 0.040},
    'CO2': {'name': 'Carbon Dioxide (Karbondioksit - CO2)', 'M': 44.010, 'Tc': 304.10, 'Pc': 73.80, 'V_star': 0.0940, 'omega_srk': 0.224},
    'O2': {'name': 'Oxygen (Oksijen - O2)', 'M': 31.999, 'Tc': 154.60, 'Pc': 50.40, 'V_star': 0.0734, 'omega_srk': 0.022},
    'H2': {'name': 'Hydrogen (Hidrojen - H2)', 'M': 2.016, 'Tc': 33.19, 'Pc': 13.00, 'V_star': 0.0650, 'omega_srk': -0.216},
    'Ar': {'name': 'Argon (Argon - Ar)', 'M': 39.948, 'Tc': 150.80, 'Pc': 48.70, 'V_star': 0.0745, 'omega_srk': 0.001},
    'He': {'name': 'Helium (Helyum - He)', 'M': 4.003, 'Tc': 5.19, 'Pc': 2.27, 'V_star': 0.0578, 'omega_srk': -0.365},
    'H2S': {'name': 'Hydrogen Sulfide (Hidrojen Sülfür - H2S)', 'M': 34.080, 'Tc': 373.53, 'Pc': 89.63, 'V_star': 0.1118, 'omega_srk': 0.090},
    'H2O': {'name': 'Water Vapor (Su Buharı - H2O)', 'M': 18.015, 'Tc': 647.10, 'Pc': 220.64, 'V_star': 0.0560, 'omega_srk': 0.344},
    'CO': {'name': 'Carbon Monoxide (Karbonmonoksit - CO)', 'M': 28.010, 'Tc': 132.86, 'Pc': 34.94, 'V_star': 0.0931, 'omega_srk': 0.049},
    'Air': {'name': 'Air (Hava - Air)', 'M': 28.965, 'Tc': 132.53, 'Pc': 37.86, 'V_star': 0.0924, 'omega_srk': 0.035}
}

def calculate_costald_density(composition_mol_pct: dict, temperature_k: float = 118.15, pressure_bar_a: float = 1.20) -> dict:
    """
    Calculates liquid LNG density using Hankinson-Brobst-Thomson (COSTALD 1979) correlation.
    
    :param composition_mol_pct: Dictionary of mole percentages
    :param temperature_k: Liquid temperature in Kelvin
    :param pressure_bar_a: Pressure in bar absolute
    :return: dict with 'density_kg_m3', 'molar_mass_g_mol', details
    """
    sum_pct = sum(composition_mol_pct.values())
    if sum_pct <= 0:
        sum_pct = 100.0
    
    x = {comp: pct / sum_pct for comp, pct in composition_mol_pct.items() if comp in COMPONENT_DATA and pct > 0}
    if not x:
        x = {'CH4': 1.0}
    
    # 1. Mixture Molar Mass (g/mol)
    M_mix = sum(x[comp] * COMPONENT_DATA[comp]['M'] for comp in x)
    
    # 2. COSTALD Characteristic Volume V_m_star (L/mol)
    sum_x_Vstar = sum(x[c] * COMPONENT_DATA[c]['V_star'] for c in x)
    sum_x_Vstar_23 = sum(x[c] * (COMPONENT_DATA[c]['V_star']**(2/3)) for c in x)
    sum_x_Vstar_13 = sum(x[c] * (COMPONENT_DATA[c]['V_star']**(1/3)) for c in x)
    
    V_m_star = 0.25 * (sum_x_Vstar + 3.0 * sum_x_Vstar_23 * sum_x_Vstar_13)
    
    # 3. COSTALD Pseudo-Critical Temperature T_cm (K)
    numerator_Tc = 0.0
    comp_list = list(x.keys())
    for i in range(len(comp_list)):
        c_i = comp_list[i]
        for j in range(len(comp_list)):
            c_j = comp_list[j]
            V_ij_star = math.sqrt(COMPONENT_DATA[c_i]['V_star'] * COMPONENT_DATA[c_j]['V_star'])
            T_cij = math.sqrt(COMPONENT_DATA[c_i]['Tc'] * COMPONENT_DATA[c_j]['Tc'])
            numerator_Tc += x[c_i] * x[c_j] * V_ij_star * T_cij
            
    T_cm = numerator_Tc / V_m_star if V_m_star > 0 else 190.56
    
    # 4. Acentric factor mixture omega_m
    omega_m = sum(x[c] * COMPONENT_DATA[c]['omega_srk'] for c in x)
    
    # 5. Reduced temperature T_r
    T_r = temperature_k / T_cm
    T_r_clamped = max(0.25, min(0.999, T_r))
    tau = 1.0 - T_r_clamped
    
    V_0 = (1.0 
           - 1.52816 * (tau**(1/3)) 
           + 1.43907 * (tau**(2/3)) 
           - 0.81446 * tau 
           + 0.190454 * (tau**(4/3)))
    
    # Standard Hankinson-Brobst-Thomson (1979) V_delta literature formula
    if T_r_clamped < 0.95:
        V_delta = (-0.296123 + 0.386914 * T_r_clamped - 0.0427258 * (T_r_clamped**2) - 0.0480616 * (T_r_clamped**3)) / (T_r_clamped - 1.00001)
    else:
        V_delta = (-5.30571 + 12.6397 * T_r_clamped - 9.1763 * (T_r_clamped**2) + 1.84158 * (T_r_clamped**3)) / (T_r_clamped - 1.00001)
    
    # Saturated Molar Volume V_s (L/mol)
    V_s = V_m_star * V_0 * (1.0 - omega_m * V_delta)
    
    if V_s > 0:
        density_kg_m3 = M_mix / V_s
    else:
        density_kg_m3 = 471.0
        
    return {
        'density_kg_m3': float(density_kg_m3),
        'molar_mass_g_mol': float(M_mix),
        'V_s_L_mol': float(V_s),
        'T_cm_K': float(T_cm),
        'T_r': float(T_r),
        'omega_m': float(omega_m),
        'sum_mol_pct': float(sum_pct),
        'composition_normalized': x
    }

def calculate_vapor_density(P_abs_kPa: float, temperature_k: float = 118.15, M_g_mol: float = 16.04, Z: float = 0.98) -> float:
    """
    Calculates saturated/relieving gas vapor density rho_v (kg/m3).
    rho = (P * M) / (Z * R * T)
    """
    R_universal = 8.3144626
    rho_v = (P_abs_kPa * M_g_mol) / (Z * R_universal * temperature_k)
    return float(rho_v)

if __name__ == '__main__':
    sample_comp = {'CH4': 89.5, 'C2H6': 5.0, 'C3H8': 2.0, 'iC4H10': 0.5, 'nC4H10': 0.5, 'iC5H12': 0.2, 'nC5H12': 0.1, 'C6plus': 0.1, 'N2': 1.5, 'CO2': 0.6}
    res = calculate_costald_density(sample_comp, temperature_k=118.15)
    print(f"Expanded COSTALD LNG Density: {res['density_kg_m3']:.2f} kg/m3")
    print(f"Molar Mass: {res['molar_mass_g_mol']:.2f} g/mol")
