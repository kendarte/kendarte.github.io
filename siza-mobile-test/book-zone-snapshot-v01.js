(function () {
  "use strict";

  function sideSnapshot(side) {
    if (!side) return null;
    return {
      library: Array.isArray(side.library) ? side.library.length : 0,
      graveyard: Array.isArray(side.graveyard) ? side.graveyard.length : 0,
      exile: Array.isArray(side.exile) ? side.exile.length : 0
    };
  }

  function get() {
    try {
      if (typeof state === "undefined" || !state || !state.match) return null;
      return {
        player: sideSnapshot(state.match.player),
        enemy: sideSnapshot(state.match.enemy)
      };
    } catch (error) {
      return null;
    }
  }

  window.SizaBookZoneSnapshotV01 = Object.freeze({ get: get });
})();
