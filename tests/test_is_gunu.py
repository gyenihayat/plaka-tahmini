"""is_gunu.py: 2024-2028 resmi tatil takvimi, iş günü kuralları ve takvim kapsam koruması.
Beklenen listeler Diyanet resmi tatil tablolarından elle yazılmıştır (2027: icerik=159, 2028: icerik=193)."""
import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import is_gunu as ig
D = dt.date
GUN = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

# (tarih, gün adı) -- Diyanet tablosundaki "1 gün" satırları (tam gün resmi tatil)
TAM = {
  2027: [(D(2027,1,1),"Cum"), (D(2027,3,9),"Sal"), (D(2027,3,10),"Çar"), (D(2027,3,11),"Per"), (D(2027,4,23),"Cum"), (D(2027,5,1),"Cmt"),
         (D(2027,5,16),"Paz"), (D(2027,5,17),"Pzt"), (D(2027,5,18),"Sal"), (D(2027,5,19),"Çar"), (D(2027,7,15),"Per"), (D(2027,8,30),"Pzt"), (D(2027,10,29),"Cum")],
  2028: [(D(2028,1,1),"Cmt"), (D(2028,2,26),"Cmt"), (D(2028,2,27),"Paz"), (D(2028,2,28),"Pzt"), (D(2028,4,23),"Paz"), (D(2028,5,1),"Pzt"),
         (D(2028,5,5),"Cum"), (D(2028,5,6),"Cmt"), (D(2028,5,7),"Paz"), (D(2028,5,8),"Pzt"), (D(2028,5,19),"Cum"), (D(2028,7,15),"Cmt"), (D(2028,8,30),"Çar"), (D(2028,10,29),"Paz")],
}
# Diyanet "1/2 gün" satırları (arifeler ve 28 Ekim öğleden sonra): iş günü kabul edilir
YARIM = {
  2027: [(D(2027,3,8),"Pzt"), (D(2027,5,15),"Cmt"), (D(2027,10,28),"Per")],
  2028: [(D(2028,2,25),"Cum"), (D(2028,5,4),"Per"), (D(2028,10,28),"Cmt")],
}

class TakvimVerisi(unittest.TestCase):
    def test_beklenen_listelerin_gun_adlari_takvimle_uyumlu(self):
        for tablo in (TAM, YARIM):
            for y, satirlar in tablo.items():
                for d, ad in satirlar: self.assertEqual(GUN[d.weekday()], ad, f"{d} gün adı")

    def test_tam_gun_tatiller_diyanet_tablosuyla_birebir(self):
        for y, satirlar in TAM.items():
            self.assertEqual({d for d in ig.RESMI_TATIL if d.year == y}, {d for d, _ in satirlar}, f"{y} tam gün tatiller")

    def test_yarim_gunler_tatil_kumesinde_degil(self):
        for y, satirlar in YARIM.items():
            for d, _ in satirlar: self.assertNotIn(d, ig.RESMI_TATIL, f"{d} yarım gün")

    def test_2024_2026_onceki_tanimla_birebir(self):
        # Bu değişiklikten önceki is_gunu.py'nin 2024-2026 tanımı (değişmemeli)
        def rng(a, b): return {a + dt.timedelta(days=i) for i in range((b - a).days + 1)}
        eski = ({D(y,1,1) for y in (2024,2025,2026)} | {D(y,4,23) for y in (2024,2025,2026)} | {D(y,5,1) for y in (2024,2025,2026)}
                | {D(y,5,19) for y in (2024,2025,2026)} | {D(y,7,15) for y in (2024,2025,2026)} | {D(y,8,30) for y in (2024,2025,2026)} | {D(y,10,29) for y in (2024,2025,2026)}
                | rng(D(2024,4,10),D(2024,4,12)) | rng(D(2024,6,16),D(2024,6,19)) | rng(D(2025,3,30),D(2025,4,1)) | rng(D(2025,6,6),D(2025,6,9))
                | rng(D(2026,3,20),D(2026,3,22)) | rng(D(2026,5,27),D(2026,5,30)))
        self.assertEqual({d for d in ig.RESMI_TATIL if d.year <= 2026}, eski)

    def test_her_yil_iki_bayram_ve_yedi_sabit_tatil(self):
        for y, (ramazan, kurban) in ig.BAYRAMLAR.items():
            self.assertTrue(ramazan and kurban and ramazan.isdisjoint(kurban))
            for m, g in ig.SABIT_TATIL: self.assertIn(D(y, m, g), ig.RESMI_TATIL)
        self.assertEqual(ig.TAKVIM_SON_YIL, max(ig.BAYRAMLAR)); self.assertEqual(ig.TAKVIM_SON_YIL, 2028)

