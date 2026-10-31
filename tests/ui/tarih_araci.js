// Kullanım: node tarih_araci.js <chrome> <taban_url> '<[[ilAdi, slug], ...]>' '<[iso tarihler]>'
// "Belirli bir tarihte hangi plakada?" aracını GERÇEK Chrome'da sınar: ana sayfa ve 81 il sayfası eşliği, gerçek klavye (Tab/Enter/Backspace), hata mesajı, analitik olay adları,
// araçların birbirini bozmaması, atlanacak seriler, tüm iller tablosu ve 5 genişlikte taşma. Chrome, abacus/goatcounter adlarını çözemez (test ziyareti ölçüm göndermez).
const { spawn } = require("child_process"), fs = require("fs"), os = require("os"), path = require("path");
const [, , CHROME, TABAN, ILLER_JSON, TARIHLER_JSON] = process.argv, ILLER = JSON.parse(ILLER_JSON), TARIHLER = JSON.parse(TARIHLER_JSON), PORT = 9371, dir = fs.mkdtempSync(path.join(os.tmpdir(), "tarih_"));
const ch = spawn(CHROME, ["--headless=new", "--disable-gpu", "--host-resolver-rules=MAP abacus.jasoncameron.dev ~NOTFOUND, MAP *.goatcounter.com ~NOTFOUND, MAP gc.zgo.at ~NOTFOUND", `--remote-debugging-port=${PORT}`, `--user-data-dir=${dir}`, "about:blank"], { stdio: "ignore" });
const bekle = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const out = { hatalar: [] };
  try {
    let t; for (let i = 0; i < 60; i++) { try { t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json(); break; } catch (e) { await bekle(200); } }
    const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r); let id = 0; const bk = {};
    ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && bk[d.id]) { bk[d.id](d); delete bk[d.id]; } if (d.method === "Runtime.exceptionThrown") out.hatalar.push(JSON.stringify(d.params.exceptionDetails).slice(0, 200)); if (d.method === "Runtime.consoleAPICalled" && d.params.type === "error") out.hatalar.push("console.error"); };
    const send = (method, params = {}) => new Promise((r, j) => { const i = ++id; bk[i] = r; setTimeout(() => j(new Error("zaman aşımı " + method)), 20000); ws.send(JSON.stringify({ id: i, method, params })); });
    const ev = async e => { const r = (await send("Runtime.evaluate", { expression: e, returnByValue: true })).result; if (r.exceptionDetails) throw new Error("EV: " + (r.exceptionDetails.exception && r.exceptionDetails.exception.description)); return r.result.value; };
    const tus = async (key, code, vk) => { for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, text: key === "Enter" ? "\r" : undefined }); };
    await send("Page.enable"); await send("Runtime.enable");
    const git = async (yol, w = 1280, mobil = false) => { await send("Emulation.setDeviceMetricsOverride", { width: w, height: 900, deviceScaleFactor: 1, mobile: mobil }); await send("Page.navigate", { url: TABAN + yol });
      for (let i = 0; i < 60; i++) { await bekle(120); if (await ev("document.readyState==='complete'&&typeof PlakaTarih!=='undefined'&&!document.getElementById('tarih-govde').hidden")) return; } throw new Error("sayfa hazır değil " + yol); };
    const oku = `(()=>{ const g=id=>document.getElementById(id); return { gizli:g('tarih-sonuc').hidden, plaka:g('plate-num').textContent, etiket:g('tag').textContent, out:g('tarih-out').textContent, uyari:g('tarih-uyari').hidden?'':g('tarih-uyari').textContent, hata:g('tarih-hata').textContent, atla:g('tarih-atla-bilgi').hidden?'':g('tarih-atla-bilgi').textContent, atlaUyari:g('excl-warn').hidden?'':g('excl-warn').textContent }; })()`;
    const hesapla = async (iso, il) => ev(`(()=>{ const g=id=>document.getElementById(id); ${il ? `g('tarih-il').value=${JSON.stringify(il)}; g('tarih-il').dispatchEvent(new Event('change',{bubbles:true}));` : ""} g('dt').value=${JSON.stringify(iso)}; g('dt').dispatchEvent(new Event('input',{bubbles:true})); g('btn-tarih').click(); return null; })()`).then(() => ev(oku));

    // --- 1) EŞLİK: ana sayfa (il seçimi) ↔ il sayfası (yalnızca tarih), 81 il × tarihler
    out.esdeger = { ana: {}, il: {} };
    await git("/"); for (const [il] of ILLER) { out.esdeger.ana[il] = {}; for (const iso of TARIHLER) out.esdeger.ana[il][iso] = await hesapla(iso, il); }
    for (const [il, slug] of ILLER) { await git("/il/" + slug); out.esdeger.il[il] = {}; for (const iso of TARIHLER) out.esdeger.il[il][iso] = await hesapla(iso); }

    // --- 2) GERÇEK KLAVYE + hata + analitik olay adları (375 ve 1440 px, ana sayfa ve il sayfası)
    out.klavye = [];
    for (const [yol, onek, w, mobil] of [["/", "ana", 375, true], ["/il/konya", "il", 375, true], ["/", "ana", 1440, false], ["/il/konya", "il", 1440, false]]) {
      await git(yol, w, mobil); const k = { yol, w, onek };
      await ev(`(()=>{ const d=document.getElementById('dt'); d.value='2027-03-01'; d.dispatchEvent(new Event('input',{bubbles:true})); d.focus(); })()`);
      await tus("Enter", "Enter", 13); await bekle(150); k.enter = await ev(oku);                          // tarih alanında Enter
      k.tabSayisi = 0; while (k.tabSayisi < 10 && (await ev("document.activeElement.id")) !== "btn-tarih") { await tus("Tab", "Tab", 9); k.tabSayisi++; }     // tarih alanının gün/ay/yıl bölümleri ve takvim düğmesinden sonra hesaplama düğmesi
      k.tabSonrasi = await ev("document.activeElement.id");
      await tus("Enter", "Enter", 13); await bekle(150); k.dugmeEnter = await ev(oku);
      k.cerceve = await ev("(()=>{ const cs=getComputedStyle(document.activeElement); return cs.outlineStyle+' '+cs.outlineWidth; })()");
      await ev("document.getElementById('dt').focus()"); await tus("Backspace", "Backspace", 8); k.dtDegeri = await ev("document.getElementById('dt').value"); k.sonucTemizlendi = await ev("document.getElementById('tarih-sonuc').hidden");
      await tus("Enter", "Enter", 13); await bekle(150); k.hata = await ev(oku); k.hataRol = await ev("document.getElementById('tarih-hata').getAttribute('role')");
      k.olaylar = await ev("PlakaOlcum.kayit.slice()"); out.klavye.push(k);
    }

    // --- 3) ARAÇLAR BİRBİRİNİ BOZMAZ (hedef plaka aracı ↔ tarih aracı), ana sayfa ve il sayfası
    out.bagimsiz = {};
    await git("/"); out.bagimsiz.ana = await ev(`(()=>{ const g=id=>document.getElementById(id), tik=id=>g(id).click(); const hedef=()=>({res:g('target-res').style.display, out:g('target-out').textContent, plaka:g('target-plate').textContent});
      g('il').value='Konya'; g('target').value='BZZ 999'; tik('btn-target'); const h1=hedef(); g('tarih-il').value='Ankara'; g('dt').value='2027-03-01'; tik('btn-tarih'); const t1=g('plate-num').textContent; const h2=hedef();
      g('il').value='Kütahya'; g('target').value='GGL 100'; tik('btn-target'); const t2=g('plate-num').textContent, tg=g('tarih-sonuc').hidden, til=g('tarih-il').value, h3=hedef();
      return { h1, h2, h3, t1, t2, tarihGizli:tg, tarihIl:til }; })()`);
    await git("/il/konya"); out.bagimsiz.il = await ev(`(()=>{ const g=id=>document.getElementById(id); const hedef=()=>g('sonuc').textContent.replace(/\\s+/g,' ').trim();
      g('hedef').value='BZZ 999'; g('hedef-form').requestSubmit(); const h1=hedef(); g('dt').value='2027-03-01'; g('btn-tarih').click(); const t1=g('plate-num').textContent; const h2=hedef();
      g('hedef').value='GGL 100'; g('hedef-form').requestSubmit(); const h3=hedef(), t2=g('plate-num').textContent, tg=g('tarih-sonuc').hidden; return { h1, h2, h3, t1, t2, tarihGizli:tg }; })()`);

    // --- 4) ANA SAYFA: atlanacak seriler, sessiz yenileme, tüm iller tablosu
    await git("/"); out.gelismis = await ev(`(()=>{ const g=id=>document.getElementById(id), r={};
      g('tarih-il').value='İstanbul'; g('dt').value='2028-03-01'; g('btn-tarih').click(); r.once=g('plate-num').textContent; const ev0=PlakaOlcum.kayit.length;
      g('excl').value='SXX, TXX'; g('excl').dispatchEvent(new Event('input',{bubbles:true})); r.sonra=g('plate-num').textContent; r.uyari=g('tarih-uyari').hidden?'':g('tarih-uyari').textContent; r.excl2=g('excl2').value; r.bilgi=g('tarih-atla-bilgi').hidden?'':g('tarih-atla-bilgi').textContent; r.sessiz=PlakaOlcum.kayit.length===ev0; r.sonucGorunur=!g('tarih-sonuc').hidden;
      g('excl').value='QXX'; g('excl').dispatchEvent(new Event('input',{bubbles:true})); r.anlasilamayan=g('excl-warn').hidden?'gizli':'gorunur'; r.hedefExclEtkilenmedi=g('excl2').value===''; g('excl').value=''; g('excl').dispatchEvent(new Event('input',{bubbles:true})); r.geri=g('plate-num').textContent; return r; })()`);
    out.tablo = await ev(`(()=>{ const g=id=>document.getElementById(id), r={}; r.baslangic={kapali:g('all-wrap').hidden, ae:g('btn-all').getAttribute('aria-expanded'), etiket:g('btn-all').textContent, satir:g('all-tbl').rows.length};
      g('tarih-il').value='İstanbul'; g('dt').value='2028-03-01'; g('dt').dispatchEvent(new Event('input',{bubbles:true})); g('btn-tarih').click(); const plaka=g('plate-num').textContent;
      g('btn-all').click(); r.acik={kapali:g('all-wrap').hidden, ae:g('btn-all').getAttribute('aria-expanded'), etiket:g('btn-all').textContent, satir:g('all-tbl').rows.length, baslik:[...g('all-tbl').rows[0].cells].map(c=>c.textContent)};
      const ist=[...g('all-tbl').rows].find(x=>x.cells[1] && x.cells[1].textContent==='İstanbul'); r.istanbulSecili=ist.cells[5].textContent; r.sonucPlakasi=plaka;
      g('dt').value='2030-01-01'; g('dt').dispatchEvent(new Event('input',{bubbles:true})); r.baslikYeni=[...g('all-tbl').rows[0].cells].map(c=>c.textContent).join('|');
      g('btn-all').click(); r.kapandi={kapali:g('all-wrap').hidden, ae:g('btn-all').getAttribute('aria-expanded'), etiket:g('btn-all').textContent}; return r; })()`);

    // --- 4b) ATLANACAK SERİLER EŞLİĞİ: aynı il + tarih + atlanacak seri metni -> ana sayfa = il sayfası; kayıtlı pt-excl (hedef aracının ayarı) tarih sonucunu GİZLİCE etkilemez
    const A_IL = ["İstanbul", "Ankara", "İzmir", "Konya", "Hakkari"], A_TARIH = ["2025-06-15", "2027-03-01", "2028-07-01", "2030-06-01"], A_METIN = ["", "SXX, TXX", "BAA-BCZ", "TXX", "QXX", "BLX, BMX", "GJX, GKX", "DHX, DKX"], slugOf = Object.fromEntries(ILLER);
    const atlaTara = async () => { const r = { ana: {}, il: {} };
      await git("/"); for (const il of A_IL) for (const iso of A_TARIH) for (const m of A_METIN) r.ana[`${il}|${iso}|${m}`] = await atlaHesapla(iso, il, m);
      for (const il of A_IL) { await git("/il/" + slugOf[il]); for (const iso of A_TARIH) for (const m of A_METIN) r.il[`${il}|${iso}|${m}`] = await atlaHesapla(iso, null, m); }
      return r; };
    const atlaHesapla = async (iso, il, metin) => { await ev(`(()=>{ const g=id=>document.getElementById(id); ${il ? `g('tarih-il').value=${JSON.stringify(il)}; g('tarih-il').dispatchEvent(new Event('change',{bubbles:true}));` : ""} const e=g('excl'); e.value=${JSON.stringify(metin)}; e.dispatchEvent(new Event('input',{bubbles:true})); g('dt').value=${JSON.stringify(iso)}; g('dt').dispatchEvent(new Event('input',{bubbles:true})); g('btn-tarih').click(); })()`); return ev(oku); };
    out.atla = { temel: await atlaTara() };
    await git("/"); await ev("localStorage.setItem('pt-excl','SXX, TXX')");                                                 // hedef plaka aracının kalıcı ayarı (kayıtlı pt-excl)
    out.atla.kayitli = await atlaTara();
    await git("/"); out.atla.kayitliHedef = await ev(`(()=>{ const g=id=>document.getElementById(id); const r={ excl2:g('excl2').value, excl:g('excl').value, tarihAtla:g('tarih-atla-bilgi').hidden };
      g('il').value='İstanbul'; g('target').value='TAA'; g('btn-target').click(); r.hedef=g('target-out').textContent; return r; })()`);
    await git("/il/istanbul"); out.atla.kayitliIlHedef = await ev(`(()=>{ const g=id=>document.getElementById(id); g('hedef').value='TAA'; g('atla').value=''; g('hedef-form').requestSubmit(); return g('sonuc').textContent.replace(/\\s+/g,' ').trim(); })()`);
    await ev("localStorage.removeItem('pt-excl')");

    // --- 5) GENİŞLİKLER: yatay taşma, tek satır tam plaka, dokunma hedefi (ana sayfa + 5 il sayfası)
    out.genislik = [];
    for (const w of [320, 375, 390, 768, 1440]) for (const yol of ["/", "/il/konya", "/il/istanbul", "/il/hakkari", "/il/kars", "/il/ankara"]) {
      await git(yol, w, w < 500); await hesapla("2028-03-01"); if (yol === "/") await ev("document.getElementById('btn-all').click()");
      out.genislik.push({ w, yol, ...(await ev(`(()=>{ const g=id=>document.getElementById(id), p=g('plate-num'), rg=document.createRange(); rg.selectNodeContents(p); const t=rg.getBoundingClientRect(), c=g('tarih-sonuc').getBoundingClientRect(), de=document.documentElement;
        return { plaka:p.textContent, tasma:de.scrollWidth-de.clientWidth, tek:p.getBoundingClientRect().height<parseFloat(getComputedStyle(p).lineHeight)*1.4, sigar:t.left>=c.left-0.5&&t.right<=c.right+0.5, btn:Math.round(g('btn-tarih').getBoundingClientRect().height), px:parseFloat(getComputedStyle(p).fontSize) }; })()`)) });
    }
  } catch (e) { out.hatalar.push("BETIK: " + String(e)); }
  console.log(JSON.stringify(out)); ch.kill(); await bekle(300); process.exit(0);
})();
