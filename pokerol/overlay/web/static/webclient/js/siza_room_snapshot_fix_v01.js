(function () {
    "use strict";

    var explicitLookPending = false;
    var RAW_ROOMS = [
        "Embarcadero de Campana",
        "Patio de Mineral",
        "Plaza de Recepcion",
        "Calle de Servicio",
        "Casa de Remedio",
        "Cantina de Turno",
        "Pescaderia de Darsena",
        "Trastienda de la Pescaderia",
        "Muelles de Descenso"
    ];

    var META = {
        exits: ["Exits:", "Salidas:"],
        people: ["Characters:", "Personajes:", "People:", "Personas:"],
        visible: ["You see:", "Ves:", "A la vista:", "Things:", "Objetos:"]
    };

    function byId(id) {
        return document.getElementById(id);
    }

    function clean(value) {
        return String(value == null ? "" : value).replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
    }

    function knownRoom(value) {
        var text = clean(value).replace(/\s*\(#\d+\)\s*$/, "");
        for (var i = 0; i < RAW_ROOMS.length; i += 1) {
            if (text === RAW_ROOMS[i] || text.indexOf(RAW_ROOMS[i]) !== -1) {
                return RAW_ROOMS[i];
            }
        }
        return "";
    }

    function isPlaceholderDescription(value) {
        var text = clean(value).toLowerCase();
        return !text ||
            text === "the current location will be described here." ||
            text === "la ubicación actual se describirá aquí." ||
            text === "la ubicacion actual se describira aqui." ||
            text === "sin descripción disponible." ||
            text === "sin descripcion disponible.";
    }

    /*
     * This must run before the localization observer. The old bug was:
     * room snapshot -> DOM changes -> localization reads stale data-raw-room /
     * data-raw-description -> localization restores the old room/placeholder.
     * Keep the raw identity synchronized with the authoritative DOM mutation
     * before localization gets a chance to repaint it.
     */
    function syncRawIdentity() {
        var location = byId("siza-location-label");
        var description = byId("siza-scene-description");
        if (!location) {
            return false;
        }

        var room = knownRoom(location.textContent);
        if (!room) {
            return false;
        }

        location.setAttribute("data-raw-room", room);
        if (description && !isPlaceholderDescription(description.textContent)) {
            description.setAttribute("data-raw-description", clean(description.textContent));
        }
        return true;
    }

    function htmlToLines(html) {
        var holder = document.createElement("div");
        var source = String(html == null ? "" : html)
            .replace(/<br\s*\/?\s*>/gi, "\n")
            .replace(/<\/(p|div|li|tr)>/gi, "\n");
        holder.innerHTML = source;
        return String(holder.textContent || holder.innerText || "")
            .replace(/\u00a0/g, " ")
            .replace(/\r/g, "")
            .split("\n")
            .map(clean)
            .filter(Boolean);
    }

    function roomNameFromLine(line) {
        return knownRoom(line);
    }

    function metaValue(lines, prefixes) {
        for (var i = 0; i < lines.length; i += 1) {
            for (var j = 0; j < prefixes.length; j += 1) {
                if (lines[i].toLowerCase().indexOf(prefixes[j].toLowerCase()) === 0) {
                    return clean(lines[i].slice(prefixes[j].length));
                }
            }
        }
        return "";
    }

    function isMeta(line) {
        var groups = [META.exits, META.people, META.visible];
        for (var g = 0; g < groups.length; g += 1) {
            for (var i = 0; i < groups[g].length; i += 1) {
                if (line.toLowerCase().indexOf(groups[g][i].toLowerCase()) === 0) {
                    return true;
                }
            }
        }
        return false;
    }

    function parseLooseRoom(html) {
        var lines = htmlToLines(html);
        if (!lines.length) {
            return null;
        }

        var titleIndex = -1;
        var roomName = "";
        for (var i = 0; i < lines.length; i += 1) {
            roomName = roomNameFromLine(lines[i]);
            if (roomName) {
                titleIndex = i;
                break;
            }
        }
        if (titleIndex < 0) {
            return null;
        }

        var body = lines.slice(titleIndex + 1);
        var desc = [];
        for (var d = 0; d < body.length; d += 1) {
            if (isMeta(body[d])) {
                break;
            }
            desc.push(body[d]);
        }

        return {
            title: roomName,
            description: clean(desc.join(" ")),
            exits: metaValue(body, META.exits),
            people: metaValue(body, META.people),
            visible: metaValue(body, META.visible)
        };
    }

    function setFact(id, cardId, value) {
        var node = byId(id);
        var card = byId(cardId);
        var text = clean(value);
        if (node) {
            node.textContent = text || "—";
        }
        if (card) {
            card.hidden = !text;
        }
    }

    function forceSceneOpen() {
        var scene = byId("siza-scene-panel");
        var sceneToggle = byId("siza-scene-panel-toggle");
        var stats = byId("siza-stats-panel");
        var memories = byId("siza-memories-panel");
        var statsToggle = byId("siza-stats-panel-toggle");
        var memoriesToggle = byId("siza-memories-panel-toggle");
        if (scene) scene.hidden = false;
        if (sceneToggle) sceneToggle.setAttribute("aria-expanded", "true");
        if (stats) stats.hidden = true;
        if (memories) memories.hidden = true;
        if (statsToggle) statsToggle.setAttribute("aria-expanded", "false");
        if (memoriesToggle) memoriesToggle.setAttribute("aria-expanded", "false");
    }

    function render(room) {
        if (!room) {
            return false;
        }
        var location = byId("siza-location-label");
        var title = byId("siza-scene-title");
        var description = byId("siza-scene-description");
        var context = byId("siza-context-label");

        /* Set raw values first so localization cannot restore stale content. */
        if (location) {
            location.setAttribute("data-raw-room", room.title);
            location.textContent = room.title;
        }
        if (title) {
            title.textContent = room.title;
        }
        if (description && room.description) {
            description.setAttribute("data-raw-description", room.description);
            description.textContent = room.description;
        }
        if (context) {
            context.textContent = "World Engine · escena persistente";
        }

        setFact("siza-exits", "siza-exits-card", room.exits);
        setFact("siza-characters", "siza-characters-card", room.people);
        setFact("siza-visible", "siza-visible-card", room.visible);
        syncRawIdentity();

        if (window.SizaBookInteractionV04 && typeof window.SizaBookInteractionV04.refresh === "function") {
            window.SizaBookInteractionV04.refresh();
        }
        if (explicitLookPending) {
            forceSceneOpen();
        }
        explicitLookPending = false;
        return true;
    }

    function packetHtml(args) {
        if (!args || !args.length) {
            return "";
        }
        return args[0];
    }

    function onText(args) {
        render(parseLooseRoom(packetHtml(args)));
    }

    function noteExplicitLook() {
        var field = byId("siza-inputfield");
        if (!field) {
            return;
        }
        var value = clean(field.value).toLowerCase();
        if (["look", "l", "mirar", "mira", "ver", "ver alrededor", "mirar alrededor"].indexOf(value) !== -1) {
            explicitLookPending = true;
        }
    }

    function observeRawStateBeforeLocalization() {
        if (!window.MutationObserver) {
            return;
        }
        var location = byId("siza-location-label");
        var description = byId("siza-scene-description");
        var observer = new MutationObserver(syncRawIdentity);
        if (location) {
            observer.observe(location, {childList: true, characterData: true, subtree: true});
        }
        if (description) {
            observer.observe(description, {childList: true, characterData: true, subtree: true});
        }
    }

    function init() {
        syncRawIdentity();
        observeRawStateBeforeLocalization();

        if (window.Evennia && Evennia.emitter) {
            Evennia.emitter.on("text", onText);
            Evennia.emitter.on("default", function (cmdname, args) {
                if (cmdname === "html" || cmdname === "text") {
                    onText(args);
                }
            });
        }

        var field = byId("siza-inputfield");
        var send = byId("siza-inputsend");
        if (field) {
            field.addEventListener("keydown", function (event) {
                if (event.key === "Enter" && !event.shiftKey) {
                    noteExplicitLook();
                }
            }, true);
        }
        if (send) {
            send.addEventListener("click", noteExplicitLook, true);
        }
    }

    window.SizaRoomSnapshotFixV01 = Object.freeze({
        parse: parseLooseRoom,
        render: render,
        syncRawIdentity: syncRawIdentity
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
