// "Belirli bir tarihte hangi plakada?" aracı: ana sayfa ve 81 il sayfasının ORTAK kodu (tek mantık, tek DOM bağlama).
// Hesabın kendisi ortak motordan gelir (tahmin-motoru.js: estimateAt, invN, exclOverlap, toDay, trTarihGun); burada formül yoktur, yalnızca sorgunun
// girdisi doğrulanır, sonuç ve uyarı metinleri üretilir ve form bağlanır. Elle seçilen tarih kendiliğinden önceki iş gününe ÇEKİLMEZ (motorun değeri gösterilir).
// Klasik script: tahmin-motoru.js'in global bildirimlerini (EXCL dahil) kullanır; önce o yüklenmelidir.
// GERİYE DÖNÜK TARİH: ilk kayıtlı gözlemden önceki günler motorun geriye modeliyle (estimateBack = backEstimate'in tersi) hesaplanır ve "Geriye dönük tahmin" olarak, artan belirsizlikle gösterilir.
// Sınırlar: (1) MODEL tarih alt sınırı 1 Şubat 2018 (bu aracın uyguladığı kural; üç harf–üç rakam plakaların fiilen dağıtılmaya başladığı gün olarak sunulmaz); (2) model geçerli plaka üretemiyorsa (sıra < 1) plaka uydurulmaz. Modelin sayısal alt sınırı ilin gerçek dağıtım başlangıcı değildir ve "o tarihte plaka dağıtılmadı" anlamına gelmez.
// ATLANACAK SERİLER: bu aracın kendi alanı vardır (iki sayfada aynı: #excl); varsayılan BOŞTUR ve yalnızca bu aracın hesabı süresince uygulanır (atlaIle: EXCL geçici ayarlanır, sonra eski değeri geri yazılır).
// Ana sayfadaki hedef plaka aracının kalıcı "pt-excl" ayarı (global EXCL) tarih sonucunu GİZLİCE etkilemez; seri atlandıysa sonuçta açıkça yazılır.
const PlakaTarih = (function () {
  const KAPSAM_DISI = "Resmî tatil takvimi bu tarihi kapsamıyor; hafta sonu dışındaki tatiller için güncel tahmin en yakın iş gününe çekilmemiş olabilir.";
  const plakaMetni = (s, iv) => String(s.kod).padStart(2, "0") + " " + iv.let + " " + String(iv.num).padStart(3, "0");     // il kodu + 3 harf + 3 haneli sıra (baştaki sıfırlar korunur)

  // Bir ilin verilen gündeki plakası (kayıtlı / tahmin / geriye dönük tahmin) ve durumu; ana sayfa aracı, il sayfası aracı ve 81 il tablosu AYNI fonksiyonu kullanır.
  // durum: "kayit" | "tahmin" | "geri" | "sinir" (model tarih sınırı: 1 Şubat 2018 öncesi) | "model" (geriye model geçerli plaka üretemiyor) | "alfabe" (ileride seri alfabesi bitiyor)
  function plakaDurum(s, gun) {
    if (gun < GERI_SINIR_GUN) return { durum: "sinir", plaka: null };
    const est = estimateAt(s, gun);
    if (est.back && Math.round(est.n) < 1) return { durum: "model", plaka: null, est };       // sıra < 1: geçerli plaka yok (AAA 001'den önce); "AAA 001" tekrarı/uydurması yapılmaz
    const iv = invN(est.n); if (!iv) return { durum: "alfabe", plaka: null, est };
    return { durum: est.back ? "geri" : est.real ? "kayit" : "tahmin", est, iv, plaka: plakaMetni(s, iv) };
  }
  // Geriye dönük belirsizlik (yaklaşık, sezgisel; istatistiksel aralık değildir): ±%25 (≤ 1 yıl; hold-out backtest'te ≈ %91 kapsama), 1 yıldan sonra yılda +%5, en çok %50; en az ±10 gün.
  // Kademe: ≤ 365 gün "Geriye dönük tahmin", ≤ 730 gün "Kaba geriye dönük tahmin", daha uzak "Çok kaba geriye dönük tahmin".
  function geriBelirsizlik(h) {
    const oran = geriOran(h), kademe = h <= 365 ? "geri" : h <= 730 ? "kaba" : "cokkaba";
    return { err: Math.max(10, Math.round(oran * h)), kademe, etiket: { geri: "Geriye dönük tahmin", kaba: "Kaba geriye dönük tahmin", cokkaba: "Çok kaba geriye dönük tahmin" }[kademe] };
  }
  const SINIR_MESAJI = "Bu tarih için tahmin üretilemiyor: bu araç 1 Şubat 2018'den önceki tarihler için tahmin üretmiyor. Bu, modelin uyguladığı bir tarih sınırıdır; üç harf–üç rakam plakaların dağıtımının başladığı gün anlamına gelmez.";
  const MODEL_MESAJI = "Bu tarih için tahmin üretilemiyor: hesaplama modeli bu ilde bu tarih için geçerli bir plaka serisi bulamıyor. Bu, ilin gerçek plaka dağıtım başlangıcı anlamına gelmez; o tarihte plaka dağıtılmadığı anlamına da gelmez.";

  function isoGecerli(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "")); if (!m || +m[1] < 1000) return false;
    const d = new Date(0); d.setUTCFullYear(+m[1], +m[2] - 1, +m[3]); return d.toISOString().slice(0, 10) === iso;
  }

  // Atlanacak seri metni -> {aralik: motorun [başlangıç, bitiş, etiket] aralıkları, bad: anlaşılamayan girdiler, etiket: uygulanan serilerin adları}
  function atlaCoz(metin) { const px = parseExcl(String(metin || "")); return { aralik: px.intervals, bad: px.bad, etiket: px.intervals.map(x => x[2]) }; }
  // fn'yi yalnızca verilen atlanacak serilerle (boşsa hiçbiri) çalıştırır; global EXCL (hedef aracının ayarı) geçici olarak yok sayılır ve geri yazılır.
  function atlaIle(metin, fn) { const eski = EXCL; EXCL = atlaCoz(metin).aralik; try { return fn(); } finally { EXCL = eski; } }
  const ATLA_UYARI = bad => "Anlaşılamayan seri girişleri: " + bad.join(", ") + " (X yalnız sonda joker olabilir; ilk/son harfte I-O olamaz)";

  // s: il verisi; iso: "YYYY-MM-DD"; ref: trReferansGun() sonucu (yalnızca takvim kapsamı uyarısı için).
  // Dönüş: {tip:"hata", mesaj} | {tip:"sonuc", plaka, kayit, geri, etiket, sinif, err, tarih, uyari, atla}
  function sorgula(s, iso, ref, atlaMetni) {
    if (!isoGecerli(iso)) return { tip: "hata", mesaj: "Lütfen geçerli bir tarih seçin." };
    const atla = atlaCoz(atlaMetni).etiket;
    return atlaIle(atlaMetni, () => {
      const gun = toDay(iso), p = plakaDurum(s, gun), est = p.est;
      if (p.durum === "sinir") return { tip: "hata", mesaj: SINIR_MESAJI };
      if (p.durum === "model") return { tip: "hata", mesaj: MODEL_MESAJI };
      if (p.durum === "alfabe") return { tip: "hata", mesaj: "Bu tarih için tahmin üretilemedi: seri alfabesinin dışına çıkılıyor. Daha yakın bir tarih deneyin." };
      if (p.durum === "geri") {         // ilk gözlemden önce (1 Şubat 2018 ve sonrası): geriye dönük tahmin; atlanacak seriler ve ileri harf grubu uyarıları geçerli değildir
        const kal = est.kalibre, b = kal === "ara" ? { err: est.err, kademe: "kalibre", etiket: "Tarihsel referansla kalibre edilmiş tahmin" } : kal === "once" ? { err: est.err, kademe: "cokkaba", etiket: "Çok kaba geriye dönük tahmin" } : geriBelirsizlik(est.h);   // referanstan ÖNCE (Ankara, 1 Haziran 2020 öncesi): referansın da ötesi = çok kaba; sayısal tahmin ve ± gün aynı
        let u = "Bu tarih ilk kayıtlı gözlemden (" + dstr(s.obs[0][0]) + ") önce: kayıt yok. ";
        if (kal === "once") {      // bilinen referansın da ÖNCESİ: hız varsayımla geriye uzatıldı, yüksek belirsizlik
          u += "Ayrıca bu tarih, bilinen tarihsel referansın (" + est.ref.plaka + ", yaklaşık " + trTarihGun(toDay(est.ref.tarih)) + "; kullanıcı bildirimi, resmî kayıt değildir) da öncesinde kalıyor: referanstan önceki dönemde hız, referans çevresindeki hızla varsayımla geriye uzatıldı. Referans tek noktadır ve tarihi yaklaşıktır; sonuç yüksek belirsizlik taşır, yalnızca büyüklük sırası olarak okuyun. Hız değişimleri ve seri atlamaları bilinemez.";
        } else if (kal) {      // tarihsel referansla kalibre (kesin gözlem DEĞİL): referans tek noktadır, tarihi yaklaşıktır, belirsizlik korunur
          u += "Tahmin, kullanıcı tarafından bildirilen tarihsel referansla (" + est.ref.plaka + ", yaklaşık " + trTarihGun(toDay(est.ref.tarih)) + "; resmî kayıt değildir) kalibre edildi; referans tek noktadır ve tarihi yaklaşıktır, bu yüzden belirsizlik korunmuştur. Hız değişimleri ve seri atlamaları bilinemez.";
        } else {
          u += "Tahmin, ilk gözlemin sırasından, ilk yıldaki hız ve ertesi yılın aynı dönemi esas alınarak geriye doğru hesaplandı; hız değişimleri ve seri atlamaları bilinemez.";
          if (b.kademe !== "geri") u += " Uzak geçmiş: belirsizlik büyüktür, sonucu yalnızca büyüklük sırası olarak okuyun.";
        }
        return { tip: "sonuc", plaka: p.plaka, kayit: false, geri: true, etiket: b.etiket, sinif: b.kademe, err: b.err, tarih: trTarihGun(gun), uyari: u, atla };
      }
      const last = s.obs[s.obs.length - 1]; let uyari = "";
      if (!est.real && EXCL.length) {
        const atlanan = exclOverlap(last[1], est.n, EXCL);
        if (atlanan > 0) uyari = "Bu tahmin, atlanacak girdiğiniz " + Math.round(atlanan / 1000) + " serinin (" + EXCL.map(x => x[2]).join(" · ") + ") üstünden atlanarak hesaplandı.";
      }
      if (!est.real && invN(last[1]).let[0] !== p.iv.let[0])
        uyari = (uyari ? uyari + " — " : "") + "Tahmin bir harf grubu sınırını aşıyor (" + invN(last[1]).let[0] + " → " + p.iv.let[0] + "). Grup geçişlerinde il bazlı atlamalar (rezerve harfler, isim serileri) tahmini kaydırabilir" +
          (s.il === "İstanbul" ? " — İstanbul'da R'den sonra S (misafir) ve T (taksi) gruplarının atlanması bekleniyor." : ".");
      if (ref && ref.kapsamDisi && iso === ref.iso) uyari = (uyari ? uyari + " — " : "") + KAPSAM_DISI;
      return { tip: "sonuc", plaka: p.plaka, kayit: !!est.real, geri: false, etiket: est.real ? "Kayıtlı veri" : "Tahmin", sinif: est.real ? "kayit" : "tahmin", err: est.err, tarih: trTarihGun(gun), uyari, atla };
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
      const etiket = g("tag"); etiket.textContent = r.etiket; etiket.className = "t-etiket " + r.sinif;
      g("tarih-out").textContent = r.tarih + (r.kayit ? " · kayıtlı gözlemlere göre" : " · ±" + r.err + " gün");
      sonuc.hidden = false; uyari.textContent = r.uyari; uyari.hidden = !r.uyari;
      // atlanacak seri kullanıldıysa sonuçta AÇIKÇA yazılır (ayar yoksa hiçbir ek metin yok); kayıtlı veri tarihlerinde etkisi olmadığı da belirtilir
      atlaBilgi.textContent = !r.atla.length ? "" : r.geri ? "Atlanacak seriler geriye dönük tahmine uygulanmaz." : r.kayit ? "Atlanacak seriler (" + r.atla.join(" · ") + ") kayıtlı veri tarihini etkilemez." : "Atlanacak seriler uygulandı: " + r.atla.join(" · ") + ".";
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
  return { plakaDurum, sorgula, kur, plakaMetni, atlaCoz, atlaIle, geriBelirsizlik, SINIR_MESAJI };
})();
