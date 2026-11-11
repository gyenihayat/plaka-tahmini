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
# Hata kategorileri (kapalı liste; README "Hesaplayıcı hata kategorileri"). Ana sayfada baska-il ve atla oluşmaz.
HEDEF_KAT = ["bos", "tek-harf", "iki-harf", "format", "karakter", "il-kodu", "baska-il", "atla", "hesaplama"]
ANA_KAT = [k for k in HEDEF_KAT if k not in ("baska-il", "atla")]
ARA_KAT = ["bos", "belirsiz", "bulunamadi", "celisik"]
BICIM = {"bos", "karakter", "tek-harf", "iki-harf", "format"}                  # "Seri okunamadı" yolunun biçim sınıfları
KATEGORI_OLAYLARI = {"il-hesapla-hata": {k: "il-hesapla-hata/" + k for k in HEDEF_KAT}, "ana-hesapla-hata": {k: "ana-hesapla-hata/" + k for k in ANA_KAT},
                     "ana-il-ara-hata": {k: "ana-il-ara-hata/" + k for k in ARA_KAT}}
KATEGORI_ADLARI = {v for t in KATEGORI_OLAYLARI.values() for v in t.values()}
TEMEL_OLAYLAR = {"il-hesapla-basla", "il-hesapla-sonuc", "il-hesapla-hata", "ana-hesapla-basla", "ana-hesapla-sonuc", "ana-hesapla-hata", "ana-il-ara", "ana-il-ara-hata"}
# Ana sayfa hesaplayıcısı (gerçek calcTarget) eşlik derlemi: [girdi, beklenen kategori | None = sonuç]
ESLIK = [["BZZ 999", None], ["06GGS761", None], ["ggs761", None], ["06-GGS-761", None], ["6 GGS 761", None], ["  06   ggs   761 ", None], ["ABC 12", None], ["34 RMP 940", None], ["06 GIS 123", None],
         ["", "bos"], ["   ", "bos"], ["H", "tek-harf"], ["06 h", "tek-harf"], ["ı", "tek-harf"], ["HA", "iki-harf"], ["06 AB 1234", "iki-harf"], ["ab1234", "iki-harf"], ["AB-123", "iki-harf"],
         ["06 A 1234", "format"], ["06 A 12345", "format"], ["ABC 1234", "format"], ["GGS 0761", "format"], ["TR 06 GGS 761", "format"], ["ankara", "format"], ["06", "format"], ["761", "format"],
         ["06 06 GGS", "format"], ["---", "format"], ["G harfi", "format"], ["ŞAA", "karakter"], ["06 GĞS", "karakter"], ["GİS 123", "karakter"], ["İAA", "karakter"], ["ÇA 12", "karakter"],
         ["IAA", "karakter"], ["ıaa", "karakter"], ["06 QAA", "karakter"], ["AAO 1", "karakter"], ["XYZ 1", "karakter"], ["82 AAA 100", "il-kodu"], ["00 AAA 1", "il-kodu"], ["99 QAA", "il-kodu"]]
TAKMA = {"Maraş": "kahramanmaras", "K.Maraş": "kahramanmaras", "Urfa": "sanliurfa", "Antep": "gaziantep", "İzmit": "kocaeli", "Adapazarı": "sakarya", "Antakya": "hatay", "İçel": "mersin",
         "MARAŞ": "kahramanmaras", "k. maras": "kahramanmaras", "urfa": "sanliurfa", "ICEL": "mersin", "adapazari": "sakarya", "Maraş 46": "kahramanmaras"}
