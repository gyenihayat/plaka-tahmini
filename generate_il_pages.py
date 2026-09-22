#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""81 il sayfasını data/tahmin_data.json + data/seri_gecisleri.csv'den üretir; sitemap.xml'i yeniler."""
import json, csv, datetime, statistics, html

A1="ABCDEFGHJKLMNPRSTUVYZ"; A2="ABCDEFGHIJKLMNOPRSTUVYZ"; A3="ABCDEFGHJKLMNPRSTUVYZ"
def inv(n):
    n = round(n); num = max(1, min(999, n % 1000)); g = n // 1000
    return A1[g//len(A3)//len(A2)] + A2[g//len(A3)%len(A2)] + A3[g%len(A3)], num
EPOCH = datetime.date(2024,1,1)
BASE = "https://plaka-tahmini.vercel.app"
TAM = {"K.Maraş":"Kahramanmaraş", "Afyon":"Afyonkarahisar"}
def slug(s):
    t = str.maketrans("çğıöşüÇĞİÖŞÜâ. ","cgiosucgiosua--")
    return s.translate(t).lower().replace("-","")
AYLAR = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
today = datetime.date.today()
d = json.load(open("data/tahmin_data.json"))
gec = list(csv.DictReader(open("data/seri_gecisleri.csv")))
def robust_rate(o):
    upto = o[-1][0]; window = 180
    w = [x for x in o if x[0] > upto-window]
    while len(w) < 10 and window < 4000:
        window *= 2; w = [x for x in o if x[0] > upto-window]
    rates=[(w[i][1]-w[i-1][1])/(w[i][0]-w[i-1][0]) for i in range(1,len(w)) if w[i][0]>w[i-1][0]]
    return max(statistics.median(rates), 0.01) if rates else 0.01
def tr_date(d_): return f"{d_.day} {AYLAR[d_.month-1]} {d_.year}"
iller = sorted(d["iller"], key=lambda s: s["kod"])
nav = " · ".join(f'<a href="/il/{slug(TAM.get(s["il"], s["il"]))}">{html.escape(TAM.get(s["il"], s["il"]))}</a>' for s in iller)
CSS = """*{box-sizing:border-box}body{margin:0;background:#f5f5f1;color:#15171c;font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:16px;line-height:1.55}
.wrap{max-width:760px;margin:0 auto;padding:44px 24px 60px}h1{font-family:"Barlow Condensed","Arial Narrow",sans-serif;font-size:clamp(34px,6vw,54px);font-weight:700;line-height:1.05;margin:0}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#7d8491;margin-bottom:10px}
.plate{display:inline-flex;align-items:stretch;border:2.5px solid #15171c;border-radius:8px;overflow:hidden;background:#fff;color:#111;font-family:"Barlow Condensed",sans-serif;font-weight:600;letter-spacing:.06em;font-size:38px;line-height:1;margin:16px 0 6px}
.plate .band{background:#1f4fb0;color:#fff;font-size:12px;font-weight:600;display:flex;align-items:flex-end;justify-content:center;padding:5px 6px 4px;width:26px}
.plate .num{padding:10px 15px 8px;white-space:nowrap}
.tag{display:inline-block;font-size:11px;letter-spacing:.09em;text-transform:uppercase;padding:3px 9px;border-radius:99px;font-weight:600;color:#7a3fb3;border:1.5px solid currentColor;vertical-align:middle;margin-left:10px}
.card{background:#fcfcfa;border:1px solid #dcdfe5;border-radius:12px;padding:16px 20px;margin:16px 0}
.meta{font-size:14px;color:#4d5461}.meta b{color:#15171c}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:6px 8px;border-bottom:1px solid #e9ebef}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#7d8491}
a{color:#2a78d6}.cta{display:inline-block;background:#e3eefb;border:1px solid #2a78d6;border-radius:9px;padding:10px 16px;font-weight:600;text-decoration:none;margin:8px 0}
.nav{font-size:13px;color:#7d8491;border-top:1px solid #dcdfe5;padding-top:16px;margin-top:30px;line-height:2}
.mono{font-family:"IBM Plex Mono",monospace}
h2{font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:17px;font-weight:600;margin:0 0 8px;line-height:1.3}
h3{font-size:14px;font-weight:600;margin:12px 0 4px;line-height:1.4}"""
urls = [BASE + "/"]
for s in iller:
    il = s["il"]; ad = TAM.get(il, il); sl = slug(ad); kod = f"{s['kod']:02d}"
    o = s["obs"]; last = o[-1]
    rate = robust_rate(o)
    last_d = EPOCH + datetime.timedelta(days=last[0])
    est_n = last[1] + rate * ((today - last_d).days)
    el, en = inv(est_n); ll, ln = inv(last[1])
    hafta_seri = rate*7/1000
    trans = [t for t in gec if t["il"] == il]
    rows = "".join(f"<tr><td>{t['ilk_gorulen_yeni_tarih'][8:10]}.{t['ilk_gorulen_yeni_tarih'][5:7]}.{t['ilk_gorulen_yeni_tarih'][:4]}</td><td class='mono'>{t['onceki_harf_grubu']} → {t['yeni_harf_grubu']}</td><td class='mono'>{html.escape(t['son_gorulen_eski'])} → {html.escape(t['ilk_gorulen_yeni'])}</td></tr>" for t in trans)
    gecis_html = f"<div class='card'><h2>Harf grubu geçişleri (Şubat 2024'ten beri)</h2><table><tr><th>Tarih</th><th>Grup</th><th>Seri</th></tr>{rows}</table></div>" if trans else f"<div class='card'><h2>Harf grubu geçişleri (Şubat 2024'ten beri)</h2><p class='meta' style='margin:0'>{html.escape(ad)}, Şubat 2024'ten bu yana <b>{ll[0]}</b> harf grubunda ilerliyor; bu dönemde grup değişimi yaşanmadı.</p></div>"
    obs5 = o[-5:]
    obs_rows = ""
    for day_, n_ in reversed(obs5):
        od = EPOCH + datetime.timedelta(days=day_)
        osr, onum = inv(n_)
        obs_rows += f"<tr><td>{od.strftime('%d.%m.%Y')}</td><td class='mono'>{kod} {osr} {onum:03d}</td></tr>"
    obs_ozet = ""
    if len(obs5) >= 2:
        d0 = EPOCH + datetime.timedelta(days=obs5[0][0]); d1 = EPOCH + datetime.timedelta(days=obs5[-1][0])
        s0, _ = inv(obs5[0][1]); s1, _ = inv(obs5[-1][1])
        if s0 != s1:
            obs_ozet = f"<p class='meta'>Kayıtlı son gözlemlerde seri, {tr_date(d0)} – {tr_date(d1)} arasında <span class='mono'>{s0}</span> serisinden <span class='mono'>{s1}</span> serisine ilerlemiştir.</p>"
        else:
            obs_ozet = f"<p class='meta'>Kayıtlı son gözlemlerde ({tr_date(d0)} – {tr_date(d1)}) {html.escape(ad)} plakaları <span class='mono'>{s0}</span> serisi içinde ilerlemiştir.</p>"
    gozlem_html = f"<div class='card'><h2>Son plaka gözlemleri</h2>{obs_ozet}<table><tr><th>Tarih</th><th>Gözlenen seri</th></tr>{obs_rows}</table></div>"
    sure = "birkaç gün" if hafta_seri > 3 else ("yaklaşık bir hafta" if hafta_seri > 0.9 else (f"yaklaşık {round(1/hafta_seri)} hafta" if hafta_seri > 0.12 else f"aylar"))
    title = f"{ad} Plaka Sırası Hangi Harfte? Güncel Seri ({today.year})"
    desc = f"{ad} plaka sırası hangi harfte? Güncel tahmini seri {kod} {el}; son gözlem {kod} {ll} {ln:03d} ({tr_date(last_d)}). İstediğiniz plakanın tahmini çıkış tarihini hesaplayın."
    breadcrumb = json.dumps({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"Plaka Tahmini","item":f"{BASE}/"},
        {"@type":"ListItem","position":2,"name":f"{ad} Plaka Sırası","item":f"{BASE}/il/{sl}"}]}, ensure_ascii=False, separators=(",",":"))
    page = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{BASE}/il/{sl}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{BASE}/il/{sl}"><meta property="og:image" content="{BASE}/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:locale" content="tr_TR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(title)}"><meta name="twitter:description" content="{html.escape(desc)}"><meta name="twitter:image" content="{BASE}/og.png">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔮</text></svg>">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono&display=swap">
