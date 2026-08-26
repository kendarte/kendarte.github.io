(function () {
    "use strict";

    var BUILD = "0.2.0-book-battlefield-zones";
    var FRAME_ID = "siza-tcg-embed-frame";
    var STYLE_ID = "siza-book-battlefield-v02";
    var STYLE_HREF = "/static/webclient/css/siza_tcg_battlefield_v02.css?v=0200";
    var childObserver = null;
    var parentObserver = null;
    var applyTimer = null;

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

    function ensureStyle() {
        var doc = childDocument();
        if (!doc || !doc.head) return false;
        var link = doc.getElementById(STYLE_ID);
        if (!link) {
            link = doc.createElement("link");
            link.id = STYLE_ID;
            link.rel = "stylesheet";
            link.type = "text/css";
            link.href = STYLE_HREF;
        }
        /* Move it to the end every time so it wins over the Arena's own responsive overrides. */
        doc.head.appendChild(link);
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
        if (node.getAttribute("data-book-battlefield-v02") !== BUILD) {
            node.setAttribute("data-book-battlefield-v02", BUILD);
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

    window.SizaTcgBattlefieldV02 = Object.freeze({
        BUILD: BUILD,
        STYLE_HREF: STYLE_HREF,
        apply: ensureStyle,
        attach: attachFrame
    });

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
