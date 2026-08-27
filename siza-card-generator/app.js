(function(){
'use strict';

const DRAFT_KEY='siza_card_generator_draft_v1';
const HANDOFF_KEY='siza_card_generator_handoff_v1';
const LIBRARY_KEY='siza_card_generator_library_v2';
const TEMPLATE_LIBRARY_KEY='siza_card_generator_templates_v2';
const LEGACY_TEMPLATE_LIBRARY_KEY='siza_card_generator_templates_v1';
const ART_DB='siza_card_generator_assets_v1';
const ART_STORE='art';
const TEMPLATE_SLOTS=[
 {key:'frame_base',label:'Frame base',description:'Borde y estructura neutral principal.'},
 {key:'affinity_overlay',label:'Affinity overlay',description:'Color, brillo, runas o energía de afinidad.'},
 {key:'crystal_rail',label:'Crystal rail',description:'Marco visual del área de cristales; los cristales siguen siendo dinámicos.'},
 {key:'title_plate',label:'Title plate',description:'Placa visual detrás del nombre.'},
 {key:'difficulty_badge',label:'Manafestation badge',description:'Medallón visual del requisito de Manafestación.'},
 {key:'art_frame',label:'Art frame',description:'Borde ornamental alrededor de la ilustración.'},
 {key:'type_bar',label:'Type bar',description:'Barra visual del tipo de carta.'},
 {key:'rules_panel',label:'Rules panel',description:'Panel visual del texto de reglas y flavor.'},
 {key:'stat_left',label:'Stat left',description:'Placa visual de Ataque.'},
 {key:'stat_right',label:'Stat right',description:'Placa visual de Defensa.'},
 {key:'footer',label:'Footer',description:'Placa visual de set y número.'},
 {key:'ornament_overlay',label:'Ornament overlay',description:'Filigrana o adornos adicionales impresos.'}
];
const params=new URLSearchParams(location.search);
const returnUrl=params.get('returnUrl')||'../siza-mobile-test/';
const requestedCardId=params.get('cardId')||'';
const $=id=>document.getElementById(id);
const has=(obj,key)=>Object.prototype.hasOwnProperty.call(obj||{},key);
const clone=value=>JSON.parse(JSON.stringify(value));
let sourceMeta={role:'',adventureUnlock:false};
let effectsParseError='';
let library=loadLibrary();
let templates=loadTemplates();
let currentLoadedId='';
let currentArtAssetKey='';
let currentArtObjectUrl='';
let currentBattleSpriteAssetKey='';
let currentBattleSpriteObjectUrl='';
let selectedTemplatePartUrls={};
let builderTemplateDraft=null;
let builderTemplatePartUrls={};
let pendingTemplateSlot='';
let dbPromise=null;

const EXAMPLE={
 id:'memoria_reina_ahogada',name:'Memoria de la Reina Ahogada',template:'standard',templateParts:{},frameUrl:'',frameAssetKey:'',cardType:'Creature',subtype:'Avatar',affinity:'azul',difficulty:8,pips:{U:3},artId:'queen_drowned',artUrl:'',artAssetKey:'',artTransform:{x:50,y:35,scale:1},battleSpriteUrl:'',battleSpriteAssetKey:'',battleSpriteTransform:{x:50,y:50,scale:1},rules:'Al materializarse, roba dos cartas y luego descarta una.',flavor:'La corona sobrevivió porque nadie recordó enterrarla.',force:5,resistance:5,setCode:'SZA',cardNumber:'036',glyph:'♛',effects:[{event:'enter',type:'draw',target:'self',amount:2},{event:'enter',type:'discard',target:'self',amount:1,choice:'owner'}]
};

const fields=['id','name','cardType','subtype','difficulty','affinity','glyph','rules','flavor','force','resistance','setCode','cardNumber','artUrl','battleSpriteUrl','effectsJson'];
const pipIds={U:'pipU',R:'pipR',G:'pipG',W:'pipW',B:'pipB'};
function num(id,fallback=0){const el=$(id),n=Number(el?.value);return Number.isFinite(n)?n:fallback;}
function maybeNum(id){const raw=$(id)?.value?.trim()??'';if(raw==='')return null;const n=Number(raw);return Number.isFinite(n)?n:null;}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function setMessage(text){if($('handoffStatus'))$('handoffStatus').textContent=text;}
function setArtStatus(text){if($('artFileStatus'))$('artFileStatus').textContent=text;}
function setBattleSpriteStatus(text){if($('battleSpriteFileStatus'))$('battleSpriteFileStatus').textContent=text;}
function setBuilderStatus(html){if($('templateBuilderStatus'))$('templateBuilderStatus').innerHTML=html;}

function loadLibrary(){
 try{const raw=JSON.parse(localStorage.getItem(LIBRARY_KEY)||'{}');if(Array.isArray(raw))return Object.fromEntries(raw.filter(x=>x?.id).map(x=>[x.id,x]));return raw&&typeof raw==='object'?raw:{}}catch(e){return{}}
}
function saveLibrary(){localStorage.setItem(LIBRARY_KEY,JSON.stringify(library));}
function normalizeTemplateEntry(input={}){
 const parts={};
 for(const slot of TEMPLATE_SLOTS){const raw=input.parts?.[slot.key];if(!raw)continue;parts[slot.key]={assetKey:String(raw.assetKey||''),url:String(raw.url||''),fileName:String(raw.fileName||'')};}
 if(!parts.frame_base&&(input.frameAssetKey||input.frameUrl))parts.frame_base={assetKey:String(input.frameAssetKey||''),url:String(input.frameUrl||''),fileName:String(input.name||'legacy frame')};
 return{id:String(input.id||`template_${Date.now().toString(36)}`),name:String(input.name||'Template'),version:2,parts,createdAt:input.createdAt||new Date().toISOString(),updatedAt:input.updatedAt||new Date().toISOString()};
}
function loadTemplates(){
 try{
  const raw=JSON.parse(localStorage.getItem(TEMPLATE_LIBRARY_KEY)||'null');
  if(raw&&typeof raw==='object'){const list=Array.isArray(raw)?raw:Object.values(raw);return Object.fromEntries(list.filter(x=>x?.id).map(x=>{const t=normalizeTemplateEntry(x);return[t.id,t]}));}
  const legacy=JSON.parse(localStorage.getItem(LEGACY_TEMPLATE_LIBRARY_KEY)||'{}'),list=Array.isArray(legacy)?legacy:Object.values(legacy||{}),migrated={};
  for(const old of list){if(!old?.id)continue;const t=normalizeTemplateEntry(old);migrated[t.id]=t;}
  if(Object.keys(migrated).length)localStorage.setItem(TEMPLATE_LIBRARY_KEY,JSON.stringify(migrated));
  return migrated;
 }catch(e){return{};}
}
function saveTemplates(){localStorage.setItem(TEMPLATE_LIBRARY_KEY,JSON.stringify(templates));}
function refreshLibrarySelect(selectedId=''){
 const select=$('savedCards');if(!select)return;const cards=Object.values(library).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),'es'));
 select.innerHTML='<option value="">— Cartas guardadas —</option>'+cards.map(c=>`<option value="${escapeHtml(c.id)}">${escapeHtml(c.name||c.id)} · ${escapeHtml(c.id)}</option>`).join('');if(selectedId&&library[selectedId])select.value=selectedId;
}
function refreshTemplateSelect(selectedId='standard'){
 const select=$('templateSelect');if(!select)return;const list=Object.values(templates).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),'es'));
 select.innerHTML='<option value="standard">Standard · sistema</option>'+list.map(t=>`<option value="${escapeHtml(t.id)}">${escapeHtml(t.name||t.id)}</option>`).join('');
 if(selectedId&&selectedId!=='standard'&&!templates[selectedId])select.insertAdjacentHTML('beforeend',`<option value="${escapeHtml(selectedId)}">${escapeHtml(selectedId)} · sin biblioteca local</option>`);select.value=selectedId||'standard';
}
function refreshBuilderSelect(selectedId=''){
 const select=$('builderTemplateSelect');if(!select)return;const list=Object.values(templates).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),'es'));
 select.innerHTML='<option value="">— Nuevo template —</option>'+list.map(t=>`<option value="${escapeHtml(t.id)}">${escapeHtml(t.name||t.id)}</option>`).join('');if(selectedId&&templates[selectedId])select.value=selectedId;
}
function templateEntry(id){return id&&id!=='standard'?templates[id]||null:null;}
function templatePartCount(entry){return TEMPLATE_SLOTS.filter(slot=>entry?.parts?.[slot.key]&&(entry.parts[slot.key].assetKey||entry.parts[slot.key].url)).length;}
function updateCardTemplateStatus(){
 const id=$('templateSelect')?.value||'standard',box=$('templateCardStatus');if(!box)return;
 if(id==='standard'){box.innerHTML='<strong>Standard</strong> · template base del sistema.';return;}
 const entry=templateEntry(id);if(!entry){box.innerHTML=`<strong>${escapeHtml(id)}</strong> · no existe en la biblioteca local de templates.`;return;}
 box.innerHTML=`<strong>${escapeHtml(entry.name)}</strong> · ${templatePartCount(entry)} pieza(s) modulares. Edítelo desde Template Builder.`;
}

