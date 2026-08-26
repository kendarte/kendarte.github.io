(function () {
    "use strict";

    var ROOM_PRESENTATION = {
        "Embarcadero de Campana": {
            name: "Bell Dock",
            description: "A working dock platform where cargo, crews, and arrivals converge under the noise of the harbor."
        },
        "Patio de Mineral": {
            name: "Mineral Yard",
            description: "A rough handling yard where wet mineral loads are sorted before moving deeper into the dock district."
        },
        "Plaza de Recepcion": {
            name: "Receiving Square",
            description: "A busy receiving square linking dock traffic, local services, and the lower work streets."
        },
        "Calle de Servicio": {
            name: "Service Lane",
            description: "A narrow work lane used by dock crews and supply traffic; cargo noise carries between the adjoining businesses."
        },
        "Casa de Remedio": {
            name: "Remedy House",
            description: "A modest treatment house serving dock workers and families from the surrounding district."
        },
        "Cantina de Turno": {
            name: "Shift Canteen",
            description: "A cramped canteen where crews eat, trade news, and wait for the next change of shift."
        },
        "Pescaderia de Darsena": {
            name: "Dockside Fishery",
            description: "A cramped dockside shop with a scarred work counter, brine in the air, and storage pushed toward the back."
        },
        "Trastienda de la Pescaderia": {
            name: "Fishery Back Room",
            description: "A small storage room behind the shop, crowded with supplies and the residue of daily dock work."
        }
    };

    var EXIT_LABELS = {
        "salir a la calle": "Return to Service Lane",
        "entrar a la trastienda": "Enter the back room",
        "abrir la puerta de la trastienda": "Open the back-room door",
        "volver a la plaza": "Return to Receiving Square",
        "entrar a la pescaderia": "Enter the Dockside Fishery",
        "ir a la calle de servicio": "Go to Service Lane",
        "tomar la calle de servicio": "Take Service Lane",
        "ir al patio": "Go to Mineral Yard",
        "volver al patio": "Return to Mineral Yard",
        "ir a la plaza": "Go to Receiving Square",
        "volver al embarcadero": "Return to Bell Dock",
        "entrar a la casa de remedio": "Enter the Remedy House",
        "salir de la casa de remedio": "Leave the Remedy House",
        "entrar a la cantina": "Enter the Shift Canteen",
        "salir de la cantina": "Leave the Shift Canteen",
        "salir a la pescaderia": "Return to the Dockside Fishery"
    };

    var ENTITY_LABELS = {
        "Informante de Prueba C": "Dock Informant",
        "Cajon de reparto de prueba": "Delivery Crate",
        "Manifiesto de carga de prueba": "Cargo Manifest"
    };

    var MEMORY_TRANSLATIONS = [
        ["Al comparar las cifras del manifiesto", "Comparing the manifest figures reveals a discrepancy: one cargo lot was recorded twice under the same receiving seal."],
        ["Al ordenar los sellos y horarios del manifiesto", "Reordering the seals and timestamps reconstructs a consistent sequence: the duplicate cargo entry was logged at two different times under the same receiving seal."],
        ["El informante evita sostenerte la mirada", "The informant avoids your gaze. After the confrontation, their contradictions are now exposed."],
        ["Al hacer coincidir la cadencia de los sellos", "Matching the seal cadence against the reconstructed times reveals a pattern: the second entry was stamped during the same mechanical cycle as the first."],
        ["Con el ciclo de estampado ya comprendido", "With the stamping cycle understood, you identify the responsible shift: the second entry was processed during the dock's closing handoff."]
    ];

    function byId(id) { return document.getElementById(id); }
    function clean(value) { return String(value == null ? "" : value).replace(/\s+/g, " ").trim(); }
    function key(value) { return clean(value).toLowerCase(); }

    function splitItems(value) {
        var source = clean(value);
        if (!source || source === "—") return [];
        return source.replace(/\s+(?:and|y)\s+/gi, "\n").split(/\n|,/).map(clean).filter(Boolean);
    }

    function rawEntityName(value) {
        return clean(value).replace(/^(?:a|an|the|un|una|el|la)\s+/i, "");
    }

    function entityLabel(raw) {
        var name = rawEntityName(raw);
        return ENTITY_LABELS[name] || name;
    }

    function exitLabel(raw) {
        return EXIT_LABELS[key(raw)] || clean(raw);
    }

    function makeActionButton(label, rawCommand, className) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "sizaActionLink " + (className || "");
        button.textContent = label;
        button.setAttribute("data-command", rawCommand);
        button.addEventListener("click", function () {
            var client = window.SizaWorldBookClient;
            if (client && typeof client.sendText === "function") client.sendText(rawCommand);
        });
        return button;
    }

    function renderActionSource(sourceId, targetId, kind) {
        var source = byId(sourceId);
        var target = byId(targetId);
        var card = source && source.closest(".sizaBookFact");
        if (!source || !target) return;
        var items = splitItems(source.textContent);
        target.innerHTML = "";
        items.forEach(function (raw) {
            var rawName = rawEntityName(raw);
            if (kind === "exit") target.appendChild(makeActionButton(exitLabel(raw), raw, "isExit"));
            if (kind === "person") target.appendChild(makeActionButton(entityLabel(rawName), "hablar con " + rawName, "isPerson"));
            if (kind === "object") target.appendChild(makeActionButton(entityLabel(rawName), "observar " + rawName, "isObject"));
        });
        if (card) card.hidden = items.length === 0;
    }

    function translateMemory(text) {
        var value = clean(text);
        for (var i = 0; i < MEMORY_TRANSLATIONS.length; i += 1) {
            if (value.indexOf(MEMORY_TRANSLATIONS[i][0]) === 0) return MEMORY_TRANSLATIONS[i][1];
        }
        return value;
    }

    function localizeMemories() {
        var list = byId("siza-knowledge-list");
        var panel = byId("siza-knowledge-panel");
        var empty = byId("siza-memories-empty");
        var summary = byId("siza-knowledge-summary");
        if (!list) return;
        Array.prototype.forEach.call(list.children, function (node) {
            var translated = translateMemory(node.textContent);
            if (node.textContent !== translated) node.textContent = translated;
        });
        var count = list.children.length;
        if (summary) summary.textContent = count === 1 ? "1 memory" : count + " memories";
        if (empty) empty.hidden = count > 0;
        if (panel && count > 0) panel.hidden = false;
    }

    function localizeRoom() {
        var location = byId("siza-location-label");
        var description = byId("siza-scene-description");
        var placeholder = byId("siza-scene-placeholder-label");
        if (!location) return;

        var visibleName = clean(location.textContent);
        var rawName = location.getAttribute("data-raw-room") || visibleName;
        if (ROOM_PRESENTATION[visibleName]) {
            rawName = visibleName;
            location.setAttribute("data-raw-room", rawName);
        }
        var presentation = ROOM_PRESENTATION[rawName];
        if (presentation) {
            if (location.textContent !== presentation.name) location.textContent = presentation.name;
            if (description && description.textContent !== presentation.description) description.textContent = presentation.description;
            if (placeholder) placeholder.textContent = presentation.name;
        } else if (placeholder) {
            placeholder.textContent = visibleName || "Location";
        }
    }

    function replaceKnownUiText(node) {
        if (!node || node.nodeType !== 1) return;
        var text = clean(node.textContent);
        var exact = {
            "EXPLORACIÓN": "EXPLORATION",
            "DIÁLOGO": "DIALOGUE",
            "COMBATE": "COMBAT",
            "Conectado": "Connected",
            "Conectando…": "Connecting…",
            "Desconectado": "Disconnected",
            "Error de conexión": "Connection error",
            "ENVIAR": "SEND",
            "ESPERANDO": "WAITING",
            "¿Qué haces?": "What do you do?",
            "El World Engine no devolvió salida todavía. Puedes reintentar.": "The World Engine has not returned a result yet. You can try again.",
            "La conexión con el World Engine se cerró.": "The connection to the World Engine was closed.",
            "No se pudo mantener la conexión con el World Engine.": "The connection to the World Engine could not be maintained.",
            "Todavía no hay conexión con el World Engine.": "The World Engine is not connected yet."
        };
        if (exact[text] && node.textContent !== exact[text]) node.textContent = exact[text];
        else if (text.indexOf("Acción enviada:") === 0) node.textContent = "Action sent:" + text.slice("Acción enviada:".length);
        else if (text === "World Engine · escena persistente") node.textContent = "World Engine · persistent scene";

        var current = node.textContent || "";
        Object.keys(ROOM_PRESENTATION).forEach(function (rawName) {
            if (current.indexOf(rawName) !== -1) current = current.split(rawName).join(ROOM_PRESENTATION[rawName].name);
        });
        if (node.textContent !== current) node.textContent = current;
    }

    function localizeDynamicUi() {
        ["siza-mode-label", "siza-connection-label", "siza-current-prompt", "siza-inputsend", "siza-context-label"].forEach(function (id) {
            replaceKnownUiText(byId(id));
        });
        var output = byId("siza-messagewindow");
        if (output) Array.prototype.forEach.call(output.children, replaceKnownUiText);
        localizeRoom();
        localizeMemories();
    }

    function openPanel(name) {
        ["scene", "stats", "memories"].forEach(function (panelName) {
            var panel = byId("siza-" + panelName + "-panel");
            var toggle = byId("siza-" + panelName + "-panel-toggle");
            var opening = panelName === name && panel && panel.hidden;
            if (panel) panel.hidden = !(panelName === name && opening);
            if (toggle) toggle.setAttribute("aria-expanded", panelName === name && opening ? "true" : "false");
        });
        if (name === "stats") requestStats();
    }

    function requestStats() {
        var status = byId("siza-stats-status");
        if (!window.Evennia || !Evennia.isConnected()) {
            if (status) status.textContent = "World Engine is not connected.";
            return;
        }
        if (status) status.textContent = "Reading current World Engine values…";
        Evennia.msg("text", ["siza-ui-stats"], {});
    }

    function onStats(args) {
        var packet = args && args.length ? args[0] : args;
        if (Array.isArray(packet) && packet.length === 1) packet = packet[0];
        packet = packet || {};
        var stats = packet.stats || {};
        ["FUE", "AGI", "COO", "INT", "PER", "PSI"].forEach(function (stat) {
            var el = byId("siza-stat-" + stat);
            var value = stats[stat];
            if (el) el.textContent = value === null || value === undefined ? "—" : String(value);
        });
        var status = byId("siza-stats-status");
        if (status) status.textContent = "Stats are read directly from the persistent character state.";
    }

    function observe(id, callback) {
        var node = byId(id);
        if (!node || !window.MutationObserver) return;
        new MutationObserver(callback).observe(node, {childList:true, characterData:true, subtree:true});
    }

    function init() {
        var sceneToggle = byId("siza-scene-panel-toggle");
        var statsToggle = byId("siza-stats-panel-toggle");
        var memoriesToggle = byId("siza-memories-panel-toggle");
        if (sceneToggle) sceneToggle.addEventListener("click", function () { openPanel("scene"); });
        if (statsToggle) statsToggle.addEventListener("click", function () { openPanel("stats"); });
        if (memoriesToggle) memoriesToggle.addEventListener("click", function () { openPanel("memories"); });

        observe("siza-exits", function () { renderActionSource("siza-exits", "siza-exits-actions", "exit"); });
        observe("siza-characters", function () { renderActionSource("siza-characters", "siza-characters-actions", "person"); });
        observe("siza-visible", function () { renderActionSource("siza-visible", "siza-visible-actions", "object"); });
        observe("siza-location-label", localizeRoom);
        observe("siza-scene-description", localizeRoom);
        observe("siza-knowledge-list", localizeMemories);
        observe("siza-knowledge-summary", localizeMemories);
        observe("siza-mode-label", localizeDynamicUi);
        observe("siza-connection-label", localizeDynamicUi);
        observe("siza-current-prompt", localizeDynamicUi);
        observe("siza-inputsend", localizeDynamicUi);
        observe("siza-context-label", localizeDynamicUi);
        observe("siza-messagewindow", localizeDynamicUi);

        if (window.Evennia && Evennia.emitter) Evennia.emitter.on("siza_character_stats", onStats);

        renderActionSource("siza-exits", "siza-exits-actions", "exit");
        renderActionSource("siza-characters", "siza-characters-actions", "person");
        renderActionSource("siza-visible", "siza-visible-actions", "object");
        localizeDynamicUi();
    }

    window.SizaBookInteractionV03 = Object.freeze({
        splitItems: splitItems,
        renderActionSource: renderActionSource,
        openPanel: openPanel,
        requestStats: requestStats,
        localizeRoom: localizeRoom
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
