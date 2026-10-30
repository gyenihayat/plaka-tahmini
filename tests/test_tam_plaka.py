"""Güncel tahmini plakanın TAM gösterimi: İL KODU + ÜÇ HARF + ÜÇ HANELİ SIRA (örn. 06 GGL 096). Ana sayfadaki üç büyük il kartı ve 81 il sayfasının büyük tahmini aynı değeri gösterir;
statik HTML (Python, JS kapalıyken de görünür) ile canlı JS (ortak motor) aynı gün için BİREBİR aynı plakayı üretir. Beklenenler üretimden bağımsız hesaplanır (forecast.py + JS Math.round yuvarlaması)."""
import datetime as dt, json, math, os, re, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _util as u
import forecast as fc
from test_il_sayfasi import veri, sayfa, slug, TAM, E0, tahmin_plaka, inv, yuvarla
ANA = u.oku(os.path.join(u.ROOT, "index.html"))
PLAKA = re.compile(r"^\d\d [A-Z]{3} \d{3}$")
KARTLAR = (("İstanbul", 34), ("Ankara", 6), ("İzmir", 35))
ONCEKI_URETIM = "42a8460"          # tam plaka değişikliğinden önceki üretim sürümü: SEO alanlarının korunduğu bu sürümle karşılaştırılır

def referans_gunu(h): return dt.date.fromisoformat(re.search(r'data-baslangic="([^"]+)"', h)[1])
def beklenen(s, h):
    o = [tuple(x) for x in s["obs"]]; g, n = o[-1]
    return tahmin_plaka(s["kod"], n + fc.advance(o, fc.clean(o), g, (referans_gunu(h) - (E0 + dt.timedelta(days=g))).days, fc.slope(o, g)))

class Il81(unittest.TestCase):
    def test_81_il_sayfasinda_tam_plaka_uc_haneli_sira_ve_degeri_dogru(self):
        n = 0
        for s in veri():
            h = sayfa(s["il"]); m = re.search(r'<p class="buyuk mono" data-live="plaka">([^<]*)</p>', h); self.assertIsNotNone(m, s["il"])
            self.assertRegex(m[1], PLAKA, s["il"]); self.assertEqual(m[1], beklenen(s, h), s["il"]); self.assertTrue(m[1].startswith(f"{s['kod']:02d} "), s["il"]); n += 1
            self.assertIn('<p class="e">Tahmini güncel plaka</p>', h); self.assertNotIn('data-live="seri"', h)
        self.assertEqual(n, 81)

    def test_gozlem_tahminden_ayri_ve_degismedi(self):
        for s in veri():
            h = sayfa(s["il"]); g, son = s["obs"][-1]; harf, no = inv(son)
            self.assertIn(f'<dt>Son kayıtlı gözlem</dt><dd class="v mono nw">{s["kod"]:02d} {harf} {no:03d}</dd>', h, s["il"])          # gözlem alanı: gerçek kayıt
            self.assertIn('<dd class="k">tahmin; gözlem değil</dd>', h); self.assertIn("itibarıyla · tahmindir</p>", h)                                      # tahmin etiketi

    def test_seo_alanlari_degismedi(self):
        for s in veri():
            ad = slug(TAM.get(s["il"], s["il"])); yeni = sayfa(s["il"])
            eski = subprocess.run(["git", "show", f"{ONCEKI_URETIM}:il/{ad}.html"], cwd=u.ROOT, capture_output=True, text=True, check=True).stdout
            for desen in (r"<title>.*?</title>", r'<meta name="description" content="[^"]*">', r'<link rel="canonical" href="[^"]*">', r"<h1>.*?</h1>", r'<meta property="og:[a-z:]+" content="[^"]*">', r'<script type="application/ld\+json">.*?</script>'):
                self.assertEqual(re.findall(desen, yeni, re.S), re.findall(desen, eski, re.S), f"{ad}: {desen}")

class AnaSayfaKartlari(unittest.TestCase):
    def test_uc_kart_tam_plaka_il_sayfasiyla_birebir_ve_baglanti_korunur(self):
        kartlar = re.findall(r'<a class="kart" href="(/il/[a-z]+)" data-il="([^"]+)">(.*?)</a>', ANA, re.S); self.assertEqual([k[1] for k in kartlar], [k[0] for k in KARTLAR])
        iller = {s["il"]: s for s in veri()}
        for (il, kod), (href, _, ic) in zip(KARTLAR, kartlar):
            kart = re.search(r'<span class="k-seri mono" data-kart="plaka">([^<]*)</span>', ic)[1]; h = sayfa(il); il_plaka = re.search(r'data-live="plaka">([^<]*)<', h)[1]
            self.assertRegex(kart, PLAKA); self.assertEqual(kart, il_plaka); self.assertEqual(kart, beklenen(iller[il], h)); self.assertTrue(kart.startswith(f"{kod:02d} "))
            self.assertEqual(href, f"/il/{slug(il)}"); self.assertIn("Tahmindir", ic); self.assertIn("itibarıyla", ic); self.assertIn("Son gözlem:", ic)               # etiket, referans tarihi ve son gözlem korunur

