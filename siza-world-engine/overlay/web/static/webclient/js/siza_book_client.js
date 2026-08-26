(function () {
    "use strict";

    var MODES = ["EXPLORATION", "DIALOGUE", "COMBAT"];
    var history = [];
    var historyIndex = 0;

    function byId(id) {
        return document.getElementById(id);
    }

    function safeClass(value) {
        return String(value || "out").replace(/[^a-zA-Z0-9 _-]/g, "");
    }

    function scrollOutput() {
        var output = byId("siza-messagewindow");
        if (output) {
            output.scrollTop = output.scrollHeight;
        }
    }

    function appendHtml(html, cls) {
        var output = byId("siza-messagewindow");
        if (!output || html === null || html === undefined) {
            return;
        }
        var entry = document.createElement("div");
        entry.className = "sizaBookLine " + safeClass(cls);
        entry.innerHTML = String(html);
        output.appendChild(entry);
        scrollOutput();
    }

    function appendSystem(text, kind) {
        var output = byId("siza-messagewindow");
        if (!output) {
            return;
        }
        var entry = document.createElement("div");
        entry.className = "sizaBookLine sizaBookSystem " + safeClass(kind || "");
        entry.textContent = String(text || "");
        output.appendChild(entry);
        scrollOutput();
    }

    function setConnection(label, state) {
        var el = byId("siza-connection-label");
        var root = byId("siza-book-client");
        if (el) {
            el.textContent = label;
        }
        if (root) {
            root.setAttribute("data-connection", state || "unknown");
        }
    }

    function setMode(mode) {
        var normalized = String(mode || "EXPLORATION").toUpperCase();
        if (MODES.indexOf(normalized) === -1) {
            normalized = "EXPLORATION";
        }
        var root = byId("siza-book-client");
        var label = byId("siza-mode-label");
        if (root) {
            root.setAttribute("data-mode", normalized);
        }
        if (label) {
            label.textContent = normalized === "EXPLORATION" ? "EXPLORACIÓN" :
                normalized === "DIALOGUE" ? "DIÁLOGO" : "COMBATE";
        }
        return normalized;
    }

    function setContext(context) {
        context = context || {};
        if (context.mode) {
            setMode(context.mode);
        }
        var values = {
            "siza-location-label": context.location,
            "siza-context-label": context.context,
            "siza-scene-title": context.sceneTitle,
            "siza-scene-kicker": context.sceneKicker,
            "siza-player-name": context.playerName,
            "siza-player-state": context.playerState
        };
        Object.keys(values).forEach(function (id) {
            var value = values[id];
            var el = byId(id);
            if (el && value !== undefined && value !== null && value !== "") {
                el.textContent = String(value);
            }
        });
    }

    function onText(args, kwargs) {
        if (args && args.length) {
            appendHtml(args[0], kwargs && kwargs.cls);
        }
    }

    function onPrompt(args) {
        var prompt = byId("siza-prompt-label");
        if (prompt && args && args.length && args[0]) {
            prompt.innerHTML = String(args[0]);
        }
    }

    function onUnknown(cmdname, args, kwargs) {
        if ((cmdname === "html" || cmdname === "text") && args && args.length) {
            appendHtml(args[0], kwargs && kwargs.cls);
        }
    }

    function onConnectionOpen() {
        setConnection("Conectado", "open");
    }

    function onConnectionClose() {
        setConnection("Desconectado", "closed");
        appendSystem("La conexión con el World Engine se cerró.", "warning");
    }

    function onConnectionError() {
        setConnection("Error de conexión", "error");
        appendSystem("No se pudo mantener la conexión con el World Engine.", "error");
    }

    function sendText(raw) {
        var value = String(raw === undefined || raw === null ? "" : raw).trim();
        if (!value) {
            return false;
        }
        if (!window.Evennia || !Evennia.isConnected()) {
            appendSystem("Todavía no hay conexión con el World Engine.", "warning");
            return false;
        }
        history.push(value);
        if (history.length > 100) {
            history.shift();
        }
        historyIndex = history.length;
        Evennia.msg("text", [value], {});
        return true;
    }

    function submitInput() {
        var field = byId("siza-inputfield");
        if (!field) {
            return;
        }
        if (sendText(field.value)) {
            field.value = "";
        }
        field.focus();
    }

    function browseHistory(direction) {
        var field = byId("siza-inputfield");
        if (!field || !history.length) {
            return;
        }
        historyIndex = Math.max(0, Math.min(history.length, historyIndex + direction));
        field.value = historyIndex === history.length ? "" : history[historyIndex];
        requestAnimationFrame(function () {
            field.selectionStart = field.selectionEnd = field.value.length;
        });
    }

    function bindInput() {
        var field = byId("siza-inputfield");
        var button = byId("siza-inputsend");
        if (button) {
            button.addEventListener("click", submitInput);
        }
        if (field) {
            field.addEventListener("keydown", function (event) {
                if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submitInput();
                } else if (event.key === "ArrowUp" && !event.shiftKey) {
                    event.preventDefault();
                    browseHistory(-1);
                } else if (event.key === "ArrowDown" && !event.shiftKey) {
                    event.preventDefault();
                    browseHistory(1);
                }
            });
            field.focus();
        }
    }

    function init() {
        if (!window.Evennia) {
            setConnection("Cliente no disponible", "error");
            return;
        }

        Evennia.init();
        Evennia.emitter.on("text", onText);
        Evennia.emitter.on("prompt", onPrompt);
        Evennia.emitter.on("connection_open", onConnectionOpen);
        Evennia.emitter.on("connection_close", onConnectionClose);
        Evennia.emitter.on("connection_error", onConnectionError);
        Evennia.emitter.on("default", onUnknown);

        bindInput();
        setMode("EXPLORATION");
        setConnection(Evennia.isConnected() ? "Conectado" : "Conectando…", Evennia.isConnected() ? "open" : "connecting");
    }

    window.SizaWorldBookClient = Object.freeze({
        appendHtml: appendHtml,
        sendText: sendText,
        setContext: setContext,
        setMode: setMode
    });

    $(document).ready(init);
})();
