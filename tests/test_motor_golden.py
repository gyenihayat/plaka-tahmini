"""Ortak motor (assets/tahmin-motoru.js): ana sayfadaki eski motorla üretilmiş altın çıktılarla birebir eşleşir; kaynak DOM/DATA'ya bağımlı değildir."""
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
        self.assertIn('<script src="/assets/takvim.js"></script>\n<script src="/assets/tahmin-motoru.js"></script>', h)
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

if __name__ == "__main__": unittest.main()
