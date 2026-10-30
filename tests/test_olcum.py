"""GoatCounter analitik entegrasyonu: 82 sayfanın tamamı (ana sayfa + 81 il) tek paylaşılan assets/olcum.js ile kapsanır; ölçüm yalnızca plakatahmini.com'da çalışır
(yerel, Vercel önizleme, otomasyon ve kapatma anahtarında hiç ağ isteği yok); sayfa görüntüleme GoatCounter'ın standart count.js'iyle (çift sayım yok) ölçülür; özel olaylar
yalnızca sabit, anonim adlardır (plaka/arama metni gönderilmez); testler gerçek sayaçları artırmaz (sayfa tarafı denetim + tarayıcıda alan adı engeli)."""
import functools, glob, html, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL, ENGELLENEN_ALAN_ADLARI
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
def il_sayfalari(): return sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html")))
NOT = re.compile(r'<!--OLCUM--><p class="olcum-notu">(.*?)</p><!--/OLCUM-->|<p class="olcum-notu">(.*?)</p>', re.S)

class SayfaKapsami(unittest.TestCase):
    def test_82_sayfa_tek_paylasilan_betik_ve_dogrudan_kod_yok(self):
        sayfalar = il_sayfalari() + [os.path.join(u.ROOT, "index.html")]; self.assertEqual(len(sayfalar), 82)
        for yol in sayfalar:
            h = u.oku(yol); self.assertEqual(h.count('src="/assets/olcum.js"'), 1, yol)
            for yasak in ("gc.zgo.at", "data-goatcounter", "goatcounter.com/count", "goatcounter.count("): self.assertNotIn(yasak, h, f"{yol}: sayfada doğrudan analitik kodu olmamalı ({yasak}); yükleyici tek dosyadır")
        for yol in il_sayfalari():
            h = u.oku(yol); self.assertRegex(h, r'<!--OLCUM--><script src="/assets/olcum.js" defer></script><!--/OLCUM-->\n<script src="/assets/takvim.js" defer></script>')   # il: defer, diğer betiklerden önce
        self.assertRegex(ANA, r'<!--OLCUM--><script src="/assets/olcum.js"></script><!--/OLCUM-->\n<script src="/assets/ana-sayfa.js"></script>')

    def test_abacus_sayaci_uretim_kaynaklarindan_tamamen_kaldirildi(self):
        # Eski Abacus ziyaret sayacı (rozet, ziyaret/aktif süre vuruşları, 30 sn zamanlayıcı, gizli stat paneli) kaldırıldı; tek analitik GoatCounter'dır. Geçmiş yedekler (backups/) kapsam dışıdır.
        uretim = [os.path.join(u.ROOT, a) for a in ("index.html", "vercel.json", "robots.txt", "sitemap.xml", "generate_il_pages.py")] + il_sayfalari() + sorted(glob.glob(os.path.join(u.ROOT, "assets", "*")))
        self.assertGreaterEqual(len(uretim), 90)
        for yol in uretim:
            h = u.oku(yol).lower()
            for yasak in ("abacus", "jasoncameron", "sure30", "pt-sayildi", "stat-yg26", 'id="counter"', "counter-num"): self.assertNotIn(yasak, h, f"{yol}: kaldırılan sayaç kalıntısı: {yasak}")
        self.assertEqual(len(re.findall(r"\bfetch\(|\bXMLHttpRequest\b|sendBeacon", ANA)), 0, "ana sayfada sayfa kodundan doğrudan ağ isteği olmamalı (GoatCounter olcum.js üzerinden)")

    def test_gorunur_bilgilendirme_dogru_ve_dogrulanmamis_iddia_icermez(self):
        for yol in il_sayfalari() + [os.path.join(u.ROOT, "index.html")]:
            h = u.oku(yol); m = re.search(r'<p class="olcum-notu">(.*?)</p>', h, re.S); self.assertIsNotNone(m, yol); n = html.unescape(re.sub(r"<[^>]+>", "", m[1]))
            self.assertIn("GoatCounter", n); self.assertIn('href="https://www.goatcounter.com/privacy"', m[1]); self.assertIn("üçüncü taraf", n); self.assertIn("plaka", n); self.assertIn("gönderilmez", n)
            for yasak in ("çerez", "cookie", "KVKK", "GDPR", "tamamen anonim", "kişisel veri toplanmaz", "saklanmaz"): self.assertNotIn(yasak.lower(), n.lower(), f"{yol}: doğrulanmamış iddia: {yasak}")
            self.assertNotIn("abacus", n.lower(), yol)                                                    # başka üçüncü taraf sayaç yok: ana sayfa ve il sayfaları aynı notu taşır
        self.assertLess(ANA.index('class="olcum-notu"'), ANA.index("</main>"))

    def test_jsiz_gonderimde_plaka_adrese_girmez(self):
        for yol in il_sayfalari():
            h = u.oku(yol); self.assertNotIn('name="hedef"', h); self.assertNotIn('name="atla"', h)                 # yerel form yalnızca il kodunu (?il=NN) taşır
            self.assertEqual(re.findall(r'<form id="hedef-form"[^>]*>.*?</form>', h, re.S)[0].count("name="), 1)

