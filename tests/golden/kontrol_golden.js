// Ortak modülün (assets/tahmin-motoru.js) çıktılarını, eski index.html motorundan üretilen altın çıktıyla karşılaştırır. Fark varsa 1 ile çıkar.
const fs = require("fs"), path = require("path"), assert = require("assert"), hesapla = require("./ortak.js");
const kok = path.join(__dirname, "..", "..");
const yeni = hesapla(fs.readFileSync(path.join(kok, "assets", "tahmin-motoru.js"), "utf8"), JSON.parse(fs.readFileSync(path.join(__dirname, "motor_veri.json"), "utf8")));
const altin = JSON.parse(fs.readFileSync(path.join(__dirname, "motor_golden.json"), "utf8"));
assert.deepStrictEqual(JSON.parse(JSON.stringify(yeni)), altin);
console.log("altın çıktı eşleşti:", Object.keys(altin.iller).length, "il");
