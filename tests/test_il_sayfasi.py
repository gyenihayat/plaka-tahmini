"""81 il sayfası: sade ilk ekran, veriyle eşleşen ilk cevap, gözlem/tahmin ayrımı, hız/seri süresi tutarlılığı, güncellik uyarısı,
açılır bölümler, gerçek il bağlantıları, SEO etiketleri ve yapısal veri. Beklenenler data/tahmin_data.json ve forecast.py'den bağımsız hesaplanır."""
import datetime as dt, glob, html, json, os, re, shutil, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
E0 = dt.date(2024, 1, 1)
A1 = "ABCDEFGHJKLMNPRSTUVYZ"; A2 = "ABCDEFGHIJKLMNOPRSTUVYZ"; A3 = "ABCDEFGHJKLMNPRSTUVYZ"
AY = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
TAM = {"K.Maraş": "Kahramanmaraş", "Afyon": "Afyonkarahisar"}
def inv(n):
    g = n // 1000; return A1[g//len(A3)//len(A2)] + A2[g//len(A3) % len(A2)] + A3[g % len(A3)], n % 1000
def tr(d): return f"{d.day} {AY[d.month-1]} {d.year}"
def sayi(n): return f"{round(n):,}".replace(",", ".")
def slug(s):
    return s.translate(str.maketrans("çğıöşüÇĞİÖŞÜâ. ", "cgiosucgiosua--")).lower().replace("-", "")
def veri():
    with open(os.path.join(u.ROOT, "data", "tahmin_data.json"), encoding="utf-8") as f: return json.load(f)["iller"]
def sayfa(il): return u.oku(os.path.join(u.ROOT, "il", slug(TAM.get(il, il)) + ".html"))
def ilk_ekran(h):
    """Görünen ilk ekran HTML'i: gövdenin başından araca kadar; hidden (görünmeyen) bloklar çıkarılır."""
    e = h[h.index("<body>"):h.index('<section class="arac"')]
    return re.sub(r'<(div|p)[^>]*\bhidden\b[^>]*>.*?</\1>', "", e, flags=re.S)
def metin(x): return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))).strip()
def git_eski(f):
    return subprocess.run(["git", "show", "9b65ce4:" + f], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout

class SeoEtiketleri(unittest.TestCase):
    def test_title_h1_canonical_81_ilde_korunur(self):
        sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81)
        norm = lambda t: re.sub(r"\(\d{4}\)", "(YIL)", t)
        for yol in sayfalar:
            f = "il/" + os.path.basename(yol); yeni, eski = u.oku(yol), git_eski(f)
            for pat, ad in ((r"<title>(.*?)</title>", "title"), (r'rel="canonical" href="([^"]*)"', "canonical"), (r"<h1>(.*?)</h1>", "h1"), (r'property="og:url" content="([^"]*)"', "og:url")):
                a, b = re.search(pat, eski, re.S)[1], re.search(pat, yeni, re.S)[1]
                self.assertEqual(norm(a), norm(b), f"{f}: {ad}")

    def test_description_gozlemden_ve_eskimeyen(self):
        for s in veri():
            h = sayfa(s["il"]); d = html.unescape(re.search(r'name="description" content="(.*?)"', h)[1]); g, n = s["obs"][-1]; sr, no = inv(n)
            self.assertIn(f"Son gözlem: {s['kod']:02d} {sr} {no:03d} ({tr(E0 + dt.timedelta(days=g))})", d)
            self.assertNotRegex(d, r"tahmini seri \d\d [A-Z]{3}"); self.assertLessEqual(len(d), 160)
            self.assertEqual(re.search(r'og:description" content="(.*?)"', h)[1], re.search(r'twitter:description" content="(.*?)"', h)[1])

    def test_yalnizca_breadcrumb_jsonld_gecerli(self):
        for s in veri():
            h = sayfa(s["il"]); lds = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
            self.assertEqual([x["@type"] for x in lds], ["BreadcrumbList"], s["il"]); self.assertNotIn("FAQPage", h); self.assertNotIn("Sık sorulan sorular", h)
            self.assertEqual(len(re.findall(r"<h1>", h)), 1)

