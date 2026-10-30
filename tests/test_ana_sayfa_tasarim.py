"""Yenilenen ana sayfa: SEO etiketleri/yapılandırılmış veri korunur, üç büyük il kartı veriden (sabit kodlanmadan) hesaplanır ve il sayfalarıyla eşleşir,
81 ilin gerçek bağlantıları ve il seçimi, hesaplayıcı işlevleri (mevcut kimlikler), erişilebilirlik ve 5 genişlikte yerleşim."""
import datetime as dt, functools, html, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
from test_il_sayfasi import veri, sayfa, slug, TAM, inv, tr, E0
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
ESKI = subprocess.run(["git", "show", "7aff9ee:index.html"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout          # yenileme öncesi ana sayfa
KARTLAR = (("İstanbul", 34, "istanbul"), ("Ankara", 6, "ankara"), ("İzmir", 35, "izmir"))
def metin(x): return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))).strip()
def gv(h):                                   # <script> ve <style> dışı, görünür gövde
    return re.sub(r"<(script|style)\b.*?</\1>", "", h[h.index("<body>"):], flags=re.S)

class SeoVeYapi(unittest.TestCase):
    def test_title_canonical_description_og_robots_aynen_korunur(self):
        for pat in (r"<title>.*?</title>", r'<link rel="canonical"[^>]*>', r'<meta name="description"[^>]*>', r'<meta name="robots"[^>]*>', r'<meta property="og:[a-z:]+" content="[^"]*">', r'<meta name="twitter:[a-z:]+" content="[^"]*">'):
            self.assertEqual(re.findall(pat, ANA), re.findall(pat, ESKI), pat)

    def test_json_ld_korunur_gecerli_ve_gorunen_islevle_tutarli(self):
        bl = lambda h: [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
        self.assertEqual(bl(ANA), bl(ESKI)); tur = {x["@type"] for x in bl(ANA)}; self.assertEqual(tur, {"WebApplication", "WebSite"})
        wa = next(x for x in bl(ANA) if x["@type"] == "WebApplication"); self.assertEqual(wa["url"], "https://plakatahmini.com/"); self.assertTrue(wa["isAccessibleForFree"])
        self.assertIn('id="hesapla"', ANA); self.assertIn('id="target"', ANA)               # uygulamanın tarif ettiği işlevler sayfada görünür

    def test_baslik_ve_ilk_ekran_metin_butcesi(self):
        g = gv(ANA); self.assertEqual(len(re.findall(r"<h1>", ANA)), 1); self.assertIn("<h1>Türkiye Plaka Sırası Tahminleri</h1>", ANA)
        self.assertIn('<p class="alt-baslik">81 il için güncel tahmini plaka serilerini inceleyin, istediğiniz plakanın yaklaşık çıkış tarihini hesaplayın.</p>', ANA)
        ilk = g[:g.index('<section class="il-bolum"')]; kelime = len(metin(ilk).split()); self.assertLessEqual(kelime, 100, kelime)                       # üç kart (il, seri, tarih, son gözlem) + tek cümlelik açıklama; uzun paragraf yok
        for p in re.findall(r"<p[^>]*>(.*?)</p>", ilk, re.S): self.assertLessEqual(len(metin(p).split()), 25, metin(p)[:60])
        self.assertNotIn('class="lede"', ANA); self.assertEqual(ANA.count("Sık sorulan"), 0)

    def test_komut_dizisi_sirasi_ve_kimlikler_korunur(self):
        self.assertLess(ANA.index('src="/assets/takvim.js"'), ANA.index('src="/assets/tahmin-motoru.js"')); self.assertLess(ANA.index('src="/assets/tahmin-motoru.js"'), ANA.index("const DATA = "))
        self.assertLess(ANA.index("const DATA = "), ANA.index('src="/assets/ana-sayfa.js"')); self.assertRegex(ANA, r"const DATA = .*?;\n")
        eski_idler = set(re.findall(r'id="([\w-]+)"', gv(ESKI))); yeni_idler = set(re.findall(r'id="([\w-]+)"', gv(ANA)))
        self.assertEqual(eski_idler - yeni_idler, set(), "hesaplayıcı kimlikleri korunmalı")
        for gizli in ('id="kart-uyari" role="status" hidden', 'id="il-hata" class="hata" role="alert"'): self.assertIn(gizli, ANA)

    def test_erisilebilirlik_etiketleri(self):
        self.assertIn("<main", ANA); self.assertIn('lang="tr"', ANA)
        for i in ("il-ara", "il", "target", "dt", "excl", "excl2"): self.assertRegex(ANA, rf'<label for="{i}"')
        self.assertIn('aria-live="polite"', ANA); self.assertIn("focus-visible", ANA); self.assertIn('list="il-liste"', ANA)

class Kartlar(unittest.TestCase):
    def test_uc_kart_veriden_hesaplanir_ve_il_sayfasiyla_ayni(self):
        kartlar = re.findall(r'<a class="kart" href="(/il/[a-z]+)" data-il="([^"]+)">(.*?)</a>', ANA, re.S); self.assertEqual([(k[1], k[0]) for k in kartlar], [(a, f"/il/{c}") for a, _, c in KARTLAR])
        iller = {s["il"]: s for s in veri()}
        for (il, kod, sl), (href, _, ic) in zip(KARTLAR, kartlar):
            s = iller[il]; h = sayfa(il); bas = dt.date.fromisoformat(re.search(r'data-baslangic="([^"]+)"', h)[1]); o = [tuple(x) for x in s["obs"]]; g, n = o[-1]; ld = E0 + dt.timedelta(days=g)
            py = inv(round(n + fc.advance(o, fc.clean(o), g, (bas - ld).days, fc.slope(o, g))))[0]; sr, no = inv(n)
            self.assertEqual(re.search(r'data-kart="seri">([^<]*)<', ic)[1], f"{kod:02d} {py}"); self.assertEqual(re.search(r'data-kart="seri">([^<]*)<', ic)[1], re.search(r'data-live="seri">([^<]*)<', h)[1])     # il sayfasıyla aynı
            self.assertEqual(re.search(r'data-kart="tarih">([^<]*)<', ic)[1], tr(bas)); self.assertIn("itibarıyla", ic); self.assertIn("Tahmindir", ic)
            self.assertIn(f"Son gözlem: {kod:02d} {sr} {no:03d} · {tr(ld)}", metin(ic)); self.assertIn(f"{il} · {kod:02d}", metin(ic))                                                   # gözlem tahminden ayrı
            self.assertTrue(os.path.isfile(os.path.join(u.ROOT, href.lstrip("/") + ".html")))
        self.assertIn('<span id="last-global">23.10.2026</span>', ANA)

    def test_kart_degerleri_sabit_degil_veriye_baglidir(self):
        d = u.kopya(ekstra=("sitemap.xml",))
        try:
            yol = os.path.join(d, "data", "tahmin_data.json")
            with open(yol, encoding="utf-8") as f: v = json.load(f)
            ist = next(x for x in v["iller"] if x["il"] == "İstanbul"); ist["obs"][-1][1] += 90000                    # 90 seri ileri
            with open(yol, "w", encoding="utf-8") as f: json.dump(v, f, ensure_ascii=False, separators=(",", ":"))
            r = u.uret(d, "--bugun", "2026-10-30"); self.assertEqual(r.returncode, 0, r.stderr)
            yeni = u.oku(os.path.join(d, "index.html")); eski_seri = re.search(r'data-il="İstanbul">.*?data-kart="seri">([^<]*)<', ANA, re.S)[1]
            yeni_seri = re.search(r'data-il="İstanbul">.*?data-kart="seri">([^<]*)<', yeni, re.S)[1]; self.assertNotEqual(yeni_seri, eski_seri)
            self.assertEqual(yeni_seri, re.search(r'data-live="seri">([^<]*)<', u.oku(os.path.join(d, "il", "istanbul.html")))[1])                  # kart = il sayfası
            self.assertEqual(re.search(r'data-il="Ankara">.*?data-kart="seri">([^<]*)<', yeni, re.S)[1], re.search(r'data-il="Ankara">.*?data-kart="seri">([^<]*)<', ANA, re.S)[1])
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_kart_tarihi_hafta_sonu_uretiminde_onceki_is_gunu(self):
        d = u.kopya(ekstra=("sitemap.xml",))
        try:
            for bugun, etiket in (("2026-10-31", "30 Ekim 2026"), ("2026-11-01", "30 Ekim 2026"), ("2026-11-02", "2 Kasım 2026")):
                u.uret(d, "--bugun", bugun); self.assertEqual(set(re.findall(r'data-kart="tarih">([^<]*)<', u.oku(os.path.join(d, "index.html")))), {etiket}, bugun)
        finally: shutil.rmtree(d, ignore_errors=True)

class IlSecimiVeBaglantilar(unittest.TestCase):
    def test_81_gercek_baglanti_html_icinde_ve_il_sayfalariyla_ayni(self):
        nav = re.search(r'<nav class="iller-liste".*?</nav>', ANA, re.S)[0]; linkler = re.findall(r'<a href="(/il/[a-z]+)">([^<]+)</a>', nav)
        self.assertEqual(len(linkler), 81); self.assertEqual(len({l[0] for l in linkler}), 81)
        dosyalar = {f"/il/{os.path.basename(p)[:-5]}" for p in __import__("glob").glob(os.path.join(u.ROOT, "il", "*.html"))}; self.assertEqual({l[0] for l in linkler}, dosyalar)
        self.assertIn("<h2>İllere Göre Güncel Plaka Serileri</h2>", nav)

    def test_datalist_81_il_kod_ad_slug(self):
        ops = re.findall(r'<option value="([^"]+)" data-ad="([^"]+)" data-kod="(\d+)" data-slug="([a-z]+)">', ANA); self.assertEqual(len(ops), 81)
        self.assertEqual(sorted(int(o[2]) for o in ops), list(range(1, 82))); self.assertEqual({f"/il/{o[3]}" for o in ops}, {l for l in re.findall(r'<a href="(/il/[a-z]+)">', re.search(r'<nav class="iller-liste".*?</nav>', ANA, re.S)[0])})
        for deger, ad, kod, sl in ops: self.assertEqual(deger, f"{html.unescape(ad)} ({int(kod):02d})"); self.assertEqual(sl, slug(html.unescape(ad)))

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_il_bul_81_il_ad_kod_biçimleri_ve_hatalar(self):
        ops = re.findall(r'<option value="[^"]+" data-ad="([^"]+)" data-kod="(\d+)" data-slug="([a-z]+)">', ANA); liste = [{"ad": html.unescape(a), "kod": int(k), "slug": s} for a, k, s in ops]
        fold = lambda t: t.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
        girisler = []
        for il in liste:
            n = il["ad"]; benzersiz = next(n[:i] for i in range(1, len(n) + 1) if sum(1 for x in liste if fold(x["ad"]).lower().startswith(fold(n[:i]).lower())) == 1)
            for g in (n, n.upper().replace("İ", "I") if False else n.replace("i", "İ").replace("ı", "I").upper(), n.lower(), fold(n), f"{n} ({il['kod']:02d})", f"{il['kod']:02d} {n}", str(il["kod"]), f"{il['kod']:02d}", benzersiz):
                girisler.append([g, il["slug"]])
        kod = ("const fs=require('fs'),vm=require('vm');const c={Math,Date,console};vm.createContext(c);vm.runInContext(fs.readFileSync('assets/ana-sayfa.js','utf8'),c);"
               "c.__l=JSON.parse(process.argv[1]);c.__g=JSON.parse(process.argv[2]);console.log(JSON.stringify(c.__g.map(function(x){c.__x=x[0];var r=vm.runInContext('PlakaAnaSayfa.ilBul(__x,__l)',c);return [r.tip,r.il?r.il.slug:null]})));")
        sonuc = json.loads(subprocess.run([u.NODE, "-e", kod, json.dumps(liste), json.dumps(girisler, ensure_ascii=False)], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout)
        self.assertEqual(len(sonuc), 81 * 9)
        for (g, beklenen), (tip, sl) in zip(girisler, sonuc): self.assertEqual((tip, sl), ("tamam", beklenen), g)
        hatalar = json.loads(subprocess.run([u.NODE, "-e", kod.replace("c.__g.map", "c.__g.map"), json.dumps(liste), json.dumps([[""], ["82"], ["0"], ["00"], ["abc"], ["konya 06"], ["k"], ["ka"], ["1 2"], ["42 42"], ["   "]])], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout)
        self.assertEqual([h[0] for h in hatalar], ["bos", "yok", "yok", "yok", "yok", "celisik", "belirsiz", "belirsiz", "yok", "yok", "bos"])

@unittest.skipUnless(CHROME, "Chrome yok")
class TarayiciYerlesim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp(prefix="plaka_anayer_", dir=u.ROOT)
        try:
            with open(os.path.join(u.ROOT, "tests", "ui", "ana_yerlesim.html"), encoding="utf-8") as f: h = f.read()
            with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(h.replace("__GENISLIKLER__", json.dumps([375, 320, 390, 768, 1440])))
            class H(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k): pass
                def do_GET(self):
                    yol = self.path.split("?")[0]
                    if "." not in os.path.basename(yol) and os.path.isfile(os.path.join(u.ROOT, yol.lstrip("/") + ".html")): self.path = yol + ".html"
                    super().do_GET()
            s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); port = s_.getsockname()[1]; s_.close()
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
            try: r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=120000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=200)
            finally: srv.shutdown(); srv.server_close()
            m = re.search(r"SONUC (\[.*?\])\s*</pre>", r.stdout, re.S); assert m, r.stderr[-400:]
            cls.sonuc = json.loads(html.unescape(m[1]))
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_yatay_tasma_yok_5_genislik(self):
        self.assertEqual({r["w"] for r in self.sonuc}, {320, 375, 390, 768, 1440})
        for r in self.sonuc: self.assertLessEqual(r["sw"], r["cw"], f"{r['w']}px sayfa taşıyor"); self.assertEqual(r["tasan"], [], f"{r['w']}px")

    def test_testler_uretim_ziyaret_sayacina_istek_atmaz(self):
        for r in self.sonuc: self.assertEqual(r["sayac"], "none", "sayaç yüklendi: test tarayıcısı üretim sayacına istek atmış olabilir")
        for f in ("test_ana_sayfa_regresyon.py", "test_il_arac.py", "test_ana_sayfa_tasarim.py", "test_il_yerlesim.py", "test_tarih_tutarliligi.py"):
            self.assertNotIn("subprocess.run([" + "CHROME,", u.oku(os.path.join(u.ROOT, "tests", f)), f"{f}: Chrome CHROME_TEMEL ile başlatılmalı")

    def test_uc_kart_buyuk_seri_ve_ilk_ekran(self):
        for r in self.sonuc:
            self.assertEqual(r["kartSayisi"], 3); self.assertGreaterEqual(r["seriPx"], 36, r["w"]); self.assertTrue(r["seriTekSatir"], f"{r['w']}px: seri tek satır olmalı"); self.assertGreaterEqual(r["govdePx"], 16)
            self.assertGreater(r["seriPx"], r["h1Px"] * 0.9, r["w"]); self.assertTrue(r["etiketli"], r["w"])
            if r["w"] <= 390:
                self.assertLess(r["kartUst"][2], 700, f"{r['w']}px: üçüncü kart ilk ekranda başlamalı"); self.assertLess(r["ctaUst"], 900, f"{r['w']}px: ana eylem kartların hemen altında")
            else: self.assertLess(r["ctaAlt"], 700, f"{r['w']}px: kartlar ve ana eylem ilk ekranda"); self.assertEqual(len(set(r["kartUst"])), 1 if r["w"] >= 768 else 3)
            for m in r["kartMetin"]: self.assertIn("Tahmindir", m); self.assertIn("itibarıyla", m); self.assertIn("Son gözlem", m)

    def test_hesaplayici_islevleri_calisir(self):
        r = next(x for x in self.sonuc if x["w"] == 375)
        self.assertIn("Tahmini ulaşma", r["hedef"]["out"]); self.assertEqual(r["hedef"]["canli"], "polite")
        self.assertEqual(r["hedefHata"]["out"], ""); self.assertIn("kullanılmıyor", r["hedefHata"]["warn"])
        self.assertIn("atlanan seri düşüldü", r["hedefAtla"]["out"])
        self.assertNotEqual(r["hedef"]["out"], r["hedefAtla"]["out"])                               # atlanacak seriler sonucu değiştirir
        self.assertRegex(r["tarihPlaka"], r"^\d\d [A-Z]{3} \d{3}$")             # (hedef girişinde başa yazılan il kodu, ana sayfadaki gibi ili değiştirir: 06 GAA -> Ankara); self.assertNotEqual(r["tarihPlaka"], r["tarih2028"]); self.assertRegex(r["bugunDt"], r"^\d{4}-\d\d-\d\d$")

    def test_il_secimi_hatalari_ve_gecis(self):
        r = next(x for x in self.sonuc if x["w"] == 375)
        self.assertIn("Bir il adı", r["ilHatalar"]["bos"]); self.assertIn("bulunamadı", r["ilHatalar"]["yok"]); self.assertIn("Birden fazla il", r["ilHatalar"]["belirsiz"]); self.assertIn("plaka kodu 42", r["ilHatalar"]["celisik"])
        self.assertEqual(r["ilGecis"], "/il/cankiri")

if __name__ == "__main__": unittest.main()
