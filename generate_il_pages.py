#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""81 il sayfasını data/tahmin_data.json + data/seri_gecisleri.csv'den üretir; sitemap.xml'i yeniler."""
import json, csv, datetime, statistics, html, bisect, argparse, sys, re, os
import forecast as fc
from is_gunu import RESMI_TATIL, onceki_is_gunu, kapsam_kontrol, TakvimKapsamHatasi, TAHMIN_PENCERESI_GUN

A1="ABCDEFGHJKLMNPRSTUVYZ"; A2="ABCDEFGHIJKLMNOPRSTUVYZ"; A3="ABCDEFGHJKLMNPRSTUVYZ"
def inv(n):
    n = round(n); num = max(1, min(999, n % 1000)); g = n // 1000
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
GERCEK_BUGUN = datetime.date.fromisoformat(_args.bugun) if _args.bugun else datetime.date.today()   # yalnızca içerik gerçekten değiştiğinde sitemap lastmod'u için
try:
    today = onceki_is_gunu(GERCEK_BUGUN)
    kapsam_kontrol(today, today + datetime.timedelta(days=TAHMIN_PENCERESI_GUN))   # tahmin penceresi tatil takvimi kapsamını aşıyorsa üretim hatası (sayfalar yazılmadan)
except TakvimKapsamHatasi as e:
    sys.exit(f"HATA: {e}")
if _args.bugun: print(f"NOT: --bugun {today}: tahmin tarihi sabitlendi; son gözlem tarihleri veriden gelir", file=sys.stderr)   # tescil iş günlerinde yapılır: hafta sonu/resmi tatilde en yakın önceki iş gününe çekilir
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
# "Plaka sırasındaki son değişim" bölümü şimdilik yalnızca bu illerde (Türkçe sayı biçimi tüm illerde uygulanır)
SON_DEGISIM_ILLERI = {"Konya", "Eskişehir", "Denizli"}

