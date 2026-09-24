"""
LNG PORV Sizing Application - Version & Update Management Module
Manages application versioning, build metadata, and remote/local update status checks.
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

CURRENT_VERSION = "1.4.0"
BUILD_DATE = "2026-09-24"
RELEASE_CHANNEL = "Stable / Production (BOTAŞ & NFPA 59A Certified)"
GITHUB_REPO = "SLedgehammer-dev12/LNG-PORV-Sizing-Portal"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

CHANGELOG_HIGHLIGHTS = [
    "v1.4.0: Vana kapasiteleri API 520 Part I fiziksel modele geçirildi (kalibre referans kaldırıldı); 16\"x18\" artık gerçek %338 kapasiteyle OVERSIZED olarak eleniyor.",
    "v1.4.0: Kriyojenik ideal gaz Cp düzeltmesi (CoolProp referans eğrileri); metan Cp0 118 K'de %23 hatalıydı, k=Cp/Cv ve izentalpik flaş düzeltildi.",
    "v1.4.0: Cp/Cv için eksakt EOS türevi uygulandı; k artık basınca duyarlı (PR/SRK).",
    "v1.4.0: Rapor veri zinciri düzeltildi (Z, M, yangın değerleri); dinamik vana tavsiyesi ve TR/EN rapor dili eklendi.",
    "v1.4.0: Yangın senaryosu ayrı %21 overpressure ve API 521 ısı akısı sabiti seçimi; Kd=1.0 matrise uygulanıyor.",
    "v1.4.0: NFPA 59A Q_a, API 520 eşdeğer orifis yöntemiyle standartlaştırıldı; Q_a ile vana kapasitesi aynı bazda.",
    "v1.4.0: Tam konfigürasyon kaydet/yükle, girdi doğrulama, port fallback, DB şema doğrulaması ve ruff/CI eklendi.",
    "v1.2.0: Vana seçim matrisinde aşırı boyutlandırılmış vanalar filtrelendi; %90-%200 ve %100-%200 filtreleme.",
    "v1.1.0: İzentalpik PH-Flash (Joule-Thomson h1=h2) genleşme motoru ve EOS entalpi modeli eklendi.",
]

def parse_version_tuple(ver_str: str) -> tuple:
    cleaned = ver_str.strip().lstrip("v").lstrip("V")
    parts = []
    for p in cleaned.split("."):
        num_part = ""
        for ch in p:
            if ch.isdigit():
                num_part += ch
            else:
                break
        parts.append(int(num_part) if num_part else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])

def get_version_info() -> dict:
    return {
        "current_version": CURRENT_VERSION,
        "build_date": BUILD_DATE,
        "release_channel": RELEASE_CHANNEL,
        "github_repo": GITHUB_REPO,
        "changelog": CHANGELOG_HIGHLIGHTS
    }

def check_for_updates(timeout_sec: float = 2.0) -> dict:
    current_tuple = parse_version_tuple(CURRENT_VERSION)

    result = {
        "current_version": CURRENT_VERSION,
        "latest_version": CURRENT_VERSION,
        "update_available": False,
        "status_code": "UP_TO_DATE",
        "status_message": f"Sisteminiz günceldir (Sürüm: v{CURRENT_VERSION}).",
        "checked_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "release_url": f"https://github.com/{GITHUB_REPO}/releases",
        "release_notes": ""
    }

    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"User-Agent": f"LNG-PORV-Sizing/{CURRENT_VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                remote_tag = data.get("tag_name", "").strip()
                latest_tuple = parse_version_tuple(remote_tag)
                result["latest_version"] = remote_tag
                result["release_notes"] = data.get("body", "")
                result["release_url"] = data.get("html_url", result["release_url"])

                if latest_tuple > current_tuple:
                    result["update_available"] = True
                    result["status_code"] = "UPDATE_AVAILABLE"
                    result["status_message"] = f"🔔 Yeni bir sürüm mevcut: {remote_tag} (Mevcut: v{CURRENT_VERSION})"
                else:
                    result["status_code"] = "UP_TO_DATE"
                    result["status_message"] = f"✅ En güncel sürümü kullanıyorsunuz (v{CURRENT_VERSION})."
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception) as err:
        logger.debug(f"Update check skipped / offline: {err}")
        result["status_code"] = "OFFLINE_CHECK"
        result["status_message"] = f"Yerel sürüm doğrulaması aktif: v{CURRENT_VERSION} (Çevrimdışı/Yerel Mod)"

    return result

if __name__ == "__main__":
    print("Version Info:", get_version_info())
    print("Update Check:", check_for_updates())
