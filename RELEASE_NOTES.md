# 🚀 LNG PORV Emniyet Vanası Boyutlandırma Portalı v2.0.1 (Windows EXE + macOS)

Hesap motoru v2.0.0 ile aynıdır. Bu sürüm, "yangın Q_a'sı daha yüksekken neden
operasyonel governing seçiliyor?" sorusunu gideren **açıklanabilirlik** iyileştirmesidir.

---

## 🌟 v2.0.1 — Governing Kararının Açıklanması

### 1. Governing Kararı Mini Tablosu (Arayüz + Rapor)
- Her senaryo için **W (kg/h) | Q_a (m³/h) | Q_a'nın hesaplandığı P1 (kPa_a) | Gerekli A_o (mm²/valf)**
  ve iki senaryo arasındaki **marj** gösteriliyor; governing satırı işaretleniyor.
- Karar, ortak referans Kd = 0.85 ile hesaplanan **gerekli A_o** baz alınarak veriliyor.

### 2. Q_a Karşılaştırılabilirlik Notu
- Q_a değerlerinin her senaryonun **kendi relieving basıncında** hesaplandığı (yangın %21,
  operasyonel %10 overpressure), bu nedenle **senaryolar arası doğrudan karşılaştırılamayacağı**
  açıkça belirtiliyor. Aynı 1 mm² orifis yangın basıncında daha fazla hava geçirir; küçük bir
  A_o daha büyük Q_a üretebilir.

### 3. Sınır Uyarısı ve Test Kapsamı
- İki senaryo arasındaki fark **%5'in altındaysa** "governing sınırda — seçilen vana her iki
  senaryoyu da karşılamalıdır" uyarısı veriliyor (ör. %0,46 fark).
- `compute_governing_decision()` yardımcısı, birim testleri, rapor metin kontrolleri ve
  AppTest UI render kontrolü eklendi (**91 test**).

---

# 🚀 LNG PORV Emniyet Vanası Boyutlandırma Portalı v2.0.0 (Windows EXE + macOS)

Bu sürüm; bağımsız incelemede tespit edilen hesap doğruluğu, standart bazı ve rapor
güvenilirliği bulgularını giderir. **Sonuçlar v1.4.1'e göre değişir** (özellikle vana
seçimi ve yangın gerekli alanı); nihai tasarımda sertifikalı üretici verisiyle
doğrulama zorunludur.

---

## 🌟 v2.0.0 Öne Çıkan Düzeltmeler

### 1. Molar Flaş Oranı Kütle Dengesine Dönüştürüldü (P0)
- PH-Flaş/VLE sonucu **molar V/F** artık `W_flash = Q_fill × ρ_feed × β × (M_vapor/M_feed)`
  ile kütle debisine çevriliyor; "molar oranı kütle oranı gibi kullanma" hatası giderildi.
- Sabit flaş modunda **Molar/Kütlesel baz seçimi** eklendi (varsayılan molar).
- Kargo kompozisyonu farklıysa flaş debisinde **kargo yoğunluğu ve kargo mol kütlesi**
  kullanılıyor.

### 2. Boyutlandırma Gazı Durumu Ayrıştırıldı (P0)
- Tank+flaş buharı **mol akışına göre karıştırılıyor**; Z, k, M bu karışımdan ve
  **P1 relieving basıncından** hesaplanıyor (önceki aritmetik Z/k harmanı kaldırıldı).
- `W_disp` yoğunluğu P1 bazında; raporda durum etiketleri gösteriliyor.

### 3. Kd Politikası Düzeltildi (P0)
- Yangın matrisine uygulanan **global Kd=1.0 override kaldırıldı**; her vana kendi
  katalog Kd değeriyle değerlendiriliyor.
- Gerekli orifis alanları (operasyonel ve yangın) **ortak referans Kd=0.85** ile
  hesaplanıyor; hüküm süren senaryo karşılaştırması yanlılıktan kurtarıldı.
- Kd=1.0 yalnızca ilgili model için üretici tarafından sertifikalandırılmışsa geçerlidir.

### 4. Maksimum Dolum Debisi ve Rapor Metrikleri (P0)
- `max_fill = Q_fill × coverage/100` kaldırıldı; limit **operasyonel kütle dengesinden**
  bisection ile çözülüyor (yangın hüküm sürse bile).
- **Kapasite Karşılama Oranı (kapsama)** ile **Gerçek Kapasite Kullanımı
  (talep/kapasite)** ayrı gösteriliyor.
- Kritik/subkritik akışta raporda **gerçek kullanılan denklem dalı** (F2 veya C_crit)
  gösteriliyor.

