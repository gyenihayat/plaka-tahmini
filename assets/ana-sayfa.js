// Ana sayfa: (1) üç büyük ilin güncel tahmini plaka (il kodu + harf serisi + 3 haneli sıra) kartlarını ortak motorla günceller, (2) il adı/plaka kodu ile il sayfasına yönlendirir.
// Klasik script: sayfadaki DATA, byName ve REF (index.html) ile ortak motorun (tahmin-motoru.js) global bildirimlerini kullanır; index.html'in inline betiğinden SONRA yüklenir.
// (3) "Belirli bir tarihte hangi plakada?" aracını (ortak kod: tarih-sorgu.js) bağlar ve ikincil "81 ilin bu tarihteki tahminleri" tablosunu çizer.
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
  // Tüm iller tablosu (ikincil eylem, varsayılan kapalı): seçili tarihin plakaları AYNI ortak fonksiyonla (PlakaTarih.plakaGun) hesaplanır; hız/seri süresi ortak motorun tek hız tanımıdır.
  function tabloKur(doc) {
    const btn = doc.getElementById("btn-all"), wrap = doc.getElementById("all-wrap"), t = doc.getElementById("all-tbl"), dt = doc.getElementById("dt"), atla = doc.getElementById("excl"); if (!btn || !wrap || !t || !dt) return;
    const ETIKET = btn.textContent; let acik = false;
    const plakaMetin = (s, gun) => { const p = PlakaTarih.plakaDurum(s, gun); return { p, m: p.iv ? p.iv.let + " " + String(p.iv.num).padStart(3, "0") : "—" }; };
    function ciz() { if (acik) PlakaTarih.atlaIle(atla ? atla.value : "", ciz2); }       // tablo, tarih aracıyla AYNI atlanacak serilerle hesaplanır (varsayılan: hiçbiri); hedef aracının kalıcı ayarı kullanılmaz
    function ciz2() {
      const secili = dt.value && /^\d{4}-\d{2}-\d{2}$/.test(dt.value) ? dt.value : isoToday, day = toDay(secili), farkli = secili !== isoToday;
      t.innerHTML = ""; const atlaEtiket = PlakaTarih.atlaCoz(atla ? atla.value : "").etiket;
      const ilkGun = DATA.iller[0].obs[0][0];
      if (farkli && day < ilkGun) { const cap = doc.createElement("caption"); cap.textContent = day < GERI_SINIR_GUN ? PlakaTarih.SINIR_MESAJI : "≈ geriye dönük tahmin (bu tarih için kayıt yok; belirsizlik büyüktür; Ankara tarihsel referansla kalibre edilmiştir, 1 Haziran 2020 öncesi için çok kabadır). — : model geçerli plaka üretemiyor."; cap.style.cssText = "text-align:left;padding:6px 10px;font-size:14px"; t.appendChild(cap); }
      if (atlaEtiket.length) { const cap = doc.createElement("caption"); cap.textContent = "Atlanacak seriler uygulandı: " + atlaEtiket.join(" · ") + "."; cap.style.cssText = "text-align:left;padding:6px 10px;font-size:14px"; t.appendChild(cap); }
      const th = doc.createElement("thead"), hr = doc.createElement("tr");
      ["Kod", "İl", "Son veri", "Tarih", "Bugün (tahmin)", farkli ? "Seçili tarihte (" + dstr(day) + ")" : "", "Hız (sıra/gün)", "Bir seri (gün)", "Güvenilirlik"].filter(x => x !== "").forEach(h => { const c = doc.createElement("th"); c.textContent = h; hr.appendChild(c); });
      th.appendChild(hr); t.appendChild(th);
      const tb = doc.createElement("tbody");
      DATA.iller.forEach(s => {
        const kod = String(s.kod).padStart(2, "0"), last = s.obs[s.obs.length - 1], li = invN(last[1]), f = fit(s, last[0]);
        const cells = [kod, s.il, li.let + " " + String(li.num).padStart(3, "0"), dstr(last[0]), plakaMetin(s, todayDay).m];
        if (farkli) { const e = plakaMetin(s, day); cells.push(e.p.iv ? e.m + (e.p.durum === "kayit" ? " ✓" : e.p.durum === "geri" ? " ≈" : "") : "—"); }       // ✓ kayıtlı veri, ≈ geriye dönük tahmin, — tahmin üretilemiyor (aynı kurallar tarih aracıyla)
        cells.push(fmt(yuvarla(f.slope)), seriGun(f.slope));
        const r = doc.createElement("tr");
        cells.forEach((c, j) => { const td = doc.createElement("td"); td.textContent = c; if (j === 2 || j === 4 || (farkli && j === 5)) td.className = "mono"; if (j >= cells.length - 2) td.className = "n"; r.appendChild(td); });
        const td = doc.createElement("td"); td.innerHTML = relDot(s); r.appendChild(td); tb.appendChild(r);
      });
      t.appendChild(tb);
    }
    btn.addEventListener("click", () => { acik = !acik; wrap.hidden = !acik; btn.setAttribute("aria-expanded", acik ? "true" : "false"); btn.textContent = acik ? "Tabloyu gizle" : ETIKET; ciz(); });
    dt.addEventListener("input", ciz); dt.addEventListener("change", ciz); if (atla) atla.addEventListener("input", ciz);
  }
  // İl seçimi bu araca aittir: başlangıçta ana sayfanın mevcut varsayılanı (İstanbul ya da ?il=NN) kopyalanır, sonra hedef plaka aracındaki seçimden BAĞIMSIZ çalışır.
  function tarihAraci(doc) {
    const tIl = doc.getElementById("tarih-il"), hIl = doc.getElementById("il"); if (!tIl || !hIl || typeof PlakaTarih === "undefined") return;
    tIl.innerHTML = hIl.innerHTML; tIl.value = hIl.value;
    PlakaTarih.kur(doc, { onek: "ana", s: () => byName[tIl.value], ref: REF, olay, secim: tIl });
    tabloKur(doc);
  }
  function uyar(doc, mesaj) { const u = doc.getElementById("kart-uyari"); if (u) { u.textContent = mesaj; u.hidden = false; } }

  function baslat() {
    try {
      kartlariGuncelle(document, byName, REF);
      if (REF.kapsamDisi) uyar(document, "Resmî tatil takvimi bu tarihi kapsamıyor; hafta sonu dışındaki tatillerde güncel tahmin en yakın iş gününe çekilmemiş olabilir.");
    } catch (err) { console.error("plakatahmini: kartlar güncellenemedi", err); uyar(document, "Canlı güncelleme yapılamadı; kartlardaki değerler belirtilen tarih itibarıyla hesaplanmıştır."); }
    try { tarihAraci(document); } catch (err) { console.error("plakatahmini: tarih aracı kurulamadı", err); }
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
