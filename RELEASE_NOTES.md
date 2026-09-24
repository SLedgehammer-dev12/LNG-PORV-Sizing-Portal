# 🚀 LNG PORV Emniyet Vanası Boyutlandırma Portalı v1.4.0 (Windows EXE + macOS)

Bu sürüm; **vana kapasite modelinin API 520 Part I fiziksel denklemlerine geçirilmesini**, kriyojenik ideal gaz Cp ve Cp/Cv (k) hesabının düzeltilmesini, rapor veri zincirinin onarılmasını, yangın senaryosunun API 521/520 uyumlu hale getirilmesini ve tam konfigürasyon yönetimini içerir.

---

## 🌟 v1.4.0 Öne Çıkan Yenilikler

### 1. Vana Kapasitesi Artık API 520 Part I Fiziksel Modeli (Kalibrasyon Kaldırıldı)
- Önceki sürümlerde vana hava kapasitesi, varsayılan senaryoya göre kalibre edilmiş bir referans sabitiyle (`148.500 mm² → 25.380 m³/h`) hesaplanıyordu. Bu, programın kendi API 520 gerekli orifis alanı hesabıyla **3,4 kat çelişiyordu** (ör. 16"×18" gerçekte %338 kapasite iken %97 görünüyordu).
- Kapasite artık kritik/subkritik F2 faktörü, P1, P2, Kd ve standart hava özellikleriyle doğrudan API 520 denkleminden hesaplanır.
- Sonuç: Vana seçim matrisi, `OVERSIZED` (>%200) filtresi ve rapor tavsiyeleri artık fiziksel olarak tutarlıdır. Varsayılan senaryoda 16"×18" ve üzeri modeller aşırı büyük olarak elenir; en küçük uygun model dinamik olarak seçilir.

### 2. NFPA 59A Eşdeğer Hava Debisi (Q_a) Standartlaştırıldı
- `0.93 × 990.8` sihirli sabitleri kaldırıldı. Q_a; proses gazı debisinin API 520 ile gerektirdiği efektif orifis alanının, aynı P1/P2 şartlarında standart hava (15 °C, 1.01325 bar_a) kapasitesi olarak hesaplanır.
- Böylece Q_a ile vana hava kapasiteleri **aynı bazda** karşılaştırılır (tutarlılık testi: ±1e-6).

### 3. Kriyojenik Termodinamik Düzeltmeler
- **İdeal gaz Cp (Cp0):** Reid/Aly-Lee polinomları 200 K altında geçersizdir; metan Cp0'ı 118 K'de %23 düşük veriyordu. Artık CoolProp referans-EOS ideal eğrileri (`Cp0molar`) kullanılır, polinom yalnızca yedektir.
- **Cp/Cv (k):** Boyut olarak tutarsız ve daima ideal gaz değerini döndüren eski formül, eksakt `Cp − Cv = −T·(∂P/∂T)²/(∂P/∂V)` EOS türeviyle değiştirildi. k artık basınca duyarlıdır (PR/SRK).
- **HEOS bileşen haritası:** C6+, Ar, H2O, CO ve Air bileşenleri artık CoolProp karışımına dahil edilir (önce sessizce düşürülüyordu).
- **COSTALD** yoğunluğu CoolProp HEOS referansıyla ±%0,5 içinde doğrulanmıştır (otomatik golden test).

### 4. Yangın Senaryosu (API 521 / API 520)
- Yangın için **ayrı overpressure** girdisi (varsayılan %21) eklendi; operasyonel %10'dan bağımsızdır.
- Isı akısı sabiti seçilebilir: **70,9 kW/m²** (34.500 Btu/h·ft², drenaj/söndürme yok) veya **43,2 kW/m²** (21.000 Btu/h·ft², drenaj + söndürme mevcut).
- `Kd = 1.0` yangın matrisine artık gerçekten uygulanır (önce yok sayılıyordu). Atıf API 521 §5.15 olarak düzeltildi.