function openArtDb(){
 if(!('indexedDB'in window))return Promise.resolve(null);if(dbPromise)return dbPromise;
 dbPromise=new Promise((resolve,reject)=>{const req=indexedDB.open(ART_DB,1);req.onupgradeneeded=()=>{const db=req.result;if(!db.objectStoreNames.contains(ART_STORE))db.createObjectStore(ART_STORE)};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)}).catch(()=>null);return dbPromise;
}
async function artPut(key,blob){const db=await openArtDb();if(!db)return false;return new Promise(resolve=>{const tx=db.transaction(ART_STORE,'readwrite');tx.objectStore(ART_STORE).put(blob,key);tx.oncomplete=()=>resolve(true);tx.onerror=()=>resolve(false)});}
async function artGet(key){const db=await openArtDb();if(!db||!key)return null;return new Promise(resolve=>{const tx=db.transaction(ART_STORE,'readonly'),req=tx.objectStore(ART_STORE).get(key);req.onsuccess=()=>resolve(req.result||null);req.onerror=()=>resolve(null)});}
async function artDelete(key){const db=await openArtDb();if(!db||!key)return;await new Promise(resolve=>{const tx=db.transaction(ART_STORE,'readwrite');tx.objectStore(ART_STORE).delete(key);tx.oncomplete=tx.onerror=()=>resolve()});}
function revokeUrl(url){if(url&&url.startsWith('blob:')&&URL.revokeObjectURL)URL.revokeObjectURL(url);}
function revokeArtObjectUrl(){revokeUrl(currentArtObjectUrl);currentArtObjectUrl='';}
function revokeBattleSpriteObjectUrl(){revokeUrl(currentBattleSpriteObjectUrl);currentBattleSpriteObjectUrl='';}
function revokeUrlMap(map){for(const url of Object.values(map||{}))revokeUrl(url);}
function blobToDataUrl(blob){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result||''));r.onerror=()=>reject(r.error);r.readAsDataURL(blob)});}
async function hydrateArtAsset(key,cardId){if(!key)return;const blob=await artGet(key);if(currentArtAssetKey!==key||$('id').value.trim()!==cardId)return;revokeArtObjectUrl();if(blob&&URL.createObjectURL){currentArtObjectUrl=URL.createObjectURL(blob);setArtStatus(`Ilustración guardada localmente · ${Math.max(1,Math.round(blob.size/1024))} KB`);render()}else setArtStatus('La carta referencia una ilustración local que no está disponible en este navegador.');}
async function hydrateBattleSpriteAsset(key,cardId){if(!key)return;const blob=await artGet(key);if(currentBattleSpriteAssetKey!==key||$('id').value.trim()!==cardId)return;revokeBattleSpriteObjectUrl();if(blob&&URL.createObjectURL){currentBattleSpriteObjectUrl=URL.createObjectURL(blob);setBattleSpriteStatus(`Battle Sprite guardado localmente · ${Math.max(1,Math.round(blob.size/1024))} KB`);render()}else setBattleSpriteStatus('La carta referencia un Battle Sprite local que no está disponible en este navegador.');}
async function hydrateSelectedTemplate(templateId){
 revokeUrlMap(selectedTemplatePartUrls);selectedTemplatePartUrls={};const entry=templateEntry(templateId);updateCardTemplateStatus();if(!entry){render();return;}
 const resolved={};for(const slot of TEMPLATE_SLOTS){const part=entry.parts?.[slot.key];if(!part)continue;if(part.assetKey){const blob=await artGet(part.assetKey);if(blob&&URL.createObjectURL)resolved[slot.key]=URL.createObjectURL(blob);}else if(part.url)resolved[slot.key]=part.url;}
 if(($('templateSelect')?.value||'standard')!==templateId){revokeUrlMap(resolved);return;}selectedTemplatePartUrls=resolved;render();
}
function staticTemplateParts(templateId){const entry=templateEntry(templateId),out={};if(!entry)return out;for(const slot of TEMPLATE_SLOTS){const part=entry.parts?.[slot.key];if(part?.url)out[slot.key]=part.url;}return out;}

