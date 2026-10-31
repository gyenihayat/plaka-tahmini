// /api/geri-bildirim: doğrulama, kayıt biçimi, güvenlik, hız sınırı ve GitHub yazımı. GitHub API'si taklit edilir (github_taklit.js): gerçek ağ isteği ve gerçek commit yoktur.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const { githubTaklidi, yanit } = require("./github_taklit.js");
const C = require("../../api/_geri-bildirim.js");
const ILLER = require("../../api/_iller.js");
const handlerModul = require("../../api/geri-bildirim.js");

const SIMDI = Date.parse("2026-10-31T09:00:00Z");
const TOKEN = "ghp_SAHTE_TOKEN_0123456789abcdef";
const ENV = { GITHUB_TOKEN: TOKEN, GERI_BILDIRIM_REPO: "gyenihayat/geri-bildirimler" };
const ORIGIN = "https://plakatahmini.com";
const bekleme = [];
const bekle = async ms => { bekleme.push(ms); };

function istek(govde, { yontem = "POST", ip = "203.0.113.7", baslik = {}, ham } = {}) {
  return { method: yontem, body: ham !== undefined ? ham : govde, headers: { origin: ORIGIN, "content-type": "application/json", "x-real-ip": ip, ...baslik } };
}
function yanitNesnesi() { const r = { basliklar: {}, setHeader(k, v) { this.basliklar[k] = v; }, status(n) { this.durum = n; return this; }, json(o) { this.govde = o; return this; } }; return r; }
function kur({ env = ENV, gh = githubTaklidi(), sinir, saat = () => SIMDI } = {}) {
  C.ozelDepoOnbellek.clear();
  const h = handlerModul.olustur({ env, fetch: gh.fetch, simdi: saat, bekle, sinir: sinir || C.sinirlayici() });
  const gonder = async (govde, secenek) => { const res = yanitNesnesi(); await h(istek(govde, secenek), res); return res; };
  return { gh, h, gonder };
}
const plaka = (ek = {}) => ({ form: "plaka", il: "06", plaka: "06 BYS 922", tarih: "2020-06", tarihKesinligi: "ay", aciklama: "", sayfa: "/il/ankara", website: "", gecen: 15000, ...ek });
const oneri = (ek = {}) => ({ form: "oneri", tur: "oneri", mesaj: "Harika bir site, teşekkürler.", isim: "", sayfa: "/", website: "", gecen: 15000, ...ek });
const satirlar = d => d.split("\n").filter(Boolean).map(x => JSON.parse(x));
const hataKonsolu = () => { const eski = console.error, log = []; console.error = (...a) => log.push(a.map(String).join(" ")); return { log, geri: () => { console.error = eski; } }; };

// --- doğrulama ---------------------------------------------------------------------------------------------------
test("iki form ayrı ayrı doğrulanır ve ayrı dosyalara yönlenir", () => {
  const p = C.dogrula(plaka(), SIMDI), o = C.dogrula(oneri(), SIMDI);
  assert.equal(p.dosya, "plaka"); assert.equal(o.dosya, "oneri");
  assert.deepEqual(p.kayit, { v: 1, zaman: "2026-10-31T09:00:00Z", tur: "plaka", il_kod: 6, il: "Ankara", plaka: "06 BYS 922", seri: "BYS", no: "922", tarih: "2020-06", tarih_kesinligi: "ay", aciklama: null, sayfa: "/il/ankara" });
  assert.deepEqual(o.kayit, { v: 1, zaman: "2026-10-31T09:00:00Z", tur: "oneri", isim: null, mesaj: "Harika bir site, teşekkürler.", sayfa: "/" });
});

test("81 ilin tamamı kabul edilir; kayıttaki il adı/kodu listeyle aynıdır", () => {
  assert.equal(ILLER.length, 81);
  for (const [kod, ad] of ILLER) {
    for (const girdi of [String(kod).padStart(2, "0"), String(kod)]) {
      const s = C.dogrula(plaka({ il: girdi, plaka: "ABC 123" }), SIMDI);
      assert.equal(s.hata, undefined, `${girdi}: ${s.hata}`); assert.equal(s.kayit.il_kod, kod); assert.equal(s.kayit.il, ad); assert.equal(s.kayit.plaka, `${String(kod).padStart(2, "0")} ABC 123`);
    }
  }
});

test("il seçiminde geçersiz değerler reddedilir", () => {
  for (const il of ["", "00", "0", "82", "99", "100", "abc", "6a", " ", "06;DROP", "1e1", "-6", "6.5", null, undefined, 6.5, 0, 82, -1, [], {}, true, "٠٦"]) {
    const s = C.dogrula(plaka({ il }), SIMDI); assert.ok(s.hata, `kabul edilmemeliydi: ${JSON.stringify(il)}`); assert.equal(s.alan, "il");
  }
});

