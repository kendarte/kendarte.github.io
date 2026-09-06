(function () {
    "use strict";

    if (window.SizaRoomStateRendererV01) return;

    var BUILD = "20260905-room-state-renderer-v6-description-only";
    var requested = false;
    var lastRequestAt = 0;
    var lastSignature = "";
    var hasRoomState = false;
    var outOfCharacter = false;

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

    function applyButtonCap() {
        if (window.SizaActionButtonCapV01 && typeof window.SizaActionButtonCapV01.apply === "function") {
            window.SizaActionButtonCapV01.apply();
        }
    }

    function renderActions(packet) {
        if (window.SizaBookInteractionV04 && typeof window.SizaBookInteractionV04.renderContextActions === "function") {
            window.SizaBookInteractionV04.renderContextActions(actionPacket(packet));
        }
        window.setTimeout(applyButtonCap, 20);
        window.setTimeout(applyButtonCap, 120);
    }

    function buildObservation(packet) {
        var description = cleanBlock(packet.room_description || packet.description || "");
        return description || "Este cuarto no tiene descripción narrativa importada desde el Map Editor.";
    }

    function renderRoomState(args) {
        var packet = args && args.length ? args[0] : args;
        if (Array.isArray(packet) && packet.length === 1) packet = packet[0];
        packet = packet || {};
        if (packet.status && packet.status !== "ROOM_SNAPSHOT") return;
        hasRoomState = true;
        outOfCharacter = false;

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

    function requestRoomState(force) {
        if (outOfCharacter) return;
        var now = Date.now();
        if (!force && now - lastRequestAt < 900) return;
        lastRequestAt = now;
        if (!window.Evennia || typeof Evennia.isConnected !== "function" || !Evennia.isConnected()) return;
        Evennia.msg("text", ["siza-room-state"], {});
    }

    function requestRoomStateBurst() {
        if (requested || outOfCharacter) return;
        requested = true;
        [250, 900, 1800].forEach(function (delay) {
            window.setTimeout(function () { requestRoomState(true); }, delay);
        });
        window.setTimeout(function () { requested = false; }, 2400);
    }

    function textLooksOoc(value) {
        return /out-of-character|available character\(s\)|connected session\(s\)|charcreate\s+<name>|ic\s+<name>/i.test(String(value || ""));
    }

    function shouldRefreshAfterText(value) {
        var text = clean(value).toLowerCase();
        if (!text) return false;
        if (textLooksOoc(text)) return false;
        if (/command ['"]?siza-room-state/i.test(text)) return false;
        if (/the current location will be described here/i.test(text)) return false;
        if (!hasRoomState) return /you become|entras en|you arrive|you see|exits:|salidas:/i.test(text);
        return /entras en|sales hacia|examinas|revisas|hablas|tiras|ves:|salidas:/i.test(text);
    }

    function onText(args) {
        var value = args && args.length ? String(args[0] || "") : "";
        if (textLooksOoc(value)) {
            outOfCharacter = true;
            return;
        }
        if (/you become/i.test(value)) {
            outOfCharacter = false;
            requestRoomStateBurst();
            return;
        }
        if (shouldRefreshAfterText(value)) {
            window.setTimeout(function () { requestRoomState(false); }, 350);
        }
    }

    function bind() {
        if (!window.Evennia || !Evennia.emitter) return false;
        Evennia.emitter.on("siza_room_snapshot", renderRoomState);
        Evennia.emitter.on("siza_room_state", renderRoomState);
        Evennia.emitter.on("text", onText);
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
