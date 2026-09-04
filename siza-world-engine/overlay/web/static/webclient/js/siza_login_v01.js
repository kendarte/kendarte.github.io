(function () {
    "use strict";

    var STORAGE_KEY = "siza.world.account.v2";
    var authenticated = false;
    var awaitingLogin = false;
    var registrationPending = false;
    var authTimer = null;
    var currentAccount = "";
    var pendingAccount = "";
    var logoutRequested = false;

    function byId(id) {
        return document.getElementById(id);
    }

    function packetText(value) {
        var holder = document.createElement("div");
        holder.innerHTML = String(value === undefined || value === null ? "" : value);
        return String(holder.textContent || holder.innerText || "").replace(/\s+/g, " ").trim();
    }

    function readRememberedAccount() {
        try {
            var saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
            if (saved && typeof saved.account === "string" && saved.account.trim()) {
                return saved.account.trim();
            }
            /* Remove the old format because it contained a password. */
            window.localStorage.removeItem("siza.world.login.v1");
        } catch (error) {
            window.localStorage.removeItem(STORAGE_KEY);
        }
        return "";
    }

    function rememberAccount(account) {
        var remember = byId("siza-login-remember");
        try {
            if (remember && remember.checked) {
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify({account: String(account || "")}));
            } else {
                window.localStorage.removeItem(STORAGE_KEY);
            }
        } catch (error) {
            setStatus("El navegador no permitió recordar la cuenta.", "error");
        }
    }

    function forgetSavedAccount() {
        try {
            window.localStorage.removeItem(STORAGE_KEY);
            window.localStorage.removeItem("siza.world.login.v1");
        } catch (error) {
            /* The visible session flow still works without local storage. */
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
        var panel = byId("siza-login-panel");
        var submit = byId("siza-login-submit");
        var creatorSubmit = byId("siza-creator-submit");
        if (panel) {
            Array.prototype.forEach.call(panel.querySelectorAll("button, input, select"), function (element) {
                element.disabled = !!busy;
            });
        }
        if (submit) {
            submit.textContent = busy ? "Conectando…" : "Entrar al mundo";
        }
        if (creatorSubmit) {
            creatorSubmit.textContent = busy ? "Creando…" : "Crear y entrar";
        }
    }

    function setPlayerName(name, account) {
        var cleanName = String(name || "").trim();
        var displayName = cleanName || "Sin personaje";
        var initial = cleanName ? cleanName.charAt(0).toUpperCase() : "?";
        var state = byId("siza-player-state");
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
        if (state) {
            state.textContent = cleanName ? "Cuenta: " + String(account || currentAccount || "") : "Persistent character";
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

    function showStep(step) {
        var panel = byId("siza-login-panel");
        ["login", "characters", "creator"].forEach(function (name) {
            var section = byId("siza-login-step-" + name);
            if (section) {
                section.hidden = name !== step;
            }
        });
        if (panel) {
            panel.setAttribute("data-step", step);
        }
        if (step === "creator") {
            var hasAccount = !!currentAccount;
            var accountFields = byId("siza-creator-account-fields");
            var accountLabel = byId("siza-creator-account-label");
            var accountInput = byId("siza-creator-account");
            var creatorTitle = byId("siza-creator-title");
            var creatorCopy = byId("siza-creator-copy");
            if (accountFields) {
                accountFields.hidden = hasAccount;
            }
            if (accountLabel) {
                accountLabel.textContent = hasAccount ? currentAccount : "";
            }
            if (accountInput && hasAccount) {
                accountInput.value = currentAccount;
            }
            if (creatorTitle) {
                creatorTitle.textContent = hasAccount ? "Crear personaje" : "Crear cuenta y personaje";
            }
            if (creatorCopy) {
                creatorCopy.textContent = hasAccount
                    ? "Este personaje se añadirá a la cuenta " + currentAccount + "."
                    : "Tu cuenta y tu primer personaje se crean en un único paso.";
            }
        }
    }

    function showGate(message, kind, step) {
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
        showStep(step || "login");
        setStatus(message || "Introduce tu cuenta para continuar.", kind || "info");
    }

    function completeLogin(characterName, accountName) {
        var gate = byId("siza-login-gate");
        var output = byId("siza-messagewindow");
        var root = byId("siza-book-client");

        authenticated = true;
        awaitingLogin = false;
        registrationPending = false;
        logoutRequested = false;
        currentAccount = String(accountName || currentAccount || pendingAccount || "");
        clearTimeout(authTimer);
        setBusy(false);
        setStatus("Acceso confirmado.", "success");
        rememberAccount(currentAccount);
        setPlayerName(characterName, currentAccount);

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

    function resetToLogin(message, kind) {
        var output = byId("siza-messagewindow");
        var password = byId("siza-login-password");

        authenticated = false;
        awaitingLogin = false;
        registrationPending = false;
        pendingAccount = "";
        currentAccount = "";
        clearTimeout(authTimer);
        if (output) {
            output.innerHTML = "";
        }
        if (password) {
            password.value = "";
        }
        setPlayerName("", "");
        showGate(message || "Introduce tu cuenta para continuar.", kind || "info", "login");
    }

    function quote(value) {
        return String(value || "").trim().replace(/\s+/g, "");
    }

    function encodePayload(payload) {
        var json = JSON.stringify(payload);
        var utf8 = unescape(encodeURIComponent(json));
        return btoa(utf8).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    }

    function startTimer(message) {
        clearTimeout(authTimer);
        authTimer = window.setTimeout(function () {
            if (!authenticated) {
                awaitingLogin = false;
                registrationPending = false;
                setBusy(false);
                setStatus(message, "error");
            }
        }, 12000);
    }

    function submitLogin() {
        var accountInput = byId("siza-login-username");
        var passwordInput = byId("siza-login-password");
        var account = accountInput ? accountInput.value.trim() : "";
        var password = passwordInput ? passwordInput.value : "";
        if (!account || !password) {
            setStatus("Escribe la cuenta y la contraseña.", "error");
            (account ? passwordInput : accountInput).focus();
            return;
        }
        if (!window.Evennia || !Evennia.isConnected()) {
            setStatus("El World Engine todavía está conectando.", "error");
            return;
        }
        pendingAccount = account;
        awaitingLogin = true;
        registrationPending = false;
        setBusy(true);
        setStatus("Validando cuenta…", "info");
        Evennia.msg("text", ["connect " + quote(account) + " " + password], {});
        /*
         * Evennia authenticates the socket before the browser's optional
         * logged_in notification. Query the authenticated account directly
         * so this flow also works with webclient builds that omit it.
         */
        [350, 900, 1800].forEach(function (delay) {
            window.setTimeout(function () {
                if (awaitingLogin && !authenticated) {
                    requestCharacters();
                }
            }, delay);
        });
        startTimer("El servidor no confirmó el login. Inténtalo otra vez.");
    }

    function requestCharacters() {
        if (!window.Evennia || !Evennia.isConnected()) {
            resetToLogin("La conexión se perdió antes de elegir personaje.", "error");
            return;
        }
        setStatus("Cuenta validada. Cargando personajes…", "info");
        Evennia.msg("text", ["siza-auth-characters"], {});
    }

    function playCharacter(characterId) {
        setBusy(true);
        setStatus("Abriendo personaje…", "info");
        Evennia.msg("text", ["siza-auth-play " + String(characterId)], {});
        startTimer("El personaje no terminó de cargar. Vuelve a intentarlo.");
    }

    function renderCharacters(packet) {
        var list = byId("siza-character-list");
        var accountLabel = byId("siza-character-account");
        var create = byId("siza-character-create");
        var characters = Array.isArray(packet.characters) ? packet.characters : [];
        currentAccount = String(packet.account || pendingAccount || currentAccount || "");
        if (accountLabel) {
            accountLabel.textContent = currentAccount;
        }
        if (list) {
            list.innerHTML = "";
            characters.forEach(function (character) {
                var button = document.createElement("button");
                var title = document.createElement("strong");
                var detail = document.createElement("span");
                button.type = "button";
                button.className = "sizaCharacterChoice";
                title.textContent = String(character.name || "Personaje");
                detail.textContent = character.location ? "Ubicación: " + String(character.location) : "Entrar al mundo";
                button.appendChild(title);
                button.appendChild(detail);
                button.addEventListener("click", function () {
                    playCharacter(character.id);
                });
                list.appendChild(button);
            });
        }
        if (!characters.length) {
            showStep("creator");
            setStatus("Esta cuenta aún no tiene personaje. Crea el primero.", "info");
            return;
        }
        if (create) {
            create.hidden = packet.slots === 0;
        }
        showStep("characters");
        setBusy(false);
        setStatus("Elige el personaje con el que quieres entrar.", "info");
    }

    function submitCreator() {
        var characterInput = byId("siza-creator-character");
        var originInput = byId("siza-creator-origin");
        var accountInput = byId("siza-creator-account");
        var passwordInput = byId("siza-creator-password");
        var confirmInput = byId("siza-creator-password-confirm");
        var character = characterInput ? characterInput.value.trim() : "";
        var origin = originInput ? originInput.value.trim() : "";
        var creatingAccount = !currentAccount;
        var account = creatingAccount && accountInput ? accountInput.value.trim() : currentAccount;
        var password = creatingAccount && passwordInput ? passwordInput.value : "";

        if (!character) {
            setStatus("Ponle un nombre a tu personaje.", "error");
            characterInput.focus();
            return;
        }
        if (creatingAccount && (!account || !password)) {
            setStatus("Escribe la cuenta y la contraseña.", "error");
            (account ? passwordInput : accountInput).focus();
            return;
        }
        if (creatingAccount && confirmInput && password !== confirmInput.value) {
            setStatus("Las contraseñas no coinciden.", "error");
            confirmInput.focus();
            return;
        }
        if (!window.Evennia || !Evennia.isConnected()) {
            setStatus("El World Engine todavía está conectando.", "error");
            return;
        }
        setBusy(true);
        setStatus(creatingAccount ? "Creando cuenta y personaje…" : "Creando personaje…", "info");
        if (creatingAccount) {
            pendingAccount = account;
            registrationPending = true;
            Evennia.msg("text", ["siza-auth-register " + encodePayload({
                account: account,
                password: password,
                character: character,
                origin: origin
            })], {});
        } else {
            Evennia.msg("text", ["siza-auth-create-character " + encodePayload({
                character: character,
                origin: origin
            })], {});
        }
        startTimer("No se pudo completar el creador. Revisa los datos e inténtalo otra vez.");
    }

    function onLoggedIn() {
        if (authenticated || registrationPending) {
            return;
        }
        if (awaitingLogin) {
            window.setTimeout(requestCharacters, 80);
        }
    }

    function onAuth(args) {
        var packet = args && args.length && args[0] && typeof args[0] === "object" ? args[0] : {};
        var status = String(packet.status || "");
        if (status === "CHARACTERS") {
            clearTimeout(authTimer);
            renderCharacters(packet);
            return;
        }
        if (status === "PUPPET_READY") {
            completeLogin(packet.character, packet.account);
            return;
        }
        if (status === "ERROR") {
            clearTimeout(authTimer);
            awaitingLogin = false;
            registrationPending = false;
            setBusy(false);
            setStatus(String(packet.message || "No se pudo completar esa operación."), "error");
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
        if (/incorrect password|authentication failed|does not exist|no account|unknown account|usage:\s*connect|could not connect/i.test(text)) {
            clearTimeout(authTimer);
            awaitingLogin = false;
            registrationPending = false;
            setBusy(false);
            setStatus("No se pudo validar esa cuenta. Revisa los datos e inténtalo otra vez.", "error");
        }
    }

    function forwardText(args, kwargs) {
        if (window.SizaWorldBookClient && typeof window.SizaWorldBookClient.receiveText === "function") {
            window.SizaWorldBookClient.receiveText(args, kwargs);
        }
    }

    function performLogout() {
        logoutRequested = true;
        forgetSavedAccount();
        resetToLogin("Sesión cerrada.", "info");
        if (window.Evennia && Evennia.isConnected()) {
            Evennia.msg("text", ["quit"], {});
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
            clear.addEventListener("click", function () {
                forgetSavedAccount();
                setStatus("Cuenta recordada borrada.", "info");
                setMenuOpen(false);
            });
        }
        document.addEventListener("click", function (event) {
            if (menu && !menu.contains(event.target)) {
                setMenuOpen(false);
            }
        });
    }

    function init() {
        var loginForm = byId("siza-login-form");
        var createAccount = byId("siza-login-create");
        var creatorForm = byId("siza-creator-form");
        var characterCreate = byId("siza-character-create");
        var characterBack = byId("siza-character-back");
        var creatorBack = byId("siza-creator-back");
        var accountInput = byId("siza-login-username");
        var rememberedAccount = readRememberedAccount();

        setupSessionMenu();
        setPlayerName("", "");
        if (rememberedAccount && accountInput) {
            accountInput.value = rememberedAccount;
        }
        if (loginForm) {
            loginForm.addEventListener("submit", function (event) {
                event.preventDefault();
                submitLogin();
            });
        }
        if (createAccount) {
            createAccount.addEventListener("click", function () {
                currentAccount = "";
                showStep("creator");
                setStatus("Crea tu cuenta y tu primer personaje.", "info");
            });
        }
        if (characterCreate) {
            characterCreate.addEventListener("click", function () {
                showStep("creator");
                setStatus("Define el nuevo personaje.", "info");
            });
        }
        if (characterBack) {
            characterBack.addEventListener("click", function () {
                logoutRequested = true;
                resetToLogin("Introduce otra cuenta para continuar.", "info");
                if (window.Evennia && Evennia.isConnected()) {
                    Evennia.msg("text", ["quit"], {});
                }
            });
        }
        if (creatorBack) {
            creatorBack.addEventListener("click", function () {
                showStep(currentAccount ? "characters" : "login");
                setStatus("", "info");
            });
        }
        if (creatorForm) {
            creatorForm.addEventListener("submit", function (event) {
                event.preventDefault();
                submitCreator();
            });
        }
        if (!window.Evennia) {
            showGate("El cliente del World Engine no está disponible.", "error");
            return;
        }
        Evennia.emitter.on("text", onServerText);
        Evennia.emitter.on("logged_in", onLoggedIn);
        Evennia.emitter.on("siza_auth", onAuth);
        Evennia.emitter.on("connection_open", function () {
            if (!authenticated) {
                showGate("Conexión lista. Introduce tu cuenta.", "info", "login");
            }
        });
        Evennia.emitter.on("connection_close", function () {
            if (!logoutRequested) {
                resetToLogin("La conexión se cerró. Reconectando…", "error");
            }
        });
        Evennia.emitter.on("connection_error", function () {
            resetToLogin("No se pudo conectar con el World Engine.", "error");
        });
        if (Evennia.isConnected()) {
            showGate("Conexión lista. Introduce tu cuenta.", "info", "login");
        }
        window.setTimeout(function () {
            (accountInput || {}).focus && accountInput.focus();
        }, 50);
    }

    window.SizaLoginGate = Object.freeze({
        show: showGate,
        logout: performLogout
    });

    $(document).ready(init);
})();
