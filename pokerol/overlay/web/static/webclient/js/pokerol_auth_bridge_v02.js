(function(){
  'use strict';

  var BUILD='0.2.0-authoritative-auth-handshake';
  var auth=null;
  var pollTimer=null;
  var feedObserver=null;
  var emitterBound=false;

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

  function isConnected(){
    try{return !!(window.Evennia&&typeof Evennia.isConnected==='function'&&Evennia.isConnected())}catch(e){return false}
  }

  function formMode(form){
    var button=form&&form.querySelector('button[type="submit"]');
    var text=clean(button&&button.textContent).toUpperCase();
    return /CREAR/.test(text)?'new':'login';
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

  function setProgress(label,detail,error){
    var box=byId('pk-login-progress');
    if(!box)return;
    box.hidden=false;
    box.classList.remove('pkLoginSlow','pkLoginError','pkLoginDone');
    if(error)box.classList.add('pkLoginError');
    var lab=byId('pk-login-progress-label'),det=byId('pk-login-progress-detail'),pct=byId('pk-login-progress-pct'),bar=byId('pk-login-progress-bar');
    if(lab)lab.textContent=label||'CONECTANDO';
    if(det)det.textContent=detail||'';
    if(error){if(pct)pct.textContent='100%';if(bar)bar.style.width='100%'}
  }

  function syntheticText(text){
    var feed=byId('messagewindow');if(!feed)return;
    var row=document.createElement('div');row.className='pkAuthBridgeSignal';row.textContent=String(text||'');feed.appendChild(row);
  }

  function stopPolling(){if(pollTimer){clearTimeout(pollTimer);pollTimer=null}}

  function fail(message){
    if(!auth||!auth.active)return;
    auth.active=false;stopPolling();
    var msg=clean(message)||'No se pudo completar el acceso.';
    setStatus(msg,true);setProgress('NO SE PUDO ENTRAR',msg,true);setFormBusy(false);
    syntheticText(msg);
    var retry=byId('pk-login-progress-retry');if(retry){retry.hidden=false;retry.textContent='REINTENTAR'}
  }

  function succeed(name){
    if(!auth||!auth.active)return;
    var resolved=clean(name||auth.name)||auth.name;
    auth.active=false;stopPolling();
    try{sessionStorage.removeItem('pokerol.manual_logout')}catch(e){}
    setStatus('Acceso confirmado.',false);
    syntheticText('You become '+resolved+'.');
  }

  function probe(delay){
    stopPolling();
    pollTimer=setTimeout(function(){
      if(!auth||!auth.active)return;
      if(Date.now()-auth.startedAt>55000){fail('El servidor no confirmó el acceso.');return}
      if(!isConnected()){pollTimer=setTimeout(function(){probe(0)},250);return}
      sendRaw('pokerol-auth-state '+auth.name);
      pollTimer=setTimeout(function(){probe(0)},450);
    },Math.max(0,Number(delay)||0));
  }

  function resumeAfterCleanReconnect(){
    if(!auth||!auth.active)return;
    auth.phase='preflight';auth.createSent=false;auth.connectSent=false;
    setProgress('VERIFICANDO SESIÓN','Sesión anterior cerrada. Verificando la cuenta…',false);
    probe(120);
  }

  function reconnectAfterLogout(){
    var started=Date.now();
    (function waitClosed(){
      if(!auth||!auth.active)return;
      if(!isConnected()){
        setTimeout(function(){
          try{Evennia.connect()}catch(e){}
          var reopenStarted=Date.now();
          (function waitOpen(){
            if(!auth||!auth.active)return;
            if(isConnected()){setTimeout(resumeAfterCleanReconnect,180);return}
            if(Date.now()-reopenStarted>8000){fail('No se pudo reabrir una sesión limpia con el servidor.');return}
            setTimeout(waitOpen,120);
          })();
        },300);
        return;
      }
      if(Date.now()-started>8000){fail('No se pudo cerrar la sesión anterior.');return}
      setTimeout(waitClosed,120);
    })();
  }

  function clearStaleSession(accountName){
    if(!auth||!auth.active||auth.phase==='recovering')return;
    auth.phase='recovering';stopPolling();
    setStatus('Cerrando la sesión anterior…',false);
    setProgress('CERRANDO SESIÓN ANTERIOR','El navegador todavía estaba autenticado como '+(clean(accountName)||'otro entrenador')+'. Cerrándola antes de continuar…',false);
    if(!sendRaw('quit')){fail('No se pudo cerrar la sesión anterior.');return}
    reconnectAfterLogout();
  }

  function sendCreate(){
    if(!auth||!auth.active||auth.createSent)return;
    auth.createSent=true;auth.phase='creating';
    setStatus('Creando entrenador…',false);setProgress('CREANDO ENTRENADOR','Guardando la nueva cuenta en POKEROL…',false);
    if(!sendRaw('create '+auth.name+' '+auth.password)){fail('No se pudo enviar la creación al servidor.');return}
    probe(220);
  }

  function sendConnect(){
    if(!auth||!auth.active||auth.connectSent)return;
    auth.connectSent=true;auth.phase='connecting';
    setStatus('Entrando…',false);setProgress('ABRIENDO SESIÓN','Validando la cuenta y cargando el entrenador…',false);
    if(!sendRaw('connect '+auth.name+' '+auth.password)){fail('No se pudo enviar el acceso al servidor.');return}
    probe(220);
  }

  function onAuthState(args){
    var packet=packetFrom(args);
    if(clean(packet.status).toUpperCase()!=='AUTH_STATE'||!auth||!auth.active)return true;
    if(packet.requested_name&&lower(packet.requested_name)!==lower(auth.name))return true;

    if(auth.phase==='preflight'){
      if(packet.logged_in){clearStaleSession(packet.account_name);return true}
      if(auth.mode==='new'){
        if(packet.account_exists){fail('Ese nombre ya está registrado. Elige otro o usa CONTINUAR AVENTURA.');return true}
        sendCreate();return true;
      }
      if(!packet.account_exists){fail('Esa cuenta no existe en este servidor. Usa NUEVO JUGADOR para crearla.');return true}
      sendConnect();return true;
    }

    if(auth.phase==='creating'){
      if(packet.logged_in){
        if(lower(packet.account_name)===lower(auth.name))succeed(packet.character_name||packet.account_name);
        else clearStaleSession(packet.account_name);
        return true;
      }
      if(packet.account_exists){sendConnect();return true}
      return true;
    }

    if(auth.phase==='connecting'){
      if(packet.logged_in){
        if(lower(packet.account_name)===lower(auth.name))succeed(packet.character_name||packet.account_name);
        else clearStaleSession(packet.account_name);
      }
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

    auth={active:true,mode:mode,name:name,password:password,phase:'preflight',startedAt:Date.now(),createSent:false,connectSent:false};
    setFormBusy(true);setStatus(mode==='new'?'Comprobando nombre…':'Comprobando cuenta…',false);
    setProgress('VERIFICANDO CUENTA','Consultando el estado real de la sesión y de la cuenta…',false);
    probe(80);
  }

  function bindForm(form){
    if(!form||form.dataset.pkAuthBridge==='1')return;
    form.dataset.pkAuthBridge='1';
    form.onsubmit=function(ev){ev.preventDefault();beginAuth(form);return false};
  }

  function watchForms(){
    var root=byId('pk-onboarding-root')||document.body;
    var bind=function(){var form=byId('pk-auth-form');if(form)bindForm(form)};
    bind();
    new MutationObserver(bind).observe(root,{childList:true,subtree:true});
  }

  function parseFeedText(value){
    if(!auth||!auth.active)return;
    var text=clean(value);if(!text)return;
    if(/you become\s+/i.test(text)){
      var m=text.match(/you become\s+([^\.\n]+)/i);var who=m&&clean(m[1]);
      if(!who||lower(who)===lower(auth.name))succeed(who||auth.name);
      return;
    }
    if(/username.*password.*incorrect|username\/password.*incorrect|password.*incorrect|incorrect.*password|invalid.*password|authentication.*fail|login.*fail|credentials.*invalid/i.test(text)){fail('Nombre de entrenador o clave incorrectos.');return}
    if(/already exists|already taken/i.test(text)&&auth.mode==='new'){fail('Ese nombre ya está registrado. Elige otro o usa CONTINUAR AVENTURA.');return}
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
