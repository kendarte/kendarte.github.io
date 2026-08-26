(function(){
'use strict';

const DRAFT_KEY='siza_card_generator_draft_v1';
const HANDOFF_KEY='siza_card_generator_handoff_v1';
const LIBRARY_KEY='siza_card_generator_library_v2';
const TEMPLATE_LIBRARY_KEY='siza_card_generator_templates_v1';
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
let templates=loadTemplates();
let currentLoadedId='';
let currentArtAssetKey='';
let currentArtObjectUrl='';
let currentBattleSpriteAssetKey='';
let currentBattleSpriteObjectUrl='';
let currentFrameAssetKey='';
let currentFrameObjectUrl='';
let currentFrameInlineUrl='';
let dbPromise=null;

const EXAMPLE={
 id:'memoria_reina_ahogada',name:'Memoria de la Reina Ahogada',template:'standard',frameUrl:'',frameAssetKey:'',cardType:'Creature',subtype:'Avatar',affinity:'azul',difficulty:8,cost:5,pips:{U:3},artId:'queen_drowned',artUrl:'',artAssetKey:'',artTransform:{x:50,y:35,scale:1},battleSpriteUrl:'',battleSpriteAssetKey:'',battleSpriteTransform:{x:50,y:50,scale:1},rules:'Al materializarse, roba dos cartas y luego descarta una.',flavor:'La corona sobrevivió porque nadie recordó enterrarla.',force:5,resistance:5,setCode:'SZA',cardNumber:'036',glyph:'♛',effects:[{event:'enter',type:'draw',target:'self',amount:2},{event:'enter',type:'discard',target:'self',amount:1,choice:'owner'}]
};

const fields=['id','name','cardType','subtype','difficulty','cost','affinity','glyph','rules','flavor','force','resistance','setCode','cardNumber','artUrl','battleSpriteUrl','effectsJson'];
const pipIds={U:'pipU',R:'pipR',G:'pipG',W:'pipW',B:'pipB'};
function num(id,fallback=0){const n=Number($(id).value);return Number.isFinite(n)?n:fallback;}
function maybeNum(id){const raw=$(id).value.trim();if(raw==='')return null;const n=Number(raw);return Number.isFinite(n)?n:null;}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function setMessage(text){$('handoffStatus').textContent=text;}
function setArtStatus(text){$('artFileStatus').textContent=text;}
function setBattleSpriteStatus(text){$('battleSpriteFileStatus').textContent=text;}
function setFrameStatus(text){$('frameFileStatus').innerHTML=text;}

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
function loadTemplates(){
 try{
  const raw=JSON.parse(localStorage.getItem(TEMPLATE_LIBRARY_KEY)||'{}');
  if(Array.isArray(raw))return Object.fromEntries(raw.filter(x=>x?.id).map(x=>[x.id,x]));
  return raw&&typeof raw==='object'?raw:{};
 }catch(e){return{};}
}
function saveTemplates(){localStorage.setItem(TEMPLATE_LIBRARY_KEY,JSON.stringify(templates));}
function refreshTemplateSelect(selectedId='standard'){
 const select=$('templateSelect');if(!select)return;
 const list=Object.values(templates).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),'es'));
 select.innerHTML='<option value="standard">Standard · sistema</option>'+list.map(t=>`<option value="${escapeHtml(t.id)}">${escapeHtml(t.name||t.id)}</option>`).join('');
 if(selectedId&&selectedId!=='standard'&&!templates[selectedId])select.insertAdjacentHTML('beforeend',`<option value="${escapeHtml(selectedId)}">${escapeHtml(selectedId)} · importado</option>`);
 select.value=selectedId||'standard';
}
function templateEntry(id){return id&&id!=='standard'?templates[id]||null:null;}

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
function revokeBattleSpriteObjectUrl(){if(currentBattleSpriteObjectUrl&&currentBattleSpriteObjectUrl.startsWith('blob:')&&URL.revokeObjectURL)URL.revokeObjectURL(currentBattleSpriteObjectUrl);currentBattleSpriteObjectUrl='';}
function revokeFrameObjectUrl(){if(currentFrameObjectUrl&&currentFrameObjectUrl.startsWith('blob:')&&URL.revokeObjectURL)URL.revokeObjectURL(currentFrameObjectUrl);currentFrameObjectUrl='';}
async function hydrateArtAsset(key,cardId){
 if(!key)return;
 const blob=await artGet(key);
 if(currentArtAssetKey!==key||$('id').value.trim()!==cardId)return;
 revokeArtObjectUrl();
 if(blob&&URL.createObjectURL){currentArtObjectUrl=URL.createObjectURL(blob);setArtStatus(`Ilustración guardada localmente · ${Math.max(1,Math.round(blob.size/1024))} KB`);render();}
 else setArtStatus('La carta referencia una ilustración local que no está disponible en este navegador.');
}
async function hydrateBattleSpriteAsset(key,cardId){
 if(!key)return;
 const blob=await artGet(key);
 if(currentBattleSpriteAssetKey!==key||$('id').value.trim()!==cardId)return;
 revokeBattleSpriteObjectUrl();
 if(blob&&URL.createObjectURL){currentBattleSpriteObjectUrl=URL.createObjectURL(blob);setBattleSpriteStatus(`Battle Sprite guardado localmente · ${Math.max(1,Math.round(blob.size/1024))} KB`);render();}
 else setBattleSpriteStatus('La carta referencia un Battle Sprite local que no está disponible en este navegador.');
}
async function hydrateFrameAsset(key,templateId){
 if(!key)return;
 const blob=await artGet(key);
 if(currentFrameAssetKey!==key||$('templateSelect').value!==templateId)return;
 revokeFrameObjectUrl();
 if(blob&&URL.createObjectURL){currentFrameObjectUrl=URL.createObjectURL(blob);setFrameStatus(`<strong>${escapeHtml(templateEntry(templateId)?.name||templateId)}</strong> · template cargado · ${Math.max(1,Math.round(blob.size/1024))} KB`);render();}
 else setFrameStatus(`<strong>${escapeHtml(templateId)}</strong> · el archivo del template no está disponible en este navegador.`);
}
async function applyTemplateSelection(templateId){
 const id=templateId||'standard',entry=templateEntry(id);revokeFrameObjectUrl();currentFrameAssetKey=entry?.frameAssetKey||'';currentFrameInlineUrl=entry?.frameUrl||'';
 if(id==='standard'){setFrameStatus('<strong>Standard</strong> · usando el frame base del sistema.');render();return;}
 if(entry?.frameAssetKey){setFrameStatus(`<strong>${escapeHtml(entry.name||id)}</strong> · cargando template guardado…`);render();await hydrateFrameAsset(entry.frameAssetKey,id);return;}
 if(entry?.frameUrl){setFrameStatus(`<strong>${escapeHtml(entry.name||id)}</strong> · template guardado en el navegador.`);render();return;}
 setFrameStatus(`<strong>${escapeHtml(id)}</strong> · template sin archivo disponible.`);render();
}

