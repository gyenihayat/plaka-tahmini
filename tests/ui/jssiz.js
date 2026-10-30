// Kullanım: node jssiz.js <chrome> <url> [<url>...]  -> JavaScript kapalıyken (Emulation.setScriptExecutionDisabled) sayfanın görünen temel içeriğini ve bağlantılarını ölçer.
const { spawn } = require("child_process"), fs = require("fs"), os = require("os"), path = require("path");
const [, , CHROME, ...urller] = process.argv, PORT = 9361, dir = fs.mkdtempSync(path.join(os.tmpdir(), "jssiz_"));
const ch = spawn(CHROME, ["--headless=new", "--disable-gpu", "--host-resolver-rules=MAP abacus.jasoncameron.dev ~NOTFOUND, MAP *.goatcounter.com ~NOTFOUND, MAP gc.zgo.at ~NOTFOUND", `--remote-debugging-port=${PORT}`, `--user-data-dir=${dir}`, "about:blank"], { stdio: "ignore" });
const bekle = ms => new Promise(r => setTimeout(r, ms));
async function hedef() { for (let i = 0; i < 60; i++) { try { return await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json(); } catch (e) { await bekle(200); } } throw new Error("Chrome açılmadı"); }
(async () => {
  const out = [];
  try {
    for (const url of urller) {
      const t = await hedef(), ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
      let id = 0; const bek = {}; ws.onmessage = m => { const x = JSON.parse(m.data); if (x.id && bek[x.id]) { bek[x.id](x); delete bek[x.id]; } };
      const send = (method, params = {}) => new Promise(r => { const i = ++id; bek[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
      await send("Page.enable"); await send("Runtime.enable"); await send("Emulation.setScriptExecutionDisabled", { value: true });
      await send("Page.navigate", { url }); await bekle(1500);
      const r = await send("Runtime.evaluate", { expression: `JSON.stringify({h1:(document.querySelector('h1')||{}).textContent,seri:(document.querySelector('.buyuk')||document.querySelector('.k-seri')||{}).textContent,gozlem:!!document.querySelector('.metrik')||!!document.querySelector('.k-gozlem'),
        linkler:document.querySelectorAll('a[href^="/il/"]').length,not:!!document.querySelector('.olcum-notu'),betikGC:!!document.querySelector('script[data-goatcounter]'),olcum:typeof PlakaOlcum,formAction:(document.querySelector('form')||{}).getAttribute&&document.querySelector('form').getAttribute('action'),
        sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})`, returnByValue: true });
      out.push({ url, ...JSON.parse(r.result.result.value) }); ws.close(); fetch(`http://127.0.0.1:${PORT}/json/close/${t.id}`).catch(() => {});
    }
  } catch (e) { out.push({ hata: String(e) }); }
  console.log(JSON.stringify(out)); ch.kill(); process.exit(0);
})();
