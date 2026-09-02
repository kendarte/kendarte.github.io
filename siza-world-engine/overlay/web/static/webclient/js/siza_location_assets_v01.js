(function () {
    "use strict";

    var FISHERY_IMAGE = "/static/webclient/images/pescaderia_darsena_v02.png?v=20260902";

    function normalize(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9]+/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function imageForLocation(value) {
        var key = normalize(value);
        if (
            key === "dockside fishery" ||
            key === "pescaderia de darsena" ||
            key === "pescaderia de darsenas"
        ) {
            return FISHERY_IMAGE;
        }
        return "";
    }

    function apply() {
        var location = document.getElementById("siza-location-label");
        var media = document.getElementById("siza-scene-visual-media");
        if (!location || !window.SizaBookShellV02) {
            return false;
        }
        var label = String(location.textContent || "").trim();
        var url = imageForLocation(label);
        window.SizaBookShellV02.setSceneVisual({url: url, label: label});
        if (media) {
            media.style.backgroundPosition = url ? "center 38%" : "";
        }
        return !!url;
    }

    function init() {
        apply();
        var location = document.getElementById("siza-location-label");
        if (location && window.MutationObserver) {
            new MutationObserver(apply).observe(location, {
                childList: true,
                characterData: true,
                subtree: true
            });
        }
    }

    window.SizaLocationAssetsV01 = Object.freeze({
        apply: apply,
        imageForLocation: imageForLocation
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