test("tam plaka ve yalnızca seri biçimleri", () => {
  const ok = (ham, tam, seri, no, il = "06") => { const s = C.dogrula(plaka({ plaka: ham, il }), SIMDI); assert.equal(s.hata, undefined, `${ham}: ${s.hata}`); assert.equal(s.kayit.plaka, tam, ham); assert.equal(s.kayit.seri, seri); assert.equal(s.kayit.no, no); };
  ok("06 BYS 922", "06 BYS 922", "BYS", "922"); ok("bys 922", "06 BYS 922", "BYS", "922"); ok("06bys922", "06 BYS 922", "BYS", "922"); ok("06-BYS-922", "06 BYS 922", "BYS", "922");
  ok("BYS", "06 BYS", "BYS", null); ok("06 BYS", "06 BYS", "BYS", null); ok("  by  ", "06 BY", "BY", null); ok("a 1234", "06 A 1234", "A", "1234"); ok("34 AB 12", "34 AB 12", "AB", "12", "34");
  for (const ham of ["", "   ", "06", "922", "ABCD 123", "06 BYS 12345", "BYŞ 922", "06 BYS 922 X", "<b>X</b>", "06 BYS 922; DROP", "ÇĞİ", "06 06 BYS", "123 ABC 123"]) {
    const s = C.dogrula(plaka({ plaka: ham }), SIMDI); assert.ok(s.hata, `kabul edilmemeliydi: ${JSON.stringify(ham)}`); assert.equal(s.alan, "plaka");
  }
  const uyusmaz = C.dogrula(plaka({ plaka: "34 BYS 922", il: "06" }), SIMDI); assert.match(uyusmaz.hata, /uyuşmuyor/);
});

test("gün / ay / yıl düzeyinde tarih girişi", () => {
  const t = (tarih, tarihKesinligi) => C.dogrula(plaka({ tarih, tarihKesinligi }), SIMDI);
  assert.equal(t("2020-06-01", "gun").kayit.tarih, "2020-06-01"); assert.equal(t("2020-06-01", "gun").kayit.tarih_kesinligi, "gun");
  assert.equal(t("2020-06", "ay").kayit.tarih, "2020-06"); assert.equal(t("2020", "yil").kayit.tarih, "2020");
  assert.equal(t("2024-02-29", "gun").hata, undefined); assert.equal(t("2026-10-31", "gun").hata, undefined); assert.equal(t("2026-10", "ay").hata, undefined); assert.equal(t("2026", "yil").hata, undefined);
  for (const [tarih, k, ne] of [["2021-02-29", "gun", "geçersiz gün"], ["2020-13", "ay", "ay 13"], ["2020-00", "ay", "ay 0"], ["2026-11-01", "gun", "gelecek gün"], ["2026-11", "ay", "gelecek ay"], ["2027", "yil", "gelecek yıl"], ["1989", "yil", "1990 öncesi"],
    ["2020-06", "gun", "gün seçili ama ay verilmiş"], ["2020-06-01", "ay", "ay seçili ama gün verilmiş"], ["2020", "ay", "ay seçili ama yıl verilmiş"], ["20200601", "gun", "biçim"], ["", "gun", "boş"], [null, "yil", "null"], ["2020-06-01", "kesin", "bilinmeyen kesinlik"], ["2020-06-01", undefined, "kesinlik yok"], ["2020-6-1", "gun", "tek haneli"], ["abcd", "yil", "harf"]]) {
    assert.ok(t(tarih, k).hata, `kabul edilmemeliydi (${ne}): ${tarih} / ${k}`);
  }
});

test("Türkiye saatiyle gün sınırı: 31 Ekim 23:30 UTC = 1 Kasım Türkiye", () => {
  const gece = Date.parse("2026-10-31T23:30:00Z");
  assert.equal(C.dogrula(plaka({ tarih: "2026-11-01", tarihKesinligi: "gun" }), gece).hata, undefined);
  assert.ok(C.dogrula(plaka({ tarih: "2026-11-01", tarihKesinligi: "gun" }), SIMDI).hata);
});

test("plaka bildiriminde tarih zorunludur: eksik tarih ya da kesinlik reddedilir, GitHub'a gidilmez", async () => {
  for (const ek of [{ tarih: "" }, { tarih: undefined }, { tarih: null }, { tarih: "  " }, { tarihKesinligi: undefined }, { tarihKesinligi: "" }, { tarih: undefined, tarihKesinligi: undefined }]) {
    const s = C.dogrula(plaka(ek), SIMDI); assert.ok(s.hata, JSON.stringify(ek)); assert.ok(["tarih", "tarihKesinligi"].includes(s.alan), JSON.stringify(ek));
  }
  const g = { ...plaka() }; delete g.tarih; delete g.tarihKesinligi;
  const { gh, gonder } = kur(); const res = await gonder(g); assert.equal(res.durum, 400); assert.equal(res.govde.ok, false); assert.equal(gh.cagrilar.length, 0);
  assert.equal(C.dogrula(plaka({ tarih: "2020", tarihKesinligi: "yil" }), SIMDI).hata, undefined);   // üç kesinlik düzeyinden biri yeterli
});

