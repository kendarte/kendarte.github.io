(function () {
    "use strict";

    var BUILD = "0.2.0-real-combat-transitions";
    var FRAME_ID = "siza-tcg-embed-frame";
    var STYLE_ID = "siza-combat-animation-v02";
    var STYLE_HREF = "/static/webclient/css/siza_combat_animation_v02.css?v=0200";
    var childFrame = null;
    var childObserver = null;
    var parentObserver = null;
    var scanTimer = null;
    var curtainToken = 0;
    var state = {
        ready: false,
        lastTurn: "",
        lastPhase: "",
        lastDecision: "",
        manifestActive: false,
        manifestStatus: "",
        hand: Object.create(null),
        enemyField: Object.create(null),
        playerField: Object.create(null),
        stack: Object.create(null)
    };

    function text(value) {
        return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    }

    function tr(es, en) {
        try {
            return localStorage.getItem("siza_player_language") === "en" ? en : es;
        } catch (error) {
            return es;
        }
    }

    function setText(node, value) {
        if (!node) return;
        var next = String(value == null ? "" : value);
        if (node.textContent !== next) node.textContent = next;
    }

    function bookClient() {
        return document.getElementById("siza-book-client");
    }

    function ensureParentCurtain() {
        var client = bookClient();
        if (!client) return null;
        var body = client.querySelector(".sizaBookBody") || client;
        var node = document.getElementById("siza-combat-book-transition-v02");
        if (!node) {
            node = document.createElement("div");
            node.id = "siza-combat-book-transition-v02";
            node.className = "sizaCombatBookTransitionV02";
            node.innerHTML = '<i class="sizaCombatBladeV02 bladeA"></i><i class="sizaCombatBladeV02 bladeB"></i><div class="sizaCombatBookTitleV02"><small></small><strong></strong></div>';
            body.appendChild(node);
        }
        setText(node.querySelector("small"), tr("ENCUENTRO", "ENCOUNTER"));
        setText(node.querySelector("strong"), tr("COMBATE", "COMBAT"));
        return node;
    }

    function playBookTransition() {
        var node = ensureParentCurtain();
        if (!node) return;
        node.setAttribute("data-state", "closing");
        window.setTimeout(function () {
            if (node) node.setAttribute("data-state", "locked");
        }, 260);
        window.setTimeout(function () {
            if (node) node.setAttribute("data-state", "opening");
        }, 680);
        window.setTimeout(function () {
            if (node) node.removeAttribute("data-state");
        }, 1180);
    }

    function frame() {
        return document.getElementById(FRAME_ID);
    }

    function childDocument() {
        var node = frame();
        try {
            return node && node.contentDocument ? node.contentDocument : null;
        } catch (error) {
            return null;
        }
    }

    function ensureChildStyle(doc) {
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

    function ensureChildUi(doc) {
        var board = doc && doc.querySelector(".matchBoardV5");
        if (!board) return null;

        var readout = doc.getElementById("siza-combat-readout-v02");
        if (!readout) {
            readout = doc.createElement("div");
            readout.id = "siza-combat-readout-v02";
            readout.className = "sizaCombatReadoutV02";
            readout.innerHTML = '<span class="owner"></span><b class="phase"></b>';
            board.appendChild(readout);
        }

        var curtain = doc.getElementById("siza-combat-turn-curtain-v02");
        if (!curtain) {
            curtain = doc.createElement("div");
            curtain.id = "siza-combat-turn-curtain-v02";
            curtain.className = "sizaCombatTurnCurtainV02";
            curtain.innerHTML = '<small></small><strong></strong>';
            board.appendChild(curtain);
        }

        var decision = doc.getElementById("siza-combat-decision-v02");
        if (!decision) {
            decision = doc.createElement("div");
            decision.id = "siza-combat-decision-v02";
            decision.className = "sizaCombatDecisionV02";
            decision.innerHTML = '<strong></strong><span></span>';
            board.appendChild(decision);
        }

        var impact = doc.getElementById("siza-combat-impact-v02");
        if (!impact) {
            impact = doc.createElement("div");
            impact.id = "siza-combat-impact-v02";
            impact.className = "sizaCombatImpactV02";
            board.appendChild(impact);
        }

        return {board:board, readout:readout, curtain:curtain, decision:decision, impact:impact};
    }

    function parseTurn(doc) {
        var raw = text(doc.querySelector(".topMatchChip") && doc.querySelector(".topMatchChip").textContent);
        var match = raw.match(/(?:·|\s)(\d+)\s*$/);
        return match ? match[1] : "";
    }

    function parseBanner(doc) {
        var raw = text(doc.querySelector(".phaseBannerV600") && doc.querySelector(".phaseBannerV600").textContent);
        if (!raw) return {side:"", phase:""};
        var parts = raw.split("·").map(text).filter(Boolean);
        return {side:parts[0] || "", phase:parts.slice(1).join(" · ") || parts[0] || ""};
    }

    function ownerFromBanner(banner) {
        var raw = (banner.side + " " + banner.phase).toLowerCase();
        if (/rival|enemy/.test(raw) && !/tu respuesta|your response|tu defensa|your defense/.test(raw)) return "enemy";
        return "player";
    }

    function friendlyPhase(value) {
        var raw = text(value).toLowerCase();
        if (/inicio rival/.test(raw)) return tr("INICIO RIVAL", "RIVAL START");
        if (/main rival/.test(raw)) return tr("FASE RIVAL", "RIVAL MAIN");
        if (/main/.test(raw)) return tr("FASE PRINCIPAL", "MAIN PHASE");
        if (/defensa/.test(raw)) return tr("DEFENSA", "DEFENSE");
        if (/respuesta/.test(raw)) return tr("RESPUESTA", "RESPONSE");
        if (/stack|resol/.test(raw)) return tr("RESOLUCIÓN", "RESOLUTION");
        return text(value) || tr("COMBATE", "COMBAT");
    }

    function decisionState(doc) {
        var response = doc.querySelector(".responseWindowV53");
        if (response && /tu respuesta|your response/i.test(text(response.textContent))) {
            return {key:"response", title:tr("TU RESPUESTA", "YOUR RESPONSE"), detail:tr("Juega un Instant o pasa prioridad", "Play an Instant or pass priority")};
        }
        var defense = doc.querySelector(".defensePanelV600");
        if (defense && /tu defensa|your defense/i.test(text(defense.textContent))) {
            return {key:"defense", title:tr("TU DEFENSA", "YOUR DEFENSE"), detail:tr("Elige bloqueadores", "Choose blockers")};
        }
        var choice = doc.querySelector(".pendingChoiceV070");
        if (choice) return {key:"choice", title:tr("TU ELECCIÓN", "YOUR CHOICE"), detail:text(choice.textContent)};
        return null;
    }

    function showCurtain(ui, kicker, title, duration) {
        curtainToken += 1;
        var token = curtainToken;
        setText(ui.curtain.querySelector("small"), kicker);
        setText(ui.curtain.querySelector("strong"), title);
        ui.curtain.setAttribute("data-visible", "true");
        window.setTimeout(function () {
            if (token === curtainToken) ui.curtain.removeAttribute("data-visible");
        }, duration || 760);
    }

    function pulseImpact(ui, result) {
        ui.impact.setAttribute("data-impact", result);
        window.setTimeout(function () {
            if (ui.impact.getAttribute("data-impact") === result) ui.impact.removeAttribute("data-impact");
        }, 520);
    }

    function countByName(nodes, nameSelector) {
        var counts = Object.create(null);
        Array.prototype.forEach.call(nodes, function (node) {
            var nameNode = nameSelector ? node.querySelector(nameSelector) : null;
            var key = text(nameNode ? nameNode.textContent : node.textContent) || "?";
            counts[key] = (counts[key] || 0) + 1;
        });
        return counts;
    }

    function animateNewByCount(nodes, oldCounts, nameSelector, kind) {
        var seen = Object.create(null);
        Array.prototype.forEach.call(nodes, function (node) {
            var nameNode = nameSelector ? node.querySelector(nameSelector) : null;
            var key = text(nameNode ? nameNode.textContent : node.textContent) || "?";
            seen[key] = (seen[key] || 0) + 1;
            if ((oldCounts[key] || 0) < seen[key]) {
                node.setAttribute("data-siza-v02-enter", kind);
                window.setTimeout(function () {
                    if (node && node.getAttribute("data-siza-v02-enter") === kind) node.removeAttribute("data-siza-v02-enter");
                }, 820);
            }
        });
    }

    function syncSemanticAnimations(doc) {
        var handNodes = doc.querySelectorAll(".handV5 .handCardV5");
        var enemyNodes = doc.querySelectorAll(".enemyHalf .arenaField .arenaMiniCard");
        var playerNodes = doc.querySelectorAll(".playerHalf .arenaField .arenaMiniCard");
        var stackNodes = doc.querySelectorAll(".stackAnchorV5 .stackObj");

        if (state.ready) {
            animateNewByCount(handNodes, state.hand, ".cardName", "draw");
            animateNewByCount(enemyNodes, state.enemyField, ".mName", "enemy-deploy");
            animateNewByCount(playerNodes, state.playerField, ".mName", "player-deploy");
            animateNewByCount(stackNodes, state.stack, null, "stack");
        }

        state.hand = countByName(handNodes, ".cardName");
        state.enemyField = countByName(enemyNodes, ".mName");
        state.playerField = countByName(playerNodes, ".mName");
        state.stack = countByName(stackNodes, null);
    }

    function syncManifest(doc, ui) {
        var manifest = doc.querySelector(".manifestInlineV5");
        var active = !!manifest;
        if (active) {
            ui.board.setAttribute("data-siza-v02-focus", "manifest");
            if (!state.manifestActive) {
                manifest.setAttribute("data-siza-v02-manifest", "enter");
                window.setTimeout(function () {
                    if (manifest) manifest.removeAttribute("data-siza-v02-manifest");
                }, 900);
            }
            var statusNode = manifest.querySelector(".mfStatus");
            var status = text(statusNode && statusNode.textContent);
            if (status && status !== state.manifestStatus) {
                var good = !!(statusNode && statusNode.classList.contains("good"));
                var bad = !!(statusNode && statusNode.classList.contains("bad"));
                var result = manifest.querySelector(".manifestResultV5");
                if (result) {
                    result.setAttribute("data-siza-v02-result", good ? "good" : bad ? "bad" : "neutral");
                    window.setTimeout(function () {
                        if (result) result.removeAttribute("data-siza-v02-result");
                    }, 720);
                }
                pulseImpact(ui, good ? "good" : bad ? "bad" : "neutral");
            }
            state.manifestStatus = status;
        } else {
            ui.board.removeAttribute("data-siza-v02-focus");
            state.manifestStatus = "";
        }
        state.manifestActive = active;
    }

    function scan() {
        scanTimer = null;
        var doc = childDocument();
        if (!doc) return;
        ensureChildStyle(doc);
        var ui = ensureChildUi(doc);
        if (!ui) return;

        var banner = parseBanner(doc);
        var turn = parseTurn(doc);
        var owner = ownerFromBanner(banner);
        var phase = friendlyPhase(banner.phase || banner.side);
        var decision = decisionState(doc);
        var decisionKey = decision ? decision.key : "";

        setText(ui.readout.querySelector(".owner"), (turn ? tr("TURNO ", "TURN ") + turn + " · " : "") + (owner === "enemy" ? tr("RIVAL", "RIVAL") : tr("JUGADOR", "PLAYER")));
        setText(ui.readout.querySelector(".phase"), phase);
        ui.readout.setAttribute("data-owner", owner);

        if (decision) {
            ui.board.setAttribute("data-siza-v02-decision", decision.key);
            setText(ui.decision.querySelector("strong"), decision.title);
            setText(ui.decision.querySelector("span"), decision.detail);
            ui.decision.setAttribute("data-visible", "true");
        } else {
            ui.board.removeAttribute("data-siza-v02-decision");
            ui.decision.removeAttribute("data-visible");
        }

        if (state.ready) {
            if (turn && turn !== state.lastTurn) {
                showCurtain(ui, tr("CAMBIO DE TURNO", "TURN CHANGE"), owner === "enemy" ? tr("TURNO RIVAL", "RIVAL TURN") : tr("TU TURNO", "YOUR TURN"), 900);
            } else if (phase && phase !== state.lastPhase && !decision) {
                showCurtain(ui, tr("FASE", "PHASE"), phase, 680);
            }
            if (decisionKey && decisionKey !== state.lastDecision) {
                showCurtain(ui, tr("SE REQUIERE TU ACCIÓN", "YOUR ACTION REQUIRED"), decision.title, 820);
            }
        }

        syncManifest(doc, ui);
        syncSemanticAnimations(doc);

        state.lastTurn = turn;
        state.lastPhase = phase;
        state.lastDecision = decisionKey;
        state.ready = true;
    }

    function scheduleScan() {
        if (scanTimer) window.clearTimeout(scanTimer);
        scanTimer = window.setTimeout(scan, 28);
    }

    function observeChild() {
        var doc = childDocument();
        if (!doc || !doc.documentElement || typeof MutationObserver !== "function") return false;
        ensureChildStyle(doc);
        if (childObserver) childObserver.disconnect();
        childObserver = new MutationObserver(scheduleScan);
        childObserver.observe(doc.documentElement, {childList:true, subtree:true, characterData:true});
        scheduleScan();
        return true;
    }

    function resetState() {
        state.ready = false;
        state.lastTurn = "";
        state.lastPhase = "";
        state.lastDecision = "";
        state.manifestActive = false;
        state.manifestStatus = "";
        state.hand = Object.create(null);
        state.enemyField = Object.create(null);
        state.playerField = Object.create(null);
        state.stack = Object.create(null);
    }

    function attachFrame() {
        var node = frame();
        if (!node) return false;
        if (childFrame !== node) {
            childFrame = node;
            resetState();
            node.addEventListener("load", function () {
                resetState();
                window.setTimeout(observeChild, 0);
            });
        }
        observeChild();
        return true;
    }

    function init() {
        ensureParentCurtain();
        attachFrame();
        if (window.Evennia) {
            window.Evennia.init();
            if (window.Evennia.emitter && typeof window.Evennia.emitter.on === "function") {
                window.Evennia.emitter.on("siza_combat_encounter", function () {
                    playBookTransition();
                    window.setTimeout(attachFrame, 0);
                });
            }
        }
        if (typeof MutationObserver === "function" && document.documentElement) {
            parentObserver = new MutationObserver(attachFrame);
            parentObserver.observe(document.documentElement, {childList:true, subtree:true});
        }
    }

    window.SizaCombatAnimationV02 = Object.freeze({
        BUILD: BUILD,
        STYLE_HREF: STYLE_HREF,
        playBookTransition: playBookTransition,
        attachFrame: attachFrame,
        refresh: scheduleScan
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
