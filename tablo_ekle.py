#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Yeni bir forum tablosunu siteye ekler.

  python3 tablo_ekle.py --tarih 2026-10-31 --plakalar plakalar.txt --hft hft.txt [--gun 7] [--hafta-no 44] [--mesaj '#970'] [--kuru]

plakalar.txt : "Güncel plakalar" listesi; 81 kayıt, her biri "il_kodu HARF NUMARA" (satır/virgül/boşlukla ayrılmış), örn. "01 BIE 404"
hft.txt      : dönem plaka sayıları (HFT sütunu), tablodaki sırayla; her satır "İl adı sayı" (örn. "K.Maraş 642", "İstanbul 9.451")

Yaptığı işler:
  * tarih hafta sonu/resmi tatile denk gelirse bir önceki iş gününe çeker (is_gunu.py)
  * data/tahmin_data.json ve index.html içindeki gömülü DATA'ya gözlemi ekler, hafta ve bterr'i yeniler
  * harf grubu değişen il varsa data/seri_gecisleri.csv'ye satır ekler
  * plakaTR/data/haftalik_plaka.csv'ye dönem satırlarını ekler (hafta = son 24 tablo; dosya yoksa hafta değişmez)
  * generate_il_pages.py ile il sayfalarını ve sitemap'i üretir
