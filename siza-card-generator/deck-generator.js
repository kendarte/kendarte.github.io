(function(){
'use strict';

const DECK_LIBRARY_KEY='siza_card_generator_decks_v1';
const CARD_LIBRARY_KEY='siza_card_generator_library_v2';
const $=id=>document.getElementById(id);
const clone=value=>JSON.parse(JSON.stringify(value));
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));

let deckLibrary=loadDeckLibrary();
let cardLibrary=loadCardLibrary();
let currentDeck=newBlankDeck();
let dirty=false;

function loadDeckLibrary(){
 try{
  const raw=JSON.parse(localStorage.getItem(DECK_LIBRARY_KEY)||'{}');
  if(Array.isArray(raw))return Object.fromEntries(raw.filter(deck=>deck?.id).map(deck=>[deck.id,normalizeDeck(deck)]));
  if(raw&&typeof raw==='object')return Object.fromEntries(Object.values(raw).filter(deck=>deck?.id).map(deck=>[deck.id,normalizeDeck(deck)]));
 }catch(e){}
 return{};
}

function loadCardLibrary(){
 try{
  const raw=JSON.parse(localStorage.getItem(CARD_LIBRARY_KEY)||'{}');
  if(Array.isArray(raw))return Object.fromEntries(raw.filter(card=>card?.id).map(card=>[card.id,card]));
  return raw&&typeof raw==='object'?raw:{};
 }catch(e){return{};}
}

function saveDeckLibrary(){localStorage.setItem(DECK_LIBRARY_KEY,JSON.stringify(deckLibrary));}
function makeDeckId(){return`deck_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,7)}`;}
function newBlankDeck(){const now=new Date().toISOString();return{id:makeDeckId(),name:'',cards:{},createdAt:now,updatedAt:now};}
function normalizeDeck(input={}){
 const cards={};
 const source=input.cards&&typeof input.cards==='object'?input.cards:{};
 for(const[id,qtyRaw]of Object.entries(source)){
  const qty=Math.max(0,Math.trunc(Number(qtyRaw)||0));
  if(qty)cards[String(id)]=qty;
 }
 return{id:String(input.id||makeDeckId()),name:String(input.name||''),cards,createdAt:input.createdAt||new Date().toISOString(),updatedAt:input.updatedAt||new Date().toISOString()};
}
function deckTotal(deck=currentDeck){return Object.values(deck.cards||{}).reduce((sum,qty)=>sum+(Number(qty)||0),0);}
function deckUnique(deck=currentDeck){return Object.values(deck.cards||{}).filter(qty=>Number(qty)>0).length;}
function cardLabel(card,id){return card?.name||id;}
function cardMeta(card){
 const bits=[];
 if(card?.cardType)bits.push(card.cardType);
 if(card?.subtype)bits.push(card.subtype);
 if(Number.isFinite(Number(card?.difficulty)))bits.push(`Manafestación ${Number(card.difficulty)}`);
 return bits.join(' · ');
}
function markDirty(){dirty=true;renderStatus();renderPreview();}
function setStatus(message,type=''){
 const box=$('deckGeneratorStatus');if(!box)return;
 box.dataset.message=message||'';
 box.dataset.type=type||'';
 renderStatus();
}
function renderStatus(){
 const box=$('deckGeneratorStatus');if(!box)return;
 const explicit=box.dataset.message||'';
 if(explicit){box.className=`templateStatus deckGeneratorStatus ${box.dataset.type||''}`;box.innerHTML=explicit;return;}
 const saved=!!deckLibrary[currentDeck.id];
 const state=dirty?'Cambios sin guardar':saved?'Guardado':'Nuevo deck';
 box.className='templateStatus deckGeneratorStatus';
 box.innerHTML=`<strong>${escapeHtml(state)}</strong> · ${deckTotal()} carta(s), ${deckUnique()} carta(s) distinta(s).`;
}

