/**
 * /api/geri-bildirim çekirdeği: yapılandırma, doğrulama, kayıt biçimi, gönderim sınırı ve GitHub'a ekleme.
 * Alt çizgi önekli dosya Vercel'de uç nokta olmaz; api/geri-bildirim.js bunu kullanır, testler doğrudan yükler.
 *
 * Kayıtlar siteyle AYNI depoya değil, ayrı ve ÖZEL bir depoya yazılır (GERI_BILDIRIM_REPO). Bu depo özel değilse
 * (GitHub "private" göstermiyorsa) hiçbir şey yazılmaz. Dosyalar JSONL'dir: her gönderim tek satır JSON.
 * Kullanıcı plaka bildirimleri hiçbir koşulda data/tahmin_data.json veya data/tarihsel_referanslar.json'a yazılmaz.
 */
"use strict";
const crypto = require("crypto");
const ILLER = require("./_iller.js");

const SINIRLAR = {
  mesaj: { min: 5, max: 1500 }, isim: { max: 40 }, aciklama: { max: 500 }, plaka: { max: 16 },
  govde: 8192,                  // bayt: formdan gelen JSON bundan büyük olamaz
  gecenMinMs: 2000,             // form açıldıktan en az bu kadar sonra gönderilebilir (botlar anında gönderir)
  dosyaMax: 900000,             // bayt: GitHub Contents API ~1 MB'a kadar içeriği JSON içinde döndürür; aşılırsa yazılmaz (dosyayı döndürün)
};
const ILK_YIL = 1990;           // daha eski tarihler kabul edilmez (üç harfli plaka dönemi çok daha yenidir; 1990 öncesi anlamlı bir bildirim değildir)
const BILDIRIM_TURLERI = ["oneri", "hata", "diger"];
const KESINLIKLER = ["gun", "ay", "yil"];
const SAYFALAR = new Set(["/", ...ILLER.map(x => "/il/" + x[2])]);
const IL_KODU = new Map(ILLER.map(x => [x[0], x]));

// --- yapılandırma ------------------------------------------------------------------------------------------------
// GITHUB_TOKEN yalnızca sunucuda okunur; hiçbir yanıta, loga ya da kayda girmez.
function yapilandirma(env = process.env) {
  const token = env.GITHUB_TOKEN, repo = env.GERI_BILDIRIM_REPO;
  const dal = env.GERI_BILDIRIM_BRANCH || "main";
  const dosyalar = { oneri: env.GERI_BILDIRIM_ONERI_DOSYASI || "oneriler.txt", plaka: env.GERI_BILDIRIM_PLAKA_DOSYASI || "plaka_bildirimleri.txt" };
  if (!token) return { hata: "GITHUB_TOKEN tanımlı değil" };
  if (!repo || !/^[\w.-]+\/[\w.-]+$/.test(repo)) return { hata: "GERI_BILDIRIM_REPO tanımlı değil ya da 'sahip/depo' biçiminde değil" };
  // Güvenlik ağı: Vercel'in sistem değişkenleri (Git depo adı) açıksa, kayıtlar sitenin kendi (herkese açık olabilecek) deposuna yazılmaz.
  const siteDeposu = env.VERCEL_GIT_REPO_OWNER && env.VERCEL_GIT_REPO_SLUG ? `${env.VERCEL_GIT_REPO_OWNER}/${env.VERCEL_GIT_REPO_SLUG}` : null;
  if (siteDeposu && siteDeposu.toLowerCase() === repo.toLowerCase()) return { hata: "GERI_BILDIRIM_REPO sitenin kendi deposu olamaz; ayrı özel bir depo kullanın" };
  if (!/^[\w./-]+$/.test(dal) || dal.includes("..")) return { hata: "GERI_BILDIRIM_BRANCH geçersiz" };
  for (const d of Object.values(dosyalar)) if (!/^[\w][\w./-]*$/.test(d) || d.includes("..")) return { hata: "kayıt dosyası yolu geçersiz" };
  if (dosyalar.oneri === dosyalar.plaka) return { hata: "öneri ve plaka dosyaları farklı olmalı" };
  const izinli = (env.GERI_BILDIRIM_ORIGINLER || "https://plakatahmini.com,https://www.plakatahmini.com").split(",").map(s => s.trim()).filter(Boolean);
  return { token, repo, dal, dosyalar, izinli };
}