test("boş ve aşırı uzun mesajlar reddedilir; sınır değerleri kabul edilir", () => {
  const m = mesaj => C.dogrula(oneri({ mesaj }), SIMDI);
  for (const mesaj of ["", "   ", "\n\n \t", "abc", "a b", "1234567", "....."]) assert.ok(m(mesaj).hata, JSON.stringify(mesaj));
  assert.equal(m("ab".repeat(750)).hata, undefined); assert.equal(m("ab".repeat(750) + "a").alan, "mesaj"); assert.equal(m("ab".repeat(50000)).alan, "mesaj");
  assert.equal(m("abcde").hata, undefined);
  assert.ok(m(undefined).hata); assert.ok(m(null).hata); assert.ok(m(12345).hata); assert.ok(m(["abc def"]).hata); assert.ok(m({ toString: () => "abcdef" }).hata);
  assert.equal(C.dogrula(oneri({ isim: "ab".repeat(20) }), SIMDI).hata, undefined); assert.equal(C.dogrula(oneri({ isim: "ab".repeat(20) + "a" }), SIMDI).alan, "isim");
  assert.equal(C.dogrula(plaka({ aciklama: "ab".repeat(250) }), SIMDI).hata, undefined); assert.equal(C.dogrula(plaka({ aciklama: "ab".repeat(250) + "a" }), SIMDI).alan, "aciklama");
  for (const tur of ["", "yorum", "ONERI", null, undefined, 1, ["oneri"]]) assert.equal(C.dogrula(oneri({ tur }), SIMDI).alan, "tur", JSON.stringify(tur));
  for (const tur of ["oneri", "hata", "diger"]) assert.equal(C.dogrula(oneri({ tur }), SIMDI).kayit.tur, tur);
});

test("script/HTML içerikli metin: satır geçerli JSON kalır, HTML karakteri içermez, metin değişmeden okunur", () => {
  const kotu = ["<script>alert(1)</script> merhaba", "\"><img src=x onerror=alert(1)>", "<b>kalın</b> & &lt;", "javascript:alert(1)", "</script><script>x</script>"];
  for (const mesaj of kotu) {
    const s = C.dogrula(oneri({ mesaj, isim: "<i>ad</i>" }), SIMDI), satir = C.satirYap(s.kayit);
    assert.equal(satir.endsWith("\n"), true); assert.equal(satir.slice(0, -1).includes("\n"), false);
    assert.equal(/[<>&]/.test(satir), false, "ham HTML karakteri satırda olmamalı");
    assert.equal(JSON.parse(satir).mesaj, mesaj); assert.equal(JSON.parse(satir).isim, "<i>ad</i>");
  }
  const p = C.dogrula(plaka({ aciklama: "<script>x</script>" }), SIMDI); assert.equal(JSON.parse(C.satirYap(p.kayit)).aciklama, "<script>x</script>");
  assert.ok(C.dogrula(plaka({ plaka: "<script>" }), SIMDI).hata);
});

test("çok satırlı mesaj tek satırlık JSON'a girer; kontrol ve yön değiştirme karakterleri atılır", () => {
  const s = C.dogrula(oneri({ mesaj: "ilk satır\r\n\r\n\r\n\r\nikinci satır üçüncü\u0000‮​ gizli" }), SIMDI), satir = C.satirYap(s.kayit);
  assert.equal(satir.slice(0, -1).includes("\n"), false); assert.equal(satir.includes("\r"), false); assert.equal(satir.includes(" "), false);
  const m = JSON.parse(satir).mesaj; assert.equal(m, "ilk satır\n\nikinci satırüçüncü gizli"); assert.equal(/[\u0000‮​]/.test(m), false);
  assert.equal(C.dogrula(oneri({ isim: "ali\nveli\t kaya" }), SIMDI).kayit.isim, "ali veli kaya");
});