Commit/push yapmaz.
"""
import argparse, csv, datetime, json, os, re, subprocess, sys
from collections import defaultdict
import forecast as fc
from is_gunu import onceki_is_gunu

KOK = os.path.dirname(os.path.abspath(__file__))
EPOCH = datetime.date(2024, 1, 1)
A1 = "ABCDEFGHJKLMNPRSTUVYZ"; A2 = "ABCDEFGHIJKLMNOPRSTUVYZ"; A3 = "ABCDEFGHJKLMNPRSTUVYZ"
def to_n(l, num): return ((A1.index(l[0])*len(A2) + A2.index(l[1]))*len(A3) + A3.index(l[2]))*1000 + num
def inv(n):
    g = n // 1000
    return A1[g//len(A3)//len(A2)] + A2[g//len(A3) % len(A2)] + A3[g % len(A3)], n % 1000

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--tarih", required=True, help="tablonun tarihi (YYYY-MM-DD); hafta sonu/tatilse önceki iş gününe çekilir")
ap.add_argument("--plakalar", required=True); ap.add_argument("--hft", required=True)
ap.add_argument("--gun", type=int, help="dönemin gün sayısı (varsayılan: önceki tablodan bu yana geçen gün)")
ap.add_argument("--hafta-no", type=int, help="ISO hafta (varsayılan: hesaplanır)"); ap.add_argument("--mesaj", default="")
ap.add_argument("--plakatr", default=os.path.expanduser("~/work/plakaTR/data/haftalik_plaka.csv"))
ap.add_argument("--kuru", action="store_true", help="yalnızca doğrulama yap, dosyaları değiştirme")
a = ap.parse_args()

yayin = datetime.date.fromisoformat(a.tarih); tarih = onceki_is_gunu(yayin); day = (tarih - EPOCH).days
if tarih != yayin: print(f"tarih {yayin} iş günü değil → {tarih}")

# --- girdiler
plaka = {}
for m in re.finditer(r"(\d{2})\s+([A-Z]{3})\s+(\d{3})", open(a.plakalar, encoding="utf-8").read()):
    plaka[int(m[1])] = (m[2], int(m[3]))
hft = {}
for sat in open(a.hft, encoding="utf-8").read().splitlines():
    if sat.strip():
        ad, v = sat.strip().rsplit(None, 1); hft[ad] = int(v.replace(".", "").replace(",", ""))
d = json.load(open(os.path.join(KOK, "data/tahmin_data.json")))
hata = []
if sorted(plaka) != list(range(1, 82)): hata.append(f"plaka listesi 81 kayıt olmalı, {len(plaka)} var")
if set(hft) != {s["il"] for s in d["iller"]}: hata.append(f"HFT il adları uyuşmuyor: {sorted(set(hft) ^ {s['il'] for s in d['iller']})}")
if hata: sys.exit("HATA: " + "; ".join(hata))
print(f"HFT toplamı: {sum(hft.values()):,}".replace(",", "."), "(tablodaki toplamla karşılaştırın)")

# --- gözlemleri ekle
gecisler = []; uyari = []
for s in d["iller"]:
    l, num = plaka[s["kod"]]; n = to_n(l, num); son_gun, son_n = s["obs"][-1]
    if son_gun >= day: sys.exit(f"HATA: {s['il']} için {tarih} tarihli ya da daha yeni gözlem zaten var")
    ilerleme = n - son_n
    if ilerleme <= 0: uyari.append(f"{s['il']}: plaka geriye gitmiş ({inv(son_n)} → {l} {num})")
    elif abs(ilerleme - hft[s["il"]]) > max(8, 0.05*hft[s["il"]]): uyari.append(f"{s['il']}: ilerleme {ilerleme}, HFT {hft[s['il']]} (atlama ya da okuma hatası?)")
    if inv(son_n)[0][0] != l[0]:
        gecisler.append({"il": s["il"], "il_kodu": s["kod"], "onceki_harf_grubu": inv(son_n)[0][0], "yeni_harf_grubu": l[0],
                         "son_gorulen_eski": f"{s['kod']:02d} {inv(son_n)[0]} {inv(son_n)[1]:03d}", "son_gorulen_eski_tarih": (EPOCH + datetime.timedelta(days=son_gun)).isoformat(),
                         "ilk_gorulen_yeni": f"{s['kod']:02d} {l} {num:03d}", "ilk_gorulen_yeni_tarih": tarih.isoformat()})
    s["obs"].append([day, n])
for u in uyari: print("UYARI:", u)
for g in gecisler: print("harf grubu geçişi:", g["il"], g["son_gorulen_eski"], "→", g["ilk_gorulen_yeni"])
if a.kuru: sys.exit("kuru çalıştırma: dosyalar değiştirilmedi")

# --- plakaTR haftalık satırlar ve hafta (son 24 tablo)
rows = defaultdict(list); onceki = {}
if os.path.exists(a.plakatr):
    okunan = list(csv.DictReader(open(a.plakatr, encoding="utf-8"))); alanlar = list(okunan[0].keys())
    for x in okunan:
        if x["plaka_sayisi"]:
            rows[int(x["il_kodu"])].append((int(x["gun_sayisi"] or 7), int(x["plaka_sayisi"])))
            onceki[int(x["il_kodu"])] = x
    onceki_tarih = datetime.date.fromisoformat(next(iter(onceki.values()))["tarih"])
    gun = a.gun or (tarih - onceki_tarih).days
    sira = {ad: i+1 for i, ad in enumerate(hft)}; yeni = []
    for s in d["iller"]:
        p = onceki[s["kod"]]; h = hft[s["il"]]
        yeni.append({"tarih": tarih.isoformat(), "donem_baslangic": (onceki_tarih + datetime.timedelta(days=1)).isoformat(), "gun_sayisi": gun,
                     "iso_hafta": a.hafta_no or tarih.isocalendar()[1], "il_kodu": s["kod"], "il": s["il"], "plaka_sayisi": h, "sira": sira[s["il"]],
                     "yilici_kumulatif": (int(p["yilici_kumulatif"]) + h if tarih.year == onceki_tarih.year else h) if p["yilici_kumulatif"] else "",
                     "kumulatif_2018": int(p["kumulatif_2018"]) + h if p["kumulatif_2018"] else "", "kaynak": "tablo", "ek_id": "", "mesaj": a.mesaj})
        rows[s["kod"]].append((gun, h))
    yeni.sort(key=lambda r: r["sira"])
    with open(a.plakatr, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, alanlar); [w.writerow(r) for r in yeni]
    print(f"{a.plakatr}: {len(yeni)} satır eklendi (kümülatifler önceki tabloya HFT eklenerek türetildi; ek_id boş)")
else:
    print(f"UYARI: {a.plakatr} yok; hafta değerleri güncellenmedi")
for s in d["iller"]:
    if rows[s["kod"]]:
        w = rows[s["kod"]][-24:]; s["hafta"] = round(sum(x[1] for x in w) / sum(x[0] for x in w) * 7)
    s["bterr"] = fc.bterr([tuple(o) for o in s["obs"]])

# --- dosyalar
js = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
open(os.path.join(KOK, "data/tahmin_data.json"), "w").write(js)
yol = os.path.join(KOK, "index.html"); h = open(yol).read()
h2 = re.sub(r"const DATA = .*?;\n", lambda m: "const DATA = " + js + ";\n", h, count=1); assert h2 != h; open(yol, "w").write(h2)
if gecisler:
    yol = os.path.join(KOK, "data/seri_gecisleri.csv"); ham = open(yol, "rb").read(); nl = "\r\n" if b"\r\n" in ham else "\n"
    alan = list(csv.DictReader(open(yol, encoding="utf-8")).fieldnames)
    with open(yol, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, alan, lineterminator=nl); [w.writerow(g) for g in gecisler]
subprocess.check_call([sys.executable, "generate_il_pages.py"], cwd=KOK)
print("tamam — git diff ile bakıp commit/push edin")
