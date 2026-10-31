"""Production yolları ve haftalık güncelleme akışı: (1) ortak motor/araç dosyaları doğru mutlak yoldan, Vercel cleanUrls biçimindeki gerçek URL'lerden yüklenir;
(2) tablo_ekle.py haftalık akışı (veri + index.html DATA + seri geçişleri + 81 sayfa + sitemap) bozulmadan çalışır ve mevcut durumu aynen yeniden üretir;
(3) takvim kapsam koruması tablo_ekle'de sürer; (4) öneri .md dosyası depoda izlenmez."""
import csv, datetime as dt, functools, glob, http.server, json, mimetypes, os, re, shutil, socket, subprocess, sys, threading, unittest, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_il_sayfasi import veri, slug, TAM, inv, tr, E0

class ProductionYollari(unittest.TestCase):
    def test_varliklar_mevcut_ve_git_tarafindan_yok_sayilmiyor(self):
        for f in ("assets/olcum.js", "assets/takvim.js", "assets/tahmin-motoru.js", "assets/il-arac.js", "assets/ana-sayfa.js"):
            self.assertTrue(os.path.isfile(os.path.join(u.ROOT, f)), f)
            self.assertEqual(subprocess.run(["git", "check-ignore", "-q", f], cwd=u.ROOT).returncode, 1, f"{f} .gitignore tarafından yok sayılıyor")
        self.assertNotIn("assets", u.oku(os.path.join(u.ROOT, ".gitignore")))

    def test_vercel_yonlendirmeleri_varliklari_etkilemez(self):
        v = json.loads(u.oku(os.path.join(u.ROOT, "vercel.json"))); self.assertTrue(v["cleanUrls"]); self.assertFalse(v["trailingSlash"])
        for r in v["redirects"]: self.assertTrue(r.get("has") and all(h["type"] == "host" for h in r["has"]), r)       # yalnızca eski/www host'lara; alan adı üzerindeki /assets etkilenmez
        self.assertTrue(all(r["destination"].startswith("https://plakatahmini.com/") for r in v["redirects"]))

    def test_sayfalar_varliklara_mutlak_yolla_ve_dogru_sirayla_baglanir(self):
        ana = u.oku(os.path.join(u.ROOT, "index.html")); self.assertLess(ana.index('src="/assets/takvim.js"'), ana.index('src="/assets/tahmin-motoru.js"')); self.assertLess(ana.index('src="/assets/tahmin-motoru.js"'), ana.index("const DATA = "))
        for yol in glob.glob(os.path.join(u.ROOT, "il", "*.html")):
            h = u.oku(yol); m = re.findall(r'<script src="(/assets/[^"]+)"( defer)?>', h)
            self.assertEqual([x[0] for x in m], ["/assets/olcum.js", "/assets/takvim.js", "/assets/tahmin-motoru.js", "/assets/tarih-sorgu.js", "/assets/il-arac.js"], yol); self.assertTrue(all(x[1] for x in m), yol)

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_js_sozdizimi_gecerli(self):
        for f in ("olcum.js", "takvim.js", "tahmin-motoru.js", "tarih-sorgu.js", "il-arac.js", "ana-sayfa.js"):
            r = subprocess.run([u.NODE, "--check", os.path.join(u.ROOT, "assets", f)], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr)

    def test_temiz_url_ve_varlik_http_200_dogru_icerik_turu(self):
        class H(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k): pass
            def do_GET(self):
                yol = self.path.split("?")[0]
                if "." not in os.path.basename(yol) and os.path.isfile(os.path.join(u.ROOT, yol.lstrip("/") + ".html")): self.path = yol + ".html"      # Vercel cleanUrls
                super().do_GET()
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            for yol in ("/il/konya", "/il/istanbul", "/", "/assets/olcum.js", "/assets/takvim.js", "/assets/tahmin-motoru.js", "/assets/il-arac.js", "/assets/ana-sayfa.js"):
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{yol}") as r: self.assertEqual(r.status, 200, yol); tur = r.headers.get_content_type()
                if yol.endswith(".js"): self.assertIn(tur, ("text/javascript", "application/javascript"), yol)
        finally: srv.shutdown(); srv.server_close()

