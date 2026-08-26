(function(){
'use strict';

const TEMPLATE_LIBRARY_KEY='siza_card_generator_templates_v2';
const SYSTEM_TEMPLATE_VERSION=1;
const FRAME_BASE='../siza-core/assets/frames/standard/frame_standard_base.svg?v=094b0ee6';
const SYSTEM_TEMPLATES=[
 {id:'standard_white',name:'Standard · Blanco',overlay:'../siza-core/assets/templates/standard/affinity_white.svg?v=1'},
 {id:'standard_blue',name:'Standard · Azul',overlay:'../siza-core/assets/templates/standard/affinity_blue.svg?v=1'},
 {id:'standard_black',name:'Standard · Negro',overlay:'../siza-core/assets/templates/standard/affinity_black.svg?v=1'},
 {id:'standard_red',name:'Standard · Rojo',overlay:'../siza-core/assets/templates/standard/affinity_red.svg?v=1'},
 {id:'standard_green',name:'Standard · Verde',overlay:'../siza-core/assets/templates/standard/affinity_green.svg?v=1'},
 {id:'standard_colorless',name:'Standard · Incoloro',overlay:'../siza-core/assets/templates/standard/affinity_colorless.svg?v=1'},
 {id:'standard_multicolor',name:'Standard · Multicolor',overlay:'../siza-core/assets/templates/standard/affinity_multicolor.svg?v=1'}
];

function seedSystemTemplates(){
 let library={};
 try{const parsed=JSON.parse(localStorage.getItem(TEMPLATE_LIBRARY_KEY)||'{}');library=parsed&&typeof parsed==='object'&&!Array.isArray(parsed)?parsed:{}}catch(e){library={}}
 let added=0;
 const now=new Date().toISOString();
 for(const spec of SYSTEM_TEMPLATES){
  if(library[spec.id])continue;
  library[spec.id]={
   id:spec.id,
   name:spec.name,
   version:2,
   systemTemplateVersion:SYSTEM_TEMPLATE_VERSION,
   parts:{
    frame_base:{assetKey:'',url:FRAME_BASE,fileName:'frame_standard_base.svg'},
    affinity_overlay:{assetKey:'',url:spec.overlay,fileName:spec.overlay.split('/').pop().split('?')[0]}
   },
   createdAt:now,
   updatedAt:now
  };
  added++;
 }
 if(!added)return false;
 try{localStorage.setItem(TEMPLATE_LIBRARY_KEY,JSON.stringify(library));return true}catch(e){return false}
}

if(seedSystemTemplates()){
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
