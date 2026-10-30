"""İl sayfasındaki plaka tahmin aracı: (1) 81 ilde girdi sınıflandırması ve hata mesajları, (2) aynı girişte ana sayfa hesaplayıcısıyla aynı sonuç
(Chrome ile gerçek ana sayfa arayüzü sürülür; normal, geçilmiş, kayıt öncesi, atlanacak seri, uzak tarih, sınır/geçersiz girdiler)."""
import datetime as dt, functools, glob, http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as u
from test_il_sayfasi import veri, sayfa, slug, TAM, inv
from test_ana_sayfa_regresyon import CHROME
E0 = dt.date(2024, 1, 1)

def node_arac(senaryolar):
    d = tempfile.mkdtemp(prefix="plaka_ilarac_")
    try:
        yol = os.path.join(d, "s.json")
        with open(yol, "w", encoding="utf-8") as f: json.dump(senaryolar, f)
        r = subprocess.run([u.NODE, os.path.join(u.ROOT, "tests", "ui", "il_arac_cikti.js"), yol], capture_output=True, text=True); assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    finally: shutil.rmtree(d, ignore_errors=True)
def sayfa_yolu(s): return os.path.join(u.ROOT, "il", slug(TAM.get(s["il"], s["il"])) + ".html")
def hedefler(s):
    g, n = s["obs"][-1]; sr, _ = inv(n)
    return ["BZZ 999", "AAA 001", "ZZZ 999", f"{sr[0]}ZZ 999", f"{inv(n + 3000)[0]} 500", f"{sr} 999", f"{sr} 001", "abc 12", "IAA", "", "ABC 5000", "XYZ 1", f"{sr}"]
def gun(ddmmyyyy): d, m, y = map(int, ddmmyyyy.split(".")); return (dt.date(y, m, d) - E0).days
def ana_sayfa_ayristir(t, warn):
    if t.startswith("Bu seri, atlanacaklar listenizde"): return {"tip": "dislanan"}
    if t.startswith("Bu ilde seri ilerlemesi"): return {"tip": "yok"}
    m = re.match(r"Geçildi — kayıtlara göre (\d\d\.\d\d\.\d{4}) civarında", t)
    if m: return {"tip": "gecildi", "gun": gun(m[1])}
    m = re.match(r"Tahmini: (\d\d\.\d\d\.\d{4})\s*\(±(\d+) gün · kayıtlarımızdan önce", t)
    if m: return {"tip": "geriye", "gun": gun(m[1]), "err": int(m[2])}
    m = re.match(r"Tahmini ulaşma: (\d\d\.\d\d\.\d{4})\s*\(±(\d+) gün(?:.*?aradaki (\d+) atlanan)?", t.replace("\xa0", " "))
    if m: return {"tip": "tahmin", "gun": gun(m[1]), "err": int(m[2]), "atlanan": int(m[3] or 0)}
    return {"tip": "hata", "warn": warn}

@unittest.skipUnless(u.NODE, "node kurulu değil")
class GirdiSiniflandirma(unittest.TestCase):
    def test_81_ilde_girdiler(self):
        iller = veri(); sn = []
        for s in iller:
            kod = s["kod"]; diger = 1 if kod != 1 else 2
            for h in ("BZZ 999", "99 AAA", "00 AAA", f"{diger:02d} AAA", f"{kod:02d} BZZ 999", f"{kod} BZZ", "", "IAA", "ABC 5000", "XYZ 1", "bj 1"): sn.append({"sayfa": sayfa_yolu(s), "hedef": h})
            sn.append({"sayfa": sayfa_yolu(s), "hedef": "BZZ 999", "excl": "SXY"})
        sonuc = node_arac(sn); i = 0
        for s in iller:
            kod = s["kod"]; diger = 1 if kod != 1 else 2; r = sonuc[i:i+12]; i += 12
            self.assertIn(r[0]["tip"], ("tahmin", "gecildi", "geriye", "yok"), s["il"])      # "yok": çok yavaş ilerleyen ilde motor sonuç üretemez
            self.assertEqual((r[1]["tip"], r[2]["tip"]), ("hata", "hata")); self.assertIn("Geçersiz il kodu", r[1]["mesaj"])
            self.assertEqual(r[3]["tip"], "baska_il"); self.assertEqual(r[3]["href"], f"/?il={diger}"); self.assertIn(f"({kod:02d})", r[3]["mesaj"])
            self.assertEqual(r[4]["tip"], r[0]["tip"]); self.assertEqual({k: r[4].get(k) for k in ("gun", "err")}, {k: r[0].get(k) for k in ("gun", "err")})   # kendi il kodu yazılabilir
            self.assertIn(r[5]["tip"], ("tahmin", "gecildi", "geriye", "yok"))
            self.assertEqual(r[6]["tip"], "hata"); self.assertIn("Seri okunamadı", r[6]["mesaj"])
            self.assertEqual(r[7]["tip"], "hata"); self.assertIn("kullanılmıyor", r[7]["mesaj"])
            self.assertEqual((r[8]["tip"], r[9]["tip"]), ("hata", "hata")); self.assertEqual(r[10]["tip"], "hata")        # 5000: 3 haneyi aşar; "bj 1": 3 harf değil
            self.assertEqual(r[11]["tip"], "hata"); self.assertIn("Atlanacak seriler okunamadı", r[11]["mesaj"])

    def test_sonuc_alanlari_tutarli(self):
        for s, r in zip(veri(), node_arac([{"sayfa": sayfa_yolu(s), "hedef": f"{inv(s['obs'][-1][1] + 5000)[0]} 500"} for s in veri()])):
            self.assertEqual(r["tip"], "tahmin", s["il"]); self.assertGreater(r["gun"], s["obs"][-1][0]); self.assertGreaterEqual(r["err"], 2)
            self.assertTrue(re.match(rf"{s['kod']:02d} [A-Z]{{3}} 500", r["plaka"]))

