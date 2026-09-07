(function(){
  'use strict';

  var BUILD='0.4.0-direct-auth-no-poll-loop';
  var auth=null,feedObserver=null,emitterBound=false;

  function byId(id){return document.getElementById(id)}
  function clean(value){return String(value==null?'':value).replace(/\s+/g,' ').trim()}
  function normalizeUser(value){return clean(value).replace(/\s+/g,'_')}
  function lower(value){return clean(value).toLowerCase()}
  function packetFrom(args){
    var packet=args&&args.length?args[0]:args;
    if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
    return packet&&typeof packet==='object'?packet:{};
  }
  function sendRaw(command){
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{Evennia.msg('text',[String(command||'')],{});return true}catch(e){return false}
  }
  function formMode(form){
    var button=form&&form.querySelector('button[type="submit"]');
    var text=clean(button&&button.textContent).toUpperCase();
    var body=form&&form.closest('.pkOnboardingBody');
    var all=clean(body&&body.textContent).toUpperCase();
    return /CREAR/.test(text)||/CREAR ENTRENADOR/.test(all)?'new':'login';
  }
  function setStatus(text,isError){
    var node=byId('pk-auth-status');
    if(node){node.textContent=text||'';node.style.color=isError?'#8b2d24':'#31402d'}
  }
  function setFormBusy(busy){
    var form=byId('pk-auth-form');if(!form)return;
    var name=byId('pk-auth-name'),pass=byId('pk-auth-pass'),button=form.querySelector('button[type="submit"]');
    if(name)name.disabled=!!busy;
    if(pass)pass.disabled=!!busy;
    if(button){
      button.disabled=!!busy;
      if(busy)button.textContent=auth&&auth.mode==='new'?'CREANDO…':'ENTRANDO…';
      else button.textContent=auth&&auth.mode==='new'?'CREAR Y ENTRAR':'ENTRAR';
    }
  }
  function progress(percent,label,detail,state){
    try{
      window.dispatchEvent(new CustomEvent('pokerol-auth-progress',{detail:{
        percent:Number(percent)||0,label:label||'',detail:detail||'',state:state||''
      }}));
    }catch(e){}
    var box=byId('pk-login-progress');if(!box)return;
    box.hidden=false;box.classList.remove('pkLoginSlow','pkLoginError','pkLoginDone');
    if(state)box.classList.add(state);
    var lab=byId('pk-login-progress-label'),det=byId('pk-login-progress-detail'),pct=byId('pk-login-progress-pct'),bar=byId('pk-login-progress-bar');
    if(lab)lab.textContent=label||'CONECTANDO';
    if(det)det.textContent=detail||'';
    if(pct)pct.textContent=Math.max(0,Math.min(100,Math.round(Number(percent)||0)))+'%';
    if(bar)bar.style.width=Math.max(0,Math.min(100,Math.round(Number(percent)||0)))+'%';
  }
  function syntheticText(text){
    var feed=byId('messagewindow');if(!feed)return;
    var row=document.createElement('div');row.className='pkAuthBridgeSignal';row.textContent=String(text||'');feed.appendChild(row);
  }
  function clearTimers(){
    if(!auth)return;
    (auth.timers||[]).forEach(function(t){clearTimeout(t)});
    auth.timers=[];
  }
  function later(fn,ms){
    if(!auth)return null;
    var t=setTimeout(fn,ms);
    auth.timers.push(t);
    return t;
  }
  function fail(message){
    if(!auth||!auth.active)return;
    auth.active=false;clearTimers();
    var msg=clean(message)||'No se pudo completar el acceso.';
    setStatus(msg,true);progress(100,'NO SE PUDO ENTRAR',msg,'pkLoginError');setFormBusy(false);
    var retry=byId('pk-login-progress-retry');if(retry){retry.hidden=false;retry.textContent='REINTENTAR'}
  }
  function succeed(characterName){
    if(!auth||!auth.active)return;
    var trainerName=clean(auth.name),character=clean(characterName)||trainerName;
    auth.active=false;clearTimers();
    try{sessionStorage.removeItem('pokerol.manual_logout')}catch(e){}
    try{localStorage.setItem('pokerol.last_user',trainerName)}catch(e){}
    setStatus('Acceso confirmado.',false);progress(100,'LISTO','Entrando a Kanto…','pkLoginDone');
    try{window.dispatchEvent(new CustomEvent('pokerol-authenticated',{detail:{trainerName:trainerName,characterName:character}}))}catch(e){}
    syntheticText('You become '+trainerName+'.');
  }
  function checkState(delay){
    later(function(){
      if(!auth||!auth.active)return;
      sendRaw('pokerol-auth-state '+auth.name);
    },delay);
  }
  function sendCreate(){
    if(!auth||!auth.active||auth.createSent)return;
    auth.createSent=true;auth.phase='creating';
    setStatus('Creando entrenador…',false);
    progress(55,'CREANDO ENTRENADOR','El servidor está creando la cuenta…','');
    if(!sendRaw('create '+auth.name+' '+auth.password)){fail('No se pudo enviar la creación al servidor.');return}
    checkState(700);checkState(1800);
  }
  function sendConnect(){
    if(!auth||!auth.active||auth.connectSent)return;
    auth.connectSent=true;auth.phase='connecting';
    setStatus('Entrando…',false);
    progress(72,'ABRIENDO SESIÓN','Validando la clave y cargando el entrenador…','');
    if(!sendRaw('connect '+auth.name+' '+auth.password)){fail('No se pudo enviar el acceso al servidor.');return}
    checkState(650);checkState(1600);checkState(3200);
  }
  function fallbackDirect(){
    if(!auth||!auth.active||auth.phase!=='preflight')return;
    progress(38,'VALIDANDO CUENTA','La comprobación previa no respondió; entrando por la ruta directa…','pkLoginSlow');
    if(auth.mode==='new')sendCreate();else sendConnect();
  }
  function onAuthState(args){
    var packet=packetFrom(args);
    if(clean(packet.status).toUpperCase()!=='AUTH_STATE'||!auth||!auth.active)return true;
    if(packet.requested_name&&lower(packet.requested_name)!==lower(auth.name))return true;

    if(packet.logged_in){
      if(!packet.account_name||lower(packet.account_name)===lower(auth.name)){
        succeed(packet.character_name||packet.account_name||auth.name);
      }else{
        fail('El navegador sigue conectado como '+clean(packet.account_name)+'. Pulsa SALIR una vez y vuelve a entrar.');
      }
      return true;
    }

    if(auth.phase==='preflight'){
      progress(32,'CUENTA COMPROBADA','El servidor respondió. Continuando…','');
      if(auth.mode==='new'){
        if(packet.account_exists){fail('Ese nombre ya está registrado. Elige otro o usa CONTINUAR AVENTURA.');return true}
        sendCreate();return true;
      }
      if(!packet.account_exists){fail('Esa cuenta no existe en este servidor. Usa NUEVO JUGADOR para crearla.');return true}
      sendConnect();return true;
    }

    if(auth.phase==='creating'){
      if(packet.account_exists){progress(64,'CUENTA CREADA','La cuenta existe. Abriendo sesión…','');sendConnect()}
      return true;
    }
    return true;
  }
  function beginAuth(form){
    if(auth&&auth.active)return;
    var name=normalizeUser(byId('pk-auth-name')&&byId('pk-auth-name').value);
    var password=String(byId('pk-auth-pass')&&byId('pk-auth-pass').value||'').trim();
    var mode=formMode(form);
    if(!/^[A-Za-z0-9_\-]{3,24}$/.test(name)){setStatus('El nombre debe tener 3–24 caracteres: letras, números, _ o -.',true);return}
    if(password.length<4||/\s/.test(password)){setStatus('La clave debe tener al menos 4 caracteres y no usar espacios.',true);return}

    auth={active:true,mode:mode,name:name,password:password,phase:'preflight',startedAt:Date.now(),createSent:false,connectSent:false,timers:[]};
    setFormBusy(true);setStatus(mode==='new'?'Comprobando nombre…':'Comprobando cuenta…',false);
    progress(18,'CONTACTANDO SERVIDOR','Enviando una comprobación corta al servidor…','');

    /* Important: do not gate auth on Evennia.isConnected(). That test was
       intermittently false even while the websocket transport was usable. */
    sendRaw('pokerol-auth-state '+name);
    later(fallbackDirect,1200);
    later(function(){
      if(auth&&auth.active)fail('El servidor no respondió al acceso en 15 segundos. La solicitud se canceló; reintenta.');
    },15000);
  }
  function bindForm(form){
    if(!form||form.dataset.pkAuthBridge==='1')return;
    form.dataset.pkAuthBridge='1';
    form.onsubmit=function(ev){ev.preventDefault();beginAuth(form);return false};
  }
  function watchForms(){
    var root=byId('pk-onboarding-root')||document.body;
    var bind=function(){var form=byId('pk-auth-form');if(form)bindForm(form)};
    bind();new MutationObserver(bind).observe(root,{childList:true,subtree:true});
  }
  function parseFeedText(value){
    if(!auth||!auth.active)return;
    var text=clean(value);if(!text)return;
    if(/you become\s+/i.test(text)){
      var m=text.match(/you become\s+([^.\n]+)/i),who=m&&clean(m[1]);
      succeed(who||auth.name);return;
    }
    if(/you can now log|account.*created|created.*account/i.test(text)&&auth.mode==='new'){
      progress(64,'CUENTA CREADA','La cuenta fue creada. Abriendo sesión…','');sendConnect();return;
    }
    if(/username.*password.*incorrect|username\/password.*incorrect|password.*incorrect|incorrect.*password|invalid.*password|authentication.*fail|login.*fail|credentials.*invalid/i.test(text)){fail('Nombre de entrenador o clave incorrectos.');return}
    if(/already exists|already taken/i.test(text)&&auth.mode==='new'){fail('Ese nombre ya está registrado. Elige otro o usa CONTINUAR AVENTURA.');return}
    if(/no account|account.*not found|unknown account|does not exist/i.test(text)&&auth.mode==='login'){fail('Esa cuenta no existe en este servidor. Usa NUEVO JUGADOR para crearla.');return}
    if(/cannot create|creation.*fail|could not create/i.test(text)&&auth.mode==='new'){fail('No se pudo crear la cuenta.');return}
  }
  function watchFeed(){
    if(feedObserver)return;
    var feed=byId('messagewindow');if(!feed){setTimeout(watchFeed,100);return}
    feedObserver=new MutationObserver(function(records){
      records.forEach(function(record){Array.from(record.addedNodes||[]).forEach(function(node){parseFeedText(node.textContent||'')})});
    });
    feedObserver.observe(feed,{childList:true,subtree:true});
  }
  function bindEmitter(){
    if(emitterBound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_auth_state',onAuthState);emitterBound=true;return true;
  }
  function init(){
    watchForms();watchFeed();
    var tries=0;(function waitEmitter(){tries++;if(bindEmitter())return;if(tries<240)setTimeout(waitEmitter,50)})();
  }

  window.PokerolAuthBridgeV02=Object.freeze({BUILD:BUILD});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