CANLI_JS = """(function(){
var T=__TABLO__,S="__START__",K="__KOD__",H=__TATIL__;
var A1="ABCDEFGHJKLMNPRSTUVYZ",A2="ABCDEFGHIJKLMNOPRSTUVYZ",A3="ABCDEFGHJKLMNPRSTUVYZ";
var AY=["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
function inv(n){n=Math.round(n);var num=Math.max(1,Math.min(999,n%1000)),g=Math.floor(n/1000);
 return [A1[Math.floor(g/A3.length/A2.length)]+A2[Math.floor(g/A3.length)%A2.length]+A3[g%A3.length],num];}
function iso(x){return x.getFullYear()+"-"+("0"+(x.getMonth()+1)).slice(-2)+"-"+("0"+x.getDate()).slice(-2);}
function tr(x){return x.getDate()+" "+AY[x.getMonth()]+" "+x.getFullYear();}
function uyar(m){var u=document.getElementById("guncellik");if(!u)return;var t=u.querySelector("span");if(t)t.textContent=m;u.hidden=false;}
try{
var d=new Date();d=new Date(d.getFullYear(),d.getMonth(),d.getDate());
while(d.getDay()===0||d.getDay()===6||H.indexOf(iso(d))>=0)d.setDate(d.getDate()-1);
var p=S.split("-"),s0=new Date(+p[0],+p[1]-1,+p[2]);
var i=Math.round((d-s0)/864e5);
if(i<0){i=0;d=s0;}
if(i>=T.length){uyar("Bu sayfadaki tahmin "+tr(s0)+" itibarıyla hesaplandı ve "+tr(new Date(s0.getFullYear(),s0.getMonth(),s0.getDate()+T.length-1))+" tarihine kadar güncellenebiliyor. Tarayıcı tarihiniz bu aralığın dışında olduğundan gösterilen değer güncel olmayabilir.");return;}
var r=inv(T[i]),n=("00"+r[1]).slice(-3);
var v={seri:K+" "+r[0],plaka:K+" "+r[0]+" "+n,tarih:tr(d)};
var e=document.querySelectorAll("[data-live]");
for(var j=0;j<e.length;j++)e[j].textContent=v[e[j].getAttribute("data-live")];
}catch(x){console.error("plakatahmini: canlı tahmin güncellenemedi",x);uyar("Canlı tahmin güncellenemedi; sayfada gösterilen tahmin, belirtilen tarih itibarıyla hesaplanmıştır.");}
})();"""
iller = sorted(d["iller"], key=lambda s: s["kod"])
nav = " · ".join(f'<a href="/il/{slug(TAM.get(s["il"], s["il"]))}">{html.escape(TAM.get(s["il"], s["il"]))}</a>' for s in iller)
CSS = """*{box-sizing:border-box}body{margin:0;background:#f5f5f1;color:#15171c;font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:16px;line-height:1.55}
.wrap{max-width:760px;margin:0 auto;padding:44px 24px 60px}h1{font-family:"Barlow Condensed","Arial Narrow",sans-serif;font-size:clamp(34px,6vw,54px);font-weight:700;line-height:1.05;margin:0}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#7d8491;margin-bottom:10px}
.plate{display:inline-flex;align-items:stretch;border:2.5px solid #15171c;border-radius:8px;overflow:hidden;background:#fff;color:#111;font-family:"Barlow Condensed",sans-serif;font-weight:600;letter-spacing:.06em;font-size:38px;line-height:1;margin:16px 0 6px}
.plate .band{background:#1f4fb0;color:#fff;font-size:12px;font-weight:600;display:flex;align-items:flex-end;justify-content:center;padding:5px 6px 4px;width:26px}
.plate .num{padding:10px 15px 8px;white-space:nowrap}
.plrow{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px}.plrow .plate{margin:16px 0 6px}.plrow .tag{margin-left:0}.plrow .cta{margin:10px 0 4px}
.tag{display:inline-block;font-size:11px;letter-spacing:.09em;text-transform:uppercase;padding:3px 9px;border-radius:99px;font-weight:600;color:#7a3fb3;border:1.5px solid currentColor;vertical-align:middle;margin-left:10px}
.card{background:#fcfcfa;border:1px solid #dcdfe5;border-radius:12px;padding:16px 20px;margin:16px 0}
.meta{font-size:14px;color:#4d5461}.meta b{color:#15171c}
table{border-collapse:collapse;width:100%;font-size:14px;border:1px solid #c5cad3}td,th{text-align:left;padding:6px 8px;border:1px solid #d5d9e0}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#5d6572;background:#eef0f3}
a{color:#2a78d6}.cta{display:inline-block;background:#e3eefb;border:1px solid #2a78d6;border-radius:9px;padding:10px 16px;font-weight:600;text-decoration:none;margin:8px 0}
.nav{font-size:13px;color:#7d8491;border-top:1px solid #dcdfe5;padding-top:16px;margin-top:30px;line-height:2}
.mono{font-family:"IBM Plex Mono",monospace}
h2{font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:17px;font-weight:600;margin:0 0 8px;line-height:1.3}
h3{font-size:14px;font-weight:600;margin:12px 0 4px;line-height:1.4}
.yoy{overflow-x:auto;-webkit-overflow-scrolling:touch}.yoy table{min-width:560px}.yoy td.n,.yoy th.n{text-align:right;white-space:nowrap}
.yoy td.p{color:#7d8491;font-style:italic}.yoy tr.pct td{font-weight:600;background:#f3f4f7}.yoy .up{color:#1a7f4b}.yoy .dn{color:#b3402a}
.fn{font-size:12px;color:#7d8491;margin:8px 0 0}
.uyari{background:#fff6e0;border:1px solid #e3c36a;color:#7a4a00;border-radius:9px;padding:10px 14px;font-size:14px;margin:12px 0}.uyari[hidden]{display:none}"""

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
def son_degisim_blok(o, c, ad):
    """Yalnızca kayıtlı gözlemlerden: son iki gözlem arası ilerleme ve son iki ~28 günlük dönemin karşılaştırması.
    Tarihlerin hepsi o'daki gözlem günlerinden gelir (üretim tarihi/--bugun kullanılmaz).
    Veri yetersizse ya da seride kırılma varsa ilgili cümle üretilmez; hiç cümle yoksa bölüm de yoktur."""
    def ok(a, b): return ilerleme(o, c, a[0], b[0])[1] == "ok" and b[1] > a[1]
    def tar(x): return EPOCH + datetime.timedelta(days=x)
    def aralik(g0, g1):
        a, b = tar(g0), tar(g1)
        return f"{a.day} {AYLAR[a.month-1]} – {tr_date(b)}" if a.year == b.year else f"{tr_date(a)} – {tr_date(b)}"
    son = o[-1]; cumle = ""
    if len(o) >= 2 and 1 <= son[0]-o[-2][0] <= 14 and ok(o[-2], son):
        on = o[-2]; g = son[0]-on[0]; a = son[1]-on[1]
        cumle += f"<p class='meta'>{html.escape(ad)} için plaka sırası, son iki gözlem arasında ({aralik(on[0], son[0])}) {sayi(a)} sıra ilerledi; günlük ortalama yaklaşık {sayi(a/g)} sıra.</p>"
    orta = _gozlem_yakin(o, son[0]-28); bas = _gozlem_yakin(o, son[0]-56)
    if orta and bas and bas[0] < orta[0] < son[0] and ok(bas, orta) and ok(orta, son):
        g1 = son[0]-orta[0]; g0 = orta[0]-bas[0]; a1 = son[1]-orta[1]; a0 = orta[1]-bas[1]
        r1 = a1/g1*7; r0 = a0/g0*7; fark = (r1/r0-1)*100
        if abs(fark) < 5: yon = "hız iki dönemde benzer düzeyde (fark %5'in altında)."
        else: yon = f"hız önceki döneme göre yaklaşık %{abs(round(fark))} {'arttı' if fark > 0 else 'azaldı'}."
        cumle += (f"<p class='meta'>Kayıtlı son {g1} günde ({aralik(orta[0], son[0])}) {sayi(a1)} sıra, bir önceki {g0} günde ({aralik(bas[0], orta[0])}) {sayi(a0)} sıra ilerledi. "
                  f"Haftalık ortalama {sayi(r1)} sıra (önceki dönemde {sayi(r0)}); {yon}</p>")
    if not cumle: return ""
    return (f"<div class='card'><h2>Plaka sırasındaki son değişim</h2>{cumle}"
            f"<p class='fn'>Son gözlem: {tr_date(tar(son[0]))}; sonrası için sayfadaki seri tahmindir. Sıra değerleri gözlenen plaka numaraları arasındaki farktır, tescil edilen araç sayısı değildir.</p></div>")
