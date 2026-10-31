// Plaka tahmin motoru: index.html ve il sayfalarının ORTAK hesaplama kodu (tek mantık). forecast.py ile aynı matematik
// (tests/test_motor_golden.py ve tests/golden/ ile korunur). Klasik script: üst düzey const/let/function bildirimleri sayfadaki
// diğer scriptlerle paylaşılır. DOM ve sayfa verisine bağımlı değildir.
const A1="ABCDEFGHJKLMNPRSTUVYZ", A2="ABCDEFGHIJKLMNOPRSTUVYZ", A3="ABCDEFGHJKLMNPRSTUVYZ";
const DAY = 86400000, EPOCH = Date.UTC(2024,0,1);
const fmt = n => n.toLocaleString("tr-TR");
const dstr = d => { const x = new Date(EPOCH + d*DAY); return String(x.getUTCDate()).padStart(2,"0")+"."+String(x.getUTCMonth()+1).padStart(2,"0")+"."+x.getUTCFullYear(); };
const toDay = iso => Math.round((Date.UTC(+iso.slice(0,4), +iso.slice(5,7)-1, +iso.slice(8,10)) - EPOCH)/DAY);
const invN = n => { n = Math.round(n); let num = ((n % 1000)+1000)%1000; let g = Math.floor(n/1000); const i3 = g % A3.length; g = Math.floor(g/A3.length); const i2 = g % A2.length; const i1 = Math.floor(g/A2.length); if (i1 >= A1.length || i1 < 0) return null; return {let: A1[i1]+A2[i2]+A3[i3], num: Math.min(999, Math.max(1, num))}; };
const toN = (let3, num) => { const i1=A1.indexOf(let3[0]), i2=A2.indexOf(let3[1]), i3=A3.indexOf(let3[2]); if (i1<0||i2<0||i3<0) return null; return ((i1*A2.length+i2)*A3.length+i3)*1000 + (num||1); };
let EXCL = [];   // dışlanan [başlangıç, bitiş) nominal aralıkları, sıralı ve birleşik
function parseExcl(txt){
  const items = [], bad = [];
  const push = (a,b,lab)=>{ if (b>a) items.push([a,b,lab]); };
  txt.toUpperCase().split(/[,;\s]+/).filter(Boolean).forEach(tok=>{
    const t = tok.replace(/[^A-Z-]/g,"");
    if (!t) return;
    const range = t.match(/^([A-Z]{3})-([A-Z]{3})$/);
    if (range){
      const a = toN(range[1],1), b = toN(range[2],1);
      if (a==null || b==null || b < a){ bad.push(tok); return; }
      push(a-1, b-1+1000, range[1]+"–"+range[2]); return;
    }
    const p = t.replace(/X+$/,"");   // sondaki X'ler joker (X plakalarda zaten yok)
    if (!/^[A-Z]{1,3}$/.test(p) || /X/.test(p)){ bad.push(tok); return; }
    if (p[0] && !A1.includes(p[0])){ bad.push(tok); return; }
    if (p[1] && !A2.includes(p[1])){ bad.push(tok); return; }
    if (p.length===3 && !A3.includes(p[2])){ bad.push(tok); return; }
    const first = p + "A".repeat(3-p.length);
    const last  = p[0] + (p[1]||"Z") + (p.length===3 ? p[2] : "Z");
    push(toN(first,1)-1, toN(last,1)-1+1000, p.length===1 ? p+" grubu" : (p.length===2 ? p+"A–"+p+"Z" : p));
  });
  items.sort((x,y)=>x[0]-y[0]);
  const merged = [];
  items.forEach(iv=>{ const m = merged[merged.length-1]; if (m && iv[0] <= m[1]) { m[1] = Math.max(m[1], iv[1]); m[2] += ", "+iv[2]; } else merged.push([...iv]); });
  return {intervals: merged, bad};
}
function skipAdvance(cur, adv, intervals){
  // cur'dan başlayıp adv kadar "verilebilir" nominal ilerledikten sonraki konum (dışlananların üstünden atlar)
  let pos = cur, rem = adv;
  for (const [a,b] of intervals){
    if (b <= pos) continue;
    if (pos >= a) { pos = b; continue; }        // dışlananın içindeysek sonuna atla
    const gap = a - pos;
    if (rem <= gap) { return pos + rem; }
    rem -= gap; pos = b;
  }
  return pos + rem;
}
function exclOverlap(a, b, intervals){
  let s = 0;
  for (const [x,y] of intervals) s += Math.max(0, Math.min(b,y) - Math.max(a,x));
  return s;
}
function inExcl(n, intervals){ for (const [a,b,l] of intervals) if (n >= a && n < b) return l; return null; }
function fit(s, upto){
  // robust rate: median of interval rates (dN/dt) over 365 days; one-off block skips (e.g. Kutahya ADZ->AHZ) are ignored by the median.
  let win = 365, w;
  const o = s.obs;
  do { w = o.filter(x=>x[0] <= upto && x[0] > upto - win); win *= 2; } while (w.length < 10 && win < 8000);
  const rates = [], dts = [];
  for (let i=1;i<w.length;i++){ const dt = w[i][0]-w[i-1][0]; if (dt>0){ rates.push((w[i][1]-w[i-1][1])/dt); dts.push(dt); } }
  const med = a => { const b=[...a].sort((x,y)=>x-y); const m=b.length>>1; return b.length%2 ? b[m] : (b[m-1]+b[m])/2; };
  const slope = Math.max(rates.length ? med(rates) : 0, 0.01);
  const mdt = dts.length ? med(dts) : 7;
  const mad = rates.length ? 1.4826*med(rates.map(r=>Math.abs(r-slope))) : 0;
  const rstd = mad * mdt;   // typical per-interval deviation in nominal units
  const skipped = rates.filter(r => r > 6*slope && r*mdt > 5000).length;  // detected block skips in window
  return {slope, rstd, n: w.length, win: win/2, last: o[o.length-1], skipped};
}
function cleanCum(s){
  if (s._c) return s._c;
  const o = s.obs, med = a => { const b=[...a].sort((x,y)=>x-y); const m=b.length>>1; return b.length%2 ? b[m] : (b[m-1]+b[m])/2; };
  const c = [[o[0][0], o[0][1]]];
  for (let i=1;i<o.length;i++){
    const dt = o[i][0]-o[i-1][0]; if (dt<=0) continue;
    let rr = (o[i][1]-o[i-1][1])/dt;
    const loc = [];
    for (let j=Math.max(1,i-10); j<Math.min(o.length,i+11); j++){ const d=o[j][0]-o[j-1][0]; if (d>0) loc.push((o[j][1]-o[j-1][1])/d); }
    const lm = med(loc);
    if (rr > 6*Math.max(lm,0.5) && rr*dt > 5000) rr = lm;
    c.push([o[i][0], c[c.length-1][1] + Math.max(rr,0)*dt]);
  }
  return s._c = c;
}
function atC(c, day){
  if (day <= c[0][0]) return c[0][1];
  if (day >= c[c.length-1][0]) return c[c.length-1][1];
  let lo = 0, hi = c.length-1;
  while (hi-lo > 1){ const m=(lo+hi)>>1; if (c[m][0] <= day) lo=m; else hi=m; }
  const dx = c[hi][0]-c[lo][0];
  return c[lo][1] + (dx ? (c[hi][1]-c[lo][1])*(day-c[lo][0])/dx : 0);
}
// Ileri ilerleme: son 365 gun medyan hizi ile gecen yilin ayni takvim araliginin ilerlemesinin ortalamasi.
// Geriye donuk test (hata gun): 30g %20, 90g %25, 180g %30 daha iyi (yalniz medyan180'e gore).
function advAt(s, f, h){
  const c = cleanCum(s), T = f.last[0];
  const Y = atC(c,T) - atC(c,T-365), k = Math.floor(h/365), rem = h - 365*k;
  const seas = k*Y + atC(c, T-365+rem) - atC(c, T-365);
  return 0.5*f.slope*h + 0.5*seas;
}
function errDays(s, f, horizon){
  const base = Math.max(s.bterr || 0, f.rstd/f.slope || 0, 2);
  return Math.max(2, Math.round(base * Math.max(1, Math.abs(horizon)/60)));
}
function estimateAt(s, day){
  const o = s.obs;
  if (day < o[0][0]) return estimateBack(s, day);      // ilk kayıtlı gözlemden ÖNCE: geriye dönük tahmin (backEstimate ile aynı model; eskiden ilk gözleme sabitleniyordu)
  if (day <= o[o.length-1][0]){  // historical: interpolate observations
    let lo = o[0], hi = o[o.length-1];
    if (day <= o[0][0]) return {n: o[0][1], real: true};
    for (let i=1;i<o.length;i++){ if (o[i][0] >= day){ hi = o[i]; lo = o[i-1]; break; } }
    const t = hi[0]===lo[0] ? 0 : (day-lo[0])/(hi[0]-lo[0]);
    return {n: lo[1] + t*(hi[1]-lo[1]), real: true};
  }
  const f = fit(s, o[o.length-1][0]);
  const adv = advAt(s, f, day - o[o.length-1][0]);
  return {n: skipAdvance(o[o.length-1][1], adv, EXCL), real: false, f, err: errDays(s, f, day - o[o.length-1][0])};
}
// Kayıt öncesi plaka: ilk gözlemin ilk 365 gündeki medyan hızı ile ertesi yılın aynı takvim aralığının ilerlemesinin karışımı, geriye doğru.
function backAdv(s, c, rate0, h){
  const F = s.obs[0][0], Y = atC(c,F+365) - atC(c,F), k = Math.floor(h/365), rem = h - 365*k;
  const seas = k*Y + atC(c,F+365) - atC(c,F+365-rem);
  return 0.5*rate0*h + 0.5*seas;
}
// Geriye dönük modelin hızı: ilk gözlemden sonraki ilk 365 gündeki ardışık aralık hızlarının medyanı (sıra/gün). backEstimate (plaka -> tarih) ve estimateBack (tarih -> plaka) AYNI hızı kullanır.
function backRate0(s){
  if (s._r0 !== undefined) return s._r0;
  const o = s.obs, F = o[0][0], rates = []; for (let i=1;i<o.length && o[i][0] <= F+365;i++){ const dt=o[i][0]-o[i-1][0]; if (dt>0) rates.push((o[i][1]-o[i-1][1])/dt); }
  const med = a => { const b=[...a].sort((x,y)=>x-y); const m=b.length>>1; return b.length%2 ? b[m] : (b[m-1]+b[m])/2; };
  return s._r0 = Math.max(rates.length ? med(rates) : 0, 0.01);
}
// ---- Tarihsel referansla KALİBRASYON (yalnızca assets/tarihsel-referanslar.js'te kaydı olan il; şimdilik Ankara) ---------------------------------------------------------------------
// Referans: gözlem verisinden AYRI, kullanıcı bildirimli, yaklaşık tarihli tek nokta (resmî değil). İlk gözlem F ile referans R arasında model eğrisi g(h) = backAdv, referansı tam yakalayacak şekilde ölçeklenir:
//   A(h) = g(h) · (1 − (1 − κ)·h/H),  κ = (n0 − nR)/g(H),  H = F − R.   A(0) = 0 (ilk gözlemde süreklilik: sıçrama yok), A(H) = n0 − nR (referans noktasından geçer), mevsimsel şekil g'den gelir.
//   Düzeltme ilk gözlemden uzaklaştıkça artar: ilk gözlem yakınında model zaten doğrudur (Ankara hold-out'ta ±8 gün); tek katsayılı ölçek bunu bozardı.
// R'den önce: referans sonrası ilk yılın ortalama hızıyla (rR) doğrusal geriye gidilir (süreklilik korunur). Monotonluk bozulursa (olağan dışı veri) tek katsayılı ölçeğe düşülür.
function tarihselReferans(s){ const r = (typeof PlakaReferanslar !== "undefined") ? PlakaReferanslar[s.kod] : null; return r && r.length ? r[0] : null; }
function kalibrasyon(s){
  if (s._kal !== undefined) return s._kal;
  s._kal = null; const r = tarihselReferans(s); if (!r) return null;
  const m = /^(\d\d) ([A-Z]{3}) (\d{3})$/.exec(r.plaka), o = s.obs, F = o[0][0], n0 = o[0][1]; if (!m || +m[1] !== s.kod) return null;
  const R = toDay(r.tarih), nR = toN(m[2], +m[3]), H = F - R, c = cleanCum(s), rate0 = backRate0(s), g = h => backAdv(s, c, rate0, h);
  if (nR == null || !(H > 0) || !(nR < n0)) return null;
  const gH = g(H), kappa = (n0 - nR) / gH; if (!(gH > 0) || !(kappa > 0) || !isFinite(kappa)) return null;
  let A = h => g(h) * (1 - (1 - kappa) * h / H), mono = true; for (let h = 1; h <= H; h++) if (!(A(h) > A(h - 1))) { mono = false; break; }
  if (!mono) A = h => g(h) * kappa;
  const rR = H > 365 ? (A(H) - A(H - 365)) / 365 : A(H) / H;
  return s._kal = {r, R, nR, H, kappa, mono, A, rR, taban: 2 * (r.tarihBelirsizligiGun || 30)};
}
// Geriye dönük göreli belirsizlik oranı: ±%25 (≤ 1 yıl), 1 yıldan sonra yılda +%5, en çok %50 (tarih aracı ve kalibre hata aynı kuralı kullanır).
function geriOran(d){ return Math.min(0.5, 0.25 + 0.05 * Math.max(0, d - 365) / 365); }
// Kalibre belirsizlik (gün): en yakın çapadan uzaklığa göre. İlk gözlem kesin (min ±10); referans yaklaşık ve TEK nokta olduğundan referans yakınında bile en az 2×tarih belirsizliği (±60) + uzaklık payı: aşırı kesinlik üretilmez.
function kalibreHata(k, h){
  const eR = d => k.taban + Math.round(geriOran(d) * d);
  if (h > k.H) return eR(h - k.H);
  return Math.min(Math.max(10, Math.round(geriOran(h) * h)), eR(k.H - h));
}
function backAdvKal(s, h){
  const k = kalibrasyon(s); if (!k) return backAdv(s, cleanCum(s), backRate0(s), h);
  return h <= k.H ? k.A(h) : k.A(k.H) + k.rR * (h - k.H);
}
// Tarih -> plaka (ilk gözlemden önce): backEstimate'in tam tersi; n = ilk gözlem - ilerleme(h). h büyüdükçe n kesin azalır. Sonuç yuvarlanmamış ham sıradır (invN yuvarlar; n < 1 ise geçerli plaka yoktur).
function estimateBack(s, day){
  const o = s.obs, h = o[0][0] - day, k = kalibrasyon(s), r = {n: o[0][1] - backAdvKal(s, h), real: false, back: true, h};
  if (k) { r.kalibre = h <= k.H ? "ara" : "once"; r.err = kalibreHata(k, h); r.ref = k.r; }
  return r;
}
// Geriye dönük TARİH tahmininin MODEL alt tarih sınırı (yalnızca bu araçta uygulanan bir kural): 1 Şubat 2018'den önceki tarihler için tahmin üretilmez. Bu tarih, üç harf–üç rakam plakaların hiçbir ilde fiilen dağıtılmaya başladığı gün olarak SUNULMAZ ve hiçbir ilin gerçek başlangıç serisi/tarihi anlamına gelmez.
const GERI_SINIR_ISO = "2018-02-01", GERI_SINIR_GUN = toDay(GERI_SINIR_ISO);
// Hedef plaka aracı: modelin geriye hesapladığı tarih bu model sınırından önceye düşüyorsa tarih verilmez (tarih aracıyla aynı kural).
const GERI_SINIR_HEDEF_MESAJI = "Bu plaka için tarih tahmini üretilemiyor: modelin hesapladığı tarih, bu aracın tahmin ürettiği alt tarih sınırından (1 Şubat 2018) önceye düşüyor. Bu, modelin uyguladığı bir sınırdır; plakanın o tarihte verilmediği anlamına gelmez.";
function backEstimate(s, targetN){
  const o = s.obs, F = o[0][0], dist = o[0][1] - targetN, c = cleanCum(s);
  const rate0 = backRate0(s);
  let hi = Math.max(1, dist/rate0); while (backAdvKal(s,hi) < dist && hi < 80000) hi *= 2;
  let lo = 0; for (let i=0;i<60;i++){ const m=(lo+hi)/2; if (backAdvKal(s,m) < dist) lo=m; else hi=m; }
  const h = Math.round(hi), k = kalibrasyon(s);
  const r = {passed:true, back:true, day: F - h, err: Math.max(7, Math.round(0.15*h)), back_h: h, first: o[0]};
  if (k) { r.kalibre = h <= k.H ? "ara" : "once"; r.err = kalibreHata(k, h); r.ref = k.r; }      // referanslı il: tarih aracıyla AYNI kalibre eğri ve belirsizlik
  return r;
}
function reachDate(s, targetN){
  const o = s.obs; const last = o[o.length-1];
  if (targetN <= last[1]){  // passed: find crossing in history
    for (let i=0;i<o.length;i++){ if (o[i][1] >= targetN){ if (i===0) return targetN === o[0][1] ? {passed:true, day:o[0][0]} : backEstimate(s, targetN); const lo=o[i-1], hi=o[i]; const t=(targetN-lo[1])/(hi[1]-lo[1]); return {passed:true, day: Math.round(lo[0]+t*(hi[0]-lo[0]))}; } }
  }
  const exLab = inExcl(targetN, EXCL);
  if (exLab) return {excluded: exLab};
  const f = fit(s, last[0]);
  if (f.slope <= 0) return {never:true};
  const dist = (targetN - last[1]) - exclOverlap(last[1], targetN, EXCL);
  let hi = Math.max(1, dist/f.slope);
  while (advAt(s, f, hi) < dist && hi < 80000) hi *= 2;
  if (advAt(s, f, hi) < dist) return {never:true};
  let lo = 0;
  for (let i=0;i<60;i++){ const m=(lo+hi)/2; if (advAt(s, f, m) < dist) lo=m; else hi=m; }
  const d = last[0] + hi;
  return {passed:false, day: Math.round(d), err: errDays(s, f, d - last[0]), f, atlanan: Math.round(exclOverlap(last[1], targetN, EXCL)/1000)};
}

