#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Rimuove il servizio systemd del simulatore CassiTrack.
# Uso: sudo ./deploy/uninstall_service.sh
# ---------------------------------------------------------------------------
set -euo pipefail

SERVICE_NAME="cassitrack-sim"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ $EUID -ne 0 ]]; then
  echo "Questo script va eseguito come root: sudo $0" >&2
  exit 1
fi

# disable --now = ferma il servizio e ne toglie l'avvio automatico al boot
systemctl disable --now "${SERVICE_NAME}.service" 2>/dev/null || true
rm -f "$UNIT_PATH"
systemctl daemon-reload
systemctl reset-failed "${SERVICE_NAME}.service" 2>/dev/null || true

echo "Servizio ${SERVICE_NAME} rimosso."