function readEffects(){effectsParseError='';const raw=$('effectsJson').value.trim();if(!raw)return[];try{const parsed=JSON.parse(raw);if(!Array.isArray(parsed)){effectsParseError='Effects debe ser una lista JSON.';return[]}return parsed}catch(e){effectsParseError='Effects contiene JSON inválido: '+e.message;return[]}}
function readForm(opts={}){
 const pips={};for(const[k,id]of Object.entries(pipIds)){const n=Math.max(0,Math.trunc(num(id,0)));if(n)pips[k]=n;}
 const externalArt=$('artUrl').value.trim(),externalBattleSprite=$('battleSpriteUrl').value.trim(),template=$('templateSelect')?.value||'standard';
 return{id:$('id').value.trim(),name:$('name').value,template,templateParts:opts.preview?clone(selectedTemplatePartUrls):staticTemplateParts(template),frameUrl:'',frameAssetKey:'',cardType:$('cardType').value,subtype:$('subtype').value,affinity:$('affinity').value,difficulty:num('difficulty',0),pips,artId:$('id').value.trim(),artUrl:opts.preview&&currentArtObjectUrl?currentArtObjectUrl:externalArt,artAssetKey:currentArtAssetKey,artTransform:{x:num('artX',50),y:num('artY',50),scale:num('artScale',1)},battleSpriteUrl:opts.preview&&currentBattleSpriteObjectUrl?currentBattleSpriteObjectUrl:externalBattleSprite,battleSpriteAssetKey:currentBattleSpriteAssetKey,battleSpriteTransform:{x:num('battleSpriteX',50),y:num('battleSpriteY',50),scale:num('battleSpriteScale',1)},rules:$('rules').value,flavor:$('flavor').value,force:maybeNum('force'),resistance:maybeNum('resistance'),setCode:$('setCode').value.trim(),cardNumber:$('cardNumber').value.trim(),glyph:$('glyph').value||'✦',role:sourceMeta.role,adventureUnlock:sourceMeta.adventureUnlock,effects:readEffects()};
}
function ensureTemplateFromCard(c){
 if(!c||c.template==='standard'||templates[c.template])return;const parts={};for(const slot of TEMPLATE_SLOTS){const url=c.templateParts?.[slot.key];if(url)parts[slot.key]={assetKey:'',url,fileName:'importado'};}
 if(!Object.keys(parts).length&&c.frameUrl)parts.frame_base={assetKey:'',url:c.frameUrl,fileName:'frame legado'};if(!Object.keys(parts).length)return;
 templates[c.template]=normalizeTemplateEntry({id:c.template,name:c.template,parts,createdAt:new Date().toISOString()});saveTemplates();refreshTemplateSelect(c.template);refreshBuilderSelect();
}
function writeForm(input){
 const c=SizaCardSchema.normalizeCard(input);ensureTemplateFromCard(c);currentLoadedId=c.id;sourceMeta={role:c.role||'',adventureUnlock:!!c.adventureUnlock};revokeArtObjectUrl();currentArtAssetKey=c.artAssetKey||'';revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey=c.battleSpriteAssetKey||'';refreshTemplateSelect(c.template||'standard');
 $('id').value=c.id;$('name').value=c.name;$('cardType').value=c.cardType;$('subtype').value=c.subtype;$('difficulty').value=c.difficulty;$('affinity').value=['azul','rojo','multi','land'].includes(c.affinity)?c.affinity:'multi';$('glyph').value=c.glyph;$('rules').value=c.rules;$('flavor').value=c.flavor;$('force').value=c.power??'';$('resistance').value=c.toughness??'';$('setCode').value=c.setCode;$('cardNumber').value=c.cardNumber;$('artUrl').value=c.artUrl;$('battleSpriteUrl').value=c.battleSpriteUrl;$('effectsJson').value=JSON.stringify(c.effects||[],null,2);for(const[k,id]of Object.entries(pipIds))$(id).value=c.pips?.[k]||0;$('artX').value=c.artTransform.x;$('artY').value=c.artTransform.y;$('artScale').value=c.artTransform.scale;$('battleSpriteX').value=c.battleSpriteTransform.x;$('battleSpriteY').value=c.battleSpriteTransform.y;$('battleSpriteScale').value=c.battleSpriteTransform.scale;syncArtNumeric();syncBattleSpriteNumeric();
 setArtStatus(currentArtAssetKey?'Cargando ilustración guardada…':c.artUrl?'Usando URL externa de ilustración.':'Sin ilustración cargada.');setBattleSpriteStatus(currentBattleSpriteAssetKey?'Cargando Battle Sprite guardado…':c.battleSpriteUrl?'Usando URL externa de Battle Sprite.':'Sin Battle Sprite cargado.');refreshLibrarySelect(c.id);updateCardTemplateStatus();render();if(currentArtAssetKey)hydrateArtAsset(currentArtAssetKey,c.id);if(currentBattleSpriteAssetKey)hydrateBattleSpriteAsset(currentBattleSpriteAssetKey,c.id);hydrateSelectedTemplate(c.template||'standard');
}
function syncArtNumeric(){$('artXValue').value=$('artX').value;$('artYValue').value=$('artY').value;$('artScaleValue').value=$('artScale').value;}
function syncArtRange(){$('artX').value=$('artXValue').value;$('artY').value=$('artYValue').value;$('artScale').value=$('artScaleValue').value;}
function syncBattleSpriteNumeric(){$('battleSpriteXValue').value=$('battleSpriteX').value;$('battleSpriteYValue').value=$('battleSpriteY').value;$('battleSpriteScaleValue').value=$('battleSpriteScale').value;}
function syncBattleSpriteRange(){$('battleSpriteX').value=$('battleSpriteXValue').value;$('battleSpriteY').value=$('battleSpriteYValue').value;$('battleSpriteScale').value=$('battleSpriteScaleValue').value;}
function renderBattleSpritePreview(c){const box=$('battleSpritePreview');if(!box)return;const src=currentBattleSpriteObjectUrl||c.battleSpriteUrl,t=c.battleSpriteTransform;if(!src){box.innerHTML='<span>Sin Battle Sprite</span>';return;}box.innerHTML=`<img src="${escapeHtml(src)}" alt="" style="left:${t.x}%;top:${t.y}%;transform:translate(-50%,-50%) scale(${t.scale})" onerror="this.parentElement.innerHTML='<span>Battle Sprite no disponible</span>'">`;}
function render(){
 const storedValidation=SizaCardSchema.validateCard(readForm()),previewValidation=SizaCardSchema.validateCard(readForm({preview:true}));if(effectsParseError){storedValidation.valid=false;storedValidation.errors.unshift(effectsParseError);previewValidation.valid=false;}
 SizaCardRenderer.mount($('cardPreview'),previewValidation.card);renderBattleSpritePreview(previewValidation.card);$('jsonOutput').value=JSON.stringify(storedValidation.card,null,2);$('schemaVersion').textContent='Schema '+SizaCardSchema.VERSION+' · Effects '+(window.SizaCardEffects?.VERSION||'—');
 const box=$('validationStatus');if(storedValidation.valid){box.className='status good';box.innerHTML=`<b>Schema válido</b>${storedValidation.warnings.length?storedValidation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'Lista para guardar o probar.'}`}else{box.className='status bad';box.innerHTML='<b>Schema inválido</b>'+storedValidation.errors.map(escapeHtml).join('<br>')+(storedValidation.warnings.length?'<br>'+storedValidation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'')}
 return storedValidation;
}

