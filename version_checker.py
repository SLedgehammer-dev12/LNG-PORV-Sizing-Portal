"""
LNG PORV Sizing Application - Version & Update Management Module
Manages application versioning, build metadata, and remote/local update status checks.
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

CURRENT_VERSION = "1.1.0"
BUILD_DATE = "2026-09-09"
RELEASE_CHANNEL = "Stable / Production (BOTAŞ & NFPA 59A Certified)"
GITHUB_REPO = "SLedgehammer-dev12/LNG-PORV-Sizing-Portal"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

CHANGELOG_HIGHLIGHTS = [
    "v1.1.0: İzentalpik PH-Flash (Joule-Thomson h1=h2) genleşme motoru ve EOS entalpi modeli eklendi.",
    "v1.1.0: Vana seçim kataloğunda %90 üzeri kapasiteli tüm vanaların listelenmesi modu eklendi.",
    "v1.1.0: Otomatik Doygunluk Sıcaklığı (Bubble Point) çözücüsü entegre edildi.",
    "v1.1.0: Güncelleme yönetimi ve versiyon kontrol paneli eklendi.",
    "v1.0.0: Yangın senaryosu API 520, GERG-2008 HEOS, Rachford-Rice VLE Flash ve vana veritabanı."
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
    info = get_version_info()
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
