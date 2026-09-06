(function(){
  'use strict';
  var BUILD='0.4.1-pokerol-native-ui-protocol';
  var emitterBound=false;
  var lastSnapshot=null;
  var lastActions=null;
  var lastNarratedRoomKey='';
  var currentSpeaker='NARRADOR';

  function byId(id){return document.getElementById(id)}
  function clean(value){return String(value==null?'':value).replace(/\s+/g,' ').trim()}
  function packetFrom(args){var packet=args&&args.length?args[0]:args;if(Array.isArray(packet)&&packet.length===1)packet=packet[0];return packet&&typeof packet==='object'?packet:{}}
  function scrollFeed(){var feed=byId('messagewindow');if(feed)feed.scrollTop=feed.scrollHeight}
  function appendFeed(value,kind,allowHtml){
    var feed=byId('messagewindow');if(!feed)return;
    var raw=String(value==null?'':value);if(!raw.trim())return;
    var row=document.createElement('div');row.className='pkFeedLine pkFeed-'+(kind||'world');
    if(allowHtml)row.innerHTML=raw;else row.textContent=raw;
    feed.appendChild(row);while(feed.children.length>180)feed.removeChild(feed.firstChild);scrollFeed();
  }
  function setDialogue(value,speaker,allowHtml){
    var textNode=byId('pk-dialogue-text'),speakerNode=byId('pk-speaker');
    var raw=String(value==null?'':value);if(!raw.trim())return;
    currentSpeaker=clean(speaker||currentSpeaker||'NARRADOR')||'NARRADOR';
    if(speakerNode)speakerNode.textContent=currentSpeaker.toUpperCase();
    if(textNode){if(allowHtml)textNode.innerHTML=raw;else textNode.textContent=raw;textNode.scrollTop=0}
  }
  function appendSystem(text){appendFeed(text,'system',false)}
  function appendCommand(text){appendFeed('> '+text,'command',false)}

  function send(command){
    var field=byId('inputfield'),button=byId('inputsend');if(!field||!button)return false;
    var outgoing=String(command||'').trim();if(!outgoing)return false;
    appendCommand(outgoing);setDialogue('Intentas: '+outgoing,'ENTRENADOR',false);
    field.value=outgoing;field.dispatchEvent(new Event('input',{bubbles:true}));button.click();
    window.setTimeout(function(){field.focus()},40);return true;
  }
  function bind(id,command){var el=byId(id);if(el)el.addEventListener('click',function(){send(command)})}

  function rowName(row){return clean(typeof row==='string'?row:(row&&(row.name||row.label||row.target||row.key)))}
  function imageOf(row){
    if(!row||typeof row!=='object')return '';
    var sprite=row.sprite||{};
    return clean(row.scene_sprite||row.image||row.portrait||row.sprite_url||sprite.front||sprite.icon||'');
  }
  function actionRows(packet){var actions=(packet&&(packet.available_actions||packet.actions))||[];return Array.isArray(actions)?actions:[]}
  function commandForTarget(name,actions){
    var wanted=clean(name).toLowerCase();
    var matches=actions.filter(function(a){return a&&clean(a.target||a.name).toLowerCase()===wanted&&clean(a.command)});
    var priority=['TALK','INTERACT','USE','PERCEPTION'];
    for(var p=0;p<priority.length;p++){
      var found=matches.find(function(a){return clean(a.kind).toUpperCase()===priority[p]});
      if(found)return clean(found.command);
    }
    if(matches[0])return clean(matches[0].command);
    return name?'observar '+name:'';
  }

  function classifyBiome(packet){
    var hay=(clean(packet.room_id)+' '+clean(packet.room_name)+' '+clean(packet.location)+' '+clean(packet.biome)+' '+clean(packet.room_description)).toLowerCase();
    if(/forest|bosque|arboleda|árbol|arbol/.test(hay))return 'forest';
    if(/water|pond|lake|river|arroyo|estanque|agua/.test(hay))return 'water';
    if(/lab|centro|mart|academ|interior|sala|tienda/.test(hay))return 'interior';
    if(/route|ruta|pradera|camino|sendero|senda/.test(hay))return 'route';
    if(/pallet|viridian|pueblo|ciudad|plaza|calle|puerta/.test(hay))return 'town';
    return 'generic';
  }
  function renderBackground(packet){
    var stage=byId('pk-stage'),bg=byId('pk-stage-bg');if(!stage||!bg)return;
    ['town','route','forest','water','interior','generic'].forEach(function(v){stage.classList.remove('pkBiome-'+v)});
    stage.classList.add('pkBiome-'+classifyBiome(packet));
    var url=clean(packet.scene_image||packet.background_image||packet.room_image||(packet.visual&&packet.visual.background)||'');
    if(url)bg.style.backgroundImage='url("'+url.replace(/"/g,'%22')+'")';else bg.style.backgroundImage='';
  }

  function renderExits(packet){
    var root=byId('pk-exit-strip');if(!root)return;root.innerHTML='';
    var exits=Array.isArray(packet.exits)?packet.exits:[];
    exits.forEach(function(row){
      var name=rowName(row);if(!name)return;
      var command=clean(row&&typeof row==='object'&&(row.command||row.key||row.name))||name;
      var btn=document.createElement('button');btn.type='button';btn.className='pkExitButton';btn.textContent='IR · '+name.toUpperCase();btn.addEventListener('click',function(){send(command)});root.appendChild(btn);
    });
  }

  function renderActors(packet){
    var root=byId('pk-actor-layer');if(!root)return;root.innerHTML='';
    var npcs=Array.isArray(packet.visible_npcs)?packet.visible_npcs:(Array.isArray(packet.people)?packet.people:[]);
    var objects=Array.isArray(packet.visible_objects)?packet.visible_objects:(Array.isArray(packet.objects)?packet.objects:[]);
    var actions=actionRows(packet),rows=[];
    npcs.forEach(function(r){rows.push({row:r,kind:'NPC'})});
    objects.forEach(function(r){
      var name=rowName(r);if(!name||/pokeroladmin/i.test(name))return;
      if(!rows.some(function(x){return rowName(x.row)===name}))rows.push({row:r,kind:'OBJECT'});
    });
    var count=Math.min(rows.length,5);rows.slice(0,5).forEach(function(entry,index){
      var row=entry.row,name=rowName(row);if(!name)return;
      var actor=document.createElement('button');actor.type='button';actor.className='pkActor';actor.dataset.kind=entry.kind;
      var x=count<=1?50:18+(64*(index/(count-1)));actor.style.left=x+'%';
      var img=imageOf(row);
      if(img){var image=document.createElement('img');image.className='pkActorSprite';image.src=img;image.alt=name;actor.appendChild(image)}
      else{var placeholder=document.createElement('span');placeholder.className='pkActorPlaceholder';actor.appendChild(placeholder)}
      var label=document.createElement('span');label.className='pkActorLabel';label.textContent=name;actor.appendChild(label);
      var command=commandForTarget(name,actions);actor.addEventListener('click',function(){if(command)send(command);else setDialogue('Observas a '+name+'.','NARRADOR',false)});root.appendChild(actor);
    });
  }

  function renderActions(packet){
    lastActions=packet||lastActions||{};var root=byId('pk-context-actions');if(!root)return;root.innerHTML='';
    var actions=actionRows(packet);if(!actions.length){var empty=document.createElement('span');empty.className='pkNoActions';empty.textContent='Puedes escribir una acción libre abajo.';root.appendChild(empty);return}
    actions.slice(0,8).forEach(function(action){
      if(!action)return;var command=clean(action.command),label=clean(action.label||action.name||command||'ACCIÓN');if(!command)return;
      var button=document.createElement('button');button.type='button';button.className='pkContextButton';button.textContent=label;button.addEventListener('click',function(){send(command)});root.appendChild(button);
    });
  }

  function narrateSnapshot(packet){
    var name=clean(packet.room_name||packet.location||''),description=clean(packet.room_description||packet.description||''),roomId=clean(packet.room_id||'');
    var key=(roomId||name)+'|'+description;if(!name||key===lastNarratedRoomKey)return;lastNarratedRoomKey=key;
    appendFeed(name.toUpperCase(),'location',false);if(description)appendFeed(description,'narrative',false);
    setDialogue(description||('Has llegado a '+name+'.'),'NARRADOR',false);
  }

  function renderSnapshot(args){
    var packet=packetFrom(args);if(packet.status&&packet.status!=='ROOM_SNAPSHOT')return;lastSnapshot=packet;
    var name=clean(packet.room_name||packet.location||'Ubicación actual'),roomId=clean(packet.room_id||'');
    var nameNode=byId('pk-room-name');if(nameNode)nameNode.textContent=name||'Ubicación actual';
    var idNode=byId('pk-room-id');if(idNode)idNode.textContent=roomId||'';
    renderBackground(packet);renderExits(packet);renderActors(packet);renderActions(packet);narrateSnapshot(packet);
  }
  function renderContextActions(args){var packet=packetFrom(args);lastActions=packet;renderActions(packet)}
  function requestRoomState(){if(!window.Evennia||typeof Evennia.msg!=='function')return false;try{Evennia.msg('text',['pokerol-room-state'],{});return true}catch(e){return false}}

  function onText(args,kwargs){
    var value=args&&args.length?String(args[0]||''):'';if(!value)return true;
    var isErr=kwargs&&kwargs.cls==='err';appendFeed(value,isErr?'error':'world',true);
    if(isErr)setDialogue(value,'SISTEMA',true);else if(!/you become|welcome to|connected/i.test(value))setDialogue(value,'NARRADOR',true);
    if(/you become/i.test(value)){window.setTimeout(requestRoomState,120);window.setTimeout(requestRoomState,650)}
    return true;
  }
  function onPrompt(args){var value=args&&args.length?String(args[0]||''):'';var node=byId('prompt');if(node)node.innerHTML=value;return true}
  function onConnectionOpen(){appendSystem('Conectado a POKEROL.');setDialogue('Conectado. Preparando la escena…','SISTEMA',false);window.setTimeout(requestRoomState,300)}
  function onConnectionClose(){appendFeed('La conexión con POKEROL se cerró.','error',false);setDialogue('La conexión se cerró.','SISTEMA',false)}
  function onDefault(cmdname,args){
    if(/^siza_/i.test(String(cmdname||''))){if(window.console&&console.warn)console.warn('POKEROL bloqueó evento legacy:',cmdname);return true}
    appendFeed('Evento no manejado: '+String(cmdname||''),'error',false);return true;
  }

  function bindManualEcho(){var field=byId('inputfield');if(!field||field.dataset.pkEchoBound==='1')return;field.dataset.pkEchoBound='1';field.addEventListener('keydown',function(ev){if(ev.key==='Enter'&&!ev.shiftKey){var line=String(field.value||'').trim();if(line)appendCommand(line)}})}
  function bindHistory(){var open=byId('pk-log-toggle'),close=byId('pk-log-close'),panel=byId('pk-history');if(open&&panel)open.addEventListener('click',function(){panel.classList.add('pkOpen')});if(close&&panel)close.addEventListener('click',function(){panel.classList.remove('pkOpen')})}

  function bindEmitter(){
    if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_room_snapshot',renderSnapshot);Evennia.emitter.on('pokerol_context_actions',renderContextActions);
    Evennia.emitter.on('text',onText);Evennia.emitter.on('prompt',onPrompt);Evennia.emitter.on('connection_open',onConnectionOpen);Evennia.emitter.on('connection_close',onConnectionClose);Evennia.emitter.on('default',onDefault);emitterBound=true;return true;
  }
  function init(){
    document.title='POKEROL';bind('pk-look','look');bind('pk-party','equipo');bind('pk-bag','bolsa');bind('pk-test','solo-prueba');bindManualEcho();bindHistory();
    var field=byId('inputfield');if(field){field.setAttribute('placeholder','¿Qué haces?');window.setTimeout(function(){field.focus()},250)}
    appendSystem('POKEROL listo.');setDialogue('Inicia sesión o crea tu entrenador para comenzar.','SISTEMA',false);
    if(lastSnapshot)renderSnapshot(lastSnapshot);else if(lastActions)renderActions(lastActions);
    var tries=0;(function retryBind(){tries+=1;if(bindEmitter()){window.setTimeout(requestRoomState,250);return}if(tries<80)window.setTimeout(retryBind,100)})();
  }

  bindEmitter();
  window.PokerolPlayableClientV01=Object.freeze({BUILD:BUILD,send:send,requestRoomState:requestRoomState,renderSnapshot:renderSnapshot,appendFeed:appendFeed,setDialogue:setDialogue});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
