(function () {
    "use strict";

    if (window.SizaEditorRuntimeBridgeLoaded) return;
    window.SizaEditorRuntimeBridgeLoaded = true;

    var LOOK_COMMAND = "look";
    var lastLookAt = 0;
    var bindTries = 0;
    var bound = false;
    var hasRoom = false;
    var inCharacter = false;

    function byId(id) {
        return document.getElementById(id);
    }

    function clean(value) {
        return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
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
        return String(holder.textContent || holder.innerText || "").replace(/\u00a0/g, " ").replace(/\r/g, "");
    }

    function send(command) {
        if (!window.Evennia || typeof Evennia.isConnected !== "function" || !Evennia.isConnected()) {
            return false;
        }
        Evennia.msg("text", [command], {});
        return true;
    }

    function requestLook(force) {
        if (!inCharacter) return;
        var now = Date.now();
        if (!force && now - lastLookAt < 1400) return;
        lastLookAt = now;
        send(LOOK_COMMAND);
    }

    function setText(id, value) {
        var node = byId(id);
        var text = clean(value);
        if (node && useful(text)) {
            node.textContent = text;
            node.setAttribute("data-raw-description", text);
        }
    }

    function clearActions() {
        var interactions = byId("siza-contextual-interactions");
        var movement = byId("siza-contextual-movement");
        if (interactions) interactions.innerHTML = "";
        if (movement) movement.innerHTML = "";
    }

    function finishActions() {
        var interactions = byId("siza-contextual-interactions");
        var movement = byId("siza-contextual-movement");
        var empty = byId("siza-contextual-actions-empty");
        var iCount = interactions ? interactions.children.length : 0;
        var mCount = movement ? movement.children.length : 0;
        if (empty) empty.hidden = (iCount + mCount) > 0;
        var iGroup = byId("siza-contextual-interactions-group");
        var mGroup = byId("siza-contextual-movement-group");
        if (iGroup) iGroup.hidden = iCount === 0;
        if (mGroup) mGroup.hidden = mCount === 0;
    }

    function makeButton(label, command, className) {
        var text = clean(label);
        var cmd = clean(command || label);
        if (!useful(text) || !useful(cmd)) return null;
        var button = document.createElement("button");
        button.type = "button";
        button.className = "sizaActionLink " + (className || "");
        button.textContent = text;
        button.setAttribute("data-command", cmd);
        button.addEventListener("click", function () {
            var client = window.SizaWorldBookClient;
            var raw = button.getAttribute("data-command");
            if (client && typeof client.sendText === "function") {
                client.sendText(raw);
            } else {
                send(raw);
            }
            setTimeout(function () { requestLook(true); }, 700);
        });
        return button;
    }

    function appendButton(container, label, command, className) {
        var button = makeButton(label, command, className);
        if (container && button) container.appendChild(button);
    }

    function removePlaceholderActions() {
        var roots = [byId("siza-contextual-interactions"), byId("siza-contextual-movement")];
        roots.forEach(function (root) {
            if (!root) return;
            Array.prototype.slice.call(root.children).forEach(function (node) {
                var label = clean(node.textContent);
                var command = clean(node.getAttribute && node.getAttribute("data-command"));
                if (!useful(label) || !useful(command)) node.remove();
            });
        });
        finishActions();
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
        return /^(?:you become|connected session|available character|type help|command|no entiendo|help -|charcreate|chardelete|ic\b|public\b)/i.test(clean(line));
    }

    function parseRoom(html) {
        var lines = htmlToText(html).split("\n").map(clean).filter(useful);
        if (!lines.length) return null;
        var exits = parseMetadata(lines, ["Exits", "Salidas"]);
        var characters = parseMetadata(lines, ["Characters", "Personas", "Personajes"]);
        var visible = parseMetadata(lines, ["You see", "Ves", "A la vista"]);
        var meta = [exits.index, characters.index, visible.index].filter(function (n) { return n >= 0; });
        if (!meta.length) return null;
        var firstMeta = Math.min.apply(null, meta);
        if (!isFinite(firstMeta) || firstMeta <= 0) return null;
        var title = clean(lines[0].replace(/\(#\d+\)\s*$/, ""));
        var description = lines.slice(1, firstMeta).filter(function (line) { return !isSystemLine(line); }).join(" ");
        if (!useful(title) && !useful(description)) return null;
        return { title: title, description: description, exits: exits.value, characters: characters.value, visible: visible.value };
    }

    function renderParsedRoom(room) {
        if (!room) return;
        hasRoom = true;
        if (room.title) {
            setText("siza-location-label", room.title);
            setText("siza-scene-title", room.title);
            setText("siza-scene-placeholder-label", room.title);
        }
        if (room.description) setText("siza-scene-description", room.description);
        clearActions();
        var interactions = byId("siza-contextual-interactions");
        var movement = byId("siza-contextual-movement");
        splitItems(room.characters).forEach(function (name) { appendButton(interactions, "Hablar con " + name, "hablar con " + name, "isPerson"); });
        splitItems(room.visible).forEach(function (name) { appendButton(interactions, "Examinar " + name, "observar " + name, "isObject"); });
        splitItems(room.exits).forEach(function (name) { appendButton(movement, name, name, "isExit"); });
        finishActions();
    }

    function onText(args) {
        var html = args && args.length ? args[0] : "";
        var text = htmlToText(html);
        if (/\byou become\b/i.test(text)) {
            inCharacter = true;
            setTimeout(function () { requestLook(true); }, 400);
            setTimeout(function () { if (!hasRoom) requestLook(true); }, 1400);
            return;
        }
        var room = parseRoom(html);
        if (room) {
            renderParsedRoom(room);
        }
    }

    function bind() {
        if (bound) return true;
        if (!window.Evennia || !Evennia.emitter) return false;
        bound = true;
        Evennia.emitter.on("text", onText);
        Evennia.emitter.on("html", onText);
        Evennia.emitter.on("connection_open", function () {
            removePlaceholderActions();
        });
        setTimeout(removePlaceholderActions, 250);
        return true;
    }

    function tryBindLoop() {
        bindTries += 1;
        if (bind()) return;
        if (bindTries < 80) setTimeout(tryBindLoop, 250);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", tryBindLoop);
    } else {
        tryBindLoop();
    }
})();