@unittest.skipUnless(u.NODE, "node kurulu değil")
class UretimDisiAnalitikYok(unittest.TestCase):
    """olcum.js'in ağ davranışı, sahte tarayıcı ortamında (vm) denetlenir: hangi koşulda betik eklenir, hangi olay gönderilir."""
    def _calistir(self, host="plakatahmini.com", webdriver=False, kapali=False, iki_kez=False, olaylar=()):
        kod = r"""
const fs=require('fs'),vm=require('vm'); const a=JSON.parse(process.argv[1]); const eklenen=[], sayilan=[];
const el=()=>({attrs:{},setAttribute(k,v){this.attrs[k]=v}});
const ctx={console,document:{createElement:()=>el(),head:{appendChild:x=>eklenen.push(x)}},location:{hostname:a.host},navigator:{webdriver:a.webdriver},localStorage:{getItem:k=>(a.kapali&&k==='plaka-olcum')?'kapali':null}};
vm.createContext(ctx); const kaynak=fs.readFileSync('assets/olcum.js','utf8'); vm.runInContext(kaynak,ctx); if(a.ikiKez){ vm.runInContext('PlakaOlcum.baslat()',ctx); }
const sonuc=[]; ctx.goatcounter=undefined;
for(const o of a.olaylar){ ctx.__o=o; sonuc.push(vm.runInContext('PlakaOlcum.olay(__o)',ctx)); }
const once=eklenen.length?eklenen[0]:null;
let kuyrukOnce=0, yukluSonra=0;
if(once){ ctx.goatcounter={count:v=>sayilan.push(v)}; if(typeof once.onload==='function') once.onload(); }
if(once){ for(const o of a.olaylar){ ctx.__o=o; vm.runInContext('PlakaOlcum.olay(__o)',ctx); } }
console.log(JSON.stringify({eklenen:eklenen.map(e=>({src:e.src,async:e.async,dg:e.attrs['data-goatcounter']})),sonuc,sayilan,uygun:vm.runInContext('PlakaOlcum.uygun()',ctx),kayit:vm.runInContext('PlakaOlcum.kayit',ctx)}));
"""
        r = subprocess.run([u.NODE, "-e", kod, json.dumps({"host": host, "webdriver": webdriver, "kapali": kapali, "ikiKez": iki_kez, "olaylar": list(olaylar)})], cwd=u.ROOT, capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_yalnizca_uretim_alan_adinda_betik_eklenir(self):
        r = self._calistir(); self.assertEqual(r["eklenen"], [{"src": "https://gc.zgo.at/count.js", "async": True, "dg": "https://plakatahmini.goatcounter.com/count"}]); self.assertTrue(r["uygun"])
        for host in ("localhost", "127.0.0.1", "0.0.0.0", "192.168.1.5", "", "www.plakatahmini.com", "plaka-tahmini.vercel.app", "plaka-tahmini-git-main-guvenyenihayat-3218s-projects.vercel.app", "plaka-tahmini-abc123.vercel.app", "plakatahmini.com.evil.example", "evilplakatahmini.com", "PLAKATAHMINI.COM.tr"):
            r = self._calistir(host=host); self.assertEqual(r["eklenen"], [], host); self.assertFalse(r["uygun"], host)

    def test_otomasyon_ve_kapatma_anahtari_betik_eklemez(self):
        for kw in ({"webdriver": True}, {"kapali": True}): r = self._calistir(**kw); self.assertEqual(r["eklenen"], [], kw); self.assertFalse(r["uygun"])

    def test_tek_yukleme_cift_sayim_yok(self):
        r = self._calistir(iki_kez=True); self.assertEqual(len(r["eklenen"]), 1)                                      # baslat() ikinci kez çağrılsa da betik bir kez eklenir
        self.assertEqual([c for c in r["sayilan"] if not c.get("event")], [])                                         # sayfa görüntüleme burada sayılmaz: count.js kendisi sayar

    def test_olaylar_sabit_listeyle_sinirli_ve_uretim_disinda_gonderilmez(self):
        gecerli = ["il-hesapla-basla", "il-hesapla-sonuc", "il-hesapla-hata", "ana-hesapla-basla", "ana-hesapla-sonuc", "ana-hesapla-hata", "ana-il-ara", "ana-il-ara-hata", "ana-kart-tikla/istanbul"]
        gecersiz = ["", "plaka-BZZ-999", "il-hesapla-basla?q=BZZ999", "il-hesapla-basla BZZ", "ana-kart-tikla/34", "ana-kart-tikla/İstanbul", "ana-il-ara/konya", "hesapla", "il-hesapla-sonuc/42-BZZ", "ana-kart-tikla/"]
        r = self._calistir(host="localhost", olaylar=gecerli + gecersiz); self.assertEqual(r["sonuc"], [True] * len(gecerli) + [False] * len(gecersiz)); self.assertEqual(r["kayit"], gecerli); self.assertEqual(r["sayilan"], [])        # üretim dışı: kabul edilir ama hiçbir şey gönderilmez
        r = self._calistir(olaylar=gecerli + gecersiz)                                                                  # üretim: betik yüklenince kuyruk boşalır, ardından doğrudan gönderilir
        self.assertEqual(r["sonuc"], [True] * len(gecerli) + [False] * len(gecersiz)); self.assertEqual(len(r["sayilan"]), 2 * len(gecerli))
        for c in r["sayilan"]: self.assertEqual(set(c), {"path", "title", "event"}); self.assertTrue(c["event"]); self.assertEqual(c["path"], c["title"]); self.assertRegex(c["path"], r"^[a-z/-]+$")     # içerik/rakam yok

@unittest.skipUnless(CHROME, "Chrome yok")
class TarayicidaOlaylarVeEngel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sayfalar = ["/il/" + os.path.basename(p)[:-5] for p in il_sayfalari()] + ["/"]
        d = tempfile.mkdtemp(prefix="plaka_olcum_", dir=u.ROOT)
        try:
            with open(os.path.join(u.ROOT, "tests", "ui", "olcum_olaylar.html"), encoding="utf-8") as f: h = f.read()
            with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(h.replace("__SAYFALAR__", json.dumps(sayfalar)))
            class H(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k): pass
                def do_GET(self):
                    yol = self.path.split("?")[0]
                    if "." not in os.path.basename(yol) and os.path.isfile(os.path.join(u.ROOT, yol.lstrip("/") + ".html")): self.path = yol + ".html"
                    super().do_GET()
            s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); port = s_.getsockname()[1]; s_.close()
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
            try: r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=200000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=300)
            finally: srv.shutdown(); srv.server_close()
            m = re.search(r"SONUC (\{.*\})\s*</pre>", r.stdout, re.S); assert m, r.stderr[-400:]
            cls.sonuc = json.loads(html.unescape(m[1]))
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_test_tarayicisinda_analitik_ve_sayac_alan_adlari_engelli(self):
        self.assertEqual(self.sonuc["engel"], {"gc.zgo.at": "engelli", "goatcounter.com": "engelli", "abacus": "engelli"})
        for a in ENGELLENEN_ALAN_ADLARI: self.assertTrue(any(a in x for x in CHROME_TEMEL), a)

    def test_82_sayfa_olcum_yuklu_uretim_disinda_pasif(self):
        self.assertEqual(len(self.sonuc["sayfalar"]), 82)
        for x in self.sonuc["sayfalar"]:
            self.assertEqual((x["tur"], x["uygun"], x["gc"], x["gcNesne"], x["kayit"]), ("object", False, False, "undefined", 0), x["s"])       # yüklü, pasif, GoatCounter betiği/nesnesi yok

    def test_il_sayfasi_hesaplayici_olaylari(self):
        il = self.sonuc["il"]; b = "il-hesapla-basla"
        self.assertEqual(il["gecerli"], [b, "il-hesapla-sonuc"]); self.assertEqual(il["dislanan"], [b, "il-hesapla-sonuc"])
        for k in ("gecersiz", "bos", "baska", "kod", "yok"): self.assertEqual(il[k], [b, "il-hesapla-hata"], k)

    def test_ana_sayfa_hesaplayici_il_arama_ve_kart_olaylari(self):
        a = self.sonuc["ana"]; b = "ana-hesapla-basla"
        self.assertEqual(a["hesapla"], {"gecerli": [b, "ana-hesapla-sonuc"], "gecersiz": [b, "ana-hesapla-hata"], "enter": [b, "ana-hesapla-sonuc"], "enterHata": [b, "ana-hesapla-hata"]})
        self.assertEqual(a["araHata"], ["ana-il-ara-hata"]); self.assertEqual(a["araBos"], ["ana-il-ara-hata"]); self.assertEqual(a["araBasari"], ["ana-il-ara"])
        self.assertEqual(a["kartlar"], [["ana-kart-tikla/istanbul"], ["ana-kart-tikla/ankara"], ["ana-kart-tikla/izmir"]])

