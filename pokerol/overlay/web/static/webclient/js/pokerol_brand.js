(function () {
  "use strict";
  function brand() {
    var locationLabel = document.getElementById("siza-location-label");
    var visualLabel = document.getElementById("siza-scene-visual-label");
    if (locationLabel && /SIZA WORLD ENGINE/i.test(locationLabel.textContent || "")) {
      locationLabel.textContent = "POKEROL WORLD ENGINE";
    }
    if (visualLabel && /SIZA WORLD ENGINE/i.test(visualLabel.textContent || "")) {
      visualLabel.textContent = "POKEROL WORLD ENGINE";
    }
    document.title = (document.title || "").replace(/SIZA/gi, "POKEROL") || "POKEROL";
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", brand);
  } else {
    brand();
  }
})();
