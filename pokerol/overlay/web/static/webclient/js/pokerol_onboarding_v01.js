(function(){
  'use strict';

  var BUILD='0.1.0-simplified-login-oak-intro';
  var FEMALE_SRC='data:image/png;base64,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';
  var OAK_SRC='https://play.pokemonshowdown.com/sprites/trainers/oak.png';
  var root=null, body=null, statusNode=null, authMode='', pendingName='', pendingPassword='', loggedIn=false, currentUser='';
  var defaultMaleSrc='';
  var tutorialNode=null, tutorialStep=0;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).trim()}
  function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function normalizeUser(v){return clean(v).replace(/\s+/g,'_')}
  function profileKey(name){return 'pokerol.profile.'+String(name||'').toLowerCase()}
  function loadProfile(name){try{return JSON.parse(localStorage.getItem(profileKey(name))||'{}')||{}}catch(e){return {}}}
  function saveProfile(name,data){try{localStorage.setItem(profileKey(name),JSON.stringify(data||{}));localStorage.setItem('pokerol.last_user',String(name||''))}catch(e){}}
  function setStatus(text,isError){if(!statusNode)return;statusNode.textContent=text||'';statusNode.style.color=isError?'#8b2d24':'#31402d'}
  function sendRaw(command){
    if(!window.Evennia||typeof Evennia.msg!=='function'){setStatus('Todavía conectando con el servidor…',true);return false}
    try{Evennia.msg('text',[String(command||'')],{});return true}catch(e){setStatus('No pude enviar la orden al servidor.',true);return false}
  }

  function ensureRoot(){
    if(root)return root;
    root=document.createElement('div');root.id='pk-onboarding-root';root.className='pkOnboardingRoot';
    root.innerHTML='<section class="pkOnboardingCard"><header class="pkOnboardingTop"><div class="pkOnboardingBrand"><strong>POKEROL</strong><span>AVENTURA POKÉMON · KANTO</span></div><span id="pk-onboarding-build">'+BUILD+'</span></header><div id="pk-onboarding-body" class="pkOnboardingBody"></div></section>';
    document.body.appendChild(root);body=byId('pk-onboarding-body');return root;
  }

  function showWelcome(){
    ensureRoot();root.classList.remove('pkHidden');authMode='';
    body.innerHTML='<div class="pkWelcomeTitle">BIENVENIDO A POKEROL</div><div class="pkWelcomeCopy">Una aventura Pokémon persistente donde puedes explorar, hablar, investigar y combatir sin caminar casilla por casilla.</div><div class="pkOnboardingChoices"><button id="pk-new-player" class="pkOnboardingButton pkPrimary" type="button">NUEVO JUGADOR</button><button id="pk-login-player" class="pkOnboardingButton" type="button">YA TENGO CUENTA</button></div><div id="pk-auth-status" class="pkAuthStatus"></div>';
    statusNode=byId('pk-auth-status');
    byId('pk-new-player').onclick=function(){showAuth('new')};
    byId('pk-login-player').onclick=function(){showAuth('login')};
  }

  function showAuth(mode){
    authMode=mode;var title=mode==='new'?'CREAR ENTRENADOR':'CONTINUAR AVENTURA';
    body.innerHTML='<div class="pkWelcomeTitle">'+title+'</div><form id="pk-auth-form" class="pkAuthForm"><div class="pkAuthField"><label for="pk-auth-name">NOMBRE DE ENTRENADOR</label><input id="pk-auth-name" autocomplete="username" maxlength="24" placeholder="Azulith"></div><div class="pkAuthField"><label for="pk-auth-pass">CLAVE</label><input id="pk-auth-pass" type="password" autocomplete="'+(mode==='new'?'new-password':'current-password')+'" maxlength="64" placeholder="••••••••"></div><div class="pkAuthHint">Usa letras, números, guion o guion bajo. La clave no puede llevar espacios en esta prueba.</div><div id="pk-auth-status" class="pkAuthStatus"></div><div class="pkAuthActions"><button id="pk-auth-back" class="pkOnboardingButton" type="button">ATRÁS</button><button class="pkOnboardingButton pkPrimary" type="submit">'+(mode==='new'?'CREAR Y ENTRAR':'ENTRAR')+'</button></div></form>';
    statusNode=byId('pk-auth-status');
    byId('pk-auth-back').onclick=showWelcome;
    byId('pk-auth-form').onsubmit=function(ev){ev.preventDefault();submitAuth()};
    setTimeout(function(){var n=byId('pk-auth-name');if(n)n.focus()},20);
  }

  function submitAuth(){
    var name=normalizeUser(byId('pk-auth-name')&&byId('pk-auth-name').value),pass=clean(byId('pk-auth-pass')&&byId('pk-auth-pass').value);
    if(!/^[A-Za-z0-9_\-]{3,24}$/.test(name)){setStatus('El nombre debe tener 3–24 caracteres: letras, números, _ o -.',true);return}
    if(pass.length<4||/\s/.test(pass)){setStatus('La clave debe tener al menos 4 caracteres y no usar espacios.',true);return}
    pendingName=name;pendingPassword=pass;setStatus(authMode==='new'?'Creando entrenador…':'Entrando…',false);
    if(authMode==='new')sendRaw('create '+name+' '+pass);else sendRaw('connect '+name+' '+pass);
  }

  function parseFeedText(text){
    var value=String(text||'');if(!value)return;
    if(authMode==='new'&&pendingName&&/you can now log|account.*created|created.*account/i.test(value)){
      setStatus('Cuenta creada. Entrando…',false);setTimeout(function(){sendRaw('connect '+pendingName+' '+pendingPassword)},120);return;
    }
    if(/you become\s+/i.test(value)){
      var m=value.match(/you become\s+([^\n.]+)/i);currentUser=pendingName||(m&&clean(m[1]))||localStorage.getItem('pokerol.last_user')||'';loggedIn=true;onLoggedIn();return;
    }
    if(/already exists|already taken|already connected|incorrect password|invalid password|no account|not found|cannot create|error/i.test(value)&&root&&!root.classList.contains('pkHidden'))setStatus(clean(value.replace(/\s+/g,' ')).slice(0,220),true);
  }

  function observeFeed(){
    var feed=byId('messagewindow');if(!feed)return false;
    parseFeedText(feed.textContent||'');
    new MutationObserver(function(records){records.forEach(function(r){Array.from(r.addedNodes||[]).forEach(function(n){parseFeedText(n.textContent||'')})})}).observe(feed,{childList:true,subtree:true});return true;
  }

  function onLoggedIn(){
    if(!currentUser)currentUser=localStorage.getItem('pokerol.last_user')||'entrenador';
    localStorage.setItem('pokerol.last_user',currentUser);
    var profile=loadProfile(currentUser);applyGender(profile.gender||'');
    pendingPassword='';
    if(authMode==='new'||!profile.introComplete){showIntro(0)}else{
      root.classList.add('pkHidden');resumeTutorial(profile.tutorialStep||99);
      if(window.PokerolPlayableClientV01&&PokerolPlayableClientV01.requestRoomState)setTimeout(PokerolPlayableClientV01.requestRoomState,120);
    }
  }

  function maleSrc(){var img=byId('pk-player-sprite');if(!defaultMaleSrc&&img)defaultMaleSrc=img.getAttribute('src')||img.src||'';return defaultMaleSrc}
  function applyGender(gender){
    var img=byId('pk-player-sprite');if(!img)return;
    if(!defaultMaleSrc)defaultMaleSrc=img.getAttribute('src')||img.src||'';
    if(gender==='girl'){
      img.src=FEMALE_SRC;img.style.width='158px';img.style.height='138px';img.style.maxWidth='none';img.style.imageRendering='pixelated';
    }else{
      img.src=defaultMaleSrc;img.style.width='96px';img.style.height='140px';img.style.maxWidth='96px';img.style.imageRendering='pixelated';
    }
  }

  function oakLayout(text,controls){
    return '<div class="pkOakScene"><div class="pkOakPortraitWrap"><img class="pkOakPortrait" src="'+OAK_SRC+'" alt="Profesor Oak" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'"><div class="pkOakFallback">PROF.<br>OAK</div></div><div class="pkOakDialogue"><div class="pkOakName">PROF. OAK</div><div class="pkOakText">'+text+'</div><div>'+controls+'</div></div></div>';
  }

  function nextButton(label,next){return '<button id="pk-oak-next" class="pkOnboardingButton pkPrimary pkOakNext" type="button">'+label+'</button>'}

  function showIntro(step){
    ensureRoot();root.classList.remove('pkHidden');var profile=loadProfile(currentUser);
    if(step===0){
      body.innerHTML=oakLayout('¡Hola, '+esc(currentUser)+'! Soy el Profesor Oak. Estudio a las criaturas que llamamos Pokémon y cómo viven junto a nosotros.',nextButton('SIGUIENTE ▶',1));
    }else if(step===1){
      body.innerHTML=oakLayout('Kanto está lleno de personas, Pokémon, caminos y problemas que cambian con lo que haces. No todo se resuelve peleando: también puedes hablar, observar, ayudar o intentar una idea propia.',nextButton('SIGUIENTE ▶',2));
    }else if(step===2){
      body.innerHTML=oakLayout('Antes de empezar necesito saber cómo quieres que se vea tu entrenador.<div class="pkGenderGrid"><button id="pk-gender-boy" class="pkGenderChoice '+(profile.gender==='boy'?'pkSelected':'')+'" type="button"><img class="pkGenderSprite pkBoy" src="'+maleSrc()+'" alt="Entrenador chico"><span>CHICO</span></button><button id="pk-gender-girl" class="pkGenderChoice '+(profile.gender==='girl'?'pkSelected':'')+'" type="button"><img class="pkGenderSprite pkGirl" src="'+FEMALE_SRC+'" alt="Entrenadora chica"><span>CHICA</span></button></div>','');
      byId('pk-gender-boy').onclick=function(){chooseGender('boy')};byId('pk-gender-girl').onclick=function(){chooseGender('girl')};return;
    }else if(step===3){
      var who=profile.gender==='girl'?'entrenadora':'entrenador';
      body.innerHTML=oakLayout('Perfecto. Entonces tú eres '+esc(currentUser)+', '+who+' de Pueblo Paleta. Tu aventura no tiene una única ruta correcta: explora y decide qué clase de entrenador quieres ser.',nextButton('SIGUIENTE ▶',4));
    }else{
      body.innerHTML=oakLayout('Una última cosa: si quieres hacer algo que no aparezca como botón, escríbelo en ACCIÓN LIBRE. El mundo intentará resolverlo usando el lugar, los personajes y tus capacidades reales.',nextButton('COMENZAR AVENTURA',5));
    }
    var btn=byId('pk-oak-next');if(btn)btn.onclick=function(){var n=parseInt(btn.textContent&&btn.dataset.next||'',10);showIntro(next||step+1)};
    if(btn){var target=step===0?1:step===1?2:step===3?4:5;btn.onclick=function(){if(target===5)finishIntro();else showIntro(target)}}
  }

  function chooseGender(gender){
    var profile=loadProfile(currentUser);profile.gender=gender;saveProfile(currentUser,profile);applyGender(gender);showIntro(3);
  }

  function finishIntro(){
    var profile=loadProfile(currentUser);profile.introComplete=true;profile.tutorialStep=1;saveProfile(currentUser,profile);root.classList.add('pkHidden');
    if(window.PokerolPlayableClientV01&&PokerolPlayableClientV01.requestRoomState)setTimeout(PokerolPlayableClientV01.requestRoomState,120);
    setTimeout(function(){startTutorial(1)},250);
  }

  function ensureTutorial(){
    if(tutorialNode)return tutorialNode;tutorialNode=document.createElement('aside');tutorialNode.id='pk-tutorial-card';tutorialNode.className='pkTutorialCard pkHidden';document.body.appendChild(tutorialNode);return tutorialNode;
  }
  function clearFocus(){document.querySelectorAll('.pkTutorialFocus').forEach(function(el){el.classList.remove('pkTutorialFocus')})}
  function focusSelector(sel){clearFocus();var el=document.querySelector(sel);if(el)el.classList.add('pkTutorialFocus')}
  function updateProfileStep(step){var p=loadProfile(currentUser);p.tutorialStep=step;saveProfile(currentUser,p)}
  function startTutorial(step){
    tutorialStep=Number(step)||1;var n=ensureTutorial();n.classList.remove('pkHidden');clearFocus();
    if(tutorialStep===1){n.innerHTML='<div class="pkTutorialStep">TUTORIAL 1/4</div><div class="pkTutorialTitle">MIRA LA ESCENA</div><div class="pkTutorialText">Pulsa <b>MIRAR</b>. El narrador te dirá qué hay en el lugar y qué puedes percibir.</div><button class="pkTutorialSkip" type="button">SALTAR TUTORIAL</button>';focusSelector('#pk-look')}
    else if(tutorialStep===2){n.innerHTML='<div class="pkTutorialStep">TUTORIAL 2/4</div><div class="pkTutorialTitle">MUÉVETE</div><div class="pkTutorialText">Los botones <b>IR · ...</b> son las salidas reales del lugar. Elige una para cambiar de Room; no hay animación de caminar.</div><button class="pkTutorialSkip" type="button">SALTAR TUTORIAL</button>';focusSelector('.pkExitButton')}
    else if(tutorialStep===3){var actor=document.querySelector('.pkActor');if(!actor){setTimeout(function(){advanceTutorial(4)},350);return}n.innerHTML='<div class="pkTutorialStep">TUTORIAL 3/4</div><div class="pkTutorialTitle">INTERACTÚA</div><div class="pkTutorialText">Personas, Pokémon y objetos delante de ti son hotspots. Haz clic sobre uno para hablar, observar o usarlo.</div><button class="pkTutorialSkip" type="button">SALTAR TUTORIAL</button>';actor.classList.add('pkTutorialFocus')}
    else if(tutorialStep===4){n.innerHTML='<div class="pkTutorialStep">TUTORIAL 4/4</div><div class="pkTutorialTitle">ACCIÓN LIBRE</div><div class="pkTutorialText">Escribe abajo algo que quieras intentar. Por ejemplo: <b>reviso el camino buscando huellas</b>. No estás limitado a los botones.</div><button class="pkTutorialSkip" type="button">TERMINAR TUTORIAL</button>';focusSelector('#inputfield')}
    else{finishTutorial();return}
    var skip=n.querySelector('.pkTutorialSkip');if(skip)skip.onclick=finishTutorial;updateProfileStep(tutorialStep);
  }
  function advanceTutorial(step){startTutorial(step)}
  function finishTutorial(){clearFocus();tutorialStep=99;updateProfileStep(99);var n=ensureTutorial();n.innerHTML='<div class="pkTutorialStep">TUTORIAL COMPLETO</div><div class="pkTutorialTitle">TU AVENTURA EMPIEZA AQUÍ</div><div class="pkTutorialText">Explora Kanto. El juego te irá enseñando combate, captura y multiplayer cuando aparezcan.</div>';setTimeout(function(){n.classList.add('pkHidden')},2800)}
  function resumeTutorial(step){if(Number(step)>0&&Number(step)<99)setTimeout(function(){startTutorial(Number(step))},350)}

  function bindTutorialProgress(){
    document.addEventListener('click',function(ev){
      if(!loggedIn||tutorialStep<=0||tutorialStep>=99)return;
      var t=ev.target;
      if(tutorialStep===1&&t.closest&&t.closest('#pk-look'))setTimeout(function(){advanceTutorial(2)},300);
      else if(tutorialStep===2&&t.closest&&t.closest('.pkExitButton'))setTimeout(function(){advanceTutorial(3)},650);
      else if(tutorialStep===3&&t.closest&&t.closest('.pkActor'))setTimeout(function(){advanceTutorial(4)},350);
      else if(tutorialStep===4&&t.closest&&t.closest('#inputsend'))setTimeout(finishTutorial,250);
    },true);
    var field=byId('inputfield');if(field)field.addEventListener('keydown',function(ev){if(tutorialStep===4&&ev.key==='Enter'&&!ev.shiftKey&&clean(field.value))setTimeout(finishTutorial,250)},true);
  }

  function detectExistingSession(){
    var feed=byId('messagewindow');var txt=feed&&feed.textContent||'';var m=txt.match(/you become\s+([^\n.]+)/i);
    if(m){currentUser=clean(m[1])||localStorage.getItem('pokerol.last_user')||'';loggedIn=true;onLoggedIn();return true}
    var room=byId('pk-room-name');var last=localStorage.getItem('pokerol.last_user')||'';
    if(room&&last&&!/conectando/i.test(room.textContent||'')){currentUser=last;loggedIn=true;onLoggedIn();return true}
    return false;
  }

  function init(){
    ensureRoot();var trainer=byId('pk-player-sprite');if(trainer)defaultMaleSrc=trainer.getAttribute('src')||trainer.src||'';
    bindTutorialProgress();var tries=0;(function waitFeed(){tries++;if(observeFeed()){if(!detectExistingSession())showWelcome();return}if(tries<80)setTimeout(waitFeed,100);else showWelcome()})();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
  window.PokerolOnboardingV01={BUILD:BUILD,showWelcome:showWelcome,applyGender:applyGender,startTutorial:startTutorial};
})();
