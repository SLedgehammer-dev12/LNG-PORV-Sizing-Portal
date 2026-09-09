# 🚀 LNG PORV Emniyet Vanası Boyutlandırma Portalı v1.1.0 (Windows EXE + macOS)

Bu sürüm; **İzentalpik PH-Flash (Joule-Thomson $h_1 = h_2$)** termodinamik motorunu, genişletilmiş kriyojenik vana kataloğunu, %90 üzeri kapasiteye sahip tüm vanaların listelenmesi modunu, otomatik doygunluk sıcaklığı çözücüsünü ve güncelleme yönetimi kontrolünü içerir.

---

## 🌟 v1.1.0 Öne Çıkan Yenilikler

### 1. İzentalpik PH-Flash ve EOS Entalpi Altyapısı
- **Joule-Thomson Genleşmesi ($h_1 = h_2$)**: Gemi/transfer hattı koşullarından ($P_{\text{gemi}} \approx 4-8\text{ bar}_g$) tank basıncına ($P_{\text{tank}} \approx 200\text{ mbar}_g$) doğru gerçekleşen izentalpik genleşme tam entalpi dengesiyle modellenmiştir.
- **Analitik EOS Entalpisi ($h = h^{\text{ideal}} + h^{\text{residual}}$)**: Peng-Robinson (PR 1976), SRK ve GERG-2008 için Aly-Lee polinom integrali ve analitik türevler entegre edilmiştir.
- **Otomatik Flaş Sıcaklığı ($T_{\text{flash}}$)**: Genleşme sonucu tankta oluşan gerçek denge sıcaklığı otomatik hesaplanır.

### 2. %90 ve Üzeri Kapasiteye Sahip Tüm Vanaların Gösterilmesi
- Vana kataloğu eşleştirme bölümüne **"🔍 Tüm Vanaları Göster (Kapasite Oranı ≥ %90 Olan Modeller)"** filtresi eklendi.
- Kapsama oranı %90.0 ve üzerinde olan tüm ticari modeller (sınırda uygun ve tam uygun olanlar) `⚠️ YAKIN KAPASİTE (%90-%100 Sınırda/Kritik)` etiketiyle tam şeffaflıkla listelenir.

### 3. Genişletilmiş Kriyojenik Vana Kataloğu
- Veritabanına orta ve küçük ölçekli LNG tesisleri için **4"x6", 6"x8", 8"x10", 10"x12" ve 12"x16"** sertifikalı kriyojenik pilot vanalar (Anderson Greenwood, Leser, Consolidated) eklenerek toplam model sayısı 22'ye çıkarıldı.

### 4. Otomatik Doygunluk (Kaynama) Sıcaklığı Çözücüsü
- `calculate_bubble_point_temperature()` fonksiyonu ile tank basıncında karışımın gerçek doygunluk sıcaklığı ($T_{\text{bubble}}$) otomatik çözülmektedir.

### 5. Güncelleme Yönetimi Paneli
- `version_checker.py` modülü ile GitHub API üzerinden zaman aşımlı ve çevrimdışı güvenli sürüm doğrulama ve güncelleme kontrol paneli Streamlit yan menüsüne entegre edildi.

---

# 🚀 Önceki Sürümler

## v1.0.2 (Windows EXE + macOS ARM)


## 🐛 v1.0.2'de Düzeltilenler

- **Pure/Near-Pure Kompozisyon Flaş Düzeltmesi**: Tek bileşenli veya %99.5'ten yüksek tek bileşen içeren kompozisyonlarda (ör. %100 CH₄) izentalpik flaş, iki-fazlı bölgenin tekil sıcaklıkta (T_sat) çökmesi nedeniyle VF=0 verebiliyordu. Artık bu durumlarda faz sınırı tespit edilip **doğrudan enerji dengesi** (h_feed = VF·h_vap + (1-VF)·h_liq) ile çözülüyor.
- **Build/Dağıtım İyileştirmeleri**:
  - macOS `.app` bundle'ları GitHub Actions'ta `ditto` ile zip'lenerek yayınlanıyor (artifact flattening sorunu giderildi).
  - `macos-13` (Intel) runner'ı meşgulken release oluşumu artık bloklanmıyor; Intel build'i best-effort olarak çalışıyor.
  - **macOS ARM build** artık release'e dahil (önceki sürümde yalnızca Windows vardı).

---

## 📋 v1.0.1 Öne Çıkanları (önceki sürümden korunur)

### 1. İzentalpik Flaş (PH-Flash) Termodinamik Motoru
- **PR (Peng-Robinson 1976)**: Residual entalpi + ideal gaz Cp entegrasyonu ile h_total(T,P).
- **SRK (Soave-Redlich-Kwong)**: Aynı metodoloji, SRK spesifik residual entalpi formülasyonu.
- **HEOS (GERG-2008)**: CoolProp `PropsSI('Hmolar')` ile doğrudan toplam entalpi (fallback: PR).
- **Ideal Gas**: h_residual = 0 (basınçtan bağımsız, referans model).
- tüm EOS seçenekleri kullanıcı arayüzünden seçilebilir.

### 2. Termodinamik Altyapı
- `h_ideal(T)` = Σ x_i · ∫ Cp_ideal,i dT (Aly-Lee polinom, T_ref=0K).
- `h_residual(T,P)` — PR/SRK analitik EOS residual entalpi formülü:
  - **PR**: `h_res = RT(Z-1) + [T·da/dT - a] / (2√2·b) · ln[(Z+(1+√2)B)/(Z+(1-√2)B)]`
  - **SRK**: `h_res = RT(Z-1) + [T·da/dT - a] / b · ln(1 + B/Z)`
