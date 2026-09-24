# ⚓ LNG PORV Emniyet Vanası Boyutlandırma ve Termodinamik Analiz Portalı

![Build Status](https://github.com/SLedgehammer-dev12/LNG-PORV-Sizing-Portal/actions/workflows/build-exe.yml/badge.svg)
![Standard Compliance](https://img.shields.io/badge/Standards-NFPA%2059A%20%7C%20API%20520%20%7C%20API%20521%20%7C%20API%20620-blue)
![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-orange)

Bu yazılım; kriyojenik LNG depolama tankları için **Pilot Uyarılı Emniyet Vanası (PORV)** boyutlandırma hesaplarını, sahadaki iklimsel minimum/maksimum atmosferik basınç dalgalanmalarını, Hankinson-Brobst-Thomson (**COSTALD**) yöntemi ile dinamik sıvı LNG yoğunluğunu ve çoklu EOS (PR / SRK / GERG-2008) ile buhar termodinamiğini hesaplayan mühendislik portalıdır.

---

## 📚 Standart ve Mühendislik Referansları

- **NFPA 59A**: Standard for the Production, Storage, and Handling of Liquefied Natural Gas (LNG) — Madde 8.4.10.7.4.2 eşdeğer hava debisi
- **API 520 Part I & II**: Sizing, Selection, and Installation of Pressure-Relieving Devices — kritik ve subkritik gaz akışı
- **API 521**: Pressure-relieving and Depressuring Systems — yangın senaryosu ısı girişi
- **API 625 / API 620 Appendix Q**: LNG depolama tank sistemleri
- **ASME Section VIII Div. 1**: Boiler and Pressure Vessel Code

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
   - Kriyojenik geçerli ideal gaz Cp (CoolProp `Cp0molar`) ve eksakt EOS `Cp − Cv` türevi ile basınca duyarlı k = Cp/Cv.

5. **Yangın Senaryosu (API 521 / API 520)**:
   - Ayrı yangın overpressure girdisi (varsayılan %21).
   - Seçilebilir ısı akısı sabiti: 70,9 kW/m² (34.500 Btu/h·ft²) veya 43,2 kW/m² (21.000 Btu/h·ft²).
   - Governing (hüküm süren) senaryo otomatik belirlenir.

6. **Kriyojenik Vana Veritabanı**:
   - 12 üretici markası, 97 kriyojenik model (2"×3" – 20"×24"); veriler `indicative` (temsili) olarak işaretlidir.

7. **Raporlama ve Konfigürasyon**:
   - Dinamik, TR/EN dilli, yazdırılabilir HTML mühendislik raporu (proje künyesi, revizyon, formüller, tavsiyeler).
   - Tüm girdilerin JSON olarak kaydedilip yüklenmesi; girdi doğrulama ve çökme korumaları.

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

# Uygulamayı başlatın
streamlit run app.py
```

---

## ⚠️ Veri Kalitesi Notu

Vana kataloğundaki orifis alanları ve Kd değerleri **temsilidir**; nihai vana seçimi ve sipariş öncesinde üreticinin sertifikalı kapasite tablosu ile doğrulanmalıdır.

---

## 📄 Lisans
Bu proje MIT lisansı altında sunulmaktadır.
