"""Ana sayfa başlık satırı: H1'in ("Türkiye Plaka Sırası Tahminleri") sağında "/istatistik" duyuru bağlantısı (YENİ rozeti + sade grafik simgesi + "Plaka İstatistikleri").
Yan yana sığdığı genişliklerde (700 px ve üstü) H1 ile aynı satırda ve içerik sütununun sağ kenarında; sığmadığında H1'in hemen altında, sağa hizalı. H1 metni, puntosu ve satır sayısı değişmez;
alttaki yeşil istatistik kutusu, SEO etiketleri, il sayfaları ve betikler etkilenmez. Tarayıcı testleri Chrome headless ister (yoksa atlanır)."""
import glob, html, json, os, re, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
BAGLANTI = ('<a class="yeni-bag" href="/istatistik"><span class="rozet">YENİ</span> <svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 16 16">'
            '<rect x="1.5" y="8.5" width="3" height="6" rx="1"/><rect x="6.5" y="5" width="3" height="9.5" rx="1"/><rect x="11.5" y="1.5" width="3" height="13" rx="1"/></svg> <span class="ad">Plaka İstatistikleri</span></a>')
GENISLIK = [320, 375, 390, 412, 430, 768, 1024, 1440]
ESIK = 700                                     # ölçüm: içerik sütunu 668 px olduğunda (700 px ekran) H1 (444 px) + 20 px boşluk + bağlantı (204 px) yan yana sığar
def metin(x): return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))).strip()

class StatikHtml(unittest.TestCase):
    def test_baglanti_h1in_hemen_ardinda_ve_tek(self):
        self.assertIn('  <div class="eyebrow">Plaka Tahmini</div>\n  <div class="baslik-satiri">\n  <h1>Türkiye Plaka Sırası Tahminleri</h1>\n  ' + BAGLANTI + '\n  </div>\n  <p class="alt-baslik">', ANA)
        self.assertEqual(ANA.count('class="yeni-bag"'), 1); self.assertEqual(ANA.count('class="baslik-satiri"'), 1); self.assertEqual(len(re.findall(r"<h1\b", ANA)), 1)
        self.assertEqual(metin(BAGLANTI), "YENİ Plaka İstatistikleri")                                                    # ekran okuyucu ve JS'siz metin: rozet ile ad arasında boşluk var
        self.assertNotRegex(BAGLANTI, r"onclick|data-|target=|javascript:")                                               # sıradan bağlantı: betik, olay ya da yeni sekme yok

    def test_alttaki_yesil_kutu_korunur_ve_iki_baglanti_ayni_sayfaya_gider(self):
        self.assertEqual(re.findall(r'href="(/istatistik[^"]*)"', ANA), ["/istatistik", "/istatistik"])
        self.assertLess(ANA.index('class="yeni-bag"'), ANA.index("<!--ANA:ISTATISTIK-->")); self.assertIn('<p class="istatistik" style="margin:14px 0"><a href="/istatistik"', ANA)
        self.assertIn("Plaka istatistikleri ve grafikler", ANA)

    def test_stil_yalnizca_ana_sayfanin_kendi_css_inde(self):
        stil = re.search(r"<style>(.*?)</style>", ANA, re.S)[1]; ortak = re.search(r"/\*ANA:TEMEL-CSS\*/(.*?)/\*/ANA:TEMEL-CSS\*/", stil, re.S)[1]
        self.assertNotRegex(ortak, r"yeni-bag|baslik-satiri"); self.assertIn(".baslik-satiri{display:flex;flex-wrap:wrap;", stil); self.assertIn(".baslik-satiri h1{margin:0}", stil)
        self.assertNotRegex(stil, r"\.yeni-bag[^{]*\{[^}]*outline\s*:")                                                   # odak halkası genel a:focus-visible kuralından gelir; bastırılmaz
        self.assertIn("a:focus-visible", ortak); self.assertNotRegex(stil, r"@keyframes|animation|transition")           # animasyon yok
        k = u.oku(os.path.join(u.ROOT, "generate_il_pages.py")); self.assertNotRegex(k, r"yeni-bag|baslik-satiri")       # üretici bu satırı yazmaz/ezmez: elle yazılmış ana sayfa bölümü

    def test_il_sayfalari_ve_istatistik_sayfasi_etkilenmez(self):
        sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81)
        for p in sayfalar + [os.path.join(u.ROOT, "istatistik.html")]: self.assertNotRegex(u.oku(p), r"yeni-bag|baslik-satiri", p)

    def test_uretim_basligi_ve_baglantiyi_korur(self):
        d = u.kopya(ekstra=("sitemap.xml", "il"), il_dizini=False)
        try:
            r = u.uret(d, "--bugun", u.sayfa_bilgisi(os.path.join(u.ROOT, "il", "konya.html"))); self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(u.oku(os.path.join(d, "index.html")), ANA); self.assertEqual(u.oku(os.path.join(d, "sitemap.xml")), u.oku(os.path.join(u.ROOT, "sitemap.xml")))    # aynı günle yeniden üretim: ana sayfa ve sitemap bayt bayt aynı
        finally: shutil.rmtree(d, ignore_errors=True)

