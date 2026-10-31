// /geri-bildirim sayfası: iki form (plaka bilgisi, öneri/hata), istemci tarafı ön kontrol ve /api/geri-bildirim'e gönderim.
// Sunucu doğrulaması esastır (api/_geri-bildirim.js); buradaki kontroller yalnızca hızlı geri bildirim içindir. Kullanıcı metni yalnızca textContent/value ile işlenir (innerHTML yok).
// Analitik (olcum.js, GoatCounter): sayfa görüntüleme dışında YALNIZCA sunucu kaydı başarıyla yaptıktan sonra tek bir anonim olay gönderilir (plaka_bildirimi / genel_oneri). Forma yazılan hiçbir şey üçüncü tarafa gitmez.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var acilis = Date.now();                      // sunucu, formun çok hızlı (bot) gönderilmediğini bu süreden anlar
  var gonderiliyor = false;
  var olay = function (ad) { try { if (typeof PlakaOlcum !== "undefined") PlakaOlcum.olay(ad); } catch (e) { /* ölçüm hatası formu etkilemez */ } };

  var ilSecim = $("p-il"), sekmeler = document.querySelectorAll('input[name="sekme"]');
  var formlar = { plaka: $("f-plaka"), oneri: $("f-oneri") }, tesekkur = $("tesekkur");

  // --- adres parametreleri: ?il=06 (plaka kodu), ?sayfa=/il/ankara, ?tur=plaka|oneri ---------------------------------------
  var params = new URLSearchParams(location.search);
  var slugKod = {};
  Array.prototype.forEach.call(ilSecim.options, function (o) { if (o.value) slugKod[o.dataset.slug] = o.value; });
  var ilParam = (params.get("il") || "").trim(), ilKod = /^\d{1,2}$/.test(ilParam) && ilSecim.querySelector('option[value="' + ("0" + ilParam).slice(-2) + '"]') ? ("0" + ilParam).slice(-2) : "";
  var sayfa = null, sraw = params.get("sayfa") || "", sp = sraw ? sraw.split(/[?#]/)[0].replace(/\/+$/, "") || "/" : "";
  if (sp === "/" || (/^\/il\/[a-z0-9]+$/.test(sp) && slugKod[sp.slice(4)])) sayfa = sp;
  if (!ilKod && sayfa && sayfa.indexOf("/il/") === 0) ilKod = slugKod[sayfa.slice(4)];
  if (ilKod && !sayfa) { var o = ilSecim.querySelector('option[value="' + ilKod + '"]'); if (o) sayfa = "/il/" + o.dataset.slug; }
  if (ilKod) ilSecim.value = ilKod;                 // otomatik seçim; kullanıcı değiştirebilir
  // plaka kutusu ipucu: seçili ilin kendi plaka kodu ("örn. 06 XYZ 123 ya da XYZ"); XYZ gerçek bir seri olamaz (X harfi plakalarda kullanılmaz); il seçili değilse kodsuz örnek
  function plakaIpucu() { $("p-plaka").placeholder = "örn. " + (ilSecim.value ? ilSecim.value + " " : "") + "XYZ 123 ya da XYZ"; }
  ilSecim.addEventListener("change", plakaIpucu); plakaIpucu();
  if (sayfa) ["p", "o"].forEach(function (k) { var n = $(k + "-sayfa-notu"); n.textContent = "Bu bildirim şu sayfayla ilişkilendirilecek: " + sayfa; n.hidden = false; });

  // --- sekmeler -----------------------------------------------------------------------------------------------------
  function sekmeAc(ad) {
    Object.keys(formlar).forEach(function (k) { formlar[k].hidden = k !== ad; });
    tesekkur.hidden = true;
    Array.prototype.forEach.call(sekmeler, function (r) { r.checked = r.value === ad; });
  }
  Array.prototype.forEach.call(sekmeler, function (r) { r.addEventListener("change", function () { if (r.checked) sekmeAc(r.value); }); });
  sekmeAc(params.get("tur") === "oneri" ? "oneri" : "plaka");

  // --- tarih alanları: kesinliğe göre gün/ay/yıl ---------------------------------------------------------------------
  var kesinlikRadyo = document.querySelectorAll('input[name="kesinlik"]');
  function kesinlik() { var s = document.querySelector('input[name="kesinlik"]:checked'); return s ? s.value : "ay"; }
  function tarihAlanlari() {
    var k = kesinlik(); $("p-gun-k").hidden = k !== "gun"; $("p-ay-k").hidden = k === "yil";
  }
  Array.prototype.forEach.call(kesinlikRadyo, function (r) { r.addEventListener("change", tarihAlanlari); });
  tarihAlanlari();
  $("p-yil").max = String(new Date().getFullYear());

  function tarihDegeri() {
    var k = kesinlik(), y = $("p-yil").value.trim(), a = $("p-ay").value, g = $("p-gun").value;
    if (!/^\d{4}$/.test(y)) return { hata: "Yılı dört haneli yazın (örn. 2021).", alan: "p-yil" };
    if (k !== "yil" && !a) return { hata: "Ayı seçin.", alan: "p-ay" };
    if (k === "gun" && !g) return { hata: "Günü seçin.", alan: "p-gun" };
    return { deger: k === "yil" ? y : k === "ay" ? y + "-" + a : y + "-" + a + "-" + g, kesinlik: k };
  }

  // --- gönderim -----------------------------------------------------------------------------------------------------
  function hataGoster(form, mesaj, alanId) {
    var kutu = $(form === "plaka" ? "p-hata" : "o-hata"); kutu.textContent = mesaj;
    Array.prototype.forEach.call(formlar[form].querySelectorAll("[aria-invalid]"), function (e) { e.removeAttribute("aria-invalid"); });
    var e = alanId && $(alanId); if (e) { e.setAttribute("aria-invalid", "true"); try { e.focus(); } catch (x) { /* odak verilemedi */ } }
  }
  var SUNUCU_ALAN = { il: "p-il", plaka: "p-plaka", tarih: "p-yil", tarihKesinligi: "p-yil", aciklama: "p-aciklama", tur: "o-mesaj", mesaj: "o-mesaj", isim: "o-isim" };

  function onKontrol(ad) {
    if (ad === "plaka") {
      if (!ilSecim.value) return { hata: "Listeden bir il seçin.", alan: "p-il" };
      if (!$("p-plaka").value.trim()) return { hata: "Plaka ya da harf serisi girin.", alan: "p-plaka" };
      var t = tarihDegeri(); if (t.hata) return t;
    } else {
      var m = $("o-mesaj").value.trim();
      if (m.length < 5) return { hata: "Mesaj en az 5 karakter olmalı.", alan: "o-mesaj" };
    }
    return null;
  }
  function yuk(ad) {
    var web = $(ad === "plaka" ? "p-web" : "o-web").value, gecen = Date.now() - acilis;
    if (ad === "plaka") { var t = tarihDegeri(); return { form: "plaka", il: ilSecim.value, plaka: $("p-plaka").value, tarih: t.deger, tarihKesinligi: t.kesinlik, aciklama: $("p-aciklama").value, sayfa: sayfa, website: web, gecen: gecen }; }
    return { form: "oneri", tur: document.querySelector('input[name="tur"]:checked').value, mesaj: $("o-mesaj").value, isim: $("o-isim").value, sayfa: sayfa, website: web, gecen: gecen };
  }
  function gonder(ad, ev) {
    ev.preventDefault();
    if (gonderiliyor) return;
    var form = formlar[ad], dugme = form.querySelector("button[type=submit]"), kutu = $(ad === "plaka" ? "p-hata" : "o-hata");
    kutu.textContent = "";
    var on = onKontrol(ad); if (on) { hataGoster(ad, on.hata, on.alan); return; }
    gonderiliyor = true; dugme.disabled = true; var eski = dugme.textContent; dugme.textContent = "Gönderiliyor…";
    var son = function () { gonderiliyor = false; dugme.disabled = false; dugme.textContent = eski; };
    var kontrol = typeof AbortController === "function" ? new AbortController() : null, zamanAsimi = kontrol && setTimeout(function () { kontrol.abort(); }, 15000);
    fetch("/api/geri-bildirim", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(yuk(ad)), signal: kontrol ? kontrol.signal : undefined })
      .then(function (r) { return r.json().catch(function () { return null; }).then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (s) {
        clearTimeout(zamanAsimi); son();
        if (s.ok && s.j && s.j.ok === true) {
          if (!s.j.tekrar) olay(ad === "plaka" ? "plaka_bildirimi" : "genel_oneri");      // tekrar: aynı içerik az önce kaydedilmişti, yeniden sayılmaz
          form.reset(); tarihAlanlari(); if (ilKod) ilSecim.value = ilKod; plakaIpucu();
          Object.keys(formlar).forEach(function (k) { formlar[k].hidden = true; }); $("sekmeler").parentNode.hidden = true;
          tesekkur.hidden = false; tesekkur.focus(); acilis = Date.now();
          return;
        }
        var msg = s.j && typeof s.j.error === "string" ? s.j.error : "Gönderilemedi. Lütfen biraz sonra tekrar deneyin.";
        hataGoster(ad, msg, s.j && SUNUCU_ALAN[s.j.alan]);
      })
      .catch(function () {
        clearTimeout(zamanAsimi); son();
        hataGoster(ad, "Gönderilemedi: bağlantı kurulamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.", null);
      });
  }
  formlar.plaka.addEventListener("submit", function (e) { gonder("plaka", e); });
  formlar.oneri.addEventListener("submit", function (e) { gonder("oneri", e); });
  $("yeni").addEventListener("click", function () { $("sekmeler").parentNode.hidden = false; sekmeAc(document.querySelector('input[name="sekme"]:checked').value); });
  document.body.setAttribute("data-hazir", "1");     // betik çalıştı (testler ve erişilebilirlik araçları için)
})();
