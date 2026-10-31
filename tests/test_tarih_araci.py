"""Ana sayfa ve 81 il sayfasındaki "Belirli bir tarihte hangi plakada?" aracı: ortak işaretleme/kod, ana sayfada sade ve bağımsız il seçimi, il sayfasında yalnızca tarih;
aynı il ve tarih için tam plaka eşliği (ana sayfa = il sayfası = üretimden bağımsız Python hesabı), elle seçilen hafta sonu/tatil tarihinin önceki iş gününe ÇEKİLMEMESİ,
ikincil "81 il" tablosu (varsayılan kapalı), atlanacak seriler, hedef plaka aracıyla karşılıklı bağımsızlık, gerçek klavye ve hata mesajları, analitik olay adları
(kullanıcı girdisi taşınmaz) ve 5 genişlikte taşma. Chrome testleri CHROME_TEMEL gibi analitik adlarını çözemeyen bir tarayıcıyla çalışır."""
import datetime as dt, glob, json, math, os, re, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
from test_il_sayfasi import veri, sayfa, slug, TAM, E0, tahmin_plaka, yuvarla
from test_ana_sayfa_regresyon import CHROME
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
BASLIK = "Belirli bir tarihte hangi plakada?"
ACIKLAMA_ANA = "İl ve tarih seçerek o günün tahmini plakasını öğrenin."
ACIKLAMA_IL = "Seçtiğiniz tarihte bu ilde hangi plakanın verilmesinin beklendiğini öğrenin."
# geçmiş (veri öncesi, veri içi, son gözlem), bugün/Cuma, Cumartesi, Pazar, Pazartesi, resmî tatil (29 Ekim, 1 Ocak, Kurban), yakın/uzak gelecek
TARIHLER = ["2023-06-01", "2024-02-09", "2025-06-15", "2026-10-23", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2027-01-01", "2027-05-17", "2028-07-01", "2032-01-01", "2060-01-01"]

def bolum(h, kimlik): return re.search(rf'<section class="arac tarih-arac" id="{kimlik}".*?</section>', h, re.S)[0]
def beklenen_plaka(s, iso):
    """Üretimden bağımsız: gözlem aralığında doğrusal ara değer (kayıt öncesi: ilk gözlem), sonrasında forecast.py ilerlemesi; yuvarlama JS Math.round gibi (yarım yukarı)."""
    o = [tuple(x) for x in s["obs"]]; gun = (dt.date.fromisoformat(iso) - E0).days; g, n = o[-1]
    if gun > g: ham = n + fc.advance(o, fc.clean(o), g, gun - g, fc.slope(o, g))
    elif gun <= o[0][0]: ham = o[0][1]
    else:
        i = next(i for i in range(1, len(o)) if o[i][0] >= gun); lo, hi = o[i - 1], o[i]; ham = lo[1] + ((gun - lo[0]) / (hi[0] - lo[0]) if hi[0] != lo[0] else 0) * (hi[1] - lo[1])
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

    def test_ana_sayfa_ile_il_sayfasi_81_il_x_14_tarih_tam_plaka_birebir_ve_python_ile_ayni(self):
        e = self.s["esdeger"]; self.assertEqual((len(e["ana"]), len(e["il"])), (81, 81)); sayi = sifirli = hatali = 0
        for il, s in self.iller.items():
            for iso in TARIHLER:
                a, i = e["ana"][il][iso], e["il"][il][iso]; kim = (il, iso); beklenen = beklenen_plaka(s, iso)
                self.assertEqual(a, i, kim)                                                                                         # plaka, etiket, ± gün, uyarı, hata: ana sayfa = il sayfası (birebir)
                if beklenen is None:                                                                                                # çok uzak tarih (İstanbul 2031 sonrası, Ankara 2047 sonrası ...): iki sayfa da aynı hatayı verir
                    self.assertTrue(a["gizli"] and "alfabesinin dışına" in a["hata"] and a["plaka"] == "", kim); hatali += 1; continue
                self.assertFalse(a["gizli"], kim); self.assertRegex(a["plaka"], r"^\d\d [A-Z]{3} \d{3}$", kim); self.assertEqual(a["hata"], "", kim)
                self.assertEqual(a["plaka"], beklenen, kim)                                                                         # ve üretimden bağımsız Python hesabıyla aynı (sıra numarası dahil)
                sayi += 1; sifirli += a["plaka"].split()[2][0] == "0"
        self.assertEqual(sayi + hatali, 81 * len(TARIHLER)); self.assertGreater(sifirli, 20); self.assertGreater(hatali, 0); self.assertLess(hatali, 81)                                                 # baştaki sıfırlı sıra numaraları (006, 042 ...) gerçekten sınandı

    def test_hafta_sonu_ve_resmi_tatil_elle_secilince_onceki_is_gunune_cekilmez(self):
        e = self.s["esdeger"]["ana"]; farkli = 0
        for il in self.iller:
            cuma, cts, paz, pzt, tatil = (e[il][d]["plaka"] for d in ("2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2026-10-29"))
            farkli += len({cuma, cts, paz, pzt}) == 4                                                                                  # elle seçilen günler ayrı ayrı hesaplanır (güncel tahmin kuralı burada uygulanmaz)
            self.assertNotEqual(tatil, cuma, il)
        self.assertGreater(farkli, 70)

    def test_gecmis_ve_uzak_gelecek_uyari_ve_belirsizlik(self):
        e = self.s["esdeger"]["ana"]["Konya"]; ist = self.s["esdeger"]["ana"]["İstanbul"]
        self.assertTrue(ist["2032-01-01"]["gizli"] and "seri alfabesinin dışına" in ist["2032-01-01"]["hata"])                         # çok uzak tarih: plaka uydurulmaz, açık hata
        self.assertEqual(e["2023-06-01"]["etiket"], "Kayıtlı veri"); self.assertIn("veri başlangıcından (09.02.2024) önce", e["2023-06-01"]["uyari"]); self.assertIn("kayıtlı gözlemlere göre", e["2025-06-15"]["out"])
        self.assertEqual(e["2060-01-01"]["etiket"], "Tahmin"); self.assertRegex(e["2060-01-01"]["out"], r"· ±\d+ gün$"); self.assertGreater(int(re.search(r"±(\d+)", e["2060-01-01"]["out"])[1]), int(re.search(r"±(\d+)", e["2026-10-31"]["out"])[1]))
        gecisler = [(il, iso) for il, v in self.s["esdeger"]["ana"].items() for iso, r in v.items() if "harf grubu sınırını aşıyor" in r["uyari"]]
        self.assertGreater(len(gecisler), 10); self.assertTrue(all("→" in self.s["esdeger"]["ana"][il][iso]["uyari"] for il, iso in gecisler))

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

    def test_5_genislikte_yatay_tasma_yok_ve_plaka_tek_satir(self):
        self.assertEqual({x["w"] for x in self.s["genislik"]}, {320, 375, 390, 768, 1440}); self.assertEqual(len(self.s["genislik"]), 5 * 6)
        for x in self.s["genislik"]:
            kim = (x["w"], x["yol"]); self.assertLessEqual(x["tasma"], 0, kim); self.assertTrue(x["tek"] and x["sigar"], kim); self.assertGreaterEqual(x["btn"], 44, kim); self.assertGreaterEqual(x["px"], 36, kim)
            self.assertRegex(x["plaka"], r"^\d\d [A-Z]{3} \d{3}$", kim)

class JsKapali(unittest.TestCase):
    def test_statik_bilgiler_ve_baglantilar_gorunur_arac_js_ister(self):
        for s in veri():
            h = sayfa(s["il"]); body = re.sub(r'<div id="tarih-govde" hidden>.*?</div>\n</section>', "", h, flags=re.S)
            self.assertRegex(body, r'class="buyuk mono" data-live="plaka">\d\d [A-Z]{3} \d{3}<'); self.assertIn("Son kayıtlı gözlem", body); self.assertIn(BASLIK, body); self.assertIn("Bu araç JavaScript gerektirir.", body)
            self.assertEqual(len(re.findall(r'<a href="/il/[a-z]+">', h)), 81)                                                                     # gerçek il bağlantıları HTML'de
        self.assertEqual(len(re.findall(r'<a href="/il/[a-z]+">', ANA)), 81); self.assertIn('data-kart="plaka">', ANA)

if __name__ == "__main__": unittest.main()