@unittest.skipUnless(u.NODE, "node kurulu değil")
class PythonJsEsligi(unittest.TestCase):
    NODE_BETIK = r"""const fs=require("fs"),vm=require("vm"),R=process.argv[1],gunler=JSON.parse(process.argv[2]);
const ctx=vm.createContext({console,Math,Date}); vm.runInContext(fs.readFileSync(R+"/assets/tahmin-motoru.js","utf8"),ctx);
const d=JSON.parse(fs.readFileSync(R+"/data/tahmin_data.json","utf8")), out=[];
for(const s of d.iller){ const son=s.obs[s.obs.length-1][0]; ctx.__s={kod:s.kod,il:s.il,bterr:s.bterr,obs:s.obs};
  for(const k of gunler){ ctx.__g=son+k; const r=vm.runInContext("guncelSeriBilgisi(__s,__g)",ctx); out.push([s.kod,k,r.n,r.plaka]); } }
console.log(JSON.stringify(out));"""
    def test_81_il_x_400_gun_tam_plaka_python_ve_js_birebir(self):
        """Eski sapma: ham tahmin iki tarafta bit-bit aynı, ama tam .5 değerlerde Python round() çifte, JS Math.round yukarı yuvarlıyordu (≈%2,4 durumda 1 sıra, 1000 sınırında harf farkı)."""
        gunler = list(range(1, 401, 3)); r = subprocess.run([u.NODE, "-e", self.NODE_BETIK, u.ROOT, json.dumps(gunler)], capture_output=True, text=True, check=True); js = json.loads(r.stdout)
        iller = {s["kod"]: s for s in veri()}; yari = 0
        for kod, k, n_js, plaka_js in js:
            o = [tuple(x) for x in iller[kod]["obs"]]; g, n = o[-1]; ham = n + fc.advance(o, fc.clean(o), g, k, fc.slope(o, g))
            self.assertEqual(n_js, ham, (kod, k)); self.assertEqual(plaka_js, tahmin_plaka(kod, ham), (kod, k)); yari += (ham % 1 == 0.5)
        self.assertEqual(len(js), 81 * len(gunler)); print(f"  (tam .5 yuvarlama gerektiren {yari} durum dahil)", file=sys.stderr)

    def test_uretici_inv_js_ile_ayni_yaridegerleri_yukari_yuvarlar(self):
        kaynak = open(os.path.join(u.ROOT, "generate_il_pages.py"), encoding="utf-8").read()
        ad = {"math": math, "A1": "ABCDEFGHJKLMNPRSTUVYZ", "A2": "ABCDEFGHIJKLMNOPRSTUVYZ", "A3": "ABCDEFGHJKLMNPRSTUVYZ"}
        exec(re.search(r"def inv\(n\):.*?return [^\n]*\n", kaynak, re.S)[0], ad); inv_uretici = ad["inv"]                   # üreticinin kendi inv'i (modül içe aktarılamaz: argparse/yan etki)
        degerler = [1005.5, 1006.5, 1007.5, 1999.5, 2000.5, 2999.5, 663368.5, 0.5, 1.5, 2.5]
        js = json.loads(subprocess.run([u.NODE, "-e", r"""const v=require("vm"),fs=require("fs"),c=v.createContext({Math});v.runInContext(fs.readFileSync(process.argv[1]+"/assets/tahmin-motoru.js","utf8"),c);
console.log(JSON.stringify(JSON.parse(process.argv[2]).map(n=>{const i=v.runInContext("invN("+n+")",c);return [i.let,i.num];})))""", u.ROOT, json.dumps(degerler)], capture_output=True, text=True, check=True).stdout)
        for x, j in zip(degerler, js): self.assertEqual(list(inv_uretici(x)), j, x)

    def test_sifir_dolgusu_il_kodu_ve_sira_numarasi(self):
        r = json.loads(subprocess.run([u.NODE, "-e", r"""const v=require("vm"),fs=require("fs"),c=v.createContext({Math,Date});v.runInContext(fs.readFileSync(process.argv[1]+"/assets/tahmin-motoru.js","utf8"),c);
c.__a={kod:6,obs:[[0,1006],[10,1006]]}; c.__b={kod:6,obs:[[0,2000],[10,2000]]}; c.__c={kod:6,obs:[[0,1042],[10,1042]]};
console.log(JSON.stringify(["__a","__b","__c"].map(k=>v.runInContext("guncelSeriBilgisi("+k+",5).plaka",c))))""", u.ROOT], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(r, ["06 AAB 006", "06 AAC 001", "06 AAB 042"])             # 006 / 042: baştaki sıfırlar korunur; 000 → 001 (numaralar 001–999)

if __name__ == "__main__": unittest.main()
