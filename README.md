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
**İl sayfaları:** `generate_il_pages.py` 81 sayfayı tek şablondan üretir (il bazında elle yazılmış içerik yok): büyük tahmini plaka (il kodu + 3 harf + 3 haneli sıra, örn. `06 GGL 096`; ana sayfadaki üç büyük il kartı da aynı biçim ve aynı değerdir), ayrı etiketli son kayıtlı gözlem / gözlenen harf grubu / son 28 gün değişimi, sayfa içi hesaplayıcı; tablolar ve metodoloji `<details>` içinde HTML'de durur. Son gözlem 21 günden eskiyse kısa güncellik uyarısı gösterilir (`BAYAT_ESIK_GUN`).
**Tarih aracı ("Belirli bir tarihte hangi plakada?"):** ana sayfa ve 81 il sayfası aynı işaretlemeyi (`generate_il_pages.py` `tarih_arac_html`) ve aynı kodu (`assets/tarih-sorgu.js`, ortak motor üzerinde) kullanır; ana sayfada il seçimi ve ikincil "81 ilin bu tarihteki tahminleri" tablosu vardır, il sayfasında yalnızca tarih. Atlanacak seriler: aracın kendi alanı (`#excl`, iki sayfada aynı, varsayılan boş, kalıcı değil); sonuçta uygulandığı açıkça yazılır. Hedef plaka aracının kalıcı `pt-excl` ayarı tarih sonucunu etkilemez. Elle seçilen tarih önceki iş gününe çekilmez (güncel tahminin referans günü kuralı yalnızca başlıktaki güncel plakaya uygulanır). Analitik: yalnızca `ana|il-tarih-hesapla|sonuc|hata` adları, girdi gönderilmez. Testler: `tests/test_tarih_araci.py`.
**Tam plaka eşliği:** statik HTML (Python) ve canlı JS (ortak motor) aynı gün için aynı tam plakayı üretir; ham tahmin iki tarafta bit-bit aynıdır, gösterim yuvarlaması da JS `Math.round` ile aynıdır (yarım değer yukarı; Python `round()` kullanılmaz, bkz. `inv` ve `tests/test_tam_plaka.py`).
**Tarih kuralı:** güncel tahminin referans günü, Türkiye yerel tarihinin (UTC+3; tarayıcı saat diliminden bağımsız) en yakın önceki iş günüdür: Cumartesi, Pazar ve tam gün resmî tatilde değer değişmez; arife/yarım günler iş günüdür. Tek kaynak `is_gunu.py` (`RESMI_TATIL`); JS için `generate_il_pages.py` bunu `assets/takvim.js` olarak üretir (elle düzenlenmez), `trReferansGun()` (ortak motor) ana sayfada ve il sayfalarında aynı kuralı uygular. Son kayıtlı gözlem tarihi bu kuraldan bağımsız, verideki gerçek tarihtir. İl sayfasındaki büyük tahmin ana sayfayla aynı motorla (`estimateAt`) canlı hesaplanır; HTML'deki statik değer üretim referans günü içindir.
**Tek hız tanımı:** il sayfaları ve ana sayfa hesaplayıcısı aynı hızı gösterir: tahmin motorunun hızı (son ~365 günlük aralık hızlarının medyanı, sıra/gün; haftalık değer bunun 7 katı). Bir serinin süresi (1.000 sıra) bu hızdan, atlamasız ilerleme varsayımıyla ve "yaklaşık" olarak hesaplanır (ana sayfada gün cinsinden). Forum tablolarının haftalık ortalaması (`hafta`) artık hız olarak gösterilmez.
**Ana sayfa:** `index.html` elle yazılmıştır; yalnızca işaretli bölgeler (`ANA:KARTLAR`, `ANA:IL-LISTE`, `ANA:IL-BAGLANTILAR`, temel CSS, `ANA:SURUM`) `generate_il_pages.py` tarafından üretilir. Sitemap'teki ana sayfa `lastmod`'u yalnızca anlamlı içerik (gözlem verisi, metin, şablon, CSS) değişince yenilenir; kartlardaki günlük seri/tarih değişimi tek başına sayılmaz (iz `ANA:SURUM` bölgesinde saklanır).
**Testler ve sayaç:** Chrome testleri `CHROME_TEMEL` ile başlar; üretim analitiği (GoatCounter) tarayıcıda engellenir, testler üretim sayacına istek göndermez. Eski Abacus ziyaret sayacı kaldırılmıştır (geçmiş veriler `backups/abacus/` altında yereldedir, Git'te değildir); engel `abacus.jasoncameron.dev` için, yalnızca karşılaştırma testinin git geçmişinden aldığı eski ana sayfa kopyası için korunur.
**Analitik (GoatCounter):** `assets/olcum.js` ana sayfa ve 81 il sayfasında TEK yükleyicidir (HTML'de doğrudan GoatCounter kodu yoktur). Yalnızca `location.hostname === "plakatahmini.com"` iken, `navigator.webdriver` değilken ve `localStorage["plaka-olcum"] !== "kapali"` iken GoatCounter'ın standart `count.js` betiğini ekler; sayfa görüntülemeyi `count.js` kendisi sayar (burada ayrıca sayım yok). Yerel, Vercel önizleme ve test ortamlarında hiç ağ isteği yapılmaz; test Chrome'ları ayrıca `abacus.jasoncameron.dev`, `*.goatcounter.com`, `gc.zgo.at` adlarını çözemez (`CHROME_TEMEL`). Özel olaylar yalnızca sabit, anonim adlardır (`PlakaOlcum.IZINLI`): `ana|il-hesapla-basla|sonuc|hata`, `ana-il-ara`, `ana-il-ara-hata`, `ana-kart-tikla/<il>`; plaka, arama metni veya başka içerik gönderilmez. Kendi ziyaretinizi saymamak için tarayıcıda `localStorage.setItem("plaka-olcum","kapali")`. Mevcut Abacus sayacı ve gizli panel korunmuştur. Analitik betiği ve bilgilendirme notu (`<!--OLCUM-->` bölgeleri) sitemap `lastmod` parmak izine katılmaz.
