(function(){
'use strict';

const DRAFT_KEY='siza_card_generator_draft_v1';
const HANDOFF_KEY='siza_card_generator_handoff_v1';
const params=new URLSearchParams(location.search);
const returnUrl=params.get('returnUrl')||'../siza-mobile-test/';
const requestedCardId=params.get('cardId')||'';
const $=id=>document.getElementById(id);

const EXAMPLE={
 id:'memoria_reina_ahogada',name:'Memoria de la Reina Ahogada',template:'standard',cardType:'Creature',subtype:'Avatar',affinity:'azul',difficulty:8,cost:5,pips:{U:3},artId:'queen_drowned',artUrl:'',artTransform:{x:50,y:35,scale:1},rules:'Al materializarse, roba dos cartas y luego descarta una.',flavor:'La corona sobrevivió porque nadie recordó enterrarla.',force:5,resistance:5,setCode:'SZA',cardNumber:'036',glyph:'♛'
};

const fields=['id','name','cardType','subtype','difficulty','cost','affinity','glyph','rules','flavor','force','resistance','setCode','cardNumber','artUrl'];
const pipIds={U:'pipU',R:'pipR',G:'pipG',W:'pipW',B:'pipB'};
function num(id,fallback=0){const n=Number($(id).value);return Number.isFinite(n)?n:fallback;}
function maybeNum(id){const raw=$(id).value.trim();if(raw==='')return null;const n=Number(raw);return Number.isFinite(n)?n:null;}

function readForm(){const pips={};for(const[k,id]of Object.entries(pipIds)){const n=Math.max(0,Math.trunc(num(id,0)));if(n)pips[k]=n;}return{id:$('id').value.trim(),name:$('name').value,template:'standard',cardType:$('cardType').value,subtype:$('subtype').value,affinity:$('affinity').value,difficulty:num('difficulty',0),cost:num('cost',0),pips,artId:$('id').value.trim(),artUrl:$('artUrl').value.trim(),artTransform:{x:num('artX',50),y:num('artY',50),scale:num('artScale',1)},rules:$('rules').value,flavor:$('flavor').value,force:maybeNum('force'),resistance:maybeNum('resistance'),setCode:$('setCode').value.trim(),cardNumber:$('cardNumber').value.trim(),glyph:$('glyph').value||'✦'};}

function writeForm(input){const c=SizaCardSchema.normalizeCard(input);$('id').value=c.id;$('name').value=c.name;$('cardType').value=c.cardType;$('subtype').value=c.subtype;$('difficulty').value=c.difficulty;$('cost').value=c.cost;$('affinity').value=['azul','rojo','multi','land'].includes(c.affinity)?c.affinity:'multi';$('glyph').value=c.glyph;$('rules').value=c.rules;$('flavor').value=c.flavor;$('force').value=c.power??'';$('resistance').value=c.toughness??'';$('setCode').value=c.setCode;$('cardNumber').value=c.cardNumber;$('artUrl').value=c.artUrl;for(const[k,id]of Object.entries(pipIds))$(id).value=c.pips?.[k]||0;$('artX').value=c.artTransform.x;$('artY').value=c.artTransform.y;$('artScale').value=c.artTransform.scale;syncArtNumeric();render();}
function syncArtNumeric(){$('artXValue').value=$('artX').value;$('artYValue').value=$('artY').value;$('artScaleValue').value=$('artScale').value;}
function syncArtRange(){$('artX').value=$('artXValue').value;$('artY').value=$('artYValue').value;$('artScale').value=$('artScaleValue').value;}

function render(){const validation=SizaCardSchema.validateCard(readForm()),card=validation.card;SizaCardRenderer.mount($('cardPreview'),card);$('jsonOutput').value=JSON.stringify(card,null,2);$('schemaVersion').textContent='Schema '+SizaCardSchema.VERSION;const box=$('validationStatus');if(validation.valid){box.className='status good';box.innerHTML=`<b>Schema válido</b>${validation.warnings.length?validation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'La carta puede pasar al handoff de prueba.'}`}else{box.className='status bad';box.innerHTML='<b>Schema inválido</b>'+validation.errors.map(escapeHtml).join('<br>')+(validation.warnings.length?'<br>'+validation.warnings.map(x=>'Advertencia: '+escapeHtml(x)).join('<br>'):'')}return validation;}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function saveDraft(){const validation=render();localStorage.setItem(DRAFT_KEY,JSON.stringify(validation.card));$('handoffStatus').textContent=`Borrador guardado localmente: ${validation.card.id}`;}
function resetDraft(){localStorage.removeItem(DRAFT_KEY);writeForm({...EXAMPLE,id:'card_'+Date.now(),name:'Carta sin nombre',rules:'',flavor:'',artUrl:'',force:2,resistance:2,cardNumber:'000'});}

function prepareHandoff(){const validation=render();if(!validation.valid){$('handoffStatus').textContent='Handoff bloqueado: corrige los errores de schema.';return;}localStorage.setItem(DRAFT_KEY,JSON.stringify(validation.card));const payload={action:'test-card',card:SizaCardSchema.cardToMobileShape(validation.card),generatorCard:validation.card,target:'collection',returnUrl,createdAt:new Date().toISOString()};localStorage.setItem(HANDOFF_KEY,JSON.stringify(payload));location.href=returnUrl;}

function loadInitial(){let draft=null;try{draft=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null')}catch(e){}if(draft)writeForm(draft);else writeForm({...EXAMPLE,id:requestedCardId||EXAMPLE.id});$('testMobile').textContent='Probar en Mobile Test';$('handoffStatus').textContent=requestedCardId?`Editando ${requestedCardId}. Probar en Mobile Test reemplaza sólo la versión temporal con este mismo ID.`:'Probar en Mobile Test guarda esta versión como carta temporal y abre Collection. El catálogo oficial no se modifica.';}

for(const id of fields)$(id).addEventListener('input',render);for(const id of Object.values(pipIds))$(id).addEventListener('input',render);for(const id of ['artX','artY','artScale'])$(id).addEventListener('input',()=>{syncArtNumeric();render();});for(const id of ['artXValue','artYValue','artScaleValue'])$(id).addEventListener('input',()=>{syncArtRange();render();});
$('saveDraft').addEventListener('click',saveDraft);$('loadExample').addEventListener('click',()=>writeForm(EXAMPLE));$('resetDraft').addEventListener('click',resetDraft);$('testMobile').addEventListener('click',prepareHandoff);loadInitial();
})();
