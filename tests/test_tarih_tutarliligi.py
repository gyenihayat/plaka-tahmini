"""Tarih ve tahmin tutarlılığı (KESİN İŞ KURALI): güncel tahminin referans günü, Türkiye yerel tarihinin (UTC+3) EN YAKIN ÖNCEKİ İŞ GÜNÜDÜR.
Cumartesi, Pazar ve tam gün resmî tatilde değer değişmez (arife/yarım günler iş günüdür). Ana sayfa, il sayfası büyük tahmini ve araç aynı kuralı kullanır;
statik HTML (Python) ve canlı JS aynı takvimi (is_gunu.py -> assets/takvim.js) kullanır. Son kayıtlı gözlem tarihi bu kuraldan bağımsızdır."""
import datetime as dt, functools, glob, html, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
import is_gunu as ig
from test_il_sayfasi import veri, sayfa, slug, TAM, inv, tr, E0
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL
TRT = dt.timezone(dt.timedelta(hours=3))
D = dt.date
def an(*a): return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp() * 1000)       # UTC an (ms)
# (UTC an, Türkiye'de gerçek takvim günü, beklenen REFERANS gün, açıklama) -- beklenenler elle yazılmıştır
ANLAR = [
    (an(2026, 10, 30, 20, 59, 59), D(2026, 10, 30), D(2026, 10, 30), "Cuma 23:59:59 TRT"),
    (an(2026, 10, 30, 21, 0, 0), D(2026, 10, 31), D(2026, 10, 30), "Cumartesi 00:00:00 TRT (gece yarısı geçişi): değer değişmez"),
    (an(2026, 10, 31, 12), D(2026, 10, 31), D(2026, 10, 30), "Cumartesi"),
    (an(2026, 11, 1, 12), D(2026, 11, 1), D(2026, 10, 30), "Pazar"),
    (an(2026, 11, 1, 20, 59, 59), D(2026, 11, 1), D(2026, 10, 30), "Pazar 23:59:59 TRT"),
    (an(2026, 11, 1, 21, 0, 0), D(2026, 11, 2), D(2026, 11, 2), "Pazartesi 00:00:00 TRT: yeni iş günü, değer değişir"),
    (an(2026, 11, 2, 12), D(2026, 11, 2), D(2026, 11, 2), "Pazartesi"),
    (an(2026, 12, 31, 21, 0, 0), D(2027, 1, 1), D(2026, 12, 31), "Yılbaşı 00:00 TRT (yıl sınırı, resmî tatil, Cuma)"),
    (an(2027, 1, 1, 9), D(2027, 1, 1), D(2026, 12, 31), "1 Ocak 2027 (resmî tatil)"),
    (an(2027, 3, 9, 9), D(2027, 3, 9), D(2027, 3, 8), "Ramazan Bayramı 1. gün (Salı) -> Pazartesi arife (yarım gün, iş günü)"),
    (an(2027, 5, 16, 9), D(2027, 5, 16), D(2027, 5, 14), "Kurban Bayramı 1. gün (Pazar) -> Cuma"),
    (an(2027, 5, 19, 9), D(2027, 5, 19), D(2027, 5, 14), "Kurban 4. gün + 19 Mayıs (Çarşamba) -> Cuma"),
]
TZLER = ["UTC", "America/Los_Angeles", "Pacific/Kiritimati", "Asia/Tokyo", "Europe/Istanbul"]
def tum_sayfalar(): return sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html")))

