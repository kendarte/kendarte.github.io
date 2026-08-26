(function(){
'use strict';

const DRAFT_KEY='siza_card_generator_draft_v1';
const HANDOFF_KEY='siza_card_generator_handoff_v1';
const LIBRARY_KEY='siza_card_generator_library_v2';
const ART_DB='siza_card_generator_assets_v1';
const ART_STORE='art';
const params=new URLSearchParams(location.search);
const returnUrl=params.get('returnUrl')||'../siza-mobile-test/';
const requestedCardId=params.get('cardId')||'';
const $=id=>document.getElementById(id);
const has=(obj,key)=>Object.prototype.hasOwnProperty.call(obj||{},key);
let sourceMeta={role:'',adventureUnlock:false};
let effectsParseError='';
let library=loadLibrary();
let currentLoadedId='';
let currentArtAssetKey='';
let currentArtObjectUrl='';
let dbPromise=null;

const EXAMPLE={
 id:'memoria_reina_ahogada',name:'Memoria de la Reina Ahogada',template:'standard',cardType:'Creature',subtype:'Avatar',affinity:'azul',difficulty:8,cost:5,pips:{U:3},artId:'queen_drowned',artUrl:'',artAssetKey:'',artTransform:{x:50,y:35,scale:1},rules:'Al materializarse, roba dos cartas y luego descarta una.',flavor:'La corona sobrevivió porque nadie recordó enterrarla.',force:5,resistance:5,setCode:'SZA',cardNumber:'036',glyph:'♛',effects:[{event:'enter',type:'draw',target:'self',amount:2},{event:'enter',type:'discard',target:'self',amount:1,choice:'owner'}]
};

const fields=['id','name','cardType','subtype','difficulty','cost','affinity','glyph','rules','flavor','force','resistance','setCode','cardNumber','artUrl','effectsJson'];
const pipIds={U:'pipU',R:'pipR',G:'pipG',W:'pipW',B:'pipB'};
function num(id,fallback=0){const n=Number($(id).value);return Number.isFinite(n)?n:fallback;}
function maybeNum(id){const raw=$(id).value.trim();if(raw==='')return null;const n=Number(raw);return Number.isFinite(n)?n:null;}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function setMessage(text){$('handoffStatus').textContent=text;}
function setArtStatus(text){$('artFileStatus').textContent=text;}

function loadLibrary(){
 try{
  const raw=JSON.parse(localStorage.getItem(LIBRARY_KEY)||'{}');
  if(Array.isArray(raw))return Object.fromEntries(raw.filter(x=>x?.id).map(x=>[x.id,x]));
  return raw&&typeof raw==='object'?raw:{};
 }catch(e){return{};}
}
function saveLibrary(){localStorage.setItem(LIBRARY_KEY,JSON.stringify(library));}
function refreshLibrarySelect(selectedId=''){
 const select=$('savedCards');if(!select)return;
 const cards=Object.values(library).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),'es'));
 select.innerHTML='<option value="">— Cartas guardadas —</option>'+cards.map(c=>`<option value="${escapeHtml(c.id)}">${escapeHtml(c.name||c.id)} · ${escapeHtml(c.id)}</option>`).join('');
 if(selectedId&&library[selectedId])select.value=selectedId;
}

function openArtDb(){
 if(!('indexedDB'in window))return Promise.resolve(null);
 if(dbPromise)return dbPromise;
 dbPromise=new Promise((resolve,reject)=>{
  const req=indexedDB.open(ART_DB,1);
  req.onupgradeneeded=()=>{const db=req.result;if(!db.objectStoreNames.contains(ART_STORE))db.createObjectStore(ART_STORE);};
  req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);
 }).catch(()=>null);
 return dbPromise;
}
async function artPut(key,blob){const db=await openArtDb();if(!db)return false;return new Promise(resolve=>{const tx=db.transaction(ART_STORE,'readwrite');tx.objectStore(ART_STORE).put(blob,key);tx.oncomplete=()=>resolve(true);tx.onerror=()=>resolve(false);});}
async function artGet(key){const db=await openArtDb();if(!db||!key)return null;return new Promise(resolve=>{const tx=db.transaction(ART_STORE,'readonly'),req=tx.objectStore(ART_STORE).get(key);req.onsuccess=()=>resolve(req.result||null);req.onerror=()=>resolve(null);});}
async function artDelete(key){const db=await openArtDb();if(!db||!key)return;await new Promise(resolve=>{const tx=db.transaction(ART_STORE,'readwrite');tx.objectStore(ART_STORE).delete(key);tx.oncomplete=tx.onerror=()=>resolve();});}
function revokeArtObjectUrl(){if(currentArtObjectUrl&&currentArtObjectUrl.startsWith('blob:')&&URL.revokeObjectURL)URL.revokeObjectURL(currentArtObjectUrl);currentArtObjectUrl='';}
async function hydrateArtAsset(key,cardId){
 if(!key)return;
 const blob=await artGet(key);
 if(currentArtAssetKey!==key||$('id').value.trim()!==cardId)return;
 revokeArtObjectUrl();
 if(blob&&URL.createObjectURL){currentArtObjectUrl=URL.createObjectURL(blob);setArtStatus(`Ilustración guardada localmente · ${Math.max(1,Math.round(blob.size/1024))} KB`);render();}
 else setArtStatus('La carta referencia una ilustración local que no está disponible en este navegador.');
}

