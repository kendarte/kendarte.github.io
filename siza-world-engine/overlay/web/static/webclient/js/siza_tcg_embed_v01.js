(function () {
    "use strict";

    var BUILD = "0.1.0-local-arena-embed";
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
        if (child.document.getElementById("siza-world-embed-style")) return true;
        var style = child.document.createElement("style");
        style.id = "siza-world-embed-style";
        style.textContent = [
            "html,body,#app{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;overflow:hidden!important;background:#07111b!important;}",
            "#bootFallback{display:none!important;}",
            ".sidebar,.topbar,.arenaNavToggleV600,.arenaNavPanelV600,.arenaNavVeilV600,.bookHeaderV01,.bookNarrativeV01{display:none!important;}",
            ".shell{display:block!important;width:100%!important;height:100%!important;min-height:0!important;}",
            ".main{display:block!important;grid-column:auto!important;width:100%!important;height:100%!important;min-height:0!important;padding:0!important;margin:0!important;}",
            ".bookShellV01,.bookBodyV01,.bookSceneV01{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;border:0!important;}",
            ".bookBodyV01{display:block!important;}",
            ".bookSceneV01{overflow:auto!important;}",
            ".matchShell.v05{min-height:100%!important;border-radius:0!important;}",
            ".matchHeader{margin-top:0!important;}"
        ].join("\n");
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
        pendingEncounter = {encounter:clone(encounter), mode:mode || "prepare"};
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
        forwardResult:forwardResult
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
