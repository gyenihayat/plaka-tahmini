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
        for yasak in ("s.hafta", "plaka/hafta", "seri/hafta", "son 26 hafta", "Plaka/hafta", "Seri/hafta"): self.assertNotIn(yasak, ANA, yasak)
        self.assertIn("tahmin hızı:", ANA); self.assertIn("bir serinin tahmini süresi:", ANA); self.assertIn("yaklaşık değer", ANA); self.assertIn("1.000 sıralık aralık", ANA)
        self.assertIn('"Hız (sıra/gün)","Bir seri (gün)"', ANA)
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

    def test_meta_hiz_ve_seri_suresi_tek_tanimdan_81_il(self):
        self.assertEqual(len(self.sonuc["iller"]), 81); iller = {s["il"]: s for s in veri()}
        for x in self.sonuc["iller"]:
            s = iller[x["il"]]; o = [tuple(a) for a in s["obs"]]; rate = fc.slope(o, o[-1][0]); p = x["parcalar"]
            m = re.match(r"tahmin hızı: günde ~([\d.]+) sıra \(haftada ~([\d.]+)\); son (\d+) gündeki aralık hızlarının medyanı, (\d+) gözlem", p[0]); self.assertIsNotNone(m, (x["il"], p[0]))
            self.assertEqual((tr_float(m[1]), tr_float(m[2])), (round(rate), round(rate * 7)), x["il"])                 # il sayfasıyla aynı sayılar (motor hızı)
            m2 = re.match(r"bir serinin tahmini süresi: ~([\d.,]+) gün \(yaklaşık değer; atlamasız ilerleme varsayımıyla, bir seri 1\.000 sıralık aralıktır\)", p[1]); self.assertIsNotNone(m2, (x["il"], p[1]))
            self.assertEqual(m2[1], gun_metni(1000 / rate), x["il"])                                                    # aynı hızdan, gün cinsinden
            self.assertNotIn("plaka/hafta", " ".join(p)); self.assertNotIn("seri/hafta", " ".join(p))

    def test_ana_sayfa_ve_il_sayfasi_ayni_hiz_ayni_sure(self):
        birim = {"saatte": 1 / 24, "günde": 1, "haftada": 7, "ayda": 30}
        for x in self.sonuc["iller"]:
            h = sayfa(x["il"]); il = re.search(r"günde yaklaşık ([\d.]+) sıra \(haftada yaklaşık ([\d.]+)\)\. Atlamasız ilerleme varsayımıyla bir seri \(1\.000 sıralık aralık; numaralar 001–999\) yaklaşık ([\d,]+) (saatte|günde|haftada|ayda) dolar", h)
            m = re.match(r"tahmin hızı: günde ~([\d.]+) sıra \(haftada ~([\d.]+)\)", x["parcalar"][0]); self.assertEqual((m[1], m[2]), (il[1], il[2]), x["il"])           # sayılar birebir aynı
            ana_gun = tr_float(re.match(r"bir serinin tahmini süresi: ~([\d.,]+) gün", x["parcalar"][1])[1]); il_gun = tr_float(il[3]) * birim[il[4]]
            self.assertLessEqual(abs(il_gun - ana_gun), birim[il[4]] * 0.5 + 0.06, (x["il"], il[0], x["parcalar"][1]))      # aynı süre; yalnızca birim gösterimi farklı (il sayfası saat/hafta/ay kullanabilir)

    def test_tum_iller_tablosu_ayni_hiz_tanimi(self):
        t = self.sonuc["tablo"]; self.assertEqual(t["basliklar"][-3:-1], ["Hız (sıra/gün)", "Bir seri (gün)"]); self.assertEqual(len(t["satirlar"]), 81)
        self.assertFalse(any("hafta" in b for b in t["basliklar"])); iller = {f"{s['kod']:02d}": s for s in veri()}
        for r in t["satirlar"]:
            s = iller[r[0]]; o = [tuple(a) for a in s["obs"]]; rate = fc.slope(o, o[-1][0])
            self.assertEqual((tr_float(r[-3]), r[-2]), (round(rate), gun_metni(1000 / rate)), r[:2])

@unittest.skipUnless(CHROME, "Chrome yok")
class Okunabilirlik(unittest.TestCase):
    def test_375_ve_1440_hiz_aciklamasi_okunur(self):
        from test_ana_sayfa_tasarim import TarayiciYerlesim
        TarayiciYerlesim.setUpClass()
        for r in TarayiciYerlesim.sonuc:
            if r["w"] in (375, 1440):
                self.assertGreaterEqual(r["metaPx"], 15, r["w"]); self.assertFalse(r["metaTasma"], f"{r['w']}px: hız açıklaması taşıyor"); self.assertGreaterEqual(r["metaParca"], 4, r["w"])
                self.assertLessEqual(max(r["metaSatir"]), 5 if r["w"] == 375 else 3, f"{r['w']}px: her parça en çok 5 (mobil) / 3 (masaüstü) satır")

if __name__ == "__main__": unittest.main()
