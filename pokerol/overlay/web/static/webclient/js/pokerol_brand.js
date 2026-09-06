(function(){
  'use strict';
  var BUILD='0.2.0-pokerol-bootstrap';

  function loadStylesheet(href,id){
    if(document.getElementById(id))return;
    var link=document.createElement('link');link.id=id;link.rel='stylesheet';link.href=href;document.head.appendChild(link);
  }
  function loadScript(src,id){
    if(document.getElementById(id))return;
    var script=document.createElement('script');script.id=id;script.src=src;script.async=false;document.head.appendChild(script);
  }
  function boot(){
    document.title='POKEROL';
    loadStylesheet('/static/webclient/css/pokerol_onboarding_v01.css?v=20260906b','pokerol-onboarding-css');
    loadScript('/static/webclient/js/pokerol_onboarding_v01.js?v=20260906b','pokerol-onboarding-js');
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
  window.PokerolBrand={BUILD:BUILD};
})();
