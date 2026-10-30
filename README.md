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
