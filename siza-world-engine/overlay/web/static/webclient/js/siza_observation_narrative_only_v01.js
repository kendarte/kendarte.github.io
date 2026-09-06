(function () {
    "use strict";

    if (window.SizaObservationNarrativeOnlyV01) return;

    var BUILD = "20260905-observation-narrative-only-v2-buttons-safe";
    var MARKERS = [
        "Personas presentes:",
        "Personas:",
        "A la vista:",
        "Ves:",
        "Salidas:",
        "Exits:",
        "Characters:",
        "You see:",
        "SIZA Scene Image:",
        "SIZA Scene Position:",
        "SIZA Scene Fit:",
        "SIZA Scene Alt:"
    ];

    function cleanBlock(value) {
        return String(value == null ? "" : value)
            .replace(/\r/g, "\n")
            .replace(/[ \t]+\n/g, "\n")
            .replace(/\n[ \t]+/g, "\n")
            .replace(/\n{3,}/g, "\n\n")
            .trim();
    }

    function removePlaceholder(text) {
        return cleanBlock(text)
            .replace(/^\s*the current location will be described here\.??\s*(?:[-–—_]{3,}\s*)?/i, "")
            .trim();
    }

    function narrativeOnly(value) {
        var text = removePlaceholder(value);
        var lower = text.toLowerCase();
        var cutAt = text.length;
        MARKERS.forEach(function (marker) {
            var index = lower.indexOf(marker.toLowerCase());
            if (index >= 0 && index < cutAt) cutAt = index;
        });
        return cleanBlock(text.slice(0, cutAt));
    }

    function setNodeNarrativeOnly(node) {
        if (!node) return;
        var current = cleanBlock(node.textContent || node.innerText || "");
        var next = narrativeOnly(current);
        if (next !== current) {
            node.textContent = next || "Este lugar todavía no tiene descripción narrativa importada desde el Map Editor.";
            node.style.whiteSpace = "pre-line";
        }
        node.setAttribute("data-siza-narrative-only", BUILD);
    }

    function apply() {
        setNodeNarrativeOnly(document.getElementById("siza-scene-description"));

        Array.prototype.forEach.call(document.querySelectorAll(".sizaBookLine"), function (node) {
            var text = cleanBlock(node.textContent || node.innerText || "");
            if (/\b(Personas presentes|Personas|A la vista|Ves|Salidas|Exits|Characters|You see)\s*:/i.test(text) || /the current location will be described here/i.test(text)) {
                setNodeNarrativeOnly(node);
            }
        });
    }

    function init() {
        apply();
        window.setTimeout(apply, 50);
        window.setTimeout(apply, 250);
        window.setTimeout(apply, 800);
        window.setInterval(apply, 250);
        if (window.Evennia && Evennia.emitter) {
            Evennia.emitter.on("text", function () { window.setTimeout(apply, 0); });
            Evennia.emitter.on("siza_room_snapshot", function () { window.setTimeout(apply, 0); });
            Evennia.emitter.on("siza_room_state", function () { window.setTimeout(apply, 0); });
        }
    }

    window.SizaObservationNarrativeOnlyV01 = Object.freeze({
        build: BUILD,
        apply: apply,
        narrativeOnly: narrativeOnly
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
