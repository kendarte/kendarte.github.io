(function () {
    "use strict";

    var BUILD = "0.2.1-real-combat-transitions";
    var FRAME_ID = "siza-tcg-embed-frame";
    var STYLE_ID = "siza-combat-animation-v02";
    var STYLE_HREF = "/static/webclient/css/siza_combat_animation_v02.css?v=0201";
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
        stack: Object.create(null),
        positions: null,
        enemyHand: 0,
        life: {player:null, enemy:null}
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

        var phases = doc.getElementById("siza-combat-phase-track-v035");
        if (!phases) {
            phases = doc.createElement("div");
            phases.id = "siza-combat-phase-track-v035";
            phases.className = "sizaCombatPhaseTrackV035";
            phases.innerHTML = '<span data-phase="main">MAIN</span><span data-phase="combat">COMBATE</span><span data-phase="end">END</span><b></b>';
            board.appendChild(phases);
        }

        return {board:board, readout:readout, curtain:curtain, decision:decision, impact:impact, phases:phases};
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

    function phaseKey(value) {
        var raw = text(value).toLowerCase();
        if (/defensa|combat|ataque/.test(raw)) return "combat";
        if (/fin|end/.test(raw)) return "end";
        return "main";
    }

    function syncPhaseTrack(ui, phase, owner) {
        var key = phaseKey(phase);
        ui.phases.setAttribute("data-phase", key);
        ui.phases.setAttribute("data-owner", owner);
        Array.prototype.forEach.call(ui.phases.querySelectorAll("[data-phase]"), function (node) {
            node.setAttribute("data-active", node.getAttribute("data-phase") === key ? "true" : "false");
        });
        var ownerNode = ui.phases.querySelector("b");
        if (ownerNode) ownerNode.textContent = owner === "enemy" ? tr("RIVAL", "RIVAL") : tr("TÚ", "YOU");
    }

    function cardNodes(doc, selector, nameSelector) {
        return Array.prototype.map.call(doc.querySelectorAll(selector), function (node) {
            var label = text(nameSelector ? node.querySelector(nameSelector) && node.querySelector(nameSelector).textContent : node.textContent) || "?";
            var rect = node.getBoundingClientRect();
            return {key:label, node:node, html:node.outerHTML, rect:{left:rect.left, top:rect.top, width:rect.width, height:rect.height}};
        });
    }

    function pointFor(doc, selector) {
        var node = doc.querySelector(selector);
        if (!node) return null;
        var rect = node.getBoundingClientRect();
        return {node:node, html:node.outerHTML, rect:{left:rect.left, top:rect.top, width:rect.width, height:rect.height}};
    }

    function withoutMatches(next, previous) {
        var used = Object.create(null);
        (previous || []).forEach(function (row) { used[row.key] = (used[row.key] || 0) + 1; });
        return (next || []).filter(function (row) {
            if (!used[row.key]) return true;
            used[row.key] -= 1;
            return false;
        });
    }

    function disappeared(previous, next) {
        return withoutMatches(previous, next);
    }

    function firstByKey(rows, key) {
        return (rows || []).find(function (row) { return row.key === key; }) || null;
    }

    function flyCard(doc, from, to, kind) {
        if (!from || !to || !from.rect || !to.rect || !from.rect.width || !to.rect.width) return;
        var ghost = doc.createElement("div");
        ghost.className = "sizaCombatCardFlightV02 sizaCombatCardFlightV02-" + kind;
        ghost.innerHTML = from.html || to.html || "";
        ghost.style.left = from.rect.left + "px";
        ghost.style.top = from.rect.top + "px";
        ghost.style.width = from.rect.width + "px";
        ghost.style.height = from.rect.height + "px";
        doc.body.appendChild(ghost);
        var dx = to.rect.left - from.rect.left;
        var dy = to.rect.top - from.rect.top;
        var scale = Math.max(.45, Math.min(1.35, to.rect.width / from.rect.width));
        window.requestAnimationFrame(function () {
            ghost.style.transform = "translate(" + dx + "px," + dy + "px) scale(" + scale + ")";
            ghost.style.opacity = "0";
        });
        window.setTimeout(function () { if (ghost.parentNode) ghost.parentNode.removeChild(ghost); }, 720);
    }

    function physicalTransfers(doc, positions) {
        var current = {
            hand: cardNodes(doc, ".handV5 .handCardV5", ".cardName"),
            enemyField: cardNodes(doc, ".enemyHalf .arenaField .arenaMiniCard", ".mName"),
            playerField: cardNodes(doc, ".playerHalf .arenaField .arenaMiniCard", ".mName"),
            stack: cardNodes(doc, ".stackAnchorV5 .stackObj", null)
        };
        var enemyBacks = doc.querySelectorAll(".bookEnemyCardBackV03");
        if (!positions) {
            state.positions = current;
            state.enemyHand = enemyBacks.length;
            return;
        }
        var playerLibrary = pointFor(doc, '.bookTcgZoneDock-player [data-book-zone="library"]');
        var enemyLibrary = pointFor(doc, '.bookTcgZoneDock-enemy [data-book-zone="library"]');
        var playerGraveyard = pointFor(doc, '.bookTcgZoneDock-player [data-book-zone="graveyard"]');
        var enemyGraveyard = pointFor(doc, '.bookTcgZoneDock-enemy [data-book-zone="graveyard"]');
        var manifest = pointFor(doc, ".manifestInlineV5");

        if (manifest) {
            disappeared(positions.hand, current.hand).forEach(function (card) {
                flyCard(doc, card, manifest, "manifest");
            });
        }

        withoutMatches(current.hand, positions.hand).forEach(function (card) { flyCard(doc, playerLibrary, card, "draw"); });
        withoutMatches(current.enemyField, positions.enemyField).forEach(function (card) {
            var source = firstByKey(positions.stack, card.key) || manifest;
            flyCard(doc, source, card, "deploy");
        });
        withoutMatches(current.playerField, positions.playerField).forEach(function (card) {
            var source = firstByKey(positions.stack, card.key) || manifest;
            flyCard(doc, source, card, "deploy");
        });
        withoutMatches(current.stack, positions.stack).forEach(function (card) {
            var source = firstByKey(positions.hand, card.key) || manifest;
            flyCard(doc, source, card, "stack");
        });

        disappeared(positions.stack, current.stack).forEach(function (card) {
            var target = firstByKey(current.enemyField, card.key) || firstByKey(current.playerField, card.key) || (card.key && enemyGraveyard);
            flyCard(doc, card, target, "resolve");
        });
        disappeared(positions.playerField, current.playerField).forEach(function (card) {
            flyCard(doc, card, firstByKey(current.hand, card.key) || playerGraveyard, "leave");
        });
        disappeared(positions.enemyField, current.enemyField).forEach(function (card) {
            flyCard(doc, card, enemyGraveyard, "leave");
        });

        if (enemyBacks.length > state.enemyHand && enemyLibrary) {
            flyCard(doc, enemyLibrary, {node:enemyBacks[enemyBacks.length - 1], html:enemyBacks[enemyBacks.length - 1].outerHTML, rect:enemyBacks[enemyBacks.length - 1].getBoundingClientRect()}, "enemy-draw");
        }
        state.enemyHand = enemyBacks.length;
        state.positions = current;
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
        physicalTransfers(doc, state.positions);
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

    function readLife(doc, owner) {
        var node = doc.querySelector("." + owner + "Half .participantHudV035");
        var match = text(node && node.textContent).match(/VIDA\s+(\d+)/i);
        return match ? Number(match[1]) : null;
    }

    function showDamage(ui, owner, amount) {
        if (!amount) return;
        var marker = ui.board.ownerDocument.createElement("div");
        marker.className = "sizaCombatDamageV035";
        marker.setAttribute("data-owner", owner);
        marker.textContent = "−" + amount;
        ui.board.appendChild(marker);
        window.setTimeout(function () { if (marker.parentNode) marker.parentNode.removeChild(marker); }, 950);
    }

    function syncLife(doc, ui) {
        ["player", "enemy"].forEach(function (owner) {
            var next = readLife(doc, owner);
            var previous = state.life[owner];
            if (state.ready && next !== null && previous !== null && next < previous) {
                showDamage(ui, owner, previous - next);
                pulseImpact(ui, "bad");
            }
            state.life[owner] = next;
        });
    }

    function syncCombatTargeting(doc, ui) {
        var attacker = doc.querySelector(".arenaMiniCard.attackingV035");
        var line = doc.getElementById("siza-combat-target-line-v035");
        if (!attacker) {
            if (line) line.remove();
            return;
        }
        var owner = attacker.closest(".enemyHalf") ? "enemy" : "player";
        var blocker = doc.querySelector(".arenaMiniCard.blockingV035");
        var target = blocker || doc.querySelector("." + (owner === "enemy" ? "player" : "enemy") + "Half .participantHudV035");
        if (!target) return;
        if (!line) {
            line = doc.createElement("i");
            line.id = "siza-combat-target-line-v035";
            line.className = "sizaCombatTargetLineV035";
            ui.board.appendChild(line);
        }
        var board = ui.board.getBoundingClientRect();
        var from = attacker.getBoundingClientRect();
        var to = target.getBoundingClientRect();
        var x1 = from.left + from.width / 2 - board.left;
        var y1 = from.top + from.height / 2 - board.top;
        var x2 = to.left + to.width / 2 - board.left;
        var y2 = to.top + to.height / 2 - board.top;
        var dx = x2 - x1;
        var dy = y2 - y1;
        line.style.left = x1 + "px";
        line.style.top = y1 + "px";
        line.style.width = Math.sqrt(dx * dx + dy * dy) + "px";
        line.style.transform = "rotate(" + Math.atan2(dy, dx) + "rad)";
        line.setAttribute("data-blocked", blocker ? "true" : "false");
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
        syncPhaseTrack(ui, banner.phase || banner.side, owner);

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
                showCurtain(ui, tr("TURNO", "TURN"), owner === "enemy" ? tr("RIVAL ACTÚA", "RIVAL ACTS") : tr("TÚ ACTÚAS", "YOU ACT"), 720);
            } else if (phase && phase !== state.lastPhase && !decision) {
                showCurtain(ui, tr("FASE", "PHASE"), phase, 420);
            }
            if (decisionKey && decisionKey !== state.lastDecision) {
                showCurtain(ui, tr("SE REQUIERE TU ACCIÓN", "YOUR ACTION REQUIRED"), decision.title, 820);
            }
        }

        syncManifest(doc, ui);
        syncSemanticAnimations(doc);
        syncLife(doc, ui);
        syncCombatTargeting(doc, ui);

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
        state.positions = null;
        state.enemyHand = 0;
        state.life = {player:null, enemy:null};
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