class HaftalikGuncelleme(unittest.TestCase):
    def _hazirla(self):
        d = u.kopya(ekstra=("index.html", "tablo_ekle.py", "il", "sitemap.xml", "assets"), il_dizini=False)
        orijinal = {f: u.oku(os.path.join(u.ROOT, f)) for f in ("data/tahmin_data.json", "index.html", "data/seri_gecisleri.csv")}
        v = json.loads(orijinal["data/tahmin_data.json"]); son_gun = max(s["obs"][-1][0] for s in v["iller"]); tarih = E0 + dt.timedelta(days=son_gun)
        plaka, hft = [], []
        for s in v["iller"]:
            g, n = s["obs"].pop(); self.assertEqual(g, son_gun); _, n0 = s["obs"][-1]; sr, no = inv(n); plaka.append(f"{s['kod']:02d} {sr} {no:03d}"); hft.append(f"{s['il']} {n - n0}")
        js = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        with open(os.path.join(d, "data", "tahmin_data.json"), "w", encoding="utf-8") as f: f.write(js)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f: f.write(re.sub(r"const DATA = .*?;\n", lambda m: "const DATA = " + js + ";\n", orijinal["index.html"], count=1))
        ham = orijinal["data/seri_gecisleri.csv"]; nl = "\r\n" if "\r\n" in ham else "\n"; satirlar = ham.split(nl)
        kalan = [x for x in satirlar if not (x and x.split(",")[-1].strip() == tarih.isoformat())]
        with open(os.path.join(d, "data", "seri_gecisleri.csv"), "w", encoding="utf-8", newline="") as f: f.write(nl.join(kalan))
        for ad, icerik in (("plakalar.txt", "\n".join(plaka)), ("hft.txt", "\n".join(hft))):
            with open(os.path.join(d, ad), "w", encoding="utf-8") as f: f.write(icerik)
        return d, orijinal, tarih

    def test_tablo_ekle_mevcut_durumu_aynen_yeniden_uretir(self):
        d, orijinal, tarih = self._hazirla()
        try:
            r = subprocess.run([sys.executable, "tablo_ekle.py", "--tarih", tarih.isoformat(), "--plakalar", "plakalar.txt", "--hft", "hft.txt", "--plakatr", os.path.join(d, "yok.csv")], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-600:]); self.assertIn("tamam", r.stdout); self.assertNotIn("UYARI:", r.stdout.replace("UYARI: " + os.path.join(d, "yok.csv"), ""))
            kart = lambda h: re.sub(r"<!--ANA:KARTLAR-->.*?<!--/ANA:KARTLAR-->", "<!--KART-->", h, flags=re.S)       # statik kartlar üretim gününe bağlıdır; geri kalan her şey (DATA dahil) aynı olmalı
            for f in ("data/tahmin_data.json", "data/seri_gecisleri.csv"): self.assertEqual(u.oku(os.path.join(d, f)), orijinal[f], f)
            yeni_ana = u.oku(os.path.join(d, "index.html")); self.assertEqual(kart(yeni_ana), kart(orijinal["index.html"]), "index.html (kartlar hariç)")
            self.assertEqual(len(re.findall(r'<a class="kart" href="/il/', yeni_ana)), 3); self.assertIn("23 Ekim 2026</span></a>", yeni_ana)       # kartlar yenilendi; son gözlem veriden
            self.assertIn('<script src="/assets/tahmin-motoru.js"></script>', u.oku(os.path.join(d, "index.html")))
            sayfalar = sorted(glob.glob(os.path.join(d, "il", "*.html"))); self.assertEqual(len(sayfalar), 81)
            for s in veri(): self.assertIn(f"<dd class=\"k\">{tr(tarih)}</dd>", u.oku(os.path.join(d, "il", slug(TAM.get(s["il"], s["il"])) + ".html")))      # son kayıtlı gözlem tarihi veriden
            self.assertEqual(len(re.findall(r"<loc>", u.oku(os.path.join(d, "sitemap.xml")))), 82)
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_takvim_kapsam_korumasi_tablo_ekle_dosya_yazmadan_durdurur(self):
        d = u.kopya(ekstra=("index.html", "tablo_ekle.py"), il_dizini=False)
        try:
            once = u.oku(os.path.join(d, "data", "tahmin_data.json"))
            for tarih in ("2029-01-10", "2028-07-04"):
                r = subprocess.run([sys.executable, "tablo_ekle.py", "--tarih", tarih, "--plakalar", "yok1", "--hft", "yok2"], cwd=d, capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0); self.assertIn("HATA", r.stderr); self.assertIn("BAYRAMLAR", r.stderr)
            self.assertEqual(u.oku(os.path.join(d, "data", "tahmin_data.json")), once)
        finally: shutil.rmtree(d, ignore_errors=True)

class OneriDosyasi(unittest.TestCase):
    def test_md_onerisi_depoda_izlenmez(self):
        izlenen = subprocess.run(["git", "ls-files"], cwd=u.ROOT, capture_output=True, text=True).stdout.split("\n")
        self.assertNotIn("PlakaTahmini_81_Il_Yenileme_Guncel.md", izlenen)

if __name__ == "__main__": unittest.main()
