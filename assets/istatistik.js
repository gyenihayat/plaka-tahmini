// İstatistik sayfası (/istatistik): kayıtlı gözlemlerden (data/tahmin_data.json) il il plaka artışı grafikleri.
// Bağımsız modül: tahmin motorunu (tahmin-motoru.js) KULLANMAZ ve tahmin üretmez; yalnızca gözlemler arasındaki sıra farklarını özetler.
// Üst yarı (temizle … ozet) DOM'a dokunmayan saf hesaptır ve Node'da test edilir (tests/test_istatistik.py); alt yarı SVG çizimidir.
// "Plaka artışı" = iki tarih arasındaki sıra (nominal plaka numarası) farkı; ara tarihler gözlemler arasında doğrusal interpolasyonla bulunur
// (il sayfalarındaki "Geçen yıla kıyasla" tablosuyla aynı takvim kuralı: dönem = [ilk gün, sonraki dönemin ilk günü)).
const PlakaIstatistik = (function () {
  "use strict";
  const AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  const AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  const CEYREK = ["Oca–Mar", "Nis–Haz", "Tem–Eyl", "Eki–Ara"];

  // ---------- takvim: gün numarası = veri dosyasındaki epoch'tan (2024-01-01) beri gün ----------
  let EPOCH_MS = Date.UTC(2024, 0, 1);
  function gunNo(y, m, d) { return Math.round((Date.UTC(y, m - 1, d) - EPOCH_MS) / 864e5); }       // m: 1–12 (13 = sonraki yılın Ocak'ı)
  function tarih(g) { const t = new Date(EPOCH_MS + g * 864e5); return { y: t.getUTCFullYear(), m: t.getUTCMonth() + 1, d: t.getUTCDate() }; }
  function yilOnce(g) { const t = tarih(g); return gunNo(t.y - 1, t.m, t.d); }                     // bir önceki yılın aynı takvim günü

  // ---------- seri temizliği ----------
  // Ham gözlem serisinde verilen plaka OLMAYAN süreksizlikler vardır: seri atlamaları (hep 1.000'in katı: +1.000, +21.000, +160.000 …) ve
  // kayıt kırılmaları/geri düzeltmeler (negatif fark). İstatistikte dönemi şişirmesinler diye ayıklanır; ayıklanan aralık "atlama" olarak işaretlenir (grafikte †).
  // Sıçramaya benzeyen ama atlama OLMAYAN iki durum ayıklanmaz: (1) telafi — il birkaç gözlem boyunca hiç ilerlememiş görünüp (bayat tablo) sonra birden
  // ilerlemişse toplam doğrudur; (2) ülke çapında dalga — aynı aralıkta illerin çoğu birlikte hızlanmışsa (yıl ortası/yıl sonu yoğunluğu, kaymış tablo tarihi) gerçektir.
  // Yöntem (her gözlem aralığı için):
  //   beklenen = yerel hız (çevredeki ±10 aralığın medyanı) × gün × ülke çarpanı (aynı aralıkta 81 ilin "ham ilerleme / kendi beklenen" oranının medyanı; en az 1)
  //   net fazlalık = ilerleme − beklenen; aralığın hemen yanında duraklama (beklenenin yarısından az ilerleme, en çok 2 aralık) varsa birleşik pencerede
  //   yeniden hesaplanır (çarpan en az 0,5) ve en küçüğü alınır → telafi ise fazlalık kaybolur.
  //   B (seri imzası): beklenen ≤ 1.000, ilerleme ≥ 2 × beklenen, net ≥ 800 ve net, 1.000'in bir katına yakınsa (±(100 + beklenenin %35'i), en çok ±450) → tam o kat düşülür.
  //   A (büyük sıçrama): hız > 6 × beklenen hız ve net > 800 → aralık yerel hızla değiştirilir.   Negatif fark: < −800 ise yerel hız, değilse 0.
  // Haftalık ilerlemesi ~1.000 sıranın üstündeki illerde tek bir serinin atlanması olağan dalgalanmadan ayırt edilemez ve sayıda kalır.
  // (Tahmin motorunun temizliği farklıdır: yalnızca > 5.000 sıralık atlamaları yerel hızla değiştirir.)
  const ATLAMA_ORAN = 6, ATLAMA_FAZLA = 800, ATLAMA_PENCERE = 10, SERI = 1000, DURAK_KOMSU = 2, CARPAN_EN_AZ_IL = 20;
  function medyan(a) { const s = a.slice().sort((x, y) => x - y), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0; }
  // Ham seri: g (gün), v (sıra), hiz[i] ve yerel[i] = i. gözlemle biten aralığın hızı ve çevresinin medyan hızı (sıra/gün).
  function hamSeri(obs) {
    const o = obs.filter((x, i) => i === 0 || x[0] > obs[i - 1][0]), hiz = [0], yerel = [0];
    for (let i = 1; i < o.length; i++) hiz.push((o[i][1] - o[i - 1][1]) / (o[i][0] - o[i - 1][0]));
    for (let i = 1; i < o.length; i++) yerel.push(Math.max(0, medyan(hiz.slice(Math.max(1, i - ATLAMA_PENCERE), Math.min(o.length, i + ATLAMA_PENCERE + 1)))));
    return { g: o.map(x => x[0]), v: o.map(x => x[1]), hiz, yerel };
  }
  // Ülke çarpanı: [a, b] aralığında illerin ham ilerlemesinin kendi yerel hızına oranının medyanı (tek tek illerin atlamalarına dayanıklı); yeterli il yoksa 1.
  function ulkeCarpani(hamlar) {
    const bellek = {};
    return function (a, b) {
      const k = a + "_" + b; if (k in bellek) return bellek[k];
      const q = [], orta = (a + b) / 2;
      hamlar.forEach(h => { const x = deger(h, a), y = deger(h, b); if (x == null || y == null) return; let i = 1; while (i < h.g.length - 1 && h.g[i] < orta) i++; if (h.yerel[i] > 0) q.push((y - x) / (h.yerel[i] * (b - a))); });
      return (bellek[k] = q.length >= CARPAN_EN_AZ_IL ? Math.max(0, medyan(q)) : 1);
    };
  }
  function temizle(h, carpan) {
    carpan = carpan || function () { return 1; };
    const n = h.g.length, g = [h.g[0]], v = [h.v[0]], atlama = [];
    const gun = i => h.g[i] - h.g[i - 1], fark = i => h.v[i] - h.v[i - 1], durak = j => j >= 1 && j < n && fark(j) >= 0 && fark(j) < 0.5 * h.yerel[j] * gun(j);
    for (let i = 1; i < n; i++) {
      const dt = gun(i), f = fark(i), yerel = h.yerel[i]; let yeni = f;
      if (f < 0) { yeni = f < -ATLAMA_FAZLA ? yerel * dt : 0; atlama.push({ a: h.g[i - 1], b: h.g[i], fark: f, tur: "kirilma" }); }
      else if (f - yerel * dt > ATLAMA_FAZLA) {                                                    // ucuz ön eleme: çarpan ≥ 1 olduğundan net fazlalık bundan büyük olamaz
        const c = Math.max(1, carpan(h.g[i - 1], h.g[i])), bek = yerel * dt * c; let net = f - bek, sol = 0, sag = 0;
        while (sol < DURAK_KOMSU && durak(i - 1 - sol)) sol++;
        while (sag < DURAK_KOMSU && durak(i + 1 + sag)) sag++;
        for (let l = 0; l <= sol; l++) for (let r = 0; r <= sag; r++) { if (!l && !r) continue; const a = h.g[i - 1 - l], b = h.g[i + r]; net = Math.min(net, h.v[i + r] - h.v[i - 1 - l] - yerel * (b - a) * Math.max(0.5, carpan(a, b))); }
        const kat = Math.round(net / SERI);
        if (bek <= SERI && f >= 2 * bek && net >= ATLAMA_FAZLA && kat >= 1 && Math.abs(net - SERI * kat) <= Math.min(450, 100 + 0.35 * bek)) { yeni = Math.max(0, f - SERI * kat); atlama.push({ a: h.g[i - 1], b: h.g[i], fark: f, tur: "seri", kat }); }
        else if (h.hiz[i] > ATLAMA_ORAN * Math.max(yerel * c, 0.5) && net > ATLAMA_FAZLA) { yeni = yerel * dt; atlama.push({ a: h.g[i - 1], b: h.g[i], fark: f, tur: "sicrama" }); }
      }
      g.push(h.g[i]); v.push(v[i - 1] + yeni);
    }
    return { g, v, atlama };
  }
  // Temizlenmiş kümülatif serinin verilen gündeki değeri (doğrusal interpolasyon); kapsam dışında null (ileri/geri uzatma yok).
  function deger(s, gun) {
    const g = s.g, n = g.length;
    if (!(gun >= g[0] && gun <= g[n - 1])) return null;
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) { const orta = (lo + hi) >> 1; if (g[orta] <= gun) lo = orta; else hi = orta; }
    if (g[hi] === gun) return s.v[hi];
    if (g[lo] === gun) return s.v[lo];
    return s.v[lo] + (s.v[hi] - s.v[lo]) * (gun - g[lo]) / (g[hi] - g[lo]);
  }
  function artis(s, a, b) { const x = deger(s, a), y = deger(s, b); return x == null || y == null ? null : y - x; }
  function atlamali(s, a, b) { return s.atlama.some(t => t.a < b && t.b > a); }
  // 81 ilin toplamı: tüm gözlem günlerinin birleşiminde illerin (temizlenmiş) değerleri toplanır; ortak kapsamla sınırlıdır.
  function toplamSeri(seriler) {
    const bas = Math.max.apply(null, seriler.map(s => s.g[0])), son = Math.min.apply(null, seriler.map(s => s.g[s.g.length - 1]));
    const gunler = Array.from(new Set([].concat.apply([], seriler.map(s => s.g)))).filter(x => x >= bas && x <= son).sort((x, y) => x - y);
    return { g: gunler, v: gunler.map(x => seriler.reduce((t, s) => t + deger(s, x), 0)), atlama: [] };
  }
  function hazirla(veri) {
    const e = String(veri.epoch).split("-"); EPOCH_MS = Date.UTC(+e[0], +e[1] - 1, +e[2]);
    const hamlar = veri.iller.map(x => hamSeri(x.obs)), carpan = ulkeCarpani(hamlar);
    const iller = veri.iller.map((x, i) => ({ kod: x.kod, ad: x.il, seri: temizle(hamlar[i], carpan) }));
    const toplam = toplamSeri(iller.map(x => x.seri));
    return { iller, toplam, ilk: toplam.g[0], son: toplam.g[toplam.g.length - 1] };
  }

  // ---------- dönem hesapları ----------
  // [a, b) dönemindeki artış. Dönem ilk gözlemden önce başlıyorsa ya da henüz başlamadıysa v = null;
  // sürüyorsa (b son gözlemden sonra) son gözleme kadarki kısmi değer verilir (kismi = true, bit = son gözlem günü).
  function donemDegeri(s, a, b) {
    const ilk = s.g[0], son = s.g[s.g.length - 1];
    if (a < ilk || a >= son || b <= a) return { v: null, a, b, bit: b, kismi: false, atlama: false };
    const kismi = b > son, bit = kismi ? son : b;
    return { v: artis(s, a, bit), a, b, bit, kismi, atlama: atlamali(s, a, bit) };
  }
  // Son n hafta: son gözlem gününden geriye 7 günlük dilimler; "once" = 52 hafta (364 gün) önceki aynı dilim (aynı hafta günleri).
  function sonHaftalar(s, n) {
    const son = s.g[s.g.length - 1], r = [];
    for (let k = n - 1; k >= 0; k--) {
      const b = son - 7 * k, a = b - 7;
      r.push({ a, b, v: artis(s, a, b), once: artis(s, a - 364, b - 364), atlama: atlamali(s, a, b), onceAtlama: atlamali(s, a - 364, b - 364) });
    }
    return r;
  }
  // Yılın aynı dönemleri. tur: "hafta" (1 Ocak'tan başlayan 7 günlük 52 dilim) | "ay" | "ceyrek". Dönüş: { yillar, n, hucre[yıl][k] }.
  function donemSiniri(tur, y, k) {
    if (tur === "ay") return [gunNo(y, k + 1, 1), gunNo(y, k + 2, 1)];
    if (tur === "ceyrek") return [gunNo(y, 3 * k + 1, 1), gunNo(y, 3 * k + 4, 1)];
    if (tur === "yil") return [gunNo(y, 1, 1), gunNo(y + 1, 1, 1)];
    const a = gunNo(y, 1, 1) + 7 * k; return [a, a + 7];
  }
  const DONEM_SAYISI = { hafta: 52, ay: 12, ceyrek: 4, yil: 1 };
  function yilDonemleri(s, tur) {
    const y0 = tarih(s.g[0]).y, y1 = tarih(s.g[s.g.length - 1]).y, n = DONEM_SAYISI[tur], yillar = [], hucre = {};
    for (let y = Math.max(y0, y1 - 3); y <= y1; y++) {
      yillar.push(y); hucre[y] = [];
      for (let k = 0; k < n; k++) {
        const sn = donemSiniri(tur, y, k), d = donemDegeri(s, sn[0], sn[1]);
        if (d.kismi) {
          if (tur === "hafta") d.v = null;                                                        // haftalık eğride yalnızca tamamlanan haftalar
          else { d.onceA = yilOnce(d.a); d.onceBit = yilOnce(d.bit); d.onceAyni = artis(s, d.onceA, d.onceBit); }   // geçen yılın aynı takvim aralığı
        }
        hucre[y].push(d);
      }
    }
    return { yillar, n, hucre };
  }
  // Yıl içi kümülatif artış (1 Ocak'tan beri), gün gün. 1 Ocak'ı kapsam dışında kalan yıl (2024: kayıtlar 9 Şubat'ta başlar) yer almaz.
  function kumulatif(s) {
    const ilk = s.g[0], son = s.g[s.g.length - 1], y1 = tarih(son).y, r = [];
    for (let y = y1 - 3; y <= y1; y++) {
      const a = gunNo(y, 1, 1), b = Math.min(gunNo(y + 1, 1, 1), son);
      if (a < ilk || a >= son) continue;
      const nokta = []; for (let x = a; x <= b; x++) nokta.push(artis(s, a, x));
      r.push({ yil: y, a, nokta });
    }
    return r;
  }
  // İller arası kıyas: [a, b) döneminde her ilin artışı ve bir yıl önceki aynı takvim aralığı (dönem sürüyorsa aynı güne kadar).
  function ilKiyas(iller, a, b) {
    return iller.map(x => {
      const d = donemDegeri(x.seri, a, b), oa = yilOnce(a), ob = yilOnce(d.bit);
      const once = d.v == null || oa < x.seri.g[0] ? null : artis(x.seri, oa, ob);
      return { kod: x.kod, ad: x.ad, v: d.v, once, yuzde: d.v != null && once > 0 ? (d.v / once - 1) * 100 : null,
               kismi: d.kismi, bit: d.bit, atlama: d.atlama || (once != null && atlamali(x.seri, oa, ob)) };
    });
  }
  function donemSecenekleri(ilk, son, tur) {                                                       // yeniden eskiye; başlangıcı veri kapsamındaki dönemler
    const r = [], y1 = tarih(son).y, n = DONEM_SAYISI[tur];
    for (let y = y1; y >= tarih(ilk).y; y--) for (let k = n - 1; k >= 0; k--) {
      const sn = donemSiniri(tur, y, k); if (sn[0] < ilk || sn[0] >= son) continue;
      const ad = tur === "ay" ? AYLAR[k] + " " + y : tur === "ceyrek" ? CEYREK[k] + " " + y : String(y);
      r.push({ a: sn[0], b: sn[1], ad, kismi: sn[1] > son, yil: y, k });
    }
    return r;
  }
  // Özet kutuları: son hafta / son 4 hafta / son 52 hafta (364 gün önceki aynı dilime göre) ve yılbaşından beri (geçen yılın aynı gününe kadar).
  function ozet(s) {
    const son = s.g[s.g.length - 1], y = tarih(son).y, yb = gunNo(y, 1, 1);
    const dilim = (a, b, oa, ob) => { const v = artis(s, a, b), once = artis(s, oa, ob); return { a, b, v, once, yuzde: v != null && once > 0 ? (v / once - 1) * 100 : null }; };
    return { hafta: dilim(son - 7, son, son - 371, son - 364), dortHafta: dilim(son - 28, son, son - 392, son - 364),
             yilBasi: dilim(yb, son, gunNo(y - 1, 1, 1), yilOnce(son)), elliIki: dilim(son - 364, son, son - 728, son - 364) };
  }

  // ---------- biçimlendirme ----------
  function sayi(n) { const r = Math.round(n); return (r < 0 ? "−" : "") + String(Math.abs(r)).replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function yaklasik(x) { if (x == null) return "—"; const q = Math.abs(x) < 200 ? 1 : Math.abs(x) < 2000 ? 10 : 100; return "~" + sayi(Math.round(x / q) * q); }   // il sayfalarındaki yuvarlama (tn) + küçük illerin haftalık değerleri için 200'ün altında tam sayı
  function oranYaz(x) { return x == null ? "—" : "%" + String(Math.round(x * 10) / 10).replace(".", ","); }       // işaretsiz oran: %43,2
  function yuzdeYaz(p) { if (p == null) return "—"; const r = Math.round(p); return (r > 0 ? "+" : r < 0 ? "−" : "±") + "%" + Math.abs(r); }
  function kesir(x) { return String(+x.toFixed(2)).replace(".", ","); }
  function eksenBicimi(ust) {
    if (ust >= 1e6) return d => d === 0 ? "0" : kesir(d / 1e6) + " mn";
    if (ust >= 1e4) return d => d === 0 ? "0" : kesir(d / 1e3) + " bin";
    return d => sayi(d);
  }
  function gunAy(g, kisa) { const t = tarih(g); return t.d + " " + (kisa ? AY_KISA : AYLAR)[t.m - 1]; }
  function tamTarih(g) { const t = tarih(g); return t.d + " " + AYLAR[t.m - 1] + " " + t.y; }
  function aralikKisa(a, b) { const x = tarih(a), y = tarih(b); return x.m === y.m ? x.d + "–" + y.d + " " + AYLAR[y.m - 1] : gunAy(a) + " – " + gunAy(b); }   // yılsız
  function aralik(a, b) {                                                                          // a ve b DAHİL: "7–13 Kasım 2026", "28 Ekim – 3 Kasım 2026"
    const x = tarih(a), y = tarih(b);
    if (x.y !== y.y) return tamTarih(a) + " – " + tamTarih(b);
    return x.m === y.m ? x.d + "–" + y.d + " " + AYLAR[y.m - 1] + " " + y.y : gunAy(a) + " – " + tamTarih(b);
  }
  // Eksen için "güzel" üst sınır ve çizgiler (0 dahil).
  function olcek(maks, hedef) {
    if (!(maks > 0)) maks = 1;
    const ham = maks / (hedef || 4), us = Math.pow(10, Math.floor(Math.log10(ham))), k = ham / us;
    const adim = (k <= 1 ? 1 : k <= 2 ? 2 : k <= 2.5 ? 2.5 : k <= 5 ? 5 : 10) * us, adet = Math.ceil(maks / adim - 1e-9), cizgiler = [];
    for (let i = 0; i <= adet; i++) cizgiler.push(+(i * adim).toPrecision(12));
    return { ust: adet * adim, adim, cizgiler };
  }

  const saf = { AYLAR, gunNo, tarih, yilOnce, medyan, hamSeri, ulkeCarpani, temizle, deger, artis, atlamali, toplamSeri, hazirla, donemDegeri, sonHaftalar, donemSiniri, yilDonemleri,
                kumulatif, ilKiyas, donemSecenekleri, ozet, sayi, yaklasik, yuzdeYaz, oranYaz, eksenBicimi, aralik, olcek };
  if (typeof document === "undefined") return saf;

  // =====================================================================================================================
  // Çizim (tarayıcı). Renkler: yıllar yenilik sırasıyla (son yıl mavi, önceki turuncu, …) — tests/test_istatistik.py paleti doğrulanmış sırayla sabitler.
  // =====================================================================================================================
  const NS = "http://www.w3.org/2000/svg";
  const RENK = { yil: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"], arti: "#2a78d6", eksi: "#e34948", ref: "#4d5461", izgara: "#e9ebef", taban: "#aeb4bf", murekkep: "#15171c", yuzey: "#fcfcfa", vurgu: "#e3eefb" };
  const $ = (s, k) => (k || document).querySelector(s);
  function el(ad, oz, ust) { const e = document.createElementNS(NS, ad); for (const k in oz) e.setAttribute(k, oz[k]); if (ust) ust.appendChild(e); return e; }
  function yazi(ust, x, y, metin, oz) { const t = el("text", Object.assign({ x, y, class: "eksen" }, oz || {}), ust); t.textContent = metin; return t; }
  function html(ad, sinif, metin) { const e = document.createElement(ad); if (sinif) e.className = sinif; if (metin != null) e.textContent = metin; return e; }

  let V = null;                                                                                    // hazirla() çıktısı
  const durum = { il: 0, n: 13, tur: "ay", kTur: "ay", kDonem: 0, olcu: "adet", goster: "ilk", ek: [], anaGizli: false, anaRenk: 0, bOlcek: "adet" };   // ek: birikim grafiğine eklenen iller [{kod, renk}] (0 = Türkiye); anaGizli: seçili il o grafikten çıkarıldı
  const adlar = {};                                                                                // kod → görünen ad (sayfadaki <select>'ten)
  function seriOf(kod) { if (!kod) return V.toplam; const x = V.iller.find(i => i.kod === kod); return x ? x.seri : V.toplam; }
  function adOf(kod) { return kod ? adlar[kod] : "Türkiye (81 il)"; }
  function seciliSeri() { return seriOf(durum.il); }
  function seciliAd() { return adOf(durum.il); }
  function yilRengi(y, sonYil) { return RENK.yil[Math.min(sonYil - y, RENK.yil.length - 1)]; }

  function tuval(kap, yuk, k) {
    const eski = $("svg", kap); if (eski) eski.remove(); ipucuGizle(kap);
    const W = Math.max(220, Math.floor(kap.clientWidth || 688));
    const svg = el("svg", { viewBox: "0 0 " + W + " " + yuk, width: W, height: yuk, role: "img" });
    kap.insertBefore(svg, kap.firstChild);
    return { svg, kap, W, H: yuk, x0: k.sol, x1: W - k.sag, y0: k.ust, y1: yuk - k.alt };
  }
  function yEkseni(t, maks, bicim) {
    const o = olcek(maks), b = bicim || eksenBicimi(o.ust), y = v => t.y1 - (v / o.ust) * (t.y1 - t.y0);
    o.cizgiler.forEach(d => { if (d) el("line", { x1: t.x0, x2: t.x1, y1: y(d), y2: y(d), stroke: RENK.izgara, "stroke-width": 1 }, t.svg); yazi(t.svg, t.x0 - 6, y(d) + 4, b(d), { "text-anchor": "end" }); });
    return y;
  }
  function tabanCiz(t) { el("line", { x1: t.x0, x2: t.x1, y1: t.y1, y2: t.y1, stroke: RENK.taban, "stroke-width": 1 }, t.svg); }
  // Sütun: veri ucunda 4px yuvarlak, tabanda düz. Yatay çubukta (yatay = true) uç sağdadır; eksi değerde solda.
  function cubuk(ust, x, y, w, h, dolgu, yon) {
    w = Math.max(w, 0); h = Math.max(h, 0);
    const r = Math.min(4, yon === "yukari" ? w / 2 : h / 2, yon === "yukari" ? h : w);
    const d = yon === "yukari" ? `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`
            : yon === "sag" ? `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`
            : `M${x + w},${y}H${x + r}Q${x},${y} ${x},${y + r}V${y + h - r}Q${x},${y + h} ${x + r},${y + h}H${x + w}Z`;
    return el("path", { d, fill: dolgu }, ust);
  }
  function cizgi(ust, noktalar, renk, kalinlik) {                                                  // null noktalarda çizgi kesilir
    let d = "", acik = false;
    noktalar.forEach(p => { if (!p) { acik = false; return; } d += (acik ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1); acik = true; });
    return el("path", { d, fill: "none", stroke: renk, "stroke-width": kalinlik || 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, ust);
  }
  function tarama(svg, kimlik, renk) {                                                             // süren (kısmi) dönem dolgusu: aynı rengin 45° taraması
    const defs = $("defs", svg) || el("defs", {}, svg);
    const p = el("pattern", { id: kimlik, width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    el("rect", { width: 5, height: 5, fill: renk, opacity: 0.28 }, p); el("rect", { width: 2, height: 5, fill: renk }, p);
    return "url(#" + kimlik + ")";
  }

  // ---------- ipucu (hover/dokunma): değer önde, ad arkada; tüm metinler textContent ile yazılır ----------
  function ipucuGizle(kap) { const k = $(".gr-ipucu", kap); if (k) k.hidden = true; const v = $(".vurgu", kap); if (v) v.textContent = ""; }
  function ipucuGoster(t, px, py, ic) {
    let k = $(".gr-ipucu", t.kap); if (!k) { k = html("div", "gr-ipucu"); t.kap.appendChild(k); }
    k.textContent = ""; k.appendChild(html("div", "b", ic.baslik));
    (ic.satirlar || []).forEach(s => {
      const r = html("div", "s"); const a = html("i", s.bicim === "cizgi" ? "cizgi" : s.bicim === "isaret" ? "isaret" : "");
      if (s.renk) { a.style.color = s.renk; r.appendChild(a); }
      r.appendChild(html("b", "", s.deger)); r.appendChild(html("span", "", s.ad)); k.appendChild(r);
    });
    (ic.notlar || []).forEach(n => k.appendChild(html("div", "n", n)));
    k.hidden = false;
    const kw = k.offsetWidth, kh = k.offsetHeight, olc = t.kap.clientWidth / t.W;
    let sol = px * olc + 14; if (sol + kw > t.kap.clientWidth) sol = px * olc - 14 - kw;
    k.style.left = Math.max(0, Math.min(sol, t.kap.clientWidth - kw)) + "px";
    k.style.top = Math.max(0, Math.min(py * olc - kh / 2, t.H * olc - kh)) + "px";
  }
  // coz(px, py) → dilim numarası (yoksa −1); icerik(i) → ipucu; vurgula(g, i) → vurgu katmanını çizer.
  function etkilesim(t, coz, icerik, vurgula) {
    const g = el("g", { class: "vurgu", "pointer-events": "none" }, t.svg);
    function git(e) {
      const r = t.svg.getBoundingClientRect(), px = (e.clientX - r.left) * t.W / r.width, py = (e.clientY - r.top) * t.H / r.height, i = coz(px, py);
      g.textContent = ""; if (i < 0) { ipucuGizle(t.kap); return; }
      vurgula(g, i); ipucuGoster(t, px, py, icerik(i));
    }
    t.svg.addEventListener("pointermove", git); t.svg.addEventListener("pointerdown", git);
    t.svg.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") ipucuGizle(t.kap); });
  }
  document.addEventListener("pointerdown", e => { document.querySelectorAll(".cizim").forEach(k => { if (!k.contains(e.target)) ipucuGizle(k); }); });

  function lejantYaz(bolum, ogeler) {                                                              // ogeler: [{renk, bicim: "kutu"|"cizgi"|"tarali"|"isaret", ad}]
    const l = $(".lejant", bolum); l.textContent = "";
    ogeler.forEach(o => { const s = html("span"); const i = html("i", o.bicim === "kutu" ? "" : o.bicim); i.style.color = o.renk; s.appendChild(i); s.appendChild(document.createTextNode(o.ad)); l.appendChild(s); });
  }
  function tabloYaz(bolum, basliklar, satirlar) {
    const kap = $(".tablo .kaydir", bolum); kap.textContent = "";
    const tb = html("table"), tr = html("tr"); basliklar.forEach((b, i) => { const th = html("th", i ? "n" : "", b); th.scope = "col"; tr.appendChild(th); }); tb.appendChild(tr);
    satirlar.forEach(s => { const r = html("tr"); s.forEach((h, i) => r.appendChild(html("td", i ? "n" : "", h))); tb.appendChild(r); });
    kap.appendChild(tb);
  }
  function dipnot(bolum, metinler) { const d = $(".dipnot", bolum); d.textContent = metinler.join(" "); d.hidden = !metinler.length; }
  const ATLAMA_NOTU = "† Bu dönemde seri atlaması ya da kayıt kırılması var; ilgili gözlem aralığı olağan hızla değiştirildi.";

  // ---------- özet kutuları ----------
  function cizOzet() {
    const o = ozet(seciliSeri()), y = tarih(V.son).y;
    [["hafta", "Son hafta", "geçen yılın aynı haftasına göre"], ["dortHafta", "Son 4 hafta", "geçen yılın aynı 4 haftasına göre"],
     ["yilBasi", y + " başından beri", "geçen yılın aynı gününe göre"], ["elliIki", "Son 52 hafta", "önceki 52 haftaya göre"]].forEach(a => {
      const k = $('[data-ozet="' + a[0] + '"]'), d = o[a[0]];
      $(".e", k).textContent = a[1]; $(".v", k).textContent = yaklasik(d.v);
      $(".k", k).textContent = d.yuzde == null ? "karşılaştırma yok" : (d.yuzde >= 0.5 ? "▲ " : d.yuzde <= -0.5 ? "▼ " : "") + yuzdeYaz(d.yuzde) + " · " + a[2];
    });
  }

  // ---------- 1) son N hafta ----------
  function cizHafta() {
    const b = $("#g-hafta"), s = seciliSeri(), veri = sonHaftalar(s, durum.n), t = tuval($(".cizim", b), 250, { sol: 52, sag: 6, ust: 14, alt: 26 });
    const y = yEkseni(t, Math.max.apply(null, veri.map(d => Math.max(d.v || 0, d.once || 0)))), bant = (t.x1 - t.x0) / veri.length, gen = Math.max(1.5, Math.min(24, bant - 2));
    const xo = i => t.x0 + (i + 0.5) * bant;
    veri.forEach((d, i) => { if (d.v == null) return; cubuk(t.svg, xo(i) - gen / 2, y(d.v), gen, t.y1 - y(d.v), RENK.yil[0], "yukari"); if (d.atlama) yazi(t.svg, xo(i), y(d.v) - 4, "†", { "text-anchor": "middle" }); });
    cizgi(t.svg, veri.map((d, i) => d.once == null ? null : [xo(i), y(d.once)]), RENK.ref, 1.5);
    tabanCiz(t);
    const adim = Math.ceil(56 / bant);
    veri.forEach((d, i) => { if ((veri.length - 1 - i) % adim) return; const sonMu = i === veri.length - 1; yazi(t.svg, sonMu ? Math.min(t.x1, xo(i) + 18) : xo(i), t.H - 8, gunAy(d.b, true), { "text-anchor": sonMu ? "end" : "middle" }); });
    t.svg.setAttribute("aria-label", seciliAd() + ": son " + durum.n + " haftada haftalık plaka artışı; son hafta " + yaklasik(veri[veri.length - 1].v) + ".");
    etkilesim(t, (px, py) => px < t.x0 || px > t.x1 ? -1 : Math.min(veri.length - 1, Math.floor((px - t.x0) / bant)),
      i => { const d = veri[i]; return { baslik: aralik(d.a + 1, d.b), satirlar: [{ renk: RENK.yil[0], deger: yaklasik(d.v), ad: "bu hafta" }, { renk: RENK.ref, bicim: "cizgi", deger: yaklasik(d.once), ad: "bir yıl önce (" + aralik(d.a - 363, d.b - 364) + ")" }],
        notlar: (d.v != null && d.once > 0 ? ["Değişim: " + yuzdeYaz((d.v / d.once - 1) * 100)] : []).concat(d.atlama || d.onceAtlama ? [ATLAMA_NOTU] : []) }; },
      (g, i) => el("rect", { x: t.x0 + i * bant, y: t.y0, width: bant, height: t.y1 - t.y0, fill: RENK.murekkep, opacity: 0.06 }, g));
    lejantYaz(b, [{ renk: RENK.yil[0], bicim: "kutu", ad: "Haftalık artış" }, { renk: RENK.ref, bicim: "cizgi", ad: "Bir yıl önceki aynı hafta" }]);
    $(".aciklama", b).textContent = seciliAd() + " · " + tamTarih(veri[0].a + 1) + " – " + tamTarih(V.son) + " · her sütun 7 gün";
    dipnot(b, veri.some(d => d.atlama) ? [ATLAMA_NOTU] : []);
    tabloYaz(b, ["Hafta", "Artış", "Bir yıl önce", "Değişim"], veri.slice().reverse().map(d => [aralik(d.a + 1, d.b) + (d.atlama ? " †" : ""), yaklasik(d.v), yaklasik(d.once), d.v != null && d.once > 0 ? yuzdeYaz((d.v / d.once - 1) * 100) : "—"]));
  }

  // ---------- 2) yılın aynı dönemleri ----------
  function ayKonumlari(y) { const b = gunNo(y, 1, 1), r = []; for (let m = 1; m <= 13; m++) r.push(gunNo(y, m, 1) - b); return r; }   // her ayın yıl içindeki başlangıç günü (+ yıl sonu)
  function ayEtiketleri(t, x, y) {                                                                 // x(gün) → piksel; ay adları ayın ortasına
    const k = ayKonumlari(y), dar = (t.x1 - t.x0) / 12 < 30;
    for (let m = 0; m < 12; m++) {
      if (m) el("line", { x1: x(k[m]), x2: x(k[m]), y1: t.y1, y2: t.y1 + 4, stroke: RENK.taban, "stroke-width": 1 }, t.svg);
      if (!dar || m % 2 === 0) yazi(t.svg, x((k[m] + k[m + 1]) / 2), t.H - 8, AY_KISA[m], { "text-anchor": "middle" });       // dar ekranda iki ayda bir etiket
    }
  }
  function cizDonem() {
    const b = $("#g-donem"), s = seciliSeri(), tur = durum.tur, D = yilDonemleri(s, tur), sonYil = D.yillar[D.yillar.length - 1];
    const t = tuval($(".cizim", b), 270, { sol: 52, sag: tur === "hafta" ? 12 : 6, ust: 14, alt: 26 });
    const hepsi = []; D.yillar.forEach(yl => D.hucre[yl].forEach(d => { if (d.v != null) hepsi.push(d.v); }));
    const y = yEkseni(t, Math.max.apply(null, hepsi.concat([1]))), bant = (t.x1 - t.x0) / D.n;
    const etiket = k => tur === "ay" ? AYLAR[k] : tur === "ceyrek" ? CEYREK[k] : (k + 1) + ". hafta";
    let surenVar = false, atlamaVar = false; const lej = [], notlar = [];
    if (tur === "hafta") {
      const xo = k => t.x0 + (k + 0.5) * bant;
      D.yillar.forEach(yl => { const r = yilRengi(yl, sonYil), n = D.hucre[yl].map((d, k) => d.v == null ? null : [xo(k), y(d.v)]); cizgi(t.svg, n, r, 2); lej.push({ renk: r, bicim: "cizgi", ad: String(yl) });
        if (yl === sonYil) { const son = n.filter(Boolean).pop(); if (son) el("circle", { cx: son[0], cy: son[1], r: 4, fill: r, stroke: RENK.yuzey, "stroke-width": 2 }, t.svg); } });
      tabanCiz(t); ayEtiketleri(t, g => t.x0 + g / 7 * bant, sonYil);
      etkilesim(t, (px, py) => px < t.x0 || px > t.x1 ? -1 : Math.min(D.n - 1, Math.floor((px - t.x0) / bant)),
        k => { const sn = donemSiniri("hafta", sonYil, k); return { baslik: etiket(k) + " · " + aralikKisa(sn[0], sn[1] - 1),
          satirlar: D.yillar.slice().reverse().map(yl => ({ renk: yilRengi(yl, sonYil), bicim: "cizgi", deger: yaklasik(D.hucre[yl][k].v), ad: String(yl) })) }; },
        (g, k) => { el("line", { x1: xo(k), x2: xo(k), y1: t.y0, y2: t.y1, stroke: RENK.ref, "stroke-width": 1 }, g);
          D.yillar.forEach(yl => { const d = D.hucre[yl][k]; if (d.v != null) el("circle", { cx: xo(k), cy: y(d.v), r: 4, fill: yilRengi(yl, sonYil), stroke: RENK.yuzey, "stroke-width": 2 }, g); }); });
      notlar.push("Haftalar 1 Ocak’tan başlayan 7 günlük dilimlerdir; yalnızca tamamlanan haftalar çizilir.");
    } else {
      const adet = D.yillar.length, ic = Math.min(24, Math.max(2, (bant * 0.82 - 2 * (adet - 1)) / adet)), grup = adet * ic + 2 * (adet - 1);
      D.yillar.forEach((yl, j) => { const r = yilRengi(yl, sonYil); lej.push({ renk: r, bicim: "kutu", ad: String(yl) });
        D.hucre[yl].forEach((d, k) => { if (d.v == null) return; const x = t.x0 + k * bant + (bant - grup) / 2 + j * (ic + 2);
          if (d.kismi) surenVar = true; if (d.atlama) atlamaVar = true;
          cubuk(t.svg, x, y(d.v), ic, t.y1 - y(d.v), d.kismi ? tarama(t.svg, "tarali-" + j, r) : r, "yukari");
          if (d.atlama && ic >= 5) yazi(t.svg, x + ic / 2, y(d.v) - 4, "†", { "text-anchor": "middle" }); }); });
      tabanCiz(t);
      for (let k = 0; k < D.n; k++) if (tur !== "ay" || bant >= 30 || k % 2 === 0) yazi(t.svg, t.x0 + (k + 0.5) * bant, t.H - 8, tur === "ay" ? AY_KISA[k] : CEYREK[k], { "text-anchor": "middle" });
      etkilesim(t, (px, py) => px < t.x0 || px > t.x1 ? -1 : Math.min(D.n - 1, Math.floor((px - t.x0) / bant)),
        k => { const nt = []; const sat = D.yillar.slice().reverse().map(yl => { const d = D.hucre[yl][k];
            if (d.v != null && d.kismi) { nt.push(yl + ": " + aralik(d.a, d.bit) + " arası (dönem sürüyor)." + (d.onceAyni > 0 ? " Önceki yılın aynı aralığında " + yaklasik(d.onceAyni) + " (" + yuzdeYaz((d.v / d.onceAyni - 1) * 100) + ")." : "")); }
            if (d.atlama) nt.push(yl + " " + ATLAMA_NOTU);
            return { renk: yilRengi(yl, sonYil), deger: yaklasik(d.v) + (d.kismi && d.v != null ? "*" : ""), ad: String(yl) }; });
          return { baslik: etiket(k), satirlar: sat, notlar: nt }; },
        (g, k) => el("rect", { x: t.x0 + k * bant, y: t.y0, width: bant, height: t.y1 - t.y0, fill: RENK.murekkep, opacity: 0.06 }, g));
      if (surenVar) { lej.push({ renk: RENK.yil[0], bicim: "tarali", ad: "süren dönem (" + gunAy(V.son) + " itibarıyla)" }); }
      if (atlamaVar) notlar.push(ATLAMA_NOTU);
    }
    notlar.push("Kayıtlar " + tamTarih(s.g[0]) + " tarihinde başlar; bu tarihten önce başlayan dönemler gösterilmez.");
    t.svg.setAttribute("aria-label", seciliAd() + ": yıllara göre " + (tur === "ay" ? "aylık" : tur === "ceyrek" ? "üç aylık" : "haftalık") + " plaka artışı.");
    lejantYaz(b, lej); $(".aciklama", b).textContent = seciliAd() + " · " + D.yillar[0] + "–" + sonYil + " · aynı takvim dönemleri yan yana"; dipnot(b, notlar);
    const satirlar = []; for (let k = 0; k < D.n; k++) satirlar.push([etiket(k)].concat(D.yillar.map(yl => { const d = D.hucre[yl][k]; return yaklasik(d.v) + (d.v != null && d.kismi ? "*" : "") + (d.atlama ? " †" : ""); })));
    tabloYaz(b, ["Dönem"].concat(D.yillar.map(String)), satirlar);
  }

  // ---------- 3) yıl içi kümülatif ----------
  // Birikim grafiğinde il karşılaştırma: en çok 3 çizgi (kategorik paletin ilk üç rengi her çift için doğrulanmıştır).
  // Üstte seçili il ("ana") varsayılan olarak çizilir; başka il eklendikten sonra o da çıkarılabilir (anaGizli) — böylece yalnızca seçilen iller kalır.
  // Renk ile bağlıdır: il, eklendiği andaki boş rengi alır ve başka il çıkarılınca rengi değişmez. Eklenen son il çıkarılınca grafik tek il / yıllar görünümüne döner.
  const CIZGI_EN_COK = 3;
  function cizgiSayisi() { return durum.ek.length + (durum.anaGizli ? 0 : 1); }
  function bosRenk() { let r = 0; while ((!durum.anaGizli && durum.anaRenk === r) || durum.ek.some(e => e.renk === r)) r++; return r; }
  function ekEkle(kod) {
    if (kod === durum.il) { if (durum.anaGizli && cizgiSayisi() < CIZGI_EN_COK) { durum.anaRenk = bosRenk(); durum.anaGizli = false; } return; }      // çıkarılmış ana il listeden yeniden eklenir
    if (cizgiSayisi() >= CIZGI_EN_COK || durum.ek.some(e => e.kod === kod) || (kod && !adlar[kod])) return;
    durum.ek.push({ kod, renk: bosRenk() });
  }
  function ekCikar(kod) {                                                                         // kod: "ana" ya da il kodu
    if (kod === "ana") { if (durum.ek.length) durum.anaGizli = true; } else durum.ek = durum.ek.filter(x => x.kod !== kod);
    if (!durum.ek.length) { durum.anaGizli = false; durum.anaRenk = 0; }
  }
  function anaIlDegisti() {                                                                       // üstteki il seçimi değişti: yeni il zaten ekliyse ekten düşer; ana il çıkarılmışsa ve yer varsa yeniden çizilir
    const eski = durum.ek.find(e => e.kod === durum.il); durum.ek = durum.ek.filter(e => e.kod !== durum.il);
    if (!durum.ek.length) { durum.anaGizli = false; durum.anaRenk = 0; }
    else if (durum.anaGizli && cizgiSayisi() < CIZGI_EN_COK) { durum.anaRenk = eski ? eski.renk : bosRenk(); durum.anaGizli = false; }
  }
  function ekleriYaz() {
    const sec = $("#b-ekle"), kap = $("#b-ekler"), dolu = cizgiSayisi() >= CIZGI_EN_COK; sec.textContent = "";
    const ilk = html("option", "", dolu ? "En çok 3 il karşılaştırılır" : "Karşılaştırmak için il ekle…"); ilk.value = ""; sec.appendChild(ilk); sec.disabled = dolu;
    if (!dolu) Array.prototype.forEach.call($("#il").options, o => { const k = +o.value || 0; if ((k === durum.il && !durum.anaGizli) || durum.ek.some(e => e.kod === k)) return; const y = html("option", "", k ? adlar[k] : "Türkiye (81 il toplamı)"); y.value = String(k); sec.appendChild(y); });
    kap.textContent = "";
    const cip = (kod, ad, renk) => { const d = html("button", "ek"); d.type = "button"; d.dataset.kod = kod; d.setAttribute("aria-label", ad + ": karşılaştırmadan çıkar");
      const i = html("i"); i.style.color = RENK.yil[renk]; d.appendChild(i); d.appendChild(document.createTextNode(ad)); const x = html("span", "", "×"); x.setAttribute("aria-hidden", "true"); d.appendChild(x); kap.appendChild(d); };
    if (durum.ek.length) { if (!durum.anaGizli) cip("ana", seciliAd(), durum.anaRenk); durum.ek.forEach(e => cip(e.kod, adOf(e.kod), e.renk)); }
    $("#b-olcek").hidden = !durum.ek.length;
  }
  function cizBirikimCoklu(b) {
    const sonYil = tarih(V.son).y, oran = durum.bOlcek === "oran", yb = gunNo(sonYil, 1, 1), gunSayisi = 366, notlar = [];
    let seriler = (durum.anaGizli ? [] : [{ kod: durum.il, renk: RENK.yil[durum.anaRenk] }]).concat(durum.ek.map(e => ({ kod: e.kod, renk: RENK.yil[e.renk] }))).map(x => {
      const K = kumulatif(seriOf(x.kod)), bu = K.find(k => k.yil === sonYil), gecen = K.find(k => k.yil === sonYil - 1);
      const tam = gecen && gecen.nokta.length === gunNo(sonYil, 1, 1) - gecen.a + 1 ? gecen.nokta[gecen.nokta.length - 1] : null;      // geçen yılın TAM yıl toplamı
      return Object.assign(x, { ad: adOf(x.kod), adet: bu ? bu.nokta : [], gecen: gecen ? gecen.nokta : [], tam, nokta: !bu ? [] : !oran ? bu.nokta : tam > 0 ? bu.nokta.map(v => v / tam * 100) : [] });
    });
    const eksik = seriler.filter(x => !x.nokta.length).map(x => x.ad); if (eksik.length) notlar.push(eksik.join(", ") + " için bu ölçekte veri yok."); seriler = seriler.filter(x => x.nokta.length);
    const t = tuval($(".cizim", b), 260, { sol: 52, sag: 14, ust: 14, alt: 26 }), x = g => t.x0 + g / gunSayisi * (t.x1 - t.x0);
    const y = yEkseni(t, Math.max.apply(null, seriler.map(q => q.nokta[q.nokta.length - 1]).concat([1])), oran ? d => "%" + kesir(d) : null), bic = oran ? oranYaz : yaklasik;
    seriler.forEach(q => { cizgi(t.svg, q.nokta.map((v, i) => [x(i), y(v)]), q.renk, 2); const i = q.nokta.length - 1; el("circle", { cx: x(i), cy: y(q.nokta[i]), r: 4, fill: q.renk, stroke: RENK.yuzey, "stroke-width": 2 }, t.svg); });
    tabanCiz(t); ayEtiketleri(t, x, sonYil);
    etkilesim(t, (px, py) => px < t.x0 || px > t.x1 ? -1 : Math.min(gunSayisi - 1, Math.round((px - t.x0) / (t.x1 - t.x0) * gunSayisi)),
      i => { const sat = seriler.filter(q => i < q.nokta.length).map(q => ({ renk: q.renk, bicim: "cizgi", deger: bic(q.nokta[i]),
          ad: q.ad + (oran ? " (" + yaklasik(q.adet[i]) + ")" : i > 0 && q.gecen[i] > 0 ? " (" + yuzdeYaz((q.adet[i] / q.gecen[i] - 1) * 100) + ")" : "") }));
        return { baslik: "1 Ocak – " + tamTarih(yb + i), satirlar: sat, notlar: !sat.length ? ["Bu gün için veri yok."] : oran ? [] : ["Parantez içi: geçen yılın aynı gününe göre değişim."] }; },
      (g, i) => { el("line", { x1: x(i), x2: x(i), y1: t.y0, y2: t.y1, stroke: RENK.ref, "stroke-width": 1 }, g);
        seriler.forEach(q => { if (i < q.nokta.length) el("circle", { cx: x(i), cy: y(q.nokta[i]), r: 4, fill: q.renk, stroke: RENK.yuzey, "stroke-width": 2 }, g); }); });
    lejantYaz(b, seriler.map(q => ({ renk: q.renk, bicim: "cizgi", ad: q.ad })));
    $(".aciklama", b).textContent = sonYil + " · " + tamTarih(V.son) + " itibarıyla · " + seriler.map(q => q.ad + " " + bic(q.nokta[q.nokta.length - 1])).join(" · ");
    t.svg.setAttribute("aria-label", sonYil + " yılında 1 Ocak’tan beri biriken plaka artışı: " + seriler.map(q => q.ad).join(", ") + ".");
    notlar.unshift(oran ? "Oran: ilin 1 Ocak’tan beri biriken artışının, aynı ilin " + (sonYil - 1) + " yılı toplamına bölümü (%100 = geçen yılın tamamı kadar)."
                        : "Büyüklüğü çok farklı illeri kıyaslamak için “Geçen yılın toplamına oran” ölçeğini seçin."); dipnot(b, notlar);
    const satirlar = []; for (let m = 2; m <= 13; m++) { const i = gunNo(sonYil, m, 1) - yb; if (!seriler.some(q => i < q.nokta.length)) break; satirlar.push(["1 " + AYLAR[m - 1]].concat(seriler.map(q => bic(i < q.nokta.length ? q.nokta[i] : null)))); }
    satirlar.push([gunAy(V.son) + " (son veri)"].concat(seriler.map(q => bic(q.nokta[q.nokta.length - 1]))));
    tabloYaz(b, [sonYil + ": 1 Ocak’tan şu güne kadar"].concat(seriler.map(q => q.ad)), satirlar);
  }
  function cizKumulatif() {
    ekleriYaz(); if (durum.ek.length) return cizBirikimCoklu($("#g-kumulatif"));
    const b = $("#g-kumulatif"), s = seciliSeri(), K = kumulatif(s), sonYil = tarih(V.son).y, t = tuval($(".cizim", b), 260, { sol: 52, sag: 14, ust: 14, alt: 26 });
    const y = yEkseni(t, Math.max.apply(null, K.map(k => k.nokta[k.nokta.length - 1]).concat([1]))), gunSayisi = 366, x = g => t.x0 + g / gunSayisi * (t.x1 - t.x0);
    K.forEach(k => { const r = yilRengi(k.yil, sonYil); cizgi(t.svg, k.nokta.map((v, i) => [x(i), y(v)]), r, 2);
      if (k.yil === sonYil) { const i = k.nokta.length - 1; el("circle", { cx: x(i), cy: y(k.nokta[i]), r: 4, fill: r, stroke: RENK.yuzey, "stroke-width": 2 }, t.svg); } });
    tabanCiz(t); ayEtiketleri(t, x, sonYil);
    const bu = K.find(k => k.yil === sonYil), gecen = K.find(k => k.yil === sonYil - 1);
    etkilesim(t, (px, py) => px < t.x0 || px > t.x1 ? -1 : Math.min(gunSayisi - 1, Math.round((px - t.x0) / (t.x1 - t.x0) * gunSayisi)),
      i => { const sat = K.slice().reverse().filter(k => i < k.nokta.length).map(k => ({ renk: yilRengi(k.yil, sonYil), bicim: "cizgi", deger: yaklasik(k.nokta[i]), ad: String(k.yil) }));
        const nt = bu && gecen && i < bu.nokta.length && i < gecen.nokta.length && gecen.nokta[i] > 0 && i > 0 ? ["Önceki yıla göre " + yuzdeYaz((bu.nokta[i] / gecen.nokta[i] - 1) * 100)] : [];
        return { baslik: "1 Ocak – " + gunAy(gunNo(sonYil, 1, 1) + i), satirlar: sat, notlar: sat.length ? nt : ["Bu gün için veri yok."] }; },
      (g, i) => { el("line", { x1: x(i), x2: x(i), y1: t.y0, y2: t.y1, stroke: RENK.ref, "stroke-width": 1 }, g);
        K.forEach(k => { if (i < k.nokta.length) el("circle", { cx: x(i), cy: y(k.nokta[i]), r: 4, fill: yilRengi(k.yil, sonYil), stroke: RENK.yuzey, "stroke-width": 2 }, g); }); });
    lejantYaz(b, K.slice().reverse().map(k => ({ renk: yilRengi(k.yil, sonYil), bicim: "cizgi", ad: String(k.yil) })));
    const fark = bu && gecen && gecen.nokta[bu.nokta.length - 1] > 0 ? (bu.nokta[bu.nokta.length - 1] / gecen.nokta[bu.nokta.length - 1] - 1) * 100 : null;
    $(".aciklama", b).textContent = seciliAd() + " · " + (bu ? tamTarih(V.son) + " itibarıyla " + yaklasik(bu.nokta[bu.nokta.length - 1]) + (fark == null ? "" : " · önceki yılın aynı gününe göre " + yuzdeYaz(fark)) : "");
    t.svg.setAttribute("aria-label", seciliAd() + ": 1 Ocak’tan beri biriken plaka artışı, yıllara göre.");
    const ilkYil = tarih(s.g[0]).y; dipnot(b, K.some(k => k.yil === ilkYil) ? [] : [ilkYil + " yılı bu grafikte yok: kayıtlar " + tamTarih(s.g[0]) + " tarihinde başladığı için 1 Ocak’tan beri toplam hesaplanamaz."]);
    const satirlar = []; for (let m = 2; m <= 13; m++) { const r = [m === 13 ? "Yıl sonu" : "1 " + AYLAR[m - 1]]; let dolu = false;
      K.forEach(k => { const i = gunNo(k.yil, m, 1) - k.a; const v = i < k.nokta.length ? k.nokta[i] : null; if (v != null) dolu = true; r.push(yaklasik(v)); }); if (dolu) satirlar.push(r); }
    if (bu) satirlar.push([gunAy(V.son) + " (son veri)"].concat(K.map(k => yaklasik(bu.nokta.length - 1 < k.nokta.length ? k.nokta[bu.nokta.length - 1] : null))));
    tabloYaz(b, ["1 Ocak’tan şu güne kadar"].concat(K.map(k => String(k.yil))), satirlar);
  }

  // ---------- 4) iller arası kıyas ----------
  let donemler = [];
  function donemListesi() {
    donemler = donemSecenekleri(V.ilk, V.son, durum.kTur);
    const sec = $("#k-donem"); sec.textContent = "";
    donemler.forEach((d, i) => { const o = html("option", "", d.ad + (d.kismi ? " (" + gunAy(V.son) + " itibarıyla, sürüyor)" : "")); o.value = i; sec.appendChild(o); });
    // varsayılan: ay/çeyrekte son TAMAMLANAN dönem; yılda içinde bulunulan yıl (geçen yılın aynı gününe kadar olan kısmıyla kıyaslanır)
    durum.kDonem = durum.kTur === "yil" ? 0 : Math.max(0, donemler.findIndex(d => !d.kismi)); sec.value = durum.kDonem;
  }
  function cizIller() {
    const b = $("#g-iller"), dn = donemler[durum.kDonem], yuzde = durum.olcu === "yuzde";
    let liste = ilKiyas(V.iller, dn.a, dn.b).filter(x => (yuzde ? x.yuzde : x.v) != null).map(x => Object.assign(x, { ad: adlar[x.kod] || x.ad }));
    liste.sort((p, q) => yuzde ? q.yuzde - p.yuzde : q.v - p.v); liste.forEach((x, i) => { x.sira = i + 1; });
    const toplam = liste.length; let goster = durum.goster === "tum" ? liste.slice() : durum.goster === "son" ? liste.slice(-15) : liste.slice(0, 15), ekSatir = -1;
    const secili = liste.find(x => x.kod === durum.il); if (secili && goster.indexOf(secili) < 0) { if (secili.sira < goster[0].sira) { goster.unshift(secili); ekSatir = 0; } else { goster.push(secili); ekSatir = goster.length - 1; } }
    const satirY = 24, kap = $(".cizim", b), dar = (kap.clientWidth || 688) < 420, solGen = dar ? 120 : 138, sagGen = yuzde ? (dar ? 46 : 50) : (dar ? 60 : 70);
    const t = tuval(kap, goster.length * satirY + 8 + 26 + (ekSatir >= 0 ? 8 : 0), { sol: solGen, sag: sagGen, ust: 8, alt: 26 });
    const ry = i => t.y0 + i * satirY + (ekSatir >= 0 && ((ekSatir === 0 && i > 0) || (ekSatir > 0 && i === ekSatir)) ? 8 : 0);
    // Yatay eksen: çubuklar alanın tamamını kullanır (alan = gerçek en büyük değer); çizgiler "güzel" adımlarda, etiketler en az ~44 px arayla (0 her zaman etiketli).
    let x, sifir; const alanGen = t.x1 - t.x0;
    const dikey = (deger, adimPx, sira, metin) => { el("line", { x1: x(deger), x2: x(deger), y1: t.y0, y2: t.y1, stroke: RENK.izgara, "stroke-width": 1 }, t.svg);
      if (sira % Math.max(1, Math.ceil(44 / adimPx)) === 0) yazi(t.svg, x(deger), t.H - 8, metin, { "text-anchor": "middle" }); };
    if (yuzde) { const enAz = Math.min(0, Math.min.apply(null, goster.map(d => d.yuzde))), enCok = Math.max(0, Math.max.apply(null, goster.map(d => d.yuzde))), gen = (enCok - enAz) * 1.04 || 1, o = olcek(gen, dar ? 3 : 5);
      x = v => t.x0 + (v - enAz + (gen - (enCok - enAz)) / 2) / gen * alanGen; sifir = x(0);
      for (let i = Math.ceil(enAz / o.adim); i * o.adim <= enCok; i++) dikey(i * o.adim, o.adim / gen * alanGen, Math.abs(i), i ? yuzdeYaz(i * o.adim) : "%0");
    } else { const maks = Math.max.apply(null, goster.map(d => Math.max(d.v, d.once || 0)).concat([1])), gen = maks * 1.04, o = olcek(maks, dar ? 2 : 4), bc = eksenBicimi(o.ust); x = v => t.x0 + v / gen * alanGen; sifir = t.x0;
      o.cizgiler.forEach((d, i) => { if (d <= maks) dikey(d, o.adim / gen * alanGen, i, bc(d)); }); }
    goster.forEach((d, i) => {
      const yy = ry(i), v = yuzde ? d.yuzde : d.v;
      if (d.kod === durum.il) el("rect", { x: 0, y: yy + 1, width: t.W, height: satirY - 2, rx: 4, fill: RENK.vurgu }, t.svg);
      yazi(t.svg, t.x0 - 8, yy + 16, d.sira + ". " + d.ad, { "text-anchor": "end", "font-size": dar ? 12 : 13, fill: RENK.murekkep, "font-weight": d.kod === durum.il ? 600 : 400 });
      if (yuzde) { if (v >= 0) cubuk(t.svg, sifir, yy + 5, x(v) - sifir, 14, RENK.arti, "sag"); else cubuk(t.svg, x(v), yy + 5, sifir - x(v), 14, RENK.eksi, "sol"); }
      else { cubuk(t.svg, sifir, yy + 5, x(v) - sifir, 14, RENK.arti, "sag"); if (d.once != null) el("rect", { x: x(d.once) - 1, y: yy + 2, width: 2, height: 20, fill: RENK.murekkep }, t.svg); }
      yazi(t.svg, t.W - 2, yy + 16, (yuzde ? yuzdeYaz(v) : yaklasik(v)) + (d.atlama ? "†" : ""), { "text-anchor": "end", fill: RENK.murekkep });
    });
    el("line", { x1: sifir, x2: sifir, y1: t.y0, y2: t.y1, stroke: RENK.taban, "stroke-width": 1 }, t.svg);
    const donemAdi = dn.kismi ? aralik(dn.a, V.son) : dn.ad, onceAdi = dn.kismi ? aralik(yilOnce(dn.a), yilOnce(V.son)) : dn.ad.replace(/\d{4}$/, m => m - 1);
    etkilesim(t, (px, py) => { for (let i = 0; i < goster.length; i++) if (py >= ry(i) && py < ry(i) + satirY) return i; return -1; },
      i => { const d = goster[i]; return { baslik: d.sira + ". " + d.ad + " (" + toplam + " il içinde)", satirlar: [{ renk: yuzde ? null : RENK.arti, deger: yaklasik(d.v), ad: donemAdi }, { renk: yuzde ? null : RENK.murekkep, bicim: "isaret", deger: yaklasik(d.once), ad: onceAdi }],
        notlar: (d.yuzde == null ? [] : ["Değişim: " + yuzdeYaz(d.yuzde)]).concat(d.atlama ? [ATLAMA_NOTU] : []) }; },
      (g, i) => el("rect", { x: 0, y: ry(i), width: t.W, height: satirY, fill: RENK.murekkep, opacity: 0.06 }, g));
    lejantYaz(b, yuzde ? [{ renk: RENK.arti, bicim: "kutu", ad: "Geçen yılın aynı dönemine göre artış" }, { renk: RENK.eksi, bicim: "kutu", ad: "azalış" }]
                       : [{ renk: RENK.arti, bicim: "kutu", ad: donemAdi }, { renk: RENK.murekkep, bicim: "isaret", ad: "Geçen yılın aynı dönemi (" + onceAdi + ")" }]);
    $(".aciklama", b).textContent = (yuzde ? "Geçen yılın aynı dönemine göre değişim" : "Plaka artışı") + " · " + donemAdi + (dn.kismi ? " (dönem sürüyor)" : "") + " · " + toplam + " il";
    t.svg.setAttribute("aria-label", "İllerin " + donemAdi + " dönemindeki plaka artışı sıralaması; ilk sırada " + (liste[0] ? liste[0].ad : "—") + ".");
    const nt = []; if (goster.some(d => d.atlama)) nt.push(ATLAMA_NOTU); if (toplam < V.iller.length) nt.push((V.iller.length - toplam) + " il için bu dönemde karşılaştırılabilir veri yok.");
    if (yuzde) nt.push("Düşük hacimli illerde küçük sayısal farklar büyük yüzde değişim olarak görünebilir."); dipnot(b, nt);
    tabloYaz(b, ["İl", donemAdi, onceAdi, "Değişim"], goster.map(d => [d.sira + ". " + d.ad + (d.atlama ? " †" : ""), yaklasik(d.v), yaklasik(d.once), yuzdeYaz(d.yuzde)]));
  }

  // ---------- sayfa ----------
  function hepsiniCiz() { cizOzet(); cizHafta(); cizDonem(); cizKumulatif(); cizIller(); }
  function ilDegisti() {
    const sec = $("#il"), o = sec.options[sec.selectedIndex], bag = $("#il-sayfa");
    durum.il = +sec.value || 0; anaIlDegisti();
    if (durum.il && o.dataset.slug) { bag.href = "/il/" + o.dataset.slug; bag.textContent = adlar[durum.il] + " plaka tahmini →"; bag.hidden = false; } else bag.hidden = true;
    try { history.replaceState(null, "", durum.il ? "?il=" + String(durum.il).padStart(2, "0") : location.pathname); } catch (x) { /* dosyadan açılınca adres değiştirilemeyebilir */ }
  }
  function baslat(veri) {
    V = hazirla(veri);
    const sec = $("#il"); Array.prototype.forEach.call(sec.options, o => { if (+o.value) adlar[+o.value] = o.dataset.ad || o.textContent; });
    const istek = +(new URLSearchParams(location.search).get("il") || 0); if (istek && adlar[istek]) sec.value = String(istek).padStart(2, "0");
    ilDegisti(); donemListesi();
    $("#veri-tarihi").textContent = "Son veri: " + tamTarih(V.son) + " · " + V.iller.length + " il · ilk kayıt: " + tamTarih(V.ilk);
    sec.addEventListener("change", () => { ilDegisti(); hepsiniCiz(); });
    document.querySelectorAll(".secim").forEach(grup => grup.addEventListener("click", e => {
      const d = e.target.closest("button[data-deger]"); if (!d) return;
      const anahtar = grup.dataset.durum; durum[anahtar] = anahtar === "n" ? +d.dataset.deger : d.dataset.deger;
      grup.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === d ? "true" : "false"));
      if (anahtar === "kTur") donemListesi();
      ({ n: cizHafta, tur: cizDonem, kTur: cizIller, olcu: cizIller, goster: cizIller, bOlcek: cizKumulatif })[anahtar]();
    }));
    $("#b-ekle").addEventListener("change", e => { if (e.target.value !== "") { ekEkle(+e.target.value); cizKumulatif(); } });
    $("#b-ekler").addEventListener("click", e => { const d = e.target.closest("button[data-kod]"); if (!d) return; ekCikar(d.dataset.kod === "ana" ? "ana" : +d.dataset.kod); cizKumulatif(); $("#b-ekle").focus(); });
    $("#k-donem").addEventListener("change", e => { durum.kDonem = +e.target.value; cizIller(); });
    $("#icerik").hidden = false; $("#yukleniyor").hidden = true;
    hepsiniCiz();
    // Çizim genişliği kabın genişliğine göredir: kap daralır/genişlerse (pencere boyutu, ekran döndürme, içerik uzayınca beliren kaydırma çubuğu) yeniden çizilir.
    const kap = $("#g-hafta .cizim"); let genislik = kap.clientWidth, bekle = 0;
    const boyut = () => { if (kap.clientWidth === genislik) return; genislik = kap.clientWidth; clearTimeout(bekle); bekle = setTimeout(hepsiniCiz, 100); };
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(boyut).observe(kap); else window.addEventListener("resize", boyut);
  }
  function yukle() {
    fetch("/data/tahmin_data.json").then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(baslat)
      .catch(x => { console.error("plakatahmini: istatistik verisi yüklenemedi", x); const y = $("#yukleniyor"); y.textContent = "Veri yüklenemedi. Sayfayı yenileyip tekrar deneyin."; y.className = "uyari"; });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", yukle); else yukle();
  return Object.assign({ durum, baslat }, saf);
})();
if (typeof module !== "undefined" && module.exports) module.exports = PlakaIstatistik;
