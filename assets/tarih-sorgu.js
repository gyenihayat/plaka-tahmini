// "Belirli bir tarihte hangi plakada?" aracı: ana sayfa ve 81 il sayfasının ORTAK kodu (tek mantık, tek DOM bağlama).
// Hesabın kendisi ortak motordan gelir (tahmin-motoru.js: estimateAt, invN, exclOverlap, toDay, trTarihGun); burada formül yoktur, yalnızca sorgunun
// girdisi doğrulanır, sonuç ve uyarı metinleri üretilir ve form bağlanır. Elle seçilen tarih kendiliğinden önceki iş gününe ÇEKİLMEZ (motorun değeri gösterilir).
// Klasik script: tahmin-motoru.js'in global bildirimlerini (EXCL dahil) kullanır; önce o yüklenmelidir.
// ATLANACAK SERİLER: bu aracın kendi alanı vardır (iki sayfada aynı: #excl); varsayılan BOŞTUR ve yalnızca bu aracın hesabı süresince uygulanır (atlaIle: EXCL geçici ayarlanır, sonra eski değeri geri yazılır).
// Ana sayfadaki hedef plaka aracının kalıcı "pt-excl" ayarı (global EXCL) tarih sonucunu GİZLİCE etkilemez; seri atlandıysa sonuçta açıkça yazılır.
const PlakaTarih = (function () {
  const KAPSAM_DISI = "Resmî tatil takvimi bu tarihi kapsamıyor; hafta sonu dışındaki tatiller için güncel tahmin en yakın iş gününe çekilmemiş olabilir.";
  const plakaMetni = (s, iv) => String(s.kod).padStart(2, "0") + " " + iv.let + " " + String(iv.num).padStart(3, "0");     // il kodu + 3 harf + 3 haneli sıra (baştaki sıfırlar korunur)

  // Bir ilin verilen gündeki tahmini (ya da kayıtlı) plakası; ana sayfa aracı, il sayfası aracı ve tüm iller tablosu AYNI fonksiyonu kullanır.
  function plakaGun(s, gun) { const est = estimateAt(s, gun), iv = invN(est.n); return { est, iv, plaka: iv ? plakaMetni(s, iv) : null }; }

  function isoGecerli(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "")); if (!m || +m[1] < 1000) return false;
    const d = new Date(0); d.setUTCFullYear(+m[1], +m[2] - 1, +m[3]); return d.toISOString().slice(0, 10) === iso;
  }

  // Atlanacak seri metni -> {aralik: motorun [başlangıç, bitiş, etiket] aralıkları, bad: anlaşılamayan girdiler, etiket: uygulanan serilerin adları}
  function atlaCoz(metin) { const px = parseExcl(String(metin || "")); return { aralik: px.intervals, bad: px.bad, etiket: px.intervals.map(x => x[2]) }; }
  // fn'yi yalnızca verilen atlanacak serilerle (boşsa hiçbiri) çalıştırır; global EXCL (hedef aracının ayarı) geçici olarak yok sayılır ve geri yazılır.
  function atlaIle(metin, fn) { const eski = EXCL; EXCL = atlaCoz(metin).aralik; try { return fn(); } finally { EXCL = eski; } }
  const ATLA_UYARI = bad => "Anlaşılamayan seri girişleri: " + bad.join(", ") + " (X yalnız sonda joker olabilir; ilk/son harfte I-O olamaz)";

  // s: il verisi; iso: "YYYY-MM-DD"; ref: trReferansGun() sonucu (yalnızca takvim kapsamı uyarısı için). Dönüş: {tip:"hata", mesaj} | {tip:"sonuc", plaka, kayit, err, tarih, uyari}
  function sorgula(s, iso, ref, atlaMetni) {
    if (!isoGecerli(iso)) return { tip: "hata", mesaj: "Lütfen geçerli bir tarih seçin." };
    const atla = atlaCoz(atlaMetni).etiket;
    return atlaIle(atlaMetni, () => {
      const gun = toDay(iso), p = plakaGun(s, gun), est = p.est;
      if (!p.iv) return { tip: "hata", mesaj: "Bu tarih için tahmin üretilemedi: seri alfabesinin dışına çıkılıyor. Daha yakın bir tarih deneyin." };
      const last = s.obs[s.obs.length - 1]; let uyari = "";
      if (!est.real && EXCL.length) {
        const atlanan = exclOverlap(last[1], est.n, EXCL);
        if (atlanan > 0) uyari = "Bu tahmin, atlanacak girdiğiniz " + Math.round(atlanan / 1000) + " serinin (" + EXCL.map(x => x[2]).join(" · ") + ") üstünden atlanarak hesaplandı.";
      }
      if (!est.real && invN(last[1]).let[0] !== p.iv.let[0])
        uyari = (uyari ? uyari + " — " : "") + "Tahmin bir harf grubu sınırını aşıyor (" + invN(last[1]).let[0] + " → " + p.iv.let[0] + "). Grup geçişlerinde il bazlı atlamalar (rezerve harfler, isim serileri) tahmini kaydırabilir" +
          (s.il === "İstanbul" ? " — İstanbul'da R'den sonra S (misafir) ve T (taksi) gruplarının atlanması bekleniyor." : ".");
      if (ref && ref.kapsamDisi && iso === ref.iso) uyari = (uyari ? uyari + " — " : "") + KAPSAM_DISI;
      if (est.extrap === "öncesi") uyari = "Seçilen tarih veri başlangıcından (" + dstr(s.obs[0][0]) + ") önce; ilk gözlem gösteriliyor.";
      return { tip: "sonuc", plaka: p.plaka, kayit: !!est.real, err: est.err, tarih: trTarihGun(gun), uyari, atla };
    });
  }

  // Sayfadaki standart işaretlemeyi (tarih-form, dt, tarih-sonuc ...; generate_il_pages.py üretir) bağlar.
  // o: { onek: "ana"|"il" (analitik olay öneki), s: () => il verisi, ref: trReferansGun(), olay: ad => void, secim?: <select> (ana sayfa: ilin değişmesi sonucu temizler) }
  // Analitiğe yalnızca sabit olay adları gider (onek + "-tarih-hesapla|sonuc|hata"); seçilen tarih, plaka ya da il gönderilmez.
  function kur(doc, o) {
    const g = id => doc.getElementById(id), govde = g("tarih-govde"), form = g("tarih-form"), dt = g("dt"), sonuc = g("tarih-sonuc"), hata = g("tarih-hata"), uyari = g("tarih-uyari");
    const atlaAlan = g("excl"), atlaUyari = g("excl-warn"), atlaBilgi = g("tarih-atla-bilgi");           // bu aracın KENDİ atlanacak seri alanı (varsayılan boş, kalıcı değil)
    const atlaMetni = () => atlaAlan ? atlaAlan.value : "";
    if (!govde || !form || !dt || !sonuc) return null;
    const olay = ek => { try { if (o.olay) o.olay(o.onek + "-tarih-" + ek); } catch (e) { /* ölçüm hatası aracı etkilemez */ } };
    dt.value = o.ref.iso;                                                    // varsayılan: güncel tahminin referans günü (ana sayfanın mevcut varsayılanı); sonuç hesaplanana kadar GÖSTERİLMEZ
    function temizle() { sonuc.hidden = true; uyari.hidden = true; uyari.textContent = ""; hata.textContent = ""; g("plate-num").textContent = ""; g("tarih-out").textContent = ""; atlaBilgi.hidden = true; atlaBilgi.textContent = ""; }
    function atlaUyarisi() { if (!atlaUyari) return; const c = atlaCoz(atlaMetni()); atlaUyari.hidden = !c.bad.length; atlaUyari.textContent = c.bad.length ? ATLA_UYARI(c.bad) : ""; }
    function hesapla(olayli) {
      if (olayli) olay("hesapla");
      const r = sorgula(o.s(), dt.value, o.ref, atlaMetni()); atlaUyarisi();
      if (r.tip === "hata") { temizle(); hata.textContent = r.mesaj; if (olayli) olay("hata"); return r; }
      hata.textContent = ""; g("plate-num").textContent = r.plaka;
      const etiket = g("tag"); etiket.textContent = r.kayit ? "Kayıtlı veri" : "Tahmin"; etiket.className = "t-etiket " + (r.kayit ? "kayit" : "tahmin");
      g("tarih-out").textContent = r.tarih + (r.kayit ? " · kayıtlı gözlemlere göre" : " · ±" + r.err + " gün");
      sonuc.hidden = false; uyari.textContent = r.uyari; uyari.hidden = !r.uyari;
      // atlanacak seri kullanıldıysa sonuçta AÇIKÇA yazılır (ayar yoksa hiçbir ek metin yok); kayıtlı veri tarihlerinde etkisi olmadığı da belirtilir
      atlaBilgi.textContent = !r.atla.length ? "" : r.kayit ? "Atlanacak seriler (" + r.atla.join(" · ") + ") kayıtlı veri tarihini etkilemez." : "Atlanacak seriler uygulandı: " + r.atla.join(" · ") + ".";
      atlaBilgi.hidden = !r.atla.length;
      if (olayli) olay("sonuc"); return r;
    }
    form.addEventListener("submit", e => { e.preventDefault(); hesapla(true); });
    dt.addEventListener("input", temizle); dt.addEventListener("change", temizle);                    // girdi değişince eski sonuç kalmaz (girdi ile sonuç hiçbir zaman uyuşmaz durumda olmaz)
    if (o.secim) o.secim.addEventListener("change", temizle);
    if (atlaAlan) atlaAlan.addEventListener("input", () => { atlaUyarisi(); if (!sonuc.hidden) hesapla(false); });   // atlanacak seriler değişti -> görünen sonuç sessizce (analitiksiz) yenilenir
    govde.hidden = false;
    return { hesapla, temizle };
  }
  return { plakaGun, sorgula, kur, plakaMetni, atlaCoz, atlaIle };
})();
