"""Geçici il sayfaları üretip sayfadaki canlı JS'in iş günü sonuçlarını Python (onceki_is_gunu) ile karşılaştırır.
JS tatil listesi (H) tek kaynaktan, yani is_gunu.RESMI_TATIL'dan gelmelidir. Node yoksa atlanır."""
import datetime as dt, os, shutil, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import is_gunu as ig
import _util as u
AY = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
def tr(d): return f"{d.day} {AY[d.month-1]} {d.year}"

@unittest.skipUnless(u.NODE, "node kurulu değil")
class PythonJsPariteTesti(unittest.TestCase):
    # her üretim penceresi (bugün .. bugün+181) farklı tatilleri kapsar: 2026 mevcut üretim, 2027 sabit tatilleri, 2028 bayramları
    URETIMLER = ["2026-10-30",   # mevcut canlı üretim
                 "2027-02-01",   # 15 Temmuz 2027 pencerede
                 "2027-05-03",   # 30 Ağustos ve 29 Ekim 2027 pencerede
                 "2027-09-01",   # 29 Ekim 2027 ve 2028 başı
                 "2028-01-03",   # Ramazan Bayramı 2028 (26-28 Şubat), 1 Mayıs, Kurban 5-8 Mayıs 2028
                 "2028-07-03"]   # kapsamın son geçerli üretim günü (pencere 31 Aralık 2028'de biter)

    @classmethod
    def setUpClass(cls):
        cls.dizin = u.kopya()
        cls.sayfalar = {}
        for b in cls.URETIMLER:
            r = u.uret(cls.dizin, "--bugun", b, "--iller", "konya")
            assert r.returncode == 0, (b, r.stderr)
            cls.sayfalar[b] = os.path.join(cls.dizin, "il", f"konya_{b}.html")
            shutil.copy(os.path.join(cls.dizin, "il", "konya.html"), cls.sayfalar[b])

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.dizin, ignore_errors=True)

    def test_js_tatil_listesi_resmi_tatil_kumesinin_pencere_kesitidir(self):
        for b, sayfa in self.sayfalar.items():
            start, h = u.sayfa_bilgisi(sayfa)
            s = dt.date.fromisoformat(start); self.assertEqual(s, ig.onceki_is_gunu(dt.date.fromisoformat(b)))
            beklenen = sorted(t.isoformat() for t in ig.RESMI_TATIL if s <= t <= s + dt.timedelta(days=ig.TAHMIN_PENCERESI_GUN))
            self.assertEqual(h, beklenen, b)

    def test_js_etiketi_python_is_gunu_ile_ayni_pencerenin_her_gunu(self):
        for b, sayfa in self.sayfalar.items():
            start, _ = u.sayfa_bilgisi(sayfa); s = dt.date.fromisoformat(start)
            gunler = [s + dt.timedelta(days=k) for k in range(ig.TAHMIN_PENCERESI_GUN)]
            sonuc = u.js_sonuc(sayfa, [d.isoformat() for d in gunler])
            hatalar = [(r["tarayici"], r["tarih"], tr(ig.onceki_is_gunu(d))) for r, d in zip(sonuc, gunler) if r["tarih"] != tr(ig.onceki_is_gunu(d)) or r["uyari"]]
            self.assertEqual(hatalar, [], b)

    def test_istenen_2027_2028_tarihleri_js_ve_python(self):
        beklenen = {  # (üretim, tarayıcı tarihi) -> etiket
            ("2027-02-01", "2027-07-15"): "14 Temmuz 2027",
            ("2027-05-03", "2027-08-30"): "27 Ağustos 2027",
            ("2027-05-03", "2027-10-29"): "28 Ekim 2027",
            ("2028-01-03", "2028-02-28"): "25 Şubat 2028",
            ("2028-01-03", "2028-05-01"): "28 Nisan 2028",
            ("2028-01-03", "2028-05-08"): "4 Mayıs 2028",
        }
        for (b, t), etiket in beklenen.items():
            r = u.js_sonuc(self.sayfalar[b], [t])[0]
            self.assertEqual(r["tarih"], etiket, (b, t)); self.assertIsNone(r["uyari"])
            self.assertEqual(tr(ig.onceki_is_gunu(dt.date.fromisoformat(t))), etiket)

    def test_pencere_disi_ve_start_oncesi_davranisi_korunur(self):
        sayfa = self.sayfalar["2028-01-03"]; start, _ = u.sayfa_bilgisi(sayfa); s = dt.date.fromisoformat(start)
        once = u.js_sonuc(sayfa, [(s - dt.timedelta(days=5)).isoformat()])[0]
        self.assertEqual(once["tarih"], tr(s)); self.assertIsNone(once["uyari"])
        sonra = u.js_sonuc(sayfa, [(s + dt.timedelta(days=ig.TAHMIN_PENCERESI_GUN + 20)).isoformat()])[0]   # hafta sonu iş gününe çekilip pencereye girmesin diye +20
        self.assertEqual(sonra["tarih"], tr(s)); self.assertIn("güncel olmayabilir", sonra["uyari"])

class UretimKapsamKorumasi(unittest.TestCase):
    def test_kapsam_disi_uretim_hata_verir_ve_sayfa_yazmaz(self):
        d = u.kopya()
        try:
            for b in ("2028-07-04", "2029-01-03"):
                r = u.uret(d, "--bugun", b, "--iller", "konya")
                self.assertNotEqual(r.returncode, 0, b); self.assertIn("HATA", r.stderr); self.assertIn("BAYRAMLAR", r.stderr)
                self.assertFalse(os.path.exists(os.path.join(d, "il", "konya.html")), b)
                self.assertFalse(os.path.exists(os.path.join(d, "sitemap.xml")), b)
            self.assertEqual(u.uret(d, "--bugun", "2028-07-03", "--iller", "konya").returncode, 0)   # son geçerli üretim günü
        finally: shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__": unittest.main()
