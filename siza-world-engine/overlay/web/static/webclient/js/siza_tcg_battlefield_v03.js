(function () {
    "use strict";

    var BUILD = "0.3.2-book-battlefield-rpg-tcg-zones";
    var FRAME_ID = "siza-tcg-embed-frame";
    var STYLE_ID = "siza-book-battlefield-v03";
    var STYLE_HREF = "/static/webclient/css/siza_tcg_battlefield_v03.css?v=0320";
    var DOCK_STYLE_ID = "siza-book-zone-docks-v01";
    var DOCK_STYLE_HREF = "/static/webclient/css/siza_tcg_zone_docks_v01.css?v=0100";
    var SNAPSHOT_ID = "siza-book-zone-snapshot-v01";
    var SNAPSHOT_SRC = "/static/webclient/tcg/siza-mobile-test/book-zone-snapshot-v01.js?v=0100";
    var childObserver = null;
    var parentObserver = null;
    var applyTimer = null;

    function frame() {
        return document.getElementById(FRAME_ID);
    }

    function childWindow() {
        var node = frame();
        try {
            return node && node.contentWindow ? node.contentWindow : null;
        } catch (error) {
            return null;
        }
    }

    function childDocument() {
        var node = frame();
        try {
            return node && node.contentDocument ? node.contentDocument : null;
        } catch (error) {
            return null;
        }
    }

    function ensureLink(doc, id, href) {
        var link = doc.getElementById(id);
        if (!link) {
            link = doc.createElement("link");
            link.id = id;
            link.rel = "stylesheet";
            link.type = "text/css";
        }
        if (link.getAttribute("href") !== href) link.href = href;
        if (doc.head.lastElementChild !== link) doc.head.appendChild(link);
        return link;
    }

    function ensureSnapshotApi() {
        var doc = childDocument();
        var win = childWindow();
        if (!doc || !doc.head || !win) return false;
        if (win.SizaBookZoneSnapshotV01 && typeof win.SizaBookZoneSnapshotV01.get === "function") return true;

        var script = doc.getElementById(SNAPSHOT_ID);
        if (!script) {
            script = doc.createElement("script");
            script.id = SNAPSHOT_ID;
            script.src = SNAPSHOT_SRC;
            script.addEventListener("load", scheduleApply);
            doc.head.appendChild(script);
        }
        return false;
    }

    function makePile(doc, key, label) {
        var node = doc.createElement("div");
        node.className = "bookTcgPile bookTcgPile-" + key;
        node.setAttribute("data-book-zone", key);

        var name = doc.createElement("span");
        name.className = "bookTcgPileLabel";
        name.textContent = label;

        var count = doc.createElement("b");
        count.className = "bookTcgPileCount";
        count.textContent = "0";

        node.appendChild(name);
        node.appendChild(count);
        return node;
    }

    function ensureDock(doc, board, owner) {
        var selector = ".bookTcgZoneDock[data-owner=\"" + owner + "\"]";
        var dock = board.querySelector(selector);
        if (!dock) {
            dock = doc.createElement("div");
            dock.className = "bookTcgZoneDock bookTcgZoneDock-" + owner;
            dock.setAttribute("data-owner", owner);
            dock.appendChild(makePile(doc, "library", "LIB"));
            dock.appendChild(makePile(doc, "graveyard", "GY"));
            dock.appendChild(makePile(doc, "exile", "EX"));
            board.appendChild(dock);
        }
        return dock;
    }

    function updateDock(dock, snapshot) {
        if (!dock || !snapshot) return;
        ["library", "graveyard", "exile"].forEach(function (key) {
            var count = dock.querySelector("[data-book-zone=\"" + key + "\"] .bookTcgPileCount");
            var next = String(Number(snapshot[key] || 0));
            if (count && count.textContent !== next) count.textContent = next;
        });
    }

    function ensureZoneDocks() {
        var doc = childDocument();
        var win = childWindow();
        if (!doc || !win) return false;
        var board = doc.querySelector(".matchBoardV5");
        if (!board) return false;
        if (!ensureSnapshotApi()) return false;

        var snapshot;
        try {
            snapshot = win.SizaBookZoneSnapshotV01.get();
        } catch (error) {
            return false;
        }
        if (!snapshot) return false;

        updateDock(ensureDock(doc, board, "enemy"), snapshot.enemy);
        updateDock(ensureDock(doc, board, "player"), snapshot.player);
        return true;
    }

    function ensureStyle() {
        var doc = childDocument();
        if (!doc || !doc.head) return false;

        var obsolete = doc.getElementById("siza-book-battlefield-v02");
        if (obsolete) obsolete.remove();

        ensureLink(doc, STYLE_ID, STYLE_HREF);
        ensureLink(doc, DOCK_STYLE_ID, DOCK_STYLE_HREF);
        ensureSnapshotApi();
        ensureZoneDocks();
        return true;
    }

    function scheduleApply() {
        if (applyTimer) window.clearTimeout(applyTimer);
        applyTimer = window.setTimeout(function () {
            applyTimer = null;
            ensureStyle();
        }, 0);
    }

    function observeChild() {
        var doc = childDocument();
        if (!doc || !doc.documentElement || typeof MutationObserver !== "function") return false;
        if (childObserver) childObserver.disconnect();
        childObserver = new MutationObserver(scheduleApply);
        childObserver.observe(doc.documentElement, {childList:true, subtree:true});
        scheduleApply();
        return true;
    }

    function attachFrame() {
        var node = frame();
        if (!node) return false;
        if (node.getAttribute("data-book-battlefield-v03") !== BUILD) {
            node.setAttribute("data-book-battlefield-v03", BUILD);
            node.removeAttribute("data-book-battlefield-v02");
            node.addEventListener("load", function () {
                scheduleApply();
                window.setTimeout(observeChild, 0);
            });
        }
        scheduleApply();
        observeChild();
        return true;
    }

    function init() {
        attachFrame();
        if (typeof MutationObserver === "function" && document.documentElement) {
            parentObserver = new MutationObserver(attachFrame);
            parentObserver.observe(document.documentElement, {childList:true, subtree:true});
        }
    }

    window.SizaTcgBattlefieldV03 = Object.freeze({
        BUILD: BUILD,
        STYLE_HREF: STYLE_HREF,
        DOCK_STYLE_HREF: DOCK_STYLE_HREF,
        SNAPSHOT_SRC: SNAPSHOT_SRC,
        apply: ensureStyle,
        attach: attachFrame
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
