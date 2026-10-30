# Plaka Tahmini

Türkiye 3+3 araç plakalarında il il **güncel seri tahmini**: bir il şu an hangi seride,
ileri bir tarihte nerede olur, istediğiniz seriye ne zaman ulaşır — 81 il tablolarıyla.

Tamamen statik tek sayfa (`index.html`); veri sayfaya gömülüdür.

**Veri kaynağı:** wowturkey.com "Türkiye Genelindeki Araç Plakalarının Gelişimi" başlığında
Güven_Hoca'nın paylaştığı haftalık/günlük tablolar (Şubat 2024'ten beri), OCR ile sayısallaştırılıp
toplam ve haftalar-arası tutarlılık kontrolleriyle doğrulanmıştır.

**Yöntem:** seri konumu nominal bir sayıya çevrilir (plaka alfabesi; ilk/son harfte I-O yok,
seri başına 1000 numara); hız, son ~180 gündeki aralık hızlarının medyanıdır (tek seferlik blok
atlamalarına dayanıklı). Geriye dönük testte medyan hata ~7 gün.

Güncelleme: forumdaki yeni tablo okunup `plakalar.txt` ("01 BIE 404, ...") ve `hft.txt` ("İstanbul 9451", ...)
dosyalarına yazıldıktan sonra
`python3 tablo_ekle.py --tarih YYYY-MM-DD --plakalar plakalar.txt --hft hft.txt` çalıştırılır (önce `--kuru` ile doğrulanabilir).
Tarih hafta sonu/resmi tatile denk gelirse bir önceki iş gününe çekilir (`is_gunu.py`); gömülü `DATA`,
`data/` dosyaları, il sayfaları ve sitemap güncellenir. Ardından commit/push edilir.

Sitemap `lastmod`: ana sayfada verideki en son gözlem günü; il sayfalarında yalnızca sayfanın anlamlı içeriği (canlı tahmin alanları ve JS hariç) değiştiyse üretim günü, aksi hâlde önceki değer korunur.
`generate_il_pages.py --bugun YYYY-MM-DD` yalnızca tahmin tarihini sabitler; "son gözlem" tarihleri her zaman veriden gelir.

Resmî tatil takvimi `is_gunu.py` içindedir (`BAYRAMLAR` + `SABIT_TATIL`; şu an 2024–2028, kaynak: Diyanet) ve il sayfalarındaki JS tatil listesinin tek kaynağıdır. Yeni yıl için `BAYRAMLAR`'a o yılın Ramazan/Kurban tam gün aralıkları eklenir; takvim kapsamı dışındaki tarih ya da 181 günlük tahmin penceresi (2028-07-03 sonrası üretim) `HATA` ile durur.
Testler: `python3 -m unittest discover -s tests -v` (Node varsa Python–JS iş günü eşliği de denenir).

**Ortak motor:** tahmin hesabı `assets/tahmin-motoru.js` içindedir; ana sayfa (`index.html`) ve 81 il sayfasındaki plaka tahmin aracı (`assets/il-arac.js`) aynı dosyayı kullanır. `forecast.py` ile aynı matematiktir; `tests/golden/` altındaki altın çıktılarla korunur (ana sayfa arayüzü ortak modül öncesiyle birebir aynı sonuç verir). `tablo_ekle.py` yalnızca `index.html` içindeki `const DATA = …;` satırını günceller.
**İl sayfaları:** `generate_il_pages.py` 81 sayfayı tek şablondan üretir (il bazında elle yazılmış içerik yok): büyük tahmini seri, ayrı etiketli son kayıtlı gözlem / gözlenen harf grubu / son 28 gün değişimi, sayfa içi hesaplayıcı; tablolar ve metodoloji `<details>` içinde HTML'de durur. Son gözlem 21 günden eskiyse kısa güncellik uyarısı gösterilir (`BAYAT_ESIK_GUN`).
**Tarih kuralı:** güncel tahminin referans günü, Türkiye yerel tarihinin (UTC+3; tarayıcı saat diliminden bağımsız) en yakın önceki iş günüdür: Cumartesi, Pazar ve tam gün resmî tatilde değer değişmez; arife/yarım günler iş günüdür. Tek kaynak `is_gunu.py` (`RESMI_TATIL`); JS için `generate_il_pages.py` bunu `assets/takvim.js` olarak üretir (elle düzenlenmez), `trReferansGun()` (ortak motor) ana sayfada ve il sayfalarında aynı kuralı uygular. Son kayıtlı gözlem tarihi bu kuraldan bağımsız, verideki gerçek tarihtir. İl sayfasındaki büyük tahmin ana sayfayla aynı motorla (`estimateAt`) canlı hesaplanır; HTML'deki statik değer üretim referans günü içindir.
