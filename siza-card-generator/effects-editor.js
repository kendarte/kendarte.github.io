(function(){
'use strict';

const textarea=document.getElementById('effectsJson');
const core=window.SizaCardEffects;
if(!textarea||!core)return;

const section=textarea.closest('.section');
const originalField=textarea.closest('.field');
let effects=[];
let internalWrite=false;

const style=document.createElement('style');
style.textContent=`
.effectsBuilderV1{display:grid;gap:10px;margin-top:10px}
.effectsToolbarV1{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:end;padding:10px;border:1px solid #29465a;border-radius:10px;background:#071722}
.effectsToolbarV1 label,.effectFieldV1 label{display:block;margin-bottom:5px;font-size:8px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#9db2c0}
.effectsToolbarV1 select,.effectFieldV1 select,.effectFieldV1 input{width:100%;border:1px solid #31516a;border-radius:7px;background:#06131d;color:#e5eef3;padding:8px 9px;outline:none}
.effectListV1{display:grid;gap:9px}
.effectCardV1{border:1px solid #31516a;border-radius:11px;background:#081923;padding:10px;display:grid;gap:9px}
.effectCardTopV1{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) auto;gap:7px;align-items:end}
.effectFieldsV1{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
.effectDescriptionV1{font-size:9px;line-height:1.4;color:#7f99aa}
.effectActionsV1{display:flex;gap:5px;align-items:center}
.effectMiniBtnV1{border:1px solid #466a81;border-radius:7px;background:#0c2b3d;color:#dceaf2;min-width:29px;height:31px;padding:0 7px;font-size:10px;font-weight:900;cursor:pointer}
.effectMiniBtnV1.danger{border-color:#70454a;background:#32171b;color:#f0c7c7}
.effectBooleanV1{min-height:35px;border:1px solid #31516a;border-radius:7px;background:#06131d;display:flex;align-items:center;gap:7px;padding:7px 9px;color:#dbe7ee;font-size:9px}
.effectBooleanV1 input{width:auto;margin:0}
.effectEmptyV1{padding:14px;border:1px dashed #29465a;border-radius:9px;color:#7892a3;text-align:center;font-size:9px}
.effectsStatusV1{font-size:9px;line-height:1.4;color:#83a0b1;padding:0 2px}
.effectsStatusV1.bad{color:#e0a6a6}
.effectsAdvancedV1{margin-top:8px;border-top:1px solid #20384a;padding-top:8px}
.effectsAdvancedV1 summary{cursor:pointer;color:#718b9b;font-size:8px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}
.effectsAdvancedV1 .field{margin-top:8px}
.effectsAdvancedV1 textarea{min-height:130px!important;color:#7794a5!important}
@media(max-width:700px){.effectCardTopV1{grid-template-columns:1fr}.effectFieldsV1{grid-template-columns:1fr}.effectsToolbarV1{grid-template-columns:1fr}.effectActionsV1{justify-content:flex-start}}
`;
document.head.appendChild(style);

if(section){
 const note=section.querySelector('.sectionNote');
 if(note)note.innerHTML='Agregue efectos con selectores. Cada tipo define sus propios parámetros y el editor se amplía automáticamente desde el catálogo de <b>card-effects.js</b>.';
}

const builder=document.createElement('div');
builder.className='effectsBuilderV1';
const toolbar=document.createElement('div');
toolbar.className='effectsToolbarV1';
const addField=document.createElement('div');
const addLabel=document.createElement('label');
addLabel.textContent='Nuevo efecto';
const addSelect=document.createElement('select');
for(const type of core.TYPES){
 const option=document.createElement('option');
 option.value=type;
 option.textContent=core.editorDefinition(type)?.label||type;
 addSelect.appendChild(option);
}
addField.append(addLabel,addSelect);
const addButton=document.createElement('button');
addButton.type='button';
addButton.className='btn primary';
addButton.textContent='Agregar efecto';
toolbar.append(addField,addButton);
const list=document.createElement('div');
list.className='effectListV1';
const status=document.createElement('div');
status.className='effectsStatusV1';
builder.append(toolbar,list,status);

const advanced=document.createElement('details');
advanced.className='effectsAdvancedV1';
const summary=document.createElement('summary');
summary.textContent='JSON generado · avanzado';
advanced.appendChild(summary);
if(originalField){
 originalField.parentNode.insertBefore(builder,originalField);
 advanced.appendChild(originalField);
 builder.parentNode.insertBefore(advanced,builder.nextSibling);
 const label=originalField.querySelector('label');
 if(label)label.textContent='Salida JSON de efectos';
}
textarea.readOnly=true;

function parseTextarea(){
 const raw=textarea.value.trim();
 if(!raw)return[];
 try{
  const parsed=JSON.parse(raw);
  return Array.isArray(parsed)?core.normalizeEffects(parsed):[];
 }catch(e){return[];}
}

function setTextareaFromEffects(dispatch=true){
 internalWrite=true;
 textarea.value=JSON.stringify(effects,null,2);
 internalWrite=false;
 if(dispatch)textarea.dispatchEvent(new Event('input',{bubbles:true}));
}

const valueDescriptor=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value');
if(valueDescriptor?.get&&valueDescriptor?.set){
 Object.defineProperty(textarea,'value',{
  configurable:true,
  get(){return valueDescriptor.get.call(this);},
  set(value){
   valueDescriptor.set.call(this,value);
   if(!internalWrite)queueMicrotask(syncFromTextarea);
  }
 });
}

function syncFromTextarea(){
 effects=parseTextarea();
 renderEffects();
}

function optionList(values,labels,current){
 return values.map(value=>`<option value="${value}"${value===current?' selected':''}>${labels?.[value]||value}</option>`).join('');
}

function createField(effect,index,field){
 const wrap=document.createElement('div');
 wrap.className='effectFieldV1';
 const label=document.createElement('label');
 label.textContent=field.label||field.key;
 wrap.appendChild(label);
 let input;
 if(field.kind==='target'){
  input=document.createElement('select');
  input.innerHTML=optionList(core.TARGETS,core.TARGET_LABELS,effect[field.key]);
 }else if(field.kind==='color'){
  input=document.createElement('select');
  input.innerHTML=optionList(core.COLORS,core.COLOR_LABELS,effect[field.key]);
 }else if(field.kind==='boolean'){
  const boolean=document.createElement('label');
  boolean.className='effectBooleanV1';
  input=document.createElement('input');input.type='checkbox';input.checked=!!effect[field.key];
  const text=document.createElement('span');text.textContent=effect[field.key]?'Sí':'No';
  boolean.append(input,text);wrap.replaceChildren(label,boolean);
  input.addEventListener('change',()=>{text.textContent=input.checked?'Sí':'No';updateField(index,field.key,input.checked);});
  return wrap;
 }else{
  input=document.createElement('input');input.type='number';
  if(field.min!=null)input.min=String(field.min);if(field.max!=null)input.max=String(field.max);if(field.step!=null)input.step=String(field.step);
  input.value=effect[field.key]??field.min??0;
 }
 input.dataset.effectField=field.key;
 input.addEventListener('change',()=>{
  const value=field.kind==='number'?Number(input.value):input.value;
  updateField(index,field.key,value);
 });
 wrap.appendChild(input);
 return wrap;
}

function updateField(index,key,value){
 effects[index]=core.normalizeEffect({...effects[index],[key]:value});
 setTextareaFromEffects();
 renderEffects();
}

function replaceType(index,type){
 const def=core.editorDefinition(type);
 const oldEvent=effects[index]?.event;
 effects[index]=core.newEffect(type,def?.lockedEvent?null:oldEvent);
 setTextareaFromEffects();
 renderEffects();
}

function replaceEvent(index,event){
 effects[index]=core.normalizeEffect({...effects[index],event});
 setTextareaFromEffects();
 renderEffects();
}

function moveEffect(index,delta){
 const next=index+delta;if(next<0||next>=effects.length)return;
 const item=effects[index];effects[index]=effects[next];effects[next]=item;
 setTextareaFromEffects();renderEffects();
}

function removeEffect(index){effects.splice(index,1);setTextareaFromEffects();renderEffects();}

function renderEffects(){
 list.innerHTML='';
 if(!effects.length){
  const empty=document.createElement('div');empty.className='effectEmptyV1';empty.textContent='Esta carta no tiene efectos estructurados.';list.appendChild(empty);
 }
 effects.forEach((effect,index)=>{
  const def=core.editorDefinition(effect.type)||{label:effect.type,description:'Efecto registrado sin formulario específico.',fields:[]};
  const card=document.createElement('div');card.className='effectCardV1';
  const top=document.createElement('div');top.className='effectCardTopV1';

  const typeField=document.createElement('div');typeField.className='effectFieldV1';
  const typeLabel=document.createElement('label');typeLabel.textContent=`Efecto ${index+1}`;
  const typeSelect=document.createElement('select');
  typeSelect.innerHTML=core.TYPES.map(type=>`<option value="${type}"${type===effect.type?' selected':''}>${core.editorDefinition(type)?.label||type}</option>`).join('');
  typeSelect.addEventListener('change',()=>replaceType(index,typeSelect.value));
  typeField.append(typeLabel,typeSelect);

  const eventField=document.createElement('div');eventField.className='effectFieldV1';
  const eventLabel=document.createElement('label');eventLabel.textContent='Cuándo ocurre';
  const eventSelect=document.createElement('select');
  eventSelect.innerHTML=optionList(core.EVENTS,core.EVENT_LABELS,effect.event);
  eventSelect.disabled=!!def.lockedEvent;
  eventSelect.addEventListener('change',()=>replaceEvent(index,eventSelect.value));
  eventField.append(eventLabel,eventSelect);

  const actions=document.createElement('div');actions.className='effectActionsV1';
  const up=document.createElement('button');up.type='button';up.className='effectMiniBtnV1';up.textContent='↑';up.title='Mover arriba';up.disabled=index===0;up.addEventListener('click',()=>moveEffect(index,-1));
  const down=document.createElement('button');down.type='button';down.className='effectMiniBtnV1';down.textContent='↓';down.title='Mover abajo';down.disabled=index===effects.length-1;down.addEventListener('click',()=>moveEffect(index,1));
  const remove=document.createElement('button');remove.type='button';remove.className='effectMiniBtnV1 danger';remove.textContent='×';remove.title='Eliminar efecto';remove.addEventListener('click',()=>removeEffect(index));
  actions.append(up,down,remove);
  top.append(typeField,eventField,actions);
  card.appendChild(top);

  if(def.description){const description=document.createElement('div');description.className='effectDescriptionV1';description.textContent=def.description;card.appendChild(description);}
  if(def.fields?.length){const fields=document.createElement('div');fields.className='effectFieldsV1';for(const field of def.fields)fields.appendChild(createField(effect,index,field));card.appendChild(fields);}
  list.appendChild(card);
 });
 const validation=core.validateEffects(effects);
 if(validation.valid){status.className='effectsStatusV1';status.textContent=`${effects.length} efecto(s) · catálogo ${core.TYPES.length} tipos · contrato v${core.VERSION}`;}
 else{status.className='effectsStatusV1 bad';status.textContent=validation.errors.join(' | ');}
}

addButton.addEventListener('click',()=>{
 effects.push(core.newEffect(addSelect.value));
 setTextareaFromEffects();
 renderEffects();
});

syncFromTextarea();
window.SizaEffectsEditor=Object.freeze({
 getEffects:()=>core.normalizeEffects(effects),
 setEffects:value=>{effects=core.normalizeEffects(value||[]);setTextareaFromEffects();renderEffects();},
 refresh:syncFromTextarea
});
})();