class IlkEkran(unittest.TestCase):
    def test_ilk_cevap_veriyle_eslesir_81_il(self):
        for s in veri():
            h = sayfa(s["il"]); o = [tuple(x) for x in s["obs"]]; c = fc.clean(o); g, n = o[-1]; sr, no = inv(n); ld = E0 + dt.timedelta(days=g)
            start = dt.date.fromisoformat(re.search(r'data-baslangic="([^"]+)"', h)[1]); rate = fc.slope(o, g)
            est = inv(round(n + fc.advance(o, c, g, (start - ld).days, rate)))[0]; kod = f"{s['kod']:02d}"
            self.assertEqual(re.search(r'class="buyuk mono" data-live="seri">([^<]*)<', h)[1], f"{kod} {est}", s["il"])
            self.assertIn(f"<span data-live=\"tarih\">{tr(start)}</span> itibarıyla · tahmindir", h)
            self.assertRegex(h, rf'<dt>Son kayıtlı gözlem</dt><dd class="v mono nw">{kod} {sr} {no:03d}</dd><dd class="k">{tr(ld)}</dd>')
            self.assertRegex(h, rf'<dt>Harf grubu</dt><dd class="v mono">{sr[0]}</dd><dd class="k">gözlenen · serinin ilk harfi</dd>')
            self.assertEqual(est[0] == sr[0], bool(re.search(r'id="tahmin-grup"[^>]*\bhidden\b', h)), s["il"])    # tahmini grup farklıysa ayrıca gösterilir

    def test_28_gunluk_degisim_ham_gozlemden(self):
        for s in veri():
            h = sayfa(s["il"]); o = s["obs"]; L = o[-1]
            ort = min(o, key=lambda x: abs(x[0] - (L[0] - 28))); bas = min(o, key=lambda x: abs(x[0] - (L[0] - 56)))
            m = re.search(r'<dt>Son (\d+) günde ilerleme</dt><dd class="v">([\d.]+) sıra</dd><dd class="k">([^<]*)</dd>', h)
            self.assertIsNotNone(m, s["il"]); a1 = L[1] - ort[1]; a0 = ort[1] - bas[1]; g1 = L[0] - ort[0]; g0 = ort[0] - bas[0]
            self.assertEqual((int(m[1]), m[2]), (g1, sayi(a1)), s["il"]); fark = ((a1/g1)/(a0/g0) - 1)*100
            beklenen = "önceki döneme benzer" if abs(fark) < 5 else f"önceki döneme göre %{abs(round(fark))} {'daha fazla' if fark > 0 else 'daha az'}"
            self.assertEqual(m[3], beklenen, s["il"])

    def test_metin_butcesi_ve_kaldirilan_ifadeler(self):
        for s in veri():
            h = sayfa(s["il"]); e = ilk_ekran(h); kelime = len(metin(e).split())
            self.assertLessEqual(kelime, 75, f"{s['il']}: ilk ekran {kelime} kelime")
            for p in re.findall(r"<p[^>]*>(.*?)</p>", e, re.S): self.assertLessEqual(len(metin(p).split()), 25, (s["il"], metin(p)[:60]))
            for yasak in ("ilinde son doğrulanmış", "şu anda", "yaklaşık bir hafta", "999 plak", "Güncel tahminimiz", "basıyor"): self.assertNotIn(yasak, h, (s["il"], yasak))
            self.assertIn("tahmindir", e); self.assertIn("Son kayıtlı gözlem", e); self.assertIn("resmî tahsis kaydı değildir", e)

    def test_tek_ana_eylem_ve_arac_ilk_ekrana_yakin(self):
        for s in veri():
            h = sayfa(s["il"]); e = ilk_ekran(h)
            self.assertEqual(len(re.findall(r'class="cta"', e)), 1); self.assertIn('href="#hesapla"', e); self.assertIn('id="hesapla"', h)
            self.assertLess(len(e), 3500, s["il"])

