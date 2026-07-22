# ⚓ LNG PORV Emniyet Vanası Boyutlandırma ve Termodinamik Analiz Portalı

![Build Status](https://github.com/SLedgehammer-dev12/LNG-PORV-Sizing-Portal/actions/workflows/build-exe.yml/badge.svg)
![Standard Compliance](https://img.shields.io/badge/Standards-NFPA%2059A%20%7C%20API%20520%20%7C%20API%20625%20%7C%20API%20620-blue)
![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-orange)

Bu yazılım; Kriyojenik Depolama Tankları için **Pilot Uyarılı Emniyet Vanası (PORV - Pilot Operated Relief Valve)** boyutlandırma hesaplarını, sahadaki iklimsel minimum/maksimum atmosferik basınç dalgalanmalarını ($P_{\text{atm, min}} = 906.03\text{ mbar}_a$), Hankinson-Brobst-Thomson (**COSTALD**) yöntemi ile dinamik sıvı LNG yoğunluğu ve buhar termodinamiğini eksiksiz hesaplayan mühendislik portalıdır.

---

## 📚 Standart ve Mühendislik Referansları

Yazılım aşağıdaki uluslararası standartlara ve şartnamelere tam uyumlu olarak kodlanmıştır:
- **NFPA 59A (2019 Baskısı)**: Standard for the Production, Storage, and Handling of Liquefied Natural Gas (LNG) - *Madde 8.4.10.7.4.2 uyarınca Hava Eşdeğeri $Q_a$ hesabı*
- **API 520 Part I & II (10. Baskı)**: Sizing, Selection, and Installation of Pressure-Relieving Devices - *Subcritical (Kritik Altı) Gaz Akış Formülasyonu*
- **API 625**: Tank Systems for Storage of Liquefied Petroleum Gases
- **API 620 Appendix Q**: Low-Pressure Storage Tanks for Liquefied Hydrocarbon Gases
- **ASME Section VIII Div. 1**: Boiler and Pressure Vessel Code

---

## 🔥 Temel Özellikler

1. **İklimsel Atmosferik Basınç Duyarlılığı ($P_{\text{atm, min}} = 906.03\text{ mbar}_a$)**:
   - Minimum atmosferik basınçta buhar kütlesel yoğunluğunun düşmesiyle orifis alanının $\%9.4$ oranında büyüdüğünü dikkate alan emniyetli tarafta kalma (worst-case sizing) algoritması.

2. **14 Bileşenli COSTALD Kriyojenik Yoğunluk Motoru**:
   - $CH_4, C_2H_6, C_3H_8, i-C_4H_{10}, n-C_4H_{10}, i-C_5H_{12}, n-C_5H_{12}, C_6+, N_2, CO_2, O_2, H_2, Ar, He$ bileşenleri ile sıvı LNG yoğunluğu ($\rho_{\text{LNG}}$) hesabı.

3. **%100 Mol Toplamı Doğrulaması & Otomatik Eşitleme**:
   - Canlı mol yüzdesi toplamı kontrolü ve tek tıkla $\%100$'e normalize etme butonu.

4. **Ayrıştırılmış Kriyojenik Sıcaklıklar**:
   - **Sıvı LNG Sıcaklığı ($T_{\text{LNG}}$)**: COSTALD sıvı yoğunluğu hesabı için.
   - **Tahliye Buhar Sıcaklığı ($T_{\text{relief}}$)**: Buhar yoğunluğu ($\rho_v$) ve vana gaz akışı hesabı için.

5. **Dinamik Birim Çevrim Yönetimi**:
   - Basınç (`mbar_a`, `bar_a`, `kPa_a`, `psi_a`, `atm`), Debi (`m³/h`, `GPM`, `kg/h`, `lb/h`), Sıcaklık (`°C`, `K`, `°F`), Hacim (`m³`, `L`, `bbl`, `gal`) ve Yoğunluk (`kg/m³`, `g/cm³`) birimleri arasında anlık iki yönlü çevrim.

6. **Entegre Üretici Vana Veritabanı Eşleştirmesi**:
   - **Anderson Greenwood (Emerson)**, **Crosby**, **Baker Hughes (Consolidated)**, **Leser**, **Curtiss-Wright (Farris)** ve **Mercer Valve** kataloğundan proses şartlarını karşılayan vana marka/modellerinin otomatik sıralanması.

7. **Yazdırılabilir Mühendislik Hesap Raporu**:
   - Tek tıkla onaylı HTML mühendislik hesap raporu indirme imkanı.

---

## 💻 Windows `.exe` Çalıştırılabilir Sürümünü İndirme

Windows işletim sisteminde herhangi bir Python kurulumuna ihtiyaç duymadan doğrudan çalıştırmak için:
1. GitHub deposunun **[Releases](https://github.com/SLedgehammer-dev12/LNG-PORV-Sizing-Portal/releases)** sayfasına gidin.
2. `LNG_PORV_Sizing.exe` dosyasını indirin.
3. Çift tıklayarak çalıştırın. Web tarayıcınızda portal otomatik açılacaktır!

---

## 🛠️ Yerel Geliştirme ve Çalıştırma (Local Setup)

### Gereksinimler
- Python 3.10 veya üzeri

### Kurulum Adımları
```bash
# Repoyu klonlayın
git clone https://github.com/SLedgehammer-dev12/LNG-PORV-Sizing-Portal.git
cd LNG-PORV-Sizing-Portal

# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Birim testlerini çalıştırın
python -m pytest test_app.py test_unit_converter.py -v

# Uygulamayı başlatın
streamlit run app.py
```

---

## 📄 Lisans
Bu proje MIT lisansı altında sunulmaktadır.
