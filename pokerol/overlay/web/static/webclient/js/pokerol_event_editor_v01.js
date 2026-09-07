(function(){
  'use strict';

  var BUILD='0.2.0-generic-event-lifecycle-authoring';
  var state={events:[],room_id:'',room_name:''};
  var selectedId='';
  var emitterBound=false;

  var TEXT_LABELS={
    intro:'TEXTO PRINCIPAL',
    oak_intro:'OAK · PRIMERA CONVERSACIÓN',
    oak_choose_again:'OAK · RECORDATORIO DE ELECCIÓN',
    oak_after_choice:'OAK · DESPUÉS DE ELEGIR',
    oak_battle:'OAK · DURANTE LA BATALLA',
    oak_complete:'OAK · EVENTO COMPLETADO',
    rival_wait:'RIVAL · ANTES DE ELEGIR',
    rival_challenge:'RIVAL · PRESENTA SU POKÉMON',
    rival_battle:'RIVAL · DURANTE LA BATALLA',
    rival_player_win:'RIVAL · JUGADOR GANA',
    rival_player_loss:'RIVAL · JUGADOR PIERDE',
    rival_draw:'RIVAL · EMPATE',
    oak_starter_chosen:'OAK · ENTREGA DEL STARTER',
    rival_starter_chosen:'RIVAL · ELECCIÓN Y RETO',
    rival_battle_start:'RIVAL · INICIO DEL COMBATE'
  };

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).trim()}
  function show(node,on){if(node)node.hidden=!on}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function encodePayload(data){
    var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';
    for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  }
  function send(command,data){
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{
      var line=command+(data?' '+encodePayload(data):'');
      Evennia.msg('text',[line],{});return true;
    }catch(e){return false}
  }
  function status(text,error){
    var node=byId('pk-event-status');if(!node)return;
    node.textContent=clean(text);node.classList.toggle('pkEventError',!!error);
  }
  function currentEvent(){return (state.events||[]).find(function(row){return clean(row&&row.id)===selectedId})||null}
  function clone(obj){try{return JSON.parse(JSON.stringify(obj||{}))}catch(e){return {}}}
  function listValue(value){return Array.isArray(value)?value:[]}
  function lines(value){return listValue(value).map(clean).filter(Boolean).join('\n')}
  function readLines(id){var node=byId(id);return node?String(node.value||'').split(/\r?\n/).map(clean).filter(Boolean):[]}

  function inject(){
    var menu=byId('pk-edit-menu'),stage=byId('pk-stage');if(!menu||!stage)return false;
    if(!byId('pk-edit-events')){
      var button=document.createElement('button');button.id='pk-edit-events';button.type='button';button.textContent='EVENTOS';
      var player=byId('pk-edit-player');menu.insertBefore(button,player||null);
    }
    if(!byId('pk-event-panel')){
      var panel=document.createElement('aside');panel.id='pk-event-panel';panel.className='pkEventPanel';panel.hidden=true;
      panel.innerHTML=''
        +'<div class="pkEventHead"><div><strong>EVENT EDITOR</strong><span id="pk-event-room">ROOM</span></div><div><button id="pk-event-new" type="button">NUEVO</button><button id="pk-event-refresh" type="button">ACTUALIZAR</button><button id="pk-event-close" type="button" aria-label="Cerrar">×</button></div></div>'
        +'<div class="pkEventBody">'
          +'<nav class="pkEventListPane"><div class="pkEventListTitle">EVENTOS POSIBLES EN ESTE ROOM</div><div id="pk-event-list" class="pkEventList"></div></nav>'
          +'<section class="pkEventDetail">'
            +'<div id="pk-event-empty" class="pkEventEmpty">Selecciona un evento del cuarto o crea uno nuevo.</div>'
            +'<div id="pk-event-form" hidden>'
              +'<div class="pkEventIdentity"><span id="pk-event-source" class="pkEventBadge">EVENT</span><span id="pk-event-handler" class="pkEventHandler"></span></div>'
              +'<div class="pkEventTwo"><label>ID<input id="pk-event-id" type="text" readonly></label><label>NOMBRE<input id="pk-event-name" type="text" maxlength="160"></label></div>'
              +'<div class="pkEventThree"><label>TIPO<select id="pk-event-type"><option>TUTORIAL</option><option>STORY</option><option>EVENT</option><option>DANGER</option><option>ORDER</option><option>ENCOUNTER</option><option>AMBIENT</option></select></label><label>TRIGGER<select id="pk-event-trigger"><option>INTERACT_NPC</option><option>INTERACT_OBJECT</option><option>ENTER_ROOM</option><option>STATE</option><option>MANUAL</option></select></label><label>PRIORIDAD<input id="pk-event-priority" type="number" min="0" max="999" step="1"></label></div>'
              +'<div class="pkEventTwo"><label>TARGET DEL TRIGGER<input id="pk-event-trigger-target" type="text" maxlength="160"></label><label>REPETICIÓN<select id="pk-event-repeat"><option>PER_CHARACTER</option><option>ONCE</option><option>REPEATABLE</option><option>ALWAYS</option><option>ACK</option><option>PERSISTENT</option></select></label></div>'
              +'<label class="pkEventCheck"><input id="pk-event-enabled" type="checkbox"> EVENTO HABILITADO</label>'
              +'<label>DESCRIPCIÓN<textarea id="pk-event-description" rows="3" maxlength="6000"></textarea></label>'
              +'<div id="pk-event-stages-wrap" class="pkEventSection"><strong>FLUJO / ESTADOS</strong><div id="pk-event-stages" class="pkEventStages"></div></div>'
              +'<div id="pk-event-generic-runtime" class="pkEventSection" hidden><strong>RUNTIME DEL EVENTO</strong>'
                +'<div class="pkEventThree"><label class="pkEventCheck"><input id="pk-event-autorun" type="checkbox"> AUTORUN</label><label>PROBABILIDAD %<input id="pk-event-chance" type="number" min="0" max="100" step="1"></label><label class="pkEventCheck"><input id="pk-event-blocking" type="checkbox"> BLOQUEANTE</label></div>'
                +'<div class="pkEventTwo"><label class="pkEventCheck"><input id="pk-event-allow-snooze" type="checkbox"> PERMITE POSPONER</label><label>REANUDAR<select id="pk-event-snooze-policy"><option>UNTIL_REENTRY</option><option>MANUAL</option><option>NONE</option></select></label></div>'
                +'<label>CONDICIONES DE INICIO · UNA POR LÍNEA<textarea id="pk-event-start-conditions" rows="3" placeholder="FLAG:permiso=true&#10;POKEMON:PKMN-025"></textarea></label>'
                +'<label>CONDICIONES DE COMPLETADO · TODAS DEBEN CUMPLIRSE<textarea id="pk-event-completion-conditions" rows="3" placeholder="EVENT:OTRO-EVENTO:COMPLETE:1&#10;BADGE:BADGE-BOULDER"></textarea></label>'
                +'<div class="pkEventHint">Condiciones: ROOM:id · FLAG:clave=valor · BADGE:id · MEMORY:id · EVENT:id · EVENT_COMPLETE:id · POKEMON:id · BATTLE_OUTCOME:resultado · ALWAYS.</div>'
              +'</div>'
              +'<div id="pk-event-presentation" class="pkEventSection" hidden><strong>PRESENTACIÓN</strong>'
                +'<div class="pkEventTwo"><label>TÍTULO<input id="pk-event-present-title" type="text" maxlength="160"></label><label>HABLANTE<input id="pk-event-present-speaker" type="text" maxlength="120"></label></div>'
                +'<label>TEXTO<textarea id="pk-event-present-text" rows="3" maxlength="6000"></textarea></label>'
                +'<div class="pkEventThree"><label>MEDIA<select id="pk-event-media-type"><option>image</option><option>video</option></select></label><label>ARCHIVO / URL<input id="pk-event-media-src" type="text" maxlength="1000"></label><label class="pkEventCheck"><input id="pk-event-ack-completes" type="checkbox"> CONTINUAR COMPLETA</label></div>'
              +'</div>'
              +'<div id="pk-event-memory" class="pkEventSection" hidden><strong>MEMORIA DEL ENTRENADOR</strong>'
                +'<label class="pkEventCheck"><input id="pk-event-memory-start-enabled" type="checkbox"> CREAR MEMORIA AL INICIAR</label><div class="pkEventTwo"><label>TÍTULO INICIO<input id="pk-event-memory-start-title" type="text" maxlength="160"></label><label>IMPORTANCIA<input id="pk-event-memory-start-importance" type="number" min="0" max="10"></label></div><label>TEXTO INICIO<textarea id="pk-event-memory-start-text" rows="2"></textarea></label>'
                +'<label class="pkEventCheck"><input id="pk-event-memory-complete-enabled" type="checkbox"> CREAR MEMORIA AL COMPLETAR</label><div class="pkEventTwo"><label>TÍTULO COMPLETADO<input id="pk-event-memory-complete-title" type="text" maxlength="160"></label><label>IMPORTANCIA<input id="pk-event-memory-complete-importance" type="number" min="0" max="10"></label></div><label>TEXTO COMPLETADO<textarea id="pk-event-memory-complete-text" rows="2"></textarea></label>'
              +'</div>'
              +'<div id="pk-event-oak-settings" class="pkEventSection" hidden><strong>CONFIGURACIÓN DEL INICIO</strong><div class="pkEventTwo"><label>NIVEL DE LOS STARTERS<input id="pk-event-starter-level" type="number" min="1" max="100" step="1"></label><div><span class="pkEventMiniLabel">STARTERS DISPONIBLES</span><label class="pkEventCheck"><input class="pk-event-starter-choice" value="bulbasaur" type="checkbox"> Bulbasaur</label><label class="pkEventCheck"><input class="pk-event-starter-choice" value="charmander" type="checkbox"> Charmander</label><label class="pkEventCheck"><input class="pk-event-starter-choice" value="squirtle" type="checkbox"> Squirtle</label></div></div><div class="pkEventHint">El rival conserva la regla COUNTER. Cambiar estos valores modifica el evento real, no una copia del navegador.</div></div>'
              +'<div id="pk-event-world-settings" class="pkEventSection" hidden><strong>CONDICIÓN WORLD EVENT</strong><div class="pkEventThree"><label>CAMPO<input id="pk-event-world-field" type="text"></label><label>OPERADOR<select id="pk-event-world-op"><option value="eq">=</option><option value="ne">!=</option><option value="gt">&gt;</option><option value="gte">&gt;=</option><option value="lt">&lt;</option><option value="lte">&lt;=</option></select></label><label>VALOR<input id="pk-event-world-value" type="text"></label></div><label>ACTIVIDAD / RESPUESTA<input id="pk-event-world-activity" type="text" maxlength="1000"></label><div class="pkEventTwo"><label>AWARENESS<select id="pk-event-world-awareness"><option>AUDIENCE</option><option>LOCAL</option></select></label><label class="pkEventCheck pkEventInlineCheck"><input id="pk-event-world-blocks" type="checkbox"> BLOQUEA JOBS</label></div><div id="pk-event-world-state" class="pkEventHint"></div></div>'
              +'<div id="pk-event-texts-wrap" class="pkEventSection"><strong>DIÁLOGOS / TEXTO DEL EVENTO</strong><div id="pk-event-texts"></div></div>'
              +'<div class="pkEventActions"><button id="pk-event-save" type="button" class="pkEventPrimary">GUARDAR EVENTO</button><button id="pk-event-reset" type="button">RESTABLECER</button></div>'
            +'</div>'
          +'</section>'
        +'</div>'
        +'<div id="pk-event-status" class="pkEventStatus"></div>';
      stage.appendChild(panel);
    }

    var open=byId('pk-edit-events'),close=byId('pk-event-close'),refresh=byId('pk-event-refresh'),fresh=byId('pk-event-new'),save=byId('pk-event-save'),reset=byId('pk-event-reset');
    if(open&&open.dataset.pkEventBound!=='1'){
      open.dataset.pkEventBound='1';open.addEventListener('click',function(){var m=byId('pk-edit-menu');if(m)m.hidden=true;show(byId('pk-event-panel'),true);requestState()});
    }
    if(close&&close.dataset.pkEventBound!=='1'){close.dataset.pkEventBound='1';close.addEventListener('click',function(){show(byId('pk-event-panel'),false)})}
    if(refresh&&refresh.dataset.pkEventBound!=='1'){refresh.dataset.pkEventBound='1';refresh.addEventListener('click',requestState)}
    if(fresh&&fresh.dataset.pkEventBound!=='1'){fresh.dataset.pkEventBound='1';fresh.addEventListener('click',newEvent)}
    if(save&&save.dataset.pkEventBound!=='1'){save.dataset.pkEventBound='1';save.addEventListener('click',saveCurrent)}
    if(reset&&reset.dataset.pkEventBound!=='1'){reset.dataset.pkEventBound='1';reset.addEventListener('click',resetCurrent)}
    return true;
  }

  function requestState(){status('LEYENDO EVENTOS DEL ROOM…',false);if(!send('pokerol-event-editor-list'))status('No se pudo consultar el World Engine.',true)}

  function newEvent(){
    var id='__NEW__'+Date.now();
    var event={id:id,_new:true,source:'ROOM',handler:'ROOM_EVENT',name:'Nuevo evento',event_type:'STORY',trigger:'ENTER_ROOM',trigger_target:'',repeat_mode:'PER_CHARACTER',priority:50,enabled:true,description:'',stages:[],texts:{intro:''},settings:{},scene_policy:{free_input_priority:true,completion_conditions:[]},autorun:true,chance_percent:100,blocking:false,allow_snooze:true,snooze_policy:'UNTIL_REENTRY',start_conditions:[],completion_conditions:[],presentation:{title:'',speaker:'NARRADOR',text:'',media_type:'image',media_src:'',acknowledge_completes:true},memory_on_start:{enabled:false,title:'',text:'',importance:5},memory_on_complete:{enabled:false,title:'',text:'',importance:7}};
    state.events.unshift(event);selectedId=id;renderList();status('NUEVO EVENTO · GUÁRDALO PARA CREARLO EN EL WORLD ENGINE',false);
  }

  function sourceLabel(event){var source=clean(event&&event.source).toUpperCase();if(source==='SYSTEM')return 'SISTEMA';if(source==='WORLD_EVENT')return 'WORLD EVENT';return 'ROOM'}

  function renderList(){
    var root=byId('pk-event-list');if(!root)return;root.innerHTML='';
    var events=state.events||[];
    if(!events.length){var none=document.createElement('div');none.className='pkEventNone';none.textContent='No hay eventos registrados en este room.';root.appendChild(none);selectEvent('');return}
    if(!events.some(function(e){return clean(e.id)===selectedId}))selectedId=clean(events[0].id);
    events.forEach(function(event){
      var button=document.createElement('button');button.type='button';button.className='pkEventListItem';button.dataset.eventId=clean(event.id);button.classList.toggle('pkSelected',button.dataset.eventId===selectedId);
      var top=document.createElement('span');top.className='pkEventListTop';var name=document.createElement('strong');name.textContent=clean(event.name)||clean(event.id);var enabled=document.createElement('span');enabled.className='pkEventDot '+(event.enabled?'pkOn':'pkOff');enabled.textContent=event.enabled?'ON':'OFF';top.appendChild(name);top.appendChild(enabled);
      var meta=document.createElement('span');meta.className='pkEventListMeta';meta.textContent=sourceLabel(event)+' · '+clean(event.event_type||event.handler)+' · '+clean(event.trigger);
      button.appendChild(top);button.appendChild(meta);button.addEventListener('click',function(){selectEvent(button.dataset.eventId)});root.appendChild(button);
    });
    renderCurrent();
  }

  function selectEvent(id){selectedId=clean(id);Array.from(document.querySelectorAll('.pkEventListItem')).forEach(function(n){n.classList.toggle('pkSelected',n.dataset.eventId===selectedId)});renderCurrent()}

  function setSelect(id,value){
    var n=byId(id);if(!n)return;
    var wanted=clean(value).toUpperCase(),match=null;
    Array.from(n.options).some(function(o){if(clean(o.value||o.textContent).toUpperCase()===wanted){match=o;return true}return false});
    if(!match&&wanted){match=document.createElement('option');match.value=clean(value)||wanted;match.textContent=clean(value)||wanted;n.appendChild(match)}
    if(match)n.value=match.value;
  }
  function setValue(id,value){var n=byId(id);if(n)n.value=value==null?'':String(value)}
  function setChecked(id,value){var n=byId(id);if(n)n.checked=!!value}

  function renderStages(event){
    var root=byId('pk-event-stages');if(!root)return;root.innerHTML='';var stages=listValue(event.stages);byId('pk-event-stages-wrap').hidden=!stages.length;
    stages.forEach(function(stage,index){var chip=document.createElement('span');chip.className='pkEventStage';chip.textContent=(index+1)+'. '+clean(stage.label||stage.id);root.appendChild(chip)});
  }

  function renderTexts(event){
    var root=byId('pk-event-texts');if(!root)return;root.innerHTML='';var texts=event.texts&&typeof event.texts==='object'?event.texts:{};var keys=Object.keys(texts);byId('pk-event-texts-wrap').hidden=!keys.length;
    keys.forEach(function(key){var label=document.createElement('label');label.className='pkEventTextField';label.dataset.textKey=key;var title=document.createElement('span');title.textContent=TEXT_LABELS[key]||key.replace(/_/g,' ').toUpperCase();var area=document.createElement('textarea');area.rows=2;area.maxLength=6000;area.value=String(texts[key]||'');area.dataset.textKey=key;label.appendChild(title);label.appendChild(area);root.appendChild(label)});
  }

  function renderOakSettings(event){
    var wrap=byId('pk-event-oak-settings'),settings=clone(event.settings);var isOak=clean(event.handler)==='OAK_STARTER_TUTORIAL';wrap.hidden=!isOak;if(!isOak)return;
    setValue('pk-event-starter-level',settings.starter_level==null?5:settings.starter_level);var choices=listValue(settings.starter_choices).map(function(v){return clean(v).toLowerCase()});Array.from(document.querySelectorAll('.pk-event-starter-choice')).forEach(function(box){box.checked=choices.indexOf(clean(box.value).toLowerCase())>=0});
  }

  function renderWorldSettings(event){
    var wrap=byId('pk-event-world-settings'),settings=clone(event.settings);var isWorld=clean(event.handler)==='WORLD_EVENT_RULE';wrap.hidden=!isWorld;if(!isWorld)return;
    setValue('pk-event-world-field',settings.field);setSelect('pk-event-world-op',settings.op||'eq');setValue('pk-event-world-value',settings.value);setValue('pk-event-world-activity',settings.activity);setSelect('pk-event-world-awareness',settings.awareness_mode||'AUDIENCE');setChecked('pk-event-world-blocks',settings.blocks_jobs);var stateNode=byId('pk-event-world-state');if(stateNode)stateNode.textContent='ESTADO ACTUAL · '+clean(settings.field)+' = '+String(settings.current_state==null?'—':settings.current_state)+' · SITE '+clean(settings.site_name);
  }

  function renderGeneric(event){
    var generic=clean(event.source)==='ROOM'&&['ROOM_EVENT','GENERIC_ROOM_EVENT'].indexOf(clean(event.handler).toUpperCase())>=0;
    show(byId('pk-event-generic-runtime'),generic);show(byId('pk-event-presentation'),generic);show(byId('pk-event-memory'),generic);if(!generic)return;
    var p=clone(event.presentation),mStart=clone(event.memory_on_start),mComplete=clone(event.memory_on_complete);
    setChecked('pk-event-autorun',event.autorun!==false);setValue('pk-event-chance',event.chance_percent==null?100:event.chance_percent);setChecked('pk-event-blocking',event.blocking);setChecked('pk-event-allow-snooze',event.allow_snooze!==false);setSelect('pk-event-snooze-policy',event.snooze_policy||'UNTIL_REENTRY');
    setValue('pk-event-start-conditions',lines(event.start_conditions));setValue('pk-event-completion-conditions',lines(event.completion_conditions||clone(event.scene_policy).completion_conditions));
    setValue('pk-event-present-title',p.title);setValue('pk-event-present-speaker',p.speaker||'NARRADOR');setValue('pk-event-present-text',p.text);setSelect('pk-event-media-type',p.media_type||'image');setValue('pk-event-media-src',p.media_src);setChecked('pk-event-ack-completes',p.acknowledge_completes!==false);
    setChecked('pk-event-memory-start-enabled',mStart.enabled);setValue('pk-event-memory-start-title',mStart.title);setValue('pk-event-memory-start-text',mStart.text);setValue('pk-event-memory-start-importance',mStart.importance==null?5:mStart.importance);
    setChecked('pk-event-memory-complete-enabled',mComplete.enabled);setValue('pk-event-memory-complete-title',mComplete.title);setValue('pk-event-memory-complete-text',mComplete.text);setValue('pk-event-memory-complete-importance',mComplete.importance==null?7:mComplete.importance);
  }

  function renderCurrent(){
    var event=currentEvent(),form=byId('pk-event-form'),empty=byId('pk-event-empty');show(form,!!event);show(empty,!event);if(!event)return;
    setValue('pk-event-id',event._new?'(se asigna al guardar)':event.id);setValue('pk-event-name',event.name);setSelect('pk-event-type',event.event_type);setSelect('pk-event-trigger',event.trigger);setValue('pk-event-priority',event.priority);setValue('pk-event-trigger-target',event.trigger_target);setSelect('pk-event-repeat',event.repeat_mode);setChecked('pk-event-enabled',event.enabled);setValue('pk-event-description',event.description);
    var source=byId('pk-event-source');if(source)source.textContent=sourceLabel(event)+(event.overridden?' · EDITADO':'');var handler=byId('pk-event-handler');if(handler)handler.textContent=clean(event.handler);renderStages(event);renderTexts(event);renderOakSettings(event);renderWorldSettings(event);renderGeneric(event);
    var reset=byId('pk-event-reset');if(reset){reset.hidden=!!event._new||clean(event.source)==='WORLD_EVENT';reset.textContent=clean(event.source)==='SYSTEM'?'RESTABLECER EVENTO':'BORRAR EVENTO'}status('WORLD ENGINE · '+(event._new?'NUEVO EVENTO':clean(event.id)),false);
  }

  function coerceValue(value){var raw=clean(value);if(/^true$/i.test(raw))return true;if(/^false$/i.test(raw))return false;if(/^-?\d+$/.test(raw))return parseInt(raw,10);if(/^-?\d+\.\d+$/.test(raw))return parseFloat(raw);return raw}

  function collectCurrent(){
    var event=currentEvent();if(!event)return null;var payload=clone(event);delete payload._new;
    payload.id=event._new?'':clean(event.id);payload.name=clean(byId('pk-event-name').value);payload.event_type=clean(byId('pk-event-type').value);payload.trigger=clean(byId('pk-event-trigger').value);payload.priority=parseInt(byId('pk-event-priority').value||'0',10)||0;payload.trigger_target=clean(byId('pk-event-trigger-target').value);payload.repeat_mode=clean(byId('pk-event-repeat').value);payload.enabled=!!byId('pk-event-enabled').checked;payload.description=String(byId('pk-event-description').value||'').trim();
    payload.texts={};Array.from(document.querySelectorAll('#pk-event-texts textarea[data-text-key]')).forEach(function(area){payload.texts[area.dataset.textKey]=String(area.value||'').trim()});payload.settings=clone(event.settings);
    if(clean(event.handler)==='OAK_STARTER_TUTORIAL'){payload.settings.starter_level=Math.max(1,Math.min(100,parseInt(byId('pk-event-starter-level').value||'5',10)||5));payload.settings.starter_choices=Array.from(document.querySelectorAll('.pk-event-starter-choice:checked')).map(function(box){return box.value});if(!payload.settings.starter_choices.length)payload.settings.starter_choices=['bulbasaur','charmander','squirtle']}
    if(clean(event.handler)==='WORLD_EVENT_RULE'){payload.settings.field=clean(byId('pk-event-world-field').value);payload.settings.op=clean(byId('pk-event-world-op').value);payload.settings.value=coerceValue(byId('pk-event-world-value').value);payload.settings.activity=clean(byId('pk-event-world-activity').value);payload.settings.awareness_mode=clean(byId('pk-event-world-awareness').value);payload.settings.blocks_jobs=!!byId('pk-event-world-blocks').checked}
    if(clean(event.source)==='ROOM'&&['ROOM_EVENT','GENERIC_ROOM_EVENT'].indexOf(clean(event.handler).toUpperCase())>=0){
      payload.handler='ROOM_EVENT';payload.autorun=!!byId('pk-event-autorun').checked;payload.chance_percent=Math.max(0,Math.min(100,parseInt(byId('pk-event-chance').value||'100',10)||0));payload.blocking=!!byId('pk-event-blocking').checked;payload.allow_snooze=!!byId('pk-event-allow-snooze').checked;payload.snooze_policy=clean(byId('pk-event-snooze-policy').value)||'UNTIL_REENTRY';payload.start_conditions=readLines('pk-event-start-conditions');payload.completion_conditions=readLines('pk-event-completion-conditions');
      payload.presentation={title:clean(byId('pk-event-present-title').value),speaker:clean(byId('pk-event-present-speaker').value)||'NARRADOR',text:String(byId('pk-event-present-text').value||'').trim(),media_type:clean(byId('pk-event-media-type').value)||'image',media_src:clean(byId('pk-event-media-src').value),acknowledge_completes:!!byId('pk-event-ack-completes').checked,allow_snooze:payload.allow_snooze,blocking:payload.blocking};
      payload.memory_on_start={enabled:!!byId('pk-event-memory-start-enabled').checked,title:clean(byId('pk-event-memory-start-title').value)||payload.name,text:String(byId('pk-event-memory-start-text').value||'').trim()||payload.description,category:'EVENTO',importance:Math.max(0,Math.min(10,parseInt(byId('pk-event-memory-start-importance').value||'5',10)||5))};
      payload.memory_on_complete={enabled:!!byId('pk-event-memory-complete-enabled').checked,title:clean(byId('pk-event-memory-complete-title').value)||payload.name,text:String(byId('pk-event-memory-complete-text').value||'').trim()||payload.description,category:'EVENTO COMPLETADO',importance:Math.max(0,Math.min(10,parseInt(byId('pk-event-memory-complete-importance').value||'7',10)||7))};
      payload.scene_policy=clone(payload.scene_policy);payload.scene_policy.completion_conditions=payload.completion_conditions;payload.scene_policy.memory_on_complete=payload.memory_on_complete.enabled;
    }
    return payload;
  }

  function saveCurrent(){var payload=collectCurrent();if(!payload)return;status('GUARDANDO EVENTO EN WORLD ENGINE…',false);if(!send('pokerol-event-editor-save',payload))status('No se pudo enviar el evento.',true)}
  function resetCurrent(){var event=currentEvent();if(!event||event._new)return;var system=clean(event.source)==='SYSTEM';var question=system?'¿Restablecer este evento a la definición del sistema?':'¿Borrar este evento del room?';if(window.confirm&&!window.confirm(question))return;status(system?'RESTABLECIENDO…':'BORRANDO…',false);if(!send('pokerol-event-editor-delete',{id:event.id}))status('No se pudo enviar la operación.',true)}

  function onState(args){var packet=packetFrom(args);state={events:Array.isArray(packet.events)?packet.events:[],room_id:clean(packet.room_id),room_name:clean(packet.room_name)};var room=byId('pk-event-room');if(room)room.textContent=(state.room_name||'ROOM')+(state.room_id?' · '+state.room_id:'');renderList();status('EVENTOS CARGADOS · '+state.events.length,false)}
  function onResult(args){var packet=packetFrom(args),ok=['SAVED','RESET','DELETED'].indexOf(clean(packet.status).toUpperCase())>=0;status(packet.message||packet.status,!ok);if(ok&&packet.event_id)selectedId=clean(packet.event_id)}
  function bindEmitter(){if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_event_editor_state',onState);Evennia.emitter.on('pokerol_event_editor_result',onResult);emitterBound=true;return true}
  function init(){var tries=0;(function wait(){tries++;var ready=inject();var bound=bindEmitter();if(ready&&bound)return;if(tries<180)setTimeout(wait,50)})()}

  window.PokerolEventEditorV01=Object.freeze({BUILD:BUILD,requestState:requestState,newEvent:newEvent});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();