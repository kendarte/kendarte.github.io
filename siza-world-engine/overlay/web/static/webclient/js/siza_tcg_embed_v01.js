(function () {
    "use strict";

    var BUILD = "0.5.0-full-board-canonical-arena";
    var FRAME_SRC = "/static/webclient/tcg/siza-mobile-test/index.html?siza_world_embed=1";
    var CANONICAL_PLAYER_FALLBACK = "Nereida";
    var CANONICAL_PLAYER_PORTRAIT = "/static/webclient/tcg/siza-mobile-test/portraits/nereida_voss.webp?v=0514";
    var frame = null;
    var frameReady = false;
    var pendingEncounter = null;
    var lastResultId = "";
    var pollTimer = null;

    function byId(id) { return document.getElementById(id); }
    function clone(value) {
        try { return JSON.parse(JSON.stringify(value)); }
        catch (error) { return value; }
    }
    function text(value) { return String(value == null ? "" : value).trim(); }

    function setStatus(label) {
        var node = byId("siza-tcg-status");
        if (node) node.textContent = text(label);
    }

    function childWindow() {
        try { return frame && frame.contentWindow ? frame.contentWindow : null; }
        catch (error) { return null; }
    }

    function canonicalPlayerName() {
        var stores = [];
        var child = childWindow();
        try { if (child && child.localStorage) stores.push(child.localStorage); } catch (error) {}
        try { if (window.localStorage) stores.push(window.localStorage); } catch (error) {}
        for (var i = 0; i < stores.length; i += 1) {
            try {
                var raw = stores[i].getItem("siza_work_state_v1");
                if (!raw) continue;
                var saved = JSON.parse(raw);
                var name = text(saved && saved.player && saved.player.mag && saved.player.mag.name);
                if (name && !/^(admin|administrator)$/i.test(name)) return name;
            } catch (error) {}
        }
        return CANONICAL_PLAYER_FALLBACK;
    }

    function canonicalEncounter(encounter) {
        var packet = clone(encounter);
        if (!packet || typeof packet !== "object") return packet;
        packet.initiator = packet.initiator && typeof packet.initiator === "object" ? packet.initiator : {};
        packet.initiator.name = canonicalPlayerName();
        if (!text(packet.initiator.portrait)) packet.initiator.portrait = CANONICAL_PLAYER_PORTRAIT;
        return packet;
    }

    function applyEncounterContext(encounter) {
        var player = encounter && encounter.initiator || {};
        var rival = encounter && encounter.opponents && encounter.opponents[0] || {};
        var site = encounter && encounter.site || {};
        var playerName = text(player.name);
        var rivalName = text(rival.name);
        var location = text(site.name || site.room_id);
        var set = function (id, value) {
            var node = byId(id);
            if (node && value) node.textContent = value;
        };
        set("siza-player-name", playerName);
        set("siza-player-portrait-name", playerName);
        set("siza-focus-portrait-name", rivalName);
        set("siza-location-label", location);
        set("siza-mode-label", "COMBATE");
    }

    function host() {
        var tray = byId("siza-tcg-tray");
        if (!tray) return null;
        var node = byId("siza-tcg-embed-host");
        if (!node) {
            node = document.createElement("div");
            node.id = "siza-tcg-embed-host";
            node.className = "sizaTcgEmbedHost";
            tray.insertBefore(node, tray.firstChild || null);
        }
        tray.setAttribute("data-embed-mounted", "true");
        tray.setAttribute("data-arena-source", "siza-mobile-test");
        return node;
    }

    /* The iframe hosts the canonical Arena. The embed adaptation is limited to:
       - removing duplicate standalone/book chrome,
       - making the Arena consume the iframe height exactly,
       - keeping the canonical player identity visible.
       It does not replace battlefield interaction or card logic. */
    function injectEmbedStyle() {
        var child = childWindow();
        if (!child || !child.document || !child.document.head) return false;
        var existing = child.document.getElementById("siza-world-embed-style");
        if (existing) existing.remove();
        var style = child.document.createElement("style");
        style.id = "siza-world-embed-style";
        style.textContent = `
html,body,#app{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;overflow:hidden!important;background:#07111b!important}
#bootFallback,.sidebar,.topbar,.arenaNavToggleV600,.arenaNavPanelV600,.arenaNavVeilV600{display:none!important}
.shell,.main{display:block!important;width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;grid-column:auto!important;background:#07111b!important;overflow:hidden!important}
.bookShellV01.modeCombat{width:100%!important;height:100%!important;min-height:0!important;max-height:none!important;margin:0!important;border:0!important;border-radius:0!important;box-shadow:none!important;overflow:hidden!important}
.bookShellV01.modeCombat>.bookHeaderV01{display:none!important}
.bookShellV01.modeCombat>.bookBodyV01{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;overflow:hidden!important}
.bookShellV01.modeCombat .bookSceneV01{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;overflow:hidden!important;background:#07111b!important}
.bookShellV01.modeCombat .bookNarrativeV01{display:none!important}
.bookShellV01.modeCombat .matchShell.v05{display:block!important;width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important}
.bookShellV01.modeCombat .matchBoardV5{width:100%!important;height:100%!important;min-height:0!important;max-height:none!important;margin:0!important;border-radius:0!important}
.participantHudV035{display:flex!important;flex-direction:column!important;gap:3px!important;align-items:flex-start!important;justify-content:center!important;min-width:104px!important;line-height:1.15!important}
.participantHudV035>b,.participantHudV035>span{display:block!important;margin:0!important}
.arenaHalf.playerHalf .participantHudV035::before{content:"";display:block;width:86px;height:100px;margin:0 auto 7px;border:1px solid #8b6b36;border-radius:10px;background:url("${CANONICAL_PLAYER_PORTRAIT}") 50% 18%/cover no-repeat;box-shadow:0 9px 20px rgba(0,0,0,.42)}
@media(max-height:700px) and (min-width:761px){
  .arenaHalf{height:calc(50% - 62px)!important;min-height:0!important;padding-top:6px!important;padding-bottom:6px!important}
  .arenaHalf.playerHalf{padding-bottom:6px!important}
  .handAreaV5{height:178px!important}
  .handV5{height:176px!important}
}
`;
        child.document.head.appendChild(style);
        return true;
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function forwardResult(result) {
        var packet = result && result.result ? result.result : result;
        if (!packet || typeof packet !== "object" || !text(packet.encounter_id)) return false;
        var resultId = text(packet.result_id) || text(packet.encounter_id) + ":RESULT";
        if (resultId === lastResultId) return true;
        lastResultId = resultId;
        stopPolling();
        window.dispatchEvent(new CustomEvent("siza:combat-result", {detail: clone(packet)}));
        return true;
    }

    function attachChildResultBridge() {
        var child = childWindow();
        if (!child || typeof child.addEventListener !== "function") return false;
        child.addEventListener("siza:combat-result", function (event) {
            forwardResult(event && event.detail);
        });
        return true;
    }

    function startPollingResult() {
        stopPolling();
        pollTimer = setInterval(function () {
            var child = childWindow();
            if (!child || !child.SIZA || typeof child.SIZA.getWorldCombatResult !== "function") return;
            try {
                var result = child.SIZA.getWorldCombatResult();
                if (result) forwardResult(result);
            } catch (error) {
                /* The child event is primary; polling is only a safety net. */
            }
        }, 400);
    }

    function startInChild(encounter, mode) {
        var child = childWindow();
        if (!frameReady || !child || !child.SIZA || typeof child.SIZA.startWorldEncounter !== "function") {
            return {ok:true, status:"ARENA_LOADING", build:BUILD};
        }
        injectEmbedStyle();
        var started;
        try {
            started = child.SIZA.startWorldEncounter(clone(encounter), mode || "prepare");
        } catch (error) {
            setStatus("Arena start error");
            return {ok:false, status:"ARENA_START_EXCEPTION", error:text(error && error.message || error), build:BUILD};
        }
        if (!started || started.ok !== true) return started || {ok:false,status:"ARENA_START_REJECTED",build:BUILD};
        window.setTimeout(injectEmbedStyle, 0);
        setStatus("Arena active");
        startPollingResult();
        return started;
    }

    function onFrameLoad() {
        frameReady = true;
        injectEmbedStyle();
        attachChildResultBridge();
        if (pendingEncounter) {
            var packet = startInChild(pendingEncounter.encounter, pendingEncounter.mode);
            if (!packet || packet.ok !== true) setStatus("Arena rejected encounter");
        } else {
            setStatus("Arena ready");
        }
    }

    function ensureFrame() {
        var mount = host();
        if (!mount) return null;
        if (frame) return frame;
        frame = document.createElement("iframe");
        frame.id = "siza-tcg-embed-frame";
        frame.className = "sizaTcgEmbedFrame";
        frame.title = "Siza Arena";
        frame.setAttribute("loading", "eager");
        frame.setAttribute("allow", "autoplay");
        frame.src = FRAME_SRC;
        frame.addEventListener("load", onFrameLoad);
        mount.appendChild(frame);
        setStatus("Loading Arena");
        return frame;
    }

    function startWorldEncounter(encounter, mode) {
        if (!encounter || typeof encounter !== "object" || !text(encounter.encounter_id)) {
            return {ok:false,status:"INVALID_ENCOUNTER",build:BUILD};
        }
        lastResultId = "";
        var packet = canonicalEncounter(encounter);
        pendingEncounter = {encounter:packet, mode:mode || "prepare"};
        applyEncounterContext(packet);
        ensureFrame();
        return startInChild(packet, pendingEncounter.mode);
    }

    function getWorldCombatResult() {
        var child = childWindow();
        if (!child || !child.SIZA || typeof child.SIZA.getWorldCombatResult !== "function") return null;
        try { return clone(child.SIZA.getWorldCombatResult()); }
        catch (error) { return null; }
    }

    function init() {
        var proxy = window.SIZA && typeof window.SIZA === "object" ? window.SIZA : {};
        proxy.startWorldEncounter = startWorldEncounter;
        proxy.getWorldCombatResult = getWorldCombatResult;
        window.SIZA = proxy;
    }

    window.SizaTcgEmbedV01 = Object.freeze({
        BUILD:BUILD,
        FRAME_SRC:FRAME_SRC,
        ensureFrame:ensureFrame,
        startWorldEncounter:startWorldEncounter,
        getWorldCombatResult:getWorldCombatResult,
        forwardResult:forwardResult,
        injectEmbedStyle:injectEmbedStyle,
        canonicalEncounter:canonicalEncounter
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
