#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RUNTIME="$ROOT/runtime"
TEST_MODE="${POKEROL_SOLO_TEST_MODE:-0}"
DATA_DIR="${POKEROL_DATA_DIR:-/data}"

# Production must always use the persistent Railway volume. The GitHub Actions
# smoke container intentionally has no /data mount, so only explicit test mode
# may fall back to an isolated ephemeral directory.
if [ ! -d "$DATA_DIR" ] || [ ! -w "$DATA_DIR" ]; then
  if [ "$TEST_MODE" = "1" ]; then
    DATA_DIR="${POKEROL_SMOKE_DATA_DIR:-/tmp/pokerol-smoke-data}"
    mkdir -p "$DATA_DIR"
    echo "[POKEROL] Smoke test: usando almacenamiento efímero en $DATA_DIR"
  else
    echo "[POKEROL] ERROR: volumen persistente no disponible en $DATA_DIR" >&2
    exit 1
  fi
fi

PERSISTENT_DB="$DATA_DIR/evennia.db3"
RUNTIME_DB="$RUNTIME/server/evennia.db3"
ASSET_DIR="${POKEROL_ASSET_ROOT:-$DATA_DIR/pokerol_assets}"

export POKEROL_SOLO_TEST_MODE="$TEST_MODE"
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

# Project assets live beside the selected data store. In production this is
# /data/pokerol_assets; in smoke mode it is the isolated temporary directory.
mkdir -p "$ASSET_DIR/rooms" "$ASSET_DIR/entities" "$ASSET_DIR/players" "$ASSET_DIR/hotspots" "$ASSET_DIR/pokemon" "$ASSET_DIR/.tmp"
chmod 755 "$DATA_DIR" 2>/dev/null || true
find "$ASSET_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
find "$ASSET_DIR" -type f -exec chmod 644 {} \; 2>/dev/null || true

echo "[POKEROL] Assets persistentes activos: $ASSET_DIR"

# First boot for the selected data store: preserve a runtime DB if one exists.
# Production deploys keep /data/evennia.db3 untouched.
if [ ! -f "$PERSISTENT_DB" ] && [ -f "$RUNTIME_DB" ]; then
  echo "[POKEROL] Inicializando DB desde runtime existente..."
  cp "$RUNTIME_DB" "$PERSISTENT_DB"
fi

echo "[POKEROL] DB activa: $PERSISTENT_DB"

SETTINGS="$RUNTIME/server/conf/settings.py"
if ! grep -q "POKEROL_RAILWAY_SETTINGS" "$SETTINGS" 2>/dev/null; then
  printf '\n# POKEROL_RAILWAY_SETTINGS\n' >> "$SETTINGS"
  if [ -f "$ROOT/railway_settings.py" ]; then
    cat "$ROOT/railway_settings.py" >> "$SETTINGS"
  fi
fi

cd "$RUNTIME"
echo "[POKEROL] Migrando DB..."
python -m evennia migrate

if command -v nginx >/dev/null 2>&1; then
  echo "[POKEROL] Iniciando proxy HTTP/WebSocket en puerto ${PORT}..."
  nginx -t
  nginx
fi

if [ "${POKEROL_ASSET_SMOKE_TEST:-0}" = "1" ] && [ -f "$RUNTIME/production_asset_smoke.py" ]; then
  echo "[POKEROL] Smoke test Fakemon assets habilitado para este arranque."
  (
    cd "$RUNTIME"
    python production_asset_smoke.py
  ) &
fi

echo "[POKEROL] Iniciando Evennia HTTP interno 4003 + WebSocket 4002..."
exec python -m evennia start --log
