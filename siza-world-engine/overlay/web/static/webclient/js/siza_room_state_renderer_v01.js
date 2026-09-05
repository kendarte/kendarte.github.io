(function () {
    "use strict";

    if (window.SizaRoomStateRendererV01) return;

    var BUILD = "20260905-room-state-renderer-v1";
    var requested = false;
    var lastSignature = "";

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

    function rows(value) {
        if (Array.isArray(value)) return value;
        if (value && Array.isArray(value.rows)) return value.rows;
        return [];
    }

    function names(value) {
        return rows(value).map(function (row) {
            if (typeof row === "string") return clean(row);
            return clean(row && (row.name || row.label || row.target));
        }).filter(Boolean).filter(function (item, index, array) {
            return array.indexOf(item) === index;
        });
    }

    function setText(id, value) {
        var node = byId(id);
        if (!node) return;
        var text = cleanBlock(value);
        node.textContent = text || "—";
        node.style.whiteSpace = "pre-line";
        if (id === "siza-scene-description") {
            node.setAttribute("data-raw-description", text || "");
        }
    }

    function setOptionalText(id, wrapId, value) {
        var text = clean(value);
        var node = byId(id);
        var wrap = byId(wrapId);
        if (node) node.textContent = text || "—";
        if (wrap) wrap.hidden = !text;
    }

    function actionPacket(packet) {
        var actions = packet.available_actions || packet.actions || [];
        if (!Array.isArray(actions)) actions = [];
        return {
            location: packet.room_name || packet.location || "",
            room_id: packet.room_id || null,
            actions: actions,
            pending_roll: !!packet.pending_roll,
            build: packet.build || BUILD
        };
    }

    function renderActions(packet) {
        if (window.SizaBookInteractionV04 && typeof window.SizaBookInteractionV04.renderContextActions === "function") {
            window.SizaBookInteractionV04.renderContextActions(actionPacket(packet));
        }
    }

    function buildObservation(packet) {
        var description = cleanBlock(packet.room_description || packet.description || "");
        var visibleObjects = names(packet.visible_objects || packet.objects);
        var visibleNpcs = names(packet.visible_npcs || packet.people);
        var exits = names(packet.exits);
        var blocks = [];
        if (description) blocks.push(description);
        if (visibleObjects.length) blocks.push("Ves: " + visibleObjects.join(", ") + ".");
        if (visibleNpcs.length) blocks.push("Personas presentes: " + visibleNpcs.join(", ") + ".");
        if (exits.length) blocks.push("Salidas: " + exits.join(", ") + ".");
        return blocks.join("\n\n") || "Este cuarto no tiene descripción narrativa importada desde el Map Editor.";
    }

    function renderRoomState(args) {
        var packet = args && args.length ? args[0] : args;
        if (Array.isArray(packet) && packet.length === 1) packet = packet[0];
        packet = packet || {};
        if (packet.status && packet.status !== "ROOM_SNAPSHOT") return;

        var title = clean(packet.room_name || packet.location || "Ubicación actual");
        var observation = buildObservation(packet);
        var signature = clean(title + "|" + observation + "|" + JSON.stringify(packet.available_actions || packet.actions || []));
        if (signature && signature === lastSignature) {
            renderActions(packet);
            return;
        }
        lastSignature = signature;

        setText("siza-location-label", title);
        setText("siza-scene-title", title);
        setText("siza-scene-placeholder-label", title);
        setText("siza-scene-description", observation);

        setOptionalText("siza-exits", "siza-exits-card", names(packet.exits).join(", "));
        setOptionalText("siza-characters", "siza-characters-card", names(packet.visible_npcs || packet.people).join(", "));
        setOptionalText("siza-visible", "siza-visible-card", names(packet.visible_objects || packet.objects).join(", "));
        renderActions(packet);
    }

    function requestRoomState() {
        if (!window.Evennia || typeof Evennia.isConnected !== "function" || !Evennia.isConnected()) return;
        Evennia.msg("text", ["siza-room-state"], {});
    }

    function requestInitialRoomState() {
        if (requested) return;
        requested = true;
        [250, 900, 1800].forEach(function (delay) {
            window.setTimeout(requestRoomState, delay);
        });
        window.setTimeout(function () { requested = false; }, 2400);
    }

    function onText(args) {
        var value = args && args.length ? String(args[0] || "") : "";
        if (/you become/i.test(value)) {
            requestInitialRoomState();
        }
    }

    function bind() {
        if (!window.Evennia || !Evennia.emitter) return false;
        Evennia.emitter.on("siza_room_snapshot", renderRoomState);
        Evennia.emitter.on("siza_room_state", renderRoomState);
        Evennia.emitter.on("connection_open", requestInitialRoomState);
        Evennia.emitter.on("text", onText);
        requestInitialRoomState();
        return true;
    }

    function init() {
        var tries = 0;
        function loop() {
            tries += 1;
            if (bind()) return;
            if (tries < 80) window.setTimeout(loop, 250);
        }
        loop();
    }

    window.SizaRoomStateRendererV01 = Object.freeze({
        build: BUILD,
        renderRoomState: renderRoomState,
        requestRoomState: requestRoomState
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
