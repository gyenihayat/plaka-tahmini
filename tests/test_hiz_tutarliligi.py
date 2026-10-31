"""Ana sayfa hesaplayıcısındaki hız ve seri süresi anlatımı, il sayfalarındaki TEK hız tanımıyla aynıdır: tahmin motorunun hızı (son ~365 günlük aralık hızlarının
medyanı, sıra/gün). Farklı yöntemle bulunan ölçüler (forum tablolarının haftalık ortalaması) aynı büyüklükmüş gibi sunulmaz. Bir serinin süresi (1.000 sıra) aynı hızdan,
GÜN cinsinden ve "yaklaşık" olarak hesaplanır. Testler üretim analitiğine (GoatCounter) istek göndermez (Chrome CHROME_TEMEL ile başlatılır)."""
import functools, html, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
from test_il_sayfasi import veri, sayfa, slug, TAM, E0
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
def tr_say(x): return f"{round(x):,}".replace(",", ".")
def gun_metni(g):                                   # JS: toLocaleString("tr-TR", {maximumFractionDigits: g < 10 ? 1 : 0})
    x = round(g, 1) if g < 10 else round(g)
    return f"{x:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".").rstrip("0").rstrip(",") if g < 10 else f"{x:,}".replace(",", ".")
def tr_float(t): return float(t.replace(".", "").replace(",", "."))

class StatikKaynak(unittest.TestCase):
    def test_eski_olcu_ve_ifadeler_kalmadi(self):
        ana_js = u.oku(os.path.join(u.ROOT, "assets", "ana-sayfa.js"))
        for yasak in ("s.hafta", "plaka/hafta", "seri/hafta", "son 26 hafta", "Plaka/hafta", "Seri/hafta"): self.assertNotIn(yasak, ANA + ana_js, yasak)
        self.assertIn('"Hız (sıra/gün)", "Bir seri (gün)"', ana_js)                           # hız ve seri süresi artık "81 ilin bu tarihteki tahminleri" tablosunda (tek hız tanımı)
        self.assertIn("son 365 gündeki ardışık gözlem", ANA)                                 # yöntem metni de aynı tanımı anlatır

@unittest.skipUnless(CHROME, "Chrome yok")
class AnaSayfaHizIlSayfasiylaAyni(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp(prefix="plaka_hiz_", dir=u.ROOT)
        try:
            shutil.copy(os.path.join(u.ROOT, "tests", "ui", "ana_hiz.html"), os.path.join(d, "h.html"))
            class H(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k): pass
            s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); port = s_.getsockname()[1]; s_.close()
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
            try: r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=60000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=200)
            finally: srv.shutdown(); srv.server_close()
            m = re.search(r"SONUC (\{.*\})\s*</pre>", r.stdout, re.S); assert m, r.stderr[-400:]
            cls.sonuc = json.loads(html.unescape(m[1]))
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_ana_sayfa_ve_il_sayfasi_ayni_hiz_ayni_sure(self):
        birim = {"saatte": 1 / 24, "günde": 1, "haftada": 7, "ayda": 30}; iller = {f"{s['kod']:02d}": s for s in veri()}; self.assertEqual(len(self.sonuc["tablo"]["satirlar"]), 81)
        for r in self.sonuc["tablo"]["satirlar"]:
            s = iller[r[0]]; h = sayfa(s["il"])
            il = re.search(r"günde yaklaşık ([\d.]+) sıra \(haftada yaklaşık ([\d.]+)\)\. Atlamasız ilerleme varsayımıyla bir seri \(1\.000 sıralık aralık; numaralar 001–999\) yaklaşık ([\d,]+) (saatte|günde|haftada|ayda) dolar", h)
            self.assertEqual(r[-3], il[1], s["il"])                                                                                                    # günlük hız: sayılar birebir aynı
            ana_gun = tr_float(r[-2]); il_gun = tr_float(il[3]) * birim[il[4]]
            self.assertLessEqual(abs(il_gun - ana_gun), birim[il[4]] * 0.5 + 0.06, (s["il"], il[0], r[-2]))                                           # aynı süre; yalnızca birim gösterimi farklı

    def test_tum_iller_tablosu_ayni_hiz_tanimi(self):
        t = self.sonuc["tablo"]; self.assertTrue(self.sonuc["baslangicKapali"]); self.assertEqual(t["basliklar"][-3:-1], ["Hız (sıra/gün)", "Bir seri (gün)"]); self.assertEqual(len(t["satirlar"]), 81)
        self.assertFalse(any("hafta" in b for b in t["basliklar"])); iller = {f"{s['kod']:02d}": s for s in veri()}
        for r in t["satirlar"]:
            s = iller[r[0]]; o = [tuple(a) for a in s["obs"]]; rate = fc.slope(o, o[-1][0])
            self.assertEqual((tr_float(r[-3]), r[-2]), (round(rate), gun_metni(1000 / rate)), r[:2])

if __name__ == "__main__": unittest.main()
