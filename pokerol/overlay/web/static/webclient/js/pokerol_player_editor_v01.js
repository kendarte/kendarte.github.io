(function(){
  'use strict';

  var BUILD='0.4.0-authoritative-player-save';
  var editing=false;
  var anchored=false;
  var drag=null;
  var resize=null;
  var current={x:11,y:94,scale:1};
  var emitterBound=false;
  var assetEmitterBound=false;
  var seq=0;
  var pendingSeq=0;
  var dirty=false;
  var lastRoomDbref=null;

  function byId(id){return document.getElementById(id)}
  function clamp(v,min,max){var n=Number(v);if(!Number.isFinite(n))n=min;return Math.max(min,Math.min(max,n))}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function encodePayload(data){var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
  function status(text,bad){var n=byId('pk-player-status');if(!n)return;n.textContent=text||'';n.classList.toggle('pkError',!!bad)}
  function sendCommand(command,payload){
    if(!window.Evennia||typeof Evennia.msg!=='function'){status('SIN CONEXIÓN',true);return false}
    try{Evennia.msg('text',[command+' '+encodePayload(payload)],{});return true}catch(e){status('NO SE PUDO ENVIAR',true);return false}
  }
  function desiredPayload(reset){
    seq+=1;pendingSeq=seq;dirty=true;
    return {anchored:!!anchored,x:current.x,y:current.y,scale:current.scale,reset:!!reset,seq:seq};
  }
  function saveState(reset){
    var payload=desiredPayload(reset);
    status('GUARDANDO…',false);
    if(!sendCommand('pokerol-editor-player-state',payload)){dirty=false;return false}
    return true;
  }
  function setAnchor(on){
    anchored=!!on;
    var checkbox=byId('pk-player-anchor');if(checkbox)checkbox.checked=anchored;
    apply();
    saveState(false);
  }

  function apply(){
    var avatar=byId('pk-player-avatar');if(!avatar)return;
    avatar.style.left=current.x+'%';
    avatar.style.bottom=current.y+'px';
    avatar.style.setProperty('--pk-player-edit-scale',String(current.scale));
    avatar.style.transform='translateX(-50%) scale('+current.scale+')';
    avatar.style.transformOrigin='bottom center';
    var x=byId('pk-player-x'),y=byId('pk-player-y'),s=byId('pk-player-scale'),a=byId('pk-player-anchor');
    if(x)x.value=current.x.toFixed(1);if(y)y.value=current.y.toFixed(0);if(s)s.value=current.scale.toFixed(2);if(a)a.checked=anchored;
  }
  function sameLayout(row){
    if(!row)return false;
    return Math.abs(Number(row.scene_x)-current.x)<0.05&&Math.abs(Number(row.scene_y)-current.y)<0.5&&Math.abs(Number(row.scene_scale)-current.scale)<0.005&&!!row.anchored===!!anchored;
  }
  function applyPacket(packet){
    var row=packet&&packet.player_editor||{};
    var roomDbref=packet&&packet.room_dbref!=null?Number(packet.room_dbref):null;
    var roomChanged=lastRoomDbref!=null&&roomDbref!=null&&roomDbref!==lastRoomDbref;
    if(roomDbref!=null)lastRoomDbref=roomDbref;

    if(editing||drag||resize)return false;
    if(dirty&&!sameLayout(row)){
      /* Ignore stale server snapshots until the save ACK arrives. */
      return false;
    }
    /* When ANCLAR is active, room changes must keep the player-global layout. */
    anchored=!!row.anchored;
    current={
      x:clamp(row.scene_x==null?11:row.scene_x,1,99),
      y:clamp(row.scene_y==null?94:row.scene_y,0,500),
      scale:clamp(row.scene_scale==null?1:row.scene_scale,.35,3)
    };
    apply();
    if(roomChanged&&anchored)status('ANCLADO · POSICIÓN GLOBAL',false);
    return true;
  }
  function setEditing(on){
    var wasEditing=editing;
    editing=!!on;
    var stage=byId('pk-stage'),avatar=byId('pk-player-avatar'),panel=byId('pk-player-panel'),btn=byId('pk-edit-player');
    if(stage)stage.classList.toggle('pkPlayerEditing',editing);
    if(avatar)avatar.classList.toggle('pkPlayerEditable',editing);
    if(panel)panel.hidden=!editing;
    if(btn)btn.classList.toggle('pkActive',editing);
    document.documentElement.dataset.pkPlayerEditing=editing?'1':'0';
    if(editing){ensureHandle();apply();status(anchored?'ANCLADO · EDITANDO':'EDITANDO ROOM',false)}
    else{
      drag=null;resize=null;
      if(wasEditing)saveState(false);
    }
  }
  function ensureHandle(){
    var avatar=byId('pk-player-avatar');if(!avatar||byId('pk-player-resize-handle'))return;
    var h=document.createElement('span');h.id='pk-player-resize-handle';h.className='pkPlayerResizeHandle';h.title='Arrastra para cambiar tamaño';avatar.appendChild(h)
  }
  function bindAvatar(){
    var avatar=byId('pk-player-avatar'),stage=byId('pk-stage');if(!avatar||!stage||avatar.dataset.pkPlayerEditBound==='1')return false;
    avatar.dataset.pkPlayerEditBound='1';ensureHandle();
    avatar.addEventListener('pointerdown',function(ev){
      if(!editing||ev.target===byId('pk-player-resize-handle'))return;
      ev.preventDefault();ev.stopPropagation();drag={id:ev.pointerId,rect:stage.getBoundingClientRect()};avatar.setPointerCapture&&avatar.setPointerCapture(ev.pointerId)
    },true);
    avatar.addEventListener('pointermove',function(ev){
      if(!editing||!drag||drag.id!==ev.pointerId)return;
      ev.preventDefault();ev.stopPropagation();
      var r=drag.rect;current.x=clamp(((ev.clientX-r.left)/r.width)*100,1,99);current.y=clamp(r.bottom-ev.clientY,0,Math.max(100,r.height-20));dirty=true;apply()
    },true);
    avatar.addEventListener('pointerup',function(ev){if(drag&&drag.id===ev.pointerId){ev.preventDefault();ev.stopPropagation();drag=null;saveState(false)}},true);
    avatar.addEventListener('pointercancel',function(ev){if(drag&&drag.id===ev.pointerId){drag=null;saveState(false)}},true);
    var h=byId('pk-player-resize-handle');if(h&&h.dataset.pkBound!=='1'){
      h.dataset.pkBound='1';
      h.addEventListener('pointerdown',function(ev){if(!editing)return;ev.preventDefault();ev.stopPropagation();resize={id:ev.pointerId,startY:ev.clientY,startScale:current.scale};h.setPointerCapture&&h.setPointerCapture(ev.pointerId)},true);
      h.addEventListener('pointermove',function(ev){if(!editing||!resize||resize.id!==ev.pointerId)return;ev.preventDefault();ev.stopPropagation();current.scale=clamp(resize.startScale+((resize.startY-ev.clientY)/120),.35,3);dirty=true;apply()},true);
      h.addEventListener('pointerup',function(ev){if(resize&&resize.id===ev.pointerId){ev.preventDefault();ev.stopPropagation();resize=null;saveState(false)}},true);
      h.addEventListener('pointercancel',function(ev){if(resize&&resize.id===ev.pointerId){resize=null;saveState(false)}},true);
    }
    return true;
  }
  function readFields(){
    var x=parseFloat(byId('pk-player-x')&&byId('pk-player-x').value),y=parseFloat(byId('pk-player-y')&&byId('pk-player-y').value),s=parseFloat(byId('pk-player-scale')&&byId('pk-player-scale').value);
    if(Number.isFinite(x))current.x=clamp(x,1,99);if(Number.isFinite(y))current.y=clamp(y,0,500);if(Number.isFinite(s))current.scale=clamp(s,.35,3)
  }
  function bindPanel(){
    var btn=byId('pk-edit-player'),close=byId('pk-player-close'),save=byId('pk-player-save'),reset=byId('pk-player-reset'),anchor=byId('pk-player-anchor');
    if(btn&&btn.dataset.pkBound!=='1'){btn.dataset.pkBound='1';btn.addEventListener('click',function(){setEditing(true)})}
    if(close&&close.dataset.pkBound!=='1'){close.dataset.pkBound='1';close.addEventListener('click',function(){setEditing(false)})}
    if(save&&save.dataset.pkBound!=='1'){save.dataset.pkBound='1';save.addEventListener('click',function(){readFields();apply();saveState(false)})}
    if(reset&&reset.dataset.pkBound!=='1'){reset.dataset.pkBound='1';reset.addEventListener('click',function(){current={x:11,y:94,scale:1};dirty=true;apply();saveState(true)})}
    if(anchor&&anchor.dataset.pkBound!=='1'){anchor.dataset.pkBound='1';anchor.addEventListener('change',function(){readFields();dirty=true;setAnchor(anchor.checked)})}
    ['pk-player-x','pk-player-y','pk-player-scale'].forEach(function(id){var n=byId(id);if(n&&n.dataset.pkBound!=='1'){n.dataset.pkBound='1';n.addEventListener('input',function(){readFields();dirty=true;apply()});n.addEventListener('change',function(){readFields();dirty=true;apply();saveState(false)})}});
  }
  function onSnapshot(args){applyPacket(packetFrom(args));return true}
  function onAssetResult(args){
    var p=packetFrom(args),st=String(p.status||'').toUpperCase();
    if(st==='PLAYER_STATE_SAVED'){
      var ackSeq=Number(p.seq||0);
      if(ackSeq<pendingSeq)return true;
      var row=p.layout||{};
      anchored=!!p.anchored;
      current={x:clamp(row.x==null?current.x:row.x,1,99),y:clamp(row.y==null?current.y:row.y,0,500),scale:clamp(row.scale==null?current.scale:row.scale,.35,3)};
      dirty=false;pendingSeq=0;apply();status(anchored?'GUARDADO · ANCLADO GLOBAL':'GUARDADO EN ESTE ROOM',false);return true;
    }
    if(st==='ERROR'&&String(p.kind||'')==='player_state'){dirty=false;pendingSeq=0;status(String(p.message||'ERROR AL GUARDAR PLAYER'),true);return true}
    return true;
  }
  function bindEmitter(){
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    if(!emitterBound){Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);emitterBound=true}
    if(!assetEmitterBound){Evennia.emitter.on('pokerol_asset_result',onAssetResult);assetEmitterBound=true}
    return emitterBound&&assetEmitterBound;
  }
  function init(){var tries=0;(function wait(){tries++;bindEmitter();if(byId('pk-player-avatar')&&byId('pk-edit-player')){bindAvatar();bindPanel();apply();if(emitterBound&&assetEmitterBound)return}if(tries<200)setTimeout(wait,50)})()}

  window.PokerolPlayerEditorV01=Object.freeze({BUILD:BUILD,applyPacket:applyPacket,isEditing:function(){return editing},isDirty:function(){return dirty}});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
