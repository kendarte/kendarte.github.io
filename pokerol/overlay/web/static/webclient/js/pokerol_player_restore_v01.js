(function(){
  'use strict';

  var BUILD='1.0.0-authoritative-player-restore';
  var emitterBound=false;
  var assetBound=false;
  var lastPacket=null;
  var refreshTimers=[];

  function clean(v){return String(v==null?'':v).trim()}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function clamp(v,min,max){var n=Number(v);if(!Number.isFinite(n))n=min;return Math.max(min,Math.min(max,n))}
  function editor(){return window.PokerolPlayerEditorV01||null}
  function editorBusy(){var e=editor();if(!e)return false;try{return (typeof e.isEditing==='function'&&e.isEditing())||(typeof e.isDirty==='function'&&e.isDirty())}catch(err){return false}}

  function requestRoom(){
    if(window.PokerolPlayableClientV01&&typeof window.PokerolPlayableClientV01.requestRoomState==='function'){
      try{return !!window.PokerolPlayableClientV01.requestRoomState()}catch(e){}
    }
    if(window.Evennia&&typeof window.Evennia.msg==='function'){
      try{window.Evennia.msg('text',['pokerol-room-state'],{});return true}catch(e){}
    }
    return false;
  }

  function fallbackApply(packet){
    if(editorBusy())return false;
    var row=packet&&packet.player_editor||{};
    var avatar=document.getElementById('pk-player-avatar');
    if(!avatar)return false;
    var x=clamp(row.scene_x==null?11:row.scene_x,1,99);
    var y=clamp(row.scene_y==null?94:row.scene_y,0,500);
    var scale=clamp(row.scene_scale==null?1:row.scene_scale,.35,3);
    avatar.style.left=x+'%';
    avatar.style.bottom=y+'px';
    avatar.style.transform='translateX(-50%) scale('+scale+')';
    avatar.style.transformOrigin='bottom center';
    avatar.dataset.pkRestoredX=String(x);
    avatar.dataset.pkRestoredY=String(y);
    avatar.dataset.pkRestoredScale=String(scale);
    return true;
  }

  function applyPacket(packet){
    if(!packet||!packet.player_editor)return false;
    lastPacket=packet;
    if(editorBusy())return false;
    var e=editor();
    if(e&&typeof e.applyPacket==='function'){
      try{
        var applied=e.applyPacket(packet);
        if(applied!==false)return true;
      }catch(err){}
    }
    return fallbackApply(packet);
  }

  function onSnapshot(args){
    var packet=packetFrom(args);
    applyPacket(packet);
    setTimeout(function(){applyPacket(packet)},60);
    setTimeout(function(){applyPacket(packet)},220);
    return true;
  }

  function onAssetResult(args){
    var p=packetFrom(args),status=clean(p.status).toUpperCase();
    if(status==='PLAYER_STATE_SAVED'){
      var layout=p.layout||{};
      var packet={
        room_dbref:p.room_dbref,
        player_editor:{
          scene_x:layout.x,
          scene_y:layout.y,
          scene_scale:layout.scale,
          anchored:!!p.anchored,
          revision:p.revision||layout.revision||0
        }
      };
      lastPacket=packet;
      if(!editorBusy())applyPacket(packet);
      scheduleRefresh();
    }
    return true;
  }

  function bindEmitter(){
    if(!window.Evennia||!window.Evennia.emitter||typeof window.Evennia.emitter.on!=='function')return false;
    if(!emitterBound){window.Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);emitterBound=true}
    if(!assetBound){window.Evennia.emitter.on('pokerol_asset_result',onAssetResult);assetBound=true}
    return emitterBound&&assetBound;
  }

  function scheduleRefresh(){
    refreshTimers.forEach(function(t){clearTimeout(t)});refreshTimers=[];
    [40,180,500,1200,2500,5000].forEach(function(ms){
      refreshTimers.push(setTimeout(function(){requestRoom();if(lastPacket&&!editorBusy())applyPacket(lastPacket)},ms));
    });
  }

  function init(){
    var tries=0;
    (function wait(){
      tries+=1;
      bindEmitter();
      if(emitterBound&&assetBound){scheduleRefresh();return}
      if(tries<240)setTimeout(wait,50);
    })();
    window.addEventListener('pokerol-authenticated',scheduleRefresh);
    window.addEventListener('focus',function(){if(!editorBusy())scheduleRefresh()});
    document.addEventListener('visibilitychange',function(){if(!document.hidden&&!editorBusy())scheduleRefresh()});
  }

  window.PokerolPlayerRestoreV01=Object.freeze({BUILD:BUILD,refresh:scheduleRefresh,applyPacket:applyPacket});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
