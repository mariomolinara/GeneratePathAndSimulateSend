# Deploy come servizio Linux (systemd)

Esegue `simulate_bus.py` come **servizio di sistema**:

- parte **automaticamente al riavvio** della macchina;
- gira **in background** e viene **riavviato** se il processo termina/crasha;
- **istanza singola** garantita: da systemd (una sola unità attiva) e in più da un
  lock `flock` nel wrapper, che impedisce una seconda copia anche se lanciata a mano.

## File

| File | Ruolo |
|------|-------|
| `run_simulator.sh`     | wrapper: acquisisce il lock e avvia il simulatore |
| `install_service.sh`   | crea venv+dipendenze, scrive l'unit systemd, abilita e avvia |
| `uninstall_service.sh` | ferma, disabilita e rimuove il servizio |

## Installazione

Sulla macchina Linux, dentro la cartella del progetto:

```bash
# se i file arrivano da Windows, normalizza una volta i fine-riga:
sudo apt-get install -y dos2unix && dos2unix deploy/*.sh   # oppure: sed -i 's/\r$//' deploy/*.sh

sudo ./deploy/install_service.sh                       # usa percorsiCassino.json
# oppure specificando file e argomenti extra:
sudo ./deploy/install_service.sh percorsiCassino.json --insecure
```

Il servizio si chiama **`cassitrack-sim`**.

## Gestione

```bash
journalctl -u cassitrack-sim -f      # log in tempo reale
systemctl status  cassitrack-sim     # stato
systemctl restart cassitrack-sim     # riavvia
systemctl stop    cassitrack-sim     # ferma (resta abilitato al boot)
systemctl disable cassitrack-sim     # non parte piu' al boot
sudo ./deploy/uninstall_service.sh   # rimozione completa
```

## Cambiare il file JSON dei percorsi e riavviare

### Caso 1 — hai modificato lo *stesso* file già in uso
Se hai solo aggiornato il contenuto del JSON (es. rigenerato `percorsiCassino.json`, o
modificato i tracciati con `crea_path.html` e sovrascritto il file), basta **riavviare**:

```bash
sudo systemctl restart cassitrack-sim
journalctl -u cassitrack-sim -f          # verifica che riparta senza errori
```

### Caso 2 — vuoi usare un file JSON *diverso*
Il nome del file è nella riga `Environment=SIM_JSON=...` dell'unit. Due modi:

**A) Reinstallando (più semplice)** — rilancia l'installer col nuovo file: riscrive l'unit
e riavvia da solo.
```bash
cd ~/cassitrack_simulator
sudo bash deploy/install_service.sh nuovo_percorso.json
# con argomenti extra, es.:  sudo bash deploy/install_service.sh nuovo_percorso.json --insecure
```

**B) Modificando l'unit a mano**
```bash
sudo systemctl edit --full cassitrack-sim      # cambia SIM_JSON=... (e SIM_ARGS=... se serve)
sudo systemctl daemon-reload
sudo systemctl restart cassitrack-sim
```

> Il file JSON deve trovarsi nella cartella del progetto (quella indicata da
> `WorkingDirectory` nell'unit, cioè la cartella padre di `deploy/`). Puoi indicare un
> percorso relativo a quella cartella (es. `percorsiCassino.json`) o assoluto.

## Note

- **Istanza singola**: se il servizio è attivo e lanci `./deploy/run_simulator.sh` a mano,
  il secondo processo esce subito (codice 1) senza avviare un secondo simulatore.
- **Argomenti / file**: modificabili in `Environment=SIM_JSON=...` e `Environment=SIM_ARGS=...`
  dentro `/etc/systemd/system/cassitrack-sim.service` (poi `systemctl daemon-reload &&
  systemctl restart cassitrack-sim`).
- **Utente**: il servizio gira come l'utente che ha invocato `sudo` (non root), con
  `WorkingDirectory` sulla cartella del progetto.