@unittest.skipUnless(CHROME and u.NODE, "Chrome/Node yok")
class AnaSayfaIleEslik(unittest.TestCase):
    def test_ayni_girdi_ayni_sonuc(self):
        iller = [s for s in veri() if s["kod"] in (1, 6, 12, 16, 20, 26, 34, 35, 42, 43, 63, 5)]
        sn = [{"il": s["il"], "hedef": h, "excl": e, "sayfa": sayfa_yolu(s)} for s in iller for h in hedefler(s) for e in ("", "SXX, TXX", "BAA-BCZ", inv(s["obs"][-1][1])[0][0] + "XX")]
        d = tempfile.mkdtemp(prefix="plaka_parite_")
        try:
            shutil.copy(os.path.join(u.ROOT, "index.html"), d); shutil.copytree(os.path.join(u.ROOT, "assets"), os.path.join(d, "assets"))
            with open(os.path.join(u.ROOT, "tests", "ui", "ana_sayfa_hedef.html"), encoding="utf-8") as f: h = f.read()
            with open(os.path.join(d, "h.html"), "w", encoding="utf-8") as f: f.write(h.replace("__SENARYOLAR__", json.dumps([{k: x[k] for k in ("il", "hedef", "excl")} for x in sn], ensure_ascii=False)))
            s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); port = s_.getsockname()[1]; s_.close()
            class Sessiz(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k): pass
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Sessiz, directory=d)); threading.Thread(target=srv.serve_forever, daemon=True).start()
            try: r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=60000", "--dump-dom", f"http://127.0.0.1:{port}/h.html"], capture_output=True, text=True, timeout=180)
            finally: srv.shutdown(); srv.server_close()
            import html as _h
            m = re.search(r"SONUC (\[.*?\])\s*</pre>", r.stdout, re.S); self.assertIsNotNone(m, r.stderr[-300:])
            ana = json.loads(_h.unescape(m[1]))
        finally: shutil.rmtree(d, ignore_errors=True)
        il_sonuc = node_arac(sn); self.assertEqual(len(ana), len(sn)); sayac = {}; fark = []
        for x, a, b in zip(sn, ana, il_sonuc):
            pa = ana_sayfa_ayristir(a["out"], a["warn"]); tip = b["tip"]; sayac[(pa["tip"])] = sayac.get(pa["tip"], 0) + 1
            if pa["tip"] == "hata": ok = tip == "hata" and (("Seri okunamadı" in a["warn"]) == ("Seri okunamadı" in b["mesaj"])) and (("kullanılmıyor" in a["warn"]) == ("kullanılmıyor" in b["mesaj"]))
            else: ok = tip == pa["tip"] and all(b.get(k) == pa[k] for k in ("gun", "err", "atlanan") if k in pa and tip != "dislanan")
            if tip == "tahmin" and pa["tip"] == "tahmin":
                ok = ok and b["atlanan"] == pa["atlanan"]
                my = re.search(r"([\d.,]+) yıl sonra", a["out"].replace("\xa0", " "))                    # "x yıl sonra": ikisi de Türkiye takvim gününe göre
                if b["yil"] > 1: ok = ok and my is not None and float(my[1].replace(".", "").replace(",", ".")) == round(b["yil"], 1)
                else: ok = ok and my is None
            if not ok: fark.append((x["il"], x["hedef"], x["excl"], pa, b))
        self.assertEqual(fark[:3], [], f"{len(fark)}/{len(sn)} fark")
        for tip in ("tahmin", "gecildi", "geriye", "dislanan", "hata"): self.assertGreater(sayac.get(tip, 0), 0, f"{tip} durumu hiç sınanmadı: {sayac}")
        self.assertGreater(sum(1 for a in ana if "atlanan seri" in a["out"]), 0)                  # atlanacak seri düşümü gerçekten sınandı

if __name__ == "__main__": unittest.main()
