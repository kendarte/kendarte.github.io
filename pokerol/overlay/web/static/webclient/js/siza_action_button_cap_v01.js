(function () {
    "use strict";

    if (window.SizaActionButtonCapV01) return;

    var MAX_PER_GROUP = 5;
    var CAP_BUILD = "20260905-action-button-cap-v1";
    var observer = null;
    var applying = false;

    function byId(id) {
        return document.getElementById(id);
    }

    function capGroup(rootId, groupId) {
        var root = byId(rootId);
        var group = byId(groupId);
        if (!root) return 0;

        var buttons = Array.prototype.slice.call(root.children || []).filter(function (node) {
            return node && node.tagName && node.tagName.toLowerCase() === "button";
        });

        buttons.forEach(function (button, index) {
            if (index < MAX_PER_GROUP) {
                button.hidden = false;
                button.style.display = "";
                button.removeAttribute("data-siza-overflow-hidden");
            } else {
                button.hidden = true;
                button.style.display = "none";
                button.setAttribute("data-siza-overflow-hidden", "true");
            }
        });

        var visible = Math.min(buttons.length, MAX_PER_GROUP);
        if (group) group.hidden = visible === 0;
        return visible;
    }

    function applyCap() {
        if (applying) return;
        applying = true;
        var visibleInteractions = capGroup("siza-contextual-interactions", "siza-contextual-interactions-group");
        var visibleMovement = capGroup("siza-contextual-movement", "siza-contextual-movement-group");
        var empty = byId("siza-contextual-actions-empty");
        var root = byId("siza-contextual-actions");
        if (empty) empty.hidden = (visibleInteractions + visibleMovement) > 0;
        if (root) {
            root.setAttribute("data-visible-interactions", String(visibleInteractions));
            root.setAttribute("data-visible-movement", String(visibleMovement));
            root.setAttribute("data-max-per-group", String(MAX_PER_GROUP));
            root.setAttribute("data-action-cap-build", CAP_BUILD);
        }
        applying = false;
    }

    function scheduleCap() {
        window.setTimeout(applyCap, 0);
        window.setTimeout(applyCap, 50);
        window.setTimeout(applyCap, 200);
    }

    function bindObserver() {
        var root = byId("siza-contextual-actions");
        if (!root || observer) return;
        observer = new MutationObserver(scheduleCap);
        observer.observe(root, { childList: true, subtree: true, attributes: true });
    }

    function init() {
        bindObserver();
        scheduleCap();
        if (window.Evennia && Evennia.emitter) {
            Evennia.emitter.on("siza_context_actions", scheduleCap);
            Evennia.emitter.on("siza_room_snapshot", scheduleCap);
            Evennia.emitter.on("siza_room_state", scheduleCap);
            Evennia.emitter.on("text", scheduleCap);
        }
        window.setInterval(applyCap, 1000);
    }

    window.SizaActionButtonCapV01 = Object.freeze({
        build: CAP_BUILD,
        maxPerGroup: MAX_PER_GROUP,
        apply: applyCap
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
