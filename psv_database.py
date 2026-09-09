"""
PSV Manufacturer Database Search and Matching Engine
Searches commercial relief valves (Anderson Greenwood, Crosby, Consolidated, Leser, Farris, Mercer)
and matches models meeting required orifice area under specific relief conditions.
"""

import json
import os
import sys

def get_db_path():
    """ Resolves path to psv_database.json for both standard execution and PyInstaller sys._MEIPASS """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'psv_database.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'psv_database.json')

DB_PATH = get_db_path()

def load_psv_database() -> list:
    """
    Loads PSV manufacturer database from JSON file with error protection.
    """
    db_file = get_db_path()
    if os.path.exists(db_file):
        try:
            with open(db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def search_matching_valves(
    req_orifice_area_mm2: float,
    required_air_capacity_m3_h: float = 26419.5,
    P1_kPa_a: float = 117.003,
    min_coverage_pct: float = 100.0,
    max_coverage_pct: float = 200.0,
    cryogenic_only: bool = True,
    show_all_above_90: bool = False
) -> list:
    """
    Filters and ranks commercial valve models by coverage percentage and capacity.
    If show_all_above_90 is True, includes models with 90.0% <= coverage_pct <= max_coverage_pct.
    Valves with coverage_pct > max_coverage_pct (oversized >200%) are filtered out by default.
    """
    valves = load_psv_database()
    matched_results = []
    
    for v in valves:
        if cryogenic_only and not v.get('cryogenic_certified', False):
            continue
            
        area = v['orifice_area_mm2']
        # Capacity calculation proportional to standard 16"x18" (148500 mm2 -> 25380 m3/h at 117.003 kPa_a)
        # adjusted by Kd of specific valve
        kd_ratio = v.get('discharge_coeff_kd', 0.85) / 0.85
        capacity_m3_h = (area / 148500.0) * 25380.0 * (P1_kPa_a / 117.003) * kd_ratio
        
        coverage_pct = (capacity_m3_h / required_air_capacity_m3_h) * 100.0
        
        # When show_all_above_90 is requested, skip valves strictly below 90%
        if show_all_above_90 and coverage_pct < 90.0:
            continue
            
        # Filter out valves exceeding max_coverage_pct (>200% oversizing risk)
        if max_coverage_pct is not None and coverage_pct > max_coverage_pct:
            continue
        
        if coverage_pct > 200.0:
            status = '⚠️ AŞIRI BÜYÜK (>%200 Oversizing Riski)'
            recommendation_level = 5
        elif coverage_pct >= 110.0:
            status = '🌟 TAM UYGUN (Tavsiye Edilir)'
            recommendation_level = 1
        elif coverage_pct >= 100.0:
            status = '✅ UYGUN (Sınırda Emniyetli)'
            recommendation_level = 2
        elif coverage_pct >= 90.0:
            status = '⚠️ YAKIN KAPASİTE (%90-%100 Sınırda/Kritik)'
            recommendation_level = 3
        else:
            status = '❌ YETERSİZ (Kapasite Açığı Var)'
            recommendation_level = 4
            
        matched_results.append({
            'id': v['id'],
            'manufacturer': v['manufacturer'],
            'series': v['series'],
            'type': v['type'],
            'dn_size': v['dn_size'],
            'orifice_area_mm2': area,
            'discharge_coeff_kd': v.get('discharge_coeff_kd', 0.85),
            'capacity_m3_h': capacity_m3_h,
            'coverage_pct': coverage_pct,
            'status': status,
            'recommendation_level': recommendation_level,
            'standards': ", ".join(v.get('standards', [])),
            'description': v.get('description', '')
        })
        
    # If all valves exceed max_coverage_pct (e.g. extremely low flow rate),
    # provide a fallback with the smallest available valves so results are not empty
    if not matched_results and valves:
        cryo_valves = [v for v in valves if not cryogenic_only or v.get('cryogenic_certified', False)]
        if cryo_valves:
            sorted_cryo = sorted(cryo_valves, key=lambda v: v['orifice_area_mm2'])
            for v in sorted_cryo[:3]:
                area = v['orifice_area_mm2']
                kd_ratio = v.get('discharge_coeff_kd', 0.85) / 0.85
                capacity_m3_h = (area / 148500.0) * 25380.0 * (P1_kPa_a / 117.003) * kd_ratio
                cov = (capacity_m3_h / required_air_capacity_m3_h) * 100.0
                matched_results.append({
                    'id': v['id'],
                    'manufacturer': v['manufacturer'],
                    'series': v['series'],
                    'type': v['type'],
                    'dn_size': v['dn_size'],
                    'orifice_area_mm2': area,
                    'discharge_coeff_kd': v.get('discharge_coeff_kd', 0.85),
                    'capacity_m3_h': capacity_m3_h,
                    'coverage_pct': cov,
                    'status': '⚠️ AŞIRI BÜYÜK (>%200 Düşük Debi Alternatifi)',
                    'recommendation_level': 3,
                    'standards': ", ".join(v.get('standards', [])),
                    'description': v.get('description', '')
                })

    # Sort by recommendation level (1 best) then highest coverage pct
    matched_results.sort(key=lambda x: (x['recommendation_level'], -x['coverage_pct']))
    return matched_results

if __name__ == '__main__':
    res = search_matching_valves(req_orifice_area_mm2=154500.0, required_air_capacity_m3_h=26419.5, P1_kPa_a=117.003)
    print(f"Matched Valves Count: {len(res)}")
    for r in res:
        print(f"[{r['status']}] {r['manufacturer']} - {r['series']} ({r['dn_size']}) -> {r['coverage_pct']:.1f}%")
