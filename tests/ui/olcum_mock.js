// GoatCounter MOCK ile analitik olay akışı (Node vm + sahte DOM; ağ yok, gerçek sayaca istek yapılmaz).
// olcum.js "üretim" koşulunda (hostname plakatahmini.com) çalıştırılır; count.js yerine sahte goatcounter.count çağrıları toplanır.
// İl sayfası (il-arac.js gönderim işleyicisi) ve ana sayfa (ana-sayfa.js il araması + hedef plaka dinleyicileri) gerçek kodlarıyla sürülür.
// Ana sayfada index.html'deki calcTarget bu ortamda yoktur: onun sonucu (sonuç kutusu gizli/görünür) adımda verilir; calcTarget ile eşlik tarayıcı testindedir.
// Kullanım: node olcum_mock.js <senaryolar.json>
//   senaryo: {sayfa: "il", il: "<slug>", adimlar: [{tur: "hedef", deger, atla?, bozuk?}]} | {sayfa: "ana", adimlar: [{tur: "ara", deger} | {tur: "hedef", deger, gizli, enter?}]}
//   çıktı: her senaryo için her adımın {cagrilar: [count() argümanları], gidilen: [location.assign adresleri]}
const fs = require("fs"), path = require("path"), vm = require("vm");
const kok = path.join(__dirname, "..", "..");
const oku = f => fs.readFileSync(path.join(kok, f), "utf8");

function el(ek) {
  return Object.assign({ dinleyici: {}, style: {}, attrs: {}, cocuk: [], value: "", textContent: "", hidden: false,
    addEventListener(t, f) { (this.dinleyici[t] = this.dinleyici[t] || []).push(f); }, setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    appendChild(c) { this.cocuk.push(c); return c; }, focus() {}, querySelector() { return null; }, querySelectorAll() { return []; } }, ek || {});
}
const tetikle = (e, tur, olay) => (e.dinleyici[tur] || []).forEach(f => f(olay));

function ortam(idler, secenekler) {
  const eklenen = [], cagrilar = [], gidilen = [];
  const document = { readyState: "complete", head: { appendChild: x => eklenen.push(x) }, createElement: () => el(),
    getElementById: id => idler[id] || null, querySelector: () => null, querySelectorAll: s => (s === "#il-liste option" ? secenekler : []), addEventListener() {} };
  const ctx = { Math, Date, JSON, console: { error() {}, log() {} }, document, setTimeout,
    location: { hostname: "plakatahmini.com", assign: u => gidilen.push(String(u)) }, navigator: { webdriver: false }, localStorage: { getItem: () => null } };
  vm.createContext(ctx);
  vm.runInContext(oku("assets/olcum.js"), ctx);
  if (eklenen.length !== 1 || eklenen[0].src !== "https://gc.zgo.at/count.js") throw new Error("olcum.js üretim koşulunda count.js eklemedi");
  ctx.goatcounter = { count: v => cagrilar.push(JSON.parse(JSON.stringify(v))) };          // MOCK: count.js yüklenmiş gibi; gerçek count.js hiç indirilmez
  eklenen[0].onload();
  return { ctx, cagrilar, gidilen };
}

function ilSayfasi(sn) {
  const h = oku(path.join("il", sn.il + ".html")), veri = h.match(/<script type="application\/json" id="il-veri">(.*?)<\/script>/s)[1];
  const idler = { "il-veri": el({ textContent: veri }), "hedef-form": el(), "sonuc": el(), "hedef": el(), "atla": el() };
  const o = ortam(idler, []);
  for (const f of ["assets/takvim.js", "assets/tarihsel-referanslar.js", "assets/tahmin-motoru.js", "assets/il-arac.js"]) vm.runInContext(oku(f), o.ctx);
  const asil = o.ctx.reachDate;
  return sn.adimlar.map(a => {
    const once = o.cagrilar.length; idler.hedef.value = a.deger; idler.atla.value = a.atla || "";
    if (a.bozuk) o.ctx.reachDate = () => { throw new Error("test: beklenmeyen hesaplama hatası"); };
    try { tetikle(idler["hedef-form"], "submit", { preventDefault() {} }); } finally { o.ctx.reachDate = asil; }
    return { cagrilar: o.cagrilar.slice(once), gidilen: [] };
  });
}

function anaSayfa(sn) {
  const ana = oku("index.html");
  const secenekler = [...ana.matchAll(/<option value="[^"]+" data-ad="([^"]+)" data-kod="(\d+)" data-slug="([a-z]+)">/g)].map(m => el({ attrs: { "data-ad": m[1], "data-kod": m[2], "data-slug": m[3] } }));
  const idler = { "il-form": el(), "il-ara": el(), "il-hata": el(), "btn-target": el(), "target": el(), "target-res": el({ style: { display: "none" } }) };
  const o = ortam(idler, secenekler);
  for (const f of ["assets/takvim.js", "assets/tahmin-motoru.js"]) vm.runInContext(oku(f), o.ctx);
  o.ctx.DATA = { iller: [] };                                  // ana-sayfa.js yalnızca DATA tanımlıysa başlar (kart/tarih bölümleri bu sahte DOM'da kendi try'larında atlanır)
  vm.runInContext(oku("assets/ana-sayfa.js"), o.ctx);
  return sn.adimlar.map(a => {
    const once = o.cagrilar.length, gOnce = o.gidilen.length;
    if (a.tur === "ara") { idler["il-ara"].value = a.deger; tetikle(idler["il-form"], "submit", { preventDefault() {} }); }
    else {
      idler.target.value = a.deger; idler["target-res"].style.display = a.gizli ? "none" : "flex";          // calcTarget'ın bıraktığı durum
      if (a.enter) tetikle(idler.target, "keydown", { key: "Enter" }); else tetikle(idler["btn-target"], "click", {});
    }
    return { cagrilar: o.cagrilar.slice(once), gidilen: o.gidilen.slice(gOnce) };
  });
}

const senaryolar = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
console.log(JSON.stringify(senaryolar.map(sn => (sn.sayfa === "il" ? ilSayfasi(sn) : anaSayfa(sn)))));
