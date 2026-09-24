"""
PSV Manufacturer Database Search and Matching Engine
Searches commercial relief valves (Anderson Greenwood, Crosby, Consolidated, Leser, Farris, Mercer)
and matches models meeting required orifice area under specific relief conditions.
"""

import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

REQUIRED_VALVE_FIELDS = {
    'id': str,
    'manufacturer': str,
    'series': str,
    'type': str,
    'dn_size': str,
    'orifice_area_mm2': (int, float),
    'discharge_coeff_kd': (int, float),
    'cryogenic_certified': bool,
}


def get_db_path():
    """ Resolves path to psv_database.json for both standard execution and PyInstaller sys._MEIPASS """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'psv_database.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'psv_database.json')


DB_PATH = get_db_path()


def validate_psv_database(raw_data) -> tuple:
    """
    Validates the raw PSV database against the expected schema.
    Returns (valid_entries, errors). Invalid entries are dropped with a logged error.
    """
    errors = []
    if not isinstance(raw_data, list):
        return [], ["Veritabanı kök elemanı liste değil."]

    valid = []
    seen_ids = set()
    for idx, entry in enumerate(raw_data):
        if not isinstance(entry, dict):
            errors.append(f"Kayıt #{idx}: sözlük değil.")
            continue

        missing = [f for f in REQUIRED_VALVE_FIELDS if f not in entry]
        if missing:
            errors.append(f"Kayıt #{idx} ({entry.get('id', '?')}): eksik alanlar {missing}.")
            continue

        type_errors = [
            f for f, t in REQUIRED_VALVE_FIELDS.items()
            if not isinstance(entry[f], t) or isinstance(entry[f], bool) and t is not bool
        ]
        if type_errors:
            errors.append(f"Kayıt #{idx} ({entry.get('id', '?')}): tip hataları {type_errors}.")
            continue

        if entry['orifice_area_mm2'] <= 0:
            errors.append(f"Kayıt #{idx} ({entry['id']}): orifis alanı pozitif değil.")
            continue
        if not (0.3 <= entry['discharge_coeff_kd'] <= 1.0):
            errors.append(f"Kayıt #{idx} ({entry['id']}): Kd 0.3-1.0 aralığı dışında.")
            continue
        if entry['id'] in seen_ids:
            errors.append(f"Kayıt #{idx}: tekrarlanan id '{entry['id']}'.")
            continue

        seen_ids.add(entry['id'])
        valid.append(entry)

    return valid, errors


def load_psv_database() -> list:
    """
    Loads PSV manufacturer database from JSON file with schema validation and error protection.
    Returns [] if the file is missing/corrupted (errors are logged).
    """
    db_file = get_db_path()
    if not os.path.exists(db_file):
        logger.error(f"PSV veritabanı bulunamadı: {db_file}")
        return []
    try:
        with open(db_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception as err:
        logger.error(f"PSV veritabanı okunamadı: {err}")
        return []

    valid, errors = validate_psv_database(raw)
    for err in errors:
        logger.warning(f"PSV veritabanı şema uyarısı: {err}")
    return valid


def search_matching_valves(
    req_orifice_area_mm2: float = None,
    required_air_capacity_m3_h: float = None,
    P1_kPa_a: float = 117.003,
    P2_kPa_a: float = 90.603,
    min_coverage_pct: float = 100.0,
    max_coverage_pct: float = 200.0,
    cryogenic_only: bool = True,
    show_all_above_90: bool = False
) -> list:
    """
    Filters and ranks commercial valve models by API 520 Part I air capacity coverage.

    The required air capacity may be given directly (required_air_capacity_m3_h) or
    derived from the required effective orifice area (req_orifice_area_mm2) at the
    same relieving pressures.

    If show_all_above_90 is True, includes models with 90.0% <= coverage_pct <= max_coverage_pct.
    Valves with coverage_pct > max_coverage_pct (oversized >200%) are filtered out by default.
    """
    from psv_sizing import calculate_valve_air_capacity_m3_h

    valves = load_psv_database()

    if required_air_capacity_m3_h is None:
        if req_orifice_area_mm2 is None:
            raise ValueError("required_air_capacity_m3_h veya req_orifice_area_mm2 verilmelidir.")
        required_air_capacity_m3_h = calculate_valve_air_capacity_m3_h(
            req_orifice_area_mm2, P1_kPa_a, P2_kPa_a, K_d=0.85
        )
    required_air_capacity_m3_h = max(1e-9, required_air_capacity_m3_h)

    matched_results = []

    for v in valves:
        if cryogenic_only and not v.get('cryogenic_certified', False):
            continue

        area = v['orifice_area_mm2']
        kd_val = v.get('discharge_coeff_kd', 0.85)
        capacity_m3_h = calculate_valve_air_capacity_m3_h(area, P1_kPa_a, P2_kPa_a, K_d=kd_val)
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
            'discharge_coeff_kd': kd_val,
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
                kd_val = v.get('discharge_coeff_kd', 0.85)
                capacity_m3_h = calculate_valve_air_capacity_m3_h(area, P1_kPa_a, P2_kPa_a, K_d=kd_val)
                cov = (capacity_m3_h / required_air_capacity_m3_h) * 100.0
                matched_results.append({
                    'id': v['id'],
                    'manufacturer': v['manufacturer'],
                    'series': v['series'],
                    'type': v['type'],
                    'dn_size': v['dn_size'],
                    'orifice_area_mm2': area,
                    'discharge_coeff_kd': kd_val,
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
    res = search_matching_valves(required_air_capacity_m3_h=26419.5, P1_kPa_a=117.003, P2_kPa_a=90.603)
    print(f"Matched Valves Count: {len(res)}")
    for r in res:
        print(f"[{r['status']}] {r['manufacturer']} - {r['series']} ({r['dn_size']}) -> {r['coverage_pct']:.1f}%")
