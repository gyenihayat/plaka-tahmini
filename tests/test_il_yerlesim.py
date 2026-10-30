"""Gerçek tarayıcıda (Chrome headless) 81 il sayfası: 320/375/390/768/1440 px'te yatay taşma, büyük punto hiyerarşisi, ilk ekranda tek ana eylem ve araca erişim,
tek satır plaka değerleri, form erişilebilirliği ve araç etkileşimi; motor dosyası yüklenemezse görünür hata. Chrome yoksa atlanır."""
import functools, glob, html, http.server, json, os, re, socket, subprocess, sys, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_ana_sayfa_regresyon import CHROME
GENISLIK = [320, 375, 390, 768, 1440]

def sunucu(engelle=()):
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k): pass
        def do_GET(self):
            yol = self.path.split("?")[0]
            if yol in engelle: self.send_error(404); return
            if "." not in os.path.basename(yol) and os.path.isfile(os.path.join(u.ROOT, yol.lstrip("/") + ".html")): self.path = yol + ".html"      # Vercel cleanUrls: /il/konya -> il/konya.html
            super().do_GET()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port
def calistir(sayfalar, genislikler, etkilesim=True, engelle=()):
    import tempfile, shutil
    d = tempfile.mkdtemp(prefix="plaka_yerlesim_", dir=u.ROOT)            # sunucu kökü depo: /assets ve /il gerçek yollarıyla çalışır
    try:
        with open(os.path.join(u.ROOT, "tests", "ui", "yerlesim.html"), encoding="utf-8") as f: h = f.read()
        h = h.replace("__SAYFALAR__", json.dumps(sayfalar)).replace("__GENISLIKLER__", json.dumps(genislikler)).replace("__ETKILESIM__", "true" if etkilesim else "false")
        with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(h)
        srv, port = sunucu(engelle)
        try: r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=240000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=280)
        finally: srv.shutdown(); srv.server_close()
        m = re.search(r"SONUC (\[.*?\])\s*</pre>", r.stdout, re.S); assert m, r.stderr[-400:] + r.stdout[-300:]
        return json.loads(html.unescape(m[1]))
    finally: shutil.rmtree(d, ignore_errors=True)

@unittest.skipUnless(CHROME, "Chrome yok")
class Yerlesim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sayfalar = ["/il/" + os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html")))]     # canonical (temiz) URL biçimi; assert len(sayfalar) == 81
        cls.sonuc = calistir(sayfalar, GENISLIK)

    def test_yatay_tasma_yok_81_il_5_genislik(self):
        self.assertEqual(len(self.sonuc), 81 * len(GENISLIK))
        for r in self.sonuc:
            self.assertLessEqual(r["sw"], r["cw"], f"{r['sayfa']} {r['w']}px: sayfa yatay taşıyor"); self.assertEqual(r["tasan"], [], f"{r['sayfa']} {r['w']}px")

    def test_tipografi_hiyerarsisi(self):
        for r in self.sonuc:
            self.assertGreaterEqual(r["buyukPx"], 40, r); self.assertLessEqual(r["buyukPx"], 56 + 0.01, r); self.assertEqual(r["buyukSatir"], 1, f"{r['sayfa']} {r['w']}: tahmini seri tek satırda olmalı")
            self.assertGreater(r["buyukPx"], r["h1Px"], r); self.assertGreaterEqual(r["vPx"], 18, r); self.assertGreaterEqual(r["h2Px"], 20, r); self.assertGreaterEqual(r["govdePx"], 16, r)
            self.assertEqual(r["nwSatir"], 1, f"{r['sayfa']} {r['w']}: son gözlem plakası bölünmemeli")

    def test_ana_eylem_ve_arac_ilk_ekranda_veya_kisa_kaydirmada(self):
        for r in self.sonuc:
            if r["w"] <= 390: self.assertLess(r["ctaAlt"], 700, f"{r['sayfa']} {r['w']}: CTA ilk ekranda olmalı"); self.assertLess(r["hedefUst"], 1100, f"{r['sayfa']} {r['w']}: araç tek kısa kaydırmada")
            self.assertTrue(r["etiketli"], r["sayfa"]); self.assertFalse(r["uyari"], f"{r['sayfa']} {r['w']}: motor yüklüyken canlı tahmin uyarısı görünmemeli")

    def test_arac_etkilesimi(self):
        ilk = [r for r in self.sonuc if "sonucTahmin" in r]; self.assertEqual(len(ilk), 81)
        for r in ilk:
            self.assertTrue(any(x in r["sonucTahmin"]["metin"] for x in ("±", "geçildi", "tespit edilemedi")), (r["sayfa"], r["sonucTahmin"])); self.assertFalse(r["sonucTahmin"]["alert"])   # BZZ 999 bazı illerde çoktan geçilmiş
            self.assertTrue(r["sonucHata"]["alert"] and "kullanılmıyor" in r["sonucHata"]["metin"], r["sayfa"])
            self.assertTrue(r["sonucBos"]["alert"] and "Seri okunamadı" in r["sonucBos"]["metin"], r["sayfa"])
            self.assertIn("Geçersiz il kodu", r["sonucBaska"]["metin"])

@unittest.skipUnless(CHROME, "Chrome yok")
class MotorYuklenemezse(unittest.TestCase):
    def test_gorunur_hata_ve_sayfa_kullanilabilir(self):
        r = calistir(["/il/konya"], [375], engelle=("/assets/tahmin-motoru.js",))[0]
        self.assertTrue(r["sonucTahmin"]["alert"] and "Hesaplama yapılamadı" in r["sonucTahmin"]["metin"], r["sonucTahmin"])
        self.assertTrue(r["uyari"])                                                      # canlı tahmin güncellenemediği kullanıcıya görünür
        self.assertEqual(r["sw"], r["cw"]); self.assertEqual(r["nwSatir"], 1)           # statik içerik ve yerleşim bozulmaz

if __name__ == "__main__": unittest.main()
