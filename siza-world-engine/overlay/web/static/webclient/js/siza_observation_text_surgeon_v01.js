(function () {
    "use strict";

    if (window.SizaObservationTextSurgeonV01) return;

    var BUILD = "20260905-observation-text-surgeon-v2-promote-room-move";
    var MARKER_RE = /\b(?:Personas presentes|Personas|A la vista|Ves|Salidas|Exits|Characters|You see|SIZA Scene Image|SIZA Scene Position|SIZA Scene Fit|SIZA Scene Alt)\s*:/i;
    var PLACEHOLDER_RE = /^\s*the current location will be described here\.?\s*(?:[-–—_]{3,}\s*)?/i;
    var ENTER_RE = /^\s*(?:Entras en|Entras a|Llegas a|You enter|You arrive at|You arrive in)\s+(.+?)\.?\s*$/i;
    var ENTER_PREFIX_RE = /^\s*(?:Entras en|Entras a|Llegas a|You enter|You arrive at|You arrive in)\s+[^.\n]+\.?\s*/i;
    var UNKNOWN_RE = /^\s*(?:No entiendo esa acci[oó]n todav[ií]a\.?|I do not understand that action yet\.?)\s*$/i;
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
        var text = cleanBlock(value).replace(PLACEHOLDER_RE, "").replace(ENTER_PREFIX_RE, "").trim();
        var match = MARKER_RE.exec(text);
        if (match) text = text.slice(0, match.index).trim();
        text = text.replace(/^[-–—_]{3,}\s*/g, "").trim();
        return cleanBlock(text);
    }

    function looksLikeNarrative(value) {
        var text = narrativeOnly(value);
        if (!text || UNKNOWN_RE.test(text)) return false;
        if (/^(?:Conectado|Desconectado|Connecting|Connected|Disconnected|Error de conexi[oó]n|Command )/i.test(text)) return false;
        if (/^(?:Interacciones|Desplazamiento|¿Qu[eé] haces\?|What do you do\?)/i.test(text)) return false;
        return text.length >= 24;
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

    function lineText(node) {
        return cleanBlock(node && (node.textContent || node.innerText || ""));
    }

    function hideLine(node, reason) {
        if (!node) return;
        node.hidden = true;
        node.setAttribute("data-siza-hidden-room-dump", reason || BUILD);
    }

    function lineHasRoomDump(text) {
        return MARKER_RE.test(text) || PLACEHOLDER_RE.test(text) || /the current location will be described here/i.test(text);
    }

    function promoteLatestMovedRoom(lines) {
        var promoted = "";
        for (var i = 0; i < lines.length; i += 1) {
            var raw = lineText(lines[i]);
            if (!raw || !ENTER_RE.test(raw)) continue;

            for (var j = i + 1; j < Math.min(lines.length, i + 5); j += 1) {
                var nextRaw = lineText(lines[j]);
                if (!nextRaw || ENTER_RE.test(nextRaw) || UNKNOWN_RE.test(nextRaw)) continue;
                if (!looksLikeNarrative(nextRaw)) continue;

                promoted = narrativeOnly(nextRaw);
                setDescription(promoted);
                hideLine(lines[i], BUILD + "-enter-line");
                hideLine(lines[j], BUILD + "-room-description-line");

                if (i > 0 && UNKNOWN_RE.test(lineText(lines[i - 1]))) {
                    hideLine(lines[i - 1], BUILD + "-stale-unknown-before-move");
                }
                break;
            }
        }
        return promoted;
    }

    function cleanOutputLines(currentDescription) {
        var output = document.getElementById("siza-messagewindow");
        if (!output) return;

        var lines = Array.prototype.slice.call(output.querySelectorAll(".sizaBookLine"));
        var promoted = promoteLatestMovedRoom(lines);
        if (promoted) currentDescription = promoted;

        lines.forEach(function (line) {
            if (line.hidden) return;
            var raw = lineText(line);
            if (!raw) return;

            if (UNKNOWN_RE.test(raw)) {
                hideLine(line, BUILD + "-unknown-action-noise");
                return;
            }

            if (!lineHasRoomDump(raw)) return;

            var clean = narrativeOnly(raw);
            if (clean && (isPlaceholder(currentDescription) || cleanBlock(currentDescription) === clean)) {
                setDescription(clean);
                hideLine(line, BUILD + "-room-dump");
                return;
            }

            if (clean) {
                line.textContent = clean;
                line.style.whiteSpace = "pre-line";
                line.setAttribute("data-siza-observation-surgeon", BUILD);
            } else {
                hideLine(line, BUILD + "-empty-room-dump");
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