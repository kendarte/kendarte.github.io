(function () {
    "use strict";

    var CONTEXT_COMMAND = "siza-ui-context";
    var LOOK_COMMAND = "look";
    var lastLookAt = 0;
    var lastContextAt = 0;

    function byId(id) {
        return document.getElementById(id);
    }

    function clean(value) {
        return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
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

    function requestLook() {
        var now = Date.now();
        if (now - lastLookAt < 2500) {
            return;
        }
        lastLookAt = now;
        setTimeout(function () { send(LOOK_COMMAND); }, 250);
        setTimeout(requestContext, 700);
    }

    function requestContext() {
        var now = Date.now();
        if (now - lastContextAt < 1200) {
            return;
        }
        lastContextAt = now;
        setTimeout(function () { send(CONTEXT_COMMAND); }, 100);
    }

    function setText(id, value) {
        var node = byId(id);
        var text = clean(value);
        if (node && text) {
            node.textContent = text;
            node.setAttribute("data-raw-description", text);
        }
    }

    function splitItems(value) {
        var text = clean(value);
        if (!text || text === "—") {
            return [];
        }
        return text.replace(/\s+(?:and|y)\s+/gi, "\n").split(/\n|,/).map(clean).filter(Boolean);
    }

    function makeButton(label, command, className) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "sizaActionLink " + (className || "");
        button.textContent = clean(label) || clean(command);
        button.setAttribute("data-command", clean(command));
        button.addEventListener("click", function () {
            var client = window.SizaWorldBookClient;
            if (client && typeof client.sendText === "function") {
                client.sendText(button.getAttribute("data-command"));
            } else {
                send(button.getAttribute("data-command"));
            }
        });
        return button;
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

    function renderContextActions(packet) {
        packet = packet || {};
        clearActions();
        var interactions = byId("siza-contextual-interactions");
        var movement = byId("siza-contextual-movement");
        var actions = Array.isArray(packet.actions) ? packet.actions : [];
        actions.forEach(function (action) {
            var kind = clean(action.kind).toUpperCase();
            var command = clean(action.command || action.label);
            var label = clean(action.label || command);
            if (!command || !label) return;
            if (kind === "MOVEMENT") {
                if (movement) movement.appendChild(makeButton(label, command, "isExit"));
            } else {
                if (interactions) interactions.appendChild(makeButton(label, command, kind === "INTERACTION" ? "isPerson" : "isObject"));
            }
        });
        finishActions();
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

    function parseRoom(html) {
        var lines = htmlToText(html).split("\n").map(clean).filter(Boolean);
        if (!lines.length) return null;
        var exits = parseMetadata(lines, ["Exits", "Salidas"]);
        var characters = parseMetadata(lines, ["Characters", "Personas", "Personajes"]);
        var visible = parseMetadata(lines, ["You see", "Ves", "A la vista"]);
        var firstMeta = Math.min.apply(null, [exits.index, characters.index, visible.index].filter(function (n) { return n >= 0; }));
        if (!isFinite(firstMeta) || firstMeta <= 0) return null;
        var title = clean(lines[0].replace(/\(#\d+\)\s*$/, ""));
        var description = lines.slice(1, firstMeta).filter(function (line) {
            return !/^(?:you become|connected session|available character|type help|command )/i.test(line);
        }).join(" ");
        if (!title && !description) return null;
        return { title: title, description: description, exits: exits.value, characters: characters.value, visible: visible.value };
    }

    function renderRoom(room) {
        if (!room) return;
        if (room.title) {
            setText("siza-location-label", room.title);
            setText("siza-scene-title", room.title);
            setText("siza-scene-placeholder-label", room.title);
        }
        if (room.description) {
            setText("siza-scene-description", room.description);
        }
        clearActions();
        var interactions = byId("siza-contextual-interactions");
        var movement = byId("siza-contextual-movement");
        splitItems(room.characters).forEach(function (name) {
            if (interactions) interactions.appendChild(makeButton("Hablar con " + name, "hablar con " + name, "isPerson"));
        });
        splitItems(room.visible).forEach(function (name) {
            if (interactions) interactions.appendChild(makeButton("Observar " + name, "observar " + name, "isObject"));
        });
        splitItems(room.exits).forEach(function (name) {
            if (movement) movement.appendChild(makeButton(name, name, "isExit"));
        });
        finishActions();
        requestContext();
    }

    function renderContextPacket(args) {
        var packet = Array.isArray(args) ? args[0] : args;
        if (!packet || typeof packet !== "object") return;
        if (packet.location) setText("siza-location-label", packet.location);
        renderContextActions(packet);
    }

    function onText(args) {
        var html = args && args.length ? args[0] : "";
        var text = htmlToText(html);
        var room = parseRoom(html);
        if (room) {
            renderRoom(room);
            return;
        }
        if (/\byou become\b/i.test(text)) {
            requestLook();
            requestContext();
        }
    }

    function bind() {
        if (!window.Evennia || !Evennia.emitter) return false;
        Evennia.emitter.on("text", onText);
        Evennia.emitter.on("html", onText);
        Evennia.emitter.on("siza_context_actions", renderContextPacket);
        Evennia.emitter.on("default", function (cmdname, args) {
            if (cmdname === "siza_context_actions") renderContextPacket(args);
        });
        Evennia.emitter.on("connection_open", function () {
            requestLook();
            requestContext();
        });
        setTimeout(requestLook, 900);
        setTimeout(requestContext, 1600);
        return true;
    }

    if (!bind()) {
        document.addEventListener("DOMContentLoaded", bind);
    }
})();
