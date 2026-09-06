#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RUNTIME="$ROOT/runtime"

export POKEROL_SOLO_TEST_MODE="${POKEROL_SOLO_TEST_MODE:-1}"
export PORT="${PORT:-4001}"

if [ ! -d "$RUNTIME/server" ]; then
  echo "[POKEROL] Creando runtime Evennia..."
  cd "$ROOT"
  python -m evennia --init runtime
fi

# Railpack runs from repository contents and has overlay/. Docker already
# copied overlay/ into runtime at image-build time.
if [ -d "$ROOT/overlay" ]; then
  echo "[POKEROL] Aplicando overlay desde repo..."
  cp -R "$ROOT/overlay/." "$RUNTIME/"
else
  echo "[POKEROL] Overlay ya incluido en runtime Docker."
fi

SETTINGS="$RUNTIME/server/conf/settings.py"
if ! grep -q "POKEROL_RAILWAY_SETTINGS" "$SETTINGS" 2>/dev/null; then
  printf '\n# POKEROL_RAILWAY_SETTINGS\n' >> "$SETTINGS"
  if [ -f "$ROOT/railway_settings.py" ]; then
    cat "$ROOT/railway_settings.py" >> "$SETTINGS"
  fi
fi

cd "$RUNTIME"
echo "[POKEROL] Migrando DB de prueba..."
python -m evennia migrate

if command -v nginx >/dev/null 2>&1; then
  echo "[POKEROL] Iniciando proxy HTTP/WebSocket en puerto ${PORT}..."
  nginx -t
  nginx
fi

echo "[POKEROL] Iniciando Evennia HTTP interno 4003 + WebSocket 4002..."
exec python -m evennia start --log
