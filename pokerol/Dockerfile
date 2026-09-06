FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

RUN python -m evennia --init runtime

COPY overlay/ /app/runtime/
COPY railway_start.sh /app/railway_start.sh
RUN chmod +x /app/railway_start.sh \
    && cat >> /app/runtime/server/conf/settings.py <<'PYSETTINGS'

# --- POKEROL Railway smoke-test settings ---
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
# --- end POKEROL Railway smoke-test settings ---
PYSETTINGS

EXPOSE 4001

CMD ["/app/railway_start.sh"]