test("spam: çok sayıda bağlantı, tekrarlı karakter, bal küpü alanı ve çok hızlı gönderim reddedilir", () => {
  assert.ok(C.dogrula(oneri({ mesaj: "bak http://a.com http://b.com https://c.com" }), SIMDI).hata);
  assert.ok(C.dogrula(oneri({ mesaj: "a".repeat(40) + " merhaba" }), SIMDI).hata);
  assert.equal(C.dogrula(oneri({ mesaj: "Kaynak: https://example.com/tablo çok işe yarar" }), SIMDI).hata, undefined);
  for (const website of ["http://spam.example", " x ", 1, true, {}, []]) assert.ok(C.dogrula(oneri({ website }), SIMDI).hata, JSON.stringify(website));
  assert.equal(C.dogrula(oneri({ website: "   " }), SIMDI).hata, undefined);
  for (const gecen of [0, 1999, -5, NaN, "20000", null, undefined, Infinity]) assert.ok(C.dogrula(oneri({ gecen }), SIMDI).hata, String(gecen));
  assert.equal(C.dogrula(oneri({ gecen: 2000 }), SIMDI).hata, undefined);
  for (const g of [null, undefined, "x", 5, [], [oneri()], true]) assert.ok(C.dogrula(g, SIMDI).hata);
  assert.ok(C.dogrula({ ...oneri(), form: "baska" }, SIMDI).hata); assert.ok(C.dogrula({ ...oneri(), form: undefined }, SIMDI).hata);
});

test("ilgili sayfa yalnızca bilinen yollardan biri olabilir; bilinmeyen null olur (isteği düşürmez)", () => {
  for (const [girdi, beklenen] of [["/", "/"], ["/il/ankara", "/il/ankara"], ["/il/ankara/", "/il/ankara"], ["/il/ankara?x=1#y", "/il/ankara"], ["/il/yok", null], ["https://evil.example/", null], ["javascript:alert(1)", null], ["/il/../etc", null], ["", null], [null, null], [5, null], ["/geri-bildirim", null], ["<script>", null]])
    assert.equal(C.sayfaYolu(girdi), beklenen, String(girdi));
  assert.equal(C.dogrula(oneri({ sayfa: "https://evil.example" }), SIMDI).kayit.sayfa, null);
  for (const [, , slug] of ILLER) assert.equal(C.sayfaYolu("/il/" + slug), "/il/" + slug);
});

// --- işleyici: istek denetimleri ve yapılandırma -------------------------------------------------------------------
test("yalnızca POST; GET 405 döner ve GitHub'a hiç gidilmez", async () => {
  const { gh, h } = kur(); for (const yontem of ["GET", "PUT", "DELETE", "OPTIONS"]) { const res = yanitNesnesi(); await h(istek(null, { yontem }), res); assert.equal(res.durum, 405); assert.equal(res.basliklar.Allow, "POST"); }
  assert.equal(gh.cagrilar.length, 0);
});

test("token eksik: 503, GitHub'a gidilmez, yanıt yapılandırma ayrıntısı/başarı sızdırmaz", async () => {
  const k = hataKonsolu();
  try {
    for (const env of [{ GERI_BILDIRIM_REPO: ENV.GERI_BILDIRIM_REPO }, { GITHUB_TOKEN: "", GERI_BILDIRIM_REPO: ENV.GERI_BILDIRIM_REPO }, { GITHUB_TOKEN: TOKEN }, { GITHUB_TOKEN: TOKEN, GERI_BILDIRIM_REPO: "bozuk" },
      { ...ENV, VERCEL_GIT_REPO_OWNER: "gyenihayat", VERCEL_GIT_REPO_SLUG: "geri-bildirimler" }, { ...ENV, GERI_BILDIRIM_BRANCH: "../x" }, { ...ENV, GERI_BILDIRIM_ONERI_DOSYASI: "../x.txt" }, { ...ENV, GERI_BILDIRIM_ONERI_DOSYASI: "a.txt", GERI_BILDIRIM_PLAKA_DOSYASI: "a.txt" }]) {
      const { gh, gonder } = kur({ env }), res = await gonder(oneri());
      assert.equal(res.durum, 503, JSON.stringify(env)); assert.equal(res.govde.ok, false); assert.equal(gh.cagrilar.length, 0);
      assert.doesNotMatch(JSON.stringify(res.govde), /GITHUB|GERI_BILDIRIM|token|repo/i);
    }
  } finally { k.geri(); }
  assert.ok(k.log.length >= 8); assert.ok(k.log.every(x => !x.includes(TOKEN)));
});

