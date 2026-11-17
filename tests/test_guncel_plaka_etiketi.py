"""81 il sayfasında büyük tahmini plakanın üstündeki alt başlık: "[İl] Güncel Plaka Serisi (Tahmini)" (eski "Tahmini güncel plaka" etiketinin yerine; ikinci bir başlık eklenmez).
Statik HTML'de bulunur (JS ile eklenmez), il adı veriden gelir; title, H1, meta description, canonical, JSON-LD, ana sayfa ve istatistik sayfası bu değişiklikten etkilenmez.
Tarayıcıda (Chrome headless) 375/390/430 px: taşma yok, en çok iki satır, büyük plaka tek satır ve hemen altında, ana eylem ilk ekranda. Chrome yoksa tarayıcı testleri atlanır."""
import glob, json, os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_il_sayfasi import veri, sayfa, slug, inv, tr, TAM, E0, metin
from test_ana_sayfa_regresyon import CHROME
import datetime as dt
IFADE = "Güncel Plaka Serisi (Tahmini)"
AYRI_BAKILAN = ("İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Konya", "Eskişehir", "Denizli")
def ad(s): return TAM.get(s["il"], s["il"])
def etiket(s): return f'<h2 class="e">{ad(s)} {IFADE}</h2>'

class StatikHtml(unittest.TestCase):
    def test_81_ilde_tek_alt_baslik_dogru_yerde_ve_dogru_il_adiyla(self):
        n = 0; adlar = set()
        for s in veri():
            h = sayfa(s["il"]); e = etiket(s); n += 1; adlar.add(ad(s))
            self.assertEqual(h.count(e), 1, s["il"]); self.assertEqual(h.count(IFADE), 1, s["il"]); self.assertEqual(len(re.findall(r"güncel plaka serisi", h, re.I)), 1, s["il"])     # tekrar yok: ifade sayfada bir kez
            self.assertNotIn("Tahmini güncel plaka", h, s["il"]); self.assertEqual(len(re.findall(r'class="e"', h)), 1, s["il"])                                                         # eski etiketin YERİNE geçti; ikinci etiket yok
            self.assertRegex(h, r'<section aria-label="Özet" data-baslangic="\d{4}-\d\d-\d\d">\n' + re.escape(e) + r'\n<p class="buyuk mono" data-live="plaka">\d\d [A-Z]{3} \d{3}</p>\n<p class="alt">', s["il"])
            self.assertLess(h.index("<body>"), h.index(e), s["il"]); self.assertLess(h.index(e), h.index("</main>"), s["il"]); self.assertNotIn(IFADE, "".join(re.findall(r"<script.*?</script>", h, re.S)), s["il"])                             # statik gövdede; betik eklemiyor
            self.assertIn(f"<h1>{ad(s)} Plaka Sırası Hangi Harfte?</h1>", h, s["il"])                                                                                                   # il adı H1'dekiyle aynı
        self.assertEqual(n, 81); self.assertEqual(len(adlar), 81)
        self.assertLessEqual({"Kahramanmaraş", "Afyonkarahisar", "Şanlıurfa", "Ağrı", "Çanakkale", "Iğdır", "Muş", "Gümüşhane", "Kırıkkale", "Düzce", "İzmir", "Eskişehir"}, adlar)     # kısaltma (K.Maraş, Afyon) değil tam ad; Türkçe harfler

    def test_turkce_karakterler_dosyada_bozulmadan_utf8(self):
        for s in veri():
            with open(os.path.join(u.ROOT, "il", slug(ad(s)) + ".html"), "rb") as f: b = f.read()
            self.assertIn(etiket(s).encode("utf-8"), b, s["il"]); self.assertNotIn("�", b.decode("utf-8"), s["il"]); self.assertIn(b'<meta charset="utf-8">', b[:200]); self.assertIn(b'<html lang="tr">', b[:60])     # lang="tr": büyük harfe çevrilen etikette i → İ

    def test_ayri_bakilan_sekiz_il(self):
        for a in AYRI_BAKILAN:
            h = u.oku(os.path.join(u.ROOT, "il", slug(a) + ".html")); self.assertEqual(h.count(f'<h2 class="e">{a} {IFADE}</h2>'), 1, a)

    def test_korunan_seo_alanlari_veriden_beklenen_degerlerde(self):
        for s in veri():
            h = sayfa(s["il"]); a = ad(s); g, n = s["obs"][-1]; sr, no = inv(n); ld = E0 + dt.timedelta(days=g); yil = re.search(r'data-baslangic="(\d{4})', h)[1]
            baslik = f"{a} Plaka Sırası Hangi Harfte? Güncel Seri ({yil})"
            tanim = f"{a} plaka sırası hangi harfte? Son gözlem: {s['kod']:02d} {sr} {no:03d} ({tr(ld)}). Güncel tahmini seriyi ve plakanızın tahmini çıkış tarihini araçla hesaplayın."
            self.assertEqual(re.findall(r"<title>(.*?)</title>", h), [baslik], s["il"]); self.assertEqual(re.findall(r'<meta name="description" content="([^"]*)">', h), [tanim], s["il"])
            self.assertEqual(re.findall(r'<link rel="canonical" href="([^"]*)">', h), [f"https://plakatahmini.com/il/{slug(a)}"], s["il"])
            self.assertEqual(re.findall(r"<h1>(.*?)</h1>", h), [f"{a} Plaka Sırası Hangi Harfte?"], s["il"])
            ld_json = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]; self.assertEqual(len(ld_json), 1, s["il"])
            self.assertEqual(ld_json[0], {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Plaka Tahmini", "item": "https://plakatahmini.com/"},
                {"@type": "ListItem", "position": 2, "name": f"{a} Plaka Sırası", "item": f"https://plakatahmini.com/il/{slug(a)}"}]}, s["il"])
            self.assertNotIn(IFADE, baslik + tanim)

    def test_baslik_sirasi_h1_sonra_alt_baslik_sonra_araclar(self):
        for s in veri():
            h = re.sub(r"<script.*?</script>", "", sayfa(s["il"]), flags=re.S); bas = re.findall(r"<(h[1-6])\b[^>]*>(.*?)</\1>", h, re.S)
            self.assertEqual([(b[0], metin(b[1])) for b in bas[:3]], [("h1", f"{ad(s)} Plaka Sırası Hangi Harfte?"), ("h2", f"{ad(s)} {IFADE}"), ("h2", "Hedef plakanın tahmini tarihi")], s["il"])
            self.assertEqual(h.count('<section aria-label="Özet"'), 1, s["il"])                                # bölgenin ekran okuyucu adı korunur

    def test_ana_sayfa_ve_istatistik_sayfasi_etkilenmez(self):
        ana = u.oku(os.path.join(u.ROOT, "index.html")); ist = u.oku(os.path.join(u.ROOT, "istatistik.html"))
        self.assertNotIn(IFADE, ana); self.assertNotIn(IFADE, ist); self.assertNotIn("h2.e", ana); self.assertNotIn("h2.e", ist)
        self.assertIn("<h2>İllere Göre Güncel Plaka Serileri</h2>", ana)                                         # ana sayfanın kendi başlığı yerinde

    def test_uretici_ifadeyi_sablondan_yazar_il_adi_kacisli(self):
        k = u.oku(os.path.join(u.ROOT, "generate_il_pages.py"))
        self.assertEqual(k.count('<h2 class="e">{html.escape(ad)} Güncel Plaka Serisi (Tahmini)</h2>'), 1); self.assertNotIn("Tahmini güncel plaka", k)
        css_ana = re.search(r'^CSS = """(.*?)"""', k, re.S | re.M)[1]; self.assertNotIn("h2.e", css_ana)       # yeni kural yalnızca il sayfası CSS'inde (IL_CSS); ortak CSS'e dokunulmadı
        self.assertRegex(k, r'(?m)^IL_CSS = ".*h2\.e\{line-height:1\.55;letter-spacing:\.06em\}"$')

