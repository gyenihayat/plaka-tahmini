"""Ortak motor (assets/tahmin-motoru.js): altın çıktılarla birebir eşleşir (ilk üretim eski ana sayfa motorundan; Kasım 2026 eğilim düzeltmesinden sonra yalnızca ileri tahmin
alanları değişecek şekilde yeniden üretildi); kaynak DOM/DATA'ya bağımlı değildir; Python (forecast.py) ile aynı matematik."""
import os, re, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u

@unittest.skipUnless(u.NODE, "node kurulu değil")
class MotorAltinCikti(unittest.TestCase):
    def test_altin_cikti_eslesir(self):
        r = subprocess.run([u.NODE, os.path.join(u.ROOT, "tests", "golden", "kontrol_golden.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn("eşleşti", r.stdout)

    def test_motor_dom_ve_veriye_bagimli_degil(self):
        src = u.oku(os.path.join(u.ROOT, "assets", "tahmin-motoru.js"))
        for yasak in ("document.", "window.", "DATA", "byName", "getElementById"): self.assertNotIn(yasak, src, yasak)
        self.assertNotIn("2026-", src); self.assertNotIn("tatiller:", src)                       # tatil takvimi motorda değil, üretilen assets/takvim.js'te (tek kaynak is_gunu.py)

    def test_index_html_motoru_tekrar_tanimlamaz(self):
        h = u.oku(os.path.join(u.ROOT, "index.html"))
        self.assertIn('<script src="/assets/takvim.js"></script>\n<script src="/assets/tarihsel-referanslar.js"></script>\n<script src="/assets/tahmin-motoru.js"></script>', h)
        self.assertLess(h.index("/assets/tahmin-motoru.js"), h.index("const DATA = "))
        for fn in ("function fit(", "function reachDate(", "function estimateAt(", "function parseExcl(", "const A1="): self.assertNotIn(fn, h, fn)
        self.assertRegex(h, r"const DATA = .*?;\n")          # tablo_ekle.py'nin güncellediği kalıp

    def test_motor_python_ile_ayni_matematik(self):
        # İl sayfalarının Python tarafı (forecast.py) ile JS motoru: 12 il x 9 ufuk, fark <= 1 sıra
        import json; sys.path.insert(0, u.ROOT); import forecast as fc
        with open(os.path.join(u.ROOT, "tests", "golden", "motor_golden.json"), encoding="utf-8") as f: g = json.load(f)
        with open(os.path.join(u.ROOT, "tests", "golden", "motor_veri.json"), encoding="utf-8") as f: v = json.load(f)
        for s in v["iller"]:
            o = [tuple(x) for x in s["obs"]]; c = fc.clean(o); last = o[-1]; rate = fc.slope(o, last[0])
            for h, n, _ in g["iller"][s["il"]]["estimate"]:
                self.assertLessEqual(abs(round(last[1] + fc.advance(o, c, last[0], h, rate)) - n), 1, (s["il"], h))

    def test_hafta_ici_dagilim(self):
        # Etkin gün: hafta 7 birim (Cuma–Cuma değişmez), hafta sonu 0; Python ve JS aynı sabitler. İleri tahmin hafta sonunda ilerlemez; hedef günü (ileri ve geçilmiş) hafta sonuna düşmez.
        import json; sys.path.insert(0, u.ROOT); import forecast as fc
        self.assertEqual([fc.etkin_gun(4, 4 + h) for h in (0, 1, 2, 7, 14, 371)], [0, 0, 0, 7, 14, 371]); self.assertEqual(fc.etkin_gun(-3, 4), 7)          # gün 4 = 5 Ocak 2024 Cuma
        for h, bek in ((3, 1.82), (4, 3.08), (5, 4.34), (6, 5.6), (3.5, 2.45)): self.assertAlmostEqual(fc.etkin_gun(4, 4 + h), bek, places=12)
        self.assertAlmostEqual(sum(fc.HAFTA_GUN_PAYI), 7, places=12); self.assertEqual(fc.HAFTA_GUN_PAYI[5:], (0, 0))
        js = ("const fs=require('fs'),vm=require('vm');const c={Math,Date,console};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+';this.m={estimateAt,reachDate,etkinGun,HAFTA_GUN_SONU,HAFTA_GUN_PAYI}',c);"
              "const v=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const out={hs:0,n:0,duz:true,cuma:true,sabit:[Array.from(c.m.HAFTA_GUN_SONU),Array.from(c.m.HAFTA_GUN_PAYI)],etkin:[3,4,5,6,3.5,7,371].map(h=>c.m.etkinGun(4,4+h))};"
              "for(const s of v.iller){const L=s.obs[s.obs.length-1];if(L[0]%7!==4)out.cuma=false;const e=h=>c.m.estimateAt(s,L[0]+h).n;if(!(e(1)===L[1]&&e(2)===L[1]&&e(3)>L[1]&&e(9)===e(8)&&e(8)===e(7)))out.duz=false;"
              "for(let k=1;k<=300;k++){for(const n of [L[1]+k*137,L[1]-k*137]){const r=c.m.reachDate(s,n);if(r.day===undefined||r.back)continue;out.n++;if(r.day%7>4)out.hs++;}}}console.log(JSON.stringify(out));")
        r = subprocess.run([u.NODE, "-e", js, os.path.join(u.ROOT, "assets", "tahmin-motoru.js"), os.path.join(u.ROOT, "tests", "golden", "motor_veri.json")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-500:]); o = json.loads(r.stdout)
        self.assertEqual((o["sabit"][0], o["sabit"][1]), (list(fc.HAFTA_GUN_SONU), list(fc.HAFTA_GUN_PAYI)))
        self.assertEqual(o["etkin"], [fc.etkin_gun(4, 4 + h) for h in (3, 4, 5, 6, 3.5, 7, 371)])                 # bit-bit aynı
        self.assertTrue(o["cuma"] and o["duz"]); self.assertGreater(o["n"], 5000); self.assertEqual(o["hs"], 0)

if __name__ == "__main__": unittest.main()