### 5. Rapor Onarıldı ve Dinamikleştirildi
- Rapor, hesaplanan gerçek **Z, M_vapor, yangın değerleri** ve governing senaryoyu kullanır (önce eksik sözlükler nedeniyle varsayılan değerler basılıyordu).
- Sabit 16"×18"/18"×20" tavsiyeleri kaldırıldı; en küçük uygun vana ve maksimum dolum debisi dinamik hesaplanır.
- **TR/EN rapor dili**, proje künyesi (proje adı, revizyon, hazırlayan, kontrol eden) ve yazdırma (print) CSS'i eklendi. Proje başlığı artık geneldir.

### 6. Robustluk, UX ve Altyapı
- **Tam konfigürasyon kaydet/yükle:** Tüm girdiler, birimler, kompozisyonlar ve kargo kompozisyonu JSON'a kaydedilir (eski format uyumlu).
- **Girdi doğrulama:** Sıcaklık aralıkları, P_atm_min ≤ P_atm_max, sıfır kompozisyon vb. hatalar hesaplama öncesi yakalanır.
- **VLE yakınsama bayrağı** ve yakınsamama uyarısı; kübik kök seçiminde sonlu/pozitif kontrol.
- **Boş/bozuk vana veritabanı** şema doğrulaması ve çökme koruması; veriler `indicative` olarak işaretlendi.
- **Port fallback:** 8501 doluysa sıradaki boş port kullanılır; başlatma hatasında kullanıcıya mesaj gösterilir.
- Sürüm numarası tek kaynaktan (`version_checker.py`) okunur; `ruff` lint + CI adımı eklendi.
- **Paketleme koruması:** PyInstaller yerel modül toplama importları kilitlendi ve CI artık her platformda paket içeriğini (PYZ arşivi) doğrular; eksik modüllü binary yayınlanması engellenir.
- Yanıltıcı "EOS VLE Flaş Oranı" modu kaldırıldı; üç mod: İzentalpik PH-Flaş, Sabit Oran, Manuel Debi.

### 7. Test Kapsamı Genişletildi (71 test + 60 senaryoluk kampanya)
- API 520 fiziksel kapasite ↔ gerekli orifis alanı tutarlılığı, 16"×18" oversized doğrulaması, Kd override.
- COSTALD ↔ CoolProp golden karşılaştırması, PR ↔ HEOS tutarlılığı.
- Kriyojenik Cp0, basınca duyarlı k, VLE yakınsama, saf metan PH-flaş.
- Rapor (TR/EN, dinamik tavsiye, boş matris), DB şema doğrulaması, eksik dosya, port fallback.
- **Streamlit AppTest uçtan uca smoke testi** (tam uygulama hatasız çalışmalı).
- **60 senaryoluk uçtan uca fonksiyon kampanyası** (`scenario_campaign.py`): kompozisyon, EOS, sıcaklık, basınç, debi, yangın, kritik rejim, birim, dayanıklılık ve rapor/UI kategorileri; tümü PASS.
- Kalıcı regresyon seti `test_scenarios.py` (25 test).

---

## ⚠️ Önemli Uyarı (Model Değişikliği)

Vana kapasiteleri artık fiziksel API 520 modeline göre hesaplandığından, **önceki sürümlere göre vana önerileri değişir**. Örneğin eski sürümde 3+1 düzeninde 16"×18" → 18"×20" yükseltmesi önerilirken, yeni modelde aynı senaryoda 16"×18" fiziksel olarak %338 kapasiteye sahiptir ve aşırı büyük (chattering riski) olarak elenir; en küçük uygun model seçilir. Katalog verileri temsilidir; nihai seçim üretici sertifikalı kapasite tablosuyla doğrulanmalıdır.

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
- 71 birim/entegrasyon/termodinamik doğrulama testi (`pytest`) başarıyla geçer.
- `ruff check .` lint denetimi CI'da zorunludur.
- Streamlit AppTest ile uçtan uca uygulama smoke testi.

---

# 🚀 Önceki Sürümler

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