test("köken, içerik türü ve boyut denetimi", async () => {
  const { gh, h } = kur();
  const dene = async (opt, govde = oneri()) => { const res = yanitNesnesi(); await h(istek(govde, opt), res); return res; };
  assert.equal((await dene({ baslik: { origin: "https://evil.example" } })).durum, 403);
  assert.equal((await dene({ baslik: { origin: undefined } })).durum, 403);                   // origin de referer de yok
  assert.equal((await dene({ baslik: { origin: "null" } })).durum, 403);
  assert.equal((await dene({ baslik: { origin: undefined, referer: "https://plakatahmini.com/geri-bildirim" } })).durum, 200);
  assert.equal((await dene({ baslik: { origin: undefined, referer: "https://evil.example/https://plakatahmini.com/" } })).durum, 403);
  assert.equal((await dene({ baslik: { "content-type": "text/plain" } })).durum, 415);
  assert.equal((await dene({ baslik: { "content-length": "99999" } })).durum, 413);
  assert.equal((await dene({}, oneri({ mesaj: "ab".repeat(4500) }))).durum, 413);
  assert.equal((await dene({ ham: JSON.stringify(oneri({ mesaj: "ab".repeat(4500) })) })).durum, 413);
  assert.equal((await dene({ ham: "{bozuk json" })).durum, 400);
  assert.equal((await dene({ ham: "" })).durum, 400);
  assert.equal((await dene({ ham: "[]" })).durum, 400);
  const yazimlar = gh.cagrilar.filter(c => c.yontem === "PUT").length; assert.equal(yazimlar, 1, "yalnızca geçerli (referer'lı) istek yazılmalı");
});

// --- işleyici: kayıt ---------------------------------------------------------------------------------------------
test("iki form ayrı dosyalara yazılır; commit mesajı [skip ci] içerir; dal ve yol doğrudur; kayıtlar sitenin veri dosyalarına yazılmaz", async () => {
  const { gh, gonder } = kur({ gh: githubTaklidi({ dosyalar: { "oneriler.txt": JSON.stringify({ eski: 1 }) + "\n" } }) });
  const a = await gonder(oneri({ mesaj: "Birinci mesaj\nikinci satır", isim: "Ali", tur: "hata" })), b = await gonder(plaka(), { ip: "198.51.100.2" });
  assert.equal(a.durum, 200); assert.deepEqual(a.govde, { ok: true }); assert.equal(b.durum, 200);
  const o = satirlar(gh.dosya.get("oneriler.txt").icerik), p = satirlar(gh.dosya.get("plaka_bildirimleri.txt").icerik);
  assert.deepEqual(o[0], { eski: 1 }); assert.equal(o.length, 2); assert.equal(o[1].tur, "hata"); assert.equal(o[1].mesaj, "Birinci mesaj\nikinci satır"); assert.equal(o[1].isim, "Ali");
  assert.equal(p.length, 1); assert.equal(p[0].tur, "plaka"); assert.equal(p[0].il, "Ankara"); assert.equal(p[0].plaka, "06 BYS 922");
  assert.deepEqual(gh.yazilanYollar().sort(), ["/repos/gyenihayat/geri-bildirimler/contents/oneriler.txt", "/repos/gyenihayat/geri-bildirimler/contents/plaka_bildirimleri.txt"]);
  assert.equal(gh.commitler.length, 2); for (const c of gh.commitler) { assert.match(c.mesaj, /\[skip ci\]$/); assert.equal(c.dal, "main"); assert.doesNotMatch(c.mesaj, /Birinci|Ali|BYS/); }
  assert.ok(gh.cagrilar.every(c => !/tahmin_data|tarihsel_referanslar/.test(c.yol)));
  assert.ok(gh.cagrilar.filter(c => c.yontem === "GET" && c.yol.includes("/contents/")).every(c => c.arama === "?ref=main"));
  assert.ok(gh.cagrilar.every(c => c.basliklar.Authorization === `Bearer ${TOKEN}`));
});

test("yapılandırılabilir dal ve dosya yolları; eksik dosya oluşturulur (201); sonda satır sonu olmayan dosyaya satır sonu eklenir", async () => {
  const gh = githubTaklidi({ dosyalar: { "kayit/oneri.jsonl": '{"eski":1}' } });
  const { gonder } = kur({ env: { ...ENV, GERI_BILDIRIM_BRANCH: "veri", GERI_BILDIRIM_ONERI_DOSYASI: "kayit/oneri.jsonl", GERI_BILDIRIM_PLAKA_DOSYASI: "kayit/plaka.jsonl" }, gh });
  assert.equal((await gonder(oneri())).durum, 200); assert.equal((await gonder(plaka(), { ip: "198.51.100.9" })).durum, 200);
  assert.equal(gh.dosya.get("kayit/oneri.jsonl").icerik.split("\n").length, 3); assert.equal(satirlar(gh.dosya.get("kayit/oneri.jsonl").icerik)[0].eski, 1);
  assert.equal(satirlar(gh.dosya.get("kayit/plaka.jsonl").icerik).length, 1); assert.ok(gh.commitler.every(c => c.dal === "veri"));
  assert.ok(gh.cagrilar.filter(c => c.yontem === "GET" && c.yol.includes("/contents/")).every(c => c.arama === "?ref=veri"));
});

