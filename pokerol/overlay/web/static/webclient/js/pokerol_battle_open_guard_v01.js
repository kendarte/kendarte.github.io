(function(){
'use strict';
var BUILD='0.4.0-room-text-fallback';
var ROOM_PREFIX='__POKEROL_ROOM_STATE_V1__:';
var bound=false;
var requested=false;
var roomSyncTimer=null;
var roomSyncActive=false;
var roomSyncAttempts=0;
var pendingRoomPacket=null;
var lastFallbackRoomPacket=null;
function packetFrom(args){
  var p=args;
  if(p&&typeof p.length==='number'&&typeof p!=='string')p=p.length?p[0]:null;
  while(Array.isArray(p)&&p.length===1)p=p[0];
  return p&&typeof p==='object'&&!Array.isArray(p)?p:{};
}
function connected(){
  try{return !!(window.Evennia&&typeof Evennia.isConnected==='function'&&Evennia.isConnected()&&typeof Evennia.msg==='function')}catch(e){return false}
}
function battleClient(){return window.PokerolPokemonBattleV01||null}
function playableClient(){return window.PokerolPlayableClientV01||null}
function renderPacket(args){
  var packet=packetFrom(args);
  if(!packet||!Object.keys(packet).length)return false;
  var client=battleClient();
  if(!client||typeof client.render!=='function')return false;
  client.render(packet);
  return true;
}
function requestState(force){
  if(force)requested=false;
  if(requested)return true;
  if(!connected())return false;
  requested=true;
  Evennia.msg('text',['pokerol-battle-state'],{});
  return true;
}
function stopRoomSync(){
  roomSyncActive=false;
  roomSyncAttempts=0;
  if(roomSyncTimer){clearTimeout(roomSyncTimer);roomSyncTimer=null}
}
function requestRoomState(){
  if(!connected())return false;
  try{Evennia.msg('text',['pokerol-room-state'],{});return true}catch(e){return false}
}
function flushPendingRoom(){
  if(!pendingRoomPacket)return false;
  var client=playableClient();
  if(!client||typeof client.renderSnapshot!=='function')return false;
  client.renderSnapshot(pendingRoomPacket);
  lastFallbackRoomPacket=pendingRoomPacket;
  pendingRoomPacket=null;
  return true;
}
function removeFallbackEcho(){
  window.setTimeout(function(){
    var feed=document.getElementById('messagewindow');
    if(feed){
      Array.prototype.slice.call(feed.children||[]).forEach(function(node){
        if(String(node.textContent||'').indexOf(ROOM_PREFIX)!==-1&&node.parentNode)node.parentNode.removeChild(node);
      });
    }
    var packet=lastFallbackRoomPacket;
    var client=playableClient();
    if(packet&&client&&typeof client.setDialogue==='function'){
      var text=String(packet.room_description||packet.description||'').trim();
      if(text)client.setDialogue(text,'NARRADOR',false);
    }
  },0);
}
function acceptFallbackText(value){
  var raw=String(value||'');
  var at=raw.indexOf(ROOM_PREFIX);
  if(at===-1)return false;
  var encoded=raw.slice(at+ROOM_PREFIX.length).trim();
  try{
    var payload=JSON.parse(encoded);
    var room=payload&&payload.room&&typeof payload.room==='object'?payload.room:payload;
    if(room&&typeof room==='object'&&!Array.isArray(room)){
      pendingRoomPacket=room;
      lastFallbackRoomPacket=room;
      if(flushPendingRoom())stopRoomSync();
      window.setTimeout(function(){requestState(true)},40);
    }
  }catch(err){
    if(window.console&&console.error)console.error('[POKEROL room fallback]',err);
  }
  removeFallbackEcho();
  return true;
}
function roomSyncTick(){
  if(!roomSyncActive)return;
  roomSyncAttempts+=1;
  flushPendingRoom();
  requestRoomState();
  if(roomSyncAttempts>=24){stopRoomSync();return}
  roomSyncTimer=setTimeout(roomSyncTick,450);
}
function startRoomSync(){
  stopRoomSync();
  roomSyncActive=true;
  roomSyncAttempts=0;
  roomSyncTimer=setTimeout(roomSyncTick,25);
}
function onRoomSnapshot(args){
  var packet=packetFrom(args);
  if(packet&&Object.keys(packet).length){
    pendingRoomPacket=packet;
    var rendered=flushPendingRoom();
    if(rendered)stopRoomSync();
  }
  window.setTimeout(function(){requestState(true)},40);
}
function onAuthState(args){
  var packet=packetFrom(args);
  if(packet&&packet.logged_in===true)startRoomSync();
}
function onText(args){
  var value=args&&args.length?String(args[0]||''):String(args||'');
  if(acceptFallbackText(value))return true;
  if(/you become\s+/i.test(value))startRoomSync();
  return true;
}
function onConnectionClose(){
  requested=false;
  stopRoomSync();
}
function bind(){
  if(bound)return true;
  if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
  Evennia.emitter.on('pokerol_pokemon_battle_state',renderPacket);
  Evennia.emitter.on('pokerol_room_snapshot',onRoomSnapshot);
  Evennia.emitter.on('pokerol_auth_state',onAuthState);
  Evennia.emitter.on('text',onText);
  Evennia.emitter.on('connection_close',onConnectionClose);
  bound=true;
  return true;
}
function init(){
  window.addEventListener('pokerol-authenticated',startRoomSync);
  var tries=0;
  (function wait(){
    tries+=1;
    bind();
    flushPendingRoom();
    if(requestState(false))return;
    if(tries<150)setTimeout(wait,100);
  })();
}
window.PokerolBattleOpenGuardV01=Object.freeze({BUILD:BUILD,requestState:function(){return requestState(true)},renderPacket:renderPacket,startRoomSync:startRoomSync,requestRoomState:requestRoomState});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
