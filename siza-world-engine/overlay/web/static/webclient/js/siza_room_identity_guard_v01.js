(function () {
    "use strict";

    var RAW_ROOMS = {
        "Embarcadero de Campana": true,
        "Patio de Mineral": true,
        "Plaza de Recepcion": true,
        "Calle de Servicio": true,
        "Casa de Remedio": true,
        "Cantina de Turno": true,
        "Pescaderia de Darsena": true,
        "Trastienda de la Pescaderia": true,
        "Muelles de Descenso": true
    };

    function byId(id) { return document.getElementById(id); }
    function clean(value) { return String(value == null ? "" : value).replace(/\s+/g, " ").trim(); }

    function syncRawRoomIdentity() {
        var location = byId("siza-location-label");
        var description = byId("siza-scene-description");
        if (!location) return false;

        var visible = clean(location.textContent);
        if (!RAW_ROOMS[visible]) return false;

        var previous = clean(location.getAttribute("data-raw-room"));
        if (previous === visible) return false;

        location.setAttribute("data-raw-room", visible);
        if (description) {
            description.setAttribute("data-raw-description", clean(description.textContent));
        }
        return true;
    }

    function init() {
        var location = byId("siza-location-label");
        if (!location) return;

        syncRawRoomIdentity();
        if (window.MutationObserver) {
            new MutationObserver(syncRawRoomIdentity).observe(location, {
                childList: true,
                characterData: true,
                subtree: true
            });
        }
    }

    window.SizaRoomIdentityGuardV01 = Object.freeze({
        sync: syncRawRoomIdentity
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
