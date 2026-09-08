(function () {
  "use strict";

  var BUILD = "0.1.0-local-websocket-bootstrap";
  var reconnectTimer = null;
  var reconnectAttempts = 0;
  var reconnectDelays = [700, 1400, 2800, 5000, 8000];

  function byId(id) {
    return document.getElementById(id);
  }

  function setConnectionState(state, detail) {
    var dialogue = byId("pk-dialogue-text");
    var speaker = byId("pk-speaker");
    var room = byId("pk-room-name");
    if (speaker) speaker.textContent = "SISTEMA";
    if (dialogue && detail) dialogue.textContent = detail;
    if (room && state === "error") room.textContent = "Reconectando con Kanto…";
  }

  function createEmitter() {
    var listeners = Object.create(null);

    function on(name, listener) {
      if (typeof listener !== "function") return;
      var key = String(name || "");
      if (!key) return;
      var group = listeners[key] || (listeners[key] = []);
      if (group.indexOf(listener) === -1) group.push(listener);
    }

    function off(name, listener) {
      var key = String(name || "");
      var group = listeners[key];
      if (!group) return;
      if (typeof listener !== "function") {
        delete listeners[key];
        return;
      }
      var index = group.indexOf(listener);
      if (index !== -1) group.splice(index, 1);
      if (!group.length) delete listeners[key];
    }

    function notify(group, args) {
      group.slice().forEach(function (listener) {
        try {
          listener.apply(null, args);
        } catch (error) {
          if (window.console && console.error) console.error("[POKEROL transport] listener failed", error);
        }
      });
    }

    function emit(name, args, kwargs) {
      var key = String(name || "");
      var group = listeners[key];
      if (group && group.length) {
        notify(group, [args || [], kwargs || {}]);
        return;
      }
      var fallback = listeners.default;
      if (fallback && fallback.length) notify(fallback, [key, args || [], kwargs || {}]);
    }

    return { on: on, off: off, emit: emit };
  }

  function createWebSocketConnection() {
    var socket = null;
    var open = false;
    var connecting = false;

    function socketUrl() {
      var base = String(window.wsurl || "").trim();
      var session = window.csessid ? String(window.csessid) : "";
      var client = window.cuid ? String(window.cuid) : "";
      var browserName = typeof window.browser === "string" ? window.browser : "browser";
      return base + "?" + session + "&" + client + "&" + browserName;
    }

    function scheduleReconnect() {
      if (reconnectTimer || reconnectAttempts >= reconnectDelays.length) return;
      var delay = reconnectDelays[reconnectAttempts++];
      reconnectTimer = window.setTimeout(function () {
        reconnectTimer = null;
        connect();
      }, delay);
    }

    function connect() {
      if (connecting || open) return;
      if (!window.WebSocket || !window.wsactive || !window.wsurl) {
        window.Evennia.emit("connection_error", ["websocket"], { reason: "WebSocket no disponible" });
        setConnectionState("error", "Este navegador no pudo abrir la conexión con POKEROL.");
        return;
      }

      connecting = true;
      setConnectionState("connecting", "Conectando con el mundo…");
      try {
        socket = new window.WebSocket(socketUrl(), ["v1.evennia.com"]);
      } catch (error) {
        connecting = false;
        window.Evennia.emit("connection_error", ["websocket"], { error: String(error) });
        setConnectionState("error", "No se pudo abrir la conexión. Reintentando…");
        scheduleReconnect();
        return;
      }

      socket.onopen = function () {
        connecting = false;
        open = true;
        reconnectAttempts = 0;
        setConnectionState("open", "Conectado. Preparando el mundo…");
        window.Evennia.emit("connection_open", ["websocket"], {});
      };

      socket.onmessage = function (event) {
        try {
          var data = JSON.parse(String(event.data || ""));
          if (Array.isArray(data) && data.length >= 3) window.Evennia.emit(data[0], data[1], data[2]);
        } catch (error) {
          if (window.console && console.error) console.error("[POKEROL transport] invalid server packet", error);
        }
      };

      socket.onerror = function () {
        if (open || connecting) {
          window.Evennia.emit("connection_error", ["websocket"], { reason: "socket error" });
        }
      };

      socket.onclose = function (event) {
        var wasOpen = open;
        socket = null;
        open = false;
        connecting = false;
        window.Evennia.emit(wasOpen ? "connection_close" : "connection_error", ["websocket"], event || {});
        setConnectionState("error", "La conexión se interrumpió. Reintentando…");
        scheduleReconnect();
      };
    }

    function msg(data) {
      if (!socket || !open) throw new Error("POKEROL todavía no está conectado.");
      socket.send(JSON.stringify(data));
    }

    function close() {
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      reconnectAttempts = reconnectDelays.length;
      if (socket && socket.readyState === window.WebSocket.OPEN) socket.close(1000, "client closed");
      else if (socket) socket.close();
      socket = null;
      open = false;
      connecting = false;
    }

    return { connect: connect, msg: msg, close: close, isOpen: function () { return open; } };
  }

  function sendTypedAction() {
    var field = byId("inputfield");
    if (!field) return;
    var command = String(field.value || "").trim();
    if (!command) return;
    if (!window.Evennia || !window.Evennia.isConnected || !window.Evennia.isConnected()) {
      setConnectionState("error", "La conexión todavía no está lista. Reintentando…");
      if (window.Evennia && typeof window.Evennia.connect === "function") window.Evennia.connect();
      return;
    }
    try {
      window.Evennia.msg("text", [command], {});
      field.value = "";
    } catch (error) {
      setConnectionState("error", "No se pudo enviar la acción. Reintentando…");
    }
  }

  function bindInput() {
    var field = byId("inputfield");
    var send = byId("inputsend");
    if (send && send.dataset.pkTransportBound !== "1") {
      send.dataset.pkTransportBound = "1";
      send.addEventListener("click", sendTypedAction);
    }
    if (field && field.dataset.pkTransportBound !== "1") {
      field.dataset.pkTransportBound = "1";
      field.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          sendTypedAction();
        }
      });
    }
  }

  function init() {
    if (!window.Evennia || typeof window.Evennia.init !== "function") {
      setConnectionState("error", "El cliente de POKEROL no pudo iniciar.");
      return;
    }
    window.Evennia.init({ emitter: createEmitter(), connection: createWebSocketConnection() });
    bindInput();
  }

  window.PokerolTransportBootstrapV01 = Object.freeze({ BUILD: BUILD, send: sendTypedAction });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
