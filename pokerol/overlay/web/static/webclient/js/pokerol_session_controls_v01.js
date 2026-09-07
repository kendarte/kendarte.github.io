(function(){
  'use strict';

  var BUILD='0.2.0-hard-browser-logout';
  var leaving=false,currentToken='',emitterBound=false,timeoutId=null;

  function byId(id){return document.getElementById(id)}
  function packetFrom(args){
    var packet=args&&args.length?args[0]:args;
    if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
    return packet&&typeof packet==='object'?packet:{};
  }

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
    leaving=false;currentToken='';
    if(timeoutId){clearTimeout(timeoutId);timeoutId=null}
    var button=byId('pk-logout');
    if(button){button.disabled=false;button.textContent='SALIR';button.title=message||'Cerrar sesión y volver al login'}
  }

  function closeTransportThenLogin(){
    try{
      if(window.Evennia&&Evennia.connection&&typeof Evennia.connection.close==='function')Evennia.connection.close();
    }catch(e){}
    setTimeout(goToLogin,700);
  }

  function onLogoutReady(args){
    var packet=packetFrom(args);
    try{window.dispatchEvent(new CustomEvent('pokerol-logout-ready',{detail:packet}))}catch(e){}
    if(!leaving||!currentToken||String(packet.token||'')!==currentToken)return true;
    if(packet.cleared!==true){restoreButton('El servidor no pudo limpiar la sesión del navegador. Reintenta.');return true}
    if(timeoutId){clearTimeout(timeoutId);timeoutId=null}
    var button=byId('pk-logout');
    if(button)button.textContent='CERRANDO…';
    closeTransportThenLogin();
    return true;
  }

  function bindEmitter(){
    if(emitterBound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_logout_ready',onLogoutReady);
    emitterBound=true;
    return true;
  }

  function doLogout(){
    if(leaving)return;
    leaving=true;markManualLogout();

    var button=byId('pk-logout');
    if(button){button.disabled=true;button.textContent='LIMPIANDO SESIÓN…'}

    if(!connected()){
      goToLogin();
      return;
    }

    currentToken='manual-'+Date.now()+'-'+Math.random().toString(36).slice(2,8);
    try{
      if(!window.Evennia||typeof Evennia.msg!=='function')throw new Error('sin Evennia');
      Evennia.msg('text',['pokerol-hard-logout '+currentToken],{});
    }catch(e){restoreButton('No se pudo solicitar el cierre de sesión.');return}

    timeoutId=setTimeout(function(){
      if(leaving)restoreButton('El servidor no confirmó la limpieza de sesión. Pulsa SALIR para reintentar.');
    },6000);
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
      var ready=bindEmitter();
      var injected=inject();
      if(ready&&injected)return;
      if(tries<240)setTimeout(wait,50);
    })();
  }

  window.PokerolSessionControlsV01=Object.freeze({BUILD:BUILD,logout:doLogout});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
