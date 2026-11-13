"""Yenilenen ana sayfa: SEO etiketleri/yapılandırılmış veri korunur, üç büyük il kartı veriden (sabit kodlanmadan) hesaplanır ve il sayfalarıyla eşleşir,
81 ilin gerçek bağlantıları ve il seçimi, hesaplayıcı işlevleri (mevcut kimlikler), erişilebilirlik ve 5 genişlikte yerleşim."""
import datetime as dt, functools, html, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
from test_il_sayfasi import veri, sayfa, slug, TAM, inv, tr, E0, tahmin_plaka
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
        KALDIRILAN = {"counter", "counter-num",                                   # Abacus ziyaret rozeti (kaldırıldı)
                      "plate", "pop", "btn-last", "last-txt", "last-panel", "meta", "warn", "btn-today"}   # tarih sorgusunun eski karmaşık arayüzü (sadeleştirildi: plaka+etiket+belirsizlik; son veri açılırı, hız satırları, "Bugün" düğmesi yok)
        self.assertEqual(eski_idler - yeni_idler - KALDIRILAN, set(), "hesaplayıcı kimlikleri korunmalı (yalnızca belgelenen sadeleştirme dışında)")
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
            py = tahmin_plaka(kod, n + fc.advance(o, fc.clean(o), g, (bas - ld).days, fc.slope(o, g))); sr, no = inv(n)
            self.assertEqual(re.search(r'data-kart="plaka">([^<]*)<', ic)[1], py); self.assertEqual(re.search(r'data-kart="plaka">([^<]*)<', ic)[1], re.search(r'data-live="plaka">([^<]*)<', h)[1])     # tam plaka: il sayfasıyla birebir aynı
            self.assertEqual(re.search(r'data-kart="tarih">([^<]*)<', ic)[1], tr(bas)); self.assertIn("itibarıyla", ic); self.assertIn("Tahmindir", ic)
            self.assertIn(f"Son gözlem: {kod:02d} {sr} {no:03d} · {tr(ld)}", metin(ic)); self.assertIn(f"{il} · {kod:02d}", metin(ic))                                                   # gözlem tahminden ayrı
            self.assertTrue(os.path.isfile(os.path.join(u.ROOT, href.lstrip("/") + ".html")))
        self.assertIn('<span id="last-global">13.11.2026</span>', ANA)

    def test_kart_degerleri_sabit_degil_veriye_baglidir(self):
        d = u.kopya(ekstra=("sitemap.xml",))
        try:
            yol = os.path.join(d, "data", "tahmin_data.json")
            with open(yol, encoding="utf-8") as f: v = json.load(f)
            ist = next(x for x in v["iller"] if x["il"] == "İstanbul"); ist["obs"][-1][1] += 90000                    # 90 seri ileri
            with open(yol, "w", encoding="utf-8") as f: json.dump(v, f, ensure_ascii=False, separators=(",", ":"))
            r = u.uret(d, "--bugun", "2026-11-13"); self.assertEqual(r.returncode, 0, r.stderr)
            yeni = u.oku(os.path.join(d, "index.html")); eski_seri = re.search(r'data-il="İstanbul">.*?data-kart="plaka">([^<]*)<', ANA, re.S)[1]
            yeni_seri = re.search(r'data-il="İstanbul">.*?data-kart="plaka">([^<]*)<', yeni, re.S)[1]; self.assertNotEqual(yeni_seri, eski_seri)
            self.assertEqual(yeni_seri, re.search(r'data-live="plaka">([^<]*)<', u.oku(os.path.join(d, "il", "istanbul.html")))[1])                  # kart = il sayfası
            self.assertEqual(re.search(r'data-il="Ankara">.*?data-kart="plaka">([^<]*)<', yeni, re.S)[1], re.search(r'data-il="Ankara">.*?data-kart="plaka">([^<]*)<', ANA, re.S)[1])
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

    # Alternatif il adları (yalnızca arama eşleştirmesi): ana sayfa il araması. Değişiklik öncesi sürüm sabit commit'ten alınır (ALTERNATIF_AD_ONCESI) ve aynı girdilerde karşılaştırılır.
    TAKMA = {"Maraş": "kahramanmaras", "K.Maraş": "kahramanmaras", "Urfa": "sanliurfa", "Antep": "gaziantep", "İzmit": "kocaeli", "Adapazarı": "sakarya", "Antakya": "hatay", "İçel": "mersin"}
    ALTERNATIF_AD_ONCESI = "6c62082"
    def _il_bul_karsilastir(self, girisler):
        ops = re.findall(r'<option value="[^"]+" data-ad="([^"]+)" data-kod="(\d+)" data-slug="([a-z]+)">', ANA); liste = [{"ad": html.unescape(a), "kod": int(k), "slug": s} for a, k, s in ops]
        eski = subprocess.run(["git", "show", f"{self.ALTERNATIF_AD_ONCESI}:assets/ana-sayfa.js"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout
        self.assertNotIn("TAKMA_ADLAR", eski)
        d = tempfile.mkdtemp(prefix="plaka_ilbul_")
        try:
            for ad, icerik in (("eski.js", eski), ("liste.json", json.dumps(liste)), ("g.json", json.dumps(girisler, ensure_ascii=False))):
                with open(os.path.join(d, ad), "w", encoding="utf-8") as f: f.write(icerik)
            kod = ("const fs=require('fs'),vm=require('vm'),p=require('path'),d=process.argv[1];const yukle=k=>{const c={Math,Date,console};vm.createContext(c);vm.runInContext(k+';this.P=PlakaAnaSayfa;',c);return c.P;};"
                   "const E=yukle(fs.readFileSync(p.join(d,'eski.js'),'utf8')),Y=yukle(fs.readFileSync('assets/ana-sayfa.js','utf8'));const l=JSON.parse(fs.readFileSync(p.join(d,'liste.json'),'utf8'));"
                   "const oz=r=>[r.tip,r.il?r.il.slug:null,r.adaylar?r.adaylar.map(x=>x.slug):null];"
                   "console.log(JSON.stringify(JSON.parse(fs.readFileSync(p.join(d,'g.json'),'utf8')).map(g=>{const t=Y.trNorm(g),ad=t.replace(/\\b\\d{1,2}\\b/g,' ').replace(/\\s+/g,' ').trim();return [g,ad,oz(E.ilBul(g,l)),oz(Y.ilBul(g,l))];})));")
            return liste, json.loads(subprocess.run([u.NODE, "-e", kod, d], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout)
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_alternatif_il_adlari_dogru_ile_gider(self):
        fold = lambda t: t.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
        girisler, beklenen = [], {}
        for takma, sl in self.TAKMA.items():
            for g in (takma, takma.lower(), takma.replace("i", "İ").replace("ı", "I").upper(), fold(takma), fold(takma).lower(), fold(takma).upper(), f"  {takma}  ", takma.replace(".", ". ")):
                girisler.append(g); beklenen[g] = ("tamam", sl)
        liste, sonuc = self._il_bul_karsilastir(girisler + ["Maraş 46", "46 Maraş", "Maraş 27", "Urfa (63)", "K. Maraş", "k.maras"])
        kod = {x["slug"]: x["kod"] for x in liste}
        beklenen.update({"Maraş 46": ("tamam", "kahramanmaras"), "46 Maraş": ("tamam", "kahramanmaras"), "Maraş 27": ("celisik", "kahramanmaras"), "Urfa (63)": ("tamam", "sanliurfa"),
                         "K. Maraş": ("tamam", "kahramanmaras"), "k.maras": ("tamam", "kahramanmaras")})
        self.assertEqual((kod["kahramanmaras"], kod["sanliurfa"], kod["gaziantep"], kod["kocaeli"], kod["sakarya"], kod["hatay"], kod["mersin"]), (46, 63, 27, 41, 54, 31, 33))      # hedef iller ve kodları değişmedi
        for g, ad, eski, yeni in sonuc:
            self.assertEqual(tuple(yeni[:2]), beklenen[g], g)
            self.assertEqual(eski[0], "yok", f"{g}: değişiklikten önce bulunamıyordu")              # alternatif adlar yeni eşleşmedir; başka bir ile gitmiyordu

    def test_alternatif_adlar_mevcut_aramayi_degistirmez(self):
        # Değişiklik öncesiyle aynı girdilerde birebir aynı sonuç (tip, il, belirsiz adaylar); TEK fark: ad kısmı tam olarak bir alternatif ad olan girdiler.
        import random; rnd = random.Random(20261111)
        ops = re.findall(r'data-ad="([^"]+)" data-kod="(\d+)"', ANA); fold = lambda t: t.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
        girisler = ["", " ", "k", "ka", "kar", "an", "ant", "anta", "a", "ad", "ada", "mar", "mara", "ur", "urf", "ante", "izm", "izmi", "ic", "ice", "sa", "ha", "me", "ko", "ga", "kah", "san"]
        for a, k in ops:
            a = html.unescape(a); f = fold(a).lower()
            girisler += [a, a.upper(), a.lower(), f, f"{a} {k}", f"{k} {a}", f"{a} 99", k, f"{int(k):02d}"] + [f[:i] for i in range(1, len(f) + 1)] + [a[:i] for i in range(1, len(a) + 1)]
        for t in self.TAKMA: girisler += [t[:i] for i in range(1, len(t) + 1)] + [t + "x", "x" + t, t + " " + t, t + " merkez"]
        harfler = "abcçdefgğhıijklmnoöprsştuüvyzABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ0123456789 .-'()"
        girisler += ["".join(rnd.choice(harfler) for _ in range(rnd.randint(1, 12))) for _ in range(4000)] + [str(i) for i in range(0, 101)]
        _, sonuc = self._il_bul_karsilastir(girisler)
        takma_anahtar = {"maras", "k maras", "urfa", "antep", "izmit", "adapazari", "antakya", "icel"}; degisen = 0
        for g, ad, eski, yeni in sonuc:
            if ad in takma_anahtar: degisen += 1; self.assertEqual(eski[0], "yok", g); self.assertIn(yeni[0], ("tamam", "celisik"), g); continue
            self.assertEqual(eski, yeni, g)
        self.assertGreater(len(sonuc), 5000); self.assertGreater(degisen, 0)
        bek = {g: ("belirsiz", None) for g in ("k", "ka", "an", "a", "ad", "sa", "ha", "ko", "ma", "i", "b", "e", "s", "m")}          # belirsiz kısmi aramalar belirsiz kalır
        bek.update({"kah": ("tamam", "kahramanmaras"), "san": ("tamam", "sanliurfa"), "ant": ("tamam", "antalya"), "mar": ("tamam", "mardin"), "ada": ("tamam", "adana"), "izmi": ("tamam", "izmir"), "me": ("tamam", "mersin"), "ga": ("tamam", "gaziantep"),   # alternatif adın öneki
                    "mara": ("yok", None), "urf": ("yok", None), "ante": ("yok", None), "ic": ("yok", None), "ice": ("yok", None), "ur": ("yok", None)})                             # kısmi eşleşmeye katılmaz
        for g, ad, eski, yeni in sonuc:
            if g in bek: self.assertEqual(tuple(yeni[:2]), bek[g], g); self.assertEqual(eski, yeni, g)
        self.assertTrue(set(bek) <= {x[0] for x in sonuc})

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

    def test_testler_uretim_analitigine_istek_atmaz(self):
        for r in self.sonuc: self.assertFalse(r["analitikBetigi"], "GoatCounter betiği yüklendi: test tarayıcısı üretim analitiğine istek atmış olabilir")
        for f in ("test_ana_sayfa_regresyon.py", "test_il_arac.py", "test_ana_sayfa_tasarim.py", "test_il_yerlesim.py", "test_tarih_tutarliligi.py"):
            self.assertNotIn("subprocess.run([" + "CHROME,", u.oku(os.path.join(u.ROOT, "tests", f)), f"{f}: Chrome CHROME_TEMEL ile başlatılmalı")

    def test_uc_kart_buyuk_seri_ve_ilk_ekran(self):
        for r in self.sonuc:
            self.assertEqual(r["kartSayisi"], 3); self.assertTrue(r["seriTekSatir"], f"{r['w']}px: tam tahmini plaka (06 GGL 482) tek satır olmalı"); self.assertGreaterEqual(r["govdePx"], 16)
            # tek sütunda (<700 px) plaka ≥ 36 px ve başlıktan büyük; 3 sütunda (≥700 px) kart içeriği ~190 px olduğundan 10 karakterlik plaka ≈ 30 px: yine gövdenin ≈ 1,9 katı ve kartta baskın
            if r["w"] < 700: self.assertGreaterEqual(r["seriPx"], 36, r["w"]); self.assertGreater(r["seriPx"], r["h1Px"] * 0.9, r["w"])
            else: self.assertGreaterEqual(r["seriPx"], 29, r["w"]); self.assertGreater(r["seriPx"], r["govdePx"] * 1.8, r["w"])
            self.assertTrue(r["seriSigar"], f"{r['w']}px: plaka kart içine sığmalı"); self.assertTrue(r["etiketli"], r["w"])
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
        self.assertEqual(r["ilBagimsiz"], {"hedefIl": "Ankara", "tarihIl": "İzmir"})          # hedef girişinde başa yazılan il kodu (06 GAA) yalnızca hedef aracının ilini değiştirir; tarih aracının ili bağımsızdır
        self.assertRegex(r["tarihKonya"], r"^42 [A-Z]{3} \d{3}$"); self.assertEqual(r["hedefIlSonra"], "Ankara"); self.assertTrue(r["ilDegisinceTemiz"])
        self.assertEqual((r["bosTarih"]["hata"], r["bosTarih"]["rol"], r["bosTarih"]["sonucGizli"]), ("Lütfen geçerli bir tarih seçin.", "alert", True))

    def test_tarih_araci_sade_baslangic_ve_5_genislikte_okunur(self):
        self.assertEqual({r["w"] for r in self.sonuc}, {320, 375, 390, 768, 1440})
        for r in self.sonuc:
            o, t, w = r["tarihOnce"], r["tarih"], r["w"]
            self.assertTrue(o["sonucGizli"] and o["plakaBos"], f"{w}px: hesaplamadan önce yanıltıcı örnek plaka olmamalı"); self.assertEqual(o["ilVarsayilan"], "İstanbul"); self.assertTrue(o["govdeGorunur"] and o["tabloKapali"] and o["gelismisKapali"], w)
            self.assertRegex(o["dtVarsayilan"], r"^\d{4}-\d\d-\d\d$"); self.assertRegex(t["plaka"], r"^35 [A-Z]{3} \d{3}$", w); self.assertTrue(t["sonucGorunur"] and t["tekSatir"] and t["sigar"], f"{w}px: büyük tam plaka tek satır ve sığmalı")
            self.assertGreaterEqual(t["px"], 36, w); self.assertGreaterEqual(t["btnYuk"], 44, w); self.assertGreaterEqual(t["dtYuk"], 44, w); self.assertGreaterEqual(t["ilYuk"], 44, w); self.assertLessEqual(t["tasma"], 0, w); self.assertGreaterEqual(t["govdePx"], 15, w); self.assertEqual(t["tag"], "Tahmin")

    def test_il_secimi_hatalari_ve_gecis(self):
        r = next(x for x in self.sonuc if x["w"] == 375)
        self.assertIn("Bir il adı", r["ilHatalar"]["bos"]); self.assertIn("bulunamadı", r["ilHatalar"]["yok"]); self.assertIn("Birden fazla il", r["ilHatalar"]["belirsiz"]); self.assertIn("plaka kodu 42", r["ilHatalar"]["celisik"])
        self.assertEqual(r["ilGecis"], "/il/cankiri")
        self.assertEqual((r["ilTakma"], r["ilTakmaHata"]), ("/il/kahramanmaras", ""))          # alternatif ad (Maraş), 375 px: resmî il sayfasına gider

if __name__ == "__main__": unittest.main()
