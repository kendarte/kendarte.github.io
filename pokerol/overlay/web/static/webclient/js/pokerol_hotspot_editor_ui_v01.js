(function(){
  'use strict';
  function byId(id){return document.getElementById(id)}
  function inject(){
    if(byId('pk-edit-hotspots'))return true;
    var tools=document.querySelector('.pkBackgroundTools'),stage=byId('pk-stage');
    if(!tools||!stage)return false;

    var edit=document.createElement('button');edit.id='pk-edit-hotspots';edit.type='button';edit.textContent='HOTSPOTS';edit.title='Editar hotspots de este Room';
    var reset=byId('pk-reset-background');tools.insertBefore(edit,reset||null);

    var panel=document.createElement('aside');panel.id='pk-hotspot-panel';panel.className='pkHotspotPanel';panel.hidden=true;
    panel.innerHTML=''
      +'<div class="pkHotspotPanelHead"><strong>HOTSPOTS</strong><button id="pk-hotspot-new" type="button">+ NUEVO</button></div>'
      +'<div class="pkHotspotField"><label for="pk-hotspot-name">NOMBRE</label><input id="pk-hotspot-name" type="text" maxlength="80" placeholder="Nombre visible"></div>'
      +'<div class="pkHotspotField"><label for="pk-hotspot-command">COMANDO · SOLO MANUAL</label><input id="pk-hotspot-command" type="text" maxlength="160" placeholder="ej. observar cartel"></div>'
      +'<div class="pkHotspotXY">'
        +'<div class="pkHotspotField"><label for="pk-hotspot-x">X %</label><input id="pk-hotspot-x" type="number" min="2" max="98" step="0.1"></div>'
        +'<div class="pkHotspotField"><label for="pk-hotspot-y">Y %</label><input id="pk-hotspot-y" type="number" min="0" max="92" step="0.1"></div>'
      +'</div>'
      +'<div class="pkHotspotActions">'
        +'<button id="pk-hotspot-save" type="button" class="pkWide">GUARDAR</button>'
        +'<button id="pk-hotspot-hide" type="button" disabled>OCULTAR</button>'
        +'<button id="pk-hotspot-delete" type="button" disabled>BORRAR</button>'
      +'</div>'
      +'<div class="pkHotspotHint">Arrastra un hotspot directamente sobre la escena. Los existentes del World Engine se renombran/mueven; los nuevos son hotspots visuales locales.</div>';
    stage.appendChild(panel);
    return true;
  }
  function init(){var tries=0;(function wait(){tries++;if(inject())return;if(tries<100)setTimeout(wait,50)})()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
