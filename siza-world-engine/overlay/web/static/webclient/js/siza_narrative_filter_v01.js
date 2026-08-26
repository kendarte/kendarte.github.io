(function () {
    "use strict";

    var MAX_VISIBLE_EVENTS = 3;

    function byId(id) {
        return document.getElementById(id);
    }

    function clean(value) {
        return String(value === undefined || value === null ? "" : value)
            .replace(/\u00a0/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function isDebugNoise(value) {
        var text = clean(value);
        if (!text) {
            return true;
        }
        return /^\[MudInfo\]/i.test(text) ||
            /^You become admin\.?$/i.test(text) ||
            /^admin (?:connected|disconnected)\.?$/i.test(text) ||
            /^TCG bridge:/i.test(text);
    }

    function isSystemOnly(entry) {
        return !!(entry && entry.classList && entry.classList.contains("sizaBookSystem"));
    }

    function isDialogueDuplicate(entry, output, value) {
        if (!entry || !output || entry.getAttribute("data-siza-structured-dialogue") === "true") {
            return false;
        }
        var lastDialogue = clean(output.getAttribute("data-last-dialogue-text"));
        return !!lastDialogue && clean(value) === lastDialogue;
    }

    function trimVisibleEvents(output) {
        if (!output) {
            return;
        }
        var visible = Array.prototype.filter.call(output.children, function (node) {
            return node && node.getAttribute("data-siza-player-visible") === "true";
        });
        while (visible.length > MAX_VISIBLE_EVENTS) {
            var oldest = visible.shift();
            if (oldest && oldest.parentNode === output) {
                output.removeChild(oldest);
            }
        }
    }

    function cleanEntry(entry, output) {
        if (!entry || entry.nodeType !== 1 || entry.getAttribute("data-siza-filtered") === "true") {
            return;
        }
        entry.setAttribute("data-siza-filtered", "true");

        var value = clean(entry.textContent);
        if (isDebugNoise(value) || isSystemOnly(entry) || isDialogueDuplicate(entry, output, value)) {
            if (entry.parentNode === output) {
                output.removeChild(entry);
            }
            return;
        }

        // The book narrative is prose, not a terminal. Strip ANSI/HTML styling
        // inherited from Evennia and keep only the player-visible text.
        entry.textContent = value;
        entry.classList.add("sizaNarrativeEvent");
        entry.setAttribute("data-siza-player-visible", "true");
        if (entry.getAttribute("data-siza-structured-dialogue") !== "true") {
            output.removeAttribute("data-last-dialogue-text");
        }
        trimVisibleEvents(output);
    }

    function cleanExisting(output) {
        Array.prototype.slice.call(output.children).forEach(function (entry) {
            cleanEntry(entry, output);
        });
        trimVisibleEvents(output);
    }

    function init() {
        var output = byId("siza-messagewindow");
        if (!output) {
            return;
        }

        cleanExisting(output);
        if (!window.MutationObserver) {
            return;
        }

        new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                Array.prototype.forEach.call(mutation.addedNodes || [], function (node) {
                    cleanEntry(node, output);
                });
            });
        }).observe(output, {childList: true});
    }

    window.SizaNarrativeFilterV01 = Object.freeze({
        clean: clean,
        isDebugNoise: isDebugNoise,
        isDialogueDuplicate: isDialogueDuplicate
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
