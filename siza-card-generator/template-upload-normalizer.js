(function(){
'use strict';

const BAD_TEMPLATE_IDS=new Set([
 'standard_white','standard_blue','standard_black','standard_red','standard_green','standard_colorless','standard_multicolor'
]);

function cleanCard(card){
 if(!card||typeof card!=='object'||!BAD_TEMPLATE_IDS.has(String(card.template||'')))return false;
 card.template='standard';
 card.templateParts={};
 card.frameUrl='';
 card.frameAssetKey='';
 return true;
}
function cleanupInjectedTemplates(){
 let changed=false;
 try{
  const key='siza_card_generator_templates_v2';
  const raw=JSON.parse(localStorage.getItem(key)||'{}');
  if(raw&&typeof raw==='object'&&!Array.isArray(raw)){
   for(const id of BAD_TEMPLATE_IDS){
    const entry=raw[id];
    if(entry&&entry.systemTemplateVersion){delete raw[id];changed=true;}
   }
   if(changed)localStorage.setItem(key,JSON.stringify(raw));
  }
 }catch(e){}
 for(const key of ['siza_card_generator_draft_v1','siza_card_generator_handoff_v1']){
  try{
   const value=JSON.parse(localStorage.getItem(key)||'null');
   if(cleanCard(value)){localStorage.setItem(key,JSON.stringify(value));changed=true;}
  }catch(e){}
 }
 try{
  const key='siza_card_generator_library_v2';
  const value=JSON.parse(localStorage.getItem(key)||'{}');
  if(Array.isArray(value)){
   let localChanged=false;
   for(const card of value)localChanged=cleanCard(card)||localChanged;
   if(localChanged){localStorage.setItem(key,JSON.stringify(value));changed=true;}
  }else if(value&&typeof value==='object'){
   let localChanged=false;
   for(const card of Object.values(value))localChanged=cleanCard(card)||localChanged;
   if(localChanged){localStorage.setItem(key,JSON.stringify(value));changed=true;}
  }
 }catch(e){}
 return changed;
}
if(cleanupInjectedTemplates()){
 location.reload();
 return;
}

const WIDTH=1500;
const HEIGHT=2100;
const input=document.getElementById('templatePartFile');
if(!input)return;

input.accept='image/*';
let replaying=false;

function builderStatus(message){
 const box=document.getElementById('templateBuilderStatus');
 if(box)box.innerHTML='<strong>Imagen</strong> · '+message;
}

async function imageBitmapFromFile(file){
 if(window.createImageBitmap)return createImageBitmap(file);
 return new Promise((resolve,reject)=>{
  const url=URL.createObjectURL(file),img=new Image();
  img.onload=()=>{URL.revokeObjectURL(url);resolve(img)};
  img.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('image-load-failed'))};
  img.src=url;
 });
}

function canvasBlob(canvas){
 return new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
}

async function normalizeTemplateImage(file){
 if(!file||!String(file.type||'').startsWith('image/'))throw new Error('El archivo seleccionado no es una imagen.');
 const source=await imageBitmapFromFile(file);
 const sourceWidth=source.width||source.naturalWidth||0;
 const sourceHeight=source.height||source.naturalHeight||0;
 if(!sourceWidth||!sourceHeight)throw new Error('No se pudo leer el tamaño de la imagen.');

 if(sourceWidth===WIDTH&&sourceHeight===HEIGHT&&(file.type==='image/png'||file.type==='image/webp')){
  source.close?.();
  return file;
 }

 const canvas=document.createElement('canvas');
 canvas.width=WIDTH;
 canvas.height=HEIGHT;
 const ctx=canvas.getContext('2d',{alpha:true});
 if(!ctx)throw new Error('El navegador no pudo preparar el canvas del template.');
 ctx.clearRect(0,0,WIDTH,HEIGHT);
 ctx.drawImage(source,0,0,WIDTH,HEIGHT);
 source.close?.();
 const blob=await canvasBlob(canvas);
 if(!blob)throw new Error('No se pudo convertir la imagen al canvas del template.');
 const base=String(file.name||'template-piece').replace(/\.[^.]+$/,'')||'template-piece';
 return new File([blob],base+'.png',{type:'image/png',lastModified:Date.now()});
}

input.addEventListener('change',async event=>{
 if(replaying)return;
 const file=input.files?.[0];
 if(!file)return;
 event.preventDefault();
 event.stopImmediatePropagation();
 builderStatus('procesando '+String(file.name||'imagen')+'…');
 try{
  const normalized=await normalizeTemplateImage(file);
  const transfer=new DataTransfer();
  transfer.items.add(normalized);
  input.files=transfer.files;
  replaying=true;
  input.dispatchEvent(new Event('change',{bubbles:true}));
  replaying=false;
 }catch(error){
  replaying=false;
  input.value='';
  builderStatus(error?.message||'No se pudo cargar la imagen.');
 }
},true);
})();
