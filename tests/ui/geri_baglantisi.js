// Kullanım: node geri_baglantisi.js <chrome> <taban_url> <sayfa_yolu>...  -> 375 ve 1440 px'te "← Tüm illere dön" bağlantısını GERÇEK klavye olaylarıyla (Tab, Enter) ve konum ölçümüyle sınar.
// Chrome, abacus/goatcounter adlarını çözemeyecek şekilde başlatılır (test ziyareti ölçüm göndermez).
const { spawn } = require("child_process"), fs = require("fs"), os = require("os"), path = require("path");
const [, , CHROME, TABAN, ...sayfalar] = process.argv, PORT = 9362, dir = fs.mkdtempSync(path.join(os.tmpdir(), "geri_"));
const ch = spawn(CHROME, ["--headless=new", "--disable-gpu", "--host-resolver-rules=MAP abacus.jasoncameron.dev ~NOTFOUND, MAP *.goatcounter.com ~NOTFOUND, MAP gc.zgo.at ~NOTFOUND", `--remote-debugging-port=${PORT}`, `--user-data-dir=${dir}`, "about:blank"], { stdio: "ignore" });
const bekle = ms => new Promise(r => setTimeout(r, ms));
async function hedef() { for (let i = 0; i < 60; i++) { try { return await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json(); } catch (e) { await bekle(200); } } throw new Error("Chrome açılmadı"); }
(async () => {
  const out = [];
  try {
    const t = await hedef(), ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
    let id = 0; const bek = {}; ws.onmessage = m => { const x = JSON.parse(m.data); if (x.id && bek[x.id]) { bek[x.id](x); delete bek[x.id]; } };
    const send = (method, params = {}) => new Promise(r => { const i = ++id; bek[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
    const ev = async e => (await send("Runtime.evaluate", { expression: e, returnByValue: true })).result.result.value;
    const tus = async (key, code, vk) => { for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, text: key === "Enter" ? "\r" : undefined }); };
    await send("Page.enable"); await send("Runtime.enable");
    const bilgi = `(()=>{ const a=document.activeElement, cs=getComputedStyle(a); return { etiket:a.tagName, metin:a.textContent.trim(), href:a.getAttribute('href'), cerceve:cs.outlineStyle+' '+cs.outlineWidth, cerceveRenk:cs.outlineColor }; })()`;
    for (const w of [375, 1440]) {
      await send("Emulation.setDeviceMetricsOverride", { width: w, height: 800, deviceScaleFactor: 1, mobile: w < 500 });
      for (const s of sayfalar) {
        await send("Page.navigate", { url: TABAN + s }); await bekle(900);
        const r = { w, s };
        r.olcum = await ev(`(()=>{ const g=document.querySelector('.geri a'), e=document.querySelector('.eyebrow a'), h=document.querySelector('h1'), gr=g.getBoundingClientRect(), hr=h.getBoundingClientRect(), er=document.querySelector('.eyebrow').getBoundingClientRect(), cs=getComputedStyle(g);
          return { sayi:document.querySelectorAll('.geri a').length, href:g.getAttribute('href'), metin:g.textContent.replace(/\\s+/g,' ').trim(), eyebrowHref:e.getAttribute('href'), sira:!!document.querySelector('.eyebrow + .geri + h1'), ustuH1:gr.bottom<=hr.top+0.5, bosluk:Math.round(hr.top-gr.bottom), eyebrowAlti:gr.top>=er.bottom-0.5,
            yuk:Math.round(gr.height), genis:Math.round(gr.width), px:parseFloat(cs.fontSize), renk:cs.color, tasma:document.documentElement.scrollWidth-innerWidth, ekranda:gr.top>=0&&gr.bottom<=innerHeight }; })()`);
        await tus("Tab", "Tab", 9); r.tab1 = await ev(bilgi); await tus("Tab", "Tab", 9); r.tab2 = await ev(bilgi);
        await tus("Enter", "Enter", 13); await bekle(1200);
        r.sonra = await ev(`(()=>{ const h=document.getElementById('il-baslik'), b=h?h.getBoundingClientRect():null; return { yol:location.pathname, hash:location.hash, baslik:h?h.textContent.trim():null, ekranda:b?(b.top>=-1&&b.top<innerHeight):false, ust:b?Math.round(b.top):null, formVar:!!document.getElementById('il-form') }; })()`);
        out.push(r);
      }
    }
    ws.close();
  } catch (e) { out.push({ hata: String(e) }); }
  console.log(JSON.stringify(out)); ch.kill(); await bekle(300); process.exit(0);
})();
