// Ana sayfa: (1) üç büyük ilin güncel tahmini plaka (il kodu + harf serisi + 3 haneli sıra) kartlarını ortak motorla günceller, (2) il adı/plaka kodu ile il sayfasına yönlendirir.
// Klasik script: sayfadaki DATA, byName ve REF (index.html) ile ortak motorun (tahmin-motoru.js) global bildirimlerini kullanır; index.html'in inline betiğinden SONRA yüklenir.
// Kartlar il sayfalarındaki büyük tahminle AYNI fonksiyonu (guncelSeriBilgisi) ve AYNI referans günü (trReferansGun) kullanır; hesap burada tekrarlanmaz.
const PlakaAnaSayfa = (function () {
  // Türkçe duyarsız karşılaştırma anahtarı: "İstanbul", "ISTANBUL", "istanbul" -> "istanbul"; "Iğdır" -> "igdir"
  const trNorm = t => String(t == null ? "" : t).replace(/\u0307/g, "").replace(/İ/g, "i").replace(/I/g, "ı").toLowerCase().replace(/ı/g, "i").replace(/ç/g, "c").replace(/ğ/g, "g")
    .replace(/ö/g, "o").replace(/ş/g, "s").replace(/ü/g, "u").replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();

  // liste: [{ad, kod, slug}]. Sonuç: {tip: "tamam", il} | "bos" | "yok" | "belirsiz" (adaylar) | "celisik" (il)
  function ilBul(metin, liste) {
    const t = trNorm(metin); if (!t) return { tip: "bos" };
    const kodlar = (t.match(/\b\d{1,2}\b/g) || []), ad = t.replace(/\b\d{1,2}\b/g, " ").replace(/\s+/g, " ").trim(), kod = kodlar.length ? +kodlar[0] : null;
    if (/\d/.test(ad) || kodlar.length > 1) return { tip: "yok" };
    if (!ad) { const il = liste.find(i => i.kod === kod); return il ? { tip: "tamam", il } : { tip: "yok" }; }       // yalnızca kod (1-81)
    let adaylar = liste.filter(i => trNorm(i.ad) === ad);
    if (!adaylar.length) adaylar = liste.filter(i => trNorm(i.ad).startsWith(ad));
    if (!adaylar.length) return { tip: "yok" };
    if (adaylar.length > 1) return { tip: "belirsiz", adaylar };
    if (kod != null && adaylar[0].kod !== kod) return { tip: "celisik", il: adaylar[0] };
    return { tip: "tamam", il: adaylar[0] };
  }
  const MESAJ = (o, girdi) => {
    if (o.tip === "bos") return "Bir il adı ya da plaka kodu yazın.";
    if (o.tip === "yok") return "“" + String(girdi).trim() + "” için il bulunamadı. İl adını ya da 1–81 arası plaka kodunu yazın.";
    if (o.tip === "belirsiz") return "Birden fazla il eşleşti: " + o.adaylar.slice(0, 6).map(i => i.ad).join(", ") + (o.adaylar.length > 6 ? " ve diğerleri" : "") + ". Daha fazla harf yazın.";
    if (o.tip === "celisik") return o.il.ad + " ilinin plaka kodu " + String(o.il.kod).padStart(2, "0") + " (yazdığınız kod farklı).";
    return "";
  };

  function kartlariGuncelle(doc, iller, ref) {
    doc.querySelectorAll(".kart[data-il]").forEach(k => {
      const s = iller[k.getAttribute("data-il")]; if (!s) throw new Error("kart ili veride yok: " + k.getAttribute("data-il"));
      const b = guncelSeriBilgisi(s, ref.gun); if (!b) throw new Error("tahmin alfabe dışında");
      k.querySelector('[data-kart="plaka"]').textContent = b.plaka; k.querySelector('[data-kart="tarih"]').textContent = b.tarih;
    });
  }
  // Analitik olayı (olcum.js yüklü değilse ya da üretimde değilsek sessizce yok sayılır); yalnızca sabit olay adları, içerik gönderilmez
  const olay = ad => { try { if (typeof PlakaOlcum !== "undefined") PlakaOlcum.olay(ad); } catch (e) { /* ölçüm hatası sayfayı etkilemez */ } };
  function uyar(doc, mesaj) { const u = doc.getElementById("kart-uyari"); if (u) { u.textContent = mesaj; u.hidden = false; } }

  function baslat() {
    try {
      kartlariGuncelle(document, byName, REF);
      if (REF.kapsamDisi) uyar(document, "Resmî tatil takvimi bu tarihi kapsamıyor; hafta sonu dışındaki tatillerde güncel tahmin en yakın iş gününe çekilmemiş olabilir.");
    } catch (err) { console.error("plakatahmini: kartlar güncellenemedi", err); uyar(document, "Canlı güncelleme yapılamadı; kartlardaki değerler belirtilen tarih itibarıyla hesaplanmıştır."); }
    const form = document.getElementById("il-form"), giris = document.getElementById("il-ara"), hata = document.getElementById("il-hata");
    if (!form || !giris) return;
    const liste = [].map.call(document.querySelectorAll("#il-liste option"), o => ({ ad: o.getAttribute("data-ad"), kod: +o.getAttribute("data-kod"), slug: o.getAttribute("data-slug") }));
    form.addEventListener("submit", e => {
      e.preventDefault(); const o = ilBul(giris.value, liste);
      if (o.tip === "tamam") { hata.textContent = ""; olay("ana-il-ara"); location.assign("/il/" + o.il.slug); return; }
      olay("ana-il-ara-hata"); hata.textContent = MESAJ(o, giris.value); giris.focus();
    });
    // Üç büyük il kartı: tıklama (kart adresi herkese açık il adresidir)
    document.querySelectorAll(".kart[data-il]").forEach(k => k.addEventListener("click", () => olay("ana-kart-tikla/" + String(k.getAttribute("href")).replace(/^\/il\//, ""))));
    // Hesaplayıcı: index.html'deki calcTarget işleyicileri bu dinleyicilerden ÖNCE çalışır; sonuç kutusunun görünürlüğü sonucu söyler (içerik okunmaz/gönderilmez)
    const sonuc = () => olay(document.getElementById("target-res").style.display === "none" ? "ana-hesapla-hata" : "ana-hesapla-sonuc");
    const hBtn = document.getElementById("btn-target"), hGiris = document.getElementById("target");
    if (hBtn) hBtn.addEventListener("click", () => { olay("ana-hesapla-basla"); sonuc(); });
    if (hGiris) hGiris.addEventListener("keydown", e => { if (e.key === "Enter") { olay("ana-hesapla-basla"); sonuc(); } });
    const cta = document.querySelector('a.cta[href="#hesapla"]');
    if (cta) cta.addEventListener("click", () => setTimeout(() => { const h = document.getElementById("target"); if (h) h.focus({ preventScroll: true }); }, 0));
  }
  if (typeof document !== "undefined" && typeof DATA !== "undefined") baslat();
  return { ilBul, trNorm, MESAJ, kartlariGuncelle };
})();