test("IP adresi ve istek üstbilgileri kayda girmez; kayıt yalnızca beklenen alanları taşır", async () => {
  const { gh, gonder } = kur(); await gonder(oneri(), { ip: "203.0.113.77", baslik: { "user-agent": "TestTarayici/1.0", "x-forwarded-for": "203.0.113.77" } }); await gonder(plaka(), { ip: "203.0.113.78" });
  for (const d of ["oneriler.txt", "plaka_bildirimleri.txt"]) { const t = gh.dosya.get(d).icerik; assert.doesNotMatch(t, /203\.0\.113|TestTarayici|origin|plakatahmini\.com/i); }
  assert.deepEqual(Object.keys(satirlar(gh.dosya.get("oneriler.txt").icerik)[0]), ["v", "zaman", "tur", "isim", "mesaj", "sayfa"]);
  assert.deepEqual(Object.keys(satirlar(gh.dosya.get("plaka_bildirimleri.txt").icerik)[0]), ["v", "zaman", "tur", "il_kod", "il", "plaka", "seri", "no", "tarih", "tarih_kesinligi", "aciklama", "sayfa"]);
});

test("tekrarlanan gönderim: aynı içerik ikinci kez yazılmaz, kullanıcıya başarı döner; farklı içerik yazılır", async () => {
  const { gh, gonder } = kur({ sinir: C.sinirlayici({ ipMax: 50, gunMax: 50 }) });
  const a = await gonder(oneri()), b = await gonder(oneri()), c = await gonder(oneri({ mesaj: "Başka bir mesaj yazıyorum" }));
  assert.equal(a.durum, 200); assert.equal(a.govde.tekrar, undefined); assert.equal(b.durum, 200); assert.equal(b.govde.tekrar, true); assert.equal(c.durum, 200);
  assert.equal(satirlar(gh.dosya.get("oneriler.txt").icerik).length, 2);
  assert.equal(gh.cagrilar.filter(x => x.yontem === "PUT").length, 2);
});

test("gönderim sıklığı sınırı: IP başına 10 dakikada 3, günde 12; başka IP etkilenmez; süre dolunca açılır", async () => {
  let t = SIMDI;
  const { gh, gonder } = kur({ saat: () => t, sinir: C.sinirlayici() });
  const g = (n, ip) => gonder(oneri({ mesaj: `Mesaj numarası ${n} burada` }), { ip });
  assert.deepEqual([(await g(1, "1.1.1.1")).durum, (await g(2, "1.1.1.1")).durum, (await g(3, "1.1.1.1")).durum, (await g(4, "1.1.1.1")).durum], [200, 200, 200, 429]);
  const r = await g(5, "1.1.1.1"); assert.equal(r.govde.ok, false); assert.doesNotMatch(JSON.stringify(r.govde), /1\.1\.1\.1/);
  assert.equal((await g(6, "2.2.2.2")).durum, 200);
  t += 11 * 60e3; assert.equal((await g(7, "1.1.1.1")).durum, 200);
  assert.equal(satirlar(gh.dosya.get("oneriler.txt").icerik).length, 5);
  // günlük sınır
  let say = 0; const gun = kur({ saat: () => t, sinir: C.sinirlayici() });
  const sonuc = []; for (let i = 0; i < 14; i++) { t += 11 * 60e3; sonuc.push((await gun.gonder(oneri({ mesaj: `Günlük deneme ${i} yazısı` }), { ip: "9.9.9.9" })).durum); }
  assert.deepEqual(sonuc, [...Array(12).fill(200), 429, 429]); void say;
  // genel sınır (örnek başına saatlik)
  const genel = kur({ saat: () => t, sinir: C.sinirlayici({ genelMax: 3 }) }), d = [];
  for (let i = 0; i < 5; i++) d.push((await genel.gonder(oneri({ mesaj: `Genel sınır ${i} metni` }), { ip: `7.7.7.${i}` })).durum);
  assert.deepEqual(d, [200, 200, 200, 429, 429]);
});

test("geçersiz istekler hız sınırını tüketmez ve GitHub'a gitmez", async () => {
  const { gh, gonder } = kur();
  for (let i = 0; i < 10; i++) assert.equal((await gonder(oneri({ mesaj: "" }))).durum, 400);
  assert.equal(gh.cagrilar.length, 0); assert.equal((await gonder(oneri())).durum, 200);
});

