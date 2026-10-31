"""Ana sayfa ve 81 il sayfasındaki "Belirli bir tarihte hangi plakada?" aracı: ortak işaretleme/kod, ana sayfada sade ve bağımsız il seçimi, il sayfasında yalnızca tarih;
aynı il ve tarih için tam plaka eşliği (ana sayfa = il sayfası = üretimden bağımsız Python hesabı), elle seçilen hafta sonu/tatil tarihinin önceki iş gününe ÇEKİLMEMESİ,
ikincil "81 il" tablosu (varsayılan kapalı), atlanacak seriler, hedef plaka aracıyla karşılıklı bağımsızlık, gerçek klavye ve hata mesajları, analitik olay adları
(kullanıcı girdisi taşınmaz) ve 5 genişlikte taşma. Chrome testleri CHROME_TEMEL gibi analitik adlarını çözemeyen bir tarayıcıyla çalışır."""
import datetime as dt, glob, json, math, os, re, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
from test_il_sayfasi import veri, sayfa, slug, TAM, E0, tahmin_plaka, yuvarla, A1, A2, A3
from test_ana_sayfa_regresyon import CHROME
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
BASLIK = "Belirli bir tarihte hangi plakada?"
ACIKLAMA_ANA = "İl ve tarih seçerek o günün tahmini plakasını öğrenin."
ACIKLAMA_IL = "Seçtiğiniz tarihte bu ilde hangi plakanın verilmesinin beklendiğini öğrenin."
# geçmiş (veri öncesi, veri içi, son gözlem), bugün/Cuma, Cumartesi, Pazar, Pazartesi, resmî tatil (29 Ekim, 1 Ocak, Kurban), yakın/uzak gelecek
TARIHLER = ["2018-01-31", "2018-02-01", "2019-06-01", "2020-06-01", "2022-06-01", "2023-06-01", "2024-02-09", "2025-06-15", "2026-10-23", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2027-01-01", "2027-05-17", "2028-07-01", "2032-01-01", "2060-01-01"]
SINIR_ISO = "2018-02-01"      # yeni merkezî üç harf–üç rakam plaka düzeninin başlangıcı: bundan önce tahmin yok

def bolum(h, kimlik): return re.search(rf'<section class="arac tarih-arac" id="{kimlik}".*?</section>', h, re.S)[0]
def _med(a): return fc.med(a)
REFERANSLAR = {r["kod"]: r for r in json.load(open(os.path.join(u.ROOT, "data", "tarihsel_referanslar.json"), encoding="utf-8"))["referanslar"]}    # gözlem verisinden AYRI dosya
def _geri_ham(o, h):
    """Kalibresiz geriye model (forecast.py yardımcılarıyla): ilerleme(h) = 0,5·hız0·h + 0,5·mevsimsel; hız0 = ilk 365 günün aralık hızlarının medyanı."""
    F, n0 = o[0]; c = fc.clean(o); r = [(o[i][1] - o[i-1][1]) / (o[i][0] - o[i-1][0]) for i in range(1, len(o)) if o[i][0] <= F + 365 and o[i][0] > o[i-1][0]]
    rate0 = max(_med(r) if r else 0, 0.01); Y = fc.at(c, F + 365) - fc.at(c, F); k = h // 365; rem = h - 365 * k
    return 0.5 * rate0 * h + 0.5 * (k * Y + fc.at(c, F + 365) - fc.at(c, F + 365 - rem))
def _tarih_n(plaka):
    kod, harf, no = plaka.split(); return ((A1.index(harf[0]) * 23 + A2.index(harf[1])) * 21 + A3.index(harf[2])) * 1000 + int(no)
def kalibre_katsayilar(kod, o):
    r = REFERANSLAR.get(kod)
    if not r: return None
    F, n0 = o[0]; H = F - (dt.date.fromisoformat(r["tarih"]) - E0).days; nR = _tarih_n(r["plaka"]); return {"H": H, "nR": nR, "kappa": (n0 - nR) / _geri_ham(o, H), "taban": 2 * r["tarih_belirsizligi_gun"]}
def geri_ilerleme(o, h, kod=None):
    """Geriye ilerleme (sıra). Referanssız il: kalibresiz model. Referanslı il (Ankara): A(h) = g(h)·(1 − (1 − κ)·h/H), h ≤ H; sonrası referans sonrası ilk yıl ortalama hızıyla doğrusal."""
    k = kalibre_katsayilar(kod, o)
    if not k: return _geri_ham(o, h)
    A = lambda x: _geri_ham(o, x) * (1 - (1 - k["kappa"]) * x / k["H"])
    return A(h) if h <= k["H"] else A(k["H"]) + (A(k["H"]) - A(k["H"] - 365)) / 365 * (h - k["H"])
def geri_n(o, h, kod=None): return o[0][1] - geri_ilerleme(o, h, kod)
def geri_hata(o, h, kod):
    """Kalibre belirsizlik (gün): ilk gözlem yakını ±%25.. (min 10), referans yakını en az 2×tarih belirsizliği + payı; referans ötesi: taban + pay."""
    k = kalibre_katsayilar(kod, o); oran = lambda d: min(0.5, 0.25 + 0.05 * max(0, d - 365) / 365); eR = lambda d: k["taban"] + round(oran(d) * d)
    return eR(h - k["H"]) if h > k["H"] else min(max(10, round(oran(h) * h)), eR(k["H"] - h))
def beklenen_plaka(s, iso):
    """Dönüş: plaka metni | "SINIR" (1 Şubat 2018 öncesi) | "MODEL" (geriye model geçerli plaka üretemiyor: sıra < 1) | None (ileride seri alfabesi bitiyor)."""
    o = [tuple(x) for x in s["obs"]]; gun = (dt.date.fromisoformat(iso) - E0).days; g, n = o[-1]
    if iso < SINIR_ISO: return "SINIR"
    if gun > g: ham = n + fc.advance(o, fc.clean(o), g, gun - g, fc.slope(o, g))
    elif gun < o[0][0]:
        ham = geri_n(o, o[0][0] - gun, s["kod"])
        if yuvarla(ham) < 1: return "MODEL"
    else:
        i = next(i for i in range(1, len(o)) if o[i][0] >= gun) if gun > o[0][0] else 1; lo, hi = o[i - 1], o[i]; ham = lo[1] + ((gun - lo[0]) / (hi[0] - lo[0]) if hi[0] != lo[0] else 0) * (hi[1] - lo[1])
    if yuvarla(ham) // 1000 >= 21 * 23 * 21: return None                                    # seri alfabesi biter (A1×A2×A3): araç hata verir, plaka uydurmaz
    return tahmin_plaka(s["kod"], ham)

class Statik(unittest.TestCase):
    def test_81_il_sayfasinda_tarih_araci_var_il_secimi_yok(self):
        n = 0
        for s in veri():
            h = sayfa(s["il"]); b = bolum(h, "tarih"); n += 1
            self.assertIn(f'<h2 id="tarih-baslik">{BASLIK}</h2>', b); self.assertIn(f'<p class="ipucu">{ACIKLAMA_IL}</p>', b)
            self.assertEqual(b.count('type="date"'), 1); self.assertNotIn("<select", b); self.assertNotIn('id="tarih-il"', b); self.assertNotIn("<select", h)                          # il seçimi yok: sayfanın kendi ili
            self.assertIn('<button type="submit" class="t-btn" id="btn-tarih">Tahmini plakayı göster</button>', b); self.assertIn('<label for="dt">Tarih</label>', b)
            self.assertIn('<div class="t-sonuc" id="tarih-sonuc" aria-live="polite" hidden><p class="t-plaka mono" id="plate-num"></p>', b)             # hesaplamadan önce yanıltıcı örnek plaka yok
            self.assertRegex(b, r'<details class="gelismis" id="tarih-gelismis"><summary>Atlanacak seriler \(bu tarih tahmini için\)</summary><label for="excl">'); self.assertNotIn('id="tarih-gelismis" open', b)   # ana sayfayla aynı seçenek, varsayılan kapalı
            self.assertIn("Boş bırakırsanız hiçbir seri atlanmaz.", b); self.assertIn('id="excl" placeholder="örn. SXX, TXX"', b); self.assertIn('id="tarih-atla-bilgi" hidden', b)    # varsayılan: hiçbir seri atlanmaz, bilgi satırı gizli
            self.assertIn('id="tarih-govde" hidden', b); self.assertIn("<noscript>", b); self.assertIn('role="alert"', b)
            self.assertLess(h.index('id="hesapla"'), h.index('id="tarih"'))                                                                              # hedef plaka aracının hemen altında
            self.assertLess(h.index('id="sonuc"'), h.index('id="tarih"')); self.assertEqual(h.count(BASLIK), 1)
            self.assertIn('id="hedef-form"', h); self.assertRegex(h, r'class="buyuk mono" data-live="plaka">\d\d [A-Z]{3} \d{3}<')                                 # mevcut hedef aracı ve güncel tahmin korunur
        self.assertEqual(n, 81)

    def test_ana_sayfa_tarih_araci_yenilendi_ve_sade(self):
        b = bolum(ANA, "tarih")
        self.assertIn(f'<h2 id="tarih-baslik">{BASLIK}</h2>', b); self.assertIn(f'<p class="ipucu">{ACIKLAMA_ANA}</p>', b)
        self.assertIn('<label for="tarih-il">İl</label><select id="tarih-il"></select>', b); self.assertIn('<label for="dt">Tarih</label><input type="date" id="dt">', b)
        self.assertIn('id="btn-tarih">Tahmini plakayı göster</button>', b); self.assertIn("hidden><p class=\"t-plaka mono\" id=\"plate-num\"></p>", b)                  # sonuç başta gizli ve boş
        for eski in ("btn-today", 'id="plate"', 'id="pop"', "btn-last", 'id="meta"', "Belirli bir tarihte hangi seride?", ">Bugün<", "Tüm illeri göster"): self.assertNotIn(eski, ANA, eski)
        self.assertIn('<button type="button" class="t-ikincil" id="btn-all" aria-expanded="false" aria-controls="all-wrap">81 ilin bu tarihteki tahminlerini göster</button>', b)
        self.assertIn('<div class="tblwrap" id="all-wrap" hidden>', b)                                                                                              # tablo varsayılan kapalı
        self.assertRegex(b, r'<details class="gelismis" id="tarih-gelismis"><summary>Atlanacak seriler \(bu tarih tahmini için\)</summary>'); self.assertNotIn("<details class=\"gelismis\" id=\"tarih-gelismis\" open", b)
        self.assertEqual(b.count("<button"), 2)                                                                                                                   # yalnızca hesapla + ikincil eylem
        # iki işlev ayrı ve bulunabilir: hedef plaka aracı (Plakam ne zaman çıkar?) ve tarih aracı iki ayrı bölüm; biri diğerinin içinde değil
        self.assertLess(ANA.index('id="hesapla"'), ANA.index('id="tarih"')); self.assertEqual(len(re.findall(r'<section class="arac', ANA)), 2); self.assertIn("<h2 id=\"arac-baslik\">Plakam ne zaman çıkar?</h2>", ANA)
        for korunan in ('data-il="İstanbul"', 'data-il="Ankara"', 'data-il="İzmir"', 'id="il-form"', 'id="il-ara"', 'id="btn-target"', 'id="btn-81"', 'id="excl2"'): self.assertIn(korunan, ANA, korunan)   # kartlar, il arama, hedef aracı

    def test_ortak_isaretleme_ve_css(self):
        ana, il = bolum(ANA, "tarih"), bolum(sayfa("Konya"), "tarih")
        ana_idler, il_idler = set(re.findall(r'id="([\w-]+)"', ana)), set(re.findall(r'id="([\w-]+)"', il))
        self.assertEqual(il_idler - ana_idler, set())                                                                             # il sayfasının her kimliği ana sayfada da aynı
        self.assertEqual(ana_idler - il_idler, {"tarih-il", "btn-all", "all-wrap", "all-tbl"})                                    # farklar yalnızca ana sayfaya özgü il seçimi ve ikincil "81 il" tablosu; atlanacak seri alanı (#excl) iki sayfada AYNI
        for sinif in (".t-btn{", ".t-sonuc{", ".t-plaka{", ".t-etiket{", ".t-alanlar{"):
            self.assertIn(sinif, ANA); self.assertIn(sinif, sayfa("Konya"))                                                         # aynı CSS (ortak kaynak) iki sayfada

    def test_baa_aab_baslangic_serisi_kaynaklarda_ve_sayfalarda_kullanilmaz(self):
        # ARTES'teki BAA/AAB başlangıç grupları gerçek tarihsel başlangıç / zorunlu alt seri sınırı olarak KULLANILMAZ (kod, uyarı metni, sayfa); "BAA-BCZ" yalnızca atlanacak seri giriş örneğidir
        kod = [os.path.join(u.ROOT, "assets", f) for f in ("tahmin-motoru.js", "tarih-sorgu.js", "ana-sayfa.js", "il-arac.js", "tarihsel-referanslar.js")] + [os.path.join(u.ROOT, "index.html"), os.path.join(u.ROOT, "generate_il_pages.py")]
        for yol in kod:                                                                                       # kod ve ana sayfa: BAA/AAB belirteci hiç yok
            h = u.oku(yol).replace("BAA-BCZ", ""); self.assertNotRegex(h, r"\b(?:BAA|AAB)\b", os.path.basename(yol)); self.assertNotIn("baslangicSeri", h)
        for yol in kod + sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))):                            # ana sayfa ve 81 il sayfası: yanıltıcı başlangıç ifadeleri yok (il tablolarındaki "01 BAA 030" gibi GERÇEK gözlem plakaları serbest)
            h = u.oku(yol)
            for yasak in ("başlangıç serisinden", "düzeninin başladığı", "yeni düzen", "ARTES"): self.assertNotIn(yasak, h, f"{os.path.basename(yol)}: {yasak}")
        arac = u.oku(os.path.join(u.ROOT, "assets", "tarih-sorgu.js")); motor = u.oku(os.path.join(u.ROOT, "assets", "tahmin-motoru.js"))
        self.assertIn("üç harf–üç rakam plakaların dağıtımının başladığı gün anlamına gelmez", arac)                                    # 1 Şubat 2018: yalnızca MODEL tarih sınırı olarak açıklanır
        self.assertIn("Bu, modelin uyguladığı bir sınırdır; plakanın o tarihte verilmediği anlamına gelmez.", motor); self.assertNotIn("düzeninin başladığı", motor)
        self.assertEqual(re.findall(r'GERI_SINIR_ISO = "([\d-]+)"', motor), ["2018-02-01"])                                                  # genel tarih alt sınırı korunur

    def test_dogrulanmamis_notlar_ayri_dosyada_ve_hesapta_kullanilmaz(self):
        v = json.load(open(os.path.join(u.ROOT, "data", "tarihsel_referanslar.json"), encoding="utf-8")); notlar = v["dogrulanmamis_degerlendirme_notlari"]["notlar"]
        self.assertEqual([n["konu"] for n in notlar], ["Ankara 06 AFC", "Ankara 2019 belediye araç listesi", "ARTES BAA/AAB başlangıç grupları"]); self.assertTrue(all(n["durum"] == "doğrulanmamış" and n["hesapta_kullanilir"] is False for n in notlar))
        self.assertIn("2019 baharı olabilir", notlar[0]["metin"]); self.assertIn("kesin değil", notlar[0]["metin"]); self.assertIn("AEA, AFM ve AFP", notlar[1]["metin"]); self.assertIn("MUTLAK tarihsel başlangıcı olmadığını", notlar[2]["metin"]); self.assertEqual(len(notlar[2]["kaynaklar"]), 3)
        self.assertIn("MODELLEME VARSAYIMIDIR", v["referanslar"][0]["tarih_belirsizligi_aciklama"]); self.assertEqual(v["referanslar"][0]["tarih_belirsizligi_gun"], 30)                       # ±30 gün: açıkça modelleme varsayımı
        asset = u.oku(os.path.join(u.ROOT, "assets", "tarihsel-referanslar.js")); gozlem = u.oku(os.path.join(u.ROOT, "data", "tahmin_data.json"))
        for dosya in (asset, u.oku(os.path.join(u.ROOT, "assets", "tahmin-motoru.js")), u.oku(os.path.join(u.ROOT, "assets", "tarih-sorgu.js"))):
            for yasak in ("AFC", "AEA", "AFM", "AFP", "belediye", "tanıdık", "ARTES"): self.assertNotIn(yasak, dosya, yasak)                                                    # notlar JS'e/hesaba hiç girmez
        self.assertNotIn("AFC", gozlem); self.assertEqual(json.loads(asset[asset.index("{"):asset.rindex("}") + 1].replace("PlakaReferanslar = ", ""))["6"][0]["plaka"], "06 BYS 922")       # gözlem verisi değişmedi; kalibrasyon girdisi yalnızca BYS 922

    def test_tek_hesaplama_mantigi(self):
        arac = u.oku(os.path.join(u.ROOT, "assets", "tarih-sorgu.js"))
        for f in ("ana-sayfa.js", "il-arac.js"): self.assertNotIn("estimateAt(", u.oku(os.path.join(u.ROOT, "assets", f)), f"{f}: tarih hesabı yeniden yazılmamalı")
        for yasak in ("function fit(", "function reachDate(", "function advAt(", "Math.round(x"): self.assertNotIn(yasak, arac)
        self.assertIn("estimateAt(", arac); self.assertIn("PlakaTarih.kur(", u.oku(os.path.join(u.ROOT, "assets", "il-arac.js"))); self.assertIn("PlakaTarih.kur(", u.oku(os.path.join(u.ROOT, "assets", "ana-sayfa.js")))
        self.assertNotIn("PlakaTakvim", arac); self.assertNotIn("onceki", arac.lower().replace("önceki", ""))                      # elle seçilen tarih iş gününe çekilmez (takvim/önceki iş günü kullanılmaz)

    def test_analitige_yalnizca_sabit_olay_adlari_gider(self):
        arac = u.oku(os.path.join(u.ROOT, "assets", "tarih-sorgu.js"))
        self.assertEqual(sorted(set(re.findall(r'olay\("(\w+)"\)', arac))), ["hata", "hesapla", "sonuc"])                           # yalnızca üç sabit sonek; değişken/girdi geçmez
        self.assertEqual(re.findall(r'o\.olay\(([^)]*)\)', arac), ['o.onek + "-tarih-" + ek'])
        izinli = u.oku(os.path.join(u.ROOT, "assets", "olcum.js"))
        # JS: izinli liste yeni adları kabul eder, girdi taşıyan adları reddeder
        r = json.loads(subprocess.run([u.NODE, "-e", r"""const m=require('fs').readFileSync(process.argv[1]+'/assets/olcum.js','utf8').match(/IZINLI = (\/.*\/);/)[1], re=eval(m);
console.log(JSON.stringify(['ana-tarih-hesapla','ana-tarih-sonuc','ana-tarih-hata','il-tarih-hesapla','il-tarih-sonuc','il-tarih-hata','ana-tarih-2027-03-01','il-tarih-hesapla/42','ana-tarih-06GMB628','tarih-hesapla'].map(a=>re.test(a))))""", u.ROOT], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(r, [True] * 6 + [False] * 4)

@unittest.skipUnless(CHROME and u.NODE, "Chrome/Node yok")
class Tarayici(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_il_yerlesim import sunucu
        srv, port = sunucu(); iller = [[s["il"], slug(TAM.get(s["il"], s["il"]))] for s in veri()]
        try:
            r = subprocess.run([u.NODE, os.path.join(u.ROOT, "tests", "ui", "tarih_araci.js"), CHROME, f"http://127.0.0.1:{port}", json.dumps(iller, ensure_ascii=False), json.dumps(TARIHLER)], capture_output=True, text=True, timeout=600)
        finally: srv.shutdown(); srv.server_close()
        assert r.returncode == 0, r.stderr[-500:]
        cls.s = json.loads(r.stdout); cls.iller = {x["il"]: x for x in veri()}

    def test_calisti_ve_hata_yok(self): self.assertEqual(self.s["hatalar"], [], self.s["hatalar"])

    def test_ana_sayfa_ile_il_sayfasi_81_il_x_tarih_tam_plaka_birebir_ve_python_ile_ayni(self):
        e = self.s["esdeger"]; self.assertEqual((len(e["ana"]), len(e["il"])), (81, 81)); sayi = sifirli = sinir = model = alfabe = geri = 0
        for il, s in self.iller.items():
            ilk = tahmin_plaka(s["kod"], s["obs"][0][1])
            for iso in TARIHLER:
                a, i = e["ana"][il][iso], e["il"][il][iso]; kim = (il, iso); beklenen = beklenen_plaka(s, iso)
                self.assertEqual(a, i, kim)                                                                                         # plaka, etiket, ±gün, uyarı, hata: ana sayfa = il sayfası (birebir)
                if beklenen == "SINIR":                                                                                             # 1 Şubat 2018 öncesi: tahmin yok
                    self.assertTrue(a["gizli"] and "1 Şubat 2018'den önceki tarihler için tahmin üretmiyor" in a["hata"] and a["plaka"] == "", kim); sinir += 1; continue
                if beklenen == "MODEL":                                                                                             # model geçerli plaka üretemiyor: plaka uydurulmaz, ilin gerçek başlangıcı iddia edilmez
                    self.assertTrue(a["gizli"] and "geçerli bir plaka serisi bulamıyor" in a["hata"] and "gerçek plaka dağıtım başlangıcı anlamına gelmez" in a["hata"] and a["plaka"] == "", kim); model += 1; continue
                if beklenen is None:                                                                                                # çok uzak ileri tarih: iki sayfa da aynı hatayı verir
                    self.assertTrue(a["gizli"] and "alfabesinin dışına" in a["hata"] and a["plaka"] == "", kim); alfabe += 1; continue
                self.assertFalse(a["gizli"], kim); self.assertRegex(a["plaka"], r"^\d\d [A-Z]{3} \d{3}$", kim); self.assertEqual(a["hata"], "", kim)
                self.assertEqual(a["plaka"], beklenen, kim)                                                                         # ve üretimden bağımsız Python hesabıyla aynı (sıra numarası dahil)
                if iso < "2024-02-09": self.assertNotEqual(a["plaka"], ilk, kim); self.assertTrue("geriye dönük tahmin" in a["etiket"].lower() or "kalibre" in a["etiket"].lower()); geri += 1   # ilk gözlemin plakası TEKRARLANMAZ
                sayi += 1; sifirli += a["plaka"].split()[2][0] == "0"
        self.assertEqual(sayi + sinir + model + alfabe, 81 * len(TARIHLER)); self.assertEqual(sinir, 81)                              # 2018-01-31: 81 ilin hepsinde tahmin yok
        self.assertGreater(sifirli, 20); self.assertGreater(geri, 150); self.assertGreater(model, 20); self.assertGreater(alfabe, 0); self.assertLess(alfabe, 81)

    def test_sinir_tarihleri_2018_oncesi_2018_02_01_2020_2023_ve_ilk_gozlem(self):
        e = self.s["esdeger"]["ana"]
        for il in self.iller:
            self.assertIn("1 Şubat 2018'den önceki tarihler için tahmin üretmiyor", e[il]["2018-01-31"]["hata"])                                                    # 2018 öncesi: hiçbir ilde tahmin yok
            ilk, son = e[il]["2024-02-09"], e[il]["2023-06-01"]
            self.assertEqual(ilk["etiket"], "Kayıtlı veri"); self.assertEqual(ilk["uyari"], "")                                      # ilk gözlem günü kayıtlı değer; "veri başlangıcından önce" uyarısı yok
            self.assertEqual(son["etiket"], "Tarihsel referansla kalibre edilmiş tahmin" if il == "Ankara" else "Geriye dönük tahmin"); self.assertIn("ilk kayıtlı gözlemden (09.02.2024) önce", son["uyari"])   # 2023: ≤ 1 yıl, ilk kademe (Ankara: tarihsel referansla kalibre)
            self.assertRegex(son["out"], r"· ±\d+ gün$")
            # sınır günü (1 Şubat 2018): ya geriye tahmin ya da modelin geçerli plaka üretemediği açık mesaj; asla sessiz sabitleme
            b = e[il]["2018-02-01"]; self.assertTrue(b["gizli"] and "geçerli bir plaka serisi bulamıyor" in b["hata"] or b["etiket"] == "Çok kaba geriye dönük tahmin", il)
            # kronolojik monotonluk: plakalar tarihle birlikte azalmaz (aynı ilde sözlük sırası = seri sırası)
            sira = [e[il][d]["plaka"] for d in ("2018-02-01", "2020-06-01", "2022-06-01", "2023-06-01", "2024-02-09", "2025-06-15") if not e[il][d]["gizli"]]
            self.assertEqual(sira, sorted(sira), il)
        ist = e["İstanbul"]; self.assertEqual((ist["2020-06-01"]["etiket"], ist["2022-06-01"]["etiket"], ist["2023-06-01"]["etiket"]), ("Çok kaba geriye dönük tahmin", "Kaba geriye dönük tahmin", "Geriye dönük tahmin"))   # kalibresiz kademeler (referanssız iller)
        e1, e2, e3 = (int(re.search(r"±(\d+)", ist[d]["out"])[1]) for d in ("2023-06-01", "2022-06-01", "2020-06-01")); self.assertTrue(e1 < e2 < e3)    # belirsizlik ufukla artar
        self.assertEqual(ist["2020-06-01"]["out"], "1 Haziran 2020 · ±519 gün")
        # Ankara: tarihsel referansla kalibre; referans noktası kesin gözlem DEĞİL, "kalibre edilmiş tahmin" olarak etiketlenir ve belirsizlik korunur
        for il, v in self.s["esdeger"]["ana"].items():
            for iso, r in v.items():
                for metin in (r["uyari"], r["hata"], r["etiket"], r["out"]): self.assertNotRegex(metin, r"\b(?:BAA|AAB)\b|başlangıç serisinden|düzeninin başladığı", (il, iso))   # hiçbir ilde BAA/AAB başlangıç/alt seri uyarısı yok
        self.assertEqual(e["Konya"]["2018-01-31"]["hata"], "Bu tarih için tahmin üretilemiyor: bu araç 1 Şubat 2018'den önceki tarihler için tahmin üretmiyor. Bu, modelin uyguladığı bir tarih sınırıdır; üç harf–üç rakam plakaların dağıtımının başladığı gün anlamına gelmez.")
        self.assertEqual(e["Konya"]["2020-06-01"]["hata"], "Bu tarih için tahmin üretilemiyor: hesaplama modeli bu ilde bu tarih için geçerli bir plaka serisi bulamıyor. Bu, ilin gerçek plaka dağıtım başlangıcı anlamına gelmez; o tarihte plaka dağıtılmadığı anlamına da gelmez.")
        a = e["Ankara"]; r = a["2020-06-01"]
        self.assertEqual((r["plaka"], r["etiket"], r["out"]), ("06 BYS 922", "Tarihsel referansla kalibre edilmiş tahmin", "1 Haziran 2020 · ±60 gün")); self.assertNotEqual(r["etiket"], "Kayıtlı veri")
        self.assertIn("kullanıcı tarafından bildirilen tarihsel referansla (06 BYS 922, yaklaşık 1 Haziran 2020; resmî kayıt değildir)", r["uyari"]); self.assertIn("tek noktadır ve tarihi yaklaşıktır", r["uyari"])
        self.assertEqual(a["2018-02-01"]["etiket"], "Çok kaba geriye dönük tahmin"); self.assertNotIn("BAA", a["2018-02-01"]["uyari"]); self.assertNotIn("başlangıç serisinden", a["2018-02-01"]["uyari"])   # BAA/AAB gerçek başlangıç ya da alt seri sınırı olarak kullanılmaz; 1 Şubat 2018 model sınırı korunur
        self.assertEqual(a["2018-01-31"]["gizli"], True); self.assertIn("1 Şubat 2018'den önceki tarihler için tahmin üretmiyor", a["2018-01-31"]["hata"])
        for d in ("2022-06-01", "2023-06-01"): self.assertEqual(a[d]["etiket"], "Tarihsel referansla kalibre edilmiş tahmin")
        for d in ("2018-02-01", "2019-06-01"):                                                                                                        # 1 Haziran 2020 ÖNCESİ: referansın da ötesi -> "Çok kaba geriye dönük tahmin" + güçlendirilmiş açıklama
            self.assertEqual(a[d]["etiket"], "Çok kaba geriye dönük tahmin", d); u = a[d]["uyari"]
            for parca in ("ilk kayıtlı gözlemden (09.02.2024) önce: kayıt yok", "bilinen tarihsel referansın (06 BYS 922, yaklaşık 1 Haziran 2020; kullanıcı bildirimi, resmî kayıt değildir) da öncesinde kalıyor",
                          "hız, referans çevresindeki hızla varsayımla geriye uzatıldı", "Referans tek noktadır ve tarihi yaklaşıktır", "sonuç yüksek belirsizlik taşır", "yalnızca büyüklük sırası olarak okuyun"): self.assertIn(parca, u, (d, parca))
            self.assertNotIn("kalibre edildi", u)                                                                                                        # referans öncesi için "kalibre" ifadesi yok
        self.assertNotIn("öncesinde kalıyor", a["2020-06-01"]["uyari"]); self.assertNotIn("öncesinde kalıyor", a["2023-06-01"]["uyari"])               # 2020-06-01 ve sonrası: referans öncesi açıklaması çıkmaz

    def test_hafta_sonu_ve_resmi_tatil_elle_secilince_onceki_is_gunune_cekilmez(self):
        e = self.s["esdeger"]["ana"]; farkli = 0
        for il in self.iller:
            cuma, cts, paz, pzt, tatil = (e[il][d]["plaka"] for d in ("2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2026-10-29"))
            farkli += len({cuma, cts, paz, pzt}) == 4                                                                                  # elle seçilen günler ayrı ayrı hesaplanır (güncel tahmin kuralı burada uygulanmaz)
            self.assertNotEqual(tatil, cuma, il)
        self.assertGreater(farkli, 70)

    def test_gecmis_ve_uzak_gelecek_uyari_ve_belirsizlik(self):
        e = self.s["esdeger"]["ana"]["Konya"]; ist = self.s["esdeger"]["ana"]["İstanbul"]
        self.assertTrue(ist["2032-01-01"]["gizli"] and "seri alfabesinin dışına" in ist["2032-01-01"]["hata"])                         # çok uzak ileri tarih: plaka uydurulmaz, açık hata
        self.assertEqual(e["2025-06-15"]["etiket"], "Kayıtlı veri"); self.assertIn("kayıtlı gözlemlere göre", e["2025-06-15"]["out"])
        self.assertEqual(e["2060-01-01"]["etiket"], "Tahmin"); self.assertRegex(e["2060-01-01"]["out"], r"· ±\d+ gün$"); self.assertGreater(int(re.search(r"±(\d+)", e["2060-01-01"]["out"])[1]), int(re.search(r"±(\d+)", e["2026-10-31"]["out"])[1]))
        gecisler = [(il, iso) for il, v in self.s["esdeger"]["ana"].items() for iso, r in v.items() if "harf grubu sınırını aşıyor" in r["uyari"]]
        self.assertGreater(len(gecisler), 10); self.assertTrue(all("→" in self.s["esdeger"]["ana"][il][iso]["uyari"] for il, iso in gecisler))
        self.assertFalse(any("harf grubu sınırını aşıyor" in r["uyari"] for v in self.s["esdeger"]["ana"].values() for iso, r in v.items() if iso < "2024-02-09"))   # ileri harf grubu uyarısı geriye dönük sonuçta çıkmaz

    def test_gercek_klavye_enter_tab_hata_ve_olay_adlari(self):
        self.assertEqual(len(self.s["klavye"]), 4)
        for k in self.s["klavye"]:
            kim = (k["yol"], k["w"]); on = k["onek"]
            self.assertRegex(k["enter"]["plaka"], r"^\d\d [A-Z]{3} \d{3}$", kim); self.assertFalse(k["enter"]["gizli"], kim)                       # tarih alanında Enter hesaplar
            self.assertEqual(k["tabSonrasi"], "btn-tarih", kim); self.assertEqual(k["dugmeEnter"]["plaka"], k["enter"]["plaka"], kim)                  # Tab düğmeye gider; Enter aynı sonucu verir
            self.assertRegex(k["cerceve"], r"^solid [3-9]", kim)                                                                                      # görünür odak halkası
            self.assertEqual(k["dtDegeri"], "", kim); self.assertTrue(k["sonucTemizlendi"], kim)                                                      # girdi bozulunca eski sonuç kalmaz
            self.assertEqual((k["hata"]["hata"], k["hata"]["gizli"], k["hataRol"]), ("Lütfen geçerli bir tarih seçin.", True, "alert"), kim)           # erişilebilir hata
            self.assertEqual(k["olaylar"], [f"{on}-tarih-hesapla", f"{on}-tarih-sonuc"] * 2 + [f"{on}-tarih-hesapla", f"{on}-tarih-hata"], kim)       # yalnızca sabit adlar; tarih/plaka/il yok
            self.assertFalse(any(re.search(r"\d{4}|[A-Z]{3}", a) for a in k["olaylar"]), kim)

    def test_hedef_plaka_ve_tarih_araclari_birbirini_bozmaz(self):
        a = self.s["bagimsiz"]["ana"]
        self.assertEqual((a["h1"]["res"], a["h1"]["plaka"]), ("flex", "42 BZZ 999")); self.assertEqual(a["h2"], a["h1"])                                 # tarih hesabı hedef sonucunu değiştirmez
        self.assertNotEqual(a["h3"], a["h1"])                                                                                                           # yeni hedef sonucu gerçekten farklı (harness hesapladı)
        self.assertTrue(a["tarihGizli"] is False); self.assertEqual(a["tarihIl"], "Ankara"); self.assertEqual(a["t1"], a["t2"])                          # hedef hesabı tarih sonucunu/ilini değiştirmez
        i = self.s["bagimsiz"]["il"]; self.assertEqual(i["h1"], i["h2"]); self.assertNotEqual(i["h1"], i["h3"]); self.assertEqual(i["t1"], i["t2"]); self.assertFalse(i["tarihGizli"])

    def test_atlanacak_seriler_tarih_aracina_ozgu_aciklanir_ve_sessizce_yenilenir(self):
        g = self.s["gelismis"]
        self.assertNotEqual(g["once"], g["sonra"]); self.assertIn("atlanarak hesaplandı", g["uyari"]); self.assertEqual(g["bilgi"], "Atlanacak seriler uygulandı: S grubu, T grubu.")   # sonuçta açıkça belirtilir
        self.assertEqual(g["excl2"], ""); self.assertTrue(g["hedefExclEtkilenmedi"])                                                  # tarih aracının ayarı hedef aracının alanını/kalıcı ayarını DEĞİŞTİRMEZ
        self.assertTrue(g["sessiz"] and g["sonucGorunur"]); self.assertEqual(g["anlasilamayan"], "gorunur"); self.assertEqual(g["geri"], g["once"])   # sessiz yenileme (analitik olayı yok); anlaşılamayan giriş uyarılır; boşalınca varsayılana döner

    def test_atlanacak_seri_ayni_il_tarih_ayar_ana_sayfa_ve_il_sayfasi_birebir_kayitli_pt_excl_gizlice_etkilemez(self):
        at = self.s["atla"]; temel, kayitli = at["temel"], at["kayitli"]; beklenen = 5 * 4 * 8
        for kume in (temel["ana"], temel["il"], kayitli["ana"], kayitli["il"]): self.assertEqual(len(kume), beklenen)
        etkili = alfabe_hatasi = 0
        for anahtar, ref in temel["ana"].items():
            il, iso, metin = anahtar.split("|", 2)
            for ad, kume in (("il sayfası", temel["il"]), ("ana sayfa + kayıtlı pt-excl", kayitli["ana"]), ("il sayfası + kayıtlı pt-excl", kayitli["il"])):
                self.assertEqual(kume[anahtar], ref, (ad, anahtar))                                                                    # plaka, etiket, ±gün, uyarı, atlanacak seri bilgisi: dört durumda BİREBİR aynı
            taban = temel["ana"][f"{il}|{iso}|"]; self.assertFalse(taban["gizli"], anahtar)
            if ref["gizli"]:                                                                                                       # atlanan seriler yüzünden seri alfabesi bitebilir (örn. İstanbul 2030 + S/T grubu): açık hata, plaka uydurulmaz
                self.assertIn("alfabesinin dışına", ref["hata"], anahtar); self.assertEqual(ref["plaka"], "", anahtar); alfabe_hatasi += 1; continue
            self.assertEqual(taban["atla"], ""); self.assertNotIn("atlanarak hesaplandı", taban["uyari"]); self.assertEqual(taban["plaka"], beklenen_plaka(self.iller[il], iso), (il, iso))     # varsayılan: hiçbir seri atlanmaz (üretimden bağımsız Python hesabıyla aynı)
            if metin == "QXX": self.assertEqual((ref["atla"], ref["plaka"], "Anlaşılamayan" in ref["atlaUyari"]), ("", taban["plaka"], True), anahtar)     # geçersiz giriş: uygulanmaz, açıkça uyarılır
            elif metin:
                self.assertIn("kayıtlı veri tarihini etkilemez" if iso == "2025-06-15" else "Atlanacak seriler uygulandı", ref["atla"], anahtar)
                if iso == "2025-06-15": self.assertEqual(ref["plaka"], taban["plaka"], anahtar)                                    # kayıtlı veri tarihleri atlamadan etkilenmez
                else: etkili += ref["plaka"] != taban["plaka"]
        self.assertGreater(etkili, 10); self.assertLess(alfabe_hatasi, 6)                                                                                             # atlanacak seriler gerçekten sonucu değiştirir (test boş geçmiyor)
        h = at["kayitliHedef"]; self.assertEqual((h["excl2"], h["excl"], h["tarihAtla"]), ("SXX, TXX", "", True))                    # kayıtlı ayar hedef aracında yüklenir; tarih aracının alanı boş
        self.assertIn("atlanacaklar listenizde", h["hedef"])                                                # hedef plaka aracının atlanacak seri davranışı DEĞİŞMEDİ (kayıtlı ayar uygulanır)
        self.assertNotIn("atlanacaklar listenizde", at["kayitliIlHedef"])                                                              # il sayfası hedef aracı kayıtlı ana sayfa ayarını kullanmaz (mevcut davranış)

    def test_81_il_tablosu_varsayilan_kapali_acilir_kapanir_ve_sonuca_esit(self):
        t = self.s["tablo"]
        self.assertEqual(t["baslangic"], {"kapali": True, "ae": "false", "etiket": "81 ilin bu tarihteki tahminlerini göster", "satir": 0})
        self.assertEqual((t["acik"]["kapali"], t["acik"]["ae"], t["acik"]["etiket"], t["acik"]["satir"]), (False, "true", "Tabloyu gizle", 82))        # 81 il + başlık
        self.assertIn("Seçili tarihte (01.03.2028)", t["acik"]["baslik"]); self.assertEqual(t["istanbulSecili"], t["sonucPlakasi"][3:])                    # tablo hücresi = sonuç plakası (il kodu hariç)
        self.assertIn("01.01.2030", t["baslikYeni"]); self.assertEqual(t["kapandi"], {"kapali": True, "ae": "false", "etiket": "81 ilin bu tarihteki tahminlerini göster"})

    def test_geriye_donuk_tarih_plaka_tarih_tutarliligi_tarih_araci_hedef_araci_ve_81_il_tablosu(self):
        ay = {a: i + 1 for i, a in enumerate(["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"])}
        for k in self.s["geriTutarlilik"]:
            kim = (k["il"], k["iso"]); beklenen = dt.date.fromisoformat(k["iso"])
            if k["ana"]["gizli"]: continue
            m = re.search(r"Tahmini: (\d\d)\.(\d\d)\.(\d{4})", k["hedefAna"]); self.assertIsNotNone(m, kim)
            self.assertLessEqual(abs((dt.date(int(m[3]), int(m[2]), int(m[1])) - beklenen).days), 1, kim)                              # ana sayfa hedef aracı: plaka -> aynı tarih (±1 gün yuvarlama)
            m = re.search(r"~(\d+) (\w+) (\d{4})", k["hedefIl"]); self.assertIsNotNone(m, kim)
            self.assertLessEqual(abs((dt.date(int(m[3]), ay[m[2]], int(m[1])) - beklenen).days), 1, kim)                              # il sayfası hedef aracı: aynı
            self.assertEqual(k["tablo"], k["ana"]["plaka"][3:] + " ≈", kim)                                                          # 81 il tablosu: aynı plaka (il kodu hariç), geriye dönük işaretiyle
            if k["il"] == "Ankara" and k["iso"] < "2020-06-01":                                                                      # referans öncesi: TÜM arayüzlerde aynı etiket (tarih aracı, ana sayfa hedef aracı, il sayfası hedef aracı)
                self.assertEqual(k["ana"]["etiket"], "Çok kaba geriye dönük tahmin", kim); self.assertIn("çok kaba geriye dönük tahmin", k["hedefAna"], kim); self.assertIn("çok kaba geriye dönük tahmin", k["hedefIl"], kim)
                self.assertNotIn("kalibre edilmiş tahmin", k["hedefAna"] + k["hedefIl"], kim)
            elif k["il"] == "Ankara": self.assertIn("tarihsel referansla kalibre edilmiş tahmin", k["hedefAna"], kim); self.assertIn("tarihsel referansla kalibre edilmiş tahmin", k["hedefIl"], kim); self.assertEqual(k["ana"]["etiket"], "Tarihsel referansla kalibre edilmiş tahmin", kim)
        t = self.s["tabloGeri"]
        self.assertEqual((t["2018-01-31"]["tireSayisi"], t["2018-01-31"]["satir"]), (81, 81)); self.assertIn("1 Şubat 2018'den önceki tarihler için tahmin üretmiyor", t["2018-01-31"]["cap"]); self.assertIn("Seçili tarihte (31.01.2018)", t["2018-01-31"]["baslik"])
        self.assertEqual((t["2018-02-01"]["Ankara"], t["2018-02-01"]["Konya"]), ("ATH 800 ≈", "—"));        # Ankara: referansla kalibre edilmiş tahmin; Konya: model plaka üretemiyor
        self.assertGreater(t["2018-02-01"]["tireSayisi"], 70)    # modelin plaka üretemediği iller "—"
        self.assertEqual(t["2020-06-01"]["Ankara"], "BYS 922 ≈"); self.assertEqual(t["2020-06-01"]["Konya"], "—"); self.assertIn("≈ geriye dönük tahmin", t["2020-06-01"]["cap"])
        self.assertIn("1 Haziran 2020 öncesi için çok kabadır", t["2018-02-01"]["cap"]); self.assertEqual(t["2018-02-01"]["Ankara"], "ATH 800 ≈")                  # tablo notu aynı dili kullanır; sayısal değer aynı
        self.assertEqual(t["2023-06-01"]["tireSayisi"], 0); self.assertTrue(all(t["2023-06-01"][i].endswith(" ≈") for i in ("Ankara", "Istanbul", "Konya")))
        self.assertEqual(t["2024-02-09"]["Ankara"], "EGF 799 ✓"); self.assertEqual(t["2024-02-09"]["cap"], "")                              # ilk gözlem günü: kayıtlı değer, geriye uyarı yok

    def test_5_genislikte_yatay_tasma_yok_ve_plaka_tek_satir(self):
        self.assertEqual({x["w"] for x in self.s["genislik"]}, {320, 375, 390, 768, 1440}); self.assertEqual(len(self.s["genislik"]), 5 * 6)
        for x in self.s["genislik"]:
            kim = (x["w"], x["yol"]); self.assertLessEqual(x["tasma"], 0, kim); self.assertTrue(x["tek"] and x["sigar"], kim); self.assertGreaterEqual(x["btn"], 44, kim); self.assertGreaterEqual(x["px"], 36, kim)
            self.assertRegex(x["plaka"], r"^\d\d [A-Z]{3} \d{3}$", kim)

@unittest.skipUnless(u.NODE, "node kurulu değil")
class AnkaraTarihselReferans(unittest.TestCase):
    """KULLANICI REFERANSI (resmî veri DEĞİL, gözlem verisine KARIŞTIRILMAZ): Ankara 06 BYS 922 ≈ 1 Haziran 2020, data/tarihsel_referanslar.json. Yalnızca Ankara'nın ilk gözlem öncesi tahminini kalibre eder.
    Eski (kalibresiz) ve yeni (kalibre) motor aynı Node bağlamında karşılaştırılır; diğer 80 il, Ankara'nın 2024 sonrası değerleri ve güncel tahmin (06 GGL 096) DEĞİŞMEZ."""
    TARIHLER_A = ["2018-01-31", "2018-02-01", "2018-06-01", "2019-06-01", "2020-01-01", "2020-06-01", "2021-06-01", "2022-06-01", "2023-06-01", "2024-02-09", "2024-06-01", "2027-03-01", "2028-07-01"]
    BETIK = r"""const fs=require('fs'),vm=require('vm'),R=process.argv[1],T=JSON.parse(process.argv[2]);
const yap=ref=>{const c=vm.createContext({console,Math,Date});for(const f of ['takvim.js',...(ref?['tarihsel-referanslar.js']:[]),'tahmin-motoru.js','tarih-sorgu.js'])vm.runInContext(fs.readFileSync(R+'/assets/'+f,'utf8'),c);return c};
const e=yap(false),y=yap(true),D=JSON.parse(fs.readFileSync(R+'/data/tahmin_data.json','utf8')),E0=Date.UTC(2024,0,1),gun=t=>Math.round((Date.UTC(+t.slice(0,4),+t.slice(5,7)-1,+t.slice(8,10))-E0)/864e5);
const kop=il=>JSON.parse(JSON.stringify(D.iller.find(x=>x.il===il))), sor=(c,il,t)=>{c.__s=kop(il);c.__t=t;return vm.runInContext("PlakaTarih.sorgula(__s,__t,null,'')",c)}, ozet=r=>r.tip==='hata'?{hata:r.mesaj}:{plaka:r.plaka,etiket:r.etiket,err:r.err,kayit:r.kayit,uyari:r.uyari};
const out={ankara:{}};for(const t of T){out.ankara[t]={eski:ozet(sor(e,'Ankara',t)),yeni:ozet(sor(y,'Ankara',t))}}
const gunler=['2018-02-01','2019-01-01','2020-06-01','2022-06-01','2023-06-01','2024-02-09','2025-06-15','2026-10-30','2030-01-01','2027-03-01','2028-07-01','2032-01-01'];let say=0,fark=0;
for(const s0 of D.iller){if(s0.il==='Ankara')continue;for(const t of gunler){say++;if(JSON.stringify(sor(e,s0.il,t))!==JSON.stringify(sor(y,s0.il,t)))fark++}}out.digerIller={say,fark};
let sa=0,fa=0;for(let g=39;g<=2500;g++){const t=new Date(E0+g*864e5).toISOString().slice(0,10);sa++;if(JSON.stringify(sor(e,'Ankara',t))!==JSON.stringify(sor(y,'Ankara',t)))fa++}out.ankaraSonrasi={say:sa,fark:fa};
for(const [ad,c] of [['eski',e],['yeni',y]]){c.__s=kop('Ankara');const ref=vm.runInContext("trReferansGun(Date.UTC(2026,9,30,12))",c);out['guncel_'+ad]=vm.runInContext("guncelSeriBilgisi(__s,"+ref.gun+").plaka",c)}
y.__s=kop('Ankara');const F=39,g0=gun('2018-02-01'),Rg=gun('2020-06-01'),n=g=>vm.runInContext("estimateAt(__s,"+g+").n",y);let mono=true,minAdim=1e18,prev=null;for(let g=g0;g<=F;g++){const v=n(g);if(prev!==null){if(!(v>prev))mono=false;minAdim=Math.min(minAdim,v-prev)}prev=v}
out.monoton={mono,minAdim,nF1:n(F-1),nF:n(F),nF2:n(F+1),nR:n(Rg),nRef:vm.runInContext("toN('BYS',922)",y),R:Rg,F};
let tm=0,tn=0;for(let g=g0;g<F;g+=3){const v=n(g);if(Math.round(v)<1)continue;y.__n=Math.round(v);const b=vm.runInContext("backEstimate(__s,__n)",y);tm=Math.max(tm,Math.abs(b.day-g));tn++}out.ters={maks:tm,n:tn};
y.__n=vm.runInContext("toN('BYS',922)",y);const bb=vm.runInContext("backEstimate(__s,__n)",y);out.hedefRef={day:bb.day,err:bb.err,kalibre:bb.kalibre};
out.asset=vm.runInContext("JSON.stringify(PlakaReferanslar)",y);
console.log(JSON.stringify(out))"""
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads(subprocess.run([u.NODE, "-e", cls.BETIK, u.ROOT, json.dumps(cls.TARIHLER_A)], capture_output=True, text=True, check=True).stdout); cls.s = next(x for x in veri() if x["il"] == "Ankara"); cls.o = [tuple(a) for a in cls.s["obs"]]

    def test_referans_ayri_dosyada_gozlemlerle_karismaz_ve_yalnizca_ankara(self):
        v = json.load(open(os.path.join(u.ROOT, "data", "tarihsel_referanslar.json"), encoding="utf-8")); self.assertEqual(len(v["referanslar"]), 1); r = v["referanslar"][0]
        self.assertEqual((r["il"], r["kod"], r["plaka"], r["tarih"], r["tarih_kesinligi"], r["resmi_veri"]), ("Ankara", 6, "06 BYS 922", "2020-06-01", "yaklaşık", False)); self.assertIn("Kullanıcı", r["kaynak"]); self.assertIn("kesin gözlem olarak etiketlenmez", r["not"])
        self.assertNotIn(_tarih_n(r["plaka"]), [x[1] for x in self.o]); self.assertEqual(self.o[0][0], 39)                                                    # gözlem verisinde YOK; ilk gözlem değişmedi
        self.assertEqual(json.loads(self.r["asset"]), {"6": [{"plaka": "06 BYS 922", "tarih": "2020-06-01", "tarihKesinligi": "yaklaşık", "tarihBelirsizligiGun": 30, "kaynak": r["kaynak"], "resmi": False}]})   # üretilmiş varlık = JSON
        for f in ("il/istanbul.html", "il/izmir.html", "il/konya.html"): self.assertNotIn("tarihsel-referanslar.js", u.oku(os.path.join(u.ROOT, f)))        # yalnızca Ankara sayfası ve ana sayfa yükler
        self.assertIn("tarihsel-referanslar.js", u.oku(os.path.join(u.ROOT, "il", "ankara.html"))); self.assertIn("tarihsel-referanslar.js", u.oku(os.path.join(u.ROOT, "index.html")))

    def test_ankara_eski_yeni_karsilastirma_2020_2024_ve_kalibre_etiket(self):
        a = self.r["ankara"]; eski = {t: a[t]["eski"] for t in a}; yeni = {t: a[t]["yeni"] for t in a}
        self.assertEqual([eski[t].get("plaka") for t in ("2020-06-01", "2021-06-01", "2022-06-01", "2023-06-01")], ["06 BFZ 076", "06 CBP 898", "06 CVH 720", "06 DRB 541"])      # ESKİ (kalibresiz) sonuçlar
        self.assertEqual([yeni[t].get("plaka") for t in ("2020-06-01", "2021-06-01", "2022-06-01", "2023-06-01")], ["06 BYS 922", "06 CKB 589", "06 DAR 749", "06 DRP 403"])      # YENİ (referansla kalibre)
        self.assertEqual((yeni["2020-06-01"]["etiket"], yeni["2020-06-01"]["err"]), ("Tarihsel referansla kalibre edilmiş tahmin", 60)); self.assertFalse(yeni["2020-06-01"]["kayit"])    # kesin gözlem DEĞİL; referans yakınında belirsizlik azalır (519 → 60) ama sıfırlanmaz
        self.assertTrue(60 <= yeni["2020-06-01"]["err"] < eski["2020-06-01"]["err"]); self.assertEqual((eski["2020-06-01"]["err"], eski["2021-06-01"]["err"], eski["2022-06-01"]["err"]), (519, 329, 176))
        self.assertEqual([yeni[t]["err"] for t in ("2021-06-01", "2022-06-01", "2023-06-01")], [151, 176, 63]); self.assertEqual(yeni["2018-02-01"]["etiket"], "Çok kaba geriye dönük tahmin"); self.assertEqual(yeni["2019-06-01"]["etiket"], "Çok kaba geriye dönük tahmin"); self.assertEqual((yeni["2018-02-01"]["plaka"], yeni["2018-02-01"]["err"], yeni["2019-06-01"]["plaka"], yeni["2019-06-01"]["err"]), ("06 ATH 800", 329, "06 BKJ 604", 152))   # etiket değişti; sayısal tahmin ve ± gün AYNI
        self.assertTrue(yeni["2018-01-31"].get("hata", "").startswith("Bu tarih için tahmin üretilemiyor: bu araç 1 Şubat 2018")); self.assertIn("1 Şubat 2018", yeni["2018-01-31"]["hata"]); self.assertIn("hesaplama modeli", eski["2018-02-01"]["hata"])  # sınır ve geçerli-seri alt sınırı korunur
        for t in ("2024-02-09", "2024-06-01", "2027-03-01", "2028-07-01"): self.assertEqual(eski[t], yeni[t], t)                                                           # 2024 ve sonrası AYNI
        print("\n  Ankara eski → yeni:", "; ".join(f"{t[:4]} {eski[t].get('plaka', '—')} → {yeni[t].get('plaka', '—')}" for t in ("2020-06-01", "2021-06-01", "2022-06-01", "2023-06-01", "2024-02-09")), file=sys.stderr)

    def test_js_bagimsiz_python_kalibrasyonuyla_ayni_plaka_ve_belirsizlik(self):
        for t, v in self.r["ankara"].items():
            if t < "2018-02-01" or t >= "2024-02-09": continue
            h = self.o[0][0] - (dt.date.fromisoformat(t) - E0).days; n = geri_n(self.o, h, 6); self.assertEqual(v["yeni"]["plaka"], tahmin_plaka(6, n), t); self.assertEqual(v["yeni"]["err"], geri_hata(self.o, h, 6), t)
        k = kalibre_katsayilar(6, self.o); self.assertAlmostEqual(k["kappa"], 0.7720, places=3); self.assertEqual(round(geri_n(self.o, k["H"], 6)), k["nR"])             # referans noktası yakalanır

    def test_monotonluk_sureklilik_ve_tarih_plaka_tarih_tutarliligi(self):
        m = self.r["monoton"]; self.assertTrue(m["mono"]); self.assertGreater(m["minAdim"], 200)                                                          # 2018-02-01 → ilk gözlem: günlük kesin artış
        self.assertEqual(m["nF"], self.o[0][1]); self.assertLess(m["nF"] - m["nF1"], 1500); self.assertGreater(m["nF"] - m["nF1"], 500)                    # ilk gözlemde sıçrama yok (bir gün öncesi ≈ günlük hız kadar geride)
        self.assertEqual(round(m["nR"]), m["nRef"])                                                                                                       # referans tarihinde referans plakası (kalibre)
        self.assertEqual(self.r["ters"]["maks"], 0); self.assertGreater(self.r["ters"]["n"], 600)                                                          # tarih→plaka→tarih: 0 gün sapma
        h = self.r["hedefRef"]; self.assertEqual((dt.date(2024, 1, 1) + dt.timedelta(days=h["day"]), h["kalibre"], h["err"]), (dt.date(2020, 6, 1), "ara", 60))   # hedef aracı: 06 BYS 922 → 1 Haziran 2020 (±60, kalibre)

    def test_81_il_gecerli_seri_gunluk_monotonluk_surekllilik_ve_ters_tutarlilik(self):
        """81 il, 2018-02-01 → ilk gözlem, HER GÜN: sıra kesin artar; yuvarlanmış sıra ≥ 1 olan her gün geçerli plaka (invN ≠ null) ve ilk gözlem plakasından küçük; ilk gözlemde süreklilik; tarih→plaka→tarih sapması ≤ 1 gün."""
        r = json.loads(subprocess.run([u.NODE, "-e", r"""const fs=require('fs'),vm=require('vm'),R=process.argv[1],c=vm.createContext({console,Math,Date});
['takvim.js','tarihsel-referanslar.js','tahmin-motoru.js','tarih-sorgu.js'].forEach(f=>vm.runInContext(fs.readFileSync(R+'/assets/'+f,'utf8'),c));
const D=JSON.parse(fs.readFileSync(R+'/data/tahmin_data.json','utf8')),E0=Date.UTC(2024,0,1),g0=Math.round((Date.UTC(2018,1,1)-E0)/864e5),sonuc={il:0,monoIhlal:[],gecersiz:[],buyuk:[],sureksiz:[],ters:0,tersMaks:0,gecerliGun:0,yokGun:0};
for(const s0 of D.iller){const s=JSON.parse(JSON.stringify(s0)),F=s.obs[0][0],n0=s.obs[0][1];c.__s=s;sonuc.il++;let prev=null,gecerliOnce=false;
 for(let g=g0;g<=F;g++){c.__g=g;const e=vm.runInContext('estimateAt(__s,__g)',c),n=e.n;if(prev!==null&&!(n>prev))sonuc.monoIhlal.push(s.il+'@'+g);prev=n;
  const d=vm.runInContext('PlakaTarih.plakaDurum(__s,__g)',c);if(Math.round(n)>=1){sonuc.gecerliGun++;if(d.plaka===null)sonuc.gecersiz.push(s.il+'@'+g);if(g<F&&!(n<n0))sonuc.buyuk.push(s.il+'@'+g);gecerliOnce=true}else{sonuc.yokGun++;if(d.plaka!==null)sonuc.gecersiz.push('uydurma '+s.il+'@'+g)}
  if(g%11===0&&Math.round(n)>=1&&g<F){c.__n=Math.round(n);const b=vm.runInContext('backEstimate(__s,__n)',c);const fark=Math.abs(b.day-g);sonuc.ters++;sonuc.tersMaks=Math.max(sonuc.tersMaks,fark)}}
 c.__g=F-1;const a=vm.runInContext('estimateAt(__s,__g).n',c);if(!(n0-a>0&&n0-a<30000*1+ 40000))sonuc.sureksiz.push(s.il+':'+(n0-a))}
console.log(JSON.stringify(sonuc))""", u.ROOT], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(r["il"], 81); self.assertEqual(r["monoIhlal"], []); self.assertEqual(r["gecersiz"], []); self.assertEqual(r["buyuk"], [])                    # geçerli seri, monotonluk, ilk gözlemden küçük; geçersizken plaka uydurulmaz
        self.assertEqual(r["sureksiz"], []); self.assertLessEqual(r["tersMaks"], 1); self.assertGreater(r["ters"], 5000); self.assertGreater(r["gecerliGun"], 100000); self.assertGreater(r["yokGun"], 1000)   # ilk gözlemde sıçrama yok; plaka→tarih ≤ 1 gün

    def test_diger_81_den_80_il_ve_ankara_ilk_gozlem_sonrasi_degismez_guncel_tahmin_korunur(self):
        self.assertEqual(self.r["digerIller"]["fark"], 0); self.assertGreater(self.r["digerIller"]["say"], 900)                                           # İstanbul, İzmir ve diğer 77 il: eski == yeni (tüm alanlar)
        self.assertEqual(self.r["ankaraSonrasi"]["fark"], 0); self.assertGreater(self.r["ankaraSonrasi"]["say"], 2400)                                    # Ankara ilk gözlemden 2030'a her gün aynı
        self.assertEqual((self.r["guncel_eski"], self.r["guncel_yeni"]), ("06 GGL 096", "06 GGL 096"))                                                   # 30 Ekim 2026 güncel tahmin korunur

class JsKapali(unittest.TestCase):
    def test_statik_bilgiler_ve_baglantilar_gorunur_arac_js_ister(self):
        for s in veri():
            h = sayfa(s["il"]); body = re.sub(r'<div id="tarih-govde" hidden>.*?</div>\n</section>', "", h, flags=re.S)
            self.assertRegex(body, r'class="buyuk mono" data-live="plaka">\d\d [A-Z]{3} \d{3}<'); self.assertIn("Son kayıtlı gözlem", body); self.assertIn(BASLIK, body); self.assertIn("Bu araç JavaScript gerektirir.", body)
            self.assertEqual(len(re.findall(r'<a href="/il/[a-z]+">', h)), 81)                                                                     # gerçek il bağlantıları HTML'de
        self.assertEqual(len(re.findall(r'<a href="/il/[a-z]+">', ANA)), 81); self.assertIn('data-kart="plaka">', ANA)

if __name__ == "__main__": unittest.main()
