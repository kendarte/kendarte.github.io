(function () {
    "use strict";

    if (window.SizaObservationDescriptionGuardV01) return;

    var BUILD = "20260905-observation-description-guard-v1";
    var SECTION_RE = /(?:^|\s)(?:Personas presentes|Personas|A la vista|Ves|Salidas|Exits|Characters|You see)\s*:/i;
    var observer = null;
    var applying = false;

    function cleanBlock(value) {
        return String(value == null ? "" : value)
            .replace(/\r/g, "")
            .replace(/[ \t]+\n/g, "\n")
            .replace(/\n[ \t]+/g, "\n")
            .replace(/\n{3,}/g, "\n\n")
            .trim();
    }

    function descriptionOnly(value) {
        var text = cleanBlock(value);
        var match = SECTION_RE.exec(text);
        if (match) text = text.slice(0, match.index).trim();
        return text;
    }

    function apply() {
        if (applying) return;
        applying = true;
        var node = document.getElementById("siza-scene-description");
        if (node) {
            var current = cleanBlock(node.textContent);
            var next = descriptionOnly(current);
            if (next && next !== current) {
                node.textContent = next;
                node.setAttribute("data-raw-description", next);
                node.style.whiteSpace = "pre-line";
            }
            node.setAttribute("data-observation-description-guard", BUILD);
        }
        applying = false;
    }

    function bind() {
        var node = document.getElementById("siza-scene-description");
        if (node && !observer) {
            observer = new MutationObserver(apply);
            observer.observe(node, { childList: true, characterData: true, subtree: true });
        }
        apply();
    }

    function init() {
        bind();
        window.setTimeout(bind, 250);
        window.setTimeout(apply, 700);
        window.setTimeout(apply, 1600);
        window.setInterval(apply, 1000);
        if (window.Evennia && Evennia.emitter) {
            Evennia.emitter.on("siza_room_snapshot", function () { window.setTimeout(apply, 20); });
            Evennia.emitter.on("siza_room_state", function () { window.setTimeout(apply, 20); });
            Evennia.emitter.on("text", function () { window.setTimeout(apply, 20); });
        }
    }

    window.SizaObservationDescriptionGuardV01 = Object.freeze({
        build: BUILD,
        apply: apply,
        descriptionOnly: descriptionOnly
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