function readEffects(){effectsParseError='';const raw=$('effectsJson').value.trim();if(!raw)return[];try{const parsed=JSON.parse(raw);if(!Array.isArray(parsed)){effectsParseError='Effects debe ser una lista JSON.';return[]}return parsed}catch(e){effectsParseError='Effects contiene JSON inválido: '+e.message;return[]}}
function readForm(opts={}){
 const pips={};for(const[k,id]of Object.entries(pipIds)){const n=Math.max(0,Math.trunc(num(id,0)));if(n)pips[k]=n;}
 const externalArt=$('artUrl').value.trim(),externalBattleSprite=$('battleSpriteUrl').value.trim(),template=$('templateSelect')?.value||'standard',entry=templateEntry(template),storedFrame=currentFrameInlineUrl||entry?.frameUrl||'',previewFrame=currentFrameObjectUrl||storedFrame;
 return{id:$('id').value.trim(),name:$('name').value,template,frameUrl:opts.preview?previewFrame:storedFrame,frameAssetKey:currentFrameAssetKey,cardType:$('cardType').value,subtype:$('subtype').value,affinity:$('affinity').value,difficulty:num('difficulty',0),cost:num('cost',0),pips,artId:$('id').value.trim(),artUrl:opts.preview&&currentArtObjectUrl?currentArtObjectUrl:externalArt,artAssetKey:currentArtAssetKey,artTransform:{x:num('artX',50),y:num('artY',50),scale:num('artScale',1)},battleSpriteUrl:opts.preview&&currentBattleSpriteObjectUrl?currentBattleSpriteObjectUrl:externalBattleSprite,battleSpriteAssetKey:currentBattleSpriteAssetKey,battleSpriteTransform:{x:num('battleSpriteX',50),y:num('battleSpriteY',50),scale:num('battleSpriteScale',1)},rules:$('rules').value,flavor:$('flavor').value,force:maybeNum('force'),resistance:maybeNum('resistance'),setCode:$('setCode').value.trim(),cardNumber:$('cardNumber').value.trim(),glyph:$('glyph').value||'✦',role:sourceMeta.role,adventureUnlock:sourceMeta.adventureUnlock,effects:readEffects()};
}

