"""AI arama görünürlüğü pilotu (İstanbul, Ankara, İzmir, Bursa, Antalya): JavaScript'siz okunabilen tarihli kısa cevap, veri/kaynak satırı,
görünür sayfa güncellemesi = sitemap lastmod ve gözlem–tahmin ayrımı. Pilot dışındaki 76 il kısa cevap/veri satırı taşımaz ("not" satırı korunur).
#bayat güncellik uyarısı pilota özgü değildir; 81 ilin ortak davranışı test_il_sayfasi.Guncellik'te sınanır.
Beklenenler data/tahmin_data.json ve sitemap.xml'den, üreticiden bağımsız hesaplanır."""
import datetime as dt, os, re, shutil, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_il_sayfasi import veri, sayfa, inv, tr, slug, ilk_ekran, metin, betiksiz, E0, TAM, AI_OZET, ILK_EKRAN_KELIME_AI
BULUNMA = {34: "İstanbul'da", 6: "Ankara'da", 35: "İzmir'de", 16: "Bursa'da", 7: "Antalya'da"}
KAYNAK = "https://www.wowturkey.com/konu/turkiye-genelindeki-arac-plakalarinin-gelisimi.1299/"
def lastmodlar(yol=os.path.join(u.ROOT, "sitemap.xml")): return dict(re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", u.oku(yol)))
def ozet(h): m = re.search(r'<p class="ozet-cevap">(.*?)</p>', h, re.S); return m[1] if m else None
def veri_satiri(h): m = re.search(r'<p class="veri-satiri">(.*?)</p>', h, re.S); return m[1] if m else None
def gozlem(s):
    g, n = s["obs"][-1]; sr, no = inv(n); return sr, f"{s['kod']:02d} {sr} {no:03d}", E0 + dt.timedelta(days=g)
def beklenen_ozet(s, ek):
    sr, plaka, ld = gozlem(s)
    return f"Son kayıtlı gözleme göre {ek} plaka sırası {sr[0]} harf grubunda: {tr(ld)} tarihinde {plaka} gözlendi. Güncel plaka tahmindir; resmî tahsis kaydı değildir."

class PilotKisaCevap(unittest.TestCase):
    def test_bes_pilot_il_tam_olarak_secili(self):
        self.assertEqual(AI_OZET, set(BULUNMA)); bulunan = {s["kod"] for s in veri() if ozet(sayfa(s["il"]))}
        self.assertEqual(bulunan, AI_OZET)

    def test_jssiz_html_de_tarihli_gozlem_cevabi_veriyle_eslesir(self):
        for s in veri():
            if s["kod"] not in AI_OZET: continue
            h = sayfa(s["il"]); p = ozet(h); sr, plaka, ld = gozlem(s)
            self.assertIsNotNone(p, s["il"]); self.assertEqual(metin(p), beklenen_ozet(s, BULUNMA[s["kod"]]), s["il"])
            self.assertIn(f'<time datetime="{ld.isoformat()}">{tr(ld)}</time>', p); self.assertIn(f'<span class="nw">{plaka}</span>', p)
            self.assertNotIn("data-live", p); self.assertNotIn(" id=", p)                                         # canlı JS bu paragrafa dokunmaz (yalnızca [data-live] ve kimlikli öğeler güncellenir)
            self.assertLess(h.index('class="ozet-cevap"'), h.index('<section class="arac"'))                     # ilk ekranda, araçlardan önce
            self.assertLess(h.index('class="cta"'), h.index('class="ozet-cevap"'))                               # büyük plaka ve CTA yerinde kalır; cevap CTA'nın altında
            self.assertLessEqual(len(metin(p).split()), 25, s["il"]); self.assertLessEqual(len(metin(ilk_ekran(h)).split()), ILK_EKRAN_KELIME_AI)
            for yasak in ("şu anda", "bugün", "kesin olarak", "veriliyor"): self.assertNotIn(yasak, metin(p).lower(), (s["il"], yasak))
            self.assertNotIn('<p class="not">', h)                                                                # "not" satırının yerini aldı (aynı uyarı cevabın içinde)

    def test_pilot_disi_76_ilde_kisa_cevap_ve_veri_satiri_yok(self):
        n = 0
        for s in veri():
            if s["kod"] in AI_OZET: continue
            h = sayfa(s["il"]); n += 1
            self.assertIsNone(ozet(h), s["il"]); self.assertIsNone(veri_satiri(h), s["il"]); self.assertNotIn("ozet-cevap", h); self.assertNotIn("data-guncelleme", h)
            self.assertIn('<p class="not">Son gözlemden hesaplanan tahmindir; resmî tahsis kaydı değildir.</p>', h)
        self.assertEqual(n, 76)

class VeriSatiri(unittest.TestCase):
    def test_son_gozlem_sayfa_guncellemesi_lastmod_ve_kaynak(self):
        lm = lastmodlar()
        for s in veri():
            if s["kod"] not in AI_OZET: continue
            ad = TAM.get(s["il"], s["il"]); h = sayfa(s["il"]); v = veri_satiri(h); _, _, ld = gozlem(s); self.assertIsNotNone(v, s["il"])
            gun = dt.date.fromisoformat(lm[f"https://plakatahmini.com/il/{slug(ad)}"])
            self.assertEqual(metin(v), f"Son gözlem: {tr(ld)} · Sayfa güncellemesi: {tr(gun)} · Kaynak: wowTURKEY forum tabloları", s["il"])
            self.assertIn(f'<time datetime="{ld.isoformat()}">', v); self.assertIn(f'<time datetime="{gun.isoformat()}" data-guncelleme>{tr(gun)}</time>', v)    # görünür tarih = sitemap lastmod
            self.assertEqual(re.findall(r'<a href="([^"]+)"', v), [KAYNAK]); self.assertGreaterEqual(gun, ld)          # normal <a> bağlantısı; güncelleme gözlemden önce olamaz
            self.assertLess(h.index('class="ozet-cevap"'), h.index('class="veri-satiri"')); self.assertLess(h.index('class="veri-satiri"'), h.index('<section class="arac"'))

class GozlemTahminAyrimi(unittest.TestCase):
    def test_ileri_tarihli_uretimde_cevap_gozlemde_kalir_buyuk_plaka_tarihli_tahmin(self):
        d = u.kopya(ekstra=("sitemap.xml", "il"), il_dizini=False)
        try:
            once = lastmodlar(os.path.join(d, "sitemap.xml"))["https://plakatahmini.com/il/ankara"]
            r = u.uret(d, "--bugun", "2026-11-12", "--iller", "ankara"); self.assertEqual(r.returncode, 0, r.stderr)
            h = u.oku(os.path.join(d, "il", "ankara.html")); s = next(x for x in veri() if x["kod"] == 6); sr, plaka, ld = gozlem(s)
            buyuk = re.search(r'class="buyuk mono" data-live="plaka">([^<]*)<', h)[1]
            self.assertNotEqual(buyuk, plaka); self.assertNotIn(buyuk, ozet(h))                                   # tahmin cevaba sızmaz
            self.assertIn(plaka, ozet(h)); self.assertIn(tr(ld), metin(ozet(h)))
            self.assertIn('<span data-live="tarih">12 Kasım 2026</span> itibarıyla · tahmindir', h)              # statik tahmin her zaman kendi tarihiyle
            self.assertIn(f'data-guncelleme>{tr(dt.date.fromisoformat(once))}</time>', h)                        # yalnızca tahmin günü değişti: sayfa güncellemesi tarihi oynamaz
        finally: shutil.rmtree(d, ignore_errors=True)

class Yayginlastirma(unittest.TestCase):
    """Üretici parametrik: pilot kümesi 81 ile genişletildiğinde her sayfa geçerli cevap üretir (ekler, kelime sınırları). Depoya dokunulmaz."""
    EKLER = {"Bayburt": "Bayburt'ta", "Kilis": "Kilis'te", "Iğdır": "Iğdır'da", "Elazığ": "Elazığ'da", "Muş": "Muş'ta", "Karabük": "Karabük'te", "Rize": "Rize'de",
             "Hakkari": "Hakkari'de", "Kars": "Kars'ta", "Sinop": "Sinop'ta", "Siirt": "Siirt'te", "Tokat": "Tokat'ta", "Kahramanmaraş": "Kahramanmaraş'ta",
             "Afyonkarahisar": "Afyonkarahisar'da", "Eskişehir": "Eskişehir'de", "Uşak": "Uşak'ta", "Van": "Van'da", "Düzce": "Düzce'de", "Şırnak": "Şırnak'ta", "Bitlis": "Bitlis'te"}
    def test_81_ile_genisletilince_tum_sayfalar_gecerli(self):
        d = u.kopya(ekstra=("sitemap.xml", "il"), il_dizini=False)
        try:
            yol = os.path.join(d, "generate_il_pages.py"); src = u.oku(yol)
            yeni, n = re.subn(r"AI_OZET_ILLER = frozenset\(\{[^}]*\}\)", "AI_OZET_ILLER = frozenset(range(1, 82))", src); self.assertEqual(n, 1)
            with open(yol, "w", encoding="utf-8") as f: f.write(yeni)
            r = u.uret(d, "--bugun", "2026-11-01"); self.assertEqual(r.returncode, 0, r.stderr); lm = lastmodlar(os.path.join(d, "sitemap.xml"))
            ekler = {}
            for s in veri():
                ad = TAM.get(s["il"], s["il"]); h = u.oku(os.path.join(d, "il", slug(ad) + ".html")); p = ozet(h); self.assertIsNotNone(p, ad)
                ek = re.match(r"Son kayıtlı gözleme göre (\S+) plaka sırası", metin(p))[1]; ekler[ad] = ek; self.assertTrue(ek.startswith(ad + "'"), ek)
                self.assertEqual(metin(p), beklenen_ozet(s, ek)); self.assertLessEqual(len(metin(p).split()), 25, ad)
                self.assertLessEqual(len(metin(ilk_ekran(h)).split()), ILK_EKRAN_KELIME_AI, ad); self.assertNotIn("günden eski", betiksiz(h), ad)
                self.assertIn(f'data-guncelleme>{tr(dt.date.fromisoformat(lm["https://plakatahmini.com/il/" + slug(ad)]))}</time>', h)
            for ad, ek in {**self.EKLER, **{"İstanbul": "İstanbul'da", "Ankara": "Ankara'da", "İzmir": "İzmir'de", "Bursa": "Bursa'da", "Antalya": "Antalya'da"}}.items():
                self.assertEqual(ekler[ad], ek)
        finally: shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__": unittest.main()