// --- metin temizliği ---------------------------------------------------------------------------------------------
// Görünmez/yön değiştiren karakterler (bidi, sıfır genişlik) ve kontrol karakterleri atılır. Satır sonu yalnızca çok satırlı alanda korunur (JSON onu \n olarak kaçışlar).
const GIZLI = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u00ad\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060-\u2069\ufeff]/g;
function metin(s, cokSatir) {
  if (typeof s !== "string") return "";
  let t = s.normalize("NFC").replace(/\r\n?/g, "\n").replace(GIZLI, "");
  if (cokSatir) return t.split("\n").map(x => x.replace(/[ \t]+/g, " ").trim()).join("\n").replace(/\n{3,}/g, "\n\n").trim();
  return t.replace(/\s+/g, " ").trim();
}
// JSON satırında < > & karakterleri \u003c gibi kaçışlanır: satır geçerli JSON kalır, ama bir HTML'e yapıştırılsa bile etiket oluşturamaz.
function satirYap(kayit) {
  return JSON.stringify(kayit).replace(/</g, "\\u003c").replace(/>/g, "\\u003e").replace(/&/g, "\\u0026").replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029") + "\n";
}
function zamanDamgasi(simdi) { return new Date(simdi).toISOString().replace(/\.\d{3}Z$/, "Z"); }
function sayfaYolu(s) {         // yalnızca bilinen sayfalar (/ ve /il/<slug>); başka her şey null
  const t = typeof s === "string" && s ? s.split(/[?#]/)[0].replace(/\/+$/, "") || "/" : null;
  return t && SAYFALAR.has(t) ? t : null;
}
function spamMi(t) {
  if ((t.match(/https?:\/\/|www\.|\b[a-z0-9-]+\.(?:com|net|org|ru|xyz|top|info)\b/gi) || []).length >= 3) return true;
  if (/(.)\1{29,}/u.test(t)) return true;
  return false;
}

// --- tarih ve plaka ----------------------------------------------------------------------------------------------
function takvimGecerli(y, m, g) { const d = new Date(Date.UTC(y, m - 1, g)); return d.getUTCFullYear() === y && d.getUTCMonth() === m - 1 && d.getUTCDate() === g; }
function trTarih(simdi) { const d = new Date(simdi + 3 * 3600e3); return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, g: d.getUTCDate() }; }   // Türkiye UTC+3 sabit
/** { tarih, kesinlik } doğrular. Gün: YYYY-MM-DD, ay: YYYY-MM, yıl: YYYY. Gelecek tarih ve ILK_YIL öncesi reddedilir. */
function tarihDogrula(tarih, kesinlik, simdi) {
  if (!KESINLIKLER.includes(kesinlik)) return { hata: "Tarih kesinliği seçilmeli.", alan: "tarihKesinligi" };
  const t = typeof tarih === "string" ? tarih.trim() : "";
  const re = { gun: /^(\d{4})-(\d{2})-(\d{2})$/, ay: /^(\d{4})-(\d{2})$/, yil: /^(\d{4})$/ }[kesinlik], m = re.exec(t);
  if (!m) return { hata: { gun: "Gün, ay ve yıl olarak tam bir tarih girin.", ay: "Ay ve yıl girin.", yil: "Yıl girin (dört hane)." }[kesinlik], alan: "tarih" };
  const y = +m[1], ay = m[2] ? +m[2] : 1, g = m[3] ? +m[3] : 1, bu = trTarih(simdi);
  if (y < ILK_YIL) return { hata: `${ILK_YIL} öncesi tarihler kabul edilmiyor.`, alan: "tarih" };
  if (ay < 1 || ay > 12 || !takvimGecerli(y, ay, g)) return { hata: "Geçerli bir tarih girin.", alan: "tarih" };
  const gelecek = kesinlik === "gun" ? y * 10000 + ay * 100 + g > bu.y * 10000 + bu.m * 100 + bu.g : kesinlik === "ay" ? y * 100 + ay > bu.y * 100 + bu.m : y > bu.y;
  if (gelecek) return { hata: "Tarih gelecekte olamaz.", alan: "tarih" };
  return { tarih: t, kesinlik };
}
/** "34 ABC 123", "ABC 123", "34ABC", "abc" ... -> { il, seri, no, tam }. Seri 1-3 harf (A-Z), numara isteğe bağlı 1-4 rakam. */
function plakaDogrula(ham, ilKodu) {
  const t = metin(ham, false).toUpperCase().replace(/[.\-_]/g, " ").replace(/\s+/g, " ").trim();
  const m = /^(?:(\d{1,2}) ?)?([A-Z]{1,3})(?: ?(\d{1,4}))?$/.exec(t);
  if (!t) return { hata: "Plaka ya da harf serisi girin.", alan: "plaka" };
  if (!m) return { hata: "Plakayı \"XYZ 123\" ya da yalnızca \"XYZ\" biçiminde girin (1-3 harf, isteğe bağlı rakamlar).", alan: "plaka" };
  if (m[1] && +m[1] !== ilKodu) return { hata: "Plakadaki il kodu seçtiğiniz ille uyuşmuyor.", alan: "plaka" };
  const il = String(ilKodu).padStart(2, "0"), tam = `${il} ${m[2]}${m[3] ? " " + m[3] : ""}`;
  return { seri: m[2], no: m[3] || null, tam };
}

// --- doğrulama ---------------------------------------------------------------------------------------------------
/**
 * Ham gövdeyi doğrular. Hata: { hata, alan?, durum? }. Geçerliyse { dosya: "oneri"|"plaka", kayit } döner.
 * `simdi`: ms (test için enjekte edilebilir).
 */
function dogrula(b, simdi = Date.now()) {
  if (!b || typeof b !== "object" || Array.isArray(b)) return { hata: "Geçersiz istek." };
  if (typeof b.website === "string" && b.website.trim() !== "" || (b.website !== undefined && typeof b.website !== "string")) return { hata: "Geçersiz istek." };   // bal küpü alanı: gerçek kullanıcı doldurmaz
  if (typeof b.gecen !== "number" || !isFinite(b.gecen) || b.gecen < SINIRLAR.gecenMinMs) return { hata: "Form çok hızlı gönderildi; lütfen alanları kontrol edip tekrar deneyin." };
  const sayfa = sayfaYolu(b.sayfa);

  if (b.form === "plaka") {
    const kod = typeof b.il === "string" && /^\d{1,2}$/.test(b.il.trim()) ? +b.il.trim() : typeof b.il === "number" && Number.isInteger(b.il) ? b.il : NaN;
    const il = IL_KODU.get(kod);
    if (!il) return { hata: "Listeden bir il seçin.", alan: "il" };
    const p = plakaDogrula(b.plaka, kod); if (p.hata) return p;
    const t = tarihDogrula(b.tarih, b.tarihKesinligi, simdi); if (t.hata) return t;
    const aciklama = metin(b.aciklama, true);
    if (aciklama.length > SINIRLAR.aciklama.max) return { hata: `Açıklama en fazla ${SINIRLAR.aciklama.max} karakter olabilir.`, alan: "aciklama" };
    if (spamMi(aciklama)) return { hata: "Açıklamada çok fazla bağlantı var.", alan: "aciklama" };
    return { dosya: "plaka", kayit: { v: 1, zaman: zamanDamgasi(simdi), tur: "plaka", il_kod: kod, il: il[1], plaka: p.tam, seri: p.seri, no: p.no, tarih: t.tarih, tarih_kesinligi: t.kesinlik, aciklama: aciklama || null, sayfa } };
  }
  if (b.form === "oneri") {
    if (!BILDIRIM_TURLERI.includes(b.tur)) return { hata: "Bildirim türünü seçin.", alan: "tur" };
    const mesaj = metin(b.mesaj, true), isim = metin(b.isim, false);
    if (mesaj.length < SINIRLAR.mesaj.min || (mesaj.match(/\p{L}/gu) || []).length < 3) return { hata: `Mesaj en az ${SINIRLAR.mesaj.min} karakter olmalı.`, alan: "mesaj" };
    if (mesaj.length > SINIRLAR.mesaj.max) return { hata: `Mesaj en fazla ${SINIRLAR.mesaj.max} karakter olabilir.`, alan: "mesaj" };
    if (isim.length > SINIRLAR.isim.max) return { hata: `İsim en fazla ${SINIRLAR.isim.max} karakter olabilir.`, alan: "isim" };
    if (spamMi(mesaj) || spamMi(isim)) return { hata: "Mesajda çok fazla bağlantı var.", alan: "mesaj" };
    return { dosya: "oneri", kayit: { v: 1, zaman: zamanDamgasi(simdi), tur: b.tur, isim: isim || null, mesaj, sayfa } };
  }
  return { hata: "Geçersiz istek." };
}

// --- gönderim sınırı ve tekrar engeli (bellekte, örnek başına; IP ve içerik yalnızca tuzlanmış özet olarak, kalıcı değil) --------------
// Sunucusuz örnekler arasında paylaşılmaz: bu bir ilk savunma hattıdır, kesin sınır değil (README: Vercel Firewall hız sınırı kuralı önerilir).
function sinirlayici({ pencere = 10 * 60e3, ipMax = 3, gunMax = 12, genelMax = 120, tekrarSure = 30 * 60e3 } = {}) {
  const tuz = crypto.randomBytes(16), ipler = new Map(), tekrar = new Map(), genel = [];
  const ozet = s => crypto.createHmac("sha256", tuz).update(s).digest("hex").slice(0, 20);
  const buda = (liste, simdi, sure) => { while (liste.length && simdi - liste[0] > sure) liste.shift(); };
  return {
    /** true: izin verildi (kayda sayıldı). false: sınır aşıldı. */
    izin(ip, simdi = Date.now()) {
      buda(genel, simdi, 3600e3); if (genel.length >= genelMax) return false;
      const k = ozet(ip || "bilinmiyor"), l = ipler.get(k) || [];
      buda(l, simdi, 24 * 3600e3);
      if (l.length >= gunMax || l.filter(t => simdi - t <= pencere).length >= ipMax) { ipler.set(k, l); return false; }
      l.push(simdi); ipler.set(k, l); genel.push(simdi);
      if (ipler.size > 5000) for (const [a, v] of ipler) { buda(v, simdi, 24 * 3600e3); if (!v.length) ipler.delete(a); }
      return true;
    },
    /** Aynı içerik kısa sürede ikinci kez gelirse true (yazılmaz). İçerik tuzlu özet olarak tutulur, 30 dk sonra unutulur. */
    tekrarMi(dosya, kayit, simdi = Date.now()) {
      const { zaman, ...icerik } = kayit, k = ozet(dosya + JSON.stringify(icerik));
      for (const [a, t] of tekrar) if (simdi - t > tekrarSure) tekrar.delete(a);
      if (tekrar.has(k)) return true;
      tekrar.set(k, simdi); if (tekrar.size > 5000) tekrar.delete(tekrar.keys().next().value);
      return false;
    },
    /** Yazım başarısız olduysa özet geri alınır: kullanıcı aynı içerikle yeniden deneyebilsin. */
    unut(dosya, kayit) { const { zaman, ...icerik } = kayit; tekrar.delete(ozet(dosya + JSON.stringify(icerik))); },
  };
}

// --- GitHub ------------------------------------------------------------------------------------------------------
class GithubHatasi extends Error { constructor(kod, durum) { super(kod); this.kod = kod; this.durum = durum; } }   // mesajda içerik/token yok
const ozelDepoOnbellek = new Map();     // "depo" -> bitiş zamanı (yalnızca olumlu sonuç, 6 saat)

function ghIstegi(cfg, ekstra = {}) {
  return { ...ekstra, signal: AbortSignal.timeout(7000), headers: { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "plakatahmini-geri-bildirim", ...(ekstra.body ? { "Content-Type": "application/json" } : {}) } };
}
async function depoOzelMi(cfg, f, simdi) {
  if ((ozelDepoOnbellek.get(cfg.repo) || 0) > simdi) return;
  const r = await f(`https://api.github.com/repos/${cfg.repo}`, ghIstegi(cfg));
  if (!r.ok) throw new GithubHatasi("depo_okunamadi", r.status);
  const j = await r.json();
  if (j.private !== true) throw new GithubHatasi("depo_ozel_degil", 0);
  ozelDepoOnbellek.set(cfg.repo, simdi + 6 * 3600e3);
}
/**
 * Satırı dosyanın sonuna ekler (GitHub Contents API). SHA çakışmasında (409, ya da eşzamanlı ilk oluşturmada 422) üstel geri çekilmeyle
 * en fazla `deneme` kez yeniden dener; süre bütçesi aşılırsa vazgeçer. Başarısızlıkta GithubHatasi fırlatır (yanıltıcı başarı yok).
 */
async function ekle(cfg, dosya, satir, { fetch: f = globalThis.fetch, bekle = ms => new Promise(r => setTimeout(r, ms)), simdi = () => Date.now(), deneme = 5, butceMs = 8000, mesaj = "Geri bildirim: yeni kayıt [skip ci]" } = {}) {
  const baslangic = simdi();
  await depoOzelMi(cfg, f, baslangic);
  const url = `https://api.github.com/repos/${cfg.repo}/contents/${dosya.split("/").map(encodeURIComponent).join("/")}`;
  for (let i = 0; i < deneme; i++) {
    const g = await f(`${url}?ref=${encodeURIComponent(cfg.dal)}`, ghIstegi(cfg));
    let icerik = "", sha = null;
    if (g.status === 404) { /* dosya henüz yok: oluşturulacak */ }
    else if (!g.ok) throw new GithubHatasi("okuma", g.status);
    else {
      const j = await g.json();
      if (j.type !== "file" || j.encoding !== "base64" || typeof j.content !== "string") throw new GithubHatasi("dosya_okunamadi", 0);   // >1 MB dosyalarda içerik boş gelir
      icerik = Buffer.from(j.content, "base64").toString("utf8"); sha = j.sha;
      if (Buffer.byteLength(icerik) > SINIRLAR.dosyaMax) throw new GithubHatasi("dosya_cok_buyuk", 0);
    }
    const yeni = (icerik === "" || icerik.endsWith("\n") ? icerik : icerik + "\n") + satir;
    const p = await f(url, ghIstegi(cfg, { method: "PUT", body: JSON.stringify({ message: mesaj, content: Buffer.from(yeni, "utf8").toString("base64"), branch: cfg.dal, ...(sha ? { sha } : {}) }) }));
    if (p.status === 200 || p.status === 201) return;
    if ((p.status === 409 || p.status === 422) && i < deneme - 1 && simdi() - baslangic < butceMs) { await bekle(Math.min(1500, 60 * 2 ** i) + Math.floor(Math.random() * 60)); continue; }
    throw new GithubHatasi(p.status === 409 || p.status === 422 ? "cakisma" : "yazma", p.status);
  }
  throw new GithubHatasi("cakisma", 409);
}

module.exports = { SINIRLAR, ILK_YIL, BILDIRIM_TURLERI, yapilandirma, metin, satirYap, sayfaYolu, spamMi, tarihDogrula, plakaDogrula, dogrula, sinirlayici, ekle, GithubHatasi, ozelDepoOnbellek };
