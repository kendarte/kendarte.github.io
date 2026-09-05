(function () {
    "use strict";

    var MODES = ["EXPLORATION", "DIALOGUE", "COMBAT"];
    var history = [];
    var historyIndex = 0;
    var pendingCommand = null;
    var pendingTimer = null;
    var lastPacketSignature = "";
    var lastPacketAt = 0;
    var currentRoomKey = "";
    var currentRoomNotes = [];

    function byId(id) {
        return document.getElementById(id);
    }

    function safeClass(value) {
        return String(value || "out").replace(/[^a-zA-Z0-9 _-]/g, "");
    }

    function normalizeSpace(value) {
        return String(value || "").replace(/\s+/g, " ").trim();
    }

    function htmlToText(html) {
        var holder = document.createElement("div");
        var source = String(html === undefined || html === null ? "" : html)
            .replace(/<br\s*\/?\s*>/gi, "\n")
            .replace(/<\/(p|div|li|tr)>/gi, "\n");
        holder.innerHTML = source;
        return String(holder.textContent || holder.innerText || "")
            .replace(/\u00a0/g, " ")
            .replace(/\r/g, "");
    }

    function packetSignature(html) {
        return htmlToText(html).replace(/\s+/g, " ").trim();
    }

    function isDuplicatePacket(html) {
        var signature = packetSignature(html);
        var now = Date.now();
        if (signature && signature === lastPacketSignature && now - lastPacketAt < 10000) {
            return true;
        }
        lastPacketSignature = signature;
        lastPacketAt = now;
        return false;
    }

    function scrollOutput() {
        var output = byId("siza-messagewindow");
        if (output) {
            output.scrollTop = output.scrollHeight;
        }
    }

    function trimNarrative() {
        var output = byId("siza-messagewindow");
        if (!output) {
            return;
        }
        while (output.children.length > 50) {
            output.removeChild(output.firstChild);
        }
    }

    function appendHtml(html, cls) {
        var output = byId("siza-messagewindow");
        if (!output || html === null || html === undefined || normalizeSpace(htmlToText(html)) === "") {
            return;
        }
        var entry = document.createElement("div");
        entry.className = "sizaBookLine";
        entry.setAttribute("data-evennia-class", safeClass(cls));
        entry.innerHTML = String(html);
        output.appendChild(entry);
        trimNarrative();
        scrollOutput();
    }

    function appendText(text, cls) {
        var output = byId("siza-messagewindow");
        var value = normalizeSpace(text);
        if (!output || !value) {
            return;
        }
        var previous = output.lastElementChild;
        if (previous && previous.getAttribute("data-siza-text") === value) {
            return;
        }
        var entry = document.createElement("div");
        entry.className = "sizaBookLine";
        entry.setAttribute("data-evennia-class", safeClass(cls));
        entry.setAttribute("data-siza-text", value);
        entry.textContent = value;
        output.appendChild(entry);
        trimNarrative();
        scrollOutput();
    }

    function appendSystem(text, kind) {
        var output = byId("siza-messagewindow");
        if (!output) {
            return;
        }
        var value = normalizeSpace(text);
        var previous = output.lastElementChild;
        if (previous && previous.getAttribute("data-siza-text") === value) {
            return;
        }
        var entry = document.createElement("div");
        entry.className = "sizaBookLine sizaBookSystem " + safeClass(kind || "");
        entry.setAttribute("data-siza-text", value);
        entry.textContent = value;
        output.appendChild(entry);
        trimNarrative();
        scrollOutput();
    }

    function setConnection(label, state) {
        var el = byId("siza-connection-label");
        var root = byId("siza-book-client");
        if (el) {
            el.textContent = label;
        }
        if (root) {
            root.setAttribute("data-connection", state || "unknown");
        }
    }

    function setMode(mode) {
        var normalized = String(mode || "EXPLORATION").toUpperCase();
        if (MODES.indexOf(normalized) === -1) {
            normalized = "EXPLORATION";
        }
        var root = byId("siza-book-client");
        var label = byId("siza-mode-label");
        if (root) {
            root.setAttribute("data-mode", normalized);
        }
        if (label) {
            label.textContent = normalized === "EXPLORATION" ? "EXPLORACIÓN" :
                normalized === "DIALOGUE" ? "DIÁLOGO" : "COMBATE";
        }
        return normalized;
    }

    function setContext(context) {
        context = context || {};
        if (context.mode) {
            setMode(context.mode);
        }
        var values = {
            "siza-location-label": context.location,
            "siza-context-label": context.context,
            "siza-scene-title": context.sceneTitle,
            "siza-scene-kicker": context.sceneKicker,
            "siza-player-name": context.playerName,
            "siza-player-state": context.playerState
        };
        Object.keys(values).forEach(function (id) {
            var value = values[id];
            var el = byId(id);
            if (el && value !== undefined && value !== null && value !== "") {
                el.textContent = String(value);
            }
        });
    }

    function metadataValue(lines, prefix) {
        var lower = prefix.toLowerCase();
        for (var i = 0; i < lines.length; i += 1) {
            if (lines[i].toLowerCase().indexOf(lower) === 0) {
                return normalizeSpace(lines[i].slice(prefix.length));
            }
        }
        return "";
    }

    function metadataIndex(lines, prefixes) {
        for (var i = 0; i < lines.length; i += 1) {
            for (var j = 0; j < prefixes.length; j += 1) {
                if (lines[i].toLowerCase().indexOf(prefixes[j].toLowerCase()) === 0) {
                    return i;
                }
            }
        }
        return -1;
    }

    function parseRoomSnapshot(html) {
        var lines = htmlToText(html)
            .split("\n")
            .map(function (line) { return normalizeSpace(line); })
            .filter(function (line) { return !!line; });
        if (!lines.length) {
            return null;
        }

        var prefixes = ["Exits:", "Characters:", "You see:"];
        var sizaMetadataPrefixes = ["SIZA Scene Image:", "SIZA Scene Position:", "SIZA Scene Fit:", "SIZA Scene Alt:"];
        var titleIndex = -1;
        for (var i = 0; i < lines.length; i += 1) {
            if (/\(#\d+\)\s*$/.test(lines[i])) {
                titleIndex = i;
                break;
            }
        }
        if (titleIndex === -1) {
            // Normal players do not see database references such as (#9).
            // A room snapshot is still unambiguous when it contains Evennia's
            // authored room metadata after a title/description.
            var unprivilegedMeta = metadataIndex(lines, prefixes);
            if (unprivilegedMeta > 0) {
                titleIndex = 0;
            } else {
                return null;
            }
        }

        var body = lines.slice(titleIndex);
        var firstMeta = metadataIndex(body, prefixes);
        if (firstMeta === -1) {
            return null;
        }

        var lastMeta = firstMeta;
        for (var m = 0; m < body.length; m += 1) {
            for (var p = 0; p < prefixes.length; p += 1) {
                if (body[m].toLowerCase().indexOf(prefixes[p].toLowerCase()) === 0) {
                    lastMeta = Math.max(lastMeta, m);
                }
            }
        }

        var rawTitle = body[0];
        var dbrefMatch = rawTitle.match(/\(#(\d+)\)\s*$/);
        var cleanTitle = normalizeSpace(rawTitle.replace(/\(#\d+\)\s*$/, ""));

        return {
            key: rawTitle,
            title: cleanTitle,
            dbref: dbrefMatch ? dbrefMatch[1] : "",
            description: body.slice(1, firstMeta).join(" "),
            exits: metadataValue(body, "Exits:"),
            characters: metadataValue(body, "Characters:"),
            visible: metadataValue(body, "You see:"),
            sceneImage: metadataValue(body, "SIZA Scene Image:"),
            scenePosition: metadataValue(body, "SIZA Scene Position:"),
            sceneFit: metadataValue(body, "SIZA Scene Fit:"),
            sceneAlt: metadataValue(body, "SIZA Scene Alt:"),
            notes: body.slice(lastMeta + 1).filter(function (line) {
                return !sizaMetadataPrefixes.some(function (prefix) {
                    return line.toLowerCase().indexOf(prefix.toLowerCase()) === 0;
                });
            })
        };
    }

    function setFact(id, wrapId, value) {
        var el = byId(id);
        var wrap = byId(wrapId);
        var text = normalizeSpace(value);
        if (el) {
            el.textContent = text || "—";
        }
        if (wrap) {
            wrap.hidden = !text;
        }
    }

    function renderKnowledge(notes) {
        var panel = byId("siza-knowledge-panel");
        var summary = byId("siza-knowledge-summary");
        var list = byId("siza-knowledge-list");
        if (!panel || !summary || !list) {
            return;
        }
        list.innerHTML = "";
        notes.forEach(function (note) {
            var item = document.createElement("div");
            item.className = "sizaKnowledgeItem";
            item.textContent = note;
            list.appendChild(item);
        });
        panel.hidden = notes.length === 0;
        summary.textContent = notes.length === 1 ? "1 dato recordado" : notes.length + " datos recordados";
    }

    function renderSceneImage(room) {
        var shell = window.SizaBookShellV02;
        if (!shell || typeof shell.setSceneVisual !== "function") {
            return;
        }
        shell.setSceneVisual({
            url: room.sceneImage || "",
            label: room.sceneAlt || room.title || "",
            position: room.scenePosition || "center center",
            fit: room.sceneFit || "cover"
        });
    }

    function renderRoomSnapshot(room) {
        var description = byId("siza-scene-description");
        var location = byId("siza-location-label");
        var sceneTitle = byId("siza-scene-title");
        var context = byId("siza-context-label");
        var sameRoom = currentRoomKey === room.key;
        var previousNotes = currentRoomNotes.slice();
        var newNotes = [];

        if (location) {
            location.textContent = room.title;
        }
        if (sceneTitle) {
            sceneTitle.textContent = room.title;
        }
        if (context) {
            context.textContent = room.dbref ? "World Engine · escena persistente" : "World Engine";
        }
        if (description) {
            description.textContent = room.description || "Sin descripción disponible.";
        }
        renderSceneImage(room);

        setFact("siza-exits", "siza-exits-card", room.exits);
        setFact("siza-characters", "siza-characters-card", room.characters);
        setFact("siza-visible", "siza-visible-card", room.visible);
        renderKnowledge(room.notes);

        if (sameRoom) {
            room.notes.forEach(function (note) {
                if (previousNotes.indexOf(note) === -1) {
                    newNotes.push(note);
                }
            });
        }

        currentRoomKey = room.key;
        currentRoomNotes = room.notes.slice();

        newNotes.forEach(function (note) {
            appendText(note, "sizaBookDiscovery");
        });
    }

    function renderExplicitLook(room) {
        var details = [room.description || "Sin descripción disponible."];
        if (room.characters) {
            details.push("Personas: " + room.characters + ".");
        }
        if (room.visible) {
            details.push("A la vista: " + room.visible + ".");
        }
        if (room.exits) {
            details.push("Salidas: " + room.exits + ".");
        }
        appendText(details.join(" "), "sizaBookLook");
    }

    function setPending(isPending, command) {
        var root = byId("siza-book-client");
        var button = byId("siza-inputsend");
        var prompt = byId("siza-current-prompt");

        if (pendingTimer) {
            clearTimeout(pendingTimer);
            pendingTimer = null;
        }

        pendingCommand = isPending ? String(command || "") : null;
        if (root) {
            root.setAttribute("data-pending", isPending ? "true" : "false");
        }
        if (button) {
            button.disabled = !!isPending;
            button.textContent = isPending ? "ESPERANDO" : "ENVIAR";
        }
        if (prompt) {
            prompt.textContent = isPending && pendingCommand ? "Acción enviada: " + pendingCommand : "¿Qué haces?";
        }

        if (isPending) {
            pendingTimer = setTimeout(function () {
                if (!pendingCommand) {
                    return;
                }
                setPending(false);
                appendSystem("El World Engine no devolvió salida todavía. Puedes reintentar.", "warning");
            }, 8000);
        }
    }

    function handleServerPacket(html, cls) {
        var completedCommand = pendingCommand;
        setPending(false);
        if (html === null || html === undefined) {
            return;
        }
        if (isDuplicatePacket(html) && !completedCommand) {
            return;
        }
        var room = parseRoomSnapshot(html);
        if (room) {
            renderRoomSnapshot(room);
            if (/^(look|l|mirar|mira)$/i.test(normalizeSpace(completedCommand))) {
                renderExplicitLook(room);
            }
            if (window.SizaBookInteractionV04 && typeof window.SizaBookInteractionV04.requestContext === "function") {
                window.SizaBookInteractionV04.requestContext();
            }
            return;
        }
        appendHtml(html, cls);
        if (window.SizaBookInteractionV04 && typeof window.SizaBookInteractionV04.requestContext === "function") {
            window.SizaBookInteractionV04.requestContext();
        }
    }

    function onText(args, kwargs) {
        if (args && args.length) {
            handleServerPacket(args[0], kwargs && kwargs.cls);
        }
    }

    function onPrompt(args) {
        var prompt = byId("siza-prompt-label");
        setPending(false);
        if (prompt && args && args.length && args[0]) {
            prompt.innerHTML = String(args[0]);
        }
    }

    function onUnknown(cmdname, args, kwargs) {
        if ((cmdname === "html" || cmdname === "text") && args && args.length) {
            handleServerPacket(args[0], kwargs && kwargs.cls);
        }
    }

    function onConnectionOpen() {
        setPending(false);
        setConnection("Conectado", "open");
    }

    function onConnectionClose() {
        setPending(false);
        setConnection("Desconectado", "closed");
        appendSystem("La conexión con el World Engine se cerró.", "warning");
    }

    function onConnectionError() {
        setPending(false);
        setConnection("Error de conexión", "error");
        appendSystem("No se pudo mantener la conexión con el World Engine.", "error");
    }

    function sendText(raw) {
        var value = String(raw === undefined || raw === null ? "" : raw).trim();
        if (!value) {
            return false;
        }
        if (!window.Evennia || !Evennia.isConnected()) {
            appendSystem("Todavía no hay conexión con el World Engine.", "warning");
            return false;
        }
        if (pendingCommand) {
            return false;
        }
        history.push(value);
        if (history.length > 100) {
            history.shift();
        }
        historyIndex = history.length;
        setPending(true, value);
        Evennia.msg("text", [value], {});
        return true;
    }

    function submitInput() {
        var field = byId("siza-inputfield");
        if (!field) {
            return;
        }
        if (sendText(field.value)) {
            field.value = "";
        }
        field.focus();
    }

    function browseHistory(direction) {
        var field = byId("siza-inputfield");
        if (!field || !history.length) {
            return;
        }
        historyIndex = Math.max(0, Math.min(history.length, historyIndex + direction));
        field.value = historyIndex === history.length ? "" : history[historyIndex];
        requestAnimationFrame(function () {
            field.selectionStart = field.selectionEnd = field.value.length;
        });
    }

    function bindInput() {
        var field = byId("siza-inputfield");
        var button = byId("siza-inputsend");
        if (button) {
            button.addEventListener("click", submitInput);
        }
        if (field) {
            field.addEventListener("keydown", function (event) {
                if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submitInput();
                } else if (event.key === "ArrowUp" && !event.shiftKey) {
                    event.preventDefault();
                    browseHistory(-1);
                } else if (event.key === "ArrowDown" && !event.shiftKey) {
                    event.preventDefault();
                    browseHistory(1);
                }
            });
            field.focus();
        }
    }

    function init() {
        if (!window.Evennia) {
            setConnection("Cliente no disponible", "error");
            return;
        }

        Evennia.init();
        Evennia.emitter.on("text", onText);
        Evennia.emitter.on("prompt", onPrompt);
        Evennia.emitter.on("connection_open", onConnectionOpen);
        Evennia.emitter.on("connection_close", onConnectionClose);
        Evennia.emitter.on("connection_error", onConnectionError);
        Evennia.emitter.on("default", onUnknown);

        bindInput();
        setMode("EXPLORATION");
        setPending(false);
        setConnection(Evennia.isConnected() ? "Conectado" : "Conectando…", Evennia.isConnected() ? "open" : "connecting");
    }

    window.SizaWorldBookClient = Object.freeze({
        appendHtml: appendHtml,
        receiveText: onText,
        receivePrompt: onPrompt,
        connectionOpen: onConnectionOpen,
        connectionClose: onConnectionClose,
        connectionError: onConnectionError,
        parseRoomSnapshot: parseRoomSnapshot,
        sendText: sendText,
        setContext: setContext,
        setMode: setMode
    });

    $(document).ready(init);
})();
