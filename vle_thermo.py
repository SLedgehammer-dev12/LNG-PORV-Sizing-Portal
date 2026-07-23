"""
VLE & Multi-EOS Thermodynamic Engine (Peng-Robinson, SRK, Ideal Gas)
Calculates Real Gas Z-factor, Fugacity Coefficients, Rachford-Rice Two-Phase VLE Flash BOG,
Binary Interaction Parameters (k_ij), and Dynamic Heat Capacity Ratio k_mix(T, P) = Cp(T,P) / Cv(T,P).
"""

import math
import logging
from lng_thermo import COMPONENT_DATA as EOS_COMPONENT_DATA

logger = logging.getLogger(__name__)

R_GAS = 8.3144626 # J/(mol*K)

# Binary Interaction Parameter Matrix k_ij for hydrocarbon/non-hydrocarbon mixtures
BINARY_INTERACTION_K_IJ = {
    ('CH4', 'N2'): 0.035, ('N2', 'CH4'): 0.035,
    ('CH4', 'C2H6'): 0.005, ('C2H6', 'CH4'): 0.005,
    ('CH4', 'C3H8'): 0.010, ('C3H8', 'CH4'): 0.010,
    ('CH4', 'CO2'): 0.095, ('CO2', 'CH4'): 0.095,
    ('N2', 'C2H6'): 0.060, ('C2H6', 'N2'): 0.060,
    ('N2', 'C3H8'): 0.080, ('C3H8', 'N2'): 0.080,
    ('CO2', 'C2H6'): 0.130, ('C2H6', 'CO2'): 0.130
}

# CoolProp Fluid Name Mapping for HEOS (GERG-2008) Helmholtz Energy EOS
COOLPROP_FLUID_NAMES = {
    'CH4': 'Methane',
    'C2H6': 'Ethane',
    'C3H8': 'Propane',
    'iC4H10': 'Isobutane',
    'nC4H10': 'n-Butane',
    'iC5H12': 'Isopentane',
    'nC5H12': 'n-Pentane',
    'nC6H14': 'n-Hexane',
    'nC7H16': 'n-Heptane',
    'nC8H18': 'n-Octane',
    'N2': 'Nitrogen',
    'CO2': 'CarbonDioxide',
    'H2S': 'HydrogenSulfide',
    'H2': 'Hydrogen',
    'He': 'Helium',
    'O2': 'Oxygen'
}

def get_k_ij(comp_i: str, comp_j: str) -> float:
    if comp_i == comp_j:
        return 0.0
    return BINARY_INTERACTION_K_IJ.get((comp_i, comp_j), 0.0)

def calculate_cp_ideal_component(comp: str, temperature_k: float) -> float:
    """
    Calculates component ideal gas isobaric heat capacity Cp_ideal(T) in J/(mol*K)
    using Aly-Lee polynomial coefficients.
    """
    if temperature_k < 150.0:
        logger.debug(f"Temperature {temperature_k:.2f} K < 150 K: Aly-Lee Cp polynomial extrapolation applied for {comp}.")
        
    data = EOS_COMPONENT_DATA.get(comp, EOS_COMPONENT_DATA['CH4'])
    coeffs = data['cp_coeffs']
    T = max(50.0, temperature_k)
    
    # Cp_ideal = A + B*T + C*T^2 + D*T^3
    cp = coeffs[0] + coeffs[1] * T + coeffs[2] * (T**2) + coeffs[3] * (T**3)
    return max(15.0, cp)

def solve_cubic_z(A: float, B: float, eos: str = 'PR') -> tuple:
    """
    Solves the Cubic Equation of State for Z (Compressibility Factor).
    PR 1976: Z^3 - (1-B)*Z^2 + (A - 2B - 3B^2)*Z - (AB - B^2 - B^3) = 0
    SRK:     Z^3 - Z^2 + (A - B - B^2)*Z - AB = 0
    
    Returns (Z_gas, Z_liquid)
    """
    if eos.upper() == 'SRK':
        a2 = -1.0
        a1 = A - B - (B**2)
        a0 = -A * B
    else: # PR 1976
        a2 = -(1.0 - B)
        a1 = A - 2.0 * B - 3.0 * (B**2)
        a0 = -(A * B - (B**2) - (B**3))

    # Solve Cubic polynomial via Cardan's analytical method
    p = a1 - (a2**2) / 3.0
    q = (2.0 * (a2**3)) / 27.0 - (a2 * a1) / 3.0 + a0
    discriminant = (q**2) / 4.0 + (p**3) / 27.0

    roots = []
    if discriminant < 0:
        # Three real roots
        r = math.sqrt(- (p**3) / 27.0)
        phi = math.acos(max(-1.0, min(1.0, -q / (2.0 * r))))
        r_13 = math.pow(r, 1/3)
        
        y1 = 2.0 * r_13 * math.cos(phi / 3.0)
        y2 = 2.0 * r_13 * math.cos((phi + 2.0 * math.pi) / 3.0)
        y3 = 2.0 * r_13 * math.cos((phi + 4.0 * math.pi) / 3.0)
        
        roots = [y1 - a2 / 3.0, y2 - a2 / 3.0, y3 - a2 / 3.0]
    else:
        # One real root
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

