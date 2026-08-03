#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Installa simulate_bus.py come servizio systemd:
#   * parte automaticamente al riavvio della macchina;
#   * gira in background e viene riavviato se crasha;
#   * istanza singola (systemd + lock flock nel wrapper).
#
# Uso:
#   sudo ./deploy/install_service.sh [file.json] [args extra...]
# Esempi:
#   sudo ./deploy/install_service.sh
#   sudo ./deploy/install_service.sh percorsiCassino.json --insecure
# ---------------------------------------------------------------------------
set -euo pipefail

SERVICE_NAME="cassitrack-sim"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ $EUID -ne 0 ]]; then
  echo "Questo script va eseguito come root: sudo $0 ..." >&2
  exit 1
fi

# Percorsi e utente ---------------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-root}"
JSON="${1:-percorsiCassino.json}"
shift || true
EXTRA_ARGS="$*"                       # eventuali argomenti extra (es. --insecure)

echo "Progetto: $PROJECT_DIR"
echo "Utente:   $RUN_USER"
echo "JSON:     $JSON"
[[ -n "$EXTRA_ARGS" ]] && echo "Args:     $EXTRA_ARGS"

# Normalizza i fine-riga del wrapper (se il repo arriva da Windows/CRLF) -----
sed -i 's/\r$//' "$PROJECT_DIR/deploy/run_simulator.sh"
chmod +x "$PROJECT_DIR/deploy/run_simulator.sh"

# 1) virtualenv + dipendenze ------------------------------------------------
VENV="$PROJECT_DIR/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creo il virtualenv in $VENV ..."
  python3 -m venv "$VENV"
fi
echo "Installo/aggiorno le dipendenze (paho-mqtt) ..."
"$VENV/bin/pip" install --quiet --upgrade pip paho-mqtt
if [[ "$RUN_USER" != "root" ]]; then
  chown -R "$RUN_USER:$RUN_USER" "$VENV" 2>/dev/null || true
fi

# 2) scrivo l'unit systemd --------------------------------------------------
cat > "$UNIT_PATH" <<EOF
[Unit]
Description=CassiTrack bus simulator (simulate_bus.py -> MQTT)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR
Environment=SIM_JSON=$JSON
Environment=SIM_ARGS=$EXTRA_ARGS
ExecStart=$PROJECT_DIR/deploy/run_simulator.sh
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
echo "Scritto $UNIT_PATH"

# 3) abilito (avvio al boot) + avvio adesso ---------------------------------
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"

echo
systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
cat <<EOF

Fatto. Il simulatore parte ora e ad ogni riavvio. Comandi utili:
  journalctl -u ${SERVICE_NAME} -f     # log in tempo reale
  systemctl status ${SERVICE_NAME}     # stato
  systemctl restart ${SERVICE_NAME}    # riavvia
  systemctl stop ${SERVICE_NAME}       # ferma (non riparte al boot? resta enabled)
  sudo ${PROJECT_DIR}/deploy/uninstall_service.sh   # rimuove il servizio
EOF
