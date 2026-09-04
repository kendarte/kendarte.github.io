(function () {
    "use strict";

    var BUILD = "0.1.0-shared-codex-contextual-surface";

    function byId(id) {
        return document.getElementById(id);
    }

    function clean(value) {
        return String(value === undefined || value === null ? "" : value).replace(/\s+/g, " ").trim();
    }

    function send(command) {
        var client = window.SizaWorldBookClient;
        if (client && typeof client.sendText === "function") {
            return client.sendText(command);
        }
        return false;
    }

    function setInteraction(kind, label, title) {
        var root = byId("siza-book-client");
        var surface = byId("siza-active-interaction");
        var labelNode = byId("siza-active-interaction-label");
        var titleNode = byId("siza-active-interaction-title");
        var dialogue = byId("siza-dialogue-card");

        if (surface) {
            surface.setAttribute("data-kind", kind || "scene");
        }
        if (root) {
            root.setAttribute("data-interaction", kind || "scene");
        }
        if (labelNode) {
            labelNode.textContent = label || "OBSERVACIÓN";
        }
        if (titleNode) {
            titleNode.textContent = title || "Escena actual";
        }
        if (dialogue) {
            dialogue.hidden = kind !== "dialogue";
        }
    }

    function currentLocation() {
        return clean(byId("siza-location-label") && byId("siza-location-label").textContent) || "Escena actual";
    }

    function syncScene() {
        var root = byId("siza-book-client");
        if (!root || root.getAttribute("data-mode") === "DIALOGUE") {
            return;
        }
        setInteraction("scene", "OBSERVACIÓN", currentLocation());
    }

    function setDialogue(packet) {
        packet = packet || {};
        var speaker = clean(packet.speaker) || "Persona presente";
        var text = clean(packet.text);
        var root = byId("siza-book-client");
        var speakerName = byId("siza-dialogue-speaker-name");
        var speakerInitial = byId("siza-dialogue-speaker-initial");
        var speakerState = byId("siza-dialogue-speaker-state");
        var prompt = byId("siza-current-prompt");
        var input = byId("siza-inputfield");

        if (root) {
            root.setAttribute("data-mode", "DIALOGUE");
        }
        setInteraction("dialogue", "CONVERSACIÓN", speaker);
        if (speakerName) {
            speakerName.textContent = speaker;
        }
        if (speakerInitial) {
            speakerInitial.textContent = speaker.charAt(0).toUpperCase() || "?";
        }
        if (speakerState) {
            speakerState.textContent = text ? "Conversación en curso" : "Interlocutor presente";
        }
        if (prompt) {
            prompt.textContent = "¿Qué dices o preguntas?";
        }
        if (input) {
            input.setAttribute("placeholder", "Escribe lo que dices o preguntas…");
        }
    }

    function routeEntries() {
        return Array.prototype.slice.call(document.querySelectorAll("#siza-exits-actions [data-command]"))
            .map(function (button) {
                return {
                    command: clean(button.getAttribute("data-command")),
                    label: clean(button.textContent)
                };
            })
            .filter(function (entry) {
                return entry.command && entry.label;
            });
    }

    function renderRoutes() {
        var toggle = byId("siza-map-foldout-toggle");
        var foldout = byId("siza-map-foldout");
        var location = byId("siza-map-foldout-location");
        var list = byId("siza-map-foldout-routes");
        var entries = routeEntries();

        if (!toggle || !foldout || !list) {
            return;
        }

        toggle.hidden = entries.length === 0;
        if (!entries.length) {
            foldout.hidden = true;
            toggle.setAttribute("aria-expanded", "false");
            return;
        }

        if (location) {
            location.textContent = currentLocation();
        }
        list.innerHTML = "";
        entries.forEach(function (entry) {
            var button = document.createElement("button");
            button.type = "button";
            button.className = "sizaMapRoute";
            button.textContent = entry.label;
            button.addEventListener("click", function () {
                closeRoutes();
                send(entry.command);
            });
            list.appendChild(button);
        });
    }

    function openRoutes() {
        var foldout = byId("siza-map-foldout");
        var toggle = byId("siza-map-foldout-toggle");
        if (!foldout || !toggle || toggle.hidden) {
            return;
        }
        renderRoutes();
        foldout.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
    }

    function closeRoutes() {
        var foldout = byId("siza-map-foldout");
        var toggle = byId("siza-map-foldout-toggle");
        if (foldout) {
            foldout.hidden = true;
        }
        if (toggle) {
            toggle.setAttribute("aria-expanded", "false");
        }
    }

    function observe(id, callback) {
        var node = byId(id);
        if (!node || !window.MutationObserver) {
            return;
        }
        new MutationObserver(callback).observe(node, {
            childList: true,
            characterData: true,
            subtree: true,
            attributes: true
        });
    }

    function onDialogue(args) {
        var packet = args && args.length ? args[0] : args;
        if (Array.isArray(packet) && packet.length === 1) {
            packet = packet[0];
        }
        setDialogue(packet || {});
    }

    function init() {
        var mapToggle = byId("siza-map-foldout-toggle");
        var mapClose = byId("siza-map-foldout-close");

        if (mapToggle) {
            mapToggle.addEventListener("click", openRoutes);
        }
        if (mapClose) {
            mapClose.addEventListener("click", closeRoutes);
        }

        observe("siza-location-label", function () {
            closeRoutes();
            syncScene();
            renderRoutes();
        });
        observe("siza-exits-actions", renderRoutes);
        observe("siza-exits", renderRoutes);
        observe("siza-book-client", function () {
            var root = byId("siza-book-client");
            if (root && root.getAttribute("data-mode") !== "DIALOGUE") {
                syncScene();
            }
        });

        if (window.Evennia && Evennia.emitter) {
            Evennia.emitter.on("siza_dialogue", onDialogue);
        }

        syncScene();
        renderRoutes();
    }

    window.SizaSharedCodexV01 = Object.freeze({
        BUILD: BUILD,
        openRoutes: openRoutes,
        closeRoutes: closeRoutes,
        renderRoutes: renderRoutes,
        setDialogue: setDialogue
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();