class IsGunuKurallari(unittest.TestCase):
    def test_hafta_sonu_is_gunu_degil(self):
        d = D(2024, 1, 1)
        while d <= D(2028, 12, 31):
            if d.weekday() >= 5: self.assertFalse(ig.is_is_gunu(d), d)
            d += dt.timedelta(days=1)

    def test_tam_gun_tatiller_is_gunu_degil(self):
        for satirlar in TAM.values():
            for d, _ in satirlar: self.assertFalse(ig.is_is_gunu(d), d)

    def test_hafta_ici_yarim_gunler_is_gunu(self):
        for d in (D(2027,3,8), D(2027,10,28), D(2028,2,25), D(2028,5,4)): self.assertTrue(ig.is_is_gunu(d), d)

    def test_istenen_tarihler_icin_onceki_is_gunu(self):
        beklenen = {
            D(2027,7,15): D(2027,7,14),    # Perşembe -> Çarşamba
            D(2027,8,30): D(2027,8,27),    # Pazartesi -> önceki Cuma
            D(2027,10,29): D(2027,10,28),  # Cuma -> Perşembe (28 Ekim yarım gün, iş günü)
            D(2027,10,30): D(2027,10,28), D(2027,10,31): D(2027,10,28),
            D(2028,2,28): D(2028,2,25),    # Ramazan 3. gün (Pzt) -> Cuma (arife yarım gün, iş günü)
            D(2028,5,1): D(2028,4,28),     # Emek ve Dayanışma Günü (Pzt) -> Cuma
            D(2028,5,8): D(2028,5,4),      # Kurban 4. gün (Pzt) -> Perşembe (arife yarım gün)
            D(2028,5,5): D(2028,5,4), D(2028,5,19): D(2028,5,18), D(2028,8,30): D(2028,8,29),
            D(2028,5,9): D(2028,5,9), D(2027,3,12): D(2027,3,12),   # tatili izleyen iş günü kendisi
        }
        for d, e in beklenen.items(): self.assertEqual(ig.onceki_is_gunu(d), e, f"{d}")

    def test_2026_davranisi_ayni(self):
        for d, e in {D(2026,10,29): D(2026,10,28), D(2026,10,30): D(2026,10,30), D(2026,5,30): D(2026,5,26), D(2026,3,22): D(2026,3,19),
                     D(2026,8,30): D(2026,8,28), D(2026,7,15): D(2026,7,14)}.items(): self.assertEqual(ig.onceki_is_gunu(d), e, f"{d}")

class KapsamKorumasi(unittest.TestCase):
    def test_kapsam_disi_tarih_hata_verir(self):
        for d in (D(2029,1,2), D(2030,6,1), D(2023,12,29)):
            with self.assertRaises(ig.TakvimKapsamHatasi): ig.onceki_is_gunu(d)
            with self.assertRaises(ig.TakvimKapsamHatasi): ig.is_is_gunu(d)

    def test_hata_bir_value_error_ve_yonlendirici_mesaj(self):
        with self.assertRaises(ValueError) as c: ig.onceki_is_gunu(D(2029, 1, 2))
        self.assertIn("BAYRAMLAR", str(c.exception)); self.assertIn("2029", str(c.exception))

    def test_tahmin_penceresi_kapsam_siniri(self):
        p = dt.timedelta(days=ig.TAHMIN_PENCERESI_GUN)
        son_gecerli = D(ig.TAKVIM_SON_YIL, 12, 31) - p
        ig.kapsam_kontrol(son_gecerli, son_gecerli + p)                     # pencere tam 31 Aralık'ta bitiyor: geçerli
        self.assertEqual(son_gecerli, D(2028, 7, 3))
        with self.assertRaises(ig.TakvimKapsamHatasi): ig.kapsam_kontrol(son_gecerli + dt.timedelta(days=1), son_gecerli + dt.timedelta(days=1) + p)

    def test_rollback_yil_basinda_hata_vermez(self):
        self.assertEqual(ig.onceki_is_gunu(D(2024, 1, 1)), D(2023, 12, 29))   # 1 Ocak 2024 tatil: geri yürüme kapsam dışına taşabilir
        self.assertEqual(ig.onceki_is_gunu(D(2028, 12, 31)), D(2028, 12, 29))

    def test_pencere_sabiti_tek_kaynak(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generate_il_pages.py"), encoding="utf-8") as f: src = f.read()
        self.assertEqual(ig.TAHMIN_PENCERESI_GUN, 181)
        self.assertNotIn("range(181)", src); self.assertNotIn("days=181", src)

if __name__ == "__main__": unittest.main()
