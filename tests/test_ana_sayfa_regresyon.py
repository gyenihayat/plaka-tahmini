"""Ana sayfa hesaplayıcısı: motor ortak modüle çıkarıldıktan sonra arayüz sonuçları, çıkarılmadan önceki index.html ile aynı girişlerde birebir aynı olmalı.
Eski index.html git geçmişinden (9b65ce4) alınır, DATA'sı güncel veriyle değiştirilir; ikisi aynı tarayıcı oturumunda sürülür (tarihe bağlı çıktılar eşit kalır).
Chrome (headless) yoksa atlanır."""
import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest, http.server, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
CHROME = next((p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("google-chrome") or "", shutil.which("chromium") or "") if p and os.path.exists(p)), None)
ESKI_COMMIT = "9b65ce4"
# Testler üretim sayaçlarına/analitiğe ASLA istek atmamalı: olcum.js yalnızca plakatahmini.com'da GoatCounter'ı yükler. Güncel sayfalarda Abacus kodu yoktur; ancak karşılaştırma için
# git geçmişinden alınan ESKI_COMMIT kopyası eski Abacus sayaç betiğini içerir, bu yüzden abacus.jasoncameron.dev adı tarayıcıda çözümlenmeyecek şekilde engeli korunur (kasıtlı).
# Birinci koruma sayfa tarafındaki alan adı denetimi (olcum.js), ikincisi bu: tarayıcıda bu adlar çözümlenmez.
ENGELLENEN_ALAN_ADLARI = ("abacus.jasoncameron.dev", "*.goatcounter.com", "gc.zgo.at")
CHROME_TEMEL = [CHROME, "--headless=new", "--disable-gpu", "--host-resolver-rules=" + ", ".join(f"MAP {a} ~NOTFOUND" for a in ENGELLENEN_ALAN_ADLARI)]

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
                icerik = re.sub(r'<link[^>]+fonts\.(?:googleapis|gstatic)\.com[^>]*>', "", icerik)       # harness davranışı karşılaştırır: internetten yazı tipi beklenmez (render-blocking stil dosyası betik çalışmasını geciktirip testi kararsız yapıyordu)
                with open(os.path.join(d, ad), "w", encoding="utf-8") as f: f.write(icerik)
            shutil.copytree(os.path.join(u.ROOT, "assets"), os.path.join(d, "assets")); shutil.copy(os.path.join(u.ROOT, "tests", "ui", "karsilastir.html"), os.path.join(d, "h.html"))
            s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
            class Sessiz(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k): pass
            class Sunucu(http.server.ThreadingHTTPServer): request_queue_size = 128       # varsayılan bekleme kuyruğu (5) iki iframe'in paralel betik isteklerinde bağlantı düşürüp testi aralıklı kilitliyordu
            srv = Sunucu(("127.0.0.1", port), functools.partial(Sessiz, directory=d))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=600000", "--dump-dom", f"http://127.0.0.1:{port}/h.html"], capture_output=True, text=True, timeout=180)
            finally: srv.shutdown(); srv.server_close()
            m = re.search(r"SONUC (\{.*?\})\s*</pre>", r.stdout, re.S); self.assertIsNotNone(m, r.stdout[-500:] + r.stderr[-300:])
            sonuc = json.loads(m[1].replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
            self.assertGreaterEqual(sonuc["senaryo"], 500); self.assertEqual(sonuc["fark"], 0, sonuc["ornekFark"])
            self.assertGreater(sonuc["kalibre"], 0); self.assertEqual(sonuc["kalibreDogru"], sonuc["kalibre"])             # ikinci bilinçli fark: Ankara'nın geriye dönük hedef tarihi tarihsel referansla kalibre edilmiş tahmin olarak etiketlenir
            self.assertGreater(sonuc["sinir"], 0); self.assertEqual(sonuc["sinirDogru"], sonuc["sinir"])      # tek bilinçli fark: 2018 öncesine düşen hedef tarihi artık verilmez
            self.assertTrue(sonuc["tum_iller_tablo_ayni"] and sonuc["t81_tablo_ayni"]); self.assertNotEqual(sonuc["ankaraSatir"]["eski"], sonuc["ankaraSatir"]["yeni"])      # 81 il tablosunda yalnızca Ankara satırı (kalibre tarih) farklı; self.assertGreater(sonuc["t81_satir"], 80)
            self.assertIn("Tahmini ulaşma", sonuc["ornek"]["hout"])          # harness gerçekten hesap yaptı
        finally: shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__": unittest.main()
