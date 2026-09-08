(function(){
'use strict';
var BUILD='0.2.0-battle-open-guard';
var bound=false;
var requested=false;
function packetFrom(args){
  var p=args;
  if(p&&typeof p.length==='number'&&typeof p!=='string')p=p.length?p[0]:null;
  while(Array.isArray(p)&&p.length===1)p=p[0];
  return p&&typeof p==='object'&&!Array.isArray(p)?p:{};
}
function battleClient(){return window.PokerolPokemonBattleV01||null}
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
  if(!window.Evennia||typeof Evennia.isConnected!=='function'||!Evennia.isConnected()||typeof Evennia.msg!=='function')return false;
  requested=true;
  Evennia.msg('text',['pokerol-battle-state'],{});
  return true;
}
function onRoomSnapshot(){
  window.setTimeout(function(){requestState(true)},40);
}
function bind(){
  if(bound)return true;
  if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
  Evennia.emitter.on('pokerol_pokemon_battle_state',renderPacket);
  Evennia.emitter.on('pokerol_room_snapshot',onRoomSnapshot);
  bound=true;
  return true;
}
function init(){
  var tries=0;
  (function wait(){
    tries+=1;
    bind();
    if(requestState(false))return;
    if(tries<150)setTimeout(wait,100);
  })();
}
window.PokerolBattleOpenGuardV01=Object.freeze({BUILD:BUILD,requestState:function(){return requestState(true)},renderPacket:renderPacket});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
