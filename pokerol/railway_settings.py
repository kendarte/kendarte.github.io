# POKEROL Railway settings.
# This fragment is appended to the generated Evennia settings.py during image build.

import os as _pokerol_os

SERVERNAME = "POKEROL"
ALLOWED_HOSTS = ["*"]

# Persist the Evennia SQLite DB on the Railway volume mounted at /data.
# This keeps accounts, characters and world state across code deploys.
_pokerol_db_path = _pokerol_os.environ.get("POKEROL_DB_PATH", "/data/evennia.db3").strip()
if _pokerol_db_path:
    DATABASES["default"]["NAME"] = _pokerol_db_path

# Railway exposes nginx on 4001. Evennia's own HTTP proxy and websocket
# listeners stay internal to the container and nginx multiplexes both over
# the single public domain.
WEBSERVER_INTERFACES = ["0.0.0.0"]
WEBSERVER_PORTS = [(4003, 4005)]
TELNET_ENABLED = False
SSH_ENABLED = False
WEBCLIENT_ENABLED = True
WEBSOCKET_CLIENT_ENABLED = True
WEBSOCKET_CLIENT_INTERFACE = "0.0.0.0"
WEBSOCKET_CLIENT_PORT = 4002

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_pokerol_public_domain = _pokerol_os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _pokerol_public_domain:
    CSRF_TRUSTED_ORIGINS = [f"https://{_pokerol_public_domain}"]
    WEBSOCKET_CLIENT_URL = f"wss://{_pokerol_public_domain}/ws"
else:
    WEBSOCKET_CLIENT_URL = None