def node_json(betik, veri):
    d = tempfile.mkdtemp(prefix="plaka_olcum_")
    try:
        yol = os.path.join(d, "s.json")
        with open(yol, "w", encoding="utf-8") as f: json.dump(veri, f, ensure_ascii=False)
        r = subprocess.run([u.NODE, os.path.join(u.ROOT, "tests", "ui", betik), yol], cwd=u.ROOT, capture_output=True, text=True, timeout=300); assert r.returncode == 0, r.stderr[-800:]
        return json.loads(r.stdout)
    finally: shutil.rmtree(d, ignore_errors=True)

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
        gecerli = ["il-hesapla-basla", "il-hesapla-sonuc", "il-hesapla-hata", "ana-hesapla-basla", "ana-hesapla-sonuc", "ana-hesapla-hata", "ana-il-ara", "ana-il-ara-hata", "ana-kart-tikla/istanbul"] + sorted(KATEGORI_ADLARI)
        gecersiz = ["", "plaka-BZZ-999", "il-hesapla-basla?q=BZZ999", "il-hesapla-basla BZZ", "ana-kart-tikla/34", "ana-kart-tikla/İstanbul", "ana-il-ara/konya", "hesapla", "il-hesapla-sonuc/42-BZZ", "ana-kart-tikla/",
                    "il-hesapla-hata/", "il-hesapla-hata/BOS", "il-hesapla-hata/bos/", "il-hesapla-hata//bos", "il-hesapla-hata/bos ", "il-hesapla-hata/yok", "il-hesapla-hata/42", "il-hesapla-hata/BZZ-999",
                    "ana-hesapla-hata/baska-il", "ana-hesapla-hata/atla", "ana-il-ara-hata/yok", "ana-il-ara-hata/konya", "ana-il-ara-hata/kahramanmaras", "il-hesapla-sonuc/bos", "il-hesapla-basla/bos",
                    "il-tarih-hata/bos", "ana-il-ara/bos", "il-hesapla-hata/tek_harf", "il-hesapla-hata/null", "null", "undefined"]
        r = self._calistir(host="localhost", olaylar=gecerli + gecersiz); self.assertEqual(r["sonuc"], [True] * len(gecerli) + [False] * len(gecersiz)); self.assertEqual(r["kayit"], gecerli); self.assertEqual(r["sayilan"], [])        # üretim dışı: kabul edilir ama hiçbir şey gönderilmez
        r = self._calistir(olaylar=gecerli + gecersiz)                                                                  # üretim: betik yüklenince kuyruk boşalır, ardından doğrudan gönderilir
        self.assertEqual(r["sonuc"], [True] * len(gecerli) + [False] * len(gecersiz))
        self.assertEqual([c["path"] for c in r["sayilan"]], gecerli[:20] + gecerli)                    # yükleme öncesi kuyruk en fazla 20 olay (mevcut sınır), sonra doğrudan gönderim
        for c in r["sayilan"]: self.assertEqual(set(c), {"path", "title", "event"}); self.assertTrue(c["event"]); self.assertEqual(c["path"], c["title"]); self.assertRegex(c["path"], r"^[a-z/-]+$")     # içerik/rakam yok

def olcum_js(ifade, veri=None):
    """olcum.js'i (üretim dışı: ağ yok) Node vm'de yükler ve ifadenin JSON değerini döndürür; __v = veri."""
    kod = ("const fs=require('fs'),vm=require('vm');const c={Math,Date,console,JSON};vm.createContext(c);vm.runInContext(fs.readFileSync('assets/olcum.js','utf8'),c);"
           "c.__v=JSON.parse(process.argv[1]);console.log(JSON.stringify(vm.runInContext(process.argv[2],c)));")
    r = subprocess.run([u.NODE, "-e", kod, json.dumps(veri, ensure_ascii=False), ifade], cwd=u.ROOT, capture_output=True, text=True); assert r.returncode == 0, r.stderr[-600:]
    return json.loads(r.stdout)

