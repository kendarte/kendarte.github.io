(function(){
  'use strict';

  var BUILD='0.1.0-logout-control';
  var leaving=false;

  function byId(id){return document.getElementById(id)}

  function doLogout(){
    if(leaving)return;
    leaving=true;
    var button=byId('pk-logout');
    if(button){button.disabled=true;button.textContent='SALIENDO…'}

    try{
      if(window.Evennia&&typeof Evennia.msg==='function'){
        Evennia.msg('text',['quit'],{});
      }
    }catch(e){}

    setTimeout(function(){
      try{window.location.reload()}catch(e){window.location.href=window.location.href}
    },900);
  }

  function inject(){
    if(byId('pk-logout'))return true;
    var tools=document.querySelector('.pkBackgroundTools');
    if(!tools)return false;

    var button=document.createElement('button');
    button.id='pk-logout';
    button.className='pkLogoutButton';
    button.type='button';
    button.textContent='SALIR';
    button.title='Cerrar sesión y volver al login';
    button.addEventListener('click',doLogout);
    tools.appendChild(button);
    return true;
  }

  function init(){
    var tries=0;
    (function wait(){
      tries++;
      if(inject())return;
      if(tries<180)setTimeout(wait,50);
    })();
  }

  window.PokerolSessionControlsV01=Object.freeze({BUILD:BUILD,logout:doLogout});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
