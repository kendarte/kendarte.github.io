(function(){
'use strict';

const effectsField=document.getElementById('effectsJson');
const rulesField=document.getElementById('rules');
const rulesCore=window.SizaCardRulesText;
if(!effectsField||!rulesField||!rulesCore)return;

const rulesLabel=document.querySelector('label[for="rules"]');
let lastGenerated='';

function readEffects(){
 try{const parsed=JSON.parse(effectsField.value||'[]');return Array.isArray(parsed)?parsed:[];}catch(e){return[];}
}
function syncRules(){
 const effects=readEffects();
 /* Structured effects are the executable contract. Printed rules remain an
    editable presentation layer so English vertical-slice copy is not replaced
    by the Spanish fallback renderer. */
 rulesField.readOnly=false;
 delete rulesField.dataset.rulesMode;
 lastGenerated=effects.length?rulesCore.rulesText(effects):'';
 if(rulesLabel)rulesLabel.textContent=effects.length?'Rules · structured effects attached':'Rules';
}

effectsField.addEventListener('input',syncRules);
const previous=Object.getOwnPropertyDescriptor(effectsField,'value');
if(previous?.get&&previous?.set){
 Object.defineProperty(effectsField,'value',{
  configurable:true,
  get(){return previous.get.call(this);},
  set(value){previous.set.call(this,value);queueMicrotask(syncRules);}
 });
}
queueMicrotask(syncRules);
window.SizaRulesSync=Object.freeze({refresh:syncRules,getGeneratedFallback:()=>lastGenerated});
})();

(function(){
 const starter=document.createElement('script');
 starter.src='./starter-decks.js?v=dragon-thunder-effects-v02';
 starter.onload=()=>{
  const script=document.createElement('script');
  script.src='./deck-generator.js?v=dragon-thunder-effects-v02';
  document.body.appendChild(script);
 };
 document.body.appendChild(starter);
})();
