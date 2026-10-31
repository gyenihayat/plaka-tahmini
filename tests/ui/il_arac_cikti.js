// Kullanım: node il_arac_cikti.js <senaryolar.json> -> her senaryo için il sayfasındaki araç mantığının (PlakaIlArac.hesapla) sonucunu yazdırır.
// Senaryo: {sayfa: "il/konya.html" (mutlak yol), hedef, excl}. Motor ve araç, sayfadaki gibi aynı bağlamda (tahmin-motoru.js sonra il-arac.js) yüklenir.
const fs = require("fs"), path = require("path"), vm = require("vm");
const kok = path.join(__dirname, "..", "..");
const senaryolar = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const ctx = { Math, Date, console }; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(kok, "assets", "takvim.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(path.join(kok, "assets", "tarihsel-referanslar.js"), "utf8"), ctx);      // yalnızca referansı olan il (Ankara) etkilenir; Ankara sayfası bu betiği yükler
vm.runInContext(fs.readFileSync(path.join(kok, "assets", "tahmin-motoru.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(path.join(kok, "assets", "il-arac.js"), "utf8"), ctx);
const bugun = vm.runInContext("trReferansGun().gun", ctx), onbellek = {};
const sonuc = senaryolar.map(sn => {
  const veri = onbellek[sn.sayfa] || (onbellek[sn.sayfa] = JSON.parse(fs.readFileSync(sn.sayfa, "utf8").match(/<script type="application\/json" id="il-veri">(.*?)<\/script>/s)[1]));
  ctx.__s = veri; ctx.__g = sn.hedef; ctx.__e = sn.excl || ""; ctx.__b = bugun;
  const r = vm.runInContext("PlakaIlArac.hesapla(__s, __g, __e, __b)", ctx);
  return JSON.parse(JSON.stringify(r));
});
console.log(JSON.stringify(sonuc));
