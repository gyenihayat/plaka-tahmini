"""Kullanıcı katkı sistemi (/geri-bildirim + /api/geri-bildirim): API testleri (Node, GitHub taklit), sayfa/altbilgi/yapı denetimleri ve gerçek tarayıcıda (Chrome headless)
form etkileşimi. GitHub'a hiçbir istek gitmez; tarayıcı testlerinde API yerine Python'daki sahte uç nokta konuşur ve aldığı gövdeleri gerçek sunucu doğrulayıcısından geçirilir."""
import functools, glob, html, http.server, json, os, re, socket, subprocess, sys, tempfile, threading, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL

ONCEKI_URETIM = "4feab5d"          # geri bildirim bağlantısı eklenmeden önceki yayın: sayfalar bu bağlantı dışında birebir aynı kalmalı
KATKI_COMMIT = "b3a993d"           # katkı sistemini ekleyen commit (ebeveyni ONCEKI_URETIM)
SAYFA = u.oku(os.path.join(u.ROOT, "geri-bildirim.html"))
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
BAGLANTI_METNI = "Öneri ve katkı gönder"
GENISLIKLER = [320, 375, 390, 768, 1440]
TAM = {"K.Maraş": "Kahramanmaraş", "Afyon": "Afyonkarahisar"}
def slug(s): return s.translate(str.maketrans("çğıöşüÇĞİÖŞÜâ. ", "cgiosucgiosua--")).lower().replace("-", "")
def il_listesi(): return json.loads(subprocess.run([u.NODE, "-e", "console.log(JSON.stringify(require('./api/_iller.js')))"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout)
def git(*a): return subprocess.run(["git", *a], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout
def kod_satirlari(yol): return "\n".join(l for l in u.oku(yol).split("\n") if not l.lstrip().startswith(("*", "//", "/*")))      # yorum satırları hariç
def katkisiz(h): return re.sub(r"<!--KATKI-->.*?<!--/KATKI-->\n|<!--ANA:KATKI-->.*?<!--/ANA:KATKI-->\n", "", h, flags=re.S)

@unittest.skipUnless(u.NODE, "Node yok")
class ApiTestleri(unittest.TestCase):
    def test_node_api_testleri(self):
        r = subprocess.run([u.NODE, "--test", "tests/api/geri_bildirim.test.js"], cwd=u.ROOT, capture_output=True, text=True, timeout=120)
        gecen = int(re.search(r"ℹ pass (\d+)", r.stdout)[1]); kalan = int(re.search(r"ℹ fail (\d+)", r.stdout)[1])
        self.assertEqual((r.returncode, kalan), (0, 0), r.stdout[-3000:] + r.stderr[-500:]); self.assertGreaterEqual(gecen, 29)

@unittest.skipUnless(u.NODE, "Node yok")
class YapiVeSayfa(unittest.TestCase):
    def test_il_listesi_tek_kaynak_uc_yerde_ayni(self):
        api = il_listesi(); self.assertEqual(len(api), 81)
        veri = {x["kod"]: TAM.get(x["il"], x["il"]) for x in json.loads(u.oku(os.path.join(u.ROOT, "data", "tahmin_data.json")))["iller"]}
        self.assertEqual({k: a for k, a, _ in api}, veri); self.assertEqual({s for _, _, s in api}, {slug(a) for a in veri.values()})
        secenekler = re.findall(r'<option value="(\d\d)" data-slug="([a-z]+)">([^<]+) \((\d\d)\)</option>', SAYFA)
        self.assertEqual(len(secenekler), 81); self.assertEqual(sorted((int(v), s, a) for v, s, a, _ in secenekler), sorted((k, s, a) for k, a, s in api)); self.assertTrue(all(v == k for v, _, _, k in secenekler))
        for _, a, s in api:
            self.assertTrue(os.path.isfile(os.path.join(u.ROOT, "il", s + ".html")), s); self.assertIn(f"<h1>{html.escape(a)} Plaka Sırası Hangi Harfte?</h1>", u.oku(os.path.join(u.ROOT, "il", s + ".html")))

    def test_ana_sayfa_altbilgi_baglantisi(self):
        self.assertEqual(len(re.findall(re.escape(BAGLANTI_METNI), ANA)), 1)
        self.assertRegex(ANA, r'<!--ANA:KATKI-->\n<p class="katki"[^>]*><a href="/geri-bildirim\?sayfa=%2F"[^>]*><span[^>]*>Öneri ve katkı gönder</span><span[^>]*>Plaka bilgisi paylaşın, öneri veya hata bildirin</span></a></p>\n<!--/ANA:KATKI-->\n<!--ANA:IL-BAGLANTILAR-->\n<nav class="iller-liste" aria-label="İl sayfaları"><h2>İllere Göre Güncel Plaka Serileri</h2>')       # kutu, "İllere Göre Güncel Plaka Serileri" başlığının hemen üstünde
        self.assertLess(ANA.index("ANA:KATKI"), ANA.index("ANA:OLCUM-NOTU")); self.assertGreater(ANA.index("ANA:KATKI"), ANA.index("Tahminlerin sınırlamaları")); self.assertEqual(ANA.count("/geri-bildirim"), 1)

    def test_81_il_sayfasinin_altbilgisinde_dogru_il_ile_baglanti(self):
        sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81); esle = {s: k for k, _, s in il_listesi()}
        for yol in sayfalar:
            s = os.path.basename(yol)[:-5]; h = u.oku(yol); b = re.findall(r'<!--KATKI--><p class="katki"[^>]*><a href="(/geri-bildirim\?[^"]*)"[^>]*><span[^>]*>Öneri ve katkı gönder</span><span[^>]*>[^<]*</span></a></p><!--/KATKI-->', h)
            self.assertEqual(b, [f"/geri-bildirim?il={esle[s]:02d}&amp;sayfa=%2Fil%2F{s}"], s); self.assertEqual(h.count(BAGLANTI_METNI), 1)
            self.assertLess(h.index("<!--KATKI-->"), h.index("</main>")); self.assertLess(h.index("<!--KATKI-->"), h.index('<!--OLCUM--><p class="olcum-notu">'))

    def test_mevcut_82_sayfa_seo_olcum_ve_yapi_ayni(self):
        """Katkı sistemi öncesi yayın (4feab5d) ile karşılaştırma: SEO etiketleri, GoatCounter yükleyicisi ve ölçüm notu, başlık/JSON-LD yapısı aynı; günlük veri (son gözlem plakası/tarihi) maskelenir.
        Hesaplayıcı sonuçlarının aynılığı ayrı testlerde (motor golden, tarih aracı eski/yeni karşılaştırması) denetlenir."""
        sayfalar = ["index.html"] + [f"il/{os.path.basename(p)}" for p in sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html")))]; self.assertEqual(len(sayfalar), 82)
        maske = lambda t: re.sub(r"\d{1,2} (?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık) 20\d\d", "TARIH", re.sub(r"\b\d\d [A-Z]{3} \d{3}\b", "PLAKA", t))
        for s in sayfalar:
            eski = git("show", f"{ONCEKI_URETIM}:{s}"); yeni = u.oku(os.path.join(u.ROOT, s))
            for desen in (r"<title>.*?</title>", r'<meta name="description" content="[^"]*">', r'<link rel="canonical" href="[^"]*">', r"<h1>.*?</h1>", r'<meta property="og:[a-z:]+" content="[^"]*">', r'<script type="application/ld\+json">.*?</script>',
                          r"<!--OLCUM-->.*?<!--/OLCUM-->", r'<p class="olcum-notu">.*?</p>'):
                self.assertEqual([maske(x) for x in re.findall(desen, yeni, re.S)], [maske(x) for x in re.findall(desen, eski, re.S)], (s, desen))
            self.assertEqual(len(re.findall(r"<!--KATKI-->|<!--ANA:KATKI-->", yeni)), 1, s); self.assertEqual(len(re.findall(r"<!--KATKI-->|<!--ANA:KATKI-->", eski)), 0, s)
        # Katkı sistemi bu dosyalara dokunmaz. Önceki biçim `git diff HEAD` idi: commit edilmemiş, beklenen her değişiklikte başarısız oluyor (liste bu yüzden zamanla kısaltılmıştı),
        # commit'ten sonra ise hiçbir şey denetlemiyordu. HEAD'den bağımsız iki denetim: (1) katkı sistemini ekleyen commit'in bu dosyalardaki ayak izi boştur (özgün iddia, kalıcı);
        # (2) bu dosyaların hiçbirinde, commit edilmiş olsun ya da olmasın, katkı sistemine bağlanan kod yoktur (sayfa/API yolu, katkı olay adları, GitHub, ağ isteği).
        # Dosyaların kendi içerik doğruluğu ayrı testlerdedir (motor golden ve Python–JS eşliği, iş günü/takvim eşliği, ana sayfa ve ölçüm testleri).
        korunan = ("assets/ana-sayfa.js", "assets/takvim.js", "vercel.json", "robots.txt", "forecast.py", "is_gunu.py")
        self.assertEqual(git("rev-parse", f"{KATKI_COMMIT}^"), git("rev-parse", ONCEKI_URETIM))                  # ayak izi, katkı öncesi yayına göre ölçülür
        self.assertEqual(git("diff", "--stat", f"{KATKI_COMMIT}^", KATKI_COMMIT, "--", *korunan), "")
        self.assertNotEqual(git("diff", "--stat", f"{KATKI_COMMIT}^", KATKI_COMMIT, "--", "geri-bildirim.html", "api"), "")      # ayak izi ölçümü gerçekten katkı commit'ini görüyor
        for f in korunan: self.assertNotRegex(u.oku(os.path.join(u.ROOT, f)), r"(?i)geri[-_]bildirim|/api/|katk[ıi]|plaka_bildirimi|genel_oneri|github|fetch\(|XMLHttpRequest|sendBeacon", f)

    def test_sitemap_ve_arama_motoru(self):
        sm = u.oku(os.path.join(u.ROOT, "sitemap.xml")); self.assertEqual(sm.count("<url>"), 83); self.assertNotIn("geri-bildirim", sm)       # ana sayfa + 81 il + /istatistik
        self.assertIn('<meta name="robots" content="noindex, follow">', SAYFA); self.assertNotIn("canonical", SAYFA)
        self.assertNotIn("geri-bildirim", u.oku(os.path.join(u.ROOT, "robots.txt")))

    def test_sayfa_icerigi_ve_gizlilik(self):
        self.assertIn("<h1>Sitemizi geliştirmemize yardımcı olun</h1>", SAYFA)
        self.assertIn("Paylaştığınız plaka ve tarih bilgileri tahminleri geliştirmek amacıyla incelenir. Gönderilen bilgiler otomatik olarak tahminlere dahil edilmez.", SAYFA)
        self.assertRegex(SAYFA, r"Plaka sahibinin adını.*?başka kişisel bilgi yazmayın"); self.assertIn("Teşekkürler! Bildiriminiz alındı.", SAYFA)
        self.assertIn("Plaka bilgisi paylaş", SAYFA); self.assertIn("Öneri / Hata bildir", SAYFA)
        self.assertNotIn("abacus", SAYFA.lower())
        self.assertEqual(re.findall(r'<script[^>]*src="([^"]+)"', SAYFA), ["/assets/olcum.js", "/assets/geri-bildirim.js"]);       # olcum.js önce: form betiği PlakaOlcum'u kullanır self.assertNotIn("GITHUB", SAYFA + u.oku(os.path.join(u.ROOT, "assets", "geri-bildirim.js")))
        self.assertNotRegex(kod_satirlari(os.path.join(u.ROOT, "assets", "geri-bildirim.js")), r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(")
        for ad in re.findall(r'<(?:input|select|textarea)[^>]*\bname="([^"]+)"', SAYFA): self.assertIn(ad, {"sekme", "il", "plaka", "kesinlik", "gun", "ay", "yil", "aciklama", "website", "tur", "mesaj", "isim"}, ad)
        self.assertNotRegex(SAYFA, r'type="(?:email|tel|file|password)"|name="(?:email|e-posta|telefon|ad_soyad|tc|ruhsat)')
        self.assertEqual(len(re.findall(r'<label[^>]*for="(?:p|o)-(?:il|plaka|aciklama|mesaj|isim|gun|ay|yil)"', SAYFA)), 8)

    def test_goatcounter_entegrasyonu_mevcut_yukleyiciyle_ve_yalniz_anonim_olay(self):
        self.assertEqual(SAYFA.count('<!--OLCUM--><script src="/assets/olcum.js" defer></script><!--/OLCUM-->'), 1)
        js = u.oku(os.path.join(u.ROOT, "assets", "geri-bildirim.js")); kod = kod_satirlari(os.path.join(u.ROOT, "assets", "geri-bildirim.js"))
        for yasak in ("gc.zgo.at", "data-goatcounter", "goatcounter.com/count", "goatcounter.count(", "sendBeacon"): self.assertNotIn(yasak, SAYFA + js, f"doğrudan analitik kodu olmamalı: {yasak}")
        self.assertEqual(re.search(r'<p class="olcum-notu">.*?</p>', SAYFA, re.S)[0], re.search(r'<p class="olcum-notu">.*?</p>', ANA, re.S)[0])       # diğer sayfalarla aynı görünür bilgilendirme
        # olay çağrıları: yalnızca iki sabit ad, yalnızca sunucu başarısından sonra (ok === true) ve tekrar yanıtında değil
        self.assertEqual(re.findall(r"\bolay\(([^)]*)\)", kod), ['ad', 'ad === "plaka" ? "plaka_bildirimi" : "genel_oneri"']); self.assertEqual(len(re.findall(r"PlakaOlcum", kod)), 2)
        self.assertRegex(js, r'if \(s\.ok && s\.j && s\.j\.ok === true\) \{\n\s+if \(!s\.j\.tekrar\) olay\(')
        self.assertLess(js.index("PlakaOlcum"), js.index("fetch(")); self.assertGreater(js.index('olay(ad === "plaka"'), js.index("fetch("))
        # olcum.js: yalnızca izin listesine iki ad eklendi (bir önceki yayına göre); yükleme koşulları ve geri kalan her şey aynı.
        # Kasım 2026'daki hesaplayıcı hata kategorileri eklemesi (izin listesindeki kategori olayları, KATEGORI_OLAYLARI..girisBicimi bloğu, dışa aktarılan adlar) çıkarılınca da aynı kalmalı.
        yorumsuz = lambda t: "\n".join(l for l in t.split("\n") if not l.lstrip().startswith("//"))
        yeni = yorumsuz(u.oku(os.path.join(u.ROOT, "assets", "olcum.js"))).replace("|plaka_bildirimi|genel_oneri", "")
        kategori = (r"\|ana-hesapla-hata\\/\(\?:bos\|tek-harf\|iki-harf\|format\|karakter\|il-kodu\|hesaplama\)\|il-hesapla-hata\\/\(\?:bos\|tek-harf\|iki-harf\|format\|karakter\|il-kodu\|baska-il\|atla\|hesaplama\)",
                    r"\|ana-il-ara-hata\\/\(\?:bos\|belirsiz\|bulunamadi\|celisik\)", r"  const KATEGORI_OLAYLARI = .*?\n(?=  const kayit = \[\];)", r", KATEGORI_OLAYLARI, kategoriOlayi, hedefHataKategorisi, girisBicimi(?= \})")
        for desen in kategori: yeni, n = re.subn(desen, "", yeni, count=1, flags=re.S); self.assertEqual(n, 1, desen)
        self.assertEqual(yeni, yorumsuz(git("show", f"{ONCEKI_URETIM}:assets/olcum.js")))

    def test_olcum_uretimde_yalniz_iki_yeni_olayi_icerik_olmadan_gonderir(self):
        kod = r"""
const fs=require('fs'),vm=require('vm'); const eklenen=[], sayilan=[]; const el=()=>({attrs:{},setAttribute(k,v){this.attrs[k]=v}});
const ctx={console,document:{createElement:()=>el(),head:{appendChild:x=>eklenen.push(x)}},location:{hostname:'plakatahmini.com'},navigator:{webdriver:false},localStorage:{getItem:()=>null}};
vm.createContext(ctx); vm.runInContext(fs.readFileSync('assets/olcum.js','utf8'),ctx); ctx.goatcounter={count:v=>sayilan.push(v)}; eklenen[0].onload();
const adlar=['plaka_bildirimi','genel_oneri','plaka_bildirimi/06','genel_oneri?x=1','plaka_bildirimi BYS','Plaka_Bildirimi','plaka-bildirimi','genel_oneri/','oneri','06 BYS 922'];
const sonuc=adlar.map(a=>{ctx.__a=a;return vm.runInContext('PlakaOlcum.olay(__a)',ctx)});
console.log(JSON.stringify({sonuc,sayilan}));"""
        r = subprocess.run([u.NODE, "-e", kod], cwd=u.ROOT, capture_output=True, text=True, check=True); o = json.loads(r.stdout)
        self.assertEqual(o["sonuc"], [True, True] + [False] * 8); self.assertEqual(o["sayilan"], [{"path": "plaka_bildirimi", "title": "plaka_bildirimi", "event": True}, {"path": "genel_oneri", "title": "genel_oneri", "event": True}])

    def test_kayitlar_herkese_acik_site_dosyalarinda_degil(self):
        for ad in ("oneriler.txt", "plaka_bildirimleri.txt"):
            self.assertFalse(os.path.exists(os.path.join(u.ROOT, ad)), ad); self.assertEqual(git("ls-files", "--", ad), ""); self.assertIn(ad, u.oku(os.path.join(u.ROOT, ".gitignore")).splitlines())
        izlenen = git("ls-files").split("\n"); self.assertFalse([x for x in izlenen if re.search(r"oneriler|plaka_bildirimleri|geri_bildirim.*\.(txt|jsonl)$", x, re.I) and not x.startswith("tests/")])
        for yol in glob.glob(os.path.join(u.ROOT, "api", "*.js")):                    # kullanıcı kayıtları hiçbir koşulda sitenin gözlem/referans verisine yazılmaz: kodda bu dosyalara yol yok
            self.assertNotRegex(kod_satirlari(yol), r"tahmin_data|tarihsel_referanslar|data/", yol)
        self.assertEqual(json.loads(u.oku(os.path.join(u.ROOT, "vercel.json"))).keys(), {"cleanUrls": 0, "trailingSlash": 0, "redirects": 0}.keys())     # yönlendirme/yeniden yazma kuralı eklenmedi: /api ile çakışma yok

    def test_token_depoda_yok(self):
        for yol in git("ls-files", "--others", "--cached", "--exclude-standard").split("\n"):
            if not yol or not os.path.isfile(os.path.join(u.ROOT, yol)) or yol.startswith(("backups/", "tests/")) or yol.endswith((".png", ".zip")): continue
            self.assertNotRegex(u.oku(os.path.join(u.ROOT, yol)), r"ghp_[A-Za-z0-9]{20}|github_pat_[A-Za-z0-9_]{20}", yol)

# --- tarayıcı testleri -------------------------------------------------------------------------------------------------------
def sahte_sunucu():
    durum = {"mod": "basari", "kayit": []}
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k): pass
        def _json(self, kod, govde, tur="application/json"):
            b = (govde if isinstance(govde, str) else json.dumps(govde, ensure_ascii=False)).encode(); self.send_response(kod); self.send_header("Content-Type", tur + "; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            yol, _, q = self.path.partition("?")
            if yol == "/__mod": durum["mod"] = q.split("=")[1]; return self._json(200, {})
            if yol == "/__sifirla": durum["kayit"].clear(); durum["mod"] = "basari"; return self._json(200, {})
            if yol == "/__kayit": return self._json(200, durum["kayit"])
            if yol == "/api/geri-bildirim": return self._json(405, {"ok": False})
            if "." not in os.path.basename(yol) and os.path.isfile(os.path.join(u.ROOT, yol.lstrip("/") + ".html")): self.path = yol + ".html" + (("?" + q) if q else "")
            super().do_GET()
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0); govde = json.loads(self.rfile.read(n) or b"{}"); durum["kayit"].append(govde); m = durum["mod"]
            if m == "ag": self.close_connection = True; self.connection.close(); return
            if m == "yavas": time.sleep(0.8)
            cevap = {"basari": (200, {"ok": True}), "yavas": (200, {"ok": True}),
                     "hata500": (500, {"ok": False, "error": "Bildiriminiz kaydedilemedi. Lütfen biraz sonra tekrar deneyin."}),
                     "sinir429": (429, {"ok": False, "error": "Kısa sürede çok fazla gönderim yapıldı. Lütfen biraz bekleyip tekrar deneyin."}),
                     "kapali503": (503, {"ok": False, "error": "Bildirim alma şu an kapalı. Lütfen daha sonra tekrar deneyin."}),
                     "alan400": (400, {"ok": False, "error": "Listeden bir il seçin.", "alan": "il"}),
                     "html": (500, {"ok": False, "error": "<img src=x onerror=window.__xss=1>Sunucu mesajı"}), "tekrar": (200, {"ok": True, "tekrar": True})}.get(m)
            if m == "jsondegil": return self._json(502, "<html><body>Bad Gateway</body></html>", "text/html")
            self._json(*cevap)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port, durum

@unittest.skipUnless(CHROME and u.NODE, "Chrome/Node yok")
class Tarayici(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        il_baglantilari = []
        for k, _, s in il_listesi():
            h = u.oku(os.path.join(u.ROOT, "il", s + ".html")); href = html.unescape(re.search(r'<!--KATKI--><p[^>]*><a href="([^"]+)"', h)[1]); il_baglantilari.append([href, {"il": f"{k:02d}", "sayfa": f"/il/{s}"}])
        il_baglantilari.append([html.unescape(re.search(r'<!--ANA:KATKI-->\n<p[^>]*><a href="([^"]+)"', ANA)[1]), {"il": "", "sayfa": "/"}])
        for q in ("?il=99", "?il=abc", "?il=0", "?il=06;DROP", "?sayfa=https%3A%2F%2Fevil.example", "?sayfa=%2Fil%2Fyok", "?sayfa=%3Cscript%3E", ""): il_baglantilari.append(["/geri-bildirim" + q, {"il": "", "sayfa": ""}])
        il_baglantilari.append(["/geri-bildirim?il=06&sayfa=%2Fil%2Fkonya", {"il": "06", "sayfa": "/il/konya"}]); il_baglantilari.append(["/geri-bildirim?sayfa=%2Fil%2Fkonya", {"il": "42", "sayfa": "/il/konya"}])
        cls.baglantilar = il_baglantilari
        d = tempfile.mkdtemp(prefix="plaka_gb_", dir=u.ROOT); srv, port, durum = sahte_sunucu()
        try:
            h = u.oku(os.path.join(u.ROOT, "tests", "ui", "geri_bildirim.html")).replace("__GENISLIKLER__", json.dumps(GENISLIKLER)).replace("__IL_BAGLANTILARI__", json.dumps(il_baglantilari))
            with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(h)
            r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=600000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=400)
        finally: srv.shutdown(); srv.server_close(); __import__("shutil").rmtree(d, ignore_errors=True)
        m = re.search(r"(SONUC|HATA) (.*?)\s*</pre>", r.stdout, re.S); assert m and m[1] == "SONUC", (m and html.unescape(m[2])[:800]) or (r.stderr[-400:] + r.stdout[-300:])
        cls.s = json.loads(html.unescape(m[2]))

    def test_yerlesim_5_genislik_2_sekme(self):
        self.assertEqual(len(self.s["yerlesim"]), 10)
        for r in self.s["yerlesim"]:
            k = f"{r['w']}px {r['sekme']}"
            self.assertLessEqual(r["sw"], r["cw"], k); self.assertEqual(r["tasan"], [], k); self.assertTrue(r["dugmeIcinde"], k)
            self.assertEqual(r["h1"], "Sitemizi geliştirmemize yardımcı olun"); self.assertEqual((r["plakaGorunur"], r["oneriGorunur"]), (r["sekme"] == "plaka", r["sekme"] == "oneri"), k)
            self.assertEqual(r["kucukKontrol"], [], f"{k}: dokunma hedefi < 44 px ya da yazı < 16 px (iOS yakınlaştırması)"); self.assertEqual(r["etiketsiz"], [], k)
            self.assertEqual(r["bal"]["tabindex"], -1); self.assertTrue(r["bal"]["disaridan"] and r["bal"]["ariaGizli"], k)
            self.assertFalse(r["zorunluSayfa"], "ilgili sayfa alanı kullanıcıya gösterilmemeli")
            if r["sekme"] == "plaka": self.assertNotRegex(r["metin"], r"(?i)e-?posta|telefon|ruhsat belgesi|\bT\.?C\.? ?no|kimlik no")
        plaka = [r for r in self.s["yerlesim"] if r["sekme"] == "plaka"][0]; self.assertEqual(plaka["alanlar"], ["il", "plaka", "kesinlik", "kesinlik", "kesinlik", "gun", "ay", "yil", "aciklama", "website"])
        oneri = [r for r in self.s["yerlesim"] if r["sekme"] == "oneri"][0]; self.assertEqual(oneri["alanlar"], ["tur", "tur", "tur", "mesaj", "isim", "website"])
        self.assertIn("Paylaştığınız plaka ve tarih bilgileri tahminleri geliştirmek amacıyla incelenir. Gönderilen bilgiler otomatik olarak tahminlere dahil edilmez.", plaka["metin"])
        self.assertIn("Plaka sahibinin adını", plaka["metin"])

    def test_plaka_formu_gun_ay_yil_ve_tam_plaka_yalnizca_seri(self):
        p = self.s["plaka"]
        self.assertEqual(p["ilkKesinlik"], {"gun": False, "ay": True, "yil": True}); self.assertEqual(p["gunSecili"], {"gun": True, "ay": True, "yil": True}); self.assertEqual(p["yilSecili"], {"gun": False, "ay": False, "yil": True})
        self.assertEqual(len(p["istekler"]), 3); gun, ay, yil = p["istekler"]
        for g in (gun, ay, yil): self.assertEqual(g["form"], "plaka"); self.assertEqual(g["website"], ""); self.assertGreaterEqual(g["gecen"], 2000); self.assertIsNone(g["sayfa"])
        self.assertEqual((gun["il"], gun["plaka"], gun["tarih"], gun["tarihKesinligi"], gun["aciklama"]), ("06", "06 BYS 922", "2020-06-01", "gun", "Bir tanıdığın aracı\nikinci satır"))
        self.assertEqual((ay["il"], ay["plaka"], ay["tarih"], ay["tarihKesinligi"]), ("34", "34 abc", "2021-03", "ay"))
        self.assertEqual((yil["il"], yil["plaka"], yil["tarih"], yil["tarihKesinligi"]), ("35", "ayt", "2019", "yil"))
        for r in (p["gun"], p["ay"], p["yil"]): self.assertTrue(r["tesekkur"], r)
        self.assertEqual(p["sonrasi"]["tesekkurMetin"], "Teşekkürler! Bildiriminiz alındı."); self.assertFalse(p["sonrasi"]["plakaForm"]); self.assertFalse(p["sonrasi"]["sekmeler"]); self.assertEqual(p["sonrasi"]["odak"], "tesekkur")
        self.assertTrue(p["yeniSonrasi"]["plakaForm"] and p["yeniSonrasi"]["sekmeler"] and not p["yeniSonrasi"]["tesekkur"]); self.assertEqual((p["yeniSonrasi"]["plaka"], p["yeniSonrasi"]["il"]), ("", ""))

    def test_oneri_formu(self):
        o = self.s["oneri"]
        self.assertEqual(o["sekmeSonrasi"], {"plakaForm": False, "oneriForm": True, "sayfaNotu": "Bu bildirim şu sayfayla ilişkilendirilecek: /il/ankara"}); self.assertTrue(o["sonuc"]["tesekkur"])
        self.assertEqual(len(o["istekler"]), 1); k = o["istekler"][0]
        self.assertEqual((k["form"], k["tur"], k["isim"], k["sayfa"]), ("oneri", "hata", "Ayşe <b>K</b>", "/il/ankara")); self.assertIn("<script>window.__xss=1</script>\n<img src=x", k["mesaj"])
        self.assertEqual(o["xss"], {"global": True, "img": 0, "script": 0 + o["xss"]["script"]}); self.assertEqual(o["xss"]["script"], 0)

    def test_istemci_dogrulamasi_istek_gondermez(self):
        h = self.s["istemciHata"]; self.assertEqual(len(h), 8)
        beklenen = {"il yok": ("p-il", "Listeden bir il seçin."), "plaka yok": ("p-plaka", "Plaka ya da harf serisi girin."), "yıl yok": ("p-yil", "dört haneli"), "yıl 3 hane": ("p-yil", "dört haneli"), "ay yok": ("p-ay", "Ayı seçin."), "gün yok": ("p-gun", "Günü seçin."), "mesaj boş": ("o-mesaj", "en az 5"), "mesaj kısa": ("o-mesaj", "en az 5")}
        for r in h: alan, metin = beklenen[r["ad"]]; self.assertIn(metin, r["metin"], r); self.assertEqual(r["alan"], alan, r); self.assertTrue(r["invalid"], r); self.assertEqual(r["istek"], 0, r); self.assertEqual(r["durum"], "alert")

    def test_sunucu_ve_ag_hatalari_anlasilir_mesaj_ve_yeniden_deneme(self):
        e = self.s["hatalar"]
        for ad, metin in (("sunucu500", "Bildiriminiz kaydedilemedi"), ("sinir429", "çok fazla gönderim"), ("kapali503", "şu an kapalı"), ("alanHatasi", "Listeden bir il seçin"), ("html", "Sunucu mesajı"), ("json_degil", "Gönderilemedi. Lütfen biraz sonra tekrar deneyin."), ("ag", "bağlantı kurulamadı")):
            r = e[ad]; self.assertFalse(r["tesekkur"], ad); self.assertIn(metin, r["hata"], ad); self.assertTrue(r["dugmeAcik"], ad); self.assertEqual(r["dugmeMetni"], "Gönder", ad); self.assertTrue(r["formGorunur"], ad); self.assertEqual(r["plaka"], "06 BYS ", ad); self.assertEqual(r["il"], "06", ad)
        self.assertEqual(e["alanOdak"], "p-il"); self.assertEqual(e["alanHatasi"]["invalid"], "true")
        self.assertEqual((e["htmlImg"], e["htmlGlobal"]), (0, True))
        self.assertTrue(e["tekrarDeneme"]["tesekkur"]); self.assertEqual(e["tekrarIstek"], 1)
        for ad, kelime in (("sunucu500", "token"), ("sunucu500", "GitHub")): self.assertNotIn(kelime, e[ad]["hata"])

    def test_anonim_olaylar_yalniz_basarili_kayittan_sonra(self):
        p, o, e = self.s["plaka"], self.s["oneri"], self.s["hatalar"]
        self.assertEqual(p["olay1"], ["plaka_bildirimi"]); self.assertEqual(p["olay2"], ["plaka_bildirimi", "plaka_bildirimi"]); self.assertEqual(o["olay"], ["genel_oneri"])
        self.assertEqual(e["olayHatada"], [], "sunucu/ağ hatasında olay gönderilmemeli"); self.assertEqual(e["olaySonra"], ["plaka_bildirimi"])
        self.assertEqual(self.s["istemciOlay"], [], "istemci doğrulama hatasında olay yok"); self.assertEqual(self.s["tekrar"], {"tesekkur": True, "olay": []})
        self.assertTrue(all(len(k) < 20 and re.fullmatch(r"[a-z_]+", k) for k in p["olay2"] + o["olay"]))

    def test_cift_gonderim_engellenir(self):
        c = self.s["cift"]; self.assertTrue(c["hemen"]["disabled"]); self.assertEqual(c["hemen"]["metin"], "Gönderiliyor…"); self.assertEqual(c["istek"], 1); self.assertTrue(c["tesekkur"])

    def test_81_il_sayfasindan_dogru_il_ve_sayfa_aktarilir(self):
        r = self.s["parametre"]; self.assertEqual(len(r), len(self.baglantilar))
        self.assertEqual(len([x for x in r if x["ne"]["il"] and x["ne"]["sayfa"].startswith("/il/")]), 83)
        for x in r:
            self.assertEqual(x["il"], x["ne"]["il"], x["src"]); self.assertTrue(x["degistirilebilir"], x["src"]); self.assertTrue(x["plakaForm"] and not x["oneriForm"], x["src"])
            self.assertEqual(x["not"], ("Bu bildirim şu sayfayla ilişkilendirilecek: " + x["ne"]["sayfa"]) if x["ne"]["sayfa"] else "", x["src"]); self.assertEqual(x["onot"], x["not"], x["src"])
            self.assertEqual(x["ph"], f"örn. {x['il']} XYZ 123 ya da XYZ" if x["il"] else "örn. XYZ 123 ya da XYZ", x["src"])      # örnek plaka seçili ilin kendi kodunu taşır
            if x["il"]: self.assertRegex(x["ilMetin"], r"\(%s\)$" % x["il"], x["src"])
        ilk81 = r[:81]; self.assertEqual(len({x["il"] for x in ilk81}), 81)
        self.assertEqual(self.s["phDegisince"], "örn. 35 XYZ 123 ya da XYZ"); self.assertEqual(self.s["degistirilmis"], {"il": "35", "sayfa": "/il/ankara"}); self.assertEqual(self.s["oneriSayfa"], "/il/ankara")      # kullanıcı Ankara sayfasından gelip İzmir'i seçti: il değişir, sayfa kalır

    def test_tarayicidan_giden_gövdeler_gercek_sunucu_dogrulayicisindan_gecer(self):
        gövdeler = self.s["plaka"]["istekler"] + self.s["oneri"]["istekler"]; self.assertEqual(len(gövdeler), 4)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f: json.dump(gövdeler, f, ensure_ascii=False)
        try:
            r = subprocess.run([u.NODE, "-e", "const C=require('./api/_geri-bildirim.js');const b=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));console.log(JSON.stringify(b.map(x=>C.dogrula(x))))", f.name], cwd=u.ROOT, capture_output=True, text=True, check=True)
        finally: os.unlink(f.name)
        sonuc = json.loads(r.stdout); self.assertEqual([x.get("hata") for x in sonuc], [None] * 4, sonuc)
        self.assertEqual([x["dosya"] for x in sonuc], ["plaka", "plaka", "plaka", "oneri"]); self.assertEqual(sonuc[0]["kayit"]["plaka"], "06 BYS 922"); self.assertEqual(sonuc[1]["kayit"]["plaka"], "34 ABC"); self.assertEqual(sonuc[2]["kayit"]["seri"], "AYT")
        self.assertEqual(sonuc[2]["kayit"]["no"], None); self.assertEqual(sonuc[3]["kayit"]["tur"], "hata")

if __name__ == "__main__": unittest.main()