- Sürekli `h_mix(T)` fonksiyonu: Bubble-point bölgesinde EOS fugacity bazlı VF refine ile VLE flash süreksizliği giderildi.

### 3. Yeni Kullanıcı Arayüzü Özellikleri
- **Gemi Pompa Çıkış Basıncı (P_ship)** girdisi — LNG pompa çıkış basıncı (varsayılan: 5 bar_g). Boru hattı kayıpları izentalpik kabul edilir (konservatif).
- **Flaş BOG Hesap Modu** seçeneğine "İzentalpik Flaş (PH-Flash, EOS)" eklendi.
- **Ayrı Kargo Kompozisyonu** — "Kargo LNG Kompozisyonu Tanktakinden Farklı" checkbox'ı ile gemi kargosu için ayrı bileşen tablosu açılır. İzentalpik flaşta kargo kompozisyonu kullanılır, tank kompozisyonu VLE flash ve yoğunluk hesaplarında kalır.
- İzentalpik flaş sonuçları metrik kartlarda ve detaylı formül sekmesinde görüntülenir:
  - Besleme entalpisi (h_feed, J/mol)
  - Flaş sıcaklığı (T_flash, K)
  - Buhar oranı (VF, % mol/mol) — küçük oranlar için yüksek hassasiyetli gösterim (%.4f)
- **Dinamik Vana Öneri Paneli**: Artık vana önerileri veritabanındaki en küçük uygun vanadan başlayarak dinamik olarak hesaplanır. Girdi değişimlerinde otomatik yenilenir.
- **Dinamik Dolum Debisi Grafiği**: Veritabanındaki en küçük 3 vana için kapasite karşılama eğrileri çizilir (sabit 16"x18"/18"x20" yerine).

### 3b. Kargo Kompozisyonunun Flaşa Etkisi — Doğrulama (PR EOS)
| Kargo CH₄ Oranı | Tank CH₄ Oranı | Flaş Oranı (VF) |
|:---:|:---:|:---:|
| %95.0 | %90.5 | **%1.34** (yüksek uçuculuk → daha fazla flaş) |
| %90.5 | %90.5 | **%0.45** (aynı kompozisyon) |
| %85.0 | %90.5 | **%0.12** (düşük uçuculuk → daha az flaş) |

### 5. Hata Düzeltmeleri
- **HEOS/IDEAL EOS & cargo kompozisyonu bug fix**: CoolProp ile PR entalpi referans farkı giderildi. HEOS ve IDEAL seçimlerinde izentalpik flaş artık PR entalpi tabanlı çalışır, tüm EOS'lar tutarlı sonuç verir.
- **EOS VLE Flaş Oranı modu düzeltmesi**: Artık bu mod da izentalpik flaş hesabını kullanır (NFPA 59A uyumlu). Eski VLE modu tank içeriğinin denge buhar oranını hesaplıyordu (%77), dolum flaşı ile ilgisi yoktu.
- **Birim çevrim hatası yok**: VLE flash molar/kütle VF farkı ~%3 mertebesinde, ihmal edilebilir.

### 6. Yeni Özellikler
- **💾 Konfigürasyon Kaydet/Yükle**: Tüm girdiler JSON formatında kaydedilip geri yüklenebilir.
- **📊 Dinamik Vana Listesi**: Vanalar orifis alanına göre artan sırada listelenir. Kapasite ≥%100 şartını sağlayan en küçük vana otomatik vurgulanır.
- **🖼️ Uygulama İkonu**: LNG tankı ikonu macOS .app bundle'ına eklendi.

### 4. Fiziksel Doğrulama — Tipik Senaryo Sonuçları (PR EOS)
| Gemi Sıcaklığı | Gemi Basıncı | Tank Basıncı | Flaş Oranı (VF) |
|:---:|:---:|:---:|:---:|
| -160°C (113.15 K) | 5 bar_g | 200 mbar_g | ~%0.44 |
| -155°C (118.0 K) | 5 bar_g | 200 mbar_g | ~%3.03 |
| -150°C (123.0 K) | 5 bar_g | 200 mbar_g | ~%5.50 |

---

## ⚙️ Platform Çalıştırma Talimatı

### Windows
1. `LNG_PORV_Sizing_Windows.exe` dosyasını indirin.
2. Çift tıklayarak çalıştırın.
3. Uygulama web tarayıcınızda `http://localhost:8501` adresinde açılır.

### macOS (Intel)
1. `LNG_PORV_Sizing_Intel.app.zip` dosyasını indirin (Intel runner müsait olduğunda yayınlanır).
2. ZIP'i açın ve `LNG_PORV_Sizing_Intel.app` dosyasını çift tıklayarak çalıştırın (ilk çalıştırmada Güvenlik ayarlarından izin vermeniz gerekebilir).
3. Uygulama web tarayıcınızda `http://localhost:8501` adresinde açılır.

### macOS (Apple Silicon / ARM)
1. `LNG_PORV_Sizing_ARM.app.zip` dosyasını indirin.
2. ZIP'i açın ve `LNG_PORV_Sizing_ARM.app` dosyasını çift tıklayarak çalıştırın.
3. Uygulama web tarayıcınızda `http://localhost:8501` adresinde açılır.

---

## 🧪 Doğrulama ve Testler
- Tüm birim ve termodinamik doğrulama testleri (`pytest`) `%100` başarı oranı ile geçmiştir.
- 14 test + 8 yeni entalpi/PH-flash validasyon testi.
- Üç platformda da (Windows, macOS Intel, macOS ARM) otomatik build ve test.
