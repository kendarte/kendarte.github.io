(function(){
  'use strict';
  var BUILD='0.1.0-playable-client';
  function byId(id){return document.getElementById(id)}
  function send(command){
    var field=byId('inputfield');
    var button=byId('inputsend');
    if(!field||!button)return false;
    field.value=String(command||'');
    field.dispatchEvent(new Event('input',{bubbles:true}));
    button.click();
    window.setTimeout(function(){field.focus()},40);
    return true;
  }
  function bind(id,command){var el=byId(id);if(el)el.addEventListener('click',function(){send(command)})}
  function init(){
    document.title='POKEROL';
    bind('pk-look','look');
    bind('pk-party','equipo');
    bind('pk-bag','bolsa');
    bind('pk-test','solo-prueba');
    var field=byId('inputfield');
    if(field){
      field.setAttribute('placeholder','Escribe una acción o comando…');
      window.setTimeout(function(){field.focus()},250);
    }
  }
  window.PokerolPlayableClientV01=Object.freeze({BUILD:BUILD,send:send});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