function injectStyles(){
 if($('sizaDeckGeneratorStyles'))return;
 const style=document.createElement('style');
 style.id='sizaDeckGeneratorStyles';
 style.textContent=`
 .deckIntro{padding:12px 13px;border:1px solid #29465a;border-radius:11px;background:#071722;color:#8ca4b4;font-size:10px;line-height:1.55;margin-bottom:12px}.deckIntro b{color:#e8d49e}.deckLibraryBar{display:grid;grid-template-columns:1fr auto auto;gap:7px;align-items:end;padding:11px;border:1px solid #29465a;border-radius:11px;background:#071722}.deckLibraryBar .field{min-width:0}.deckNameRow{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end;margin-top:12px}.deckList{display:grid;gap:7px;max-height:340px;overflow:auto;padding-right:2px}.deckCardRow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:center;padding:9px 10px;border:1px solid #29465a;border-radius:9px;background:#071722}.deckCardCopy{min-width:0}.deckCardCopy b{display:block;color:#e7d29a;font:500 12px Georgia,serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.deckCardCopy span{display:block;margin-top:3px;color:#718b9d;font-size:8px;line-height:1.35}.deckCardActions{display:flex;align-items:center;gap:5px}.deckQty{min-width:26px;text-align:center;color:#e6d49e;font-size:10px;font-weight:900}.deckEmpty{padding:16px;border:1px dashed #36556a;border-radius:9px;color:#718b9d;font-size:9px;line-height:1.5;text-align:center}.deckSearch{margin-bottom:8px}.deckGeneratorStatus{margin-top:10px}.deckPreviewStage{width:min(500px,100%);display:grid;gap:8px}.deckPreviewHero{padding:16px;border:1px solid #39576c;border-radius:14px;background:linear-gradient(145deg,#0b2130,#030a0f);box-shadow:0 18px 48px rgba(0,0,0,.28)}.deckPreviewHero h3{margin:0;font:500 22px Georgia,serif;color:#ecd9a6}.deckPreviewHero p{margin:5px 0 0;color:#7893a4;font-size:9px}.deckPreviewCards{display:grid;gap:6px}.deckPreviewCard{display:grid;grid-template-columns:auto minmax(0,1fr);gap:9px;align-items:center;padding:8px 10px;border:1px solid #29465a;border-radius:9px;background:#071722}.deckPreviewCount{min-width:28px;height:28px;border:1px solid #80653b;border-radius:999px;display:grid;place-items:center;color:#efd89d;background:#171a1d;font-size:9px;font-weight:900}.deckPreviewCard b{display:block;color:#dce8ee;font-size:10px}.deckPreviewCard span{display:block;margin-top:2px;color:#718b9d;font-size:8px}.deckMissing b{color:#d49a9a}.deckSectionHead{display:flex;justify-content:space-between;gap:10px;align-items:end}.deckSectionHead h2{margin-bottom:8px}.deckSectionHead span{color:#718b9d;font-size:8px;margin-bottom:9px}
 @media(max-width:900px){.deckLibraryBar{grid-template-columns:1fr 1fr}.deckLibraryBar .field{grid-column:1/-1}.deckNameRow{grid-template-columns:1fr}}
 `;
 document.head.appendChild(style);
}

