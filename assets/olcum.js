// Analitik: GoatCounter yükleyici ve anonim olay gönderici. Ana sayfa, 81 il sayfası ve /geri-bildirim bu TEK dosyayı yükler; sayfalarda GoatCounter kodu doğrudan bulunmaz.
//  - Sayfa görüntüleme: GoatCounter'ın standart count.js betiği yüklenince kendisi sayar (burada ayrıca sayım yapılmaz, çift sayım olmaz).
//  - Yalnızca üretimde çalışır: location.hostname === "plakatahmini.com", tarayıcı otomasyonu (navigator.webdriver) değil ve yerel kapatma anahtarı (localStorage "plaka-olcum" = "kapali") yok.
//    Yerel geliştirme, Vercel önizlemeleri ve testlerde count.js hiç yüklenmez, ağ isteği yapılmaz.
//  - Olaylar anonimdir ve yalnızca aşağıdaki sabit adlardan biri olabilir; girdi metni, plaka, arama sözcüğü ya da başka içerik hiçbir zaman gönderilmez.
const PlakaOlcum = (function () {
  const URETIM_HOST = "plakatahmini.com", SAYAC = "https://plakatahmini.goatcounter.com/count", BETIK = "https://gc.zgo.at/count.js";
  // ana-/il- önekli hesaplayıcı ve tarih sorgusu (ana|il-tarih-hesapla|sonuc|hata) olayları, ana sayfa il araması ve üç büyük il kartı (il adresi gibi herkese açık bir ad: kart tıklaması)
  // ve /geri-bildirim formlarının, GitHub'a kaydedildikten SONRA gönderilen iki anonim olayı (plaka_bildirimi, genel_oneri): içerik, il, tarih, isim ya da mesaj taşımaz.
  // Hata kategorisi olayları (aşağıdaki KATEGORI_OLAYLARI): başarısız bir işlemde mevcut toplam hata olayına EK olarak tek bir sabit kategori; kategori listesi kapalıdır.
  const IZINLI = /^(?:(?:ana|il)-hesapla-(?:basla|sonuc|hata)|ana-hesapla-hata\/(?:bos|tek-harf|iki-harf|format|karakter|il-kodu|hesaplama)|il-hesapla-hata\/(?:bos|tek-harf|iki-harf|format|karakter|il-kodu|baska-il|atla|hesaplama)|(?:ana|il)-tarih-(?:hesapla|sonuc|hata)|ana-il-ara|ana-il-ara-hata|ana-il-ara-hata\/(?:bos|belirsiz|bulunamadi|celisik)|ana-kart-tikla\/[a-z]+|plaka_bildirimi|genel_oneri)$/;
  // Kategori -> olay adı: yalnızca bu sabit tablodan seçilir (girdiden olay adı üretilmez). Ana sayfada "baska-il" (il seçimi koda göre değişir) ve "atla"
  // (geçersiz atlanacak seri hesaplamayı durdurmaz, ayrı uyarı gösterilir) oluşmaz; bu yüzden ana sayfa tablosunda yoktur.
  const KATEGORI_OLAYLARI = Object.freeze({
    "il-hesapla-hata": Object.freeze({ "bos": "il-hesapla-hata/bos", "tek-harf": "il-hesapla-hata/tek-harf", "iki-harf": "il-hesapla-hata/iki-harf", "format": "il-hesapla-hata/format",
      "karakter": "il-hesapla-hata/karakter", "il-kodu": "il-hesapla-hata/il-kodu", "baska-il": "il-hesapla-hata/baska-il", "atla": "il-hesapla-hata/atla", "hesaplama": "il-hesapla-hata/hesaplama" }),
    "ana-hesapla-hata": Object.freeze({ "bos": "ana-hesapla-hata/bos", "tek-harf": "ana-hesapla-hata/tek-harf", "iki-harf": "ana-hesapla-hata/iki-harf", "format": "ana-hesapla-hata/format",
      "karakter": "ana-hesapla-hata/karakter", "il-kodu": "ana-hesapla-hata/il-kodu", "hesaplama": "ana-hesapla-hata/hesaplama" }),
    "ana-il-ara-hata": Object.freeze({ "bos": "ana-il-ara-hata/bos", "belirsiz": "ana-il-ara-hata/belirsiz", "bulunamadi": "ana-il-ara-hata/bulunamadi", "celisik": "ana-il-ara-hata/celisik" })
  });
  const kendi = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  // Sabit tablodaki olay adı ya da null (bilinmeyen taban/kategori hiçbir olay üretmez)
  function kategoriOlayi(taban, kategori) { return kendi(KATEGORI_OLAYLARI, taban) && kendi(KATEGORI_OLAYLARI[taban], kategori) ? KATEGORI_OLAYLARI[taban][kategori] : null; }

  // Hedef plaka hesaplayıcısı: başarısız bir işlemin TEK hata kategorisi. Doğrulama sırası iki sayfadaki ayrıştırıcıyla aynıdır (il-arac.js hesapla, index.html calcTarget):
  //   1) seri deseni okunamadı -> girdinin biçimi: bos | karakter | tek-harf | iki-harf | format (girisBicimi)
  //   2) baştaki il kodu 1–81 dışında -> il-kodu      3) il sayfasında başka ilin geçerli kodu -> baska-il (ana sayfada oluşmaz: sayfaKodu null)
  //   4) harf dizisi plakalarda kullanılmıyor (Q/W/X; ilk/son harfte I/O) -> karakter      5) il sayfasında atlanacak seriler okunamadı -> atla (ana sayfada atlaHatali hep false)
  //   6) girdi geçerli ama sonuç üretilemedi (beklenmeyen hata) -> hesaplama
  // b: {sayfaKodu: il kodu | null, harfGecerli: (harf3, sira) => bool (ortak motorun toN'u), atlaHatali: bool}. Dönen değer yalnızca sabit kategori adıdır; girdi saklanmaz/gönderilmez.
  const HEDEF_DESEN = /^(?:(\d{1,2})\s*)?([A-Z]{3})(?:\s*(\d{1,3}))?$/;          // iki sayfadaki desenle aynı (parite testi: tests/test_olcum.py)
  function hedefHataKategorisi(giris, b) {
    try {
      const raw = String(giris == null ? "" : giris).toUpperCase().replace(/[^A-Z0-9 ]/g, " ").trim(), m = raw.match(HEDEF_DESEN);
      if (!m) return girisBicimi(giris);
      if (m[1]) { const k = +m[1]; if (k < 1 || k > 81) return "il-kodu"; if (b.sayfaKodu != null && k !== b.sayfaKodu) return "baska-il"; }
      if (!b.harfGecerli(m[2], m[3] ? +m[3] : 1)) return "karakter";
      if (b.atlaHatali) return "atla";
      return "hesaplama";
    } catch (e) { return "hesaplama"; }         // sınıflandırma da beklenmeyen biçimde başarısızsa: yine tek kategori
  }
  // Seri deseni okunamayan girdinin biçimi (öncelik sırasıyla, her girdi tek kategoriye düşer):
  //   bos: yalnızca boşluk · karakter: büyük harfe çevrildikten sonra boşluk dışı ASCII olmayan karakter (Ç Ğ İ Ö Ş Ü vb.; ayrıştırıcı bunları boşluğa çevirir)
  //   tek-harf: (baştaki 1–2 haneli il kodu dışında) yalnızca tek harf · iki-harf: iki harf, isteğe bağlı ardından rakamlar (örn. 06 AB 1234)
  //   format: geri kalan her şey (örn. 06 A 1234, ABC 1234, TR 06 ABC 123, yalnız rakam, il adı)
  function girisBicimi(giris) {
    const ham = String(giris == null ? "" : giris);
    if (!ham.trim()) return "bos";
    const buyuk = ham.toUpperCase();
    if (/[^\x00-\x7F]/.test(buyuk.replace(/\s/g, ""))) return "karakter";
    const parca = buyuk.match(/[A-Z]+|[0-9]+/g) || [];
    const govde = parca.length > 1 && /^\d{1,2}$/.test(parca[0]) ? parca.slice(1) : parca;
    if (govde.length === 1 && /^[A-Z]$/.test(govde[0])) return "tek-harf";
    if (/^[A-Z]{2}$/.test(govde[0] || "") && (govde.length === 1 || (govde.length === 2 && /^\d+$/.test(govde[1])))) return "iki-harf";
    return "format";
  }
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
  return { olay, uygun, baslat, kayit, IZINLI, KATEGORI_OLAYLARI, kategoriOlayi, hedefHataKategorisi, girisBicimi };
})();
