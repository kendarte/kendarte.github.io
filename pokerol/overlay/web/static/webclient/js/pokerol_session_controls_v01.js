(function(){
  'use strict';

  var BUILD='0.1.1-real-logout';
  var leaving=false;

  function byId(id){return document.getElementById(id)}

  function markManualLogout(){
    try{
      sessionStorage.setItem('pokerol.manual_logout','1');
      localStorage.removeItem('pokerol.last_user');
    }catch(e){}
  }

  function goToLogin(){
    var path=(window.location&&window.location.pathname)||'/webclient/';
    if(!/\/webclient\/?$/i.test(path))path='/webclient/';
    var target=path+'?pokerol_logout='+Date.now();
    try{window.location.replace(target)}catch(e){window.location.href=target}
  }

  function doLogout(){
    if(leaving)return;
    leaving=true;
    markManualLogout();

    var button=byId('pk-logout');
    if(button){button.disabled=true;button.textContent='SALIENDO…'}

    try{
      if(window.Evennia&&typeof Evennia.msg==='function'){
        Evennia.msg('text',['quit'],{});
      }
    }catch(e){}

    /*
     * Do not reload immediately. The old 900 ms reload could reconnect the
     * browser before Evennia had fully torn down the authenticated session,
     * which made the last trainer appear to auto-login again.
     */
    setTimeout(goToLogin,2600);
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
