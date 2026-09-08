(function(){
'use strict';
var BUILD='0.1.0-attacks-first-guard',observer=null;
function clean(){
  var reaction=document.getElementById('pkb-reaction-menu');if(reaction)reaction.remove();
  var strip=document.querySelector('#pokerol-pokemon-battle .pkbUtilityStrip');if(strip)strip.style.gridTemplateColumns='repeat(4,minmax(0,1fr))';
  var hint=document.getElementById('pkb-command-hint');if(hint)hint.textContent='ATAQUES + ACCIONES';
  var input=document.getElementById('pkb-free-order-input');if(input&&/reacci/i.test(input.placeholder||''))input.placeholder='Describe la orden: ataque, movimiento, posición o uso del entorno';
}
function init(){clean();var root=document.getElementById('pokerol-client')||document.body;if(observer)return;observer=new MutationObserver(function(){clean()});observer.observe(root,{childList:true,subtree:true})}
window.PokerolBattleUiGuardV01=Object.freeze({BUILD:BUILD,refresh:clean});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();