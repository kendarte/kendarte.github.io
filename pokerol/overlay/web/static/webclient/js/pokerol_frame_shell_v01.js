(function(){
  'use strict';
  var BUILD='0.1.0-gba-frame-shell';
  var STORAGE='pokerol.project.frame.data';
  function byId(id){return document.getElementById(id)}
  function root(){return byId('pk-frame-root')}
  function setStatus(text){var n=byId('pk-frame-status');if(n)n.textContent=String(text||'')}
  function applyFrame(dataUrl){
    var r=root();if(!r)return;
    if(dataUrl){r.style.setProperty('--pk-frame-custom','url("'+String(dataUrl).replace(/"/g,'%22')+'")');}
    else r.style.removeProperty('--pk-frame-custom');
    var p=byId('pk-frame-preview');if(p){p.src=dataUrl||'';p.hidden=!dataUrl;}
  }
  function loadSaved(){try{var saved=localStorage.getItem(STORAGE)||'';if(saved)applyFrame(saved)}catch(e){}}
  function compressFrame(file){
    return new Promise(function(resolve,reject){
      if(!file||!/^image\//i.test(file.type||'')){reject(new Error('Ese archivo no es una imagen.'));return}
      if(file.size>8*1024*1024){reject(new Error('El frame supera 8 MB.'));return}
      var url=URL.createObjectURL(file),img=new Image();
      img.onload=function(){
        try{
          var maxW=1920,maxH=1080,scale=Math.min(1,maxW/img.naturalWidth,maxH/img.naturalHeight);
          var w=Math.max(1,Math.round(img.naturalWidth*scale)),h=Math.max(1,Math.round(img.naturalHeight*scale));
          var canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
          canvas.getContext('2d').drawImage(img,0,0,w,h);URL.revokeObjectURL(url);
          canvas.toBlob(function(blob){
            if(!blob){reject(new Error('No se pudo procesar el frame.'));return}
            var reader=new FileReader();reader.onload=function(){resolve(String(reader.result||''))};reader.onerror=function(){reject(new Error('No se pudo leer el frame.'))};reader.readAsDataURL(blob);
          },'image/webp',0.9);
        }catch(e){URL.revokeObjectURL(url);reject(e)}
      };
      img.onerror=function(){URL.revokeObjectURL(url);reject(new Error('No se pudo abrir la imagen.'))};img.src=url;
    });
  }
  function installRoot(){
    var client=byId('pokerol-client');if(!client)return false;if(root())return true;
    var r=document.createElement('div');r.id='pk-frame-root';r.className='pkFrameRoot';client.parentNode.insertBefore(r,client);r.appendChild(client);loadSaved();return true;
  }
  function injectEditor(){
    var menu=byId('pk-edit-menu'),stage=byId('pk-stage');if(!menu||!stage)return false;if(byId('pk-edit-frame'))return true;
    var button=document.createElement('button');button.id='pk-edit-frame';button.type='button';button.textContent='FRAME';menu.appendChild(button);
    var panel=document.createElement('aside');panel.id='pk-frame-panel';panel.className='pkFramePanel';panel.hidden=true;
    panel.innerHTML='<div class="pkFramePanelHead"><strong>FRAME DE CONSOLA</strong><button id="pk-frame-close" type="button">×</button></div><img id="pk-frame-preview" class="pkFramePreview" alt="Preview del frame" hidden><div class="pkFramePanelActions"><button id="pk-frame-load" type="button">CAMBIAR FRAME</button><button id="pk-frame-reset" type="button">FRAME DEFAULT</button></div><input id="pk-frame-file" type="file" accept="image/png,image/jpeg,image/webp" hidden><div id="pk-frame-status" class="pkFramePanelStatus"></div><div class="pkFramePanelHint">Usa un frame 16:9. La interfaz se compacta automáticamente dentro de la pantalla central.</div>';
    stage.appendChild(panel);var file=byId('pk-frame-file');
    button.addEventListener('click',function(){panel.hidden=!panel.hidden;menu.hidden=true});
    byId('pk-frame-close').addEventListener('click',function(){panel.hidden=true});
    byId('pk-frame-load').addEventListener('click',function(){file.value='';file.click()});
    byId('pk-frame-reset').addEventListener('click',function(){try{localStorage.removeItem(STORAGE)}catch(e){}applyFrame('');setStatus('Frame restaurado al diseño default del proyecto.');});
    file.addEventListener('change',function(){var selected=file.files&&file.files[0];if(!selected)return;setStatus('Procesando frame…');compressFrame(selected).then(function(dataUrl){try{localStorage.setItem(STORAGE,dataUrl)}catch(e){throw new Error('No hay espacio suficiente para guardar el frame en el navegador.')}applyFrame(dataUrl);setStatus('Frame guardado y aplicado.');}).catch(function(err){setStatus(err&&err.message?err.message:'No se pudo cambiar el frame.');});});
    try{var saved=localStorage.getItem(STORAGE)||'';if(saved){var p=byId('pk-frame-preview');if(p){p.src=saved;p.hidden=false}}}catch(e){}
    return true;
  }
  function init(){var tries=0;(function wait(){tries++;var okRoot=installRoot(),okEditor=injectEditor();if(okRoot&&okEditor)return;if(tries<200)setTimeout(wait,50)})();}
  window.PokerolFrameShellV01=Object.freeze({BUILD:BUILD,applyFrame:applyFrame});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();