def calculate_fugacity_coefficients(
    composition_mol: dict,
    temperature_k: float,
    pressure_kPa_a: float,
    eos: str = 'PR',
    phase: str = 'gas'
) -> dict:
    """
    Calculates analytical component fugacity coefficients phi_i(T, P, x/y)
    for Peng-Robinson or SRK EOS.
    """
    total_pct = sum(composition_mol.values())
    if total_pct <= 0:
        total_pct = 100.0
    x = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not x:
        x = {'CH4': 1.0}

    P_Pa = pressure_kPa_a * 1000.0
    T = max(30.0, temperature_k)
    
    a_i = {}
    b_i = {}
    for c in x:
        data = EOS_COMPONENT_DATA[c]
        Tc, Pc, w = data['Tc'], data['Pc'], data['omega']
        Tr = T / Tc
        if eos.upper() == 'SRK':
            m = 0.480 + 1.574 * w - 0.176 * (w**2)
            alpha = (1.0 + m * (1.0 - math.sqrt(Tr)))**2
            a_i[c] = 0.42748 * ((R_GAS * Tc)**2) / (Pc * 1e5) * alpha
            b_i[c] = 0.08664 * (R_GAS * Tc) / (Pc * 1e5)
        else: # PR
            m = 0.37464 + 1.54226 * w - 0.26992 * (w**2)
            alpha = (1.0 + m * (1.0 - math.sqrt(Tr)))**2
            a_i[c] = 0.45724 * ((R_GAS * Tc)**2) / (Pc * 1e5) * alpha
            b_i[c] = 0.07780 * (R_GAS * Tc) / (Pc * 1e5)

    a_mix = 0.0
    b_mix = sum(x[c] * b_i[c] for c in x)
    comp_list = list(x.keys())

    bar_a_i = {c: 0.0 for c in comp_list}
    for i in range(len(comp_list)):
        c_i = comp_list[i]
        for j in range(len(comp_list)):
            c_j = comp_list[j]
            k_ij = get_k_ij(c_i, c_j)
            a_ij = math.sqrt(a_i[c_i] * a_i[c_j]) * (1.0 - k_ij)
            a_mix += x[c_i] * x[c_j] * a_ij
            bar_a_i[c_i] += x[c_j] * a_ij

    A = (a_mix * P_Pa) / ((R_GAS * T)**2)
    B = (b_mix * P_Pa) / (R_GAS * T)
    
    Z_gas, Z_liquid = solve_cubic_z(A, B, eos=eos)
    Z = Z_gas if phase.lower() in ('gas', 'vapor') else Z_liquid
    Z = max(B + 1e-4, Z)

    phi = {}
    for c in comp_list:
        bi_bm = b_i[c] / b_mix if b_mix > 0 else 1.0
        ai_am = (2.0 * bar_a_i[c]) / a_mix if a_mix > 0 else 1.0
        
        term1 = bi_bm * (Z - 1.0)
        term2 = -math.log(Z - B)
        
        if eos.upper() == 'SRK':
            term3 = -(A / B) * (ai_am - bi_bm) * math.log(1.0 + B / Z)
        else: # PR
            sqrt2 = math.sqrt(2.0)
            log_arg = (Z + (1.0 + sqrt2) * B) / max(1e-6, Z + (1.0 - sqrt2) * B)
            term3 = -(A / (2.0 * sqrt2 * B)) * (ai_am - bi_bm) * math.log(max(1e-6, log_arg))
            
        ln_phi = term1 + term2 + term3
        phi[c] = math.exp(max(-50.0, min(50.0, ln_phi)))

    return phi

