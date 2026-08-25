const fs=require('fs');
const cp=require('child_process');
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
function patchHarness(text,path){
  const old="['card-effects.js','card-schema.js','cards.js','card-renderer.js']";
  const next="['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js']";
  assert(text.includes(old),`${path}: shared core list anchor missing`);
  const out=text.replace(old,next);
  assert(out.includes('manifest-rules.js'),`${path}: manifest module not added`);
  return out;
}
function patchIndex(text){
  const tag='<script src="../siza-core/card-renderer.js"></script>';
  assert(text.includes(tag),'card-renderer tag missing');
  assert(!text.includes('<script src="../siza-core/manifest-rules.js"></script>'),'manifest-rules already linked');
  let out=text.replace(tag,tag+'\n<script src="../siza-core/manifest-rules.js"></script>');
  const old=`function affinityInfo(c,m=state.player.mag){let penalty=0,unsupported=[];for(const [k,v] of Object.entries(c.pips||{})){if(v<=0)continue;const a=m.aff[k]||0;if(a===0)unsupported.push(k);else if(v>a)penalty+=v-a}return {penalty,unsupported}}\nfunction dcFor(c,m=state.player.mag){const ai=affinityInfo(c,m);if(ai.unsupported.length)return Infinity;return c.difficulty??(4+Math.ceil((c.cost+1)/2))}\nfunction naturalChance(c,m=state.player.mag){if(c.type==='Land')return 100;const dc=dcFor(c,m);if(!isFinite(dc))return 0;const need=dc-m.mf;if(need<=1)return 100;if(need>6)return 0;return Math.round((7-need)/6*100)}\nfunction manifestRequirement(c,m=state.player.mag){const dc=dcFor(c,m);if(!isFinite(dc))return {unsupported:true,text:'SIN AFINIDAD',die:0,minBurn:0};const raw=dc-m.mf,minBurn=Math.max(0,raw-6),die=Math.max(1,Math.min(6,raw));return {unsupported:false,die,minBurn,text:minBurn?\`${'${die}'}+ · Burn mínimo ${'${minBurn}'}\`:\`${'${die}'}+\`}}`;
  const next=`function affinityInfo(c,m=state.player.mag){return SizaManifestRules.affinityInfo(c,m)}\nfunction dcFor(c,m=state.player.mag){return SizaManifestRules.dcFor(c,m)}\nfunction naturalChance(c,m=state.player.mag){return SizaManifestRules.naturalChance(c,m)}\nfunction manifestRequirement(c,m=state.player.mag){return SizaManifestRules.manifestRequirement(c,m)}`;
  assert(out.includes(old),'Manafestation rule block anchor missing');
  out=out.replace(old,next);
  assert(out.includes('return SizaManifestRules.manifestRequirement(c,m)'),'manifest wrapper missing');
  return out;
}
function inlineCore(html,files,withManifest){
  let out=html;
  const names=['card-effects.js','card-schema.js','cards.js','card-renderer.js',...(withManifest?['manifest-rules.js']:[])];
  for(const name of names){
    const tag=`<script src="../siza-core/${name}"></script>`;
    assert(out.includes(tag),`Missing tag ${name}`);
    out=out.replace(tag,`<script>${files[name]}</script>`);
  }
  return out;
}
function makeDom(html,label){
  const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error(`[JSDOM ${label}]`,e.message));
  const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.setTimeout=()=>0;return dom;
}
function compareRules(oldHtml,newHtml,files){
  const marker='window.SIZA={';assert(oldHtml.includes(marker)&&newHtml.includes(marker),'SIZA marker missing');
  const probe=`window.__MANIFEST_EXTRACT__={affinityInfo,dcFor,naturalChance,manifestRequirement,cardById};\n`;
  const oldDom=makeDom(inlineCore(oldHtml,files,false).replace(marker,probe+marker),'manifest-old');
  const newDom=makeDom(inlineCore(newHtml,files,true).replace(marker,probe+marker),'manifest-new');
  const O=oldDom.window.__MANIFEST_EXTRACT__,N=newDom.window.__MANIFEST_EXTRACT__;
  const mags=[{mf:2,aff:{U:2,R:1,G:0}},{mf:1,aff:{U:0,R:2,G:1}},{mf:4,aff:{U:3,R:0,G:0}}];
  const cards=['mist','spark','servitor','ignimite','counter','prism','watcher','smuggler','tideblade','leviathan','dock','cinder','queen'].map(id=>O.cardById(id));
  cards.push({id:'fallback',type:'Creature',cost:3,pips:{}},{id:'unsupported',type:'Creature',cost:2,difficulty:9,pips:{G:1}});
  for(const mag of mags)for(const c of cards){
    const oa=O.affinityInfo(c,mag),na=N.affinityInfo(c,mag);assert(JSON.stringify(oa)===JSON.stringify(na),`affinity mismatch ${c.id}`);
    const od=O.dcFor(c,mag),nd=N.dcFor(c,mag);assert(Object.is(od,nd),`dc mismatch ${c.id}: ${od} != ${nd}`);
    assert(O.naturalChance(c,mag)===N.naturalChance(c,mag),`chance mismatch ${c.id}`);
    assert(JSON.stringify(O.manifestRequirement(c,mag))===JSON.stringify(N.manifestRequirement(c,mag)),`requirement mismatch ${c.id}`);
  }
  const a=oldDom.window.SIZA.runArenaCriticalV071(),b=newDom.window.SIZA.runArenaCriticalV071();
  assert(a.passed===a.total&&b.passed===b.total,`Arena compare ${a.passed}/${a.total} -> ${b.passed}/${b.total}`);
  console.log(`PASS Manafestation old/new equivalence across ${cards.length*mags.length} cases; Arena ${a.passed}/${a.total}`);
  oldDom.window.close();newDom.window.close();
}
async function atomicCommit(changes,message){
  const ref=await request(`${api}/git/ref/heads/main`),parentSha=ref.object.sha,commit=await request(`${api}/git/commits/${parentSha}`);
  const treeEntries=[];
  for(const [path,text] of Object.entries(changes)){
    const blob=await request(`${api}/git/blobs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:text,encoding:'utf-8'})});
    treeEntries.push({path,mode:'100644',type:'blob',sha:blob.sha});
  }
  const tree=await request(`${api}/git/trees`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_tree:commit.tree.sha,tree:treeEntries})});
  const created=await request(`${api}/git/commits`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,tree:tree.sha,parents:[parentSha]})});
  await request(`${api}/git/refs/heads/main`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({sha:created.sha,force:false})});
  return created.sha;
}

(async()=>{
  const index=await getFile('siza-mobile-test/index.html');
  console.log('Current Mobile blob '+index.sha);
  const harnessPaths=['.github/scripts/siza-arena-regression.js','.github/scripts/siza-combat-effects-regression.js','.github/scripts/siza-prism-effects-regression.js','.github/scripts/siza-equipment-effects-regression.js','.github/scripts/siza-battlefield-ui-index-regression.js'];
  const coreNames=['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js'];
  const files={};for(const name of coreNames)files[name]=(await getFile(`siza-core/${name}`)).text;
  const changes={'siza-mobile-test/index.html':patchIndex(index.text)};
  for(const path of harnessPaths)changes[path]=patchHarness((await getFile(path)).text,path);
  compareRules(index.text,changes['siza-mobile-test/index.html'],files);
  for(const [path,text] of Object.entries(changes)){fs.mkdirSync(path.split('/').slice(0,-1).join('/'),{recursive:true});fs.writeFileSync(path,text)}
  for(const name of coreNames){const path=`siza-core/${name}`;fs.mkdirSync('siza-core',{recursive:true});fs.writeFileSync(path,files[name])}
  for(const path of harnessPaths){console.log(`RUN ${path}`);cp.execFileSync('node',[path],{stdio:'inherit'})}
  const sha=await atomicCommit(changes,'Extract pure Manafestation rules into shared core');
  console.log('COMMIT '+sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
