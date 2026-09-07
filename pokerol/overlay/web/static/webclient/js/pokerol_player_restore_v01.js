(function(){
  'use strict';
  // Compatibility API only. PLAYER editor owns both state and rendering.
  window.PokerolPlayerRestoreV01=Object.freeze({
    BUILD:'2.0.0-editor-delegate',
    refresh:function(){var e=window.PokerolPlayerEditorV01;return e&&e.refresh()},
    applyPacket:function(packet){var e=window.PokerolPlayerEditorV01;return e?e.applyPacket(packet):false}
  });
})();
