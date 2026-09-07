#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RUNTIME="$ROOT/runtime"
DATA_DIR="${POKEROL_DATA_DIR:-/data}"
PERSISTENT_DB="$DATA_DIR/evennia.db3"
RUNTIME_DB="$RUNTIME/server/evennia.db3"
ASSET_DIR="${POKEROL_ASSET_ROOT:-$DATA_DIR/pokerol_assets}"

export POKEROL_SOLO_TEST_MODE="${POKEROL_SOLO_TEST_MODE:-1}"
export PORT="${PORT:-4001}"
export POKEROL_DATA_DIR="$DATA_DIR"
export POKEROL_ASSET_ROOT="$ASSET_DIR"

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

if [ ! -d "$DATA_DIR" ] || [ ! -w "$DATA_DIR" ]; then
  echo "[POKEROL] ERROR: volumen persistente no disponible en $DATA_DIR" >&2
  exit 1
fi

# Persistent project assets must be traversable/readable by the nginx worker.
# This fixes old uploads too, without changing the database file permissions.
mkdir -p "$ASSET_DIR/rooms" "$ASSET_DIR/entities" "$ASSET_DIR/players" "$ASSET_DIR/hotspots" "$ASSET_DIR/.tmp"
chmod 755 "$DATA_DIR" 2>/dev/null || true
find "$ASSET_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
find "$ASSET_DIR" -type f -exec chmod 644 {} \; 2>/dev/null || true

echo "[POKEROL] Assets persistentes activos: $ASSET_DIR"

# First persistent boot: preserve a runtime DB if one exists.
# Subsequent deploys always keep /data/evennia.db3 untouched.
if [ ! -f "$PERSISTENT_DB" ] && [ -f "$RUNTIME_DB" ]; then
  echo "[POKEROL] Inicializando DB persistente desde runtime existente..."
  cp "$RUNTIME_DB" "$PERSISTENT_DB"
fi

echo "[POKEROL] DB persistente activa: $PERSISTENT_DB"

SETTINGS="$RUNTIME/server/conf/settings.py"
if ! grep -q "POKEROL_RAILWAY_SETTINGS" "$SETTINGS" 2>/dev/null; then
  printf '\n# POKEROL_RAILWAY_SETTINGS\n' >> "$SETTINGS"
  if [ -f "$ROOT/railway_settings.py" ]; then
    cat "$ROOT/railway_settings.py" >> "$SETTINGS"
  fi
fi

cd "$RUNTIME"
echo "[POKEROL] Migrando DB persistente..."
python -m evennia migrate

if command -v nginx >/dev/null 2>&1; then
  echo "[POKEROL] Iniciando proxy HTTP/WebSocket en puerto ${PORT}..."
  nginx -t
  nginx
fi

echo "[POKEROL] Iniciando Evennia HTTP interno 4003 + WebSocket 4002..."
exec python -m evennia start --log
