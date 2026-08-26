(function(){
'use strict';

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
