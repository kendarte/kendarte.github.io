(function(){
  'use strict';

  var BUILD='0.1.0-player-sheet';
  var emitterBound=false;
  var lastPacket=null;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).trim()}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function esc(v){return String(v==null?'':v).replace(/[&<>'"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]})}

  function request(){
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{Evennia.msg('text',['pokerol-player-sheet'],{});return true}catch(e){return false}
  }

  function inject(){
    if(byId('pk-trainer-sheet-button'))return true;
    var tools=document.querySelector('.pkBackgroundTools'),stage=byId('pk-stage');
    if(!tools||!stage)return false;

    var button=document.createElement('button');
    button.id='pk-trainer-sheet-button';button.className='pkTrainerSheetButton';button.type='button';button.textContent='FICHA';button.title='Abrir ficha del entrenador';
    var logout=byId('pk-logout');if(logout)tools.insertBefore(button,logout);else tools.appendChild(button);

    var wrap=document.createElement('div');wrap.id='pk-trainer-sheet-backdrop';wrap.className='pkTrainerSheetBackdrop';wrap.hidden=true;
    wrap.innerHTML=''
      +'<section class="pkTrainerSheet" role="dialog" aria-modal="true" aria-label="Ficha del entrenador">'
        +'<div class="pkTrainerSheetHead"><strong>FICHA DE ENTRENADOR</strong><button id="pk-trainer-sheet-close" type="button" aria-label="Cerrar">×</button></div>'
        +'<div class="pkTrainerSheetBody">'
          +'<div class="pkTrainerSheetIdentity">'
            +'<div class="pkTrainerSheetName"><small>ENTRENADOR</small><strong id="pk-trainer-sheet-name">—</strong><span id="pk-trainer-sheet-location" class="pkTrainerMeta"></span></div>'
            +'<div id="pk-trainer-sheet-portrait" class="pkTrainerPortrait"><div class="pkTrainerPortraitEmpty">IMAGEN DE CUERPO COMPLETO<br>NO ASIGNADA</div></div>'
            +'<div class="pkTrainerPortraitTools"><button id="pk-trainer-sheet-upload" type="button">CARGAR CUERPO COMPLETO</button><button id="pk-trainer-sheet-clear" type="button">QUITAR</button><input id="pk-trainer-sheet-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden><div id="pk-trainer-sheet-upload-status" class="pkTrainerPortraitStatus"></div></div>'
          +'</div>'
          +'<div class="pkTrainerSheetData">'
            +'<section class="pkTrainerSection"><div class="pkTrainerSectionTitle">PARÁMETROS</div><div id="pk-trainer-sheet-stats" class="pkTrainerSectionBody pkTrainerStats"></div></section>'
            +'<section class="pkTrainerSection"><div class="pkTrainerSectionTitle">MEDALLAS</div><div id="pk-trainer-sheet-badges" class="pkTrainerSectionBody pkTrainerBadges"></div></section>'
            +'<section class="pkTrainerSection"><div class="pkTrainerSectionTitle">EQUIPO</div><div id="pk-trainer-sheet-party" class="pkTrainerSectionBody pkTrainerParty"></div></section>'
            +'<section class="pkTrainerSection"><div class="pkTrainerSectionTitle">CONOCIMIENTOS</div><div id="pk-trainer-sheet-knowledge" class="pkTrainerSectionBody pkTrainerKnowledge"></div></section>'
            +'<section class="pkTrainerSection"><div class="pkTrainerSectionTitle">RECUERDOS</div><div id="pk-trainer-sheet-memories" class="pkTrainerSectionBody pkTrainerMemories"></div></section>'
            +'<section class="pkTrainerSection"><div class="pkTrainerSectionTitle">HISTORIAL DE EVENTOS</div><div id="pk-trainer-sheet-events" class="pkTrainerSectionBody pkTrainerEvents"></div></section>'
          +'</div>'
        +'</div>'
      +'</section>';
    stage.appendChild(wrap);

    button.addEventListener('click',function(){wrap.hidden=false;request()});
    byId('pk-trainer-sheet-close').addEventListener('click',function(){wrap.hidden=true});
    wrap.addEventListener('click',function(ev){if(ev.target===wrap)wrap.hidden=true});
    byId('pk-trainer-sheet-upload').addEventListener('click',function(){var f=byId('pk-trainer-sheet-file');if(f){f.value='';f.click()}});
    byId('pk-trainer-sheet-clear').addEventListener('click',clearPortrait);
    byId('pk-trainer-sheet-file').addEventListener('change',uploadPortrait);
    return true;
  }

  function renderPortrait(url){
    var root=byId('pk-trainer-sheet-portrait');if(!root)return;root.innerHTML='';
    if(url){var img=document.createElement('img');img.src=url;img.alt='Entrenador cuerpo completo';root.appendChild(img)}
    else{var empty=document.createElement('div');empty.className='pkTrainerPortraitEmpty';empty.innerHTML='IMAGEN DE CUERPO COMPLETO<br>NO ASIGNADA';root.appendChild(empty)}
  }

  function renderStats(stats){
    var root=byId('pk-trainer-sheet-stats');if(!root)return;root.innerHTML='';
    ['FUE','AGI','COO','INT','PER','PSI'].forEach(function(key){
      var row=document.createElement('div');row.className='pkTrainerStat';row.innerHTML='<span>'+key+'</span><span>'+esc(stats&&stats[key]!=null?stats[key]:'—')+'</span>';root.appendChild(row);
    });
  }
  function renderBadges(rows){
    var root=byId('pk-trainer-sheet-badges');if(!root)return;root.innerHTML='';rows=Array.isArray(rows)?rows:[];
    if(!rows.length){root.innerHTML='<div class="pkTrainerEmpty">Todavía no has obtenido medallas.</div>';return}
    rows.forEach(function(row){var n=document.createElement('div');n.className='pkTrainerBadge';n.innerHTML=(row.image?'<img src="'+esc(row.image)+'" alt="">':'')+'<div>'+esc(row.name||'Medalla')+'</div>';root.appendChild(n)});
  }
  function renderParty(rows,storageCount){
    var root=byId('pk-trainer-sheet-party');if(!root)return;root.innerHTML='';rows=Array.isArray(rows)?rows:[];
    if(!rows.length){root.innerHTML='<div class="pkTrainerEmpty">No tienes Pokémon en el equipo.</div>';return}
    rows.forEach(function(row){var n=document.createElement('div');n.className='pkTrainerPartyRow'+(row.active?' pkActive':'');n.innerHTML=(row.icon?'<img src="'+esc(row.icon)+'" alt="">':'<span></span>')+'<strong>'+esc(row.name||'Pokémon')+'</strong><span>Lv '+esc(row.level||1)+'</span>';root.appendChild(n)});
    if(storageCount){var meta=document.createElement('div');meta.className='pkTrainerMeta';meta.textContent='PC / almacenamiento: '+storageCount;root.appendChild(meta)}
  }
  function renderKnowledge(levels,facts){
    var root=byId('pk-trainer-sheet-knowledge');if(!root)return;root.innerHTML='';levels=levels&&typeof levels==='object'?levels:{};facts=Array.isArray(facts)?facts:[];
    var keys=Object.keys(levels);
    if(!keys.length&&!facts.length){root.innerHTML='<div class="pkTrainerEmpty">Todavía no hay conocimientos registrados.</div>';return}
    keys.sort().forEach(function(key){var n=document.createElement('div');n.className='pkTrainerKnowledgeRow';n.innerHTML='<strong>'+esc(key)+'</strong><span class="pkTrainerMeta">Nivel '+esc(levels[key])+'</span>';root.appendChild(n)});
    facts.forEach(function(row){var n=document.createElement('div');n.className='pkTrainerKnowledgeRow';n.innerHTML='<strong>'+esc(row.topic||row.id||'Conocimiento')+'</strong><span class="pkTrainerMeta">'+esc(row.knowledge_key||'')+(row.level!=null?' · nivel '+esc(row.level):'')+'</span>';root.appendChild(n)});
  }
  function renderMemories(rows){
    var root=byId('pk-trainer-sheet-memories');if(!root)return;root.innerHTML='';rows=Array.isArray(rows)?rows:[];
    if(!rows.length){root.innerHTML='<div class="pkTrainerEmpty">Todavía no hay recuerdos registrados.</div>';return}
    rows.forEach(function(row){var n=document.createElement('article');n.className='pkTrainerMemory';n.innerHTML='<strong>'+esc(row.title||'Recuerdo')+'</strong><span class="pkTrainerMeta">'+esc(row.category||'EVENTO')+(row.room_id?' · '+esc(row.room_id):'')+'</span>'+(row.text?'<p>'+esc(row.text)+'</p>':'')+(row.image?'<img src="'+esc(row.image)+'" alt="">':'');root.appendChild(n)});
  }
  function renderEvents(rows){
    var root=byId('pk-trainer-sheet-events');if(!root)return;root.innerHTML='';rows=Array.isArray(rows)?rows:[];
    if(!rows.length){root.innerHTML='<div class="pkTrainerEmpty">Todavía no hay eventos registrados.</div>';return}
    rows.forEach(function(row){var n=document.createElement('div');n.className='pkTrainerEvent';n.innerHTML='<strong>'+esc(row.title||row.event_id||'Evento')+'</strong><span class="pkTrainerMeta">'+esc(row.result||'')+(row.room_id?' · '+esc(row.room_id):'')+'</span>';root.appendChild(n)});
  }

  function render(packet){
    lastPacket=packet||{};
    var name=byId('pk-trainer-sheet-name'),loc=byId('pk-trainer-sheet-location');if(name)name.textContent=clean(packet.name)||'ENTRENADOR';if(loc)loc.textContent=clean(packet.room&&packet.room.name)||'';
    renderPortrait(clean(packet.full_body_image));renderStats(packet.stats||{});renderBadges(packet.badges);renderParty(packet.party,packet.storage_count);renderKnowledge(packet.knowledge_levels,packet.knowledge_facts);renderMemories(packet.memories);renderEvents(packet.events);
  }

  function uploadPortrait(){
    var file=this.files&&this.files[0];if(!file)return;var status=byId('pk-trainer-sheet-upload-status'),manager=window.PokerolAssetManagerV01;
    if(!manager||typeof manager.uploadFile!=='function'){if(status)status.textContent='Gestor de assets no disponible.';return}
    if(status)status.textContent='GUARDANDO 0%';
    manager.uploadFile({kind:'player_fullbody'},file,function(p){if(status)status.textContent='GUARDANDO '+Math.round(p*100)+'%'}).then(function(result){if(status)status.textContent='GUARDADO EN EL PROYECTO';renderPortrait(result.url);request()}).catch(function(err){if(status)status.textContent=err&&err.message||'No se pudo guardar.'});
  }
  function clearPortrait(){
    var status=byId('pk-trainer-sheet-upload-status'),manager=window.PokerolAssetManagerV01;if(!manager||typeof manager.clearAsset!=='function')return;
    if(status)status.textContent='QUITANDO…';manager.clearAsset({kind:'player_fullbody'}).then(function(){if(status)status.textContent='IMAGEN QUITADA';renderPortrait('');request()}).catch(function(err){if(status)status.textContent=err&&err.message||'No se pudo quitar.'});
  }

  function onSheet(args){var p=packetFrom(args);if(clean(p.status).toUpperCase()!=='PLAYER_SHEET')return true;render(p);return true}
  function bindEmitter(){if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_player_sheet',onSheet);emitterBound=true;return true}
  function init(){var tries=0;(function wait(){tries++;var ok=inject();bindEmitter();if(ok&&emitterBound)return;if(tries<180)setTimeout(wait,50)})()}

  window.PokerolPlayerSheetV01=Object.freeze({BUILD:BUILD,request:request,render:render});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
