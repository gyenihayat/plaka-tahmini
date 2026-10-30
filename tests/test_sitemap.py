"""Sitemap: 82 URL; ana sayfa lastmod'u yalnızca ANLAMLI içerik değişince (gözlem verisi, metin/şablon/CSS) üretim gününe taşınır; günlük tarih/seri değişimi
(kartlardaki referans gün) tek başına yeni içerik sayılmaz. 81 il sayfasının lastmod'u ana sayfa değişiminden etkilenmez. İz, index.html içindeki ANA:SURUM bölgesinde saklanır."""
import datetime as dt, json, os, re, shutil, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
E0 = dt.date(2024, 1, 1)
def lm(yol):
    with open(yol, encoding="utf-8") as f: return dict(re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", f.read()))
ANA = "https://plakatahmini.com/"

class MevcutSitemap(unittest.TestCase):
    def test_82_url_gecerli_tarihler_ve_ana_sayfa_izi_var(self):
        m = lm(os.path.join(u.ROOT, "sitemap.xml")); self.assertEqual(len(m), 82); self.assertIn(ANA, m)
        for url, t in m.items(): dt.date.fromisoformat(t)
        son = E0 + dt.timedelta(days=max(x["obs"][-1][0] for x in json.loads(u.oku(os.path.join(u.ROOT, "data", "tahmin_data.json")))["iller"]))
        self.assertGreaterEqual(dt.date.fromisoformat(m[ANA]), son)                       # ana sayfa en az son gözlem kadar yeni
        self.assertRegex(u.oku(os.path.join(u.ROOT, "index.html")), r"<!--ANA:SURUM-->\s*[0-9a-f]{16}\s*<!--/ANA:SURUM-->")

class LastmodKurali(unittest.TestCase):
    def _kopya(self):
        return u.kopya(ekstra=("sitemap.xml", "il"), il_dizini=False)
    def _uret(self, d, bugun):
        r = u.uret(d, "--bugun", bugun); self.assertEqual(r.returncode, 0, r.stderr)

    def test_gunluk_tarih_degisimi_lastmod_degistirmez(self):
        d = self._kopya()
        try:
            once = lm(os.path.join(d, "sitemap.xml")); self._uret(d, "2026-10-30"); self.assertEqual(lm(os.path.join(d, "sitemap.xml")), once)      # aynı gün yeniden üretim
            for bugun in ("2026-11-02", "2026-11-03", "2026-11-05", "2026-11-10"):
                self._uret(d, bugun); self.assertEqual(lm(os.path.join(d, "sitemap.xml")), once, bugun)
                self.assertIn(f'data-kart="tarih">', u.oku(os.path.join(d, "index.html")))                              # kart tarihleri gerçekten güncellendi
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_yeni_gozlem_ana_sayfa_ve_ilgili_il_lastmodunu_yeniler_digerlerini_degil(self):
        d = self._kopya()
        try:
            once = lm(os.path.join(d, "sitemap.xml")); yol = os.path.join(d, "data", "tahmin_data.json"); v = json.loads(u.oku(yol))
            k = next(x for x in v["iller"] if x["il"] == "Konya"); k["obs"].append([k["obs"][-1][0] + 7, k["obs"][-1][1] + 1700])
            js = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
            with open(yol, "w", encoding="utf-8") as f: f.write(js)
            ana = os.path.join(d, "index.html"); h = u.oku(ana)
            with open(ana, "w", encoding="utf-8") as f: f.write(re.sub(r"const DATA = .*?;\n", lambda m: "const DATA = " + js + ";\n", h, count=1))      # tablo_ekle.py'nin yaptığı DATA güncellemesi
            self._uret(d, "2026-11-06"); yeni = lm(os.path.join(d, "sitemap.xml"))
            self.assertEqual(sorted(k_ for k_ in yeni if yeni[k_] != once[k_]), [ANA, ANA + "il/konya"]); self.assertEqual(yeni[ANA], "2026-11-06"); self.assertEqual(yeni[ANA + "il/konya"], "2026-11-06")
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_metin_sablon_degisimi_yalniz_ana_sayfa_lastmodunu_yeniler(self):
        d = self._kopya()
        try:
            once = lm(os.path.join(d, "sitemap.xml")); ana = os.path.join(d, "index.html"); h = u.oku(ana); self.assertIn("<h1>Türkiye Plaka Sırası Tahminleri</h1>", h)
            with open(ana, "w", encoding="utf-8") as f: f.write(h.replace("<h1>Türkiye Plaka Sırası Tahminleri</h1>", "<h1>Türkiye Plaka Sırası Tahminleri (güncel)</h1>"))
            self._uret(d, "2026-11-06"); yeni = lm(os.path.join(d, "sitemap.xml"))
            self.assertEqual(sorted(k_ for k_ in yeni if yeni[k_] != once[k_]), [ANA]); self.assertEqual(yeni[ANA], "2026-11-06")
            self._uret(d, "2026-11-09"); self.assertEqual(lm(os.path.join(d, "sitemap.xml")), yeni)                  # sonraki günlük üretim yine lastmod'u oynatmaz
        finally: shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__": unittest.main()