function readEffects(){effectsParseError='';const raw=$('effectsJson').value.trim();if(!raw)return[];try{const parsed=JSON.parse(raw);if(!Array.isArray(parsed)){effectsParseError='Effects debe ser una lista JSON.';return[]}return parsed}catch(e){effectsParseError='Effects contiene JSON inválido: '+e.message;return[]}}
function readForm(opts={}){
 const pips={};for(const[k,id]of Object.entries(pipIds)){const n=Math.max(0,Math.trunc(num(id,0)));if(n)pips[k]=n;}
 const externalArt=$('artUrl').value.trim();
 return{id:$('id').value.trim(),name:$('name').value,template:'standard',cardType:$('cardType').value,subtype:$('subtype').value,affinity:$('affinity').value,difficulty:num('difficulty',0),cost:num('cost',0),pips,artId:$('id').value.trim(),artUrl:opts.preview&&currentArtObjectUrl?currentArtObjectUrl:externalArt,artAssetKey:currentArtAssetKey,artTransform:{x:num('artX',50),y:num('artY',50),scale:num('artScale',1)},rules:$('rules').value,flavor:$('flavor').value,force:maybeNum('force'),resistance:maybeNum('resistance'),setCode:$('setCode').value.trim(),cardNumber:$('cardNumber').value.trim(),glyph:$('glyph').value||'✦',role:sourceMeta.role,adventureUnlock:sourceMeta.adventureUnlock,effects:readEffects()};
}

function writeForm(input){
 const c=SizaCardSchema.normalizeCard(input);currentLoadedId=c.id;sourceMeta={role:c.role||'',adventureUnlock:!!c.adventureUnlock};
 revokeArtObjectUrl();currentArtAssetKey=c.artAssetKey||'';
 $('id').value=c.id;$('name').value=c.name;$('cardType').value=c.cardType;$('subtype').value=c.subtype;$('difficulty').value=c.difficulty;$('cost').value=c.cost;$('affinity').value=['azul','rojo','multi','land'].includes(c.affinity)?c.affinity:'multi';$('glyph').value=c.glyph;$('rules').value=c.rules;$('flavor').value=c.flavor;$('force').value=c.power??'';$('resistance').value=c.toughness??'';$('setCode').value=c.setCode;$('cardNumber').value=c.cardNumber;$('artUrl').value=c.artUrl;$('effectsJson').value=JSON.stringify(c.effects||[],null,2);for(const[k,id]of Object.entries(pipIds))$(id).value=c.pips?.[k]||0;$('artX').value=c.artTransform.x;$('artY').value=c.artTransform.y;$('artScale').value=c.artTransform.scale;syncArtNumeric();
 setArtStatus(currentArtAssetKey?'Cargando ilustración guardada…':c.artUrl?'Usando URL externa de ilustración.':'Sin ilustración cargada.');render();refreshLibrarySelect(c.id);if(currentArtAssetKey)hydrateArtAsset(currentArtAssetKey,c.id);
}
function syncArtNumeric(){$('artXValue').value=$('artX').value;$('artYValue').value=$('artY').value;$('artScaleValue').value=$('artScale').value;}
function syncArtRange(){$('artX').value=$('artXValue').value;$('artY').value=$('artYValue').value;$('artScale').value=$('artScaleValue').value;}

function render(){
 const storedValidation=SizaCardSchema.validateCard(readForm()),previewValidation=SizaCardSchema.validateCard(readForm({preview:true}));
 if(effectsParseError){storedValidation.valid=false;storedValidation.errors.unshift(effectsParseError);previewValidation.valid=false;}
 SizaCardRenderer.mount($('cardPreview'),previewValidation.card);$('jsonOutput').value=JSON.stringify(storedValidation.card,null,2);$('schemaVersion').textContent='Schema '+SizaCardSchema.VERSION+' · Effects '+(window.SizaCardEffects?.VERSION||'—');
 const box=$('validationStatus');if(storedValidation.valid){box.className='status good';box.innerHTML=`<b>Schema válido</b>${storedValidation.warnings.length?storedValidation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'Lista para guardar o probar.'}`}else{box.className='status bad';box.innerHTML='<b>Schema inválido</b>'+storedValidation.errors.map(escapeHtml).join('<br>')+(storedValidation.warnings.length?'<br>'+storedValidation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'')}
 return storedValidation;
}

