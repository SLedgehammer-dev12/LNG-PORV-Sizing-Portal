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

CURRENT_VERSION = "2.0.1"
BUILD_DATE = "2026-09-28"
RELEASE_CHANNEL = "Stable / Production (PORV ön boyutlandırma aracı)"
GITHUB_REPO = "SLedgehammer-dev12/LNG-PORV-Sizing-Portal"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

CHANGELOG_HIGHLIGHTS = [
    "v2.0.1: Governing kararı gerekçesi arayüzde ve raporda gösteriliyor: her senaryo için W, Q_a, Q_a'nın hesaplandığı P1 ve gerekli A_o; karar A_o bazlı.",
    "v2.0.1: Q_a değerlerinin farklı relieving basınçlarında hesaplandığı ve senaryolar arası karşılaştırılamayacağı açıkça belirtiliyor.",
    "v2.0.1: İki senaryo arasındaki fark %5'in altındaysa 'governing sınırda' uyarısı veriliyor (ör. %0,46 fark).",
    "v2.0.0: Molar flaş oranı kütle dengesiyle kütle debisine dönüştürülüyor (W_flash = Q·ρ_feed·β·M_vapor/M_feed); kargo farklıysa kargo yoğunluğu/mol kütlesi kullanılıyor.",
    "v2.0.0: Boyutlandırma gazı özellikleri (Z, k, M) tank+flaş buharının mol-akışı karışımından ve P1 relieving basıncından hesaplanıyor.",
    "v2.0.0: Global Kd override kaldırıldı; her vana kendi katalog Kd değeriyle değerlendiriliyor, gerekli alanlar referans Kd=0.85 ile.",
    "v2.0.0: Maksimum dolum debisi operasyonel kütle dengesinden çözülüyor (yangın hüküm sürse bile); kapsama ve kapasite kullanımı ayrı gösteriliyor.",
    "v2.0.0: Kritik/subkritik akış gösterimi gerçek kullanılan denklem dalına bağlandı; Kd etiketleri dinamik.",
    "v2.0.0: Yangın katsayısı C (kW/m^1.64) olarak yeniden adlandırıldı; birim yorumu düzeltildi.",
    "v2.0.0: EOS fallback/faz ayrımı/arama sınırı durumları raporda açıkça raporlanıyor.",
    "v2.0.0: HTML raporu escape ediliyor; boş DB, NaN/Inf, bilinmeyen birim ve konfigürasyon girdileri güvenli ele alınıyor.",
    "v1.4.1: Flaş/sıcaklık termodinamik tutarlılığı — T_tank ve T_relief artık tank doygunluk sıcaklığına otomatik eşitleniyor; subcooled kargoda VF=0 uyarısı ve flaş eşiği gösteriliyor.",
    "v1.4.1: Sıcaklık tutarsızlığı uyarısı; tutarlı T_relief ile ρ_v, M_vapor ve gerekli orifis alanı fiziksel olarak doğru (≈%4 daha konservatif).",
    "v1.4.1: M_liquid ve M_vapor etiketleri netleştirildi; rapora M_vapor satırı eklendi.",
    "v1.4.1: Kargo kompozisyonu tanktan farklıysa boyutlandırma gazı özellikleri (M, Z, k) taşma ve flaş buharlarının mol-akışına göre harmanlanıyor.",
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