@unittest.skipUnless(CHROME, "Chrome yok")
class Tarayici(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_il_yerlesim import sunucu
        d = tempfile.mkdtemp(prefix="plaka_baslik_", dir=u.ROOT)
        try:
            h = u.oku(os.path.join(u.ROOT, "tests", "ui", "ana_baslik.html")).replace("__GENISLIKLER__", json.dumps(GENISLIK)).replace("__TIKLA__", json.dumps([375, 1440]))
            with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(h)
            srv, port = sunucu()
            try: r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=90000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=150)
            finally: srv.shutdown(); srv.server_close()
            m = re.search(r"SONUC (\[.*?\])\s*</pre>", r.stdout, re.S); assert m, r.stderr[-400:] + r.stdout[-300:]
            cls.sonuc = json.loads(html.unescape(m[1]))
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_sekiz_genislikte_tasma_ve_ust_uste_binme_yok(self):
        self.assertEqual([r["w"] for r in self.sonuc], GENISLIK)
        for r in self.sonuc:
            k = f"{r['w']}px"; b = r["bag"]
            self.assertLessEqual(r["sw"], r["cw"], k); self.assertFalse(r["h1Kesisir"], k); self.assertFalse(r["altKesisir"], k); self.assertFalse(r["gozKesisir"], k)
            self.assertGreaterEqual(b["sol"], r["icerikSol"] - 0.5, k); self.assertLessEqual(b["sag"], r["icerikSag"] + 0.5, k)            # içerik sütununun (16 px kenar boşluğu) içinde

    def test_h1_metni_puntosu_ve_satir_sayisi_degismedi(self):
        for r in self.sonuc:
            k = f"{r['w']}px"; self.assertEqual(r["h1Metin"], "Türkiye Plaka Sırası Tahminleri", k)
            self.assertAlmostEqual(r["h1Px"], max(28, min(40, 0.07 * r["w"])), delta=0.02, msg=k)                                         # clamp(1.75rem, 7vw, 2.5rem): küçültülmedi
            self.assertEqual(r["h1Satir"], 2 if r["w"] == 320 else 1, k)                                                                  # 320 px'te bağlantıdan önce de iki satırdı; bağlantı H1'i bölmez
            self.assertAlmostEqual(r["h1Sol"], r["icerikSol"], delta=0.5, msg=k)

    def test_genis_ekranda_yan_yana_dar_ekranda_altta_saga_hizali(self):
        for r in self.sonuc:
            k = f"{r['w']}px"; b = r["bag"]; self.assertEqual(r["yanYana"], r["w"] >= ESIK, k)
            self.assertAlmostEqual(b["sag"], r["icerikSag"], delta=0.5, msg=k)                                                            # her iki durumda da sağ kenara hizalı
            if r["yanYana"]:
                self.assertGreaterEqual(b["sol"] - r["h1Sag"], 20, k)                                                                      # başlıkla arasında en az 20 px
                self.assertAlmostEqual(r["altUst"] - r["h1Alt"], 18, delta=0.6, msg=k)                                                    # başlık satırının yüksekliği büyümedi: alt başlık eski yerinde (18 px)
            else:
                self.assertGreaterEqual(b["ust"], r["h1Alt"] - 0.6, k); self.assertLess(b["ust"] - r["h1Alt"], 4, k)                       # H1'in hemen altında
                self.assertAlmostEqual(r["altUst"] - r["h1Alt"], 48, delta=0.6, msg=k)                                                    # sayfanın geri kalanı yalnızca 30 px aşağı kayar (18 → 48)

    def test_baglanti_okunur_dokunulabilir_ve_h1den_geri_planda(self):
        for r in self.sonuc:
            k = f"{r['w']}px"; b = r["bag"]
            self.assertEqual(b["metin"], "YENİ Plaka İstatistikleri", k); self.assertEqual(b["rozet"], "YENİ", k); self.assertTrue(b["simge"], k); self.assertTrue(b["tekSatir"], k)
            self.assertEqual(b["px"], 15, k); self.assertLess(b["px"], r["h1Px"] / 1.8, k)                                                 # belirgin ama H1'in yarısından küçük
            self.assertGreaterEqual(b["yuk"], 40, k); self.assertGreaterEqual(b["gen"], 180, k)                                           # dokunma alanı
            self.assertEqual(b["renk"], "rgb(13, 92, 63)", k)                                                                             # alttaki yeşil kutunun yazı rengi (#0d5c3f)

    def test_baglanti_dogru_adrese_gider_ve_klavyeyle_erisilir(self):
        for r in self.sonuc:
            k = f"{r['w']}px"; self.assertEqual(r["bag"]["href"], "/istatistik", k); self.assertTrue(r["odak"]["aktif"], k); self.assertEqual(r["odak"]["cerceve"], "solid 3px", (k, r["odak"]))
            self.assertTrue(r["sira"]["h1Once"] and r["sira"]["karttanOnce"], k); self.assertIsNone(r["sira"]["tabindex"], k)
            self.assertTrue(r["kutuVar"], k); self.assertEqual(r["baglantiSayisi"], 2, k)                                                 # alttaki kutu yerinde
        tik = {r["w"]: r["tik"] for r in self.sonuc if "tik" in r}; self.assertEqual(set(tik), {375, 1440})
        for w, t in tik.items(): self.assertEqual(t["yol"], "/istatistik", w); self.assertIn("Plaka İstatistikleri", t["baslik"], w)

if __name__ == "__main__": unittest.main()
