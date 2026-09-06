(function(){
  'use strict';

  var active=false,timer=null,startedAt=0,percent=0,lastMessage='',observerBound=false;

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
    box.innerHTML='<div class="pkLoginProgressTop"><strong id="pk-login-progress-label">CONECTANDO</strong><span id="pk-login-progress-pct">0%</span></div><div class="pkLoginProgressTrack"><span id="pk-login-progress-bar"></span></div><div id="pk-login-progress-detail" class="pkLoginProgressDetail">Preparando conexión…</div><button id="pk-login-progress-retry" type="button" class="pkLoginRetry" hidden>REINTENTAR</button>';
    var status=byId('pk-auth-status');
    if(status&&status.parentNode)status.parentNode.insertBefore(box,status.nextSibling);else form.appendChild(box);
    var retry=byId('pk-login-progress-retry');if(retry)retry.onclick=resetProgress;
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
    var name=byId('pk-auth-name'),pass=byId('pk-auth-pass');if(name)name.disabled=!!busy;if(pass)pass.disabled=!!busy;
  }

  function stopTimer(){if(timer){clearInterval(timer);timer=null}}

  function resetProgress(){
    active=false;stopTimer();percent=0;lastMessage='';setFormBusy(false);
    var box=byId('pk-login-progress');if(box)box.hidden=true;
    var retry=byId('pk-login-progress-retry');if(retry)retry.hidden=true;
    var pass=byId('pk-auth-pass');if(pass){pass.focus();pass.select()}
  }

  function startProgress(){
    if(active)return;active=true;startedAt=Date.now();percent=0;lastMessage='';setFormBusy(true);
    setProgress(18,'CONTACTANDO SERVIDOR','Enviando tus credenciales a POKEROL…');
    timer=setInterval(function(){
      if(!active)return;
      var elapsed=(Date.now()-startedAt)/1000;
      if(elapsed<2)setProgress(Math.min(30,18+elapsed*6),'CONTACTANDO SERVIDOR','Conexión WebSocket activa. Enviando credenciales…');
      else if(elapsed<5)setProgress(Math.min(48,30+(elapsed-2)*6),'VALIDANDO CUENTA','Esperando respuesta de autenticación…');
      else if(elapsed<10)setProgress(Math.min(68,48+(elapsed-5)*4),'ABRIENDO SESIÓN','La cuenta respondió; esperando personaje…');
      else if(elapsed<15)setProgress(Math.min(82,68+(elapsed-10)*2.8),'CARGANDO PERSONAJE','Esperando confirmación del personaje…','pkLoginSlow');
      else if(elapsed<20)setProgress(Math.min(90,82+(elapsed-15)*1.6),'ESPERANDO RESPUESTA','El servidor sigue procesando la solicitud…','pkLoginSlow');
      else if(elapsed<45)setProgress(Math.min(96,90+(elapsed-20)*0.24),'CREANDO / VALIDANDO','La primera creación puede tardar más mientras el servidor guarda la cuenta y el personaje…','pkLoginSlow');
      else if(elapsed<60)setProgress(Math.min(99,96+(elapsed-45)*0.2),'ESPERANDO CONFIRMACIÓN','La conexión sigue activa. Esperando la confirmación final del servidor…','pkLoginSlow');
      else failProgress('El servidor no confirmó el acceso en 60 segundos. Puedes reintentar sin recargar la página.');
    },400);
  }

  function finishProgress(){
    if(!active)return;active=false;stopTimer();setProgress(100,'LISTO','Entrando a Kanto…','pkLoginDone');
    setTimeout(function(){var box=byId('pk-login-progress');if(box)box.hidden=true},650);
  }

  function friendlyFailure(value){
    var v=clean(value);
    if(/username.*password.*incorrect|username\/password.*incorrect|password.*incorrect|incorrect.*password|invalid.*password|authentication.*fail|login.*fail|credentials.*invalid/i.test(v))return 'Nombre de entrenador o clave incorrectos.';
    if(/no account|account.*not found|not found.*account|unknown account|does not exist/i.test(v))return 'Esa cuenta no existe en este servidor. Usa NUEVO JUGADOR para crearla.';
    if(/too many authentication|throttle|too many.*attempt/i.test(v))return 'Demasiados intentos fallidos. Espera un momento antes de volver a intentar.';
    if(/already exists|already taken/i.test(v))return 'Ese nombre ya está registrado. Elige otro o entra con esa cuenta.';
    if(/cannot create/i.test(v))return 'No se pudo crear la cuenta.';
    return v||'No se pudo iniciar sesión.';
  }

  function failProgress(message){
    active=false;stopTimer();percent=100;setProgress(100,'NO SE PUDO ENTRAR',friendlyFailure(message).slice(0,180),'pkLoginError');setFormBusy(false);
    var retry=byId('pk-login-progress-retry');if(retry){retry.hidden=false;retry.textContent='REINTENTAR'}
  }

  function parseServerText(text){
    var value=clean(text);if(!value||value===lastMessage)return;lastMessage=value;
    if(!active)return;
    if(/you can now log|account.*created|created.*account/i.test(value))setProgress(58,'CUENTA CREADA','Entrando con tu nuevo entrenador…');
    if(/you become\s+/i.test(value)){setProgress(94,'PERSONAJE CARGADO','Preparando Kanto…');setTimeout(finishProgress,100);return}
    if(/username.*password.*incorrect|username\/password.*incorrect|password.*incorrect|incorrect.*password|invalid.*password|authentication.*fail|login.*fail|credentials.*invalid|already exists|already taken|no account|account.*not found|not found.*account|unknown account|does not exist|too many authentication|throttle|too many.*attempt|cannot create/i.test(value)){failProgress(value);return}
  }

  function watchOutput(){
    if(observerBound)return true;
    var target=byId('messagewindow')||document.body;if(!target)return false;
    observerBound=true;
    parseServerText(target.textContent||'');
    new MutationObserver(function(records){records.forEach(function(r){Array.from(r.addedNodes||[]).forEach(function(n){parseServerText(n.textContent||'')})})}).observe(target,{childList:true,subtree:true});
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
      watchOutput();
    }).observe(root,{childList:true,subtree:true});
    var form=byId('pk-auth-form');if(form)bindForm(form);watchOutput();
  }

  function init(){watchOnboarding();var tries=0;(function waitOutput(){tries++;if(watchOutput())return;if(tries<100)setTimeout(waitOutput,100)})()}

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