@unittest.skipUnless(u.NODE, "node kurulu değil")
class HataKategorileri(unittest.TestCase):
    """olcum.js: kapalı kategori listesi, sabit olay adı tablosu, gerçek doğrulama sırası (il sayfası aracıyla eşlik) ve gizlilik (girdiden bağımsız sabit adlar)."""
    ETIKET = [  # [il, girdi, atlanacak seriler, beklenen kategori]: doğrulama sırası = okunamadı(biçim) > il kodu > başka il > harf dizisi > atlanacak seriler
        ["konya", "", "", "bos"], ["konya", "   ", "", "bos"], ["konya", " ", "", "bos"], ["konya", "", "xyz!!", "bos"],
        ["konya", "B", "", "tek-harf"], ["konya", "42 b", "", "tek-harf"], ["konya", "ı", "", "tek-harf"],
        ["konya", "BZ", "", "iki-harf"], ["konya", "42 AB 1234", "", "iki-harf"], ["konya", "ab-123", "", "iki-harf"], ["konya", "00 AB 1", "", "iki-harf"],
        ["konya", "42 A 1234", "", "format"], ["konya", "ABC 1234", "", "format"], ["konya", "TR 42 BZZ 999", "", "format"], ["konya", "konya", "", "format"], ["konya", "42", "", "format"], ["konya", "---", "", "format"],
        ["konya", "ŞAA", "", "karakter"], ["konya", "BİZ 1", "", "karakter"], ["konya", "ÇA 12", "", "karakter"], ["konya", "IAA", "", "karakter"], ["konya", "BZQ", "", "karakter"], ["konya", "AAO 1", "", "karakter"], ["konya", "IAA", "xyz!!", "karakter"],
        ["konya", "99 AAA", "", "il-kodu"], ["konya", "0 AAA", "", "il-kodu"], ["konya", "99 QAA", "", "il-kodu"],
        ["konya", "06 GAA", "", "baska-il"], ["konya", "06 QAA", "", "baska-il"], ["konya", "06 GAA", "xyz!!", "baska-il"], ["ankara", "42 BZZ", "", "baska-il"],
        ["konya", "BZZ 999", "xyz!!", "atla"], ["konya", "42 BZZ 999", "AXX-ZXX", "atla"],
    ]
    @classmethod
    def setUpClass(cls):
        cls.c = node_json("hata_kategori_cikti.js", {"iller": ["konya", "ankara", "istanbul", "kilis", "sivas"], "etiketli": [x[:3] for x in cls.ETIKET], "fuzz": 20000, "tohum": 20261111})

    def test_kategori_tablosu_kapali_sabit_ve_izin_listesiyle_uyumlu(self):
        r = olcum_js("({t: PlakaOlcum.KATEGORI_OLAYLARI, donuk: Object.isFrozen(PlakaOlcum.KATEGORI_OLAYLARI) && Object.values(PlakaOlcum.KATEGORI_OLAYLARI).every(Object.isFrozen),"
                     " izin: Object.values(PlakaOlcum.KATEGORI_OLAYLARI).flatMap(Object.values).map(a => PlakaOlcum.IZINLI.test(a)),"
                     " bilinmeyen: __v.map(([t, k]) => PlakaOlcum.kategoriOlayi(t, k))})",
                     [["il-hesapla-hata", "yok"], ["il-hesapla-hata", "constructor"], ["constructor", "bos"], ["__proto__", "bos"], ["ana-hesapla-hata", "baska-il"], ["ana-hesapla-hata", "atla"],
                      ["ana-il-ara-hata", "yok"], ["il-hesapla-sonuc", "bos"], ["il-hesapla-hata", "BOS"], ["il-hesapla-hata", None], ["il-hesapla-hata", "06 AB 1234"]])
        self.assertEqual(r["t"], KATEGORI_OLAYLARI); self.assertTrue(r["donuk"]); self.assertTrue(all(r["izin"])); self.assertEqual(r["bilinmeyen"], [None] * 11)

    def test_giris_bicimi_siniflari(self):
        bek = {"": "bos", " \t ": "bos", "H": "tek-harf", "h": "tek-harf", "06 H": "tek-harf", "06H": "tek-harf", "HA": "iki-harf", "06 AB": "iki-harf", "06 AB 1234": "iki-harf", "06AB1234": "iki-harf",
               "06 A 1234": "format", "A 12": "format", "ABCD": "format", "ABC 1234": "format", "GG S": "format", "06": "format", "761": "format", "06 761": "format", "TR 06 GGS 761": "format",
               "G harfi": "format", "?!": "format", "ŞA": "karakter", "06 AB 1234 ş": "karakter", "ＡＢＣ": "karakter", "GİS": "karakter", "😀": "karakter", "06 AB 1234": "iki-harf"}
        r = olcum_js("__v.map(PlakaOlcum.girisBicimi)", list(bek)); self.assertEqual(dict(zip(bek, r)), bek)

    def test_il_sayfasi_hata_yollari_dogru_kategoride(self):
        for (sl, g, a, k), o in zip(self.ETIKET, self.c["etiketli"]):
            self.assertIn(o["tip"], ("hata", "baska_il"), (sl, g, a)); self.assertEqual(o["kat"], k, (sl, g, a, o["mesaj"]))

    def test_il_sayfasi_araciyla_eslik_her_hata_tek_kategori(self):
        e = self.c["eslik"]; self.assertGreater(e["deneme"], 60000); self.assertEqual((e["uyumsuzSayi"], e["uyumsuz"]), (0, []))
        for k in HEDEF_KAT: self.assertGreater(e["sayac"].get(k, 0), 0, f"{k} yolu derlemde sınanmadı")        # "hesaplama": hiçbir doğrulama hatası bulunmayan geçerli girdiler (hata olarak sayılmazlar)

    def test_gizlilik_rastgele_girdide_yalnizca_sabit_adlar(self):
        f = self.c["fuzz"]; self.assertTrue(set(f["kategoriler"]) <= set(HEDEF_KAT)); self.assertTrue(set(f["olaylar"]) <= KATEGORI_ADLARI, f["olaylar"])
        self.assertGreaterEqual(len(f["kategoriler"]), 6)
        for a in f["olaylar"]: self.assertRegex(a, r"^[a-z]+(?:-[a-z]+)*/[a-z]+(?:-[a-z]+)*$")

