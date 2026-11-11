// Hedef plaka hata kategorileri: il sayfası aracının gerçek sonucu (PlakaIlArac.hesapla) ile olcum.js sınıflandırmasının (hedefHataKategorisi) eşliği.
// Node vm; ağ yok (olcum.js üretim alan adında değil: hiçbir şey göndermez). Kullanım: node hata_kategori_cikti.js <spec.json>
//   spec: {iller: [slug], etiketli: [[slug, giris, atla]], fuzz: N, tohum}
//   çıktı: {etiketli: [{tip, mesaj, kat}], eslik: {deneme, uyumsuz, sayac}, fuzz: {kategoriler, olaylar}}
const fs = require("fs"), path = require("path"), vm = require("vm");
const kok = path.join(__dirname, "..", "..");
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const ctx = { Math, Date, console }; vm.createContext(ctx);
for (const f of ["takvim.js", "tarihsel-referanslar.js", "tahmin-motoru.js", "il-arac.js", "olcum.js"]) vm.runInContext(fs.readFileSync(path.join(kok, "assets", f), "utf8"), ctx);
const bugun = vm.runInContext("trReferansGun().gun", ctx), veri = {};
const s = sl => veri[sl] || (veri[sl] = JSON.parse(fs.readFileSync(path.join(kok, "il", sl + ".html"), "utf8").match(/<script type="application\/json" id="il-veri">(.*?)<\/script>/s)[1]));
// il sayfasındaki işleyiciyle AYNI bağlam (il-arac.js baslat): sayfa kodu, ortak motorun toN'u, atlanacak seriler ayrıştırması
function calistir(sl, giris, atla) {
  ctx.__s = s(sl); ctx.__g = giris; ctx.__e = atla; ctx.__b = bugun;
  const o = vm.runInContext("PlakaIlArac.hesapla(__s, __g, __e, __b)", ctx);
  const kat = vm.runInContext("PlakaOlcum.hedefHataKategorisi(__g, {sayfaKodu: __s.kod, harfGecerli: (l, n) => toN(l, n) != null, atlaHatali: parseExcl(String(__e || '')).bad.length > 0})", ctx);
  return { tip: o.tip, mesaj: o.mesaj || "", kat };
}
const BICIM = ["bos", "karakter", "tek-harf", "iki-harf", "format"];
function beklenen(o) {                     // ekranda gösterilen sonuç -> izin verilen kategori(ler)
  if (o.tip === "baska_il") return ["baska-il"];
  if (o.tip !== "hata") return ["hesaplama"];                       // hata değil: sınıflandırıcı hiçbir doğrulama hatası bulmamalı
  if (o.mesaj.startsWith("Seri okunamadı")) return BICIM;
  if (o.mesaj.startsWith("Geçersiz il kodu")) return ["il-kodu"];
  if (o.mesaj.includes("plakalarda kullanılmıyor")) return ["karakter"];
  if (o.mesaj.startsWith("Atlanacak seriler okunamadı")) return ["atla"];
  return ["?"];
}
const etiketli = spec.etiketli.map(([sl, g, a]) => calistir(sl, g, a));
// Yapısal derlem: il kodu x harf kısmı x sıra x ayraç x atlanacak seriler
const kodlar = ["", "0", "6", "06", "34", "42", "58", "81", "82", "99"], harfler = ["", "B", "BZ", "BZZ", "GGS", "AID", "RMP", "IAA", "QAA", "AAO", "ŞAA", "GİS", "abc", "Ç", "TR", "konya", "AB CD", "ı"];
const siralar = ["", "1", "12", "999", "1234", "0761"], ayraclar = [" ", "-", ""], atlalar = ["", "SXX", "xyz!!", "BAA-BCZ"];
let deneme = 0; const uyumsuz = [], sayac = {};
for (const sl of spec.iller) for (const k of kodlar) for (const h of harfler) for (const n of siralar) for (const a of ayraclar) for (const ex of atlalar) {
  const g = [k, h, n].filter(Boolean).join(a); const o = calistir(sl, g, ex); deneme++;
  sayac[o.kat] = (sayac[o.kat] || 0) + 1;
  if (!beklenen(o).includes(o.kat)) uyumsuz.push({ sl, g, ex, o });
}
// Rastgele girdiler (tohumlu): kategori her zaman kapalı listeden, olay adı sabit tablodan
let t = spec.tohum >>> 0; const rnd = () => { t += 0x6D2B79F5; let x = Math.imul(t ^ (t >>> 15), 1 | t); x ^= x + Math.imul(x ^ (x >>> 7), 61 | x); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
const alfabe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcçdefgğhıijklmnoöprsştuüvyzÇĞİÖŞÜ0123456789   -./,_!?#' ＡБ😀";
const kategoriler = new Set(), olaylar = new Set();
for (let i = 0; i < spec.fuzz; i++) {
  const g = Array.from({ length: 1 + Math.floor(rnd() * 14) }, () => alfabe[Math.floor(rnd() * alfabe.length)]).join(""), ex = rnd() < 0.2 ? "x#1" : "";
  const sl = spec.iller[i % spec.iller.length], o = calistir(sl, g, ex); deneme++;
  if (!beklenen(o).includes(o.kat)) uyumsuz.push({ sl, g, ex, o });
  if (o.tip === "hata" || o.tip === "baska_il") { kategoriler.add(o.kat); ctx.__k = o.kat; olaylar.add(vm.runInContext("PlakaOlcum.kategoriOlayi('il-hesapla-hata', __k)", ctx)); }
}
console.log(JSON.stringify({ etiketli, eslik: { deneme, uyumsuz: uyumsuz.slice(0, 10), uyumsuzSayi: uyumsuz.length, sayac }, fuzz: { kategoriler: [...kategoriler].sort(), olaylar: [...olaylar].map(String).sort() } }));
