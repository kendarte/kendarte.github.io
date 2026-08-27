(function () {
    "use strict";

    var BUILD = "0.2.0-book-combat-composition";
    var FRAME_SRC = "/static/webclient/tcg/siza-mobile-test/index.html?siza_world_embed=1";
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
        return node;
    }

    function childWindow() {
        try { return frame && frame.contentWindow ? frame.contentWindow : null; }
        catch (error) { return null; }
    }

    function injectEmbedStyle() {
        var child = childWindow();
        if (!child || !child.document || !child.document.head) return false;
        var existing = child.document.getElementById("siza-world-embed-style");
        if (existing) existing.remove();

        var style = child.document.createElement("style");
        style.id = "siza-world-embed-style";
        style.textContent = `
html,body,#app{
  width:100%!important;height:100%!important;min-height:0!important;margin:0!important;
  overflow:hidden!important;background:transparent!important;
}
#bootFallback{display:none!important}
.sidebar,.topbar,.arenaNavToggleV600,.arenaNavPanelV600,.arenaNavVeilV600,
.bookHeaderV01,.bookNarrativeV01,.matchHeader,.mobileDuelHudV610,.rotateHintV5,
.ruleModeBadgeV070,.combatLaneV610{display:none!important}
.shell,.main,.bookShellV01,.bookBodyV01,.bookSceneV01{
  width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;
  border:0!important;background:transparent!important;box-shadow:none!important;
}
.shell{display:block!important}.main{display:block!important;grid-column:auto!important}
.bookBodyV01{display:block!important}.bookSceneV01{overflow:hidden!important}
.matchShell.v05{position:relative!important;display:block!important;width:100%!important;height:100%!important;min-height:0!important;margin:0!important;gap:0!important;background:transparent!important}
.matchBoardV5{
  position:absolute!important;inset:0!important;width:100%!important;height:100%!important;min-height:0!important;max-height:none!important;
  overflow:hidden!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;
}
.matchBoardV5:before{display:none!important}
.phaseBannerV600{
  top:7px!important;left:50%!important;z-index:24!important;padding:4px 10px!important;
  border:1px solid rgba(99,69,38,.72)!important;border-radius:999px!important;
  background:rgba(37,24,16,.76)!important;color:#d7c39b!important;font:700 7px/1.2 system-ui,sans-serif!important;
}
/* Battlefield: same location image underneath, portraits at the book edges, summons in the middle. */
.arenaHalf{
  position:absolute!important;z-index:5!important;left:0!important;right:0!important;top:22px!important;height:255px!important;min-height:0!important;
  display:block!important;padding:0!important;border:0!important;background:transparent!important;pointer-events:none!important;
}
.arenaHalf.enemyHalf{border:0!important}
.arenaHalf .arenaMag,.arenaHalf .arenaField,.arenaHalf .arenaZones{pointer-events:auto!important}
.enemyHalf .arenaMag{
  position:absolute!important;right:14px!important;top:15px!important;width:142px!important;height:220px!important;
  border:1px solid rgba(105,72,43,.72)!important;border-radius:4px!important;background:rgba(33,21,15,.58)!important;
  box-shadow:0 10px 24px rgba(0,0,0,.34)!important;
}
.playerHalf .arenaMagSlot{
  position:absolute!important;left:14px!important;top:15px!important;width:142px!important;height:220px!important;display:block!important;
}
.playerHalf .arenaMag{
  width:142px!important;height:220px!important;border:1px solid rgba(79,82,72,.72)!important;border-radius:4px!important;
  background:rgba(21,28,27,.54)!important;box-shadow:0 10px 24px rgba(0,0,0,.34)!important;
}
.arenaMagInfo{
  left:5px!important;right:5px!important;bottom:5px!important;padding:5px 7px!important;border-radius:3px!important;
  border:1px solid rgba(175,139,83,.32)!important;background:rgba(24,16,11,.78)!important;
}
.arenaMagInfo b{font:700 11px Georgia,serif!important;color:#ead9b7!important}.arenaMagInfo span{font-size:7px!important;color:#b9a785!important}
.arenaLifeV5{top:5px!important;right:5px!important;border-radius:999px!important;background:rgba(48,20,22,.82)!important}
.enemyHalf .arenaField{
  position:absolute!important;left:52%!important;right:170px!important;top:48px!important;height:155px!important;min-height:0!important;
  justify-content:flex-start!important;align-items:center!important;flex-wrap:wrap!important;gap:7px!important;overflow:visible!important;
}
.playerHalf .arenaField{
  position:absolute!important;left:170px!important;right:52%!important;top:48px!important;height:155px!important;min-height:0!important;
  justify-content:flex-end!important;align-items:center!important;flex-wrap:wrap!important;gap:7px!important;overflow:visible!important;
}
.arenaHalf .arenaZones{display:none!important}
.arenaMiniCard{width:78px!important;height:112px!important;padding:3px!important;border-radius:8px!important;box-shadow:0 8px 18px rgba(0,0,0,.38)!important}
.arenaMiniCard .finalPrintedImageV59{border-radius:5px!important}
.emptyFieldV5{min-height:88px!important;color:rgba(229,215,184,.58)!important;font:700 8px Georgia,serif!important;text-shadow:0 1px 3px rgba(0,0,0,.8)!important}
/* Combat narration occupies the same horizontal book strip used by dialogue/exploration. */
.matchBoardV5 .matchLog{
  display:block!important;position:absolute!important;z-index:28!important;left:0!important;right:0!important;top:278px!important;
  width:auto!important;height:68px!important;max-height:68px!important;overflow:hidden!important;transform:none!important;
  padding:9px 22px!important;border:0!important;border-top:3px solid #3b281a!important;border-bottom:2px solid #3b281a!important;border-radius:0!important;
  background:linear-gradient(90deg,rgba(92,59,31,.06),transparent 10%,transparent 90%,rgba(92,59,31,.06)),linear-gradient(180deg,#e3d2ae,#cfb98f)!important;
  box-shadow:inset 0 0 24px rgba(89,61,32,.12)!important;
}
.matchLog .logItem{padding:2px 0!important;border:0!important;color:#3b2b1d!important;font:12px/1.28 Georgia,serif!important}
.matchLog .logItem strong{color:#6b3829!important}.matchLog .logItem:nth-child(n+4){display:none!important}
/* Hand is the lower book page, large and readable. */
.handAreaV5{
  left:155px!important;right:285px!important;bottom:44px!important;height:150px!important;z-index:30!important;
  padding:0!important;display:flex!important;align-items:flex-end!important;justify-content:center!important;
  overflow:visible!important;background:transparent!important;pointer-events:none!important;
}
.handV5{height:148px!important;display:flex!important;justify-content:center!important;align-items:flex-end!important;pointer-events:auto!important}
.handCardV5{width:112px!important;height:158px!important;margin-left:-27px!important}.handCardV5:first-child{margin-left:0!important}
.handCardV5 .sizaCard{height:158px!important;min-height:0!important}.handCardV5:hover,.handCardV5.selected{transform:translateY(-24px) scale(1.07)!important}
.handLabelV610{display:block!important;position:absolute!important;left:50%!important;top:-13px!important;transform:translateX(-50%)!important;color:#654a2f!important;font:800 7px/1 system-ui,sans-serif!important;letter-spacing:.12em!important}
/* Bottom HUD: resources left, contextual action + end turn right. */
.resourceRailV610{
  position:absolute!important;z-index:34!important;left:12px!important;bottom:8px!important;width:230px!important;height:32px!important;
  display:flex!important;align-items:center!important;gap:5px!important;
}
.resourceRailV610 .mfActionsBadgeV600,.resourceRailV610 .burnAvailableBadgeV600{
  position:static!important;display:flex!important;align-items:center!important;min-height:30px!important;padding:5px 8px!important;
  border:1px solid #594128!important;border-radius:4px!important;background:rgba(29,20,14,.88)!important;color:#e0cfae!important;font-size:7px!important;
}
.creatureCommandDockV610{
  position:absolute!important;z-index:35!important;left:auto!important;right:96px!important;bottom:7px!important;transform:none!important;
  width:255px!important;min-height:42px!important;grid-template-columns:minmax(0,1fr) auto!important;gap:6px!important;padding:5px 7px!important;
  border:1px solid #5a4027!important;border-radius:4px!important;background:rgba(35,23,15,.92)!important;box-shadow:0 8px 20px rgba(0,0,0,.34)!important;
}
.commandEyebrowV610{color:#b99966!important;font-size:6px!important}.commandCopyV610 b{font-size:10px!important;color:#ead9b7!important}.commandEffectV610{font-size:6px!important;color:#bca989!important}
.commandBtnV610{min-height:30px!important;padding:5px 7px!important;border-radius:3px!important;font-size:7px!important}.commandBtnV610.primary{background:linear-gradient(180deg,#c7a05d,#8d6435)!important}
.endTurnV5{
  right:12px!important;bottom:7px!important;width:76px!important;height:42px!important;border-radius:4px!important;
  border:1px solid #5b3f25!important;background:linear-gradient(180deg,#c9a761,#8e6536)!important;color:#1d160f!important;font-size:8px!important;box-shadow:0 6px 16px rgba(0,0,0,.3)!important;
}
.turnStatusV5{display:none!important}.mfActionsBadgeV600{display:block!important}.burnAvailableBadgeV600{display:block!important}
/* Keep modal/card focus functional but centered over the book. */
.cardFocusV5,.fieldCardFocusV610,.defensePanelV600,.equipPanelV600,.manifestInlineV5{z-index:70!important}
.cardFocusScrimV600,.fieldFocusScrimV610{z-index:69!important}
@media(max-width:850px){
  .enemyHalf .arenaMag,.playerHalf .arenaMag,.playerHalf .arenaMagSlot{width:105px!important;height:205px!important}
  .enemyHalf .arenaField{left:52%!important;right:125px!important}.playerHalf .arenaField{left:125px!important;right:52%!important}
  .arenaMiniCard{width:66px!important;height:96px!important}
  .handAreaV5{left:90px!important;right:205px!important}.handCardV5{width:94px!important;height:138px!important;margin-left:-31px!important}.handCardV5 .sizaCard{height:138px!important}
  .creatureCommandDockV610{right:76px!important;width:210px!important}.endTurnV5{width:60px!important}
  .resourceRailV610{width:175px!important}
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
                // The custom child event remains the primary route; polling is only a safety net.
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
        /* startWorldEncounter re-renders the child; re-apply the book composition after that render. */
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
        frame.setAttribute("allowtransparency", "true");
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
        pendingEncounter = {encounter:clone(encounter), mode:mode || "prepare"};
        applyEncounterContext(pendingEncounter.encounter);
        ensureFrame();
        return startInChild(pendingEncounter.encounter, pendingEncounter.mode);
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
        injectEmbedStyle:injectEmbedStyle
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
