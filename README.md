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

Güncelleme: yeni haftalık tablo işlendiğinde `index.html` içindeki gömülü `DATA` yenilenip
push edilir (üretim akışı: plakaTR projesindeki `scripts/`).
