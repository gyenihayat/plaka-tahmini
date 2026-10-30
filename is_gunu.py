"""Resmi iş günü yardımcıları: hafta sonu ve tam gün resmi tatiller (arife/yarım günler iş günü kabul edilir).
Kaynak: Diyanet resmi tatil takvimi (2027: vakithesaplama.diyanet.gov.tr/icerik.php?icerik=159, 2028: ...icerik=193).
Resmi karar olmayan köprü/idari izin günleri eklenmez.

Yeni yıl eklemek: BAYRAMLAR'a o yılın Ramazan ve Kurban Bayramı tam gün aralıklarını ekleyin (arifeler hariç).
Sabit tatiller o yıl için otomatik gelir ve kapsam (TAKVIM_SON_YIL) otomatik genişler. Kapsam dışı tarih ya da
tahmin penceresi kullanılırsa kapsam_kontrol() TakvimKapsamHatasi verir (eksik takvim sessizce doğru sayılmaz)."""
import datetime
D=datetime.date
def rng(a,b): return {a+datetime.timedelta(days=i) for i in range((b-a).days+1)}
# Her yıl tam gün sabit tatiller (ay, gün): Yılbaşı, 23 Nisan, 1 Mayıs, 19 Mayıs, 15 Temmuz, 30 Ağustos, 29 Ekim
# (28 Ekim öğleden sonra yarım gün, Ramazan/Kurban arifeleri yarım gün: iş günü kabul edilir)
SABIT_TATIL = ((1,1),(4,23),(5,1),(5,19),(7,15),(8,30),(10,29))
# Yıl -> (Ramazan Bayramı, Kurban Bayramı) tam gün aralıkları (1. günden son güne)
BAYRAMLAR = {
  2024: (rng(D(2024,4,10),D(2024,4,12)), rng(D(2024,6,16),D(2024,6,19))),
  2025: (rng(D(2025,3,30),D(2025,4,1)),  rng(D(2025,6,6),D(2025,6,9))),
  2026: (rng(D(2026,3,20),D(2026,3,22)), rng(D(2026,5,27),D(2026,5,30))),
  2027: (rng(D(2027,3,9),D(2027,3,11)),  rng(D(2027,5,16),D(2027,5,19))),
  2028: (rng(D(2028,2,26),D(2028,2,28)), rng(D(2028,5,5),D(2028,5,8))),
}
TAKVIM_ILK_YIL = min(BAYRAMLAR); TAKVIM_SON_YIL = max(BAYRAMLAR)
TAHMIN_PENCERESI_GUN = 181     # il sayfalarındaki tahmin tablosu ve JS tatil listesi penceresi (bugün + 181 gün)
RESMI_TATIL = {D(y,m,g) for y in BAYRAMLAR for m,g in SABIT_TATIL}.union(*(s for r in BAYRAMLAR.values() for s in r))

class TakvimKapsamHatasi(ValueError):
    """Tarih ya da pencere, tatil takviminin tanımlı olduğu yılların dışında."""
def kapsam_kontrol(bas, bit=None):
    """bas..bit (dahil) aralığının uç yılları tatil takvimi kapsamında değilse TakvimKapsamHatasi verir."""
    for d in (bas, bit or bas):
        if not TAKVIM_ILK_YIL <= d.year <= TAKVIM_SON_YIL:
            raise TakvimKapsamHatasi(f"{d} resmi tatil takvimi kapsamı ({TAKVIM_ILK_YIL}–{TAKVIM_SON_YIL}) dışında: "
                                     f"is_gunu.py BAYRAMLAR'a {d.year} yılının Diyanet tatil takvimini ekleyin")
def _is_gunu(d): return d.weekday()<5 and d not in RESMI_TATIL
def is_is_gunu(d):
    kapsam_kontrol(d)
    return _is_gunu(d)
def onceki_is_gunu(d):
    kapsam_kontrol(d)
    while not _is_gunu(d): d-=datetime.timedelta(days=1)
    return d
