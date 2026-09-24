"""
Unit Conversion Test Suite
Tests conversions for Pressure, Volumetric Flow, Mass Flow, Volume, Temperature, Density, and Area.
"""

import pytest

from unit_converter import (
    convert_area_from_mm2,
    convert_density_to_kg_m3,
    convert_mass_flow_to_kg_h,
    convert_pressure_to_mbar,
    convert_temperature_to_kelvin,
    convert_volume_to_m3,
    convert_volumetric_flow_to_m3_h,
)


def test_pressure_conversion():
    assert convert_pressure_to_mbar(1.0, 'bar_a') == 1000.0
    assert convert_pressure_to_mbar(100.0, 'kPa_a') == 1000.0
    assert convert_pressure_to_mbar(1000.0, 'mbar_a') == 1000.0
    assert convert_pressure_to_mbar(240.0, 'mbar_g', is_gauge=True) == 240.0
    assert convert_pressure_to_mbar(0.24, 'bar_g', is_gauge=True) == 240.0
    assert convert_pressure_to_mbar(1.0, 'atm') == pytest.approx(1013.25, abs=1e-6)
    assert convert_pressure_to_mbar(750.0617, 'mmHg (Torr)') == pytest.approx(1000.0, abs=0.01)
    assert convert_pressure_to_mbar(1.0, 'psi_a') == pytest.approx(68.94757, abs=1e-6)
    assert convert_pressure_to_mbar(1.0, 'psi_g', is_gauge=True) == pytest.approx(68.94757, abs=1e-6)
    assert convert_pressure_to_mbar(100000.0, 'Pa_a') == 1000.0


def test_volumetric_flow_conversion():
    assert convert_volumetric_flow_to_m3_h(1.0, 'm³/s') == 3600.0
    assert convert_volumetric_flow_to_m3_h(10000.0, 'm³/h') == 10000.0
    assert convert_volumetric_flow_to_m3_h(100.0, 'GPM (US)') == pytest.approx(22.71247, abs=1e-5)
    assert convert_volumetric_flow_to_m3_h(1.0, 'm³/min') == 60.0
    assert convert_volumetric_flow_to_m3_h(1.0, 'CFM (ft³/min)') == pytest.approx(1.699011, abs=1e-6)
    assert convert_volumetric_flow_to_m3_h(24.0, 'BPD (Barrels/day)') == pytest.approx(0.1589873, abs=1e-6)


def test_mass_flow_conversion():
    assert convert_mass_flow_to_kg_h(1.0, 'kg/s') == 3600.0
    assert convert_mass_flow_to_kg_h(1.0, 't/h (ton/h)') == 1000.0
    assert convert_mass_flow_to_kg_h(115270.0, 'kg/h') == 115270.0
    assert convert_mass_flow_to_kg_h(1.0, 'lb/h') == pytest.approx(0.45359237, abs=1e-8)
    assert convert_mass_flow_to_kg_h(1.0, 'g/s') == pytest.approx(3.6, abs=1e-9)


def test_volume_conversion():
    assert convert_volume_to_m3(1.0, 'm³') == 1.0
    assert convert_volume_to_m3(1000.0, 'Litre (L)') == 1.0
    assert convert_volume_to_m3(1.0, 'Gallon (US gal)') == pytest.approx(0.00378541, abs=1e-8)
    assert convert_volume_to_m3(1.0, 'Barrel (bbl)') == pytest.approx(0.1589873, abs=1e-7)
    assert convert_volume_to_m3(1.0, 'ft³') == pytest.approx(0.02831685, abs=1e-8)


def test_temperature_conversion():
    assert convert_temperature_to_kelvin(-155.0, '°C') == pytest.approx(118.15, abs=1e-4)
    assert convert_temperature_to_kelvin(118.15, 'K') == 118.15
    assert convert_temperature_to_kelvin(-247.0, '°F') == pytest.approx(118.15, abs=0.2)
    assert convert_temperature_to_kelvin(212.67, '°R') == pytest.approx(118.15, abs=1e-2)
    assert convert_temperature_to_kelvin(0.0, 'Celsius') == pytest.approx(273.15, abs=1e-9)


def test_density_conversion():
    assert convert_density_to_kg_m3(0.471, 'g/cm³') == 471.0
    assert convert_density_to_kg_m3(471.0, 'kg/m³') == 471.0
    assert convert_density_to_kg_m3(1.0, 'lb/ft³') == pytest.approx(16.018463, abs=1e-6)


def test_area_conversion():
    assert convert_area_from_mm2(645.16, 'in²') == pytest.approx(1.0, abs=1e-4)
    assert convert_area_from_mm2(100.0, 'cm²') == 1.0
    assert convert_area_from_mm2(1e6, 'm²') == 1.0
    assert convert_area_from_mm2(500.0, 'mm²') == 500.0


if __name__ == '__main__':
    pytest.main(['-v', 'test_unit_converter.py'])
