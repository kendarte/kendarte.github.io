(function () {
    "use strict";

    var BUILD = "0.1.0-world-combat-transition";
    var TRANSITION_ID = "siza-combat-book-transition-v02";
    var token = 0;

    function tr(es, en) {
        try {
            return localStorage.getItem("siza_player_language") === "en" ? en : es;
        } catch (error) {
            return es;
        }
    }

    function ensureTransition() {
        var client = document.getElementById("siza-book-client");
        if (!client) return null;
        var body = client.querySelector(".sizaBookBody") || client;
        var node = document.getElementById(TRANSITION_ID);
        if (!node) {
            node = document.createElement("div");
            node.id = TRANSITION_ID;
            node.className = "sizaCombatBookTransitionV02";
            node.innerHTML = '<i class="sizaCombatBladeV02 bladeA"></i><i class="sizaCombatBladeV02 bladeB"></i><div class="sizaCombatBookTitleV02"><small></small><strong></strong></div>';
            body.appendChild(node);
        }
        node.querySelector("small").textContent = tr("ENCUENTRO", "ENCOUNTER");
        node.querySelector("strong").textContent = tr("COMBATE", "COMBAT");
        return node;
    }

    function playBookTransition() {
        var node = ensureTransition();
        if (!node) return false;
        token += 1;
        var current = token;
        node.setAttribute("data-state", "closing");
        window.setTimeout(function () {
            if (current === token) node.setAttribute("data-state", "locked");
        }, 260);
        window.setTimeout(function () {
            if (current === token) node.setAttribute("data-state", "opening");
        }, 680);
        window.setTimeout(function () {
            if (current === token) node.removeAttribute("data-state");
        }, 1180);
        return true;
    }

    window.SizaCombatTransitionV01 = Object.freeze({
        BUILD: BUILD,
        playBookTransition: playBookTransition
    });
})();
