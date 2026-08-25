const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

function inlineCore(html){let out=html;for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js']){const tag=`<script src="../siza-core/${name}"></script>`;if(!out.includes(tag))throw new Error(`Missing shared core tag ${name}`);out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`)}return out}
const original=inlineCore(fs.readFileSync('siza-mobile-test/index.html','utf8')),marker='window.SIZA={';if(!original.includes(marker))throw new Error('SIZA export marker not found');
const probe=`window.__UI_INDEX_REGRESSION__={createMatch,setMatch:m=>state.match=m,removeBattlefieldAt};\n`,vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM ui-index]',e.message));const dom=new JSDOM(original.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.setTimeout=()=>0;const H=dom.window.__UI_INDEX_REGRESSION__;if(!H)throw new Error('UI index hooks unavailable');
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
function fresh(){const M=H.createMatch(false,'prepare');H.setMatch(M);return M}

test('Eliminar índice anterior desplaza creature attackers y focus del jugador',()=>{const M=fresh(),P=M.player;P.hand=[];P.graveyard=[];P.battlefield=['servitor','ignimite','watcher'];P.powerCounters=[0,1,0];P.summonedOn=[1,1,1];P.exhausted=[1,2];P.equipment=[{id:'tideblade',target:2}];M.ui={hand:-1,creature:2,attackMode:true,attackers:[1,2],fieldFocus:{owner:'player',index:2}};H.removeBattlefieldAt(P,0,'hand');return M.ui.creature===1&&JSON.stringify(M.ui.attackers)==='[0,1]'&&M.ui.fieldFocus?.index===1&&P.equipment[0].target===1&&JSON.stringify(P.exhausted)==='[0,1]'&&P.hand[0]==='servitor'});

test('Eliminar criatura seleccionada limpia creature focus y atacante removido',()=>{const M=fresh(),P=M.player;P.battlefield=['servitor','watcher'];P.powerCounters=[0,0];P.summonedOn=[1,1];P.exhausted=[];P.equipment=[];P.graveyard=[];M.ui={hand:-1,creature:0,attackMode:true,attackers:[0,1],fieldFocus:{owner:'player',index:0}};H.removeBattlefieldAt(P,0);return M.ui.creature===-1&&M.ui.fieldFocus===null&&JSON.stringify(M.ui.attackers)==='[0]'&&P.battlefield[0]==='watcher'});

test('Focus rival se desplaza y se limpia con battlefield rival',()=>{const M=fresh(),E=M.enemy;E.battlefield=['servitor','watcher'];E.powerCounters=[0,0];E.summonedOn=[1,1];E.exhausted=[];E.equipment=[];E.graveyard=[];M.ui.fieldFocus={owner:'enemy',index:1};H.removeBattlefieldAt(E,0);const shifted=M.ui.fieldFocus?.owner==='enemy'&&M.ui.fieldFocus.index===0;H.removeBattlefieldAt(E,0);return shifted&&M.ui.fieldFocus===null});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA battlefield UI index regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
