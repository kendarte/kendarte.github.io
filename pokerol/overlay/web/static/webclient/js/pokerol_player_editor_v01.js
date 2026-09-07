(function(){
  'use strict';

  var BUILD='0.8.0-character-global-player-authority';
  var editing=false;
  var anchored=false;
  var drag=null;
  var resize=null;
  var current={x:11,y:94,scale:1};
  var committed={x:11,y:94,scale:1,anchored:false,revision:0,roomDbref:null};
  var emitterBound=false;
  var assetEmitterBound=false;
  var seq=0;
  var pendingSeq=0;
  var pendingClose=false;
  var saveTimer=null;
  var dirty=false;
  var lastRoomDbref=null;
  // Stable logical dimensions, independent of frame initialization and Room CSS.
  var baseSize={w:96,h:140};
  var characterDbref=null;
  var renderedAvatar=null;
  var refreshTimers=[];

  function byId(id){return document.getElementById(id)}
  function clamp(v,min,max){var n=Number(v);if(!Number.isFinite(n))n=min;return Math.max(min,Math.min(max,n))}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function encodePayload(data){var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
  function status(text,bad){var n=byId('pk-player-status');if(!n)return;n.textContent=text||'';n.classList.toggle('pkError',!!bad)}

  function sendCommand(command,payload){
    if(!window.Evennia||typeof Evennia.msg!=='function'){status('SIN CONEXIÓN',true);return false}
    try{Evennia.msg('text',[command+' '+encodePayload(payload)],{});return true}catch(e){status('NO SE PUDO ENVIAR',true);return false}
  }

  function requestRoomState(){
    if(window.PokerolPlayableClientV01&&typeof PokerolPlayableClientV01.requestRoomState==='function'){
      try{return !!PokerolPlayableClientV01.requestRoomState()}catch(e){}
    }
    if(window.Evennia&&typeof Evennia.msg==='function'){
      try{Evennia.msg('text',['pokerol-room-state'],{});return true}catch(e){}
    }
    return false;
  }

  function scheduleRefresh(){
    refreshTimers.forEach(function(t){clearTimeout(t)});refreshTimers=[];
    [25,120,350,900,1800].forEach(function(ms){
      refreshTimers.push(setTimeout(function(){if(!editing&&!dirty&&!pendingSeq)requestRoomState()},ms));
    });
  }

  function markDirty(){dirty=true;status(anchored?'CAMBIOS SIN GUARDAR · ANCLADO':'CAMBIOS SIN GUARDAR',false)}

  function apply(){
    var avatar=byId('pk-player-avatar');if(!avatar||characterDbref===null)return false;
    renderedAvatar=avatar;
    var size=baseSize;
    var w=size.w*current.scale,h=size.h*current.scale;

    // Inline !important is intentional: PLAYER editor is the only owner of
    // these four visual properties. Frame/theme CSS cannot reset a saved edit.
    avatar.style.setProperty('left',current.x+'%','important');
    avatar.style.setProperty('bottom',current.y+'px','important');
    avatar.style.setProperty('width',w+'px','important');
    avatar.style.setProperty('height',h+'px','important');
    avatar.style.setProperty('transform','translateX(-50%)','important');
    avatar.style.setProperty('transform-origin','bottom center','important');
    avatar.style.setProperty('--pk-player-edit-scale',String(current.scale));
    avatar.dataset.pkPlayerAppliedScale=String(current.scale);
    avatar.dataset.pkPlayerX=String(current.x);
    avatar.dataset.pkPlayerY=String(current.y);
    avatar.dataset.pkPlayerScale=String(current.scale);
    avatar.dataset.pkPlayerCharacter=String(characterDbref);
    avatar.dataset.pkPlayerRevision=String(committed.revision);

    var sprite=byId('pk-player-sprite');
    if(sprite){
      sprite.style.setProperty('width','100%','important');
      sprite.style.setProperty('height','100%','important');
      sprite.style.setProperty('max-width','100%','important');
      sprite.style.setProperty('max-height','100%','important');
      sprite.style.setProperty('object-fit','contain','important');
      sprite.style.setProperty('object-position','center bottom','important');
    }

    var x=byId('pk-player-x'),y=byId('pk-player-y'),s=byId('pk-player-scale'),a=byId('pk-player-anchor');
    if(x)x.value=current.x.toFixed(1);
    if(y)y.value=current.y.toFixed(0);
    if(s)s.value=current.scale.toFixed(2);
    if(a)a.checked=anchored;
    return true;
  }

  function saveState(reset){
    if(characterDbref===null){status('ESPERANDO ESTADO DEL PERSONAJE',true);return false}
    if(pendingSeq){status('GUARDADO YA EN PROCESO…',false);return false}
    seq+=1;pendingSeq=seq;
    var payload={
      anchored:!!anchored,
      x:current.x,
      y:current.y,
      scale:current.scale,
      reset:!!reset,
      seq:seq,
      character_dbref:characterDbref,
      room_dbref:lastRoomDbref
    };
    status('GUARDANDO EN SERVIDOR…',false);
    if(!sendCommand('pokerol-editor-player-state',payload)){
      pendingSeq=0;dirty=true;return false;
    }
    clearTimeout(saveTimer);
    saveTimer=setTimeout(function(){
      if(!pendingSeq)return;
      pendingSeq=0;pendingClose=false;dirty=true;
      status('EL SERVIDOR NO CONFIRMÓ EL GUARDADO',true);
      editing=true;
    },8000);
    return true;
  }

  function closeNow(skipRender){
    editing=false;drag=null;resize=null;pendingClose=false;
    var stage=byId('pk-stage'),avatar=byId('pk-player-avatar'),panel=byId('pk-player-panel'),btn=byId('pk-edit-player');
    if(stage)stage.classList.remove('pkPlayerEditing');
    if(avatar)avatar.classList.remove('pkPlayerEditable');
    if(panel)panel.hidden=true;
    if(btn)btn.classList.remove('pkActive');
    document.documentElement.dataset.pkPlayerEditing='0';
    // Closing EDIT must never change the saved transform.
    if(!skipRender)apply();
  }

  function setEditing(on,force){
    if(on){
      editing=true;
      var stage=byId('pk-stage'),avatar=byId('pk-player-avatar'),panel=byId('pk-player-panel'),btn=byId('pk-edit-player');
      if(stage)stage.classList.add('pkPlayerEditing');
      if(avatar)avatar.classList.add('pkPlayerEditable');
      if(panel)panel.hidden=false;
      if(btn)btn.classList.add('pkActive');
      document.documentElement.dataset.pkPlayerEditing='1';
      ensureHandle();apply();
      if(!force)status(dirty?(anchored?'CAMBIOS SIN GUARDAR · ANCLADO':'CAMBIOS SIN GUARDAR'):(anchored?'ANCLADO · GUARDADO':'GUARDADO'),false);
      return;
    }
    if(force){closeNow();return}
    if(pendingSeq){pendingClose=true;status('ESPERANDO CONFIRMACIÓN DEL SERVIDOR…',false);return}
    if(dirty){pendingClose=true;saveState(false);return}
    closeNow();
  }

  function applyPacket(packet){
    var row=packet&&packet.player_editor;
    if(!row||row.character_dbref==null||row.scene_x==null||row.scene_y==null||row.scene_scale==null)return false;
    var incomingCharacter=Number(row.character_dbref);
    if(!Number.isFinite(incomingCharacter))return false;
    if(characterDbref!==incomingCharacter){
      clearTimeout(saveTimer);pendingSeq=0;pendingClose=false;dirty=false;
      editing=false;drag=null;resize=null;characterDbref=incomingCharacter;
      committed={revision:0,roomDbref:null};
      closeNow(true);
    }
    var roomDbref=packet&&packet.room_dbref!=null?Number(packet.room_dbref):null;
    if(!Number.isFinite(roomDbref))roomDbref=null;
    if(editing||drag||resize||dirty||pendingSeq)return false;

    var incoming={
      x:clamp(row.scene_x==null?11:row.scene_x,1,99),
      y:clamp(row.scene_y==null?94:row.scene_y,0,500),
      scale:clamp(row.scene_scale==null?1:row.scene_scale,.35,3),
      anchored:!!row.anchored,
      revision:Number(row.revision||0),
      roomDbref:roomDbref
    };

    // Revisions belong to the character, so stale packets are rejected across
    // all Rooms, including a delayed default packet after a confirmed save.
    if(incoming.revision<committed.revision)return false;

    lastRoomDbref=roomDbref;
    committed=incoming;
    anchored=incoming.anchored;
    current={x:incoming.x,y:incoming.y,scale:incoming.scale};
    apply();
    return true;
  }

  function ensureHandle(){
    var avatar=byId('pk-player-avatar');if(!avatar||byId('pk-player-resize-handle'))return;
    var h=document.createElement('span');h.id='pk-player-resize-handle';h.className='pkPlayerResizeHandle';h.title='Arrastra para cambiar tamaño';avatar.appendChild(h);
  }

  function bindAvatar(){
    var avatar=byId('pk-player-avatar'),stage=byId('pk-stage');if(!avatar||!stage||avatar.dataset.pkPlayerEditBound==='1')return false;
    avatar.dataset.pkPlayerEditBound='1';ensureHandle();

    avatar.addEventListener('pointerdown',function(ev){
      if(!editing||pendingSeq||ev.target===byId('pk-player-resize-handle'))return;
      ev.preventDefault();ev.stopPropagation();
      drag={id:ev.pointerId,rect:stage.getBoundingClientRect()};
      avatar.setPointerCapture&&avatar.setPointerCapture(ev.pointerId);
    },true);

    avatar.addEventListener('pointermove',function(ev){
      if(!editing||pendingSeq||!drag||drag.id!==ev.pointerId)return;
      ev.preventDefault();ev.stopPropagation();
      var r=drag.rect;
      current.x=clamp(((ev.clientX-r.left)/r.width)*100,1,99);
      current.y=clamp(r.bottom-ev.clientY,0,Math.max(100,r.height-20));
      markDirty();apply();
    },true);

    avatar.addEventListener('pointerup',function(ev){
      if(drag&&drag.id===ev.pointerId){ev.preventDefault();ev.stopPropagation();drag=null;status('POSICIÓN CAMBIADA · PULSE GUARDAR',false)}
    },true);
    avatar.addEventListener('pointercancel',function(ev){if(drag&&drag.id===ev.pointerId)drag=null},true);

    var h=byId('pk-player-resize-handle');
    if(h&&h.dataset.pkBound!=='1'){
      h.dataset.pkBound='1';
      h.addEventListener('pointerdown',function(ev){
        if(!editing||pendingSeq)return;
        ev.preventDefault();ev.stopPropagation();
        resize={id:ev.pointerId,startY:ev.clientY,startScale:current.scale};
        h.setPointerCapture&&h.setPointerCapture(ev.pointerId);
      },true);
      h.addEventListener('pointermove',function(ev){
        if(!editing||pendingSeq||!resize||resize.id!==ev.pointerId)return;
        ev.preventDefault();ev.stopPropagation();
        current.scale=clamp(resize.startScale+((resize.startY-ev.clientY)/120),.35,3);
        markDirty();apply();
      },true);
      h.addEventListener('pointerup',function(ev){
        if(resize&&resize.id===ev.pointerId){ev.preventDefault();ev.stopPropagation();resize=null;status('TAMAÑO CAMBIADO · PULSE GUARDAR',false)}
      },true);
      h.addEventListener('pointercancel',function(ev){if(resize&&resize.id===ev.pointerId)resize=null},true);
    }
    return true;
  }

  function readFields(){
    var x=parseFloat(byId('pk-player-x')&&byId('pk-player-x').value);
    var y=parseFloat(byId('pk-player-y')&&byId('pk-player-y').value);
    var s=parseFloat(byId('pk-player-scale')&&byId('pk-player-scale').value);
    if(Number.isFinite(x))current.x=clamp(x,1,99);
    if(Number.isFinite(y))current.y=clamp(y,0,500);
    if(Number.isFinite(s))current.scale=clamp(s,.35,3);
  }

  function bindPanel(){
    var btn=byId('pk-edit-player'),close=byId('pk-player-close'),save=byId('pk-player-save'),reset=byId('pk-player-reset'),anchor=byId('pk-player-anchor');
    if(btn&&btn.dataset.pkBound!=='1'){btn.dataset.pkBound='1';btn.addEventListener('click',function(){setEditing(true)})}
    if(close&&close.dataset.pkBound!=='1'){close.dataset.pkBound='1';close.addEventListener('click',function(){setEditing(false)})}
    if(save&&save.dataset.pkBound!=='1'){
      save.dataset.pkBound='1';
      save.addEventListener('click',function(){if(pendingSeq)return;readFields();apply();dirty=true;saveState(false)});
    }
    if(reset&&reset.dataset.pkBound!=='1'){
      reset.dataset.pkBound='1';
      reset.addEventListener('click',function(){if(pendingSeq)return;current={x:11,y:94,scale:1};markDirty();apply();status('RESET PREPARADO · PULSE GUARDAR',false)});
    }
    if(anchor&&anchor.dataset.pkBound!=='1'){
      anchor.dataset.pkBound='1';
      anchor.addEventListener('change',function(){if(pendingSeq){anchor.checked=anchored;return}readFields();anchored=!!anchor.checked;markDirty();apply();status(anchored?'ANCLAR ACTIVADO · PULSE GUARDAR':'ANCLAR DESACTIVADO · PULSE GUARDAR',false)});
    }
    ['pk-player-x','pk-player-y','pk-player-scale'].forEach(function(id){
      var n=byId(id);if(n&&n.dataset.pkBound!=='1'){
        n.dataset.pkBound='1';
        n.addEventListener('input',function(){if(pendingSeq)return;readFields();markDirty();apply()});
      }
    });
  }

  function onSnapshot(args){applyPacket(packetFrom(args));return true}

  function onAssetResult(args){
    var p=packetFrom(args),st=String(p.status||'').toUpperCase();
    if(st==='PLAYER_STATE_SAVED'){
      if(Number(p.character_dbref)!==characterDbref)return true;
      var ackSeq=Number(p.seq||0);if(!pendingSeq||ackSeq!==pendingSeq)return true;
      clearTimeout(saveTimer);saveTimer=null;
      var row=p.layout||{};
      var saved={
        x:clamp(row.x==null?current.x:row.x,1,99),
        y:clamp(row.y==null?current.y:row.y,0,500),
        scale:clamp(row.scale==null?current.scale:row.scale,.35,3),
        anchored:!!p.anchored,
        revision:Number(p.revision||row.revision||0),
        roomDbref:p.room_dbref==null?lastRoomDbref:Number(p.room_dbref)
      };
      committed=saved;
      lastRoomDbref=saved.roomDbref;
      anchored=saved.anchored;
      current={x:saved.x,y:saved.y,scale:saved.scale};
      dirty=false;pendingSeq=0;
      apply();
      status(anchored?'GUARDADO · PERSONAJE · ANCLADO':'GUARDADO · PERSONAJE',false);
      requestRoomState();
      if(pendingClose)setTimeout(function(){if(!dirty&&!pendingSeq)closeNow()},80);
      return true;
    }
    if(st==='ERROR'&&String(p.kind||'')==='player_state'){
      clearTimeout(saveTimer);saveTimer=null;pendingSeq=0;pendingClose=false;dirty=true;
      status(String(p.message||'ERROR AL GUARDAR PLAYER'),true);
      editing=true;
      return true;
    }
    return true;
  }

  function bindEmitter(){
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    if(!emitterBound){Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);emitterBound=true}
    if(!assetEmitterBound){Evennia.emitter.on('pokerol_asset_result',onAssetResult);assetEmitterBound=true}
    return emitterBound&&assetEmitterBound;
  }

  function init(){
    var tries=0;
    (function wait(){
      tries++;
      bindEmitter();
      if(byId('pk-player-avatar')&&byId('pk-edit-player')){
        bindAvatar();bindPanel();apply();
        if(emitterBound&&assetEmitterBound){scheduleRefresh();return}
      }
      if(tries<240)setTimeout(wait,50);
    })();

    // Rebind only when the avatar node is replaced. No transform writer or
    // timed restore layer competes with this renderer.
    new MutationObserver(function(){
      var avatar=byId('pk-player-avatar');
      if(avatar&&avatar!==renderedAvatar){bindAvatar();bindPanel();apply()}
    }).observe(document.body,{childList:true,subtree:true});
    window.addEventListener('pokerol-room-transition-complete',apply);
    window.addEventListener('pokerol-authenticated',scheduleRefresh);
    window.addEventListener('focus',function(){if(!editing&&!dirty&&!pendingSeq)scheduleRefresh()});
    document.addEventListener('visibilitychange',function(){if(!document.hidden&&!editing&&!dirty&&!pendingSeq)scheduleRefresh()});
  }

  window.PokerolPlayerEditorV01=Object.freeze({
    BUILD:BUILD,
    applyPacket:applyPacket,
    render:apply,
    isEditing:function(){return editing},
    isDirty:function(){return dirty||!!pendingSeq},
    current:function(){return {x:current.x,y:current.y,scale:current.scale,anchored:anchored}},
    committed:function(){return committed},
    refresh:scheduleRefresh
  });

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
