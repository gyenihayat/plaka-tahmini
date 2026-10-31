// Analitik: GoatCounter yükleyici ve anonim olay gönderici. Ana sayfa ve 81 il sayfası bu TEK dosyayı yükler; sayfalarda GoatCounter kodu doğrudan bulunmaz.
//  - Sayfa görüntüleme: GoatCounter'ın standart count.js betiği yüklenince kendisi sayar (burada ayrıca sayım yapılmaz, çift sayım olmaz).
//  - Yalnızca üretimde çalışır: location.hostname === "plakatahmini.com", tarayıcı otomasyonu (navigator.webdriver) değil ve yerel kapatma anahtarı (localStorage "plaka-olcum" = "kapali") yok.
//    Yerel geliştirme, Vercel önizlemeleri ve testlerde count.js hiç yüklenmez, ağ isteği yapılmaz.
//  - Olaylar anonimdir ve yalnızca aşağıdaki sabit adlardan biri olabilir; girdi metni, plaka, arama sözcüğü ya da başka içerik hiçbir zaman gönderilmez.
const PlakaOlcum = (function () {
  const URETIM_HOST = "plakatahmini.com", SAYAC = "https://plakatahmini.goatcounter.com/count", BETIK = "https://gc.zgo.at/count.js";
  // ana-/il- önekli hesaplayıcı ve tarih sorgusu (ana|il-tarih-hesapla|sonuc|hata) olayları, ana sayfa il araması ve üç büyük il kartı (il adresi gibi herkese açık bir ad: kart tıklaması)
  const IZINLI = /^(?:(?:ana|il)-hesapla-(?:basla|sonuc|hata)|(?:ana|il)-tarih-(?:hesapla|sonuc|hata)|ana-il-ara|ana-il-ara-hata|ana-kart-tikla\/[a-z]+)$/;
  const kayit = [];                       // bellekte, testler ve hata ayıklama için: kabul edilen olay adları (gönderilip gönderilmediğinden bağımsız)
  let kuyruk = [], yuklu = false;
  const g = typeof globalThis !== "undefined" ? globalThis : window;

  function kapali() { try { return g.localStorage.getItem("plaka-olcum") === "kapali"; } catch (e) { return false; } }
  function uygun() {
    try { return g.location.hostname === URETIM_HOST && !(g.navigator && g.navigator.webdriver) && !kapali(); } catch (e) { return false; }
  }
  function gonder(ad) { try { g.goatcounter.count({ path: ad, title: ad, event: true }); } catch (e) { /* ölçüm hatası sayfayı etkilemez */ } }

  function baslat() {
    if (!uygun() || !g.document || g.__plakaOlcumYuklendi) return false;
    g.__plakaOlcumYuklendi = true;
    const s = g.document.createElement("script");
    s.async = true; s.src = BETIK; s.setAttribute("data-goatcounter", SAYAC);
    s.onload = () => { yuklu = true; kuyruk.splice(0).forEach(gonder); };
    s.onerror = () => { kuyruk = []; };     // engelleyici varsa sessizce vazgeç
    g.document.head.appendChild(s);
    return true;
  }
  // Olay adı sabit listede değilse reddedilir (kazara içerik sızıntısına karşı). true: kabul edildi (üretimdeyse gönderilir/kuyruğa alınır)
  function olay(ad) {
    ad = String(ad); if (!IZINLI.test(ad)) return false;
    kayit.push(ad); if (kayit.length > 50) kayit.shift();
    if (!uygun()) return true;
    if (yuklu && g.goatcounter && g.goatcounter.count) gonder(ad); else if (kuyruk.length < 20) kuyruk.push(ad);
    return true;
  }
  baslat();
  return { olay, uygun, baslat, kayit, IZINLI };
})();
