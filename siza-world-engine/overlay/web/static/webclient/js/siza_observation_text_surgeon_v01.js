(function () {
    "use strict";

    if (window.SizaObservationTextSurgeonV01) return;

    var BUILD = "20260905-observation-text-surgeon-v1";
    var MARKER_RE = /\b(?:Personas presentes|Personas|A la vista|Ves|Salidas|Exits|Characters|You see|SIZA Scene Image|SIZA Scene Position|SIZA Scene Fit|SIZA Scene Alt)\s*:/i;
    var PLACEHOLDER_RE = /^\s*the current location will be described here\.?\s*(?:[-–—_]{3,}\s*)?/i;
    var FALLBACK = "Este lugar todavía no tiene descripción narrativa importada desde el Map Editor.";
    var applying = false;

    function cleanBlock(value) {
        return String(value == null ? "" : value)
            .replace(/\r/g, "\n")
            .replace(/[ \t]+\n/g, "\n")
            .replace(/\n[ \t]+/g, "\n")
            .replace(/\n{3,}/g, "\n\n")
            .trim();
    }

    function isPlaceholder(value) {
        var text = cleanBlock(value).toLowerCase();
        return !text || text === "the current location will be described here." || text === "the current location will be described here" || text === FALLBACK.toLowerCase();
    }

    function narrativeOnly(value) {
        var text = cleanBlock(value).replace(PLACEHOLDER_RE, "").trim();
        var match = MARKER_RE.exec(text);
        if (match) text = text.slice(0, match.index).trim();
        text = text.replace(/^[-–—_]{3,}\s*/g, "").trim();
        return cleanBlock(text);
    }

    function setDescription(text) {
        var node = document.getElementById("siza-scene-description");
        if (!node) return;
        var clean = narrativeOnly(text);
        if (!clean) return;
        if (cleanBlock(node.textContent) !== clean) {
            node.textContent = clean;
            node.setAttribute("data-raw-description", clean);
            node.style.whiteSpace = "pre-line";
        }
        node.setAttribute("data-siza-observation-surgeon", BUILD);
    }

    function cleanDescriptionNode() {
        var node = document.getElementById("siza-scene-description");
        if (!node) return "";
        var current = cleanBlock(node.textContent || node.innerText || "");
        var clean = narrativeOnly(current);
        if (clean && clean !== current) {
            node.textContent = clean;
            node.setAttribute("data-raw-description", clean);
            node.style.whiteSpace = "pre-line";
        }
        node.setAttribute("data-siza-observation-surgeon", BUILD);
        return cleanBlock(node.textContent || node.innerText || "");
    }

    function lineHasRoomDump(text) {
        return MARKER_RE.test(text) || PLACEHOLDER_RE.test(text) || /the current location will be described here/i.test(text);
    }

    function cleanOutputLines(currentDescription) {
        var output = document.getElementById("siza-messagewindow");
        if (!output) return;

        Array.prototype.forEach.call(output.querySelectorAll(".sizaBookLine"), function (line) {
            var raw = cleanBlock(line.textContent || line.innerText || "");
            if (!raw || !lineHasRoomDump(raw)) return;

            var clean = narrativeOnly(raw);
            if (clean && (isPlaceholder(currentDescription) || cleanBlock(currentDescription) === clean)) {
                setDescription(clean);
                line.hidden = true;
                line.setAttribute("data-siza-hidden-room-dump", BUILD);
                return;
            }

            if (clean) {
                line.textContent = clean;
                line.style.whiteSpace = "pre-line";
                line.setAttribute("data-siza-observation-surgeon", BUILD);
            } else {
                line.hidden = true;
                line.setAttribute("data-siza-hidden-room-dump", BUILD);
            }
        });
    }

    function apply() {
        if (applying) return;
        applying = true;
        var current = cleanDescriptionNode();
        cleanOutputLines(current);
        cleanDescriptionNode();
        applying = false;
    }

    function bindObservers() {
        var description = document.getElementById("siza-scene-description");
        var output = document.getElementById("siza-messagewindow");
        if (description && !description.getAttribute("data-siza-surgeon-observed")) {
            description.setAttribute("data-siza-surgeon-observed", "1");
            new MutationObserver(apply).observe(description, { childList: true, characterData: true, subtree: true });
        }
        if (output && !output.getAttribute("data-siza-surgeon-observed")) {
            output.setAttribute("data-siza-surgeon-observed", "1");
            new MutationObserver(apply).observe(output, { childList: true, characterData: true, subtree: true });
        }
    }

    function init() {
        bindObservers();
        apply();
        [20, 80, 160, 350, 700, 1200, 2200].forEach(function (delay) {
            window.setTimeout(function () { bindObservers(); apply(); }, delay);
        });
        window.setInterval(function () { bindObservers(); apply(); }, 500);
        if (window.Evennia && Evennia.emitter) {
            Evennia.emitter.on("text", function () { window.setTimeout(apply, 0); });
            Evennia.emitter.on("siza_room_snapshot", function () { window.setTimeout(apply, 0); });
            Evennia.emitter.on("siza_room_state", function () { window.setTimeout(apply, 0); });
        }
    }

    window.SizaObservationTextSurgeonV01 = Object.freeze({
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