class HizVeSure(unittest.TestCase):
    def test_tek_hiz_tanimi_ve_seri_suresi_81_il(self):
        for s in veri():
            h = sayfa(s["il"]); o = [tuple(x) for x in s["obs"]]; rate = fc.slope(o, o[-1][0])
            m = re.search(r"günde yaklaşık ([\d.]+) sıra \(haftada yaklaşık ([\d.]+)\)\. Atlamasız ilerleme varsayımıyla bir seri \(1\.000 sıralık aralık; numaralar 001–999\) yaklaşık ([\d,]+) (saatte|günde|haftada|ayda) dolar", h)
            self.assertIsNotNone(m, s["il"]); self.assertEqual((m[1], m[2]), (sayi(rate), sayi(rate*7)), s["il"])
            gun = 1000 / rate; deger = float(m[3].replace(",", "."))
            beklenen = {"saatte": gun*24, "günde": gun, "haftada": gun/7, "ayda": gun/30}[m[4]]
            self.assertLessEqual(abs(deger - beklenen), 0.5 if m[4] != "günde" else 0.06, (s["il"], m[0], gun))
            self.assertEqual(m[4], "saatte" if gun < 1 else "günde" if gun < 14 else "haftada" if gun < 60 else "ayda", s["il"])

    def test_ornek_ilerleme_degerleri(self):           # belgenin örneği: Konya ~3,8 gün (eski ifade "yaklaşık bir hafta" yanlıştı)
        h = sayfa("Konya"); self.assertIn("yaklaşık 3,8 günde dolar", h)

class Guncellik(unittest.TestCase):
    def test_statik_uyari_21_gunden_eskiyse_gorunur(self):
        d = u.kopya()
        try:
            for bugun, gorunur in (("2026-11-13", False), ("2026-11-17", True)):   # son gözlem 23 Ekim: 21 gün (uyarı yok) / 25 gün (uyarı var)
                r = u.uret(d, "--bugun", bugun, "--iller", "konya"); self.assertEqual(r.returncode, 0, r.stderr)
                h = u.oku(os.path.join(d, "il", "konya.html")); self.assertEqual(not re.search(r'id="bayat"[^>]*\bhidden\b', h), gorunur, bugun)
                self.assertIn("Tahmin güncel olmayabilir ve kesin değildir", h)
        finally: shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_js_ziyaret_tarihine_gore_uyari(self):
        h = os.path.join(u.ROOT, "il", "konya.html"); an = lambda y, m, d, sa=12: int(dt.datetime(y, m, d, sa, tzinfo=dt.timezone.utc).timestamp() * 1000)
        r = [x["bayat"] for x in u.canli_sonuc(h, [an(2026, 10, 30), an(2026, 11, 13), an(2026, 11, 14), an(2027, 2, 1)])]     # yaş: 7, 21, 22 (Cumartesi), 101 gün (takvim günü; iş günü kuralından bağımsız)
        self.assertEqual(r, [False, False, True, True])

class AcilirBolumlerVeBaglantilar(unittest.TestCase):
    def test_tablolar_ve_metodoloji_acilirda_icerik_html_icinde(self):
        for s in veri():
            h = sayfa(s["il"]); basliklar = re.findall(r'<details class="bolum"><summary><h2>(.*?)</h2></summary>', h)
            for b in ("Son plaka gözlemleri", "Geçen yıla kıyasla durum — 2 aylık dönemler", "Harf grubu geçişleri (Şubat 2024'ten beri)", "Nasıl hesaplanıyor?", "Veri kaynağı ve sınırlamalar", "Diğer iller"):
                self.assertIn(b, basliklar, (s["il"], b))
            self.assertGreaterEqual(h.count("<table"), 2); self.assertNotRegex(h, r'<details class="bolum" open')
            self.assertIn("gerçek tescil sayısı değildir", h)

    def test_81_gercek_il_baglantisi(self):
        for s in veri():
            h = sayfa(s["il"]); bolum = re.search(r'<h2>Diğer iller</h2>.*?</details>', h, re.S)[0]
            linkler = re.findall(r'<a href="(/il/[a-z]+)">', bolum); self.assertEqual(len(linkler), 81, s["il"]); self.assertEqual(len(set(linkler)), 81)