@unittest.skipUnless(CHROME and u.NODE, "Chrome/Node yok")
class JavascriptKapaliyken(unittest.TestCase):
    def test_sayfalar_jssiz_calisir_temel_icerik_ve_gezinme(self):
        urller = ["file://" + os.path.join(u.ROOT, "il", sl + ".html") for sl in ("konya", "istanbul", "kutahya")] + ["file://" + os.path.join(u.ROOT, "index.html")]
        r = subprocess.run([u.NODE, os.path.join(u.ROOT, "tests", "ui", "jssiz.js"), CHROME, *urller], capture_output=True, text=True, timeout=120); self.assertEqual(r.returncode, 0, r.stderr)
        for x in json.loads(r.stdout):
            self.assertNotIn("hata", x, x); self.assertIn("Plaka Sırası", x["h1"]); self.assertRegex(x["seri"], r"^\d\d [A-Z]{3} \d{3}$", x["url"]); self.assertTrue(x["gozlem"])        # JS kapalıyken statik HTML tam tahmini plakayı (3 haneli sıra) gösterir
            self.assertEqual(x["linkler"], 84 if x["url"].endswith("index.html") else 81, x["url"])         # il: 81 bağlantı; ana sayfa: 81 + 3 kart
            self.assertTrue(x["not"]); self.assertFalse(x["betikGC"]); self.assertEqual(x["olcum"], "undefined"); self.assertLessEqual(x["sw"], x["cw"])             # betik çalışmaz: GoatCounter yüklenmez, içerik ve il bağlantıları HTML'de
            if x["url"].endswith("index.html"): self.assertEqual(x["formAction"], "/")

if __name__ == "__main__": unittest.main()
