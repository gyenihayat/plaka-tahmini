"""İlk ekrandaki "Harf grubu" bilgi satırı: yalnızca Ankara, İstanbul ve Konya sayfalarında; değerler son kayıtlı gözlemden hesaplanır."""
import datetime as dt, glob, json, os, re, shutil, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
A1 = "ABCDEFGHJKLMNPRSTUVYZ"; A2 = "ABCDEFGHIJKLMNOPRSTUVYZ"; A3 = "ABCDEFGHJKLMNPRSTUVYZ"
E0 = dt.date(2024, 1, 1)
AY = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
def tr(d): return f"{d.day} {AY[d.month-1]} {d.year}"
def inv(n):
    g = n // 1000
    return A1[g//len(A3)//len(A2)] + A2[g//len(A3) % len(A2)] + A3[g % len(A3)], n % 1000
def to_n(seri, no): return ((A1.index(seri[0])*len(A2) + A2.index(seri[1]))*len(A3) + A3.index(seri[2]))*1000 + no
SATIR = re.compile(r'<p class="meta">Harf grubu: <b class="mono">(\w)</b> \(serinin ilk harfi\) — son kayıtlı gözlem: <span class="mono" style="white-space:nowrap">(\d\d \w{3} \d{3})</span>, ([^<]*)\.</p>')
UC = {"Ankara": "ankara", "İstanbul": "istanbul", "Konya": "konya"}
def veri(dizin=u.ROOT):
    with open(os.path.join(dizin, "data", "tahmin_data.json"), encoding="utf-8") as f: return json.load(f)
def son_gozlem(d, il):
    s = next(x for x in d["iller"] if x["il"] == il); gun, n = s["obs"][-1]; seri, no = inv(n)
    return s["kod"], seri, no, E0 + dt.timedelta(days=gun)

class HarfGrubuSatiri(unittest.TestCase):
    def test_uc_ilde_deger_gozlem_verisinden(self):
        d = veri()
        for il, sl in UC.items():
            kod, seri, no, tarih = son_gozlem(d, il); h = u.oku(os.path.join(u.ROOT, "il", sl + ".html"))
            m = SATIR.findall(h); self.assertEqual(len(m), 1, il)
            self.assertEqual(m[0], (seri[0], f"{kod:02d} {seri} {no:03d}", tr(tarih)), il)

    def test_mevcut_veri_icin_beklenen_degerler(self):
        d = veri()
        beklenen = {"Ankara": ("G", "06 GGD 591"), "İstanbul": ("R", "34 RLN 835"), "Konya": ("B", "42 BJA 124")}
        for il, (grup, plaka) in beklenen.items():
            kod, seri, no, tarih = son_gozlem(d, il)
            if tarih != dt.date(2026, 10, 23): self.skipTest("veri 23 Ekim 2026'dan sonra güncellendi; bu anlık görüntü testi artık geçerli değil")
            m = SATIR.findall(u.oku(os.path.join(u.ROOT, "il", UC[il] + ".html")))[0]
            self.assertEqual((m[0], m[1], m[2]), (grup, plaka, "23 Ekim 2026"), il)

    def test_diger_78_ilde_satir_yok(self):
        sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81)
        for yol in sayfalar:
            sl = os.path.basename(yol)[:-5]; var = "Harf grubu:" in u.oku(yol)
            self.assertEqual(var, sl in UC.values(), sl)

    def test_satir_tahmin_satirinin_hemen_altinda_ve_js_ile_degismez(self):
        for sl in UC.values():
            h = u.oku(os.path.join(u.ROOT, "il", sl + ".html"))
            self.assertRegex(h, r'<div class="plrow">.*?</div>\n<div class="uyari" id="guncellik"[^\n]*</div>\n<p class="meta">Harf grubu:')
            self.assertRegex(h, r'Harf grubu:[^\n]*</p>\n<p class="meta">[^\n]*haftada ortalama')
            self.assertNotIn("data-live", SATIR.search(h).group(0))      # canlı JS bu satıra dokunmaz

    def test_mevcut_giris_ve_baslik_alanlari_korunur(self):
        for sl in UC.values():
            h = u.oku(os.path.join(u.ROOT, "il", sl + ".html"))
            self.assertIn("ilinde son doğrulanmış plaka gözlemi", h); self.assertIn("itibarıyla tahmini olarak", h)
            self.assertIn("<h1>", h); self.assertIn('rel="canonical"', h)

@unittest.skipUnless(u.NODE, "node kurulu değil")
class GozlemTahminAyrimi(unittest.TestCase):
    def test_tahmin_baska_harf_grubuna_gecmisse_satir_gozlemi_gosterir(self):
        d = u.kopya()
        try:
            yol = os.path.join(d, "data", "tahmin_data.json"); v = veri(d)
            a = next(x for x in v["iller"] if x["il"] == "Ankara"); a["obs"][-1][1] = to_n("GZZ", 990)   # grubun son serisi
            with open(yol, "w", encoding="utf-8") as f: json.dump(v, f, ensure_ascii=False, separators=(",", ":"))
            r = u.uret(d, "--bugun", "2026-11-13", "--iller", "ankara"); self.assertEqual(r.returncode, 0, r.stderr)
            h = u.oku(os.path.join(d, "il", "ankara.html"))
            self.assertEqual(SATIR.findall(h)[0][:2], ("G", "06 GZZ 990"))                       # satır: son kayıtlı gözlem, G grubu
            plaka = re.search(r'data-live="plaka">([^<]*)<', h)[1]
            self.assertTrue(plaka.startswith("06 H"), plaka)                                      # tahmin: H grubuna geçmiş
            self.assertIn("son kayıtlı gözlem", SATIR.search(h)[0]); self.assertNotIn(plaka, SATIR.search(h)[0])
        finally: shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__": unittest.main()
