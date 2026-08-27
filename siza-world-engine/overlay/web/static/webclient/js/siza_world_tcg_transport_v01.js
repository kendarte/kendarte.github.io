(function () {
    "use strict";

    var BUILD = "0.2.1-world-tcg-combat-transition";
    var activeEncounter = null;
    var lastSubmittedResultId = "";

    function byId(id) {
        return document.getElementById(id);
    }

    function text(value) {
        return String(value === undefined || value === null ? "" : value).trim();
    }

    function clone(value) {
        try {
            return JSON.parse(JSON.stringify(value));
        } catch (error) {
            return value;
        }
    }

    function setTrayStatus(label) {
        var status = byId("siza-tcg-status");
        if (status) {
            status.textContent = text(label) || "PREPARADO";
        }
    }

    function showEncounterSummary(encounter) {
        var hand = byId("siza-tcg-hand-mount");
        var resources = byId("siza-tcg-resource-mount");
        var opponent = encounter && encounter.opponents && encounter.opponents[0];
        if (hand) {
            hand.textContent = "ENCOUNTER · " + text(opponent && opponent.name || "Rival");
        }
        if (resources) {
            resources.textContent = text(encounter && encounter.site && encounter.site.name || "WORLD ENGINE");
        }
    }

    function activateCombatShell(encounter) {
        if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.setMode === "function") {
            window.SizaWorldBookClient.setMode("COMBAT");
        }
        if (window.SizaBookShellV02 && typeof window.SizaBookShellV02.setCombatTray === "function") {
            window.SizaBookShellV02.setCombatTray({
                active: true,
                status: "Encounter recibido"
            });
        }
        showEncounterSummary(encounter);
    }

    function startArena(encounter) {
        if (!window.SIZA || typeof window.SIZA.startWorldEncounter !== "function") {
            setTrayStatus("Encounter recibido · Arena pendiente de montaje");
            return {
                ok: false,
                status: "ARENA_RUNTIME_NOT_MOUNTED"
            };
        }
        var started;
        try {
            started = window.SIZA.startWorldEncounter(clone(encounter), "prepare");
        } catch (error) {
            setTrayStatus("Error al iniciar Arena");
            return {ok: false, status: "ARENA_START_EXCEPTION", error: text(error && error.message || error)};
        }
        if (!started || started.ok !== true) {
            setTrayStatus("Arena rechazó el encounter");
            return {ok: false, status: text(started && started.status || "ARENA_START_REJECTED"), packet: started};
        }
        setTrayStatus("Combate activo");
        return {ok: true, status: "ARENA_STARTED", packet: started};
    }

    function onEncounter(args) {
        var encounter = args && args[0];
        if (!encounter || typeof encounter !== "object" || !text(encounter.encounter_id)) {
            setTrayStatus("Encounter inválido");
            return {ok: false, status: "INVALID_ENCOUNTER_PACKET"};
        }

        /* Presentation must begin before the Book switches to COMBAT. The animation
           layer also listens to the encounter as a fallback, but the transport owns
           the guaranteed handoff that actually activates the Arena. */
        if (window.SizaCombatAnimationV02 && typeof window.SizaCombatAnimationV02.playBookTransition === "function") {
            window.SizaCombatAnimationV02.playBookTransition();
        }

        activeEncounter = clone(encounter);
        lastSubmittedResultId = "";
        activateCombatShell(activeEncounter);
        return startArena(activeEncounter);
    }

    function utf8Base64Url(value) {
        var json = JSON.stringify(value);
        var bytes;
        if (window.TextEncoder) {
            bytes = Array.from(new TextEncoder().encode(json));
        } else {
            var encoded = unescape(encodeURIComponent(json));
            bytes = Array.from(encoded).map(function (ch) { return ch.charCodeAt(0); });
        }
        var binary = "";
        bytes.forEach(function (byte) { binary += String.fromCharCode(byte); });
        return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    }

    function submitCombatResult(result) {
        if (!result || typeof result !== "object") {
            return {ok: false, status: "INVALID_RESULT"};
        }
        if (!activeEncounter || text(result.encounter_id) !== text(activeEncounter.encounter_id)) {
            return {ok: false, status: "RESULT_ENCOUNTER_MISMATCH"};
        }
        var resultId = text(result.result_id) || text(result.encounter_id) + ":RESULT";
        if (resultId === lastSubmittedResultId) {
            return {ok: true, status: "RESULT_ALREADY_SUBMITTED"};
        }
        if (!window.Evennia || !Evennia.isConnected()) {
            setTrayStatus("Resultado pendiente · sin conexión");
            return {ok: false, status: "WORLD_ENGINE_DISCONNECTED"};
        }
        var token = utf8Base64Url(result);
        Evennia.msg("text", ["siza-combat-result " + token], {});
        lastSubmittedResultId = resultId;
        setTrayStatus("Resultado enviado al World Engine");
        return {ok: true, status: "RESULT_SUBMITTED", result_id: resultId};
    }

    function onBrowserCombatResult(event) {
        return submitCombatResult(event && event.detail);
    }

    function returnToExploration(packet) {
        var applied = !!(packet && packet.world_consequences_applied === true);
        var status = applied ? "Resultado aplicado al mundo" : "Resultado aceptado";
        setTrayStatus(status);

        if (window.SizaBookShellV02 && typeof window.SizaBookShellV02.setCombatTray === "function") {
            window.SizaBookShellV02.setCombatTray({active: false, status: status});
        }
        if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.setMode === "function") {
            window.SizaWorldBookClient.setMode("EXPLORATION");
        }

        activeEncounter = null;
        lastSubmittedResultId = "";

        if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.sendText === "function") {
            window.setTimeout(function () {
                window.SizaWorldBookClient.sendText("look");
            }, 0);
        }

        return {
            ok: true,
            status: "RETURNED_TO_EXPLORATION",
            world_consequences_applied: applied,
            consequence_status: text(packet && packet.consequence_status),
            build: BUILD
        };
    }

    function onResultAccepted(args) {
        var packet = args && args[0];
        if (!packet || typeof packet !== "object" || !activeEncounter) {
            return;
        }
        if (text(packet.encounter_id) !== text(activeEncounter.encounter_id)) {
            return;
        }
        return returnToExploration(packet);
    }

    function init() {
        if (!window.Evennia) {
            return;
        }
        Evennia.init();
        if (Evennia.emitter && typeof Evennia.emitter.on === "function") {
            Evennia.emitter.on("siza_combat_encounter", onEncounter);
            Evennia.emitter.on("siza_combat_result_accepted", onResultAccepted);
        }
        window.addEventListener("siza:combat-result", onBrowserCombatResult);
    }

    window.SizaWorldTcgTransportV01 = Object.freeze({
        BUILD: BUILD,
        onEncounter: onEncounter,
        onResultAccepted: onResultAccepted,
        returnToExploration: returnToExploration,
        submitCombatResult: submitCombatResult,
        getActiveEncounter: function () { return clone(activeEncounter); }
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