@unittest.skipUnless(u.NODE, "node kurulu değil")
class GoatCounterMockOlaylari(unittest.TestCase):
    """count.js yerine sahte goatcounter.count (tests/ui/olcum_mock.js): olcum.js üretim koşulunda çalışırken gerçek sayfa kodunun gönderdiği olaylar. Ağ isteği yoktur."""
    IL = [("BZZ 999", "", False, None), ("", "", False, "bos"), ("   ", "", False, "bos"), ("B", "", False, "tek-harf"), ("42 AB 1234", "", False, "iki-harf"), ("ABC 1234", "", False, "format"),
          ("ŞAA", "", False, "karakter"), ("IAA", "", False, "karakter"), ("99 AAA", "", False, "il-kodu"), ("06 GAA", "", False, "baska-il"), ("BZZ 999", "SXY", False, "atla"),
          ("BZZ 999", "BXX", False, None), ("BZZ 999", "", True, "hesaplama"), ("AAA 001", "", False, None), ("42 BZZ 999", "", False, None)]
    ARA = [("Konya", None, "/il/konya"), ("Maraş", None, "/il/kahramanmaras"), ("Urfa", None, "/il/sanliurfa"), ("", "bos", None), ("   ", "bos", None), ("k", "belirsiz", None),
           ("82", "bulunamadi", None), ("xyz", "bulunamadi", None), ("Mara", "bulunamadi", None), ("konya 06", "celisik", None), ("Maraş 27", "celisik", None)]
    HEDEF = [("BZZ 999", False, False, None), ("BZZ 999", False, True, None), ("", True, False, "bos"), ("06 AB 1234", True, True, "iki-harf"), ("S", True, False, "tek-harf"), ("ABC 1234", True, False, "format"),
             ("ŞAA", True, False, "karakter"), ("IAA", True, False, "karakter"), ("99 AAA", True, False, "il-kodu"), ("BZZ 999", True, False, "hesaplama"), ("06 GAA", False, False, None)]
    @classmethod
    def setUpClass(cls):
        cls.il, cls.ana = node_json("olcum_mock.js", [
            {"sayfa": "il", "il": "konya", "adimlar": [{"tur": "hedef", "deger": g, "atla": a, "bozuk": b} for g, a, b, _ in cls.IL]},
            {"sayfa": "ana", "adimlar": [{"tur": "ara", "deger": g} for g, _, _ in cls.ARA] + [{"tur": "hedef", "deger": g, "gizli": z, "enter": e} for g, z, e, _ in cls.HEDEF]}])

    def _yuk_denetimi(self, adimlar):
        for a in adimlar:
            kat = [c["path"] for c in a["cagrilar"] if "/" in c["path"]]; self.assertLessEqual(len(kat), 1)                  # bir işlem en fazla bir kategori olayı
            for c in a["cagrilar"]:
                self.assertEqual(set(c), {"path", "title", "event"}); self.assertIs(c["event"], True); self.assertEqual(c["path"], c["title"])
                self.assertIn(c["path"], TEMEL_OLAYLAR | KATEGORI_ADLARI); self.assertNotRegex(c["path"], r"\d")

    def test_il_sayfasi_olay_dizileri(self):
        self.assertEqual(len(self.il), len(self.IL)); self._yuk_denetimi(self.il)
        for (g, a, b, k), r in zip(self.IL, self.il):
            yollar = [c["path"] for c in r["cagrilar"]]
            self.assertEqual(yollar, ["il-hesapla-basla", "il-hesapla-sonuc"] if k is None else ["il-hesapla-basla", "il-hesapla-hata", "il-hesapla-hata/" + k], (g, a, b))
        hatali = sum(1 for x in self.IL if x[3]); self.assertEqual(sum(1 for r in self.il for c in r["cagrilar"] if c["path"] == "il-hesapla-hata"), hatali)    # toplam hata olayı: eskisi gibi başarısız işlem başına bir

    def test_ana_sayfa_il_aramasi_ve_hesaplayici_olay_dizileri(self):
        self.assertEqual(len(self.ana), len(self.ARA) + len(self.HEDEF)); self._yuk_denetimi(self.ana)
        for (g, k, yol), r in zip(self.ARA, self.ana[:len(self.ARA)]):
            yollar = [c["path"] for c in r["cagrilar"]]
            if k is None: self.assertEqual((yollar, r["gidilen"]), (["ana-il-ara"], [yol]), g)
            else: self.assertEqual((yollar, r["gidilen"]), (["ana-il-ara-hata", "ana-il-ara-hata/" + k], []), g)
        for (g, z, e, k), r in zip(self.HEDEF, self.ana[len(self.ARA):]):
            yollar = [c["path"] for c in r["cagrilar"]]
            self.assertEqual(yollar, ["ana-hesapla-basla", "ana-hesapla-sonuc"] if k is None else ["ana-hesapla-basla", "ana-hesapla-hata", "ana-hesapla-hata/" + k], (g, z, e))

