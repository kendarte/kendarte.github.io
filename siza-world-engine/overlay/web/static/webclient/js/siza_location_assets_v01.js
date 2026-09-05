(function () {
    "use strict";

    function clean(value) {
        return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    }

    function applyRoomAsset(asset) {
        var shell = window.SizaBookShellV02;
        if (!shell || typeof shell.setSceneVisual !== "function") {
            return false;
        }
        asset = asset || {};
        shell.setSceneVisual({
            url: clean(asset.src || asset.url),
            label: clean(asset.alt || asset.label),
            position: clean(asset.position) || "center center",
            fit: clean(asset.fit) || "cover"
        });
        return true;
    }

    window.SizaLocationAssetsV01 = Object.freeze({
        applyRoomAsset: applyRoomAsset
    });
})();
