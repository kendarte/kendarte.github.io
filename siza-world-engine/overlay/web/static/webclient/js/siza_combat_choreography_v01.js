(function () {
    "use strict";

    var BUILD = "0.1.0-combat-choreography";
    var FRAME_ID = "siza-tcg-embed-frame";
    var STYLE_ID = "siza-combat-choreography-v01";
    var STYLE_HREF = "/static/webclient/css/siza_combat_choreography_v01.css?v=0100";
    var parentObserver = null;
    var childObserver = null;
    var childFrame = null;
    var updateTimer = null;
    var cueTimer = null;
    var cueQueue = [];
    var cueBusy = false;
    var lastStateSignature = "";
    var lastTurn = "";
    var lastSide = "";
    var lastPhase = "";
    var lastDecision = "";
    var lastLog = "";

    function text(value) {
        return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    }

    function language() {
        try {
            return localStorage.getItem("siza_player_language") === "en" ? "en" : "es";
        } catch (error) {
            return "es";
        }
    }

    function tr(es, en) {
        return language() === "en" ? en : es;
    }

    function bookClient() {
        return document.getElementById("siza-book-client");
    }

    function ensureParentTransitionCue() {
        var client = bookClient();
        if (!client) return null;
        var body = client.querySelector(".sizaBookBody") || client;
        var cue = document.getElementById("siza-combat-entry-cue-v01");
        if (!cue) {
            cue = document.createElement("div");
            cue.id = "siza-combat-entry-cue-v01";
            cue.className = "sizaCombatEntryCueV01";
            cue.setAttribute("aria-hidden", "true");
            cue.innerHTML = '<span class="sizaCombatEntryRuleV01"></span><strong></strong><small></small><span class="sizaCombatEntryRuleV01"></span>';
            body.appendChild(cue);
        }
        return cue;
    }

    function beginCombatTransition() {
        var client = bookClient();
        if (!client) return false;
        var cue = ensureParentTransitionCue();
        client.setAttribute("data-combat-transition", "entering");
        if (cue) {
            cue.querySelector("strong").textContent = tr("COMBATE", "COMBAT");
            cue.querySelector("small").textContent = tr("El escenario se convierte en campo de batalla", "The scene becomes the battlefield");
        }
        window.setTimeout(function () {
            if (client.getAttribute("data-combat-transition") === "entering") {
                client.setAttribute("data-combat-transition", "arming");
            }
        }, 260);
        window.setTimeout(function () {
            var stage = client.getAttribute("data-combat-transition");
            if (stage === "entering" || stage === "arming") {
                client.setAttribute("data-combat-transition", "deploy");
            }
        }, 520);
        window.setTimeout(function () {
            if (client.getAttribute("data-combat-transition") === "deploy") {
                client.removeAttribute("data-combat-transition");
            }
        }, 980);
        return true;
    }

    function childWindow() {
        try {
            return childFrame && childFrame.contentWindow ? childFrame.contentWindow : null;
        } catch (error) {
            return null;
        }
    }

    function childDocument() {
        var win = childWindow();
        try {
            return win && win.document ? win.document : null;
        } catch (error) {
            return null;
        }
    }

    function ensureChildStyle() {
        var doc = childDocument();
        if (!doc || !doc.head) return false;
        var link = doc.getElementById(STYLE_ID);
        if (!link) {
            link = doc.createElement("link");
            link.id = STYLE_ID;
            link.rel = "stylesheet";
            link.type = "text/css";
            doc.head.appendChild(link);
        }
        if (link.getAttribute("href") !== STYLE_HREF) link.href = STYLE_HREF;
        return true;
    }

    function ensureChildUi() {
        var doc = childDocument();
        if (!doc) return null;
        var board = doc.querySelector(".matchBoardV5");
        if (!board) return null;

        var hud = doc.getElementById("siza-combat-state-hud-v01");
        if (!hud) {
            hud = doc.createElement("div");
            hud.id = "siza-combat-state-hud-v01";
            hud.className = "sizaCombatStateHudV01";
            hud.innerHTML = '<span class="sizaCombatTurnV01"></span><strong class="sizaCombatPhaseV01"></strong>';
            board.appendChild(hud);
        }

        var cue = doc.getElementById("siza-combat-phase-cue-v01");
        if (!cue) {
            cue = doc.createElement("div");
            cue.id = "siza-combat-phase-cue-v01";
            cue.className = "sizaCombatPhaseCueV01";
            cue.innerHTML = '<small></small><strong></strong>';
            board.appendChild(cue);
        }

        var decision = doc.getElementById("siza-combat-decision-v01");
        if (!decision) {
            decision = doc.createElement("div");
            decision.id = "siza-combat-decision-v01";
            decision.className = "sizaCombatDecisionV01";
            decision.innerHTML = '<strong></strong><span></span>';
            board.appendChild(decision);
        }

        var action = doc.getElementById("siza-combat-action-v01");
        if (!action) {
            action = doc.createElement("div");
            action.id = "siza-combat-action-v01";
            action.className = "sizaCombatActionV01";
            action.innerHTML = '<strong></strong><span></span>';
            board.appendChild(action);
        }

        return {board:board,hud:hud,cue:cue,decision:decision,action:action};
    }

    function parseTurn(doc) {
        var chip = doc.querySelector(".topMatchChip");
        var raw = text(chip && chip.textContent);
        var match = raw.match(/(?:·|\s)(\d+)\s*$/);
        return match ? match[1] : "";
    }

    function parseBanner(doc) {
        var banner = doc.querySelector(".phaseBannerV600");
        var raw = text(banner && banner.textContent);
        if (!raw) return {side:"",phase:""};
        var pieces = raw.split("·").map(text).filter(Boolean);
        return {side:pieces[0] || "", phase:pieces.slice(1).join(" · ") || pieces[0] || ""};
    }

    function sideKey(side) {
        var s = text(side).toLowerCase();
        if (/rival|enemy/.test(s)) return "enemy";
        if (/tu turno|your turn|tu respuesta|your response|tu defensa|your defense/.test(s)) return "player";
        return "neutral";
    }

    function friendlyPhase(side, phase) {
        var value = text(phase).toLowerCase();
        var sideValue = sideKey(side);
        if (/inicio rival/.test(value)) return tr("INICIO DEL RIVAL", "RIVAL START");
        if (/main rival/.test(value)) return tr("FASE PRINCIPAL RIVAL", "RIVAL MAIN PHASE");
        if (/main/.test(value)) return sideValue === "enemy" ? tr("FASE PRINCIPAL RIVAL", "RIVAL MAIN PHASE") : tr("FASE PRINCIPAL", "MAIN PHASE");
        if (/defensa rival/.test(value)) return tr("DEFENSA RIVAL", "RIVAL DEFENSE");
        if (/tu defensa/.test(value)) return tr("TU DEFENSA", "YOUR DEFENSE");
        if (/respuesta rival/.test(value)) return tr("RESPUESTA RIVAL", "RIVAL RESPONSE");
        if (/respuesta/.test(value)) return tr("TU RESPUESTA", "YOUR RESPONSE");
        if (/stack|resol/.test(value)) return tr("RESOLUCIÓN", "RESOLUTION");
        if (/elecci|choice|elige/.test(value)) return tr("ELECCIÓN", "CHOICE");
        return text(phase || side) || tr("COMBATE", "COMBAT");
    }

    function friendlyTurn(side, turn) {
        var key = sideKey(side);
        var prefix = turn ? tr("TURNO ", "TURN ") + turn + " · " : "";
        if (key === "enemy") return prefix + tr("RIVAL", "RIVAL");
        if (key === "player") return prefix + tr("TU TURNO", "YOUR TURN");
        return prefix + tr("COMBATE", "COMBAT");
    }

    function decisionState(doc) {
        var response = doc.querySelector(".responseWindowV53");
        if (response && /tu respuesta|your response/i.test(text(response.textContent))) {
            return {key:"response",title:tr("TU RESPUESTA", "YOUR RESPONSE"),detail:tr("Juega un Instant o pasa prioridad", "Play an Instant or pass priority")};
        }
        var defense = doc.querySelector(".defensePanelV600");
        if (defense && /tu defensa|your defense/i.test(text(defense.textContent))) {
            return {key:"defense",title:tr("TU DEFENSA", "YOUR DEFENSE"),detail:tr("Elige bloqueadores", "Choose blockers")};
        }
        var choice = doc.querySelector(".pendingChoiceV070");
        if (choice) {
            var heading = text(choice.querySelector("h3") && choice.querySelector("h3").textContent);
            return {key:"choice",title:tr("TU ELECCIÓN", "YOUR CHOICE"),detail:heading || tr("Elige una opción", "Choose an option")};
        }
        var equip = doc.querySelector(".equipPanelV600");
        if (equip) {
            return {key:"equip",title:tr("EQUIPAR", "EQUIP"),detail:tr("Elige objetivo y cristal", "Choose target and crystal")};
        }
        return null;
    }

    function meaningfulLog(doc) {
        var item = doc.querySelector(".matchLog .logItem");
        if (!item) return null;
        var full = text(item.textContent);
        if (!full || full === lastLog) return null;
        var heading = text(item.querySelector("strong") && item.querySelector("strong").textContent);
        if (!/(Manafestation|Materializaci[oó]n|Permanente|Daño|Ataque|Negaci[oó]n|Equipar|Respuesta|Efecto|Combate|Cristales)/i.test(heading)) {
            lastLog = full;
            return null;
        }
        lastLog = full;
        var detail = full;
        if (heading && detail.indexOf(heading) === 0) detail = text(detail.slice(heading.length).replace(/^\s*[·:-]\s*/, ""));
        return {heading:heading || tr("ACCIÓN", "ACTION"),detail:detail};
    }

    function showAction(ui, packet) {
        if (!ui || !packet) return;
        var node = ui.action;
        node.querySelector("strong").textContent = packet.heading;
        node.querySelector("span").textContent = packet.detail;
        node.setAttribute("data-visible", "true");
        window.setTimeout(function () {
            if (node) node.removeAttribute("data-visible");
        }, 760);
    }

    function enqueueCue(packet) {
        if (!packet || !packet.title) return;
        var last = cueQueue[cueQueue.length - 1];
        if (last && last.signature === packet.signature) return;
        if (cueQueue.length >= 3 && packet.kind === "phase") {
            for (var i = cueQueue.length - 1; i >= 0; i--) {
                if (cueQueue[i].kind === "phase") {
                    cueQueue.splice(i, 1);
                    break;
                }
            }
        }
        cueQueue.push(packet);
        playNextCue();
    }

    function playNextCue() {
        if (cueBusy || !cueQueue.length) return;
        var doc = childDocument();
        var ui = ensureChildUi();
        if (!doc || !ui) return;
        var packet = cueQueue.shift();
        cueBusy = true;
        var cue = ui.cue;
        cue.setAttribute("data-kind", packet.kind || "phase");
        cue.querySelector("small").textContent = packet.kicker || "";
        cue.querySelector("strong").textContent = packet.title;
        cue.setAttribute("data-visible", "true");
        var duration = packet.duration || 380;
        cueTimer = window.setTimeout(function () {
            cue.removeAttribute("data-visible");
            window.setTimeout(function () {
                cueBusy = false;
                playNextCue();
            }, 120);
        }, duration);
    }

    function updatePresentation() {
        updateTimer = null;
        var doc = childDocument();
        if (!doc) return;
        ensureChildStyle();
        var ui = ensureChildUi();
        if (!ui) return;

        var banner = parseBanner(doc);
        var turn = parseTurn(doc);
        var phaseTitle = friendlyPhase(banner.side, banner.phase);
        var turnTitle = friendlyTurn(banner.side, turn);
        var decision = decisionState(doc);
        var decisionKey = decision ? decision.key : "";
        var signature = [turn,banner.side,banner.phase,decisionKey].join("|");

        ui.hud.querySelector(".sizaCombatTurnV01").textContent = turnTitle;
        ui.hud.querySelector(".sizaCombatPhaseV01").textContent = phaseTitle;
        ui.hud.setAttribute("data-side", sideKey(banner.side));

        if (decision) {
            ui.board.setAttribute("data-siza-decision", decision.key);
            ui.decision.querySelector("strong").textContent = decision.title;
            ui.decision.querySelector("span").textContent = decision.detail;
            ui.decision.setAttribute("data-visible", "true");
        } else {
            ui.board.removeAttribute("data-siza-decision");
            ui.decision.removeAttribute("data-visible");
        }

        if (signature !== lastStateSignature) {
            var side = sideKey(banner.side);
            var turnChanged = !!lastTurn && turn !== lastTurn;
            var sideChanged = !!lastSide && side !== lastSide && side !== "neutral";
            var phaseChanged = !!lastPhase && banner.phase !== lastPhase;
            var decisionChanged = decisionKey && decisionKey !== lastDecision;

            if (!lastStateSignature || turnChanged || sideChanged) {
                enqueueCue({kind:"turn",kicker:turn ? tr("TURNO ", "TURN ") + turn : "",title:side === "enemy" ? tr("TURNO RIVAL", "RIVAL TURN") : tr("TU TURNO", "YOUR TURN"),duration:650,signature:"turn|"+turn+"|"+side});
            } else if (decisionChanged) {
                enqueueCue({kind:"decision",kicker:tr("SE NECESITA TU DECISIÓN", "YOUR DECISION REQUIRED"),title:decision.title,duration:500,signature:"decision|"+decisionKey+"|"+turn});
            } else if (phaseChanged) {
                enqueueCue({kind:"phase",kicker:tr("CAMBIO DE FASE", "PHASE CHANGE"),title:phaseTitle,duration:360,signature:"phase|"+turn+"|"+banner.phase});
            }

            lastStateSignature = signature;
            lastTurn = turn;
            lastSide = side;
            lastPhase = banner.phase;
            lastDecision = decisionKey;
        }

        showAction(ui, meaningfulLog(doc));
    }

    function scheduleUpdate() {
        if (updateTimer) window.clearTimeout(updateTimer);
        updateTimer = window.setTimeout(updatePresentation, 24);
    }

    function observeChild() {
        var doc = childDocument();
        if (!doc || !doc.documentElement || typeof MutationObserver !== "function") return false;
        ensureChildStyle();
        if (childObserver) childObserver.disconnect();
        childObserver = new MutationObserver(scheduleUpdate);
        childObserver.observe(doc.documentElement, {childList:true,subtree:true,characterData:true});
        scheduleUpdate();
        return true;
    }

    function attachFrame() {
        var frame = document.getElementById(FRAME_ID);
        if (!frame) return false;
        if (childFrame !== frame) {
            childFrame = frame;
            lastStateSignature = "";
            lastTurn = "";
            lastSide = "";
            lastPhase = "";
            lastDecision = "";
            lastLog = "";
            cueQueue = [];
            cueBusy = false;
            frame.addEventListener("load", function () {
                window.setTimeout(observeChild, 0);
            });
        }
        observeChild();
        return true;
    }

    function onEncounter() {
        beginCombatTransition();
        window.setTimeout(attachFrame, 0);
    }

    function init() {
        ensureParentTransitionCue();
        attachFrame();
        if (window.Evennia) {
            Evennia.init();
            if (Evennia.emitter && typeof Evennia.emitter.on === "function") {
                Evennia.emitter.on("siza_combat_encounter", onEncounter);
            }
        }
        if (typeof MutationObserver === "function" && document.documentElement) {
            parentObserver = new MutationObserver(attachFrame);
            parentObserver.observe(document.documentElement, {childList:true,subtree:true});
        }
    }

    window.SizaCombatChoreographyV01 = Object.freeze({
        BUILD: BUILD,
        STYLE_HREF: STYLE_HREF,
        beginCombatTransition: beginCombatTransition,
        attachFrame: attachFrame,
        refresh: scheduleUpdate
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
