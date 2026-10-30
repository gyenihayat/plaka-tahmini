// kullanım: node js_sim.js sayfa.html tarih1,tarih2,... [hata]  -> her tarih için sayfadaki canlı JS sonucunu JSON verir
const fs=require('fs'),vm=require('vm');
const page=fs.readFileSync(process.argv[2],'utf8'), tarihler=process.argv[3].split(','), hata=process.argv[4]==='hata';
const js=page.match(/<script>(\(function\(\)\{[\s\S]*?)<\/script><\/body>/)[1];
const live=[...page.matchAll(/data-live="(\w+)">([^<]*)</g)].map(m=>({k:m[1],t:m[2]}));
const hiddenAtStart=/id="guncellik"[^>]*\bhidden\b/.test(page);
const out=[];
for(const iso of tarihler){
  const [y,m,d]=iso.split('-').map(Number);
  const els=live.map(x=>({k:x.k,textContent:x.t,getAttribute(){return this.k}}));
  const span={textContent:""}; const u={hidden:hiddenAtStart,querySelector:()=>span};
  const errs=[]; const RD=Date;
  class FD extends RD{constructor(...a){a.length?super(...a):super(y,m-1,d,12)}}
  const ctx={Date:FD,console:{error:(...a)=>errs.push(String(a[0]))},document:{
    querySelectorAll:()=>{if(hata)throw new Error("dom");return els},
    getElementById:id=>id==="guncellik"?u:null}};
  vm.runInNewContext(js,ctx);
  const r={}; els.forEach(e=>r[e.k]=e.textContent);
  out.push({tarayici:iso,...r,uyari:u.hidden?null:span.textContent,consoleError:errs.length});
}
console.log(JSON.stringify(out));
