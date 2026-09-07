(function(){
  'use strict';
  var BUILD='0.1.0-kendboy-frame';
  var emitterBound=false;
  var lastPacket={};

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).trim()}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function manager(){return window.PokerolAssetManagerV01||null}
  function requestRoom(){if(window.PokerolPlayableClientV01&&typeof PokerolPlayableClientV01.requestRoomState==='function')PokerolPlayableClientV01.requestRoomState();else if(window.Evennia&&typeof Evennia.msg==='function')Evennia.msg('text',['pokerol-room-state'],{})}
  function dialogue(text){var t=byId('pk-dialogue-text'),s=byId('pk-speaker');if(t)t.textContent=String(text||'');if(s)s.textContent='SISTEMA'}

  function ensureHardware(){
    var game=byId('pokerol-client');if(!game)return false;
    if(byId('pk-hardware-frame'))return true;
    var parent=game.parentNode;if(!parent)return false;
    var frame=document.createElement('div');frame.id='pk-hardware-frame';frame.className='pkHardwareFrame';
    var art=document.createElement('div');art.id='pk-frame-art';art.className='pkFrameArt';
    var theme=document.createElement('div');theme.className='pkFrameTheme';theme.textContent='THEME';
    var brand=document.createElement('div');brand.className='pkFrameBrand';brand.textContent='KENDBOY ADVANCE';
    parent.insertBefore(frame,game);frame.appendChild(art);frame.appendChild(theme);frame.appendChild(brand);frame.appendChild(game);
    return true;
  }

  function applyFrame(url){
    ensureHardware();
    var frame=byId('pk-hardware-frame'),art=byId('pk-frame-art');if(!frame||!art)return;
    url=clean(url);
    if(url){art.style.backgroundImage='url("'+url.replace(/"/g,'%22')+'")';frame.classList.add('pkHasCustomFrame')}
    else{art.style.backgroundImage='';frame.classList.remove('pkHasCustomFrame')}
    var preview=byId('pk-frame-preview');if(preview){preview.style.backgroundImage=url?'url("'+url.replace(/"/g,'%22')+'")':'';preview.textContent=url?'':'FRAME KENDBOY POR DEFECTO'}
  }

  function ensureEditor(){
    var stage=byId('pk-stage'),menu=byId('pk-edit-menu');if(!stage||!menu)return false;
    if(byId('pk-edit-frame'))return true;
    var button=document.createElement('button');button.id='pk-edit-frame';button.type='button';button.textContent='FRAME';
    var player=byId('pk-edit-player');if(player)menu.insertBefore(button,player);else menu.appendChild(button);

    var panel=document.createElement('aside');panel.id='pk-frame-panel';panel.className='pkFramePanel';panel.hidden=true;
    panel.innerHTML=''
      +'<div class="pkFramePanelHead"><strong>FRAME DE PANTALLA</strong><button id="pk-frame-close" type="button" aria-label="Cerrar">×</button></div>'
      +'<div id="pk-frame-preview" class="pkFramePreview">FRAME KENDBOY POR DEFECTO</div>'
      +'<div class="pkFrameActions"><button id="pk-frame-load" type="button">CARGAR FRAME</button><button id="pk-frame-reset" type="button">RESET FRAME</button></div>'
      +'<input id="pk-frame-file" type="file" accept="image/png,image/webp,image/jpeg,image/gif" hidden>'
      +'<div class="pkFrameHint">El frame es global para POKEROL. Usa una imagen 16:9; la interfaz queda dentro del área de pantalla medida del frame.</div>';
    stage.appendChild(panel);

    button.addEventListener('click',function(){panel.hidden=!panel.hidden;menu.hidden=true;applyFrame(clean(lastPacket.ui_frame))});
    byId('pk-frame-close').addEventListener('click',function(){panel.hidden=true});
    byId('pk-frame-load').addEventListener('click',function(){byId('pk-frame-file').click()});
    byId('pk-frame-file').addEventListener('change',function(){
      var file=this.files&&this.files[0];this.value='';if(!file)return;
      var m=manager();if(!m){dialogue('El gestor de assets todavía no está listo.');return}
      dialogue('Guardando frame en el proyecto…');
      m.uploadFile({kind:'ui_frame'},file).then(function(result){lastPacket.ui_frame=result.url;applyFrame(result.url);dialogue('Frame guardado globalmente en el proyecto.');requestRoom()}).catch(function(err){dialogue(err&&err.message||'No se pudo guardar el frame.')});
    });
    byId('pk-frame-reset').addEventListener('click',function(){
      var m=manager();if(!m){dialogue('El gestor de assets todavía no está listo.');return}
      m.clearAsset({kind:'ui_frame'}).then(function(){lastPacket.ui_frame='';applyFrame('');dialogue('Frame restaurado al KENDBOY por defecto.');requestRoom()}).catch(function(err){dialogue(err&&err.message||'No se pudo restaurar el frame.')});
    });
    applyFrame(clean(lastPacket.ui_frame));return true;
  }

  function onSnapshot(args){lastPacket=packetFrom(args);applyFrame(clean(lastPacket.ui_frame));ensureEditor();return true}
  function bindEmitter(){if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);emitterBound=true;return true}
  function init(){ensureHardware();var tries=0;(function wait(){tries++;ensureHardware();ensureEditor();bindEmitter();if((!byId('pk-edit-frame')||!emitterBound)&&tries<180)setTimeout(wait,50)})();setTimeout(requestRoom,220)}

  window.PokerolConsoleFrameV01=Object.freeze({BUILD:BUILD,applyFrame:applyFrame,refresh:ensureEditor});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