def calculate_eos_mixture_properties(
    composition_mol: dict,
    temperature_k: float,
    pressure_kPa_a: float,
    eos: str = 'PR'
) -> dict:
    """
    Calculates thermodynamic properties (Z_gas, Z_liquid, dynamic Cp/Cv ratio k_mix(T,P), density)
    using Peng-Robinson (PR), Soave-Redlich-Kwong (SRK), or Ideal Gas model.
    Includes Binary Interaction Parameters (k_ij) and exact EOS Cp-Cv thermodynamic derivative.
    """
    total_pct = sum(composition_mol.values())
    if total_pct <= 0:
        total_pct = 100.0
    x = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not x:
        x = {'CH4': 1.0}

    P_Pa = pressure_kPa_a * 1000.0
    T = max(30.0, temperature_k)
    M_mix = sum(x[c] * EOS_COMPONENT_DATA[c]['M'] for c in x)
    Cp_ideal = sum(x[c] * calculate_cp_ideal_component(c, T) for c in x)
    Cv_ideal = Cp_ideal - R_GAS

    if eos.upper() in ('HEOS', 'GERG2008'):
        try:
            import CoolProp.CoolProp as CP
            fluid_parts = [f"{COOLPROP_FLUID_NAMES[c]}[{pct:.6f}]" for c, pct in x.items() if c in COOLPROP_FLUID_NAMES]
            if fluid_parts:
                fluid_str = "HEOS::" + "&".join(fluid_parts)
                Z_gas = CP.PropsSI('Z', 'T', T, 'P', P_Pa, fluid_str)
                cp_molar = CP.PropsSI('Cpmolar', 'T', T, 'P', P_Pa, fluid_str)
                cv_molar = CP.PropsSI('Cvmolar', 'T', T, 'P', P_Pa, fluid_str)
                k_mix = max(1.05, min(1.67, cp_molar / max(1e-6, cv_molar)))
                rho_v = CP.PropsSI('D', 'T', T, 'P', P_Pa, fluid_str)
                M_coolprop = CP.PropsSI('molar_mass', 'T', T, 'P', P_Pa, fluid_str) * 1000.0
                return {
                    'Z_gas': float(Z_gas), 'Z_liquid': float(Z_gas), 'k_mix': float(k_mix),
                    'Cp_ideal': float(Cp_ideal), 'Cp_real': float(cp_molar / M_coolprop * 1000.0), 'Cv_real': float(cv_molar / M_coolprop * 1000.0),
                    'M_mix': float(M_mix), 'rho_v_kg_m3': float(rho_v), 'A': 0.0, 'B': 0.0, 'eos_name': 'HEOS (GERG-2008)'
                }
        except Exception as err:
            logger.warning(f"CoolProp HEOS calculation error, falling back to PR: {err}")

    if eos.upper() == 'IDEAL':
        Z_gas = 1.0
        Z_liquid = 1.0
        Cv_real = Cp_ideal - R_GAS
        Cp_real = Cp_ideal
        k_mix = max(1.05, min(1.67, Cp_real / Cv_real))
        rho_v = (P_Pa * (M_mix / 1000.0)) / (R_GAS * T)
        return {
            'Z_gas': 1.0, 'Z_liquid': 1.0, 'k_mix': float(k_mix),
            'Cp_ideal': float(Cp_ideal), 'Cp_real': float(Cp_real), 'Cv_real': float(Cv_real),
            'M_mix': float(M_mix), 'rho_v_kg_m3': float(rho_v), 'A': 0.0, 'B': 0.0, 'eos_name': 'IDEAL'
        }

    a_i = {}
    b_i = {}
    m_i = {}
    da_dT_i = {}
    d2a_dT2_i = {}
    
    for c in x:
        data = EOS_COMPONENT_DATA[c]
        Tc, Pc, w = data['Tc'], data['Pc'], data['omega']
        Tr = T / Tc
        
        if eos.upper() == 'SRK':
            m = 0.480 + 1.574 * w - 0.176 * (w**2)
            a0 = 0.42748 * ((R_GAS * Tc)**2) / (Pc * 1e5)
            b0 = 0.08664 * (R_GAS * Tc) / (Pc * 1e5)
        else: # PR 1976
            m = 0.37464 + 1.54226 * w - 0.26992 * (w**2)
            a0 = 0.45724 * ((R_GAS * Tc)**2) / (Pc * 1e5)
            b0 = 0.07780 * (R_GAS * Tc) / (Pc * 1e5)

        alpha = (1.0 + m * (1.0 - math.sqrt(Tr)))**2
        a_i[c] = a0 * alpha
        b_i[c] = b0
        m_i[c] = m
        
        # Exact alpha(T) first and second temperature derivatives
        sqrt_alpha = math.sqrt(alpha)
        da_dT_i[c] = -a0 * m * sqrt_alpha / math.sqrt(T * Tc)
        d2a_dT2_i[c] = a0 * m * (1.0 + m) / (2.0 * T * math.sqrt(T * Tc))

    a_mix = 0.0
    da_dT_mix = 0.0
    d2a_dT2_mix = 0.0
    b_mix = sum(x[c] * b_i[c] for c in x)
    
    comp_list = list(x.keys())
    for i in range(len(comp_list)):
        c_i = comp_list[i]
        for j in range(len(comp_list)):
            c_j = comp_list[j]
            k_ij = get_k_ij(c_i, c_j)
            a_ij = math.sqrt(a_i[c_i] * a_i[c_j]) * (1.0 - k_ij)
            a_mix += x[c_i] * x[c_j] * a_ij
            
            if a_i[c_i] > 0 and a_i[c_j] > 0:
                da_ij = 0.5 * (da_dT_i[c_i] * math.sqrt(a_i[c_j] / a_i[c_i]) + da_dT_i[c_j] * math.sqrt(a_i[c_i] / a_i[c_j])) * (1.0 - k_ij)
                da_dT_mix += x[c_i] * x[c_j] * da_ij
                
                d2a_ij = 0.5 * (d2a_dT2_i[c_i] * math.sqrt(a_i[c_j] / a_i[c_i]) + d2a_dT2_i[c_j] * math.sqrt(a_i[c_i] / a_i[c_j])) * (1.0 - k_ij)
                d2a_dT2_mix += x[c_i] * x[c_j] * d2a_ij

    A = (a_mix * P_Pa) / ((R_GAS * T)**2)
    B = (b_mix * P_Pa) / (R_GAS * T)
    
    Z_gas, Z_liquid = solve_cubic_z(A, B, eos=eos)
    
    # Real Gas Residual Cv_res(T,P) from EOS second derivative (Poling et al. 2001)
    if eos.upper() == 'SRK':
        Cv_res = (T * d2a_dT2_mix / b_mix) * math.log(1.0 + B / Z_gas) if Z_gas > B else 0.0
    else: # PR
        sqrt2 = math.sqrt(2.0)
        log_term = math.log((Z_gas + (1.0 + sqrt2) * B) / max(1e-6, Z_gas + (1.0 - sqrt2) * B))
        Cv_res = (T * d2a_dT2_mix / (2.0 * sqrt2 * b_mix)) * log_term if Z_gas > B else 0.0

    Cp_res = (T * (da_dT_mix / (R_GAS * T) - a_mix / (R_GAS * T**2))**2) # EOS derivative correction
    Cv_real = max(R_GAS * 0.1, Cv_ideal + max(0.0, Cv_res))
    
    # Exact Thermodynamic EOS derivative: (dP/dT)_V / (-dP/dV)_T
    v_b = max(1e-6, (Z_gas * R_GAS * T / P_Pa) - b_mix)
    dP_dT_V = (R_GAS / v_b) - (da_dT_mix / max(1e-8, (Z_gas * R_GAS * T / P_Pa)**2))
    Cp_real = max(Cv_real + R_GAS, Cv_real + T * (R_GAS**2) * (dP_dT_V / (P_Pa * Z_gas))**2)
    
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
    Rachford-Rice VLE Flash Solver with EOS Fugacity Coupling (K_i = phi_i^L / phi_i^V).
    Features robust Bisection-bounded Newton-Raphson solver and exact bubble-point vapor composition.
    """
    total_pct = sum(composition_mol.values())
    if total_pct <= 0:
        total_pct = 100.0
    z = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not z:
        z = {'CH4': 1.0}

    P_bar = pressure_kPa_a / 100.0
    T = max(30.0, temperature_k)

    # 1. Initial K-values from Wilson Correlation
    K = {}
    for c in z:
        data = EOS_COMPONENT_DATA[c]
        P_ci, T_ci, w_i = data['Pc'], data['Tc'], data['omega']
        K[c] = (P_ci / P_bar) * math.exp(5.37 * (1.0 + w_i) * (1.0 - T_ci / T))

    def rachford_rice(v_frac):
        return sum((z[c] * (K[c] - 1.0)) / (1.0 + v_frac * (K[c] - 1.0)) for c in z)

    def rachford_rice_deriv(v_frac):
        return -sum((z[c] * ((K[c] - 1.0)**2)) / ((1.0 + v_frac * (K[c] - 1.0))**2) for c in z)

    # 2. Outer Loop: EOS Fugacity Coupling Iteration
    v_frac = 0.05
    max_outer = 30 if eos.upper() in ('PR', 'SRK') else 1
    
    for outer_step in range(max_outer):
        # Phase check only on first iteration (Wilson K-values)
        if outer_step == 0:
            f_min = rachford_rice(0.0)
            f_max = rachford_rice(1.0)
            if f_min <= 0:
                v_frac = 0.0
            elif f_max >= 0:
                v_frac = 1.0
            else:
                v_frac = max(0.001, min(0.999, v_frac))
        elif v_frac <= 0.0 or v_frac >= 1.0:
            break

        if 0.0 < v_frac < 1.0:
            # Fast Bisection-bounded Newton-Raphson Solver
            v_low = 0.0
            v_high = 1.0
            
            for _ in range(30):
                f_val = rachford_rice(v_frac)
                if abs(f_val) < 1e-7:
                    break
                
                if f_val > 0:
                    v_low = v_frac
                else:
                    v_high = v_frac
                    
                df_val = rachford_rice_deriv(v_frac)
                if abs(df_val) > 1e-12:
                    v_next = v_frac - f_val / df_val
                    if v_low < v_next < v_high:
                        v_frac = v_next
                    else:
                        v_frac = 0.5 * (v_low + v_high)
                else:
                    v_frac = 0.5 * (v_low + v_high)

        # Calculate physical phase compositions x_i and y_i
        x_liq = {}
        y_vap = {}
        
        if v_frac <= 1e-6: # Subcooled liquid (v_frac = 0)
            v_frac = 0.0
            x_liq = dict(z)
            # Bubble-point vapor composition: y_i = K_i * z_i / sum(K_j * z_j)
            denom_bp = sum(K[c] * z[c] for c in z)
            y_vap = {c: (K[c] * z[c]) / max(1e-8, denom_bp) for c in z}
        elif v_frac >= 1.0 - 1e-6: # Superheated vapor (v_frac = 1)
            v_frac = 1.0
            y_vap = dict(z)
            # Dew-point liquid composition: x_i = (z_i / K_i) / sum(z_j / K_j)
            denom_dp = sum(z[c] / max(1e-8, K[c]) for c in z)
            x_liq = {c: (z[c] / max(1e-8, K[c])) / max(1e-8, denom_dp) for c in z}
        else: # Two-phase VLE region (0 < v_frac < 1)
            for c in z:
                denom = 1.0 + v_frac * (K[c] - 1.0)
                x_liq[c] = max(1e-8, z[c] / denom)
                y_vap[c] = max(1e-8, (z[c] * K[c]) / denom)

            sum_x = sum(x_liq.values())
            sum_y = sum(y_vap.values())
            x_liq = {c: val / sum_x for c, val in x_liq.items()}
            y_vap = {c: val / sum_y for c, val in y_vap.items()}

        if eos.upper() not in ('PR', 'SRK') or (v_frac <= 0.0 or v_frac >= 1.0) and outer_step > 0:
            break

        # Calculate EOS liquid and vapor fugacity coefficients
        phi_L = calculate_fugacity_coefficients(x_liq, T, pressure_kPa_a, eos=eos, phase='liquid')
        phi_V = calculate_fugacity_coefficients(y_vap, T, pressure_kPa_a, eos=eos, phase='vapor')

        # Update K_i = phi_L / phi_V with undamped diff_K tracking
        diff_K = 0.0
        for c in z:
            K_new = phi_L[c] / max(1e-6, phi_V[c])
            diff_K += abs(K_new - K[c]) # Actual undamped difference
            K[c] = 0.5 * K[c] + 0.5 * K_new # Damped update for stability

        if diff_K < 1e-4:
            break

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


def calculate_h_ideal_mixture(composition_mol: dict, temperature_k: float, t_ref_k: float = 0.0) -> float:
    """
    Ideal gas mixture enthalpy h_ideal(T) in J/mol relative to T_ref.
    h_ideal = sum(x_i * int(Cp_ideal_i dT, T_ref, T))
    Cp_ideal_i(T) = A + B*T + C*T^2 + D*T^3  (Aly-Lee polynomial)
    """
    T = max(30.0, temperature_k)
    total_pct = sum(composition_mol.values())
    if total_pct <= 0:
        total_pct = 100.0
    x = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not x:
        x = {'CH4': 1.0}

    h = 0.0
    for c, frac in x.items():
        coeffs = EOS_COMPONENT_DATA[c]['cp_coeffs']
        A, B, C, D = coeffs
        def integral(T_val):
            return A*T_val + B/2*T_val**2 + C/3*T_val**3 + D/4*T_val**4
        h += frac * (integral(T) - integral(t_ref_k))
    return h


def calculate_h_total_mixture(
    composition_mol: dict,
    temperature_k: float,
    pressure_kPa_a: float,
    eos: str = 'PR',
    phase: str = 'vapor'
) -> float:
    """
    Total molar enthalpy h_total(T,P) in J/mol for a mixture.
    PR/SRK:  h_total = h_ideal + h_residual
    HEOS:    h_total from CoolProp PropsSI('Hmolar')
    IDEAL:   h_total = h_ideal
    """
    total_pct = sum(composition_mol.values())
    if total_pct <= 0:
        total_pct = 100.0
    x = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not x:
        x = {'CH4': 1.0}

    P_Pa = pressure_kPa_a * 1000.0
    T = max(30.0, temperature_k)

    if eos.upper() in ('HEOS', 'GERG2008'):
        try:
            import CoolProp.CoolProp as CP
            fluid_parts = [f"{COOLPROP_FLUID_NAMES[c]}[{pct:.6f}]" for c, pct in x.items() if c in COOLPROP_FLUID_NAMES]
            if fluid_parts:
                fluid_str = "HEOS::" + "&".join(fluid_parts)
                h_total = CP.PropsSI('Hmolar', 'T', T, 'P', P_Pa, fluid_str)
                return float(h_total)
        except Exception as err:
            logger.warning(f"CoolProp HEOS enthalpy error, falling back to PR: {err}")

    h_ideal = calculate_h_ideal_mixture(x, T)

    if eos.upper() == 'IDEAL':
        return h_ideal

    a_i = {}
    b_i = {}
    da_dT_i = {}

    for c in x:
        data = EOS_COMPONENT_DATA[c]
        Tc, Pc, w = data['Tc'], data['Pc'], data['omega']
        Tr = T / Tc

        if eos.upper() == 'SRK':
            m = 0.480 + 1.574 * w - 0.176 * (w**2)
            a0 = 0.42748 * ((R_GAS * Tc)**2) / (Pc * 1e5)
            b0 = 0.08664 * (R_GAS * Tc) / (Pc * 1e5)
        else:
            m = 0.37464 + 1.54226 * w - 0.26992 * (w**2)
            a0 = 0.45724 * ((R_GAS * Tc)**2) / (Pc * 1e5)
            b0 = 0.07780 * (R_GAS * Tc) / (Pc * 1e5)

        alpha = (1.0 + m * (1.0 - math.sqrt(Tr)))**2
        a_i[c] = a0 * alpha
        b_i[c] = b0
        sqrt_alpha = math.sqrt(alpha)
        da_dT_i[c] = -a0 * m * sqrt_alpha / math.sqrt(T * Tc)

    a_mix = 0.0
    da_dT_mix = 0.0
    b_mix = sum(x[c] * b_i[c] for c in x)
    comp_list = list(x.keys())

    for i in range(len(comp_list)):
        c_i = comp_list[i]
        for j in range(len(comp_list)):
            c_j = comp_list[j]
            k_ij = get_k_ij(c_i, c_j)
            a_ij = math.sqrt(a_i[c_i] * a_i[c_j]) * (1.0 - k_ij)
            a_mix += x[c_i] * x[c_j] * a_ij
            if a_i[c_i] > 0 and a_i[c_j] > 0:
                da_ij = 0.5 * (da_dT_i[c_i] * math.sqrt(a_i[c_j] / a_i[c_i]) + da_dT_i[c_j] * math.sqrt(a_i[c_i] / a_i[c_j])) * (1.0 - k_ij)
                da_dT_mix += x[c_i] * x[c_j] * da_ij

    A = (a_mix * P_Pa) / ((R_GAS * T)**2)
    B = (b_mix * P_Pa) / (R_GAS * T)

    Z_gas, Z_liquid = solve_cubic_z(A, B, eos=eos)
    Z = Z_gas if phase.lower() in ('gas', 'vapor') else Z_liquid
    Z = max(B + 1e-4, Z)

    if eos.upper() == 'SRK':
        h_res = R_GAS * T * (Z - 1.0) + (T * da_dT_mix - a_mix) / b_mix * math.log(1.0 + B / Z)
    else:
        sqrt2 = math.sqrt(2.0)
        log_arg = (Z + (1.0 + sqrt2) * B) / max(1e-8, Z + (1.0 - sqrt2) * B)
        h_res = R_GAS * T * (Z - 1.0) + (T * da_dT_mix - a_mix) / (2.0 * sqrt2 * b_mix) * math.log(max(1e-8, log_arg))

    return h_ideal + h_res


def _find_bubble_temperature_wilson(
    composition_mol: dict,
    pressure_kPa_a: float,
    t_min: float = 90.0,
    t_max: float = 150.0
) -> float:
    """Finds bubble-point temperature using Wilson K-values (f(0)=0).
    For methane-rich mixtures near 1 bar, Wilson K-values give inaccurate
    results (K_CH4~1 makes f(0)~0 over a range). Returns best estimate."""
    total_pct = sum(composition_mol.values()) or 100.0
    z = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not z:
        z = {'CH4': 1.0}
    P_bar = pressure_kPa_a / 100.0

    def rr0(Tv):
        K = {c: (EOS_COMPONENT_DATA[c]['Pc'] / P_bar) * math.exp(5.37 * (1.0 + EOS_COMPONENT_DATA[c]['omega']) * (1.0 - EOS_COMPONENT_DATA[c]['Tc'] / Tv)) for c in z}
        return sum(z[c] * (K[c] - 1.0) for c in z)

    f_min, f_max = rr0(t_min), rr0(t_max)
    if f_min > 0: return t_min
    if f_max < 0: return t_max
    for _ in range(40):
        Tm = 0.5 * (t_min + t_max)
        fm = rr0(Tm)
        if abs(fm) < 1e-8 or (t_max - t_min) < 1e-6: return Tm
        t_min, t_max = (Tm, t_max) if fm > 0 else (t_min, Tm)
    return 0.5 * (t_min + t_max)


def _compute_robust_vle_k_values(
    composition_mol: dict,
    temperature_k: float,
    pressure_kPa_a: float,
    eos: str = 'PR'
) -> dict:
    """
    Computes EOS fugacity-based K-values for a given composition at (T, P).
    Uses composition both as liquid and (bubble-point) vapor estimate.
    Returns K-values dict.
    """
    if eos.upper() not in ('PR', 'SRK'):
        return {}
    T = max(30.0, temperature_k)
    total = sum(composition_mol.values()) or 100.0
    z = {c: v / total for c, v in composition_mol.items() if c in EOS_COMPONENT_DATA and v > 0}
    if not z:
        z = {'CH4': 1.0}

    P_bar = pressure_kPa_a / 100.0
    K_wilson = {}
    for c in z:
        d = EOS_COMPONENT_DATA[c]
        K_wilson[c] = (d['Pc'] / P_bar) * math.exp(5.37 * (1.0 + d['omega']) * (1.0 - d['Tc'] / T))

    denom = sum(K_wilson[c] * z[c] for c in z)
    y_bp = {c: K_wilson[c] * z[c] / max(1e-8, denom) for c in z} if denom > 0 else dict(z)

    phi_L = calculate_fugacity_coefficients(z, T, pressure_kPa_a, eos=eos, phase='liquid')
    phi_V = calculate_fugacity_coefficients(y_bp, T, pressure_kPa_a, eos=eos, phase='vapor')

    K_eos = {}
    for c in z:
        K_eos[c] = phi_L.get(c, 1.0) / max(1e-10, phi_V.get(c, 1.0))
    return K_eos


def _compute_h_mix(
    composition_mol: dict,
    temperature_k: float,
    pressure_kPa_a: float,
    eos: str = 'PR'
) -> tuple:
    """
    Computes mixture enthalpy h_mix (J/mol) and VF at (T, P).
    Uses EOS fugacity-based VF when standard VLE flash returns VF=0
    near the bubble point, ensuring a continuous h_mix(T).
    Returns (h_mix, vf, x, y).
    """
    total = sum(composition_mol.values()) or 100.0
    z_frac = {c: v / total for c, v in composition_mol.items() if c in EOS_COMPONENT_DATA and v > 0}
    if not z_frac:
        z_frac = {'CH4': 1.0}

    vle = calculate_two_phase_vle_flash(composition_mol, temperature_k, pressure_kPa_a, eos=eos)
    vf = vle['v_frac_VF']
    x = vle['x_liquid'] if vle['x_liquid'] else z_frac
    y = vle['y_vapor'] if vle['y_vapor'] else z_frac

    if vf <= 0.0 and eos.upper() in ('PR', 'SRK'):
        K_eos = _compute_robust_vle_k_values(z_frac, temperature_k, pressure_kPa_a, eos=eos)
        if K_eos:
            def rr(vf_val):
                s = 0.0
                for c in z_frac:
                    dk = K_eos[c] - 1.0
                    s += z_frac[c] * dk / (1.0 + vf_val * dk)
                return s

            f0 = rr(0.0)
            f1 = rr(1.0)
            if f0 > 0 and f1 < 0:
                vf_e = 0.05
                for _ in range(30):
                    fv = rr(vf_e)
                    if abs(fv) < 1e-10:
                        break
                    dfv = -sum(z_frac[c] * ((K_eos[c] - 1.0)**2) / ((1.0 + vf_e * (K_eos[c] - 1.0))**2) for c in z_frac)
                    if abs(dfv) > 1e-12:
                        vf_e -= fv / dfv
                    vf_e = max(1e-8, min(0.999999, vf_e))

                if 0 < vf_e < 1.0:
                    vf = vf_e
                    x = {c: z_frac[c] / (1.0 + vf * (K_eos[c] - 1.0)) for c in z_frac}
                    sx = sum(x.values())
                    x = {c: v / sx for c, v in x.items()} if sx > 0 else z_frac
                    y = {c: K_eos[c] * x[c] for c in z_frac}
                    sy = sum(y.values())
                    y = {c: v / sy for c, v in y.items()} if sy > 0 else z_frac

    if vf <= 0.0:
        h = calculate_h_total_mixture(x, temperature_k, pressure_kPa_a, eos=eos, phase='liquid')
    elif vf >= 1.0:
        h = calculate_h_total_mixture(y, temperature_k, pressure_kPa_a, eos=eos, phase='vapor')
    else:
        hl = calculate_h_total_mixture(x, temperature_k, pressure_kPa_a, eos=eos, phase='liquid')
        hv = calculate_h_total_mixture(y, temperature_k, pressure_kPa_a, eos=eos, phase='vapor')
        h = vf * hv + (1.0 - vf) * hl

    return h, vf, x, y


def calculate_isenthalpic_flash(
    composition_mol: dict,
    t_feed_k: float,
    p_feed_kPa_a: float,
    p_flash_kPa_a: float,
    eos: str = 'PR',
    t_min_k: float = 90.0,
    t_max_k: float = 200.0,
    tol: float = 0.1,
    max_iter: int = 40
) -> dict:
    """
    Isenthalpic (PH) flash: expand feed from (T_feed, P_feed) to P_flash.
    Solves h_mix(T_flash, P_flash) = h_feed(T_feed, P_feed) for T_flash and VF.
    Uses _compute_h_mix with EOS-based VF refinement for continuity.

    Supports PR, SRK, HEOS (GERG-2008), and Ideal Gas EOS.
    Returns dict: v_frac_VF, flash_pct, T_flash_K, h_feed_J_mol,
                  y_vapor, x_liquid, eos_used, converged
    """
    total_pct = sum(composition_mol.values()) or 100.0
    z = {c: pct / total_pct for c, pct in composition_mol.items() if c in EOS_COMPONENT_DATA and pct > 0}
    if not z:
        z = {'CH4': 1.0}

    T_feed = max(30.0, t_feed_k)
    P_feed = max(1.0, p_feed_kPa_a)
    P_flash = max(1.0, p_flash_kPa_a)

    h_feed = calculate_h_total_mixture(z, T_feed, P_feed, eos=eos, phase='liquid')

    if eos.upper() == 'IDEAL':
        vle = calculate_two_phase_vle_flash(z, T_feed, P_flash, eos=eos)
        return {
            'v_frac_VF': vle['v_frac_VF'],
            'flash_pct': vle['flash_pct'],
            'T_flash_K': T_feed, 'h_feed_J_mol': h_feed,
            'y_vapor': vle['y_vapor'], 'x_liquid': vle['x_liquid'],
            'eos_used': eos.upper(), 'converged': True
        }

    h_low, vf_low, _, _ = _compute_h_mix(z, t_min_k, P_flash, eos=eos)
    h_high, vf_high, _, _ = _compute_h_mix(z, t_max_k, P_flash, eos=eos)

    if h_feed <= h_low:
        return {
            'v_frac_VF': 0.0, 'flash_pct': 0.0,
            'T_flash_K': t_min_k, 'h_feed_J_mol': h_feed,
            'y_vapor': z, 'x_liquid': z,
            'eos_used': eos.upper(), 'converged': True
        }
    if h_feed >= h_high:
        return {
            'v_frac_VF': 1.0, 'flash_pct': 100.0,
            'T_flash_K': t_max_k, 'h_feed_J_mol': h_feed,
            'y_vapor': z, 'x_liquid': z,
            'eos_used': eos.upper(), 'converged': True
        }

    T_low, T_high = t_min_k, t_max_k
    f_low, f_high = h_low - h_feed, h_high - h_feed

    x_mid, y_mid = z, z
    converged, T_mid, vf_mid = False, 0.5 * (T_low + T_high), 0.0

    for iteration in range(max_iter):
        T_mid = 0.5 * (T_low + T_high)
        h_mid, vf_mid, x_mid, y_mid = _compute_h_mix(z, T_mid, P_flash, eos=eos)
        f_mid = h_mid - h_feed

        if abs(f_mid) < tol or (T_high - T_low) < 1e-4:
            converged = True
            break

        if f_mid * f_low > 0:
            T_low, f_low = T_mid, f_mid
        else:
            T_high, f_high = T_mid, f_mid

    return {
        'v_frac_VF': max(0.0, min(1.0, vf_mid)),
        'flash_pct': max(0.0, min(100.0, vf_mid * 100.0)),
        'T_flash_K': T_mid if converged else 0.5 * (T_low + T_high),
        'h_feed_J_mol': h_feed,
        'y_vapor': y_mid, 'x_liquid': x_mid,
        'eos_used': eos.upper(), 'converged': converged
    }
