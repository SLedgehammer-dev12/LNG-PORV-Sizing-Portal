# 🚀 LNG PORV Emniyet Vanası Boyutlandırma Portalı v1.0.0 (Windows Release)

Bu sürüm, Kriyojenik LNG Depolama Tankları için **Pilot Uyarılı Emniyet Vanası (PORV - Pilot Operated Relief Valve)** boyutlandırma hesaplarını, sahadaki atmosferik basınç sınırlarını ($P_{\text{atm, min}} = 906.03\text{ mbar}_a$), Hankinson-Brobst-Thomson (**COSTALD**) yöntemi ile sıvı LNG ve buhar termodinamiğini eksiksiz hesaplayan **Windows Standalone Executable (`LNG_PORV_Sizing.exe`)** paketini içerir.

---

## 📋 Sürüm Öne Çıkanları (Release Highlights)

### 1. Standartlar ve Mühendislik Formülasyonları
- **NFPA 59A (2019)** Madde 8.4.10.7.4.2 uyarınca Hava Eşdeğeri debi ($Q_a$) hesabı.
- **API 520 Part I & II** Subcritical (Kritik Altı) gaz akış denklemi ve $A_o$ orifis alanı hesabı.
- **API 625**, **API 620 Appendix Q** ve **ASME Section VIII Div. 1** uyumluluğu.

### 2. Kritik Saha Koşulları & Basınç Duyarlılığı
- Minimum sahadaki atmosferik basınç ($906.03\text{ mbar}_a$) altında gaz kütlesel yoğunluğunun düşmesiyle Orifis Alanının $154.500\text{ mm}^2$'ye çıktığını doğrulayan worst-case boyutlandırma.

### 3. 14 Bileşenli COSTALD Kriyojenik Yoğunluk Motoru
- $CH_4, C_2H_6, C_3H_8, i-C_4H_{10}, n-C_4H_{10}, i-C_5H_{12}, n-C_5H_{12}, C_6+, N_2, CO_2, O_2, H_2, Ar, He$ bileşenlerini destekler.
- Anlık %100 mol toplamı kontrolü ve tek tıkla **"⚡ Kompozisyonu Otomatik %100'e Eşitle"** butonu.

### 4. Esnek Birim Yönetimi
- Basınç (`mbar_a`, `bar_a`, `kPa_a`, `psi_a`, `atm`), Debi (`m³/h`, `GPM`, `kg/h`, `lb/h`), Sıcaklık (`°C`, `K`, `°F`), Hacim (`m³`, `L`, `bbl`, `gal`) ve Yoğunluk (`kg/m³`, `g/cm³`) birimleri arasında anlık iki yönlü çevrim.

### 5. Entegre PSV Üretici Katalog Eşleştirmesi
- **Anderson Greenwood (Emerson)**, **Crosby**, **Baker Hughes (Consolidated)**, **Leser**, **Curtiss-Wright (Farris)** ve **Mercer Valve** modellerinin otomatik eşleştirmesi.

---

## ⚙️ Windows Executable Kullanım Talimatı

1. `LNG_PORV_Sizing.exe` dosyasını bilgisayarınıza indirin.
2. Çift tıklayarak çalıştırın.
3. Uygulama otomatik olarak web tarayıcınızda `http://localhost:8501` adresinde açılacaktır.

---

## 🧪 Doğrulama ve Testler
- Tüm birim ve termodinamik doğrulama testleri (`pytest`) `%100` başarı oranı ile geçmiştir.