// --- GitHub hataları ve çakışmalar ---------------------------------------------------------------------------------
test("GitHub hataları: kullanıcıya başarı gösterilmez, ayrıntı/token sızmaz, loga yalnızca kod ve durum yazılır", async () => {
  const senaryolar = {
    "okuma 500": { kanca: async ({ yontem, u }) => yontem === "GET" && u.pathname.includes("/contents/") ? yanit(500, { message: "Server Error " + TOKEN }) : null },
    "okuma 401": { kanca: async ({ yontem, u }) => yontem === "GET" && u.pathname.includes("/contents/") ? yanit(401, { message: "Bad credentials" }) : null },
    "yazma 403": { kanca: async ({ yontem }) => yontem === "PUT" ? yanit(403, { message: "Resource not accessible by personal access token" }) : null },
    "yazma 500": { kanca: async ({ yontem }) => yontem === "PUT" ? yanit(500, { message: "boom" }) : null },
    "depo okunamadı": { kanca: async ({ yontem, u }) => yontem === "GET" && !u.pathname.includes("/contents/") ? yanit(404, { message: "Not Found" }) : null },
    "ağ hatası": { kanca: async () => { throw new TypeError("fetch failed: ECONNRESET " + TOKEN); } },
    "zaman aşımı": { kanca: async () => { const e = new Error("The operation was aborted due to timeout"); e.name = "TimeoutError"; throw e; } },
    "depo özel değil": { ozel: false },
    "bozuk dosya yanıtı": { kanca: async ({ yontem, u }) => yontem === "GET" && u.pathname.includes("/contents/") ? yanit(200, { type: "file", encoding: "none", content: "" }) : null },
    "çok büyük dosya": { dosyalar: { "oneriler.txt": "x".repeat(950000) + "\n" } },
  };
  for (const [ad, ayar] of Object.entries(senaryolar)) {
    const k = hataKonsolu(); const gh = githubTaklidi(ayar), { gonder } = kur({ gh });
    let res; try { res = await gonder(oneri({ mesaj: "Gizli kullanıcı metni burada" })); } finally { k.geri(); }
    assert.equal(res.durum, 500, ad); assert.equal(res.govde.ok, false, ad); assert.equal(res.govde.error, "Bildiriminiz kaydedilemedi. Lütfen biraz sonra tekrar deneyin.", ad);
    assert.deepEqual(Object.keys(res.govde).sort(), ["error", "ok"]);
    const hepsi = JSON.stringify(res.govde) + k.log.join(" ");
    assert.ok(!hepsi.includes(TOKEN), `${ad}: token sızdı`); assert.doesNotMatch(hepsi, /Gizli kullanıcı|Server Error|Bad credentials|ECONNRESET|Resource not accessible/, ad);
    assert.equal(k.log.length, 1, ad); assert.match(k.log[0], /^geri-bildirim: kayıt başarısız: [a-z_]+/);
    if (ad === "depo özel değil" || ad === "çok büyük dosya") assert.equal(gh.cagrilar.filter(c => c.yontem === "PUT").length, 0, ad);
  }
});

test("başarısız yazımdan sonra aynı içerikle yeniden denemek mümkündür (tekrar engeli takılmaz)", async () => {
  let basarisiz = true;
  const gh = githubTaklidi({ kanca: async ({ yontem }) => yontem === "PUT" && basarisiz ? yanit(500, {}) : null }), { gonder } = kur({ gh, sinir: C.sinirlayici({ ipMax: 50, gunMax: 50 }) });
  const k = hataKonsolu(); try { assert.equal((await gonder(oneri())).durum, 500); } finally { k.geri(); }
  basarisiz = false; const r = await gonder(oneri()); assert.equal(r.durum, 200); assert.equal(r.govde.tekrar, undefined);
  assert.equal(satirlar(gh.dosya.get("oneriler.txt").icerik).length, 1);
});

test("eşzamanlı commit çakışması: 409 sonrası yeniden okunur, diğer yazarın satırı kaybolmaz", async () => {
  let ilk = true;
  const gh = githubTaklidi({ dosyalar: { "oneriler.txt": '{"mevcut":1}\n' }, kanca: async ({ yontem, dosya, yeniSha }) => {
    if (yontem === "PUT" && ilk) { ilk = false; const d = dosya.get("oneriler.txt"); dosya.set("oneriler.txt", { icerik: d.icerik + '{"baska_yazar":1}\n', sha: yeniSha("x") }); }   // GET ile PUT arasında başka biri yazdı
    return null;
  } });
  bekleme.length = 0; const { gonder } = kur({ gh }), res = await gonder(oneri());
  assert.equal(res.durum, 200); const o = satirlar(gh.dosya.get("oneriler.txt").icerik);
  assert.deepEqual(o.map(x => x.mevcut || x.baska_yazar || x.tur), [1, 1, "oneri"]); assert.equal(bekleme.length, 1);
  assert.equal(gh.cagrilar.filter(c => c.yontem === "PUT").length, 2);
});