function saveDraft(opts={}){
 const validation=render();if(!validation.valid){if(!opts.quiet)setMessage('Carta no guardada: corrija los errores.');return null;}
 const card=validation.card;localStorage.setItem(DRAFT_KEY,JSON.stringify(card));library[card.id]=card;saveLibrary();currentLoadedId=card.id;refreshLibrarySelect(card.id);if(!opts.quiet)setMessage(`Carta guardada: ${card.name} · ${card.id}`);return card;
}
function newBlank(){return{...EXAMPLE,id:'card_'+Date.now(),name:'Carta sin nombre',difficulty:1,cost:1,pips:{},artId:'',artUrl:'',artAssetKey:'',artTransform:{x:50,y:50,scale:1},rules:'',flavor:'',force:2,resistance:2,cardNumber:'000',glyph:'✦',effects:[]};}
function newCard(){writeForm(newBlank());setMessage('Nueva carta. Suba la ilustración, ajuste el template y guárdela cuando esté lista.');}
function resetDraft(){const saved=library[currentLoadedId];if(saved)writeForm(saved);else newCard();}
async function deleteCurrentCard(){
 const id=$('id').value.trim(),saved=library[id];if(!saved){setMessage('Esta carta todavía no está guardada en la biblioteca.');return;}
 if(saved.artAssetKey)await artDelete(saved.artAssetKey);delete library[id];saveLibrary();try{const draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');if(draft?.id===id)localStorage.removeItem(DRAFT_KEY);}catch(e){}refreshLibrarySelect();newCard();setMessage(`Carta eliminada de la biblioteca: ${id}`);
}

async function optimizedArtBlob(file){
 if(!window.createImageBitmap)return file;
 try{
  const bitmap=await createImageBitmap(file),limit=1800,ratio=Math.min(1,limit/bitmap.width,limit/bitmap.height),w=Math.max(1,Math.round(bitmap.width*ratio)),h=Math.max(1,Math.round(bitmap.height*ratio)),canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0,w,h);bitmap.close?.();
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',.9));return blob||file;
 }catch(e){return file;}
}
function blobToDataUrl(blob){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result||''));r.onerror=()=>reject(r.error);r.readAsDataURL(blob);});}
async function acceptArtFile(file){
 if(!file||!file.type?.startsWith('image/')){setArtStatus('El archivo seleccionado no es una imagen.');return;}
 const id=$('id').value.trim()||('card_'+Date.now());if(!$('id').value.trim())$('id').value=id;setArtStatus('Procesando ilustración…');const blob=await optimizedArtBlob(file);
 const db=await openArtDb();
 if(db){
  const oldKey=currentArtAssetKey,key=`art:${id}:${Date.now()}`;if(!(await artPut(key,blob))){setArtStatus('No se pudo guardar la ilustración localmente.');return;}if(oldKey&&oldKey!==key)artDelete(oldKey);revokeArtObjectUrl();currentArtAssetKey=key;currentArtObjectUrl=URL.createObjectURL?URL.createObjectURL(blob):'';$('artUrl').value='';setArtStatus(`Ilustración guardada · ${Math.max(1,Math.round(blob.size/1024))} KB · ajuste X/Y/zoom y vuelva a guardar la carta.`);render();saveDraft({quiet:true});
 }else{
  try{revokeArtObjectUrl();currentArtAssetKey='';$('artUrl').value=await blobToDataUrl(blob);setArtStatus('Ilustración guardada dentro del borrador del navegador.');render();saveDraft({quiet:true});}catch(e){setArtStatus('No se pudo leer la ilustración.');}
 }
}
async function removeArt(){const old=currentArtAssetKey;if(old)await artDelete(old);revokeArtObjectUrl();currentArtAssetKey='';$('artUrl').value='';setArtStatus('Sin ilustración cargada.');render();saveDraft({quiet:true});}

async function materializeArt(card){
 if(!card.artAssetKey)return card;const blob=await artGet(card.artAssetKey);if(!blob)return card;try{return{...card,artUrl:await blobToDataUrl(blob)}}catch(e){return card;}
}
async function prepareHandoff(){
 const validation=render();if(!validation.valid){setMessage('Handoff bloqueado: corrija los errores de schema.');return;}
 const stored=validation.card;localStorage.setItem(DRAFT_KEY,JSON.stringify(stored));const card=await materializeArt(stored),payload={action:'test-card',card:SizaCardSchema.cardToMobileShape(card),generatorCard:card,target:'collection',returnUrl,createdAt:new Date().toISOString()};
 try{localStorage.setItem(HANDOFF_KEY,JSON.stringify(payload));location.href=returnUrl;}catch(e){setMessage('La ilustración es demasiado grande para el handoff temporal. Vuelva a subirla para que el generador la optimice.');}
}

