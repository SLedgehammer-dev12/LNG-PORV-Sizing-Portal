# 🚀 LNG PORV Emniyet Vanası Boyutlandırma Portalı v1.4.1 (Windows EXE + macOS)

Bu sürüm; **izentalpik flaş ve sıcaklık girdilerinin termodinamik tutarlılığını** sağlar, **flaş oranının neden %0 çıktığını** arayüzde açıklar ve **M_liquid / M_vapor** ayrımını netleştirir. v1.4.0'daki API 520 fiziksel model ve kriyojenik termodinamik düzeltmeleri içerir.

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
