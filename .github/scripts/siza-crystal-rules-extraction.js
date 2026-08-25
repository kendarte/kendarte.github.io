const fs=require('fs');
const cp=require('child_process');
const vm=require('vm');
const {JSDOM,VirtualConsole}=require('jsdom');

const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;
const headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'};
const api=`https://api.github.com/repos/${repo}`;
const assert=(v,m)=>{if(!v)throw new Error(m)};

async function request(url,options={}){
  const r=await fetch(url,{...options,headers:{...headers,...(options.headers||{})}});
  if(!r.ok)throw new Error(`${options.method||'GET'} ${url}: ${r.status} ${await r.text()}`);
  return r.json();
}
async function getFile(path,ref='main'){
  const f=await request(`${api}/contents/${path}?ref=${encodeURIComponent(ref)}`);
  return {sha:f.sha,text:Buffer.from(f.content.replace(/\n/g,''),'base64').toString('utf8')};
}
function patchIndex(text){
  const manifestTag='<script src="../siza-core/manifest-rules.js"></script>';
  const crystalTag='<script src="../siza-core/crystal-rules.js"></script>';
  assert(text.includes(manifestTag),'manifest-rules tag missing');
  assert(!text.includes(crystalTag),'crystal-rules already linked');
  let out=text.replace(manifestTag,manifestTag+'\n'+crystalTag);
  const replacements=[
    ["function crystalReqV070(c){const r={};for(const[k,n]of Object.entries(c?.pips||{}))if(n>0)r[k]=n;return r}","function crystalReqV070(c){return SizaCrystalRules.crystalReq(c)}"],
    ["function spellCostV070(c){return c?.type==='Land'?0:Math.max(1,Object.values(crystalReqV070(c)).reduce((a,b)=>a+b,0))}","function spellCostV070(c){return SizaCrystalRules.spellCost(c)}"],
    ["function directPlanV070(P,c){const req=crystalReqV070(c),spent={};for(const[k,n]of Object.entries(req)){if((P.crystals?.[k]||0)<n)return null;spent[k]=n}if(!Object.keys(req).length){const opts=['U','R','G','W','B'].filter(k=>(P.crystals?.[k]||0)>0);return opts.length?{kind:'flex',options:opts}:null}return{kind:'direct',spent}}","function directPlanV070(P,c){return SizaCrystalRules.directPlan(P,c)}"]
  ];
  for(const [oldValue,newValue] of replacements){assert(out.includes(oldValue),`runtime anchor missing: ${oldValue.slice(0,32)}`);out=out.replace(oldValue,newValue)}
  return out;
}
function patchHarness(text,path){
  const old="['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js']";
  const next="['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js']";
  assert(text.includes(old),`${path}: shared module list missing`);
  return text.replace(old,next);
}
function patchArenaWorkflow(text){
  const old="'siza-core/manifest-rules.js','.github/scripts/siza-arena-regression.js'";
  const next="'siza-core/manifest-rules.js','siza-core/crystal-rules.js','.github/scripts/siza-arena-regression.js'";
  assert(text.includes(old),'Arena workflow input anchor missing');
  return text.replace(old,next);
}
function patchCardCoreWorkflow(text){
  let out=text;
  const filesOld="'siza-core/cards.js','siza-core/manifest-rules.js','siza-card-generator/index.html'";
  const filesNew="'siza-core/cards.js','siza-core/manifest-rules.js','siza-core/crystal-rules.js','siza-card-generator/index.html'";
  assert(out.includes(filesOld),'card-core files anchor missing');out=out.replace(filesOld,filesNew);
  const vmOld="          vm.runInContext(fs.readFileSync('siza-core/manifest-rules.js','utf8'),context);";
  const vmNew=vmOld+"\n          vm.runInContext(fs.readFileSync('siza-core/crystal-rules.js','utf8'),context);";
  assert(out.includes(vmOld),'card-core vm anchor missing');out=out.replace(vmOld,vmNew);
  const constOld="          const E=context.window.SizaCardEffects,S=context.window.SizaCardSchema,R=context.window.SizaCardRenderer,C=context.window.SizaCardCatalog,M=context.window.SizaManifestRules;";
  const constNew="          const E=context.window.SizaCardEffects,S=context.window.SizaCardSchema,R=context.window.SizaCardRenderer,C=context.window.SizaCardCatalog,M=context.window.SizaManifestRules,X=context.window.SizaCrystalRules;";
  assert(out.includes(constOld),'card-core const anchor missing');out=out.replace(constOld,constNew);
  const loopAnchor="          for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);";
  const crystalTest="          test('Cristales compartidos conservan requisito coste y pago directo',()=>{const c={type:'Creature',cost:9,pips:{U:2,R:1,G:0}},p={crystals:{U:2,R:1,G:0,W:1,B:0}},req=X.crystalReq(c),direct=X.directPlan(p,c),flex=X.directPlan(p,{type:'Creature',cost:4,pips:{}});return JSON.stringify(req)==='{\"U\":2,\"R\":1}'&&X.spellCost(c)===3&&X.spellCost({type:'Creature',cost:8,pips:{}})===1&&X.spellCost({type:'Land',cost:8,pips:{U:3}})===0&&direct?.kind==='direct'&&direct.spent.U===2&&direct.spent.R===1&&flex?.kind==='flex'&&JSON.stringify(flex.options)==='[\"U\",\"R\",\"W\"]'&&X.directPlan({crystals:{U:1,R:1}},c)===null});\n";
  assert(out.includes(loopAnchor),'card-core test loop anchor missing');out=out.replace(loopAnchor,crystalTest+loopAnchor);
  const bridgeOld="let html=fs.readFileSync('siza-mobile-test/index.html','utf8'),effects=fs.readFileSync('siza-core/card-effects.js','utf8'),schema=fs.readFileSync('siza-core/card-schema.js','utf8'),renderer=fs.readFileSync('siza-core/card-renderer.js','utf8'),catalog=fs.readFileSync('siza-core/cards.js','utf8'),manifest=fs.readFileSync('siza-core/manifest-rules.js','utf8');";
  const bridgeNew="let html=fs.readFileSync('siza-mobile-test/index.html','utf8'),effects=fs.readFileSync('siza-core/card-effects.js','utf8'),schema=fs.readFileSync('siza-core/card-schema.js','utf8'),renderer=fs.readFileSync('siza-core/card-renderer.js','utf8'),catalog=fs.readFileSync('siza-core/cards.js','utf8'),manifest=fs.readFileSync('siza-core/manifest-rules.js','utf8'),crystal=fs.readFileSync('siza-core/crystal-rules.js','utf8');";
  assert(out.includes(bridgeOld),'card-core bridge variables anchor missing');out=out.replace(bridgeOld,bridgeNew);
  const inlineOld="          if(html.includes('<script src=\"../siza-core/manifest-rules.js\"></script>'))html=html.replace('<script src=\"../siza-core/manifest-rules.js\"></script>',`<script>${manifest}</script>`);";
  const inlineNew=inlineOld+"\n          if(html.includes('<script src=\"../siza-core/crystal-rules.js\"></script>'))html=html.replace('<script src=\"../siza-core/crystal-rules.js\"></script>',`<script>${crystal}</script>`);";
  assert(out.includes(inlineOld),'card-core bridge inline anchor missing');out=out.replace(inlineOld,inlineNew);
  return out;
}
function patchHandoffWorkflow(text){
  let out=text;
  const varsOld="catalog=await get('siza-core/cards.js'),manifest=await get('siza-core/manifest-rules.js');";
  const varsNew="catalog=await get('siza-core/cards.js'),manifest=await get('siza-core/manifest-rules.js'),crystal=await get('siza-core/crystal-rules.js');";
  assert(out.includes(varsOld),'handoff vars anchor missing');out=out.replace(varsOld,varsNew);
  const inlineOld="if(html.includes('<script src=\"../siza-core/manifest-rules.js\"></script>'))html=html.replace('<script src=\"../siza-core/manifest-rules.js\"></script>',`<script>${manifest}</script>`);const marker='window.SIZA={';";
  const inlineNew="if(html.includes('<script src=\"../siza-core/manifest-rules.js\"></script>'))html=html.replace('<script src=\"../siza-core/manifest-rules.js\"></script>',`<script>${manifest}</script>`);if(html.includes('<script src=\"../siza-core/crystal-rules.js\"></script>'))html=html.replace('<script src=\"../siza-core/crystal-rules.js\"></script>',`<script>${crystal}</script>`);const marker='window.SIZA={';";
  assert(out.includes(inlineOld),'handoff inline anchor missing');out=out.replace(inlineOld,inlineNew);
  return out;
}
function inlineCore(html,files,withCrystal){
  let out=html;
  const names=['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js',...(withCrystal?['crystal-rules.js']:[])];
  for(const name of names){const tag=`<script src="../siza-core/${name}"></script>`;assert(out.includes(tag),`Missing tag ${name}`);out=out.replace(tag,`<script>${files[name]}</script>`)}
  return out;
}
function makeDom(html,label){const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error(`[JSDOM ${label}]`,e.message));const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.setTimeout=()=>0;return dom}
function compareRules(oldHtml,newHtml,files){
  const marker='window.SIZA={';assert(oldHtml.includes(marker)&&newHtml.includes(marker),'SIZA marker missing');
  const probe=`window.__CRYSTAL_EXTRACT__={crystalReqV070,spellCostV070,directPlanV070,cardById};\n`;
  const oldDom=makeDom(inlineCore(oldHtml,files,false).replace(marker,probe+marker),'crystal-old');
  const newDom=makeDom(inlineCore(newHtml,files,true).replace(marker,probe+marker),'crystal-new');
  const O=oldDom.window.__CRYSTAL_EXTRACT__,N=newDom.window.__CRYSTAL_EXTRACT__;
  const cards=['mist','spark','servitor','ignimite','counter','prism','watcher','smuggler','tideblade','leviathan','dock','cinder','queen'].map(id=>O.cardById(id));
  cards.push({id:'no_pips',type:'Creature',cost:9,pips:{}},{id:'odd_pips',type:'Creature',cost:0,pips:{U:2,R:1,G:0}});
  const players=[{crystals:{U:2,R:1,G:0,W:0,B:0}},{crystals:{U:1,R:1,G:1,W:1,B:1}},{crystals:{U:0,R:0,G:0,W:0,B:0}}];
  for(const c of cards){assert(JSON.stringify(O.crystalReqV070(c))===JSON.stringify(N.crystalReqV070(c)),`req mismatch ${c.id}`);assert(O.spellCostV070(c)===N.spellCostV070(c),`cost mismatch ${c.id}`);for(const p of players)assert(JSON.stringify(O.directPlanV070(p,c))===JSON.stringify(N.directPlanV070(p,c)),`direct plan mismatch ${c.id}`)}
  const a=oldDom.window.SIZA.runArenaCriticalV071(),b=newDom.window.SIZA.runArenaCriticalV071();assert(a.passed===a.total&&b.passed===b.total,`Arena ${a.passed}/${a.total} -> ${b.passed}/${b.total}`);
  console.log(`PASS crystal old/new equivalence across ${cards.length} cards x ${players.length} pools; Arena ${a.passed}/${a.total}`);
  oldDom.window.close();newDom.window.close();
}
function unitCrystal(source){const context={window:{}};vm.createContext(context);vm.runInContext(source,context);const X=context.window.SizaCrystalRules;assert(X,'SizaCrystalRules missing');const c={type:'Creature',cost:99,pips:{U:2,R:1,G:0}},p={crystals:{U:2,R:1,G:0,W:1,B:0}};assert(JSON.stringify(X.crystalReq(c))==='{"U":2,"R":1}','crystalReq unit');assert(X.spellCost(c)===3,'spellCost unit');assert(X.spellCost({type:'Land',cost:9,pips:{U:4}})===0,'Land cost unit');assert(JSON.stringify(X.directPlan(p,c))==='{"kind":"direct","spent":{"U":2,"R":1}}','direct unit');assert(JSON.stringify(X.directPlan(p,{type:'Creature',pips:{}}))==='{"kind":"flex","options":["U","R","W"]}','flex unit');console.log('PASS standalone crystal core unit')}
async function atomicCommit(changes,message){
  const ref=await request(`${api}/git/ref/heads/main`),parentSha=ref.object.sha,commit=await request(`${api}/git/commits/${parentSha}`),treeEntries=[];
  for(const [path,text] of Object.entries(changes)){const blob=await request(`${api}/git/blobs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:text,encoding:'utf-8'})});treeEntries.push({path,mode:'100644',type:'blob',sha:blob.sha})}
  const tree=await request(`${api}/git/trees`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_tree:commit.tree.sha,tree:treeEntries})});
  const created=await request(`${api}/git/commits`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,tree:tree.sha,parents:[parentSha]})});
  await request(`${api}/git/refs/heads/main`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({sha:created.sha,force:false})});return created.sha;
}

(async()=>{
  const index=await getFile('siza-mobile-test/index.html');console.log('Current Mobile blob '+index.sha);
  const harnessPaths=['.github/scripts/siza-arena-regression.js','.github/scripts/siza-combat-effects-regression.js','.github/scripts/siza-prism-effects-regression.js','.github/scripts/siza-equipment-effects-regression.js','.github/scripts/siza-battlefield-ui-index-regression.js'];
  const coreNames=['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js'];const files={};for(const name of coreNames)files[name]=(await getFile(`siza-core/${name}`)).text;
  unitCrystal(files['crystal-rules.js']);
  const changes={'siza-mobile-test/index.html':patchIndex(index.text)};
  for(const path of harnessPaths)changes[path]=patchHarness((await getFile(path)).text,path);
  changes['.github/workflows/siza-arena-tests.yml']=patchArenaWorkflow((await getFile('.github/workflows/siza-arena-tests.yml')).text);
  changes['.github/workflows/siza-card-core-tests.yml']=patchCardCoreWorkflow((await getFile('.github/workflows/siza-card-core-tests.yml')).text);
  changes['.github/workflows/siza-card-handoff-tests.yml']=patchHandoffWorkflow((await getFile('.github/workflows/siza-card-handoff-tests.yml')).text);
  compareRules(index.text,changes['siza-mobile-test/index.html'],files);
  for(const [path,text] of Object.entries(changes)){const dir=path.split('/').slice(0,-1).join('/');if(dir)fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path,text)}
  for(const name of coreNames){fs.mkdirSync('siza-core',{recursive:true});fs.writeFileSync(`siza-core/${name}`,files[name])}
  for(const path of harnessPaths){console.log(`RUN ${path}`);cp.execFileSync('node',[path],{stdio:'inherit'})}
  const sha=await atomicCommit(changes,'Extract pure crystal payment rules into shared core');console.log('COMMIT '+sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