class TakvimBirligi(unittest.TestCase):
    """JS takvimi Python'daki is_gunu.py ile aynı kuralları kullanır (ayrı bir JS takvimi yoktur)."""
    def test_takvim_js_is_gunu_py_den_uretilmis(self):
        js = u.oku(os.path.join(u.ROOT, "assets", "takvim.js")); m = re.search(r"PlakaTakvim = \{ilkYil: (\d+), sonYil: (\d+), tatiller: (\[.*?\])\}", js)
        self.assertEqual((int(m[1]), int(m[2])), (ig.TAKVIM_ILK_YIL, ig.TAKVIM_SON_YIL)); self.assertEqual(json.loads(m[3]), sorted(t.isoformat() for t in ig.RESMI_TATIL))
        self.assertNotIn("tatiller", u.oku(os.path.join(u.ROOT, "assets", "tahmin-motoru.js")).split("trReferansGun")[0])      # motorda kopya takvim yok

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_js_referans_gun_python_onceki_is_gunu_ile_her_gun_ayni(self):
        kod = ("const fs=require('fs'),vm=require('vm');const c={Math,Date,console};vm.createContext(c);"
               "for(const f of ['takvim.js','tahmin-motoru.js'])vm.runInContext(fs.readFileSync('assets/'+f,'utf8'),c);"
               "const o=[];for(let g=Date.UTC(2024,0,1);g<=Date.UTC(2028,11,31);g+=864e5){c.__n=g+12*3600e3-3*3600e3;"   # TRT 12:00
               "const r=vm.runInContext('trReferansGun(__n)',c);o.push([new Date(g).toISOString().slice(0,10),r.iso,r.kapsamDisi]);}console.log(JSON.stringify(o));")
        sonuc = json.loads(subprocess.run([u.NODE, "-e", kod], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout); self.assertEqual(len(sonuc), 1827)
        for gun, ref, disi in sonuc:
            self.assertEqual(ref, ig.onceki_is_gunu(D.fromisoformat(gun)).isoformat(), gun); self.assertFalse(disi, gun)

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_kapsam_disi_isaretlenir_ve_takvim_yoksa_hafta_sonu_kurali(self):
        kod = ("const fs=require('fs'),vm=require('vm');function ctx(takvim){const c={Math,Date,console};vm.createContext(c);if(takvim)vm.runInContext(fs.readFileSync('assets/takvim.js','utf8'),c);"
               "vm.runInContext(fs.readFileSync('assets/tahmin-motoru.js','utf8'),c);return c;}"
               "const t=(c,y,m,d,h)=>{c.__n=Date.UTC(y,m-1,d,h);return vm.runInContext('trReferansGun(__n)',c);};const a=ctx(true),b=ctx(false);"
               "console.log(JSON.stringify([t(a,2029,1,3,9),t(a,2028,12,29,9),t(a,2023,12,31,9),t(b,2026,10,31,9),t(b,2027,1,1,9)]));")
        r = json.loads(subprocess.run([u.NODE, "-e", kod], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout)
        self.assertTrue(r[0]["kapsamDisi"]); self.assertFalse(r[1]["kapsamDisi"]); self.assertTrue(r[2]["kapsamDisi"])        # 2029 ve 2023: açıkça kapsam dışı
        self.assertEqual((r[3]["iso"], r[3]["kapsamDisi"]), ("2026-10-30", True))                                          # takvim yok: hafta sonu kuralı + kapsam dışı işareti
        self.assertEqual((r[4]["iso"], r[4]["kapsamDisi"]), ("2027-01-01", True))                                          # takvim yokken tatil bilinemez: sessizce doğru sayılmaz

class SayfaIciTutarlilik(unittest.TestCase):
    """Node (takvim + ortak motor + il-arac.js): il başlık tahmini = ana sayfanın estimateAt(referans gün) değeri; etiket referans gün."""
    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_81_ilde_referans_gun_kurali_gece_yarisi_hafta_sonu_tatil_ve_saat_dilimleri(self):
        sayfalar = tum_sayfalar(); self.assertEqual(len(sayfalar), 81); referans = None
        for tz in TZLER:
            tum = {}
            for yol in sayfalar:
                for (a, gercek, ref, ack), r in zip(ANLAR, u.canli_sonuc(yol, [x[0] for x in ANLAR], tz=tz)):
                    ad = os.path.basename(yol); self.assertIsNone(r["hata"], (tz, ad, ack)); self.assertEqual(r["ana"]["tr"], gercek.isoformat(), (tz, ack))   # Türkiye takvim günü doğru
                    self.assertEqual(r["ana"]["iso"], ref.isoformat(), (tz, ack)); self.assertEqual(r["canli"]["tarih"], tr(ref), (tz, ad, ack))
                    self.assertEqual(r["canli"]["plaka"], r["ana"]["plaka"], (tz, ad, ack)); self.assertRegex(r["canli"]["plaka"], r"^\d\d [A-Z]{3} \d{3}$"); self.assertEqual(r["canli"]["grup"], r["canli"]["plaka"].split()[1][0])
                    self.assertIsNone(r["uyari"], (tz, ack)); self.assertFalse(r["ana"]["kapsamDisi"])
                    tum[(ad, a)] = (r["canli"]["plaka"], r["canli"]["tarih"], r["bayat"])
            if referans is None: referans = tum
            else: self.assertEqual(tum, referans, f"{tz}: tarayıcı saat diliminden bağımsız olmalı")

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_81_ilde_cuma_cumartesi_pazar_ayni_pazartesi_ileri(self):
        cuma, cts, paz, paz_gece, pzt = (an(2026, 10, 30, 20, 59, 59), an(2026, 10, 31, 12), an(2026, 11, 1, 12), an(2026, 11, 1, 20, 59, 59), an(2026, 11, 2, 12))
        for yol in tum_sayfalar():
            r = u.canli_sonuc(yol, [cuma, an(2026, 10, 30, 21), cts, paz, paz_gece, pzt]); ad = os.path.basename(yol)
            for x in r[1:5]:
                self.assertEqual((x["canli"]["plaka"], x["canli"]["tarih"], x["ana"]["n"], x["ana"]["plaka"]), (r[0]["canli"]["plaka"], r[0]["canli"]["tarih"], r[0]["ana"]["n"], r[0]["ana"]["plaka"]), ad)     # Cuma = Cumartesi = Pazar (tam plaka ve sıra numarası dahil, sayısal olarak da aynı)
            self.assertEqual(r[0]["canli"]["tarih"], "30 Ekim 2026", ad); self.assertEqual(r[5]["canli"]["tarih"], "2 Kasım 2026", ad); self.assertGreater(r[5]["ana"]["n"], r[0]["ana"]["n"], ad); self.assertNotEqual(r[5]["canli"]["plaka"], r[0]["canli"]["plaka"], ad)          # Pazartesi: yeni iş günü, tam plaka (sıra numarası) ilerler

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_29_ekim_resmi_tatilinde_28_ekim_tahmini_81_il(self):
        d = u.kopya()
        try:
            r0 = u.uret(d, "--bugun", "2026-10-28"); self.assertEqual(r0.returncode, 0, r0.stderr)         # sayfalar 28 Ekim (Çarşamba) referansıyla
            cars, per, cum = an(2026, 10, 28, 9), an(2026, 10, 29, 9), an(2026, 10, 30, 9)
            for yol in sorted(glob.glob(os.path.join(d, "il", "*.html"))):
                a, b, c = u.canli_sonuc(yol, [cars, per, cum]); ad = os.path.basename(yol)
                self.assertEqual((b["canli"]["plaka"], b["canli"]["tarih"], b["ana"]["n"]), (a["canli"]["plaka"], "28 Ekim 2026", a["ana"]["n"]), ad)   # 29 Ekim (tatil) = 28 Ekim
                self.assertEqual(b["ana"]["iso"], "2026-10-28"); self.assertEqual(c["canli"]["tarih"], "30 Ekim 2026")
        finally: shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_baslangictan_onceki_saatte_baslangic_tarihiyle_tutarli(self):
        yol = os.path.join(u.ROOT, "il", "konya.html"); bas = D.fromisoformat(u.sayfa_bilgisi(yol))
        r = u.canli_sonuc(yol, [an(bas.year, bas.month, bas.day, 12) - 5 * 86400000])[0]
        self.assertEqual(r["canli"]["tarih"], tr(bas)); self.assertEqual(r["ana"]["iso"], ig.onceki_is_gunu(bas - dt.timedelta(days=5)).isoformat())

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_python_statik_ile_js_ayni_gun_en_fazla_1_sira(self):
        """Üretimde Python'un yazdığı statik başlık tahmini (tam plaka) ile aynı referans günün JS (ortak motor) tahmini BİREBİR aynı olmalı (sıra numarası dahil, tolerans yok).
        Ham tahmin iki tarafta bit-bit aynıdır; eski sapmanın nedeni Python round() (yarım değer çifte) ile JS Math.round (yarım yukarı) farkıydı (test_tam_plaka.py ayrıntılı)."""
        for s in veri():
            h = sayfa(s["il"]); bas = D.fromisoformat(re.search(r'data-baslangic="([^"]+)"', h)[1]); o = [tuple(x) for x in s["obs"]]; g, n = o[-1]
            self.assertEqual(bas, ig.onceki_is_gunu(bas))                                                   # üretim referans günü iş günü
            ham = n + fc.advance(o, fc.clean(o), g, (bas - (E0 + dt.timedelta(days=g))).days, fc.slope(o, g))
            r = u.canli_sonuc(os.path.join(u.ROOT, "il", slug(TAM.get(s["il"], s["il"])) + ".html"), [an(bas.year, bas.month, bas.day, 9)])[0]
            self.assertEqual(r["ana"]["n"], ham, s["il"])                                                    # ham tahmin bit-bit aynı
            statik = re.search(r'data-live="plaka">([^<]*)<', h)[1]
            self.assertEqual(statik, r["ana"]["plaka"], s["il"]); self.assertEqual(statik, r["canli"]["plaka"], s["il"])

class UretimTarihi(unittest.TestCase):
    def test_python_uretim_gunu_turkiye_tarihinin_onceki_is_gunu_ve_saat_diliminden_bagimsiz(self):
        d = u.kopya()
        try:
            for tz in ("Pacific/Kiritimati", "America/Los_Angeles"):
                once = dt.datetime.now(TRT).date(); env = dict(os.environ, TZ=tz)
                r = subprocess.run([sys.executable, "generate_il_pages.py", "--iller", "konya"], cwd=d, capture_output=True, text=True, env=env); self.assertEqual(r.returncode, 0, r.stderr)
                sonra = dt.datetime.now(TRT).date(); bas = D.fromisoformat(u.sayfa_bilgisi(os.path.join(d, "il", "konya.html")))
                self.assertIn(bas, (ig.onceki_is_gunu(once), ig.onceki_is_gunu(sonra)), f"{tz}: üretim referans günü Türkiye tarihinin önceki iş günü olmalı")
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_uretim_hafta_sonu_ve_tatilde_onceki_is_gunune_ceker_gozlem_tarihi_ayri(self):
        d = u.kopya()
        try:
            for bugun, ref in (("2026-10-30", "2026-10-30"), ("2026-10-31", "2026-10-30"), ("2026-11-01", "2026-10-30"), ("2026-11-02", "2026-11-02"), ("2026-10-29", "2026-10-28"),
                               ("2027-01-01", "2026-12-31"), ("2027-03-09", "2027-03-08"), ("2027-05-16", "2027-05-14")):
                r = u.uret(d, "--bugun", bugun, "--iller", "konya"); self.assertEqual(r.returncode, 0, r.stderr)
                yol = os.path.join(d, "il", "konya.html"); h = u.oku(yol); self.assertEqual(u.sayfa_bilgisi(yol), ref, bugun)
                y, m, g = map(int, ref.split("-")); self.assertIn(f'<span data-live="tarih">{tr(D(y, m, g))}</span> itibarıyla · tahmindir', h)
                self.assertIn('<dt>Son kayıtlı gözlem</dt><dd class="v mono nw">42 BJA 124</dd><dd class="k">23 Ekim 2026</dd>', h)     # gözlem tarihi kuraldan bağımsız
            # aynı referans günündeki statik seri hafta sonu üretimiyle Cuma üretiminde aynıdır
            seri = {}
            for bugun in ("2026-10-30", "2026-10-31", "2026-11-01"):
                u.uret(d, "--bugun", bugun, "--iller", "konya"); seri[bugun] = re.search(r'data-live="plaka">([^<]*)<', u.oku(os.path.join(d, "il", "konya.html")))[1]
            self.assertEqual(len(set(seri.values())), 1, seri)
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_takvim_kapsam_korumasi_uretimi_durdurur(self):
        d = u.kopya()
        try:
            for b in ("2028-07-04", "2029-01-03"):
                r = u.uret(d, "--bugun", b, "--iller", "konya"); self.assertNotEqual(r.returncode, 0, b); self.assertIn("HATA", r.stderr); self.assertIn("BAYRAMLAR", r.stderr)
                self.assertFalse(os.path.exists(os.path.join(d, "il", "konya.html")), b); self.assertFalse(os.path.exists(os.path.join(d, "sitemap.xml")), b)
            self.assertEqual(u.uret(d, "--bugun", "2028-07-03", "--iller", "konya").returncode, 0)
        finally: shutil.rmtree(d, ignore_errors=True)

@unittest.skipUnless(CHROME, "Chrome yok")
class TarayiciAnaSayfaIlSayfasi(unittest.TestCase):
    ANLAR_TR = ANLAR + [(an(2026, 10, 29, 9), D(2026, 10, 29), D(2026, 10, 28), "29 Ekim 2026 (resmî tatil, Perşembe) -> 28 Ekim (yalnızca ana sayfa: il sayfası başlangıç tarihinden önce)")]
    def _calistir(self, tz=None):
        iller = [{"il": s["il"], "slug": slug(TAM.get(s["il"], s["il"]))} for s in veri()]; bas = D.fromisoformat(u.sayfa_bilgisi(os.path.join(u.ROOT, "il", "konya.html")))
        d = tempfile.mkdtemp(prefix="plaka_tarih_", dir=u.ROOT)
        try:
            with open(os.path.join(u.ROOT, "tests", "ui", "tarih_parite.html"), encoding="utf-8") as f: h = f.read()
            h = h.replace("__ILLER__", json.dumps(iller, ensure_ascii=False)).replace("__ANLAR__", json.dumps([a[0] for a in self.ANLAR_TR])).replace("__BASLANGIC__", str(an(bas.year, bas.month, bas.day, 0) - 3 * 3600 * 1000))
            with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(h)
            class H(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k): pass
                def do_GET(self):
                    yol = self.path.split("?")[0]
                    if "." not in os.path.basename(yol) and os.path.isfile(os.path.join(u.ROOT, yol.lstrip("/") + ".html")): self.path = yol + ".html"       # cleanUrls
                    super().do_GET()
            s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); port = s_.getsockname()[1]; s_.close()
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
            env = dict(os.environ)
            if tz: env["TZ"] = tz
            try: r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=400000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=600, env=env)
            finally: srv.shutdown(); srv.server_close()
            m = re.search(r"SONUC (\[.*?\])\s*</pre>", r.stdout, re.S); self.assertIsNotNone(m, r.stderr[-400:])
            return json.loads(html.unescape(m[1]))
        finally: shutil.rmtree(d, ignore_errors=True)

    def _kontrol(self, sonuc):
        ref = {a: r for a, _, r, _ in self.ANLAR_TR}; self.assertEqual(len(sonuc), 81 * len(self.ANLAR_TR))
        for r in sonuc:
            gun = ref[r["an"]]
            self.assertEqual(r["anaDt"], gun.isoformat(), r); self.assertFalse(r["anaGizli"], r)         # ana sayfa tarih alanı = referans gün (Python onceki_is_gunu ile aynı); sonuç gösterilmiş
            if r["kart"]:                                                                  # ana sayfa kartı: seri ve tarih, ana sayfa aracı/il sayfasıyla aynı referans gün ve motor
                self.assertEqual(r["kart"]["plaka"], " ".join(r["ana"].split()[:3]), r); self.assertEqual(r["kart"]["tarih"], tr(gun), r)
            if r["plaka"] is None: continue                                                 # başlangıçtan önceki saat: yalnızca ana sayfa
            self.assertEqual(r["tarih"], tr(gun), r)                                       # il sayfası etiketi aynı referans gün
            self.assertEqual(r["plaka"], " ".join(r["ana"].split()[:3]), r)                # il büyük tahmini (tam plaka) = ana sayfa güncel tahmini
            self.assertFalse(r["uyari"], r)
        self.assertEqual({r["il"] for r in sonuc if r["kart"]}, {"İstanbul", "Ankara", "İzmir"})
        for il in {r["il"] for r in sonuc}:                                                # hafta sonu = Cuma (ana sayfa plakası numarasıyla birebir)
            p = {r["an"]: r["ana"] for r in sonuc if r["il"] == il}
            self.assertEqual({p[a] for a in (ANLAR[0][0], ANLAR[1][0], ANLAR[2][0], ANLAR[3][0], ANLAR[4][0])}, {p[ANLAR[0][0]]}, il); self.assertNotEqual(p[ANLAR[5][0]], p[ANLAR[0][0]], il)

    def test_ana_sayfa_ve_il_sayfasi_81_ilde_ayni_referans_gun_ayni_tahmin(self): self._kontrol(self._calistir())
    def test_tarayici_saat_diliminden_bagimsiz(self): self._kontrol(self._calistir("Pacific/Kiritimati"))      # UTC+14: yerel takvim günü Türkiye gününden farklı

if __name__ == "__main__": unittest.main()
