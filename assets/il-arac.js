// İl sayfası plaka tahmin aracı. Hesaplamanın tamamı ortak motordan (tahmin-motoru.js: reachDate, parseExcl, toN, invN) gelir;
// burada yalnızca hedef girdisinin ayrıştırılması, ana sayfadaki calcTarget() ile aynı kurallarla sonuç sınıflandırması ve metin üretimi vardır.
// Klasik script: tahmin-motoru.js'in global bildirimlerini (EXCL, reachDate, ...) kullanır; önce o yüklenmelidir.
const PlakaIlArac = (function () {
  const trTarih = day => trTarihGun(day);                       // ortak motordaki Türkçe tarih biçimi
  const pad3 = n => String(n).padStart(3, "0");

  // s: {kod, il, bterr, obs}; giris: kullanıcı metni; exclTxt: atlanacak seriler; bugunGun: ana sayfadaki todayDay ile aynı tanım (referans gün: Türkiye tarihinin önceki iş günü)
  function hesapla(s, giris, exclTxt, bugunGun) {
    const kodSayfa = s.kod, kodTxt = String(kodSayfa).padStart(2, "0");
    const raw = String(giris == null ? "" : giris).toUpperCase().replace(/[^A-Z0-9 ]/g, " ").trim();
    const m = raw.match(/^(?:(\d{1,2})\s*)?([A-Z]{3})(?:\s*(\d{1,3}))?$/);
    if (!m) return { tip: "hata", mesaj: "Seri okunamadı. Örnek: BJB · BJB 500 · " + kodTxt + " BJB 001" };
    if (m[1]) {
      const k = +m[1];
      if (k < 1 || k > 81) return { tip: "hata", mesaj: "Geçersiz il kodu: " + m[1] + " (1–81 arası olmalı)." };
      if (k !== kodSayfa) return { tip: "baska_il", mesaj: "Bu sayfa " + s.il + " (" + kodTxt + ") içindir; " + String(k).padStart(2, "0") + " kodlu il için ana sayfadaki aracı kullanın.", href: "/?il=" + k };
    }
    const let3 = m[2], num = m[3] ? +m[3] : 1, tN = toN(let3, num);
    if (tN == null) return { tip: "hata", mesaj: "Bu harf dizisi plakalarda kullanılmıyor (ilk ve son harfte I/O olamaz; Q, W, X hiç kullanılmaz)." };
    const px = parseExcl(String(exclTxt || ""));
    if (px.bad.length) return { tip: "hata", mesaj: "Atlanacak seriler okunamadı: " + px.bad.join(", ") + ". Örnek: SXX, TXX · BAA-BCZ" };
    EXCL = px.intervals;          // motorun genel dışlama listesi (ana sayfadaki applyExcl ile aynı etki)
    let r;
    try { r = reachDate(s, tN); } finally { EXCL = []; }
    const plaka = kodTxt + " " + let3 + " " + pad3(num), sonGun = s.obs[s.obs.length - 1][0];
    if (r.excluded) return { tip: "dislanan", plaka, mesaj: "Bu seri, atlanacaklar listenizde (" + r.excluded + ") — bu varsayımla hiç verilmeyecek." };
    if (r.never) return { tip: "yok", plaka, mesaj: "Bu ilde seri ilerlemesi tespit edilemedi." };
    if (r.back) {
      const fv = invN(s.obs[0][1]);
      return { tip: "geriye", plaka, gun: r.day, err: r.err, ilkGun: r.first[0], ilkPlaka: kodTxt + " " + fv.let + " " + pad3(fv.num),
               uyarilar: ["Bu plaka kayıtlarımızın başlangıcından önce verilmiş; tarih kayıtlı veri değil, ilk dönem hızı ve ertesi yılın aynı dönemine dayalı geriye dönük tahmindir."] };
    }
    if (r.passed) return { tip: "gecildi", plaka, gun: r.day };
    const yil = (r.day - bugunGun) / 365.25, uyarilar = [];
    if (yil > 1.5) uyarilar.push("Uzak tarih: hız değişimi ve harf grubu atlamaları nedeniyle belirsizlik büyüktür; tahmini kaba bir sıra göstergesi olarak okuyun.");
    else if (invN(s.obs[s.obs.length - 1][1]).let[0] !== let3[0]) uyarilar.push("Hedef farklı bir harf grubunda; grup geçişindeki atlamalar tarihi öne/geriye alabilir.");
    return { tip: "tahmin", plaka, gun: r.day, err: r.err, yil, atlanan: r.atlanan || 0, sonGun, uyarilar };
  }

  // Analitik olayı (olcum.js yüklü değilse ya da üretimde değilsek sessizce yok sayılır)
  const olay = ad => { try { if (typeof PlakaOlcum !== "undefined") PlakaOlcum.olay(ad); } catch (e) { /* ölçüm hatası aracı etkilemez */ } };
  function satir(ad, metin) { const p = document.createElement("p"); p.className = ad; p.textContent = metin; return p; }
  function goster(kutu, o) {
    kutu.textContent = "";
    if (o.tip === "hata" || o.tip === "dislanan" || o.tip === "yok" || o.tip === "baska_il") {
      const p = satir("hata", o.mesaj); p.setAttribute("role", o.tip === "hata" ? "alert" : "status"); kutu.appendChild(p);
      if (o.href) { const a = document.createElement("a"); a.href = o.href; a.textContent = "Ana sayfada aç"; const q = document.createElement("p"); q.className = "s-a"; q.appendChild(a); kutu.appendChild(q); }
      return;
    }
    if (o.tip === "gecildi") { kutu.appendChild(satir("s-b", o.plaka + ": geçildi")); kutu.appendChild(satir("s-a", "Kayıtlara göre " + trTarih(o.gun) + " civarında verildi.")); return; }
    if (o.tip === "geriye") {
      kutu.appendChild(satir("s-b", o.plaka + ": ~" + trTarih(o.gun)));
      kutu.appendChild(satir("s-a", "± " + o.err + " gün · geriye dönük tahmin (ilk kayıt: " + o.ilkPlaka + ", " + trTarih(o.ilkGun) + ")"));
    } else {
      kutu.appendChild(satir("s-b", o.plaka + ": ~" + trTarih(o.gun)));
      kutu.appendChild(satir("s-a", "± " + o.err + " gün · " + trTarih(o.sonGun) + " gözlemine dayalı tahmin" + (o.yil > 1 ? " · " + o.yil.toLocaleString("tr-TR", { maximumFractionDigits: 1 }) + " yıl sonra" : "") + (o.atlanan ? " · aradaki " + o.atlanan + " atlanan seri düşüldü" : "")));
    }
    (o.uyarilar || []).forEach(u => kutu.appendChild(satir("s-u", u)));
  }

  // Sayfadaki büyük tahmini seri/tarih/harf grubu: ana sayfayla AYNI motor ve AYNI referans gün (Türkiye tarihinin en yakın önceki iş günü; hafta sonu/tatilde değişmez).
  // Tarayıcı saati başlangıç tarihinden gerideyse başlangıç tarihiyle tutarlı kalınır. now: ms (testler için).
  function guncelTahmin(doc, s, now) {
    const kok = doc.querySelector("[data-baslangic]"), bas = kok ? toDay(kok.getAttribute("data-baslangic")) : null;
    const ref = trReferansGun(now); let gun = ref.gun; if (bas != null && gun < bas) gun = bas;
    const b = guncelSeriBilgisi(s, gun); if (!b) throw new Error("tahmin alfabe dışında");
    const v = { seri: b.seri, plaka: b.plaka, tarih: b.tarih, grup: b.grup, kapsamDisi: ref.kapsamDisi };
    doc.querySelectorAll("[data-live]").forEach(e => { e.textContent = v[e.getAttribute("data-live")]; });
    const tg = doc.getElementById("tahmin-grup"); if (tg) tg.hidden = (v.grup === tg.getAttribute("data-gozlenen"));
    return v;
  }
  const KAPSAM_DISI = "Resmî tatil takvimi bu tarihi kapsamıyor; hafta sonu dışındaki tatillerde güncel tahmin en yakın iş gününe çekilmemiş olabilir.";
  function uyar(doc, mesaj) { const u = doc.getElementById("guncellik"); if (!u) return; const t = u.querySelector("span"); if (t) t.textContent = mesaj; u.hidden = false; }
  const GUNCELLENEMEDI = "Canlı tahmin güncellenemedi; sayfada gösterilen tahmin, belirtilen tarih itibarıyla hesaplanmıştır.";

  function baslat() {
    const veriEl = document.getElementById("il-veri"), form = document.getElementById("hedef-form"), kutu = document.getElementById("sonuc");
    if (!veriEl || !form || !kutu) return;
    const s = JSON.parse(veriEl.textContent), hedef = document.getElementById("hedef"), atla = document.getElementById("atla");
    try { const g = guncelTahmin(document, s); if (g.kapsamDisi) uyar(document, KAPSAM_DISI); } catch (err) { console.error("plakatahmini: canlı tahmin güncellenemedi", err); uyar(document, GUNCELLENEMEDI); }
    const bugunGun = () => trReferansGun().gun;                          // ana sayfadaki todayDay ile aynı: referans gün (önceki iş günü)
    form.addEventListener("submit", e => {
      e.preventDefault(); olay("il-hesapla-basla");                      // anonim olay: yalnızca ad; girdi metni gönderilmez
      try { const o = hesapla(s, hedef.value, atla ? atla.value : "", bugunGun()); goster(kutu, o); olay(o.tip === "hata" || o.tip === "baska_il" ? "il-hesapla-hata" : "il-hesapla-sonuc"); }
      catch (err) { console.error("plakatahmini: hesaplama başarısız", err); olay("il-hesapla-hata"); kutu.textContent = ""; const p = satir("hata", "Hesaplama yapılamadı. Ana sayfadaki aracı deneyin."); p.setAttribute("role", "alert"); kutu.appendChild(p); }
    });
    if (typeof PlakaTarih !== "undefined") PlakaTarih.kur(document, { onek: "il", s: () => s, ref: trReferansGun(), olay });          // "Belirli bir tarihte hangi plakada?": ortak araç (tarih-sorgu.js), sayfanın kendi ili
    const cta = document.querySelector('a[href="#hesapla"]');
    if (cta) cta.addEventListener("click", () => setTimeout(() => hedef.focus({ preventScroll: true }), 0));
  }
  function baslatGuvenli() { try { baslat(); } catch (err) { console.error("plakatahmini: araç başlatılamadı", err); try { uyar(document, GUNCELLENEMEDI); } catch (e2) {} } }
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", baslatGuvenli); else baslatGuvenli();
  }
  return { hesapla, trTarih, guncelTahmin };
})();
