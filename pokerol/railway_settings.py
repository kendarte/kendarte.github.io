# POKEROL Railway smoke-test settings.
# This fragment is appended to the generated Evennia settings.py during image build.

import os as _pokerol_os

SERVERNAME = "POKEROL"
ALLOWED_HOSTS = ["*"]
WEBSERVER_INTERFACES = ["0.0.0.0"]
WEBSERVER_PORTS = [(int(_pokerol_os.environ.get("PORT", "4001")), 4005)]
TELNET_ENABLED = False
SSH_ENABLED = False
WEBSOCKET_CLIENT_ENABLED = False
WEBCLIENT_ENABLED = True
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_pokerol_public_domain = _pokerol_os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _pokerol_public_domain:
    CSRF_TRUSTED_ORIGINS = [f"https://{_pokerol_public_domain}"]
