# 🚀 LNG PORV Emniyet Vanası Boyutlandırma Portalı v1.0.1 (Windows Release)

Bu sürüm, flaş gazlaşması hesaplamasına **İzentalpik (PH-Flash) EOS motoru** eklenmiş, NFPA 59A Madde 8.4.10.5.1(5) ve API 625 Madde 7.4.2.4(f)-(g) standartlarına tam uyumlu güncellemedir. LNG gemisinden tanka girişteki izentalpik genleşme (Joule-Thomson etkisi) artık dört farklı durum denklemi (PR, SRK, HEOS/GERG-2008, Ideal Gas) ile modellenebilmektedir.

---

## 📋 Sürüm Öne Çıkanları (Release Highlights)

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
- **Gemi Transfer Basıncı (P_ship)** girdisi — LNG gemisinin tanka transfer basıncı (varsayılan: 5 bar_g).
- **Flaş BOG Hesap Modu** seçeneğine "İzentalpik Flaş (PH-Flash, EOS)" eklendi.
- İzentalpik flaş sonuçları metrik kartlarda ve detaylı formül sekmesinde görüntülenir:
  - Besleme entalpisi (h_feed, J/mol)
  - Flaş sıcaklığı (T_flash, K)
  - Buhar oranı (VF, % mol/mol) — küçük oranlar için yüksek hassasiyetli gösterim (%.4f)
- **Dinamik Vana Öneri Paneli**: Artık vana önerileri veritabanındaki en küçük uygun vanadan başlayarak dinamik olarak hesaplanır. Girdi değişimlerinde otomatik yenilenir.
- **Dinamik Dolum Debisi Grafiği**: Veritabanındaki en küçük 3 vana için kapasite karşılama eğrileri çizilir (sabit 16"x18"/18"x20" yerine).

### 4. Fiziksel Doğrulama — Tipik Senaryo Sonuçları (PR EOS)
| Gemi Sıcaklığı | Gemi Basıncı | Tank Basıncı | Flaş Oranı (VF) |
|:---:|:---:|:---:|:---:|
| -160°C (113.15 K) | 5 bar_g | 200 mbar_g | ~%0.44 |
| -155°C (118.0 K) | 5 bar_g | 200 mbar_g | ~%3.03 |
| -150°C (123.0 K) | 5 bar_g | 200 mbar_g | ~%5.50 |

---

## ⚙️ Windows Executable Kullanım Talimatı

1. `LNG_PORV_Sizing.exe` dosyasını bilgisayarınıza indirin.
2. Çift tıklayarak çalıştırın.
3. Uygulama otomatik olarak web tarayıcınızda `http://localhost:8501` adresinde açılacaktır.

---

## 🧪 Doğrulama ve Testler
- Tüm birim ve termodinamik doğrulama testleri (`pytest`) `%100` başarı oranı ile geçmiştir.
- 14 test + 8 yeni entalpi/PH-flash validasyon testi.
