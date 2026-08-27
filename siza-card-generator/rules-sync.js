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
function emitRulesInput(){rulesField.dispatchEvent(new Event('input',{bubbles:true}));}
function syncRules(){
 const effects=readEffects();
 if(effects.length){
  const generated=rulesCore.rulesText(effects);
  lastGenerated=generated;
  rulesField.dataset.rulesMode='effects';
  rulesField.readOnly=true;
  if(rulesLabel)rulesLabel.textContent='Reglas · automáticas desde efectos';
  if(rulesField.value!==generated){rulesField.value=generated;emitRulesInput();}
  return;
 }
 const wasAuto=rulesField.dataset.rulesMode==='effects';
 rulesField.readOnly=false;
 delete rulesField.dataset.rulesMode;
 if(rulesLabel)rulesLabel.textContent='Reglas';
 if(wasAuto&&rulesField.value===lastGenerated){rulesField.value='';emitRulesInput();}
 lastGenerated='';
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
window.SizaRulesSync=Object.freeze({refresh:syncRules});
})();

(function(){
 const script=document.createElement('script');
 script.src='./deck-generator.js';
 document.body.appendChild(script);
})();
