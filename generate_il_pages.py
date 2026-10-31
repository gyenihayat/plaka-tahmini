#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""81 il sayfasını data/tahmin_data.json + data/seri_gecisleri.csv'den üretir; sitemap.xml'i yeniler."""
import json, csv, datetime, statistics, html, bisect, argparse, sys, re, os, hashlib, math
import forecast as fc
from is_gunu import RESMI_TATIL, onceki_is_gunu, kapsam_kontrol, TakvimKapsamHatasi, TAHMIN_PENCERESI_GUN, TAKVIM_ILK_YIL, TAKVIM_SON_YIL

A1="ABCDEFGHJKLMNPRSTUVYZ"; A2="ABCDEFGHIJKLMNOPRSTUVYZ"; A3="ABCDEFGHJKLMNPRSTUVYZ"
def inv(n):
    # Yuvarlama JS'teki Math.round ile AYNI olmalı (yarım değer yukarı): Python round() yarım değeri çift sayıya yuvarlar ve tam .5 tahminlerde canlı JS ile 1 sıra ayrışırdı.
    # Ham tahmin (forecast.py / ortak motor) iki tarafta bit-bit aynıdır; yalnızca gösterim yuvarlaması eşitlenir. Gözlemler tam sayıdır, etkilenmez.
    n = math.floor(n + 0.5); num = max(1, min(999, n % 1000)); g = n // 1000
    return A1[g//len(A3)//len(A2)] + A2[g//len(A3)%len(A2)] + A3[g%len(A3)], num
EPOCH = datetime.date(2024,1,1)
BASE = "https://plakatahmini.com"
TAM = {"K.Maraş":"Kahramanmaraş", "Afyon":"Afyonkarahisar"}
def slug(s):
    t = str.maketrans("çğıöşüÇĞİÖŞÜâ. ","cgiosucgiosua--")
    return s.translate(t).lower().replace("-","")
AYLAR = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
_ap = argparse.ArgumentParser(description=__doc__)
_ap.add_argument("--bugun", help="üretim tarihi (YYYY-MM-DD); varsayılan: bugün. Yalnızca tahmin tarihini/canlı tabloyu ve sitemap lastmod'unu etkiler; 'son gözlem' tarihleri her zaman data/tahmin_data.json'dan gelir")
_ap.add_argument("--iller", help="yalnızca bu il sayfalarını yaz (virgülle ayrılmış slug'lar, örn. konya,denizli); verilirse sitemap yazılmaz")
_args = _ap.parse_args()
SADECE = set(_args.iller.split(",")) if _args.iller else None
TR_UTC = datetime.timezone(datetime.timedelta(hours=3))     # Türkiye kalıcı UTC+3 (yaz saati yok); üretim makinesinin saat diliminden bağımsız
def tr_bugun(): return datetime.datetime.now(TR_UTC).date()
GERCEK_BUGUN = datetime.date.fromisoformat(_args.bugun) if _args.bugun else tr_bugun()   # Türkiye yerel takvim günü (sitemap lastmod için)
try:
    today = onceki_is_gunu(GERCEK_BUGUN)       # güncel tahminin referans günü: Türkiye tarihinin en yakın önceki iş günü (hafta sonu/tam gün resmî tatilde değişmez)
    kapsam_kontrol(today, today + datetime.timedelta(days=TAHMIN_PENCERESI_GUN))      # tatil takvimi kapsamı aşılıyorsa üretim hatası (sayfalar yazılmadan)
except TakvimKapsamHatasi as e:
    sys.exit(f"HATA: {e}")
if _args.bugun: print(f"NOT: --bugun {GERCEK_BUGUN}: tahmin referans günü {today}; son gözlem tarihleri veriden gelir", file=sys.stderr)   # tescil iş günlerinde yapılır: hafta sonu/resmi tatilde en yakın önceki iş gününe çekilir
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
def sayi(n): return f"{n:,.0f}".replace(",", ".")                 # Türkçe binlik ayracı: 1.802
def ondalik(x): return f"{x:.1f}".replace(".", ",")              # Türkçe ondalık ayracı: 1,8
ANA_SAYFA_KARTLARI = (34, 6, 35)   # ana sayfadaki büyük il kartları (plaka kodu): İstanbul, Ankara, İzmir; değerler veriden hesaplanır, sabit yazılmaz
# Analitik bilgilendirmesi (görünür, kısa). Doğrulanmamış iddia yok: çerez/saklama süresi gibi konular burada ele alınmaz, hizmetin kendi gizlilik sayfasına bağlanır.
OLCUM_NOTU_IL = ('<p class="olcum-notu">Bu sitede sayfa görüntüleme ve özellik kullanımı (hesaplama, il arama gibi) sayıları, üçüncü taraf bir analitik hizmeti olan '
                 '<a href="https://www.goatcounter.com/privacy" rel="noopener">GoatCounter</a> ile ölçülür; hizmete sayfa adresi, yönlendiren site ve tarayıcı/ekran bilgisi gibi standart ziyaret verileri iletilir. '
                 'Girdiğiniz plaka, il arama metni veya forma yazdığınız diğer içerikler gönderilmez.</p>')
OLCUM_NOTU_ANA = OLCUM_NOTU_IL   # ana sayfa ve il sayfaları aynı bilgilendirmeyi taşır (başka üçüncü taraf sayaç yok)
BAYAT_ESIK_GUN = 21   # son gözlem bundan eskiyse (üretim anında statik, ziyaret anında JS ile) kısa güncellik uyarısı gösterilir

CANLI_JS = """(function(){
function uyar(m){var u=document.getElementById("guncellik");if(!u)return;var t=u.querySelector("span");if(t)t.textContent=m;u.hidden=false;}
try{
var n=new Date(Date.now()+10800000),b=Date.UTC(n.getUTCFullYear(),n.getUTCMonth(),n.getUTCDate()),q="__GOZLEM__".split("-"),g=Date.UTC(+q[0],+q[1]-1,+q[2]);
if(Math.round((b-g)/864e5)>__ESIK__){var by=document.getElementById("bayat");if(by)by.hidden=false;}
}catch(x){console.error("plakatahmini: güncellik denetimi yapılamadı",x);uyar("Güncellik denetimi yapılamadı; son kayıtlı gözlem tarihine dikkat edin.");}
})();"""
iller = sorted(d["iller"], key=lambda s: s["kod"])
# Yalnızca il sayfalarındaki "← Ana sayfaya dön" bağlantısı (ana sayfa CSS'i değişmez): sade, küçük ama belirgin metin bağlantısı; odak halkası genel a:focus-visible kuralından gelir.
IL_CSS = ".geri{margin:0 0 4px}.geri a{display:inline-block;padding:8px 0;font-size:15px;font-weight:600;color:#1f63bb;text-decoration:none}.geri a:hover{text-decoration:underline}"
CSS = """*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0;background:#f5f5f1;color:#15171c;font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:16px;line-height:1.55}
.wrap{max-width:720px;margin:0 auto;padding:20px 16px 56px}a{color:#1f63bb}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:#5b6370;margin-bottom:8px}.eyebrow a{color:inherit;text-decoration:none}
h1{font-family:"Barlow Condensed","Arial Narrow",sans-serif;font-size:clamp(1.75rem,7vw,2.5rem);font-weight:700;line-height:1.1;margin:0 0 18px}
.e{font-size:13px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#5b6370;margin:0}
.buyuk{font-size:clamp(2.5rem,11vw,3.5rem);font-weight:600;line-height:1.05;letter-spacing:.02em;margin:4px 0 2px;white-space:nowrap}
.alt{margin:0;font-size:16px;color:#4d5461}.mono{font-family:"IBM Plex Mono",monospace}.nw{white-space:nowrap}
.metrik{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:18px 20px;margin:22px 0 4px}.metrik>div{margin:0}
.metrik dt{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#5b6370}
.metrik dd{margin:2px 0 0}.metrik .v{font-size:1.25rem;font-weight:600;line-height:1.3}.metrik .k{font-size:15px;color:#5b6370;line-height:1.4}
.cta{display:block;margin:22px 0 10px;background:#1f4fb0;color:#fff;text-align:center;font-weight:600;font-size:1.0625rem;padding:13px 16px;border-radius:10px;text-decoration:none}
.cta:hover{background:#18408f}.not{font-size:15px;color:#4d5461;margin:0 0 8px}
.uyari{background:#fff6e0;border:1px solid #e3c36a;color:#7a4a00;border-radius:9px;padding:10px 14px;font-size:15px;margin:10px 0}
.arac{margin:26px 0 8px;padding:18px 0;border-top:1px solid #dcdfe5}
h2{font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:1.25rem;font-weight:600;margin:0 0 10px;line-height:1.3}
label{display:block;font-weight:600;font-size:15px;margin-bottom:6px}
.alan{display:flex;gap:8px}.alan input{flex:1;min-width:0;font:600 1.125rem "IBM Plex Mono",monospace;text-transform:uppercase;padding:11px 12px;border:1.5px solid #8b94a5;border-radius:8px;background:#fff;color:#15171c}
.alan button{font:600 1rem "IBM Plex Sans",system-ui,sans-serif;padding:0 18px;border:1px solid #2a78d6;border-radius:8px;background:#e3eefb;color:#1f4fb0;cursor:pointer}
input:focus-visible,button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #f0a000;outline-offset:2px}
.alan input::placeholder,.gelismis input::placeholder{text-transform:none;color:#6b7280}.ipucu{font-size:15px;color:#4d5461;margin:8px 0 0}.gelismis{margin-top:10px;font-size:15px}.gelismis summary{cursor:pointer;color:#1f4fb0}.gelismis input{width:100%;margin-top:6px;font:600 1rem "IBM Plex Mono",monospace;text-transform:uppercase;padding:9px 10px;border:1.5px solid #8b94a5;border-radius:8px}
.sonuc{margin-top:14px;min-height:1px}.sonuc .s-b{font-size:1.5rem;font-weight:600;line-height:1.25;margin:0}.sonuc .s-a{font-size:15px;color:#4d5461;margin:2px 0 0}.sonuc .s-u{font-size:15px;color:#7a4a00;margin:6px 0 0}.sonuc .hata{color:#9b2c1d;font-weight:600;margin:0}
details.bolum{border-top:1px solid #dcdfe5;padding:12px 0}details.bolum>summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:12px}
details.bolum>summary::-webkit-details-marker{display:none}details.bolum>summary::after{content:"+";font-size:1.5rem;line-height:1;color:#5b6370}details.bolum[open]>summary::after{content:"−"}
details.bolum>summary h2{margin:0;font-size:1.25rem}.ic{padding-top:10px}.ic ul{padding-left:20px;margin:0}.ic li{margin:0 0 8px;font-size:15px}
.meta{font-size:15px;color:#4d5461;margin:0 0 8px}.meta b{color:#15171c}
table{border-collapse:collapse;width:100%;font-size:14px;border:1px solid #c5cad3}td,th{text-align:left;padding:6px 8px;border:1px solid #d5d9e0}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#5d6572;background:#eef0f3}
.yoy{overflow-x:auto;-webkit-overflow-scrolling:touch}.yoy table{min-width:560px}.yoy td.n,.yoy th.n{text-align:right;white-space:nowrap}
.yoy td.p{color:#5b6370;font-style:italic}.yoy tr.pct td{font-weight:600;background:#f3f4f7}.yoy .up{color:#1a7f4b}.yoy .dn{color:#b3402a}
.kaydir{overflow-x:auto;-webkit-overflow-scrolling:touch}td.mono{white-space:nowrap}.fn{font-size:14px;color:#5b6370;margin:8px 0 0}
.olcum-notu{font-size:14px;line-height:1.5;color:#5b6370;margin:22px 0 0}.iller p{margin:0 0 8px;font-size:15px;line-height:1.9}.iller b{display:inline-block;min-width:1.4em;color:#5b6370}.iller a{margin-right:8px;white-space:nowrap}
.tarih-arac select,.tarih-arac input[type=date]{display:block;width:100%;min-height:46px;font:inherit;font-size:1rem;padding:10px 12px;border:1.5px solid #8b94a5;border-radius:8px;background:#fff;color:#15171c}
.tarih-arac>.ipucu{margin:0 0 14px}.t-alanlar{display:grid;grid-template-columns:1fr;gap:12px}.t-btn{display:block;width:100%;min-height:46px;margin-top:14px;font:600 1rem "IBM Plex Sans",system-ui,sans-serif;padding:10px 20px;border:1px solid #2a78d6;border-radius:8px;background:#e3eefb;color:#1f4fb0;cursor:pointer}
.t-btn:hover{background:#d6e6f9}.t-hata{color:#9b2c1d;font-weight:600;font-size:15px;margin:10px 0 0}.t-hata:empty{display:none}
.t-sonuc{margin-top:16px;padding:14px 16px;background:#fcfcfa;border:1px solid #dcdfe5;border-radius:12px}.t-plaka{font-size:clamp(2.25rem,9vw,2.75rem);font-weight:600;line-height:1.1;letter-spacing:.02em;margin:0 0 6px;white-space:nowrap}
.t-alt{margin:0;font-size:15px;color:#4d5461;display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px}.t-etiket{display:inline-block;font-size:12px;letter-spacing:.09em;text-transform:uppercase;padding:3px 9px;border-radius:99px;font-weight:600;border:1.5px solid currentColor}.t-etiket.tahmin,.t-etiket.geri{color:#7a3fb3}.t-etiket.kayit{color:#0a7a2f}.t-etiket.kaba{color:#9a5b00}.t-etiket.kalibre{color:#1f4fb0}.t-etiket.cokkaba{color:#9b2c1d}.t-etiket{max-width:100%;line-height:1.35}
.t-atla{margin:8px 0 0;color:#7a4a00;font-weight:600}.tarih-arac .uyari{margin:12px 0 0}.t-ikincil{margin-top:14px;font:inherit;font-size:.9375rem;padding:9px 14px;border:1px solid #8b94a5;border-radius:8px;background:#fff;color:#4d5461;cursor:pointer}.t-ikincil:hover{background:#e3eefb;color:#15171c}
@media (min-width:520px){.t-alanlar.t-iki{grid-template-columns:1fr 1fr}.t-btn{display:inline-block;width:auto;min-width:220px}}"""

# --- "Belirli bir tarihte hangi plakada?" aracı: ana sayfa ve 81 il sayfası AYNI işaretlemeyi kullanır (davranış: assets/tarih-sorgu.js) ---------------------------------
TARIH_BASLIK = "Belirli bir tarihte hangi plakada?"
def tarih_arac_html(ana):
    """ana=True: ana sayfa (il seçimi + ikincil "81 il" eylemi + atlanacak seriler); ana=False: il sayfası (yalnızca tarih; sayfanın kendi ili)."""
    aciklama = "İl ve tarih seçerek o günün tahmini plakasını öğrenin." if ana else "Seçtiğiniz tarihte bu ilde hangi plakanın verilmesinin beklendiğini öğrenin."
    il_alani = '<div><label for="tarih-il">İl</label><select id="tarih-il"></select></div>' if ana else ""
    ek = ('<button type="button" class="t-ikincil" id="btn-all" aria-expanded="false" aria-controls="all-wrap">81 ilin bu tarihteki tahminlerini göster</button>\n'
          '<div class="tblwrap" id="all-wrap" hidden><table class="t" id="all-tbl"></table></div>\n') if ana else ""
    # atlanacak seriler: iki sayfada AYNI alan; varsayılan boş (hiçbir seri atlanmaz), kalıcı değil, hedef plaka aracının ayarından bağımsız
    atla = ('<details class="gelismis" id="tarih-gelismis"><summary>Atlanacak seriler (bu tarih tahmini için)</summary>'
            '<label for="excl">Verilmeyeceğini düşündüğünüz seriler</label>'
            '<input type="text" id="excl" placeholder="örn. SXX, TXX" spellcheck="false" autocapitalize="characters" aria-describedby="excl-ipucu">'
            '<p class="ipucu" id="excl-ipucu">Boş bırakırsanız hiçbir seri atlanmaz. <code>TXX</code> = tüm T grubu, <code>SAA</code> = tek seri, <code>TAA-TCZ</code> = aralık. Yalnızca bu tarih tahminine uygulanır.</p>'
            '<div class="uyari" id="excl-warn" role="status" hidden></div></details>\n')
    return (f'<section class="arac tarih-arac" id="tarih" aria-labelledby="tarih-baslik">\n<h2 id="tarih-baslik">{TARIH_BASLIK}</h2>\n<p class="ipucu">{aciklama}</p>\n'
            '<noscript><p class="ipucu">Bu araç JavaScript gerektirir.</p></noscript>\n<div id="tarih-govde" hidden>\n'
            f'<form id="tarih-form" novalidate>\n<div class="t-alanlar{" t-iki" if ana else ""}">{il_alani}<div><label for="dt">Tarih</label><input type="date" id="dt"></div></div>\n'
            '<button type="submit" class="t-btn" id="btn-tarih">Tahmini plakayı göster</button>\n</form>\n<p class="t-hata" id="tarih-hata" role="alert"></p>\n'
            '<div class="t-sonuc" id="tarih-sonuc" aria-live="polite" hidden><p class="t-plaka mono" id="plate-num"></p><p class="t-alt"><span class="t-etiket tahmin" id="tag">Tahmin</span><span id="tarih-out"></span></p><p class="t-alt t-atla" id="tarih-atla-bilgi" hidden></p></div>\n'
            f'<div class="uyari" id="tarih-uyari" role="status" hidden></div>\n{atla}{ek}</div>\n</section>')

# --- 2 aylık dönemlerde geçen yıla kıyasla ilerleme -------------------------------------------------
DONEMLER = [(1,3,"Oca–Şub"),(3,5,"Mar–Nis"),(5,7,"May–Haz"),(7,9,"Tem–Ağu"),(9,11,"Eyl–Eki"),(11,13,"Kas–Ara")]
def tn(x):
    q = 10 if abs(x) < 2000 else 100
    return f"{round(x/q)*q:,.0f}".replace(",", ".")
def _gun(y, m, dd=1):
    try: return (datetime.date(y, m, dd) - EPOCH).days
    except ValueError: return (datetime.date(y, m, 28) - EPOCH).days
def _raw_at(o, day):
    xs = [x[0] for x in o]; i = bisect.bisect_left(xs, day)
    if i < len(xs) and xs[i] == day: return o[i][1]
    (x0,y0),(x1,y1) = o[i-1], o[i]
    return y0 + (y1-y0)*(day-x0)/(x1-x0)
def ilerleme(o, c, s_, e_):
    """(deger, durum): 'ok' | 'yok' (veri kapsamı dışı) | 'sureksiz' (seride kırılma/blok atlaması: ham ve temizlenmiş fark >%2)."""
    if s_ < o[0][0] or e_ > o[-1][0] or e_ <= s_: return None, "yok"
    v = fc.at(c, e_) - fc.at(c, s_); rv = _raw_at(o, e_) - _raw_at(o, s_)
    if abs(rv - v) > 0.02*max(v, 1): return None, "sureksiz"
    return v, "ok"
def yoy_blok(o, c, ad, last_d):
    son_gun = o[-1][0]; Y = last_d.year; yillar = list(range(2024, Y+1))
    ust = "".join(f"<th class='n'>{lab}</th>" for _,_,lab in DONEMLER)
    satirlar = ""; vals = {}; kismi = {}; sureksiz_var = False
    for y in yillar:
        hucre = ""
        for k,(a,b,lab) in enumerate(DONEMLER):
            s_ = _gun(y,a); e_ = _gun(y+1,1) if b==13 else _gun(y,b)
            if s_ > son_gun: v, st = None, "yok"
            elif e_ > son_gun:  # dönem sürüyor: son gözlem tarihine kadar kısmi değer
                v, st = ilerleme(o, c, s_, son_gun)
                if st == "ok": kismi[(y,k)] = (v, _gun(y-1,a), _gun(y-1, last_d.month, last_d.day))
            else: v, st = ilerleme(o, c, s_, e_)
            vals[(y,k)] = v
            if st == "sureksiz": sureksiz_var = True
            if st == "ok" and (y,k) in kismi: hucre += f"<td class='n p'>~{tn(v)}*</td>"
            elif st == "ok": hucre += f"<td class='n'>~{tn(v)}</td>"
            elif st == "sureksiz": hucre += "<td class='n' title='Bu dönemde seri verisinde kırılma var'>—†</td>"
            else: hucre += "<td class='n'>—</td>"
        satirlar += f"<tr><td><b>{y}</b></td>{hucre}</tr>"
    # son yıl / önceki yıl yüzde satırı (sürmekte olan dönemde aynı takvim penceresi karşılaştırılır)
    pct = {}; kismi_notu = ""
    for k in range(6):
        cur = vals.get((Y,k)); prv = vals.get((Y-1,k))
        if (Y,k) in kismi:
            v, ps, pe = kismi[(Y,k)]; prv, st = ilerleme(o, c, ps, pe); cur = v
            pencere = f"{tr_date(EPOCH+datetime.timedelta(days=_gun(Y,DONEMLER[k][0])))} – {tr_date(last_d)}"
            if prv: kismi_notu = f"<p class='fn'>* {DONEMLER[k][2]} {Y} henüz bitmedi: {pencere} arası kısmi değer. {Y-1}'te aynı pencerede ilerleme ~{tn(prv)}; yüzde değişim bu pencereye göre hesaplandı.</p>"
            else: kismi_notu = f"<p class='fn'>* {DONEMLER[k][2]} {Y} henüz bitmedi: {pencere} arası kısmi değer; {Y-1}'in aynı penceresi için güvenilir karşılaştırma yapılamadı.</p>"
        pct[k] = (cur/prv - 1) if (cur and prv and prv > 0) else None
    pcell = ""
    for k in range(6):
        if pct[k] is None: pcell += "<td class='n'>—</td>"
        else:
            r = pct[k]*100; cls = "up" if r >= 1 else ("dn" if r <= -1 else "")
            pcell += f"<td class='n {cls}'>{'+' if r>=1 else ('−' if r<=-1 else '±')}%{abs(round(r))}</td>"
    satirlar += f"<tr class='pct'><td>{Y} / {Y-1}</td>{pcell}</tr>"
    # tek cümlelik özet: son tamamlanan ve iki yılda da verisi olan dönem
    ozet = ""
    for k in range(5,-1,-1):
        cur = vals.get((Y,k)); prv = vals.get((Y-1,k))
        if cur and prv and (Y,k) not in kismi:
            r = (cur/prv - 1)*100; lab = DONEMLER[k][2]
            yon = "yaklaşık aynı düzeyde" if abs(r) < 2 else (f"yaklaşık %{abs(round(r))} daha fazla" if r > 0 else f"yaklaşık %{abs(round(r))} daha az")
            ozet = f"<p class='meta'>Son tamamlanan dönemde ({lab} {Y}) {html.escape(ad)} için plaka ilerlemesi ~{tn(cur)}; {Y-1}'in aynı dönemine (~{tn(prv)}) göre {yon}.</p>"
            break
    kucuk = max([v for v in vals.values() if v] or [0]) < 3000
    dip = "<p class='fn'>— veri yok veya dönem başlamadı (kayıtlarımız Şubat 2024'te başlıyor)."
    if sureksiz_var: dip += " † Bu dönemde seri verisinde kırılma var; yanlış bir sayı göstermemek için değer verilmedi."
    dip += " Değerler, kayıtlı haftalık gözlemler arasında doğrusal interpolasyonla bulunan yaklaşık plaka numarası ilerlemesidir (yuvarlanmıştır); gerçek tescil sayısı değildir.</p>"
    if kucuk: dip += "<p class='fn'>Düşük hacimli illerde küçük sayısal farklar büyük yüzde değişim olarak görünebilir.</p>"
    return (f"<div class='card'><h2>Geçen yıla kıyasla durum — 2 aylık dönemler</h2>{ozet}"
            f"<div class='yoy'><table><tr><th>Yıl</th>{ust}</tr>{satirlar}</table></div>{kismi_notu}{dip}</div>")
def _gozlem_yakin(o, gun, tol=3):
    """Verilen güne en yakın gerçek gözlem; tol günden uzaksa None (interpolasyonla değer uydurulmaz)."""
    b = min(o, key=lambda x: abs(x[0]-gun))
    return b if abs(b[0]-gun) <= tol else None
def son_degisim_veri(o, c):
    """Yalnızca kayıtlı gözlemlerden: son iki gözlem arası ilerleme ve son iki ~28 günlük dönemin karşılaştırması (yapılamayanlar None).
    Tüm günler o'daki gözlem günlerinden gelir (üretim tarihi/--bugun kullanılmaz); interpolasyon yok; seride kırılma varsa ilgili parça üretilmez."""
    def ok(a, b): return ilerleme(o, c, a[0], b[0])[1] == "ok" and b[1] > a[1]
    son = o[-1]; v = {"iki": None, "donem": None}
    if len(o) >= 2 and 1 <= son[0]-o[-2][0] <= 14 and ok(o[-2], son):
        on = o[-2]; v["iki"] = {"bas": on[0], "bit": son[0], "gun": son[0]-on[0], "sira": son[1]-on[1]}
    orta = _gozlem_yakin(o, son[0]-28); bas = _gozlem_yakin(o, son[0]-56)
    if orta and bas and bas[0] < orta[0] < son[0] and ok(bas, orta) and ok(orta, son):
        g1 = son[0]-orta[0]; g0 = orta[0]-bas[0]; a1 = son[1]-orta[1]; a0 = orta[1]-bas[1]; r1 = a1/g1*7; r0 = a0/g0*7
        v["donem"] = {"g1": g1, "g0": g0, "a1": a1, "a0": a0, "r1": r1, "r0": r0, "fark": (r1/r0-1)*100, "bas": bas[0], "orta": orta[0], "bit": son[0]}
    return v
def _aralik(g0, g1):
    a = EPOCH + datetime.timedelta(days=g0); b = EPOCH + datetime.timedelta(days=g1)
    return f"{a.day} {AYLAR[a.month-1]} – {tr_date(b)}" if a.year == b.year else f"{tr_date(a)} – {tr_date(b)}"
def son_degisim_kisa(dn):
    """Karşılaştırma dönemine göre kısa durum: 'önceki döneme göre %16 daha az' / 'önceki döneme benzer' / '%12 daha fazla'."""
    f = dn["fark"]
    return "önceki döneme benzer" if abs(f) < 5 else f"önceki döneme göre %{abs(round(f))} {'daha fazla' if f > 0 else 'daha az'}"
def son_degisim_html(v, ad):
    """'Son gelişmeler' ayrıntı metni (1-2 kısa cümle); veri yoksa boş."""
    h = ""
    if v["iki"]:
        i = v["iki"]; h += f"<p class='meta'>{html.escape(ad)} için plaka sırası, son iki gözlem arasında ({_aralik(i['bas'], i['bit'])}) {sayi(i['sira'])} sıra ilerledi; günlük ortalama yaklaşık {sayi(i['sira']/i['gun'])} sıra.</p>"
    if v["donem"]:
        d_ = v["donem"]; yon = "hız iki dönemde benzer düzeyde (fark %5'in altında)." if abs(d_["fark"]) < 5 else f"hız önceki döneme göre yaklaşık %{abs(round(d_['fark']))} {'arttı' if d_['fark'] > 0 else 'azaldı'}."
        h += (f"<p class='meta'>Kayıtlı son {d_['g1']} günde ({_aralik(d_['orta'], d_['bit'])}) {sayi(d_['a1'])} sıra, bir önceki {d_['g0']} günde ({_aralik(d_['bas'], d_['orta'])}) {sayi(d_['a0'])} sıra ilerledi. "
              f"Gözlenen hız haftada {sayi(d_['r1'])} sıra (önceki dönemde {sayi(d_['r0'])}); {yon}</p>")
    return h
def seri_suresi(rate):
    """Tahmin hızıyla (sıra/gün), atlamasız ilerleme varsayımıyla bir serinin (1.000 sıralık aralık) dolma süresi."""
    gun = 1000 / rate
    if gun < 1: return f"yaklaşık {round(gun*24)} saatte"
    if gun < 14: return f"yaklaşık {ondalik(gun)} günde"
    if gun < 60: return f"yaklaşık {round(gun/7)} haftada"
    return f"yaklaşık {round(gun/30)} ayda"
TR_SIRA = "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"
def tr_up(x): return x.replace("i", "İ").replace("ı", "I").upper()
def tr_anahtar(x): return [TR_SIRA.index(ch) if ch in TR_SIRA else 99 for ch in tr_up(x)]
def acilir(kart_html, kaydir=False):
    """Eski '<div class=card><h2>Başlık</h2>…</div>' bloklarını erişilebilir <details> bölümüne çevirir (içerik HTML'de kalır)."""
    m = re.match(r"<div class='card'><h2>(.*?)</h2>(.*)</div>$", kart_html, re.S); assert m, kart_html[:80]
    ic = re.sub(r"(<table>.*?</table>)", r'<div class="kaydir">\1</div>', m[2], flags=re.S) if kaydir else m[2]     # dar ekranda geniş tablo yatay kaydırılır (sayfa taşmaz)
    return f'<details class="bolum"><summary><h2>{m[1]}</h2></summary><div class="ic">{ic}</div></details>'
def iller_gruplari_html():
    """81 il için harf harf gruplanmış gerçek <a href> bağlantıları (il sayfalarındaki 'Diğer iller' ve ana sayfadaki liste ortak kullanır)."""
    gruplar = {}
    for x in iller:
        ad_ = TAM.get(x["il"], x["il"]); gruplar.setdefault(tr_up(ad_)[0], []).append(ad_)
    satirlar = ""
    for harf in sorted(gruplar, key=lambda h: TR_SIRA.index(h) if h in TR_SIRA else 99):
        linkler = " ".join(f'<a href="/il/{slug(a_)}">{html.escape(a_)}</a>' for a_ in sorted(gruplar[harf], key=tr_anahtar))
        satirlar += f"<p><b>{harf}</b> {linkler}</p>"
    return satirlar
def diger_iller_html():
    return f'<details class="bolum"><summary><h2>Diğer iller</h2></summary><div class="ic iller">{iller_gruplari_html()}</div></details>'
# --- ana sayfa (index.html): statik kartlar, il listesi/bağlantıları ve temel CSS ----------------------------------------------------
# index.html elle yazılmış bir sayfadır; yalnızca işaretli bölgeler (<!--ANA:...-->, /*ANA:TEMEL-CSS*/) buradan üretilir (haftalık tablo_ekle.py akışı bu betiği çalıştırır).
# Gömülü DATA satırı tablo_ekle.py'nin alanıdır; hesaplayıcı mantığı ortak motordadır. Kart değerleri JS yokken de tarih etiketiyle anlamlıdır; JS aynı değeri canlı günceller.
def _bolge(h, bas, son, icerik):
    i = h.index(bas) + len(bas); j = h.index(son); return h[:i] + "\n" + icerik + "\n" + h[j:]
def ana_sayfa_guncelle():
    kartlar = ""
    for kod_ in ANA_SAYFA_KARTLARI:
        k = KARTLAR[kod_]
        kartlar += (f'<a class="kart" href="/il/{k["slug"]}" data-il="{html.escape(k["il"])}"><span class="k-ust"><span class="k-il">{html.escape(k["ad"])} · {k["kod"]}</span><span class="etiket">Tahmindir</span></span>'
                    f'<span class="k-seri mono" data-kart="plaka">{k["plaka"]}</span><span class="k-alt"><span data-kart="tarih">{k["tarih"]}</span> itibarıyla</span>'
                    f'<span class="k-gozlem">Son gözlem: {k["g_plaka"]} · {k["g_tarih"]}</span></a>\n')
    son_gun = EPOCH + datetime.timedelta(days=max(x["obs"][-1][0] for x in iller))
    kart_html = ('<section aria-label="Büyük illerin güncel tahmini plaka serisi"><div class="kartlar">\n' + kartlar + '</div>\n'
                 f'<p class="veri-tarihi">Son kayıtlı veri: <span id="last-global">{son_gun.strftime("%d.%m.%Y")}</span> · kaynak: wowTURKEY / Güven_Hoca haftalık tabloları</p></section>')
    secenek = "".join(f'<option value="{html.escape(TAM.get(x["il"], x["il"]))} ({x["kod"]:02d})" data-ad="{html.escape(TAM.get(x["il"], x["il"]))}" data-kod="{x["kod"]}" data-slug="{slug(TAM.get(x["il"], x["il"]))}"></option>'
                      for x in sorted(iller, key=lambda x: tr_anahtar(TAM.get(x["il"], x["il"]))))
    liste_html = f'<datalist id="il-liste">{secenek}</datalist>'
    bag_html = f'<nav class="iller-liste" aria-label="İl sayfaları"><h2>İllere Göre Güncel Plaka Serileri</h2><div class="iller">{iller_gruplari_html()}</div></nav>'
    h = open("index.html", encoding="utf-8").read()
    eski_iz = (re.search(r"<!--ANA:SURUM-->\s*(\w*)\s*<!--/ANA:SURUM-->", h) or [None, ""])[1]
    h = _bolge(h, "/*ANA:TEMEL-CSS*/", "/*/ANA:TEMEL-CSS*/", CSS)
    h = _bolge(h, "<!--ANA:KARTLAR-->", "<!--/ANA:KARTLAR-->", kart_html)
    h = _bolge(h, "<!--ANA:IL-LISTE-->", "<!--/ANA:IL-LISTE-->", liste_html)
    h = _bolge(h, "<!--ANA:IL-BAGLANTILAR-->", "<!--/ANA:IL-BAGLANTILAR-->", bag_html)
    h = _bolge(h, "<!--ANA:OLCUM-NOTU-->", "<!--/ANA:OLCUM-NOTU-->", OLCUM_NOTU_ANA)
    h = _bolge(h, "<!--ANA:TARIH-ARACI-->", "<!--/ANA:TARIH-ARACI-->", tarih_arac_html(True))
    # Anlamlı içerik parmak izi: kartlardaki günlük seri/tarih değişimi tek başına yeni içerik SAYILMAZ; gözlem verisi (DATA), metin, şablon ve CSS değişimi sayılır.
    # İz index.html içinde saklanır (git'e ya da saate bağlı değil); değişmediyse sitemap lastmod'u korunur.
    _iz_girdisi = re.sub(r"(<!--ANA:SURUM-->).*?(<!--/ANA:SURUM-->)", r"\1\2", re.sub(r'(data-kart="(?:plaka|tarih)">)[^<]*', r"\1", h), flags=re.S)
    _iz_girdisi = re.sub(r"<!--ANA:OLCUM-NOTU-->.*?<!--/ANA:OLCUM-NOTU-->\n|<!--OLCUM-->.*?<!--/OLCUM-->\n", "", _iz_girdisi, flags=re.S)       # analitik betiği/notu anlamlı içerik değildir       # izin kendisi ve günlük değerler girdiye katılmaz
    yeni_iz = hashlib.sha256(_iz_girdisi.encode("utf-8")).hexdigest()[:16]
    h = _bolge(h, "<!--ANA:SURUM-->", "<!--/ANA:SURUM-->", yeni_iz)
    with open("index.html", "w", encoding="utf-8") as f: f.write(h)
    return yeni_iz != eski_iz

# --- sitemap lastmod: yalnızca sayfanın anlamlı içeriği değiştiyse yenilenir -----------------------------------------
# Anlamlı içerik = sayfa metni, canlı güncellenen tahmin alanları (data-live) ve canlı JS (START/tablo/tatil listesi) hariç.
# Yani yalnızca üretim günü değiştiği için ya da aynı verilerle yeniden üretildiği için lastmod oynamaz; yeni gözlem,
# metin/şablon değişikliği ya da başka bir gerçek içerik farkı varsa üretim günü (GERCEK_BUGUN) yazılır.
ESKI_LASTMOD = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", open("sitemap.xml", encoding="utf-8").read())) if os.path.exists("sitemap.xml") else {}
def anlamli(h):
    h = re.sub(r"<!--OLCUM-->.*?<!--/OLCUM-->\n", "", h, flags=re.S)             # analitik betiği ve bilgilendirme notu lastmod'u oynatmaz
    h = re.sub(r"<script>\(function.*?</script>", "", h, flags=re.S)
    h = re.sub(r'data-baslangic="[^"]*"', 'data-baslangic=""', h)
    return re.sub(r'(data-live="\w+">)[^<]*', r"\1", h)
LASTMOD = {}
# Ana sayfa lastmod: anlamlı içerik değiştiyse (ana_sayfa_guncelle: parmak izi farkı) üretim günü, aksi hâlde önceki değer korunur (aşağıda)
DIGER_ILLER = diger_iller_html()
KARTLAR = {}
# JS için resmî tatil takvimi: TEK KAYNAK is_gunu.py (RESMI_TATIL); ayrı bir JS takvimi elle tutulmaz. Ana sayfa ve il sayfaları /assets/takvim.js'i yükler.
os.makedirs("assets", exist_ok=True)
# Tarihsel plaka referansları (data/tarihsel_referanslar.json; gözlem verisinden AYRI): motor yalnızca ilgili ilin geriye dönük tahminini kalibre etmek için okur. Üretilmiş varlık: assets/tarihsel-referanslar.js
_ref_dosyasi = json.load(open("data/tarihsel_referanslar.json", encoding="utf-8"))
assert not any(n.get("hesapta_kullanilir") for n in _ref_dosyasi["dogrulanmamis_degerlendirme_notlari"]["notlar"])      # doğrulanmamış notlar (Ankara 06 AFC, 2019 liste, başlangıç grubu duyuruları) hesaba GİRMEZ: yalnızca "referanslar" okunur
REFERANSLAR = {}
for _r in _ref_dosyasi["referanslar"]:
    assert not _r["resmi_veri"] and re.fullmatch(r"\d\d [A-Z]{3} \d{3}", _r["plaka"]) and int(_r["plaka"][:2]) == _r["kod"], _r
    REFERANSLAR.setdefault(_r["kod"], []).append({"plaka": _r["plaka"], "tarih": _r["tarih"], "tarihKesinligi": _r["tarih_kesinligi"], "tarihBelirsizligiGun": _r["tarih_belirsizligi_gun"], "kaynak": _r["kaynak"], "resmi": False})
with open("assets/tarihsel-referanslar.js", "w", encoding="utf-8") as f:
    f.write("// ÜRETİLMİŞ DOSYA: data/tarihsel_referanslar.json'dan generate_il_pages.py yazar; elle düzenlemeyin. Gözlem verisi DEĞİL: yalnızca ilgili ilin ilk gözlem öncesi tahminini kalibre eder (tahmin-motoru.js).\n"
            f"const PlakaReferanslar = {json.dumps(REFERANSLAR, ensure_ascii=False)};\n")
with open("assets/takvim.js", "w", encoding="utf-8") as f:
    f.write("// ÜRETİLMİŞ DOSYA: is_gunu.py'deki resmî tatil takviminden generate_il_pages.py yazar; elle düzenlemeyin.\n"
            f"const PlakaTakvim = {{ilkYil: {TAKVIM_ILK_YIL}, sonYil: {TAKVIM_SON_YIL}, tatiller: {json.dumps(sorted(t.isoformat() for t in RESMI_TATIL))}}};\n")
urls = [BASE + "/"]
for s in iller:
    il = s["il"]; ad = TAM.get(il, il); sl = slug(ad); kod = f"{s['kod']:02d}"
    o = s["obs"]; last = o[-1]
    rate = fc.slope(o, last[0])
    last_d = EPOCH + datetime.timedelta(days=last[0])
    _h = (today - last_d).days
    _c = fc.clean(o)
    est_n = last[1] + fc.advance(o, _c, last[0], _h, rate)
    el, en = inv(est_n); ll, ln = inv(last[1])
    if s["kod"] in ANA_SAYFA_KARTLARI:        # ana sayfa kartı: aynı hesap (aynı el/ll/ln), aynı referans gün
        KARTLAR[s["kod"]] = {"il": il, "ad": ad, "kod": kod, "slug": sl, "plaka": f"{kod} {el} {en:03d}", "tarih": tr_date(today), "g_plaka": f"{kod} {ll} {ln:03d}", "g_tarih": tr_date(last_d)}
    canli_js = CANLI_JS.replace("__GOZLEM__", last_d.isoformat()).replace("__ESIK__", str(BAYAT_ESIK_GUN))
    trans = [t for t in gec if t["il"] == il]
    rows = "".join(f"<tr><td>{t['ilk_gorulen_yeni_tarih'][8:10]}.{t['ilk_gorulen_yeni_tarih'][5:7]}.{t['ilk_gorulen_yeni_tarih'][:4]}</td><td class='mono'>{t['onceki_harf_grubu']} → {t['yeni_harf_grubu']}</td><td class='mono'>{html.escape(t['son_gorulen_eski'])} → {html.escape(t['ilk_gorulen_yeni'])}</td></tr>" for t in trans)
    gecis_html = f"<div class='card'><h2>Harf grubu geçişleri (Şubat 2024'ten beri)</h2><table><tr><th>Tarih</th><th>Grup</th><th>Seri</th></tr>{rows}</table></div>" if trans else f"<div class='card'><h2>Harf grubu geçişleri (Şubat 2024'ten beri)</h2><p class='meta' style='margin:0'>{html.escape(ad)}, Şubat 2024'ten bu yana <b>{ll[0]}</b> harf grubunda ilerliyor; bu dönemde grup değişimi yaşanmadı.</p></div>"
    yoy_html = yoy_blok(o, _c, ad, last_d)
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
    sd = son_degisim_veri(o, _c); sd_html = son_degisim_html(sd, ad)
    yas = (today - last_d).days; bayat_gizli = "" if yas > BAYAT_ESIK_GUN else " hidden"      # statik: üretim anında 21 günden eskiyse görünür; JS ziyaret anında da kontrol eder
    tahmin_grup_gizli = " hidden" if el[0] == ll[0] else ""
    if sd["donem"]:
        dn = sd["donem"]; donem_metrik = f"<div><dt>Son {dn['g1']} günde ilerleme</dt><dd class=\"v\">{sayi(dn['a1'])} sıra</dd><dd class=\"k\">{son_degisim_kisa(dn)}</dd></div>"
    elif sd["iki"]:
        ik = sd["iki"]; donem_metrik = f"<div><dt>Son iki gözlem arası</dt><dd class=\"v\">{sayi(ik['sira'])} sıra</dd><dd class=\"k\">{ik['gun']} günde</dd></div>"
    else: donem_metrik = ""
    hiz_gun = rate; hiz_hafta = rate * 7
    il_veri = json.dumps({"kod": s["kod"], "il": ad, "bterr": s["bterr"], "obs": o}, ensure_ascii=False, separators=(",", ":"))
    title = f"{ad} Plaka Sırası Hangi Harfte? Güncel Seri ({today.year})"
    desc = f"{ad} plaka sırası hangi harfte? Son gözlem: {kod} {ll} {ln:03d} ({tr_date(last_d)}). Güncel tahmini seriyi ve plakanızın tahmini çıkış tarihini araçla hesaplayın."
    breadcrumb = json.dumps({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"Plaka Tahmini","item":f"{BASE}/"},
        {"@type":"ListItem","position":2,"name":f"{ad} Plaka Sırası","item":f"{BASE}/il/{sl}"}]}, ensure_ascii=False, separators=(",",":"))
    sd_bolum = f'<details class="bolum"><summary><h2>Son gelişmeler</h2></summary><div class="ic">{sd_html}</div></details>' if sd_html else ""
    nasil = (f'<details class="bolum"><summary><h2>Nasıl hesaplanıyor?</h2></summary><div class="ic"><ul>'
             f'<li><b>Tahmini seri:</b> son kayıtlı gözlemden, ilin son ~365 günlük aralık hızlarının medyanı ile geçen yılın aynı dönemindeki ilerlemenin ortalamasıyla uzatılır. Güncel tahmin, Türkiye yerel tarihinin en yakın önceki iş gününe aittir: Cumartesi, Pazar ve resmî tatilde değer değişmez (arife günleri iş günü sayılır). Değer bir tahmindir, gerçek tescil değildir.</li>'
             f'<li><b>Tahmin hızı:</b> günde yaklaşık {sayi(hiz_gun)} sıra (haftada yaklaşık {sayi(hiz_hafta)}). Atlamasız ilerleme varsayımıyla bir seri (1.000 sıralık aralık; numaralar 001–999) {seri_suresi(rate)} dolar.</li>'
             f'<li><b>Gözlenen hız:</b> iki gözlem arasındaki sıra ilerlemesinin gün sayısına oranıdır ("Son gelişmeler"); tahmin hızından farklı olabilir.</li>'
             f'<li><b>Sıra:</b> plaka numaraları arasındaki farktır; gerçek tescil sayısı değildir. Seri atlamaları sayıya dahil olabilir; "atlanacak seriler" alanı hedef hesabında bunları düşer.</li>'
             f'<li><b>Hata payı:</b> hedef sonucundaki ± gün, ilin geçmiş tahmin doğruluğundan türetilen sezgisel bir değerdir; istatistiksel güven aralığı değildir.</li>'
             f'</ul></div></details>')
    kaynak = ('<details class="bolum"><summary><h2>Veri kaynağı ve sınırlamalar</h2></summary><div class="ic"><ul>'
              '<li>Veri: wowturkey.com "Türkiye Genelindeki Araç Plakalarının Gelişimi" başlığında Güven_Hoca\'nın paylaştığı haftalık tablolar (Şubat 2024\'ten beri); sayısallaştırılıp toplam ve haftalar-arası tutarlılık kontrolleriyle doğrulanmıştır. Resmî tahsis kaydı değildir.</li>'
              '<li>Yıllık karşılaştırma değerleri, kayıtlı gözlemler arasında doğrusal interpolasyonla bulunan yaklaşık değerlerdir.</li>'
              '<li>Plaka alfabesinde ilk ve son harfte I ve O kullanılmaz; Q, W, X hiç kullanılmaz. Harf grubu, serinin ilk harfidir.</li></ul></div></details>')
    arac = (f'<section class="arac" id="hesapla" aria-labelledby="arac-baslik"><h2 id="arac-baslik">Hedef plakanın tahmini tarihi</h2>'
            f'<form id="hedef-form" action="/" method="get" autocomplete="off" novalidate><input type="hidden" name="il" value="{s["kod"]}">'
            f'<label for="hedef">{html.escape(ad)} için hedef plaka veya seri</label>'
            f'<div class="alan"><input id="hedef" type="text" inputmode="text" autocapitalize="characters" autocorrect="off" spellcheck="false" placeholder="örn. {ll[0]}ZZ 999" aria-describedby="hedef-ipucu"><button type="submit">Hesapla</button></div>'
            f'<p id="hedef-ipucu" class="ipucu">Harf grubu ve isteğe bağlı numara (örn. {ll} veya {ll} 500). İl bu sayfadan alınır. <a href="/?il={s["kod"]}">Ana sayfada aç</a></p>'
            f'<details class="gelismis"><summary>Atlanacak seriler (isteğe bağlı)</summary><label for="atla">Verilmeyeceğini düşündüğünüz seriler</label><input id="atla" type="text" autocapitalize="characters" spellcheck="false" placeholder="örn. SXX, TXX" aria-describedby="atla-ipucu"><p id="atla-ipucu" class="ipucu">Harf, iki harf (X joker) veya aralık: SXX, TXX, BAA-BCZ.</p></details>'
            f'</form><div id="sonuc" class="sonuc" aria-live="polite"></div></section>')
    tarih_arac = tarih_arac_html(False)
    ref_betik = '<script src="/assets/tarihsel-referanslar.js" defer></script>\n' if s["kod"] in REFERANSLAR else ""      # yalnızca referansı olan il sayfası yükler; diğer 80 sayfa değişmez
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>{CSS}{IL_CSS}</style>
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body><main class="wrap">
<div class="eyebrow"><a href="/">Plaka Tahmini</a> · {kod} {html.escape(ad)}</div>
<p class="geri"><a href="/"><span aria-hidden="true">←</span> Ana sayfaya dön</a></p>
<h1>{html.escape(ad)} Plaka Sırası Hangi Harfte?</h1>
<section aria-label="Özet" data-baslangic="{today.isoformat()}">
<p class="e">Tahmini güncel plaka</p>
<p class="buyuk mono" data-live="plaka">{kod} {el} {en:03d}</p>
<p class="alt"><span data-live="tarih">{tr_date(today)}</span> itibarıyla · tahmindir</p>
<dl class="metrik">
<div><dt>Son kayıtlı gözlem</dt><dd class="v mono nw">{kod} {ll} {ln:03d}</dd><dd class="k">{tr_date(last_d)}</dd></div>
<div><dt>Harf grubu</dt><dd class="v mono">{ll[0]}</dd><dd class="k">gözlenen · serinin ilk harfi</dd></div>
{donem_metrik}
<div id="tahmin-grup" data-gozlenen="{ll[0]}"{tahmin_grup_gizli}><dt>Tahmini harf grubu</dt><dd class="v mono" data-live="grup">{el[0]}</dd><dd class="k">tahmin; gözlem değil</dd></div>
</dl>
<a class="cta" href="#hesapla">Plakamın tarihini hesapla</a>
<p class="not">Son gözlemden hesaplanan tahmindir; resmî tahsis kaydı değildir.</p>
<div class="uyari" id="bayat" role="status"{bayat_gizli}>Son kayıtlı gözlem {BAYAT_ESIK_GUN} günden eski ({tr_date(last_d)}). Tahmin güncel olmayabilir ve kesin değildir.</div>
<div class="uyari" id="guncellik" role="status" hidden><span></span> <a href="/?il={s['kod']}">Canlı tahmin aracını açın</a></div>
</section>
{arac}
{tarih_arac}
{acilir(gozlem_html, True)}
{sd_bolum}
{acilir(yoy_html)}
{acilir(gecis_html, True)}
{nasil}
{kaynak}
{DIGER_ILLER}
<!--OLCUM-->{OLCUM_NOTU_IL}<!--/OLCUM-->
</main>
<script type="application/json" id="il-veri">{il_veri}</script>
<script>{canli_js}</script>
<!--OLCUM--><script src="/assets/olcum.js" defer></script><!--/OLCUM-->
<script src="/assets/takvim.js" defer></script>
{ref_betik}<script src="/assets/tahmin-motoru.js" defer></script>
<script src="/assets/tarih-sorgu.js" defer></script>
<script src="/assets/il-arac.js" defer></script>
</body></html>"""
    _yol = f"il/{sl}.html"; _url = f"{BASE}/il/{sl}"
    _eski = open(_yol, encoding="utf-8").read() if os.path.exists(_yol) else None
    LASTMOD[_url] = ESKI_LASTMOD[_url] if (_eski is not None and _url in ESKI_LASTMOD and anlamli(_eski) == anlamli(page)) else GERCEK_BUGUN.isoformat()
    if SADECE is None or sl in SADECE:
        open(_yol,"w").write(page.replace(",", ".", 0))
    urls.append(_url)
if SADECE is None:
    _ana = BASE + "/"       # ana sayfa kartları/listeleri/CSS (aynı referans gün, aynı hesap); lastmod yalnızca anlamlı içerik değiştiyse yenilenir
    LASTMOD[_ana] = GERCEK_BUGUN.isoformat() if (ana_sayfa_guncelle() or _ana not in ESKI_LASTMOD) else ESKI_LASTMOD[_ana]
if SADECE is None:
    _sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(f"  <url><loc>{u}</loc><lastmod>{LASTMOD[u]}</lastmod><changefreq>weekly</changefreq></url>" for u in urls) + "\n</urlset>\n"
    with open("sitemap.xml", "w", encoding="utf-8") as _f: _f.write(_sm)
print(len(iller), "il sayfası +", "sitemap", len(urls), "URL")
