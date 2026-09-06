(function(){
  'use strict';

  var active=false,timer=null,startedAt=0,percent=0,lastMessage='';

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}

  function validAuthForm(form){
    if(!form)return false;
    var name=byId('pk-auth-name'),pass=byId('pk-auth-pass');
    if(!name||!pass)return false;
    var n=clean(name.value).replace(/\s+/g,'_'),p=String(pass.value||'').trim();
    return /^[A-Za-z0-9_\-]{3,24}$/.test(n)&&p.length>=4&&!/\s/.test(p);
  }

  function ensureProgress(){
    var form=byId('pk-auth-form');if(!form)return null;
    var box=byId('pk-login-progress');if(box)return box;
    box=document.createElement('section');box.id='pk-login-progress';box.className='pkLoginProgress';box.hidden=true;
    box.innerHTML='<div class="pkLoginProgressTop"><strong id="pk-login-progress-label">CONECTANDO</strong><span id="pk-login-progress-pct">0%</span></div><div class="pkLoginProgressTrack"><span id="pk-login-progress-bar"></span></div><div id="pk-login-progress-detail" class="pkLoginProgressDetail">Preparando conexión…</div><button id="pk-login-progress-retry" type="button" class="pkLoginRetry" hidden>REINTENTAR CONEXIÓN</button>';
    var status=byId('pk-auth-status');
    if(status&&status.parentNode)status.parentNode.insertBefore(box,status.nextSibling);else form.appendChild(box);
    var retry=byId('pk-login-progress-retry');if(retry)retry.onclick=function(){window.location.reload()};
    return box;
  }

  function setProgress(value,label,detail,state){
    var box=ensureProgress();if(!box)return;
    percent=Math.max(percent,Math.min(100,Math.round(Number(value)||0)));
    box.hidden=false;box.classList.remove('pkLoginSlow','pkLoginError','pkLoginDone');
    if(state)box.classList.add(state);
    var bar=byId('pk-login-progress-bar'),pct=byId('pk-login-progress-pct'),lab=byId('pk-login-progress-label'),det=byId('pk-login-progress-detail');
    if(bar)bar.style.width=percent+'%';if(pct)pct.textContent=percent+'%';if(lab)lab.textContent=label||'CONECTANDO';if(det)det.textContent=detail||'';
  }

  function setFormBusy(busy){
    var form=byId('pk-auth-form');if(!form)return;
    var submit=form.querySelector('button[type="submit"]');
    if(submit){submit.disabled=!!busy;submit.textContent=busy?'CONECTANDO…':(form.closest('.pkOnboardingBody')&&/CONTINUAR AVENTURA/i.test(form.closest('.pkOnboardingBody').textContent||'')?'ENTRAR':'CREAR Y ENTRAR')}
  }

  function stopTimer(){if(timer){clearInterval(timer);timer=null}}

  function startProgress(){
    if(active)return;active=true;startedAt=Date.now();percent=0;lastMessage='';setFormBusy(true);
    setProgress(18,'CONTACTANDO SERVIDOR','Enviando tus credenciales a POKEROL…');
    timer=setInterval(function(){
      if(!active)return;
      var elapsed=(Date.now()-startedAt)/1000;
      if(elapsed<3)setProgress(Math.min(32,18+elapsed*5),'VALIDANDO CUENTA','El servidor está comprobando tu entrenador…');
      else if(elapsed<8)setProgress(Math.min(48,32+(elapsed-3)*3),'ABRIENDO SESIÓN','Esperando confirmación de Evennia…');
      else if(elapsed<15)setProgress(Math.min(62,48+(elapsed-8)*2),'CARGANDO PERSONAJE','La conexión está tardando más de lo normal…','pkLoginSlow');
      else{
        setProgress(Math.min(78,62+(elapsed-15)*0.7),'SERVIDOR LENTO','Seguimos esperando respuesta. Puedes reintentar si supera los 20 segundos.','pkLoginSlow');
        var retry=byId('pk-login-progress-retry');if(retry&&elapsed>=20)retry.hidden=false;
      }
    },500);
  }

  function finishProgress(){
    if(!active)return;active=false;stopTimer();setProgress(100,'LISTO','Entrando a Kanto…','pkLoginDone');
    setTimeout(function(){var box=byId('pk-login-progress');if(box)box.hidden=true},900);
  }

  function failProgress(message){
    active=false;stopTimer();percent=100;setProgress(100,'NO SE PUDO ENTRAR',clean(message).slice(0,180)||'Revisa el nombre y la clave.','pkLoginError');setFormBusy(false);
    var retry=byId('pk-login-progress-retry');if(retry){retry.hidden=false;retry.textContent='REINTENTAR CONEXIÓN'}
  }

  function parseServerText(text){
    var value=clean(text);if(!value||value===lastMessage)return;lastMessage=value;
    if(!active)return;
    if(/you can now log|account.*created|created.*account/i.test(value))setProgress(55,'CUENTA CREADA','Preparando tu primera sesión…');
    if(/you become\s+/i.test(value)){setProgress(92,'PERSONAJE CARGADO','Preparando el mundo y la interfaz…');setTimeout(finishProgress,150);return}
    if(/incorrect password|invalid password|authentication failure|already exists|already taken|no account|not found|too many authentication|throttle|cannot create|error/i.test(value))failProgress(value);
  }

  function watchFeed(){
    var feed=byId('messagewindow');if(!feed)return false;
    new MutationObserver(function(records){records.forEach(function(r){Array.from(r.addedNodes||[]).forEach(function(n){parseServerText(n.textContent||'')})})}).observe(feed,{childList:true,subtree:true});
    return true;
  }

  function bindForm(form){
    if(!form||form.dataset.pkProgressBound==='1')return;form.dataset.pkProgressBound='1';ensureProgress();
    form.addEventListener('submit',function(){if(validAuthForm(form))setTimeout(startProgress,0)},false);
  }

  function watchOnboarding(){
    var root=byId('pk-onboarding-root')||document.body;
    new MutationObserver(function(){
      var form=byId('pk-auth-form');if(form)bindForm(form);
      if(active&&byId('pk-onboarding-body')&&byId('pk-onboarding-body').querySelector('.pkOakScene'))finishProgress();
    }).observe(root,{childList:true,subtree:true});
    var form=byId('pk-auth-form');if(form)bindForm(form);
  }

  function init(){
    watchOnboarding();var tries=0;(function waitFeed(){tries++;if(watchFeed())return;if(tries<80)setTimeout(waitFeed,100)})();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