function writeForm(input){
 const c=SizaCardSchema.normalizeCard(input);currentLoadedId=c.id;sourceMeta={role:c.role||'',adventureUnlock:!!c.adventureUnlock};
 revokeArtObjectUrl();currentArtAssetKey=c.artAssetKey||'';revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey=c.battleSpriteAssetKey||'';revokeFrameObjectUrl();refreshTemplateSelect(c.template||'standard');const entry=templateEntry(c.template);currentFrameAssetKey=c.frameAssetKey||entry?.frameAssetKey||'';currentFrameInlineUrl=c.frameUrl||entry?.frameUrl||'';
 $('id').value=c.id;$('name').value=c.name;$('cardType').value=c.cardType;$('subtype').value=c.subtype;$('difficulty').value=c.difficulty;$('cost').value=c.cost;$('affinity').value=['azul','rojo','multi','land'].includes(c.affinity)?c.affinity:'multi';$('glyph').value=c.glyph;$('rules').value=c.rules;$('flavor').value=c.flavor;$('force').value=c.power??'';$('resistance').value=c.toughness??'';$('setCode').value=c.setCode;$('cardNumber').value=c.cardNumber;$('artUrl').value=c.artUrl;$('battleSpriteUrl').value=c.battleSpriteUrl;$('effectsJson').value=JSON.stringify(c.effects||[],null,2);for(const[k,id]of Object.entries(pipIds))$(id).value=c.pips?.[k]||0;$('artX').value=c.artTransform.x;$('artY').value=c.artTransform.y;$('artScale').value=c.artTransform.scale;$('battleSpriteX').value=c.battleSpriteTransform.x;$('battleSpriteY').value=c.battleSpriteTransform.y;$('battleSpriteScale').value=c.battleSpriteTransform.scale;syncArtNumeric();syncBattleSpriteNumeric();
 setArtStatus(currentArtAssetKey?'Cargando ilustración guardada…':c.artUrl?'Usando URL externa de ilustración.':'Sin ilustración cargada.');setBattleSpriteStatus(currentBattleSpriteAssetKey?'Cargando Battle Sprite guardado…':c.battleSpriteUrl?'Usando URL externa de Battle Sprite.':'Sin Battle Sprite cargado.');setFrameStatus(c.template==='standard'?'<strong>Standard</strong> · usando el frame base del sistema.':currentFrameAssetKey?`<strong>${escapeHtml(entry?.name||c.template)}</strong> · cargando template guardado…`:currentFrameInlineUrl?`<strong>${escapeHtml(entry?.name||c.template)}</strong> · template listo.`:`<strong>${escapeHtml(c.template)}</strong> · template sin archivo disponible.`);render();refreshLibrarySelect(c.id);if(currentArtAssetKey)hydrateArtAsset(currentArtAssetKey,c.id);if(currentBattleSpriteAssetKey)hydrateBattleSpriteAsset(currentBattleSpriteAssetKey,c.id);if(currentFrameAssetKey)hydrateFrameAsset(currentFrameAssetKey,c.template);
}
function syncArtNumeric(){$('artXValue').value=$('artX').value;$('artYValue').value=$('artY').value;$('artScaleValue').value=$('artScale').value;}
function syncArtRange(){$('artX').value=$('artXValue').value;$('artY').value=$('artYValue').value;$('artScale').value=$('artScaleValue').value;}
function syncBattleSpriteNumeric(){$('battleSpriteXValue').value=$('battleSpriteX').value;$('battleSpriteYValue').value=$('battleSpriteY').value;$('battleSpriteScaleValue').value=$('battleSpriteScale').value;}
function syncBattleSpriteRange(){$('battleSpriteX').value=$('battleSpriteXValue').value;$('battleSpriteY').value=$('battleSpriteYValue').value;$('battleSpriteScale').value=$('battleSpriteScaleValue').value;}
function renderBattleSpritePreview(c){const box=$('battleSpritePreview');if(!box)return;const src=currentBattleSpriteObjectUrl||c.battleSpriteUrl,t=c.battleSpriteTransform;if(!src){box.innerHTML='<span>Sin Battle Sprite</span>';return;}box.innerHTML=`<img src="${escapeHtml(src)}" alt="" style="left:${t.x}%;top:${t.y}%;transform:translate(-50%,-50%) scale(${t.scale})" onerror="this.parentElement.innerHTML='<span>Battle Sprite no disponible</span>'">`;}

