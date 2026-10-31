/**
 * POST /api/geri-bildirim — /geri-bildirim sayfasındaki iki formu (plaka bilgisi, öneri/hata) alır ve ÖZEL bir GitHub deposuna JSONL olarak ekler.
 *
 *   ziyaretçi formu -> bu fonksiyon (doğrulama, hız sınırı) -> GitHub Contents API -> özel depo: oneriler.txt / plaka_bildirimleri.txt
 *
 * Vercel ortam değişkenleri (Settings -> Environment Variables; hiçbiri istemciye gitmez):
 *   GITHUB_TOKEN                     zorunlu   Yalnızca hedef depoya "Contents: Read and write" izni olan fine-grained token
 *   GERI_BILDIRIM_REPO               zorunlu   "sahip/depo" — ÖZEL depo; sitenin kendi deposu olamaz, özel değilse yazılmaz
 *   GERI_BILDIRIM_BRANCH             isteğe bağlı, varsayılan main
 *   GERI_BILDIRIM_ONERI_DOSYASI      isteğe bağlı, varsayılan oneriler.txt
 *   GERI_BILDIRIM_PLAKA_DOSYASI      isteğe bağlı, varsayılan plaka_bildirimleri.txt
 *   GERI_BILDIRIM_ORIGINLER          isteğe bağlı, virgülle ayrılmış izinli kökenler (varsayılan: https://plakatahmini.com, https://www.plakatahmini.com)
 * Ayrıntı ve kurulum adımları: README.md ("Kullanıcı katkı sistemi").
 */
"use strict";
const C = require("./_geri-bildirim.js");

const MESAJLAR = {
  yontem: "Yalnızca POST.", kokenYok: "İstek kabul edilmedi.", tur: "İstek kabul edilmedi.", buyuk: "Gönderilen içerik çok büyük.",
  kapali: "Bildirim alma şu an kapalı. Lütfen daha sonra tekrar deneyin.", sinir: "Kısa sürede çok fazla gönderim yapıldı. Lütfen biraz bekleyip tekrar deneyin.",
  kaydedilemedi: "Bildiriminiz kaydedilemedi. Lütfen biraz sonra tekrar deneyin.",
};

function ip(req) {
  const h = req.headers || {};
  return String(h["x-vercel-forwarded-for"] || h["x-real-ip"] || String(h["x-forwarded-for"] || "").split(",")[0] || "").trim();
}
function koken(req) {
  const h = req.headers || {};
  if (h.origin) return h.origin === "null" ? null : h.origin;
  try { return h.referer ? new URL(h.referer).origin : null; } catch (e) { return null; }
}
function govde(req) {
  let b = req.body;           // Vercel JSON gövdeyi ayrıştırır; bozuk JSON'da erişim hata fırlatabilir
  if (Buffer.isBuffer(b)) b = b.toString("utf8");
  if (typeof b === "string") { if (Buffer.byteLength(b) > C.SINIRLAR.govde) return { buyuk: true }; try { b = JSON.parse(b); } catch (e) { return null; } }
  if (b && typeof b === "object" && Buffer.byteLength(JSON.stringify(b)) > C.SINIRLAR.govde) return { buyuk: true };
  return b;
}

/** Test için bağımlılıkları (fetch, saat, bekleme, ortam, sınırlayıcı) enjekte edilebilir işleyici üretir. */
function olustur({ env, fetch: f, simdi = () => Date.now(), bekle, sinir = C.sinirlayici() } = {}) {
  return async function handler(req, res) {
    const yanit = (durum, gov) => { res.setHeader("Cache-Control", "no-store"); res.setHeader("X-Content-Type-Options", "nosniff"); return res.status(durum).json(gov); };
    const hata = (durum, mesaj, alan) => yanit(durum, { ok: false, error: mesaj, ...(alan ? { alan } : {}) });

    if (req.method !== "POST") { res.setHeader("Allow", "POST"); return hata(405, MESAJLAR.yontem); }

    const cfg = C.yapilandirma(env || process.env);
    if (cfg.hata) { console.error("geri-bildirim: yapılandırma eksik:", cfg.hata); return hata(503, MESAJLAR.kapali); }

    const k = koken(req);
    if (!k || !cfg.izinli.includes(k)) return hata(403, MESAJLAR.kokenYok);
    if (!/^application\/json\b/i.test(String((req.headers || {})["content-type"] || ""))) return hata(415, MESAJLAR.tur);
    if (Number((req.headers || {})["content-length"]) > C.SINIRLAR.govde) return hata(413, MESAJLAR.buyuk);

    let b;
    try { b = govde(req); } catch (e) { b = null; }
    if (b && b.buyuk) return hata(413, MESAJLAR.buyuk);

    const s = C.dogrula(b, simdi());
    if (s.hata) return hata(400, s.hata, s.alan);

    if (!sinir.izin(ip(req), simdi())) return hata(429, MESAJLAR.sinir);
    if (sinir.tekrarMi(s.dosya, s.kayit, simdi())) return yanit(200, { ok: true, tekrar: true });      // aynı içerik az önce alındı; ikinci satır yazılmaz

    try {
      await C.ekle(cfg, cfg.dosyalar[s.dosya], C.satirYap(s.kayit), {
        fetch: f || globalThis.fetch, simdi, ...(bekle ? { bekle } : {}),
        mesaj: s.dosya === "plaka" ? "Geri bildirim: yeni plaka bildirimi [skip ci]" : "Geri bildirim: yeni öneri/hata kaydı [skip ci]",
      });
    } catch (e) {
      sinir.unut(s.dosya, s.kayit);
      console.error("geri-bildirim: kayıt başarısız:", e && e.kod ? e.kod : "bilinmiyor", e && e.durum ? e.durum : "");      // yalnızca kod ve durum: içerik/token loga girmez
      return hata(500, MESAJLAR.kaydedilemedi);
    }
    return yanit(200, { ok: true });
  };
}

module.exports = olustur();
module.exports.olustur = olustur;