// Türkiye yerel takvim günü (UTC+3, yaz saati yok; tarayıcı saat diliminden bağımsız).
const TR_KAYMA_MS = 3*3600*1000;
const trBugunGun = (now = Date.now()) => Math.floor((now + TR_KAYMA_MS - EPOCH)/DAY);
const trBugunIso = (now = Date.now()) => new Date(now + TR_KAYMA_MS).toISOString().slice(0,10);
// "Güncel tahmin"in referans günü: Türkiye yerel tarihinin en yakın önceki İŞ GÜNÜ. Cumartesi, Pazar ve tam gün resmî tatilde değer değişmez
// (arife/yarım günler iş günü sayılır). Takvim: assets/takvim.js (is_gunu.py'den üretilen PlakaTakvim); tahmin hesabının kendisi değişmez, yalnızca "hangi gün" seçilir.
// Takvim yüklenemezse ya da yıl kapsam dışındaysa yalnızca hafta sonu kuralı uygulanır ve kapsamDisi=true döner (sessizce doğru kabul edilmez).
function trReferansGun(now = Date.now()){
  let gun = trBugunGun(now);
  const T = (typeof PlakaTakvim !== "undefined") ? PlakaTakvim : null, yil = new Date(EPOCH + gun*DAY).getUTCFullYear();
  const kapsamDisi = !T || yil < T.ilkYil || yil > T.sonYil, tatil = T ? T.tatiller : [];
  const isGunu = g => { const d = new Date(EPOCH + g*DAY), w = d.getUTCDay(); return w !== 0 && w !== 6 && tatil.indexOf(d.toISOString().slice(0,10)) < 0; };
  while (!isGunu(gun)) gun--;
  return {gun, iso: new Date(EPOCH + gun*DAY).toISOString().slice(0,10), kapsamDisi};
}

// Türkçe uzun tarih ("30 Ekim 2026"): gün numarası (EPOCH'tan beri) -> metin. Ana sayfa kartları, il sayfası ve araç ortak kullanır.
const AYLAR_TR = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
const trTarihGun = day => { const x = new Date(EPOCH + day*DAY); return x.getUTCDate() + " " + AYLAR_TR[x.getUTCMonth()] + " " + x.getUTCFullYear(); };
// Bir ilin verilen takvim gününe ait tahmini serisi (kullanıcının "atlanacak seriler" seçimi etkilemez: EXCL geçici olarak boşaltılır).
// Ana sayfa kartları ve il sayfasındaki büyük tahmin AYNI fonksiyonu kullanır; null: alfabe dışı.
function guncelSeriBilgisi(s, gun){
  const eski = EXCL; EXCL = [];
  try {
    const n = estimateAt(s, gun).n, iv = invN(n); if (!iv) return null;
    const kod = String(s.kod).padStart(2,"0");
    return {n, seri: kod + " " + iv.let, plaka: kod + " " + iv.let + " " + String(iv.num).padStart(3,"0"), grup: iv.let[0], tarih: trTarihGun(gun)};
  } finally { EXCL = eski; }
}
