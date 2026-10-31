// GitHub Contents API taklidi (bellekte): gerçek ağ/commit yok. SHA çakışması, 404/201 oluşturma ve 422 yarışı GitHub'daki gibi davranır.
"use strict";
const crypto = require("crypto");
const yeniSha = s => crypto.createHash("sha1").update(String(s) + Math.random()).digest("hex");

function githubTaklidi({ depo = "gyenihayat/geri-bildirimler", ozel = true, dosyalar = {}, kanca = null } = {}) {
  const dosya = new Map(Object.entries(dosyalar).map(([k, v]) => [k, { icerik: v, sha: yeniSha(k) }]));
  const cagrilar = [], commitler = [];
  const yanit = (durum, govde) => new Response(JSON.stringify(govde), { status: durum, headers: { "Content-Type": "application/json" } });
  async function fetch(url, init = {}) {
    const u = new URL(url), yontem = init.method || "GET", n = cagrilar.push({ yontem, yol: u.pathname, arama: u.search, basliklar: init.headers, govde: init.body });
    if (kanca) { const r = await kanca({ yontem, u, init, dosya, cagrilar, n, yeniSha }); if (r) return r; }
    const on = `/repos/${depo}`;
    if (u.pathname === on) return yanit(200, { full_name: depo, private: ozel });
    if (!u.pathname.startsWith(on + "/contents/")) return yanit(404, { message: "Not Found" });
    const yol = decodeURIComponent(u.pathname.slice((on + "/contents/").length));
    if (yontem === "GET") {
      const d = dosya.get(yol); if (!d) return yanit(404, { message: "Not Found" });
      return yanit(200, { type: "file", encoding: "base64", sha: d.sha, content: Buffer.from(d.icerik, "utf8").toString("base64").replace(/(.{60})/g, "$1\n") });
    }
    if (yontem === "PUT") {
      const b = JSON.parse(init.body), d = dosya.get(yol);
      if (d && !b.sha) return yanit(422, { message: "Invalid request.\n\n\"sha\" wasn't supplied." });
      if (d && b.sha !== d.sha) return yanit(409, { message: `${yol} does not match ${b.sha}` });
      if (!d && b.sha) return yanit(422, { message: "Invalid request." });
      const icerik = Buffer.from(b.content, "base64").toString("utf8"), sha = yeniSha(yol + icerik);
      dosya.set(yol, { icerik, sha }); commitler.push({ yol, mesaj: b.message, dal: b.branch });
      return yanit(d ? 200 : 201, { content: { sha }, commit: { sha: yeniSha("c") } });
    }
    return yanit(405, {});
  }
  return { fetch, dosya, cagrilar, commitler, yazilanYollar: () => [...new Set(cagrilar.filter(c => c.yontem === "PUT").map(c => c.yol))] };
}
module.exports = { githubTaklidi, yanit: (d, g) => new Response(JSON.stringify(g), { status: d }) };