class Arac(unittest.TestCase):
    def test_form_erisilebilirlik_ve_isleviyedek_81_il(self):
        for s in veri():
            h = sayfa(s["il"]); kod = s["kod"]
            self.assertRegex(h, rf'<form id="hedef-form" action="/" method="get"[^>]*><input type="hidden" name="il" value="{kod}">')
            self.assertIn('<label for="hedef">', h); self.assertIn('id="hedef"', h); self.assertIn('aria-describedby="hedef-ipucu"', h); self.assertIn('id="sonuc" class="sonuc" aria-live="polite"', h)
            self.assertIn(f'<a href="/?il={kod}">Ana sayfada aç</a>', h)                     # JS kapalıyken işlevsel yedek
            self.assertLess(h.index('src="/assets/tahmin-motoru.js"'), h.index('src="/assets/il-arac.js"'))
            self.assertEqual(h.count(" defer>"), 3)
            ilv = json.loads(re.search(r'<script type="application/json" id="il-veri">(.*?)</script>', h, re.S)[1])
            self.assertEqual((ilv["kod"], ilv["obs"], ilv["bterr"]), (kod, s["obs"], s["bterr"]))
            self.assertNotIn("function fit(", h); self.assertNotIn("function reachDate(", h)    # motor sayfaya kopyalanmaz

class VeriYetersiz(unittest.TestCase):
    """Karşılaştırılabilir gözlem yoksa ya da seride kırılma varsa ilgili bilgi uydurulmaz; sayfa yine geçerli ve tam kalır."""
    def _uret(self, degistir):
        d = u.kopya()
        try:
            yol = os.path.join(d, "data", "tahmin_data.json")
            with open(yol, encoding="utf-8") as f: v = json.load(f)
            k = next(x for x in v["iller"] if x["il"] == "Konya"); degistir(k["obs"])
            with open(yol, "w", encoding="utf-8") as f: json.dump(v, f, ensure_ascii=False, separators=(",", ":"))
            r = u.uret(d, "--bugun", "2026-10-30", "--iller", "konya"); self.assertEqual(r.returncode, 0, r.stderr)
            return u.oku(os.path.join(d, "il", "konya.html"))
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_28_gun_sinir_gozlemi_yoksa_yalnizca_son_iki_gozlem_gosterilir(self):
        h = self._uret(lambda o: o.__setitem__(slice(None), [x for x in o if abs(x[0] - (o[-1][0] - 28)) > 3]))
        self.assertNotIn("günde ilerleme</dt>", h); self.assertIn("<dt>Son iki gözlem arası</dt>", h); self.assertNotIn("önceki döneme göre", h)
        self.assertIn("son iki gözlem arasında", h); self.assertNotRegex(h, r"Kayıtlı son \d+ günde")

    def test_hic_karsilastirma_yoksa_metrik_ve_bolum_yok_ama_sayfa_tam(self):
        h = self._uret(lambda o: o.__setitem__(slice(None), [x for x in o if (x[0] <= o[-1][0] - 15 and abs(x[0] - (o[-1][0] - 28)) > 3) or x is o[-1]]))      # son iki gözlem arası > 14 gün, 28 gün sınırı da yok
        self.assertNotIn("<dt>Son iki gözlem arası</dt>", h); self.assertNotIn("günde ilerleme</dt>", h); self.assertNotIn("<h2>Son gelişmeler</h2>", h)
        self.assertIn("Son kayıtlı gözlem", h); self.assertIn('id="hesapla"', h); self.assertIn('<h2>Diğer iller</h2>', h)

    def test_seride_kirilma_varsa_degisim_uretilmez(self):
        def kir(o): o[-1][1] += 20000
        h = self._uret(kir); self.assertNotIn("günde ilerleme</dt>", h); self.assertNotIn("Son iki gözlem arası</dt>", h)
        self.assertNotIn("<h2>Son gelişmeler</h2>", h); self.assertIn("Son kayıtlı gözlem", h)

if __name__ == "__main__": unittest.main()
