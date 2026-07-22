"""
PSV Manufacturer Database Search and Matching Engine
Searches commercial relief valves (Anderson Greenwood, Crosby, Consolidated, Leser, Farris, Mercer)
and matches models meeting required orifice area under specific relief conditions.
"""

import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'psv_database.json')

def load_psv_database() -> list:
    """
    Loads PSV manufacturer database from JSON file.
    """
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def search_matching_valves(
    req_orifice_area_mm2: float,
    required_air_capacity_m3_h: float = 26419.5,
    P1_kPa_a: float = 117.003,
    min_coverage_pct: float = 100.0,
    cryogenic_only: bool = True
) -> list:
    """
    Filters and ranks commercial valve models by coverage percentage and capacity.
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
        
        if coverage_pct >= 110.0:
            status = '🌟 TAM UYGUN (Tavsiye Edilir)'
            recommendation_level = 1
        elif coverage_pct >= min_coverage_pct:
            status = '✅ UYGUN (Sınırda Emniyetli)'
            recommendation_level = 2
        else:
            status = '❌ YETERSİZ (4+1 Vana Düzeni Veya 18" Çap Gerekir)'
            recommendation_level = 3
            
        matched_results.append({
            'id': v['id'],
            'manufacturer': v['manufacturer'],
            'series': v['series'],
            'type': v['type'],
            'dn_size': v['dn_size'],
            'orifice_area_mm2': area,
            'discharge_coeff_kd': v['discharge_coeff_kd'],
            'capacity_m3_h': capacity_m3_h,
            'coverage_pct': coverage_pct,
            'status': status,
            'recommendation_level': recommendation_level,
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
