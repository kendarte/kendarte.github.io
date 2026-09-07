(function(){
  'use strict';
  function byId(id){return document.getElementById(id)}
  function show(node,on){if(node)node.hidden=!on}

  function inject(){
    if(byId('pk-edit-menu-toggle'))return true;
    var tools=document.querySelector('.pkBackgroundTools'),stage=byId('pk-stage');
    if(!tools||!stage)return false;

    var load=byId('pk-load-background'),reset=byId('pk-reset-background'),status=byId('pk-bg-status');
    if(load)load.classList.add('pkEditorInternalControl');
    if(reset)reset.classList.add('pkEditorInternalControl');
    if(status)status.classList.add('pkEditorInternalControl');

    var edit=document.createElement('button');
    edit.id='pk-edit-menu-toggle';edit.type='button';edit.textContent='EDIT';edit.title='Editar escena';
    tools.insertBefore(edit,tools.firstChild);

    var menu=document.createElement('aside');menu.id='pk-edit-menu';menu.className='pkEditMenu';menu.hidden=true;
    menu.innerHTML=''
      +'<div class="pkEditMenuHead"><strong>EDITAR ESCENA</strong><button id="pk-edit-menu-close" type="button" aria-label="Cerrar">×</button></div>'
      +'<button id="pk-edit-background" type="button">FONDO</button>'
      +'<button id="pk-edit-background-reset" type="button">RESET FONDO</button>'
      +'<button id="pk-edit-hotspots" type="button">HOTSPOTS</button>'
      +'<button id="pk-edit-player" type="button">PLAYER</button>';
    stage.appendChild(menu);

    var hotspot=document.createElement('aside');hotspot.id='pk-hotspot-panel';hotspot.className='pkHotspotPanel';hotspot.hidden=true;
    hotspot.innerHTML=''
      +'<div class="pkHotspotPanelHead"><strong>HOTSPOTS</strong><div><button id="pk-hotspot-new" type="button">+ NUEVO</button><button id="pk-hotspot-close" type="button" aria-label="Cerrar">×</button></div></div>'
      +'<div class="pkHotspotField"><label for="pk-hotspot-name">NOMBRE</label><input id="pk-hotspot-name" type="text" maxlength="80" placeholder="Nombre visible"></div>'
      +'<div class="pkHotspotField"><label for="pk-hotspot-command">COMANDO · SOLO MANUAL</label><input id="pk-hotspot-command" type="text" maxlength="160" placeholder="ej. observar cartel"></div>'
      +'<div class="pkHotspotXY">'
        +'<div class="pkHotspotField"><label for="pk-hotspot-x">X %</label><input id="pk-hotspot-x" type="number" min="2" max="98" step="0.1"></div>'
        +'<div class="pkHotspotField"><label for="pk-hotspot-y">Y %</label><input id="pk-hotspot-y" type="number" min="0" max="92" step="0.1"></div>'
      +'</div>'
      +'<div class="pkHotspotXY pkHotspotSizeFields">'
        +'<div class="pkHotspotField"><label for="pk-hotspot-width">ANCHO · PX</label><input id="pk-hotspot-width" type="number" min="12" max="600" step="1"></div>'
        +'<div class="pkHotspotField"><label for="pk-hotspot-height">ALTO · PX</label><input id="pk-hotspot-height" type="number" min="12" max="500" step="1"></div>'
      +'</div>'
      +'<div class="pkHotspotActions">'
        +'<button id="pk-hotspot-save" type="button" class="pkWide">GUARDAR</button>'
        +'<button id="pk-hotspot-delete" type="button" class="pkWide pkDanger" disabled>BORRAR HOTSPOT</button>'
        +'<button id="pk-hotspot-hide" type="button" hidden disabled>OCULTAR</button>'
      +'</div>'
      +'<div class="pkHotspotHint">Arrastra para mover. ANCHO y ALTO cambian el área clickeable. BORRAR elimina el hotspot visual del Room.</div>';
    stage.appendChild(hotspot);

    var player=document.createElement('aside');player.id='pk-player-panel';player.className='pkPlayerPanel';player.hidden=true;
    player.innerHTML=''
      +'<div class="pkPlayerPanelHead"><strong>PLAYER</strong><button id="pk-player-close" type="button" aria-label="Cerrar">×</button></div>'
      +'<div class="pkPlayerHint">Arrastra al entrenador para moverlo. Usa el tirador amarillo para cambiar su tamaño.</div>'
      +'<div class="pkPlayerFields">'
        +'<label>X %<input id="pk-player-x" type="number" min="1" max="99" step="0.1"></label>'
        +'<label>Y px<input id="pk-player-y" type="number" min="0" max="500" step="1"></label>'
        +'<label>ESCALA<input id="pk-player-scale" type="number" min="0.35" max="3" step="0.05"></label>'
      +'</div>'
      +'<div class="pkPlayerActions"><button id="pk-player-save" type="button">GUARDAR</button><button id="pk-player-reset" type="button">RESET</button></div>';
    stage.appendChild(player);

    edit.addEventListener('click',function(){show(menu,menu.hidden)});
    byId('pk-edit-menu-close').addEventListener('click',function(){show(menu,false)});
    byId('pk-edit-background').addEventListener('click',function(){show(menu,false);if(load)load.click()});
    byId('pk-edit-background-reset').addEventListener('click',function(){show(menu,false);if(reset)reset.click()});
    byId('pk-edit-hotspots').addEventListener('click',function(){show(menu,false)});
    byId('pk-edit-player').addEventListener('click',function(){show(menu,false)});
    byId('pk-hotspot-close').addEventListener('click',function(){var b=byId('pk-edit-hotspots');if(b&&b.classList.contains('pkActive'))b.click();else show(hotspot,false)});

    return true;
  }
  function init(){var tries=0;(function wait(){tries++;if(inject())return;if(tries<120)setTimeout(wait,50)})()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();