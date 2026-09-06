(function(){
  'use strict';

  var BUILD='0.1.0-logout-login-screen-guard';

  function flagged(){
    try{return sessionStorage.getItem('pokerol.manual_logout')==='1'}catch(e){return false}
  }

  function clearLastTrainer(){
    try{localStorage.removeItem('pokerol.last_user')}catch(e){}
  }

  function sanitizeStaleUi(){
    if(!flagged())return;
    clearLastTrainer();
    var room=document.getElementById('pk-room-name');
    if(room)room.textContent='Conectando con Kanto…';
    var feed=document.getElementById('messagewindow');
    if(feed)feed.textContent='';
  }

  function forceLoginScreen(){
    if(!flagged())return;
    clearLastTrainer();
    if(window.PokerolOnboardingV01&&typeof PokerolOnboardingV01.showWelcome==='function'){
      try{PokerolOnboardingV01.showWelcome()}catch(e){}
    }
  }

  function releaseGuard(){
    try{sessionStorage.removeItem('pokerol.manual_logout')}catch(e){}
  }

  document.addEventListener('click',function(ev){
    var target=ev.target&&ev.target.closest?ev.target.closest('#pk-login-player,#pk-new-player'):null;
    if(target)releaseGuard();
  },true);

  function init(){
    if(!flagged())return;
    sanitizeStaleUi();
    [0,100,300,700,1500,2500].forEach(function(delay){setTimeout(forceLoginScreen,delay)});
  }

  window.PokerolLogoutGuardV01=Object.freeze({BUILD:BUILD,release:releaseGuard});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
