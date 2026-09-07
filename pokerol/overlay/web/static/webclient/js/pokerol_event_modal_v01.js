(function(){
  'use strict';

  var BUILD='0.1.0-event-media-modal';
  var queue=[];
  var current=null;
  var emitterBound=false;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).trim()}
  function packetFrom(args){
    var p=args&&args.length?args[0]:args;
    if(Array.isArray(p)&&p.length===1)p=p[0];
    return p&&typeof p==='object'?p:{};
  }
  function send(command){
    command=clean(command);if(!command)return;
    if(window.Evennia&&typeof Evennia.msg==='function')Evennia.msg('text',[command],{});
  }

  function inject(){
    if(byId('pk-event-modal-backdrop'))return true;
    var stage=byId('pk-stage');if(!stage)return false;
    var wrap=document.createElement('div');
    wrap.id='pk-event-modal-backdrop';wrap.className='pkEventModalBackdrop';wrap.hidden=true;
    wrap.innerHTML=''
      +'<section class="pkEventModal" role="dialog" aria-modal="true">'
        +'<div class="pkEventModalHead"><div><small id="pk-event-modal-kicker">EVENTO</small><strong id="pk-event-modal-title">EVENTO</strong></div><button id="pk-event-modal-close" type="button" aria-label="Cerrar">×</button></div>'
        +'<div class="pkEventModalBody">'
          +'<div id="pk-event-modal-media" class="pkEventModalMedia"></div>'
          +'<div class="pkEventModalCopy"><strong id="pk-event-modal-speaker"></strong><p id="pk-event-modal-text"></p><div id="pk-event-modal-caption" class="pkEventModalCaption"></div></div>'
        +'</div>'
        +'<div id="pk-event-modal-actions" class="pkEventModalActions"></div>'
      +'</section>';
    stage.appendChild(wrap);
    byId('pk-event-modal-close').addEventListener('click',close);
    wrap.addEventListener('click',function(ev){
      if(ev.target===wrap&&current&&!current.blocking)close();
    });
    document.addEventListener('keydown',function(ev){
      if(ev.key==='Escape'&&current&&!current.blocking)close();
    });
    return true;
  }

  function renderMedia(packet){
    var root=byId('pk-event-modal-media');if(!root)return;
    root.innerHTML='';
    var src=clean(packet.media_src||packet.image||packet.video);
    var type=clean(packet.media_type).toLowerCase();
    if(!src){root.hidden=true;return}
    root.hidden=false;
    if(type==='video'||/\.(mp4|webm|ogg)(\?|$)/i.test(src)){
      var video=document.createElement('video');
      video.src=src;video.controls=true;video.playsInline=true;
      if(packet.autoplay){video.autoplay=true;video.muted=!!packet.muted}
      root.appendChild(video);
    }else{
      var img=document.createElement('img');
      img.src=src;img.alt=clean(packet.title||packet.speaker||'Evento');
      root.appendChild(img);
    }
  }

  function renderButtons(packet){
    var root=byId('pk-event-modal-actions');if(!root)return;
    root.innerHTML='';
    var rows=Array.isArray(packet.buttons)?packet.buttons:[];
    if(!rows.length){
      rows=[{label:'CONTINUAR',close:true,primary:true}];
    }
    rows.forEach(function(row){
      if(!row||typeof row!=='object')return;
      var btn=document.createElement('button');
      btn.type='button';
      btn.textContent=clean(row.label)||'CONTINUAR';
      if(row.primary)btn.classList.add('pkEventModalPrimary');
      btn.addEventListener('click',function(){
        var command=clean(row.command);
        if(command){
          close(true);
          window.setTimeout(function(){send(command)},20);
        }else if(row.close!==false){
          close();
        }
      });
      root.appendChild(btn);
    });
  }

  function render(packet){
    inject();
    current=packet||{};
    var wrap=byId('pk-event-modal-backdrop');
    var title=byId('pk-event-modal-title'),speaker=byId('pk-event-modal-speaker'),text=byId('pk-event-modal-text'),caption=byId('pk-event-modal-caption'),kicker=byId('pk-event-modal-kicker'),closer=byId('pk-event-modal-close');
    if(title)title.textContent=clean(current.title)||'EVENTO';
    if(speaker){speaker.textContent=clean(current.speaker);speaker.hidden=!clean(current.speaker)}
    if(text)text.textContent=clean(current.text);
    if(caption){caption.textContent=clean(current.caption);caption.hidden=!clean(current.caption)}
    if(kicker)kicker.textContent=clean(current.kicker||current.kind||'EVENTO').replace(/_/g,' ');
    if(closer)closer.hidden=!!current.blocking&&!current.allow_close;
    renderMedia(current);renderButtons(current);
    if(wrap)wrap.hidden=false;
  }

  function open(packet){
    packet=packet&&typeof packet==='object'?packet:{};
    if(current&&!packet.replace){queue.push(packet);return}
    render(packet);
  }

  function close(skipQueue){
    var wrap=byId('pk-event-modal-backdrop');
    if(wrap)wrap.hidden=true;
    var media=byId('pk-event-modal-media');
    if(media)Array.from(media.querySelectorAll('video')).forEach(function(v){try{v.pause()}catch(e){}});
    current=null;
    if(!skipQueue&&queue.length){
      var next=queue.shift();
      window.setTimeout(function(){render(next)},40);
    }
  }

  function clear(){
    queue.length=0;close(true);
  }

  function onPacket(args){open(packetFrom(args));return true}
  function bindEmitter(){
    if(emitterBound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_event_modal',onPacket);
    emitterBound=true;return true;
  }
  function init(){
    var tries=0;(function wait(){
      tries++;var ready=inject();bindEmitter();
      if(ready&&emitterBound)return;
      if(tries<180)setTimeout(wait,50);
    })();
  }

  window.PokerolEventModalV01=Object.freeze({BUILD:BUILD,open:open,close:close,clear:clear});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();