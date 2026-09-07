(function(){
'use strict';

var BUILD='1.0.0-direct-file-upload';
var SHOTS=['neutral','attack_physical','attack_special','charge','hit','defend','dodge','ko'];
var MAP={
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

function q(id){return document.getElementById(id)}
function text(v){return String(v==null?'':v).trim()}
function normalizeName(name){return text(name).toLowerCase().replace(/\.[^.]+$/,'').replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'')}
function dispatch(input){
  input.dispatchEvent(new Event('input',{bubbles:true}));
  input.dispatchEvent(new Event('change',{bubbles:true}));
}
function selectedRerender(){
  var item=document.querySelector('#itemList .item.sel[data-id]');
  if(item) window.setTimeout(function(){item.click()},20);
}
function status(msg,bad){
  var el=q('status');
  if(!el)return;
  el.textContent=msg;
  el.style.color=bad?'#ff7272':'#72d99d';
  clearTimeout(status.t);
  status.t=setTimeout(function(){el.textContent='Listo';el.style.color='';},2200);
}
function dataUrl(blob){
  return new Promise(function(resolve,reject){
    var r=new FileReader();r.onload=function(){resolve(String(r.result||''))};r.onerror=reject;r.readAsDataURL(blob);
  });
}
function loadImage(file){
  return new Promise(function(resolve,reject){
    var url=URL.createObjectURL(file),img=new Image();
    img.onload=function(){URL.revokeObjectURL(url);resolve(img)};
    img.onerror=function(e){URL.revokeObjectURL(url);reject(e)};
    img.src=url;
  });
}
async function imageAsset(file,targetId){
  if(!file||!/^image\//i.test(file.type||''))throw new Error('Seleccione una imagen PNG, JPG o WEBP.');
  var smallLimit=(targetId==='spriteIcon'?110000:targetId==='spritePortrait'?160000:180000);
  if(file.size<=smallLimit && /image\/(png|webp)/i.test(file.type||''))return dataUrl(file);
  var img=await loadImage(file);
  var max=/^pose_/.test(targetId)?1280:(targetId==='spriteIcon'?256:(targetId==='spritePortrait'?640:768));
  var ratio=Math.min(1,max/Math.max(img.naturalWidth||1,img.naturalHeight||1));
  var w=Math.max(1,Math.round((img.naturalWidth||1)*ratio));
  var h=Math.max(1,Math.round((img.naturalHeight||1)*ratio));
  var canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
  var ctx=canvas.getContext('2d',{alpha:true});ctx.imageSmoothingEnabled=false;ctx.drawImage(img,0,0,w,h);
  var quality=.94;
  var blob=await new Promise(function(resolve){canvas.toBlob(resolve,'image/webp',quality)});
  if(!blob) return dataUrl(file);
  var encoded=await dataUrl(blob);
  var targetChars=/^pose_/.test(targetId)?300000:180000;
  if(encoded.length>targetChars && Math.max(w,h)>640){
    var ratio2=640/Math.max(w,h),w2=Math.max(1,Math.round(w*ratio2)),h2=Math.max(1,Math.round(h*ratio2));
    var c2=document.createElement('canvas');c2.width=w2;c2.height=h2;
    var x2=c2.getContext('2d',{alpha:true});x2.imageSmoothingEnabled=false;x2.drawImage(canvas,0,0,w2,h2);
    var b2=await new Promise(function(resolve){c2.toBlob(resolve,'image/webp',.9)});
    if(b2) encoded=await dataUrl(b2);
  }
  return encoded;
}
async function rawSmallAsset(file,kind){
  if(!file)throw new Error('Seleccione un archivo.');
  var limit=1800000;
  if(file.size>limit)throw new Error((kind||'Archivo')+' demasiado grande para guardarlo dentro del proyecto. Use una URL o reduzca el archivo a menos de 1.8 MB.');
  return dataUrl(file);
}
async function assignFile(targetId,file,rerender){
  var input=q(targetId);
  if(!input)throw new Error('No encontré el campo '+targetId+'.');
  var value;
  if(/^image\//i.test(file.type||''))value=await imageAsset(file,targetId);
  else value=await rawSmallAsset(file,'Asset');
  input.value=value;
  input.dataset.uploadName=file.name||'';
  dispatch(input);
  if(rerender!==false)selectedRerender();
  return true;
}
function makeUploader(input,accept,label){
  if(!input||input.dataset.fileUploadReady==='1')return;
  input.dataset.fileUploadReady='1';
  var wrap=document.createElement('div');wrap.className='assetUploadActions';
  var pick=document.createElement('input');pick.type='file';pick.accept=accept;pick.hidden=true;
  var btn=document.createElement('button');btn.type='button';btn.className='btn assetUploadBtn';btn.textContent=label||'SUBIR ARCHIVO';
  var clear=document.createElement('button');clear.type='button';clear.className='btn assetClearBtn';clear.textContent='QUITAR';
  var badge=document.createElement('span');badge.className='assetUploadBadge';badge.textContent=input.value&&/^data:/i.test(input.value)?'ARCHIVO CARGADO':'URL / VACÍO';
  btn.onclick=function(){pick.click()};
  pick.onchange=async function(){
    var file=pick.files&&pick.files[0];if(!file)return;
    btn.disabled=true;btn.textContent='CARGANDO...';
    try{await assignFile(input.id,file,true);status(file.name+' cargado');}
    catch(err){status(err&&err.message?err.message:String(err),true)}
    finally{btn.disabled=false;btn.textContent=label||'SUBIR ARCHIVO';pick.value='';}
  };
  clear.onclick=function(){input.value='';dispatch(input);selectedRerender();status('Asset quitado')};
  wrap.appendChild(btn);wrap.appendChild(clear);wrap.appendChild(badge);wrap.appendChild(pick);
  var field=input.closest('.field');if(field)field.appendChild(wrap);else input.insertAdjacentElement('afterend',wrap);
}
function findCard(title){
  var hs=document.querySelectorAll('#editor .card h3');
  for(var i=0;i<hs.length;i++)if(text(hs[i].textContent).toLowerCase().indexOf(title.toLowerCase())>=0)return hs[i].closest('.card');
  return null;
}
function addPackUploader(){
  if(q('asset-pack-input'))return;
  var card=findCard('Battle sprites básicos')||findCard('Tsubasa Combat Sprite Pack');
  if(!card)return;
  var box=document.createElement('div');box.className='assetPackBox';
  box.innerHTML='<div><b>CARGAR SPRITE PACK COMPLETO</b><div class="tiny">Puede seleccionar varios archivos a la vez. Nombres reconocidos: battle_front, battle_back, icon, portrait, shot_neutral, shot_attack_physical, shot_attack_special, shot_charge, shot_hit, shot_defend, shot_dodge, shot_ko.</div></div><button type="button" class="btn primary" id="asset-pack-button">SELECCIONAR SPRITES</button><input id="asset-pack-input" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden>';
  card.insertBefore(box,card.children[1]||null);
  var picker=q('asset-pack-input'),button=q('asset-pack-button');
  button.onclick=function(){picker.click()};
  picker.onchange=async function(){
    var files=Array.prototype.slice.call(picker.files||[]);if(!files.length)return;
    button.disabled=true;button.textContent='CARGANDO '+files.length+'...';
    var loaded=0,ignored=[];
    try{
      for(var i=0;i<files.length;i++){
        var file=files[i],key=normalizeName(file.name),target=MAP[key];
        if(!target){ignored.push(file.name);continue}
        if(!q(target)){ignored.push(file.name);continue}
        await assignFile(target,file,false);loaded++;
      }
      selectedRerender();
      status(loaded+' sprites cargados'+(ignored.length?' · '+ignored.length+' sin nombre reconocido':''),ignored.length&&loaded===0);
    }catch(err){status(err&&err.message?err.message:String(err),true)}
    finally{button.disabled=false;button.textContent='SELECCIONAR SPRITES';picker.value='';}
  };
}
function addDropZones(){
  document.querySelectorAll('#editor .preview').forEach(function(zone){
    if(zone.dataset.dropReady==='1')return;zone.dataset.dropReady='1';
    zone.title='También puede arrastrar una imagen aquí';
    zone.addEventListener('dragover',function(ev){ev.preventDefault();zone.classList.add('assetDrag')});
    zone.addEventListener('dragleave',function(){zone.classList.remove('assetDrag')});
    zone.addEventListener('drop',async function(ev){
      ev.preventDefault();zone.classList.remove('assetDrag');var file=ev.dataTransfer&&ev.dataTransfer.files&&ev.dataTransfer.files[0];if(!file)return;
      var target='';
      if(zone.id&&zone.id.indexOf('preview_')===0)target='pose_'+zone.id.substring(8)+'_image';
      if(!target){
        var card=findCard('Battle sprites básicos');
        if(card){var previews=card.querySelectorAll('.preview');target=previews[0]===zone?'spriteFront':previews[1]===zone?'spriteBack':'';}
      }
      if(!target)return;
      try{await assignFile(target,file,true);status(file.name+' cargado')}
      catch(err){status(err&&err.message?err.message:String(err),true)}
    });
  });
}
function enhanceFakemon(){
  makeUploader(q('spriteFront'),'image/png,image/jpeg,image/webp','SUBIR FRONT');
  makeUploader(q('spriteBack'),'image/png,image/jpeg,image/webp','SUBIR BACK');
  makeUploader(q('spriteIcon'),'image/png,image/jpeg,image/webp','SUBIR ICON');
  makeUploader(q('spritePortrait'),'image/png,image/jpeg,image/webp','SUBIR PORTRAIT');
  SHOTS.forEach(function(k){
    makeUploader(q('pose_'+k+'_image'),'image/png,image/jpeg,image/webp','SUBIR IMAGEN');
    makeUploader(q('pose_'+k+'_video'),'video/mp4,video/webm','SUBIR VIDEO');
  });
  addPackUploader();addDropZones();
}
function enhanceSkill(){
  makeUploader(q('effectAsset'),'image/png,image/jpeg,image/webp,video/mp4,video/webm','SUBIR FX');
  makeUploader(q('impactAsset'),'image/png,image/jpeg,image/webp,video/mp4,video/webm','SUBIR IMPACTO');
  makeUploader(q('soundAsset'),'audio/mpeg,audio/ogg,audio/wav','SUBIR SONIDO');
  makeUploader(q('cinematicSrc'),'image/png,image/jpeg,image/webp,video/mp4,video/webm','SUBIR CINEMÁTICA');
}
function injectStyle(){
  if(q('asset-upload-style'))return;
  var s=document.createElement('style');s.id='asset-upload-style';s.textContent='\
.assetUploadActions{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-top:5px}.assetUploadBtn,.assetClearBtn{padding:5px 7px!important;font-size:10px!important}.assetUploadBadge{font:800 9px/1 Consolas,monospace;color:#72d99d;border:1px solid #35505b;border-radius:999px;padding:4px 6px}.assetPackBox{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0 14px;padding:11px;border:1px solid #67aae0;border-radius:8px;background:#0d1c27}.assetPackBox b{display:block;color:#edf3fa;font-size:11px;letter-spacing:.05em}.assetPackBox .tiny{margin-top:4px;max-width:720px}.preview.assetDrag{outline:3px dashed #67aae0;outline-offset:-5px;background:#112936!important}';
  document.head.appendChild(s);
}
function enhance(){injectStyle();enhanceFakemon();enhanceSkill()}
function init(){
  injectStyle();enhance();
  var editor=q('editor');
  if(editor)new MutationObserver(function(){window.setTimeout(enhance,0)}).observe(editor,{childList:true,subtree:true});
}
window.PokerolAssetUploadPatch=Object.freeze({BUILD:BUILD,enhance:enhance});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
