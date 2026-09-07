(function(){
  'use strict';

  var BUILD='0.2.0-event-driven-auth-progress';
  var active=false,percent=0,lastMessage='',observerBound=false;

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
  function setFormBusy(busy){
    var form=byId('pk-auth-form');if(!form)return;
    var submit=form.querySelector('button[type="submit"]');
    if(submit)submit.disabled=!!busy;
    var name=byId('pk-auth-name'),pass=byId('pk-auth-pass');
    if(name)name.disabled=!!busy;if(pass)pass.disabled=!!busy;
  }
  function setProgress(value,label,detail,state){
    var box=ensureProgress();if(!box)return;
    percent=Math.max(0,Math.min(100,Math.round(Number(value)||0)));
    box.hidden=false;box.classList.remove('pkLoginSlow','pkLoginError','pkLoginDone');
    if(state)box.classList.add(state);
    var bar=byId('pk-login-progress-bar'),pct=byId('pk-login-progress-pct'),lab=byId('pk-login-progress-label'),det=byId('pk-login-progress-detail');
    if(bar)bar.style.width=percent+'%';
    if(pct)pct.textContent=percent+'%';
    if(lab)lab.textContent=label||'CONECTANDO';
    if(det)det.textContent=detail||'';
    if(state==='pkLoginError'){var retry=byId('pk-login-progress-retry');if(retry)retry.hidden=false}
  }
  function resetProgress(){
    active=false;percent=0;lastMessage='';setFormBusy(false);
    var box=byId('pk-login-progress');if(box)box.hidden=true;
    var retry=byId('pk-login-progress-retry');if(retry)retry.hidden=true;
    var pass=byId('pk-auth-pass');if(pass){pass.focus();pass.select()}
  }
  function startProgress(){
    active=true;percent=0;lastMessage='';setFormBusy(true);
    setProgress(10,'CONTACTANDO SERVIDOR','Enviando la solicitud de acceso…','');
  }
  function finishProgress(){
    active=false;setProgress(100,'LISTO','Entrando a Kanto…','pkLoginDone');
    setTimeout(function(){var box=byId('pk-login-progress');if(box)box.hidden=true},650);
  }
  function parseServerText(text){
    var value=clean(text);if(!value||value===lastMessage)return;lastMessage=value;
    if(!active)return;
    if(/you can now log|account.*created|created.*account/i.test(value))setProgress(64,'CUENTA CREADA','Abriendo la sesión…','');
    if(/you become\s+/i.test(value)){setProgress(96,'PERSONAJE CARGADO','Preparando Kanto…','');setTimeout(finishProgress,80)}
  }
  function watchOutput(){
    if(observerBound)return true;
    var target=byId('messagewindow')||document.body;if(!target)return false;
    observerBound=true;
    new MutationObserver(function(records){records.forEach(function(r){Array.from(r.addedNodes||[]).forEach(function(n){parseServerText(n.textContent||'')})})}).observe(target,{childList:true,subtree:true});
    return true;
  }
  function bindForm(form){
    if(!form||form.dataset.pkProgressBound==='1')return;
    form.dataset.pkProgressBound='1';ensureProgress();
    form.addEventListener('submit',function(){if(validAuthForm(form))startProgress()},false);
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
  window.addEventListener('pokerol-auth-progress',function(ev){
    var d=ev&&ev.detail||{};
    active=d.state!=='pkLoginDone'&&d.state!=='pkLoginError';
    setProgress(d.percent,d.label,d.detail,d.state);
    if(d.state==='pkLoginDone')setTimeout(function(){var box=byId('pk-login-progress');if(box)box.hidden=true},650);
    if(d.state==='pkLoginError')setFormBusy(false);
  });
  function init(){watchOnboarding();var tries=0;(function waitOutput(){tries++;if(watchOutput())return;if(tries<100)setTimeout(waitOutput,100)})()}
  window.PokerolLoginProgressV01=Object.freeze({BUILD:BUILD,reset:resetProgress});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
