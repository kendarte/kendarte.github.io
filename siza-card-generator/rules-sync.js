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
    editable presentation layer so authored card copy is not replaced by the
    fallback renderer. */
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
 function loadScript(src,onload){
  const script=document.createElement('script');
  script.src=src;
  script.onload=onload;
  document.body.appendChild(script);
 }
 loadScript('./airborne-cattle-seed.js?v=airborne-cattle-v01',()=>{
  loadScript('./starter-decks.js?v=airborne-cattle-v01',()=>{
   loadScript('./deck-generator.js?v=airborne-cattle-v01');
  });
 });
})();