function catalogSource(card){if(!card)return null;const affinity=card.art==='blue'?'azul':card.art==='red'?'rojo':card.art==='land'?'land':'multi';return{...card,affinity};}
function mergePatch(base,patch){
 const merged={...base,...patch};if(!has(patch,'pips'))merged.pips=base.pips;if(!has(patch,'effects'))merged.effects=base.effects;if(!has(patch,'artUrl'))merged.artUrl=base.artUrl;if(!has(patch,'artAssetKey'))merged.artAssetKey=base.artAssetKey;if(!has(patch,'artTransform'))merged.artTransform=base.artTransform;else merged.artTransform={...(base.artTransform||{x:50,y:50,scale:1}),...(patch.artTransform||{})};return merged;
}
function exportBatch(){const cards=Object.values(library).sort((a,b)=>String(a.id).localeCompare(String(b.id)));$('batchJson').value=JSON.stringify(cards,null,2);setMessage(`Batch exportado: ${cards.length} carta(s).`);}
function applyBatch(){
 let patches;try{patches=JSON.parse($('batchJson').value.trim()||'[]')}catch(e){setMessage('Batch inválido: '+e.message);return;}if(!Array.isArray(patches)){setMessage('Batch inválido: debe ser una lista JSON.');return;}
 const staged={...library},errors=[];for(const patch of patches){if(!patch||!String(patch.id||'').trim()){errors.push('Hay una entrada sin id.');continue;}const id=String(patch.id).trim(),official=catalogSource(window.SizaCardCatalog?.get(id)),base=staged[id]||official||{...newBlank(),id,name:patch.name||id};const validation=SizaCardSchema.validateCard(mergePatch(base,{...patch,id}));if(!validation.valid)errors.push(`${id}: ${validation.errors.join(' / ')}`);else staged[id]=validation.card;}
 if(errors.length){setMessage('Batch cancelado. '+errors.join(' | '));return;}library=staged;saveLibrary();refreshLibrarySelect($('id').value.trim());const current=library[$('id').value.trim()];if(current)writeForm(current);setMessage(`Batch aplicado: ${patches.length} entrada(s). El arte manual se conservó donde el batch no lo reemplazó.`);
}

function loadInitial(){
 let draft=null;try{draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null')}catch(e){}refreshLibrarySelect();const saved=requestedCardId?library[requestedCardId]:null,official=requestedCardId?catalogSource(window.SizaCardCatalog?.get(requestedCardId)):null;if(requestedCardId){if(saved)writeForm(saved);else if(draft?.id===requestedCardId)writeForm(draft);else if(official)writeForm(official);else writeForm({...EXAMPLE,id:requestedCardId});}else if(draft)writeForm(draft);else writeForm(EXAMPLE);$('testMobile').textContent='Probar en Mobile Test';setMessage(requestedCardId?`Editando ${requestedCardId}. Guardar conserva esta versión en la biblioteca local.`:'Guardar carta conserva datos, arte y ajustes manuales por ID.');
}

for(const id of fields)$(id).addEventListener('input',render);for(const id of Object.values(pipIds))$(id).addEventListener('input',render);for(const id of ['artX','artY','artScale'])$(id).addEventListener('input',()=>{syncArtNumeric();render();});for(const id of ['artXValue','artYValue','artScaleValue'])$(id).addEventListener('input',()=>{syncArtRange();render();});
$('savedCards').addEventListener('change',e=>{const card=library[e.target.value];if(card)writeForm(card);});$('newCard').addEventListener('click',newCard);$('deleteCard').addEventListener('click',deleteCurrentCard);$('saveDraft').addEventListener('click',()=>saveDraft());$('loadExample').addEventListener('click',()=>writeForm(EXAMPLE));$('resetDraft').addEventListener('click',resetDraft);$('testMobile').addEventListener('click',prepareHandoff);$('exportBatch').addEventListener('click',exportBatch);$('applyBatch').addEventListener('click',applyBatch);
$('chooseArt').addEventListener('click',()=>$('artFile').click());$('artFile').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)acceptArtFile(file);e.target.value='';});$('removeArt').addEventListener('click',removeArt);
const drop=$('artDropZone');drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('dragover')});drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragover');const file=e.dataTransfer?.files?.[0];if(file)acceptArtFile(file);});
window.addEventListener('beforeunload',revokeArtObjectUrl);loadInitial();
})();