# --- sitemap lastmod: yalnızca sayfanın anlamlı içeriği değiştiyse yenilenir -----------------------------------------
# Anlamlı içerik = sayfa metni, canlı güncellenen tahmin alanları (data-live) ve canlı JS (START/tablo/tatil listesi) hariç.
# Yani yalnızca üretim günü değiştiği için ya da aynı verilerle yeniden üretildiği için lastmod oynamaz; yeni gözlem,
# metin/şablon değişikliği ya da başka bir gerçek içerik farkı varsa üretim günü (GERCEK_BUGUN) yazılır.
ESKI_LASTMOD = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", open("sitemap.xml", encoding="utf-8").read())) if os.path.exists("sitemap.xml") else {}
def anlamli(h):
    h = re.sub(r"<script>\(function.*?</script>", "", h, flags=re.S)
    return re.sub(r'(data-live="\w+">)[^<]*', r"\1", h)
LASTMOD = {}
# Ana sayfa: gömülü veri yalnızca yeni gözlemle değişir -> lastmod = verideki en son gözlem günü
LASTMOD[BASE + "/"] = (EPOCH + datetime.timedelta(days=max(x["obs"][-1][0] for x in iller))).isoformat()
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
    # ziyaretçinin tarihine göre sayfayı tarayıcıda güncellemek için: bugünden itibaren 180 günün tahmini plaka numarası
    tablo = [round(last[1] + fc.advance(o, _c, last[0], _h + k, rate)) for k in range(TAHMIN_PENCERESI_GUN)]
    canli_js = CANLI_JS.replace("__KOD__", kod).replace("__START__", today.isoformat()).replace("__TATIL__", json.dumps(sorted(t.isoformat() for t in RESMI_TATIL if today <= t <= today + datetime.timedelta(days=TAHMIN_PENCERESI_GUN)), separators=(",", ":"))).replace("__TABLO__", json.dumps(tablo, separators=(",", ":")))
    hafta_seri = rate*7/1000
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
    ozel = il in SON_DEGISIM_ILLERI
    degisim_html = (son_degisim_blok(o, _c, ad) if ozel else "")
    if degisim_html: degisim_html = "\n" + degisim_html
    hafta_txt = sayi(s['hafta'] or 0); hs_txt = ondalik(hafta_seri)   # Türkçe biçim: 1.802 / 1,8 (görünen metin ve JSON-LD aynı değerleri kullanır)
    sure = "birkaç gün" if hafta_seri > 3 else ("yaklaşık bir hafta" if hafta_seri > 0.9 else (f"yaklaşık {round(1/hafta_seri)} hafta" if hafta_seri > 0.12 else f"aylar"))
    title = f"{ad} Plaka Sırası Hangi Harfte? Güncel Seri ({today.year})"
    desc = f"{ad} plaka sırası hangi harfte? Son gözlem: {kod} {ll} {ln:03d} ({tr_date(last_d)}). Güncel tahmini seriyi ve plakanızın tahmini çıkış tarihini araçla hesaplayın."
    # SSS: görünen cevap ile JSON-LD cevabı aynı metinden gelir; zamanla eskiyen tahmin değeri içermez (yalnızca gözlem tarihi/değeri)
    sss1_q = f"{ad} plaka sırası hangi seride?"
    sss1_a = f"Son doğrulanmış gözlem {tr_date(last_d)} tarihinde {kod} {ll} {ln:03d} olarak kaydedildi. Sayfadaki tahmini seri, bu gözlemden ilin son aylardaki ilerleme hızıyla uzatılır ve belirtilen tarih itibarıyla hesaplanır; gözlem değil, tahmindir."
    sss2_q = f"{ad} plakada bir harf serisi ne kadar dayanıyor?"
    sss2_a = f"Son aylarda haftada yaklaşık {hs_txt} seri ilerliyor; yani 999 plakalık bir seri {sure} içinde tükeniyor."
    faq_ld = json.dumps({"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
        {"@type":"Question","name":sss1_q,"acceptedAnswer":{"@type":"Answer","text":sss1_a}},
        {"@type":"Question","name":sss2_q,"acceptedAnswer":{"@type":"Answer","text":sss2_a}}]}, ensure_ascii=False, separators=(",",":"))
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
<script type="application/ld+json">{faq_ld}</script>
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body><div class="wrap">
<div class="eyebrow"><a href="/" style="color:inherit;text-decoration:none">Plaka Tahmini</a> · {kod} {html.escape(ad)}</div>
<h1>{html.escape(ad)} Plaka Sırası Hangi Harfte?</h1>
<p>{html.escape(ad)} ilinde son doğrulanmış plaka gözlemi {tr_date(last_d)} tarihinde <b class="mono">{kod} {ll} {ln:03d}</b> olarak kaydedilmiştir. İlin son aylardaki ilerleme hızıyla uzatılan tahmine göre plaka sırası <span data-live="tarih">{tr_date(today)}</span> itibarıyla tahmini olarak <b class="mono" data-live="seri">{kod} {el}</b> serisi civarındadır. Aşağıdaki araçla istediğiniz plakanın yaklaşık ne zaman çıkacağını görebilirsiniz.</p>
<div class="plrow"><span class="plate"><span class="band">TR</span><span class="num" data-live="plaka">{kod} {el} {en:03d}</span></span><span class="tag">tahmin · <span data-live="tarih">{tr_date(today)}</span> itibarıyla</span><span class="tag" style="color:#4d5461">son gözlem · {tr_date(last_d)}</span><a class="cta" href="/?il={s['kod']}">🔮 Canlı tahmin aracı →</a></div>
<div class="uyari" id="guncellik" role="status" hidden><span></span> <a href="/?il={s['kod']}">Canlı tahmin aracını açın</a></div>
<p class="meta">{html.escape(ad)} son aylarda haftada ortalama <b>{hafta_txt} plaka</b> basıyor ve <b>~{hs_txt} harf serisi</b> ilerliyor{" — bir seri (999 plaka) " + sure + " dayanıyor" if hafta_seri <= 3 else ""} (kaynak: wowTURKEY / Güven Hoca haftalık tabloları).</p>
{yoy_html}
{gozlem_html}{degisim_html}
{gecis_html}
<p class="meta">Yukarıdaki tahmini seri, ilin son aylardaki ilerleme hızının son gözlemden sonrasına uzatılmış hesabıdır; gözlem değildir ve yeni tablo verisi geldikçe güncellenir. Belirli bir tarihte hangi serinin verileceğini, istediğiniz seriye ne zaman ulaşılacağını ve atlanacak serileri hesaba katan canlı aracı, plakanın yanındaki «Canlı tahmin aracı» bağlantısından açabilirsiniz.</p>
<div class="card">
<h2>Sık sorulan sorular</h2>
<h3>{html.escape(sss1_q)}</h3>
<p class="meta" style="margin:0 0 6px">{html.escape(sss1_a)}</p>
<h3>{html.escape(sss2_q)}</h3>
<p class="meta" style="margin:0 0 6px">{html.escape(sss2_a)}</p>
<h3>Belirli bir plakaya ne zaman gelinir?</h3>
<p class="meta" style="margin:0"><a href="/?il={s['kod']}">Tahmin aracına</a> istediğiniz seriyi yazın (örn. <span class="mono">{el[0]}ZZ 999</span>); verilmeyeceğini düşündüğünüz serileri de hesaptan çıkarabilirsiniz.</p>
</div>
<div class="nav"><b>Tüm iller:</b> {nav}</div>
<p class="meta" style="font-size:12px;color:#7d8491;margin-top:14px">Veri: wowturkey.com "Türkiye Genelindeki Araç Plakalarının Gelişimi" başlığı (Güven_Hoca). Sayı biçimleri yaklaşıktır; ilk/son harfte I ve O kullanılmaz.</p>
</div>
<script>{canli_js}</script></body></html>"""
    _yol = f"il/{sl}.html"; _url = f"{BASE}/il/{sl}"
    _eski = open(_yol, encoding="utf-8").read() if os.path.exists(_yol) else None
    LASTMOD[_url] = ESKI_LASTMOD[_url] if (_eski is not None and _url in ESKI_LASTMOD and anlamli(_eski) == anlamli(page)) else GERCEK_BUGUN.isoformat()
    if SADECE is None or sl in SADECE:
        open(_yol,"w").write(page.replace(",", ".", 0))
    urls.append(_url)
if SADECE is None: open("sitemap.xml","w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(f"  <url><loc>{u}</loc><lastmod>{LASTMOD[u]}</lastmod><changefreq>weekly</changefreq></url>" for u in urls) + "\n</urlset>\n")
print(len(iller), "il sayfası +", "sitemap", len(urls), "URL")
