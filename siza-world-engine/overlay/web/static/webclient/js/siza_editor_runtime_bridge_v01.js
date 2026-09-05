(function () {
    "use strict";

    if (window.SizaEditorRuntimeBridgeLoaded) return;
    window.SizaEditorRuntimeBridgeLoaded = true;

    var LOOK_COMMAND = "look";
    var bound = false;
    var bindTries = 0;
    var lookBurstActive = false;
    var lastRoomSignature = "";
    var outputObserver = null;
    var suppressingOutput = false;

    function byId(id) {
        return document.getElementById(id);
    }

    function clean(value) {
        return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    }

    function cleanBlock(value) {
        return String(value == null ? "" : value)
            .replace(/\r/g, "")
            .replace(/[ \t]+\n/g, "\n")
            .replace(/\n[ \t]+/g, "\n")
            .replace(/\n{3,}/g, "\n\n")
            .trim();
    }

    function useful(value) {
        var text = clean(value);
        return text && text !== "—" && text !== "◇" && text !== "◊" && text !== "?";
    }

    function htmlToText(html) {
        var holder = document.createElement("div");
        holder.innerHTML = String(html == null ? "" : html)
            .replace(/<br\s*\/?\s*>/gi, "\n")
            .replace(/<\/(p|div|li|tr)>/gi, "\n");
        return String(holder.textContent || holder.innerText || "")
            .replace(/\u00a0/g, " ")
            .replace(/\r/g, "");
    }

    function normalizeRoomMarkers(text) {
        return String(text || "")
            .replace(/(\S)(Ves\s*:)/g, "$1\n$2")
            .replace(/(\S)(Salidas\s*:)/g, "$1\n$2")
            .replace(/(\S)(Personas presentes\s*:)/g, "$1\n$2")
            .replace(/(\S)(Personajes\s*:)/g, "$1\n$2")
            .replace(/(\S)(Characters\s*:)/g, "$1\n$2")
            .replace(/(\S)(Exits\s*:)/g, "$1\n$2")
            .replace(/(\S)(You see\s*:)/g, "$1\n$2");
    }

    function send(command) {
        if (!window.Evennia || typeof Evennia.isConnected !== "function" || !Evennia.isConnected()) {
            return false;
        }
        Evennia.msg("text", [command], {});
        return true;
    }

    function requestLookOnce() {
        send(LOOK_COMMAND);
    }

    function requestLookBurst() {
        if (lookBurstActive) return;
        lookBurstActive = true;
        [150, 900, 1800, 3200].forEach(function (delay) {
            window.setTimeout(requestLookOnce, delay);
        });
        window.setTimeout(function () { lookBurstActive = false; }, 3600);
    }

    function setPanelText(id, value) {
        var node = byId(id);
        var text = cleanBlock(value);
        if (!node || !text) return;
        node.textContent = text;
        node.style.whiteSpace = "pre-line";
        node.setAttribute("data-raw-description", text);
    }

    function clearInitialPlaceholder() {
        var node = byId("siza-scene-description");
        if (!node) return;
        if (/^the current location will be described here\.?$/i.test(clean(node.textContent))) {
            node.textContent = "Cargando observación del lugar…";
        }
        node.style.whiteSpace = "pre-line";
    }

    function hideTransportLog() {
        var output = byId("siza-messagewindow");
        if (!output) return;
        output.setAttribute("aria-hidden", "true");
        output.style.display = "none";
    }

    function clearTransportLog() {
        var output = byId("siza-messagewindow");
        if (!output || suppressingOutput) return;
        suppressingOutput = true;
        output.innerHTML = "";
        suppressingOutput = false;
    }

    function splitItems(value) {
        var text = clean(value);
        if (!useful(text)) return [];
        return text.replace(/\s+(?:and|y)\s+/gi, "\n").split(/\n|,/).map(clean).filter(useful);
    }

    function parseMetadata(lines, names) {
        for (var i = 0; i < lines.length; i += 1) {
            for (var j = 0; j < names.length; j += 1) {
                var prefix = names[j] + ":";
                if (lines[i].toLowerCase().indexOf(prefix.toLowerCase()) === 0) {
                    return { index: i, value: clean(lines[i].slice(prefix.length)) };
                }
            }
        }
        return { index: -1, value: "" };
    }

    function isSystemLine(line) {
        return /^(?:the current location will be described here|you become|connected session|available character|type help|command|no entiendo|help -|charcreate|chardelete|ic\b|public\b|\[object action\]|intentas\b|escribe\b|la accion requiere|la acción requiere|accion enviada|acción enviada|el world engine no devolvio|el world engine no devolvió)/i.test(clean(line));
    }

    function parseRoomText(raw) {
        var normalized = normalizeRoomMarkers(raw);
        var lines = normalized.split("\n").map(clean).filter(useful).filter(function (line) {
            return !isSystemLine(line);
        });
        if (!lines.length) return null;

        var exits = parseMetadata(lines, ["Exits", "Salidas"]);
        var characters = parseMetadata(lines, ["Characters", "Personas", "Personajes", "Personas presentes"]);
        var visible = parseMetadata(lines, ["You see", "Ves", "A la vista"]);
        var meta = [exits.index, characters.index, visible.index].filter(function (n) { return n >= 0; });
        if (!meta.length) return null;

        var firstMeta = Math.min.apply(null, meta);
        var header = lines.slice(0, firstMeta).filter(function (line) { return !isSystemLine(line); });
        if (!header.length) return null;

        var title = clean(header[0].replace(/\(#\d+\)\s*$/, ""));
        var description = cleanBlock(header.slice(1).join("\n"));
        if (!description && title && !/^(?:salidas|ves|personas|characters|exits|you see)\s*:/i.test(title)) {
            description = title;
        }
        if (!useful(title) && !useful(description)) return null;
        return {
            title: title || "Ubicación actual",
            description: description,
            exits: exits.value,
            characters: characters.value,
            visible: visible.value
        };
    }

    function buildObservation(room) {
        var blocks = [];
        if (room.description) blocks.push(cleanBlock(room.description));
        if (room.visible) blocks.push("Ves: " + clean(room.visible) + ".");
        if (room.characters) blocks.push("Personas presentes: " + clean(room.characters) + ".");
        if (room.exits) blocks.push("Salidas: " + clean(room.exits) + ".");
        return blocks.join("\n\n");
    }

    function renderRoom(room) {
        if (!room) return;
        var signature = clean([room.title, room.description, room.visible, room.characters, room.exits].join(" | "));
        if (!signature || signature === lastRoomSignature) return;
        lastRoomSignature = signature;

        if (room.title) {
            var location = byId("siza-location-label");
            var sceneTitle = byId("siza-scene-title");
            var placeholder = byId("siza-scene-placeholder-label");
            if (location) location.textContent = room.title;
            if (sceneTitle) sceneTitle.textContent = room.title;
            if (placeholder) placeholder.textContent = room.title;
        }

        setPanelText("siza-scene-description", buildObservation(room));

        if (window.SizaBookInteractionV04 && typeof window.SizaBookInteractionV04.renderRoomSnapshotActions === "function") {
            window.SizaBookInteractionV04.renderRoomSnapshotActions(room);
        }
        revealActionGroups();
    }

    function revealActionGroups() {
        var interactions = byId("siza-contextual-interactions");
        var movement = byId("siza-contextual-movement");
        var interactionGroup = byId("siza-contextual-interactions-group");
        var movementGroup = byId("siza-contextual-movement-group");
        var empty = byId("siza-contextual-actions-empty");
        var hasInteractions = !!(interactions && interactions.children.length);
        var hasMovement = !!(movement && movement.children.length);
        if (interactionGroup && hasInteractions) interactionGroup.hidden = false;
        if (movementGroup && hasMovement) movementGroup.hidden = false;
        if (empty) empty.hidden = hasInteractions || hasMovement;
    }

    function scrapeOutput() {
        if (suppressingOutput) return;
        var output = byId("siza-messagewindow");
        if (!output) return;
        var text = htmlToText(output.innerHTML || output.textContent || "");
        var room = parseRoomText(text);
        if (room) renderRoom(room);
        clearTransportLog();
    }

    function onText(args) {
        var html = args && args.length ? args[0] : "";
        var text = htmlToText(html);
        if (/\byou become\b/i.test(text) || /\bentras en\b/i.test(text)) {
            requestLookBurst();
        }
        var room = parseRoomText(text);
        if (room) renderRoom(room);
        window.setTimeout(scrapeOutput, 10);
    }

    function bindOutputObserver() {
        var output = byId("siza-messagewindow");
        if (!output || outputObserver) return;
        outputObserver = new MutationObserver(function () {
            window.setTimeout(scrapeOutput, 10);
        });
        outputObserver.observe(output, { childList: true, subtree: true, characterData: true });
        hideTransportLog();
        scrapeOutput();
    }

    function bind() {
        if (bound) return true;
        if (!window.Evennia || !Evennia.emitter) return false;
        bound = true;
        clearInitialPlaceholder();
        hideTransportLog();
        bindOutputObserver();
        revealActionGroups();

        Evennia.emitter.on("text", onText);
        Evennia.emitter.on("html", onText);
        Evennia.emitter.on("connection_open", function () {
            clearInitialPlaceholder();
            hideTransportLog();
            bindOutputObserver();
            revealActionGroups();
            requestLookBurst();
        });
        Evennia.emitter.on("siza_context_actions", function () {
            window.setTimeout(revealActionGroups, 20);
        });

        [250, 1000, 2200].forEach(function (delay) {
            window.setTimeout(function () {
                clearInitialPlaceholder();
                hideTransportLog();
                bindOutputObserver();
                revealActionGroups();
                requestLookBurst();
            }, delay);
        });
        return true;
    }

    function tryBindLoop() {
        bindTries += 1;
        if (bind()) return;
        if (bindTries < 80) window.setTimeout(tryBindLoop, 250);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", tryBindLoop);
    } else {
        tryBindLoop();
    }
})();