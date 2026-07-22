"""
Unit Conversion Module for LNG PSV Relief Sizing Application
Provides dynamic unit conversion functions for Pressure, Flow Rates, Volume, Temperature, Density, and Area.
"""

# Unit Conversion Factors to Base Internal Units:
# Base Units: Pressure -> mbar (abs or gauge), Volumetric Flow -> m3/h, Mass Flow -> kg/h, Volume -> m3, Temperature -> K, Density -> kg/m3

PRESSURE_UNITS_ABS = {
    'mbar_a': 1.0,
    'bar_a': 1000.0,
    'kPa_a': 10.0,
    'Pa_a': 0.01,
    'psi_a': 68.94757,
    'atm': 1013.25,
    'mmHg (Torr)': 1.333224
}

PRESSURE_UNITS_GAUGE = {
    'mbar_g': 1.0,
    'bar_g': 1000.0,
    'kPa_g': 10.0,
    'psi_g': 68.94757
}

VOLUMETRIC_FLOW_UNITS = {
    'm³/h': 1.0,
    'm³/s': 3600.0,
    'm³/min': 60.0,
    'GPM (US)': 0.2271247,
    'BPD (Barrels/day)': 0.00662447,
    'CFM (ft³/min)': 1.699011
}

MASS_FLOW_UNITS = {
    'kg/h': 1.0,
    'kg/s': 3600.0,
    't/h (ton/h)': 1000.0,
    'lb/h': 0.45359237,
    'g/s': 3.6
}

VOLUME_UNITS = {
    'm³': 1.0,
    'Litre (L)': 0.001,
    'Gallon (US gal)': 0.00378541,
    'Barrel (bbl)': 0.1589873,
    'ft³': 0.02831685
}

DENSITY_UNITS = {
    'kg/m³': 1.0,
    'g/cm³': 1000.0,
    'lb/ft³': 16.018463
}

AREA_UNITS = {
    'mm²': 1.0,
    'cm²': 100.0,
    'in²': 645.16,
    'm²': 1000000.0
}

def convert_pressure_to_mbar(val: float, unit: str, is_gauge: bool = False) -> float:
    """Converts pressure input from selected unit to mbar (abs or gauge)."""
    if is_gauge:
        factor = PRESSURE_UNITS_GAUGE.get(unit, 1.0)
    else:
        factor = PRESSURE_UNITS_ABS.get(unit, 1.0)
    return float(val * factor)

def convert_volumetric_flow_to_m3_h(val: float, unit: str) -> float:
    """Converts volumetric flow from selected unit to m3/h."""
    factor = VOLUMETRIC_FLOW_UNITS.get(unit, 1.0)
    return float(val * factor)

def convert_mass_flow_to_kg_h(val: float, unit: str) -> float:
    """Converts mass flow from selected unit to kg/h."""
    factor = MASS_FLOW_UNITS.get(unit, 1.0)
    return float(val * factor)

def convert_volume_to_m3(val: float, unit: str) -> float:
    """Converts volume from selected unit to m3."""
    factor = VOLUME_UNITS.get(unit, 1.0)
    return float(val * factor)

def convert_temperature_to_kelvin(val: float, unit: str) -> float:
    """Converts temperature from selected unit (°C, K, °F, °R) to Kelvin."""
    unit = unit.strip()
    if unit in ['°C', 'C', 'Celsius']:
        return float(val + 273.15)
    elif unit in ['K', 'Kelvin']:
        return float(val)
    elif unit in ['°F', 'F', 'Fahrenheit']:
        return float((val - 32.0) * (5.0 / 9.0) + 273.15)
    elif unit in ['°R', 'R', 'Rankine']:
        return float(val * (5.0 / 9.0))
    return float(val + 273.15)

def convert_density_to_kg_m3(val: float, unit: str) -> float:
    """Converts density from selected unit to kg/m3."""
    factor = DENSITY_UNITS.get(unit, 1.0)
    return float(val * factor)

def convert_area_from_mm2(val_mm2: float, target_unit: str) -> float:
    """Converts area from mm2 to target unit (mm2, cm2, in2, m2)."""
    factor = AREA_UNITS.get(target_unit, 1.0)
    return float(val_mm2 / factor)

if __name__ == '__main__':
    print("10 bar_a to mbar_a:", convert_pressure_to_mbar(10, 'bar_a'))
    print("100 GPM to m3/h:", convert_volumetric_flow_to_m3_h(100, 'GPM (US)'))
    print("-155 °C to K:", convert_temperature_to_kelvin(-155, '°C'))
