(function () {
    "use strict";

    var STORAGE_KEY = "siza.world.login.v1";
    var authPending = false;
    var authenticated = false;
    var authTimer = null;
    var pendingCredentials = null;
    var logoutRequested = false;

    function byId(id) {
        return document.getElementById(id);
    }

    function packetText(value) {
        var holder = document.createElement("div");
        holder.innerHTML = String(value === undefined || value === null ? "" : value);
        return String(holder.textContent || holder.innerText || "").replace(/\s+/g, " ").trim();
    }

    function readSaved() {
        try {
            var parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
            if (parsed && parsed.username && parsed.password) {
                return {username: String(parsed.username), password: String(parsed.password)};
            }
        } catch (error) {
            window.localStorage.removeItem(STORAGE_KEY);
        }
        return null;
    }

    function forgetSaved() {
        try {
            window.localStorage.removeItem(STORAGE_KEY);
        } catch (error) {
            // The session UI still resets even if storage is unavailable.
        }
    }

    function saveCredentials(credentials) {
        var remember = byId("siza-login-remember");
        try {
            if (remember && remember.checked) {
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(credentials));
            } else {
                window.localStorage.removeItem(STORAGE_KEY);
            }
        } catch (error) {
            setStatus("El navegador no permitió recordar el acceso.", "error");
        }
    }

    function setStatus(message, kind) {
        var status = byId("siza-login-status");
        if (!status) {
            return;
        }
        status.textContent = String(message || "");
        status.setAttribute("data-kind", kind || "info");
    }

    function setBusy(busy) {
        var submit = byId("siza-login-submit");
        var create = byId("siza-login-create");
        var username = byId("siza-login-username");
        var password = byId("siza-login-password");
        [submit, create, username, password].forEach(function (element) {
            if (element) {
                element.disabled = !!busy;
            }
        });
        if (submit) {
            submit.textContent = busy ? "Entrando…" : "Entrar al mundo";
        }
    }

    function setPlayerName(name) {
        var cleanName = String(name || "").trim();
        var displayName = cleanName || "Sin personaje";
        var initial = cleanName ? cleanName.charAt(0).toUpperCase() : "?";
        var playerName = byId("siza-player-name");
        var portraitName = byId("siza-player-portrait-name");
        var portraitInitial = byId("siza-player-portrait-initial");
        var portrait = byId("siza-player-portrait");

        if (playerName) {
            playerName.textContent = displayName;
        }
        if (portraitName) {
            portraitName.textContent = displayName;
        }
        if (portraitInitial) {
            portraitInitial.textContent = initial;
        }
        if (portrait) {
            portrait.setAttribute("data-empty", cleanName ? "false" : "true");
        }
    }

    function setMenuOpen(open) {
        var menu = byId("siza-session-menu");
        var toggle = byId("siza-session-menu-toggle");
        var panel = byId("siza-session-menu-panel");
        if (!menu || !toggle || !panel) {
            return;
        }
        menu.setAttribute("data-open", open ? "true" : "false");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        panel.hidden = !open;
    }

    function showGate(message, kind) {
        var gate = byId("siza-login-gate");
        var root = byId("siza-book-client");
        if (gate) {
            gate.setAttribute("data-state", "visible");
        }
        if (root) {
            root.setAttribute("data-authenticated", "false");
        }
        setBusy(false);
        setMenuOpen(false);
        setStatus(message || "Introduce tu acceso para continuar.", kind || "info");
    }

    function completeLogin(characterName) {
        var gate = byId("siza-login-gate");
        var output = byId("siza-messagewindow");
        var root = byId("siza-book-client");

        authenticated = true;
        authPending = false;
        logoutRequested = false;
        clearTimeout(authTimer);
        setBusy(false);
        setStatus("Acceso confirmado.", "success");

        if (pendingCredentials) {
            saveCredentials(pendingCredentials);
            setPlayerName(characterName || pendingCredentials.username);
        } else if (characterName) {
            setPlayerName(characterName);
        }
        if (output) {
            output.innerHTML = "";
        }
        if (root) {
            root.setAttribute("data-authenticated", "true");
        }
        window.setTimeout(function () {
            if (gate) {
                gate.setAttribute("data-state", "hidden");
            }
            if (window.Evennia && Evennia.isConnected()) {
                Evennia.msg("text", ["look"], {});
            }
        }, 180);
    }

    function resetSessionUi(message, kind) {
        var output = byId("siza-messagewindow");
        var username = byId("siza-login-username");
        var password = byId("siza-login-password");

        authenticated = false;
        authPending = false;
        pendingCredentials = null;
        clearTimeout(authTimer);
        setBusy(false);
        setMenuOpen(false);
        setPlayerName("");
        if (output) {
            output.innerHTML = "";
        }
        if (password) {
            password.value = "";
        }
        showGate(message || "Sesión cerrada. Introduce tu acceso para continuar.", kind || "info");
        window.setTimeout(function () {
            (username || password || {}).focus && (username || password).focus();
        }, 50);
    }

    function performLogout() {
        logoutRequested = true;
        forgetSaved();
        resetSessionUi("Sesión cerrada. Acceso recordado borrado en este navegador.", "info");
        if (window.Evennia && Evennia.isConnected()) {
            try {
                Evennia.msg("text", ["quit"], {});
            } catch (error) {
                // The visible login gate is already restored.
            }
        }
    }

    function isLoginBanner(text) {
        return /welcome to runtime|existing account|connect <username>|create <username>|need to create an account/i.test(text);
    }

    function isLoginFailure(text) {
        return /incorrect password|authentication failed|does not exist|no account|unknown account|already exists|name is already taken|usage:\s*(connect|create)|could not connect/i.test(text);
    }

    function looksLikeWorld(text) {
        return /\(#\d+\)|you become|logged in|pescader[ií]a|world engine|limbo|darkhaven/i.test(text) && !isLoginBanner(text);
    }

    function quoteUsername(value) {
        var username = String(value || "").trim();
        return /\s/.test(username) ? '"' + username.replace(/"/g, "") + '"' : username;
    }

    function submitCredentials(mode, supplied) {
        var usernameField = byId("siza-login-username");
        var passwordField = byId("siza-login-password");
        var credentials = supplied || {
            username: usernameField ? usernameField.value.trim() : "",
            password: passwordField ? passwordField.value : ""
        };

        if (!credentials.username || !credentials.password) {
            showGate("Escribe el personaje y la contraseña.", "error");
            var focusTarget = credentials.username ? passwordField : usernameField;
            if (focusTarget) {
                focusTarget.focus();
            }
            return;
        }
        if (!window.Evennia || !Evennia.isConnected()) {
            showGate("El World Engine todavía está conectando.", "error");
            return;
        }

        pendingCredentials = credentials;
        authPending = true;
        logoutRequested = false;
        clearTimeout(authTimer);
        setBusy(true);
        setStatus(mode === "create" ? "Creando tu acceso…" : "Recuperando tu personaje…", "info");
        Evennia.msg("text", [mode + " " + quoteUsername(credentials.username) + " " + credentials.password], {});
        authTimer = window.setTimeout(function () {
            if (!authPending || authenticated) {
                return;
            }
            authPending = false;
            pendingCredentials = null;
            showGate("El servidor no confirmó el acceso. Revisa la cuenta o vuelve a intentarlo.", "error");
        }, 10000);
    }

    function submitLocalAccess() {
        showGate("Auto-login local desactivado. Use usuario y contraseña.", "info");
    }

    function onLocalReady(args) {
        var packet = args && args.length && args[0] && typeof args[0] === "object" ? args[0] : {};
        var status = String(packet.status || "");
        if (status === "READY") {
            completeLogin(packet.character || packet.puppet || packet.account || "");
            return;
        }
        authPending = false;
        clearTimeout(authTimer);
        showGate("Acceso local automático desactivado. Use el login normal.", "info");
    }

    function onLoggedIn() {
        setStatus("Cuenta abierta. Cargando personaje…", "info");
        if (authPending && !authenticated) {
            completeLogin(pendingCredentials && pendingCredentials.username);
        }
    }

    function forwardText(args, kwargs) {
        if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.receiveText === "function") {
            window.SizaWorldBookClient.receiveText(args, kwargs);
        }
    }

    function onServerText(args, kwargs) {
        var text = packetText(args && args.length ? args[0] : "");
        if (!text) {
            return;
        }
        if (authenticated) {
            forwardText(args, kwargs);
            return;
        }
        if (isLoginFailure(text)) {
            authPending = false;
            pendingCredentials = null;
            forgetSaved();
            showGate("No se pudo validar ese acceso. Revisa los datos e inténtalo otra vez.", "error");
            return;
        }
        if (looksLikeWorld(text)) {
            completeLogin(pendingCredentials && pendingCredentials.username);
            if (/\(#\d+\)/.test(text)) {
                forwardText(args, kwargs);
            }
            return;
        }
        if (isLoginBanner(text) && !authPending) {
            showGate("Conexión lista. Introduce tu personaje y contraseña.", "info");
        }
    }

    function onConnectionOpen() {
        if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.connectionOpen === "function") {
            window.SizaWorldBookClient.connectionOpen();
        }
        if (!authenticated && !authPending) {
            showGate("Conexión lista. Introduce tu personaje y contraseña.", "info");
        }
    }

    function setupSessionMenu() {
        var menu = byId("siza-session-menu");
        var toggle = byId("siza-session-menu-toggle");
        var logout = byId("siza-logout-button");
        var clear = byId("siza-login-clear");

        if (toggle) {
            toggle.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                setMenuOpen(!(menu && menu.getAttribute("data-open") === "true"));
            });
        }
        if (logout) {
            logout.addEventListener("click", function (event) {
                event.preventDefault();
                performLogout();
            });
        }
        if (clear) {
            clear.addEventListener("click", function (event) {
                event.preventDefault();
                forgetSaved();
                setStatus("Acceso recordado borrado.", "info");
                setMenuOpen(false);
            });
        }
        document.addEventListener("click", function (event) {
            if (menu && !menu.contains(event.target)) {
                setMenuOpen(false);
            }
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                setMenuOpen(false);
            }
        });
    }

    function init() {
        var form = byId("siza-login-form");
        var create = byId("siza-login-create");
        var username = byId("siza-login-username");
        var password = byId("siza-login-password");
        var saved = readSaved();

        setupSessionMenu();
        setPlayerName("");
        if (saved) {
            if (username) {
                username.value = saved.username;
            }
            if (password) {
                password.value = saved.password;
            }
        }
        if (form) {
            form.addEventListener("submit", function (event) {
                event.preventDefault();
                submitCredentials("connect");
            });
        }
        if (create) {
            create.addEventListener("click", function () {
                submitCredentials("create");
            });
        }
        if (!window.Evennia) {
            showGate("El cliente del World Engine no está disponible.", "error");
            return;
        }

        Evennia.emitter.on("text", onServerText);
        Evennia.emitter.on("logged_in", onLoggedIn);
        Evennia.emitter.on("siza_local_ready", onLocalReady);
        Evennia.emitter.on("connection_open", onConnectionOpen);
        Evennia.emitter.on("connection_close", function () {
            authenticated = false;
            if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.connectionClose === "function") {
                window.SizaWorldBookClient.connectionClose();
            }
            showGate(logoutRequested ? "Sesión cerrada." : "La conexión se cerró. Reconectando…", logoutRequested ? "info" : "error");
        });
        Evennia.emitter.on("connection_error", function () {
            authenticated = false;
            if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.connectionError === "function") {
                window.SizaWorldBookClient.connectionError();
            }
            showGate("No se pudo conectar con el World Engine.", "error");
        });

        if (Evennia.isConnected()) {
            onConnectionOpen();
        }
        window.setTimeout(function () {
            ((saved ? password : username) || username || password || {}).focus && ((saved ? password : username) || username || password).focus();
        }, 50);
    }

    window.SizaLoginGate = Object.freeze({
        show: showGate,
        logout: performLogout,
        local: submitLocalAccess
    });

    $(document).ready(init);
})();
