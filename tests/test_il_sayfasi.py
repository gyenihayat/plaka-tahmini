"""81 il sayfası: sade ilk ekran, veriyle eşleşen ilk cevap, gözlem/tahmin ayrımı, hız/seri süresi tutarlılığı, güncellik uyarısı,
açılır bölümler, gerçek il bağlantıları, SEO etiketleri ve yapısal veri. Beklenenler data/tahmin_data.json ve forecast.py'den bağımsız hesaplanır."""
import datetime as dt, glob, html, json, math, os, re, shutil, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
E0 = dt.date(2024, 1, 1)
A1 = "ABCDEFGHJKLMNPRSTUVYZ"; A2 = "ABCDEFGHIJKLMNOPRSTUVYZ"; A3 = "ABCDEFGHJKLMNPRSTUVYZ"
AY = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
TAM = {"K.Maraş": "Kahramanmaraş", "Afyon": "Afyonkarahisar"}
def inv(n):
    g = n // 1000; return A1[g//len(A3)//len(A2)] + A2[g//len(A3) % len(A2)] + A3[g % len(A3)], n % 1000
def yuvarla(x): return math.floor(x + 0.5)                      # JS Math.round ile aynı (yarım değer yukarı); Python round() yarım değeri çifte yuvarlar ve canlı JS ile ayrışırdı
def tahmin_plaka(kod, ham):
    """Ham tahmin sıra değerinden tam plaka: İL KODU + ÜÇ HARF + ÜÇ HANELİ SIRA (numara 001–999 aralığına kısıtlanır, başındaki sıfırlar korunur). Üretimden bağımsız yazılmıştır."""
    n = yuvarla(ham); harf, no = inv(n); return f"{kod:02d} {harf} {max(1, min(999, no)):03d}"
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
def betiksiz(h): return re.sub(r"<script\b.*?</script>", "", h, flags=re.S)
BAYAT = "Son kayıtlı gözlem 21 günden eski ({}). Tahmin güncel olmayabilir ve kesin değildir."
BAYAT_RE = r'<div class="uyari" id="bayat" role="status"( hidden)?>([^<]*)</div>'
def git_eski(f):
    return subprocess.run(["git", "show", "9b65ce4:" + f], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout
AI_OZET = {34, 6, 35, 16, 7}     # AI arama pilotu (İstanbul, Ankara, İzmir, Bursa, Antalya): "not" satırının yerine tarihli kısa cevap (≤25 kelime) + veri/kaynak satırı (16 kelime)
ILK_EKRAN_KELIME = 75; ILK_EKRAN_KELIME_AI = 100       # pilot bütçesi: 75 − not satırı (8) + kısa cevap (≤25) + veri satırı (~16) ≈ 100; paragraf başına 25 kelime sınırı herkes için aynı

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
            est = tahmin_plaka(s["kod"], n + fc.advance(o, c, g, (start - ld).days, rate)); kod = f"{s['kod']:02d}"
            self.assertEqual(re.search(r'class="buyuk mono" data-live="plaka">([^<]*)<', h)[1], est, s["il"])                   # tam tahmini plaka: il kodu + 3 harf + 3 haneli sıra
            self.assertIn('<p class="e">Tahmini güncel plaka</p>', h)
            self.assertIn(f"<span data-live=\"tarih\">{tr(start)}</span> itibarıyla · tahmindir", h)
            self.assertRegex(h, rf'<dt>Son kayıtlı gözlem</dt><dd class="v mono nw">{kod} {sr} {no:03d}</dd><dd class="k">{tr(ld)}</dd>')
            self.assertRegex(h, rf'<dt>Harf grubu</dt><dd class="v mono">{sr[0]}</dd><dd class="k">gözlenen · serinin ilk harfi</dd>')
            self.assertEqual(est.split()[1][0] == sr[0], bool(re.search(r'id="tahmin-grup"[^>]*\bhidden\b', h)), s["il"])    # tahmini grup farklıysa ayrıca gösterilir

    def test_28_gunluk_degisim_ham_gozlemden(self):
        for s in veri():
            h = sayfa(s["il"]); o = s["obs"]; L = o[-1]
            ort = min(o, key=lambda x: abs(x[0] - (L[0] - 28))); bas = min(o, key=lambda x: abs(x[0] - (L[0] - 56)))
            m = re.search(r'<dt>Son (\d+) günde ilerleme</dt><dd class="v">([\d.]+) sıra</dd><dd class="k">([^<]*)</dd>', h)
            if m is None:       # gözlem aralığı düzensizse (±28/56 gün civarında gözlem yoksa) sayfa "Son iki gözlem arası" gösterir: değerler ham gözlemden
                m2 = re.search(r'<dt>Son iki gözlem arası</dt><dd class="v">([\d.]+) sıra</dd><dd class="k">(\d+) günde</dd>', h); self.assertIsNotNone(m2, s["il"])
                self.assertEqual((m2[1], int(m2[2])), (sayi(L[1] - o[-2][1]), L[0] - o[-2][0]), s["il"]); continue
            self.assertIsNotNone(m, s["il"]); a1 = L[1] - ort[1]; a0 = ort[1] - bas[1]; g1 = L[0] - ort[0]; g0 = ort[0] - bas[0]
            self.assertEqual((int(m[1]), m[2]), (g1, sayi(a1)), s["il"]); fark = ((a1/g1)/(a0/g0) - 1)*100
            beklenen = "önceki döneme benzer" if abs(fark) < 5 else f"önceki döneme göre %{abs(round(fark))} {'daha fazla' if fark > 0 else 'daha az'}"
            self.assertEqual(m[3], beklenen, s["il"])

    def test_metin_butcesi_ve_kaldirilan_ifadeler(self):
        for s in veri():
            h = sayfa(s["il"]); e = ilk_ekran(h); kelime = len(metin(e).split())
            self.assertLessEqual(kelime, ILK_EKRAN_KELIME_AI if s["kod"] in AI_OZET else ILK_EKRAN_KELIME, f"{s['il']}: ilk ekran {kelime} kelime")
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
    """#bayat güncellik uyarısı 81 ilde tek kuralla (pilot ve pilot dışı aynı kod yolu): veri tazeyken HTML'de boş ve gizli (JS'siz okuyucu yanlış uyarı görmez);
    üretim anında veri eskiyse HTML'de görünür metinle; ziyaret anında eşik aşılırsa satır içi betik metni yazar ve gösterir. Eşik: 21 günden eski (> 21).
    Statik ve JS aynı kural: yaş = Türkiye TAKVİM günü − son gözlem (statikte üretim günü, JS'te ziyaret günü; UTC+3, tarayıcı saat diliminden bağımsız).
    İş günü kuralı yalnızca güncel tahminin referans gününe uygulanır, uyarı yaşına uygulanmaz."""
    def test_81_ilde_taze_veride_uyari_metni_html_de_yok_yalniz_betikte(self):
        from is_gunu import RESMI_TATIL, onceki_is_gunu, TAKVIM_ILK_YIL, TAKVIM_SON_YIL
        g0 = dt.date(TAKVIM_ILK_YIL, 1, 8); bosluk = max((g0 + dt.timedelta(i) - onceki_is_gunu(g0 + dt.timedelta(i))).days for i in range((dt.date(TAKVIM_SON_YIL, 12, 31) - g0).days))
        n = 0
        for s in veri():
            h = sayfa(s["il"]); ld = E0 + dt.timedelta(days=s["obs"][-1][0]); n += 1
            yas = (dt.date.fromisoformat(re.search(r'data-baslangic="([^"]+)"', h)[1]) - ld).days      # referans iş gününde yaş; üretimin takvim günü en çok `bosluk` gün sonra
            b = re.findall(BAYAT_RE, h); self.assertEqual(len(b), 1, s["il"]); gizli, m = b[0]                  # tek öğe
            if yas + bosluk <= 21: self.assertEqual(gizli, " hidden", s["il"])                                  # kesin taze (bugünkü veride 81/81)
            if yas > 21: self.assertEqual(gizli, "", s["il"])                                                   # kesin eski
            self.assertEqual(m, "" if gizli else BAYAT.format(tr(ld)), s["il"]); self.assertEqual("günden eski" in betiksiz(h), not gizli, s["il"])
            self.assertEqual(h.count('by.textContent="' + BAYAT.format(tr(ld)) + '"'), 1, s["il"])          # metin satır içi betikte, ilin kendi son gözlem tarihiyle
        self.assertEqual(n, 81)

    def test_uretimde_takvim_gunune_gore_21_gunden_eskiyse_html_de_gorunur_metin(self):
        d = u.kopya()
        try:
            # son gözlem 30 Ekim (Cuma). 20 Kasım: 21 gün (uyarı yok); 21 Kasım Cumartesi: 22 gün, 22 Kasım Pazar: 23 gün (uyarı var; iş günü sayılsaydı
            # ikisi de 20 Kasım'a göre 21 gün olurdu); 24 Kasım: 25 gün. Görünür metin JS kapalıyken de okunur.
            for bugun, gorunur, referans in (("2026-11-20", False, "2026-11-20"), ("2026-11-21", True, "2026-11-20"), ("2026-11-22", True, "2026-11-20"), ("2026-11-24", True, "2026-11-24")):
                r = u.uret(d, "--bugun", bugun, "--iller", "konya,ankara"); self.assertEqual(r.returncode, 0, r.stderr)
                for sl in ("konya", "ankara"):          # pilot dışı ve pilot il
                    h = u.oku(os.path.join(d, "il", sl + ".html"))
                    self.assertEqual(re.findall(BAYAT_RE, h), [("", BAYAT.format("30 Ekim 2026"))] if gorunur else [(" hidden", "")], (sl, bugun))
                    self.assertEqual("günden eski" in betiksiz(h), gorunur, (sl, bugun))
                    self.assertIn(f'data-baslangic="{referans}"', h, (sl, bugun))                               # tahminin referans günü iş günü kuralıyla kalır
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_resmi_tatilde_uretim_takvim_gunuyle_ve_js_ile_ayni(self):
        d = u.kopya()
        try:
            yol = os.path.join(d, "data", "tahmin_data.json"); v = json.loads(u.oku(yol)); k = next(x for x in v["iller"] if x["il"] == "Konya")
            k["obs"].append([(dt.date(2026, 12, 10) - E0).days, k["obs"][-1][1] + 6000])                       # yalnızca geçici kopyada: 10 Aralık 2026 (Perşembe) gözlemi
            with open(yol, "w", encoding="utf-8") as f: f.write(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
            # 31 Aralık: 21 gün (yok); 1 Ocak 2027 resmî tatil (Cuma): 22 gün (var; önceki iş günü 31 Aralık'a göre 21 olurdu); 2 Ocak Cumartesi: 23 gün (var)
            for bugun, gorunur in (("2026-12-31", False), ("2027-01-01", True), ("2027-01-02", True)):
                r = u.uret(d, "--bugun", bugun, "--iller", "konya"); self.assertEqual(r.returncode, 0, r.stderr); h = os.path.join(d, "il", "konya.html")
                self.assertEqual(re.findall(BAYAT_RE, u.oku(h)), [("", BAYAT.format("10 Aralık 2026"))] if gorunur else [(" hidden", "")], bugun)
                self.assertIn('data-baslangic="2026-12-31"', u.oku(h))
                if u.NODE:
                    y, a, g = map(int, bugun.split("-")); x = u.canli_sonuc(h, [int(dt.datetime(y, a, g, 9, tzinfo=dt.timezone.utc).timestamp() * 1000)])[0]      # aynı gün TR 12:00
                    self.assertEqual((x["bayat"], x["bayatMetin"], x["hatalar"]), (gorunur, BAYAT.format("10 Aralık 2026") if gorunur else None, []), bugun)
        finally: shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_ayni_gun_uretim_ve_ziyaret_ayni_uyari_durumu(self):
        d = u.kopya()
        try:
            for g in range(18, 26):                     # 18–25 Kasım 2026 (21–22 hafta sonu); son gözlem 30 Ekim: yaş 19–26
                bugun = dt.date(2026, 11, g); r = u.uret(d, "--bugun", bugun.isoformat(), "--iller", "konya"); self.assertEqual(r.returncode, 0, r.stderr)
                h = os.path.join(d, "il", "konya.html"); statik = re.findall(BAYAT_RE, u.oku(h))[0][0] == ""
                x = u.canli_sonuc(h, [int(dt.datetime(2026, 11, g, 9, tzinfo=dt.timezone.utc).timestamp() * 1000)])[0]          # aynı gün TR 12:00
                beklenen = (bugun - dt.date(2026, 10, 30)).days > 21
                self.assertEqual((statik, x["bayat"]), (beklenen, beklenen), bugun); self.assertEqual(x["bayatMetin"], BAYAT.format("30 Ekim 2026") if beklenen else None, bugun)
        finally: shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_js_ziyaret_tarihine_gore_metni_yazar_ve_gosterir(self):
        an = lambda y, m, d, sa=12, dk=0: int(dt.datetime(y, m, d, sa, dk, tzinfo=dt.timezone.utc).timestamp() * 1000)
        # son gözlem 30 Ekim; Türkiye takvim gününe göre yaş: 7, 21, 21 (TR 20 Kasım 23:59), 22 (TR 21 Kasım 00:00), 22 (Cumartesi; iş günü kuralından bağımsız), 94
        anlar = [an(2026, 11, 6), an(2026, 11, 20), an(2026, 11, 20, 20, 59), an(2026, 11, 20, 21, 0), an(2026, 11, 21), an(2027, 2, 1)]
        beklenen = [False, False, False, True, True, True]; m = BAYAT.format("30 Ekim 2026")
        for il in ("konya", "ankara"):
            for tz in (None, "America/Los_Angeles", "Asia/Tokyo"):
                r = u.canli_sonuc(os.path.join(u.ROOT, "il", il + ".html"), anlar, tz)
                self.assertEqual([x["bayat"] for x in r], beklenen, (il, tz)); self.assertEqual([x["hatalar"] for x in r], [[]] * len(anlar), (il, tz))
                self.assertEqual([x["bayatMetin"] for x in r], [m if b else None for b in beklenen], (il, tz))

    @unittest.skipUnless(u.NODE, "node kurulu değil")
    def test_uretimde_eski_sayfada_js_ayni_uyariyi_korur(self):
        d = u.kopya()
        try:
            r = u.uret(d, "--bugun", "2026-11-24", "--iller", "konya"); self.assertEqual(r.returncode, 0, r.stderr)
            x = u.canli_sonuc(os.path.join(d, "il", "konya.html"), [int(dt.datetime(2026, 11, 24, 12, tzinfo=dt.timezone.utc).timestamp() * 1000)])[0]
            self.assertEqual((x["bayat"], x["bayatMetin"], x["hatalar"]), (True, BAYAT.format("30 Ekim 2026"), []))
        finally: shutil.rmtree(d, ignore_errors=True)

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
            self.assertEqual(h.count(" defer>"), 6 if kod == 6 else 5)               # olcum, takvim, (yalnızca Ankara: tarihsel referans), motor, tarih aracı, araç
            self.assertLess(h.index('src="/assets/tahmin-motoru.js"'), h.index('src="/assets/tarih-sorgu.js"')); self.assertLess(h.index('src="/assets/tarih-sorgu.js"'), h.index('src="/assets/il-arac.js"'))
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
