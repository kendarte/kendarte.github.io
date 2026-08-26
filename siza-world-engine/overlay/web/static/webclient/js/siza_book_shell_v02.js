(function () {
    "use strict";

    function byId(id) {
        return document.getElementById(id);
    }

    function normalize(value) {
        return String(value === undefined || value === null ? "" : value).replace(/\s+/g, " ").trim();
    }

    function initialFor(name) {
        var value = normalize(name);
        return value ? value.charAt(0).toUpperCase() : "?";
    }

    function splitCharacters(raw) {
        var value = normalize(raw);
        if (!value || value === "—") {
            return [];
        }
        return value
            .replace(/\s+(?:and|y)\s+/gi, ",")
            .split(",")
            .map(normalize)
            .filter(function (item, index, list) {
                return item && list.indexOf(item) === index;
            });
    }

    function setPortrait(slotId, nameId, initialId, name, role) {
        var slot = byId(slotId);
        var label = byId(nameId);
        var initial = byId(initialId);
        var roleLabel = slot ? slot.querySelector("[data-portrait-role]") : null;
        var value = normalize(name);

        if (!slot) {
            return;
        }

        slot.setAttribute("data-empty", value ? "false" : "true");
        slot.setAttribute("aria-hidden", value ? "false" : "true");
        if (label) {
            label.textContent = value || "Sin personaje";
        }
        if (initial) {
            initial.textContent = initialFor(value);
        }
        if (roleLabel) {
            roleLabel.textContent = role || "EN ESCENA";
        }
    }

    function renderPlayerPortrait() {
        var source = byId("siza-player-name");
        var name = normalize(source && source.textContent);
        setPortrait(
            "siza-player-portrait",
            "siza-player-portrait-name",
            "siza-player-portrait-initial",
            name,
            "JUGADOR"
        );
    }

    function renderSceneCast() {
        var source = byId("siza-characters");
        var charactersCard = byId("siza-characters-card");
        var cast = byId("siza-scene-cast");
        var characters = splitCharacters(source && source.textContent);
        var focus = characters.length ? characters[0] : "";

        setPortrait(
            "siza-focus-portrait",
            "siza-focus-portrait-name",
            "siza-focus-portrait-initial",
            focus,
            "EN ESCENA"
        );

        if (cast) {
            cast.innerHTML = "";
            characters.slice(1).forEach(function (name) {
                var chip = document.createElement("span");
                chip.className = "sizaSceneCastChip";
                chip.textContent = name;
                cast.appendChild(chip);
            });
            cast.hidden = characters.length <= 1;
        }

        // Once portraits own character presence, avoid printing the same list again as terminal metadata.
        if (charactersCard) {
            charactersCard.hidden = characters.length > 0;
        }
    }

    function setSceneVisual(data) {
        data = data || {};
        var visual = byId("siza-scene-visual");
        var media = byId("siza-scene-visual-media");
        var label = byId("siza-scene-visual-label");
        if (!visual || !media) {
            return false;
        }

        var url = normalize(data.url);
        if (url) {
            media.style.backgroundImage = "url(\"" + url.replace(/\"/g, "%22") + "\")";
            visual.setAttribute("data-has-image", "true");
        } else {
            media.style.backgroundImage = "";
            visual.setAttribute("data-has-image", "false");
        }

        if (label && data.label !== undefined) {
            label.textContent = normalize(data.label);
        }
        return true;
    }

    function setCombatTray(state) {
        state = state || {};
        var tray = byId("siza-tcg-tray");
        var status = byId("siza-tcg-status");
        var hand = byId("siza-tcg-hand-mount");
        var resources = byId("siza-tcg-resource-mount");
        if (!tray) {
            return false;
        }

        tray.setAttribute("data-active", state.active ? "true" : "false");
        if (status && state.status !== undefined) {
            status.textContent = normalize(state.status) || "Preparado";
        }
        if (hand && state.handNode instanceof Node) {
            hand.innerHTML = "";
            hand.appendChild(state.handNode);
        }
        if (resources && state.resourceNode instanceof Node) {
            resources.innerHTML = "";
            resources.appendChild(state.resourceNode);
        }
        return true;
    }

    function observeText(id, callback) {
        var el = byId(id);
        if (!el || !window.MutationObserver) {
            return;
        }
        var observer = new MutationObserver(callback);
        observer.observe(el, {childList: true, characterData: true, subtree: true});
    }

    function syncLocationLabel() {
        var source = byId("siza-location-label");
        var label = byId("siza-scene-visual-label");
        var value = normalize(source && source.textContent);
        if (label && value) {
            label.textContent = value;
        }
    }

    function init() {
        renderPlayerPortrait();
        renderSceneCast();
        syncLocationLabel();
        observeText("siza-player-name", renderPlayerPortrait);
        observeText("siza-characters", renderSceneCast);
        observeText("siza-location-label", syncLocationLabel);
    }

    window.SizaBookShellV02 = Object.freeze({
        renderPlayerPortrait: renderPlayerPortrait,
        renderSceneCast: renderSceneCast,
        setSceneVisual: setSceneVisual,
        setCombatTray: setCombatTray,
        splitCharacters: splitCharacters
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