function injectUi(){
 if($('tabDeckBtn'))return;
 const tabs=document.querySelector('.toolTabs');
 const templateButton=$('tabTemplateBtn');
 if(!tabs||!templateButton)return;
 tabs.style.gridTemplateColumns='repeat(3,minmax(0,1fr))';
 const button=document.createElement('button');
 button.className='toolTab';
 button.type='button';
 button.id='tabDeckBtn';
 button.dataset.tab='deck';
 button.textContent='DECK GENERATOR';
 templateButton.insertAdjacentElement('afterend',button);

 const templatePanel=$('templateTabPanel');
 const deckPanel=document.createElement('section');
 deckPanel.className='tabPanel';
 deckPanel.id='deckTabPanel';
 deckPanel.hidden=true;
 deckPanel.innerHTML=`
  <div class="deckIntro"><b>Deck Generator.</b> Arme y almacene decks usando únicamente las cartas guardadas en Card Creator. Cada deck conserva su nombre y las cantidades de cada carta en este navegador.</div>
  <div class="deckLibraryBar">
   <div class="field"><label for="savedDecks">Decks guardados</label><select id="savedDecks"><option value="">— Nuevo deck —</option></select></div>
   <button class="btn ghost" type="button" id="newDeck">Nuevo</button>
   <button class="btn danger" type="button" id="deleteDeck">Eliminar</button>
  </div>
  <div class="deckNameRow">
   <div class="field"><label for="deckName">Nombre del deck</label><input id="deckName" placeholder="Ej. Darkhaven Control"></div>
   <button class="btn primary" type="button" id="saveDeck">Guardar deck</button>
  </div>
  <section class="section">
   <div class="deckSectionHead"><h2>Cartas hechas</h2><span id="deckPoolCount">0 cartas</span></div>
   <div class="field deckSearch"><label for="deckCardSearch">Buscar</label><input id="deckCardSearch" placeholder="Nombre, ID o tipo"></div>
   <div class="deckList" id="deckCardPool"></div>
  </section>
  <section class="section">
   <div class="deckSectionHead"><h2>Contenido del deck</h2><span id="deckContentsCount">0 cartas</span></div>
   <div class="deckList" id="deckContents"></div>
  </section>
  <div class="templateStatus deckGeneratorStatus" id="deckGeneratorStatus"></div>
 `;
 templatePanel.insertAdjacentElement('afterend',deckPanel);

 const templatePreview=$('templatePreviewPanel');
 const deckPreview=document.createElement('section');
 deckPreview.className='previewPanel';
 deckPreview.id='deckPreviewPanel';
 deckPreview.hidden=true;
 deckPreview.innerHTML=`
  <div class="previewHead"><div><div class="eyebrow">DECK_GENERATOR_V1</div><h2>Deck actual</h2></div><span id="deckPreviewStats">0 cartas</span></div>
  <div class="deckPreviewStage">
   <div class="deckPreviewHero"><h3 id="deckPreviewName">Deck sin nombre</h3><p id="deckPreviewMeta">0 cartas · 0 distintas</p></div>
   <div class="deckPreviewCards" id="deckPreviewCards"></div>
  </div>
 `;
 templatePreview.insertAdjacentElement('afterend',deckPreview);
}

function refreshDeckSelect(selectedId=currentDeck.id){
 const select=$('savedDecks');if(!select)return;
 const decks=Object.values(deckLibrary).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),'es'));
 select.innerHTML='<option value="">— Nuevo deck —</option>'+decks.map(deck=>`<option value="${escapeHtml(deck.id)}">${escapeHtml(deck.name||deck.id)} · ${deckTotal(deck)} cartas</option>`).join('');
 select.value=selectedId&&deckLibrary[selectedId]?selectedId:'';
}

function renderCardPool(){
 cardLibrary=loadCardLibrary();
 const list=$('deckCardPool');if(!list)return;
 const query=String($('deckCardSearch')?.value||'').trim().toLocaleLowerCase('es');
 const cards=Object.values(cardLibrary).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id),'es')).filter(card=>{
  if(!query)return true;
  return`${card.name||''} ${card.id||''} ${card.cardType||''} ${card.subtype||''}`.toLocaleLowerCase('es').includes(query);
 });
 $('deckPoolCount').textContent=`${Object.keys(cardLibrary).length} carta(s)`;
 if(!cards.length){list.innerHTML=`<div class="deckEmpty">${Object.keys(cardLibrary).length?'No hay cartas que coincidan con la búsqueda.':'No hay cartas guardadas todavía. Guarde cartas en Card Creator y aparecerán aquí.'}</div>`;return;}
 list.innerHTML=cards.map(card=>`<div class="deckCardRow"><div class="deckCardCopy"><b>${escapeHtml(cardLabel(card,card.id))}</b><span>${escapeHtml(card.id)}${cardMeta(card)?` · ${escapeHtml(cardMeta(card))}`:''}</span></div><div class="deckCardActions"><span class="deckQty">${Number(currentDeck.cards?.[card.id]||0)}</span><button class="btn ghost" type="button" data-deck-add="${escapeHtml(card.id)}">Añadir</button></div></div>`).join('');
}

