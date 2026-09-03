(function () {
    "use strict";

    var STORAGE_KEY = "siza.world.login.v1";
    var authPending = false;
    var authenticated = false;
    var savedLoginTimer = null;
    var authTimer = null;
    var pendingCredentials = null;

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

    function showGate(message, kind) {
        var gate = byId("siza-login-gate");
        if (gate) {
            gate.setAttribute("data-state", "visible");
        }
        setBusy(false);
        setStatus(message || "Introduce tu acceso para continuar.", kind || "info");
    }

    function completeLogin() {
        var gate = byId("siza-login-gate");
        var output = byId("siza-messagewindow");
        var root = byId("siza-book-client");
        var playerName = byId("siza-player-name");

        authenticated = true;
        authPending = false;
        clearTimeout(savedLoginTimer);
        clearTimeout(authTimer);
        setBusy(false);
        setStatus("Acceso confirmado.", "success");

        if (pendingCredentials) {
            saveCredentials(pendingCredentials);
            if (playerName) {
                playerName.textContent = pendingCredentials.username;
            }
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

    function isLoginBanner(text) {
        return /welcome to runtime|existing account|connect <username>|create <username>|need to create an account/i.test(text);
    }

    function isLoginFailure(text) {
        return /incorrect password|authentication failed|does not exist|no account|unknown account|already exists|name is already taken|usage:\s*(connect|create)|could not connect/i.test(text);
    }

    function looksLikeWorld(text) {
        return /\(#\d+\)|you become|logged in|pescader[ií]a|world engine|limbo/i.test(text) && !isLoginBanner(text);
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
            (credentials.username ? passwordField : usernameField).focus();
            return;
        }
        if (!window.Evennia || !Evennia.isConnected()) {
            showGate("El World Engine todavía está conectando.", "error");
            return;
        }

        pendingCredentials = credentials;
        authPending = true;
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

    function onLoggedIn() {
        if (!authenticated) {
            completeLogin();
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
            try {
                window.localStorage.removeItem(STORAGE_KEY);
            } catch (error) {
                // The visual error remains sufficient when storage is unavailable.
            }
            showGate("No se pudo validar ese acceso. Revisa los datos e inténtalo otra vez.", "error");
            return;
        }
        if (looksLikeWorld(text)) {
            completeLogin();
            if (/\(#\d+\)/.test(text)) {
                forwardText(args, kwargs);
            }
            return;
        }
        if (isLoginBanner(text)) {
            var saved = readSaved();
            if (saved && !authPending) {
                submitCredentials("connect", saved);
            } else if (!authPending) {
                showGate("Introduce tu acceso para continuar.", "info");
            }
        }
    }

    function onConnectionOpen() {
        if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.connectionOpen === "function") {
            window.SizaWorldBookClient.connectionOpen();
        }
        var saved = readSaved();
        setStatus(saved ? "Recuperando acceso guardado…" : "Conexión lista.", "info");
        clearTimeout(savedLoginTimer);
        savedLoginTimer = window.setTimeout(function () {
            if (authenticated || authPending) {
                return;
            }
            if (saved) {
                submitCredentials("connect", saved);
            } else {
                showGate("Introduce tu acceso para continuar.", "info");
            }
        }, 1200);
    }

    function init() {
        var form = byId("siza-login-form");
        var create = byId("siza-login-create");
        var username = byId("siza-login-username");
        var password = byId("siza-login-password");
        var saved = readSaved();

        if (saved) {
            username.value = saved.username;
            password.value = saved.password;
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
        Evennia.emitter.on("connection_open", onConnectionOpen);
        Evennia.emitter.on("connection_close", function () {
            authenticated = false;
            if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.connectionClose === "function") {
                window.SizaWorldBookClient.connectionClose();
            }
            showGate("La conexión se cerró. Reconectando…", "error");
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
            (saved ? password : username).focus();
        }, 50);
    }

    window.SizaLoginGate = Object.freeze({
        show: showGate
    });

    $(document).ready(init);
})();
