"""Ana sayfa hesaplayıcısı: motor ortak modüle çıkarıldıktan sonra arayüz sonuçları, çıkarılmadan önceki index.html ile aynı girişlerde birebir aynı olmalı.
Eski index.html git geçmişinden (9b65ce4) alınır, DATA'sı güncel veriyle değiştirilir; ikisi aynı tarayıcı oturumunda sürülür (tarihe bağlı çıktılar eşit kalır).
Chrome (headless) yoksa atlanır."""
import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest, http.server, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
CHROME = next((p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("google-chrome") or "", shutil.which("chromium") or "") if p and os.path.exists(p)), None)
ESKI_COMMIT = "9b65ce4"
# Testler üretim ziyaret sayacına ASLA istek atmamalı: ana sayfa abacus.jasoncameron.dev'e "ziyaret" vuruşu yapar; tarayıcıda bu ad çözümlenmez.
CHROME_TEMEL = [CHROME, "--headless=new", "--disable-gpu", "--host-resolver-rules=MAP abacus.jasoncameron.dev ~NOTFOUND"]

@unittest.skipUnless(CHROME and u.NODE, "Chrome/Node yok")
class AnaSayfaRegresyon(unittest.TestCase):
    def test_eski_ve_yeni_index_ayni_sonuclari_verir(self):
        d = tempfile.mkdtemp(prefix="plaka_ui_")
        try:
            yeni = u.oku(os.path.join(u.ROOT, "index.html")); data = re.search(r"const DATA = .*?;\n", yeni)[0]
            eski = subprocess.run(["git", "show", f"{ESKI_COMMIT}:index.html"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout
            eski = re.sub(r"const DATA = .*?;\n", lambda m: data, eski, count=1)
            # Bilinçli tek davranış değişikliği: "bugün" artık referans gündür (Türkiye tarihinin en yakın önceki iş günü). Eski kopyaya, BAĞIMSIZ Python hesabıyla (is_gunu.py)
            # bulunan değer sabit olarak yazılır; yeni sayfa aynı değeri JS ile bulmak zorundadır. Geri kalan her şey birebir karşılaştırılır.
            sys.path.insert(0, u.ROOT); import datetime as dt, is_gunu
            ref = is_gunu.onceki_is_gunu(dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).date())
            for a_, b_ in (("const todayDay = Math.floor((Date.now()-EPOCH)/DAY);", f"const todayDay = {(ref - dt.date(2024, 1, 1)).days};"),
                           ("const isoToday = new Date().toISOString().slice(0,10);", f'const isoToday = "{ref.isoformat()}";')):
                self.assertEqual(eski.count(a_), 1, a_); eski = eski.replace(a_, b_)
            for ad, icerik in (("index.html", yeni), ("eski.html", eski)):
                with open(os.path.join(d, ad), "w", encoding="utf-8") as f: f.write(icerik)
            shutil.copytree(os.path.join(u.ROOT, "assets"), os.path.join(d, "assets")); shutil.copy(os.path.join(u.ROOT, "tests", "ui", "karsilastir.html"), os.path.join(d, "h.html"))
            s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
            class Sessiz(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k): pass
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Sessiz, directory=d))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=60000", "--dump-dom", f"http://127.0.0.1:{port}/h.html"], capture_output=True, text=True, timeout=180)
            finally: srv.shutdown(); srv.server_close()
            m = re.search(r"SONUC (\{.*?\})\s*</pre>", r.stdout, re.S); self.assertIsNotNone(m, r.stdout[-500:] + r.stderr[-300:])
            sonuc = json.loads(m[1].replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
            self.assertGreaterEqual(sonuc["senaryo"], 500); self.assertEqual(sonuc["fark"], 0, sonuc["ornekFark"])
            self.assertTrue(sonuc["tum_iller_tablo_ayni"] and sonuc["t81_tablo_ayni"]); self.assertGreater(sonuc["t81_satir"], 80)
            self.assertIn("Tahmini ulaşma", sonuc["ornek"]["hout"])          # harness gerçekten hesap yaptı
        finally: shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__": unittest.main()
