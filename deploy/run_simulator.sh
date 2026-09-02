#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Wrapper di avvio del simulatore CassiTrack.
# Garantisce UNA SOLA istanza tramite flock: se un'altra copia (systemd o
# lanciata a mano) tiene gia' il lock, questo processo esce subito.
# Usato da systemd (vedi cassitrack-sim.service) ma eseguibile anche a mano.
#
# Variabili d'ambiente opzionali:
#   SIM_PYTHON  interprete Python        (default: <progetto>/.venv/bin/python)
#   SIM_JSON    file dei percorsi        (default: percorsiCassinoSettembre2026.json)
#   SIM_ARGS    argomenti extra          (es. "--insecure --send-interval 30")
#   SIM_LOCK    file di lock             (default: /tmp/cassitrack-sim.lock)
# ---------------------------------------------------------------------------
set -euo pipefail

# Cartella del progetto = quella superiore a deploy/
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON="${SIM_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
# I percorsi di settembre 2026 sono quelli coperti da vehicle_ids.json.
JSON="${SIM_JSON:-percorsiCassinoSettembre2026.json}"
LOCKFILE="${SIM_LOCK:-/tmp/cassitrack-sim.lock}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Interprete Python non trovato: $PYTHON" >&2
  echo "Crea il virtualenv (python3 -m venv .venv) o imposta SIM_PYTHON." >&2
  exit 1
fi
if [[ ! -f "$JSON" ]]; then
  echo "File dei percorsi non trovato: $PROJECT_DIR/$JSON" >&2
  exit 1
fi

# flock -n: acquisisce il lock in modo NON bloccante e lancia il simulatore.
# Se il lock e' gia' preso -> esce con codice 1 (istanza singola garantita).
exec flock -n "$LOCKFILE" "$PYTHON" simulate_bus.py "$JSON" ${SIM_ARGS:-}