function saveDraft(opts={}){const validation=render();if(!validation.valid){if(!opts.quiet)setMessage('Carta no guardada: corrija los errores.');return null;}const card=validation.card;localStorage.setItem(DRAFT_KEY,JSON.stringify(card));library[card.id]=card;saveLibrary();currentLoadedId=card.id;refreshLibrarySelect(card.id);if(!opts.quiet)setMessage(`Carta guardada: ${card.name} · ${card.id}`);return card;}
function newBlank(){return{...EXAMPLE,id:'card_'+Date.now(),name:'Carta sin nombre',template:'standard',templateParts:{},frameUrl:'',frameAssetKey:'',difficulty:1,pips:{},artId:'',artUrl:'',artAssetKey:'',artTransform:{x:50,y:50,scale:1},battleSpriteUrl:'',battleSpriteAssetKey:'',battleSpriteTransform:{x:50,y:50,scale:1},rules:'',flavor:'',force:2,resistance:2,cardNumber:'000',glyph:'✦',effects:[]};}
function newCard(){writeForm(newBlank());setMessage('Nueva carta. Seleccione un template guardado, cargue ilustración/Battle Sprite y guarde cuando esté lista.');}
function resetDraft(){const saved=library[currentLoadedId];if(saved)writeForm(saved);else newCard();}
async function deleteCurrentCard(){const id=$('id').value.trim(),saved=library[id];if(!saved){setMessage('Esta carta todavía no está guardada en la biblioteca.');return;}if(saved.artAssetKey)await artDelete(saved.artAssetKey);if(saved.battleSpriteAssetKey)await artDelete(saved.battleSpriteAssetKey);delete library[id];saveLibrary();try{const draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');if(draft?.id===id)localStorage.removeItem(DRAFT_KEY)}catch(e){}refreshLibrarySelect();newCard();setMessage(`Carta eliminada de la biblioteca: ${id}`);}

async function optimizedArtBlob(file,limit=1800,quality=.9){if(!window.createImageBitmap)return file;try{const bitmap=await createImageBitmap(file),ratio=Math.min(1,limit/bitmap.width,limit/bitmap.height),w=Math.max(1,Math.round(bitmap.width*ratio)),h=Math.max(1,Math.round(bitmap.height*ratio)),canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0,w,h);bitmap.close?.();const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',quality));return blob||file}catch(e){return file}}
async function acceptArtFile(file){if(!file||!file.type?.startsWith('image/')){setArtStatus('El archivo seleccionado no es una imagen.');return;}const id=$('id').value.trim()||('card_'+Date.now());if(!$('id').value.trim())$('id').value=id;setArtStatus('Procesando ilustración…');const blob=await optimizedArtBlob(file),db=await openArtDb();if(db){const oldKey=currentArtAssetKey,key=`art:${id}:${Date.now()}`;if(!(await artPut(key,blob))){setArtStatus('No se pudo guardar la ilustración localmente.');return;}if(oldKey&&oldKey!==key)artDelete(oldKey);revokeArtObjectUrl();currentArtAssetKey=key;currentArtObjectUrl=URL.createObjectURL?URL.createObjectURL(blob):'';$('artUrl').value='';setArtStatus(`Ilustración guardada · ${Math.max(1,Math.round(blob.size/1024))} KB`);render();saveDraft({quiet:true})}else{try{revokeArtObjectUrl();currentArtAssetKey='';$('artUrl').value=await blobToDataUrl(blob);setArtStatus('Ilustración guardada dentro del borrador del navegador.');render();saveDraft({quiet:true})}catch(e){setArtStatus('No se pudo leer la ilustración.')}}}
async function removeArt(){const old=currentArtAssetKey;if(old)await artDelete(old);revokeArtObjectUrl();currentArtAssetKey='';$('artUrl').value='';setArtStatus('Sin ilustración cargada.');render();saveDraft({quiet:true});}
async function acceptBattleSpriteFile(file){if(!file||!file.type?.startsWith('image/')){setBattleSpriteStatus('El archivo seleccionado no es una imagen.');return;}const id=$('id').value.trim()||('card_'+Date.now());if(!$('id').value.trim())$('id').value=id;setBattleSpriteStatus('Procesando Battle Sprite…');const blob=await optimizedArtBlob(file,1400,.92),db=await openArtDb();if(db){const oldKey=currentBattleSpriteAssetKey,key=`battle-sprite:${id}:${Date.now()}`;if(!(await artPut(key,blob))){setBattleSpriteStatus('No se pudo guardar el Battle Sprite localmente.');return;}if(oldKey&&oldKey!==key)artDelete(oldKey);revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey=key;currentBattleSpriteObjectUrl=URL.createObjectURL?URL.createObjectURL(blob):'';$('battleSpriteUrl').value='';setBattleSpriteStatus(`Battle Sprite guardado · ${Math.max(1,Math.round(blob.size/1024))} KB`);render();saveDraft({quiet:true})}else{try{revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey='';$('battleSpriteUrl').value=await blobToDataUrl(blob);setBattleSpriteStatus('Battle Sprite guardado dentro del borrador del navegador.');render();saveDraft({quiet:true})}catch(e){setBattleSpriteStatus('No se pudo leer el Battle Sprite.')}}}
async function removeBattleSprite(){const old=currentBattleSpriteAssetKey;if(old)await artDelete(old);revokeBattleSpriteObjectUrl();currentBattleSpriteAssetKey='';$('battleSpriteUrl').value='';setBattleSpriteStatus('Sin Battle Sprite cargado.');render();saveDraft({quiet:true});}

function makeTemplateId(){return `template_${Date.now().toString(36)}`;}
function blankTemplate(){return{id:makeTemplateId(),name:'Nuevo template',version:2,parts:{},createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()};}
function builderPartUrl(slot){return builderTemplatePartUrls[slot]||builderTemplateDraft?.parts?.[slot]?.url||'';}
function renderTemplateBuilder(){
 if(!builderTemplateDraft)builderTemplateDraft=blankTemplate();$('templateBuilderName').value=builderTemplateDraft.name||'';$('templateBuilderId').value=builderTemplateDraft.id||'';
 const slots=$('templateSlots');slots.innerHTML=TEMPLATE_SLOTS.map(slot=>{const part=builderTemplateDraft.parts?.[slot.key],src=builderPartUrl(slot.key),file=part?.fileName||'';return `<div class="templateSlot" data-slot="${slot.key}"><div class="templateSlotPreview">${src?`<img src="${escapeHtml(src)}" alt="">`:'VACÍO'}</div><div class="templateSlotCopy"><b>${escapeHtml(slot.label)}</b><span>${escapeHtml(slot.description)}</span><span class="templateSlotFile">${file?escapeHtml(file):'Sin archivo'}</span></div><div class="templateSlotActions"><button class="btn primary" type="button" data-template-upload="${slot.key}">Subir</button><button class="btn ghost" type="button" data-template-remove="${slot.key}" ${part?'':'disabled'}>Quitar</button></div></div>`}).join('');renderTemplatePreview();
}
function renderTemplatePreview(){
 const stage=$('templatePreview'),legend=$('templateLayerLegend');if(!stage||!legend)return;const layers=[];for(const slot of TEMPLATE_SLOTS){const src=builderPartUrl(slot.key);if(src)layers.push({slot,src});}
 stage.innerHTML=layers.length?layers.map(x=>`<img src="${escapeHtml(x.src)}" alt="${escapeHtml(x.slot.label)}" data-template-layer="${x.slot.key}">`).join(''):'<div class="templateAssembleEmpty">Cargue piezas en los slots del Template Builder.</div>';
 $('templatePreviewCount').textContent=`${layers.length} pieza${layers.length===1?'':'s'}`;legend.innerHTML=TEMPLATE_SLOTS.map(slot=>`<span class="${layers.some(x=>x.slot.key===slot.key)?'on':''}">${escapeHtml(slot.label)}</span>`).join('');
}
async function hydrateBuilderTemplateParts(){
 revokeUrlMap(builderTemplatePartUrls);builderTemplatePartUrls={};const draft=builderTemplateDraft;if(!draft){renderTemplateBuilder();return;}const resolved={};for(const slot of TEMPLATE_SLOTS){const part=draft.parts?.[slot.key];if(!part)continue;if(part.assetKey){const blob=await artGet(part.assetKey);if(blob&&URL.createObjectURL)resolved[slot.key]=URL.createObjectURL(blob);}else if(part.url)resolved[slot.key]=part.url;}
 if(builderTemplateDraft?.id!==draft.id){revokeUrlMap(resolved);return;}builderTemplatePartUrls=resolved;renderTemplateBuilder();
}
async function loadBuilderTemplate(id=''){builderTemplateDraft=id&&templates[id]?clone(templates[id]):blankTemplate();refreshBuilderSelect(id&&templates[id]?id:'');setBuilderStatus(id&&templates[id]?`<strong>${escapeHtml(templates[id].name)}</strong> · editando template guardado.`:'<strong>Nuevo template</strong> · cargue piezas modulares y guárdelo.');await hydrateBuilderTemplateParts();}
async function validateTemplateFile(file){if(!file||!['image/png','image/webp'].includes(file.type))return{valid:false,message:'Las piezas del template deben ser PNG o WebP con transparencia.'};if(!window.createImageBitmap)return{valid:true};try{const bitmap=await createImageBitmap(file),w=bitmap.width,h=bitmap.height;bitmap.close?.();if(w!==1500||h!==2100)return{valid:false,message:`Canvas inválido: ${w}×${h}. Cada pieza debe ser exactamente 1500×2100.`};return{valid:true}}catch(e){return{valid:false,message:'No se pudo leer la imagen.'}}}
async function acceptTemplatePartFile(slot,file){
 if(!builderTemplateDraft)return;const check=await validateTemplateFile(file);if(!check.valid){setBuilderStatus(`<strong>${escapeHtml(TEMPLATE_SLOTS.find(x=>x.key===slot)?.label||slot)}</strong> · ${escapeHtml(check.message)}`);return;}const old=builderTemplateDraft.parts?.[slot],db=await openArtDb(),part={assetKey:'',url:'',fileName:file.name};if(db){const key=`template:${builderTemplateDraft.id}:${slot}:${Date.now()}`;if(!(await artPut(key,file))){setBuilderStatus('<strong>Error</strong> · no se pudo guardar la pieza en IndexedDB.');return;}part.assetKey=key;if(old?.assetKey&&old.assetKey!==key)artDelete(old.assetKey);revokeUrl(builderTemplatePartUrls[slot]);builderTemplatePartUrls[slot]=URL.createObjectURL?URL.createObjectURL(file):'';}else{try{part.url=await blobToDataUrl(file);builderTemplatePartUrls[slot]=part.url}catch(e){setBuilderStatus('<strong>Error</strong> · no se pudo leer la pieza.');return;}}
 builderTemplateDraft.parts=builderTemplateDraft.parts||{};builderTemplateDraft.parts[slot]=part;builderTemplateDraft.updatedAt=new Date().toISOString();setBuilderStatus(`<strong>${escapeHtml(TEMPLATE_SLOTS.find(x=>x.key===slot)?.label||slot)}</strong> · pieza cargada en canvas 1500×2100.`);renderTemplateBuilder();
}
async function removeTemplatePart(slot){const part=builderTemplateDraft?.parts?.[slot];if(!part)return;if(part.assetKey)await artDelete(part.assetKey);revokeUrl(builderTemplatePartUrls[slot]);delete builderTemplatePartUrls[slot];delete builderTemplateDraft.parts[slot];builderTemplateDraft.updatedAt=new Date().toISOString();renderTemplateBuilder();setBuilderStatus(`<strong>${escapeHtml(TEMPLATE_SLOTS.find(x=>x.key===slot)?.label||slot)}</strong> · pieza quitada.`);}
async function saveTemplate(quiet=false){
 if(!builderTemplateDraft)return null;const name=$('templateBuilderName').value.trim();if(!name){setBuilderStatus('<strong>Error</strong> · escriba un nombre para el template.');return null;}if(!templatePartCount(builderTemplateDraft)){setBuilderStatus('<strong>Error</strong> · cargue al menos una pieza antes de guardar.');return null;}
 builderTemplateDraft.name=name;builderTemplateDraft.updatedAt=new Date().toISOString();templates[builderTemplateDraft.id]=clone(builderTemplateDraft);saveTemplates();refreshTemplateSelect($('templateSelect').value||'standard');refreshBuilderSelect(builderTemplateDraft.id);if(($('templateSelect').value||'standard')===builderTemplateDraft.id)await hydrateSelectedTemplate(builderTemplateDraft.id);if(!quiet)setBuilderStatus(`<strong>${escapeHtml(name)}</strong> · guardado con ${templatePartCount(builderTemplateDraft)} pieza(s). Ya aparece en Card Creator.`);return templates[builderTemplateDraft.id];
}
async function deleteTemplate(){
 const id=builderTemplateDraft?.id;if(!id||!templates[id]){await loadBuilderTemplate('');return;}const entry=templates[id];for(const slot of TEMPLATE_SLOTS){const key=entry.parts?.[slot.key]?.assetKey;if(key)await artDelete(key);}delete templates[id];saveTemplates();if(($('templateSelect').value||'standard')===id){refreshTemplateSelect('standard');$('templateSelect').value='standard';await hydrateSelectedTemplate('standard');saveDraft({quiet:true});}refreshTemplateSelect($('templateSelect').value||'standard');refreshBuilderSelect();await loadBuilderTemplate('');setBuilderStatus(`<strong>${escapeHtml(entry.name)}</strong> · template eliminado.`);
}
async function useBuilderTemplateInCard(){const entry=await saveTemplate(true);if(!entry)return;refreshTemplateSelect(entry.id);$('templateSelect').value=entry.id;await hydrateSelectedTemplate(entry.id);saveDraft({quiet:true});switchTab('card');setMessage(`Template seleccionado: ${entry.name}.`);}

async function materializeArt(card){if(!card.artAssetKey)return card;const blob=await artGet(card.artAssetKey);if(!blob)return card;try{return{...card,artUrl:await blobToDataUrl(blob)}}catch(e){return card}}
async function materializeBattleSprite(card){if(card.battleSpriteUrl||!card.battleSpriteAssetKey)return card;const blob=await artGet(card.battleSpriteAssetKey);if(!blob)return card;try{return{...card,battleSpriteUrl:await blobToDataUrl(blob)}}catch(e){return card}}
async function materializeTemplateParts(card){
 const entry=templateEntry(card.template);if(!entry)return card;const parts={};for(const slot of TEMPLATE_SLOTS){const part=entry.parts?.[slot.key];if(!part)continue;if(part.url)parts[slot.key]=part.url;else if(part.assetKey){const blob=await artGet(part.assetKey);if(blob)try{parts[slot.key]=await blobToDataUrl(blob)}catch(e){}}}return{...card,templateParts:parts,frameUrl:'',frameAssetKey:''};
}
async function prepareHandoff(){
 const validation=render();if(!validation.valid){setMessage('Handoff bloqueado: corrija los errores de schema.');return;}const stored=validation.card;localStorage.setItem(DRAFT_KEY,JSON.stringify(stored));let card=await materializeArt(stored);card=await materializeBattleSprite(card);card=await materializeTemplateParts(card);const payload={action:'test-card',card:SizaCardSchema.cardToMobileShape(card),generatorCard:card,target:'collection',returnUrl,createdAt:new Date().toISOString()};try{localStorage.setItem(HANDOFF_KEY,JSON.stringify(payload));location.href=returnUrl}catch(e){setMessage('Los assets son demasiado grandes para el handoff temporal. Reduzca peso de las piezas o imágenes; la carta guardada localmente no se pierde.');}
}

function catalogSource(card){if(!card)return null;const affinity=card.art==='blue'?'azul':card.art==='red'?'rojo':card.art==='land'?'land':'multi';return{...card,affinity};}
function mergePatch(base,patch){const merged={...base,...patch};if(!has(patch,'pips'))merged.pips=base.pips;if(!has(patch,'effects'))merged.effects=base.effects;if(!has(patch,'artUrl'))merged.artUrl=base.artUrl;if(!has(patch,'artAssetKey'))merged.artAssetKey=base.artAssetKey;if(!has(patch,'artTransform'))merged.artTransform=base.artTransform;else merged.artTransform={...(base.artTransform||{x:50,y:50,scale:1}),...(patch.artTransform||{})};if(!has(patch,'battleSpriteUrl'))merged.battleSpriteUrl=base.battleSpriteUrl;if(!has(patch,'battleSpriteAssetKey'))merged.battleSpriteAssetKey=base.battleSpriteAssetKey;if(!has(patch,'battleSpriteTransform'))merged.battleSpriteTransform=base.battleSpriteTransform;else merged.battleSpriteTransform={...(base.battleSpriteTransform||{x:50,y:50,scale:1}),...(patch.battleSpriteTransform||{})};if(!has(patch,'template'))merged.template=base.template;if(!has(patch,'templateParts'))merged.templateParts=base.templateParts;return merged;}
function exportBatch(){const cards=Object.values(library).sort((a,b)=>String(a.id).localeCompare(String(b.id)));$('batchJson').value=JSON.stringify(cards,null,2);setMessage(`Batch exportado: ${cards.length} carta(s).`);}
function applyBatch(){let patches;try{patches=JSON.parse($('batchJson').value.trim()||'[]')}catch(e){setMessage('Batch inválido: '+e.message);return;}if(!Array.isArray(patches)){setMessage('Batch inválido: debe ser una lista JSON.');return;}const staged={...library},errors=[];for(const patch of patches){if(!patch||!String(patch.id||'').trim()){errors.push('Hay una entrada sin id.');continue;}const id=String(patch.id).trim(),official=catalogSource(window.SizaCardCatalog?.get(id)),base=staged[id]||official||{...newBlank(),id,name:patch.name||id},validation=SizaCardSchema.validateCard(mergePatch(base,{...patch,id}));if(!validation.valid)errors.push(`${id}: ${validation.errors.join(' / ')}`);else staged[id]=validation.card;}if(errors.length){setMessage('Batch cancelado. '+errors.join(' | '));return;}library=staged;saveLibrary();refreshLibrarySelect($('id').value.trim());const current=library[$('id').value.trim()];if(current)writeForm(current);setMessage(`Batch aplicado: ${patches.length} entrada(s). Arte, Battle Sprite y selección de template se conservaron donde el batch no los reemplazó.`);}

function switchTab(tab){const template=tab==='template';$('cardTabPanel').hidden=template;$('templateTabPanel').hidden=!template;$('cardPreviewPanel').hidden=template;$('templatePreviewPanel').hidden=!template;$('tabCardBtn').classList.toggle('active',!template);$('tabTemplateBtn').classList.toggle('active',template);if(template){const current=$('templateSelect').value;if(current!=='standard'&&templates[current])loadBuilderTemplate(current);else if(!builderTemplateDraft)loadBuilderTemplate('');}}
function loadInitial(){let draft=null;try{draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null')}catch(e){}refreshLibrarySelect();refreshTemplateSelect();refreshBuilderSelect();const saved=requestedCardId?library[requestedCardId]:null,official=requestedCardId?catalogSource(window.SizaCardCatalog?.get(requestedCardId)):null;if(requestedCardId){if(saved)writeForm(saved);else if(draft?.id===requestedCardId)writeForm(draft);else if(official)writeForm(official);else writeForm({...EXAMPLE,id:requestedCardId})}else if(draft)writeForm(draft);else writeForm(EXAMPLE);loadBuilderTemplate('');$('testMobile').textContent='Probar en Mobile Test';setMessage(requestedCardId?`Editando ${requestedCardId}. Guardar conserva carta, arte, Battle Sprite y selección de template.`:'Guardar carta conserva datos y selección de template; las piezas del template se administran en Template Builder.');}

for(const id of fields)$(id)?.addEventListener('input',render);for(const id of Object.values(pipIds))$(id)?.addEventListener('input',render);for(const id of ['artX','artY','artScale'])$(id)?.addEventListener('input',()=>{syncArtNumeric();render()});for(const id of ['artXValue','artYValue','artScaleValue'])$(id)?.addEventListener('input',()=>{syncArtRange();render()});for(const id of ['battleSpriteX','battleSpriteY','battleSpriteScale'])$(id)?.addEventListener('input',()=>{syncBattleSpriteNumeric();render()});for(const id of ['battleSpriteXValue','battleSpriteYValue','battleSpriteScaleValue'])$(id)?.addEventListener('input',()=>{syncBattleSpriteRange();render()});
$('savedCards').addEventListener('change',e=>{const card=library[e.target.value];if(card)writeForm(card)});$('newCard').addEventListener('click',newCard);$('deleteCard').addEventListener('click',deleteCurrentCard);$('saveDraft').addEventListener('click',()=>saveDraft());$('loadExample').addEventListener('click',()=>writeForm(EXAMPLE));$('resetDraft').addEventListener('click',resetDraft);$('testMobile').addEventListener('click',prepareHandoff);$('exportBatch').addEventListener('click',exportBatch);$('applyBatch').addEventListener('click',applyBatch);
$('chooseArt').addEventListener('click',()=>$('artFile').click());$('artFile').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)acceptArtFile(file);e.target.value=''});$('removeArt').addEventListener('click',removeArt);
$('chooseBattleSprite').addEventListener('click',()=>$('battleSpriteFile').click());$('battleSpriteFile').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)acceptBattleSpriteFile(file);e.target.value=''});$('removeBattleSprite').addEventListener('click',removeBattleSprite);
$('templateSelect').addEventListener('change',async e=>{await hydrateSelectedTemplate(e.target.value);saveDraft({quiet:true})});$('openTemplateBuilder').addEventListener('click',()=>switchTab('template'));
$('tabCardBtn').addEventListener('click',()=>switchTab('card'));$('tabTemplateBtn').addEventListener('click',()=>switchTab('template'));
$('templateBuilderName').addEventListener('input',e=>{if(builderTemplateDraft)builderTemplateDraft.name=e.target.value});$('builderTemplateSelect').addEventListener('change',e=>loadBuilderTemplate(e.target.value));$('newTemplate').addEventListener('click',()=>loadBuilderTemplate(''));$('deleteTemplate').addEventListener('click',deleteTemplate);$('saveTemplate').addEventListener('click',()=>saveTemplate());$('useTemplateInCard').addEventListener('click',useBuilderTemplateInCard);
$('templateSlots').addEventListener('click',e=>{const upload=e.target.closest('[data-template-upload]'),remove=e.target.closest('[data-template-remove]');if(upload){pendingTemplateSlot=upload.dataset.templateUpload;$('templatePartFile').click()}else if(remove)removeTemplatePart(remove.dataset.templateRemove)});$('templatePartFile').addEventListener('change',e=>{const file=e.target.files?.[0],slot=pendingTemplateSlot;pendingTemplateSlot='';if(file&&slot)acceptTemplatePartFile(slot,file);e.target.value=''});
const drop=$('artDropZone');drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('dragover')});drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragover');const file=e.dataTransfer?.files?.[0];if(file)acceptArtFile(file)});
const battleDrop=$('battleSpriteDropZone');battleDrop.addEventListener('dragover',e=>{e.preventDefault();battleDrop.classList.add('dragover')});battleDrop.addEventListener('dragleave',()=>battleDrop.classList.remove('dragover'));battleDrop.addEventListener('drop',e=>{e.preventDefault();battleDrop.classList.remove('dragover');const file=e.dataTransfer?.files?.[0];if(file)acceptBattleSpriteFile(file)});
window.addEventListener('beforeunload',()=>{revokeArtObjectUrl();revokeBattleSpriteObjectUrl();revokeUrlMap(selectedTemplatePartUrls);revokeUrlMap(builderTemplatePartUrls)});
window.SizaTemplateBuilder=Object.freeze({slots:TEMPLATE_SLOTS.map(x=>({...x})),switchTab,loadTemplate:id=>loadBuilderTemplate(id)});
loadInitial();
})();
