#!/bin/sh
set -eu

cd /app/runtime

export POKEROL_SOLO_TEST_MODE="${POKEROL_SOLO_TEST_MODE:-1}"
export PORT="${PORT:-4001}"

echo "[POKEROL] Migrando DB de prueba..."
python -m evennia migrate

echo "[POKEROL] Iniciando Evennia en puerto ${PORT}..."
exec python -m evennia start --log
