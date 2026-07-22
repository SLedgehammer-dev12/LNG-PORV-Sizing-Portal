"""
Unit Conversion Test Suite
Tests conversions for Pressure, Volumetric Flow, Mass Flow, Volume, Temperature, Density, and Area.
"""

import pytest
from unit_converter import (
    convert_pressure_to_mbar,
    convert_volumetric_flow_to_m3_h,
    convert_mass_flow_to_kg_h,
    convert_volume_to_m3,
    convert_temperature_to_kelvin,
    convert_density_to_kg_m3,
    convert_area_from_mm2
)

def test_pressure_conversion():
    assert convert_pressure_to_mbar(1.0, 'bar_a') == 1000.0
    assert convert_pressure_to_mbar(100.0, 'kPa_a') == 1000.0
    assert convert_pressure_to_mbar(1000.0, 'mbar_a') == 1000.0
    assert convert_pressure_to_mbar(240.0, 'mbar_g', is_gauge=True) == 240.0
    assert convert_pressure_to_mbar(0.24, 'bar_g', is_gauge=True) == 240.0

def test_volumetric_flow_conversion():
    assert convert_volumetric_flow_to_m3_h(1.0, 'm³/s') == 3600.0
    assert convert_volumetric_flow_to_m3_h(10000.0, 'm³/h') == 10000.0
    assert convert_volumetric_flow_to_m3_h(100.0, 'GPM (US)') > 20.0

def test_mass_flow_conversion():
    assert convert_mass_flow_to_kg_h(1.0, 'kg/s') == 3600.0
    assert convert_mass_flow_to_kg_h(1.0, 't/h (ton/h)') == 1000.0
    assert convert_mass_flow_to_kg_h(115270.0, 'kg/h') == 115270.0

def test_temperature_conversion():
    assert convert_temperature_to_kelvin(-155.0, '°C') == pytest.approx(118.15, abs=1e-4)
    assert convert_temperature_to_kelvin(118.15, 'K') == 118.15
    assert convert_temperature_to_kelvin(-247.0, '°F') == pytest.approx(118.15, abs=0.2)

def test_density_conversion():
    assert convert_density_to_kg_m3(0.471, 'g/cm³') == 471.0
    assert convert_density_to_kg_m3(471.0, 'kg/m³') == 471.0

def test_area_conversion():
    assert convert_area_from_mm2(645.16, 'in²') == pytest.approx(1.0, abs=1e-4)
    assert convert_area_from_mm2(100.0, 'cm²') == 1.0

if __name__ == '__main__':
    pytest.main(['-v', 'test_unit_converter.py'])
