(function () {
  "use strict";

  function isOnboardingTextField(target) {
    if (!target || !target.closest) return false;
    var root = target.closest("#pk-onboarding-root");
    if (!root) return false;
    return target.matches("input, textarea, [contenteditable='true']");
  }

  // Evennia's webclient installs global keyboard handlers. During the POKEROL
  // login/onboarding screen the form fields must own their keystrokes instead.
  // Stop propagation at window-capture level while preserving the browser's
  // normal text-editing default action.
  ["keydown", "keypress", "keyup"].forEach(function (eventName) {
    window.addEventListener(eventName, function (event) {
      if (isOnboardingTextField(event.target)) {
        event.stopImmediatePropagation();
      }
    }, true);
  });

  function prepareAuthFields(root) {
    if (!root) return;
    root.querySelectorAll("#pk-auth-name, #pk-auth-pass").forEach(function (field) {
      field.removeAttribute("readonly");
      field.disabled = false;
      field.style.pointerEvents = "auto";
      field.style.userSelect = "text";
      field.setAttribute("autocapitalize", "none");
      field.setAttribute("spellcheck", "false");
    });
  }

  function watchOnboarding() {
    prepareAuthFields(document.getElementById("pk-onboarding-root"));
    var observer = new MutationObserver(function () {
      prepareAuthFields(document.getElementById("pk-onboarding-root"));
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

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
    watchOnboarding();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", brand);
  } else {
    brand();
  }
})();