function renderDeckContents(){
 const list=$('deckContents');if(!list)return;
 const entries=Object.entries(currentDeck.cards||{}).filter(([,qty])=>Number(qty)>0).sort(([a],[b])=>String(cardLabel(cardLibrary[a],a)).localeCompare(String(cardLabel(cardLibrary[b],b)),'es'));
 $('deckContentsCount').textContent=`${deckTotal()} carta(s)`;
 if(!entries.length){list.innerHTML='<div class="deckEmpty">El deck está vacío. Añada cartas desde “Cartas hechas”.</div>';return;}
 list.innerHTML=entries.map(([id,qty])=>{
  const card=cardLibrary[id];
  return`<div class="deckCardRow"><div class="deckCardCopy"><b>${escapeHtml(cardLabel(card,id))}</b><span>${escapeHtml(id)}${cardMeta(card)?` · ${escapeHtml(cardMeta(card))}`:''}${card?'':' · carta no disponible en la biblioteca actual'}</span></div><div class="deckCardActions"><button class="btn ghost" type="button" data-deck-minus="${escapeHtml(id)}">−</button><span class="deckQty">${qty}</span><button class="btn ghost" type="button" data-deck-plus="${escapeHtml(id)}">+</button><button class="btn danger" type="button" data-deck-remove="${escapeHtml(id)}">Quitar</button></div></div>`;
 }).join('');
}

function renderPreview(){
 const name=$('deckPreviewName'),meta=$('deckPreviewMeta'),stats=$('deckPreviewStats'),list=$('deckPreviewCards');
 if(!name||!meta||!stats||!list)return;
 const total=deckTotal(),unique=deckUnique();
 name.textContent=currentDeck.name.trim()||'Deck sin nombre';
 meta.textContent=`${total} carta(s) · ${unique} distinta(s)${dirty?' · cambios sin guardar':''}`;
 stats.textContent=`${total} cartas`;
 const entries=Object.entries(currentDeck.cards||{}).filter(([,qty])=>Number(qty)>0).sort(([a],[b])=>String(cardLabel(cardLibrary[a],a)).localeCompare(String(cardLabel(cardLibrary[b],b)),'es'));
 if(!entries.length){list.innerHTML='<div class="deckEmpty">Sin cartas todavía.</div>';return;}
 list.innerHTML=entries.map(([id,qty])=>{const card=cardLibrary[id];return`<div class="deckPreviewCard ${card?'':'deckMissing'}"><div class="deckPreviewCount">×${qty}</div><div><b>${escapeHtml(cardLabel(card,id))}</b><span>${escapeHtml(cardMeta(card)||id)}${card?'':' · no disponible'}</span></div></div>`}).join('');
}

function renderAll(){
 refreshDeckSelect();
 if($('deckName'))$('deckName').value=currentDeck.name||'';
 renderCardPool();
 renderDeckContents();
 renderPreview();
 renderStatus();
}

