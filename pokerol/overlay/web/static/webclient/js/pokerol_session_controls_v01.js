(function(){
  'use strict';

  var BUILD='0.1.2-confirmed-websocket-logout';
  var leaving=false;

  function byId(id){return document.getElementById(id)}

  function markManualLogout(){
    try{
      sessionStorage.setItem('pokerol.manual_logout','1');
      localStorage.removeItem('pokerol.last_user');
    }catch(e){}
  }

  function connected(){
    try{return !!(window.Evennia&&typeof Evennia.isConnected==='function'&&Evennia.isConnected())}catch(e){return false}
  }

  function goToLogin(){
    var path=(window.location&&window.location.pathname)||'/webclient/';
    if(!/\/webclient\/?$/i.test(path))path='/webclient/';
    var target=path+'?pokerol_logout='+Date.now();
    try{window.location.replace(target)}catch(e){window.location.href=target}
  }

  function restoreButton(message){
    leaving=false;
    var button=byId('pk-logout');
    if(button){button.disabled=false;button.textContent='SALIR';button.title=message||'Cerrar sesión y volver al login'}
  }

  function waitForClosed(){
    var started=Date.now(),lastRetry=0;
    (function check(){
      if(!leaving)return;
      if(!connected()){
        /* Evennia clears webclient_authenticated_uid before sending the normal
         * websocket close. Only navigate after that close is visible here. */
        setTimeout(goToLogin,300);
        return;
      }

      var elapsed=Date.now()-started;
      if(elapsed>2500&&elapsed-lastRetry>2500){
        lastRetry=elapsed;
        try{Evennia.msg('text',['quit'],{})}catch(e){}
      }
      if(elapsed>10000){restoreButton('No se confirmó el cierre. Pulsa SALIR para reintentar.');return}
      setTimeout(check,120);
    })();
  }

  function doLogout(){
    if(leaving)return;
    leaving=true;markManualLogout();

    var button=byId('pk-logout');
    if(button){button.disabled=true;button.textContent='SALIENDO…'}

    if(!connected()){goToLogin();return}

    try{
      if(window.Evennia&&typeof Evennia.msg==='function')Evennia.msg('text',['quit'],{});
      else{restoreButton('No hay conexión activa.');return}
    }catch(e){restoreButton('No se pudo enviar el cierre de sesión.');return}

    waitForClosed();
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
