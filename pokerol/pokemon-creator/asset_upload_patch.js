(function(){
'use strict';

var BUILD='2.1.0-persistent-fakemon-assets';
var STORE='pokerol_fakemon_skill_generator_v2';
var BACKEND='https://pokerol-game-production.up.railway.app';
var API=BACKEND+'/pokerol-api/assets/pokemon';
var SHOTS=['neutral','attack_physical','attack_special','charge','hit','defend','dodge','ko'];
var SLOT_BY_TARGET={
  spriteFront:{slot:'battle_front',kind:'image'},
  spriteBack:{slot:'battle_back',kind:'image'},
  spriteIcon:{slot:'icon',kind:'image'},
  spritePortrait:{slot:'portrait',kind:'image'}
};
SHOTS.forEach(function(k){
  SLOT_BY_TARGET['pose_'+k+'_image']={slot:'shot_'+k,kind:'image'};
  SLOT_BY_TARGET['pose_'+k+'_video']={slot:'shot_'+k,kind:'video'};
});
var PACK_MAP={
  battle_front:'spriteFront',front:'spriteFront',
  battle_back:'spriteBack',back:'spriteBack',
  icon:'spriteIcon',portrait:'spritePortrait',
  shot_neutral:'pose_neutral_image',neutral:'pose_neutral_image',
  shot_attack_physical:'pose_attack_physical_image',attack_physical:'pose_attack_physical_image',
  shot_attack_special:'pose_attack_special_image',attack_special:'pose_attack_special_image',
  shot_charge:'pose_charge_image',charge:'pose_charge_image',
  shot_hit:'pose_hit_image',hit:'pose_hit_image',
  shot_defend:'pose_defend_image',defend:'pose_defend_image',
  shot_dodge:'pose_dodge_image',dodge:'pose_dodge_image',
  shot_ko:'pose_ko_image',ko:'pose_ko_image'
};
var IMAGE_EXT=/\.(png|jpe?g|webp)$/i;
var VIDEO_EXT=/\.(mp4|webm)$/i;
var MAX_BYTES=20*1024*1024;

function q(id){return document.getElementById(id)}
function text(v){return String(v==null?'':v).trim()}
function normalizeName(name){return text(name).toLowerCase().replace(/\.[^.]+$/,'').replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'')}
function dispatch(input){
  input.dispatchEvent(new Event('input',{bubbles:true}));
  input.dispatchEvent(new Event('change',{bubbles:true}));
}
function speciesId(){
  var input=q('speciesId'),value=text(input&&input.value);
  if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$/.test(value))throw new Error('Species ID inválido. Use letras, números, punto, guion o _.');
  return value;
}
function selectedRerender(){
  var item=document.querySelector('#itemList .item.sel[data-id]');
  if(item)window.setTimeout(function(){item.click()},20);
}
function pageStatus(msg,bad){
  var el=q('status');if(!el)return;
  el.textContent=msg;el.style.color=bad?'#ff7272':'#72d99d';
  clearTimeout(pageStatus.t);pageStatus.t=setTimeout(function(){el.textContent='Listo';el.style.color='';},2600);
}
function assetUrl(src){
  src=text(src);
  return src.indexOf('/pokerol-assets/')===0?BACKEND+src:src;
}
function isManaged(src){
  src=text(src);
  return src.indexOf('/pokerol-assets/pokemon/')===0||src.indexOf(BACKEND+'/pokerol-assets/pokemon/')===0;
}
function validateFile(file,kind){
  if(!file)throw new Error('Seleccione un archivo.');
  if(file.size<=0||file.size>MAX_BYTES)throw new Error('El archivo está vacío o supera 20 MB.');
  var name=text(file.name);
  if(kind==='video'){
    if(!VIDEO_EXT.test(name))throw new Error('Video permitido: MP4 o WEBM.');
  }else if(!IMAGE_EXT.test(name))throw new Error('Imagen permitida: PNG, JPG/JPEG o WEBP.');
}
async function apiJson(url,options){
  var response=await fetch(url,options||{}),data={};
  try{data=await response.json()}catch(_e){}
  if(!response.ok||!data.ok)throw new Error(data.error||('Error HTTP '+response.status));
  return data;
}
async function uploadPersistent(targetId,file,onProgress){
  var meta=SLOT_BY_TARGET[targetId];
  if(!meta)throw new Error('Slot visual no reconocido.');
  validateFile(file,meta.kind);
  if(onProgress)onProgress('SUBIENDO');
  var form=new FormData();
  form.append('species_id',speciesId());
  form.append('slot',meta.slot);
  form.append('media_kind',meta.kind);
  form.append('file',file,file.name);
  var data=await apiJson(API+'/upload',{method:'POST',body:form,mode:'cors'});
  if(!data.src||data.src.indexOf('/pokerol-assets/pokemon/')!==0)throw new Error('El servidor no devolvió una referencia persistente válida.');
  if(onProgress)onProgress('GUARDADO');
  return data.src;
}
async function clearPersistent(targetId,current,onProgress){
  var meta=SLOT_BY_TARGET[targetId];
  if(!meta)return;
  if(onProgress)onProgress('ELIMINANDO');
  if(isManaged(current)){
    await apiJson(API+'/clear',{method:'POST',mode:'cors',headers:{'Content-Type':'application/json'},body:JSON.stringify({species_id:speciesId(),slot:meta.slot,media_kind:meta.kind})});
  }
  if(onProgress)onProgress('VACÍO');
}
function setPreview(box,src,kind,objectUrl){
  if(!box)return;
  box.innerHTML='';
  if(!src){box.innerHTML='<span>SIN ASSET</span>';return}
  var el=document.createElement(kind==='video'?'video':'img');
  el.src=objectUrl||assetUrl(src);
  if(kind==='video'){el.muted=true;el.loop=true;el.autoplay=true;el.playsInline=true;}
  box.appendChild(el);
}
function visualPackFor(p){
  var cv=p&&p.combat_visuals||{},battle=cv.battle||{},shots=cv.shots||{},pack={};
  function battleSlot(name,src){pack[name]={src:text(src),scale:Number(battle.scale||1.25),anchor_x:.5,anchor_y:1}}
  battleSlot('battle_front',battle.front||(p.sprite&&p.sprite.front));
  battleSlot('battle_back',battle.back||(p.sprite&&p.sprite.back));
  pack.icon={src:text(battle.icon||(p.sprite&&p.sprite.icon)),scale:1,anchor_x:.5,anchor_y:.5};
  pack.portrait={src:text(battle.portrait||(p.sprite&&p.sprite.portrait)),scale:1,anchor_x:.5,anchor_y:.5};
  SHOTS.forEach(function(k){
    var row=shots[k]||{};
    pack['shot_'+k]={src:text(row.image),video:text(row.video),scale:Number(row.scale||1),anchor_x:Number(row.anchor_x==null?50:row.anchor_x)/100,anchor_y:Number(row.anchor_y==null?100:row.anchor_y)/100};
  });
  return pack;
}
function syncVisualPacks(){
  try{
    var raw=localStorage.getItem(STORE);if(!raw)return null;
    var state=JSON.parse(raw);if(!state||!Array.isArray(state.pokemon))return state;
    state.pokemon.forEach(function(p){p.visual_pack=visualPackFor(p)});
    localStorage.setItem(STORE,JSON.stringify(state));
    return state;
  }catch(_err){return null}
}
async function assignFile(targetId,file,rerender,ui){
  var input=q(targetId);if(!input)throw new Error('No encontré el campo '+targetId+'.');
  var meta=SLOT_BY_TARGET[targetId];validateFile(file,meta.kind);
  var local=URL.createObjectURL(file);
  if(ui&&ui.preview)setPreview(ui.preview,'local',meta.kind,local);
  try{
    var src=await uploadPersistent(targetId,file,function(value){if(ui)ui.setState(value,false)});
    input.value=src;input.dataset.uploadName=file.name||'';dispatch(input);syncVisualPacks();
    if(ui){ui.setState('GUARDADO',false);setPreview(ui.preview,src,meta.kind);}
    pageStatus(file.name+' guardado en Railway');
    if(rerender!==false)selectedRerender();
    return src;
  }catch(err){
    if(ui)ui.setState('ERROR',true);
    throw err;
  }finally{URL.revokeObjectURL(local)}
}
function makeUploader(input,accept,label){
  if(!input||input.dataset.fileUploadReady==='1'||!SLOT_BY_TARGET[input.id])return;
  input.dataset.fileUploadReady='1';
  var meta=SLOT_BY_TARGET[input.id];
  var wrap=document.createElement('div');wrap.className='assetUploadActions';
  var pick=document.createElement('input');pick.type='file';pick.accept=accept;pick.hidden=true;
  var btn=document.createElement('button');btn.type='button';btn.className='btn assetUploadBtn';btn.textContent=label||'SUBIR ARCHIVO';
  var clear=document.createElement('button');clear.type='button';clear.className='btn assetClearBtn';clear.textContent='ELIMINAR / RESET';
  var badge=document.createElement('span');badge.className='assetUploadBadge';badge.textContent=input.value?'GUARDADO / URL':'VACÍO';
  var preview=document.createElement('div');preview.className='assetSlotPreview';setPreview(preview,input.value,meta.kind);
  function setState(value,bad){badge.textContent=value;badge.classList.toggle('assetError',!!bad)}
  var ui={preview:preview,setState:setState};
  btn.onclick=function(){pick.click()};
  pick.onchange=async function(){
    var file=pick.files&&pick.files[0];if(!file)return;
    btn.disabled=true;
    try{await assignFile(input.id,file,true,ui)}
    catch(err){pageStatus(err&&err.message?err.message:String(err),true)}
    finally{btn.disabled=false;pick.value='';}
  };
  clear.onclick=async function(){
    var current=input.value;btn.disabled=true;clear.disabled=true;
    try{
      await clearPersistent(input.id,current,setState);
      input.value='';dispatch(input);syncVisualPacks();setPreview(preview,'',meta.kind);setState('VACÍO',false);pageStatus('Asset eliminado / reseteado');selectedRerender();
    }catch(err){setState('ERROR',true);pageStatus(err&&err.message?err.message:String(err),true)}
    finally{btn.disabled=false;clear.disabled=false;}
  };
  wrap.appendChild(btn);wrap.appendChild(clear);wrap.appendChild(badge);wrap.appendChild(pick);wrap.appendChild(preview);
  var field=input.closest('.field');if(field)field.appendChild(wrap);else input.insertAdjacentElement('afterend',wrap);
}
function findCard(title){
  var hs=document.querySelectorAll('#editor .card h3');
  for(var i=0;i<hs.length;i++)if(text(hs[i].textContent).toLowerCase().indexOf(title.toLowerCase())>=0)return hs[i].closest('.card');
  return null;
}
function addPackUploader(){
  if(q('asset-pack-input'))return;
  var card=findCard('Battle sprites básicos')||findCard('Tsubasa Combat Sprite Pack');if(!card)return;
  var box=document.createElement('div');box.className='assetPackBox';
  box.innerHTML='<div><b>CARGAR SPRITE PACK</b><div class="tiny">Seleccione varias imágenes. Nombres: battle_front, battle_back, icon, portrait, shot_neutral, shot_attack_physical, shot_attack_special, shot_charge, shot_hit, shot_defend, shot_dodge, shot_ko.</div></div><button type="button" class="btn primary" id="asset-pack-button">SELECCIONAR SPRITES</button><input id="asset-pack-input" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden>';
  card.insertBefore(box,card.children[1]||null);
  var picker=q('asset-pack-input'),button=q('asset-pack-button');button.onclick=function(){picker.click()};
  picker.onchange=async function(){
    var files=Array.prototype.slice.call(picker.files||[]);if(!files.length)return;
    button.disabled=true;button.textContent='SUBIENDO '+files.length+'...';var loaded=0,ignored=[];
    try{
      for(var i=0;i<files.length;i++){
        var file=files[i],target=PACK_MAP[normalizeName(file.name)];
        if(!target||!q(target)){ignored.push(file.name);continue}
        await assignFile(target,file,false,null);loaded++;
      }
      syncVisualPacks();selectedRerender();pageStatus(loaded+' sprites guardados'+(ignored.length?' · '+ignored.length+' ignorados':''),loaded===0);
    }catch(err){pageStatus(err&&err.message?err.message:String(err),true)}
    finally{button.disabled=false;button.textContent='SELECCIONAR SPRITES';picker.value='';}
  };
}
function addDropZones(){
  document.querySelectorAll('#editor .preview').forEach(function(zone){
    if(zone.dataset.dropReady==='1')return;zone.dataset.dropReady='1';zone.title='Puede arrastrar una imagen aquí';
    zone.addEventListener('dragover',function(ev){ev.preventDefault();zone.classList.add('assetDrag')});
    zone.addEventListener('dragleave',function(){zone.classList.remove('assetDrag')});
    zone.addEventListener('drop',async function(ev){
      ev.preventDefault();zone.classList.remove('assetDrag');var file=ev.dataTransfer&&ev.dataTransfer.files&&ev.dataTransfer.files[0];if(!file)return;
      var target='';
      if(zone.id&&zone.id.indexOf('preview_')===0)target='pose_'+zone.id.substring(8)+'_image';
      if(!target){var card=findCard('Battle sprites básicos');if(card){var previews=card.querySelectorAll('.preview');target=previews[0]===zone?'spriteFront':previews[1]===zone?'spriteBack':'';}}
      if(!target)return;
      try{await assignFile(target,file,true,null)}catch(err){pageStatus(err&&err.message?err.message:String(err),true)}
    });
  });
}
function fixAssetPreviewSources(){
  document.querySelectorAll('#editor img[src],#editor video[src]').forEach(function(el){
    var raw=el.getAttribute('src')||'';
    if(raw.indexOf('/pokerol-assets/')===0)el.src=BACKEND+raw;
  });
}
function installPersistentExport(){
  var button=q('exportBtn');if(!button||button.dataset.persistentExport==='1')return;
  button.dataset.persistentExport='1';
  button.onclick=function(){
    try{
      var state=syncVisualPacks()||JSON.parse(localStorage.getItem(STORE)||'{}');
      var blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'}),u=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=u;a.download='pokerol-fakemon-skill-set-v2.json';a.click();setTimeout(function(){URL.revokeObjectURL(u)},1000);pageStatus('JSON exportado con referencias persistentes');
    }catch(err){pageStatus('No se pudo exportar: '+(err&&err.message?err.message:err),true)}
  };
}
function enhanceFakemon(){
  makeUploader(q('spriteFront'),'image/png,image/jpeg,image/webp','SUBIR IMAGEN');
  makeUploader(q('spriteBack'),'image/png,image/jpeg,image/webp','SUBIR IMAGEN');
  makeUploader(q('spriteIcon'),'image/png,image/jpeg,image/webp','SUBIR IMAGEN');
  makeUploader(q('spritePortrait'),'image/png,image/jpeg,image/webp','SUBIR IMAGEN');
  SHOTS.forEach(function(k){
    makeUploader(q('pose_'+k+'_image'),'image/png,image/jpeg,image/webp','SUBIR IMAGEN');
    makeUploader(q('pose_'+k+'_video'),'video/mp4,video/webm','SUBIR VIDEO');
  });
  addPackUploader();addDropZones();fixAssetPreviewSources();installPersistentExport();syncVisualPacks();
}
function injectStyle(){
  if(q('asset-upload-style'))return;
  var s=document.createElement('style');s.id='asset-upload-style';s.textContent='\
.assetUploadActions{display:grid;grid-template-columns:auto auto 1fr;gap:5px;align-items:center;margin-top:5px}.assetUploadBtn,.assetClearBtn{padding:5px 7px!important;font-size:10px!important;width:auto!important}.assetUploadBadge{font:800 9px/1 Consolas,monospace;color:#72d99d;border:1px solid #35505b;border-radius:999px;padding:4px 6px;justify-self:start}.assetUploadBadge.assetError{color:#ff7272;border-color:#763940}.assetSlotPreview{grid-column:1/-1;height:92px;display:grid;place-items:center;overflow:hidden;border:1px solid #273447;border-radius:6px;background:#070b10;color:#93a3b8;font:800 9px Consolas,monospace}.assetSlotPreview img,.assetSlotPreview video{max-width:100%;max-height:100%;object-fit:contain}.assetPackBox{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0 14px;padding:11px;border:1px solid #67aae0;border-radius:8px;background:#0d1c27}.assetPackBox b{display:block;color:#edf3fa;font-size:11px;letter-spacing:.05em}.assetPackBox .tiny{margin-top:4px;max-width:720px}.preview.assetDrag{outline:3px dashed #67aae0;outline-offset:-5px;background:#112936!important}';
  document.head.appendChild(s);
}
function enhance(){injectStyle();enhanceFakemon()}
function init(){
  enhance();var editor=q('editor');
  if(editor)new MutationObserver(function(){window.setTimeout(enhance,0)}).observe(editor,{childList:true,subtree:true});
}
window.PokerolAssetUploadPatch=Object.freeze({BUILD:BUILD,enhance:enhance,backend:BACKEND,syncVisualPacks:syncVisualPacks});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
