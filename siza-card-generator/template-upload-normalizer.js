(function(){
'use strict';

const TEMPLATE_LIBRARY_KEY='siza_card_generator_templates_v2';
const SYSTEM_TEMPLATE_VERSION=2;
const FRAME_BASE='../siza-core/assets/frames/standard/frame_standard_base.svg?v=094b0ee6';
const SYSTEM_TEMPLATES=[
 {id:'standard_white',name:'Standard · Blanco',key:'white',accent:'#d8c99b',accent2:'#fff4c9',dark:'#514a3a',paper:'#f1e7cf'},
 {id:'standard_blue',name:'Standard · Azul',key:'blue',accent:'#2f9fd9',accent2:'#8bd9ff',dark:'#0b3858',paper:'#e3edf1'},
 {id:'standard_black',name:'Standard · Negro',key:'black',accent:'#705a82',accent2:'#b89dcc',dark:'#17131d',paper:'#ddd4de'},
 {id:'standard_red',name:'Standard · Rojo',key:'red',accent:'#cf4b3a',accent2:'#f58a66',dark:'#581714',paper:'#ead8ca'},
 {id:'standard_green',name:'Standard · Verde',key:'green',accent:'#4b9d62',accent2:'#93d78f',dark:'#173d27',paper:'#dce8cf'},
 {id:'standard_colorless',name:'Standard · Incoloro',key:'colorless',accent:'#9caab2',accent2:'#edf2f4',dark:'#3e494f',paper:'#e4e5e1'},
 {id:'standard_multicolor',name:'Standard · Multicolor',key:'multicolor',accent:'#c6a84e',accent2:'#79bddd',dark:'#293143',paper:'#ede1ca',multicolor:true}
];

function escXml(value){return String(value).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[m]));}
function svgUrl(svg){return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);}
function defs(spec){
 const theme=spec.multicolor
  ?'<linearGradient id="theme" x1="0" x2="1"><stop offset="0" stop-color="#d9b44a"/><stop offset=".22" stop-color="#d65a4b"/><stop offset=".45" stop-color="#4da76d"/><stop offset=".68" stop-color="#419fd4"/><stop offset=".86" stop-color="#8c67b6"/><stop offset="1" stop-color="#d9b44a"/></linearGradient>'
  :`<linearGradient id="theme" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${escXml(spec.accent2)}"/><stop offset=".34" stop-color="${escXml(spec.accent)}"/><stop offset="1" stop-color="${escXml(spec.dark)}"/></linearGradient>`;
 return `<defs>${theme}<linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff0a9"/><stop offset=".22" stop-color="#c99b42"/><stop offset=".55" stop-color="#6f491d"/><stop offset=".82" stop-color="#d6ad58"/><stop offset="1" stop-color="#fff0a9"/></linearGradient><linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#fff8e7"/><stop offset=".5" stop-color="${escXml(spec.paper)}"/><stop offset="1" stop-color="#cdbd99"/></linearGradient><filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="9" stdDeviation="10" flood-color="#000" flood-opacity=".55"/></filter><filter id="glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="28"/></filter></defs>`;
}
function svg(spec,body){return `<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="2100" viewBox="0 0 1500 2100">${defs(spec)}${body}</svg>`;}
function ringRect(x,y,w,h,rx,fill='none',stroke='url(#gold)',sw=10,extra=''){return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;}
function diamond(x,y,size){const h=size/2;return `<path d="M ${x} ${y-h} L ${x+h} ${y} L ${x} ${y+h} L ${x-h} ${y} Z" fill="url(#theme)" stroke="url(#gold)" stroke-width="8"/>`;}
function filigreePath(spec){
 const stroke=spec.multicolor?'url(#theme)':escXml(spec.accent);
 return `<g fill="none" stroke="${stroke}" stroke-width="11" stroke-linecap="round" opacity=".72"><path d="M90 260 C150 175 205 185 255 115 C205 235 180 310 165 410 C142 335 120 305 90 260Z"/><path d="M1410 260 C1350 175 1295 185 1245 115 C1295 235 1320 310 1335 410 C1358 335 1380 305 1410 260Z"/><path d="M105 1760 C170 1835 210 1905 275 1980 C190 1940 135 1910 88 1840"/><path d="M1395 1760 C1330 1835 1290 1905 1225 1980 C1310 1940 1365 1910 1412 1840"/></g><g fill="none" stroke="url(#gold)" stroke-width="5" opacity=".9"><path d="M83 270 C160 225 205 190 260 115"/><path d="M1417 270 C1340 225 1295 190 1240 115"/><path d="M96 1840 C170 1885 220 1930 278 1990"/><path d="M1404 1840 C1330 1885 1280 1930 1222 1990"/></g>`;
}
function partSvg(spec,slot){
 switch(slot){
  case'affinity_overlay':return svg(spec,`<g opacity=".16" filter="url(#glow)" fill="url(#theme)"><ellipse cx="750" cy="610" rx="590" ry="510"/><ellipse cx="750" cy="1570" rx="520" ry="370"/></g><g opacity=".22">${filigreePath(spec)}</g>`);
  case'crystal_rail':return svg(spec,`${ringRect(91,303,185,842,92,'rgba(4,16,24,.76)','url(#gold)',9,'filter="url(#shadow)"')}<rect x="111" y="324" width="145" height="800" rx="72" fill="none" stroke="url(#theme)" stroke-width="7" opacity=".9"/>${diamond(184,333,40)}${diamond(184,1114,36)}`);
  case'title_plate':return svg(spec,`${ringRect(238,92,982,196,98,'url(#paper)','url(#gold)',12,'filter="url(#shadow)"')}<rect x="258" y="112" width="942" height="156" rx="78" fill="none" stroke="url(#theme)" stroke-width="8" opacity=".82"/>${diamond(252,190,46)}${diamond(1206,190,46)}`);
  case'difficulty_badge':return svg(spec,`<g filter="url(#shadow)"><circle cx="1337" cy="187" r="121" fill="#07141d" stroke="url(#gold)" stroke-width="13"/><circle cx="1337" cy="187" r="101" fill="url(#theme)" stroke="#122634" stroke-width="10"/><circle cx="1337" cy="187" r="84" fill="#071722" fill-opacity=".42" stroke="#fff" stroke-opacity=".2" stroke-width="4"/>${diamond(1337,83,40)}</g>`);
  case'art_frame':return svg(spec,`${ringRect(228,298,1210,872,30,'none','url(#gold)',11,'filter="url(#shadow)"')}<rect x="245" y="315" width="1176" height="838" rx="20" fill="none" stroke="url(#theme)" stroke-width="7" opacity=".85"/>${diamond(245,315,34)}${diamond(1421,315,34)}${diamond(245,1153,34)}${diamond(1421,1153,34)}`);
  case'type_bar':return svg(spec,`${ringRect(216,1158,1222,171,85,'#071722','url(#gold)',11,'filter="url(#shadow)"')}<rect x="235" y="1177" width="1184" height="133" rx="66" fill="url(#theme)" fill-opacity=".72" stroke="#fff" stroke-opacity=".16" stroke-width="4"/>${diamond(233,1244,40)}${diamond(1421,1244,40)}`);
  case'rules_panel':return svg(spec,`${ringRect(178,1320,1144,536,56,'url(#paper)','url(#gold)',12,'filter="url(#shadow)"')}<rect x="198" y="1340" width="1104" height="496" rx="44" fill="none" stroke="url(#theme)" stroke-width="7" opacity=".72"/><path d="M220 1375 H340 M1280 1375 H1160 M220 1800 H340 M1280 1800 H1160" stroke="url(#gold)" stroke-width="7" stroke-linecap="round"/>`);
  case'stat_left':return svg(spec,`<g filter="url(#shadow)"><circle cx="169" cy="1920" r="137" fill="#071722" stroke="url(#gold)" stroke-width="13"/><circle cx="169" cy="1920" r="115" fill="url(#theme)" fill-opacity=".78" stroke="#123348" stroke-width="8"/><circle cx="169" cy="1920" r="94" fill="#0c3650" fill-opacity=".64" stroke="#fff" stroke-opacity=".16" stroke-width="4"/></g>`);
  case'stat_right':return svg(spec,`<g filter="url(#shadow)"><circle cx="1331" cy="1920" r="137" fill="#071722" stroke="url(#gold)" stroke-width="13"/><circle cx="1331" cy="1920" r="115" fill="url(#theme)" fill-opacity=".78" stroke="#482018" stroke-width="8"/><circle cx="1331" cy="1920" r="94" fill="#571c18" fill-opacity=".58" stroke="#fff" stroke-opacity=".16" stroke-width="4"/></g>`);
  case'footer':return svg(spec,`${ringRect(500,1918,500,116,58,'#071722','url(#gold)',10,'filter="url(#shadow)"')}<rect x="518" y="1936" width="464" height="80" rx="40" fill="url(#theme)" fill-opacity=".48" stroke="#fff" stroke-opacity=".14" stroke-width="3"/>`);
  case'ornament_overlay':return svg(spec,`${filigreePath(spec)}<g opacity=".72">${diamond(750,58,46)}${diamond(750,2040,44)}</g>`);
  default:return'';
 }
}
function systemParts(spec){
 const slots=['affinity_overlay','crystal_rail','title_plate','difficulty_badge','art_frame','type_bar','rules_panel','stat_left','stat_right','footer','ornament_overlay'];
 const parts={frame_base:{assetKey:'',url:FRAME_BASE,fileName:'frame_standard_base.svg'}};
 for(const slot of slots)parts[slot]={assetKey:'',url:svgUrl(partSvg(spec,slot)),fileName:`standard_${spec.key}_${slot}.svg`};
 return parts;
}
function seedSystemTemplates(){
 let library={};
 try{const parsed=JSON.parse(localStorage.getItem(TEMPLATE_LIBRARY_KEY)||'{}');library=parsed&&typeof parsed==='object'&&!Array.isArray(parsed)?parsed:{}}catch(e){library={}}
 let changed=false;
 const now=new Date().toISOString();
 for(const spec of SYSTEM_TEMPLATES){
  const existing=library[spec.id];
  if(existing&&Number(existing.systemTemplateVersion)>=SYSTEM_TEMPLATE_VERSION)continue;
  library[spec.id]={
   id:spec.id,
   name:spec.name,
   version:2,
   systemTemplateVersion:SYSTEM_TEMPLATE_VERSION,
   parts:systemParts(spec),
   createdAt:existing?.createdAt||now,
   updatedAt:now
  };
  changed=true;
 }
 if(!changed)return false;
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
