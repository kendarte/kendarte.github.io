(function(){
'use strict';
var BUILD='0.1.0-red-plus-shell';
function mark(){
  document.documentElement.setAttribute('data-pokerol-theme','red-plus');
  if(document.body)document.body.setAttribute('data-pokerol-theme','red-plus');
  var client=document.getElementById('siza-book-client');
  if(client){
    client.setAttribute('data-pokerol-theme','red-plus');
    var mode=client.getAttribute('data-mode')||'EXPLORATION';
    document.documentElement.setAttribute('data-pokerol-mode',String(mode).toLowerCase());
  }
}
function observe(){
  var client=document.getElementById('siza-book-client');
  if(!client)return;
  new MutationObserver(function(records){
    records.forEach(function(row){
      if(row.attributeName==='data-mode'){
        document.documentElement.setAttribute('data-pokerol-mode',String(client.getAttribute('data-mode')||'EXPLORATION').toLowerCase());
      }
    });
  }).observe(client,{attributes:true,attributeFilter:['data-mode']});
}
function init(){mark();observe()}
window.PokerolRedUiV01=Object.freeze({BUILD:BUILD,refresh:mark});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