<style>{CSS}</style>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{{"@type":"Question","name":"{html.escape(ad)} bugün hangi plaka serisinde?","acceptedAnswer":{{"@type":"Answer","text":"Güncel tahmin: {kod} {el} serisi. Son doğrulanmış gözlem {tr_date(last_d)} tarihinde {kod} {ll} {ln:03d}."}}}},{{"@type":"Question","name":"{html.escape(ad)} plakada bir harf serisi ne kadar dayanıyor?","acceptedAnswer":{{"@type":"Answer","text":"Son aylarda haftada yaklaşık {hafta_seri:.1f} seri; 999 plakalık bir seri {sure} içinde tükeniyor."}}}}]}}</script>
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body><div class="wrap">
<div class="eyebrow"><a href="/" style="color:inherit;text-decoration:none">Plaka Tahmini</a> · {kod} {html.escape(ad)}</div>
<h1>{html.escape(ad)} Plaka Sırası Hangi Harfte?</h1>
<p>Güncel gözlemlere göre {html.escape(ad)} ilinde plaka sırası şu anda tahmini olarak <b class="mono">{kod} {el}</b> serisi civarındadır. Son doğrulanmış gözlem {tr_date(last_d)} tarihinde <b class="mono">{kod} {ll} {ln:03d}</b> olarak kaydedilmiştir. Aşağıdaki araçla istediğiniz plakanın yaklaşık ne zaman çıkacağını görebilirsiniz.</p>
<div><span class="plate"><span class="band">TR</span><span class="num">{kod} {el} {en:03d}</span></span><span class="tag">tahmin · {tr_date(today)}</span></div>
<p class="meta">{html.escape(ad)} son aylarda haftada ortalama <b>{(s['hafta'] or 0):,} plaka</b> basıyor ve <b>~{hafta_seri:.1f} harf serisi</b> ilerliyor{" — bir seri (999 plaka) " + sure + " dayanıyor" if hafta_seri <= 3 else ""} (kaynak: wowTURKEY / Güven Hoca haftalık tabloları).</p>
{gozlem_html}
{gecis_html}
<p class="meta">Yukarıdaki güncel seri, ilin son aylardaki ilerleme hızının bugüne uzatılmış tahminidir ve her hafta yeni tablo verisiyle güncellenir. Belirli bir tarihte hangi serinin verileceğini, istediğiniz seriye ne zaman ulaşılacağını ve atlanacak serileri hesaba katan canlı aracı kullanın:</p>
<a class="cta" href="/?il={s['kod']}">🔮 {html.escape(ad)} için canlı tahmin aracı →</a>
<div class="card">
<h2>Sık sorulan sorular</h2>
<h3>{html.escape(ad)} bugün hangi plaka serisinde?</h3>
<p class="meta" style="margin:0 0 6px">Güncel tahminimiz <span class="mono">{kod} {el}</span> serisi. Kayıtlı en son gözlem {tr_date(last_d)} tarihli haftalık tabloda <span class="mono">{kod} {ll} {ln:03d}</span> idi; aradaki günler ilin olağan hızıyla ileri sarılır ve sayfa her hafta yeni tabloyla güncellenir.</p>
<h3>{html.escape(ad)} plakada bir harf serisi ne kadar dayanıyor?</h3>
<p class="meta" style="margin:0 0 6px">Son aylarda haftada ~{hafta_seri:.1f} seri ilerliyor; yani 999 plakalık bir seri {sure} içinde tükeniyor.</p>
<h3>Belirli bir plakaya ne zaman gelinir?</h3>
<p class="meta" style="margin:0"><a href="/?il={s['kod']}">Tahmin aracına</a> istediğiniz seriyi yazın (örn. <span class="mono">{el[0]}ZZ 999</span>); verilmeyeceğini düşündüğünüz serileri de hesaptan çıkarabilirsiniz.</p>
</div>
<div class="nav"><b>Tüm iller:</b> {nav}</div>
<p class="meta" style="font-size:12px;color:#7d8491;margin-top:14px">Veri: wowturkey.com "Türkiye Genelindeki Araç Plakalarının Gelişimi" başlığı (Güven_Hoca). Sayı biçimleri yaklaşıktır; ilk/son harfte I ve O kullanılmaz.</p>
</div></body></html>"""
    open(f"il/{sl}.html","w").write(page.replace(",", ".", 0))
    urls.append(f"{BASE}/il/{sl}")
open("sitemap.xml","w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(f"  <url><loc>{u}</loc><lastmod>{today.isoformat()}</lastmod><changefreq>weekly</changefreq></url>" for u in urls) + "\n</urlset>\n")
print(len(iller), "il sayfası +", "sitemap", len(urls), "URL")