test("dosya ilk kez eşzamanlı oluşturulurken 422 yarışı da yeniden denenir", async () => {
  let ilk = true;
  const gh = githubTaklidi({ kanca: async ({ yontem, dosya, yeniSha }) => { if (yontem === "PUT" && ilk) { ilk = false; dosya.set("plaka_bildirimleri.txt", { icerik: '{"yarisan":1}\n', sha: yeniSha("y") }); } return null; } });
  const { gonder } = kur({ gh }), res = await gonder(plaka());
  assert.equal(res.durum, 200); assert.deepEqual(satirlar(gh.dosya.get("plaka_bildirimleri.txt").icerik).map(x => x.yarisan || x.tur), [1, "plaka"]);
});

test("kalıcı çakışma: sınırlı sayıda yeniden dener (5), artan bekleme ile; sonunda hata döner, başarı sahtelenmez", async () => {
  const gh = githubTaklidi({ dosyalar: { "oneriler.txt": "" }, kanca: async ({ yontem }) => yontem === "PUT" ? yanit(409, { message: "conflict" }) : null });
  bekleme.length = 0; const k = hataKonsolu(); let res; try { res = await kur({ gh }).gonder(oneri()); } finally { k.geri(); }
  assert.equal(res.durum, 500); assert.equal(res.govde.ok, false);
  assert.equal(gh.cagrilar.filter(c => c.yontem === "PUT").length, 5); assert.equal(bekleme.length, 4);
  for (let i = 1; i < bekleme.length; i++) assert.ok(bekleme[i] > bekleme[i - 1] - 60, "bekleme artmalı (rastgele bileşen ±60 ms)");
  assert.match(k.log[0], /cakisma 409/);
});

test("süre bütçesi dolarsa yeniden deneme bırakılır", async () => {
  let t = SIMDI; const gh = githubTaklidi({ kanca: async ({ yontem }) => { if (yontem === "PUT") { t += 5000; return yanit(409, {}); } return null; } });
  const k = hataKonsolu(); let res; try { res = await kur({ gh, saat: () => t }).gonder(oneri()); } finally { k.geri(); }
  assert.equal(res.durum, 500); assert.ok(gh.cagrilar.filter(c => c.yontem === "PUT").length <= 2);
});

test("eşzamanlı gönderimler: başarı dönen her kayıt dosyada vardır, hiçbiri kaybolmaz ya da çoğalmaz", async () => {
  const gh = githubTaklidi(), { gonder } = kur({ gh, sinir: C.sinirlayici({ ipMax: 100, gunMax: 100, genelMax: 1000 }) });
  const k = hataKonsolu(); let sonuc;
  try { sonuc = await Promise.all(Array.from({ length: 12 }, (_, i) => gonder(oneri({ mesaj: `Eşzamanlı mesaj sıra ${i} gönderildi` }), { ip: `10.0.0.${i}` }))); } finally { k.geri(); }
  const tamam = sonuc.filter(r => r.durum === 200).length, dosya = satirlar((gh.dosya.get("oneriler.txt") || { icerik: "" }).icerik);
  assert.ok(tamam >= 5, `en az 5 gönderim başarılı olmalı: ${tamam}`); assert.equal(dosya.length, tamam, "başarı sayısı = kayıt sayısı");
  assert.equal(new Set(dosya.map(x => x.mesaj)).size, dosya.length);
  assert.ok(sonuc.filter(r => r.durum !== 200).every(r => r.durum === 500 && r.govde.ok === false));
});

test("depo özel mi denetimi 6 saat önbelleğe alınır (gönderim başına ek istek yok)", async () => {
  const { gh, gonder } = kur(); await gonder(oneri()); await gonder(plaka(), { ip: "5.5.5.5" }); await gonder(oneri({ mesaj: "Üçüncü mesaj metni burada" }), { ip: "6.6.6.6" });
  assert.equal(gh.cagrilar.filter(c => c.yol === "/repos/gyenihayat/geri-bildirimler").length, 1);
});

// --- deponun kendisi -----------------------------------------------------------------------------------------------
test("api/ altında yalnızca iki dosya uç noktadır ve alt çizgili yardımcılar uç nokta olmaz; token kaynakta yoktur", () => {
  const fs = require("fs"), dizin = path.join(__dirname, "..", "..", "api");
  const dosyalar = fs.readdirSync(dizin).sort(); assert.deepEqual(dosyalar, ["_geri-bildirim.js", "_iller.js", "geri-bildirim.js"]);
  for (const d of dosyalar) { const m = fs.readFileSync(path.join(dizin, d), "utf8"); assert.doesNotMatch(m, /ghp_|github_pat_|Bearer [A-Za-z0-9]{20}/); }
  assert.deepEqual(dosyalar.filter(d => !d.startsWith("_")), ["geri-bildirim.js"]);
});
