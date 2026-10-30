// "Altın" çıktı üreticisi: ana sayfa JS motoru ortak modüle çıkarılmadan ÖNCE (commit 9b65ce4) index.html'deki motorla üretildi.
// Kullanım (yalnızca motor matematiği bilerek değiştirilirse yeniden üretilir):
//   git show 9b65ce4:index.html > /tmp/eski_index.html
//   node tests/golden/uret_golden.js /tmp/eski_index.html tests/golden/motor_veri.json tests/golden/motor_golden.json
// Motor, eski index.html'in 158-164 ve 170-311. satırlarıdır (DATA ve DOM satırları hariç).
const fs = require("fs"), hesapla = require("./ortak.js");
const [, , indexYol, veriYol, ciktiYol] = process.argv;
const L = fs.readFileSync(indexYol, "utf8").split("\n");
const motor = [...L.slice(157, 164), ...L.slice(169, 311)].join("\n");
const out = hesapla(motor, JSON.parse(fs.readFileSync(veriYol, "utf8")));
fs.writeFileSync(ciktiYol, JSON.stringify(out));
console.log("golden:", Object.keys(out.iller).length, "il");