### 5. Yangın Katsayısı ve Standart Bazı (P0/P1)
- `q_constant_kW_per_m2` → **`fire_coefficient_c_si`** (kW/m^1.64); "kW/m²" birim
  yorumu düzeltildi.
- Standart baskıları koda sabitlendi: NFPA 59A (2023), API 520 Part I (10. baskı),
  API 520 Part II (7. baskı), API 521 (7. baskı). Kapsam: **PORV ön boyutlandırma**.

### 6. EOS Şeffaflığı ve Sağlamlık (P1)
- HEOS/İdeal için **faz ayrımı modeli, gerçek entalpi modeli, fallback ve arama sınırı**
  durumu ekranda ve raporda raporlanıyor.
- HTML raporu **escape ediliyor (XSS)**; boş vana DB'si UI'da güvenli hata veriyor;
  NaN/Inf katalog ve girdiler reddediliyor; bilinmeyen birim sessizce 1.0 yerine hata veriyor.

### 7. Vana Tipi Filtresi (Pilot / Yaylı)
- Aday havuzu artık **vana tipine göre filtrelenebiliyor** (varsayılan: **Yalnızca Pilot Kumandalı**;
  Tümü ve Yalnızca Yaylı seçenekleri). Pilot ve yaylı vanaların tip şartı belirtilmeden
  karıştırılması engellendi; matris ve raporda **Tip** kolonu gösteriliyor.
- Tip filtresi seçimi rapora ve standart/kapsam kartına yazılıyor.

### 8. Doğrulama ve Kapsam
- **90 pytest** (molar/kütle dönüşümü, P1 durum politikası, katalog Kd tutarlılığı,
  max_fill solver, kritik akış, tip filtresi, XSS, boş DB, NaN/Inf, EOS fallback dahil) ve
  **60/60 senaryo kampanyası** (CI kapısı; başarısızlıkta exit 1).
- Standart baskıları sabitlendi; araç **PORV ön boyutlandırma** olarak konumlandırıldı.

---

## 🌟 v1.4.1 Öne Çıkan Düzeltmeler

### 1. Sıcaklık Girdileri Artık Termodinamik Olarak Tutarlı
- **T_tank ve T_relief artık tank basıncındaki gerçek doygunluk sıcaklığına (T_doygun) otomatik eşitlenir** (varsayılan açık; kapatılıp manuel girilebilir).
- Sorun: Önceki varsayılanlar T_relief'i (−155 °C = 118,15 K) tank doygunluğundan (−160,7 °C = 112,45 K) **5,7 K sıcak** alıyordu. Bu, buhar yoğunluğunu (ρ_v) %10, buhar molar kütlesini (M_vapor) ve gerekli orifis alanını **%3,8 non-konservatif** hesaplıyordu.
- Artık tutarlı T_relief ile ρ_v, M_vapor, Z ve k fiziksel doğru duruma karşılık gelir; alan ≈%4 daha konservatif hesaplanır.
- Manuel modda T_relief, tank doygunluğundan >2 K saparsa **tutarsızlık uyarısı** ve alan etkisi açıklaması gösterilir.

### 2. "Dolum Flaş Oranı (VF) = %0" Artık Açıklanıyor
- Otomatik kargo sıcaklığı **seyir basıncındaki** doygunluktan (örn. 100 mbar_g → 110,77 K + ΔT 0,5 K = 111,27 K), tank ise **set basıncındaki** doygunluktan (240 mbar_g → 112,45 K) hesaplanır. Kargo tankta **1,19 K subcooled** kaldığı için izentalpik genleşmede **buharlaşma olmaz; VF=0 fiziksel olarak doğrudur**.
- Arayüz artık bunu açıkça bildirir: **"Subcooled Kargo → Dolum Flaşı Yok (VF=%0)"** ve flaş için gereken eşik (ΔT ≥ 1,7 K veya T_cargo ≥ 112,45 K).
- Flaş oluştuğunda yeşil "dolum flaşı oluşur" mesajı; metrik kartta "Subcooled (flaş yok)" notu.
- Flaşın **set basıncında** değerlendirildiği (flaş için en düşük/en az konservatif varsayım) arayüzde belgelendi.

### 3. M_liquid / M_vapor Netleştirildi
- Önceki "Mol Kütlesi (M) = 18,00 g/mol" **sıvı** kompozisyon ortalamasıdır; "M_vapor = 16,13 g/mol" ise **buhar** (VLE denge) fazıdır — buhar metanca zengin, ağır bileşenler sıvıda kalır.
- Etiketler **M_liquid** ve **M_vapor** olarak ayrıldı; rapora M_vapor satırı eklendi.
- Tutarlı T_relief (112,45 K) ile tank buharı doğru şekilde N₂'ce zenginleşir: **M_vapor = 17,03 g/mol, y_N₂ = %8,2** (önce 16,13 / %0,64).

