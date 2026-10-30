"""Yeniden üretim kararlılığı: depodaki il sayfaları, kendi START tarihleriyle yeniden üretildiğinde
81 il HTML'i ve sitemap.xml baytça aynı olmalı (SEO etiketleri, tahmin değerleri, lastmod dahil).
Depodaki dosyalara dokunulmaz; üretim geçici bir kopyada yapılır."""
import glob, os, re, shutil, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u

class YenidenUretimKararli(unittest.TestCase):
    def test_81_sayfa_ve_sitemap_baytca_ayni(self):
        start = u.sayfa_bilgisi(os.path.join(u.ROOT, "il", "konya.html"))[0]
        d = u.kopya(ekstra=("sitemap.xml",))
        try:
            shutil.copytree(os.path.join(u.ROOT, "il"), os.path.join(d, "il"), dirs_exist_ok=True)
            r = u.uret(d, "--bugun", start); self.assertEqual(r.returncode, 0, r.stderr)
            sayfalar = sorted(glob.glob(os.path.join(u.ROOT, "il", "*.html"))); self.assertEqual(len(sayfalar), 81)
            farkli = []
            for yol in sayfalar + [os.path.join(u.ROOT, "sitemap.xml")]:
                gorece = os.path.relpath(yol, u.ROOT)
                with open(yol, "rb") as a, open(os.path.join(d, gorece), "rb") as b:
                    if a.read() != b.read(): farkli.append(gorece)
            self.assertEqual(farkli, [], f"START={start} ile yeniden üretimde değişen dosyalar")
        finally: shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__": unittest.main()
