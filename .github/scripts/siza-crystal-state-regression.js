const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

let html=fs.readFileSync('siza-mobile-test/index.html','utf8');
for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js']){
  const tag=`<script src="../siza-core/${name}"></script>`;
  if(!html.includes(tag))throw new Error(`Missing shared core tag ${name}`);
  html=html.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
}
const entryTag='<script src="../siza-core/entry-rules.js"></script>';
if(html.includes(entryTag))html=html.replace(entryTag,`<script>${fs.readFileSync('siza-core/entry-rules.js','utf8')}</script>`);
const marker='window.SIZA={';if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__CRYSTAL_STATE_REGRESSION__={createMatch,setMatch:m=>state.match=m,resetCrystalsV070,spendV070};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM crystal-state]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.setTimeout=()=>0;
const H=dom.window.__CRYSTAL_STATE_REGRESSION__;if(!H)throw new Error('Crystal state hooks unavailable');
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};

test('Reset restaura afinidad positiva y limpia Ofrenda/Prisma',()=>{const M=H.createMatch(false,'prepare'),P=M.player;H.setMatch(M);P.aff={U:2,R:1,G:0};P.crystals={U:0,R:0,G:9};P.offeringUsed=true;P.artifactExhausted=[0,2];P.exhausted=[1];H.resetCrystalsV070(P);return JSON.stringify(P.crystals)==='{"U":2,"R":1}'&&P.offeringUsed===false&&P.artifactExhausted.length===0&&JSON.stringify(P.exhausted)==='[1]'});
test('Spend consume exactamente el plan disponible',()=>{const P={crystals:{U:2,R:1}};return H.spendV070(P,{U:1,R:1})===true&&JSON.stringify(P.crystals)==='{"U":1,"R":0}'});
test('Spend insuficiente falla sin consumo parcial',()=>{const P={crystals:{U:1,R:1}};const before=JSON.stringify(P.crystals),ok=H.spendV070(P,{U:2,R:1});return ok===false&&JSON.stringify(P.crystals)===before});
test('Spend vacío es válido y no altera cristales',()=>{const P={crystals:{U:1,R:1}};return H.spendV070(P,{})===true&&JSON.stringify(P.crystals)==='{"U":1,"R":1}'});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA crystal state regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
