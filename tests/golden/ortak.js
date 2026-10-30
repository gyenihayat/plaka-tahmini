// Motor çıktılarını (estimateAt, reachDate, parseExcl, kodlama, fit) hesaplar. uret_golden.js ve kontrol_golden.js ortak kullanır.
const vm = require("vm");
module.exports = function hesapla(motorKaynak, veri) {
  const motor = motorKaynak;
const ctx = { Math, Date, console }; vm.createContext(ctx);
vm.runInContext(motor + "\n;this.__m={fit,cleanCum,estimateAt,reachDate,parseExcl,invN,toN,dstr,errDays,setExcl:x=>{EXCL=x}};", ctx);
const m = ctx.__m;
const r6 = x => (typeof x === "number" ? Math.round(x * 1e6) / 1e6 : x);
const sade = r => { const o = {}; for (const k of ["passed","back","never","excluded","day","err","atlanan","back_h"]) if (r[k] !== undefined) o[k] = r[k]; if (r.first) o.first = r.first; return o; };
const EXCLS = ["", "SXX, TXX", "BAA-BCZ", "A", "AZ", "ABC", "S-", "XYZ", "bad!!"];
const out = { iller: {}, parseExcl: {}, kodlama: [] };
for (const e of EXCLS) { const p = m.parseExcl(e); out.parseExcl[e] = { intervals: p.intervals, bad: p.bad }; }
for (const s of veri.iller) {
  const last = s.obs[s.obs.length - 1], first = s.obs[0], g = {};
  g.estimate = [0, 1, 3, 7, 30, 90, 181, 400, 800].map(h => { m.setExcl([]); const r = m.estimateAt(s, last[0] + h); return [h, r6(r.n), r.err ?? null]; });
  g.estimate_gecmis = [first[0], Math.round((first[0] + last[0]) / 2), last[0]].map(d => { m.setExcl([]); return [d, r6(m.estimateAt(s, d).n)]; });
  const sonSeri = Math.floor(last[1] / 1000), grp = m.invN(last[1]).let[0];
  const hedefler = {
    grup_sonu: m.toN(grp + "ZZ", 999), sonraki_seri: (sonSeri + 1) * 1000 + 1, plus10: (sonSeri + 10) * 1000 + 500, plus100: (sonSeri + 100) * 1000 + 1,
    plus1000: (sonSeri + 1000) * 1000 + 1, gecmis5: (sonSeri - 5) * 1000 + 1, ilk_oncesi: first[1] - 3000, ilk: first[1], son: last[1], son_arti1: last[1] + 1,
  };
  g.reach = {};
  for (const [ad, n] of Object.entries(hedefler)) { m.setExcl([]); g.reach[ad] = sade(m.reachDate(s, n)); }
  g.reach_excl = {};
  const ex = m.parseExcl(m.invN((sonSeri + 3) * 1000 + 1).let.slice(0, 2) + "X, " + m.invN((sonSeri + 40) * 1000 + 1).let.slice(0, 2) + "X"); m.setExcl(ex.intervals);
  for (const ad of ["plus10", "plus100", "plus1000"]) g.reach_excl[ad] = sade(m.reachDate(s, hedefler[ad]));
  g.excl_aralik = ex.intervals; m.setExcl([]);
  g.fit = (f => ({ slope: r6(f.slope), rstd: r6(f.rstd), n: f.n, win: f.win, skipped: f.skipped }))(m.fit(s, last[0]));
  out.iller[s.il] = g;
}
for (const t of [["AAA", 1], ["ZZZ", 999], ["BJB", 820], ["GGL", 96], ["IAA", 1], ["AIA", 1], ["QAA", 1]]) { const n = m.toN(t[0], t[1]); out.kodlama.push([t[0], t[1], n, n == null ? null : m.invN(n)]); }
for (const n of [0, 1, 999, 1000, 123456, 672124, 1e7]) out.kodlama.push(["inv", n, m.invN(n)]);
out.dstr = [0, 39, 1026, 1100].map(d => [d, m.dstr(d)]);
  return out;
};
