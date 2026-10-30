"""81 il sayfasında "← Tüm illere dön" bağlantısı: H1'in hemen üstünde, gerçek HTML bağlantısı (JS gerektirmez), ana sayfadaki il seçimi bölümüne (/#il-baslik) götürür; mevcut "Plaka Tahmini" bağlantısı korunur;
klavye (Tab/Enter) ile erişilir ve odak halkası görünür; SEO, GoatCounter ve tahmin alanları değişmez."""
import glob, json, os, re, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
from test_il_sayfasi import veri, sayfa, slug, TAM
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
ONCEKI_URETIM = "dac5141"          # bağlantı eklenmeden önceki üretim sürümü
BAGLANTI = '<p class="geri"><a href="/#il-baslik"><span aria-hidden="true">←</span> Tüm illere dön</a></p>'

class Html81(unittest.TestCase):
    def test_81_ilde_gercek_baglanti_h1_in_hemen_ustunde_ve_dogru_url(self):
        sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81)
        for yol in sayfalar:
            h = u.oku(yol); ad = os.path.basename(yol)
            self.assertEqual(h.count(BAGLANTI), 1, ad); self.assertEqual(h.count("Tüm illere dön"), 1, ad)
            self.assertRegex(h, r'<div class="eyebrow"><a href="/">Plaka Tahmini</a> · \d\d [^<]+</div>\n' + re.escape(BAGLANTI) + r'\n<h1>', ad)         # eyebrow (mevcut ana sayfa bağlantısı) → geri bağlantısı → H1
            self.assertEqual(re.findall(r'href="(/#il-baslik)"', h), ["/#il-baslik"], ad)                                                           # tüm sayfalarda aynı, mutlak ve doğru hedef (il adresine bağlı değil)
            self.assertNotIn("onclick", BAGLANTI); self.assertNotRegex(re.search(r'<p class="geri">.*?</p>', h)[0], r"<button|role=|tabindex")    # düz <a href>: tuş/odak davranışı tarayıcıdan

    def test_hedef_ana_sayfada_var_ve_il_secimi_bolumu(self):
        self.assertEqual(ANA.count('id="il-baslik"'), 1)
        self.assertRegex(ANA, r'<section class="il-bolum" aria-labelledby="il-baslik">\s*<h2 id="il-baslik">İlinizin plaka sırasını öğrenin</h2>\s*<form id="il-form"')

    def test_ana_sayfa_ve_seo_degismedi(self):
        self.assertEqual(subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "index.html", "sitemap.xml", "assets", "forecast.py", "data"], cwd=u.ROOT).returncode, 0, "ana sayfa, sitemap, motor, veri ve analitik dosyaları değişmemeli")
        for s in veri():
            ad = slug(TAM.get(s["il"], s["il"])); yeni = sayfa(s["il"])
            eski = subprocess.run(["git", "show", f"{ONCEKI_URETIM}:il/{ad}.html"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout
            for desen in (r"<title>.*?</title>", r'<meta name="description" content="[^"]*">', r'<link rel="canonical" href="[^"]*">', r"<h1>.*?</h1>", r'<meta property="og:[a-z:]+" content="[^"]*">', r'<script type="application/ld\+json">.*?</script>',
                          r"<!--OLCUM-->.*?<!--/OLCUM-->", r'<p class="olcum-notu">.*?</p>', r'<p class="buyuk mono" data-live="plaka">[^<]*</p>'):
                self.assertEqual(re.findall(desen, yeni, re.S), re.findall(desen, eski, re.S), f"{ad}: {desen}")
            self.assertEqual(yeni.replace(BAGLANTI + "\n", "").replace(".geri{margin:0 0 4px}.geri a{display:inline-block;padding:8px 0;font-size:15px;font-weight:600;color:#1f63bb;text-decoration:none}.geri a:hover{text-decoration:underline}", ""), eski, f"{ad}: yalnızca bağlantı satırı ve CSS eklenmeli")

@unittest.skipUnless(CHROME and u.NODE, "Chrome/Node yok")
class KlavyeVeKonum(unittest.TestCase):
    def test_tab_enter_odak_halkasi_ve_ana_sayfa_il_secimine_gider(self):
        from test_il_yerlesim import sunucu
        srv, port = sunucu()
        try:
            sayfalar = ["/il/konya", "/il/istanbul", "/il/hakkari", "/il/kars", "/il/ankara"]
            r = subprocess.run([u.NODE, os.path.join(u.ROOT, "tests", "ui", "geri_baglantisi.js"), CHROME, f"http://127.0.0.1:{port}", *sayfalar], capture_output=True, text=True, timeout=240); self.assertEqual(r.returncode, 0, r.stderr)
        finally: srv.shutdown(); srv.server_close()
        sonuc = json.loads(r.stdout); self.assertEqual(len(sonuc), 2 * len(sayfalar)); self.assertEqual({x["w"] for x in sonuc}, {375, 1440})
        for x in sonuc:
            self.assertNotIn("hata", x, x); o = x["olcum"]; kim = (x["w"], x["s"])
            self.assertEqual((o["sayi"], o["href"], o["metin"], o["eyebrowHref"]), (1, "/#il-baslik", "← Tüm illere dön", "/"), kim)
            self.assertTrue(o["sira"] and o["ustuH1"] and o["eyebrowAlti"], kim); self.assertLessEqual(o["bosluk"], 20, kim)                    # H1'in hemen üstünde, eyebrow'un altında
            self.assertGreaterEqual(o["px"], 15, kim); self.assertGreaterEqual(o["yuk"], 32, kim); self.assertLessEqual(o["yuk"], 44, kim); self.assertLessEqual(o["tasma"], 0, kim); self.assertTrue(o["ekranda"], kim)   # küçük ama dokunulabilir, ilk ekranda
            self.assertEqual((x["tab1"]["etiket"], x["tab1"]["href"]), ("A", "/"), kim)                                                         # 1. Tab: mevcut "Plaka Tahmini" bağlantısı
            self.assertEqual((x["tab2"]["etiket"], x["tab2"]["href"], x["tab2"]["metin"]), ("A", "/#il-baslik", "← Tüm illere dön"), kim)      # 2. Tab: yeni bağlantı
            self.assertRegex(x["tab2"]["cerceve"], r"^solid [3-9]", kim)                                                                        # klavye odağında görünür halka (≥ 3 px)
            self.assertEqual((x["sonra"]["yol"], x["sonra"]["hash"], x["sonra"]["baslik"]), ("/", "#il-baslik", "İlinizin plaka sırasını öğrenin"), kim)   # Enter: ana sayfa, il seçimi bölümü
            self.assertTrue(x["sonra"]["ekranda"] and x["sonra"]["formVar"], kim)                                                               # bölüm görünür alana kaydırıldı

if __name__ == "__main__": unittest.main()