@unittest.skipUnless(CHROME, "Chrome yok")
class Tarayici(unittest.TestCase):
    GENISLIK = [375, 390, 430]
    @classmethod
    def setUpClass(cls):
        from test_il_yerlesim import calistir
        sayfalar = ["/il/" + os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html")))]; assert len(sayfalar) == 81
        cls.sonuc = calistir(sayfalar, cls.GENISLIK, etkilesim=False); cls.adlar = {"/il/" + slug(ad(s)): ad(s) for s in veri()}

    def test_tasma_yok_ve_etiket_govde_icinde(self):
        self.assertEqual(len(self.sonuc), 81 * len(self.GENISLIK))
        for r in self.sonuc:
            e = r["etiket"]; k = f"{r['sayfa']} {r['w']}px"
            self.assertLessEqual(r["sw"], r["cw"], k); self.assertEqual(r["tasan"], [], k)
            self.assertEqual(e["sol"], 16, k); self.assertLessEqual(e["sag"], r["cw"] - 16, k)                 # 16 px kenar boşluğunun içinde

    def test_alt_baslik_metni_gorunumu_ve_satir_sayisi(self):
        iki_satir = {w: set() for w in self.GENISLIK}
        for r in self.sonuc:
            e = r["etiket"]; k = f"{r['sayfa']} {r['w']}px"
            self.assertEqual(e["tag"], "H2", k); self.assertEqual(e["metin"], f"{self.adlar[r['sayfa']]} {IFADE}", k); self.assertEqual(e["px"], 13, k)      # eski etiketin puntosu korunur
            self.assertIn(e["satir"], (1, 2), k)
            if e["satir"] == 2: iki_satir[r["w"]].add(r["sayfa"])
        uzun = {"/il/kahramanmaras", "/il/afyonkarahisar"}                                                     # yalnızca en uzun iki il adı dar ekranda ikinci satıra iner
        self.assertLessEqual(iki_satir[375], uzun); self.assertLessEqual(iki_satir[390], uzun); self.assertEqual(iki_satir[430], set())

    def test_buyuk_plaka_hemen_altta_tek_satir_ve_ana_eylem_ilk_ekranda(self):
        for r in self.sonuc:
            e = r["etiket"]; k = f"{r['sayfa']} {r['w']}px"
            self.assertTrue(e["sonraki"], k); self.assertGreaterEqual(e["bosluk"], 0, k); self.assertLessEqual(e["bosluk"], 8, k)
            self.assertEqual(r["buyukSatir"], 1, k); self.assertGreaterEqual(r["buyukPx"], 40, k); self.assertEqual(r["nwSatir"], 1, k)
            self.assertLess(r["ctaAlt"], 700, k); self.assertFalse(r["uyari"], k)

if __name__ == "__main__": unittest.main()