function render(){
 const storedValidation=SizaCardSchema.validateCard(readForm()),previewValidation=SizaCardSchema.validateCard(readForm({preview:true}));
 if(effectsParseError){storedValidation.valid=false;storedValidation.errors.unshift(effectsParseError);previewValidation.valid=false;}
 SizaCardRenderer.mount($('cardPreview'),previewValidation.card);renderBattleSpritePreview(previewValidation.card);$('jsonOutput').value=JSON.stringify(storedValidation.card,null,2);$('schemaVersion').textContent='Schema '+SizaCardSchema.VERSION+' · Effects '+(window.SizaCardEffects?.VERSION||'—');
 const box=$('validationStatus');if(storedValidation.valid){box.className='status good';box.innerHTML=`<b>Schema válido</b>${storedValidation.warnings.length?storedValidation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'Lista para guardar o probar.'}`}else{box.className='status bad';box.innerHTML='<b>Schema inválido</b>'+storedValidation.errors.map(escapeHtml).join('<br>')+(storedValidation.warnings.length?'<br>'+storedValidation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'')}
 return storedValidation;
}

function saveDraft(opts={}){
 const validation=render();if(!validation.valid){if(!opts.quiet)setMessage('Carta no guardada: corrija los errores.');return null;}
 const card=validation.card;localStorage.setItem(DRAFT_KEY,JSON.stringify(card));library[card.id]=card;saveLibrary();currentLoadedId=card.id;refreshLibrarySelect(card.id);if(!opts.quiet)setMessage(`Carta guardada: ${card.name} · ${card.id}`);return card;
}
function newBlank(){return{...EXAMPLE,id:'card_'+Date.now(),name:'Carta sin nombre',template:'standard',frameUrl:'',frameAssetKey:'',difficulty:1,cost:1,pips:{},artId:'',artUrl:'',artAssetKey:'',artTransform:{x:50,y:50,scale:1},battleSpriteUrl:'',battleSpriteAssetKey:'',battleSpriteTransform:{x:50,y:50,scale:1},rules:'',flavor:'',force:2,resistance:2,cardNumber:'000',glyph:'✦',effects:[]};}
function newCard(){writeForm(newBlank());setMessage('Nueva carta. Puede elegir/subir un template, cargar ilustración y Battle Sprite, y guardar cuando esté lista.');}
function resetDraft(){const saved=library[currentLoadedId];if(saved)writeForm(saved);else newCard();}
async function deleteCurrentCard(){
 const id=$('id').value.trim(),saved=library[id];if(!saved){setMessage('Esta carta todavía no está guardada en la biblioteca.');return;}
 if(saved.artAssetKey)await artDelete(saved.artAssetKey);if(saved.battleSpriteAssetKey)await artDelete(saved.battleSpriteAssetKey);delete library[id];saveLibrary();try{const draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');if(draft?.id===id)localStorage.removeItem(DRAFT_KEY);}catch(e){}refreshLibrarySelect();newCard();setMessage(`Carta eliminada de la biblioteca: ${id}`);
}

async function optimizedArtBlob(file,limit=1800,quality=.9){
 if(!window.createImageBitmap)return file;
 try{
  const bitmap=await createImageBitmap(file),ratio=Math.min(1,limit/bitmap.width,limit/bitmap.height),w=Math.max(1,Math.round(bitmap.width*ratio)),h=Math.max(1,Math.round(bitmap.height*ratio)),canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0,w,h);bitmap.close?.();
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',quality));return blob||file;
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
async function acceptBattleSpriteFile(file){
 if(!file||!file.type?.startsWith('image/')){setBattleSpriteStatus('El archivo seleccionado no es una imagen.');return;}
 const id=$('id').value.trim()||('card_'+Date.now());if(!$('id').value.trim())$('id').value=id;setBattleSpriteStatus('Procesando Battle Sprite…');const blob=await optimizedArtBlob(file,1400,.92),db=await openArtDb();
 if(db){
  const oldKey=currentBattleSpriteAssetKey,key=`battle-sprite:${id}:${Date.now()}`;if(!(await artPut(key,blob))){setBattleSpriteStatus('No se pudo guardar el Battle Sprite localmente.');return;}if(oldKey&&oldKey!==key)artDelete(oldKey);revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey=key;currentBattleSpriteObjectUrl=URL.createObjectURL?URL.createObjectURL(blob):'';$('battleSpriteUrl').value='';setBattleSpriteStatus(`Battle Sprite guardado · ${Math.max(1,Math.round(blob.size/1024))} KB · éste será el visual de la Invocación manifestada.`);render();saveDraft({quiet:true});
 }else{
  try{revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey='';$('battleSpriteUrl').value=await blobToDataUrl(blob);setBattleSpriteStatus('Battle Sprite guardado dentro del borrador del navegador.');render();saveDraft({quiet:true});}catch(e){setBattleSpriteStatus('No se pudo leer el Battle Sprite.');}
 }
}
async function removeBattleSprite(){const old=currentBattleSpriteAssetKey;if(old)await artDelete(old);revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey='';$('battleSpriteUrl').value='';setBattleSpriteStatus('Sin Battle Sprite cargado.');render();saveDraft({quiet:true});}
function cleanTemplateName(filename){return String(filename||'Template').replace(/\.[^.]+$/,'').trim()||'Template';}
function templateIdFromName(name){const slug=String(name).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'').slice(0,36)||'frame';return `custom_${slug}_${Date.now().toString(36)}`;}
async function acceptFrameFile(file){
 if(!file||!file.type?.startsWith('image/')){setFrameStatus('<strong>Error</strong> · el archivo seleccionado no es una imagen.');return;}
 const name=cleanTemplateName(file.name),id=templateIdFromName(name);setFrameStatus(`<strong>${escapeHtml(name)}</strong> · procesando frame…`);const blob=await optimizedArtBlob(file,2000,.95),db=await openArtDb();revokeFrameObjectUrl();currentFrameInlineUrl='';
 if(db){
  const key=`frame:${id}`;if(!(await artPut(key,blob))){setFrameStatus(`<strong>${escapeHtml(name)}</strong> · no se pudo guardar el template.`);return;}templates[id]={id,name,frameAssetKey:key,frameUrl:'',createdAt:new Date().toISOString()};saveTemplates();currentFrameAssetKey=key;currentFrameObjectUrl=URL.createObjectURL?URL.createObjectURL(blob):'';
 }else{
  try{const dataUrl=await blobToDataUrl(blob);templates[id]={id,name,frameAssetKey:'',frameUrl:dataUrl,createdAt:new Date().toISOString()};saveTemplates();currentFrameAssetKey='';currentFrameInlineUrl=dataUrl;}catch(e){setFrameStatus(`<strong>${escapeHtml(name)}</strong> · no se pudo leer el frame.`);return;}
 }
 refreshTemplateSelect(id);$('templateSelect').value=id;setFrameStatus(`<strong>${escapeHtml(name)}</strong> · template guardado · ${Math.max(1,Math.round(blob.size/1024))} KB`);render();saveDraft({quiet:true});setMessage(`Template agregado: ${name}. Ya puede reutilizarlo desde el selector Frame / Template.`);
}
async function useStandardFrame(){refreshTemplateSelect('standard');$('templateSelect').value='standard';await applyTemplateSelection('standard');saveDraft({quiet:true});setMessage('Template Standard seleccionado.');}

async function materializeArt(card){
 if(!card.artAssetKey)return card;const blob=await artGet(card.artAssetKey);if(!blob)return card;try{return{...card,artUrl:await blobToDataUrl(blob)}}catch(e){return card;}
}
async function materializeBattleSprite(card){
 if(card.battleSpriteUrl||!card.battleSpriteAssetKey)return card;const blob=await artGet(card.battleSpriteAssetKey);if(!blob)return card;try{return{...card,battleSpriteUrl:await blobToDataUrl(blob)}}catch(e){return card;}
}
async function materializeFrame(card){
 if(card.frameUrl||!card.frameAssetKey)return card;const blob=await artGet(card.frameAssetKey);if(!blob)return card;try{return{...card,frameUrl:await blobToDataUrl(blob)}}catch(e){return card;}
}
async function prepareHandoff(){
 const validation=render();if(!validation.valid){setMessage('Handoff bloqueado: corrija los errores de schema.');return;}
 const stored=validation.card;localStorage.setItem(DRAFT_KEY,JSON.stringify(stored));let card=await materializeArt(stored);card=await materializeBattleSprite(card);card=await materializeFrame(card);const payload={action:'test-card',card:SizaCardSchema.cardToMobileShape(card),generatorCard:card,target:'collection',returnUrl,createdAt:new Date().toISOString()};
 try{localStorage.setItem(HANDOFF_KEY,JSON.stringify(payload));location.href=returnUrl;}catch(e){setMessage('El arte, Battle Sprite o frame es demasiado grande para el handoff temporal. Vuelva a subirlo para que el generador lo optimice.');}
}

function catalogSource(card){if(!card)return null;const affinity=card.art==='blue'?'azul':card.art==='red'?'rojo':card.art==='land'?'land':'multi';return{...card,affinity};}
function mergePatch(base,patch){
 const merged={...base,...patch};if(!has(patch,'pips'))merged.pips=base.pips;if(!has(patch,'effects'))merged.effects=base.effects;if(!has(patch,'artUrl'))merged.artUrl=base.artUrl;if(!has(patch,'artAssetKey'))merged.artAssetKey=base.artAssetKey;if(!has(patch,'artTransform'))merged.artTransform=base.artTransform;else merged.artTransform={...(base.artTransform||{x:50,y:50,scale:1}),...(patch.artTransform||{})};if(!has(patch,'battleSpriteUrl'))merged.battleSpriteUrl=base.battleSpriteUrl;if(!has(patch,'battleSpriteAssetKey'))merged.battleSpriteAssetKey=base.battleSpriteAssetKey;if(!has(patch,'battleSpriteTransform'))merged.battleSpriteTransform=base.battleSpriteTransform;else merged.battleSpriteTransform={...(base.battleSpriteTransform||{x:50,y:50,scale:1}),...(patch.battleSpriteTransform||{})};if(!has(patch,'template'))merged.template=base.template;if(!has(patch,'frameUrl'))merged.frameUrl=base.frameUrl;if(!has(patch,'frameAssetKey'))merged.frameAssetKey=base.frameAssetKey;if(has(patch,'template')&&patch.template==='standard'&&!has(patch,'frameUrl')&&!has(patch,'frameAssetKey')){merged.frameUrl='';merged.frameAssetKey='';}return merged;
}
function exportBatch(){const cards=Object.values(library).sort((a,b)=>String(a.id).localeCompare(String(b.id)));$('batchJson').value=JSON.stringify(cards,null,2);setMessage(`Batch exportado: ${cards.length} carta(s).`);}
function applyBatch(){
 let patches;try{patches=JSON.parse($('batchJson').value.trim()||'[]')}catch(e){setMessage('Batch inválido: '+e.message);return;}if(!Array.isArray(patches)){setMessage('Batch inválido: debe ser una lista JSON.');return;}
 const staged={...library},errors=[];for(const patch of patches){if(!patch||!String(patch.id||'').trim()){errors.push('Hay una entrada sin id.');continue;}const id=String(patch.id).trim(),official=catalogSource(window.SizaCardCatalog?.get(id)),base=staged[id]||official||{...newBlank(),id,name:patch.name||id};const validation=SizaCardSchema.validateCard(mergePatch(base,{...patch,id}));if(!validation.valid)errors.push(`${id}: ${validation.errors.join(' / ')}`);else staged[id]=validation.card;}
 if(errors.length){setMessage('Batch cancelado. '+errors.join(' | '));return;}library=staged;saveLibrary();refreshLibrarySelect($('id').value.trim());const current=library[$('id').value.trim()];if(current)writeForm(current);setMessage(`Batch aplicado: ${patches.length} entrada(s). Arte, Battle Sprite y template manual se conservaron donde el batch no los reemplazó.`);
}

function loadInitial(){
 let draft=null;try{draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null')}catch(e){}refreshLibrarySelect();refreshTemplateSelect();const saved=requestedCardId?library[requestedCardId]:null,official=requestedCardId?catalogSource(window.SizaCardCatalog?.get(requestedCardId)):null;if(requestedCardId){if(saved)writeForm(saved);else if(draft?.id===requestedCardId)writeForm(draft);else if(official)writeForm(official);else writeForm({...EXAMPLE,id:requestedCardId});}else if(draft)writeForm(draft);else writeForm(EXAMPLE);$('testMobile').textContent='Probar en Mobile Test';setMessage(requestedCardId?`Editando ${requestedCardId}. Guardar conserva esta versión, su arte, Battle Sprite y template en la biblioteca local.`:'Guardar carta conserva datos, arte, Battle Sprite, template y ajustes manuales por ID.');
}

for(const id of fields)$(id).addEventListener('input',render);for(const id of Object.values(pipIds))$(id).addEventListener('input',render);for(const id of ['artX','artY','artScale'])$(id).addEventListener('input',()=>{syncArtNumeric();render();});for(const id of ['artXValue','artYValue','artScaleValue'])$(id).addEventListener('input',()=>{syncArtRange();render();});for(const id of ['battleSpriteX','battleSpriteY','battleSpriteScale'])$(id).addEventListener('input',()=>{syncBattleSpriteNumeric();render();});for(const id of ['battleSpriteXValue','battleSpriteYValue','battleSpriteScaleValue'])$(id).addEventListener('input',()=>{syncBattleSpriteRange();render();});
$('savedCards').addEventListener('change',e=>{const card=library[e.target.value];if(card)writeForm(card);});$('newCard').addEventListener('click',newCard);$('deleteCard').addEventListener('click',deleteCurrentCard);$('saveDraft').addEventListener('click',()=>saveDraft());$('loadExample').addEventListener('click',()=>writeForm(EXAMPLE));$('resetDraft').addEventListener('click',resetDraft);$('testMobile').addEventListener('click',prepareHandoff);$('exportBatch').addEventListener('click',exportBatch);$('applyBatch').addEventListener('click',applyBatch);
$('chooseArt').addEventListener('click',()=>$('artFile').click());$('artFile').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)acceptArtFile(file);e.target.value='';});$('removeArt').addEventListener('click',removeArt);
$('chooseBattleSprite').addEventListener('click',()=>$('battleSpriteFile').click());$('battleSpriteFile').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)acceptBattleSpriteFile(file);e.target.value='';});$('removeBattleSprite').addEventListener('click',removeBattleSprite);
$('templateSelect').addEventListener('change',async e=>{await applyTemplateSelection(e.target.value);saveDraft({quiet:true});});$('chooseFrame').addEventListener('click',()=>$('frameFile').click());$('chooseFrameAlt').addEventListener('click',()=>$('frameFile').click());$('standardFrame').addEventListener('click',useStandardFrame);$('frameFile').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)acceptFrameFile(file);e.target.value='';});
const drop=$('artDropZone');drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('dragover')});drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragover');const file=e.dataTransfer?.files?.[0];if(file)acceptArtFile(file);});
const battleDrop=$('battleSpriteDropZone');battleDrop.addEventListener('dragover',e=>{e.preventDefault();battleDrop.classList.add('dragover')});battleDrop.addEventListener('dragleave',()=>battleDrop.classList.remove('dragover'));battleDrop.addEventListener('drop',e=>{e.preventDefault();battleDrop.classList.remove('dragover');const file=e.dataTransfer?.files?.[0];if(file)acceptBattleSpriteFile(file);});
const frameDrop=$('frameDropZone');frameDrop.addEventListener('dragover',e=>{e.preventDefault();frameDrop.classList.add('dragover')});frameDrop.addEventListener('dragleave',()=>frameDrop.classList.remove('dragover'));frameDrop.addEventListener('drop',e=>{e.preventDefault();frameDrop.classList.remove('dragover');const file=e.dataTransfer?.files?.[0];if(file)acceptFrameFile(file);});
window.addEventListener('beforeunload',()=>{revokeArtObjectUrl();revokeBattleSpriteObjectUrl();revokeFrameObjectUrl();});loadInitial();
})();