@unittest.skipUnless(CHROME, "Chrome yok")
class TarayicidaOlaylarVeEngel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sayfalar = ["/il/" + os.path.basename(p)[:-5] for p in il_sayfalari()] + ["/"]
        d = tempfile.mkdtemp(prefix="plaka_olcum_", dir=u.ROOT)
        try:
            with open(os.path.join(u.ROOT, "tests", "ui", "olcum_olaylar.html"), encoding="utf-8") as f: h = f.read()
            h = h.replace("__ESLIK__", json.dumps([x[0] for x in ESLIK], ensure_ascii=False)).replace("__TAKMA__", json.dumps(list(TAKMA), ensure_ascii=False))
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
        il = self.sonuc["il"]; b = "il-hesapla-basla"; h = "il-hesapla-hata"
        self.assertEqual(il["gecerli"], [b, "il-hesapla-sonuc"]); self.assertEqual(il["dislanan"], [b, "il-hesapla-sonuc"])
        bek = {"gecersiz": "karakter", "bos": "bos", "baska": "baska-il", "kod": "il-kodu", "yok": "atla", "tek": "tek-harf", "iki": "iki-harf", "format": "format", "karakterTR": "karakter", "bosluk": "bos"}
        for k, kat in bek.items(): self.assertEqual(il[k], [b, h, h + "/" + kat], k)            # mevcut toplam hata olayı korunur + tek kategori
        self.assertIn("Seri okunamadı", il["metin"])                                                 # görünür hata mesajı değişmedi

    def test_ana_sayfa_hesaplayici_il_arama_ve_kart_olaylari(self):
        a = self.sonuc["ana"]; b = "ana-hesapla-basla"; h = "ana-hesapla-hata"; s = [b, "ana-hesapla-sonuc"]
        self.assertEqual(a["hesapla"], {"gecerli": s, "gecersiz": [b, h, h + "/karakter"], "enter": s, "enterHata": [b, h, h + "/karakter"], "bos": [b, h, h + "/bos"], "tek": [b, h, h + "/tek-harf"],
                                        "iki": [b, h, h + "/iki-harf"], "format": [b, h, h + "/format"], "karakterTR": [b, h, h + "/karakter"], "ilKodu": [b, h, h + "/il-kodu"], "digerIl": s})   # ana sayfada başka il kodu ili değiştirir
        ah = "ana-il-ara-hata"
        self.assertEqual({k: a[k] for k in ("araHata", "araBos", "araBosluk", "araYok", "araAnlamsiz", "araCelisik", "araBasari")},
                         {"araHata": [ah, ah + "/belirsiz"], "araBos": [ah, ah + "/bos"], "araBosluk": [ah, ah + "/bos"], "araYok": [ah, ah + "/bulunamadi"], "araAnlamsiz": [ah, ah + "/bulunamadi"],
                          "araCelisik": [ah, ah + "/celisik"], "araBasari": ["ana-il-ara"]})
        self.assertIn("plaka kodu 42", a["araMesaj"])                                                   # görünür mesaj değişmedi
        self.assertEqual(a["kartlar"], [["ana-kart-tikla/istanbul"], ["ana-kart-tikla/ankara"], ["ana-kart-tikla/izmir"]])

    def test_ana_sayfa_gercek_calctarget_ile_kategori_esligi(self):
        b = "ana-hesapla-basla"; h = "ana-hesapla-hata"; e = self.sonuc["ana"]["eslik"]; self.assertEqual([x["v"] for x in e], [x[0] for x in ESLIK])
        for x, (_, kat) in zip(e, ESLIK):
            if kat is None: self.assertEqual((x["gizli"], x["ol"]), (False, [b, "ana-hesapla-sonuc"]), x); continue
            self.assertTrue(x["gizli"], x); self.assertEqual(x["ol"], [b, h, h + "/" + kat], x)
            w = x["warn"]                                                                                   # kategori, calcTarget'ın gösterdiği uyarıyla tutarlı
            if w.startswith("Seri okunamadı"): self.assertIn(kat, BICIM, x)
            elif w.startswith("Geçersiz il kodu"): self.assertEqual(kat, "il-kodu", x)
            elif "plakalarda kullanılmıyor" in w: self.assertEqual(kat, "karakter", x)
            else: self.fail(x)

    def test_alternatif_il_adlari_tarayicida_dogru_sayfaya(self):
        t = self.sonuc["ana"]["takma"]; self.assertEqual(set(t), set(TAKMA))
        for g, sl in TAKMA.items(): self.assertEqual((t[g]["yol"], t[g]["ol"]), ("/il/" + sl, ["ana-il-ara"]), g)

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
