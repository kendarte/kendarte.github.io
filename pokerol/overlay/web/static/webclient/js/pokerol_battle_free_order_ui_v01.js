(function(){
'use strict';
var BUILD='0.3.0-generic-battle-free-order';
var state=null;
var bound=false;
function text(v){return String(v==null?'':v).trim()}
function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
function encode(value){var json=JSON.stringify(value),raw=unescape(encodeURIComponent(json)),bin='';for(var i=0;i<raw.length;i++)bin+=String.fromCharCode(raw.charCodeAt(i));return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/g,'')}
function canSend(){return !!state&&text(state.status).toUpperCase()==='ACTIVE'&&text(state.phase).toUpperCase()==='COMMAND'}
function send(value){var raw=text(value);if(!raw||!canSend()||!window.Evennia||!Evennia.isConnected())return false;Evennia.msg('text',['pokerol-battle-free '+encode({text:raw})],{});return true}
function ensure(){
  var battle=document.getElementById('pokerol-pokemon-battle');if(!battle)return null;
  var existing=document.getElementById('pkb-free-order-bar');if(existing)return existing;
  var slot=document.getElementById('pkb-free-order-slot')||battle;
  var bar=document.createElement('div');bar.id='pkb-free-order-bar';bar.className='pkbFreeOrderBar';
  bar.innerHTML='<span class="pkbFreeOrderLabel">ACCIÓN LIBRE</span><input id="pkb-free-order-input" type="text" autocomplete="off" spellcheck="false" placeholder="Describe la orden: movimiento, posición, reacción o uso del entorno"><button id="pkb-free-order-send" type="button">ORDENAR</button>';
  slot.appendChild(bar);
  var input=document.getElementById('pkb-free-order-input'),button=document.getElementById('pkb-free-order-send');
  function submit(){if(!input)return;var raw=text(input.value);if(send(raw)){input.value='';input.focus()}}
  if(button)button.addEventListener('click',submit);
  if(input)input.addEventListener('keydown',function(ev){if(ev.key==='Enter'&&!ev.shiftKey){ev.preventDefault();submit()}});
  return bar;
}
function refresh(){
  var bar=ensure();if(!bar)return;
  var active=!!state&&text(state.status).toUpperCase()==='ACTIVE';bar.style.display=active?'flex':'none';
  var input=document.getElementById('pkb-free-order-input'),button=document.getElementById('pkb-free-order-send'),ready=canSend();
  if(input)input.disabled=!ready;if(button)button.disabled=!ready;
}
function onState(args){state=packetFrom(args);window.setTimeout(refresh,0);window.setTimeout(refresh,40)}
function bind(){if(bound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_pokemon_battle_state',onState);Evennia.emitter.on('pokerol_pokemon_battle_ended',function(){if(state)state.status='COMPLETE';refresh()});bound=true;return true}
function init(){var tries=0;(function retry(){tries+=1;if(bind()){refresh();return}if(tries<80)window.setTimeout(retry,100)})()}
window.PokerolBattleFreeOrderUIV01=Object.freeze({BUILD:BUILD,send:send,refresh:refresh});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