function clearExplicitStatus(){const box=$('deckGeneratorStatus');if(box){box.dataset.message='';box.dataset.type='';}}
function startNewDeck(){currentDeck=newBlankDeck();dirty=false;clearExplicitStatus();renderAll();$('deckName')?.focus();}
function loadDeck(id){
 const deck=deckLibrary[id];
 if(!deck){startNewDeck();return;}
 currentDeck=clone(deck);dirty=false;clearExplicitStatus();renderAll();
}
function saveCurrentDeck(){
 const name=String($('deckName')?.value||'').trim();
 if(!name){setStatus('<strong>Error</strong> · escriba un nombre para el deck.','bad');$('deckName')?.focus();return null;}
 currentDeck.name=name;
 currentDeck.updatedAt=new Date().toISOString();
 deckLibrary[currentDeck.id]=clone(currentDeck);
 saveDeckLibrary();dirty=false;clearExplicitStatus();renderAll();
 setStatus(`<strong>${escapeHtml(name)}</strong> · deck guardado con ${deckTotal()} carta(s).`,'good');
 return deckLibrary[currentDeck.id];
}
function deleteCurrentDeck(){
 const saved=deckLibrary[currentDeck.id];
 if(saved){delete deckLibrary[currentDeck.id];saveDeckLibrary();}
 startNewDeck();
 if(saved)setStatus(`<strong>${escapeHtml(saved.name||saved.id)}</strong> · deck eliminado.`);
}
function changeQuantity(id,delta){
 if(!id)return;
 const next=Math.max(0,Math.trunc(Number(currentDeck.cards?.[id]||0)+delta));
 if(next)currentDeck.cards[id]=next;else delete currentDeck.cards[id];
 currentDeck.updatedAt=new Date().toISOString();clearExplicitStatus();markDirty();renderCardPool();renderDeckContents();renderPreview();renderStatus();
}
function removeCard(id){if(!id)return;delete currentDeck.cards[id];currentDeck.updatedAt=new Date().toISOString();clearExplicitStatus();markDirty();renderCardPool();renderDeckContents();renderPreview();renderStatus();}

function showDeck(){
 cardLibrary=loadCardLibrary();
 $('cardTabPanel').hidden=true;
 $('templateTabPanel').hidden=true;
 $('deckTabPanel').hidden=false;
 $('cardPreviewPanel').hidden=true;
 $('templatePreviewPanel').hidden=true;
 $('deckPreviewPanel').hidden=false;
 $('tabCardBtn').classList.remove('active');
 $('tabTemplateBtn').classList.remove('active');
 $('tabDeckBtn').classList.add('active');
 renderAll();
}
function leaveDeck(){
 if($('deckTabPanel'))$('deckTabPanel').hidden=true;
 if($('deckPreviewPanel'))$('deckPreviewPanel').hidden=true;
 $('tabDeckBtn')?.classList.remove('active');
}

function bindEvents(){
 $('tabDeckBtn').addEventListener('click',showDeck);
 $('tabCardBtn').addEventListener('click',leaveDeck);
 $('tabTemplateBtn').addEventListener('click',leaveDeck);
 $('savedDecks').addEventListener('change',event=>loadDeck(event.target.value));
 $('newDeck').addEventListener('click',startNewDeck);
 $('deleteDeck').addEventListener('click',deleteCurrentDeck);
 $('saveDeck').addEventListener('click',saveCurrentDeck);
 $('deckName').addEventListener('input',event=>{currentDeck.name=event.target.value;currentDeck.updatedAt=new Date().toISOString();clearExplicitStatus();markDirty();});
 $('deckCardSearch').addEventListener('input',renderCardPool);
 $('deckCardPool').addEventListener('click',event=>{const add=event.target.closest('[data-deck-add]');if(add)changeQuantity(add.dataset.deckAdd,1);});
 $('deckContents').addEventListener('click',event=>{
  const plus=event.target.closest('[data-deck-plus]'),minus=event.target.closest('[data-deck-minus]'),remove=event.target.closest('[data-deck-remove]');
  if(plus)changeQuantity(plus.dataset.deckPlus,1);else if(minus)changeQuantity(minus.dataset.deckMinus,-1);else if(remove)removeCard(remove.dataset.deckRemove);
 });
}

function init(){
 injectStyles();injectUi();bindEvents();renderAll();
 window.SizaDeckGenerator=Object.freeze({show:showDeck,newDeck:startNewDeck,loadDeck,saveDeck:saveCurrentDeck,getCurrentDeck:()=>clone(currentDeck),getDecks:()=>clone(deckLibrary)});
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