### 4. Kargo ≠ Tank Buhar Harmanı
- "Kargo kompozisyonu tanktan farklı" seçiliyken boyutlandırma gazı özellikleri (M, Z, k) artık **taşma+BOG tank buharı** ile **flaş kargo buharı**nın mol-akışına göre harmanıdır; sonuç arayüzde ve raporda gösterilir.

### 5. Test Kapsamı
- **77 test** (6 yeni: VF eşiği, M_liquid > M_vapor, T_relief–alan etkisi, kargo harmanı) + **60 senaryoluk kampanya (60/60 PASS)**.
- CI, PyInstaller paketlerinin PYZ içeriğini (yerel modüller) her platformda doğrular.

---

## ⚠️ Önemli Notlar
- v1.4.0'a göre **varsayılan sonuçlar ≈%4 daha konservatif** (tutarlı T_relief). Vana seçimi çoğu senaryoda değişmez; governing çoğunlukla yangın senaryosudur.
- Flaş oranı, tank işletme basıncı set altındaysa daha yüksek olur; program tahliye (set) basıncını esas alır.
- Vana katalog verileri temsilidir (`indicative`); nihai seçim üretici sertifikalı kapasite tablosuyla doğrulanmalıdır.

---

## ⚙️ Platform Çalıştırma Talimatı

### Windows
1. `LNG_PORV_Sizing_Windows.exe` dosyasını indirin.
2. Çift tıklayarak çalıştırın.
3. Uygulama web tarayıcınızda `http://localhost:8501` adresinde açılır (port doluysa sıradaki boş port).

### macOS (Intel / Apple Silicon)
1. `LNG_PORV_Sizing_Intel.app.zip` veya `LNG_PORV_Sizing_ARM.app.zip` dosyasını indirin.
2. ZIP'i açın ve `.app` dosyasını çift tıklayarak çalıştırın (ilk çalıştırmada Güvenlik ayarlarından izin vermeniz gerekebilir).

---

## 🧪 Doğrulama ve Testler
- 77 birim/entegrasyon/termodinamik doğrulama testi (`pytest`) başarıyla geçer.
- `ruff check .` lint denetimi CI'da zorunludur.
- Streamlit AppTest ile uçtan uca uygulama smoke testi + 60 senaryoluk uçtan uca kampanya.

---

# 🚀 Önceki Sürümler

## v1.4.0
- **API 520 Part I fiziksel vana kapasite modeli** (kalibre 25.380 referansı kaldırıldı); 16"×18" gerçek %338 kapasiteyle `OVERSIZED` elenir.
- **NFPA 59A Q_a** API 520 eşdeğer-orifis yöntemiyle standartlaştırıldı.
- **Kriyojenik Cp0** CoolProp referans eğrileri (metan hatası %23 → %0) ve **eksakt EOS Cp−Cv** türevi (k basınca duyarlı).
- **Yangın senaryosu:** ayrı %21 overpressure, API 521 ısı akısı sabiti seçimi, Kd matrise uygulanıyor.
- **Rapor** onarıldı (gerçek Z/M/yangın değerleri), dinamik tavsiye, proje künyesi, TR/EN, print CSS.
- Tam konfigürasyon kaydet/yükle, girdi doğrulama, DB şema doğrulaması, port fallback, ruff + CI.
- Paketleme koruması: PyInstaller modül toplama importları kilitli, CI PYZ doğrulaması.
- v1.4.0 yeniden yayınında paketleme hatası düzeltildi (yerel modüller pakete dahil).

## v1.2.0
- Vana seçim matrisinde aşırı boyutlandırılmış vanaların filtrelenmesi (%90-%200 / %100-%200).
- 97 kriyojenik vana ve 12 üretici markasına genişletilen katalog.
- API 520 Part II chattering/oversizing riskine karşı `OVERSIZED` durum kodu.

## v1.1.0
- İzentalpik PH-Flash (h₁ = h₂) Joule-Thomson genleşme motoru ve EOS entalpi modeli.
- Otomatik doygunluk (bubble point) sıcaklığı çözücüsü.
- Güncelleme yönetimi paneli (`version_checker.py`).

## v1.0.2
- Pure/near-pure kompozisyon izentalpik flaş düzeltmesi.
- macOS Intel/ARM build ve dağıtım iyileştirmeleri.
