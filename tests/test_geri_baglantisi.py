"""81 il sayfasında "← Ana sayfaya dön" bağlantısı: H1'in hemen üstünde, gerçek HTML bağlantısı (JS gerektirmez), ana sayfayı EN ÜSTTEN açar (href="/", anchor yok); mevcut "Plaka Tahmini" bağlantısı korunur;
klavye (Tab/Enter) ile erişilir ve odak halkası görünür; SEO, GoatCounter ve tahmin alanları değişmez."""
import glob, json, os, re, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
from test_il_sayfasi import veri, sayfa, slug, TAM
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
ONCEKI_URETIM = "7086120"          # metin/adres değişmeden önceki üretim sürümü ("← Tüm illere dön" → /#il-baslik); yalnızca SEO alanları karşılaştırılır
BAGLANTI = '<p class="geri"><a href="/"><span aria-hidden="true">←</span> Ana sayfaya dön</a></p>'

class Html81(unittest.TestCase):
    def test_81_ilde_gercek_baglanti_h1_in_hemen_ustunde_ve_dogru_url(self):
        sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81)
        for yol in sayfalar:
            h = u.oku(yol); ad = os.path.basename(yol)
            self.assertEqual(h.count(BAGLANTI), 1, ad); self.assertEqual(h.count("Ana sayfaya dön"), 1, ad); self.assertNotIn("Tüm illere dön", h, ad); self.assertNotIn("il-baslik", h, ad)
            self.assertRegex(h, r'<div class="eyebrow"><a href="/">Plaka Tahmini</a> · \d\d [^<]+</div>\n' + re.escape(BAGLANTI) + r'\n<h1>', ad)         # eyebrow (mevcut ana sayfa bağlantısı) → geri bağlantısı → H1
            self.assertEqual(re.findall(r'<p class="geri"><a href="([^"]*)"', h), ["/"], ad)                                                         # tüm sayfalarda aynı, mutlak ve anchor'sız hedef: ana sayfa en üstten açılır
            self.assertNotIn("onclick", BAGLANTI); self.assertNotRegex(re.search(r'<p class="geri">.*?</p>', h)[0], r"<button|role=|tabindex")    # düz <a href>: tuş/odak davranışı tarayıcıdan

    def test_hedef_ana_sayfa_ve_ilk_ekranda_uc_kart(self):
        self.assertIn('<h1>Türkiye Plaka Sırası Tahminleri</h1>', ANA); self.assertEqual(len(re.findall(r'<a class="kart" href="/il/', ANA)), 3)             # "/" açılışında üstte H1 ve İstanbul/Ankara/İzmir kartları

    def test_seo_ve_analitik_alanlari_degismedi(self):
        for s in veri():
            ad = slug(TAM.get(s["il"], s["il"])); yeni = sayfa(s["il"])
            eski = subprocess.run(["git", "show", f"{ONCEKI_URETIM}:il/{ad}.html"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout
            for desen in (r"<title>.*?</title>", r'<meta name="description" content="[^"]*">', r'<link rel="canonical" href="[^"]*">', r"<h1>.*?</h1>", r'<meta property="og:[a-z:]+" content="[^"]*">', r'<script type="application/ld\+json">.*?</script>',
                          r"<!--OLCUM-->.*?<!--/OLCUM-->", r'<p class="olcum-notu">.*?</p>', r'<p class="buyuk mono" data-live="plaka">[^<]*</p>'):
                self.assertEqual(re.findall(desen, yeni, re.S), re.findall(desen, eski, re.S), f"{ad}: {desen}")

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
            self.assertEqual((o["sayi"], o["href"], o["metin"], o["eyebrowHref"]), (1, "/", "← Ana sayfaya dön", "/"), kim)
            self.assertTrue(o["sira"] and o["ustuH1"] and o["eyebrowAlti"], kim); self.assertLessEqual(o["bosluk"], 20, kim)                    # H1'in hemen üstünde, eyebrow'un altında
            self.assertGreaterEqual(o["px"], 15, kim); self.assertGreaterEqual(o["yuk"], 32, kim); self.assertLessEqual(o["yuk"], 44, kim); self.assertLessEqual(o["tasma"], 0, kim); self.assertTrue(o["ekranda"], kim)   # küçük ama dokunulabilir, ilk ekranda
            self.assertEqual((x["tab1"]["etiket"], x["tab1"]["href"]), ("A", "/"), kim)                                                         # 1. Tab: mevcut "Plaka Tahmini" bağlantısı
            self.assertEqual((x["tab2"]["etiket"], x["tab2"]["href"], x["tab2"]["metin"]), ("A", "/", "← Ana sayfaya dön"), kim)      # 2. Tab: geri bağlantısı
            self.assertRegex(x["tab2"]["cerceve"], r"^solid [3-9]", kim)                                                                        # klavye odağında görünür halka (≥ 3 px)
            self.assertEqual((x["sonra"]["yol"], x["sonra"]["hash"], x["sonra"]["scrollY"], x["sonra"]["baslik"]), ("/", "", 0, "Türkiye Plaka Sırası Tahminleri"), kim)   # Enter: ana sayfa en üstten, anchor yok
            self.assertTrue(x["sonra"]["h1Ekranda"] and x["sonra"]["ilkKartEkranda"] and x["sonra"]["kartSayisi"] == 3, kim)                    # H1 ve İstanbul/Ankara/İzmir kartları ilk ekranda

if __name__ == "__main__": unittest.main()
