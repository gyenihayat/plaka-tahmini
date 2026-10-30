// Kullanım: node il_canli_cikti.js <il.html> <an_ms[,an_ms...]>
// Her UTC anı (ms) için il sayfasının canlı davranışını çalıştırır: satır içi güncellik denetimi + il-arac.js (ortak motor) guncelTahmin().
// Ana sayfayla karşılaştırma için aynı anda motorun estimateAt(trReferansGun(an).gun) değeri de döner (referans gün = Türkiye tarihinin en yakın önceki iş günü). Tarayıcı saat dilimi TZ ortam değişkeniyle seçilir.
const fs = require("fs"), path = require("path"), vm = require("vm");
const kok = path.join(__dirname, "..", ".."), sayfa = fs.readFileSync(process.argv[2], "utf8"), anlar = process.argv[3].split(",").map(Number);
const veri = JSON.parse(sayfa.match(/<script type="application\/json" id="il-veri">(.*?)<\/script>/s)[1]);
const satirIci = sayfa.match(/<script>(\(function\(\)\{[\s\S]*?\}\)\(\);)<\/script>/)[1];
const takvim = fs.readFileSync(path.join(kok, "assets", "takvim.js"), "utf8"), motor = fs.readFileSync(path.join(kok, "assets", "tahmin-motoru.js"), "utf8"), arac = fs.readFileSync(path.join(kok, "assets", "il-arac.js"), "utf8");
const canli = [...sayfa.matchAll(/data-live="(\w+)">([^<]*)</g)].map(m => ({ k: m[1], textContent: m[2], getAttribute() { return this.k; } }));
const bas = sayfa.match(/data-baslangic="([^"]+)"/)[1], tgM = sayfa.match(/id="tahmin-grup" data-gozlenen="(\w)"([^>]*)>/);
const sonuc = anlar.map(an => {
  const els = canli.map(e => ({ ...e, getAttribute() { return this.k; } }));
  const by = { hidden: /id="bayat"[^>]*\bhidden\b/.test(sayfa) }, gu = { hidden: true, querySelector: () => span }, span = { textContent: "" };
  const tg = tgM ? { hidden: /\bhidden\b/.test(tgM[2]), getAttribute: () => tgM[1] } : null;
  const doc = { readyState: "complete", querySelector: s => s === "[data-baslangic]" ? { getAttribute: () => bas } : null,
    querySelectorAll: s => s === "[data-live]" ? els : [], getElementById: id => id === "bayat" ? by : id === "guncellik" ? gu : id === "tahmin-grup" ? tg : null, addEventListener() {} };
  const errs = []; class FD extends Date { static now() { return an; } }
  const ctx = { Math, Date: FD, console: { error: (...a) => errs.push(String(a[0])) }, document: doc }; vm.createContext(ctx);
  vm.runInContext(satirIci, ctx);                                   // satır içi güncellik denetimi (motor yüklenmeden de çalışır)
  vm.runInContext(takvim, ctx); vm.runInContext(motor, ctx); vm.runInContext(arac, ctx);           // il-arac.js yüklenince baslat() çalışır; il-veri yok -> araç kurulmaz
  ctx.__s = veri; ctx.__an = an;
  let v = null, hata = null; try { v = vm.runInContext("PlakaIlArac.guncelTahmin(document, __s, __an)", ctx); } catch (e) { hata = String(e); }
  const ana = vm.runInContext("(function(){const r=trReferansGun(__an), n=estimateAt(__s,r.gun).n, iv=invN(n); return {gun:r.gun, iso:r.iso, tr:trBugunIso(__an), kapsamDisi:r.kapsamDisi, n:n, seri:String(__s.kod).padStart(2,'0')+' '+iv.let, plaka:String(__s.kod).padStart(2,'0')+' '+iv.let+' '+String(iv.num).padStart(3,'0')};})()", ctx);
  const r = {}; els.forEach(e => r[e.k] = e.textContent);
  return { an, canli: r, v, hata, ana, bayat: !by.hidden, tahminGrup: tg ? !tg.hidden : null, uyari: gu.hidden ? null : span.textContent, hatalar: errs };
});
console.log(JSON.stringify(sonuc));
