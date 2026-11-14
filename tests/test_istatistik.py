"""İstatistik sayfası (/istatistik: istatistik.html + assets/istatistik.js): saf hesap katmanı (Node; bağımsız Python referansıyla karşılaştırma),
sayfa yapısı ve diğer sayfalardaki tek satır bağlantı, gerçek tarayıcıda (Chrome headless) çizim/etkileşim.
Veri her hafta güncellendiği için güncel değerler sabitlenmez: değerler Python referansından ya da değişmeyen geçmişten (2024–2025) gelir."""
import bisect, datetime as dt, functools, glob, html, http.server, json, os, re, shutil, socket, statistics, subprocess, sys, tempfile, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_ana_sayfa_regresyon import CHROME, CHROME_TEMEL
from test_sitemap import lm, ANA as ANA_URL

SAYFA = u.oku(os.path.join(u.ROOT, "istatistik.html"))
JS = u.oku(os.path.join(u.ROOT, "assets", "istatistik.js"))
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
VERI = json.loads(u.oku(os.path.join(u.ROOT, "data", "tahmin_data.json")))
E0 = dt.date.fromisoformat(VERI["epoch"])
GENISLIKLER = [320, 390, 768, 1280]
BAGLANTI_METNI = "Plaka istatistikleri ve grafikler"
def gun(y, m, d=1): return (dt.date(y + (m - 1) // 12, (m - 1) % 12 + 1, d) - E0).days
def il_listesi(): return json.loads(subprocess.run([u.NODE, "-e", "console.log(JSON.stringify(require('./api/_iller.js')))"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout)
def node(kod):
    """assets/istatistik.js'i Node'da yükler (P), veriyi hazırlar (V) ve verilen ifadenin JSON çıktısını döndürür."""
    r = subprocess.run([u.NODE, "-e", "const P=require('./assets/istatistik.js'),V=P.hazirla(require('./data/tahmin_data.json'));const il=k=>V.iller.find(x=>x.kod===k).seri;console.log(JSON.stringify(" + kod + "))"],
                       cwd=u.ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout)

# --- bağımsız Python referansı (assets/istatistik.js hamSeri/ulkeCarpani/temizle/deger ile aynı kural, ayrı yazım) --------------------
def ara(g, v, x):
    if x < g[0] or x > g[-1]: return None
    i = bisect.bisect_left(g, x)
    return v[i] if g[i] == x else v[i - 1] + (v[i] - v[i - 1]) * (x - g[i - 1]) / (g[i] - g[i - 1])
def ref_ham(obs):
    o = [x for i, x in enumerate(obs) if i == 0 or x[0] > obs[i - 1][0]]; n = len(o)
    hiz = [0] + [(o[i][1] - o[i - 1][1]) / (o[i][0] - o[i - 1][0]) for i in range(1, n)]
    return {"g": [x[0] for x in o], "v": [x[1] for x in o], "hiz": hiz, "yerel": [0] + [max(0, statistics.median(hiz[max(1, i - 10):min(n, i + 11)])) for i in range(1, n)]}
HAM = {x["kod"]: ref_ham(x["obs"]) for x in VERI["iller"]}
@functools.lru_cache(maxsize=None)
def ref_carpan(a, b):
    """Ülke çarpanı: [a, b] aralığında illerin ham ilerlemesinin kendi yerel hızına oranının medyanı (20'den az il varsa 1)."""
    q = []
    for h in HAM.values():
        x, y = ara(h["g"], h["v"], a), ara(h["g"], h["v"], b)
        if x is None or y is None: continue
        i = 1
        while i < len(h["g"]) - 1 and h["g"][i] < (a + b) / 2: i += 1
        if h["yerel"][i] > 0: q.append((y - x) / (h["yerel"][i] * (b - a)))
    return max(0, statistics.median(q)) if len(q) >= 20 else 1
def ref_temizle(h):
    G, V, Y, n = h["g"], h["v"], h["yerel"], len(h["g"]); g, v, atlama = [G[0]], [float(V[0])], []
    gun = lambda i: G[i] - G[i - 1]; fark = lambda i: V[i] - V[i - 1]; durak = lambda j: 1 <= j < n and 0 <= fark(j) < 0.5 * Y[j] * gun(j)
    for i in range(1, n):
        dt_, f, yerel = gun(i), fark(i), Y[i]; yeni = f
        if f < 0: yeni = yerel * dt_ if f < -800 else 0; atlama.append((G[i - 1], G[i], "kirilma", None))
        elif f - yerel * dt_ > 800:
            c = max(1, ref_carpan(G[i - 1], G[i])); bek = yerel * dt_ * c; netler = [f - bek]; sol = sag = 0
            while sol < 2 and durak(i - 1 - sol): sol += 1
            while sag < 2 and durak(i + 1 + sag): sag += 1
            for l in range(sol + 1):
                for r in range(sag + 1):
                    if l or r: a, b = G[i - 1 - l], G[i + r]; netler.append(V[i + r] - V[i - 1 - l] - yerel * (b - a) * max(0.5, ref_carpan(a, b)))
            net = min(netler); kat = int(net / 1000 + 0.5) if net > 0 else 0                                                          # JS Math.round (pozitifte yarım yukarı)
            if bek <= 1000 and f >= 2 * bek and net >= 800 and kat >= 1 and abs(net - 1000 * kat) <= min(450, 100 + 0.35 * bek): yeni = max(0, f - 1000 * kat); atlama.append((G[i - 1], G[i], "seri", kat))
            elif h["hiz"][i] > 6 * max(yerel * c, 0.5) and net > 800: yeni = yerel * dt_; atlama.append((G[i - 1], G[i], "sicrama", None))
        g.append(G[i]); v.append(v[-1] + yeni)
    return g, v, atlama
def ref_deger(s, x): return ara(s[0], s[1], x)
def ref_artis(s, a, b):
    x, y = ref_deger(s, a), ref_deger(s, b); return None if x is None or y is None else y - x
REF = {k: ref_temizle(h) for k, h in HAM.items()}
SON = max(x["obs"][-1][0] for x in VERI["iller"]); ILK = min(x["obs"][0][0] for x in VERI["iller"])

@unittest.skipUnless(u.NODE, "Node yok")
class SafHesap(unittest.TestCase):
    def yakin(self, a, b, m=None):
        if a is None or b is None: self.assertEqual(a, b, m)
        else: self.assertAlmostEqual(a, b, delta=1e-6 * max(1, abs(b)), msg=m)

    def test_temizlik_81_ilde_python_referansiyla_ayni(self):
        js = node("V.iller.map(x=>({kod:x.kod,g:x.seri.g,v:x.seri.v,atlama:x.seri.atlama.map(t=>[t.a,t.b,t.tur,t.kat||null])}))"); self.assertEqual(len(js), 81)
        turler = {}
        for x in js:
            g, v, atlama = REF[x["kod"]]; self.assertEqual(x["g"], g, x["kod"]); self.assertEqual([tuple(t) for t in x["atlama"]], atlama, x["kod"])
            for t in atlama: turler[t[2]] = turler.get(t[2], 0) + 1
        self.assertGreaterEqual(turler["seri"], 60); self.assertGreaterEqual(turler["kirilma"], 8); self.assertGreaterEqual(turler["sicrama"], 5)       # üç tür de veride var (sayılar yeni veriyle artabilir)
        for x in js:
            g, v, atlama = REF[x["kod"]]
            for p, q in zip(x["v"], v): self.yakin(p, q, x["kod"])
            self.assertTrue(all(b >= a for a, b in zip(x["v"], x["v"][1:])), x["kod"])                                   # temizlenmiş seri hiç geri gitmez

    def test_bilinen_atlamalar_temizlenir_atlamasiz_aralik_hama_esittir(self):
        ham = {x["kod"]: dict(map(tuple, x["obs"])) for x in VERI["iller"]}; isaret = lambda kod: {(a, b): (tur, kat) for a, b, tur, kat in REF[kod][2]}
        # İstanbul 20→21 Ağustos 2024: +485.260 (harf grubu geçişi; büyük sıçrama → yerel hız); Kütahya Eylül–Ekim 2025: kayıt kırılması (−94.775 → yerel hız)
        for kod, a, b, tur, en_cok in ((34, gun(2024, 8, 20), gun(2024, 8, 21), "sicrama", 6000), (43, gun(2025, 9, 8), gun(2025, 10, 3), "kirilma", 6000)):
            self.assertEqual(isaret(kod)[(a, b)], (tur, None), kod); t = node(f"[P.artis(il({kod}),{a},{b}),P.atlamali(il({kod}),{a},{b}),P.atlamali(il({kod}),{a - 9},{a})]")
            self.assertGreater(t[0], 0, kod); self.assertLess(t[0], en_cok, kod); self.assertEqual(t[1:], [True, False], kod)
        self.assertLess(node(f"P.donemDegeri(il(34),{gun(2024, 8)},{gun(2024, 9)}).v"), 120000)                           # Ağustos 2024 İstanbul: atlama dönemi şişirmez (tek günlük ham fark > 400.000)
        self.assertGreater(ham[34][gun(2024, 8, 21)] - ham[34][gun(2024, 8, 20)], 400000)
        # Seri imzası: fazlalık 1.000'in katıysa TAM o kat düşülür, gerisi gerçek ilerleme olarak kalır.
        # Tunceli 23→24 Haziran 2025: +1.012 → 12; Yozgat 11→25 Eylül 2026: 14 günde +1.691 (olağanın ~3 katı, eski "6 kat" kuralının kaçırdığı) → 691; Aydın 8→9 Nisan 2024: +21.088 (21 seri) → 88
        for kod, a, b, kat in ((62, gun(2025, 6, 23), gun(2025, 6, 24), 1), (66, gun(2026, 9, 11), gun(2026, 9, 25), 1), (9, gun(2024, 4, 8), gun(2024, 4, 9), 21)):
            f = ham[kod][b] - ham[kod][a]; self.assertEqual(isaret(kod)[(a, b)], ("seri", kat), kod); self.yakin(node(f"P.artis(il({kod}),{a},{b})"), f - 1000 * kat)
        eylul = node(f"[2025,2026].map(y=>P.donemDegeri(il(66),P.gunNo(y,9,1),P.gunNo(y,10,1)).v)"); self.assertLess(abs(eylul[1] / eylul[0] - 1), 0.15)   # Yozgat Eylül 2026: +%63 değil, geçen yıla yakın
        # Telafi atlama DEĞİLDİR: Aydın 12→19 Şubat 2025 hiç ilerlememiş görünür (bayat tablo), 19→20 Şubat'ta +1.092; toplam doğrudur, dokunulmaz
        a, b, c = gun(2025, 2, 12), gun(2025, 2, 19), gun(2025, 2, 20); self.assertEqual([ham[9][b] - ham[9][a], ham[9][c] - ham[9][b]], [0, 1092])
        self.assertNotIn((b, c), isaret(9)); self.assertEqual(node(f"[P.artis(il(9),{a},{b}),P.artis(il(9),{b},{c}),P.atlamali(il(9),{a},{c})]"), [0, 1092, False])
        # Ülke çapında dalga atlama DEĞİLDİR: 1→2 Ekim 2024'te illerin çoğu olağanın ~4 katı ilerler (ülke çarpanı > 3); İzmir +1.911 ve İstanbul +6.306 olduğu gibi kalır
        a, b = gun(2024, 10, 1), gun(2024, 10, 2); self.assertGreater(ref_carpan(a, b), 3); self.yakin(node(f"P.ulkeCarpani(V.iller.map((x,i)=>P.hamSeri(require('./data/tahmin_data.json').iller[i].obs)))({a},{b})"), ref_carpan(a, b))
        for kod in (35, 34): self.assertNotIn((a, b), isaret(kod)); self.yakin(node(f"P.artis(il({kod}),{a},{b})"), ham[kod][b] - ham[kod][a])
        # atlama işareti olmayan bir aralıkta temizlenmiş fark = ham gözlem farkı (Ankara, Mart 2026: iki gözlem günü arası)
        gunler = [g for g in REF[6][0] if gun(2026, 3) <= g < gun(2026, 4)]; a, b = gunler[0], gunler[-1]
        self.assertFalse(any(x < b and y > a for x, y, _, _ in REF[6][2])); self.yakin(node(f"P.artis(il(6),{a},{b})"), ham[6][b] - ham[6][a])

    def test_deger_ve_artis_interpolasyon_ve_kapsam(self):
        gunler = [ILK, ILK + 1, gun(2024, 12, 31), gun(2025, 2, 28), gun(2025, 7, 17), SON - 3, SON]
        js = node("[%s].map(k=>[%s].map(g=>P.deger(il(k),g)))" % (",".join(str(k) for k in (6, 34, 62, 43)), ",".join(map(str, gunler))))
        for k, satir in zip((6, 34, 62, 43), js):
            for g, v in zip(gunler, satir): self.yakin(v, ref_deger(REF[k], g), (k, g))
        self.assertEqual(node(f"[P.deger(il(6),{ILK - 1}),P.deger(il(6),{SON + 1}),P.artis(il(6),{ILK - 5},{ILK + 5}),P.artis(il(6),{SON - 5},{SON + 5})]"), [None] * 4)   # kapsam dışına uzatma yok

    def test_takvim_ve_donem_sinirlari(self):
        self.assertEqual(node("[P.gunNo(2024,1,1),P.gunNo(2024,3,1),P.gunNo(2025,1,1),P.gunNo(2025,13,1),P.tarih(59),P.tarih(60),P.yilOnce(P.gunNo(2026,11,13)),P.yilOnce(P.gunNo(2024,2,29))]"),
                         [0, 60, 366, 731, {"y": 2024, "m": 2, "d": 29}, {"y": 2024, "m": 3, "d": 1}, gun(2025, 11, 13), (dt.date(2023, 3, 1) - E0).days])
        self.assertEqual(node("['ay','ceyrek','yil','hafta'].map(t=>[P.donemSiniri(t,2025,0),P.donemSiniri(t,2025,t==='hafta'?51:t==='ay'?11:t==='ceyrek'?3:0)])"),
                         [[[gun(2025, 1), gun(2025, 2)], [gun(2025, 12), gun(2026, 1)]], [[gun(2025, 1), gun(2025, 4)], [gun(2025, 10), gun(2026, 1)]],
                          [[gun(2025, 1), gun(2026, 1)]] * 2, [[gun(2025, 1), gun(2025, 1) + 7], [gun(2025, 1) + 357, gun(2025, 1) + 364]]])

    def test_yilin_ayni_donemleri_referansla_ayni_kismi_ve_kapsam_disi(self):
        son_t = E0 + dt.timedelta(days=SON)
        for kod in (6, 34, 62):
            for tur, n in (("ay", 12), ("ceyrek", 4), ("hafta", 52)):
                D = node(f"P.yilDonemleri(il({kod}),'{tur}')"); self.assertEqual(D["n"], n); self.assertEqual(D["yillar"], list(range(max(2024, son_t.year - 3), son_t.year + 1)))
                for y in D["yillar"]:
                    for k, h in enumerate(D["hucre"][str(y)]):
                        a, b = (gun(y, k + 1), gun(y, k + 2)) if tur == "ay" else (gun(y, 3 * k + 1), gun(y, 3 * k + 4)) if tur == "ceyrek" else (gun(y, 1) + 7 * k, gun(y, 1) + 7 * k + 7)
                        if a < ILK or a >= SON: self.assertIsNone(h["v"], (kod, tur, y, k))                                # ilk gözlemden önce başlayan ya da henüz başlamamış dönem
                        elif b > SON:
                            self.assertTrue(h["kismi"]); self.assertEqual(h["bit"], SON)
                            if tur == "hafta": self.assertIsNone(h["v"])                                                   # haftalık eğride yalnızca tamamlanan haftalar
                            else:
                                self.yakin(h["v"], ref_artis(REF[kod], a, SON)); oa, ob = gun(y - 1, son_t.month if tur == "ay" else 3 * k + 1), gun(y - 1, son_t.month, son_t.day)
                                self.assertEqual([h["onceA"], h["onceBit"]], [oa, ob]); self.yakin(h["onceAyni"], ref_artis(REF[kod], oa, ob))   # süren dönem: geçen yılın aynı takvim aralığı
                        else: self.assertFalse(h["kismi"]); self.yakin(h["v"], ref_artis(REF[kod], a, b), (kod, tur, y, k))
        ocak, subat, mart = node("P.yilDonemleri(il(6),'ay').hucre[2024].slice(0,3).map(h=>h.v)"); self.assertEqual([ocak, subat], [None, None]); self.assertGreater(mart, 0)   # kayıtlar 9 Şubat 2024'te başlar

    def test_son_haftalar_ozet_ve_kumulatif(self):
        for kod in (6, 62):
            s = REF[kod]; h = node(f"P.sonHaftalar(il({kod}),52)"); self.assertEqual(len(h), 52); self.assertEqual([h[-1]["a"], h[-1]["b"]], [SON - 7, SON])
            for i, x in enumerate(h):
                self.assertEqual(x["b"] - x["a"], 7); self.assertEqual(x["b"], SON - 7 * (51 - i)); self.yakin(x["v"], ref_artis(s, x["a"], x["b"])); self.yakin(x["once"], ref_artis(s, x["a"] - 364, x["b"] - 364))
            o = node(f"P.ozet(il({kod}))"); yb = gun((E0 + dt.timedelta(days=SON)).year, 1)
            self.yakin(o["elliIki"]["v"], sum(x["v"] for x in h)); self.yakin(o["hafta"]["v"], h[-1]["v"]); self.yakin(o["dortHafta"]["v"], sum(x["v"] for x in h[-4:]))
            self.yakin(o["yilBasi"]["v"], ref_artis(s, yb, SON)); self.yakin(o["hafta"]["yuzde"], (h[-1]["v"] / h[-1]["once"] - 1) * 100)
            K = node(f"P.kumulatif(il({kod}))"); self.assertNotIn(2024, [k["yil"] for k in K]); self.assertEqual(K[-1]["a"], yb)            # 2024: 1 Ocak kapsam dışı
            self.assertEqual(len(K[-1]["nokta"]), SON - yb + 1); self.assertEqual(K[-1]["nokta"][0], 0); self.yakin(K[-1]["nokta"][-1], o["yilBasi"]["v"])
            k25 = next(k for k in K if k["yil"] == 2025); self.assertEqual(len(k25["nokta"]), 366); self.yakin(k25["nokta"][-1], ref_artis(s, gun(2025, 1), gun(2026, 1)))

    def test_turkiye_toplami_illerin_toplamidir_ve_il_kiyasi(self):
        for a, b in ((gun(2025, 3), gun(2025, 4)), (gun(2025, 1), gun(2026, 1)), (SON - 28, SON)):
            self.yakin(node(f"P.artis(V.toplam,{a},{b})"), sum(ref_artis(REF[k], a, b) for k in REF))
        self.assertEqual(node("[V.ilk,V.son,V.iller.length]"), [ILK, SON, 81])
        a, b = gun(2025, 10), gun(2025, 11); K = node(f"P.ilKiyas(V.iller,{a},{b})"); self.assertEqual(len(K), 81)                         # Ekim 2025 ↔ Ekim 2024 (ikisi de tamamlanmış)
        for x in K:
            v, once = ref_artis(REF[x["kod"]], a, b), ref_artis(REF[x["kod"]], gun(2024, 10), gun(2024, 11)); self.yakin(x["v"], v); self.yakin(x["once"], once); self.assertFalse(x["kismi"])
            self.yakin(x["yuzde"], (v / once - 1) * 100 if once > 0 else None)
        self.assertEqual(max(K, key=lambda x: x["v"])["kod"], 34)
        ilk_ay = node(f"P.ilKiyas(V.iller,{gun(2024, 3)},{gun(2024, 4)}).map(x=>[x.v>0,x.once,x.yuzde])"); self.assertEqual(ilk_ay, [[True, None, None]] * 81)   # geçen yılı kapsam dışı: kıyas yok

    def test_donem_secenekleri_ve_bicimler(self):
        son_t = E0 + dt.timedelta(days=SON)
        for tur in ("ay", "ceyrek", "yil"):
            S = node(f"P.donemSecenekleri(V.ilk,V.son,'{tur}')"); self.assertTrue(all(ILK <= s["a"] < SON for s in S)); self.assertEqual([s["a"] for s in S], sorted((s["a"] for s in S), reverse=True))
            self.assertEqual([s["kismi"] for s in S], [s["b"] > SON for s in S]); self.assertEqual(S[0]["yil"], son_t.year)
        ay = node("P.donemSecenekleri(V.ilk,V.son,'ay')"); self.assertEqual(ay[-1]["ad"], "Mart 2024"); self.assertEqual(ay[0]["ad"], f"{node('P.AYLAR')[son_t.month - 1]} {son_t.year}")
        self.assertEqual(node("P.donemSecenekleri(V.ilk,V.son,'yil')")[-1]["ad"], "2025")                                                    # 2024 yılı 1 Ocak'ta başlar: kapsam dışı
        self.assertEqual(node("[P.sayi(1234567),P.sayi(-1234),P.sayi(999),P.yaklasik(37),P.yaklasik(1234),P.yaklasik(44737),P.yaklasik(null),P.yuzdeYaz(12.4),P.yuzdeYaz(-8.6),P.yuzdeYaz(0.2),P.yuzdeYaz(null)]"),
                         ["1.234.567", "−1.234", "999", "~37", "~1.230", "~44.700", "—", "+%12", "−%9", "±%0", "—"])
        self.assertEqual(node("[P.aralik(P.gunNo(2026,11,7),P.gunNo(2026,11,13)),P.aralik(P.gunNo(2026,10,28),P.gunNo(2026,11,3)),P.aralik(P.gunNo(2025,12,29),P.gunNo(2026,1,4))]"),
                         ["7–13 Kasım 2026", "28 Ekim – 3 Kasım 2026", "29 Aralık 2025 – 4 Ocak 2026"])
        self.assertEqual(node("[P.olcek(73000).cizgiler,P.olcek(0).ust,P.olcek(399999).ust,[0,2500,20000,1500000].map(P.eksenBicimi(1e4)),P.eksenBicimi(2e6)(1500000),P.eksenBicimi(8000)(2500)]"),
                         [[0, 20000, 40000, 60000, 80000], 1, 400000, ["0", "2,5 bin", "20 bin", "1500 bin"], "1,5 mn", "2.500"])

@unittest.skipUnless(u.NODE, "Node yok")
class SayfaVeBaglanti(unittest.TestCase):
    def test_sayfa_yapisi_il_listesi_ve_olcum(self):
        api = il_listesi(); secenekler = re.findall(r'<option value="(\d\d)" data-slug="([a-z]+)" data-ad="([^"]+)">([^<]+) \((\d\d)\)</option>', SAYFA)
        self.assertEqual(len(secenekler), 81); self.assertEqual(sorted((int(v), a, s) for v, s, a, _, _ in secenekler), sorted(map(tuple, api))); self.assertTrue(all(v == k and a == ad for v, _, a, ad, k in secenekler))
        self.assertIn('<option value="0">Türkiye (81 il toplamı)</option>', SAYFA)
        self.assertEqual(re.findall(r"<title>.*?</title>|<h1>.*?</h1>", SAYFA), ["<title>Plaka İstatistikleri — il il plaka artışı grafikleri · Plaka Tahmini</title>", "<h1>Plaka İstatistikleri</h1>"])
        self.assertIn('<link rel="canonical" href="https://plakatahmini.com/istatistik">', SAYFA); self.assertIn('<html lang="tr">', SAYFA); self.assertIn('<a href="/"><span aria-hidden="true">←</span> Ana sayfaya dön</a>', SAYFA)
        self.assertEqual(SAYFA.count('<!--OLCUM--><script src="/assets/olcum.js" defer></script><!--/OLCUM-->'), 1); self.assertEqual(SAYFA.count('<script src="/assets/istatistik.js" defer></script>'), 1)
        self.assertEqual(re.findall(r'<p class="olcum-notu">.*?</p>', SAYFA), re.findall(r'<p class="olcum-notu">.*?</p>', ANA))               # diğer sayfalarla aynı bilgilendirme
        self.assertNotRegex(SAYFA + JS, r"(?i)goatcounter\.com/count|gc\.zgo\.at|abacus|sendBeacon|XMLHttpRequest|PlakaOlcum"); self.assertEqual(re.findall(r"fetch\(([^)]*)\)", JS), ['"/data/tahmin_data.json"'])   # tek ağ isteği: gözlem verisi; özel analitik olayı yok
        self.assertNotRegex(JS, r"innerHTML|insertAdjacentHTML|document\.write|\beval\(")                                                     # tüm metinler textContent ile yazılır
        self.assertNotRegex(SAYFA, r"tahmin-motoru|takvim\.js|il-arac"); self.assertEqual(len(re.findall(r'<section class="grafik" id="g-(?:hafta|donem|kumulatif|iller)"', SAYFA)), 4)
        self.assertEqual(re.findall(r"const CIZGI_EN_COK = (\d+)", JS), ["3"])                                                                     # 3 çizgi: paletin yalnızca ilk üç rengi her çift için doğrulanmıştır
        for b in re.findall(r'<section class="grafik".*?</section>', SAYFA, re.S):                                                             # her grafik: başlık, açıklama, lejant, çizim alanı, tablo görünümü
            for parca in ("<h2 id=", '<p class="aciklama">', '<div class="lejant">', '<div class="cizim">', '<details class="tablo"><summary>Tabloyu göster</summary>', '<p class="dipnot" hidden>'): self.assertEqual(b.count(parca), 1, parca)
        self.assertEqual(re.findall(r'yil: \[([^\]]+)\]', JS), ['"#2a78d6", "#eb6834", "#1baf7a", "#eda100"'])                                 # doğrulanmış kategorik sıra (CVD ayrımı sıraya bağlı)
        # paylaşım önizlemesi etiketleri: adres canonical ile aynı, görsel depoda var
        og = dict(re.findall(r'<meta property="og:([a-z]+)" content="([^"]*)">', SAYFA)); self.assertEqual(sorted(og), ["description", "image", "locale", "title", "type", "url"])
        self.assertEqual([og["url"], og["image"], og["locale"], og["type"]], ["https://plakatahmini.com/istatistik", "https://plakatahmini.com/og.png", "tr_TR", "website"]); self.assertTrue(os.path.isfile(os.path.join(u.ROOT, "og.png")))
        self.assertEqual(re.findall(r'<meta name="twitter:([a-z]+)" content="([^"]*)">', SAYFA), [("card", "summary_large_image"), ("title", og["title"]), ("image", og["image"])])
        self.assertTrue(all(og[k] for k in og)); self.assertNotIn("&", og["title"] + og["description"])

    def test_sitemapte_yer_alir_lastmod_yeni_gozlemle_yenilenir(self):
        url = ANA_URL + "istatistik"; m = lm(os.path.join(u.ROOT, "sitemap.xml")); self.assertEqual(u.oku(os.path.join(u.ROOT, "sitemap.xml")).count("/istatistik<"), 1)
        son = E0 + dt.timedelta(days=SON); self.assertGreaterEqual(dt.date.fromisoformat(m[url]), son)                                           # sayfa en az son gözlem kadar yeni
        d = u.kopya(ekstra=("sitemap.xml", "il"), il_dizini=False); sm = os.path.join(d, "sitemap.xml"); gun_ = lambda n: (son + dt.timedelta(days=n)).isoformat()
        try:
            r = u.uret(d, "--bugun", gun_(3)); self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(lm(sm), m)                           # yeni gözlem yok: sonraki günlerde üretim lastmod'u oynatmaz
            with open(sm, "w", encoding="utf-8") as f: f.write(re.sub(r"  <url><loc>[^<]*/istatistik</loc>.*?</url>\n", "", u.oku(os.path.join(u.ROOT, "sitemap.xml"))))
            self.assertNotIn(url, lm(sm)); r = u.uret(d, "--bugun", gun_(4)); self.assertEqual(r.returncode, 0, r.stderr); yeni = lm(sm)
            self.assertEqual({k: v for k, v in yeni.items() if m.get(k) != v}, {url: gun_(4)}); self.assertEqual(len(yeni), 83)                   # sitemap'te yoksa üretim günüyle eklenir; başka hiçbir tarih değişmez
            yol = os.path.join(d, "data", "tahmin_data.json"); v = json.loads(u.oku(yol)); k = next(x for x in v["iller"] if x["il"] == "Konya"); k["obs"].append([k["obs"][-1][0] + 7, k["obs"][-1][1] + 1700])
            with open(yol, "w", encoding="utf-8") as f: f.write(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
            r = u.uret(d, "--bugun", gun_(8)); self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(lm(sm)[url], gun_(8))                 # yeni gözlem (son gözlem + 7 gün): üretim günü
            r = u.uret(d, "--bugun", gun_(12)); self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(lm(sm)[url], gun_(8))                # aynı veriyle yeniden üretim: korunur
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_ana_sayfa_ve_81_il_sayfasinda_tek_kutu_baglanti(self):
        """Yeşil tonda tek kutu (katkı kutusuyla aynı biçim, ayrı renk): araçların hemen altında, açılır bölümlerin üstünde — ana sayfada "Tahminler nasıl hesaplanıyor?",
        il sayfasında "Son plaka gözlemleri" satırının üstünde. Stil satır içidir; ortak CSS'e ve betiklere dokunulmaz."""
        KUTU = r'<p class="istatistik" style="margin:14px 0"><a href="%s" style="display:block;[^"]*border:1\.5px solid #2f9e73;[^"]*background:#e4f4ec;color:#0d5c3f;[^"]*"><span[^>]*>' + BAGLANTI_METNI + r'</span><span[^>]*>Haftalık ve aylık artış, illerle karşılaştırma</span></a></p>'
        self.assertRegex(ANA, r'<!--/ANA:TARIH-ARACI-->\n\n<!--ANA:ISTATISTIK-->\n' + KUTU % "/istatistik" + r'\n<!--/ANA:ISTATISTIK-->\n  <details class="bolum"><summary><h2>Tahminler nasıl hesaplanıyor\?</h2>')
        self.assertEqual(ANA.index('<details class="bolum">'), ANA.index("<!--/ANA:ISTATISTIK-->\n") + len("<!--/ANA:ISTATISTIK-->\n") + 2)                       # ilk açılır bölümün hemen üstü
        self.assertEqual(ANA.count("/istatistik"), 1); self.assertEqual(ANA.count(BAGLANTI_METNI), 1); self.assertLess(ANA.index("ANA:ISTATISTIK"), ANA.index("</main>"))
        sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81); esle = {s: k for k, _, s in il_listesi()}
        for yol in sayfalar:
            s = os.path.basename(yol)[:-5]; h = u.oku(yol)
            b = re.findall(r'</section>\n<!--ISTATISTIK-->' + KUTU % r'(/istatistik\?il=\d\d)' + r'<!--/ISTATISTIK-->\n<details class="bolum"><summary><h2>Son plaka gözlemleri</h2>', h)
            self.assertEqual(b, [f"/istatistik?il={esle[s]:02d}"], s); self.assertEqual(h.count("/istatistik"), 1, s)
            self.assertEqual(h.index('<details class="bolum">'), h.index("<!--/ISTATISTIK-->\n") + len("<!--/ISTATISTIK-->\n"), s)                               # ilk açılır bölümün hemen üstü, araçların altı
        # bağlantı satırı dışında sayfalara başka bir şey eklenmedi: ortak CSS'te, betiklerde ve başlıkta iz yok
        for h in [ANA] + [u.oku(p) for p in sayfalar]:
            kalan = re.sub(r"<!--(ANA:)?ISTATISTIK-->.*?<!--/(ANA:)?ISTATISTIK-->", "", h, flags=re.S); self.assertNotRegex(kalan, r'/istatistik|class="istatistik"|istatistik\.js|PlakaIstatistik')
            self.assertNotRegex(re.search(r"<style>.*?</style>", h, re.S)[0], r"\.istatistik")

    def test_baglanti_sitemap_lastmodunu_ve_ana_sayfa_izini_oynatmaz(self):
        d = u.kopya(ekstra=("sitemap.xml", "il"), il_dizini=False)
        try:
            once = lm(os.path.join(d, "sitemap.xml")); iz = lambda: re.search(r"<!--ANA:SURUM-->\s*(\w+)", u.oku(os.path.join(d, "index.html")))[1]; iz0 = iz()
            for yol, desen in ((os.path.join(d, "il", "konya.html"), r"<!--ISTATISTIK-->.*?<!--/ISTATISTIK-->\n"), (os.path.join(d, "index.html"), r'(?<=<!--ANA:ISTATISTIK-->\n).*?\n(?=<!--/ANA:ISTATISTIK-->)')):
                h = u.oku(yol); yeni = re.sub(desen, "", h, flags=re.S); self.assertNotEqual(yeni, h)                                          # bağlantı eklenmeden önceki hâl
                with open(yol, "w", encoding="utf-8") as f: f.write(yeni)
            son = E0 + dt.timedelta(days=SON); r = u.uret(d, "--bugun", (son + dt.timedelta(days=1)).isoformat()); self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(lm(os.path.join(d, "sitemap.xml")), once); self.assertEqual(iz(), iz0)
            self.assertIn('href="/istatistik?il=42"', u.oku(os.path.join(d, "il", "konya.html"))); self.assertIn('href="/istatistik"', u.oku(os.path.join(d, "index.html")))   # üretim bağlantıyı geri yazar
        finally: shutil.rmtree(d, ignore_errors=True)

# --- tarayıcı ------------------------------------------------------------------------------------------------------------------
def sunucu():
    durum = {"mod": "normal"}
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k): pass
        def end_headers(self): self.send_header("Cache-Control", "no-store"); super().end_headers()       # "bozuk" kipinde veri dosyası önbellekten gelmesin
        def do_GET(self):
            yol, _, q = self.path.partition("?")
            if yol == "/__mod": durum["mod"] = q.split("=")[1]; self.send_response(200); self.send_header("Content-Length", "0"); self.end_headers(); return
            if yol == "/data/tahmin_data.json" and durum["mod"] == "bozuk": self.send_response(500); self.send_header("Content-Length", "0"); self.end_headers(); return
            if "." not in os.path.basename(yol) and os.path.isfile(os.path.join(u.ROOT, yol.lstrip("/") + ".html")): self.path = yol + ".html" + (("?" + q) if q else "")     # vercel cleanUrls
            super().do_GET()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=u.ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port

@unittest.skipUnless(CHROME and u.NODE, "Chrome/Node yok")
class Tarayici(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp(prefix="plaka_ist_", dir=u.ROOT); srv, port = sunucu()
        try:
            with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(u.oku(os.path.join(u.ROOT, "tests", "ui", "istatistik.html")).replace("__GENISLIKLER__", json.dumps(GENISLIKLER)))
            r = subprocess.run([*CHROME_TEMEL, "--virtual-time-budget=300000", "--dump-dom", f"http://127.0.0.1:{port}/{os.path.basename(d)}/h.html"], capture_output=True, text=True, timeout=300)
        finally: srv.shutdown(); srv.server_close(); shutil.rmtree(d, ignore_errors=True)
        m = re.search(r"(SONUC|HATA) (.*?)\s*</pre>", r.stdout, re.S); assert m and m[1] == "SONUC", (m and html.unescape(m[2])[:800]) or (r.stderr[-400:] + r.stdout[-300:])
        cls.s = json.loads(html.unescape(m[2])); cls.son = E0 + dt.timedelta(days=SON); cls.yil_sayisi = cls.son.year - 2024 + 1

    def test_dort_genislikte_tasma_ve_etiket_cakismasi_yok(self):
        self.assertEqual([r["w"] for r in self.s["yerlesim"]], GENISLIKLER)
        for r in self.s["yerlesim"]:
            w = r["w"]; self.assertEqual(r["hatalar"], [], w); self.assertLessEqual(r["sw"], r["cw"], w); self.assertLessEqual(r["sw2"], r["cw"], w); self.assertEqual(r["kucukDugme"], 0, w)   # yatay kaydırma yok; dokunma hedefleri ≥ 40 px
            for ad in ("g-hafta", "g-donem", "g-kumulatif", "g-iller", "g-hafta-2", "g-donem-2", "g-iller-2", "g-donem-3", "g-iller-3", "g-kumulatif-2", "g-kumulatif-3"):
                g = r[ad]; self.assertTrue(g["sigiyor"], (w, ad)); self.assertEqual(g["tasanYazi"], [], (w, ad)); self.assertEqual(g["cakisan"], [], (w, ad)); self.assertTrue(g["etiket"], (w, ad)); self.assertGreater(len(g["tablo"]), 2, (w, ad))

    def test_grafiklerin_icerigi(self):
        ay_no = self.son.month; yillar = [str(y) for y in range(max(2024, self.son.year - 3), self.son.year + 1)]
        for r in self.s["yerlesim"]:
            w = r["w"]; h = r["g-hafta"]; self.assertEqual(h["sutun"], 13, w); self.assertEqual(h["cizgi"], 1); self.assertEqual(h["lejant"], ["Haftalık artış", "Bir yıl önceki aynı hafta"]); self.assertEqual(len(h["tablo"]), 14)
            self.assertTrue(h["aciklama"].startswith("Ankara · ")); self.assertEqual(r["g-hafta-2"]["sutun"], 52, w); self.assertEqual(len(r["g-hafta-2"]["tablo"]), 53)
            dn = r["g-donem"]; self.assertEqual(dn["lejant"][:len(yillar)], yillar, w); self.assertEqual(dn["tablo"][0], ["Dönem"] + yillar); self.assertEqual(len(dn["tablo"]), 13); self.assertEqual(dn["tablo"][1][:2], ["Ocak", "—"])
            dolu = sum(1 for satir in dn["tablo"][1:] for hucre in satir[1:] if hucre != "—"); self.assertEqual(dn["sutun"], dolu, w)          # her dolu hücreye bir sütun (taralı süren dönem dahil)
            self.assertEqual(sum(1 for satir in dn["tablo"][1:] for hucre in satir[1:] if "*" in hucre), 1); self.assertIn("*", dn["tablo"][ay_no][-1]); self.assertTrue(dn["lejant"][-1].startswith("süren dönem"), w)
            self.assertEqual(r["g-donem-2"]["cizgi"], len(yillar), w); self.assertEqual(r["g-donem-2"]["sutun"], 0); self.assertEqual(len(r["g-donem-2"]["tablo"]), 53); self.assertEqual(r["g-donem-2"]["lejant"], yillar)
            self.assertEqual(len(r["g-donem-3"]["tablo"]), 5); self.assertEqual([s[0] for s in r["g-donem-3"]["tablo"][1:]], ["Oca–Mar", "Nis–Haz", "Tem–Eyl", "Eki–Ara"])
            k = r["g-kumulatif"]; self.assertEqual(k["cizgi"], len(yillar) - 1, w); self.assertEqual(k["lejant"], yillar[:0:-1]); self.assertIn("2024 yılı bu grafikte yok", k["dipnot"])   # 2024 hariç her yıl bir çizgi
            il = r["g-iller"]; self.assertEqual(il["sutun"], 15, w); self.assertEqual(len(il["tablo"]), 16); self.assertTrue(il["tablo"][1][0].startswith("1. İstanbul")); self.assertIn("· 81 il", il["aciklama"])
            self.assertIn("2. Ankara", il["tablo"][2][0]); self.assertEqual(r["g-iller-2"]["sutun"], 81, w); self.assertEqual(len(r["g-iller-2"]["tablo"]), 82)
            yuzdeler = [int(s[3].replace("−", "-").replace("+", "").replace("±", "").replace("%", "")) for s in r["g-iller-2"]["tablo"][1:]]; self.assertEqual(yuzdeler, sorted(yuzdeler, reverse=True), w)   # % görünümü: büyükten küçüğe
            self.assertEqual(r["g-iller-2"]["lejant"], ["Geçen yılın aynı dönemine göre artış", "azalış"]); self.assertIn("(dönem sürüyor)", r["g-iller-3"]["aciklama"])

    def test_il_secimi_adres_ozet_ve_ipuclari(self):
        e = self.s["etkilesim"]; self.assertEqual(e["hatalar"], []); self.assertEqual([e["il"], e["ilBag"], e["ilBagMetin"]], ["06", "/il/ankara", "Ankara plaka tahmini →"])
        self.assertEqual(e["durum"], {"il": 6, "n": 13, "tur": "ay", "kTur": "ay", "kDonem": 1, "olcu": "adet", "goster": "ilk", "ek": [], "anaGizli": False, "anaRenk": 0, "bOlcek": "adet"}); self.assertEqual(e["basili"], ["13", "ay", "adet", "ay", "adet", "ilk"])
        tr = lambda t: f"{t.day} {node('P.AYLAR')[t.month - 1]} {t.year}"; self.assertEqual(e["veriTarihi"], f"Son veri: {tr(self.son)} · 81 il · ilk kayıt: 9 Şubat 2024")
        o = node("(o=>['hafta','dortHafta','yilBasi','elliIki'].map(k=>P.yaklasik(o[k].v)))(P.ozet(il(6)))"); self.assertEqual([x[1] for x in e["ozet"]], o)
        self.assertEqual([x[0] for x in e["ozet"]], ["Son hafta", "Son 4 hafta", f"{self.son.year} başından beri", "Son 52 hafta"]); self.assertTrue(all("%" in x[2] for x in e["ozet"]))
        self.assertTrue(e["ipucuHafta"].startswith(node("P.aralik(V.son-6,V.son)")), e["ipucuHafta"]); self.assertIn(o[0], e["ipucuHafta"]); self.assertIn("bir yıl önce", e["ipucuHafta"]); self.assertIn("Değişim: ", e["ipucuHafta"])
        self.assertIn(e["ipucuDonem"].split("\n")[0], node("P.AYLAR")); self.assertEqual(len(re.findall(r"~[\d.]+", e["ipucuDonem"])), self.yil_sayisi)                    # tek ipucunda tüm yıllar
        self.assertTrue(e["ipucuKumulatif"].startswith("1 Ocak – ")); self.assertIn("Önceki yıla göre", e["ipucuKumulatif"]); self.assertRegex(e["ipucuIller"], r"^\d+\. \S+ \(81 il içinde\)\n~")
        self.assertIsNone(e["ipucuEksenUstunde"])
        self.assertTrue(e["trAciklama"].startswith("Türkiye (81 il) · ")); self.assertEqual([e["trAdres"], e["trBagGizli"], e["tunceliAdres"]], ["", True, "?il=62"])
        self.assertEqual(e["tunceliVurgu"], 1); self.assertEqual(len(e["tunceliSatir"]), 1); self.assertNotRegex(e["tunceliSatir"][0], r"^(?:[1-9]|1[0-5])\. ")       # seçili il ilk 15'te değilse kendi sırasıyla eklenir
        self.assertEqual(e["ayAdet"], len(node("P.donemSecenekleri(V.ilk,V.son,'ay')"))); self.assertNotIn("sürüyor", e["aySecili"]); self.assertNotIn("sürüyor", e["ceyrekSecili"])   # varsayılan: son tamamlanan dönem
        self.assertIn("sürüyor", e["ceyrekSecenek"][0]); self.assertEqual(e["yilSecenek"][-1], "2025"); self.assertIn("(dönem sürüyor)", e["yilAciklama"])

    def test_birikim_grafigine_il_ekleme_en_cok_uc_cizgi(self):
        b = self.s["birikim"]; self.assertEqual(b["hatalar"], []); self.assertLessEqual(b["sw"], b["cw"]); MAVI, TURUNCU, YESIL = "#2a78d6", "#eb6834", "#1baf7a"; yil = self.son.year
        for ad in ("bos", "bir", "iki", "ucuncu", "oran", "ankaraCikti", "turkiyeEklendi", "anaIstanbul", "tek", "anaCikti", "ucIlAnasiz", "doluykenAnaDegisti", "yerAcilincaAna", "anaYineCikti", "anaGeriEklendi", "sonTek"):
            g = b[ad]["g"]; self.assertTrue(g["sigiyor"], ad); self.assertEqual(g["tasanYazi"] + g["cakisan"], [], ad); self.assertEqual(len(b[ad]["renkler"]), len(g["lejant"]), ad)   # her çizgiye bir lejant satırı
        bos = b["bos"]; self.assertEqual([bos["cipler"], bos["ek"], bos["secKapali"], bos["olcekGizli"], bos["secenek"]], [[], [], False, True, 82]); self.assertEqual(bos["g"]["lejant"], [str(yil), str(yil - 1)])   # tek il: yıllar; seçenek: yer tutucu + Türkiye + 80 il
        self.assertEqual(bos["ilkSecenek"], "Karşılaştırmak için il ekle…")
        bir = b["bir"]; self.assertEqual(bir["cipler"], [["ana", "Yozgat×", "rgb(42, 120, 214)", "Yozgat: karşılaştırmadan çıkar"], ["6", "Ankara×", "rgb(235, 104, 52)", "Ankara: karşılaştırmadan çıkar"]]); self.assertEqual([bir["ek"], bir["olcekGizli"], bir["secenek"]], [[{"kod": 6, "renk": 1}], False, 81])
        self.assertEqual([bir["g"]["lejant"], bir["renkler"]], [["Yozgat", "Ankara"], [MAVI, TURUNCU]]); self.assertTrue(bir["g"]["aciklama"].startswith(f"{yil} · ")); self.assertEqual(bir["g"]["tablo"][0], [f"{yil}: 1 Ocak’tan şu güne kadar", "Yozgat", "Ankara"])
        iki = b["iki"]; self.assertEqual([iki["g"]["lejant"], iki["renkler"]], [["Yozgat", "Ankara", "İstanbul"], [MAVI, TURUNCU, YESIL]]); self.assertEqual([iki["secKapali"], iki["secenek"], iki["ilkSecenek"]], [True, 1, "En çok 3 il karşılaştırılır"])
        self.assertEqual(iki["yuzdeEksen"], 0); self.assertEqual(b["ucuncu"], iki)                                                              # dördüncü çizgi eklenemez
        o = node("(k=>k[k.length-1].nokta)(P.kumulatif(il(66)))"); self.assertEqual(iki["g"]["tablo"][-1][1], node(f"P.yaklasik({o[-1]})"))
        self.assertRegex(b["ipucu"], r"^1 Ocak – \d+ \S+ %d\n" % yil); self.assertTrue(all(ad in b["ipucu"] for ad in ("Yozgat", "Ankara", "İstanbul", "Parantez içi: geçen yılın aynı gününe göre değişim.")))
        oran = b["oran"]; self.assertGreater(oran["yuzdeEksen"], 2); self.assertTrue(oran["g"]["dipnot"].startswith("Oran: ")); self.assertEqual(oran["renkler"], iki["renkler"]); self.assertNotIn("Parantez içi", b["ipucuOran"])
        toplam = node(f"P.artis(il(66),P.gunNo({yil - 1},1,1),P.gunNo({yil},1,1))"); self.assertEqual(oran["g"]["tablo"][-1][1], node(f"P.oranYaz({o[-1] / toplam * 100})"))   # oran = bu yılın birikimi / geçen yılın toplamı
        self.assertRegex(b["ipucuOran"], r"%[\d,]+\nYozgat \(~[\d.]+\)")
        c = b["ankaraCikti"]; self.assertEqual([c["ek"], c["g"]["lejant"], c["renkler"], c["secKapali"]], [[{"kod": 34, "renk": 2}], ["Yozgat", "İstanbul"], [MAVI, YESIL], False])   # kalan il rengini korur
        t = b["turkiyeEklendi"]; self.assertEqual([t["ek"], t["g"]["lejant"], t["renkler"]], [[{"kod": 34, "renk": 2}, {"kod": 0, "renk": 1}], ["Yozgat", "İstanbul", "Türkiye (81 il)"], [MAVI, YESIL, TURUNCU]])
        a = b["anaIstanbul"]; self.assertEqual([a["ek"], a["g"]["lejant"], a["renkler"]], [[{"kod": 0, "renk": 1}], ["İstanbul", "Türkiye (81 il)"], [MAVI, TURUNCU]])
        tek = b["tek"]; self.assertEqual([tek["ek"], tek["olcekGizli"], tek["g"]["lejant"], tek["yuzdeEksen"]], [[], True, [str(yil), str(yil - 1)], 0])                  # ekler bitince yıllara göre görünüme döner

    def test_birikim_grafiginde_secili_il_de_cikarilabilir(self):
        b = self.s["birikim"]; MAVI, TURUNCU, YESIL = "#2a78d6", "#eb6834", "#1baf7a"; yil = self.son.year
        ozet = lambda x: [x["g"]["lejant"], x["renkler"], x["ek"], x["anaGizli"], x["secKapali"]]
        self.assertEqual(ozet(b["anaCikti"]), [["Ankara"], [TURUNCU], [{"kod": 6, "renk": 1}], True, False])                                   # üstte İstanbul seçili ama grafikte yalnızca Ankara
        self.assertEqual([c[0] for c in b["anaCikti"]["cipler"]], ["6"]); self.assertEqual(b["anaCikti"]["secenek"], 82)                         # çıkarılan seçili il ekleme listesine geri döner
        self.assertEqual(ozet(b["ucIlAnasiz"]), [["Ankara", "İzmir", "Bursa"], [TURUNCU, MAVI, YESIL], [{"kod": 6, "renk": 1}, {"kod": 35, "renk": 0}, {"kod": 16, "renk": 2}], True, True])   # seçili il yokken 3 il eklenir
        self.assertEqual(ozet(b["doluykenAnaDegisti"]), ozet(b["ucIlAnasiz"]))
        self.assertEqual(ozet(b["yerAcilincaAna"]), [["Yozgat", "Ankara", "Bursa"], [MAVI, TURUNCU, YESIL], [{"kod": 6, "renk": 1}, {"kod": 16, "renk": 2}], False, True])
        self.assertEqual(b["yerAcilincaAna"]["cipler"][0], ["ana", "Yozgat×", "rgb(42, 120, 214)", "Yozgat: karşılaştırmadan çıkar"])
        self.assertEqual(ozet(b["anaYineCikti"]), [["Ankara", "Bursa"], [TURUNCU, YESIL], [{"kod": 6, "renk": 1}, {"kod": 16, "renk": 2}], True, False])
        self.assertEqual(ozet(b["anaGeriEklendi"]), ozet(b["yerAcilincaAna"]))
        self.assertEqual(ozet(b["sonTek"]), [[str(yil), str(yil - 1)], [TURUNCU, MAVI], [], False, False]); self.assertEqual(b["sonTek"]["cipler"], [])   # son eklenen il de çıkınca seçili ilin yıllar görünümü

    def test_gecersiz_il_ve_veri_hatasi(self):
        self.assertEqual(self.s["gecersiz"], [[q, "0", "Türkiye (81 il)"] for q in ("?il=99", "?il=abc", "?il=%3Cscript%3E", "")])
        self.assertEqual(self.s["bozuk"], {"mesaj": "Veri yüklenemedi. Sayfayı yenileyip tekrar deneyin.", "icerikGizli": True, "svg": 0})

if __name__ == "__main__": unittest.main()
