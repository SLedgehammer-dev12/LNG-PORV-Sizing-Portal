# ⚓ LNG PORV Emniyet Vanası Boyutlandırma ve Termodinamik Analiz Portalı

![Build Status](https://github.com/SLedgehammer-dev12/LNG-PORV-Sizing-Portal/actions/workflows/build-exe.yml/badge.svg)
![Standard Basis](https://img.shields.io/badge/Standard%20Basis-NFPA%2059A%20%7C%20API%20520%20Part%20I%20%7C%20API%20521-blue)
![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-orange)

Bu yazılım; kriyojenik LNG depolama tankları için **Pilot Uyarılı Emniyet Vanası (PORV)**
**ön boyutlandırma ve kapasite taraması** hesaplarını, sahadaki iklimsel minimum/maksimum
atmosferik basınç dalgalanmalarını, Hankinson-Brobst-Thomson (**COSTALD**) yöntemi ile
dinamik sıvı LNG yoğunluğunu ve çoklu EOS (PR / SRK / GERG-2008) ile buhar termodinamiğini
hesaplayan mühendislik portalıdır.

> ⚠️ **Kapsam ve Sınırlamalar**: Bu araç yalnızca PORV yük/kapasite **ön boyutlandırması**
> yapar. API 520 Part II tesisat/geri basınç analizi, API 625 / API 620 App. Q
> full-containment tank tasarımı ve tank basınç-vakum koruması **kapsam dışıdır**. Vana
> kataloğu temsilî (`indicative`) veridir; nihai seçim ve sipariş öncesi üretici
> sertifikalı kapasite tablosu ile doğrulama zorunludur.

---

## 📚 Standart ve Mühendislik Referansları (sabitlenmiş baskılar)

- **NFPA 59A (2023)**: LNG üretimi, depolanması ve elleçlenmesi — eşdeğer hava debisi
- **API 520 Part I (10. baskı, 2020 + Errata 1/2023)**: Boyutlandırma — kritik/subkritik gaz akışı
- **API 520 Part II (7. baskı, 2020)**: Tesisat — bu araç kapsamaz
- **API 521 (7. baskı, 2020)**: Yangın senaryosu ısı girişi korelasyonu
- **API 625 / API 620 App. Q**: Tank sistemleri — bu araç kapsamaz
- **ASME BPVC Section VIII Div. 1**: Kapasite sertifikasyonu (UG-131)

---

## 🔥 Temel Özellikler

1. **Fiziksel API 520 Vana Kapasite Modeli**:
   - Vana hava kapasiteleri kritik/subkritik F2 faktörü, P1, P2 ve Kd ile doğrudan API 520 denkleminden hesaplanır (kalibre referans sabiti yoktur).
   - `%90 - %200` kapasite penceresi ile yetersiz ve aşırı boyutlandırılmış (chattering riski) vanalar filtrelenir.

2. **NFPA 59A Eşdeğer Hava Debisi (Q_a)**:
   - Q_a; proses gazı debisinin API 520 ile gerektirdiği efektif orifis alanının standart hava (15 °C, 1.01325 bar_a) kapasitesi olarak hesaplanır; vana kapasiteleriyle aynı bazdadır.

3. **18 Bileşenli COSTALD Kriyojenik Yoğunluk Motoru**:
   - `CH4, C2H6, C3H8, i-C4, n-C4, i-C5, n-C5, C6+, N2, CO2, O2, H2, Ar, He, H2S, H2O, CO, Air` bileşenleri; CoolProp HEOS referansıyla ±%0,5 doğrulama testi.

4. **Çoklu EOS ve İzentalpik PH-Flaş**:
   - PR 1976, SRK, HEOS (GERG-2008) ve İdeal Gaz seçenekleri.
   - `h₁ = h₂` Joule-Thomson genleşmesi ile dolum flaş oranı (VF) ve flaş sıcaklığı.
   - **Molar V/F, kütle dengesiyle kütle debisine dönüştürülür** (`M_vapor/M_feed`); kargo
     kompozisyonu farklıysa kargo yoğunluğu/mol kütlesi kullanılır.
   - Boyutlandırma gazı özellikleri (Z, k, M) tank+flaş buharının **mol-akışı karışımından**
     ve **P1 relieving basıncından** hesaplanır.
   - Kriyojenik geçerli ideal gaz Cp (CoolProp `Cp0molar`) ve eksakt EOS `Cp − Cv` türevi ile basınca duyarlı k = Cp/Cv.
   - HEOS seçiminde faz ayrımı modeli, entalpi modeli ve fallback durumu ekranda/raporda açıkça gösterilir.

5. **Vana Kapasitesi ve Kd Politikası**:
   - Her vana **kendi katalog Kd değeriyle** değerlendirilir; global Kd override yoktur.
   - Gerekli orifis alanları ortak **referans Kd = 0.85** ile hesaplanır; hüküm süren senaryo
     karşılaştırması yanlılık içermez.
   - Kd = 1.0 yalnızca ilgili model için üretici tarafından sertifikalandırılmışsa kullanılabilir.

6. **Yangın Senaryosu (API 521 / API 520)**:
   - Ayrı yangın overpressure girdisi (varsayılan %21).
   - `Q_fire = C × F × A_wetted^0.82`; seçilebilir SI korelasyon katsayısı C = 70,9 veya 43,2
     (birim kW/m^1.64 — ısı akısı **değildir**).
   - Yangın matrisi de katalog Kd kullanır; gerekli alan referans Kd=0.85 ile gösterilir.
   - Governing (hüküm süren) senaryo, aynı Kd bazında karşılaştırmayla otomatik belirlenir.

7. **Maksimum Dolum Debisi (Doğru Çözüm)**:
   - Operasyonel kütle dengesinden bisection ile çözülür (sabit BOG dahil); yangın hüküm
     sürse bile yangın kapasite oranından türetilmez.
   - Kapsama oranı ile gerçek kapasite kullanımı ayrı gösterilir.

8. **Kriyojenik Vana Veritabanı ve Tip Filtresi**:
   - 12 üretici markası, 97 kriyojenik model; veriler `indicative` (temsili) olarak işaretlidir.
   - **Vana tipi filtresi** (varsayılan: *Yalnızca Pilot Kumandalı*; Tümü / Yalnızca Yaylı
     seçenekleri) pilot ve yaylı vanaların karıştırılmasını önler; seçim ve rapor tip kolonu içerir.
   - Şema; kaynak dokümanı, revizyon, doğrulama tarihi ve alan/Kd konvansiyonu alanlarını
     (opsiyonel olarak) doğrular; NaN/Inf kayıtlar reddedilir.

9. **Raporlama ve Konfigürasyon**:
   - Dinamik, TR/EN dilli, yazdırılabilir HTML mühendislik raporu (proje künyesi, standart
     baskıları, normalize kompozisyon, formüller, EOS/fallback durumu, tavsiyeler).
   - Kullanıcı metinleri HTML-escape edilir; boş/bozuk katalog ve geçersiz konfigürasyon
     güvenli şekilde ele alınır.

---

## 💻 Windows `.exe` Çalıştırılabilir Sürümünü İndirme

1. GitHub deposunun **[Releases](https://github.com/SLedgehammer-dev12/LNG-PORV-Sizing-Portal/releases)** sayfasına gidin.
2. `LNG_PORV_Sizing_Windows.exe` dosyasını indirin.
3. Çift tıklayarak çalıştırın. Web tarayıcınızda portal otomatik açılacaktır (port 8501 doluysa sıradaki boş port kullanılır).

---

## 🛠️ Yerel Geliştirme ve Çalıştırma (Local Setup)

### Gereksinimler
- Python 3.10 veya üzeri

### Kurulum Adımları
```bash
git clone https://github.com/SLedgehammer-dev12/LNG-PORV-Sizing-Portal.git
cd LNG-PORV-Sizing-Portal

pip install -r requirements.txt

# Lint denetimi
ruff check .

# Birim/entegrasyon testleri
python -m pytest test_app.py test_unit_converter.py test_scenarios.py -v

# 60 senaryoluk sabit koşul regresyon kampanyası (CI kapısı; başarısızlıkta exit 1)
python scenario_campaign.py

# Uygulamayı başlatın
streamlit run app.py
```

---

## ⚠️ Veri Kalitesi Notu

Vana kataloğundaki orifis alanları ve Kd değerleri **temsilidir**; nihai vana seçimi ve sipariş öncesinde üreticinin sertifikalı kapasite tablosu ile doğrulanmalıdır.

---

## 📄 Lisans
Bu proje MIT lisansı altında sunulmaktadır.
