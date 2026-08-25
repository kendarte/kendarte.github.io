(function(){
'use strict';

const DRAFT_KEY='siza_card_generator_draft_v1';
const HANDOFF_KEY='siza_card_generator_handoff_v1';
const params=new URLSearchParams(location.search);
const returnUrl=params.get('returnUrl')||'../siza-mobile-test/';
const requestedCardId=params.get('cardId')||'';
const $=id=>document.getElementById(id);
let sourceMeta={role:'',adventureUnlock:false};
let effectsParseError='';

const EXAMPLE={
 id:'memoria_reina_ahogada',name:'Memoria de la Reina Ahogada',template:'standard',cardType:'Creature',subtype:'Avatar',affinity:'azul',difficulty:8,cost:5,pips:{U:3},artId:'queen_drowned',artUrl:'',artTransform:{x:50,y:35,scale:1},rules:'Al materializarse, roba dos cartas y luego descarta una.',flavor:'La corona sobrevivió porque nadie recordó enterrarla.',force:5,resistance:5,setCode:'SZA',cardNumber:'036',glyph:'♛',effects:[{event:'enter',type:'draw',target:'self',amount:2},{event:'enter',type:'discard',target:'self',amount:1,choice:'owner'}]
};

const fields=['id','name','cardType','subtype','difficulty','cost','affinity','glyph','rules','flavor','force','resistance','setCode','cardNumber','artUrl','effectsJson'];
const pipIds={U:'pipU',R:'pipR',G:'pipG',W:'pipW',B:'pipB'};
function num(id,fallback=0){const n=Number($(id).value);return Number.isFinite(n)?n:fallback;}
function maybeNum(id){const raw=$(id).value.trim();if(raw==='')return null;const n=Number(raw);return Number.isFinite(n)?n:null;}
function readEffects(){effectsParseError='';const raw=$('effectsJson').value.trim();if(!raw)return[];try{const parsed=JSON.parse(raw);if(!Array.isArray(parsed)){effectsParseError='Effects debe ser una lista JSON.';return[]}return parsed}catch(e){effectsParseError='Effects contiene JSON inválido: '+e.message;return[]}}

function readForm(){const pips={};for(const[k,id]of Object.entries(pipIds)){const n=Math.max(0,Math.trunc(num(id,0)));if(n)pips[k]=n;}return{id:$('id').value.trim(),name:$('name').value,template:'standard',cardType:$('cardType').value,subtype:$('subtype').value,affinity:$('affinity').value,difficulty:num('difficulty',0),cost:num('cost',0),pips,artId:$('id').value.trim(),artUrl:$('artUrl').value.trim(),artTransform:{x:num('artX',50),y:num('artY',50),scale:num('artScale',1)},rules:$('rules').value,flavor:$('flavor').value,force:maybeNum('force'),resistance:maybeNum('resistance'),setCode:$('setCode').value.trim(),cardNumber:$('cardNumber').value.trim(),glyph:$('glyph').value||'✦',role:sourceMeta.role,adventureUnlock:sourceMeta.adventureUnlock,effects:readEffects()};}

function writeForm(input){const c=SizaCardSchema.normalizeCard(input);sourceMeta={role:c.role||'',adventureUnlock:!!c.adventureUnlock};$('id').value=c.id;$('name').value=c.name;$('cardType').value=c.cardType;$('subtype').value=c.subtype;$('difficulty').value=c.difficulty;$('cost').value=c.cost;$('affinity').value=['azul','rojo','multi','land'].includes(c.affinity)?c.affinity:'multi';$('glyph').value=c.glyph;$('rules').value=c.rules;$('flavor').value=c.flavor;$('force').value=c.power??'';$('resistance').value=c.toughness??'';$('setCode').value=c.setCode;$('cardNumber').value=c.cardNumber;$('artUrl').value=c.artUrl;$('effectsJson').value=JSON.stringify(c.effects||[],null,2);for(const[k,id]of Object.entries(pipIds))$(id).value=c.pips?.[k]||0;$('artX').value=c.artTransform.x;$('artY').value=c.artTransform.y;$('artScale').value=c.artTransform.scale;syncArtNumeric();render();}
function syncArtNumeric(){$('artXValue').value=$('artX').value;$('artYValue').value=$('artY').value;$('artScaleValue').value=$('artScale').value;}
function syncArtRange(){$('artX').value=$('artXValue').value;$('artY').value=$('artYValue').value;$('artScale').value=$('artScaleValue').value;}

function render(){const validation=SizaCardSchema.validateCard(readForm()),card=validation.card;if(effectsParseError){validation.valid=false;validation.errors.unshift(effectsParseError)}SizaCardRenderer.mount($('cardPreview'),card);$('jsonOutput').value=JSON.stringify(card,null,2);$('schemaVersion').textContent='Schema '+SizaCardSchema.VERSION+' · Effects '+(window.SizaCardEffects?.VERSION||'—');const box=$('validationStatus');if(validation.valid){box.className='status good';box.innerHTML=`<b>Schema válido</b>${validation.warnings.length?validation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'La carta puede pasar al handoff de prueba.'}`}else{box.className='status bad';box.innerHTML='<b>Schema inválido</b>'+validation.errors.map(escapeHtml).join('<br>')+(validation.warnings.length?'<br>'+validation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'')}return validation;}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function saveDraft(){const validation=render();if(!validation.valid)return $('handoffStatus').textContent='Borrador no guardado: corrige los errores.';localStorage.setItem(DRAFT_KEY,JSON.stringify(validation.card));$('handoffStatus').textContent=`Borrador guardado localmente: ${validation.card.id}`;}
function resetDraft(){localStorage.removeItem(DRAFT_KEY);writeForm({...EXAMPLE,id:'card_'+Date.now(),name:'Carta sin nombre',rules:'',flavor:'',artUrl:'',force:2,resistance:2,cardNumber:'000',effects:[]});}

function prepareHandoff(){const validation=render();if(!validation.valid){$('handoffStatus').textContent='Handoff bloqueado: corrige los errores de schema.';return;}localStorage.setItem(DRAFT_KEY,JSON.stringify(validation.card));const payload={action:'test-card',card:SizaCardSchema.cardToMobileShape(validation.card),generatorCard:validation.card,target:'collection',returnUrl,createdAt:new Date().toISOString()};localStorage.setItem(HANDOFF_KEY,JSON.stringify(payload));location.href=returnUrl;}

function catalogSource(card){if(!card)return null;const affinity=card.art==='blue'?'azul':card.art==='red'?'rojo':card.art==='land'?'land':'multi';return{...card,affinity};}
function loadInitial(){let draft=null;try{draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null')}catch(e){}const official=requestedCardId?catalogSource(window.SizaCardCatalog?.get(requestedCardId)):null;if(requestedCardId){if(draft?.id===requestedCardId)writeForm(draft);else if(official)writeForm(official);else writeForm({...EXAMPLE,id:requestedCardId});}else if(draft)writeForm(draft);else writeForm(EXAMPLE);$('testMobile').textContent='Probar en Mobile Test';$('handoffStatus').textContent=requestedCardId?`Editando ${requestedCardId}. Probar en Mobile Test reemplaza sólo la versión temporal con este mismo ID.`:'Probar en Mobile Test guarda esta versión como carta temporal y abre Collection. El catálogo oficial no se modifica.';}

for(const id of fields)$(id).addEventListener('input',render);for(const id of Object.values(pipIds))$(id).addEventListener('input',render);for(const id of ['artX','artY','artScale'])$(id).addEventListener('input',()=>{syncArtNumeric();render();});for(const id of ['artXValue','artYValue','artScaleValue'])$(id).addEventListener('input',()=>{syncArtRange();render();});
$('saveDraft').addEventListener('click',saveDraft);$('loadExample').addEventListener('click',()=>writeForm(EXAMPLE));$('resetDraft').addEventListener('click',resetDraft);$('testMobile').addEventListener('click',prepareHandoff);loadInitial();
})();
