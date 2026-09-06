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

# Always refresh the game overlay from the repository.
echo "[POKEROL] Aplicando overlay..."
cp -R "$ROOT/overlay/." "$RUNTIME/"

# Railway-specific ports/settings are appended only once per fresh runtime.
SETTINGS="$RUNTIME/server/conf/settings.py"
if ! grep -q "POKEROL_RAILWAY_SETTINGS" "$SETTINGS" 2>/dev/null; then
  printf '\n# POKEROL_RAILWAY_SETTINGS\n' >> "$SETTINGS"
  cat "$ROOT/railway_settings.py" >> "$SETTINGS"
fi

cd "$RUNTIME"
echo "[POKEROL] Migrando DB de prueba..."
python -m evennia migrate

echo "[POKEROL] Iniciando Evennia en puerto ${PORT}..."
exec python -m evennia start --log
